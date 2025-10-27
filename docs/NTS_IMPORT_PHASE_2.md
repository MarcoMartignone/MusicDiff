# Phase 2: Spotify Track Search Implementation

## Objective
Extend the existing Spotify client to search for tracks by artist and title, returning Spotify URIs for playlist creation.

## Implementation Tasks

### 1. Extend `musicdiff/spotify.py`

Add new method to existing `SpotifyClient` class:

```python
def search_track(self, artist: str, title: str, limit: int = 5) -> Optional[str]:
    """
    Search Spotify for a track by artist and title.

    Args:
        artist: Track artist name
        title: Track title
        limit: Number of results to fetch (default: 5)

    Returns:
        Spotify track URI if found, None otherwise
    """
```

### 2. Search Strategy

**Query Construction**:
```python
# Option 1: Simple combined search
query = f"{artist} {title}"

# Option 2: Field-specific search (more accurate)
query = f"artist:{artist} track:{title}"

# Option 3: Fallback strategy (if Option 2 fails)
query = f"{artist} {title}"  # Try again without field filters
```

**Search Execution**:
```python
results = self.sp.search(q=query, type='track', limit=limit)
tracks = results['tracks']['items']
```

**Matching Logic**:
1. Return first result if found
2. Optional: Add fuzzy matching to validate result quality
3. Return None if no results

### 3. Enhanced Matching (Optional)

Use existing `TrackMatcher` from `matcher.py` for better accuracy:

```python
from .matcher import TrackMatcher

def search_track_with_validation(self, artist: str, title: str) -> Optional[str]:
    """Search with result validation using fuzzy matching."""
    results = self.sp.search(q=f"artist:{artist} track:{title}",
                            type='track', limit=5)

    for track in results['tracks']['items']:
        spotify_artist = track['artists'][0]['name']
        spotify_title = track['name']

        # Use TrackMatcher to validate similarity
        artist_match = TrackMatcher.fuzzy_match(artist, spotify_artist, threshold=80)
        title_match = TrackMatcher.fuzzy_match(title, spotify_title, threshold=80)

        if artist_match and title_match:
            return track['uri']

    return None
```

## Spotify Search API Details

**Endpoint**: Accessed via `spotipy.search()`

**Response Format**:
```json
{
  "tracks": {
    "items": [
      {
        "uri": "spotify:track:6rqhFgbbKwnb9MLmUQDhG6",
        "name": "Track Title",
        "artists": [{"name": "Artist Name"}],
        "album": {"name": "Album Name"},
        "popularity": 75
      }
    ]
  }
}
```

## Error Handling

- Rate limiting → Exponential backoff (already in SpotifyClient)
- Empty results → Return None (valid state)
- Network errors → Retry mechanism
- Invalid credentials → Clear error message

## Testing Phase 2

### Test Cases:

1. **Exact Match**:
   ```python
   # Test with well-known track
   uri = spotify_client.search_track("Radiohead", "Creep")
   assert uri is not None
   assert uri.startswith("spotify:track:")
   ```

2. **Fuzzy Match** (artist spelling variations):
   ```python
   # Test with artist name variations
   uri1 = spotify_client.search_track("Aphex Twin", "Windowlicker")
   uri2 = spotify_client.search_track("The Aphex Twin", "Windowlicker")
   # Should ideally return same track
   ```

3. **Not Found**:
   ```python
   # Test with non-existent track
   uri = spotify_client.search_track("NonExistentArtist123", "FakeTrack999")
   assert uri is None
   ```

4. **Integration Test with Phase 1**:
   ```bash
   # Fetch NTS tracklist and search each track on Spotify
   python -c "
   from musicdiff.nts import NTSClient
   from musicdiff.spotify import SpotifyClient

   nts = NTSClient()
   spotify = SpotifyClient()

   tracks = nts.fetch_tracklist('covco', 'covco-8th-december-2016')

   found = 0
   not_found = 0

   for track in tracks:
       uri = spotify.search_track(track.artist, track.title)
       if uri:
           found += 1
           print(f'✓ {track.artist} - {track.title}')
       else:
           not_found += 1
           print(f'✗ {track.artist} - {track.title}')

   print(f'\nResults: {found} found, {not_found} not found')
   print(f'Match rate: {found/(found+not_found)*100:.1f}%')
   "
   ```

### Success Criteria:
- ✅ Search returns valid Spotify URIs for known tracks
- ✅ Returns None for non-existent tracks
- ✅ Match rate > 70% on real NTS tracklists
- ✅ Handles rate limiting gracefully
- ✅ Integration with Phase 1 works smoothly

## Example Usage After Phase 2:
```python
from musicdiff.nts import NTSClient
from musicdiff.spotify import SpotifyClient

# Fetch NTS tracklist
nts = NTSClient()
episode = nts.get_episode_from_url("https://www.nts.live/shows/covco/...")

# Search each track on Spotify
spotify = SpotifyClient()
matched_uris = []

for track in episode.tracklist:
    uri = spotify.search_track(track.artist, track.title)
    if uri:
        matched_uris.append(uri)

print(f"Matched {len(matched_uris)}/{len(episode.tracklist)} tracks")
```

## Next Steps After Phase 2
Once testing shows acceptable match rates (>70%), proceed to Phase 3: CLI Command and Playlist Creation
