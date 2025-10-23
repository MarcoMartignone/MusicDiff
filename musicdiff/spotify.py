"""
Spotify API integration.

See docs/SPOTIFY.md for detailed documentation.
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from spotipy.exceptions import SpotifyException
import time
import os


@dataclass
class Track:
    """Represents a music track."""
    spotify_id: Optional[str] = None
    isrc: Optional[str] = None
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    uri: str = ""
    artists: List[str] = field(default_factory=list)


@dataclass
class Playlist:
    """Represents a playlist."""
    spotify_id: Optional[str] = None
    name: str = ""
    description: str = ""
    public: bool = False
    tracks: List[Track] = field(default_factory=list)
    snapshot_id: Optional[str] = None


@dataclass
class Album:
    """Represents an album."""
    spotify_id: Optional[str] = None
    name: str = ""
    artists: List[str] = field(default_factory=list)
    release_date: str = ""
    total_tracks: int = 0
    uri: str = ""


class SpotifyClient:
    """Client for interacting with Spotify Web API."""

    # Required OAuth scopes
    SCOPES = [
        'user-library-read',           # Read saved tracks and albums
        'user-library-modify',         # Modify saved tracks and albums
        'playlist-read-private',       # Read private playlists
        'playlist-read-collaborative', # Read collaborative playlists
        'playlist-modify-public',      # Modify public playlists
        'playlist-modify-private',     # Modify private playlists
    ]

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8888/callback", cache_path: str = None):
        """Initialize Spotify client.

        Args:
            client_id: Spotify application client ID
            client_secret: Spotify application client secret
            redirect_uri: OAuth redirect URI
            cache_path: Path to token cache file (default: ~/.musicdiff/.spotify_cache)
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri

        # Set default cache path - use project directory in Documents
        if cache_path is None:
            cache_dir = os.path.expanduser('~/Documents/MusicDiff/.musicdiff')
            os.makedirs(cache_dir, exist_ok=True)
            cache_path = os.path.join(cache_dir, '.spotify_cache')

        self.cache_path = cache_path
        self.sp = None  # Will hold spotipy.Spotify instance
        self.auth_manager = None

    def authenticate(self) -> bool:
        """Authenticate with Spotify using OAuth.

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            # Initialize OAuth manager
            self.auth_manager = SpotifyOAuth(
                client_id=self.client_id,
                client_secret=self.client_secret,
                redirect_uri=self.redirect_uri,
                scope=' '.join(self.SCOPES),
                cache_path=self.cache_path,
                open_browser=True
            )

            # Create Spotify client with auth manager
            self.sp = spotipy.Spotify(auth_manager=self.auth_manager)

            # Test authentication by getting current user
            user = self.sp.current_user()
            return user is not None

        except Exception as e:
            print(f"Authentication failed: {e}")
            return False

    def fetch_playlists_metadata(self) -> List[Dict]:
        """Fetch playlist metadata only (no track data) - fast!

        Returns list of dicts with: spotify_id, name, track_count
        Use this for displaying playlists when you don't need track details.

        Returns:
            List of playlist metadata dicts
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        playlists = []
        offset = 0
        limit = 50

        while True:
            results = self._api_call_with_retry(
                self.sp.current_user_playlists,
                limit=limit,
                offset=offset
            )

            for item in results['items']:
                playlists.append({
                    'spotify_id': item['id'],
                    'name': item['name'],
                    'track_count': item['tracks']['total']
                })

            if not results['next']:
                break
            offset += limit

        return playlists

    def fetch_playlists(self, progress_callback=None) -> List[Playlist]:
        """Fetch all user playlists with full track data.

        Args:
            progress_callback: Optional callback function(current, total, playlist_name)

        Returns:
            List of Playlist objects
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        playlists = []
        offset = 0
        limit = 50

        # First, get total count
        first_results = self._api_call_with_retry(
            self.sp.current_user_playlists,
            limit=1
        )
        total_playlists = first_results['total']

        current_playlist = 0
        offset = 0

        while True:
            results = self._api_call_with_retry(
                self.sp.current_user_playlists,
                limit=limit,
                offset=offset
            )

            for item in results['items']:
                current_playlist += 1

                if progress_callback:
                    progress_callback(current_playlist, total_playlists, item['name'])

                # Fetch full playlist with tracks
                playlist_data = self._api_call_with_retry(
                    self.sp.playlist,
                    item['id']
                )

                # Extract track data with pagination
                tracks = []
                track_items = playlist_data['tracks']['items']
                track_offset = len(track_items)

                # Parse initial tracks
                for track_item in track_items:
                    if track_item['track']:  # Can be None for deleted tracks
                        track = self._parse_track(track_item['track'])
                        tracks.append(track)

                # Handle playlist track pagination (if more than 100 tracks)
                while playlist_data['tracks']['next']:
                    more_tracks = self._api_call_with_retry(
                        self.sp.playlist_items,
                        item['id'],
                        limit=100,
                        offset=track_offset
                    )

                    for track_item in more_tracks['items']:
                        if track_item['track']:
                            track = self._parse_track(track_item['track'])
                            tracks.append(track)

                    track_offset += len(more_tracks['items'])

                    if not more_tracks['next']:
                        break

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

    def fetch_playlist_by_id(self, playlist_id: str, progress_callback=None) -> Optional[Playlist]:
        """Fetch a single playlist by ID with full track data.

        Args:
            playlist_id: Spotify playlist ID
            progress_callback: Optional callback function(current, total, playlist_name)

        Returns:
            Playlist object or None if not found
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        try:
            # Fetch playlist data
            playlist_data = self._api_call_with_retry(
                self.sp.playlist,
                playlist_id
            )

            if progress_callback:
                progress_callback(1, 1, playlist_data['name'])

            # Extract track data with pagination
            tracks = []
            track_items = playlist_data['tracks']['items']
            track_offset = len(track_items)

            # Parse initial tracks
            for track_item in track_items:
                if track_item['track']:  # Can be None for deleted tracks
                    track = self._parse_track(track_item['track'])
                    tracks.append(track)

            # Handle playlist track pagination (if more than 100 tracks)
            while playlist_data['tracks']['next']:
                more_tracks = self._api_call_with_retry(
                    self.sp.playlist_items,
                    playlist_id,
                    limit=100,
                    offset=track_offset
                )

                for track_item in more_tracks['items']:
                    if track_item['track']:
                        track = self._parse_track(track_item['track'])
                        tracks.append(track)

                track_offset += len(more_tracks['items'])

                if not more_tracks['next']:
                    break

            playlist = Playlist(
                spotify_id=playlist_data['id'],
                name=playlist_data['name'],
                description=playlist_data.get('description', ''),
                public=playlist_data['public'],
                tracks=tracks,
                snapshot_id=playlist_data['snapshot_id'],
            )

            return playlist

        except Exception as e:
            return None

    def fetch_liked_songs(self) -> List[Track]:
        """Fetch all liked/saved tracks.

        Returns:
            List of Track objects
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        tracks = []
        offset = 0
        limit = 50

        while True:
            results = self._api_call_with_retry(
                self.sp.current_user_saved_tracks,
                limit=limit,
                offset=offset
            )

            for item in results['items']:
                track = self._parse_track(item['track'])
                tracks.append(track)

            if not results['next']:
                break
            offset += limit

        return tracks

    def fetch_saved_albums(self) -> List[Album]:
        """Fetch all saved albums.

        Returns:
            List of Album objects
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        albums = []
        offset = 0
        limit = 50

        while True:
            results = self._api_call_with_retry(
                self.sp.current_user_saved_albums,
                limit=limit,
                offset=offset
            )

            for item in results['items']:
                album_data = item['album']
                album = Album(
                    spotify_id=album_data['id'],
                    name=album_data['name'],
                    artists=[artist['name'] for artist in album_data['artists']],
                    release_date=album_data.get('release_date', ''),
                    total_tracks=album_data['total_tracks'],
                    uri=album_data['uri']
                )
                albums.append(album)

            if not results['next']:
                break
            offset += limit

        return albums

    def create_playlist(self, name: str, description: str = "", public: bool = False) -> str:
        """Create a new playlist.

        Args:
            name: Playlist name
            description: Optional description
            public: Public (True) or Private (False)

        Returns:
            Spotify playlist ID
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        user_id = self.sp.current_user()['id']

        result = self._api_call_with_retry(
            self.sp.user_playlist_create,
            user_id,
            name,
            public=public,
            description=description
        )

        return result['id']

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Add tracks to a playlist.

        Args:
            playlist_id: Spotify playlist ID
            track_uris: List of Spotify track URIs (format: spotify:track:xxx)

        Returns:
            True on success
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Batch requests (max 100 tracks per call)
        batch_size = 100

        for i in range(0, len(track_uris), batch_size):
            batch = track_uris[i:i + batch_size]
            self._api_call_with_retry(
                self.sp.playlist_add_items,
                playlist_id,
                batch
            )

        return True

    def remove_tracks_from_playlist(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Remove tracks from a playlist.

        Args:
            playlist_id: Spotify playlist ID
            track_uris: List of Spotify track URIs to remove

        Returns:
            True on success
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Batch requests (max 100 tracks per call)
        batch_size = 100

        for i in range(0, len(track_uris), batch_size):
            batch = track_uris[i:i + batch_size]
            self._api_call_with_retry(
                self.sp.playlist_remove_all_occurrences_of_items,
                playlist_id,
                batch
            )

        return True

    def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist (unfollow it).

        Args:
            playlist_id: Spotify playlist ID

        Returns:
            True on success
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Spotify doesn't delete playlists, it "unfollows" them
        self._api_call_with_retry(
            self.sp.current_user_unfollow_playlist,
            playlist_id
        )

        return True

    def save_tracks(self, track_ids: List[str]) -> bool:
        """Save tracks to user's library (liked songs).

        Args:
            track_ids: List of Spotify track IDs

        Returns:
            True on success
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Batch requests (max 50 tracks per call for this endpoint)
        batch_size = 50

        for i in range(0, len(track_ids), batch_size):
            batch = track_ids[i:i + batch_size]
            self._api_call_with_retry(
                self.sp.current_user_saved_tracks_add,
                batch
            )

        return True

    def remove_saved_tracks(self, track_ids: List[str]) -> bool:
        """Remove tracks from user's library.

        Args:
            track_ids: List of Spotify track IDs

        Returns:
            True on success
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Batch requests (max 50 tracks per call)
        batch_size = 50

        for i in range(0, len(track_ids), batch_size):
            batch = track_ids[i:i + batch_size]
            self._api_call_with_retry(
                self.sp.current_user_saved_tracks_delete,
                batch
            )

        return True

    def save_albums(self, album_ids: List[str]) -> bool:
        """Save albums to user's library.

        Args:
            album_ids: List of Spotify album IDs

        Returns:
            True on success
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Batch requests (max 50 albums per call)
        batch_size = 50

        for i in range(0, len(album_ids), batch_size):
            batch = album_ids[i:i + batch_size]
            self._api_call_with_retry(
                self.sp.current_user_saved_albums_add,
                batch
            )

        return True

    def remove_saved_albums(self, album_ids: List[str]) -> bool:
        """Remove albums from user's library.

        Args:
            album_ids: List of Spotify album IDs

        Returns:
            True on success
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Batch requests (max 50 albums per call)
        batch_size = 50

        for i in range(0, len(album_ids), batch_size):
            batch = album_ids[i:i + batch_size]
            self._api_call_with_retry(
                self.sp.current_user_saved_albums_delete,
                batch
            )

        return True

    def search_track(self, isrc: str = None, query: str = None) -> Optional[Track]:
        """Search for a track by ISRC or metadata.

        Args:
            isrc: International Standard Recording Code (most reliable)
            query: Fallback search query (e.g., "artist:Daft Punk track:Get Lucky")

        Returns:
            Track object or None if not found
        """
        if not self.sp:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Prefer ISRC search (most accurate)
        if isrc:
            results = self._api_call_with_retry(
                self.sp.search,
                q=f'isrc:{isrc}',
                type='track',
                limit=1
            )
            if results['tracks']['items']:
                return self._parse_track(results['tracks']['items'][0])

        # Fallback to metadata search
        if query:
            results = self._api_call_with_retry(
                self.sp.search,
                q=query,
                type='track',
                limit=5
            )
            if results['tracks']['items']:
                # Return best match (first result)
                return self._parse_track(results['tracks']['items'][0])

        return None

    def _parse_track(self, track_data: dict) -> Track:
        """Parse Spotify track data into Track object.

        Args:
            track_data: Raw track data from Spotify API

        Returns:
            Track object
        """
        external_ids = track_data.get('external_ids', {})
        artists = [artist['name'] for artist in track_data.get('artists', [])]

        # For compatibility with existing code, join artists into single string
        artist_str = ', '.join(artists) if artists else ''

        return Track(
            spotify_id=track_data['id'],
            isrc=external_ids.get('isrc'),
            title=track_data['name'],
            artist=artist_str,
            artists=artists,
            album=track_data.get('album', {}).get('name', ''),
            duration_ms=track_data.get('duration_ms', 0),
            uri=track_data['uri'],
        )

    def _api_call_with_retry(self, func, *args, max_retries=3, **kwargs):
        """Wrapper for API calls with retry logic.

        Args:
            func: Function to call
            *args: Positional arguments
            max_retries: Maximum number of retries
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If max retries exceeded
        """
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except SpotifyException as e:
                if e.http_status == 429:
                    # Rate limited - wait and retry
                    retry_after = int(e.headers.get('Retry-After', 1))
                    time.sleep(retry_after)
                elif e.http_status >= 500:
                    # Server error - retry with exponential backoff
                    time.sleep(2 ** attempt)
                else:
                    # Client error - don't retry
                    raise
            except Exception as e:
                # Unknown error - retry with backoff
                if attempt < max_retries - 1:
                    time.sleep(2 ** attempt)
                else:
                    raise

        raise Exception(f"Max retries exceeded for {func.__name__}")
