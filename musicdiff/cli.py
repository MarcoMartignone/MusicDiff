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
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

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


def load_env_file():
    """Load environment variables from .env file if it exists."""
    env_file = get_config_dir() / '.env'
    if env_file.exists():
        load_dotenv(env_file)


# Auto-load environment variables when CLI module is imported
load_env_file()


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

    def load_existing_env():
        """Load existing credentials from .env file."""
        env_file = get_config_dir() / '.env'
        credentials = {
            'spotify_client_id': None,
            'spotify_client_secret': None,
            'spotify_redirect_uri': None,
            'deezer_arl': None
        }

        if env_file.exists():
            with open(env_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('export SPOTIFY_CLIENT_ID='):
                        credentials['spotify_client_id'] = line.split('=', 1)[1].strip('"')
                    elif line.startswith('export SPOTIFY_CLIENT_SECRET='):
                        credentials['spotify_client_secret'] = line.split('=', 1)[1].strip('"')
                    elif line.startswith('export SPOTIFY_REDIRECT_URI='):
                        credentials['spotify_redirect_uri'] = line.split('=', 1)[1].strip('"')
                    elif line.startswith('export DEEZER_ARL='):
                        credentials['deezer_arl'] = line.split('=', 1)[1].strip('"')

        return credentials

    # Check existing configuration
    existing = load_existing_env()
    has_spotify = bool(existing['spotify_client_id'] and existing['spotify_client_secret'])
    has_deezer = bool(existing['deezer_arl'])

    # Show current status
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold cyan]🎵 MusicDiff Setup[/bold cyan]\n\n"
        "Configure your API credentials",
        border_style="cyan"
    ))
    console.print()
    console.print("[bold]Current Configuration:[/bold]")
    console.print()

    if has_spotify:
        console.print("  [green]✓[/green] Spotify configured")
        console.print(f"    Client ID: {existing['spotify_client_id'][:20]}...")
    else:
        console.print("  [red]✗[/red] Spotify not configured")

    console.print()

    if has_deezer:
        console.print("  [green]✓[/green] Deezer configured")
        console.print(f"    ARL: {existing['deezer_arl'][:20]}...")
    else:
        console.print("  [yellow]○[/yellow] Deezer not configured")

    console.print()

    # If everything is configured, ask if user wants to reconfigure
    if has_spotify and has_deezer:
        console.print("[green]All services are configured![/green]")
        console.print()
        if not Confirm.ask("Do you want to reconfigure?", default=False):
            console.print("[cyan]Setup skipped - using existing configuration[/cyan]")
            return

    # Determine what needs to be set up
    setup_spotify = not has_spotify
    setup_deezer = not has_deezer

    if has_spotify and not has_deezer:
        console.print("[bold]Spotify is configured. Set up Deezer now?[/bold]")
        console.print()
        setup_deezer = Confirm.ask("Configure Deezer", default=True)
        if not setup_deezer:
            console.print("[cyan]Setup skipped - using existing configuration[/cyan]")
            return

    if has_deezer and not has_spotify:
        setup_spotify = True

    # Start setup flow
    if has_spotify and Confirm.ask("Reconfigure Spotify credentials?", default=False):
        setup_spotify = True

    if has_deezer and setup_deezer and Confirm.ask("Reconfigure Deezer credentials?", default=False):
        setup_deezer = True
    elif not has_deezer and has_spotify:
        # Only ask if Spotify is configured
        pass  # Already determined above

    # Initialize with existing or new values
    spotify_client_id = existing['spotify_client_id']
    spotify_client_secret = existing['spotify_client_secret']
    spotify_redirect_uri = existing['spotify_redirect_uri'] or "http://127.0.0.1:8888/callback"

    # Spotify Setup
    if setup_spotify:
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
        console.print("   • [bold]Redirect URI:[/bold] http://127.0.0.1:8888/callback")
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
        spotify_redirect_uri = "http://127.0.0.1:8888/callback"

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

    # Initialize Deezer with existing value
    deezer_arl = existing['deezer_arl']

    # Deezer Setup
    if setup_deezer:
        clear_screen()
        console.print()
        console.print(Panel.fit(
            "[bold magenta]🎵 Deezer Setup[/bold magenta]\n\n"
            "Extract your ARL token from Deezer",
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

    if setup_spotify or setup_deezer:
        console.print(Panel.fit(
            "[bold green]🎉 Setup Complete![/bold green]\n\n"
            "MusicDiff is ready to sync your music!",
            border_style="green"
        ))
    else:
        console.print(Panel.fit(
            "[bold cyan]✓ Configuration Updated[/bold cyan]\n\n"
            "Your credentials have been saved",
            border_style="cyan"
        ))

    console.print()
    console.print("[bold]Current configuration:[/bold]")
    console.print("  [green]✓[/green] Spotify API credentials")
    if deezer_arl:
        console.print("  [green]✓[/green] Deezer API credentials")
    else:
        console.print("  [yellow]○[/yellow] Deezer not configured (run setup again to add)")
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
    console.print("3. Select playlists to sync:")
    console.print("   [cyan]musicdiff select[/cyan]")
    console.print()
    console.print("4. Start syncing!")
    console.print("   [cyan]musicdiff sync[/cyan]")
    console.print()


@cli.command()
def init():
    """Initialize MusicDiff and authenticate with music platforms."""
    console.print()
    console.print("[bold cyan]🎵 Initializing MusicDiff...[/bold cyan]\n")

    import time

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        console=console
    ) as progress:
        # Create config directory
        task = progress.add_task("Creating config directory...", total=None)
        config_dir = get_config_dir()
        time.sleep(0.2)
        progress.update(task, description="[green]✓ Config directory ready")

        # Initialize database
        progress.add_task("[cyan]Setting up database...", total=None)
        db = get_database()
        db.init_schema()
        time.sleep(0.3)
        progress.update(task, description="[green]✓ Database initialized")

    console.print()
    console.print("[bold]🔐 Checking credentials...[/bold]\n")

    has_spotify = False
    has_deezer = False

    # Spotify
    if os.environ.get('SPOTIFY_CLIENT_ID') and os.environ.get('SPOTIFY_CLIENT_SECRET'):
        console.print("  [green]✓[/green] Spotify credentials found")
        try:
            with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console) as progress:
                task = progress.add_task("Authenticating with Spotify...", total=None)
                spotify = get_spotify_client()
                username = spotify.sp.current_user()['display_name']
                time.sleep(0.2)
                progress.update(task, description=f"[green]✓ Authenticated as {username}")
            has_spotify = True
        except Exception as e:
            console.print(f"    [yellow]⚠ Authentication failed: {e}[/yellow]")
    else:
        console.print("  [yellow]⚠[/yellow] Spotify credentials not set")
        console.print("    [dim]Run 'musicdiff setup' to configure[/dim]")

    console.print()

    # Deezer
    if os.environ.get('DEEZER_ARL'):
        console.print("  [green]✓[/green] Deezer credentials found")
        try:
            with Progress(SpinnerColumn(), TextColumn("[bold blue]{task.description}"), console=console) as progress:
                task = progress.add_task("Authenticating with Deezer...", total=None)
                deezer = get_deezer_client()
                time.sleep(0.2)
                progress.update(task, description=f"[green]✓ Authenticated (User ID: {deezer.user_id})")
            has_deezer = True
        except Exception as e:
            console.print(f"    [yellow]⚠ Authentication failed: {e}[/yellow]")
    else:
        console.print("  [yellow]⚠[/yellow] Deezer credentials not set")
        console.print("    [dim]Run 'musicdiff setup' to configure[/dim]")

    console.print()

    # Show completion message
    if has_spotify and has_deezer:
        console.print("[green bold]🎉 All set! MusicDiff is ready to rock![/green bold]")
        console.print("\n[bold]Next steps:[/bold]")
        console.print("  1. [cyan]musicdiff select[/cyan] - Choose playlists to sync")
        console.print("  2. [cyan]musicdiff sync[/cyan]   - Transfer to Deezer")
    elif has_spotify:
        console.print("[yellow bold]⚠ Almost there! Spotify is set up.[/yellow bold]")
        console.print("\n[bold]Next step:[/bold] Configure Deezer with [cyan]musicdiff setup[/cyan]")
    else:
        console.print("[yellow bold]⚠ Configuration needed[/yellow bold]")
        console.print("\n[bold]Next step:[/bold] Run [cyan]musicdiff setup[/cyan] to get started")


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
    db = get_database()
    spotify = get_spotify_client()
    ui = UI()

    # Fetch playlist metadata only (fast! no track data)
    playlist_dicts = None

    console.print()

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("🎵 Fetching your Spotify playlists...", total=None)

            # Fast fetch - just metadata, no tracks!
            playlist_dicts = spotify.fetch_playlists_metadata()

            progress.update(task, description="[green]✓ Playlists loaded![/green]")
            import time
            time.sleep(0.2)

        console.print()
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch playlists: {e}[/red]")
        console.print("[dim]Tip: Make sure you've loaded credentials with 'source .musicdiff/.env'[/dim]")
        import traceback
        if os.environ.get('MUSICDIFF_DEBUG'):
            traceback.print_exc()
        sys.exit(1)

    if not playlist_dicts:
        console.print("[yellow]⚠ No Spotify playlists found[/yellow]")
        console.print("[dim]Create some playlists on Spotify first![/dim]")
        return

    # Show count with fun message
    count = len(playlist_dicts)
    if count == 1:
        console.print(f"[cyan]Found {count} playlist! 🎵[/cyan]")
    elif count < 10:
        console.print(f"[cyan]Found {count} playlists! 🎶[/cyan]")
    elif count < 50:
        console.print(f"[cyan]Wow! Found {count} playlists! 🎸[/cyan]")
    else:
        console.print(f"[cyan]Holy moly! {count} playlists! You're a music legend! 🎹🎺🎻[/cyan]")
    console.print()

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

    # Show summary with fun messages
    selected_count = sum(1 for selected in new_selections.values() if selected)

    if selected_count == 0:
        console.print("\n[yellow]⚠ No playlists selected[/yellow]")
        console.print("[dim]Select at least one playlist to sync![/dim]")
        return

    # Show selection confirmation
    if selected_count == 1:
        console.print(f"\n[green]✓ Got it! 1 playlist ready to sync[/green] 🎵")
    elif selected_count == len(playlist_dicts):
        console.print(f"\n[green]✓ All {selected_count} playlists selected! Going for the full collection, nice![/green] 🎸")
    else:
        console.print(f"\n[green]✓ Selection saved: {selected_count}/{len(playlist_dicts)} playlists ready[/green] 🎶")

    # Fetch Deezer playlists and show diff
    try:
        deezer = get_deezer_client()

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]{task.description}"),
            console=console
        ) as progress:
            task = progress.add_task("🎧 Checking what's already on Deezer...", total=None)

            # Fetch Deezer playlists
            deezer_playlists_objs = deezer.fetch_library_playlists()
            # Convert to dicts for easier handling
            deezer_playlists = [
                {
                    'id': pl.deezer_id,
                    'title': pl.name,
                    'track_count': pl.track_count
                }
                for pl in deezer_playlists_objs
            ]

            progress.update(task, description="[green]✓ Deezer playlists loaded![/green]")
            import time
            time.sleep(0.2)

        # Get synced playlists from database
        synced_playlists = db.get_all_synced_playlists()
        synced_db = {sp['spotify_id']: sp for sp in synced_playlists}

        # Get selected playlists
        selected_spotify = [p for p in playlist_dicts if new_selections.get(p['spotify_id'], False)]

        # Show the diff
        ui.show_deezer_diff(selected_spotify, deezer_playlists, synced_db)

    except Exception as e:
        console.print(f"\n[yellow]⚠ Couldn't fetch Deezer playlists: {e}[/yellow]")
        console.print("[dim]Don't worry - you can still sync! The diff preview is just a bonus feature.[/dim]\n")

    console.print("[bold]Next step:[/bold] Run [cyan]musicdiff sync[/cyan] to transfer to Deezer")


