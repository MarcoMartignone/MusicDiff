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

            self.ui.print_info(f"Syncing {len(selected)} selected playlists to Deezer...")

            # Fetch selected playlists from Spotify
            spotify_playlist_ids = [p['spotify_id'] for p in selected]
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
            with self.ui.create_progress("Syncing playlists") as progress:
                task = progress.add_task("Processing...", total=len(spotify_playlists))

                for sp_playlist in spotify_playlists:
                    try:
                        # Check if already synced to Deezer
                        synced = self.db.get_synced_playlist(sp_playlist.spotify_id)

                        if synced:
                            # Update existing Deezer playlist (full overwrite)
                            self._update_deezer_playlist(synced['deezer_id'], sp_playlist)
                            updated += 1
                        else:
                            # Create new Deezer playlist
                            deezer_id = self._create_deezer_playlist(sp_playlist)
                            # Track it in database
                            self.db.upsert_synced_playlist(
                                spotify_id=sp_playlist.spotify_id,
                                deezer_id=deezer_id,
                                name=sp_playlist.name,
                                track_count=len(sp_playlist.tracks)
                            )
                            created += 1

                        # Mark as synced
                        self.db.mark_playlist_synced(sp_playlist.spotify_id)

                    except Exception as e:
                        failed.append((sp_playlist.name, str(e)))
                        self.ui.print_error(f"Failed to sync '{sp_playlist.name}': {e}")

                    progress.update(task, advance=1)

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
        """Fetch Spotify playlists by ID.

        Args:
            playlist_ids: List of Spotify playlist IDs

        Returns:
            List of Playlist objects with tracks
        """
        playlists = []
        all_playlists = self.spotify.fetch_playlists()

        for playlist in all_playlists:
            if playlist.spotify_id in playlist_ids:
                playlists.append(playlist)

        return playlists

    def _create_deezer_playlist(self, spotify_playlist) -> str:
        """Create new playlist on Deezer.

        Args:
            spotify_playlist: Spotify Playlist object

        Returns:
            Deezer playlist ID
        """
        # Create playlist
        deezer_id = self.deezer.create_playlist(
            name=spotify_playlist.name,
            description=spotify_playlist.description,
            public=spotify_playlist.public
        )

        # Add tracks
        if spotify_playlist.tracks:
            track_ids = self._match_tracks_to_deezer(spotify_playlist.tracks)
            if track_ids:
                self.deezer.add_tracks_to_playlist(deezer_id, track_ids)

        return deezer_id

    def _update_deezer_playlist(self, deezer_id: str, spotify_playlist) -> None:
        """Update Deezer playlist with full overwrite from Spotify.

        Args:
            deezer_id: Deezer playlist ID
            spotify_playlist: Spotify Playlist object
        """
        # Full overwrite: delete all tracks and re-add from Spotify
        # First, get current tracks
        deezer_playlist = self._fetch_deezer_playlist(deezer_id)

        if deezer_playlist and deezer_playlist.tracks:
            # Remove all current tracks
            current_track_ids = [t.deezer_id for t in deezer_playlist.tracks if t.deezer_id]
            if current_track_ids:
                self.deezer.remove_tracks_from_playlist(deezer_id, current_track_ids)

        # Add tracks from Spotify
        if spotify_playlist.tracks:
            track_ids = self._match_tracks_to_deezer(spotify_playlist.tracks)
            if track_ids:
                self.deezer.add_tracks_to_playlist(deezer_id, track_ids)

        # Update tracking
        self.db.upsert_synced_playlist(
            spotify_id=spotify_playlist.spotify_id,
            deezer_id=deezer_id,
            name=spotify_playlist.name,
            track_count=len(spotify_playlist.tracks)
        )

    def _fetch_deezer_playlist(self, deezer_id: str):
        """Fetch single Deezer playlist by ID.

        Args:
            deezer_id: Deezer playlist ID

        Returns:
            Playlist object or None
        """
        try:
            all_playlists = self.deezer.fetch_library_playlists()
            for playlist in all_playlists:
                if playlist.deezer_id == deezer_id:
                    return playlist
            return None
        except Exception:
            return None

    def _match_tracks_to_deezer(self, spotify_tracks: List) -> List[str]:
        """Match Spotify tracks to Deezer track IDs.

        Args:
            spotify_tracks: List of Spotify Track objects

        Returns:
            List of Deezer track IDs
        """
        deezer_ids = []

        for sp_track in spotify_tracks:
            if not sp_track.isrc:
                continue

            # Try to find track on Deezer by ISRC
            dz_track = self.deezer.search_track(isrc=sp_track.isrc)
            if dz_track and dz_track.deezer_id:
                deezer_ids.append(dz_track.deezer_id)
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

        return deezer_ids

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
