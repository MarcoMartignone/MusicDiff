"""
3-way diff algorithm for detecting changes between platforms.

See docs/DIFF_ALGORITHM.md for detailed documentation.
"""

from dataclasses import dataclass
from typing import List
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
    auto_merge: List[Change]
    conflicts: List[Conflict]

    def summary(self) -> str:
        """Return a summary string."""
        return f"{len(self.auto_merge)} auto-merge changes, {len(self.conflicts)} conflicts"


class DiffEngine:
    """Engine for computing 3-way diffs."""

    def compute_diff(self, local_state, spotify_state, apple_state) -> DiffResult:
        """Compute 3-way diff between local state and both platforms.

        Args:
            local_state: Last known state from database
            spotify_state: Current state from Spotify
            apple_state: Current state from Apple Music

        Returns:
            DiffResult with auto-merge changes and conflicts
        """
        # TODO: Implement 3-way diff algorithm
        # 1. Compare Spotify vs local
        # 2. Compare Apple vs local
        # 3. Categorize as auto-merge or conflicts

        raise NotImplementedError("Diff computation not yet implemented")

    def diff_playlists(self, local_playlists, spotify_playlists, apple_playlists):
        """Diff playlists specifically."""
        # TODO: Implement playlist diffing
        raise NotImplementedError()

    def diff_liked_songs(self, local_liked, spotify_liked, apple_liked):
        """Diff liked songs specifically."""
        # TODO: Implement liked songs diffing
        raise NotImplementedError()
