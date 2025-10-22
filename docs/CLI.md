# CLI Module Documentation

## Overview

The CLI module (`cli.py`) provides the command-line interface for MusicDiff using the Click framework. It implements a git-like command structure for managing music library synchronization.

## Commands

### `musicdiff init`

Initialize MusicDiff and authenticate with music platforms.

**Usage:**
```bash
musicdiff init
```

**What it does:**
1. Creates `~/.musicdiff/` directory
2. Initializes SQLite database
3. Prompts for Spotify OAuth authentication (opens browser)
4. Prompts for Apple Music authentication
5. Creates default `config.yaml` file
6. Performs initial fetch from both platforms

**Example Output:**
```
🎵 Initializing MusicDiff...
✓ Created local database at ~/.musicdiff/musicdiff.db
🔐 Authenticating with Spotify...
  Opening browser for OAuth...
✓ Spotify authenticated
🔐 Authenticating with Apple Music...
✓ Apple Music authenticated
📥 Fetching initial library state...
  Playlists: 42
  Liked Songs: 1,234
  Albums: 156
✓ Initialization complete!
```

---

### `musicdiff status`

Show current sync status and pending changes.

**Usage:**
```bash
musicdiff status
```

**What it does:**
1. Checks last sync timestamp
2. Shows number of detected changes on each platform
3. Lists unresolved conflicts
4. Shows sync daemon status (if running)

**Example Output:**
```
Last sync: 2 hours ago (2025-10-22 11:30:15)

Changes detected:
  Spotify:
    + 3 new playlists
    ~ 2 playlists modified
    - 1 playlist deleted
    + 45 liked songs added

  Apple Music:
    + 1 new playlist
    ~ 1 playlist modified
    + 12 liked songs added

Unresolved conflicts: 1
  - Playlist "Workout Mix" modified on both platforms

Run 'musicdiff sync' to synchronize changes.
```

---

### `musicdiff fetch`

Fetch latest library state from both platforms without syncing.

**Usage:**
```bash
musicdiff fetch
```

