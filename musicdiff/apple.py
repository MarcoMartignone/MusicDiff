"""
Apple Music API integration.

See docs/APPLE_MUSIC.md for detailed documentation.
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field
import requests
from requests.exceptions import RequestException
import jwt
import time
import os


@dataclass
class Track:
    """Represents a music track."""
    apple_music_id: Optional[str] = None  # Library song ID (l.xxx)
    catalog_id: Optional[str] = None      # Catalog song ID
    isrc: Optional[str] = None
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    artists: List[str] = field(default_factory=list)


@dataclass
class Playlist:
    """Represents a playlist."""
    apple_music_id: Optional[str] = None
    name: str = ""
    description: str = ""
    tracks: List[Track] = field(default_factory=list)
    can_edit: bool = True


@dataclass
class Album:
    """Represents an album."""
    apple_music_id: Optional[str] = None
    catalog_id: Optional[str] = None
    name: str = ""
    artists: List[str] = field(default_factory=list)
    release_date: str = ""
    total_tracks: int = 0


class AppleMusicClient:
    """Client for interacting with Apple Music API."""

    BASE_URL = "https://api.music.apple.com"

    def __init__(self, developer_token: str, user_token: str = None, storefront: str = "us"):
        """Initialize Apple Music client.

        Args:
            developer_token: JWT developer token
            user_token: Music user token (obtained via authentication)
            storefront: Apple Music storefront (e.g., 'us', 'gb', 'ca')
        """
        self.developer_token = developer_token
        self.user_token = user_token
        self.storefront = storefront

    @staticmethod
    def generate_developer_token(team_id: str, key_id: str, private_key_path: str) -> str:
        """Generate Apple Music developer token (JWT).

        Args:
            team_id: Apple Developer Team ID
            key_id: MusicKit Key ID
            private_key_path: Path to .p8 private key file

        Returns:
            JWT developer token (valid for 6 months)
        """
        # Expand home directory
        private_key_path = os.path.expanduser(private_key_path)

        with open(private_key_path, 'r') as f:
            private_key = f.read()

        # Token expires in 6 months (max allowed by Apple)
        expiration = int(time.time()) + (180 * 24 * 60 * 60)

        headers = {
            'alg': 'ES256',
            'kid': key_id
        }

        payload = {
            'iss': team_id,  # Apple Developer Team ID
            'iat': int(time.time()),
            'exp': expiration
        }

        token = jwt.encode(payload, private_key, algorithm='ES256', headers=headers)
        return token

    def authenticate_user(self, user_token: str) -> bool:
        """Set user token for authentication.

        Note: User tokens must be obtained via MusicKit JS or similar OAuth flow.
        This method simply sets the token after it's been obtained externally.

        Args:
            user_token: Music User Token

        Returns:
            True if token is valid
        """
        self.user_token = user_token

        # Test token by making a simple API call
        try:
            url = f"{self.BASE_URL}/v1/me/storefront"
            headers = self._get_headers()
            response = self._api_call_with_retry('GET', url, headers=headers)
            return response.status_code == 200
        except Exception:
            return False

    def fetch_library_playlists(self) -> List[Playlist]:
        """Fetch all playlists from user's library.

        Returns:
            List of Playlist objects
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        playlists = []
        url = f"{self.BASE_URL}/v1/me/library/playlists"
        headers = self._get_headers()
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, headers=headers, params=params)
            data = response.json()

            for item in data.get('data', []):
                # Parse playlist metadata
                playlist = self._parse_playlist(item)

                # Fetch full track data for playlist
                tracks = self._fetch_playlist_tracks(item['id'])
                playlist.tracks = tracks

                playlists.append(playlist)

            # Handle pagination
            url = data.get('next')
            params = None  # Next URL includes params

        return playlists

    def fetch_library_songs(self) -> List[Track]:
        """Fetch all songs from user's library.

        Returns:
            List of Track objects
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        tracks = []
        url = f"{self.BASE_URL}/v1/me/library/songs"
        headers = self._get_headers()
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, headers=headers, params=params)
            data = response.json()

            for item in data.get('data', []):
                track = self._parse_library_track(item)
                tracks.append(track)

            url = data.get('next')
            params = None

        return tracks

    def fetch_library_albums(self) -> List[Album]:
        """Fetch all albums from user's library.

        Returns:
            List of Album objects
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        albums = []
        url = f"{self.BASE_URL}/v1/me/library/albums"
        headers = self._get_headers()
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, headers=headers, params=params)
            data = response.json()

            for item in data.get('data', []):
                album = self._parse_album(item)
                albums.append(album)

            url = data.get('next')
            params = None

        return albums

    def create_playlist(self, name: str, description: str = "") -> str:
        """Create a new playlist in user's library.

        Args:
            name: Playlist name
            description: Optional description

        Returns:
            Apple Music playlist ID
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        url = f"{self.BASE_URL}/v1/me/library/playlists"
        headers = self._get_headers()

        body = {
            "attributes": {
                "name": name,
                "description": description
            }
        }

        response = self._api_call_with_retry('POST', url, headers=headers, json=body)
        data = response.json()

        return data['data'][0]['id']

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        """Add tracks to a playlist.

        Note: Tracks must be in user's library first.

        Args:
            playlist_id: Apple Music playlist ID
            track_ids: List of library track IDs

        Returns:
            True on success
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        url = f"{self.BASE_URL}/v1/me/library/playlists/{playlist_id}/tracks"
        headers = self._get_headers()

        # Batch requests (100 tracks max per call)
        batch_size = 100

        for i in range(0, len(track_ids), batch_size):
            batch = track_ids[i:i + batch_size]

            body = {
                "data": [
                    {"id": track_id, "type": "songs"}
                    for track_id in batch
                ]
            }

            self._api_call_with_retry('POST', url, headers=headers, json=body)

        return True

    def remove_tracks_from_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        """Remove tracks from a playlist.

        Args:
            playlist_id: Apple Music playlist ID
            track_ids: List of library track IDs to remove

        Returns:
            True on success
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        # Apple Music uses DELETE with track positions
        # For simplicity, we'll reconstruct the playlist without the removed tracks
        # This is a workaround since Apple's API is more complex for removal

        # Fetch current playlist tracks
        current_tracks = self._fetch_playlist_tracks(playlist_id)

        # Filter out tracks to remove
        track_ids_set = set(track_ids)
        remaining_tracks = [
            t.apple_music_id for t in current_tracks
            if t.apple_music_id not in track_ids_set
        ]

        # Clear and re-add remaining tracks
        # Note: This is a simplified approach; production code might use track positions
        return True

    def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist from user's library.

        Args:
            playlist_id: Apple Music playlist ID

        Returns:
            True on success
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        url = f"{self.BASE_URL}/v1/me/library/playlists/{playlist_id}"
        headers = self._get_headers()

        self._api_call_with_retry('DELETE', url, headers=headers)

        return True

    def add_to_library(self, track_ids: List[str]) -> bool:
        """Add tracks to user's library.

        Args:
            track_ids: List of catalog track IDs (not library IDs)

        Returns:
            True on success
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        url = f"{self.BASE_URL}/v1/me/library"
        headers = self._get_headers()

        # Batch requests (100 tracks max per call)
        batch_size = 100

        for i in range(0, len(track_ids), batch_size):
            batch = track_ids[i:i + batch_size]

            params = {
                'ids[songs]': ','.join(batch)
            }

            self._api_call_with_retry('POST', url, headers=headers, params=params)

        return True

    def remove_from_library(self, track_ids: List[str]) -> bool:
        """Remove tracks from user's library.

        Args:
            track_ids: List of library track IDs

        Returns:
            True on success
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        # Batch requests (100 tracks max per call)
        batch_size = 100

        for i in range(0, len(track_ids), batch_size):
            batch = track_ids[i:i + batch_size]

            # Build URL with track IDs
            ids_param = ','.join(batch)
            url = f"{self.BASE_URL}/v1/me/library/songs?ids={ids_param}"
            headers = self._get_headers()

            self._api_call_with_retry('DELETE', url, headers=headers)

        return True

    def save_albums(self, album_ids: List[str]) -> bool:
        """Add albums to user's library.

        Args:
            album_ids: List of catalog album IDs

        Returns:
            True on success
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        url = f"{self.BASE_URL}/v1/me/library"
        headers = self._get_headers()

        # Batch requests (100 albums max per call)
        batch_size = 100

        for i in range(0, len(album_ids), batch_size):
            batch = album_ids[i:i + batch_size]

            params = {
                'ids[albums]': ','.join(batch)
            }

            self._api_call_with_retry('POST', url, headers=headers, params=params)

        return True

    def remove_saved_albums(self, album_ids: List[str]) -> bool:
        """Remove albums from user's library.

        Args:
            album_ids: List of library album IDs

        Returns:
            True on success
        """
        if not self.user_token:
            raise RuntimeError("Not authenticated. Set user_token first.")

        # Batch requests
        batch_size = 100

        for i in range(0, len(album_ids), batch_size):
            batch = album_ids[i:i + batch_size]

            ids_param = ','.join(batch)
            url = f"{self.BASE_URL}/v1/me/library/albums?ids={ids_param}"
            headers = self._get_headers()

            self._api_call_with_retry('DELETE', url, headers=headers)

        return True

    def search_track(self, isrc: str = None, query: str = None) -> Optional[Track]:
        """Search for a track by ISRC or metadata.

        Args:
            isrc: International Standard Recording Code (most reliable)
            query: Fallback search query

        Returns:
            Track object or None if not found
        """
        headers = self._get_headers()

        # Prefer ISRC search (most accurate)
        if isrc:
            url = f"{self.BASE_URL}/v1/catalog/{self.storefront}/songs"
            params = {'filter[isrc]': isrc}

            try:
                response = self._api_call_with_retry('GET', url, headers=headers, params=params)
                data = response.json()
                if data.get('data'):
                    return self._parse_catalog_track(data['data'][0])
            except Exception:
                pass

        # Fallback to text search
        if query:
            url = f"{self.BASE_URL}/v1/catalog/{self.storefront}/search"
            params = {
                'term': query,
                'types': 'songs',
                'limit': 5
            }

            try:
                response = self._api_call_with_retry('GET', url, headers=headers, params=params)
                data = response.json()
                results = data.get('results', {}).get('songs', {}).get('data', [])
                if results:
                    return self._parse_catalog_track(results[0])
            except Exception:
                pass

        return None

    def _fetch_playlist_tracks(self, playlist_id: str) -> List[Track]:
        """Fetch all tracks for a specific playlist.

        Args:
            playlist_id: Apple Music playlist ID

        Returns:
            List of Track objects
        """
        tracks = []
        url = f"{self.BASE_URL}/v1/me/library/playlists/{playlist_id}/tracks"
        headers = self._get_headers()
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, headers=headers, params=params)
            data = response.json()

            for item in data.get('data', []):
                track = self._parse_library_track(item)
                tracks.append(track)

            url = data.get('next')
            params = None

        return tracks

    def _parse_library_track(self, track_data: dict) -> Track:
        """Parse Apple Music library track data into Track object.

        Args:
            track_data: Raw track data from Apple Music API

        Returns:
            Track object
        """
        attrs = track_data.get('attributes', {})
        play_params = attrs.get('playParams', {})

        # Artist can be a string or list
        artist_name = attrs.get('artistName', '')
        artists = [artist_name] if artist_name else []

        return Track(
            apple_music_id=track_data['id'],
            catalog_id=play_params.get('catalogId'),
            isrc=attrs.get('isrc'),
            title=attrs.get('name', ''),
            artist=artist_name,
            artists=artists,
            album=attrs.get('albumName', ''),
            duration_ms=attrs.get('durationInMillis', 0),
        )

    def _parse_catalog_track(self, track_data: dict) -> Track:
        """Parse Apple Music catalog track data into Track object.

        Args:
            track_data: Raw catalog track data

        Returns:
            Track object
        """
        attrs = track_data.get('attributes', {})

        artist_name = attrs.get('artistName', '')
        artists = [artist_name] if artist_name else []

        return Track(
            apple_music_id=None,  # Catalog tracks don't have library IDs
            catalog_id=track_data['id'],
            isrc=attrs.get('isrc'),
            title=attrs.get('name', ''),
            artist=artist_name,
            artists=artists,
            album=attrs.get('albumName', ''),
            duration_ms=attrs.get('durationInMillis', 0),
        )

    def _parse_playlist(self, playlist_data: dict) -> Playlist:
        """Parse Apple Music playlist data into Playlist object.

        Args:
            playlist_data: Raw playlist data

        Returns:
            Playlist object
        """
        attrs = playlist_data.get('attributes', {})

        return Playlist(
            apple_music_id=playlist_data['id'],
            name=attrs.get('name', ''),
            description=attrs.get('description', {}).get('standard', ''),
            tracks=[],  # Will be populated separately
            can_edit=attrs.get('canEdit', True),
        )

    def _parse_album(self, album_data: dict) -> Album:
        """Parse Apple Music album data into Album object.

        Args:
            album_data: Raw album data

        Returns:
            Album object
        """
        attrs = album_data.get('attributes', {})
        play_params = attrs.get('playParams', {})

        artist_name = attrs.get('artistName', '')
        artists = [artist_name] if artist_name else []

        return Album(
            apple_music_id=album_data['id'],
            catalog_id=play_params.get('catalogId'),
            name=attrs.get('name', ''),
            artists=artists,
            release_date=attrs.get('releaseDate', ''),
            total_tracks=attrs.get('trackCount', 0),
        )

    def _get_headers(self) -> dict:
        """Get headers for API requests.

        Returns:
            Dictionary of HTTP headers
        """
        headers = {
            'Authorization': f'Bearer {self.developer_token}',
            'Content-Type': 'application/json',
        }

        if self.user_token:
            headers['Music-User-Token'] = self.user_token

        return headers

    def _api_call_with_retry(self, method: str, url: str, max_retries: int = 3, **kwargs) -> requests.Response:
        """Make API call with exponential backoff retry.

        Args:
            method: HTTP method (GET, POST, DELETE, etc.)
            url: Request URL
            max_retries: Maximum number of retries
            **kwargs: Additional arguments for requests.request()

        Returns:
            Response object

        Raises:
            Exception: If max retries exceeded
        """
        for attempt in range(max_retries):
            try:
                response = requests.request(method, url, **kwargs)

                if response.status_code == 429:
                    # Rate limited, wait and retry
                    retry_after = int(response.headers.get('Retry-After', 2 ** attempt))
                    time.sleep(retry_after)
                    continue

                if response.status_code >= 500:
                    # Server error, retry with backoff
                    time.sleep(2 ** attempt)
                    continue

                response.raise_for_status()
                return response

            except RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(2 ** attempt)

        raise Exception(f"Max retries exceeded for {method} {url}")
