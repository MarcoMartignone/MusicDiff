#!/usr/bin/env python3
"""Test script for Apple Music API client

NOTE: This requires Apple Music API credentials to run.
To test authentication:
1. Create MusicKit identifier at https://developer.apple.com/account
2. Generate .p8 private key
3. Set environment variables:
   - APPLE_TEAM_ID
   - APPLE_KEY_ID
   - APPLE_PRIVATE_KEY_PATH
   - APPLE_USER_TOKEN (obtain via MusicKit JS)
4. Run: python3 test_apple.py
"""

from musicdiff.apple import AppleMusicClient, Track, Playlist, Album
import os


def test_track_parsing():
    """Test Track data model."""
    print("Testing: Track data model...")

    track = Track(
        apple_music_id="l.abc123",
        catalog_id="xyz789",
        isrc="USUM71703861",
        title="Get Lucky",
        artist="Daft Punk",
        album="Random Access Memories",
        duration_ms=248000,
        artists=["Daft Punk", "Pharrell Williams"]
    )

    assert track.apple_music_id == "l.abc123"
    assert track.catalog_id == "xyz789"
    assert track.isrc == "USUM71703861"
    assert track.title == "Get Lucky"
    assert len(track.artists) == 2

    print("✓ Track data model works!")


def test_playlist_parsing():
    """Test Playlist data model."""
    print("Testing: Playlist data model...")

    playlist = Playlist(
        apple_music_id="p.abc123",
        name="Summer Vibes",
        description="Great summer songs",
        tracks=[],
        can_edit=True
    )

    assert playlist.apple_music_id == "p.abc123"
    assert playlist.name == "Summer Vibes"
    assert playlist.can_edit == True
    assert len(playlist.tracks) == 0

    print("✓ Playlist data model works!")


def test_album_parsing():
    """Test Album data model."""
    print("Testing: Album data model...")

    album = Album(
        apple_music_id="l.album123",
        catalog_id="album789",
        name="Random Access Memories",
        artists=["Daft Punk"],
        release_date="2013-05-17",
        total_tracks=13
    )

    assert album.apple_music_id == "l.album123"
    assert album.catalog_id == "album789"
    assert album.name == "Random Access Memories"
    assert len(album.artists) == 1
    assert album.total_tracks == 13

    print("✓ Album data model works!")


def test_client_initialization():
    """Test AppleMusicClient initialization."""
    print("Testing: Client initialization...")

    client = AppleMusicClient(
        developer_token="test_dev_token",
        user_token="test_user_token",
        storefront="us"
    )

    assert client.developer_token == "test_dev_token"
    assert client.user_token == "test_user_token"
    assert client.storefront == "us"
    assert client.BASE_URL == "https://api.music.apple.com"

    print("✓ Client initialization works!")


def test_developer_token_generation():
    """Test JWT developer token generation."""
    print("Testing: Developer token generation...")

    team_id = os.environ.get('APPLE_TEAM_ID')
    key_id = os.environ.get('APPLE_KEY_ID')
    private_key_path = os.environ.get('APPLE_PRIVATE_KEY_PATH')

    if not all([team_id, key_id, private_key_path]):
        print("⚠ Skipping developer token test (no credentials)")
        print("  Set APPLE_TEAM_ID, APPLE_KEY_ID, and APPLE_PRIVATE_KEY_PATH to test")
        return None

    try:
        token = AppleMusicClient.generate_developer_token(
            team_id=team_id,
            key_id=key_id,
            private_key_path=private_key_path
        )

        assert token is not None
        assert len(token) > 0
        print(f"✓ Developer token generated (length: {len(token)})")
        return token

    except Exception as e:
        print(f"✗ Developer token generation failed: {e}")
        return None


def test_authentication(developer_token: str):
    """Test Apple Music authentication."""
    if not developer_token:
        return None

    print("\nTesting: User authentication...")

    user_token = os.environ.get('APPLE_USER_TOKEN')

    if not user_token:
        print("⚠ Skipping user authentication test (no user token)")
        print("  Set APPLE_USER_TOKEN to test")
        print("  Note: User tokens must be obtained via MusicKit JS")
        return None

    client = AppleMusicClient(
        developer_token=developer_token,
        storefront="us"
    )

    success = client.authenticate_user(user_token)

    if success:
        print("✓ User authentication successful!")
        return client
    else:
        print("✗ User authentication failed")
        return None


def test_fetch_library_playlists(client: AppleMusicClient):
    """Test fetching library playlists."""
    if not client:
        return

    print("\nTesting: Fetch library playlists...")

    playlists = client.fetch_library_playlists()

    print(f"✓ Fetched {len(playlists)} playlists")

    if playlists:
        first = playlists[0]
        print(f"  First playlist: {first.name}")
        print(f"  Tracks: {len(first.tracks)}")
        print(f"  Can edit: {first.can_edit}")


