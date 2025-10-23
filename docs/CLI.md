# CLI Module Documentation

## Overview

The CLI module (`cli.py`) provides the command-line interface for MusicDiff using the Click framework. It implements a simple, focused interface for one-way Spotify to Deezer playlist synchronization.

## Commands

### `musicdiff setup`

Interactive setup wizard for configuring Spotify and Deezer credentials.

**Usage:**
```bash
musicdiff setup
```

**What it does:**
1. Guides you through creating Spotify API credentials
2. Prompts for Deezer ARL token
3. Tests authentication with both platforms
4. Saves credentials to `.musicdiff/.env` file
5. Creates initial database

**Example Output:**
```
🎵 MusicDiff Setup Wizard

Let's configure your Spotify credentials...
1. Go to: https://developer.spotify.com/dashboard
2. Create a new app
3. Copy your Client ID and Client Secret

Spotify Client ID: 3d9a0836d01242fb94d579c26456f4a5
Spotify Client Secret: ****
Redirect URI: http://127.0.0.1:8888/callback

Testing Spotify authentication...
✓ Spotify authenticated successfully!

Now let's configure Deezer...
1. Login to deezer.com in your browser
2. Open Developer Tools → Application → Cookies
3. Copy the value of the 'arl' cookie

Deezer ARL token: ****

Testing Deezer authentication...
✓ Deezer authenticated successfully!
  User ID: 2191762744

✓ Setup complete! Credentials saved to .musicdiff/.env
```

---

### `musicdiff init`

Initialize local database for tracking playlists and sync state.

**Usage:**
```bash
musicdiff init
```

**What it does:**
1. Creates `~/.musicdiff/` directory
2. Initializes SQLite database schema
3. Sets up tables for playlist tracking

**Example Output:**
```
🎵 Initializing MusicDiff...
✓ Created local database at ~/.musicdiff/musicdiff.db
✓ Initialization complete!
```

---

### `musicdiff select`

Interactive playlist selection interface - choose which Spotify playlists to sync to Deezer.

**Usage:**
```bash
musicdiff select
```

**What it does:**
1. Fetches all your Spotify playlists
2. Shows checkbox interface for selection
3. Pre-selects currently selected playlists
4. Saves your selections to the database

**Interface:**
- Use **↑↓** arrow keys to navigate
- Press **SPACE** to select/deselect a playlist
- Press **ENTER** to confirm and save selections
- Press **ESC** to cancel

**Example Output:**
```
Select Playlists to Sync to Deezer

Use ↑↓ to navigate, SPACE to select/deselect, ENTER to confirm

┌─ Select Playlists ─────────────────────────────────────┐
│ Choose which Spotify playlists to sync to Deezer:     │
│                                                         │
│ ☑ Summer Vibes 2025 (45 tracks)                       │
│ ☑ Workout Mix (32 tracks)                             │
│ ☐ Chill Evening (28 tracks)                           │
│ ☑ Party Hits (67 tracks)                              │
│ ☐ Study Focus (41 tracks)                             │
│                                                         │
│         [ OK ]              [ Cancel ]                  │
└─────────────────────────────────────────────────────────┘

✓ Updated playlist selections (3 playlists selected)
```

**Fallback Mode:**

If the checkbox dialog fails, falls back to text-based selection:
```
Using simplified selection mode

1. ✓ Summer Vibes 2025 (45 tracks)
2. ✓ Workout Mix (32 tracks)
3. ✗ Chill Evening (28 tracks)
4. ✓ Party Hits (67 tracks)
5. ✗ Study Focus (41 tracks)

Enter playlist numbers to toggle (comma-separated), or 'done' to finish:
Example: 1,3,5 to toggle playlists 1, 3, and 5

Toggle playlists [done]: 3,5
```

---

### `musicdiff list`

Show all Spotify playlists with their sync status.

**Usage:**
```bash
musicdiff list
```

**What it does:**
1. Fetches all Spotify playlists
2. Shows selection status
3. Shows last sync time
4. Shows which playlists are synced to Deezer

**Example Output:**
```
Your Spotify Playlists

┌──────────────┬─────────────────────┬────────┬──────────────────┬────────────┐
│ Status       │ Playlist Name       │ Tracks │ Last Synced      │ Deezer     │
├──────────────┼─────────────────────┼────────┼──────────────────┼────────────┤
│ ✓ Selected   │ Summer Vibes 2025   │     45 │ 2025-10-22 13:30 │ ✓ Synced   │
│ ✓ Selected   │ Workout Mix         │     32 │ 2025-10-22 13:30 │ ✓ Synced   │
│ ○ Not sel... │ Chill Evening       │     28 │ Never            │ —          │
│ ✓ Selected   │ Party Hits          │     67 │ 2025-10-22 13:30 │ ✓ Synced   │
│ ○ Not sel... │ Study Focus         │     41 │ Never            │ —          │
└──────────────┴─────────────────────┴────────┴──────────────────┴────────────┘

Summary: 3/5 selected, 3 synced to Deezer
```

---

### `musicdiff sync`

Synchronize selected Spotify playlists to Deezer.

**Usage:**
```bash
musicdiff sync [OPTIONS]
```

**Options:**
- `--dry-run`: Preview what would be synced without making changes