@cli.command()
def list():
    """Show all Spotify playlists with sync status.

    Displays which playlists are selected for sync and their last sync time.
    """
    db = get_database()
    ui = UI()

    console.print()
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        console=console
    ) as progress:
        task = progress.add_task("📋 Loading your playlists...", total=None)

        # Get playlist selections from database
        selections = db.get_all_playlist_selections()

        if not selections:
            progress.update(task, description="[yellow]⚠ No playlists found")
            console.print()
            console.print("[yellow]No playlists found in database.[/yellow]")
            console.print("Run [cyan]musicdiff select[/cyan] to choose playlists to sync")
            return

        # Get synced playlists
        synced = db.get_all_synced_playlists()
        synced_dict = {s['spotify_id']: s for s in synced}

        progress.update(task, description="[green]✓ Playlists loaded!")
        import time
        time.sleep(0.2)

    console.print()
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
    console.print()

    if dry_run:
        console.print("[dim]🔍 DRY RUN MODE - Previewing changes (no actual sync)[/dim]\n")
        mode = SyncMode.DRY_RUN
    else:
        console.print("[bold cyan]🚀 Starting playlist sync to Deezer...[/bold cyan]\n")
        mode = SyncMode.NORMAL

    # Get sync engine and run sync
    try:
        sync_engine = get_sync_engine()
        result = sync_engine.sync(mode=mode)

        # Show summary with celebration
        if not dry_run:
            console.print()
            ui = UI()
            ui.show_sync_summary(result)

            # Fun messages based on result
            if result.success:
                if result.total_synced == 0:
                    console.print("[cyan]Everything's already in sync! Nothing to do here. 😎[/cyan]")
                elif result.total_synced == 1:
                    console.print("[green]🎵 Playlist synced! Your music is flowing to Deezer![/green]")
                elif result.total_synced < 5:
                    console.print("[green]🎶 Nice! Your playlists are now on Deezer![/green]")
                else:
                    console.print("[green]🎸 Boom! All your playlists are synced! Rock on! 🤘[/green]")
            else:
                console.print("[yellow]⚠ Sync completed with some issues - check the errors above[/yellow]")

    except Exception as e:
        console.print(f"\n[red]✗ Sync failed: {e}[/red]")
        console.print("[dim]Check your credentials and network connection[/dim]")
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
