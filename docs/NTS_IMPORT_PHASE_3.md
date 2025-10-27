# Phase 3: CLI Command and Playlist Creation

## Objective
Create a complete CLI command that combines NTS fetching and Spotify searching to create playlists.

## Implementation Tasks

### 1. Add CLI Command to `musicdiff/cli.py`

```python
@click.command()
@click.argument('nts_url')
@click.option('--dry-run', is_flag=True, help='Preview without creating playlist')
@click.option('--prefix', default='NTS: ', help='Playlist name prefix')
def nts_import(nts_url, dry_run, prefix):
    """
    Import NTS show tracklist to Spotify playlist.

    Example:
        musicdiff nts-import https://www.nts.live/shows/covco/episodes/...
    """
```

### 2. Implementation Flow

```python
def nts_import(nts_url, dry_run, prefix):
    # 1. Validate and fetch NTS data
    console.print("[bold]Fetching NTS episode...[/bold]")
    nts_client = NTSClient()
    episode = nts_client.get_episode_from_url(nts_url)

    console.print(f"Episode: {episode.name}")
    console.print(f"Tracks: {len(episode.tracklist)}")

    # 2. Search tracks on Spotify with progress bar
    console.print("\n[bold]Searching tracks on Spotify...[/bold]")
    spotify_client = SpotifyClient()

    matched = []
    skipped = []

    with Progress() as progress:
        task = progress.add_task("[cyan]Matching tracks...",
                                 total=len(episode.tracklist))

        for track in episode.tracklist:
            uri = spotify_client.search_track(track.artist, track.title)
            if uri:
                matched.append({'track': track, 'uri': uri})
            else:
                skipped.append(track)
            progress.update(task, advance=1)

    # 3. Display summary
    display_summary(matched, skipped, episode)

    # 4. Create playlist (if not dry-run)
    if dry_run:
        console.print("\n[yellow]Dry run - no playlist created[/yellow]")
        return

    if not matched:
        console.print("[red]No tracks found - aborting[/red]")
        return

    playlist_name = f"{prefix}{episode.name}"
    playlist = spotify_client.create_playlist(playlist_name)
    spotify_client.add_tracks_to_playlist(playlist['id'],
                                         [m['uri'] for m in matched])

    console.print(f"\n[bold green]✓ Created playlist: {playlist_name}[/bold green]")
    console.print(f"[dim]{playlist['external_urls']['spotify']}[/dim]")
```

### 3. Summary Report Display

```python
def display_summary(matched, skipped, episode):
    """Display matching results in a formatted table."""

    # Summary stats
    total = len(matched) + len(skipped)
    match_rate = len(matched) / total * 100 if total > 0 else 0

    console.print(f"\n[bold]Results:[/bold]")
    console.print(f"  Matched: {len(matched)} tracks ({match_rate:.1f}%)")
    console.print(f"  Skipped: {len(skipped)} tracks")

    # Skipped tracks table
    if skipped:
        console.print("\n[yellow]Skipped Tracks:[/yellow]")
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Artist", style="dim")
        table.add_column("Title")

        for track in skipped[:10]:  # Show first 10
            table.add_row(track.artist, track.title)

        if len(skipped) > 10:
            table.add_row("...", f"({len(skipped)-10} more)")

        console.print(table)
```

### 4. Add to Main CLI Group

```python
# In cli.py main group
cli.add_command(nts_import)
```

## Spotify Playlist Creation

**Methods needed in SpotifyClient**:

```python
def create_playlist(self, name: str, description: str = "", public: bool = True) -> dict:
    """Create a new Spotify playlist."""
    user_id = self.sp.current_user()['id']
    return self.sp.user_playlist_create(user_id, name,
                                       public=public,
                                       description=description)

def add_tracks_to_playlist(self, playlist_id: str, track_uris: List[str]):
    """Add tracks to a playlist (handles batching for >100 tracks)."""
    # Spotify API limit: 100 tracks per request
    for i in range(0, len(track_uris), 100):
        batch = track_uris[i:i+100]
        self.sp.playlist_add_items(playlist_id, batch)
```

## UI Components

Use existing `rich` library (already in requirements.txt):
- `Console` for formatted output
- `Progress` for track matching progress bar
- `Table` for skipped tracks display
- Color coding: green=success, yellow=warning, red=error

## Error Handling

- Invalid NTS URL → Display error, exit gracefully
- No Spotify credentials → Clear setup instructions
- Zero matched tracks → Warning, don't create playlist
- API errors → Retry with user feedback
- Keyboard interrupt → Clean exit

## Testing Phase 3

### Test Cases:

1. **Dry Run**:
   ```bash
   musicdiff nts-import "https://www.nts.live/shows/covco/episodes/..." --dry-run
   # Should display summary without creating playlist
   ```

2. **Full Import**:
   ```bash
   musicdiff nts-import "https://www.nts.live/shows/covco/episodes/..."
   # Should create playlist and display link
   ```

3. **Custom Prefix**:
   ```bash
   musicdiff nts-import "URL" --prefix "NTS Radio: "
   # Playlist should be named "NTS Radio: Episode Name"
   ```

4. **Error Cases**:
   ```bash
   # Invalid URL
   musicdiff nts-import "https://invalid-url.com"

   # Non-existent episode
   musicdiff nts-import "https://www.nts.live/shows/fake/episodes/fake"

   # No credentials
   musicdiff nts-import "URL"  # Without SPOTIFY_CLIENT_ID set
   ```

### Success Criteria:
- ✅ Command accepts NTS URLs
- ✅ Displays progress during matching
- ✅ Shows clear summary report
- ✅ Creates Spotify playlist with correct name
- ✅ Handles all error cases gracefully
- ✅ Dry-run mode works correctly

## Example Usage (Complete Feature):

```bash
# Setup (one-time)
musicdiff setup  # Configure Spotify credentials

# Import NTS show
musicdiff nts-import "https://www.nts.live/shows/covco/episodes/covco-8th-december-2016"

# Output:
# Fetching NTS episode...
# Episode: Covco & Jackie Dagger - 8th December 2016
# Tracks: 15
#
# Searching tracks on Spotify...
# [████████████████████] 15/15 100%
#
# Results:
#   Matched: 12 tracks (80.0%)
#   Skipped: 3 tracks
#
# Skipped Tracks:
# ┌────────────────┬─────────────────┐
# │ Artist         │ Title           │
# ├────────────────┼─────────────────┤
# │ Unknown Artist │ Unknown Track   │
# └────────────────┴─────────────────┘
#
# ✓ Created playlist: NTS: Covco & Jackie Dagger - 8th December 2016
# https://open.spotify.com/playlist/...
```

## Documentation Updates

Update `README.md`:
```markdown
### Import NTS Show to Spotify

Create a Spotify playlist from an NTS radio show:

```bash
musicdiff nts-import "https://www.nts.live/shows/..."
```

Options:
- `--dry-run`: Preview without creating playlist
- `--prefix TEXT`: Customize playlist name prefix (default: "NTS: ")
```

## Next Steps After Phase 3
- User acceptance testing
- Bug fixes and refinements
- Optional: Add to documentation
- Optional: Add unit tests for CLI commands