**What it does:**
1. Fetches selected playlists from Spotify
2. For each playlist:
   - If it exists on Deezer: Updates it (full overwrite)
   - If it doesn't exist: Creates it
3. Deletes deselected playlists from Deezer
4. Updates local database
5. Logs sync operation

**Example Output:**
```
ℹ Syncing 3 selected playlists to Deezer...

Processing...  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  100% 3/3

✓ Sync complete: 3 playlists synced (1 created, 2 updated, 0 deleted)

Sync Summary
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Playlists Created     1
Playlists Updated     2
Playlists Deleted     0
Total Synced          3
Duration              12.3s
```

**Dry Run Example:**
```bash
$ musicdiff sync --dry-run

[DRY RUN] The following changes would be made:

ℹ   CREATE: Summer Vibes 2025 (45 tracks)
ℹ   UPDATE: Workout Mix (32 tracks)
ℹ   UPDATE: Party Hits (67 tracks)

No changes applied (dry run mode)
```

**Error Handling:**
```
ℹ Syncing 3 selected playlists to Deezer...

Processing...  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  100% 3/3

✗ Failed to sync 'Workout Mix': API rate limit exceeded

⚠ Sync partial: 2 synced, 1 failed
  Workout Mix: API rate limit exceeded
```

---

### `musicdiff status`

Show current sync status and database statistics.

**Usage:**
```bash
musicdiff status
```

**What it does:**
1. Shows database path and size
2. Shows number of playlists selected
3. Shows number of synced playlists
4. Shows last sync time
5. Shows track cache statistics

**Example Output:**
```
MusicDiff Status

Database:  ~/.musicdiff/musicdiff.db
Size:      2.3 MB

Playlists:
  Selected for sync:  3
  Synced to Deezer:   3
  Last sync:          2025-10-22 13:30:45

Track Cache:
  Total tracks:       145
  With ISRC:          142
  Spotify IDs:        145
  Deezer IDs:         138
```

---

### `musicdiff log`

Show sync history.

**Usage:**
```bash
musicdiff log [OPTIONS]
```

**Options:**
- `-n, --limit NUM`: Show last N syncs (default: 10)

**Example Output:**
```
Sync History (last 10 syncs)

┌────────────────────┬─────────┬─────────┬─────────┬─────────┬──────────┐
│ Timestamp          │ Status  │ Created │ Updated │ Deleted │ Duration │
├────────────────────┼─────────┼─────────┼─────────┼─────────┼──────────┤
│ 2025-10-22 13:30   │ Success │       1 │       2 │       0 │    12.3s │
│ 2025-10-21 09:15   │ Success │       0 │       3 │       1 │    8.7s  │
│ 2025-10-20 18:45   │ Partial │       0 │       2 │       0 │    6.2s  │
│ 2025-10-19 22:10   │ Success │       2 │       0 │       0 │    15.1s │
└────────────────────┴─────────┴─────────┴─────────┴─────────┴──────────┘
```

---

## Global Options

Available for all commands:

- `--help`: Show command help
- `--version`: Show MusicDiff version

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Authentication error
- `3`: API error (Spotify/Deezer)
- `4`: Database error

## Environment Variables

The following environment variables must be set in `.musicdiff/.env`:

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8888/callback"
export DEEZER_ARL="your_arl_token"
```

Load them before running commands:
```bash
source ~/.musicdiff/.env
# or
source /path/to/MusicDiff/.musicdiff/.env
```

## Typical Workflow

### First Time Setup

```bash
# 1. Run setup wizard
musicdiff setup

# 2. Load credentials
source .musicdiff/.env

# 3. Initialize database
musicdiff init

# 4. Select playlists to sync
musicdiff select

# 5. Perform initial sync
musicdiff sync
```

### Regular Usage

```bash
# Load credentials
source .musicdiff/.env

# Check current status
musicdiff status

# View playlists
musicdiff list

# Sync changes
musicdiff sync

# View history
musicdiff log
```

### Modifying Selections

```bash
# Change which playlists to sync
musicdiff select

# Preview changes
musicdiff sync --dry-run

# Apply changes
musicdiff sync
```

## Implementation Notes

### Framework Choice: Click

We use Click because:
- Clean, declarative syntax
- Automatic help generation
- Built-in option/argument validation
- Easy command grouping
- Wide adoption in Python CLI tools

### Command Structure

```python
@click.group()
@click.version_option(version=__version__)
def cli():
    """MusicDiff - Simple Spotify to Deezer playlist sync."""
    pass

@cli.command()
def select():
    """Select playlists to sync."""
    # Implementation...

@cli.command()
@click.option('--dry-run', is_flag=True)
def sync(dry_run):
    """Synchronize playlists to Deezer."""
    # Implementation...
```

### Progress Feedback

All long-running operations use `rich.progress`:
- Progress bars for sync operations
- Spinners for API calls
- Status indicators (✓, ✗, ⚠, ℹ)
- Color-coded output

### Error Handling

- **API errors**: Retry with exponential backoff (max 3 attempts)
- **Authentication errors**: Show helpful message with setup instructions
- **Network errors**: Suggest checking connection
- **Database errors**: Log detailed error with file path

## Future Commands

Planned commands for future versions:

- `musicdiff daemon`: Run automatic syncs on schedule
- `musicdiff config`: View/edit configuration
- `musicdiff export`: Export playlist selections to file
- `musicdiff import`: Import playlist selections from file
