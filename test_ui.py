#!/usr/bin/env python3
"""Visual test for UI components"""

from musicdiff.ui import UI
from musicdiff.diff import DiffResult, Change, Conflict, ChangeType
import time

def test_ui_components():
    """Test all UI components visually."""
    ui = UI()

    print("\n" + "=" * 70)
    print("MusicDiff UI Component Tests")
    print("=" * 70)

    # Test 1: Success/Error/Warning/Info messages
    print("\n1. Testing message types...")
    ui.print_success("Successfully synced 50 tracks")
    ui.print_error("Failed to connect to Spotify API")
    ui.print_warning("3 tracks could not be matched")
    ui.print_info("Fetching library data...")

    time.sleep(1)

    # Test 2: Status display
    print("\n2. Testing status display...")
    ui.show_status("Library Status", {
        "Last Sync": "2 hours ago",
        "Playlists": "42",
        "Liked Songs": "1,234",
        "Albums": "156",
        "Pending Changes": "5"
    })

    time.sleep(1)

    # Test 3: Diff summary with tree view
    print("\n3. Testing diff summary...")

    diff_result = DiffResult()

    # Add some auto-merge changes
    diff_result.auto_merge.append(Change(
        entity_type='playlist',
        entity_id='summer-vibes-2025',
        change_type=ChangeType.PLAYLIST_CREATED,
        source_platform='spotify',
        target_platform='apple',
        data={'name': 'Summer Vibes 2025'}
    ))

    diff_result.auto_merge.append(Change(
        entity_type='playlist',
        entity_id='workout-mix',
        change_type=ChangeType.PLAYLIST_UPDATED,
        source_platform='spotify',
        target_platform='apple',
        data={'tracks_added': ['track1', 'track2', 'track3']}
    ))

    diff_result.auto_merge.append(Change(
        entity_type='liked_songs',
        entity_id='all',
        change_type=ChangeType.LIKED_SONG_ADDED,
        source_platform='spotify',
        target_platform='apple',
        data={'tracks': ['track4', 'track5']}
    ))

    # Add a conflict
    spotify_change = Change(
        entity_type='playlist',
        entity_id='chill-mix',
        change_type=ChangeType.PLAYLIST_UPDATED,
        source_platform='spotify',
        target_platform='apple',
        data={
            'name': 'Chill Mix',
            'tracks': ['t1', 't2', 't3'],
            'tracks_added': ['t3'],
            'tracks_removed': []
        }
    )

    apple_change = Change(
        entity_type='playlist',
        entity_id='chill-mix',
        change_type=ChangeType.PLAYLIST_UPDATED,
        source_platform='apple',
        target_platform='spotify',
        data={
            'name': 'Chill Mix',
            'tracks': ['t1', 't2', 't4'],
            'tracks_added': ['t4'],
            'tracks_removed': []
        }
    )

    diff_result.conflicts.append(Conflict(
        entity_type='playlist',
        entity_id='chill-mix',
        spotify_change=spotify_change,
        apple_change=apple_change
    ))

    ui.show_diff_summary(diff_result)

    time.sleep(1)

    # Test 4: Change list display
    print("\n4. Testing change list...")
    ui.show_changes(diff_result.auto_merge, "Auto-Merge Changes")

    time.sleep(1)

    # Test 5: Conflict display
    print("\n5. Testing conflict display...")
    ui.show_conflict(diff_result.conflicts[0])

    time.sleep(1)

    # Test 6: Progress bar
    print("\n6. Testing progress bar...")
    with ui.create_progress("Syncing tracks") as progress:
        task = progress.add_task("Processing...", total=10)
        for i in range(10):
            time.sleep(0.1)
            progress.update(task, advance=1)

    ui.print_success("Progress bar test complete!")

    print("\n" + "=" * 70)
    print("All UI components rendered successfully!")
    print("=" * 70)
    print("\nNote: Interactive prompts (confirm, prompt_resolution) require")
    print("user input and are not tested automatically.")
    print("=" * 70 + "\n")


if __name__ == '__main__':
    test_ui_components()
