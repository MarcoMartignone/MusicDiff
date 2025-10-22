# Track Matching Documentation

## Overview

The Track Matching module (`matcher.py`) handles the challenging task of identifying the same track across different music platforms (Spotify and Apple Music).

## The Challenge

The same song can have:
- Different metadata (typos, formatting)
- Different IDs on each platform
- Different availability (regional restrictions)
- Different featured artists
- Remixes/versions with similar names

## Matching Strategies

### 1. ISRC Matching (Primary)

**ISRC** (International Standard Recording Code) is a unique identifier for sound recordings.

**Reliability**: 99%+

**Implementation:**
```python
def match_by_isrc(spotify_track: Track, apple_client: AppleMusicClient) -> Optional[Track]:
    """Match track using ISRC code."""

    if not spotify_track.isrc:
        return None

    apple_track = apple_client.search_track(isrc=spotify_track.isrc)
    return apple_track
```

**Advantages:**
- Unique per recording
- Platform-independent
- Handles metadata variations

**Limitations:**
- Not all tracks have ISRC
- Independent/user-uploaded tracks often lack ISRC
- Some platforms don't expose ISRC via API

---

### 2. Metadata Matching (Fallback)

Match using artist, title, album, and duration.

**Reliability**: 80-95% (depends on metadata quality)

**Implementation:**
```python
def match_by_metadata(spotify_track: Track, apple_client: AppleMusicClient) -> Optional[Track]:
    """Match track using metadata search."""

    # Build search query
    query = f"{spotify_track.artist} {spotify_track.title}"

    # Search Apple Music
    results = apple_client.search_track(query=query)

    if not results:
        return None

    # Find best match from results
    best_match = find_best_match(spotify_track, results)
    return best_match
```

---

### 3. Fuzzy Matching (Enhanced Fallback)

Use similarity scoring for inexact matches.

**Reliability**: 70-90%

**Implementation:**
```python
from difflib import SequenceMatcher
from rapidfuzz import fuzz

def find_best_match(source_track: Track, candidates: List[Track]) -> Optional[Track]:
    """Find best match using fuzzy string matching."""

    best_score = 0
    best_match = None

    for candidate in candidates:
        score = compute_similarity(source_track, candidate)

        if score > best_score and score >= MATCH_THRESHOLD:
            best_score = score
            best_match = candidate

    return best_match

def compute_similarity(track1: Track, track2: Track) -> float:
    """Compute similarity score (0-100)."""

    # Normalize strings
    title1 = normalize_string(track1.title)
    title2 = normalize_string(track2.title)

    artist1 = normalize_string(track1.artist)
    artist2 = normalize_string(track2.artist)

    album1 = normalize_string(track1.album)
    album2 = normalize_string(track2.album)

    # Compute individual similarities
    title_sim = fuzz.ratio(title1, title2)
    artist_sim = fuzz.ratio(artist1, artist2)
    album_sim = fuzz.ratio(album1, album2)

    # Duration similarity (absolute difference in seconds)
    duration_diff = abs(track1.duration_ms - track2.duration_ms) / 1000
    duration_sim = max(0, 100 - (duration_diff * 10))  # Penalty: 10 points per second

    # Weighted average
    score = (
        title_sim * 0.4 +
        artist_sim * 0.35 +
        album_sim * 0.15 +
        duration_sim * 0.10
    )

    return score
```

**Normalization:**
```python
import re
import unicodedata

def normalize_string(s: str) -> str:
    """Normalize string for comparison."""

    # Convert to lowercase
    s = s.lower()

    # Remove accents/diacritics
    s = unicodedata.normalize('NFKD', s)
    s = s.encode('ASCII', 'ignore').decode('ASCII')

    # Remove punctuation and extra whitespace
    s = re.sub(r'[^\w\s]', '', s)
    s = re.sub(r'\s+', ' ', s).strip()

    # Remove common suffixes (remaster, explicit, etc.)
    suffixes = ['remaster', 'remastered', 'explicit', 'clean', 'radio edit', 'album version']
    for suffix in suffixes:
        s = s.replace(suffix, '')

    return s.strip()
```

---

### 4. Manual Mapping (Last Resort)

User can manually link tracks that couldn't be matched.

**Implementation:**
```python
class ManualMatcher:
    def __init__(self, db: Database):
        self.db = db

    def add_manual_mapping(self, spotify_id: str, apple_id: str):
        """Manually link a Spotify track to an Apple Music track."""

        self.db.execute("""
            INSERT INTO manual_mappings (spotify_id, apple_id)
            VALUES (?, ?)
        """, (spotify_id, apple_id))

    def get_manual_mapping(self, spotify_id: str) -> Optional[str]:
        """Get manually mapped Apple Music ID."""

        result = self.db.query("""
            SELECT apple_id FROM manual_mappings WHERE spotify_id = ?
        """, (spotify_id,))

        return result[0] if result else None
```

---

## Matching Flow

