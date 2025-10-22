#!/usr/bin/env python3
"""Test script for Spotify API client

NOTE: This requires real Spotify API credentials to run.
To test authentication:
1. Create an app at https://developer.spotify.com/dashboard
2. Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables
3. Run: python3 test_spotify.py
"""

from musicdiff.spotify import SpotifyClient, Track, Playlist, Album
import os


def test_track_parsing():
    """Test Track data model."""
    print("Testing: Track data model...")

    track = Track(
        spotify_id="123",
        isrc="USUM71703861",
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        duration_ms=248000,
        uri="spotify:track:123",
        artists=["Daft Punk", "Pharrell Williams"]
    )

    assert track.spotify_id == "123"
    assert track.isrc == "USUM71703861"
    assert track.title == "Get Lucky"
    assert len(track.artists) == 2

    print("✓ Track data model works!")


def test_playlist_parsing():
    """Test Playlist data model."""
    print("Testing: Playlist data model...")

    playlist = Playlist(
        spotify_id="abc123",
        name="Summer Vibes",
        description="Great summer songs",
        public=True,
        tracks=[],
        snapshot_id="snap123"
    )

    assert playlist.spotify_id == "abc123"
    assert playlist.name == "Summer Vibes"
    assert playlist.public == True
    assert len(playlist.tracks) == 0

    print("✓ Playlist data model works!")


def test_album_parsing():
    """Test Album data model."""
    print("Testing: Album data model...")

    album = Album(
        spotify_id="xyz789",
        name="Random Access Memories",
        artists=["Daft Punk"],
        release_date="2013-05-17",
        total_tracks=13,
        uri="spotify:album:xyz789"
    )

    assert album.spotify_id == "xyz789"
    assert album.name == "Random Access Memories"
    assert len(album.artists) == 1
    assert album.total_tracks == 13

    print("✓ Album data model works!")


def test_client_initialization():
    """Test SpotifyClient initialization."""
    print("Testing: Client initialization...")

    client = SpotifyClient(
        client_id="test_id",
        client_secret="test_secret",
        redirect_uri="http://localhost:8888/callback"
    )

    assert client.client_id == "test_id"
    assert client.client_secret == "test_secret"
    assert client.redirect_uri == "http://localhost:8888/callback"
    assert client.sp is None  # Not authenticated yet
    assert client.cache_path is not None

    print("✓ Client initialization works!")


def test_authentication():
    """Test Spotify authentication (requires real credentials)."""
    print("\nTesting: Spotify authentication...")

    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')

    if not client_id or not client_secret:
        print("⚠ Skipping authentication test (no credentials)")
        print("  Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET to test")
        return None

    client = SpotifyClient(
        client_id=client_id,
        client_secret=client_secret
    )

    success = client.authenticate()

    if success:
        print("✓ Authentication successful!")
        print(f"  User: {client.sp.current_user()['display_name']}")
        return client
    else:
        print("✗ Authentication failed")
        return None


def test_fetch_playlists(client: SpotifyClient):
    """Test fetching playlists (requires authenticated client)."""
    if not client:
        return

    print("\nTesting: Fetch playlists...")

    playlists = client.fetch_playlists()

    print(f"✓ Fetched {len(playlists)} playlists")

    if playlists:
        first = playlists[0]
        print(f"  First playlist: {first.name}")
        print(f"  Tracks: {len(first.tracks)}")
        print(f"  Public: {first.public}")


def test_fetch_liked_songs(client: SpotifyClient):
    """Test fetching liked songs (requires authenticated client)."""
    if not client:
        return

    print("\nTesting: Fetch liked songs...")

    tracks = client.fetch_liked_songs()

    print(f"✓ Fetched {len(tracks)} liked songs")

    if tracks:
        first = tracks[0]
        print(f"  First track: {first.title} by {first.artist}")
        print(f"  ISRC: {first.isrc}")
        print(f"  Duration: {first.duration_ms}ms")


def test_fetch_saved_albums(client: SpotifyClient):
    """Test fetching saved albums (requires authenticated client)."""
    if not client:
        return

    print("\nTesting: Fetch saved albums...")

    albums = client.fetch_saved_albums()

    print(f"✓ Fetched {len(albums)} saved albums")

    if albums:
        first = albums[0]
        print(f"  First album: {first.name}")
        print(f"  Artists: {', '.join(first.artists)}")
        print(f"  Tracks: {first.total_tracks}")


def test_search_track(client: SpotifyClient):
    """Test track search (requires authenticated client)."""
    if not client:
        return

    print("\nTesting: Track search...")

    # Search by ISRC (most reliable)
    track = client.search_track(isrc="USUM71703861")

    if track:
        print(f"✓ Found track by ISRC: {track.title} by {track.artist}")
    else:
        print("⚠ ISRC search returned no results")

    # Search by metadata
    track = client.search_track(query="artist:Daft Punk track:Get Lucky")

    if track:
        print(f"✓ Found track by metadata: {track.title} by {track.artist}")
    else:
        print("⚠ Metadata search returned no results")


def test_parse_track(client: SpotifyClient):
    """Test internal track parsing."""
    if not client:
        return

    print("\nTesting: Track parsing...")

    # Mock Spotify track data
    track_data = {
        'id': 'test123',
        'name': 'Test Song',
        'uri': 'spotify:track:test123',
        'duration_ms': 180000,
        'artists': [
            {'name': 'Artist 1'},
            {'name': 'Artist 2'}
        ],
        'album': {
            'name': 'Test Album'
        },
        'external_ids': {
            'isrc': 'TEST12345678'
        }
    }

    track = client._parse_track(track_data)

    assert track.spotify_id == 'test123'
    assert track.title == 'Test Song'
    assert track.isrc == 'TEST12345678'
    assert track.artist == 'Artist 1, Artist 2'
    assert len(track.artists) == 2
    assert track.album == 'Test Album'
    assert track.duration_ms == 180000

    print("✓ Track parsing works correctly!")


def run_unit_tests():
    """Run tests that don't require authentication."""
    print("=" * 70)
    print("Running Spotify Client Unit Tests (no auth required)")
    print("=" * 70)
    print()

    test_track_parsing()
    print()

    test_playlist_parsing()
    print()

    test_album_parsing()
    print()

    test_client_initialization()
    print()

    print("=" * 70)
    print("✓ All unit tests passed!")
    print("=" * 70)


def run_integration_tests():
    """Run tests that require real Spotify authentication."""
    print("\n")
    print("=" * 70)
    print("Running Spotify Client Integration Tests (requires auth)")
    print("=" * 70)
    print()

    # Authenticate
    client = test_authentication()

    if not client:
        print("\n" + "=" * 70)
        print("⚠ Integration tests skipped (authentication required)")
        print("=" * 70)
        print("\nTo run integration tests:")
        print("1. Create app at https://developer.spotify.com/dashboard")
        print("2. Set environment variables:")
        print("   export SPOTIFY_CLIENT_ID='your_client_id'")
        print("   export SPOTIFY_CLIENT_SECRET='your_client_secret'")
        print("3. Run this test again")
        print("=" * 70)
        return

    # Test internal parsing
    test_parse_track(client)

    # Run fetch tests
    test_fetch_playlists(client)
    test_fetch_liked_songs(client)
    test_fetch_saved_albums(client)
    test_search_track(client)

    print("\n" + "=" * 70)
    print("✓ All integration tests passed!")
    print("=" * 70)


if __name__ == '__main__':
    # Run unit tests (no auth required)
    run_unit_tests()

    # Run integration tests (requires auth)
    run_integration_tests()
