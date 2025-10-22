# Sync Logic Documentation

## Overview

The Sync module (`sync.py`) orchestrates the entire synchronization process. It coordinates between the diff engine, platform clients, and database to apply changes safely.

## Sync Workflow

```
┌─────────────────────────────────────────┐
│ 1. Fetch Current State                  │
│    - Spotify API                         │
│    - Apple Music API                     │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 2. Load Local State                     │
│    - From SQLite database                │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 3. Compute Diff                          │
│    - Run 3-way diff algorithm            │
│    - Categorize: auto-merge vs conflicts │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 4. Resolve Conflicts (if any)           │
│    - Interactive UI or auto-skip         │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 5. Apply Changes                         │
│    - Spotify API calls                   │
│    - Apple Music API calls               │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 6. Update Local State                   │
│    - Save to database                    │
│    - Log sync to history                 │
└─────────────────────────────────────────┘
```

## Class: `SyncEngine`

```python
class SyncEngine:
    def __init__(self, spotify_client, apple_client, database, ui)
    def sync(self, mode: SyncMode = SyncMode.INTERACTIVE) -> SyncResult
    def apply_changes(self, changes: List[Change]) -> ApplyResult
    def apply_change(self, change: Change) -> bool
```

## Sync Modes

### 1. Interactive Mode

Default mode for manual syncs.

**Behavior:**
- Shows all changes before applying
- Prompts for confirmation on each change type
- Opens interactive UI for conflicts
- Progress feedback in terminal

**Use Case:** `musicdiff sync`

---

### 2. Auto Mode

Automatically applies non-conflicting changes.

**Behavior:**
- Auto-applies all auto-merge changes
- Skips conflicts (logs them for later)
- No user prompts
- Suitable for scheduled syncs

**Use Case:** `musicdiff sync --auto` or daemon mode

---

### 3. Dry-Run Mode

Shows what would be synced without applying.

**Behavior:**
- Computes full diff
- Displays planned changes
- Does NOT call any platform APIs
- Does NOT update local state

**Use Case:** `musicdiff sync --dry-run`

---

### 4. Conflicts-Only Mode

Only resolves pending conflicts.

**Behavior:**
- Loads conflicts from database
- Opens interactive UI
- Applies resolutions
- Skips fetching/diffing

**Use Case:** `musicdiff resolve`

---

## Change Application

### Applying to Spotify

```python
def apply_to_spotify(self, change: Change) -> bool:
    """Apply change to Spotify."""

    if change.change_type == ChangeType.PLAYLIST_CREATED:
        # Create playlist on Spotify
        playlist_id = self.spotify.create_playlist(
            name=change.data['name'],
            description=change.data['description'],
            public=change.data.get('public', False)
        )

        # Add tracks
        track_uris = [self._get_spotify_uri(isrc) for isrc in change.data['tracks']]
        self.spotify.add_tracks_to_playlist(playlist_id, track_uris)

    elif change.change_type == ChangeType.PLAYLIST_UPDATED:
        # Update playlist metadata or tracks
        if 'name' in change.data:
            self.spotify.update_playlist_name(change.entity_id, change.data['name'])

        if 'tracks_added' in change.data:
            track_uris = [self._get_spotify_uri(isrc) for isrc in change.data['tracks_added']]
            self.spotify.add_tracks_to_playlist(change.entity_id, track_uris)

        if 'tracks_removed' in change.data:
            track_uris = [self._get_spotify_uri(isrc) for isrc in change.data['tracks_removed']]
            self.spotify.remove_tracks_from_playlist(change.entity_id, track_uris)

    elif change.change_type == ChangeType.PLAYLIST_DELETED:
        self.spotify.delete_playlist(change.entity_id)

    elif change.change_type == ChangeType.LIKED_SONG_ADDED:
        track_ids = [self._get_spotify_id(isrc) for isrc in change.data['tracks']]
        self.spotify.save_tracks(track_ids)

    elif change.change_type == ChangeType.LIKED_SONG_REMOVED:
        track_ids = [self._get_spotify_id(isrc) for isrc in change.data['tracks']]
        self.spotify.remove_saved_tracks(track_ids)

    return True
```

### Applying to Apple Music

Similar logic but using Apple Music API methods.

**Key Difference**: Tracks must be in library before adding to playlist.

```python
def apply_to_apple(self, change: Change) -> bool:
    """Apply change to Apple Music."""

    if change.change_type == ChangeType.PLAYLIST_CREATED:
        # Ensure all tracks are in library first
        track_ids = [self._get_apple_id(isrc) for isrc in change.data['tracks']]
        self.apple.add_to_library(track_ids)

        # Create playlist
        playlist_id = self.apple.create_playlist(
            name=change.data['name'],
            description=change.data['description']
        )

        # Add tracks to playlist
        self.apple.add_tracks_to_playlist(playlist_id, track_ids)

    # ... similar for other change types
```

## Error Handling

### Transactional Application

Changes should be atomic where possible.

