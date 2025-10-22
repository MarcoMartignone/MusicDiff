#!/usr/bin/env python3
"""Test script for diff.py - 3-way merge algorithm"""

from musicdiff.diff import DiffEngine, ChangeType

def test_playlist_auto_merge_spotify():
    """Test playlist changed only on Spotify - should auto-merge to Apple."""
    print("Testing: Playlist auto-merge (Spotify → Apple)...")

    engine = DiffEngine()

    local = {
        'playlists': {
            'playlist1': {
                'name': 'My Playlist',
                'description': 'Original description',
                'tracks': ['track1', 'track2']
            }
        }
    }

    spotify = {
        'playlists': {
            'playlist1': {
                'name': 'My Playlist',
                'description': 'Updated description',  # Changed
                'tracks': ['track1', 'track2', 'track3']  # Added track3
            }
        }
    }

    apple = {
        'playlists': {
            'playlist1': {
                'name': 'My Playlist',
                'description': 'Original description',
                'tracks': ['track1', 'track2']  # Unchanged
            }
        }
    }

    result = engine.compute_diff(local, spotify, apple)

    assert len(result.auto_merge) == 1, f"Expected 1 auto-merge change, got {len(result.auto_merge)}"
    assert len(result.conflicts) == 0, f"Expected 0 conflicts, got {len(result.conflicts)}"
    assert result.auto_merge[0].source_platform == 'spotify'
    assert result.auto_merge[0].target_platform == 'apple'
    assert result.auto_merge[0].change_type == ChangeType.PLAYLIST_UPDATED

    print("✓ Playlist auto-merge (Spotify → Apple) works!")


def test_playlist_conflict():
    """Test playlist changed on both platforms - should create conflict."""
    print("Testing: Playlist conflict...")

    engine = DiffEngine()

    local = {
        'playlists': {
            'playlist1': {
                'name': 'My Playlist',
                'tracks': ['track1', 'track2']
            }
        }
    }

    spotify = {
        'playlists': {
            'playlist1': {
                'name': 'My Playlist',
                'tracks': ['track1', 'track2', 'track3']  # Added track3
            }
        }
    }

    apple = {
        'playlists': {
            'playlist1': {
                'name': 'My Playlist',
                'tracks': ['track1', 'track2', 'track4']  # Added track4 (different!)
            }
        }
    }

    result = engine.compute_diff(local, spotify, apple)

    assert len(result.auto_merge) == 0, f"Expected 0 auto-merge changes, got {len(result.auto_merge)}"
    assert len(result.conflicts) == 1, f"Expected 1 conflict, got {len(result.conflicts)}"
    assert result.conflicts[0].entity_type == 'playlist'
    assert result.conflicts[0].entity_id == 'playlist1'

    print("✓ Playlist conflict detection works!")


def test_playlist_created():
    """Test new playlist created on one platform."""
    print("Testing: Playlist creation...")

    engine = DiffEngine()

    local = {'playlists': {}}

    spotify = {
        'playlists': {
            'playlist1': {
                'name': 'New Playlist',
                'tracks': ['track1']
            }
        }
    }

    apple = {'playlists': {}}

    result = engine.compute_diff(local, spotify, apple)

    assert len(result.auto_merge) == 1
    assert result.auto_merge[0].change_type == ChangeType.PLAYLIST_CREATED
    assert result.auto_merge[0].data['name'] == 'New Playlist'

    print("✓ Playlist creation detection works!")


def test_playlist_deleted():
    """Test playlist deleted on one platform."""
    print("Testing: Playlist deletion...")

    engine = DiffEngine()

    local = {
        'playlists': {
            'playlist1': {
                'name': 'To Be Deleted',
                'tracks': ['track1']
            }
        }
    }

    spotify = {'playlists': {}}  # Deleted!

    apple = {
        'playlists': {
            'playlist1': {
                'name': 'To Be Deleted',
                'tracks': ['track1']
            }
        }
    }

    result = engine.compute_diff(local, spotify, apple)

    assert len(result.auto_merge) == 1
    assert result.auto_merge[0].change_type == ChangeType.PLAYLIST_DELETED
    assert result.auto_merge[0].source_platform == 'spotify'

    print("✓ Playlist deletion detection works!")


