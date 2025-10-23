# Deezer Integration

## Overview

MusicDiff integrates with Deezer using their private API, accessed via cookie-based authentication (ARL token). This allows creating and managing playlists on Deezer to mirror your Spotify playlists.

## Authentication

### ARL Token

Deezer uses an ARL (Account Resource Locator) token for authentication. This is a cookie-based authentication method that provides access to the private Deezer API.

**How to get your ARL token:**

1. Login to [deezer.com](https://www.deezer.com) in your browser
2. Open Developer Tools (F12)
3. Go to **Application** → **Cookies** → `https://www.deezer.com`
4. Find the cookie named `arl`
5. Copy its value (long alphanumeric string)

**Example ARL format:**
```
70ddf88ad6fedd405f9a94a89eb4d1313c32420d6504e636732e4b9a826bd0935cd185...
```

### Configuration

Add your ARL token to `.musicdiff/.env`:

```bash
export DEEZER_ARL="your_arl_token_here"
```

### Authentication Flow

```python
client = DeezerClient(arl_token=os.getenv('DEEZER_ARL'))
if client.authenticate():
    print(f"Authenticated as user ID: {client.user_id}")
    print(f"CSRF Token: {client.api_token}")
```

The client:
1. Sets ARL cookie in session
2. Calls `deezer.getUserData` API method
3. Extracts user ID from response
4. **Extracts CSRF token (`checkForm`)** from response - required for write operations
5. Stores user ID and CSRF token for subsequent requests

**Important:** The CSRF token (`checkForm`) is required for all write operations (create, update, delete). It's automatically extracted during authentication and used in subsequent API calls.

## API Endpoints

### Private API

MusicDiff uses Deezer's private API endpoint:
```
https://www.deezer.com/ajax/gw-light.php
```

All requests use this endpoint with different `method` parameters.

### Common Parameters

- `api_version`: `"1.0"`
- `api_token`: Varies per method, often starts as `"null"` then uses session token
- `method`: API method name (e.g., `deezer.getUserData`)

## Core Operations

### Fetch User Playlists

```python
playlists = client.fetch_library_playlists()
```

**API Call:**
```
GET /ajax/gw-light.php
  ?method=deezer.pagePlaylist
  &api_version=1.0
  &api_token={token}
```

**Returns:** List of `Playlist` objects with:
- `deezer_id`: Playlist ID on Deezer
- `name`: Playlist name
- `description`: Playlist description
- `public`: Public/private status
- `tracks`: List of `Track` objects

### Create Playlist

```python
deezer_id = client.create_playlist(
    name="My Playlist",
    description="Synced from Spotify",
    public=False  # Always creates private playlists for reliability
)
```

**API Call:**
```
POST /ajax/gw-light.php
  ?method=playlist.create
  &api_version=1.0
  &api_token={csrf_token}
Body (form-encoded):
  title: "My Playlist"
  description: "Synced from Spotify"
  status: 0     # 0=private, 1=public
  type: 0       # 0=playlist
```

**Returns:** New playlist ID (string)

**Note:** MusicDiff always creates **private playlists** (`status: 0`) to ensure they're owned by the user and reliably accessible. Public playlists may not appear in the user's library consistently.

### Add Tracks to Playlist

```python
client.add_tracks_to_playlist(
    playlist_id="123456789",
    track_ids=["686068732", "374479411"]
)
```

**API Call:**
```
POST /ajax/gw-light.php
  ?method=playlist.addSongs
  &api_version=1.0
  &api_token={csrf_token}
Content-Type: application/json

Body (JSON):
{
  "playlist_id": "123456789",
  "songs": [[686068732, 0], [374479411, 0]],
  "offset": -1
}
```

**Critical:** The request must be sent as **JSON body** (not form-encoded). The `songs` parameter is an array of arrays where:
- First element: Track ID (integer)
- Second element: Position index (always 0 in our implementation)

**Response on Success:**
```json
{"error":[],"results":true}
```

Empty `error` array means success. Non-empty error array or error object indicates failure.

### Remove Tracks from Playlist

```python
client.remove_tracks_from_playlist(
    playlist_id="123456789",
    track_ids=["686068732", "374479411"]
)
```

**API Call:**
```
POST /ajax/gw-light.php
  ?method=playlist.deleteSongs
  &api_version=1.0
  &api_token={csrf_token}
Content-Type: application/json

Body (JSON):
{
  "playlist_id": "123456789",
  "songs": [[686068732, 0], [374479411, 0]],
  "offset": -1
}
```

**Note:** Uses same format as `addSongs` - JSON body with array of arrays.

### Delete Playlist

```python
client.delete_playlist(playlist_id="123456789")
```

**API Call:**
```
POST /ajax/gw-light.php
  ?method=playlist.delete
  &api_version=1.0
  &api_token={token}
Body: {
  "playlist_id": "123456789"
}
```

### Search for Track

```python
track = client.search_track(isrc="USRC12345678")
```

**API Call:**
```
GET /ajax/gw-light.php
  ?method=song.getListByISRC
  &api_version=1.0
  &api_token={token}
  &isrc=USRC12345678
```

**Returns:** `Track` object if found, `None` otherwise

## Data Models

### Track

```python
@dataclass
class Track:
    deezer_id: str
    isrc: str
    title: str
    artist: str
    album: str
    duration_ms: int
```

### Playlist

```python
@dataclass
class Playlist:
    deezer_id: str
    name: str
    description: str
    public: bool
    tracks: List[Track]
```

## Error Handling

### Error Response Format

Deezer's private API returns errors in a specific format:

**Success Response:**
```json
{
  "error": [],        // Empty array = success
  "results": true     // or data
}
```

**Error Response:**
```json
{
  "error": {
    "VALID_TOKEN_REQUIRED": "Invalid CSRF token"
  },
  "results": {}
}
```

or

```json
{
  "error": {
    "ERROR_DATA_EXISTS": "This song already exists in this playlist"
  },
  "results": {}
}
```

**Important:** An empty `error` array `[]` means **success**, not failure. Only check for errors if the array/object contains actual error data.

### Rate Limiting

Deezer's private API has undocumented rate limits. The client implements exponential backoff:

```python
def _api_call_with_retry(self, method, url, max_retries=3, **kwargs):
    for attempt in range(max_retries):
        response = self.session.request(method, url, **kwargs)

        if response.status_code == 429:  # Rate limit
            wait_time = (2 ** attempt) * 1  # Exponential backoff
            time.sleep(wait_time)
            continue

        return response
```

### Common Errors

**Authentication Failed:**
```
Error: Failed to authenticate with Deezer
Cause: Invalid or expired ARL token
Fix: Get new ARL token from browser cookies
```

**Track Not Found:**
```
Error: Track not found by ISRC
Cause: Track not available on Deezer, or ISRC mismatch
Fix: Track will be skipped in sync
```

**Playlist Creation Failed:**
```
Error: Failed to create playlist
Cause: API error or permission issue
Fix: Check ARL token validity, retry
```

## Best Practices

### Session Management

- Create one `DeezerClient` instance and reuse it
- Session cookies are maintained across requests
- Authenticate once at the start

### Batch Operations

For adding/removing multiple tracks:
```python
# Good: Single API call with multiple tracks
client.add_tracks_to_playlist(playlist_id, [track1, track2, track3])

# Bad: Multiple API calls
client.add_tracks_to_playlist(playlist_id, [track1])
client.add_tracks_to_playlist(playlist_id, [track2])
client.add_tracks_to_playlist(playlist_id, [track3])
```

### Error Recovery

Always handle API failures gracefully:
```python
try:
    client.create_playlist(name, description)
except Exception as e:
    logger.error(f"Failed to create playlist: {e}")
    # Continue with next playlist
```

## Limitations

### ARL Token Expiry

- ARL tokens can expire (typically after several months)
- No automatic refresh mechanism
- User must manually get new token when it expires

### Private API

- Not officially documented by Deezer
- API structure may change without notice
- No official support or SLA

### Regional Restrictions

- Track availability varies by region
- ISRC lookup may fail for region-restricted content
- No way to determine track region restrictions in advance

### Track Matching

- Some tracks don't have ISRC codes
- ISRC may not be indexed in Deezer's search
- Manual matching not supported

## Security

### Token Storage

- ARL token stored in `.env` file
- File should have restrictive permissions (600)
- Token provides full account access - keep secret

### HTTPS

- All API calls use HTTPS
- Session cookies are secure and httpOnly
- No plaintext password transmission

## Future Enhancements

Potential improvements to Deezer integration:

- **Public API**: Switch to official public API if available
- **Token Refresh**: Automatic ARL token refresh mechanism
- **Batch Limits**: Optimize batch sizes for rate limits
- **Error Details**: Better error messages from API responses
- **Track Matching**: Fallback matching strategies for ISRC failures
- **Liked Songs**: Support for syncing liked songs/favorites
- **Albums**: Support for saved albums
