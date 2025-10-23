"""
Deezer API integration.

See docs/DEEZER.md for detailed documentation.
"""

from typing import List, Optional, Dict
from dataclasses import dataclass, field
import requests
from requests.exceptions import RequestException
import time
import hashlib
import json


@dataclass
class Track:
    """Represents a music track."""
    deezer_id: Optional[str] = None
    isrc: Optional[str] = None
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0
    artists: List[str] = field(default_factory=list)


@dataclass
class Playlist:
    """Represents a playlist."""
    deezer_id: Optional[str] = None
    name: str = ""
    description: str = ""
    tracks: List[Track] = field(default_factory=list)
    can_edit: bool = True
    public: bool = False


@dataclass
class Album:
    """Represents an album."""
    deezer_id: Optional[str] = None
    name: str = ""
    artists: List[str] = field(default_factory=list)
    release_date: str = ""
    total_tracks: int = 0


class DeezerClient:
    """Client for interacting with Deezer API."""

    BASE_URL = "https://api.deezer.com"
    PRIVATE_API_URL = "https://www.deezer.com/ajax/gw-light.php"

    def __init__(self, arl_token: str = None, debug: bool = False):
        """Initialize Deezer client.

        Args:
            arl_token: Deezer ARL authentication token
            debug: Enable debug logging for API calls
        """
        self.arl_token = arl_token
        self.session = requests.Session()
        self.user_id = None
        self.api_token = None  # CSRF token for API requests
        self.debug = debug

        if arl_token:
            self.session.cookies.set('arl', arl_token, domain='.deezer.com')

    def authenticate(self) -> bool:
        """Authenticate with Deezer using ARL token.

        Returns:
            True if authentication successful
        """
        if not self.arl_token:
            raise RuntimeError("ARL token not set")

        try:
            # Use private API to get user info with ARL cookie
            url = f"{self.PRIVATE_API_URL}"
            params = {
                'method': 'deezer.getUserData',
                'api_version': '1.0',
                'api_token': 'null'
            }

            response = self._api_call_with_retry('GET', url, params=params)

            if self.debug:
                print(f"\n[DEBUG] Authentication Request:")
                print(f"  URL: {url}")
                print(f"  Params: {params}")

            if response.status_code == 200:
                data = response.json()

                if self.debug:
                    print(f"\n[DEBUG] Authentication Response:")
                    print(f"  Status: {response.status_code}")
                    print(f"  Data keys: {list(data.keys())}")
                    if 'results' in data:
                        print(f"  Results keys: {list(data['results'].keys())}")

                if 'results' in data and 'USER' in data['results']:
                    self.user_id = str(data['results']['USER']['USER_ID'])

                    # Extract CSRF token (checkForm) for API requests
                    if 'checkForm' in data['results']:
                        self.api_token = data['results']['checkForm']
                        if self.debug:
                            print(f"  CSRF Token: {self.api_token[:20]}...")
                    else:
                        if self.debug:
                            print(f"  Warning: No checkForm token in response")

                    return True
                elif 'error' in data:
                    # ARL might be invalid
                    if self.debug:
                        print(f"  Error: {data['error']}")
                    return False

            return False
        except Exception as e:
            if self.debug:
                print(f"  Exception: {e}")
            return False

    def fetch_library_playlists_metadata(self, progress_callback=None) -> List[Dict]:
        """Fetch playlist metadata only (no track data) - fast!

        Returns list of dicts with: deezer_id, name, track_count
        Use this for displaying playlists when you don't need track details.

        Args:
            progress_callback: Optional callback function(current, total, playlist_name)

        Returns:
            List of playlist metadata dicts
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        playlists = []
        url = f"{self.BASE_URL}/user/{self.user_id}/playlists"
        params = {'limit': 100}

        # First, get total count
        first_response = self._api_call_with_retry('GET', url, params={'limit': 1})
        first_data = first_response.json()
        total_playlists = first_data.get('total', 0)

        current_playlist = 0
        url = f"{self.BASE_URL}/user/{self.user_id}/playlists"

        while url:
            response = self._api_call_with_retry('GET', url, params=params)
            data = response.json()

            for item in data.get('data', []):
                current_playlist += 1

                if progress_callback:
                    progress_callback(current_playlist, total_playlists, item.get('title', 'Unknown'))

                # Just metadata - no track fetching!
                playlists.append({
                    'id': item['id'],
                    'title': item.get('title', ''),
                    'track_count': item.get('nb_tracks', 0)
                })

            # Handle pagination
            url = data.get('next')
            params = None  # Next URL includes params

        return playlists

    def fetch_playlist_by_id(self, playlist_id: str) -> Optional[Playlist]:
        """Fetch a single playlist by ID with full track data.

        Args:
            playlist_id: Deezer playlist ID

        Returns:
            Playlist object or None if not found
        """
        try:
            # Fetch playlist metadata
            url = f"{self.BASE_URL}/playlist/{playlist_id}"
            response = self._api_call_with_retry('GET', url)
            data = response.json()

            if 'error' in data:
                return None

            # Parse playlist
            playlist = self._parse_playlist(data)

            # Fetch tracks
            tracks = self._fetch_playlist_tracks(playlist_id)
            playlist.tracks = tracks

            return playlist

        except Exception:
            return None

    def fetch_library_playlists(self) -> List[Playlist]:
        """Fetch all playlists from user's library with full track data.

        Returns:
            List of Playlist objects
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        playlists = []
        url = f"{self.BASE_URL}/user/{self.user_id}/playlists"
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, params=params)
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
        """Fetch all favorite/liked tracks from user's library.

        Returns:
            List of Track objects
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        tracks = []
        url = f"{self.BASE_URL}/user/{self.user_id}/tracks"
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, params=params)
            data = response.json()

            for item in data.get('data', []):
                track = self._parse_track(item)
                tracks.append(track)

            url = data.get('next')
            params = None

        return tracks

    def fetch_library_albums(self) -> List[Album]:
        """Fetch all albums from user's library.

        Returns:
            List of Album objects
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        albums = []
        url = f"{self.BASE_URL}/user/{self.user_id}/albums"
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, params=params)
            data = response.json()

            for item in data.get('data', []):
                album = self._parse_album(item)
                albums.append(album)

            url = data.get('next')
            params = None

        return albums

    def create_playlist(self, name: str, description: str = "", public: bool = False) -> str:
        """Create a new playlist in user's library.

        Args:
            name: Playlist name
            description: Optional description
            public: Whether playlist is public

        Returns:
            Deezer playlist ID
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Use private API for playlist creation (works with ARL authentication)
        api_token = self.api_token or 'null'
        url = f"{self.PRIVATE_API_URL}?method=playlist.create&api_version=1.0&api_token={api_token}"

        # Send data as form data in POST body
        data = {
            'title': name,
            'description': description if description else '',
            'status': 1 if public else 0,  # 0 = private, 1 = public
            'type': 0  # 0 = playlist
        }

        if self.debug:
            print(f"\n[DEBUG] Create Playlist Request:")
            print(f"  URL: {url}")
            print(f"  Data: {data}")
            print(f"  Cookies: arl={self.arl_token[:20]}...")

        response = self._api_call_with_retry('POST', url, data=data)

        if self.debug:
            print(f"\n[DEBUG] Create Playlist Response:")
            print(f"  Status: {response.status_code}")
            print(f"  Body: {response.text[:500]}")

        response_data = response.json()

        if self.debug:
            print(f"  Parsed: {response_data}")

        # Check for errors - empty array or dict means success
        error = response_data.get('error')
        if error and (isinstance(error, dict) or (isinstance(error, list) and len(error) > 0)):
            error_msg = error
            if isinstance(error_msg, dict):
                error_msg = error_msg.get('message', str(error_msg))
            raise RuntimeError(f"Failed to create playlist: {error_msg}")

        # Private API returns playlist ID in results
        playlist_id = response_data.get('results')
        if not playlist_id:
            raise RuntimeError(f"No playlist ID in response: {response_data}")

        if self.debug:
            print(f"  ✓ Playlist created with ID: {playlist_id}")

        return str(playlist_id)

    def add_tracks_to_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        """Add tracks to a playlist.

        Args:
            playlist_id: Deezer playlist ID
            track_ids: List of Deezer track IDs

        Returns:
            True on success
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Use private API for adding tracks (works with ARL authentication)
        api_token = self.api_token or 'null'
        url = f"{self.PRIVATE_API_URL}?method=playlist.addSongs&api_version=1.0&api_token={api_token}"

        # Convert list to JSON array format
        import json
        data = {
            'playlist_id': playlist_id,
            'songs': json.dumps([[int(tid), 0] for tid in track_ids]),  # Format: [[track_id, position]]
            'offset': -1  # Add to end of playlist
        }

        if self.debug:
            print(f"\n[DEBUG] Add Tracks Request:")
            print(f"  URL: {url}")
            print(f"  Playlist ID: {playlist_id}")
            print(f"  Track IDs: {track_ids}")
            print(f"  Data: {data}")

        response = self._api_call_with_retry('POST', url, data=data)

        if self.debug:
            print(f"\n[DEBUG] Add Tracks Response:")
            print(f"  Status: {response.status_code}")
            print(f"  Body: {response.text[:500]}")

        # Handle empty response (which means success for this endpoint)
        if not response.text or response.text.strip() == '':
            if self.debug:
                print(f"  ✓ Tracks added successfully (empty response = success)")
            return True

        try:
            response_data = response.json()

            if self.debug:
                print(f"  Parsed: {response_data}")

            # Check for errors - empty array or dict means success
            error = response_data.get('error')
            if error and (isinstance(error, dict) or (isinstance(error, list) and len(error) > 0)):
                if self.debug:
                    print(f"  Error: {error}")
                return False

            if self.debug:
                print(f"  ✓ Tracks added successfully")

            return True
        except Exception as e:
            if self.debug:
                print(f"  JSON parse error: {e}")
                print(f"  Assuming success based on HTTP {response.status_code}")
            # If we got HTTP 200 but can't parse JSON, assume success
            return response.status_code == 200

    def remove_tracks_from_playlist(self, playlist_id: str, track_ids: List[str]) -> bool:
        """Remove tracks from a playlist.

        Args:
            playlist_id: Deezer playlist ID
            track_ids: List of Deezer track IDs to remove

        Returns:
            True on success
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Use private API for removing tracks (works with ARL authentication)
        api_token = self.api_token or 'null'
        url = f"{self.PRIVATE_API_URL}?method=playlist.deleteSongs&api_version=1.0&api_token={api_token}"

        import json
        data = {
            'playlist_id': playlist_id,
            'songs': json.dumps([[int(tid), 0] for tid in track_ids])  # Format: [[track_id, 0]]
        }

        response = self._api_call_with_retry('POST', url, data=data)
        response_data = response.json()

        # Check for errors - empty array or dict means success
        error = response_data.get('error')
        if error and (isinstance(error, dict) or (isinstance(error, list) and len(error) > 0)):
            return False

        return True

    def delete_playlist(self, playlist_id: str) -> bool:
        """Delete a playlist from user's library.

        Args:
            playlist_id: Deezer playlist ID

        Returns:
            True on success
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Use private API for deleting playlist (works with ARL authentication)
        api_token = self.api_token or 'null'
        url = f"{self.PRIVATE_API_URL}?method=playlist.delete&api_version=1.0&api_token={api_token}"

        data = {
            'playlist_id': playlist_id
        }

        response = self._api_call_with_retry('POST', url, data=data)
        response_data = response.json()

        # Check for errors - empty array or dict means success
        error = response_data.get('error')
        if error and (isinstance(error, dict) or (isinstance(error, list) and len(error) > 0)):
            return False

        return True

    def add_to_library(self, track_ids: List[str]) -> bool:
        """Add tracks to user's favorites/library.

        Args:
            track_ids: List of Deezer track IDs

        Returns:
            True on success
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        # Add tracks one by one (Deezer API limitation)
        for track_id in track_ids:
            url = f"{self.BASE_URL}/user/{self.user_id}/tracks"
            params = {
                'track_id': track_id,
                'access_token': self._get_access_token()
            }

            self._api_call_with_retry('POST', url, params=params)

        return True

    def remove_from_library(self, track_ids: List[str]) -> bool:
        """Remove tracks from user's favorites/library.

        Args:
            track_ids: List of Deezer track IDs

        Returns:
            True on success
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        for track_id in track_ids:
            url = f"{self.BASE_URL}/user/{self.user_id}/tracks"
            params = {
                'track_id': track_id,
                'access_token': self._get_access_token()
            }

            self._api_call_with_retry('DELETE', url, params=params)

        return True

    def save_albums(self, album_ids: List[str]) -> bool:
        """Add albums to user's library.

        Args:
            album_ids: List of Deezer album IDs

        Returns:
            True on success
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        for album_id in album_ids:
            url = f"{self.BASE_URL}/user/{self.user_id}/albums"
            params = {
                'album_id': album_id,
                'access_token': self._get_access_token()
            }

            self._api_call_with_retry('POST', url, params=params)

        return True

    def remove_saved_albums(self, album_ids: List[str]) -> bool:
        """Remove albums from user's library.

        Args:
            album_ids: List of Deezer album IDs

        Returns:
            True on success
        """
        if not self.user_id:
            raise RuntimeError("Not authenticated. Call authenticate() first.")

        for album_id in album_ids:
            url = f"{self.BASE_URL}/user/{self.user_id}/albums"
            params = {
                'album_id': album_id,
                'access_token': self._get_access_token()
            }

            self._api_call_with_retry('DELETE', url, params=params)

        return True

    def search_track(self, isrc: str = None, query: str = None) -> Optional[Track]:
        """Search for a track by ISRC or metadata.

        Args:
            isrc: International Standard Recording Code (most reliable)
            query: Fallback search query

        Returns:
            Track object or None if not found
        """
        # Prefer ISRC search (most accurate)
        if isrc:
            url = f"{self.BASE_URL}/track/isrc:{isrc}"

            try:
                response = self._api_call_with_retry('GET', url)
                data = response.json()
                if data and 'id' in data:
                    return self._parse_track(data)
            except Exception:
                pass

        # Fallback to text search
        if query:
            url = f"{self.BASE_URL}/search/track"
            params = {
                'q': query,
                'limit': 5
            }

            try:
                response = self._api_call_with_retry('GET', url, params=params)
                data = response.json()
                results = data.get('data', [])
                if results:
                    return self._parse_track(results[0])
            except Exception:
                pass

        return None

    def _fetch_playlist_tracks(self, playlist_id: str) -> List[Track]:
        """Fetch all tracks for a specific playlist.

        Args:
            playlist_id: Deezer playlist ID

        Returns:
            List of Track objects
        """
        tracks = []
        url = f"{self.BASE_URL}/playlist/{playlist_id}/tracks"
        params = {'limit': 100}

        while url:
            response = self._api_call_with_retry('GET', url, params=params)
            data = response.json()

            for item in data.get('data', []):
                track = self._parse_track(item)
                tracks.append(track)

            url = data.get('next')
            params = None

        return tracks

    def _parse_track(self, track_data: dict) -> Track:
        """Parse Deezer track data into Track object.

        Args:
            track_data: Raw track data from Deezer API

        Returns:
            Track object
        """
        artist_name = track_data.get('artist', {}).get('name', '')
        artists = [artist_name] if artist_name else []

        return Track(
            deezer_id=str(track_data.get('id', '')),
            isrc=track_data.get('isrc'),
            title=track_data.get('title', ''),
            artist=artist_name,
            artists=artists,
            album=track_data.get('album', {}).get('title', ''),
            duration_ms=track_data.get('duration', 0) * 1000,  # Deezer uses seconds
        )

    def _parse_playlist(self, playlist_data: dict) -> Playlist:
        """Parse Deezer playlist data into Playlist object.

        Args:
            playlist_data: Raw playlist data

        Returns:
            Playlist object
        """
        return Playlist(
            deezer_id=str(playlist_data.get('id', '')),
            name=playlist_data.get('title', ''),
            description=playlist_data.get('description', ''),
            tracks=[],  # Will be populated separately
            can_edit=not playlist_data.get('is_loved_track', False),
            public=playlist_data.get('public', False),
        )

    def _parse_album(self, album_data: dict) -> Album:
        """Parse Deezer album data into Album object.

        Args:
            album_data: Raw album data

        Returns:
            Album object
        """
        artist_name = album_data.get('artist', {}).get('name', '')
        artists = [artist_name] if artist_name else []

        return Album(
            deezer_id=str(album_data.get('id', '')),
            name=album_data.get('title', ''),
            artists=artists,
            release_date=album_data.get('release_date', ''),
            total_tracks=album_data.get('nb_tracks', 0),
        )

    def _get_access_token(self) -> str:
        """Get access token for API requests.

        For ARL-based authentication, this returns the ARL token.
        In a full implementation, this would convert ARL to access token.

        Returns:
            Access token string
        """
        # Simplified: In a production implementation, you would exchange
        # the ARL token for an access token via Deezer's private API
        return self.arl_token or ""

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
                response = self.session.request(method, url, **kwargs)

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
