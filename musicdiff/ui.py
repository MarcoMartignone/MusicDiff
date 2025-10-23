"""
Terminal UI components for MusicDiff.

Simple, focused UI for selecting Spotify playlists and showing sync status.
"""

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from prompt_toolkit import prompt
from prompt_toolkit.shortcuts import checkboxlist_dialog
from typing import List, Dict, Tuple
from datetime import datetime


class UI:
    """Terminal-based user interface."""

    def __init__(self):
        """Initialize UI."""
        self.console = Console()

    def select_playlists(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]:
        """Interactive playlist selection with checkboxes.

        Args:
            playlists: List of playlist dicts with spotify_id, name, track_count
            current_selections: Dict mapping spotify_id -> selected (bool)

        Returns:
            Dict mapping spotify_id -> selected (bool)
        """
        if not playlists:
            self.print_warning("No Spotify playlists found.")
            return {}

        self.console.print("\n[bold cyan]Select Playlists to Sync to Deezer[/bold cyan]\n")
        self.console.print("Use [cyan]↑↓[/cyan] to navigate, [cyan]SPACE[/cyan] to select/deselect, [cyan]ENTER[/cyan] to confirm\n")

        # Create checkbox list
        values = []
        for playlist in playlists:
            spotify_id = playlist.get('spotify_id') or playlist.get('id')
            name = playlist['name']
            track_count = playlist.get('track_count', 0)

            # Check if currently selected
            is_selected = current_selections.get(spotify_id, False)

            values.append((
                spotify_id,
                f"{name} ({track_count} tracks)",
                is_selected
            ))

        try:
            # Show checkbox dialog
            result = checkboxlist_dialog(
                title="Select Playlists",
                text="Choose which Spotify playlists to sync to Deezer:",
                values=[(v[0], v[1]) for v in values],
                default_values=[v[0] for v in values if v[2]]  # Pre-select currently selected
            ).run()

            if result is None:
                # User cancelled
                self.print_warning("Selection cancelled")
                return current_selections

            # Update selections
            new_selections = {}
            for playlist in playlists:
                spotify_id = playlist.get('spotify_id') or playlist.get('id')
                new_selections[spotify_id] = spotify_id in result

            return new_selections

        except Exception as e:
            self.print_error(f"Selection failed: {e}")
            # Fallback to simple text-based selection
            return self._text_based_selection(playlists, current_selections)

    def _text_based_selection(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]:
        """Fallback text-based playlist selection.

        Args:
            playlists: List of playlist dicts
            current_selections: Current selections

        Returns:
            Updated selections dict
        """
        self.console.print("\n[yellow]Using simplified selection mode[/yellow]\n")

        new_selections = {}

        for i, playlist in enumerate(playlists, 1):
            spotify_id = playlist.get('spotify_id') or playlist.get('id')
            name = playlist['name']
            track_count = playlist.get('track_count', 0)
            currently_selected = current_selections.get(spotify_id, False)

            status = "[green]✓[/green]" if currently_selected else "[red]✗[/red]"
            self.console.print(f"{i}. {status} {name} ({track_count} tracks)")

        self.console.print("\n[dim]Enter playlist numbers to toggle (comma-separated), or 'done' to finish:[/dim]")
        self.console.print("[dim]Example: 1,3,5 to toggle playlists 1, 3, and 5[/dim]\n")

        # Start with current selections
        new_selections = current_selections.copy()

        while True:
            response = Prompt.ask("Toggle playlists", default="done")

            if response.lower() == 'done':
                break

            try:
                # Parse comma-separated numbers
                numbers = [int(n.strip()) for n in response.split(',')]

                for num in numbers:
                    if 1 <= num <= len(playlists):
                        playlist = playlists[num - 1]
                        spotify_id = playlist.get('spotify_id') or playlist.get('id')
                        # Toggle selection
                        new_selections[spotify_id] = not new_selections.get(spotify_id, False)
                    else:
                        self.print_warning(f"Invalid playlist number: {num}")

                # Show current state
                self.console.print("\n[bold]Current selections:[/bold]")
                for i, playlist in enumerate(playlists, 1):
                    spotify_id = playlist.get('spotify_id') or playlist.get('id')
                    if new_selections.get(spotify_id, False):
                        self.console.print(f"  [green]✓[/green] {playlist['name']}")
                self.console.print()

            except ValueError:
                self.print_error("Invalid input. Enter numbers separated by commas, or 'done'")

        return new_selections

    def show_playlist_list(self, playlists: List[Dict], synced_playlists: Dict[str, Dict]):
        """Show list of all playlists with sync status.

        Args:
            playlists: List of playlist selection dicts
            synced_playlists: Dict mapping spotify_id -> synced playlist info
        """
        if not playlists:
            self.print_warning("No playlists found. Run 'musicdiff select' to choose playlists to sync.")
            return

        self.console.print("\n[bold cyan]Your Spotify Playlists[/bold cyan]\n")

        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Status", width=8)
        table.add_column("Playlist Name", style="white")
        table.add_column("Tracks", justify="right", width=10)
        table.add_column("Last Synced", width=20)
        table.add_column("Deezer", width=10)

        for playlist in playlists:
            spotify_id = playlist['spotify_id']
            selected = playlist.get('selected', False)
            synced = synced_playlists.get(spotify_id)

            # Status column
            if selected:
                status = "[green]✓ Selected[/green]"
            else:
                status = "[dim]○ Not selected[/dim]"

            # Last synced
            if playlist.get('last_synced'):
                try:
                    last_sync = datetime.fromisoformat(playlist['last_synced'])
                    last_synced_str = last_sync.strftime("%Y-%m-%d %H:%M")
                except:
                    last_synced_str = "Unknown"
            else:
                last_synced_str = "[dim]Never[/dim]"

            # Deezer status
            if synced:
                deezer_status = "[green]✓ Synced[/green]"
            else:
                deezer_status = "[dim]—[/dim]"

            table.add_row(
                status,
                playlist['name'],
                str(playlist.get('track_count', 0)),
                last_synced_str,
                deezer_status
            )

        self.console.print(table)
        self.console.print()

        # Summary
        selected_count = sum(1 for p in playlists if p.get('selected', False))
        synced_count = len(synced_playlists)

        self.console.print(f"[bold]Summary:[/bold] {selected_count}/{len(playlists)} selected, {synced_count} synced to Deezer")
        self.console.print()

    def show_sync_preview(self, to_create: List[str], to_update: List[str], to_delete: List[str]):
        """Show preview of what will be synced.

        Args:
            to_create: List of playlist names to be created on Deezer
            to_update: List of playlist names to be updated on Deezer
            to_delete: List of playlist names to be deleted from Deezer
        """
        self.console.print("\n[bold]Sync Preview:[/bold]\n")

        if to_create:
            self.console.print(f"[green]Create on Deezer ({len(to_create)}):[/green]")
            for name in to_create:
                self.console.print(f"  + {name}")
            self.console.print()

        if to_update:
            self.console.print(f"[yellow]Update on Deezer ({len(to_update)}):[/yellow]")
            for name in to_update:
                self.console.print(f"  ~ {name}")
            self.console.print()

        if to_delete:
            self.console.print(f"[red]Delete from Deezer ({len(to_delete)}):[/red]")
            for name in to_delete:
                self.console.print(f"  - {name}")
            self.console.print()

        if not (to_create or to_update or to_delete):
            self.console.print("[dim]No changes to make - everything is in sync[/dim]\n")

    def create_progress(self, description: str) -> Progress:
        """Create and return a progress bar.

        Args:
            description: Progress description

        Returns:
            Progress context manager
        """
        return Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=self.console
        )

    def confirm(self, message: str, default: bool = False) -> bool:
        """Ask user for yes/no confirmation.

        Args:
            message: Confirmation message
            default: Default value if user just presses Enter

        Returns:
            True if user confirms, False otherwise
        """
        return Confirm.ask(message, default=default)

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

    def show_status(self, title: str, items: dict):
        """Show status information in a table.

        Args:
            title: Status title
            items: Dict of key-value pairs to display
        """
        self.console.print()
        self.console.print(f"[bold]{title}[/bold]")

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Key", style="cyan")
        table.add_column("Value")

        for key, value in items.items():
            table.add_row(key, str(value))

        self.console.print(table)
        self.console.print()

    def show_sync_summary(self, result):
        """Show summary after sync completes.

        Args:
            result: SyncResult object
        """
        self.console.print()
        self.console.rule("[bold cyan]Sync Summary[/bold cyan]")
        self.console.print()

        table = Table(show_header=False, box=None, padding=(0, 2))
        table.add_column("Metric", style="bold")
        table.add_column("Count")

        table.add_row("Playlists Created", f"[green]{result.playlists_created}[/green]")
        table.add_row("Playlists Updated", f"[yellow]{result.playlists_updated}[/yellow]")
        table.add_row("Playlists Deleted", f"[red]{result.playlists_deleted}[/red]")
        table.add_row("Total Synced", f"[cyan]{result.total_synced}[/cyan]")

        if result.failed_operations:
            table.add_row("Failed", f"[red]{len(result.failed_operations)}[/red]")

        table.add_row("Duration", f"{result.duration_seconds:.1f}s")

        self.console.print(table)
        self.console.print()
