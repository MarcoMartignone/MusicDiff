#!/usr/bin/env python3
"""Test script for database.py"""

from musicdiff.database import Database
import tempfile
import os

def test_database():
    """Test all database operations."""

    # Create temporary database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix='.db')
    db_path = temp_db.name
    temp_db.close()

    print(f"Testing database at: {db_path}")

    try:
        # Initialize database
        db = Database(db_path)
        db.init_schema()
        print("✓ Database initialized")

        # Test metadata
        db.set_metadata('test_key', 'test_value')
        assert db.get_metadata('test_key') == 'test_value'
        print("✓ Metadata operations work")

        # Test track operations
        track1 = {
            'isrc': 'USRC12345678',
            'spotify_id': 'spotify123',
            'title': 'Test Song',
            'artist': 'Test Artist',
            'album': 'Test Album',
            'duration_ms': 180000
        }

        db.upsert_track(track1)
        retrieved = db.get_track_by_isrc('USRC12345678')
        assert retrieved['title'] == 'Test Song'
        assert retrieved['spotify_id'] == 'spotify123'
        print("✓ Track operations work")

        # Test playlist operations
        playlist1 = {
            'spotify_id': 'spotify_playlist_1',
            'name': 'My Test Playlist',
            'description': 'A playlist for testing',
            'public': True
        }

        playlist_id = db.upsert_playlist(playlist1)
        retrieved_playlist = db.get_playlist(playlist_id)
        assert retrieved_playlist['name'] == 'My Test Playlist'
        print(f"✓ Playlist operations work (ID: {playlist_id})")

        # Test playlist tracks
        db.set_playlist_tracks(playlist_id, ['USRC12345678'])
        tracks = db.get_playlist_tracks(playlist_id)
        assert len(tracks) == 1
        assert tracks[0] == 'USRC12345678'
        print("✓ Playlist track operations work")

        # Test liked songs
        db.set_liked_songs(['USRC12345678'], 'spotify')
        liked = db.get_liked_songs('spotify')
        assert 'USRC12345678' in liked
        print("✓ Liked songs operations work")

        # Test sync log
        db.add_sync_log(
            status='success',
            changes=5,
            conflicts=0,
            details={'test': 'data'},
            duration=1.5
        )
        history = db.get_sync_history(limit=1)
        assert len(history) == 1
        assert history[0]['changes_applied'] == 5
        print("✓ Sync log operations work")

        # Test conflicts
        conflict_id = db.add_conflict(
            conflict_type='playlist',
            entity_id=playlist_id,
            spotify_data={'tracks': ['A', 'B']},
            apple_data={'tracks': ['A', 'C']}
        )
        conflicts = db.get_unresolved_conflicts()
        assert len(conflicts) == 1
        assert conflicts[0]['id'] == conflict_id

        db.resolve_conflict(conflict_id, 'spotify')
        conflicts = db.get_unresolved_conflicts()
        assert len(conflicts) == 0
        print("✓ Conflict operations work")

        # Test get all playlists
        playlists = db.get_all_playlists()
        assert len(playlists) == 1
        print("✓ Get all playlists works")

        print("\n🎉 All database tests passed!")

    finally:
        # Cleanup
        if os.path.exists(db_path):
            os.unlink(db_path)
            print(f"\n🧹 Cleaned up test database")

if __name__ == '__main__':
    test_database()
