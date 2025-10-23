# UI Components Documentation

## Overview

The UI module (`ui.py`) provides terminal-based user interface components using the `rich` and `prompt_toolkit` libraries for a clean, interactive CLI experience focused on playlist selection and sync status.

## Dependencies

- **rich**: Terminal formatting, tables, progress bars, panels
- **prompt_toolkit**: Interactive checkbox selection dialog

## Class: `UI`

```python
class UI:
    def __init__(self)
    def select_playlists(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]
    def show_playlist_list(self, playlists: List[Dict], synced_playlists: Dict[str, Dict])
    def show_sync_preview(self, to_create: List[str], to_update: List[str], to_delete: List[str])
    def create_progress(self, description: str) -> Progress
    def confirm(self, message: str, default: bool = False) -> bool
    def print_success(self, message: str)
    def print_error(self, message: str)
    def print_warning(self, message: str)
    def print_info(self, message: str)
    def show_status(self, title: str, items: dict)
    def show_sync_summary(self, result: SyncResult)
```

## Core Components

### 1. Playlist Selection

Interactive checkbox interface for selecting playlists to sync.

```python
def select_playlists(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]:
    """Interactive playlist selection with checkboxes.

    Args:
        playlists: List of playlist dicts with spotify_id, name, track_count
        current_selections: Dict mapping spotify_id -> selected (bool)

    Returns:
        Dict mapping spotify_id -> selected (bool)
    """
    # Show checkbox dialog
    result = checkboxlist_dialog(
        title="Select Playlists",
        text="Choose which Spotify playlists to sync to Deezer:",
        values=[(spotify_id, f"{name} ({track_count} tracks)") for ...],
        default_values=[spotify_id for spotify_id in currently_selected]
    ).run()
```

**Example Interface:**
```
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
```

**Fallback Text Mode:**

