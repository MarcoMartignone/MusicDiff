# NTS Radio Import Feature

Import NTS Live radio show tracklists directly to Spotify playlists with a single command.

## Overview

The NTS import feature allows you to create Spotify playlists from NTS Radio show tracklists automatically. It fetches the show's metadata and tracks from the NTS API, searches for each track on Spotify, and creates a playlist with all matched tracks.

## Usage

### Basic Import

```bash
musicdiff nts-import "https://www.nts.live/shows/show-name/episodes/episode-name"
```

This will:
1. Fetch the episode metadata and tracklist from NTS
2. Authenticate with Spotify
3. Search for each track on Spotify
4. Create a private Spotify playlist with all matched tracks
5. Display a summary with the playlist URL

### Dry Run Mode

Preview what would be imported without creating a playlist:

```bash
musicdiff nts-import "URL" --dry-run
```

This is useful for:
- Checking track match rates before creating
- Verifying the episode has tracks available
- Testing the feature

### Custom Playlist Prefix

Customize the playlist name prefix (default is "NTS: "):

```bash
musicdiff nts-import "URL" --prefix "NTS Radio: "
musicdiff nts-import "URL" --prefix "🎵 "
musicdiff nts-import "URL" --prefix ""  # No prefix
```

## Examples

### Standard Import
```bash
musicdiff nts-import "https://www.nts.live/shows/the-breakfast-show-flo/episodes/the-breakfast-show-flo-27th-october-2025"
```

**Output:**
```
Fetching NTS episode...
✓ Episode: The NTS Breakfast Show w/ Flo
  Broadcast: 2025-10-27T09:00:00+00:00
  Tracks: 16

Connecting to Spotify...
✓ Connected to Spotify

Searching tracks on Spotify...
  Matching tracks... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Results:
  Matched: 16/16 tracks (100.0%)
  Skipped: 0 tracks

Creating playlist: NTS: The NTS Breakfast Show w/ Flo
✓ Playlist created successfully!
  16 tracks added
  https://open.spotify.com/playlist/5A1iFMpXgjT1rCvn1m6eXM
```

### With Custom Prefix
```bash
musicdiff nts-import "URL" --prefix "🎵 NTS Radio: "
```

Creates playlist named: `🎵 NTS Radio: The NTS Breakfast Show w/ Flo`

### Dry Run
```bash
musicdiff nts-import "URL" --dry-run
```

**Output:**
```
Fetching NTS episode...
✓ Episode: The NTS Breakfast Show w/ Flo
  Tracks: 16

Connecting to Spotify...
✓ Connected to Spotify

Searching tracks on Spotify...
  Matching tracks... ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%

Results:
  Matched: 16/16 tracks (100.0%)
  Skipped: 0 tracks

🔍 Dry run - no playlist created
```

## How It Works

### 1. NTS API Integration

The feature uses the public NTS Live API to fetch episode data:

**Endpoint:**
```
https://www.nts.live/api/v2/shows/{show_alias}/episodes/{episode_alias}
https://www.nts.live/api/v2/shows/{show_alias}/episodes/{episode_alias}/tracklist
```

**No authentication required** - uses public API endpoints.

### 2. URL Parsing

Accepts various URL formats:
- `https://www.nts.live/shows/covco/episodes/covco-8th-december-2016`
- `http://www.nts.live/shows/covco/episodes/covco-8th-december-2016`
- `www.nts.live/shows/covco/episodes/covco-8th-december-2016`

Extracts:
- `show_alias`: The show identifier (e.g., "covco")
- `episode_alias`: The episode identifier (e.g., "covco-8th-december-2016")

### 3. Track Matching

For each track in the NTS tracklist:

1. **Field-specific search** on Spotify:
   ```
   artist:{artist_name} track:{track_title}
   ```

2. **Fallback to simple search** if no results:
   ```
   {artist_name} {track_title}
   ```

3. **Return first match** or mark as skipped

**Match Rate:**
- Typically 80-100% for popular shows
- Handles special characters (é, ô, etc.)
- Matches live versions and remixes
- Works with obscure/underground artists

### 4. Playlist Creation

Creates a **private Spotify playlist** with:
- **Name**: `{prefix}{episode_name}`
- **Description**: `Imported from NTS Live - {broadcast_date}`
- **Tracks**: All matched tracks in original order

## Data Models

### NTSTrack
```python
@dataclass
class NTSTrack:
    artist: str              # Artist name
    title: str               # Track title
    uid: str                 # NTS unique identifier
    offset: Optional[int]    # Timestamp in seconds
    duration: Optional[int]  # Track length in seconds
```

### NTSEpisode
```python
@dataclass
class NTSEpisode:
    name: str                       # Episode name
    show_alias: str                 # Show identifier
    episode_alias: str              # Episode identifier
    broadcast_date: str             # ISO 8601 datetime
    description: str                # Episode description
    tracklist: List[NTSTrack]       # List of tracks
```

