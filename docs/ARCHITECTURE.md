# MusicDiff Architecture

## Overview

MusicDiff is a simple one-way playlist synchronization tool that transfers Spotify playlists to Deezer. It maintains a local state database to track which playlists are selected for sync and what's currently on Deezer.

## Core Concepts

### Simple One-Way Sync

```
Spotify (Source) → Local State (SQLite) → Deezer (Target)
```

- **Spotify**: Source of truth for playlist content
- **Local State**: Tracks playlist selections and sync status
- **Deezer**: Target platform that mirrors selected Spotify playlists

### Data Flow

1. **Select**: User chooses which Spotify playlists to sync
2. **Fetch**: Pull selected playlists from Spotify
3. **Match**: Find corresponding Deezer tracks using ISRC codes
4. **Apply**: Create/update playlists on Deezer to mirror Spotify
5. **Clean**: Delete deselected playlists from Deezer
6. **Update**: Record sync status in local database

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
            │   Database   │ │Matcher │ │  Spotify   │
            │ (database.py)│ │(.py)   │ │(spotify.py)│
            └──────────────┘ └────┬───┘ └────────────┘
                                  │
                          ┌───────▼────────┐
                          │ Deezer Client  │
                          │  (deezer.py)   │
                          └────────────────┘
```

### Module Responsibilities

| Module | Purpose |
|--------|---------|
| `cli.py` | Command-line interface, argument parsing, command routing |
| `ui.py` | Terminal UI for playlist selection, status display, progress bars |
| `sync.py` | Orchestrates sync process, applies changes to Deezer |
| `database.py` | SQLite state management for playlist selections and sync status |
| `matcher.py` | Cross-platform track matching using ISRC codes |
| `spotify.py` | Spotify API integration, OAuth, playlist fetching |
| `deezer.py` | Deezer API integration, playlist creation/updates |
| `scheduler.py` | Daemon mode for automatic syncs (future enhancement) |

## Sync Logic

### One-Way Sync Process

For each selected Spotify playlist:

1. **Fetch from Spotify**: Get complete playlist data including all tracks
2. **Check Deezer**: Query local database for existing Deezer playlist ID
3. **Match Tracks**: Convert Spotify tracks to Deezer tracks using ISRC
4. **Apply Changes**:
   - **If new**: Create playlist on Deezer with matched tracks
   - **If exists**: Full overwrite - remove all tracks, add current Spotify tracks
5. **Update Database**: Record sync status and Deezer playlist ID

### Deselection Cleanup

For playlists that were previously synced but are now deselected:

1. **Identify**: Query database for synced playlists not in current selection
2. **Delete**: Remove playlist from Deezer via API
3. **Clean Database**: Remove from synced_playlists table

### Track Matching Strategy

Tracks are matched across platforms using ISRC (International Standard Recording Code):

1. **ISRC Lookup**: Search Deezer for track with matching ISRC
2. **Cache Match**: Store ISRC → Deezer ID mapping in database
3. **Skip Missing**: Tracks without ISRC or not found on Deezer are skipped

## State Management

### Database Schema

Local SQLite database stores:

**playlist_selections**
- Spotify playlists the user has chosen to sync
- Fields: spotify_id, name, track_count, selected, last_synced

**synced_playlists**
- Mapping of Spotify playlists to their Deezer counterparts
- Fields: spotify_id, deezer_id, name, track_count, synced_at

**tracks**
- Track matching cache (ISRC → platform IDs)
- Fields: isrc, spotify_id, deezer_id, title, artist, album, duration_ms

**sync_log**
- History of sync operations
- Fields: timestamp, status, playlists_synced, playlists_created, playlists_updated, playlists_deleted, duration_seconds

See [DATABASE.md](DATABASE.md) for detailed schema documentation.

## User Interface

### Playlist Selection

Interactive checkbox interface using `prompt_toolkit`:
- Display all Spotify playlists
- Arrow keys to navigate
- SPACE to toggle selection
- ENTER to confirm
- Persist selections in database

### Sync Progress

Rich terminal UI showing:
- Progress bar for sync operations
- Real-time status updates
- Success/error messages
- Summary statistics

## Configuration

User configuration stored in `.musicdiff/.env`:

```bash
# Spotify OAuth credentials
export SPOTIFY_CLIENT_ID="xxx"
export SPOTIFY_CLIENT_SECRET="xxx"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8888/callback"

# Deezer authentication
export DEEZER_ARL="xxx"  # ARL token from browser cookies
```

## Security

- API credentials stored in `.env` file (not committed to git)
- Spotify uses OAuth 2.0 with authorization code flow
- Deezer uses ARL token authentication (private API)
- Database contains only music library data, no sensitive credentials
- File permissions should be restrictive (600 for .env)

## Error Handling

### Track Matching Failures
- Skip tracks without ISRC codes
- Log tracks that couldn't be found on Deezer
- Continue sync for remaining tracks

### API Failures
- Retry with exponential backoff for rate limits
- Log failed operations
- Continue with next playlist on single playlist failure
- Return partial success status

### Sync Interruptions
- Database updates only after successful operations
- Safe to re-run sync after interruption
- Idempotent operations (running twice has same effect as once)

## Performance Considerations

### Rate Limiting
- Respect Spotify API rate limits (429 responses)
- Deezer private API has undocumented limits
- Exponential backoff retry strategy

### Caching
- Track matches cached in database
- Reduces API calls on subsequent syncs
- Only refetch when playlists change

### Batch Operations
- Add/remove tracks in batches where possible
- Progress tracking for long operations
- User feedback during sync

## Future Enhancements

- **Daemon Mode**: Automatic syncs on schedule
- **Liked Songs**: Sync Spotify liked songs to Deezer favorites
- **Albums**: Sync saved albums
- **Bidirectional**: Option to sync Deezer changes back to Spotify
- **Web UI**: Browser-based interface for visualization
- **Conflict Detection**: Handle cases where Deezer playlist was manually modified
- **Advanced Matching**: Fuzzy matching fallback for tracks without ISRC
- **Export/Import**: Backup and restore playlist selections
