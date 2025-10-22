# MusicDiff Architecture

## Overview

MusicDiff is a bidirectional music library synchronization tool that operates like Git for music. It maintains a local state database and syncs changes between Spotify and Apple Music platforms.

## Core Concepts

### The Git Analogy

```
Local State (SQLite)  ←→  Spotify
       ↕
   Apple Music
```

- **Local State**: Acts as the "last known good state" (like Git's last commit)
- **Spotify & Apple Music**: Two "remotes" that can be modified independently
- **Sync Operation**: 3-way merge between local state and both platforms

### Data Flow

1. **Fetch**: Pull current state from both platforms
2. **Diff**: Compare platforms against local state to detect changes
3. **Conflict Detection**: Identify conflicting changes
4. **Interactive Resolution**: User approves/rejects changes
5. **Apply**: Execute changes via platform APIs
6. **Update Local State**: Record new state after successful sync

## System Architecture

### Module Breakdown

```
┌─────────────────────────────────────────────────────────────┐
│                         CLI Layer                            │
│                        (cli.py)                              │
└─────────────────────┬───────────────────────────────────────┘
                      │
         ┌────────────┴────────────┐
         │                         │
┌────────▼─────────┐      ┌───────▼────────┐
│   UI Components  │      │  Sync Engine   │
│     (ui.py)      │      │   (sync.py)    │
└──────────────────┘      └───────┬────────┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
            ┌───────▼──────┐ ┌───▼────┐ ┌─────▼──────┐
            │  Diff Engine │ │Database│ │  Matcher   │
            │  (diff.py)   │ │(.py)   │ │ (matcher.py)│
            └───────┬──────┘ └────────┘ └─────┬──────┘
                    │                          │
        ┌───────────┴───────────┬──────────────┘
        │                       │
┌───────▼────────┐     ┌───────▼────────┐
│ Spotify Client │     │Apple Music API │
│  (spotify.py)  │     │   (apple.py)   │
└────────────────┘     └────────────────┘
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | Command-line interface, argument parsing, command routing |
| `ui.py` | Terminal UI for diffs, prompts, progress bars |
| `sync.py` | Orchestrates sync process, applies changes to platforms |
| `diff.py` | 3-way diff algorithm, conflict detection |
| `database.py` | SQLite state management, schema, queries |
| `matcher.py` | Cross-platform track matching (ISRC, fuzzy matching) |
| `spotify.py` | Spotify API integration, OAuth, data fetching |
| `apple.py` | Apple Music API integration, authentication |
| `scheduler.py` | Daemon mode, scheduled syncs, background execution |

## Design Patterns

### 3-Way Merge Algorithm

For each entity (playlist, liked song, album):

1. **Compute Diffs**:
   - `spotify_changes = diff(local_state, spotify_current)`
   - `apple_changes = diff(local_state, apple_current)`

2. **Categorize Changes**:
   - **Auto-merge**: Changed on one platform only → apply to the other
   - **Conflict**: Changed on both platforms → require user input
   - **No change**: Identical on both → skip

3. **Apply Changes**:
   - Non-conflicting changes applied automatically (or with confirmation)
   - Conflicts shown in diff UI for manual resolution

### Track Matching Strategy

Tracks are matched across platforms using multiple strategies in order of reliability:

1. **ISRC** (International Standard Recording Code) - unique identifier
2. **Combined metadata** - Artist + Title + Album + Duration
3. **Fuzzy matching** - Levenshtein distance for typos/variations
4. **Manual mapping** - User can create explicit mappings for edge cases

### State Management

Local SQLite database stores:
- **Normalized track data**: All unique tracks with platform IDs
- **User library state**: Playlists, liked songs, albums
- **Sync history**: Timestamps, changes applied, conflicts resolved
- **Unresolved conflicts**: Pending user decisions

## Conflict Resolution

### Conflict Types

1. **Playlist Modification**: Same playlist modified on both platforms
   - Show side-by-side diff of track changes
   - User chooses: Spotify version, Apple version, or manual merge

2. **Track Unavailable**: Track exists on one platform but not available on other
   - Mark as visible conflict
   - Options: Skip, substitute with similar track (future), remove from both

3. **Metadata Mismatch**: Same ISRC but different metadata
   - Usually auto-resolve (metadata doesn't affect playback)
   - Log warning for user review

### Auto-Sync Mode

In daemon/scheduled mode:
- Auto-apply all non-conflicting changes
- Log conflicts to file: `~/.musicdiff/conflicts.log`
- Send notification if conflicts detected (optional)
- User can run `musicdiff resolve` to handle conflicts later

## Data Model

### Core Entities

```
Track
├── isrc (primary key for matching)
├── spotify_id
├── apple_music_id
├── title
├── artist
├── album
├── duration_ms
└── last_synced

Playlist
├── id (uuid)
├── spotify_id
├── apple_music_id
├── name
├── description
├── track_count
└── last_modified

PlaylistTrack (many-to-many)
├── playlist_id
├── track_isrc
└── position

UserLibrary
├── liked_songs (set of track ISRCs)
└── saved_albums (set of album IDs)

SyncLog
├── timestamp
├── changes_applied
├── conflicts_count
└── status
```

## Configuration

User configuration stored in `~/.musicdiff/config.yaml`:

```yaml
spotify:
  client_id: xxx
  client_secret: xxx

apple_music:
  developer_token: xxx
  user_token: xxx

sync:
  auto_accept_non_conflicts: true
  notify_on_conflicts: true
  schedule_interval: 86400  # seconds

matching:
  fuzzy_threshold: 0.85
  prefer_platform: null  # or 'spotify' / 'apple'
```

## Security

- API credentials stored in config file with restrictive permissions (0600)
- OAuth tokens refreshed automatically
- No plaintext password storage
- Database contains only music library data, no sensitive information

## Future Enhancements

- Web UI for visualization
- Conflict resolution suggestions using ML
- Support for other platforms (YouTube Music, Tidal, etc.)
- Collaborative playlists sync
- Export to Git-like format for versioning
- Rollback to previous sync state
