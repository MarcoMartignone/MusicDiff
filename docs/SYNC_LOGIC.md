# Sync Logic Documentation

## Overview

The Sync module (`sync.py`) orchestrates the one-way synchronization process from Spotify to Deezer. It coordinates between the Spotify client, Deezer client, track matcher, and database to safely mirror selected playlists.

## Sync Workflow

```
┌─────────────────────────────────────────┐
│ 1. Get Selected Playlists               │
│    - Query database for selections       │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 2. Check Playlist Status on Deezer      │
│    - Verify if playlists exist by ID     │
│    - If deleted, search by name          │
│    - Determine create vs update          │
│    - Avoid duplicate creation            │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 3. Compare Playlists (Smart Skip)       │
│    - Fetch Spotify & Deezer versions     │
│    - Compare track counts (fast check)   │
│    - Compare ISRCs in order              │
│    - Skip if already identical           │
└────────────────┬────────────────────────┘
                 │
                 │ If nothing to do: Exit with success
                 │ If changes detected: Continue
                 │
┌────────────────▼────────────────────────┐
│ 4. Show Preview & Get Confirmation      │
│    - Display accurate create/update list │
│    - Ask user to proceed                 │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 5. Fetch from Spotify                   │
│    - Get complete playlist data          │
│    - Include all tracks with ISRC        │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 6. Match Tracks to Deezer               │
│    - Search Deezer by ISRC               │
│    - Cache matches in database           │
│    - Skip tracks without ISRC            │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 7. Apply to Deezer                      │
│    - Create new playlists (private)      │
│    - Update existing (full overwrite)    │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 8. Clean Deselected                     │
│    - Delete playlists no longer selected │
└────────────────┬────────────────────────┘
                 │
┌────────────────▼────────────────────────┐
│ 9. Update Database                      │
│    - Mark playlists as synced            │
│    - Update sync timestamps              │
│    - Log sync results                    │
└─────────────────────────────────────────┘
```

## Class: `SyncEngine`

```python
class SyncEngine:
    def __init__(self, spotify_client, deezer_client, database, ui)
    def sync(self, mode: SyncMode = SyncMode.NORMAL) -> SyncResult
    def _fetch_spotify_playlists(self, playlist_ids: List[str]) -> List[Playlist]
    def _create_deezer_playlist(self, spotify_playlist: Playlist) -> str
    def _update_deezer_playlist(self, deezer_id: str, spotify_playlist: Playlist) -> None
    def _match_tracks_to_deezer(self, spotify_tracks: List[Track]) -> List[str]
    def _delete_deselected_playlists(self, selected_ids: List[str]) -> int
```

## Sync Modes

### 1. Normal Mode (Default)

Standard sync mode for regular use.

**Behavior:**
- Syncs all selected playlists
- Shows progress bar
- Displays success/error messages
- Updates database
- Returns sync results

**Use Case:** `musicdiff sync`

```python
result = sync_engine.sync(mode=SyncMode.NORMAL)
```

---

### 2. Dry-Run Mode

Preview mode - shows what would be synced without making changes.

**Behavior:**
- Fetches playlists from Spotify
- Checks what would be created/updated/deleted
- Does NOT call Deezer API
- Does NOT update database
- Returns empty result

**Use Case:** `musicdiff sync --dry-run`

```python
result = sync_engine.sync(mode=SyncMode.DRY_RUN)
```

**Example Output:**
```
[DRY RUN] The following changes would be made:

  CREATE: Summer Vibes 2025 (45 tracks)
  UPDATE: Workout Mix (32 tracks)
  UPDATE: Party Hits (67 tracks)
  DELETE: Old Playlist

No changes applied (dry run mode)
```

---

## Sync Process Details

### Step 1: Get Selected Playlists

```python
selected = self.db.get_selected_playlists()
```

Retrieves playlists marked as `selected=1` in the `playlist_selections` table.

**Example Result:**
```python
[
    {'spotify_id': 'abc123', 'name': 'Summer Vibes', 'track_count': 45, 'selected': True},
    {'spotify_id': 'def456', 'name': 'Workout Mix', 'track_count': 32, 'selected': True}
]
```

---

### Step 2: Check Playlist Status on Deezer

```python
# For each selected playlist, verify existence and find duplicates
for playlist_info in selected:
    synced = self.db.get_synced_playlist(spotify_id)

    if synced:
        playlist_exists = self._check_deezer_playlist_exists(synced['deezer_id'])

        if playlist_exists:
            # Will update existing
            to_update.append((name, track_count, synced['deezer_id']))
        else:
            # Synced playlist deleted - search for existing with same name
            existing_id = self._find_existing_deezer_playlist(name)
            if existing_id:
                to_update.append((name, track_count, existing_id))
            else:
                to_create.append((name, track_count))
    else:
        # Not synced - check if playlist already exists by name
        existing_id = self._find_existing_deezer_playlist(name)
        if existing_id:
            # Found existing - reuse it to avoid duplicates
            to_update.append((name, track_count, existing_id))
        else:
            to_create.append((name, track_count))
```