```python
class TrackMatcher:
    def __init__(self, spotify_client, apple_client, db):
        self.spotify = spotify_client
        self.apple = apple_client
        self.db = db

    def match_track(self, spotify_track: Track) -> Optional[Track]:
        """Match a Spotify track to Apple Music using multiple strategies."""

        # Strategy 1: Check manual mappings first
        manual_apple_id = self.db.get_manual_mapping(spotify_track.spotify_id)
        if manual_apple_id:
            return self.apple.get_track_by_id(manual_apple_id)

        # Strategy 2: Check local database (already matched)
        if spotify_track.isrc:
            local_track = self.db.get_track_by_isrc(spotify_track.isrc)
            if local_track and local_track.apple_id:
                return self.apple.get_track_by_id(local_track.apple_id)

        # Strategy 3: ISRC matching via API
        if spotify_track.isrc:
            apple_track = match_by_isrc(spotify_track, self.apple)
            if apple_track:
                self.db.upsert_track(merge_track_data(spotify_track, apple_track))
                return apple_track

        # Strategy 4: Metadata matching
        apple_track = match_by_metadata(spotify_track, self.apple)
        if apple_track:
            # Verify it's a good match
            similarity = compute_similarity(spotify_track, apple_track)
            if similarity >= 85:  # Threshold
                self.db.upsert_track(merge_track_data(spotify_track, apple_track))
                return apple_track

        # Strategy 5: Mark as unmatched
        return None
```

---

## Handling Unmatched Tracks

### Track Unavailable

**Scenario**: Track exists on Spotify but not available on Apple Music (or vice versa).

**Causes:**
- Regional restrictions
- Licensing issues
- Track removed from catalog
- Independent/uploaded tracks

**Solution:**
1. Mark as conflict
2. Show to user during sync
3. Options:
   - Skip (don't sync to other platform)
   - Find alternative (manual search)
   - Remove from both platforms

---

## Performance Optimization

### Caching

Cache match results to avoid repeated API calls.

```python
class CachedMatcher:
    def __init__(self, matcher: TrackMatcher):
        self.matcher = matcher
        self.cache = {}  # {spotify_id: apple_track}

    def match_track(self, spotify_track: Track) -> Optional[Track]:
        """Match track with caching."""

        if spotify_track.spotify_id in self.cache:
            return self.cache[spotify_track.spotify_id]

        result = self.matcher.match_track(spotify_track)
        self.cache[spotify_track.spotify_id] = result
        return result
```

### Batch Matching

Match multiple tracks in parallel.

```python
from concurrent.futures import ThreadPoolExecutor

def batch_match_tracks(spotify_tracks: List[Track], matcher: TrackMatcher) -> Dict[str, Optional[Track]]:
    """Match tracks in parallel."""

    results = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(matcher.match_track, track): track for track in spotify_tracks}

        for future in futures:
            track = futures[future]
            matched = future.result()
            results[track.spotify_id] = matched

    return results
```

---

## Match Confidence Scoring

Assign confidence level to matches.

```python
class MatchResult:
    def __init__(self, track: Optional[Track], confidence: float, method: str):
        self.track = track
        self.confidence = confidence  # 0-100
        self.method = method  # 'isrc', 'metadata', 'fuzzy', 'manual'

    def is_confident(self) -> bool:
        """Return True if match is confident enough to auto-apply."""
        return self.confidence >= 90

# Usage
def match_with_confidence(spotify_track: Track) -> MatchResult:
    # ISRC match: 100% confidence
    if spotify_track.isrc:
        apple_track = match_by_isrc(spotify_track, apple_client)
        if apple_track:
            return MatchResult(apple_track, confidence=100, method='isrc')

    # Metadata match: variable confidence based on similarity
    apple_track = match_by_metadata(spotify_track, apple_client)
    if apple_track:
        similarity = compute_similarity(spotify_track, apple_track)
        return MatchResult(apple_track, confidence=similarity, method='metadata')

    return MatchResult(None, confidence=0, method='none')
```

---

## Edge Cases

### 1. Multiple Artists

**Problem**: Artist order may differ ("Artist A feat. Artist B" vs "Artist B, Artist A")

**Solution**: Split and normalize artist list, compare as sets.

```python
def normalize_artists(artists: str) -> Set[str]:
    """Normalize artist string to set."""
    separators = [',', 'feat.', 'ft.', '&', 'and']
    for sep in separators:
        artists = artists.replace(sep, '|')

    return {normalize_string(a) for a in artists.split('|')}
```

### 2. Remixes and Versions

**Problem**: "Song (Radio Edit)" vs "Song (Album Version)"

**Solution**: Strip version suffixes for matching, but store original metadata.

### 3. Live Recordings

**Problem**: Studio version vs live version

**Solution**: Match only if both are live OR both are studio. Check for "live" keyword.

---

## Testing

```python
def test_isrc_matching():
    track = Track(isrc='USUM71703861', title='Get Lucky', artist='Daft Punk')
    matched = match_by_isrc(track, apple_client)

    assert matched is not None
    assert matched.isrc == track.isrc

def test_metadata_fuzzy_matching():
    track1 = Track(title='Lose Yourself', artist='Eminem', album='8 Mile')
    track2 = Track(title='Lose Yourself', artist='eminem', album='8 mile soundtrack')

    similarity = compute_similarity(track1, track2)
    assert similarity >= 85
```

## References

- [ISRC Standard](https://www.ifpi.org/isrc/)
- [Fuzzy String Matching](https://github.com/maxbachmann/RapidFuzz)
