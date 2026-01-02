# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

MusicDiff is a Python CLI tool for one-way synchronization of Spotify playlists to Deezer, with NTS Radio show import and Rekordbox DJ software integration. It also includes track downloading via Deemix.

## Commands

```bash
# Setup and initialization
source venv/bin/activate
musicdiff setup      # Interactive wizard for credentials
musicdiff init       # Initialize database

# Core operations
musicdiff select     # Choose playlists to sync
musicdiff sync       # Perform sync (Spotify → Deezer)
musicdiff sync --dry-run
musicdiff list       # Show playlists with sync status
musicdiff status     # View sync status
musicdiff log        # View sync history

# Downloading
musicdiff download              # Download selected playlists
musicdiff download --dry-run    # Preview what would be downloaded

# Rekordbox integration
musicdiff apply-tags            # Apply playlist tags to tracks in Rekordbox

# NTS Radio import
musicdiff nts-import "https://www.nts.live/shows/.../episodes/..."
musicdiff nts-import "URL" --dry-run

# Development
pytest                          # Run tests
black musicdiff/                # Format code
ruff check musicdiff/           # Lint
mypy musicdiff/                 # Type check
pip install -e ".[dev]"         # Install dev dependencies
```

## Architecture

### Data Flow
```
Spotify (source) → Local SQLite DB → Deezer (target)
                        ↓
              Download via Deemix → Local files
                        ↓
              Rekordbox tagging → DJ library
```

### Core Modules

- **cli.py** - Click-based CLI with all commands. Entry point: `musicdiff.cli:main`
- **sync.py** - `SyncEngine` orchestrates Spotify→Deezer sync with dry-run support
- **database.py** - SQLite state management (playlist_selections, synced_playlists, tracks, sync_log, download_status, tag_queue)
- **spotify.py** - `SpotifyClient` wrapping spotipy with OAuth
- **deezer.py** - `DeezerClient` using private API with ARL token auth
- **matcher.py** - `TrackMatcher` for cross-platform matching (ISRC-first, fuzzy fallback)
- **downloader.py** - `DeemixDownloader` for track downloads with metadata application
- **rekordbox.py** - `RekordboxClient` using pyrekordbox for My Tags integration
- **nts.py** - NTS Radio API for episode tracklist fetching
- **ui.py** - Terminal UI with rich library (progress bars, tables, prompts)

### Key Patterns

1. **ISRC Matching**: Primary strategy for cross-platform track matching
2. **One-Way Sync**: Spotify is source of truth, Deezer mirrors exactly
3. **Caching**: rekordbox.py builds O(1) lookup caches for batch operations (path→content, tag_name→tag, existing_tag_links)
4. **Path Mapping**: Symlink handling between `/Documents/MUSIC_LINK/` and `/Library/CloudStorage/SynologyDrive-MarcoMartignone/MUSIC/`
5. **Metadata Tags**: TCOM=playlist name, TRCK=position, TCMP=1 (compilation flag)

### Configuration

Credentials stored in `.musicdiff/.env`:
```
SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI
DEEZER_ARL  # Browser cookie value
```

Database: `.musicdiff/musicdiff.db`

## Rekordbox Integration

The Rekordbox module uses pyrekordbox to interact with Rekordbox's encrypted database:
- Creates "My Tags" under ParentID=4 (Playlist category)
- Creates smart playlists filtering by tag ID (not name)
- `FolderPath` in Rekordbox contains the full file path (not folder + filename)
