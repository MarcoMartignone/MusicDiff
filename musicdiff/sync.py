"""
One-way sync orchestration: Spotify → Deezer.

Syncs selected Spotify playlists to Deezer with full overwrite.
"""

from dataclasses import dataclass
from typing import List, Tuple
from enum import Enum
import time

from musicdiff.matcher import TrackMatcher


class SyncMode(Enum):
    """Sync modes."""
    NORMAL = "normal"        # Sync selected playlists
    DRY_RUN = "dry_run"      # Show what would be synced
    AUTO = "auto"            # Same as NORMAL (kept for compatibility)


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    playlists_created: int
    playlists_updated: int
    playlists_deleted: int
    failed_operations: List[Tuple[str, str]]  # (playlist_name, error)
    duration_seconds: float

    @property
    def total_synced(self) -> int:
        """Total playlists successfully synced."""
        return self.playlists_created + self.playlists_updated

    def summary(self) -> str:
        """Return summary string."""
        if self.success:
            return f"✓ Sync complete: {self.total_synced} playlists synced ({self.playlists_created} created, {self.playlists_updated} updated, {self.playlists_deleted} deleted)"
        else:
            return f"⚠ Sync partial: {self.total_synced} synced, {len(self.failed_operations)} failed"


class SyncEngine:
    """Orchestrates one-way Spotify → Deezer sync."""

    def __init__(self, spotify_client, deezer_client, database, ui):
        """Initialize sync engine.

        Args:
            spotify_client: SpotifyClient instance
            deezer_client: DeezerClient instance
            database: Database instance
            ui: UI instance for user interaction
        """
        self.spotify = spotify_client
        self.deezer = deezer_client
        self.db = database
        self.ui = ui
        self.matcher = TrackMatcher()

    def sync(self, mode: SyncMode = SyncMode.NORMAL) -> SyncResult:
        """Perform one-way synchronization from Spotify to Deezer.

        Args:
            mode: Sync mode (normal or dry-run)

        Returns:
            SyncResult with operation details
        """
        start_time = time.time()
        created = 0
        updated = 0
        deleted = 0
        failed = []

        try:
            # Get selected Spotify playlists from database
            selected = self.db.get_selected_playlists()

            if not selected:
                self.ui.print_warning("No playlists selected for sync. Run 'musicdiff select' first.")
                duration = time.time() - start_time
                return SyncResult(
                    success=True,
                    playlists_created=0,
                    playlists_updated=0,
                    playlists_deleted=0,
                    failed_operations=[],
                    duration_seconds=duration
                )

            # Build preview data
            to_create = []
            to_update = []
            to_delete = []

            # Check what needs to be created/updated
            self.ui.print_info("🔍 Checking playlist status on Deezer...")

            for playlist_info in selected:
                spotify_id = playlist_info['spotify_id']
                name = playlist_info['name']
                track_count = playlist_info.get('track_count', 0)

                # Check if already synced in database
                synced = self.db.get_synced_playlist(spotify_id)

                if synced:
                    # Check if the synced playlist still exists on Deezer
                    playlist_exists = self._check_deezer_playlist_exists(synced['deezer_id'])

                    if playlist_exists:
                        # Will update existing synced playlist
                        to_update.append((name, track_count, synced['deezer_id']))
                    else:
                        # Synced playlist deleted - check if another with same name exists
                        existing_id = self._find_existing_deezer_playlist(name)
                        if existing_id:
                            # Found another playlist with same name - will update it
                            to_update.append((name, track_count, existing_id))
                        else:
                            # No existing playlist found - will create new
                            to_create.append((name, track_count))
                else:
                    # Not synced - check if playlist with this name already exists
                    existing_id = self._find_existing_deezer_playlist(name)
                    if existing_id:
                        # Found existing playlist with same name - will update it
                        to_update.append((name, track_count, existing_id))
                    else:
                        # No existing playlist found - will create new
                        to_create.append((name, track_count))

            # Check for deletions (synced playlists no longer selected)
            spotify_playlist_ids = [p['spotify_id'] for p in selected]
            all_synced = self.db.get_all_synced_playlists()
            for synced_playlist in all_synced:
                if synced_playlist['spotify_id'] not in spotify_playlist_ids:
                    to_delete.append((synced_playlist['name'], synced_playlist['deezer_id']))

            # For playlists marked to update, check if they actually need updating
            # by comparing Spotify vs Deezer track lists
            if to_update and not to_create and not to_delete:
                self.ui.print_info("📊 Comparing playlists to detect changes...")

                # Fetch Spotify playlists to compare
                spotify_playlists_map = {}
                for spotify_id in spotify_playlist_ids:
                    try:
                        sp_playlist = self.spotify.fetch_playlist_by_id(spotify_id)
                        if sp_playlist:
                            spotify_playlists_map[sp_playlist.spotify_id] = sp_playlist
                    except Exception:
                        pass  # If fetch fails, we'll sync anyway to be safe

                # Check each playlist for actual changes
                actually_need_update = []
                for name, track_count, deezer_id in to_update:
                    # Find the corresponding Spotify playlist
                    spotify_playlist = None
                    for sp_id, sp_pl in spotify_playlists_map.items():
                        if sp_pl.name == name:
                            spotify_playlist = sp_pl
                            break

                    if not spotify_playlist:
                        # Can't compare, assume needs update
                        actually_need_update.append((name, track_count, deezer_id))
                        continue

                    # Fetch Deezer playlist
                    try:
                        deezer_playlist = self._fetch_deezer_playlist(deezer_id)
                        if not deezer_playlist:
                            # Can't fetch, assume needs update
                            actually_need_update.append((name, track_count, deezer_id))
                            continue

                        # Compare track counts first (fast check)
                        if len(spotify_playlist.tracks) != len(deezer_playlist.tracks):
                            actually_need_update.append((name, track_count, deezer_id))
                            continue

                        # Compare tracks by ISRC (reliable cross-platform identifier)
                        spotify_isrcs = [t.isrc for t in spotify_playlist.tracks if t.isrc]
                        deezer_isrcs = [t.isrc for t in deezer_playlist.tracks if t.isrc]

                        if spotify_isrcs != deezer_isrcs:
                            # Tracks are different
                            actually_need_update.append((name, track_count, deezer_id))
                        # else: Playlists are identical, skip it

                    except Exception:
                        # If comparison fails, assume needs update to be safe
                        actually_need_update.append((name, track_count, deezer_id))

                to_update = actually_need_update

            # If nothing to do, show success message and exit
            if not to_create and not to_update and not to_delete:
                self.ui.print_success("✓ All playlists are already in sync! Nothing to do.")
                duration = time.time() - start_time
                return SyncResult(
                    success=True,
                    playlists_created=0,
                    playlists_updated=0,
                    playlists_deleted=0,
                    failed_operations=[],
                    duration_seconds=duration
                )

            # Show preview and get confirmation
            if not self.ui.show_sync_preview_detailed(to_create, to_update, to_delete):
                self.ui.print_info("Sync cancelled")
                duration = time.time() - start_time
                return SyncResult(
                    success=True,
                    playlists_created=0,
                    playlists_updated=0,
                    playlists_deleted=0,
                    failed_operations=[],
                    duration_seconds=duration
                )

            # Fetch selected playlists from Spotify
            spotify_playlists = self._fetch_spotify_playlists(spotify_playlist_ids)

            if mode == SyncMode.DRY_RUN:
                # Show what would be synced
                self._show_dry_run(spotify_playlists)
                duration = time.time() - start_time
                return SyncResult(
                    success=True,
                    playlists_created=0,
                    playlists_updated=0,
                    playlists_deleted=0,
                    failed_operations=[],
                    duration_seconds=duration
                )

            # Sync each selected playlist
            self.ui.print_info(f"\n🔄 Starting sync of {len(spotify_playlists)} playlists...\n")

            with self.ui.create_progress("Syncing playlists") as progress:
                task = progress.add_task("Processing...", total=len(spotify_playlists))

                for i, sp_playlist in enumerate(spotify_playlists, 1):
                    try:
                        progress.update(
                            task,
                            completed=i-1,
                            description=f"🎶 Syncing: {sp_playlist.name[:40]}... ({i}/{len(spotify_playlists)})"
                        )

                        # Check if already synced to Deezer
                        synced = self.db.get_synced_playlist(sp_playlist.spotify_id)

                        if synced:
                            # Update existing Deezer playlist (full overwrite)
                            match_stats = self._update_deezer_playlist(synced['deezer_id'], sp_playlist, progress)
                            updated += 1

                            # Show match statistics
                            if match_stats:
                                self.ui.print_success(
                                    f"Updated: {sp_playlist.name} - "
                                    f"{match_stats['matched']}/{match_stats['total']} tracks matched"
                                )
                        else:
                            # Check if playlist with same name already exists on Deezer
                            existing_deezer_id = self._find_existing_deezer_playlist(sp_playlist.name)

                            if existing_deezer_id:
                                # Reuse existing playlist
                                self.ui.print_info(f"Found existing playlist '{sp_playlist.name}' on Deezer - reusing it")
                                match_stats = self._update_deezer_playlist(existing_deezer_id, sp_playlist, progress)

                                # Track it in database
                                self.db.upsert_synced_playlist(
                                    spotify_id=sp_playlist.spotify_id,
                                    deezer_id=existing_deezer_id,
                                    name=sp_playlist.name,
                                    track_count=len(sp_playlist.tracks)
                                )
                                updated += 1

                                # Show match statistics
                                if match_stats:
                                    self.ui.print_success(
                                        f"Updated: {sp_playlist.name} - "
                                        f"{match_stats['matched']}/{match_stats['total']} tracks matched"
                                    )
                            else:
                                # Create new Deezer playlist
                                deezer_id, match_stats = self._create_deezer_playlist(sp_playlist, progress)
                                # Track it in database
                                self.db.upsert_synced_playlist(
                                    spotify_id=sp_playlist.spotify_id,
                                    deezer_id=deezer_id,
                                    name=sp_playlist.name,
                                    track_count=len(sp_playlist.tracks)
                                )
                                created += 1

                                # Show match statistics
                                if match_stats:
                                    self.ui.print_success(
                                        f"Created: {sp_playlist.name} - "
                                        f"{match_stats['matched']}/{match_stats['total']} tracks matched"
                                    )

                        # Mark as synced
                        self.db.mark_playlist_synced(sp_playlist.spotify_id)

                    except Exception as e:
                        failed.append((sp_playlist.name, str(e)))
                        self.ui.print_error(f"Failed to sync '{sp_playlist.name}': {e}")

                    progress.update(task, completed=i)

            # Delete deselected playlists from Deezer
            deleted = self._delete_deselected_playlists(spotify_playlist_ids)

            # Log sync
            duration = time.time() - start_time
            result = SyncResult(
                success=len(failed) == 0,
                playlists_created=created,
                playlists_updated=updated,
                playlists_deleted=deleted,
                failed_operations=failed,
                duration_seconds=duration
            )

            self.db.add_sync_log(
                status='success' if result.success else 'partial',
                playlists_synced=result.total_synced,
                playlists_created=created,
                playlists_updated=updated,
                playlists_deleted=deleted,
                details={'failed': [f[0] for f in failed]},
                duration=duration
            )

            # Show result
            if result.success:
                self.ui.print_success(result.summary())
            else:
                self.ui.print_warning(result.summary())
                for playlist_name, error in failed:
                    self.ui.print_error(f"  {playlist_name}: {error}")

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.ui.print_error(f"Sync failed: {e}")
            return SyncResult(
                success=False,
                playlists_created=created,
                playlists_updated=updated,
                playlists_deleted=deleted,
                failed_operations=failed,
                duration_seconds=duration
            )

    def _fetch_spotify_playlists(self, playlist_ids: List[str]) -> List:
        """Fetch Spotify playlists by ID with progress.

        Args:
            playlist_ids: List of Spotify playlist IDs

        Returns:
            List of Playlist objects with tracks
        """
        playlists = []
        total = len(playlist_ids)

        self.ui.print_info(f"🎵 Fetching {total} playlists from Spotify...")

        with self.ui.create_progress("Fetching playlists") as progress:
            task = progress.add_task("Loading...", total=total)

            for i, playlist_id in enumerate(playlist_ids, 1):
                try:
                    # Fetch single playlist by ID
                    playlist = self.spotify.fetch_playlist_by_id(playlist_id)
                    if playlist:
                        playlists.append(playlist)
                        progress.update(
                            task,
                            completed=i,
                            description=f"🎵 Fetching: {playlist.name[:40]}... ({i}/{total})"
                        )
                    else:
                        progress.update(task, advance=1)
                except Exception as e:
                    self.ui.print_error(f"Failed to fetch playlist {playlist_id}: {e}")
                    progress.update(task, advance=1)

        return playlists

    def _create_deezer_playlist(self, spotify_playlist, progress=None):
        """Create new playlist on Deezer.

        Args:
            spotify_playlist: Spotify Playlist object
            progress: Optional progress object for updates

        Returns:
            Tuple of (Deezer playlist ID, match statistics dict)
        """
        # Create playlist (always private to ensure it's in user's library)
        deezer_id = self.deezer.create_playlist(
            name=spotify_playlist.name,
            description=spotify_playlist.description,
            public=False  # Always create private playlists to ensure they're accessible
        )

        # Add tracks
        match_stats = {'total': 0, 'matched': 0, 'failed': 0}
        if spotify_playlist.tracks:
            track_ids, match_stats = self._match_tracks_to_deezer(
                spotify_playlist.tracks,
                spotify_playlist.name
            )
            if track_ids:
                self.deezer.add_tracks_to_playlist(deezer_id, track_ids)

        return deezer_id, match_stats

    def _update_deezer_playlist(self, deezer_id: str, spotify_playlist, progress=None):
        """Update Deezer playlist with full overwrite from Spotify.

        Args:
            deezer_id: Deezer playlist ID
            spotify_playlist: Spotify Playlist object
            progress: Optional progress object for updates

        Returns:
            Match statistics dict
        """
        # Check if playlist still exists on Deezer
        playlist_exists = self._check_deezer_playlist_exists(deezer_id)

        if not playlist_exists:
            # Playlist was deleted or doesn't exist - check if another playlist with same name exists
            existing_deezer_id = self._find_existing_deezer_playlist(spotify_playlist.name)

            if existing_deezer_id:
                # Found existing playlist with same name - reuse it
                self.ui.print_info(f"Found existing playlist '{spotify_playlist.name}' on Deezer - reusing it")

                # Update the database with the found Deezer ID
                self.db.upsert_synced_playlist(
                    spotify_id=spotify_playlist.spotify_id,
                    deezer_id=existing_deezer_id,
                    name=spotify_playlist.name,
                    track_count=len(spotify_playlist.tracks)
                )

                # Now update that playlist
                return self._update_deezer_playlist(existing_deezer_id, spotify_playlist, progress)
            else:
                # No existing playlist found - create new one
                self.ui.print_warning(f"Playlist '{spotify_playlist.name}' no longer exists on Deezer - creating new one...")
                new_deezer_id, match_stats = self._create_deezer_playlist(spotify_playlist, progress)

                # Update the database with new Deezer ID
                self.db.upsert_synced_playlist(
                    spotify_id=spotify_playlist.spotify_id,
                    deezer_id=new_deezer_id,
                    name=spotify_playlist.name,
                    track_count=len(spotify_playlist.tracks)
                )

                return match_stats

        # Playlist exists - do full overwrite
        # First, get current tracks
        deezer_playlist = self._fetch_deezer_playlist(deezer_id)

        if deezer_playlist and deezer_playlist.tracks:
            # Remove all current tracks
            current_track_ids = [t.deezer_id for t in deezer_playlist.tracks if t.deezer_id]
            if current_track_ids:
                self.deezer.remove_tracks_from_playlist(deezer_id, current_track_ids)

        # Add tracks from Spotify
        match_stats = {'total': 0, 'matched': 0, 'failed': 0}
        if spotify_playlist.tracks:
            track_ids, match_stats = self._match_tracks_to_deezer(
                spotify_playlist.tracks,
                spotify_playlist.name
            )
            if track_ids:
                self.deezer.add_tracks_to_playlist(deezer_id, track_ids)

        # Update tracking
        self.db.upsert_synced_playlist(
            spotify_id=spotify_playlist.spotify_id,
            deezer_id=deezer_id,
            name=spotify_playlist.name,
            track_count=len(spotify_playlist.tracks)
        )

        return match_stats

    def _find_existing_deezer_playlist(self, name: str) -> str:
        """Find a Deezer playlist by name.

        Args:
            name: Playlist name to search for

        Returns:
            Deezer playlist ID if found, None otherwise
        """
        try:
            # Fetch metadata for all playlists
            playlists = self.deezer.fetch_library_playlists_metadata()

            # Debug: show what playlists we found (but only in verbose mode)
            import os
            if os.environ.get('DEBUG') == 'verbose':
                print(f"\n[DEBUG] Looking for playlist: '{name}'")
                print(f"[DEBUG] Found {len(playlists)} playlists on Deezer:")
                # Show all playlists to see if TEST BABY is there
                for p in playlists:
                    print(f"  - '{p['title']}' (ID: {p['id']})")
            elif os.environ.get('DEBUG'):
                print(f"\n[DEBUG] Looking for playlist: '{name}' in {len(playlists)} playlists...")

            # Look for exact name match
            for p in playlists:
                if p['title'].strip().lower() == name.strip().lower():
                    if os.environ.get('DEBUG'):
                        print(f"[DEBUG] ✓ Found match: {p['id']}")
                    return str(p['id'])

            if os.environ.get('DEBUG'):
                print(f"[DEBUG] ✗ No match found")
            return None
        except Exception as e:
            if os.environ.get('DEBUG'):
                print(f"[DEBUG] Exception in _find_existing_deezer_playlist: {e}")
            return None

    def _check_deezer_playlist_exists(self, deezer_id: str) -> bool:
        """Check if a Deezer playlist exists.

        Args:
            deezer_id: Deezer playlist ID

        Returns:
            True if playlist exists, False otherwise
        """
        import os
        try:
            if os.environ.get('DEBUG'):
                print(f"\n[DEBUG] Checking if playlist {deezer_id} exists...")

            # Try to fetch the playlist directly - works for both library and public playlists
            playlist = self.deezer.fetch_playlist_by_id(deezer_id)

            if os.environ.get('DEBUG'):
                if playlist:
                    print(f"[DEBUG] ✓ Playlist exists: {playlist.name}")
                else:
                    print(f"[DEBUG] ✗ Playlist not found (returned None)")

            return playlist is not None
        except Exception as e:
            if os.environ.get('DEBUG'):
                print(f"[DEBUG] ✗ Exception checking playlist existence: {e}")
            return False

    def _fetch_deezer_playlist(self, deezer_id: str):
        """Fetch single Deezer playlist by ID.

        Args:
            deezer_id: Deezer playlist ID

        Returns:
            Playlist object or None
        """
        try:
            # Use efficient single playlist fetch instead of fetching all playlists
            return self.deezer.fetch_playlist_by_id(deezer_id)
        except Exception:
            return None

    def _match_tracks_to_deezer(self, spotify_tracks: List, playlist_name: str = ""):
        """Match Spotify tracks to Deezer track IDs with statistics.

        Args:
            spotify_tracks: List of Spotify Track objects
            playlist_name: Name of playlist (for progress display)

        Returns:
            Tuple of (List of Deezer track IDs, statistics dict)
        """
        deezer_ids = []
        total = len(spotify_tracks)
        matched = 0
        failed = 0
        failed_tracks = []

        # Show header for track matching
        self.ui.console.print(f"\n  [dim]Matching tracks for: {playlist_name}[/dim]")

        for i, sp_track in enumerate(spotify_tracks, 1):
            # Truncate long titles/artists for display
            display_title = sp_track.title[:40] + "..." if len(sp_track.title) > 40 else sp_track.title
            display_artist = sp_track.artist[:30] + "..." if len(sp_track.artist) > 30 else sp_track.artist

            if not sp_track.isrc:
                failed += 1
                failed_tracks.append((sp_track.title, sp_track.artist, "No ISRC"))
                self.ui.console.print(f"  [red]✗[/red] [dim]{display_artist} - {display_title} (no ISRC)[/dim]")
                continue

            # Try to find track on Deezer by ISRC
            dz_track = self.deezer.search_track(isrc=sp_track.isrc)
            if dz_track and dz_track.deezer_id:
                deezer_ids.append(dz_track.deezer_id)
                matched += 1
                # Cache the match in database
                self.db.upsert_track({
                    'isrc': sp_track.isrc,
                    'spotify_id': sp_track.spotify_id,
                    'deezer_id': dz_track.deezer_id,
                    'title': sp_track.title,
                    'artist': sp_track.artist,
                    'album': sp_track.album,
                    'duration_ms': sp_track.duration_ms
                })
                # Show success for matched tracks
                self.ui.console.print(f"  [green]✓[/green] [dim]{display_artist} - {display_title}[/dim]")
            else:
                failed += 1
                failed_tracks.append((sp_track.title, sp_track.artist, "Not found on Deezer"))
                self.ui.console.print(f"  [yellow]⚠[/yellow] [dim]{display_artist} - {display_title} (not found)[/dim]")

        stats = {
            'total': total,
            'matched': matched,
            'failed': failed,
            'failed_tracks': failed_tracks
        }

        # Show summary
        if failed > 0:
            self.ui.console.print(f"  [yellow]⚠ {failed} track(s) could not be matched[/yellow]\n")
        else:
            self.ui.console.print(f"  [green]✓ All {matched} tracks matched successfully![/green]\n")

        return deezer_ids, stats

    def _delete_deselected_playlists(self, selected_ids: List[str]) -> int:
        """Delete playlists from Deezer that are no longer selected.

        Args:
            selected_ids: List of currently selected Spotify playlist IDs

        Returns:
            Number of playlists deleted
        """
        deleted = 0
        synced = self.db.get_all_synced_playlists()

        for synced_playlist in synced:
            if synced_playlist['spotify_id'] not in selected_ids:
                try:
                    # Delete from Deezer
                    self.deezer.delete_playlist(synced_playlist['deezer_id'])
                    # Remove from tracking
                    self.db.delete_synced_playlist(synced_playlist['spotify_id'])
                    deleted += 1
                    self.ui.print_info(f"Deleted deselected playlist: {synced_playlist['name']}")
                except Exception as e:
                    self.ui.print_error(f"Failed to delete '{synced_playlist['name']}': {e}")

        return deleted

    def _show_dry_run(self, spotify_playlists: List) -> None:
        """Show what would be synced in dry-run mode.

        Args:
            spotify_playlists: List of Spotify playlists to be synced
        """
        self.ui.print_info("\n[DRY RUN] The following changes would be made:\n")

        for playlist in spotify_playlists:
            synced = self.db.get_synced_playlist(playlist.spotify_id)
            if synced:
                self.ui.print_info(f"  UPDATE: {playlist.name} ({len(playlist.tracks)} tracks)")
            else:
                self.ui.print_info(f"  CREATE: {playlist.name} ({len(playlist.tracks)} tracks)")

        # Check for deletions
        selected_ids = [p.spotify_id for p in spotify_playlists]
        synced_playlists = self.db.get_all_synced_playlists()
        for synced in synced_playlists:
            if synced['spotify_id'] not in selected_ids:
                self.ui.print_info(f"  DELETE: {synced['name']}")

        self.ui.print_info("\nNo changes applied (dry run mode)")
