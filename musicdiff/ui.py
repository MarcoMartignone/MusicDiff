"""
Terminal UI components for MusicDiff.

Simple, focused UI for selecting Spotify playlists and showing sync status.
"""

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.columns import Columns
from rich.text import Text
from rich.tree import Tree
from typing import List, Dict, Tuple
from datetime import datetime


class UI:
    """Terminal-based user interface."""

    def __init__(self):
        """Initialize UI."""
        self.console = Console()

    def select_playlists(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]:
        """Modern, Claude Code-style playlist selection interface.

        Args:
            playlists: List of playlist dicts with spotify_id, name, track_count
            current_selections: Dict mapping spotify_id -> selected (bool)

        Returns:
            Dict mapping spotify_id -> selected (bool)
        """
        if not playlists:
            self.print_warning("No Spotify playlists found.")
            return {}

        # Display header
        self.console.print()
        self.console.print(Panel.fit(
            "[bold cyan]🎵 Select Playlists to Sync[/bold cyan]\n\n"
            "Choose which Spotify playlists you want to sync to Deezer",
            border_style="cyan"
        ))
        self.console.print()

        # Start with current selections
        new_selections = current_selections.copy()

        # Group playlists for better display
        selected_playlists = []
        unselected_playlists = []

        for playlist in playlists:
            spotify_id = playlist.get('spotify_id') or playlist.get('id')
            is_selected = current_selections.get(spotify_id, False)

            if is_selected:
                selected_playlists.append(playlist)
            else:
                unselected_playlists.append(playlist)

        # Display current selections in a clean format
        if selected_playlists:
            self.console.print("[bold green]✓ Currently Selected:[/bold green]")
            for playlist in selected_playlists[:10]:  # Show first 10
                name = playlist['name']
                track_count = playlist.get('track_count', 0)
                self.console.print(f"  [green]●[/green] {name} [dim]({track_count} tracks)[/dim]")

            if len(selected_playlists) > 10:
                remaining = len(selected_playlists) - 10
                self.console.print(f"  [dim]... and {remaining} more[/dim]")
            self.console.print()

        if unselected_playlists:
            self.console.print(f"[bold dim]○ Not Selected: {len(unselected_playlists)} playlists[/bold dim]")
            self.console.print()

        # Show total
        self.console.print(f"[bold]Total:[/bold] {len(selected_playlists)}/{len(playlists)} playlists selected")
        self.console.print()

        # Ask what to do
        self.console.print("[bold]What would you like to do?[/bold]")
        self.console.print()
        self.console.print("  [cyan]1.[/cyan] Select all playlists")
        self.console.print("  [cyan]2.[/cyan] Deselect all playlists")
        self.console.print("  [cyan]3.[/cyan] Select specific playlists (enter numbers)")
        self.console.print("  [cyan]4.[/cyan] Keep current selection and continue")
        self.console.print()

        choice = Prompt.ask("Choose an option", choices=["1", "2", "3", "4"], default="4")

        if choice == "1":
            # Select all
            for playlist in playlists:
                spotify_id = playlist.get('spotify_id') or playlist.get('id')
                new_selections[spotify_id] = True
            self.console.print("\n[green]✓ All playlists selected![/green]\n")

        elif choice == "2":
            # Deselect all
            for playlist in playlists:
                spotify_id = playlist.get('spotify_id') or playlist.get('id')
                new_selections[spotify_id] = False
            self.console.print("\n[yellow]○ All playlists deselected[/yellow]\n")

        elif choice == "3":
            # Custom selection
            return self._interactive_selection(playlists, new_selections)

        return new_selections

    def _interactive_selection(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]:
        """Interactive number-based playlist selection.

        Args:
            playlists: List of playlist dicts
            current_selections: Current selections

        Returns:
            Updated selections dict
        """
        self.console.print()
        self.console.print("[bold cyan]📋 All Playlists:[/bold cyan]\n")

        # Show all playlists with numbers
        new_selections = current_selections.copy()

        for i, playlist in enumerate(playlists, 1):
            spotify_id = playlist.get('spotify_id') or playlist.get('id')
            name = playlist['name']
            track_count = playlist.get('track_count', 0)
            currently_selected = new_selections.get(spotify_id, False)

            if currently_selected:
                status = "[green]✓[/green]"
                style = "green"
            else:
                status = "[dim]○[/dim]"
                style = "dim"

            self.console.print(f"  [{style}]{i:3d}. {status} {name} ({track_count} tracks)[/{style}]")

        self.console.print()
        self.console.print("[bold]How to select:[/bold]")
        self.console.print("  • Enter numbers separated by commas: [cyan]1,5,10[/cyan]")
        self.console.print("  • Enter a range: [cyan]1-20[/cyan]")
        self.console.print("  • Combine both: [cyan]1-10,15,20-25[/cyan]")
        self.console.print("  • Type [cyan]'done'[/cyan] when finished")
        self.console.print()

        while True:
            response = Prompt.ask("Select playlists", default="done")

            if response.lower() == 'done':
                break

            try:
                # Parse input (supports ranges like 1-10 and individual numbers)
                numbers = set()
                parts = response.split(',')

                for part in parts:
                    part = part.strip()
                    if '-' in part:
                        # Range
                        start, end = part.split('-')
                        start, end = int(start.strip()), int(end.strip())
                        numbers.update(range(start, end + 1))
                    else:
                        # Individual number
                        numbers.add(int(part))

                # Toggle selections
                for num in numbers:
                    if 1 <= num <= len(playlists):
                        playlist = playlists[num - 1]
                        spotify_id = playlist.get('spotify_id') or playlist.get('id')
                        # Toggle selection
                        new_selections[spotify_id] = not new_selections.get(spotify_id, False)
                    else:
                        self.print_warning(f"Invalid playlist number: {num}")

                # Show updated state
                selected = [p for p in playlists if new_selections.get(p.get('spotify_id') or p.get('id'), False)]
                self.console.print(f"\n[bold]Selected: {len(selected)}/{len(playlists)} playlists[/bold]")

                if selected:
                    for playlist in selected[:5]:
                        self.console.print(f"  [green]●[/green] {playlist['name']}")
                    if len(selected) > 5:
                        self.console.print(f"  [dim]... and {len(selected) - 5} more[/dim]")
                self.console.print()

            except ValueError:
                self.print_error("Invalid input. Use format: 1,2,3 or 1-10 or combination")

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

    def show_deezer_diff(self, selected_spotify: List[Dict], deezer_playlists: List[Dict], synced_db: Dict[str, Dict]):
        """Show diff between selected Spotify playlists and what's on Deezer.

        Args:
            selected_spotify: List of selected Spotify playlist dicts
            deezer_playlists: List of Deezer playlist dicts
            synced_db: Database records of what we've synced before (spotify_id -> deezer info)
        """
        self.console.print()
        self.console.print(Panel.fit(
            "[bold magenta]📊 Sync Preview: Spotify → Deezer[/bold magenta]\n\n"
            "Here's what will happen when you sync",
            border_style="magenta"
        ))
        self.console.print()

        # Build lookup of Deezer playlists by name (for rough matching)
        deezer_by_name = {p['title'].lower(): p for p in deezer_playlists}

        to_create = []
        to_update = []
        already_synced = []

        for spotify_pl in selected_spotify:
            spotify_id = spotify_pl.get('spotify_id') or spotify_pl.get('id')
            name = spotify_pl['name']
            track_count = spotify_pl.get('track_count', 0)

            # Check if we've synced this before
            synced_record = synced_db.get(spotify_id)

            if synced_record:
                # We've synced this before
                deezer_id = synced_record.get('deezer_id')
                # Check if it still exists on Deezer
                deezer_exists = any(p.get('id') == int(deezer_id) for p in deezer_playlists) if deezer_id else False

                if deezer_exists:
                    already_synced.append((name, track_count, deezer_id))
                else:
                    # Was synced before but deleted from Deezer - will recreate
                    to_create.append((name, track_count))
            else:
                # Never synced before
                # Check if a playlist with same name exists on Deezer (might be manual)
                if name.lower() in deezer_by_name:
                    to_update.append((name, track_count))
                else:
                    to_create.append((name, track_count))

        # Display results
        if to_create:
            self.console.print(f"[bold green]✨ Will Create ({len(to_create)} playlists):[/bold green]")
            for name, count in to_create[:10]:
                self.console.print(f"  [green]+[/green] {name} [dim]({count} tracks)[/dim]")
            if len(to_create) > 10:
                self.console.print(f"  [dim]... and {len(to_create) - 10} more[/dim]")
            self.console.print()

        if to_update:
            self.console.print(f"[bold yellow]🔄 Will Update ({len(to_update)} playlists):[/bold yellow]")
            self.console.print("[dim]  (Playlists with same name found on Deezer)[/dim]")
            for name, count in to_update[:10]:
                self.console.print(f"  [yellow]~[/yellow] {name} [dim]({count} tracks)[/dim]")
            if len(to_update) > 10:
                self.console.print(f"  [dim]... and {len(to_update) - 10} more[/dim]")
            self.console.print()

        if already_synced:
            self.console.print(f"[bold cyan]✓ Already Synced ({len(already_synced)} playlists):[/bold cyan]")
            self.console.print("[dim]  (Will check for changes and update if needed)[/dim]")
            for name, count, deezer_id in already_synced[:5]:
                self.console.print(f"  [cyan]●[/cyan] {name} [dim]({count} tracks)[/dim]")
            if len(already_synced) > 5:
                self.console.print(f"  [dim]... and {len(already_synced) - 5} more[/dim]")
            self.console.print()

        if not (to_create or to_update or already_synced):
            self.console.print("[dim]No playlists selected to sync[/dim]\n")
            return

        # Summary
        total = len(to_create) + len(to_update) + len(already_synced)
        self.console.print(f"[bold]Total:[/bold] {total} playlists will be synced to Deezer")
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
