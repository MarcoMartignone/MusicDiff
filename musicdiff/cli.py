"""
Command-line interface for MusicDiff.

See docs/CLI.md for detailed documentation.
"""

import click
import os
import sys
import time
import webbrowser
import shutil
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

# Import all modules
from musicdiff.database import Database
from musicdiff.spotify import SpotifyClient
from musicdiff.deezer import DeezerClient
from musicdiff.sync import SyncEngine, SyncMode
from musicdiff.scheduler import SyncDaemon
from musicdiff.ui import UI

console = Console()


def get_config_dir() -> Path:
    """Get MusicDiff configuration directory."""
    # Use project directory in Documents instead of home
    config_dir = Path.home() / 'Documents' / 'MusicDiff' / '.musicdiff'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def get_database() -> Database:
    """Get initialized database instance."""
    db_path = get_config_dir() / 'musicdiff.db'
    db = Database(str(db_path))
    return db


def get_spotify_client() -> SpotifyClient:
    """Get authenticated Spotify client."""
    # Get credentials from environment or config
    client_id = os.environ.get('SPOTIFY_CLIENT_ID')
    client_secret = os.environ.get('SPOTIFY_CLIENT_SECRET')
    redirect_uri = os.environ.get('SPOTIFY_REDIRECT_URI', 'http://localhost:8888/callback')

    if not client_id or not client_secret:
        console.print("[red]Error: Spotify credentials not found.[/red]")
        console.print("Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET environment variables")
        console.print("Or run 'musicdiff init' to configure")
        sys.exit(1)

    client = SpotifyClient(client_id, client_secret, redirect_uri)

    # Authenticate
    if not client.authenticate():
        console.print("[red]Error: Spotify authentication failed[/red]")
        sys.exit(1)

    return client


def get_deezer_client() -> DeezerClient:
    """Get authenticated Deezer client."""
    # Get credentials from environment
    arl_token = os.environ.get('DEEZER_ARL')

    if not arl_token:
        console.print("[red]Error: Deezer credentials not found.[/red]")
        console.print("Set DEEZER_ARL environment variable")
        console.print("Or run 'musicdiff init' to configure")
        sys.exit(1)

    client = DeezerClient(arl_token=arl_token)

    # Authenticate
    if not client.authenticate():
        console.print("[red]Error: Deezer authentication failed[/red]")
        sys.exit(1)

    return client


def get_sync_engine() -> SyncEngine:
    """Get initialized sync engine."""
    db = get_database()
    spotify = get_spotify_client()
    deezer = get_deezer_client()
    ui = UI()

    return SyncEngine(spotify, deezer, db, ui)


