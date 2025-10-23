# MusicDiff

> Simple one-way playlist transfer from Spotify to Deezer

MusicDiff keeps your Spotify playlists synced to Deezer. Select which playlists you want to mirror, and MusicDiff will automatically create and update them on Deezer to match your Spotify playlists exactly.

## Features

- **One-Way Sync**: Spotify → Deezer playlist transfer
- **Playlist Selection**: Choose which Spotify playlists to sync
- **Smart Sync**: Automatically detects when playlists are already in sync and skips unnecessary updates
- **No Duplicates**: Finds and reuses existing Deezer playlists instead of creating duplicates
- **Accurate Preview**: Shows exactly what will happen before you confirm
- **Full Overwrite**: Deezer playlists mirror Spotify playlists exactly
- **Smart Track Matching**: ISRC-based track matching across platforms
- **Clean Deselection**: Remove playlists from Deezer when deselected
- **Sync History**: Track all syncs and changes over time

## Quick Start

### One-Command Setup 🚀

```bash
source venv/bin/activate
musicdiff setup
```

This **interactive wizard** will:
1. ✅ Guide you step-by-step through creating Spotify API credentials
2. ✅ Set up Deezer authentication (requires ARL token from browser)
3. ✅ Test your credentials automatically
4. ✅ Save everything to `.env` file
5. ✅ Get you ready to sync in 5 minutes!

No need to read documentation or manually configure anything - just follow the prompts!

### After Setup

```bash
# Load credentials
source ~/Documents/MusicDiff/.musicdiff/.env

# Initialize database
musicdiff init

# Select playlists to sync
musicdiff select

# Start syncing!
musicdiff sync
```

## Usage

### Select Playlists

```bash
# Interactive checkbox selection
musicdiff select
```

Choose which Spotify playlists to sync to Deezer. Use arrow keys to navigate, SPACE to select/deselect, and ENTER to confirm.

### View Your Playlists

```bash
# Show all playlists with sync status
musicdiff list
```

See which playlists are selected for sync and when they were last synced.

### Sync to Deezer

```bash
# Perform sync
musicdiff sync

# Dry run (preview what would be synced)
musicdiff sync --dry-run
```

