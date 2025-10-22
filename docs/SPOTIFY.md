# Spotify Module Documentation

## Overview

The Spotify module (`spotify.py`) handles all interactions with the Spotify Web API using the `spotipy` library. It manages authentication, fetches user library data, and applies changes to the user's Spotify account.

## Dependencies

- `spotipy`: Official Spotify Web API wrapper
- `requests`: HTTP client (used by spotipy)

## Authentication

### OAuth 2.0 Flow

MusicDiff uses the **Authorization Code Flow** with PKCE (Proof Key for Code Exchange) for secure authentication.

**Required Scopes:**
```python
SCOPES = [
    'user-library-read',           # Read saved tracks and albums
    'user-library-modify',         # Modify saved tracks and albums
    'playlist-read-private',       # Read private playlists
    'playlist-read-collaborative', # Read collaborative playlists
    'playlist-modify-public',      # Modify public playlists
    'playlist-modify-private',     # Modify private playlists
]
```

### Setup Process

1. User registers app at https://developer.spotify.com/dashboard
2. Obtains `client_id` and `client_secret`
3. Sets redirect URI (default: `http://localhost:8888/callback`)
4. MusicDiff stores credentials in `~/.musicdiff/config.yaml`

### Token Management

- Access tokens expire after 1 hour
- Refresh tokens used to obtain new access tokens
- Spotipy handles token refresh automatically
- Tokens cached in `~/.musicdiff/.spotify_cache`

## API Interface

### Class: `SpotifyClient`

Main class for Spotify operations.

```python
class SpotifyClient:
    def __init__(self, client_id: str, client_secret: str, redirect_uri: str)
    def authenticate(self) -> bool
    def fetch_playlists(self) -> List[Playlist]
    def fetch_liked_songs(self) -> List[Track]
    def fetch_saved_albums(self) -> List[Album]
    def create_playlist(self, name: str, description: str = "", public: bool = False) -> str
    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> bool
    def remove_tracks_from_playlist(self, playlist_id: str, track_uris: List[str]) -> bool
    def delete_playlist(self, playlist_id: str) -> bool
    def save_tracks(self, track_ids: List[str]) -> bool
    def remove_saved_tracks(self, track_ids: List[str]) -> bool
    def save_albums(self, album_ids: List[str]) -> bool
    def remove_saved_albums(self, album_ids: List[str]) -> bool
    def search_track(self, isrc: str = None, query: str = None) -> Optional[Track]
```

## Core Methods

### `fetch_playlists()`

Retrieves all user playlists including tracks.

**Returns:** List of `Playlist` objects

**Implementation:**
```python
def fetch_playlists(self) -> List[Playlist]:
    """Fetch all user playlists with full track data."""
    playlists = []

    # Get user's playlists (paginated)
    offset = 0
    limit = 50

    while True:
        results = self.sp.current_user_playlists(limit=limit, offset=offset)

        for item in results['items']:
            # Fetch full playlist with tracks
            playlist_data = self.sp.playlist(item['id'])

            # Extract track data
            tracks = []
            for track_item in playlist_data['tracks']['items']:
                track = self._parse_track(track_item['track'])
                tracks.append(track)

            playlist = Playlist(
                spotify_id=item['id'],
                name=item['name'],
                description=item.get('description', ''),
                public=item['public'],
                tracks=tracks,
                snapshot_id=item['snapshot_id'],
            )
            playlists.append(playlist)

        if not results['next']:
            break
        offset += limit

    return playlists
```

**Notes:**
- Handles pagination automatically
- Includes both public and private playlists
- `snapshot_id` used to detect modifications
- Fetches up to 100 tracks per playlist (paginated if more)

---

### `fetch_liked_songs()`

Retrieves all tracks from user's "Liked Songs" library.

**Returns:** List of `Track` objects

**Implementation:**
```python
def fetch_liked_songs(self) -> List[Track]:
    """Fetch all liked/saved tracks."""
    tracks = []
    offset = 0
    limit = 50

    while True:
        results = self.sp.current_user_saved_tracks(limit=limit, offset=offset)

        for item in results['items']:
            track = self._parse_track(item['track'])
            track.added_at = item['added_at']
            tracks.append(track)

        if not results['next']:
            break
        offset += limit

    return tracks
```

**Notes:**
- Maximum 10,000 liked songs (Spotify API limit)
- Includes `added_at` timestamp for sorting

---

### `fetch_saved_albums()`

Retrieves all saved albums.

**Returns:** List of `Album` objects

---

### `create_playlist()`

Creates a new playlist on Spotify.

**Parameters:**
- `name`: Playlist name
- `description`: Optional description
- `public`: Public (True) or Private (False)

**Returns:** Spotify playlist ID