**What it does:**
1. Pulls current state from Spotify API
2. Pulls current state from Apple Music API
3. Updates internal cache (doesn't modify local state)
4. Shows summary of detected changes

**Options:**
- `--spotify-only`: Fetch from Spotify only
- `--apple-only`: Fetch from Apple Music only

**Example Output:**
```
📥 Fetching from Spotify...
✓ Fetched 42 playlists, 1,279 liked songs, 156 albums

📥 Fetching from Apple Music...
✓ Fetched 41 playlists, 1,256 liked songs, 150 albums

Run 'musicdiff status' to see changes.
```

---

### `musicdiff diff`

Show detailed diff between platforms without syncing.

**Usage:**
```bash
musicdiff diff [ENTITY_TYPE]
```

**Arguments:**
- `ENTITY_TYPE`: Optional filter - `playlists`, `liked`, `albums`

**What it does:**
1. Computes 3-way diff
2. Displays side-by-side comparison
3. Highlights conflicts in red
4. Shows auto-mergeable changes in green

**Example Output:**
```
═══ Playlists ═══

✓ Auto-merge (5 changes):
  + [Spotify] "Summer Vibes 2025" → will copy to Apple Music
  + [Apple] "Running Beats" → will copy to Spotify
  ~ [Spotify] "Chill Mix" (3 tracks added) → will sync to Apple
  ~ [Apple] "Party Hits" (2 tracks removed) → will sync to Spotify
  - [Spotify] "Old Playlist" (deleted) → will delete from Apple

⚠ Conflicts (1):
  ~ "Workout Mix" - modified on both platforms
    Spotify: +5 tracks, -2 tracks
    Apple:   +3 tracks, -1 track

═══ Liked Songs ═══

✓ Auto-merge (57 changes):
  + [Spotify] 45 new liked songs → will copy to Apple Music
  + [Apple] 12 new liked songs → will copy to Spotify
```

---

### `musicdiff sync`

Perform interactive synchronization with conflict resolution.

**Usage:**
```bash
musicdiff sync [OPTIONS]
```

**Options:**
- `--auto`: Automatically apply all non-conflicting changes without confirmation
- `--dry-run`: Show what would be synced without applying changes
- `--conflicts-only`: Only show and resolve conflicts

**What it does:**
1. Fetches latest from both platforms
2. Computes diffs
3. For non-conflicting changes:
   - In interactive mode: Shows each change, prompts for confirmation
   - In auto mode: Applies automatically
4. For conflicts: Opens interactive diff UI
5. Applies approved changes via APIs
6. Updates local state
7. Logs sync to history

**Interactive Mode Example:**
```
📊 Sync Summary:
  Auto-mergeable: 62 changes
  Conflicts: 1

Apply non-conflicting changes? [Y/n]: y

Syncing playlists...
  ✓ Copied "Summer Vibes 2025" to Apple Music
  ✓ Copied "Running Beats" to Spotify
  ✓ Updated "Chill Mix" on Apple Music (+3 tracks)
  [Progress: 5/62]

Resolving conflicts...

━━━ Conflict: Playlist "Workout Mix" ━━━

Spotify version:
  + "Eye of the Tiger" - Survivor
  + "Lose Yourself" - Eminem
  + "Till I Collapse" - Eminem
  - "Jump Around" - House of Pain

Apple Music version:
  + "Stronger" - Kanye West
  + "Remember the Name" - Fort Minor
  - "Thunderstruck" - AC/DC

Choose action:
  [s] Keep Spotify version
  [a] Keep Apple Music version
  [m] Manual merge (interactive)
  [k] Skip for now
> m

[Opens interactive merge UI...]

✓ Sync complete!
  Applied: 62 changes
  Conflicts resolved: 1
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
- `--verbose`: Show detailed change list for each sync

**Example Output:**
```
commit 8a3f2b1c
Date:   2025-10-22 13:30:45
Status: Success
Changes: 62 applied, 1 conflict resolved

commit 7d2e1a9b
Date:   2025-10-21 01:00:12 (scheduled)
Status: Success
Changes: 12 applied, 0 conflicts

commit 6c1d0a8a
Date:   2025-10-20 01:00:08 (scheduled)
Status: Partial (3 conflicts pending)
Changes: 8 applied, 3 conflicts skipped
```

---

### `musicdiff resolve`

Resume conflict resolution for pending conflicts.

**Usage:**
```bash
musicdiff resolve
```

**What it does:**
1. Loads unresolved conflicts from database
2. Opens interactive diff UI for each conflict
3. Applies resolutions
4. Updates local state

**Example:**
```
Found 3 unresolved conflicts from previous syncs.

━━━ Conflict 1/3: Playlist "Workout Mix" ━━━
[Shows diff UI...]
```

---

### `musicdiff daemon`

Run MusicDiff in daemon mode for scheduled syncs.

**Usage:**
```bash
musicdiff daemon [OPTIONS]
```

**Options:**
- `--interval SECONDS`: Sync interval (default: from config, or 86400)
- `--foreground`: Run in foreground with logs to stdout
- `--stop`: Stop running daemon

**What it does:**
1. Runs in background (unless `--foreground`)
2. Performs automatic sync at specified intervals
3. Uses auto-sync mode (applies non-conflicting changes)
4. Logs conflicts to `~/.musicdiff/conflicts.log`
5. Creates PID file at `~/.musicdiff/daemon.pid`

**Example:**
```bash
# Start daemon (syncs every 24 hours)
musicdiff daemon

# Start daemon with 6-hour interval
musicdiff daemon --interval 21600

# Run in foreground (for debugging)
musicdiff daemon --foreground

# Stop daemon
musicdiff daemon --stop
```

---

### `musicdiff config`

View or edit configuration.

**Usage:**
```bash
musicdiff config [KEY] [VALUE]
```

**Examples:**
```bash
# View all config
musicdiff config

# Get specific value
musicdiff config sync.auto_accept_non_conflicts

# Set value
musicdiff config sync.schedule_interval 43200
```

---

## Global Options

Available for all commands:

- `--help`: Show command help
- `--version`: Show MusicDiff version
- `--verbose, -v`: Verbose output
- `--quiet, -q`: Suppress non-error output

## Exit Codes

- `0`: Success
- `1`: General error
- `2`: Authentication error
- `3`: API error (Spotify/Apple Music)
- `4`: Database error
- `5`: Conflict resolution required (use `musicdiff resolve`)

## Environment Variables

- `MUSICDIFF_CONFIG_DIR`: Override config directory (default: `~/.musicdiff`)
- `MUSICDIFF_LOG_LEVEL`: Set log level (`DEBUG`, `INFO`, `WARNING`, `ERROR`)

## Implementation Notes

### Framework Choice: Click

We use Click because:
- Clean, decorative syntax
- Automatic help generation
- Built-in shell completion
- Easy subcommand grouping
- Wide adoption in Python CLI tools

### Command Structure

```python
@click.group()
@click.version_option(version=__version__)
@click.option('--verbose', '-v', is_flag=True)
@click.pass_context
def cli(ctx, verbose):
    """MusicDiff - Git-like sync for your music libraries."""
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose

@cli.command()
def init():
    """Initialize MusicDiff and authenticate."""
    # Implementation...

@cli.command()
@click.option('--auto', is_flag=True)
@click.option('--dry-run', is_flag=True)
def sync(auto, dry_run):
    """Synchronize music libraries."""
    # Implementation...
```

### Progress Feedback

All long-running operations use `rich.progress`:
- Progress bars for batch operations
- Spinners for API calls
- Status indicators (✓, ✗, ⚠)
- Estimated time remaining

### Error Handling

- API errors: Retry with exponential backoff (max 3 attempts)
- Authentication errors: Prompt for re-authentication
- Network errors: Show helpful message, suggest checking connection
- Database errors: Log detailed error, suggest file permission check