## Error Handling

### Invalid URL
```bash
musicdiff nts-import "https://invalid-url.com"
```
**Output:**
```
✗ Error: Invalid NTS URL format. Expected format:
https://www.nts.live/shows/<show>/episodes/<episode>
Got: https://invalid-url.com
```

### Episode Not Found
```bash
musicdiff nts-import "https://www.nts.live/shows/fake/episodes/fake"
```
**Output:**
```
✗ Episode not found. Please check the URL and try again.
```

### No Tracks Found
If an episode has no tracklist:
```
⚠ No tracks found in this episode
```

### No Spotify Matches
If no tracks can be found on Spotify:
```
✗ No tracks found on Spotify - cannot create playlist
```

### Authentication Errors
If Spotify credentials are missing or invalid:
```
Error: Spotify credentials not found.
Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables
Or run 'musicdiff init' to configure
```

## Configuration

### Required Credentials

Only **Spotify** credentials are needed (Deezer is not required for NTS import):

```bash
export SPOTIFY_CLIENT_ID="your_client_id"
export SPOTIFY_CLIENT_SECRET="your_client_secret"
export SPOTIFY_REDIRECT_URI="http://127.0.0.1:8888/callback"
```

### Setup

1. Run the setup wizard:
   ```bash
   musicdiff setup
   ```

2. Or manually create Spotify app:
   - Go to https://developer.spotify.com/dashboard
   - Create an app
   - Set redirect URI: `http://127.0.0.1:8888/callback`
   - Copy Client ID and Client Secret

## Performance

- **Episode fetch**: < 1 second
- **Track matching**: ~0.5 seconds per track
- **Playlist creation**: ~1 second

**Total time for 16-track episode**: ~10 seconds

## Limitations

1. **Spotify Only**: Creates playlists on Spotify (not Deezer)
2. **Read-Only NTS API**: Cannot modify NTS shows
3. **Match Accuracy**: Not all tracks may be available on Spotify
4. **Regional Availability**: Track availability varies by region
5. **Private Playlists**: All created playlists are private

## Implementation Details

### Files

- `musicdiff/nts.py` - NTS API client
- `musicdiff/spotify.py` - Extended with `search_track_uri()` method
- `musicdiff/cli.py` - Added `nts-import` command

### Architecture

```
User Input (NTS URL)
    ↓
URL Parsing (extract show/episode aliases)
    ↓
NTS API Fetch (metadata + tracklist)
    ↓
Spotify Authentication
    ↓
Track Search (parallel queries)
    ↓
Playlist Creation (batch add tracks)
    ↓
Success! (display playlist URL)
```

### API Endpoints Used

**NTS API:**
- `GET https://www.nts.live/api/v2/shows/{show}/episodes/{episode}`
- `GET https://www.nts.live/api/v2/shows/{show}/episodes/{episode}/tracklist`

**Spotify API:**
- `GET https://api.spotify.com/v1/search` (track search)
- `POST https://api.spotify.com/v1/users/{user}/playlists` (create playlist)
- `POST https://api.spotify.com/v1/playlists/{id}/tracks` (add tracks)

## Testing

### Phase 1: NTS API Client
```bash
python test_phase2.py
```
Tests URL parsing and tracklist fetching.

### Phase 2: Spotify Search
```bash
python test_phase2.py
```
Tests track search with real NTS tracklist.

### Phase 3: End-to-End
```bash
musicdiff nts-import "URL" --dry-run
```
Tests complete flow without creating playlist.

## Future Enhancements

- [ ] Batch import multiple episodes
- [ ] Schedule automatic imports for favorite shows
- [ ] Support for other radio stations (BBC Radio, Rinse FM, etc.)
- [ ] Playlist update mode (add new tracks to existing playlist)
- [ ] Export tracklist to CSV/JSON
- [ ] Integration with music recognition APIs for better matching

## Troubleshooting

### "Command not found: musicdiff"

Install the package:
```bash
cd /home/marcom/MusicDiff
source venv/bin/activate
pip install -e .
```

### Low Match Rate

Some shows with underground/rare tracks may have lower match rates. This is normal and depends on Spotify's catalog.

### Browser Won't Open for Auth

If running in WSL or headless environment, the OAuth URL will be printed. Copy and paste it into a browser manually.

### Playlist Not Appearing

Playlists are created as **private**. Check your Spotify Library under "Playlists" - they won't appear in public search.

## Support

For issues:
- Check [docs/NTS_IMPORT_PHASE_1.md](NTS_IMPORT_PHASE_1.md) for implementation details
- Open an issue on [GitHub](https://github.com/MarcoMartignone/MusicDiff/issues)
- Review the phase documentation for debugging

---

**Note**: This feature uses the public NTS API and does not require NTS authentication. It respects NTS's API rate limits and usage guidelines.