def test_liked_songs_changes():
    """Test liked songs changes."""
    print("Testing: Liked songs changes...")

    engine = DiffEngine()

    local = {'liked_songs': ['track1', 'track2', 'track3']}

    spotify = {'liked_songs': ['track1', 'track2', 'track4']}  # Removed track3, added track4

    apple = {'liked_songs': ['track1', 'track2', 'track3']}  # Unchanged

    result = engine.compute_diff(local, spotify, apple)

    # Should have 2 auto-merge changes: one for added, one for removed
    assert len(result.auto_merge) == 2
    assert len(result.conflicts) == 0

    # Check that we have add and remove changes
    change_types = [c.change_type for c in result.auto_merge]
    assert ChangeType.LIKED_SONG_ADDED in change_types
    assert ChangeType.LIKED_SONG_REMOVED in change_types

    print("✓ Liked songs diff works!")


def test_albums_changes():
    """Test album changes."""
    print("Testing: Album changes...")

    engine = DiffEngine()

    local = {'albums': ['album1', 'album2']}

    spotify = {'albums': ['album1', 'album2']}  # Unchanged

    apple = {'albums': ['album1', 'album2', 'album3']}  # Added album3

    result = engine.compute_diff(local, spotify, apple)

    assert len(result.auto_merge) == 1
    assert result.auto_merge[0].change_type == ChangeType.ALBUM_ADDED
    assert result.auto_merge[0].source_platform == 'apple'
    assert 'album3' in result.auto_merge[0].data['albums']

    print("✓ Album diff works!")


def test_no_changes():
    """Test when nothing changed."""
    print("Testing: No changes...")

    engine = DiffEngine()

    state = {
        'playlists': {
            'playlist1': {
                'name': 'Same',
                'tracks': ['track1']
            }
        },
        'liked_songs': ['track1'],
        'albums': ['album1']
    }

    result = engine.compute_diff(state, state, state)

    assert len(result.auto_merge) == 0
    assert len(result.conflicts) == 0
    assert result.summary() == "0 auto-merge changes, 0 conflicts"

    print("✓ No changes detection works!")


def test_multiple_playlists():
    """Test diff with multiple playlists."""
    print("Testing: Multiple playlists...")

    engine = DiffEngine()

    local = {
        'playlists': {
            'p1': {'name': 'Playlist 1', 'tracks': ['t1']},
            'p2': {'name': 'Playlist 2', 'tracks': ['t2']},
            'p3': {'name': 'Playlist 3', 'tracks': ['t3']},
        }
    }

    spotify = {
        'playlists': {
            'p1': {'name': 'Playlist 1', 'tracks': ['t1', 't4']},  # Updated
            'p2': {'name': 'Playlist 2', 'tracks': ['t2']},  # Unchanged
            # p3 deleted
            'p4': {'name': 'Playlist 4', 'tracks': ['t5']},  # Created
        }
    }

    apple = {
        'playlists': {
            'p1': {'name': 'Playlist 1', 'tracks': ['t1']},  # Unchanged
            'p2': {'name': 'Playlist 2', 'tracks': ['t2', 't6']},  # Updated
            'p3': {'name': 'Playlist 3', 'tracks': ['t3']},  # Unchanged
        }
    }

    result = engine.compute_diff(local, spotify, apple)

    # p1: Spotify changed → auto-merge
    # p2: Apple changed → auto-merge
    # p3: Spotify deleted → auto-merge
    # p4: Spotify created → auto-merge
    assert len(result.auto_merge) == 4
    assert len(result.conflicts) == 0

    print("✓ Multiple playlists diff works!")


def test_summary():
    """Test DiffResult summary."""
    print("Testing: DiffResult summary...")

    engine = DiffEngine()

    local = {'playlists': {'p1': {'name': 'P1', 'tracks': []}}}
    spotify = {'playlists': {'p1': {'name': 'P1', 'tracks': ['t1']}}}
    apple = {'playlists': {'p1': {'name': 'P1', 'tracks': ['t2']}}}

    result = engine.compute_diff(local, spotify, apple)

    summary = result.summary()
    assert "0 auto-merge" in summary
    assert "1 conflicts" in summary

    print("✓ Summary generation works!")


def run_all_tests():
    """Run all diff engine tests."""
    print("=" * 60)
    print("Running Diff Engine Tests")
    print("=" * 60)
    print()

    tests = [
        test_playlist_auto_merge_spotify,
        test_playlist_conflict,
        test_playlist_created,
        test_playlist_deleted,
        test_liked_songs_changes,
        test_albums_changes,
        test_no_changes,
        test_multiple_playlists,
        test_summary,
    ]

    for test in tests:
        test()
        print()

    print("=" * 60)
    print(f"🎉 All {len(tests)} diff engine tests passed!")
    print("=" * 60)


if __name__ == '__main__':
    run_all_tests()