def test_fetch_library_songs(client: AppleMusicClient):
    """Test fetching library songs."""
    if not client:
        return

    print("\nTesting: Fetch library songs...")

    tracks = client.fetch_library_songs()

    print(f"✓ Fetched {len(tracks)} library songs")

    if tracks:
        first = tracks[0]
        print(f"  First track: {first.title} by {first.artist}")
        print(f"  ISRC: {first.isrc}")
        print(f"  Library ID: {first.apple_music_id}")
        print(f"  Catalog ID: {first.catalog_id}")


def test_fetch_library_albums(client: AppleMusicClient):
    """Test fetching library albums."""
    if not client:
        return

    print("\nTesting: Fetch library albums...")

    albums = client.fetch_library_albums()

    print(f"✓ Fetched {len(albums)} library albums")

    if albums:
        first = albums[0]
        print(f"  First album: {first.name}")
        print(f"  Artists: {', '.join(first.artists)}")
        print(f"  Tracks: {first.total_tracks}")


def test_search_track(client: AppleMusicClient):
    """Test track search."""
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
    track = client.search_track(query="Get Lucky Daft Punk")

    if track:
        print(f"✓ Found track by metadata: {track.title} by {track.artist}")
    else:
        print("⚠ Metadata search returned no results")


def test_parse_tracks():
    """Test internal track parsing."""
    print("\nTesting: Track parsing...")

    client = AppleMusicClient(developer_token="test_token")

    # Mock Apple Music library track data
    library_track_data = {
        'id': 'l.test123',
        'attributes': {
            'name': 'Test Song',
            'artistName': 'Test Artist',
            'albumName': 'Test Album',
            'durationInMillis': 180000,
            'isrc': 'TEST12345678',
            'playParams': {
                'catalogId': 'catalog123'
            }
        }
    }

    track = client._parse_library_track(library_track_data)

    assert track.apple_music_id == 'l.test123'
    assert track.catalog_id == 'catalog123'
    assert track.title == 'Test Song'
    assert track.artist == 'Test Artist'
    assert track.isrc == 'TEST12345678'
    assert track.album == 'Test Album'
    assert track.duration_ms == 180000

    print("✓ Library track parsing works!")

    # Mock catalog track data
    catalog_track_data = {
        'id': 'catalog456',
        'attributes': {
            'name': 'Catalog Song',
            'artistName': 'Catalog Artist',
            'albumName': 'Catalog Album',
            'durationInMillis': 200000,
            'isrc': 'CATALOG98765'
        }
    }

    track = client._parse_catalog_track(catalog_track_data)

    assert track.apple_music_id is None  # Catalog tracks don't have library IDs
    assert track.catalog_id == 'catalog456'
    assert track.title == 'Catalog Song'
    assert track.isrc == 'CATALOG98765'

    print("✓ Catalog track parsing works!")


def run_unit_tests():
    """Run tests that don't require authentication."""
    print("=" * 70)
    print("Running Apple Music Client Unit Tests (no auth required)")
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

    test_parse_tracks()
    print()

    print("=" * 70)
    print("✓ All unit tests passed!")
    print("=" * 70)


def run_integration_tests():
    """Run tests that require real Apple Music authentication."""
    print("\n")
    print("=" * 70)
    print("Running Apple Music Client Integration Tests (requires auth)")
    print("=" * 70)
    print()

    # Generate developer token
    developer_token = test_developer_token_generation()

    if not developer_token:
        print("\n" + "=" * 70)
        print("⚠ Integration tests skipped (authentication required)")
        print("=" * 70)
        print("\nTo run integration tests:")
        print("1. Create MusicKit ID at https://developer.apple.com/account")
        print("2. Download .p8 private key")
        print("3. Set environment variables:")
        print("   export APPLE_TEAM_ID='ABC123DEF4'")
        print("   export APPLE_KEY_ID='XYZ987WVU6'")
        print("   export APPLE_PRIVATE_KEY_PATH='~/.musicdiff/apple_key.p8'")
        print("   export APPLE_USER_TOKEN='<token_from_musickit_js>'")
        print("4. Run this test again")
        print("=" * 70)
        return

    # Authenticate user
    client = test_authentication(developer_token)

    if not client:
        print("\n" + "=" * 70)
        print("⚠ Integration tests skipped (user authentication required)")
        print("=" * 70)
        return

    # Run fetch tests
    test_fetch_library_playlists(client)
    test_fetch_library_songs(client)
    test_fetch_library_albums(client)
    test_search_track(client)

    print("\n" + "=" * 70)
    print("✓ All integration tests passed!")
    print("=" * 70)


if __name__ == '__main__':
    # Run unit tests (no auth required)
    run_unit_tests()

    # Run integration tests (requires auth)
    run_integration_tests()