If checkbox dialog fails (e.g., terminal doesn't support it), falls back to simple text-based selection:

```python
def _text_based_selection(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]:
    """Fallback text-based playlist selection."""
    # Display numbered list
    # Prompt for comma-separated numbers to toggle
    # Return updated selections
```

**Example Output:**
```
Using simplified selection mode

1. ✓ Summer Vibes 2025 (45 tracks)
2. ✓ Workout Mix (32 tracks)
3. ✗ Chill Evening (28 tracks)
4. ✓ Party Hits (67 tracks)
5. ✗ Study Focus (41 tracks)

Enter playlist numbers to toggle (comma-separated), or 'done' to finish:
Toggle playlists [done]: 3,5
```

---

### 2. Playlist List View

Display all playlists with sync status.

```python
def show_playlist_list(self, playlists: List[Dict], synced_playlists: Dict[str, Dict]):
    """Show list of all playlists with sync status."""
    table = Table(show_header=True, header_style="bold cyan")
    table.add_column("Status", width=8)
    table.add_column("Playlist Name", style="white")
    table.add_column("Tracks", justify="right", width=10)
    table.add_column("Last Synced", width=20)
    table.add_column("Deezer", width=10)
```

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

### 3. Sync Preview

Show what will be synced in dry-run mode.

```python
def show_sync_preview(self, to_create: List[str], to_update: List[str], to_delete: List[str]):
    """Show preview of what will be synced."""
```

**Example Output:**
```
Sync Preview:

Create on Deezer (1):
  + Summer Vibes 2025

Update on Deezer (2):
  ~ Workout Mix
  ~ Party Hits

Delete from Deezer (0):
  (none)
```

---

### 4. Progress Bars

Progress tracking for long-running operations.

```python
def create_progress(self, description: str) -> Progress:
    """Create and return a progress bar."""
    return Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=self.console
    )
```

**Usage:**
```python
with ui.create_progress("Syncing playlists") as progress:
    task = progress.add_task("Processing...", total=len(playlists))

    for playlist in playlists:
        # Sync playlist
        progress.update(task, advance=1)
```

**Example Output:**
```
⠋ Syncing playlists  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  60% 3/5
```

---

### 5. Status Messages

Colored status messages for feedback.

```python
def print_success(self, message: str):
    """Print a success message."""
    self.console.print(f"[green]✓ {message}[/green]")

def print_error(self, message: str):
    """Print an error message."""
    self.console.print(f"[red]✗ {message}[/red]")

def print_warning(self, message: str):
    """Print a warning message."""
    self.console.print(f"[yellow]⚠ {message}[/yellow]")

def print_info(self, message: str):
    """Print an info message."""
    self.console.print(f"[blue]ℹ {message}[/blue]")
```

**Example Output:**
```
✓ Playlist synced successfully
✗ Failed to sync playlist: API error
⚠ Some tracks could not be matched
ℹ Syncing 3 selected playlists to Deezer...
```

---

### 6. Confirmation Prompts

Yes/no confirmation using rich.

```python
def confirm(self, message: str, default: bool = False) -> bool:
    """Ask user for yes/no confirmation."""
    return Confirm.ask(message, default=default)
```

**Example:**
```python
if ui.confirm("Delete this playlist from Deezer?", default=False):
    deezer_client.delete_playlist(playlist_id)
```

**Example Output:**
```
Delete this playlist from Deezer? [y/N]: y
```

---

### 7. Status Tables

Generic key-value status display.

```python
def show_status(self, title: str, items: dict):
    """Show status information in a table."""
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Key", style="cyan")
    table.add_column("Value")

    for key, value in items.items():
        table.add_row(key, str(value))
```

**Example:**
```python
ui.show_status("Database Status", {
    "Path": db.db_path,
    "Size": "2.3 MB",
    "Selected Playlists": 3,
    "Synced Playlists": 3
})
```

**Example Output:**
```
Database Status

Path              ~/.musicdiff/musicdiff.db
Size              2.3 MB
Selected Playlists  3
Synced Playlists    3
```

---

### 8. Sync Summary

Display summary after sync completes.

```python
def show_sync_summary(self, result: SyncResult):
    """Show summary after sync completes."""
    self.console.rule("[bold cyan]Sync Summary[/bold cyan]")

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("Metric", style="bold")
    table.add_column("Count")

    table.add_row("Playlists Created", f"[green]{result.playlists_created}[/green]")
    table.add_row("Playlists Updated", f"[yellow]{result.playlists_updated}[/yellow]")
    table.add_row("Playlists Deleted", f"[red]{result.playlists_deleted}[/red]")
    table.add_row("Total Synced", f"[cyan]{result.total_synced}[/cyan]")
    table.add_row("Duration", f"{result.duration_seconds:.1f}s")
```

**Example Output:**
```
━━━━━━━━━━━━━━━━━━━━━━ Sync Summary ━━━━━━━━━━━━━━━━━━━━━━

Playlists Created     1
Playlists Updated     2
Playlists Deleted     0
Total Synced          3
Duration              12.3s
```

---

## Design Principles

### Color Coding

Consistent color scheme across all components:
- **Green**: Success, created, selected
- **Yellow**: Warning, updated
- **Red**: Error, deleted, deselected
- **Blue**: Info, progress
- **Cyan**: Headers, labels
- **Dim**: Disabled, not selected

### Icons

Consistent icons for status:
- `✓`: Success, enabled, synced
- `✗`: Error, failed
- `⚠`: Warning
- `ℹ`: Info
- `○`: Not selected
- `~`: Updated
- `+`: Created
- `-`: Deleted

### Responsive Layout

Tables automatically adjust to terminal width:
- Column widths specified where needed
- Text truncation for long names
- Horizontal scrolling avoided

### Accessibility

- Clear text labels, not just colors
- Icons supplement color coding
- Keyboard-only navigation
- Screen reader friendly (rich's native support)

## Error Handling

### Checkbox Dialog Failure

If `checkboxlist_dialog` fails (unsupported terminal):

```python
try:
    result = checkboxlist_dialog(...).run()
except Exception as e:
    self.print_error(f"Selection failed: {e}")
    return self._text_based_selection(playlists, current_selections)
```

Gracefully falls back to text-based selection.

### Console Rendering Issues

If rich rendering fails (very rare):
- Falls back to plain print statements
- Still functional, just less pretty
- Logged for debugging

## Usage Examples

### Complete Selection Flow

```python
ui = UI()

# Get playlists from Spotify
sp_playlists = spotify.fetch_playlists()

# Get current selections from database
current_selections = {p['spotify_id']: p.get('selected', False) for p in db.get_all_playlist_selections()}

# Show selection interface
new_selections = ui.select_playlists(sp_playlists, current_selections)

# Save to database
for spotify_id, selected in new_selections.items():
    db.update_playlist_selection(spotify_id, selected)

ui.print_success(f"Updated playlist selections ({sum(new_selections.values())} selected)")
```

### Complete Sync with Progress

```python
ui = UI()

selected_playlists = db.get_selected_playlists()
ui.print_info(f"Syncing {len(selected_playlists)} playlists to Deezer...")

with ui.create_progress("Syncing playlists") as progress:
    task = progress.add_task("Processing...", total=len(selected_playlists))

    for playlist in selected_playlists:
        try:
            sync_playlist(playlist)
            progress.update(task, advance=1)
        except Exception as e:
            ui.print_error(f"Failed to sync '{playlist['name']}': {e}")

ui.print_success("Sync complete!")
```

## Future Enhancements

- **Playlist Details View**: Expand playlist to show all tracks
- **Track Match Status**: Visualize which tracks matched/skipped
- **Live Sync Progress**: Real-time track-by-track progress
- **Color Themes**: Customizable color schemes
- **Terminal Recording**: Export session as GIF for demos
