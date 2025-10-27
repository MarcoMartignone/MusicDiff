# Phase 1: NTS API Client Implementation

## Objective
Create a robust NTS API client that can parse NTS URLs and fetch episode tracklists.

## Implementation Tasks

### 1. Create `musicdiff/nts.py`

#### Classes/Functions Needed:
- `parse_nts_url(url: str) -> tuple[str, str]` - Extract show_alias and episode_alias
- `NTSClient` class with:
  - `fetch_episode_metadata(show_alias, episode_alias)` - Get episode info
  - `fetch_tracklist(show_alias, episode_alias)` - Get track list
  - `get_episode_from_url(url)` - Convenience method combining parse + fetch

#### Data Models:
```python
@dataclass
class NTSTrack:
    artist: str
    title: str
    uid: str
    offset: Optional[int] = None
    duration: Optional[int] = None

@dataclass
class NTSEpisode:
    name: str
    show_alias: str
    episode_alias: str
    broadcast_date: str
    description: str
    tracklist: List[NTSTrack]
```

## API Endpoint Details

**Base URL**: `https://www.nts.live`

**Tracklist Endpoint**:
```
GET /api/v2/shows/{show_alias}/episodes/{episode_alias}/tracklist
```

**Response Format**:
```json
{
  "metadata": {
    "resultset": {
      "count": 5,
      "offset": 0,
      "limit": 5
    }
  },
  "results": [
    {
      "artist": "Artist Name",
      "title": "Song Title",
      "uid": "uuid-string",
      "offset": 123,
      "duration": 234
    }
  ]
}
```

**Episode Metadata Endpoint** (optional, for richer info):
```
GET /api/v2/shows/{show_alias}/episodes/{episode_alias}
```

## URL Parsing

**Valid URL Formats**:
- `https://www.nts.live/shows/covco/episodes/covco-8th-december-2016`
- `http://www.nts.live/shows/covco/episodes/covco-8th-december-2016`
- `www.nts.live/shows/covco/episodes/covco-8th-december-2016`

**Regex Pattern**:
```python
pattern = r'(?:https?://)?(?:www\.)?nts\.live/shows/([^/]+)/episodes/([^/?]+)'
```

**Extract**:
- Group 1: `show_alias` (e.g., "covco")
- Group 2: `episode_alias` (e.g., "covco-8th-december-2016")

## Error Handling

- Invalid URL format → `ValueError` with clear message
- 404 Not Found → Episode doesn't exist
- Network errors → Retry with exponential backoff (3 attempts)
- Empty tracklist → Return empty list (valid state)
- API timeout → 30 second timeout

## Testing Phase 1

### Test Cases:

1. **URL Parsing**:
   ```python
   # Test valid URLs
   assert parse_nts_url("https://www.nts.live/shows/covco/episodes/covco-8th-december-2016")
   # Test invalid URLs
   pytest.raises(ValueError, parse_nts_url, "https://invalid-url.com")
   ```

2. **Tracklist Fetching**:
   ```bash
   # Manual test with real episode
   python -c "from musicdiff.nts import NTSClient; \
              client = NTSClient(); \
              tracks = client.fetch_tracklist('covco', 'covco-8th-december-2016'); \
              print(f'Found {len(tracks)} tracks'); \
              for t in tracks[:3]: print(f'- {t.artist} - {t.title}')"
   ```

3. **Error Cases**:
   - Test with non-existent episode
   - Test with malformed show alias
   - Test network error handling

### Success Criteria:
- ✅ Parse valid NTS URLs correctly
- ✅ Fetch tracklists for real episodes
- ✅ Handle errors gracefully with clear messages
- ✅ Return structured data (NTSTrack objects)

## Dependencies
- `requests` (already in requirements.txt)
- `dataclasses` (Python stdlib)
- `typing` (Python stdlib)
- `re` (Python stdlib)

## Example Usage After Phase 1:
```python
from musicdiff.nts import NTSClient

client = NTSClient()
url = "https://www.nts.live/shows/covco/episodes/covco-8th-december-2016"
episode = client.get_episode_from_url(url)

print(f"Episode: {episode.name}")
print(f"Tracks: {len(episode.tracklist)}")
for track in episode.tracklist[:5]:
    print(f"  {track.artist} - {track.title}")
```

## Next Steps After Phase 1
Once testing passes, proceed to Phase 2: Spotify Track Search
