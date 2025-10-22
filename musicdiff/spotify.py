"""
Spotify API integration.

See docs/SPOTIFY.md for detailed documentation.
"""

from typing import List, Optional
from dataclasses import dataclass


@dataclass
class Track:
    """Represents a music track."""
    spotify_id: Optional[str] = None
    isrc: Optional[str] = None
    title: str = ""
    artist: str = ""
    album: str = ""
    duration_ms: int = 0


@dataclass
class Playlist:
    """Represents a playlist."""
    spotify_id: Optional[str] = None
    name: str = ""
    description: str = ""
    public: bool = False
    tracks: List[Track] = None
    snapshot_id: Optional[str] = None

    def __post_init__(self):
        if self.tracks is None:
            self.tracks = []


class SpotifyClient:
    """Client for interacting with Spotify Web API."""

    def __init__(self, client_id: str, client_secret: str, redirect_uri: str = "http://localhost:8888/callback"):
        """Initialize Spotify client.

        Args:
            client_id: Spotify application client ID
            client_secret: Spotify application client secret
            redirect_uri: OAuth redirect URI
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.redirect_uri = redirect_uri
        self.sp = None  # Will hold spotipy.Spotify instance

    def authenticate(self) -> bool:
        """Authenticate with Spotify using OAuth."""
        # TODO: Implement OAuth authentication
        # 1. Use spotipy.oauth2.SpotifyOAuth
        # 2. Open browser for user authorization
        # 3. Cache tokens
        raise NotImplementedError("Authentication not yet implemented")

    def fetch_playlists(self) -> List[Playlist]:
        """Fetch all user playlists."""
        # TODO: Implement playlist fetching
        raise NotImplementedError("Playlist fetching not yet implemented")

    def fetch_liked_songs(self) -> List[Track]:
        """Fetch all liked/saved tracks."""
        # TODO: Implement liked songs fetching
        raise NotImplementedError("Liked songs fetching not yet implemented")

    def create_playlist(self, name: str, description: str = "", public: bool = False) -> str:
        """Create a new playlist."""
        # TODO: Implement playlist creation
        raise NotImplementedError("Playlist creation not yet implemented")

    def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]) -> bool:
        """Add tracks to a playlist."""
        # TODO: Implement adding tracks
        raise NotImplementedError("Add tracks not yet implemented")

    def search_track(self, isrc: str = None, query: str = None) -> Optional[Track]:
        """Search for a track by ISRC or metadata."""
        # TODO: Implement track search
        raise NotImplementedError("Track search not yet implemented")