**Key Features:**
- **Duplicate Prevention**: Searches Deezer by name before creating
- **Smart Recovery**: If mapped playlist deleted, finds another with same name
- **Accurate Preview**: Knows exactly what will be created vs updated

**Benefits:**
- No duplicate "My Playlist", "My Playlist (2)", "My Playlist (3)"
- Recovers from manual deletions on Deezer
- User sees accurate preview before confirming

---

### Step 3: Compare Playlists (Smart Skip)

```python
# Only compare if we're just updating (no creates/deletes)
if to_update and not to_create and not to_delete:
    for name, track_count, deezer_id in to_update:
        spotify_playlist = fetch_spotify_playlist(name)
        deezer_playlist = fetch_deezer_playlist(deezer_id)

        # Fast check: track count
        if len(spotify_playlist.tracks) != len(deezer_playlist.tracks):
            actually_need_update.append((name, track_count, deezer_id))
            continue

        # Accurate check: ISRC comparison
        spotify_isrcs = [t.isrc for t in spotify_playlist.tracks if t.isrc]
        deezer_isrcs = [t.isrc for t in deezer_playlist.tracks if t.isrc]

        if spotify_isrcs != deezer_isrcs:
            actually_need_update.append((name, track_count, deezer_id))
        # else: Identical - skip this playlist

    to_update = actually_need_update

# If nothing to do, exit successfully
if not to_create and not to_update and not to_delete:
    print("✓ All playlists are already in sync! Nothing to do.")
    return success_result
```

**Smart Skip Benefits:**
- Saves time when running sync repeatedly
- Avoids unnecessary API calls
- Perfect for cron jobs / scheduled syncs
- User knows immediately if sync is needed

**Comparison Logic:**
1. **Fast Check**: Compare track counts (O(1))
2. **Accurate Check**: Compare ISRCs in order (O(n))
3. **Skip if identical**: No API calls needed

---

### Step 4: Show Preview & Get Confirmation

```
🔍 Checking playlist status on Deezer...
📊 Comparing playlists to detect changes...

╭───────────────────────────────────────╮
│ 🔄 Sync Preview                       │
╰───────────────────────────────────────╯

✓ Will Create on Deezer (1 playlists):
  + Summer Vibes 2025 (45 tracks)

🔄 Will Update on Deezer (2 playlists):
  ~ Workout Mix (32 tracks)
  ~ Party Hits (67 tracks)

Summary: 3 playlists affected, ~144 tracks to sync

Proceed with sync? [y/n] (y):
```

User sees **exactly** what will happen before confirming.

---

### Step 5: Fetch from Spotify

```python
spotify_playlists = self._fetch_spotify_playlists(playlist_ids)
```

For each selected playlist ID:
1. Fetch playlist metadata (name, description, public status)
2. Fetch all tracks in playlist
3. Include ISRC codes for track matching

**Playlist Object:**
```python
@dataclass
class Playlist:
    spotify_id: str
    name: str
    description: str
    public: bool
    tracks: List[Track]
```

---

### Step 3: Match Tracks to Deezer

```python
deezer_track_ids = self._match_tracks_to_deezer(spotify_tracks)
```

For each Spotify track:
1. **Check cache**: Look for existing ISRC → Deezer ID mapping in database
2. **Search Deezer**: If not cached, search Deezer by ISRC
3. **Cache result**: Store successful match in database
4. **Skip if missing**: If no ISRC or not found, skip track

**Caching Benefits:**
- Reduces API calls on subsequent syncs
- Speeds up sync for unchanged playlists
- Tracks previously matched tracks

**Example:**
```python
# Input: Spotify tracks
[
    Track(spotify_id='123', isrc='USRC12345678', title='Song A', ...),
    Track(spotify_id='456', isrc='USRC87654321', title='Song B', ...),
    Track(spotify_id='789', isrc=None, title='Song C', ...)  # No ISRC
]

# Output: Deezer track IDs
['dz123456', 'dz789012']  # Song C skipped
```

---

### Step 7: Apply to Deezer

For each playlist needing changes:

#### Create New Playlist

```python
if not synced or not playlist_exists:
    deezer_id = self._create_deezer_playlist(spotify_playlist)
```

