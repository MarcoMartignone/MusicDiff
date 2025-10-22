"""
Terminal UI components.

See docs/UI_COMPONENTS.md for detailed documentation.
"""

from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn
from rich.tree import Tree
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from musicdiff.diff import Conflict, DiffResult, Change, ChangeType
from typing import List


class UI:
    """Terminal-based user interface."""

    def __init__(self):
        """Initialize UI."""
        self.console = Console()

    def show_conflict(self, conflict: Conflict):
        """Display a conflict in the terminal.

        Args:
            conflict: Conflict to display
        """
        self.console.print()
        self.console.rule(f"[red bold]⚡ Conflict: {conflict.entity_id}[/red bold]")
        self.console.print()

        # Create comparison table
        table = Table(show_header=True, header_style="bold")
        table.add_column("", style="bold", width=15)
        table.add_column("Spotify", style="cyan", width=40)
        table.add_column("Apple Music", style="magenta", width=40)

        # Show metadata
        if conflict.entity_type == 'playlist':
            spotify_data = conflict.spotify_change.data
            apple_data = conflict.apple_change.data

            table.add_row(
                "Name",
                spotify_data.get('name', ''),
                apple_data.get('name', '')
            )

            table.add_row(
                "Description",
                spotify_data.get('description', '')[:40],
                apple_data.get('description', '')[:40]
            )

            # Show track changes
            spotify_tracks = spotify_data.get('tracks', [])
            apple_tracks = apple_data.get('tracks', [])

            spotify_added = spotify_data.get('tracks_added', [])
            spotify_removed = spotify_data.get('tracks_removed', [])
            apple_added = apple_data.get('tracks_added', [])
            apple_removed = apple_data.get('tracks_removed', [])

            table.add_row(
                "Total Tracks",
                str(len(spotify_tracks)),
                str(len(apple_tracks))
            )

            if spotify_added:
                table.add_row(
                    "Added",
                    f"[green]+{len(spotify_added)} tracks[/green]",
                    ""
                )

            if spotify_removed:
                table.add_row(
                    "Removed",
                    f"[red]-{len(spotify_removed)} tracks[/red]",
                    ""
                )

            if apple_added:
                table.add_row(
                    "Added",
                    "",
                    f"[green]+{len(apple_added)} tracks[/green]"
                )

            if apple_removed:
                table.add_row(
                    "Removed",
                    "",
                    f"[red]-{len(apple_removed)} tracks[/red]"
                )

        self.console.print(table)
        self.console.print()

    def prompt_resolution(self, conflict: Conflict) -> str:
        """Prompt user to choose conflict resolution.

        Args:
            conflict: Conflict to resolve

        Returns:
            Resolution choice: 'spotify', 'apple', 'manual', 'skip'
        """
        choices = {
            's': 'spotify',
            'a': 'apple',
            'm': 'manual',
            'k': 'skip'
        }

        choice = Prompt.ask(
            "\nChoose resolution",
            choices=list(choices.keys()),
            default='k'
        )

        return choices[choice]

    def show_diff_summary(self, diff_result: DiffResult):
        """Show summary of diff results.

        Args:
            diff_result: Diff result to display
        """
        self.console.print()
        tree = Tree("📊 [bold]Sync Summary[/bold]")

        # Auto-merge changes
        if diff_result.auto_merge:
            auto_branch = tree.add(
                f"✓ [green]Auto-merge ({len(diff_result.auto_merge)} changes)[/green]"
            )

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
                    direction = f"{change.source_platform} → {change.target_platform}"
                    type_branch.add(f"[dim]{change.entity_id} ({direction})[/dim]")
                if len(changes) > 5:
                    type_branch.add(f"[dim italic]... and {len(changes) - 5} more[/dim italic]")

        # Conflicts
        if diff_result.conflicts:
            conflict_branch = tree.add(
                f"⚠ [red]Conflicts ({len(diff_result.conflicts)})[/red]"
            )
            for conflict in diff_result.conflicts:
                conflict_branch.add(f"[dim]{conflict.entity_type}: {conflict.entity_id}[/dim]")

        self.console.print(tree)
        self.console.print()

    def show_changes(self, changes: List[Change], title: str = "Changes"):
        """Show a list of changes.

        Args:
            changes: List of changes to display
            title: Title for the changes section
        """
        if not changes:
            return

        self.console.print()
        self.console.print(f"[bold]{title}[/bold]")

        for change in changes:
            icon = "✓" if change.change_type.value.endswith("added") or change.change_type.value.endswith("created") else "✗"
            color = "green" if icon == "✓" else "red"

            direction = f"{change.source_platform} → {change.target_platform}"
            self.console.print(
                f"  {icon} [{color}]{change.change_type.value}[/{color}] "
                f"[dim]{change.entity_id} ({direction})[/dim]"
            )

        self.console.print()

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