**Example:**
```python
playlist_id = client.create_playlist(
    name="Summer Vibes 2025",
    description="Synced from Apple Music",
    public=False
)
```

---

### `add_tracks_to_playlist()`

Adds tracks to an existing playlist.

**Parameters:**
- `playlist_id`: Spotify playlist ID
- `track_uris`: List of Spotify track URIs (format: `spotify:track:xxx`)

**Returns:** `True` on success

**Notes:**
- Maximum 100 tracks per API call
- Automatically batches larger requests
- Appends to end of playlist

---

### `remove_tracks_from_playlist()`

Removes tracks from playlist.

**Parameters:**
- `playlist_id`: Spotify playlist ID
- `track_uris`: List of Spotify track URIs to remove

**Returns:** `True` on success

**Notes:**
- Removes all occurrences of each track
- Maximum 100 tracks per call

---

### `search_track()`

Searches for a track using ISRC or metadata.

**Parameters:**
- `isrc`: International Standard Recording Code (most reliable)
- `query`: Fallback search query (e.g., "artist:Daft Punk track:Get Lucky")

**Returns:** `Track` object or `None` if not found

**Implementation:**
```python
def search_track(self, isrc: str = None, query: str = None) -> Optional[Track]:
    """Search for track by ISRC or metadata query."""

    # Prefer ISRC search (most accurate)
    if isrc:
        results = self.sp.search(q=f'isrc:{isrc}', type='track', limit=1)
        if results['tracks']['items']:
            return self._parse_track(results['tracks']['items'][0])

    # Fallback to metadata search
    if query:
        results = self.sp.search(q=query, type='track', limit=5)
        if results['tracks']['items']:
            # Return best match (first result)
            return self._parse_track(results['tracks']['items'][0])

    return None
```

**Search Query Examples:**
```python
# ISRC search (most reliable)
track = client.search_track(isrc='USUM71703861')

# Metadata search
track = client.search_track(query='artist:Daft Punk track:Get Lucky')
```

---

## Data Models

### Track Object

```python
@dataclass
class Track:
    spotify_id: str
    isrc: Optional[str]
    name: str
    artists: List[str]
    album: str
    duration_ms: int
    uri: str  # Spotify URI (spotify:track:xxx)
    added_at: Optional[datetime] = None
```

### Playlist Object

```python
@dataclass
class Playlist:
    spotify_id: str
    name: str
    description: str
    public: bool
    tracks: List[Track]
    snapshot_id: str  # Used to detect changes
```

### Album Object

```python
@dataclass
class Album:
    spotify_id: str
    name: str
    artists: List[str]
    release_date: str
    total_tracks: int
    uri: str
```

## Helper Methods

### `_parse_track()`

Converts Spotify API track object to our `Track` model.

```python
def _parse_track(self, track_data: dict) -> Track:
    """Parse Spotify track data into Track object."""
    external_ids = track_data.get('external_ids', {})

    return Track(
        spotify_id=track_data['id'],
        isrc=external_ids.get('isrc'),
        name=track_data['name'],
        artists=[artist['name'] for artist in track_data['artists']],
        album=track_data['album']['name'],
        duration_ms=track_data['duration_ms'],
        uri=track_data['uri'],
    )
```

## Error Handling

### Rate Limiting

Spotify API has rate limits:
- **429 Too Many Requests**: Wait and retry
- Implement exponential backoff

```python
from spotipy.exceptions import SpotifyException
import time

def _api_call_with_retry(self, func, *args, max_retries=3, **kwargs):
    """Wrapper for API calls with retry logic."""
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except SpotifyException as e:
            if e.http_status == 429:
                retry_after = int(e.headers.get('Retry-After', 1))
                time.sleep(retry_after)
            elif e.http_status >= 500:
                # Server error, retry with backoff
                time.sleep(2 ** attempt)
            else:
                raise

    raise Exception(f"Max retries exceeded for {func.__name__}")
```

### Common Exceptions

- `SpotifyOauthError`: Authentication failed
- `SpotifyException`: General API error (check `http_status`)
- `SpotifyRateLimitError`: Too many requests (429)

## Testing

### Mock Client for Tests

```python
class MockSpotifyClient(SpotifyClient):
    """Mock client for testing without API calls."""

    def __init__(self):
        self.playlists = []
        self.liked_songs = []

    def fetch_playlists(self):
        return self.playlists
```

## API Limits

- **Rate Limit**: ~180 requests per minute per user
- **Playlist Tracks**: Max 100 per request
- **Search Results**: Max 50 per request
- **Liked Songs**: Max 10,000 total

## References

- [Spotify Web API Documentation](https://developer.spotify.com/documentation/web-api/)
- [Spotipy Documentation](https://spotipy.readthedocs.io/)
- [OAuth 2.0 Authorization Guide](https://developer.spotify.com/documentation/general/guides/authorization-guide/)