**What happens during sync:**
- Checks if playlists exist on Deezer (finds existing ones by name to avoid duplicates)
- Compares Spotify vs Deezer track lists to detect changes
- If playlists are already identical: Skips sync entirely (nothing to do!)
- If changes detected:
  - Creates playlists on Deezer (if they don't exist) as **private playlists**
  - Updates existing Deezer playlists to match Spotify exactly (full overwrite)
  - Deselected playlists are deleted from Deezer
- All tracks are matched using ISRC codes (International Standard Recording Code)

### View Status

```bash
# See sync status
musicdiff status

# View sync history
musicdiff log
```

## How It Works

MusicDiff performs an intelligent one-way sync from Spotify to Deezer:

```
1. Check playlist status on Deezer
   - Verify if playlists exist (by database ID)
   - If deleted, search for existing playlist with same name
   - Avoid creating duplicates

2. Compare playlists (if only updates pending)
   - Fetch both Spotify and Deezer versions
   - Compare track counts (fast check)
   - Compare ISRCs in order (accurate check)
   - Skip if playlists are already identical

3. For each playlist needing changes:
   - If playlist doesn't exist: Create it (as private playlist)
   - If playlist exists: Update it (full overwrite)

4. Delete deselected playlists from Deezer

5. Update local database with sync mappings
```

**Track Matching:**
- Uses ISRC (International Standard Recording Code) for accurate cross-platform matching
- Searches Deezer for matching track by ISRC
- Caches successful matches in database for faster future syncs
- Skips tracks without ISRC codes (reports as unmatched)

## Configuration

### Easy Setup (Recommended)

Just run `musicdiff setup` and follow the wizard! It handles everything automatically.

### Manual Setup

If you prefer to set up manually:

**Required:**
- Spotify Client ID & Secret (free, 5 minutes)
  - Create app at https://developer.spotify.com/dashboard
  - Set redirect URI to: `http://127.0.0.1:8888/callback`
- Deezer ARL token (free with Deezer account)
  - Login to deezer.com in browser
  - Open Developer Tools → Application → Cookies
  - Copy value of `arl` cookie

Create `.musicdiff/.env` file:
```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8888/callback"
export DEEZER_ARL="your_arl_token"
```

## Architecture

```
musicdiff/
├── cli.py          # Command-line interface
├── spotify.py      # Spotify API client
├── deezer.py       # Deezer API client
├── database.py     # SQLite state management
├── sync.py         # Sync orchestration
├── matcher.py      # Cross-platform track matching
├── ui.py           # Terminal UI components
└── scheduler.py    # Daemon/scheduled syncs
```

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for detailed architecture documentation.

## Documentation

Comprehensive documentation available in the `docs/` directory:

- [ARCHITECTURE.md](docs/ARCHITECTURE.md) - System design and data flow
- [CLI.md](docs/CLI.md) - Command-line interface reference
- [SPOTIFY.md](docs/SPOTIFY.md) - Spotify API integration
- [DEEZER.md](docs/DEEZER.md) - Deezer API integration
- [DATABASE.md](docs/DATABASE.md) - Database schema and operations
- [SYNC_LOGIC.md](docs/SYNC_LOGIC.md) - Sync orchestration
- [TRACK_MATCHING.md](docs/TRACK_MATCHING.md) - Cross-platform track matching
- [UI_COMPONENTS.md](docs/UI_COMPONENTS.md) - Terminal UI components
- [SCHEDULING.md](docs/SCHEDULING.md) - Daemon and scheduled syncs

## Development

### Setup Development Environment

```bash
# Install development dependencies
pip install -r requirements.txt
pip install -e ".[dev]"

# Run tests
pytest

# Format code
black musicdiff/

# Lint
ruff check musicdiff/

# Type check
mypy musicdiff/
```

### Project Structure

```
MusicDiff/
├── musicdiff/          # Main package
├── docs/               # Documentation
├── tests/              # Test suite
├── README.md
├── pyproject.toml
└── requirements.txt
```

## Roadmap

- [x] Basic Spotify integration
- [x] Deezer integration (private API with ARL authentication)
- [x] One-way playlist sync with full overwrite
- [x] Interactive playlist selection
- [x] Smart sync (skip when already in sync)
- [x] Duplicate prevention (find and reuse existing playlists)
- [x] Accurate sync preview
- [ ] Daemon mode for automatic syncs
- [ ] Web UI for visualization
- [ ] Support for liked songs sync
- [ ] Support for albums sync
- [ ] Export/import to portable format

## Known Limitations

1. **Playlists Only**: Currently only syncs playlists (not liked songs or albums)
2. **One-Way Sync**: Changes on Deezer are not synced back to Spotify
3. **Deezer ARL Token**: Uses browser cookie for authentication; may expire and require periodic re-extraction
4. **Track Matching**: Not all tracks have ISRC codes; tracks without ISRC are skipped
5. **Rate Limits**: API rate limits may slow down large library syncs
6. **Regional Availability**: Tracks may not be available in all regions on all platforms
7. **Private Playlists Only**: Creates playlists as private on Deezer for reliability

## Contributing

Contributions welcome! Please read the documentation in `docs/` to understand the architecture.

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- Built with [spotipy](https://spotipy.readthedocs.io/) for Spotify API
- Deezer integration using private API
- Terminal UI powered by [rich](https://rich.readthedocs.io/)

## Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/MarcoMartignone/MusicDiff/issues)
- Check the [documentation](docs/)

---

**Note**: This is an early alpha version. Use at your own risk and always keep backups of your playlists!
