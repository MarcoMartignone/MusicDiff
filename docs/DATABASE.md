# Database Module Documentation

## Overview

The Database module (`database.py`) manages local state storage using SQLite. It tracks playlist selections, sync status, track matching cache, and sync history for one-way Spotify to Deezer synchronization.

## Technology

- **SQLite3**: Embedded relational database
- **Location**: `~/.musicdiff/musicdiff.db` (default) or custom path
- **Schema Version**: 2 (stored in metadata table)
- **No migrations needed**: Simple schema, clean install

## Schema

### Entity Relationship Diagram

```
┌──────────────────────┐
│   tracks             │
│──────────────────────│
│ isrc (PK)            │
│ spotify_id (UNIQUE)  │
│ deezer_id (UNIQUE)   │
│ title                │
│ artist               │
│ album                │
│ duration_ms          │
│ created_at           │
│ updated_at           │
└──────────────────────┘

┌────────────────────────────┐        ┌──────────────────────────┐
│ playlist_selections        │        │ synced_playlists         │
│────────────────────────────│        │──────────────────────────│
│ spotify_id (PK)            │───────┼│ spotify_id (PK, FK)      │
│ name                       │        │ deezer_id                │
│ track_count                │        │ name                     │
│ selected (BOOLEAN)         │        │ track_count              │
│ last_synced (TIMESTAMP)    │        │ synced_at (TIMESTAMP)    │
│ created_at                 │        └──────────────────────────┘
│ updated_at                 │
└────────────────────────────┘

┌──────────────────────┐        ┌──────────────────────┐
│ sync_log             │        │ metadata             │
│──────────────────────│        │──────────────────────│
│ id (PK)              │        │ key (PK)             │
│ timestamp            │        │ value                │
│ status               │        │ updated_at           │
│ playlists_synced     │        └──────────────────────┘
│ playlists_created    │
│ playlists_updated    │
│ playlists_deleted    │
│ duration_seconds     │
│ details (JSON)       │
│ auto_sync (BOOLEAN)  │
└──────────────────────┘
```

### Table Definitions

#### `tracks`

Track matching cache - stores ISRC to platform ID mappings.

```sql
CREATE TABLE tracks (
    isrc TEXT PRIMARY KEY,
    spotify_id TEXT UNIQUE,
    deezer_id TEXT UNIQUE,
    title TEXT NOT NULL,
    artist TEXT NOT NULL,
    album TEXT NOT NULL,
    duration_ms INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_spotify_id ON tracks(spotify_id);
CREATE INDEX idx_deezer_id ON tracks(deezer_id);
```

**Purpose:**
- Cache track matches to avoid repeated API calls
- Speed up subsequent syncs
- Track ISRC → Deezer ID mappings

**Example Row:**
```python
{
    'isrc': 'USRC12345678',
    'spotify_id': '4iV5W9uYEdYUVa79Axb7Rh',
    'deezer_id': '123456789',
    'title': 'Blinding Lights',
    'artist': 'The Weeknd',
    'album': 'After Hours',
    'duration_ms': 200040,
    'created_at': '2025-10-22 10:30:00',
    'updated_at': '2025-10-22 10:30:00'
}
```

---

#### `playlist_selections`

User's playlist selections - which Spotify playlists to sync to Deezer.

```sql
CREATE TABLE playlist_selections (
    spotify_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    track_count INTEGER DEFAULT 0,
    selected BOOLEAN DEFAULT 1,
    last_synced TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Purpose:**
- Store user's playlist selection choices
- Track when playlists were last synced
- Persist selections across sessions

**Example Rows:**
```python
[
    {
        'spotify_id': '37i9dQZF1DXcBWIGoYBM5M',
        'name': 'Summer Vibes 2025',
        'track_count': 45,
        'selected': True,
        'last_synced': '2025-10-22 13:30:45',
        'created_at': '2025-10-20 09:15:00',
        'updated_at': '2025-10-22 13:30:45'
    },
    {
        'spotify_id': '5ABHKGoOzxkaa28ttQV9sE',
        'name': 'Chill Evening',
        'track_count': 28,
        'selected': False,
        'last_synced': None,
        'created_at': '2025-10-20 09:15:00',
        'updated_at': '2025-10-21 14:20:00'
    }
]
```

---

#### `synced_playlists`

Mapping of Spotify playlists to their Deezer counterparts.

```sql
CREATE TABLE synced_playlists (
    spotify_id TEXT PRIMARY KEY,
    deezer_id TEXT NOT NULL,
    name TEXT NOT NULL,
    track_count INTEGER DEFAULT 0,
    synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (spotify_id) REFERENCES playlist_selections(spotify_id) ON DELETE CASCADE
);

