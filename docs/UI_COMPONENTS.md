# UI Components Documentation

## Overview

The UI module (`ui.py`) provides terminal-based user interface components using the `rich` library for beautiful, interactive CLI experiences.

## Dependencies

- **rich**: Terminal formatting, tables, progress bars
- **prompt_toolkit**: Interactive prompts and text input

## Core Components

### 1. Diff Viewer

Side-by-side comparison of changes.

```python
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

class DiffViewer:
    def __init__(self):
        self.console = Console()

    def show_playlist_diff(self, conflict: Conflict):
        """Display playlist conflict with side-by-side diff."""

        spotify_playlist = conflict.spotify_change.data
        apple_playlist = conflict.apple_change.data

        # Create comparison table
        table = Table(title=f"Conflict: {conflict.entity_id}", show_header=True)
        table.add_column("", style="bold")
        table.add_column("Spotify", style="cyan")
        table.add_column("Apple Music", style="magenta")

        # Compare metadata
        table.add_row(
            "Name",
            spotify_playlist.get('name', ''),
            apple_playlist.get('name', '')
        )

        # Compare tracks
        spotify_tracks = spotify_playlist.get('tracks', [])
        apple_tracks = apple_playlist.get('tracks', [])

        max_tracks = max(len(spotify_tracks), len(apple_tracks))

        for i in range(max_tracks):
            spotify_track = spotify_tracks[i] if i < len(spotify_tracks) else ""
            apple_track = apple_tracks[i] if i < len(apple_tracks) else ""

            # Highlight differences
            style_spotify = "green" if spotify_track and spotify_track not in apple_tracks else "red"
            style_apple = "green" if apple_track and apple_track not in spotify_tracks else "red"

            table.add_row(
                f"Track {i+1}",
                f"[{style_spotify}]{spotify_track}[/{style_spotify}]",
                f"[{style_apple}]{apple_track}[/{style_apple}]"
            )

        self.console.print(table)
```

**Example Output:**
```
╭────────── Conflict: Workout Mix ──────────╮
│                                           │
│           Spotify    │   Apple Music      │
│ Name    Workout Mix  │  Workout Mix       │
│ Track 1 Eye of Tiger │  Eye of Tiger      │
│ Track 2 Lose Yourself│  Stronger          │
│ Track 3 Till I Coll… │  Remember the Name │
╰───────────────────────────────────────────╯
```

---

### 2. Progress Bars

Show progress for long-running operations.

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

class ProgressDisplay:
    def __init__(self):
        self.progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=Console()
        )

    def sync_with_progress(self, changes: List[Change]):
        """Apply changes with progress bar."""

        with self.progress:
            task = self.progress.add_task("Syncing...", total=len(changes))

            for change in changes:
                self.progress.update(task, description=f"Applying {change.change_type.value}...")
                self.apply_change(change)
                self.progress.advance(task)
```

**Example Output:**
```
⠋ Applying playlist_updated... ━━━━━━━━━━━━━━━━━━╺━━ 75% 45/60
```

---

### 3. Interactive Prompts

Get user input for conflict resolution.

```python
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import radiolist_dialog

class InteractiveUI:
    def prompt_resolution(self, conflict: Conflict) -> str:
        """Prompt user to choose conflict resolution."""

        result = radiolist_dialog(
            title=f"Resolve Conflict: {conflict.entity_id}",
            text="Choose how to resolve this conflict:",
            values=[
                ('spotify', 'Keep Spotify version'),
                ('apple', 'Keep Apple Music version'),
                ('manual', 'Manual merge (interactive)'),
                ('skip', 'Skip for now')
            ]
        ).run()

        return result or 'skip'

    def confirm_changes(self, changes: List[Change]) -> bool:
        """Ask user to confirm before applying changes."""

        self.show_change_summary(changes)

        response = prompt("Apply these changes? (y/n): ").lower()
        return response in ['y', 'yes']
```

---

### 4. Change Summary

Display summary of pending changes.

```python
from rich.tree import Tree

class ChangeSummary:
    def __init__(self):
        self.console = Console()

    def show(self, diff_result: DiffResult):
        """Show tree view of changes."""

        tree = Tree("📊 Sync Summary")

        # Auto-merge changes
        if diff_result.auto_merge:
            auto_branch = tree.add(f"✓ Auto-merge ({len(diff_result.auto_merge)} changes)", style="green")

            # Group by type
            by_type = {}
            for change in diff_result.auto_merge:
                type_name = change.change_type.value
                if type_name not in by_type:
                    by_type[type_name] = []
                by_type[type_name].append(change)

            for type_name, changes in by_type.items():
                type_branch = auto_branch.add(f"{type_name} ({len(changes)})")
                for change in changes[:5]:  # Show first 5
                    type_branch.add(f"→ {change.entity_id}", style="dim")
                if len(changes) > 5:
                    type_branch.add(f"... and {len(changes) - 5} more", style="dim italic")

        # Conflicts
        if diff_result.conflicts:
            conflict_branch = tree.add(f"⚠ Conflicts ({len(diff_result.conflicts)})", style="red")
            for conflict in diff_result.conflicts:
                conflict_branch.add(f"→ {conflict.entity_id}", style="dim")

        self.console.print(tree)
