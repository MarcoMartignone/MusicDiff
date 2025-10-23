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
import questionary
from questionary import Style


class UI:
    """Terminal-based user interface."""

    def __init__(self):
        """Initialize UI."""
        self.console = Console()

    def select_playlists(self, playlists: List[Dict], current_selections: Dict[str, bool]) -> Dict[str, bool]:
        """Interactive checkbox playlist selection using questionary.

        Args:
            playlists: List of playlist dicts with spotify_id, name, track_count
            current_selections: Dict mapping spotify_id -> selected (bool)

        Returns:
            Dict mapping spotify_id -> selected (bool)
        """
        if not playlists:
            self.print_warning("No Spotify playlists found.")
            return {}

        # Check if user already has selections and show them
        selected_count = sum(1 for selected in current_selections.values() if selected)

        if selected_count > 0:
            # Show current selections info
            self.console.print()
            self.console.print(f"[dim]Currently selected: {selected_count} playlist{'s' if selected_count != 1 else ''}[/dim]")

        # Display header
        self.console.print()
        self.console.print(Panel.fit(
            "[bold cyan]🎵 Select Playlists to Sync[/bold cyan]\n\n"
            "Use ↑↓ arrows to navigate, SPACE to select/deselect, ENTER to confirm",
            border_style="cyan"
        ))
        self.console.print()

        # Prepare choices for questionary
        choices = []
        default_selected = []
        valid_spotify_ids = set()

        for playlist in playlists:
            spotify_id = playlist.get('spotify_id') or playlist.get('id')
            name = playlist['name']
            track_count = playlist.get('track_count', 0)

            # Track valid spotify IDs
            valid_spotify_ids.add(spotify_id)

            # Create choice with name and track count
            choice_text = f"{name} ({track_count} tracks)"
            choice = questionary.Choice(title=choice_text, value=spotify_id)
            choices.append(choice)

            # Mark as default if currently selected
            if current_selections.get(spotify_id, False):
                default_selected.append(spotify_id)

        # Custom styling for the checkbox
        custom_style = Style([
            ('qmark', 'fg:#00ff00 bold'),        # Question mark - green
            ('question', 'bold'),                 # Question text
            ('answer', 'fg:#00ff00 bold'),       # Answer - green
            ('pointer', 'fg:#00ffff bold'),      # Pointer - cyan
            ('highlighted', 'fg:#00ffff bold'),  # Highlighted choice - cyan
            ('selected', 'fg:#00ff00'),          # Selected items - green
            ('separator', 'fg:#555555'),         # Separator
            ('instruction', 'fg:#888888'),       # Instructions
            ('text', ''),                        # Default text
            ('disabled', 'fg:#888888 italic')    # Disabled choices
        ])

        # Show checkbox selection
        try:
            checkbox_kwargs = {
                "choices": choices,
                "default": default_selected,  # Pre-select currently selected playlists
                "style": custom_style,
                "instruction": "(Use arrow keys to move, SPACE to select, ENTER to confirm)"
            }

            selected = questionary.checkbox(
                "Select playlists to sync:",
                **checkbox_kwargs
            ).ask()

            if selected is None:
                # User cancelled (Ctrl+C)
                self.console.print("\n[yellow]Selection cancelled[/yellow]\n")
                return current_selections

            # Build new selections dict
            new_selections = {}
            for playlist in playlists:
                spotify_id = playlist.get('spotify_id') or playlist.get('id')
                new_selections[spotify_id] = spotify_id in selected

            return new_selections

        except Exception as e:
            self.print_error(f"Selection failed: {e}")
            return current_selections

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

    def show_sync_preview_detailed(self, to_create: List[Tuple], to_update: List[Tuple], to_delete: List[Tuple]) -> bool:
        """Show detailed preview of sync actions and ask for confirmation.

        Args:
            to_create: List of (name, track_count) tuples for playlists to create
            to_update: List of (name, track_count, deezer_id) tuples for playlists to update
            to_delete: List of (name, deezer_id) tuples for playlists to delete

        Returns:
            True if user confirms, False otherwise
        """
        self.console.print()
        self.console.print(Panel.fit(
            "[bold cyan]🔄 Sync Preview[/bold cyan]\n\n"
            "Review what will happen when you sync",
            border_style="cyan"
        ))
        self.console.print()

        if to_create:
            self.console.print(f"[bold green]✨ Will Create on Deezer ({len(to_create)} playlists):[/bold green]")
            for name, track_count in to_create:
                self.console.print(f"  [green]+[/green] {name} [dim]({track_count} tracks)[/dim]")
            self.console.print()

        if to_update:
            self.console.print(f"[bold yellow]🔄 Will Update on Deezer ({len(to_update)} playlists):[/bold yellow]")
            self.console.print("[dim]  (Full overwrite - all tracks will be replaced with Spotify version)[/dim]")
            for name, track_count, deezer_id in to_update:
                self.console.print(f"  [yellow]~[/yellow] {name} [dim]({track_count} tracks)[/dim]")
            self.console.print()

        if to_delete:
            self.console.print(f"[bold red]🗑️  Will Delete from Deezer ({len(to_delete)} playlists):[/bold red]")
            self.console.print("[dim]  (These playlists are no longer selected)[/dim]")
            for name, deezer_id in to_delete:
                self.console.print(f"  [red]-[/red] {name}")
            self.console.print()

        if not (to_create or to_update or to_delete):
            self.console.print("[dim]No changes to make - everything is already in sync[/dim]\n")
            return False

        # Summary
        total_actions = len(to_create) + len(to_update) + len(to_delete)
        total_tracks = sum(count for _, count in to_create) + sum(count for _, count, _ in to_update)

        self.console.print(f"[bold]Summary:[/bold] {total_actions} playlists affected, ~{total_tracks} tracks to sync")
        self.console.print()

        # Ask for confirmation
        return self.confirm("Proceed with sync?", default=True)

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
