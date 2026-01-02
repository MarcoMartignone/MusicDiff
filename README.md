# MusicDiff

> Spotify playlist sync, Deezer downloading, and Rekordbox DJ library integration

MusicDiff is a complete workflow for DJs: sync Spotify playlists to Deezer, download high-quality tracks, and automatically organize them in Rekordbox with smart tags.

## Features

### Spotify to Deezer Sync
- **One-Way Sync**: Spotify → Deezer playlist mirroring
- **Smart Sync**: Skips playlists already in sync
- **ISRC Matching**: Accurate cross-platform track matching
- **No Duplicates**: Finds and reuses existing Deezer playlists

### Track Downloading
- **High-Quality Downloads**: Download tracks via Deemix (320kbps MP3)
- **Batch Processing**: Download entire playlists at once
- **Metadata Application**: Automatically sets playlist name (TCOM), track position (TRCK), and compilation flag (TCMP)
- **Resume Support**: Tracks download status, retries failed downloads

### Rekordbox Integration
- **My Tags**: Automatically creates tags from playlist names
- **Smart Playlists**: Auto-generates smart playlists filtered by tag
- **Batch Tagging**: Apply tags to thousands of tracks efficiently
- **Path Resolution**: Handles symlinks and cloud storage paths

### NTS Radio Import
- **Instant Import**: Create Spotify playlists from NTS Live radio shows
- **High Accuracy**: 90%+ track match rate

## Quick Start

```bash
source venv/bin/activate
musicdiff setup      # Interactive credential wizard
musicdiff init       # Initialize database
musicdiff select     # Choose playlists to sync
musicdiff sync       # Sync to Deezer
musicdiff download   # Download tracks
musicdiff apply-tags # Tag tracks in Rekordbox
```

## Usage

### Select Playlists

```bash
musicdiff select
```

Interactive selection of which Spotify playlists to sync and download.

### Sync to Deezer

```bash
musicdiff sync
musicdiff sync --dry-run  # Preview changes
```

### Download Tracks

```bash
musicdiff download
musicdiff download --dry-run           # Preview what would download
musicdiff download --playlist "name"   # Download specific playlist
musicdiff download --retry-failed      # Retry failed downloads
```

Downloads tracks to the configured output directory, organized by playlist folders.

### Apply Rekordbox Tags

```bash
musicdiff apply-tags
musicdiff apply-tags --dry-run         # Preview tagging
musicdiff apply-tags --playlist "name" # Tag specific playlist
```

Creates "My Tags" in Rekordbox matching playlist names, then applies tags to all downloaded tracks. Also creates smart playlists that filter by each tag.

### Import NTS Radio Shows

```bash
musicdiff nts-import "https://www.nts.live/shows/show-name/episodes/episode-name"
musicdiff nts-import "URL" --dry-run
```

### View Status

```bash
musicdiff list    # Show playlists with sync status
musicdiff status  # View overall sync status
musicdiff log     # View sync history
```

## Configuration

### Easy Setup

```bash
musicdiff setup
```

Interactive wizard that configures:
- Spotify API credentials (Client ID, Secret, Redirect URI)
- Deezer ARL token (from browser cookies)
- Download output path

### Manual Setup

Create `.musicdiff/.env`:
```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8888/callback"
export DEEZER_ARL="your_arl_token"
```

**Getting credentials:**
- **Spotify**: Create app at https://developer.spotify.com/dashboard
- **Deezer ARL**: Login to deezer.com → Developer Tools → Application → Cookies → `arl`

## Architecture

```
musicdiff/
├── cli.py          # Click CLI commands
├── spotify.py      # Spotify API client
├── deezer.py       # Deezer API client
├── sync.py         # Sync orchestration
├── downloader.py   # Deemix track downloading
├── rekordbox.py    # Rekordbox My Tags integration
├── database.py     # SQLite state management
├── matcher.py      # ISRC-based track matching
├── nts.py          # NTS Radio API client
├── ui.py           # Terminal UI (rich)
└── scheduler.py    # Daemon/scheduled syncs
```

## Workflow

```
Spotify Playlists
       ↓
   musicdiff sync
       ↓
Deezer Playlists
       ↓
  musicdiff download
       ↓
Local MP3 Files (with metadata)
       ↓
  musicdiff apply-tags
       ↓
Rekordbox Library (tagged + smart playlists)
```

## Development

```bash
pip install -r requirements.txt
pip install -e ".[dev]"

pytest              # Run tests
black musicdiff/    # Format code
ruff check musicdiff/  # Lint
mypy musicdiff/     # Type check
```

## Roadmap

- [x] Spotify → Deezer sync
- [x] Track downloading via Deemix
- [x] Rekordbox My Tags integration
- [x] NTS Radio import
- [x] Metadata application (TCOM, TRCK, TCMP)
- [x] Smart playlist creation
- [ ] Daemon mode for automatic syncs
- [ ] Web UI

## Known Limitations

1. **One-Way Sync**: Spotify is source of truth
2. **Deezer ARL Token**: May expire, requires periodic re-extraction
3. **ISRC Required**: Tracks without ISRC codes are skipped
4. **Rekordbox Closed**: Rekordbox must be closed when applying tags

## License

MIT License

## Acknowledgments

- [spotipy](https://spotipy.readthedocs.io/) - Spotify API
- [deemix](https://gitlab.com/RemixDev/deemix-py) - Deezer downloading
- [pyrekordbox](https://github.com/dylanljones/pyrekordbox) - Rekordbox database access
- [rich](https://rich.readthedocs.io/) - Terminal UI
