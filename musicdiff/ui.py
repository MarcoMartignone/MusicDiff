"""
Terminal UI components.

See docs/UI_COMPONENTS.md for detailed documentation.
"""

from rich.console import Console
from rich.table import Table
from rich.progress import Progress
from musicdiff.diff import Conflict, DiffResult


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
        # TODO: Implement conflict display
        # Show side-by-side diff with rich
        self.console.print(f"[red]Conflict: {conflict.entity_id}[/red]")

    def prompt_resolution(self, conflict: Conflict) -> str:
        """Prompt user to choose conflict resolution.

        Args:
            conflict: Conflict to resolve

        Returns:
            Resolution choice: 'spotify', 'apple', 'manual', 'skip'
        """
        # TODO: Implement interactive prompt
        raise NotImplementedError("Conflict resolution prompt not yet implemented")

    def show_diff_summary(self, diff_result: DiffResult):
        """Show summary of diff results.

        Args:
            diff_result: Diff result to display
        """
        # TODO: Implement diff summary display
        self.console.print(diff_result.summary())

    def show_progress(self, description: str, total: int):
        """Create and return a progress bar context.

        Args:
            description: Progress description
            total: Total number of items

        Returns:
            Progress context manager
        """
        # TODO: Implement progress bar
        return Progress()

    def confirm(self, message: str) -> bool:
        """Ask user for yes/no confirmation.

        Args:
            message: Confirmation message

        Returns:
            True if user confirms, False otherwise
        """
        # TODO: Implement confirmation prompt
        response = input(f"{message} (y/n): ").lower()
        return response in ['y', 'yes']
