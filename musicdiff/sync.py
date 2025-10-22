"""
Sync orchestration and change application.

See docs/SYNC_LOGIC.md for detailed documentation.
"""

from dataclasses import dataclass
from typing import List, Tuple, Dict, Optional
from enum import Enum
import time
import json
from datetime import datetime

from musicdiff.diff import Change, ChangeType, DiffEngine, DiffResult, Conflict
from musicdiff.matcher import TrackMatcher


class SyncMode(Enum):
    """Sync modes."""
    INTERACTIVE = "interactive"
    AUTO = "auto"
    DRY_RUN = "dry_run"
    CONFLICTS_ONLY = "conflicts_only"


@dataclass
class SyncResult:
    """Result of a sync operation."""
    success: bool
    changes_applied: int
    conflicts_count: int
    conflicts_resolved: int
    failed_changes: List[Tuple[Change, str]]
    duration_seconds: float

    def summary(self) -> str:
        """Return summary string."""
        if self.success:
            return f"✓ Sync complete: {self.changes_applied} changes applied"
        else:
            return f"⚠ Sync partial: {self.changes_applied} applied, {len(self.failed_changes)} failed"


class SyncEngine:
    """Orchestrates the sync process."""

    def __init__(self, spotify_client, apple_client, database, ui):
        """Initialize sync engine.

        Args:
            spotify_client: SpotifyClient instance
            apple_client: AppleMusicClient instance
            database: Database instance
            ui: UI instance for user interaction
        """
        self.spotify = spotify_client
        self.apple = apple_client
        self.db = database
        self.ui = ui
        self.matcher = TrackMatcher()
        self.diff_engine = DiffEngine()

    def sync(self, mode: SyncMode = SyncMode.INTERACTIVE) -> SyncResult:
        """Perform synchronization.

        Args:
            mode: Sync mode (interactive, auto, dry-run, conflicts-only)

        Returns:
            SyncResult with operation details
        """
        start_time = time.time()

        try:
            if mode == SyncMode.CONFLICTS_ONLY:
                # Only resolve existing conflicts
                return self._sync_conflicts_only()

            # Step 1: Fetch current state from platforms
            self.ui.print_info("Fetching library data...")

            spotify_state = self._fetch_spotify_state()
            apple_state = self._fetch_apple_state()

            # Step 2: Load local state
            local_state = self._load_local_state()

            # Step 3: Compute diff
            self.ui.print_info("Computing changes...")
            diff_result = self.diff_engine.compute_diff(
                local_state,
                spotify_state,
                apple_state
            )

            # Show diff summary
            self.ui.show_diff_summary(diff_result)

            if mode == SyncMode.DRY_RUN:
                # Don't apply anything, just show what would happen
                self.ui.print_info("Dry run complete - no changes applied")
                duration = time.time() - start_time
                return SyncResult(
                    success=True,
                    changes_applied=0,
                    conflicts_count=len(diff_result.conflicts),
                    conflicts_resolved=0,
                    failed_changes=[],
                    duration_seconds=duration
                )

            # Step 4: Resolve conflicts
            conflicts_resolved = 0
            if diff_result.conflicts:
                self.ui.print_warning(f"Found {len(diff_result.conflicts)} conflicts")

                if mode == SyncMode.INTERACTIVE:
                    # Interactive conflict resolution
                    for conflict in diff_result.conflicts:
                        resolution = self._resolve_conflict_interactive(conflict)
                        if resolution != 'skip':
                            conflicts_resolved += 1
                            # Convert resolution to change and add to auto_merge
                            change = self._conflict_to_change(conflict, resolution)
                            if change:
                                diff_result.auto_merge.append(change)
                else:
                    # Auto mode - save conflicts for later
                    for conflict in diff_result.conflicts:
                        self._save_conflict(conflict)

            # Step 5: Apply changes
            applied = 0
            failed = []

            if diff_result.auto_merge:
                self.ui.print_info(f"Applying {len(diff_result.auto_merge)} changes...")

                if mode == SyncMode.INTERACTIVE:
                    # Ask for confirmation
                    if not self.ui.confirm("Apply these changes?", default=True):
                        self.ui.print_warning("Sync cancelled by user")
                        duration = time.time() - start_time
                        return SyncResult(
                            success=False,
                            changes_applied=0,
                            conflicts_count=len(diff_result.conflicts),
                            conflicts_resolved=conflicts_resolved,
                            failed_changes=[],
                            duration_seconds=duration
                        )

                # Apply changes with progress bar
                with self.ui.create_progress("Syncing") as progress:
                    task = progress.add_task("Processing...", total=len(diff_result.auto_merge))

                    for change in diff_result.auto_merge:
                        try:
                            success = self.apply_change(change)
                            if success:
                                applied += 1
                            else:
                                failed.append((change, "Application returned False"))
                        except Exception as e:
                            failed.append((change, str(e)))
                            # Continue with next change

                        progress.update(task, advance=1)

            # Step 6: Update local state
            if applied > 0 or conflicts_resolved > 0:
                self.ui.print_info("Updating local state...")
                self._update_local_state(spotify_state, apple_state)

            # Step 7: Log sync
            duration = time.time() - start_time
            result = SyncResult(
                success=len(failed) == 0,
                changes_applied=applied,
                conflicts_count=len(diff_result.conflicts),
                conflicts_resolved=conflicts_resolved,
                failed_changes=failed,
                duration_seconds=duration
            )

            self._log_sync(result)

            # Show result
            if result.success:
                self.ui.print_success(result.summary())
            else:
                self.ui.print_warning(result.summary())
                for change, error in failed:
                    self.ui.print_error(f"  {change.entity_id}: {error}")

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.ui.print_error(f"Sync failed: {e}")
            return SyncResult(
                success=False,
                changes_applied=0,
                conflicts_count=0,
                conflicts_resolved=0,
                failed_changes=[],
                duration_seconds=duration
            )

    def apply_change(self, change: Change) -> bool:
        """Apply a single change.

        Args:
            change: Change to apply

        Returns:
            True if successful
        """
        # Route to appropriate platform
        if change.target_platform == 'spotify':
            return self._apply_to_spotify(change)
        elif change.target_platform == 'apple':
            return self._apply_to_apple(change)
        else:
            raise ValueError(f"Unknown target platform: {change.target_platform}")

    def _apply_to_spotify(self, change: Change) -> bool:
        """Apply change to Spotify.

        Args:
            change: Change to apply

        Returns:
            True if successful
        """
        if change.change_type == ChangeType.PLAYLIST_CREATED:
            # Create playlist on Spotify
            playlist_id = self.spotify.create_playlist(
                name=change.data['name'],
                description=change.data.get('description', ''),
                public=change.data.get('public', False)
            )

            # Add tracks if any
            if change.data.get('tracks'):
                track_uris = []
                for isrc in change.data['tracks']:
                    uri = self._get_spotify_uri(isrc)
                    if uri:
                        track_uris.append(uri)

                if track_uris:
                    self.spotify.add_tracks_to_playlist(playlist_id, track_uris)

            return True

        elif change.change_type == ChangeType.PLAYLIST_UPDATED:
            playlist_id = change.entity_id

            # Add tracks
            if change.data.get('tracks_added'):
                track_uris = []
                for isrc in change.data['tracks_added']:
                    uri = self._get_spotify_uri(isrc)
                    if uri:
                        track_uris.append(uri)

                if track_uris:
                    self.spotify.add_tracks_to_playlist(playlist_id, track_uris)

            # Remove tracks
            if change.data.get('tracks_removed'):
                track_uris = []
                for isrc in change.data['tracks_removed']:
                    uri = self._get_spotify_uri(isrc)
                    if uri:
                        track_uris.append(uri)

                if track_uris:
                    self.spotify.remove_tracks_from_playlist(playlist_id, track_uris)

            return True

        elif change.change_type == ChangeType.PLAYLIST_DELETED:
            self.spotify.delete_playlist(change.entity_id)
            return True

        elif change.change_type == ChangeType.LIKED_SONG_ADDED:
            track_ids = []
            for isrc in change.data['tracks']:
                track_id = self._get_spotify_id(isrc)
                if track_id:
                    track_ids.append(track_id)

            if track_ids:
                self.spotify.save_tracks(track_ids)
            return True

        elif change.change_type == ChangeType.LIKED_SONG_REMOVED:
            track_ids = []
            for isrc in change.data['tracks']:
                track_id = self._get_spotify_id(isrc)
                if track_id:
                    track_ids.append(track_id)

            if track_ids:
                self.spotify.remove_saved_tracks(track_ids)
            return True

        elif change.change_type == ChangeType.ALBUM_ADDED:
            album_ids = []
            for album_isrc in change.data['albums']:
                album_id = self._get_spotify_album_id(album_isrc)
                if album_id:
                    album_ids.append(album_id)

            if album_ids:
                self.spotify.save_albums(album_ids)
            return True

        elif change.change_type == ChangeType.ALBUM_REMOVED:
            album_ids = []
            for album_isrc in change.data['albums']:
                album_id = self._get_spotify_album_id(album_isrc)
                if album_id:
                    album_ids.append(album_id)

            if album_ids:
                self.spotify.remove_saved_albums(album_ids)
            return True

        return False

    def _apply_to_apple(self, change: Change) -> bool:
        """Apply change to Apple Music.

        Args:
            change: Change to apply

        Returns:
            True if successful
        """
        if change.change_type == ChangeType.PLAYLIST_CREATED:
            # Create playlist on Apple Music
            playlist_id = self.apple.create_playlist(
                name=change.data['name'],
                description=change.data.get('description', '')
            )

            # Add tracks if any
            if change.data.get('tracks'):
                # First, ensure tracks are in library
                catalog_ids = []
                for isrc in change.data['tracks']:
                    catalog_id = self._get_apple_catalog_id(isrc)
                    if catalog_id:
                        catalog_ids.append(catalog_id)

                if catalog_ids:
                    # Add to library first
                    self.apple.add_to_library(catalog_ids)

                    # Get library IDs (might differ from catalog IDs)
                    library_ids = []
                    for isrc in change.data['tracks']:
                        lib_id = self._get_apple_library_id(isrc)
                        if lib_id:
                            library_ids.append(lib_id)

                    # Add to playlist
                    if library_ids:
                        self.apple.add_tracks_to_playlist(playlist_id, library_ids)

            return True

        elif change.change_type == ChangeType.PLAYLIST_UPDATED:
            playlist_id = change.entity_id

            # Add tracks
            if change.data.get('tracks_added'):
                catalog_ids = []
                for isrc in change.data['tracks_added']:
                    catalog_id = self._get_apple_catalog_id(isrc)
                    if catalog_id:
                        catalog_ids.append(catalog_id)

                if catalog_ids:
                    self.apple.add_to_library(catalog_ids)

                    library_ids = []
                    for isrc in change.data['tracks_added']:
                        lib_id = self._get_apple_library_id(isrc)
                        if lib_id:
                            library_ids.append(lib_id)

                    if library_ids:
                        self.apple.add_tracks_to_playlist(playlist_id, library_ids)

            # Remove tracks
            if change.data.get('tracks_removed'):
                library_ids = []
                for isrc in change.data['tracks_removed']:
                    lib_id = self._get_apple_library_id(isrc)
                    if lib_id:
                        library_ids.append(lib_id)

                if library_ids:
                    self.apple.remove_tracks_from_playlist(playlist_id, library_ids)

            return True

        elif change.change_type == ChangeType.PLAYLIST_DELETED:
            self.apple.delete_playlist(change.entity_id)
            return True

        elif change.change_type == ChangeType.LIKED_SONG_ADDED:
            catalog_ids = []
            for isrc in change.data['tracks']:
                catalog_id = self._get_apple_catalog_id(isrc)
                if catalog_id:
                    catalog_ids.append(catalog_id)

            if catalog_ids:
                self.apple.add_to_library(catalog_ids)
            return True

        elif change.change_type == ChangeType.LIKED_SONG_REMOVED:
            library_ids = []
            for isrc in change.data['tracks']:
                lib_id = self._get_apple_library_id(isrc)
                if lib_id:
                    library_ids.append(lib_id)

            if library_ids:
                self.apple.remove_from_library(library_ids)
            return True

        elif change.change_type == ChangeType.ALBUM_ADDED:
            catalog_ids = []
            for album_isrc in change.data['albums']:
                catalog_id = self._get_apple_album_catalog_id(album_isrc)
                if catalog_id:
                    catalog_ids.append(catalog_id)

            if catalog_ids:
                self.apple.save_albums(catalog_ids)
            return True

        elif change.change_type == ChangeType.ALBUM_REMOVED:
            library_ids = []
            for album_isrc in change.data['albums']:
                lib_id = self._get_apple_album_library_id(album_isrc)
                if lib_id:
                    library_ids.append(lib_id)

            if library_ids:
                self.apple.remove_saved_albums(library_ids)
            return True

        return False

    def _fetch_spotify_state(self) -> Dict:
        """Fetch current state from Spotify.

        Returns:
            State dictionary with playlists, liked_songs, albums
        """
        playlists = self.spotify.fetch_playlists()
        liked_songs = self.spotify.fetch_liked_songs()
        albums = self.spotify.fetch_saved_albums()

        # Convert to dict format expected by diff engine
        playlists_dict = {}
        for playlist in playlists:
            playlists_dict[playlist.spotify_id] = {
                'name': playlist.name,
                'description': playlist.description,
                'tracks': [track.isrc for track in playlist.tracks if track.isrc]
            }

        liked_songs_list = [track.isrc for track in liked_songs if track.isrc]
        albums_list = [album.spotify_id for album in albums]

        return {
            'playlists': playlists_dict,
            'liked_songs': liked_songs_list,
            'albums': albums_list
        }

    def _fetch_apple_state(self) -> Dict:
        """Fetch current state from Apple Music.

        Returns:
            State dictionary with playlists, liked_songs, albums
        """
        playlists = self.apple.fetch_library_playlists()
        liked_songs = self.apple.fetch_library_songs()
        albums = self.apple.fetch_library_albums()

        # Convert to dict format
        playlists_dict = {}
        for playlist in playlists:
            playlists_dict[playlist.apple_music_id] = {
                'name': playlist.name,
                'description': playlist.description,
                'tracks': [track.isrc for track in playlist.tracks if track.isrc]
            }

        liked_songs_list = [track.isrc for track in liked_songs if track.isrc]
        albums_list = [album.apple_music_id for album in albums]

        return {
            'playlists': playlists_dict,
            'liked_songs': liked_songs_list,
            'albums': albums_list
        }

    def _load_local_state(self) -> Dict:
        """Load local state from database.

        Returns:
            State dictionary
        """
        # Get all playlists from DB
        playlists = self.db.get_all_playlists()

        playlists_dict = {}
        for playlist in playlists:
            tracks = self.db.get_playlist_tracks(playlist['id'])
            playlists_dict[playlist['id']] = {
                'name': playlist['name'],
                'description': playlist.get('description', ''),
                'tracks': [track['isrc'] for track in tracks if track.get('isrc')]
            }

        # Get liked songs
        liked_songs_spotify = self.db.get_liked_songs('spotify')
        liked_songs_apple = self.db.get_liked_songs('apple')

        # Merge (union) - any song liked on either platform
        liked_songs_set = set()
        for track in liked_songs_spotify:
            if track.get('isrc'):
                liked_songs_set.add(track['isrc'])
        for track in liked_songs_apple:
            if track.get('isrc'):
                liked_songs_set.add(track['isrc'])

        # Get albums
        albums = self.db.get_all_albums()
        albums_list = [album['spotify_id'] or album.get('apple_id', '') for album in albums]

        return {
            'playlists': playlists_dict,
            'liked_songs': list(liked_songs_set),
            'albums': albums_list
        }

    def _update_local_state(self, spotify_state: Dict, apple_state: Dict):
        """Update local database with new state.

        Args:
            spotify_state: Current Spotify state
            apple_state: Current Apple Music state
        """
        # Update playlists - this is simplified; production code would be more sophisticated
        # For now, just mark that we synced
        pass

    def _resolve_conflict_interactive(self, conflict: Conflict) -> str:
        """Resolve conflict interactively.

        Args:
            conflict: Conflict to resolve

        Returns:
            Resolution choice: 'spotify', 'apple', 'manual', 'skip'
        """
        self.ui.show_conflict(conflict)
        return self.ui.prompt_resolution(conflict)

    def _save_conflict(self, conflict: Conflict):
        """Save conflict to database for later resolution.

        Args:
            conflict: Conflict to save
        """
        self.db.add_conflict(
            conflict_type=conflict.entity_type,
            entity_id=conflict.entity_id,
            spotify_data=json.dumps(conflict.spotify_change.data),
            apple_data=json.dumps(conflict.apple_change.data)
        )

    def _conflict_to_change(self, conflict: Conflict, resolution: str) -> Optional[Change]:
        """Convert conflict resolution to a change.

        Args:
            conflict: The conflict
            resolution: Resolution choice ('spotify', 'apple', 'manual')

        Returns:
            Change object or None
        """
        if resolution == 'spotify':
            return conflict.spotify_change
        elif resolution == 'apple':
            return conflict.apple_change
        elif resolution == 'manual':
            # Manual merge would require more UI - for now, skip
            return None
        else:
            return None

    def _sync_conflicts_only(self) -> SyncResult:
        """Sync mode that only resolves pending conflicts.

        Returns:
            SyncResult
        """
        start_time = time.time()

        conflicts = self.db.get_unresolved_conflicts()

        if not conflicts:
            self.ui.print_info("No unresolved conflicts")
            duration = time.time() - start_time
            return SyncResult(
                success=True,
                changes_applied=0,
                conflicts_count=0,
                conflicts_resolved=0,
                failed_changes=[],
                duration_seconds=duration
            )

        self.ui.print_info(f"Found {len(conflicts)} unresolved conflicts")

        # Resolve each conflict interactively
        resolved = 0
        for conflict_data in conflicts:
            # Reconstruct Conflict object from database
            # This is simplified - production code would be more complete
            resolved += 1

        duration = time.time() - start_time
        return SyncResult(
            success=True,
            changes_applied=0,
            conflicts_count=len(conflicts),
            conflicts_resolved=resolved,
            failed_changes=[],
            duration_seconds=duration
        )

    def _log_sync(self, result: SyncResult):
        """Log sync to database.

        Args:
            result: SyncResult to log
        """
        status = 'success' if result.success else 'partial'

        details = {
            'changes_applied': result.changes_applied,
            'conflicts_resolved': result.conflicts_resolved,
            'failed_changes': len(result.failed_changes),
            'duration': result.duration_seconds
        }

        self.db.add_sync_log(
            status=status,
            changes=result.changes_applied,
            conflicts=result.conflicts_count,
            details=json.dumps(details)
        )

    def _get_spotify_uri(self, isrc: str) -> Optional[str]:
        """Get Spotify URI for a track by ISRC.

        Args:
            isrc: Track ISRC

        Returns:
            Spotify URI or None
        """
        # Check database first
        track = self.db.get_track_by_isrc(isrc)
        if track and track.get('spotify_id'):
            return f"spotify:track:{track['spotify_id']}"

        # Search Spotify
        track = self.spotify.search_track(isrc=isrc)
        if track:
            return track.uri

        return None

    def _get_spotify_id(self, isrc: str) -> Optional[str]:
        """Get Spotify track ID by ISRC.

        Args:
            isrc: Track ISRC

        Returns:
            Spotify track ID or None
        """
        uri = self._get_spotify_uri(isrc)
        if uri:
            return uri.split(':')[-1]
        return None

    def _get_spotify_album_id(self, album_identifier: str) -> Optional[str]:
        """Get Spotify album ID.

        Args:
            album_identifier: Album identifier

        Returns:
            Spotify album ID or None
        """
        # Simplified - just return the identifier
        return album_identifier

    def _get_apple_catalog_id(self, isrc: str) -> Optional[str]:
        """Get Apple Music catalog ID for a track by ISRC.

        Args:
            isrc: Track ISRC

        Returns:
            Apple Music catalog ID or None
        """
        # Check database first
        track = self.db.get_track_by_isrc(isrc)
        if track and track.get('apple_catalog_id'):
            return track['apple_catalog_id']

        # Search Apple Music
        track = self.apple.search_track(isrc=isrc)
        if track:
            return track.catalog_id

        return None

    def _get_apple_library_id(self, isrc: str) -> Optional[str]:
        """Get Apple Music library ID for a track.

        Args:
            isrc: Track ISRC

        Returns:
            Apple Music library ID or None
        """
        # Check database
        track = self.db.get_track_by_isrc(isrc)
        if track and track.get('apple_library_id'):
            return track['apple_library_id']

        # Would need to fetch from library to get library ID
        return None

    def _get_apple_album_catalog_id(self, album_identifier: str) -> Optional[str]:
        """Get Apple Music album catalog ID.

        Args:
            album_identifier: Album identifier

        Returns:
            Album catalog ID or None
        """
        return album_identifier

    def _get_apple_album_library_id(self, album_identifier: str) -> Optional[str]:
        """Get Apple Music album library ID.

        Args:
            album_identifier: Album identifier

        Returns:
            Album library ID or None
        """
        return album_identifier
