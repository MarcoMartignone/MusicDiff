"""
Command-line interface for MusicDiff.

See docs/CLI.md for detailed documentation.
"""

import click
from pathlib import Path
from rich.console import Console

console = Console()


@click.group()
@click.version_option(version="0.1.0")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose):
    """MusicDiff - Git-like sync for your music libraries.

    Bidirectionally sync playlists, liked songs, and albums between
    Spotify and Apple Music with interactive conflict resolution.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose


@cli.command()
def init():
    """Initialize MusicDiff and authenticate with music platforms."""
    console.print("[bold cyan]Initializing MusicDiff...[/bold cyan]")

    # TODO: Implement initialization
    # 1. Create ~/.musicdiff directory
    # 2. Initialize database
    # 3. Authenticate with Spotify
    # 4. Authenticate with Apple Music
    # 5. Fetch initial library state

    console.print("[green]Initialization complete![/green]")
    console.print("\nRun 'musicdiff status' to see your library state.")


@cli.command()
def status():
    """Show current sync status and pending changes."""
    console.print("[bold]MusicDiff Status[/bold]\n")

    # TODO: Implement status check
    # 1. Check last sync timestamp
    # 2. Show detected changes
    # 3. List unresolved conflicts

    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
@click.option('--spotify-only', is_flag=True, help='Fetch from Spotify only')
@click.option('--apple-only', is_flag=True, help='Fetch from Apple Music only')
def fetch(spotify_only, apple_only):
    """Fetch latest library state from both platforms."""
    console.print("[bold cyan]Fetching library data...[/bold cyan]")

    # TODO: Implement fetch
    # 1. Fetch from Spotify (unless --apple-only)
    # 2. Fetch from Apple Music (unless --spotify-only)
    # 3. Show summary

    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
@click.argument('entity_type', required=False,
                type=click.Choice(['playlists', 'liked', 'albums']))
def diff(entity_type):
    """Show detailed diff between platforms.

    \b
    Examples:
        musicdiff diff              # Show all diffs
        musicdiff diff playlists    # Show only playlist diffs
        musicdiff diff liked        # Show only liked songs diffs
    """
    console.print("[bold]Computing diff...[/bold]\n")

    # TODO: Implement diff
    # 1. Load local state
    # 2. Fetch current state from platforms
    # 3. Compute 3-way diff
    # 4. Display results

    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
@click.option('--auto', is_flag=True, help='Automatically apply non-conflicting changes')
@click.option('--dry-run', is_flag=True, help='Show changes without applying')
@click.option('--conflicts-only', is_flag=True, help='Only resolve conflicts')
def sync(auto, dry_run, conflicts_only):
    """Synchronize music libraries between platforms.

    \b
    Modes:
        Interactive (default): Review each change before applying
        Auto (--auto):         Apply non-conflicting changes automatically
        Dry-run (--dry-run):   Show what would be synced
    """
    console.print("[bold cyan]Starting sync...[/bold cyan]\n")

    if dry_run:
        console.print("[dim]DRY RUN - No changes will be applied[/dim]\n")

    # TODO: Implement sync
    # 1. Fetch current state
    # 2. Compute diff
    # 3. Apply changes (based on mode)
    # 4. Update local state
    # 5. Log sync

    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
@click.option('-n', '--limit', default=10, help='Number of sync logs to show')
@click.option('--verbose', is_flag=True, help='Show detailed change list')
def log(limit, verbose):
    """Show sync history."""
    console.print("[bold]Sync History[/bold]\n")

    # TODO: Implement log
    # 1. Load sync history from database
    # 2. Display formatted log entries

    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
def resolve():
    """Resume conflict resolution for pending conflicts."""
    console.print("[bold]Resolving conflicts...[/bold]\n")

    # TODO: Implement resolve
    # 1. Load unresolved conflicts from database
    # 2. Open interactive UI for each conflict
    # 3. Apply resolutions

    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
@click.option('--interval', default=86400, type=int,
              help='Sync interval in seconds (default: 86400 = 24 hours)')
@click.option('--foreground', is_flag=True, help='Run in foreground (for debugging)')
@click.option('--stop', is_flag=True, help='Stop running daemon')
def daemon(interval, foreground, stop):
    """Run MusicDiff in daemon mode for scheduled syncs.

    \b
    Examples:
        musicdiff daemon                    # Start daemon (24h interval)
        musicdiff daemon --interval 21600   # Start with 6h interval
        musicdiff daemon --stop             # Stop daemon
    """
    if stop:
        console.print("[bold]Stopping daemon...[/bold]")
        # TODO: Stop daemon
        console.print("[yellow]Not yet implemented[/yellow]")
        return

    console.print(f"[bold cyan]Starting daemon (interval: {interval}s)[/bold cyan]")

    if foreground:
        console.print("[dim]Running in foreground...[/dim]")

    # TODO: Implement daemon
    # 1. Check if already running
    # 2. Start daemon process
    # 3. Run sync loop

    console.print("[yellow]Not yet implemented[/yellow]")


@cli.command()
@click.argument('key', required=False)
@click.argument('value', required=False)
def config(key, value):
    """View or edit configuration.

    \b
    Examples:
        musicdiff config                                    # View all config
        musicdiff config sync.auto_accept_non_conflicts     # Get value
        musicdiff config sync.schedule_interval 43200       # Set value
    """
    config_file = Path.home() / '.musicdiff' / 'config.yaml'

    if not key:
        # Show all config
        if config_file.exists():
            console.print(f"[bold]Configuration ({config_file}):[/bold]\n")
            console.print(config_file.read_text())
        else:
            console.print("[yellow]No configuration file found. Run 'musicdiff init' first.[/yellow]")
        return

    # TODO: Implement config get/set
    console.print("[yellow]Not yet implemented[/yellow]")


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()