1. Create **private playlist** on Deezer with same name/description
2. Add matched tracks to new playlist
3. Save Deezer playlist ID to database

**Important:** Always creates **private playlists** (`status: 0`) to ensure:
- Playlist is owned by the user
- Appears reliably in user's library
- Can be fetched by ID consistently

#### Update Existing Playlist (Full Overwrite)

```python
if synced:
    self._update_deezer_playlist(synced['deezer_id'], spotify_playlist)
```

1. Fetch current Deezer playlist
2. Remove ALL existing tracks
3. Add ALL current Spotify tracks (matched to Deezer)
4. Update database tracking

**Why full overwrite?**
- Simpler logic (no diff computation)
- Ensures exact match with Spotify
- Handles reordering automatically
- No conflict resolution needed

---

### Step 5: Clean Deselected

```python
deleted = self._delete_deselected_playlists(selected_ids)
```

1. Query database for all synced playlists
2. Identify playlists not in current selection
3. Delete from Deezer via API
4. Remove from database tracking

**Example:**
```python
# Selected IDs: ['abc123', 'def456']
# Synced playlists in DB: ['abc123', 'def456', 'ghi789']
# Result: Delete 'ghi789' from Deezer
```

---

### Step 6: Update Database

```python
self.db.mark_playlist_synced(spotify_id)
self.db.add_sync_log(status='success', ...)
```

1. Update `last_synced` timestamp in `playlist_selections`
2. Update `synced_at` in `synced_playlists`
3. Add entry to `sync_log` table

---

## Result Object

```python
@dataclass
class SyncResult:
    success: bool
    playlists_created: int
    playlists_updated: int
    playlists_deleted: int
    failed_operations: List[Tuple[str, str]]  # (name, error)
    duration_seconds: float

    @property
    def total_synced(self) -> int:
        return self.playlists_created + self.playlists_updated
```

**Example:**
```python
SyncResult(
    success=True,
    playlists_created=1,
    playlists_updated=2,
    playlists_deleted=0,
    failed_operations=[],
    duration_seconds=12.3
)
```

---

## Error Handling

### Track Matching Failures

```python
for sp_track in spotify_tracks:
    if not sp_track.isrc:
        continue  # Skip tracks without ISRC

    dz_track = self.deezer.search_track(isrc=sp_track.isrc)
    if not dz_track:
        continue  # Skip tracks not found on Deezer
```

**Impact:** Some tracks may be missing from Deezer playlist if:
- Track has no ISRC code
- Track not available on Deezer
- ISRC not indexed in Deezer search

### API Failures

```python
try:
    self._update_deezer_playlist(deezer_id, spotify_playlist)
    updated += 1
except Exception as e:
    failed.append((spotify_playlist.name, str(e)))
    self.ui.print_error(f"Failed to sync '{spotify_playlist.name}': {e}")
```

**Behavior:**
- Log error for failed playlist
- Continue with next playlist
- Return partial success status
- Include failures in `failed_operations`

### Sync Interruptions

**Idempotent Operations:**
- Safe to re-run sync if interrupted
- Database only updated after successful API calls
- Full overwrite means re-sync produces same result

**Recovery:**
```bash
# If sync interrupted, simply run again
musicdiff sync
```

---

## Performance Optimizations

### Caching

```python
# Check database cache first
cached = self.db.get_track_by_isrc(isrc)
if cached and cached['deezer_id']:
    return cached['deezer_id']

# Only search Deezer if not cached
dz_track = self.deezer.search_track(isrc=isrc)
```

**Benefits:**
- Reduced API calls
- Faster subsequent syncs
- Less likely to hit rate limits

### Batch Operations

```python
# Add all tracks in one API call
track_ids = [t1, t2, t3, t4, t5]
self.deezer.add_tracks_to_playlist(playlist_id, track_ids)

# Instead of:
# for track_id in track_ids:
#     self.deezer.add_tracks_to_playlist(playlist_id, [track_id])
```

**Benefits:**
- Fewer API calls
- Faster sync
- Better rate limit management

---

## Future Enhancements

### Incremental Updates

Instead of full overwrite, compute diff:
- Only add new tracks
- Only remove deleted tracks
- Preserve manual additions on Deezer (if desired)

### Fuzzy Matching

Fallback for tracks without ISRC:
- Match by title + artist + album
- Use Levenshtein distance for typos
- Manual confirmation for uncertain matches

### Parallel Syncing

Process multiple playlists concurrently:
- Thread pool for API calls
- Faster overall sync time
- Respect rate limits

### Automatic Scheduling

Daemon mode for continuous sync:
- Run sync on interval (e.g., every 6 hours)
- Detect changes and auto-sync
- Background process with logging
