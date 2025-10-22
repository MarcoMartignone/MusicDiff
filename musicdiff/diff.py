"""
3-way diff algorithm for detecting changes between platforms.

See docs/DIFF_ALGORITHM.md for detailed documentation.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Set, Optional
from enum import Enum


class ChangeType(Enum):
    """Types of changes that can occur."""
    PLAYLIST_CREATED = "playlist_created"
    PLAYLIST_UPDATED = "playlist_updated"
    PLAYLIST_DELETED = "playlist_deleted"
    LIKED_SONG_ADDED = "liked_song_added"
    LIKED_SONG_REMOVED = "liked_song_removed"
    ALBUM_ADDED = "album_added"
    ALBUM_REMOVED = "album_removed"


@dataclass
class Change:
    """Represents a change to be synced."""
    entity_type: str
    entity_id: str
    change_type: ChangeType
    source_platform: str
    target_platform: str
    data: dict


@dataclass
class Conflict:
    """Represents a conflict between platforms."""
    entity_type: str
    entity_id: str
    spotify_change: Change
    apple_change: Change
    resolution: str = None


@dataclass
class DiffResult:
    """Result of diff computation."""
    auto_merge: List[Change] = field(default_factory=list)
    conflicts: List[Conflict] = field(default_factory=list)

    def summary(self) -> str:
        """Return a summary string."""
        return f"{len(self.auto_merge)} auto-merge changes, {len(self.conflicts)} conflicts"


class DiffEngine:
    """Engine for computing 3-way diffs."""

    def compute_diff(self, local_state: Dict, spotify_state: Dict, apple_state: Dict) -> DiffResult:
        """Compute 3-way diff between local state and both platforms.

        Args:
            local_state: Dict with keys 'playlists', 'liked_songs', 'albums'
            spotify_state: Dict with keys 'playlists', 'liked_songs', 'albums'
            apple_state: Dict with keys 'playlists', 'liked_songs', 'albums'

        Returns:
            DiffResult with auto-merge changes and conflicts
        """
        result = DiffResult()

        # Diff playlists
        playlist_result = self.diff_playlists(
            local_state.get('playlists', {}),
            spotify_state.get('playlists', {}),
            apple_state.get('playlists', {})
        )
        result.auto_merge.extend(playlist_result.auto_merge)
        result.conflicts.extend(playlist_result.conflicts)

        # Diff liked songs
        liked_result = self.diff_liked_songs(
            set(local_state.get('liked_songs', [])),
            set(spotify_state.get('liked_songs', [])),
            set(apple_state.get('liked_songs', []))
        )
        result.auto_merge.extend(liked_result.auto_merge)
        result.conflicts.extend(liked_result.conflicts)

        # Diff albums
        album_result = self.diff_albums(
            set(local_state.get('albums', [])),
            set(spotify_state.get('albums', [])),
            set(apple_state.get('albums', []))
        )
        result.auto_merge.extend(album_result.auto_merge)
        result.conflicts.extend(album_result.conflicts)

        return result

    def diff_playlists(self, local_playlists: Dict, spotify_playlists: Dict,
                      apple_playlists: Dict) -> DiffResult:
        """Diff playlists between platforms.

        Args:
            local_playlists: Dict of playlist_id -> playlist data
            spotify_playlists: Dict of playlist_id -> playlist data
            apple_playlists: Dict of playlist_id -> playlist data

        Returns:
            DiffResult with playlist changes
        """
        result = DiffResult()

        # Get all playlist IDs across all states
        all_ids = set(local_playlists.keys()) | set(spotify_playlists.keys()) | set(apple_playlists.keys())

        for playlist_id in all_ids:
            local = local_playlists.get(playlist_id)
            spotify = spotify_playlists.get(playlist_id)
            apple = apple_playlists.get(playlist_id)

            # Detect what changed
            spotify_changed = self._playlist_changed(local, spotify)
            apple_changed = self._playlist_changed(local, apple)

            if spotify_changed and apple_changed:
                # Both platforms changed - CONFLICT
                spotify_change = self._create_playlist_change(
                    playlist_id, local, spotify, 'spotify', 'apple'
                )
                apple_change = self._create_playlist_change(
                    playlist_id, local, apple, 'apple', 'spotify'
                )
                result.conflicts.append(Conflict(
                    entity_type='playlist',
                    entity_id=playlist_id,
                    spotify_change=spotify_change,
                    apple_change=apple_change
                ))

            elif spotify_changed:
                # Only Spotify changed - AUTO-MERGE to Apple
                change = self._create_playlist_change(
                    playlist_id, local, spotify, 'spotify', 'apple'
                )
                result.auto_merge.append(change)

            elif apple_changed:
                # Only Apple changed - AUTO-MERGE to Spotify
                change = self._create_playlist_change(
                    playlist_id, local, apple, 'apple', 'spotify'
                )
                result.auto_merge.append(change)

        return result

    def diff_liked_songs(self, local_liked: Set[str], spotify_liked: Set[str],
                        apple_liked: Set[str]) -> DiffResult:
        """Diff liked songs between platforms.

        Args:
            local_liked: Set of track ISRCs
            spotify_liked: Set of track ISRCs
            apple_liked: Set of track ISRCs

        Returns:
            DiffResult with liked song changes
        """
        result = DiffResult()

        # Detect changes
        spotify_added = spotify_liked - local_liked
        spotify_removed = local_liked - spotify_liked
        apple_added = apple_liked - local_liked
        apple_removed = local_liked - apple_liked

        # Spotify changes (add to Apple)
        if spotify_added:
            result.auto_merge.append(Change(
                entity_type='liked_songs',
                entity_id='all',
                change_type=ChangeType.LIKED_SONG_ADDED,
                source_platform='spotify',
                target_platform='apple',
                data={'tracks': list(spotify_added)}
            ))

        if spotify_removed:
            result.auto_merge.append(Change(
                entity_type='liked_songs',
                entity_id='all',
                change_type=ChangeType.LIKED_SONG_REMOVED,
                source_platform='spotify',
                target_platform='apple',
                data={'tracks': list(spotify_removed)}
            ))

        # Apple changes (add to Spotify)
        if apple_added:
            result.auto_merge.append(Change(
                entity_type='liked_songs',
                entity_id='all',
                change_type=ChangeType.LIKED_SONG_ADDED,
                source_platform='apple',
                target_platform='spotify',
                data={'tracks': list(apple_added)}
            ))

        if apple_removed:
            result.auto_merge.append(Change(
                entity_type='liked_songs',
                entity_id='all',
                change_type=ChangeType.LIKED_SONG_REMOVED,
                source_platform='apple',
                target_platform='spotify',
                data={'tracks': list(apple_removed)}
            ))

        return result

    def diff_albums(self, local_albums: Set[str], spotify_albums: Set[str],
                   apple_albums: Set[str]) -> DiffResult:
        """Diff saved albums between platforms.

        Args:
            local_albums: Set of album IDs
            spotify_albums: Set of album IDs
            apple_albums: Set of album IDs

        Returns:
            DiffResult with album changes
        """
        result = DiffResult()

        # Detect changes
        spotify_added = spotify_albums - local_albums
        spotify_removed = local_albums - spotify_albums
        apple_added = apple_albums - local_albums
        apple_removed = local_albums - apple_albums

        # Spotify changes (add to Apple)
        if spotify_added:
            result.auto_merge.append(Change(
                entity_type='albums',
                entity_id='all',
                change_type=ChangeType.ALBUM_ADDED,
                source_platform='spotify',
                target_platform='apple',
                data={'albums': list(spotify_added)}
            ))

        if spotify_removed:
            result.auto_merge.append(Change(
                entity_type='albums',
                entity_id='all',
                change_type=ChangeType.ALBUM_REMOVED,
                source_platform='spotify',
                target_platform='apple',
                data={'albums': list(spotify_removed)}
            ))

        # Apple changes (add to Spotify)
        if apple_added:
            result.auto_merge.append(Change(
                entity_type='albums',
                entity_id='all',
                change_type=ChangeType.ALBUM_ADDED,
                source_platform='apple',
                target_platform='spotify',
                data={'albums': list(apple_added)}
            ))

        if apple_removed:
            result.auto_merge.append(Change(
                entity_type='albums',
                entity_id='all',
                change_type=ChangeType.ALBUM_REMOVED,
                source_platform='apple',
                target_platform='spotify',
                data={'albums': list(apple_removed)}
            ))

        return result

    def _playlist_changed(self, local: Optional[Dict], remote: Optional[Dict]) -> bool:
        """Check if a playlist changed between local and remote state."""
        # Playlist created
        if local is None and remote is not None:
            return True

        # Playlist deleted
        if local is not None and remote is None:
            return True

        # Both None (shouldn't happen)
        if local is None and remote is None:
            return False

        # Check metadata changes
        if local.get('name') != remote.get('name'):
            return True
        if local.get('description') != remote.get('description'):
            return True

        # Check track changes
        local_tracks = local.get('tracks', [])
        remote_tracks = remote.get('tracks', [])

        if local_tracks != remote_tracks:
            return True

        return False

    def _create_playlist_change(self, playlist_id: str, local: Optional[Dict],
                               remote: Optional[Dict], source_platform: str,
                               target_platform: str) -> Change:
        """Create a Change object for a playlist modification."""

        # Playlist created
        if local is None and remote is not None:
            return Change(
                entity_type='playlist',
                entity_id=playlist_id,
                change_type=ChangeType.PLAYLIST_CREATED,
                source_platform=source_platform,
                target_platform=target_platform,
                data={
                    'name': remote.get('name', ''),
                    'description': remote.get('description', ''),
                    'public': remote.get('public', False),
                    'tracks': remote.get('tracks', [])
                }
            )

        # Playlist deleted
        if local is not None and remote is None:
            return Change(
                entity_type='playlist',
                entity_id=playlist_id,
                change_type=ChangeType.PLAYLIST_DELETED,
                source_platform=source_platform,
                target_platform=target_platform,
                data={}
            )

        # Playlist updated
        local_tracks = local.get('tracks', [])
        remote_tracks = remote.get('tracks', [])

        tracks_added = [t for t in remote_tracks if t not in local_tracks]
        tracks_removed = [t for t in local_tracks if t not in remote_tracks]

        return Change(
            entity_type='playlist',
            entity_id=playlist_id,
            change_type=ChangeType.PLAYLIST_UPDATED,
            source_platform=source_platform,
            target_platform=target_platform,
            data={
                'name': remote.get('name', ''),
                'description': remote.get('description', ''),
                'public': remote.get('public', False),
                'tracks': remote.get('tracks', []),
                'tracks_added': tracks_added,
                'tracks_removed': tracks_removed,
                'reordered': local_tracks != remote_tracks and set(local_tracks) == set(remote_tracks)
            }
        )