```

**Example Output:**
```
📊 Sync Summary
├── ✓ Auto-merge (62 changes)
│   ├── playlist_updated (5)
│   │   ├── → Chill Mix
│   │   ├── → Party Hits
│   │   └── ... and 3 more
│   └── liked_song_added (57)
│       ├── → Track A
│       └── ... and 56 more
└── ⚠ Conflicts (1)
    └── → Workout Mix
```

---

### 5. Manual Merge UI

Interactive track-by-track merge interface.

```python
from prompt_toolkit.shortcuts import checkboxlist_dialog

class ManualMergeUI:
    def merge_playlist_tracks(self, spotify_tracks: List[str], apple_tracks: List[str]) -> List[str]:
        """Let user select tracks for merged playlist."""

        # Combine all unique tracks
        all_tracks = list(set(spotify_tracks + apple_tracks))

        # Pre-select tracks that appear on both platforms
        defaults = [t for t in all_tracks if t in spotify_tracks and t in apple_tracks]

        result = checkboxlist_dialog(
            title="Manual Merge: Select Tracks",
            text="Select tracks to include in the merged playlist:",
            values=[(track, f"{track} {'[S+A]' if track in defaults else '[S]' if track in spotify_tracks else '[A]'}")
                    for track in all_tracks],
            default_values=defaults
        ).run()

        return result or []
```

**Example UI:**
```
┌── Manual Merge: Select Tracks ────────────┐
│ Select tracks to include:                 │
│                                            │
│ [x] Eye of the Tiger [S+A]                │
│ [x] Lose Yourself [S]                     │
│ [ ] Stronger [A]                          │
│ [x] Till I Collapse [S]                   │
│ [ ] Remember the Name [A]                 │
│                                            │
│          [OK]        [Cancel]             │
└────────────────────────────────────────────┘
```

---

## Styling

### Color Scheme

```python
# Platform colors
SPOTIFY_COLOR = "cyan"
APPLE_COLOR = "magenta"

# Status colors
SUCCESS_COLOR = "green"
WARNING_COLOR = "yellow"
ERROR_COLOR = "red"
CONFLICT_COLOR = "red bold"

# Text styles
HEADER_STYLE = "bold underline"
DIM_STYLE = "dim"
```

### Icons

```python
ICONS = {
    'success': '✓',
    'error': '✗',
    'warning': '⚠',
    'info': 'ℹ',
    'music': '🎵',
    'sync': '🔄',
    'conflict': '⚡',
    'spotify': '🟢',
    'apple': '🍎'
}
```

---

## Error Display

```python
from rich.panel import Panel

class ErrorDisplay:
    def __init__(self):
        self.console = Console()

    def show_error(self, error: Exception, context: str = ""):
        """Display error in formatted panel."""

        error_panel = Panel(
            f"[red bold]Error:[/red bold] {str(error)}\n\n"
            f"[dim]Context: {context}[/dim]",
            title="❌ Error",
            border_style="red"
        )

        self.console.print(error_panel)

    def show_api_error(self, platform: str, error: Exception):
        """Display API-specific error."""

        self.console.print(f"\n[red]API Error ({platform}):[/red]")
        self.console.print(f"  {str(error)}")

        if hasattr(error, 'http_status'):
            self.console.print(f"  HTTP Status: {error.http_status}")

        self.console.print("\n[yellow]Suggestions:[/yellow]")

        if platform == "spotify":
            self.console.print("  • Check Spotify API credentials")
            self.console.print("  • Verify token hasn't expired")
        elif platform == "apple":
            self.console.print("  • Check Apple Music developer token")
            self.console.print("  • Verify user token is valid")
```

---

## Logging

Display logs with proper formatting.

```python
from rich.logging import RichHandler
import logging

# Setup rich logging
logging.basicConfig(
    level="INFO",
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(rich_tracebacks=True)]
)

logger = logging.getLogger("musicdiff")
```

**Usage:**
```python
logger.info("Starting sync...")
logger.warning("Conflict detected")
logger.error("Failed to apply change", exc_info=True)
```

---

## Testing

Mock UI for automated testing.

```python
class MockUI:
    def __init__(self):
        self.prompts = []
        self.resolutions = {}

    def set_resolution(self, conflict_id: str, resolution: str):
        """Pre-set resolution for testing."""
        self.resolutions[conflict_id] = resolution

    def prompt_resolution(self, conflict: Conflict) -> str:
        """Return pre-set resolution."""
        return self.resolutions.get(conflict.entity_id, 'skip')

    def show_conflict(self, conflict: Conflict):
        """No-op for testing."""
        pass
```

## References

- [Rich Documentation](https://rich.readthedocs.io/)
- [Prompt Toolkit](https://python-prompt-toolkit.readthedocs.io/)
