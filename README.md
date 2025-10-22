# MusicDiff

> Git-like bidirectional sync for your Spotify and Apple Music libraries

MusicDiff keeps your music libraries in sync across Spotify and Apple Music with a familiar git-like workflow. Review changes with a diff interface, resolve conflicts interactively, and schedule automatic syncs.

## Features

- **Bidirectional Sync**: Changes on either platform sync to the other
- **Git-like Workflow**: Commands like `init`, `status`, `sync`, `diff`, `log`
- **Interactive Conflict Resolution**: Terminal-based diff UI for manual conflict resolution
- **Automatic Syncing**: Daemon mode for scheduled background syncs
- **Comprehensive Sync**: Playlists, liked songs, and saved albums
- **Smart Track Matching**: ISRC-based matching with fuzzy fallback
- **Sync History**: Track all syncs and changes over time

## Quick Start

### Installation

```bash
# Clone the repository
git clone https://github.com/MarcoMartignone/MusicDiff.git
cd MusicDiff

# Install dependencies
pip install -r requirements.txt

# Install MusicDiff
pip install -e .
```

### Setup

1. **Initialize MusicDiff**

```bash
musicdiff init
```

This will:
- Create local database at `~/.musicdiff/musicdiff.db`
- Prompt you to authenticate with Spotify (opens browser)
- Prompt you to authenticate with Apple Music
- Fetch your initial library state

2. **Check Status**

```bash
musicdiff status
```

### Usage

**See pending changes:**
```bash
musicdiff diff
```

**Sync your libraries:**
```bash
# Interactive mode (review each change)
musicdiff sync

# Auto mode (apply non-conflicting changes automatically)
musicdiff sync --auto

# Dry run (see what would be synced)
musicdiff sync --dry-run
```

**View sync history:**
```bash
musicdiff log
```

**Resolve pending conflicts:**
```bash
musicdiff resolve
```

**Run as daemon (automatic syncs):**
```bash
# Start daemon (syncs every 24 hours)
musicdiff daemon

# Custom interval (6 hours)
musicdiff daemon --interval 21600

# Stop daemon
musicdiff daemon --stop
```

## How It Works

MusicDiff uses a **3-way merge algorithm** similar to Git:

```
     Local State (Database)
          /        \
         /          \
    Spotify      Apple Music
```

1. **Fetch** current state from both platforms
2. **Diff** against local state to detect changes
3. **Categorize** changes as auto-merge or conflicts
4. **Resolve** conflicts interactively (if any)
5. **Apply** changes via platform APIs
6. **Update** local state

## Configuration

### Spotify Setup

1. Go to [Spotify Developer Dashboard](https://developer.spotify.com/dashboard)
2. Create a new app
3. Add redirect URI: `http://localhost:8888/callback`
4. Copy Client ID and Client Secret
5. Add to `~/.musicdiff/config.yaml`:

```yaml
spotify:
  client_id: "your_client_id"
  client_secret: "your_client_secret"
```

### Apple Music Setup

1. Join [Apple Developer Program](https://developer.apple.com/programs/) ($99/year)
2. Create a MusicKit identifier
3. Generate a private key (.p8 file)
4. Add to `~/.musicdiff/config.yaml`:

```yaml
apple_music:
  team_id: "YOUR_TEAM_ID"
  key_id: "YOUR_KEY_ID"
  private_key_path: "~/.musicdiff/apple_music_key.p8"
```

## Architecture

```
musicdiff/
├── cli.py          # Command-line interface
├── spotify.py      # Spotify API client
├── apple.py        # Apple Music API client
├── database.py     # SQLite state management
├── diff.py         # 3-way diff algorithm
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
- [APPLE_MUSIC.md](docs/APPLE_MUSIC.md) - Apple Music API integration
- [DATABASE.md](docs/DATABASE.md) - Database schema and operations
- [DIFF_ALGORITHM.md](docs/DIFF_ALGORITHM.md) - 3-way merge algorithm
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
- [x] Apple Music integration
- [x] 3-way diff algorithm
- [x] Interactive conflict resolution
- [x] Daemon mode
- [ ] Web UI for visualization
- [ ] Support for YouTube Music
- [ ] Playlist versioning (git-like branches)
- [ ] Export/import to portable format
- [ ] ML-based conflict resolution suggestions

## Known Limitations

1. **Apple Music API**: Requires Apple Developer account ($99/year)
2. **Track Matching**: Not all tracks have ISRC codes; fallback matching may not be 100% accurate
3. **Rate Limits**: API rate limits may slow down large library syncs
4. **Regional Availability**: Tracks may not be available in all regions on all platforms

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

- Inspired by Git's 3-way merge algorithm
- Built with [spotipy](https://spotipy.readthedocs.io/) for Spotify API
- Terminal UI powered by [rich](https://rich.readthedocs.io/)

## Support

For issues and questions:
- Open an issue on [GitHub](https://github.com/MarcoMartignone/MusicDiff/issues)
- Check the [documentation](docs/)

---

**Note**: This is an early alpha version. Use at your own risk and always keep backups of your playlists!
