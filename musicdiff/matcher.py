"""
Cross-platform track matching.

See docs/TRACK_MATCHING.md for detailed documentation.
"""

from typing import Optional, List, Dict
from rapidfuzz import fuzz
import unicodedata
import re


class TrackMatcher:
    """Handles matching tracks across platforms."""

    # Default similarity threshold for auto-matching
    DEFAULT_THRESHOLD = 85.0

    def __init__(self, threshold: float = DEFAULT_THRESHOLD):
        """Initialize track matcher.

        Args:
            threshold: Minimum similarity score (0-100) for auto-matching
        """
        self.threshold = threshold

    def match_tracks(self, source_track: Dict, candidates: List[Dict]) -> Optional[Dict]:
        """Find best matching track from candidates.

        Args:
            source_track: Source track dict with keys: title, artist, album, duration_ms, isrc
            candidates: List of candidate track dicts

        Returns:
            Best matching track or None if no good match found
        """
        if not candidates:
            return None

        # Try ISRC matching first (100% reliable)
        if source_track.get('isrc'):
            for candidate in candidates:
                if candidate.get('isrc') == source_track['isrc']:
                    return candidate

        # Fall back to fuzzy matching
        best_match = None
        best_score = 0

        for candidate in candidates:
            score = self.compute_similarity(source_track, candidate)
            if score > best_score and score >= self.threshold:
                best_score = score
                best_match = candidate

        return best_match

    def compute_similarity(self, track1: Dict, track2: Dict) -> float:
        """Compute similarity score between two tracks (0-100).

        Args:
            track1: First track dict
            track2: Second track dict

        Returns:
            Similarity score from 0-100
        """
        # Normalize strings
        title1 = self.normalize_string(track1.get('title', ''))
        title2 = self.normalize_string(track2.get('title', ''))

        artist1 = self.normalize_string(track1.get('artist', ''))
        artist2 = self.normalize_string(track2.get('artist', ''))

        album1 = self.normalize_string(track1.get('album', ''))
        album2 = self.normalize_string(track2.get('album', ''))

        # Compute individual similarities
        title_sim = fuzz.ratio(title1, title2)
        artist_sim = fuzz.ratio(artist1, artist2)
        album_sim = fuzz.ratio(album1, album2)

        # Duration similarity (absolute difference in seconds)
        duration1 = track1.get('duration_ms', 0)
        duration2 = track2.get('duration_ms', 0)

        if duration1 and duration2:
            duration_diff = abs(duration1 - duration2) / 1000  # Convert to seconds
            # Penalty: 10 points per second difference, max 100 points penalty
            duration_sim = max(0, 100 - (duration_diff * 10))
        else:
            duration_sim = 50  # Neutral if duration unavailable

        # Weighted average (title and artist are most important)
        score = (
            title_sim * 0.40 +
            artist_sim * 0.35 +
            album_sim * 0.15 +
            duration_sim * 0.10
        )

        return score

    def normalize_string(self, s: str) -> str:
        """Normalize string for comparison.

        Args:
            s: String to normalize

        Returns:
            Normalized string
        """
        if not s:
            return ''

        # Convert to lowercase
        s = s.lower()

        # Remove accents/diacritics
        s = unicodedata.normalize('NFKD', s)
        s = s.encode('ASCII', 'ignore').decode('ASCII')

        # Remove punctuation and extra whitespace
        s = re.sub(r'[^\w\s]', '', s)
        s = re.sub(r'\s+', ' ', s).strip()

        # Remove common suffixes
        suffixes = [
            'remaster', 'remastered', 'explicit', 'clean',
            'radio edit', 'album version', 'single version',
            'deluxe', 'bonus track', 'live', 'acoustic'
        ]
        for suffix in suffixes:
            s = s.replace(suffix, '')

        return s.strip()

    def is_confident_match(self, source_track: Dict, candidate: Dict) -> bool:
        """Check if a match is confident enough for auto-matching.

        Args:
            source_track: Source track
            candidate: Candidate track

        Returns:
            True if match confidence is high enough
        """
        # ISRC match is always confident
        if source_track.get('isrc') and source_track.get('isrc') == candidate.get('isrc'):
            return True

        # Check similarity score
        score = self.compute_similarity(source_track, candidate)
        return score >= self.threshold

    def find_duplicates(self, tracks: List[Dict], threshold: float = 95.0) -> List[List[Dict]]:
        """Find potential duplicate tracks in a list.

        Args:
            tracks: List of track dicts
            threshold: Similarity threshold for considering tracks as duplicates

        Returns:
            List of duplicate groups (each group is a list of similar tracks)
        """
        duplicates = []
        processed = set()

        for i, track1 in enumerate(tracks):
            if i in processed:
                continue

            group = [track1]
            processed.add(i)

            for j, track2 in enumerate(tracks[i+1:], start=i+1):
                if j in processed:
                    continue

                score = self.compute_similarity(track1, track2)
                if score >= threshold:
                    group.append(track2)
                    processed.add(j)

            if len(group) > 1:
                duplicates.append(group)

        return duplicates
