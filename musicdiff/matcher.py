"""
Cross-platform track matching.

See docs/TRACK_MATCHING.md for detailed documentation.
"""

from typing import Optional
from musicdiff.spotify import Track


class TrackMatcher:
    """Handles matching tracks across platforms."""

    def __init__(self, spotify_client, apple_client, database):
        """Initialize track matcher.

        Args:
            spotify_client: SpotifyClient instance
            apple_client: AppleMusicClient instance
            database: Database instance
        """
        self.spotify = spotify_client
        self.apple = apple_client
        self.db = database

    def match_track(self, spotify_track: Track) -> Optional[Track]:
        """Match a Spotify track to Apple Music.

        Args:
            spotify_track: Track from Spotify

        Returns:
            Matched Apple Music track or None
        """
        # TODO: Implement matching strategies
        # 1. Check manual mappings
        # 2. Check local database
        # 3. ISRC matching via API
        # 4. Metadata fuzzy matching
        # 5. Mark as unmatched

        raise NotImplementedError("Track matching not yet implemented")

    def match_by_isrc(self, spotify_track: Track) -> Optional[Track]:
        """Match track using ISRC."""
        # TODO: Implement ISRC matching
        raise NotImplementedError()

    def match_by_metadata(self, spotify_track: Track) -> Optional[Track]:
        """Match track using metadata and fuzzy matching."""
        # TODO: Implement metadata matching
        raise NotImplementedError()

    def compute_similarity(self, track1: Track, track2: Track) -> float:
        """Compute similarity score between two tracks (0-100)."""
        # TODO: Implement similarity scoring
        raise NotImplementedError()