@click.group()
@click.version_option(version="0.1.0")
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose output')
@click.pass_context
def cli(ctx, verbose):
    """MusicDiff - Transfer your Spotify playlists to Deezer.

    Simple one-way sync: Select your Spotify playlists and MusicDiff
    will create/update them on Deezer to match exactly.
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose


@cli.command()
def setup():
    """Interactive setup wizard - create API credentials and configure MusicDiff.

    This wizard guides you through:
    - Creating Spotify API credentials (free, 5 minutes)
    - Optionally setting up Deezer (free with Deezer account)
    - Testing your credentials
    - Saving everything automatically
    """
    def clear_screen():
        console.clear()

    # Welcome
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🎵 MusicDiff Setup Wizard[/bold cyan]\n\n"
        "This wizard will help you set up MusicDiff to sync your\n"
        "music libraries between Spotify and Deezer.\n\n"
        "[dim]Press Enter to continue...[/dim]",
        border_style="cyan"
    ))
    console.print()
    input()

    # Choose platforms
    clear_screen()
    console.print()
    console.print("[bold]Which music platforms do you use?[/bold]")
    console.print()
    console.print("1. [green]Spotify only[/green] (easiest, free)")
    console.print("2. [cyan]Spotify + Deezer[/cyan] (free with Deezer account)")
    console.print()

    choice = Prompt.ask("Choose option", choices=["1", "2"], default="1")
    setup_deezer = choice == "2"

    # Spotify Setup - Step 1
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold green]📗 Spotify Setup - Step 1 of 3[/bold green]\n\n"
        "We need to create a Spotify app to get API credentials.\n"
        "Don't worry - this is free and takes 2 minutes!",
        border_style="green"
    ))
    console.print()
    console.print("[bold]Step 1:[/bold] Open Spotify Developer Dashboard")
    console.print()

    if Confirm.ask("Open browser automatically?", default=True):
        console.print("Opening https://developer.spotify.com/dashboard in your browser...")
        webbrowser.open("https://developer.spotify.com/dashboard")
        time.sleep(2)
    else:
        console.print("Please open: [cyan]https://developer.spotify.com/dashboard[/cyan]")

    console.print()
    console.print("[dim]Press Enter when you're ready to continue...[/dim]")
    input()

    # Spotify Setup - Step 2
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold green]📗 Spotify Setup - Step 2 of 3[/bold green]\n\n"
        "Create a new Spotify app:",
        border_style="green"
    ))
    console.print()
    console.print("1. Click the [cyan bold]'Create app'[/cyan bold] button")
    console.print("2. Fill in the form:")
    console.print("   • [bold]App name:[/bold] MusicDiff")
    console.print("   • [bold]App description:[/bold] Personal music library sync")
    console.print("   • [bold]Redirect URI:[/bold] https://localhost:8888/callback")
    console.print("   • Check the Terms of Service box")
    console.print("3. Click [cyan bold]'Save'[/cyan bold]")
    console.print()
    console.print("[dim]Press Enter when you've created the app...[/dim]")
    input()

    # Spotify Setup - Step 3
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold green]📗 Spotify Setup - Step 3 of 3[/bold green]\n\n"
        "Now let's get your credentials:",
        border_style="green"
    ))
    console.print()
    console.print("1. Click on your new [cyan bold]MusicDiff[/cyan bold] app")
    console.print("2. Click [cyan bold]'Settings'[/cyan bold] button")
    console.print("3. You'll see:")
    console.print("   • [bold]Client ID[/bold] - copy this")
    console.print("   • [bold]Client Secret[/bold] - click 'View client secret' and copy")
    console.print()

    spotify_client_id = Prompt.ask("[bold]Enter your Spotify Client ID[/bold]")
    spotify_client_secret = Prompt.ask("[bold]Enter your Spotify Client Secret[/bold]", password=True)

    console.print()
    use_https = Confirm.ask(
        "Did you use [cyan]https://[/cyan]localhost:8888/callback (instead of http)?",
        default=True
    )
    spotify_redirect_uri = "https://localhost:8888/callback" if use_https else "http://localhost:8888/callback"

    # Test Spotify credentials
    console.print()
    console.print("[bold]Testing Spotify credentials...[/bold]")

    try:
        os.environ['SPOTIFY_CLIENT_ID'] = spotify_client_id
        os.environ['SPOTIFY_CLIENT_SECRET'] = spotify_client_secret
        os.environ['SPOTIFY_REDIRECT_URI'] = spotify_redirect_uri

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Authenticating with Spotify..."),
            console=console
        ) as progress:
            progress.add_task("auth", total=None)
            client = SpotifyClient(spotify_client_id, spotify_client_secret, spotify_redirect_uri)
            success = client.authenticate()

        if success:
            user = client.sp.current_user()
            console.print(f"[green]✓ Successfully authenticated as {user['display_name']}![/green]")
        else:
            console.print("[red]✗ Authentication failed[/red]")
            if not Confirm.ask("Continue anyway?", default=False):
                console.print("[yellow]Setup cancelled.[/yellow]")
                return
    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        if not Confirm.ask("Continue anyway?", default=False):
            console.print("[yellow]Setup cancelled.[/yellow]")
            return

    # Deezer Setup
    deezer_arl = None

    if setup_deezer:
        clear_screen()
        console.print()
        console.print(Panel.fit(
            "[bold magenta]🎵 Deezer Setup[/bold magenta]\n\n"
            "[yellow]Requirements:[/yellow]\n"
            "• Free Deezer account\n"
            "• 2-3 minutes for setup\n\n"
            "You'll need to extract your ARL token from Deezer.",
            border_style="magenta"
        ))
        console.print()

        if Confirm.ask("Do you have a Deezer account?", default=True):
            # Step 1: Get ARL Token
            clear_screen()
            console.print()
            console.print(Panel.fit(
                "[bold magenta]🎵 Deezer - Get Your ARL Token[/bold magenta]\n\n"
                "The ARL token is your authentication credential",
                border_style="magenta"
            ))
            console.print()

            console.print("[bold]Method 1: Using Browser DevTools (Recommended)[/bold]")
            console.print()
            console.print("1. Open https://www.deezer.com in your browser")
            console.print("2. Log in to your Deezer account")
            console.print("3. Open DevTools (F12 or Cmd+Option+I)")
            console.print("4. Go to the [cyan]Application[/cyan] (Chrome) or [cyan]Storage[/cyan] (Firefox) tab")
            console.print("5. Click [cyan]Cookies[/cyan] → [cyan]https://www.deezer.com[/cyan]")
            console.print("6. Find the cookie named [cyan bold]'arl'[/cyan bold]")
            console.print("7. Copy its value (long string of letters and numbers)")
            console.print()

            if Confirm.ask("Open Deezer in browser?", default=True):
                console.print("Opening https://www.deezer.com in your browser...")
                webbrowser.open("https://www.deezer.com")
                time.sleep(2)

            console.print()
            console.print("[bold]Method 2: Using Browser Extension[/bold]")
            console.print()
            console.print("• Install 'EditThisCookie' (Chrome) or 'Cookie-Editor' (Firefox)")
            console.print("• Go to https://www.deezer.com and log in")
            console.print("• Click the extension icon and find the 'arl' cookie")
            console.print()

            console.print("[dim]Press Enter when you're ready to enter your ARL token...[/dim]")
            input()

            # Get ARL token
            clear_screen()
            console.print()
            console.print(Panel.fit(
                "[bold magenta]🎵 Deezer - Enter ARL Token[/bold magenta]",
                border_style="magenta"
            ))
            console.print()

            deezer_arl = Prompt.ask("[bold]Enter your Deezer ARL token[/bold]", password=True)

            # Test Deezer credentials
            console.print()
            console.print("[bold]Testing Deezer credentials...[/bold]")

            try:
                os.environ['DEEZER_ARL'] = deezer_arl

                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold blue]Authenticating with Deezer..."),
                    console=console
                ) as progress:
                    progress.add_task("auth", total=None)
                    client = DeezerClient(arl_token=deezer_arl)
                    success = client.authenticate()

                if success:
                    console.print(f"[green]✓ Successfully authenticated with Deezer (User ID: {client.user_id})![/green]")
                else:
                    console.print("[red]✗ Authentication failed[/red]")
                    console.print("[yellow]Your ARL token may be invalid or expired.[/yellow]")
                    if not Confirm.ask("Continue anyway?", default=False):
                        console.print("[yellow]Setup cancelled.[/yellow]")
                        return
            except Exception as e:
                console.print(f"[red]✗ Error: {e}[/red]")
                if not Confirm.ask("Continue anyway?", default=False):
                    console.print("[yellow]Setup cancelled.[/yellow]")
                    return

    # Save credentials
    env_file = get_config_dir() / '.env'
    console.print()
    console.print("[bold]Saving credentials...[/bold]")

    with open(env_file, 'w') as f:
        f.write("# MusicDiff Environment Variables\n")
        f.write(f"# Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n")
        f.write("# Spotify Credentials\n")
        f.write(f"export SPOTIFY_CLIENT_ID=\"{spotify_client_id}\"\n")
        f.write(f"export SPOTIFY_CLIENT_SECRET=\"{spotify_client_secret}\"\n")
        f.write(f"export SPOTIFY_REDIRECT_URI=\"{spotify_redirect_uri}\"\n")
        f.write("\n")

        if deezer_arl:
            f.write("# Deezer Credentials\n")
            f.write(f"export DEEZER_ARL=\"{deezer_arl}\"\n")
        else:
            f.write("# Deezer - Not configured\n")
            f.write("# export DEEZER_ARL=\"\"  # Add your ARL token here\n")

    console.print(f"[green]✓ Credentials saved to {env_file}[/green]")

    # Completion screen
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold green]🎉 Setup Complete![/bold green]\n\n"
        "MusicDiff is ready to sync your music!",
        border_style="green"
    ))
    console.print()
    console.print("[bold]What's been set up:[/bold]")
    console.print("  [green]✓[/green] Spotify API credentials")
    if deezer_arl:
        console.print("  [green]✓[/green] Deezer API credentials")
    console.print(f"  [green]✓[/green] Configuration saved to {env_file}")
    console.print()
    console.print("[bold]Next steps:[/bold]")
    console.print()
    console.print("1. Load your credentials:")
    console.print(f"   [cyan]source {env_file}[/cyan]")
    console.print()
    console.print("2. Initialize MusicDiff:")
    console.print("   [cyan]musicdiff init[/cyan]")
    console.print()
    console.print("3. Start syncing!")
    console.print("   [cyan]musicdiff sync[/cyan]")
    console.print()


@cli.command()
def init():
    """Initialize MusicDiff and authenticate with music platforms."""
    console.print("[bold cyan]Initializing MusicDiff...[/bold cyan]\n")

    # Create config directory
    config_dir = get_config_dir()
    console.print(f"✓ Created config directory: {config_dir}")

    # Initialize database
    db = get_database()
    db.init_schema()
    console.print("✓ Initialized database")

    # Check credentials
    console.print("\n[bold]Checking credentials...[/bold]")

    # Spotify
    if os.environ.get('SPOTIFY_CLIENT_ID') and os.environ.get('SPOTIFY_CLIENT_SECRET'):
        console.print("✓ Spotify credentials found")
        try:
            spotify = get_spotify_client()
            console.print(f"✓ Authenticated with Spotify as {spotify.sp.current_user()['display_name']}")
        except Exception as e:
            console.print(f"[yellow]⚠ Spotify authentication failed: {e}[/yellow]")
    else:
        console.print("[yellow]⚠ Spotify credentials not set[/yellow]")
        console.print("  Set SPOTIFY_CLIENT_ID and SPOTIFY_CLIENT_SECRET")

    # Deezer
    if os.environ.get('DEEZER_ARL'):
        console.print("✓ Deezer credentials found")
        try:
            deezer = get_deezer_client()
            console.print(f"✓ Authenticated with Deezer (User ID: {deezer.user_id})")
        except Exception as e:
            console.print(f"[yellow]⚠ Deezer authentication failed: {e}[/yellow]")
    else:
        console.print("[yellow]⚠ Deezer credentials not set[/yellow]")
        console.print("  Set DEEZER_ARL environment variable")

    console.print("\n[green bold]✓ Initialization complete![/green bold]")
    console.print("\nNext steps:")
    console.print("  1. Set all required environment variables")
    console.print("  2. Run 'musicdiff status' to check your setup")
    console.print("  3. Run 'musicdiff sync' to start syncing")


@cli.command()
def status():
    """Show current sync status and playlist selection summary."""
    console.print("[bold cyan]MusicDiff Status[/bold cyan]\n")

    # Check if initialized
    db_path = get_config_dir() / 'musicdiff.db'
    if not db_path.exists():
        console.print("[yellow]MusicDiff not initialized. Run 'musicdiff init' first.[/yellow]")
        return

    db = Database(str(db_path))

    # Get playlist selections
    selections = db.get_all_playlist_selections()
    synced = db.get_all_synced_playlists()

    if selections:
        selected_count = sum(1 for p in selections if p.get('selected', False))
        console.print(f"[bold]Playlist Selections:[/bold]")
        console.print(f"  Total Spotify Playlists: {len(selections)}")
        console.print(f"  Selected for Sync: [cyan]{selected_count}[/cyan]")
        console.print(f"  Currently on Deezer: [green]{len(synced)}[/green]")
    else:
        console.print("[yellow]No playlists selected yet.[/yellow]")
        console.print("Run [cyan]musicdiff select[/cyan] to choose playlists to sync\n")
        return

    # Get last sync info
    console.print()
    logs = db.get_sync_history(limit=1)
    if logs:
        last_sync = logs[0]
        console.print(f"[bold]Last Sync:[/bold] {last_sync['timestamp']}")
        console.print(f"  Status: {last_sync['status']}")
        console.print(f"  Playlists Synced: {last_sync.get('playlists_synced', 0)}")
        console.print(f"  Created/Updated/Deleted: {last_sync.get('playlists_created', 0)}/" +
                     f"{last_sync.get('playlists_updated', 0)}/{last_sync.get('playlists_deleted', 0)}")
    else:
        console.print("[bold]Last Sync:[/bold] Never")
        console.print("Run [cyan]musicdiff sync[/cyan] to start syncing\n")

    # Check daemon status
    console.print()
    try:
        sync_engine = get_sync_engine()
        daemon = SyncDaemon(sync_engine)
        daemon_status = daemon.status()

        console.print(f"[bold]Daemon:[/bold] {'[green]Running[/green]' if daemon_status['running'] else '[dim]Not running[/dim]'}")
        if daemon_status['running']:
            console.print(f"  PID: {daemon_status['pid']}")
            console.print(f"  Interval: {daemon_status['interval']}s")
    except Exception:
        pass


@cli.command()
@click.option('--spotify-only', is_flag=True, help='Fetch from Spotify only')
@click.option('--deezer-only', is_flag=True, help='Fetch from Deezer only')
def fetch(spotify_only, deezer_only):
    """Fetch latest library state from both platforms."""
    console.print("[bold cyan]Fetching library data...[/bold cyan]\n")

    if not spotify_only:
        console.print("Fetching from Spotify...")
        spotify = get_spotify_client()
        playlists = spotify.fetch_playlists()
        liked = spotify.fetch_liked_songs()
        albums = spotify.fetch_saved_albums()
        console.print(f"  ✓ {len(playlists)} playlists, {len(liked)} liked songs, {len(albums)} albums")

    if not deezer_only:
        console.print("Fetching from Deezer...")
        deezer = get_deezer_client()
        playlists = deezer.fetch_library_playlists()
        liked = deezer.fetch_library_songs()
        albums = deezer.fetch_library_albums()
        console.print(f"  ✓ {len(playlists)} playlists, {len(liked)} library songs, {len(albums)} albums")

    console.print("\n[green]✓ Fetch complete![/green]")


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

    # Get sync engine and run dry-run sync to see diff
    sync_engine = get_sync_engine()
    result = sync_engine.sync(mode=SyncMode.DRY_RUN)

    console.print(f"\n{result.summary()}")


@cli.command()
def select():
    """Select which Spotify playlists to sync to Deezer.

    Opens an interactive checkbox interface to choose playlists.
    Selected playlists will be synced when you run 'musicdiff sync'.
    """
    console.print("[bold cyan]Fetching your Spotify playlists...[/bold cyan]\n")

    db = get_database()
    spotify = get_spotify_client()
    ui = UI()

    # Fetch all Spotify playlists
    try:
        sp_playlists = spotify.fetch_playlists()
    except Exception as e:
        console.print(f"[red]Error fetching Spotify playlists: {e}[/red]")
        sys.exit(1)

    if not sp_playlists:
        console.print("[yellow]No Spotify playlists found[/yellow]")
        return

    # Convert to simple dicts
    playlist_dicts = []
    for p in sp_playlists:
        playlist_dicts.append({
            'spotify_id': p.spotify_id,
            'name': p.name,
            'track_count': len(p.tracks)
        })

    # Get current selections from database
    current_selections_list = db.get_all_playlist_selections()
    current_selections = {p['spotify_id']: p['selected'] for p in current_selections_list}

    # Show selection UI
    new_selections = ui.select_playlists(playlist_dicts, current_selections)

    # Save selections to database
    for playlist in playlist_dicts:
        spotify_id = playlist['spotify_id']
        selected = new_selections.get(spotify_id, False)

        db.upsert_playlist_selection(
            spotify_id=spotify_id,
            name=playlist['name'],
            track_count=playlist['track_count'],
            selected=selected
        )

    # Show summary
    selected_count = sum(1 for selected in new_selections.values() if selected)
    console.print(f"\n[green]✓ Selection saved: {selected_count}/{len(playlist_dicts)} playlists selected[/green]")
    console.print("\nRun [cyan]musicdiff sync[/cyan] to transfer selected playlists to Deezer")


@cli.command()
def list():
    """Show all Spotify playlists with sync status.

    Displays which playlists are selected for sync and their last sync time.
    """
    db = get_database()
    ui = UI()

    # Get playlist selections from database
    selections = db.get_all_playlist_selections()

    if not selections:
        console.print("[yellow]No playlists found in database.[/yellow]")
        console.print("Run [cyan]musicdiff select[/cyan] to choose playlists to sync")
        return

    # Get synced playlists
    synced = db.get_all_synced_playlists()
    synced_dict = {s['spotify_id']: s for s in synced}

    # Show list
    ui.show_playlist_list(selections, synced_dict)


@cli.command()
@click.option('--dry-run', is_flag=True, help='Show what would be synced without applying changes')
def sync(dry_run):
    """Transfer selected Spotify playlists to Deezer.

    Syncs all selected playlists from Spotify to Deezer. If a playlist already
    exists on Deezer, it will be updated to match Spotify exactly (full overwrite).

    Use --dry-run to preview changes without applying them.
    """
    if dry_run:
        console.print("[dim]DRY RUN - No changes will be applied[/dim]\n")
        mode = SyncMode.DRY_RUN
    else:
        mode = SyncMode.NORMAL

    # Get sync engine and run sync
    try:
        sync_engine = get_sync_engine()
        result = sync_engine.sync(mode=mode)

        # Show summary
        if not dry_run:
            ui = UI()
            ui.show_sync_summary(result)

    except Exception as e:
        console.print(f"[red]Sync failed: {e}[/red]")
        sys.exit(1)


@cli.command()
@click.option('-n', '--limit', default=10, help='Number of sync logs to show')
@click.option('--verbose', is_flag=True, help='Show detailed change list')
def log(limit, verbose):
    """Show sync history."""
    console.print("[bold]Sync History[/bold]\n")

    db = get_database()
    logs = db.get_sync_history(limit=limit)

    if not logs:
        console.print("[dim]No sync history yet[/dim]")
        return

    for entry in logs:
        status_color = "green" if entry['status'] == 'success' else "yellow"
        console.print(f"[{status_color}]●[/{status_color}] {entry['timestamp']}")
        console.print(f"  Status: {entry['status']}")
        console.print(f"  Synced: {entry.get('playlists_synced', 0)} playlists " +
                     f"({entry.get('playlists_created', 0)} created, " +
                     f"{entry.get('playlists_updated', 0)} updated, " +
                     f"{entry.get('playlists_deleted', 0)} deleted)")

        if verbose and entry['details']:
            import json
            details = json.loads(entry['details']) if isinstance(entry['details'], str) else entry['details']
            if details and details.get('failed'):
                console.print(f"  Failed: {', '.join(details['failed'])}")
        console.print()


@cli.command()
@click.option('--interval', default=86400, type=int,
              help='Sync interval in seconds (default: 86400 = 24 hours)')
@click.option('--foreground', is_flag=True, help='Run in foreground (for debugging)')
@click.option('--stop', is_flag=True, help='Stop running daemon')
@click.option('--status', 'show_status', is_flag=True, help='Show daemon status')
def daemon(interval, foreground, stop, show_status):
    """Run MusicDiff in daemon mode for scheduled syncs.

    \b
    Examples:
        musicdiff daemon                    # Start daemon (24h interval)
        musicdiff daemon --interval 21600   # Start with 6h interval
        musicdiff daemon --stop             # Stop daemon
        musicdiff daemon --status           # Check daemon status
    """
    # Get sync engine
    try:
        sync_engine = get_sync_engine()
    except SystemExit:
        # Authentication failed
        return

    daemon_inst = SyncDaemon(sync_engine, interval=interval)

    if show_status:
        status = daemon_inst.status()
        console.print(f"Daemon: {'[green]Running[/green]' if status['running'] else '[dim]Not running[/dim]'}")
        if status['running']:
            console.print(f"  PID: {status['pid']}")
            console.print(f"  Uptime: {status['uptime']}")
            console.print(f"  Interval: {status['interval']}s ({status['interval'] / 3600:.1f} hours)")
            console.print(f"  Log file: {status['log_file']}")
        return

    if stop:
        try:
            daemon_inst.stop()
        except RuntimeError as e:
            console.print(f"[red]Error: {e}[/red]")
        return

    # Start daemon
    try:
        hours = interval / 3600
        console.print(f"[bold cyan]Starting daemon (interval: {hours:.1f} hours)[/bold cyan]")

        if foreground:
            console.print("[dim]Running in foreground (press Ctrl+C to stop)...[/dim]\n")

        daemon_inst.start(foreground=foreground)

        if not foreground:
            console.print(f"[green]✓ Daemon started successfully[/green]")
            console.print(f"  Log file: ~/.musicdiff/daemon.log")
            console.print(f"  Run 'musicdiff daemon --stop' to stop")
            console.print(f"  Run 'musicdiff daemon --status' to check status")

    except RuntimeError as e:
        console.print(f"[red]Error: {e}[/red]")
    except KeyboardInterrupt:
        console.print("\n[yellow]Daemon stopped by user[/yellow]")


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
    config_file = get_config_dir() / 'config.yaml'

    if not key:
        # Show all config
        if config_file.exists():
            console.print(f"[bold]Configuration ({config_file}):[/bold]\n")
            console.print(config_file.read_text())
        else:
            console.print("[yellow]No configuration file found.[/yellow]")
            console.print("Configuration is currently managed via environment variables:")
            console.print("\nSpotify:")
            console.print("  SPOTIFY_CLIENT_ID")
            console.print("  SPOTIFY_CLIENT_SECRET")
            console.print("  SPOTIFY_REDIRECT_URI (optional, default: http://localhost:8888/callback)")
            console.print("\nDeezer:")
            console.print("  DEEZER_ARL")
        return

    # TODO: Implement config get/set with YAML
    console.print("[yellow]Config get/set not yet implemented[/yellow]")
    console.print("Use environment variables for now")


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()