```python
def apply_changes(self, changes: List[Change]) -> ApplyResult:
    """Apply all changes with error recovery."""

    applied = []
    failed = []

    for change in changes:
        try:
            success = self.apply_change(change)
            if success:
                applied.append(change)
            else:
                failed.append((change, "Application returned False"))

        except SpotifyException as e:
            # Spotify API error
            failed.append((change, f"Spotify error: {e}"))
            if e.http_status >= 500:
                # Server error, stop sync
                break

        except AppleMusicException as e:
            # Apple Music API error
            failed.append((change, f"Apple Music error: {e}"))

        except Exception as e:
            # Unexpected error
            failed.append((change, f"Unexpected error: {e}"))

    return ApplyResult(applied=applied, failed=failed)
```

### Rollback Strategy

**Problem**: What if sync fails halfway?

**Solutions:**

1. **No Rollback** (Current approach)
   - Changes are applied incrementally
   - Failed changes logged
   - User can retry or manually fix

2. **Two-Phase Commit** (Future enhancement)
   - Prepare all changes first
   - Apply atomically
   - Rollback on any failure

---

## Conflict Resolution

### Interactive Resolution

User chooses how to resolve each conflict.

```python
def resolve_conflict_interactive(self, conflict: Conflict) -> str:
    """Show UI and get user's resolution choice."""

    # Display conflict details
    self.ui.show_conflict(conflict)

    # Prompt for resolution
    choice = self.ui.prompt_choice([
        "Keep Spotify version",
        "Keep Apple Music version",
        "Manual merge",
        "Skip for now"
    ])

    if choice == "Keep Spotify version":
        return 'spotify'
    elif choice == "Keep Apple Music version":
        return 'apple'
    elif choice == "Manual merge":
        # Open interactive merge UI
        return self.ui.manual_merge(conflict)
    else:
        return 'skip'
```

### Auto Resolution

For daemon mode, conflicts are skipped.

```python
def resolve_conflict_auto(self, conflict: Conflict) -> str:
    """Auto-resolve conflict (usually skip)."""

    # Save to conflicts table for later manual resolution
    self.db.add_conflict(
        type=conflict.entity_type,
        entity_id=conflict.entity_id,
        spotify_data=conflict.spotify_change.data,
        apple_data=conflict.apple_change.data
    )

    return 'skip'
```

---

## State Update

After successful sync, update local database.

```python
def update_local_state(self, spotify_state, apple_state):
    """Update local database with new state."""

    # Update playlists
    for playlist in spotify_state.playlists:
        self.db.upsert_playlist(playlist)

    for playlist in apple_state.playlists:
        # Link to existing playlist if found
        existing = self.db.get_playlist_by_spotify_id(playlist.spotify_id)
        if existing:
            self.db.update_playlist(existing.id, apple_id=playlist.apple_id)
        else:
            self.db.upsert_playlist(playlist)

    # Update liked songs
    self.db.set_liked_songs(spotify_state.liked_songs, platform='spotify')
    self.db.set_liked_songs(apple_state.liked_songs, platform='apple')

    # Update metadata
    self.db.set_metadata('last_sync', datetime.now().isoformat())
```

---

## Sync Result

```python
@dataclass
class SyncResult:
    success: bool
    changes_applied: int
    conflicts_count: int
    conflicts_resolved: int
    failed_changes: List[Tuple[Change, str]]  # (change, error message)
    duration_seconds: float

    def summary(self) -> str:
        if self.success:
            return f"✓ Sync complete: {self.changes_applied} changes applied"
        else:
            return f"⚠ Sync partial: {self.changes_applied} applied, {len(self.failed_changes)} failed"
```

---

## Logging

All syncs are logged to the database.

```python
def log_sync(self, result: SyncResult):
    """Log sync to database."""

    status = 'success' if result.success else 'partial'

    details = {
        'changes_applied': result.changes_applied,
        'conflicts_resolved': result.conflicts_resolved,
        'failed_changes': len(result.failed_changes)
    }

    self.db.add_sync_log(
        status=status,
        changes=result.changes_applied,
        conflicts=result.conflicts_count,
        details=json.dumps(details)
    )
```

---

## Best Practices

1. **Idempotency**: Applying the same change twice should be safe
2. **Rate Limiting**: Respect API limits (batch requests, add delays)
3. **Error Recovery**: Log errors, continue with next change when possible
4. **User Feedback**: Show progress, estimated time, clear error messages
5. **Atomicity**: Where possible, batch related operations

## Testing

```python
def test_sync_auto_merge():
    # Mock clients
    spotify = MockSpotifyClient()
    apple = MockAppleMusicClient()
    db = MockDatabase()
    ui = MockUI()

    engine = SyncEngine(spotify, apple, db, ui)

    # Setup state
    db.save_playlist(Playlist(name="Test", tracks=["A"]))
    spotify.playlists = [Playlist(name="Test", tracks=["A", "B"])]  # Added B
    apple.playlists = [Playlist(name="Test", tracks=["A"])]         # Unchanged

    # Run sync
    result = engine.sync(mode=SyncMode.AUTO)

    # Verify
    assert result.success
    assert result.changes_applied == 1
    assert "B" in apple.playlists[0].tracks
```