CREATE INDEX idx_synced_deezer ON synced_playlists(deezer_id);
```

**Purpose:**
- Track which Spotify playlists have been synced to Deezer
- Store Deezer playlist IDs for updates/deletions
- Clean up when playlists are deselected (CASCADE)

**Example Row:**
```python
{
    'spotify_id': '37i9dQZF1DXcBWIGoYBM5M',
    'deezer_id': '987654321',
    'name': 'Summer Vibes 2025',
    'track_count': 45,
    'synced_at': '2025-10-22 13:30:45'
}
```

---

#### `sync_log`

History of sync operations.

```sql
CREATE TABLE sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL,
    playlists_synced INTEGER DEFAULT 0,
    playlists_created INTEGER DEFAULT 0,
    playlists_updated INTEGER DEFAULT 0,
    playlists_deleted INTEGER DEFAULT 0,
    duration_seconds REAL,
    details TEXT,
    auto_sync BOOLEAN DEFAULT 0
);

CREATE INDEX idx_sync_timestamp ON sync_log(timestamp);
```

**Purpose:**
- Track sync history
- Monitor sync performance
- Debug sync issues
- Future: Analytics and trends

**Status Values:**
- `'success'`: All operations succeeded
- `'partial'`: Some operations failed
- `'failed'`: Sync failed completely

**Example Row:**
```python
{
    'id': 1,
    'timestamp': '2025-10-22 13:30:45',
    'status': 'success',
    'playlists_synced': 3,
    'playlists_created': 1,
    'playlists_updated': 2,
    'playlists_deleted': 0,
    'duration_seconds': 12.3,
    'details': '{"failed": []}',
    'auto_sync': False
}
```

---

#### `metadata`

System metadata (schema version, etc.).

```sql
CREATE TABLE metadata (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Initialize schema version
INSERT OR IGNORE INTO metadata (key, value)
VALUES ('schema_version', '2');
```

**Purpose:**
- Store schema version for future migrations
- Store system-level configuration
- Extensible for future needs

**Example Rows:**
```python
[
    {'key': 'schema_version', 'value': '2', 'updated_at': '2025-10-20 08:00:00'},
    {'key': 'last_cleanup', 'value': '2025-10-22 00:00:00', 'updated_at': '2025-10-22 00:00:00'}
]
```

---

## Class: `Database`

```python
class Database:
    def __init__(self, db_path: str = None)
    def init_schema(self) -> None

    # Metadata operations
    def get_metadata(self, key: str) -> Optional[str]
    def set_metadata(self, key: str, value: str) -> None

    # Track operations
    def upsert_track(self, track: Dict) -> None
    def get_track_by_isrc(self, isrc: str) -> Optional[Dict]
    def get_track_by_spotify_id(self, spotify_id: str) -> Optional[Dict]
    def get_track_by_deezer_id(self, deezer_id: str) -> Optional[Dict]

    # Playlist selection operations
    def upsert_playlist_selection(self, spotify_id: str, name: str, track_count: int, selected: bool) -> None
    def get_all_playlist_selections(self) -> List[Dict]
    def get_selected_playlists(self) -> List[Dict]
    def update_playlist_selection(self, spotify_id: str, selected: bool) -> None
    def mark_playlist_synced(self, spotify_id: str) -> None

    # Synced playlists operations
    def upsert_synced_playlist(self, spotify_id: str, deezer_id: str, name: str, track_count: int) -> None
    def get_synced_playlist(self, spotify_id: str) -> Optional[Dict]
    def get_all_synced_playlists(self) -> List[Dict]
    def delete_synced_playlist(self, spotify_id: str) -> None

    # Sync log operations
    def add_sync_log(self, status: str, playlists_synced: int, ...) -> None
    def get_sync_history(self, limit: int = 10) -> List[Dict]
```

## Usage Examples

### Initialize Database

```python
from musicdiff.database import Database

db = Database()  # Uses default path: ~/.musicdiff/musicdiff.db
db.init_schema()
```

### Playlist Selection Workflow

```python
# Store user's selections
db.upsert_playlist_selection(
    spotify_id='abc123',
    name='Summer Vibes',
    track_count=45,
    selected=True
)

# Get all selected playlists
selected = db.get_selected_playlists()
# Returns: [{'spotify_id': 'abc123', 'name': 'Summer Vibes', ...}]

# Update selection
db.update_playlist_selection(spotify_id='abc123', selected=False)
```

### Track Caching

```python
# Cache a matched track
db.upsert_track({
    'isrc': 'USRC12345678',
    'spotify_id': '4iV5W9uYEdYUVa79Axb7Rh',
    'deezer_id': '123456789',
    'title': 'Blinding Lights',
    'artist': 'The Weeknd',
    'album': 'After Hours',
    'duration_ms': 200040
})

# Lookup by ISRC (for future syncs)
track = db.get_track_by_isrc('USRC12345678')
if track and track['deezer_id']:
    # Use cached Deezer ID instead of searching API
    deezer_id = track['deezer_id']
```

### Sync Tracking

```python
# Track a synced playlist
db.upsert_synced_playlist(
    spotify_id='abc123',
    deezer_id='987654321',
    name='Summer Vibes',
    track_count=45
)

# Check if playlist already synced
synced = db.get_synced_playlist('abc123')
if synced:
    deezer_id = synced['deezer_id']
    # Update existing playlist
else:
    # Create new playlist

# Mark as synced (update timestamp)
db.mark_playlist_synced('abc123')
```

### Sync History

```python
# Log a sync operation
db.add_sync_log(
    status='success',
    playlists_synced=3,
    playlists_created=1,
    playlists_updated=2,
    playlists_deleted=0,
    details={'failed': []},
    duration=12.3,
    auto_sync=False
)

# View history
history = db.get_sync_history(limit=10)
for entry in history:
    print(f"{entry['timestamp']}: {entry['status']} - {entry['playlists_synced']} synced")
```

## Design Decisions

### Why SQLite?

- **Embedded**: No separate database server needed
- **Portable**: Single file, easy to backup/restore
- **Fast**: Sufficient for local state storage
- **ACID**: Transactions ensure data consistency
- **Python stdlib**: No extra dependencies

### Connection Management

- **Per-operation connections**: Each method opens/closes its own connection
- **No persistent connection**: Simpler, avoids lock issues
- **Thread-safe**: Each thread gets its own connection
- **Auto-close**: Ensures resources are freed

### Cascade Deletes

```sql
FOREIGN KEY (spotify_id) REFERENCES playlist_selections(spotify_id) ON DELETE CASCADE
```

When a playlist selection is deleted, its `synced_playlists` entry is automatically removed. This keeps the database clean.

### UPSERT Pattern

```sql
INSERT INTO tracks (...)
VALUES (...)
ON CONFLICT(isrc) DO UPDATE SET
    deezer_id = excluded.deezer_id,
    updated_at = CURRENT_TIMESTAMP
```

Simplifies code - no need to check if record exists before insert/update.

## Performance

### Indexes

Strategic indexes for fast lookups:
- `tracks.spotify_id` - Looking up cached tracks during sync
- `tracks.deezer_id` - Reverse lookups
- `synced_playlists.deezer_id` - Finding playlist by Deezer ID
- `sync_log.timestamp` - Recent sync history queries

### Typical Database Size

- **Empty**: ~20 KB
- **100 playlists, 5000 tracks**: ~2-3 MB
- **1000 playlists, 50000 tracks**: ~20-30 MB

SQLite handles these sizes easily with sub-millisecond query times.

## Maintenance

### Backup

```bash
# Backup database
cp ~/.musicdiff/musicdiff.db ~/.musicdiff/musicdiff.db.backup

# Restore from backup
cp ~/.musicdiff/musicdiff.db.backup ~/.musicdiff/musicdiff.db
```

### Reset

```bash
# Delete database (fresh start)
rm ~/.musicdiff/musicdiff.db

# Re-initialize
musicdiff init
```

### Inspect Database

```bash
# Open with sqlite3 CLI
sqlite3 ~/.musicdiff/musicdiff.db

# Example queries
SELECT COUNT(*) FROM tracks;
SELECT COUNT(*) FROM playlist_selections WHERE selected = 1;
SELECT * FROM sync_log ORDER BY timestamp DESC LIMIT 5;
```

## Future Enhancements

- **Migrations**: Schema versioning for backward compatibility
- **Vacuum**: Periodic database compaction
- **Analytics**: Track match success rates, sync performance trends
- **Export/Import**: Backup playlist selections to JSON
- **Pruning**: Auto-delete old sync logs after N days
