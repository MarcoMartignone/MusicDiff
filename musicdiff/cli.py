"""
Command-line interface for MusicDiff.

See docs/CLI.md for detailed documentation.
"""

import warnings
# Suppress urllib3 OpenSSL warning on macOS
warnings.filterwarnings('ignore', message='urllib3 v2 only supports OpenSSL 1.1.1+')

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
from musicdiff.ui import UI, Icons
from musicdiff.downloader import (
    DeemixDownloader,
    DeemixNotFoundError,
    DeemixAuthError,
    DownloadStats,
    get_default_download_path,
    apply_playlist_metadata,
    MUTAGEN_AVAILABLE
)

console = Console()


def get_config_dir() -> Path:
    """Get MusicDiff configuration directory."""
    # Use project directory in Documents instead of home
    config_dir = Path.home() / 'Documents' / 'MusicDiff' / '.musicdiff'
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


def sanitize_folder_name(name: str) -> str:
    """Sanitize a string for use as a folder name.

    Args:
        name: The string to sanitize

    Returns:
        A filesystem-safe folder name
    """
    import re
    # Replace characters not allowed in folder names
    # Keep letters, numbers, spaces, hyphens, underscores, and parentheses
    sanitized = re.sub(r'[<>:"/\\|?*]', '', name)
    # Replace multiple spaces with single space
    sanitized = re.sub(r'\s+', ' ', sanitized)
    # Strip leading/trailing spaces and dots
    sanitized = sanitized.strip(' .')
    # Limit length to 255 characters (common filesystem limit)
    return sanitized[:255] if sanitized else 'Unknown Playlist'


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

    # Enable debug mode if DEBUG env var is set
    debug = os.environ.get('DEBUG', '').lower() in ('1', 'true', 'yes')

    client = DeezerClient(arl_token=arl_token, debug=debug)

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
        f"[bold cyan]{Icons.MUSIC} MusicDiff Setup[/bold cyan]\n\n"
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
            f"[bold magenta]{Icons.DEEZER} Deezer Setup[/bold magenta]\n\n"
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
            f"[bold magenta]{Icons.DEEZER} Deezer - Enter ARL Token[/bold magenta]",
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
    console.print(f"[bold cyan]{Icons.MUSIC} Initializing MusicDiff...[/bold cyan]\n")

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
            task = progress.add_task(f"{Icons.MUSIC} Fetching your Spotify playlists...", total=None)

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

    # Show count
    count = len(playlist_dicts)
    console.print(f"[cyan]{Icons.MUSIC} Found {count} playlist{'s' if count != 1 else ''}[/cyan]")
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
    console.print(f"\n[green]{Icons.SUCCESS}[/green] Selection saved: {selected_count}/{len(playlist_dicts)} playlists ready to sync")

    # Fetch Deezer playlists and show diff
    try:
        deezer = get_deezer_client()

        # Progress callback for Deezer fetch
        deezer_progress = None
        deezer_task = None

        def deezer_progress_callback(current, total, name):
            if deezer_progress and deezer_task is not None:
                deezer_progress.update(
                    deezer_task,
                    completed=current,
                    total=total,
                    description=f"{Icons.DEEZER} Loading Deezer playlists: {name[:40]}..."
                )

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold magenta]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            deezer_progress = progress
            deezer_task = progress.add_task(f"{Icons.DEEZER} Fetching Deezer playlists...", total=None)

            # Fast fetch - just metadata, no tracks!
            deezer_playlists = deezer.fetch_library_playlists_metadata(
                progress_callback=deezer_progress_callback
            )

            progress.update(deezer_task, description="[green]✓ Deezer playlists loaded![/green]")
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


@cli.command('list')
def list_playlists():
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
        console.print(f"[dim]{Icons.SEARCH} DRY RUN MODE - Previewing changes (no actual sync)[/dim]\n")
        mode = SyncMode.DRY_RUN
    else:
        console.print(f"[bold cyan]{Icons.ROCKET} Starting playlist sync to Deezer...[/bold cyan]\n")
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

            # Result message
            if result.success:
                if result.total_synced == 0:
                    console.print(f"[cyan]{Icons.SUCCESS} Everything's already in sync![/cyan]")
                else:
                    console.print(f"[green]{Icons.SPARKLE} Sync complete! {result.total_synced} playlists synced to Deezer[/green]")
            else:
                console.print(f"[yellow]{Icons.WARNING} Sync completed with some issues - check the errors above[/yellow]")

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
@click.option('--playlist', '-p', 'playlist_name', help='Download specific playlist by name')
@click.option('--quality', '-q', type=click.Choice(['128', '320', 'flac']),
              default='320', help='Audio quality (default: 320)')
@click.option('--path', '-o', 'output_path', type=click.Path(),
              help='Download location')
@click.option('--dry-run', is_flag=True, help='Show what would be downloaded without downloading')
@click.option('--retry-failed', is_flag=True, help='Retry previously failed downloads')
@click.option('--force', '-f', is_flag=True, help='Re-download even if already completed')
@click.option('--set-path', 'new_path', type=click.Path(),
              help='Set and save default download path')
@click.option('--status', 'show_status', is_flag=True, help='Show download queue status')
@click.option('--clear', 'clear_history', is_flag=True, help='Clear download history')
@click.option('--update-metadata', 'update_metadata', is_flag=True,
              help='Update metadata on already-downloaded files without re-downloading')
@click.option('--verify', 'verify_files', is_flag=True,
              help='Check for missing files and re-download them')
@click.option('--scan', 'scan_files', is_flag=True,
              help='Scan download folder and match existing files to database entries')
@click.option('--update-artwork', 'update_artwork', is_flag=True,
              help='Update cover art on already-downloaded files with high-res artwork')
@click.option('--no-auto-scan', 'no_auto_scan', is_flag=True,
              help='Skip automatic file scanning after download')
@click.option('--no-auto-metadata', 'no_auto_metadata', is_flag=True,
              help='Skip automatic metadata update after download')
def download(playlist_name, quality, output_path, dry_run, retry_failed, force, new_path, show_status, clear_history, update_metadata, verify_files, scan_files, update_artwork, no_auto_scan, no_auto_metadata):
    """Download tracks from synced playlists using deemix.

    Downloads tracks from all selected playlists or a specific playlist.
    Tracks that have already been downloaded are skipped unless --force is used.
    Requires deemix CLI to be installed.

    \b
    Examples:
        musicdiff download                    # Download all pending tracks
        musicdiff download -p "My Playlist"   # Download specific playlist
        musicdiff download -q flac            # Download in FLAC quality
        musicdiff download --retry-failed     # Retry failed downloads
        musicdiff download --dry-run          # Preview what would download
        musicdiff download --set-path ~/Music # Change download location
        musicdiff download --status           # Show download queue status
        musicdiff download --verify           # Find and re-download missing files
        musicdiff download --scan             # Match existing files to database
    """
    db = get_database()

    # Handle --status flag
    if show_status:
        stats = db.get_download_stats()
        console.print("[bold cyan]Download Queue Status[/bold cyan]\n")
        console.print(f"  Total tracks: {stats['total']}")
        console.print(f"  [yellow]Pending:[/yellow] {stats['pending']}")
        console.print(f"  [blue]Downloading:[/blue] {stats['downloading']}")
        console.print(f"  [green]Completed:[/green] {stats['completed']}")
        console.print(f"  [red]Failed:[/red] {stats['failed']}")
        console.print(f"  [dim]Skipped:[/dim] {stats['skipped']}")

        # Show download path
        download_path = db.get_metadata('download_path')
        if download_path:
            console.print(f"\n  Download path: {download_path}")
        return

    # Handle --clear flag
    if clear_history:
        if Confirm.ask("Clear all download history?", default=False):
            deleted = db.clear_download_history()
            console.print(f"[green]✓ Cleared {deleted} download records[/green]")
        return

    # Handle --update-metadata flag
    if update_metadata:
        try:
            if not MUTAGEN_AVAILABLE:
                console.print("[red]Error: mutagen library not installed.[/red]")
                console.print("Install with: pip install mutagen")
                return

            # Get completed downloads
            completed = db.get_downloads_by_status('completed')
            if not completed:
                console.print("[yellow]No completed downloads found.[/yellow]")
                return

            # Group by playlist and build work items
            from collections import defaultdict

            tracks_by_playlist = defaultdict(list)
            for track in completed:
                playlist_id = track.get('playlist_spotify_id') or 'unknown'
                tracks_by_playlist[playlist_id].append(track)

            # Build list of (file_path, playlist_name, position) work items
            work_items = []
            for playlist_id, tracks in tracks_by_playlist.items():
                plist = db.get_playlist_selection(playlist_id) if playlist_id != 'unknown' else None
                playlist_name = plist['name'] if plist else ''
                for track in tracks:
                    # Use stored position from database (falls back to 0 if not set)
                    stored_position = track.get('position', 0)
                    work_items.append({
                        'file_path': track.get('file_path'),
                        'playlist_name': playlist_name,
                        'position': stored_position if stored_position > 0 else 1,
                        'artist': track.get('artist', 'Unknown'),
                        'title': track.get('title', 'Unknown'),
                    })

            console.print(f"[bold]Updating metadata on {len(work_items)} files (4 parallel workers)...[/bold]\n")

            import subprocess
            from concurrent.futures import ThreadPoolExecutor, as_completed

            updated = 0
            skipped = 0
            errors = 0
            timeouts = 0
            error_details = []

            def update_one_file(item):
                """Update metadata for one file using subprocess with timeout."""
                file_path = item['file_path']
                playlist_name = item['playlist_name']
                position = item['position']

                if not file_path:
                    return ('skipped', 'no path')
                if not Path(file_path).exists():
                    return ('skipped', 'not found')
                if not playlist_name:
                    return ('skipped', 'no playlist')

                script = f'''
import sys
from mutagen.id3 import ID3, ID3NoHeaderError, TCOM, TRCK, TCMP
from mutagen.mp3 import MP3
try:
    try:
        tags = ID3({repr(file_path)})
    except ID3NoHeaderError:
        audio = MP3({repr(file_path)})
        audio.add_tags()
        audio.save()
        tags = ID3({repr(file_path)})
    tags.delall("TCOM")
    tags.add(TCOM(encoding=3, text=[{repr(playlist_name)}]))
    tags.delall("TRCK")
    tags.add(TRCK(encoding=3, text=["{position}"]))
    tags.delall("TCMP")
    tags.add(TCMP(encoding=3, text=["1"]))
    tags.save()
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
'''
                try:
                    result = subprocess.run(
                        [sys.executable, '-c', script],
                        timeout=5,
                        capture_output=True,
                        text=True
                    )
                    if result.returncode == 0:
                        return ('updated', None)
                    else:
                        return ('error', result.stderr.strip()[:60] if result.stderr else 'Unknown')
                except subprocess.TimeoutExpired:
                    return ('timeout', 'file locked or slow')

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
                console=console
            ) as progress:
                task = progress.add_task("Updating metadata...", total=len(work_items))

                with ThreadPoolExecutor(max_workers=4) as executor:
                    futures = {executor.submit(update_one_file, item): item for item in work_items}

                    for future in as_completed(futures):
                        item = futures[future]
                        status, detail = future.result()

                        if status == 'updated':
                            updated += 1
                        elif status == 'skipped':
                            skipped += 1
                        elif status == 'timeout':
                            timeouts += 1
                            error_details.append({
                                'artist': item['artist'],
                                'title': item['title'],
                                'error': detail,
                                'path': item['file_path']
                            })
                        else:
                            errors += 1
                            error_details.append({
                                'artist': item['artist'],
                                'title': item['title'],
                                'error': detail,
                                'path': item['file_path']
                            })

                        progress.update(task, advance=1, description=f"{item['artist'][:15]} - {item['title'][:20]}")

            console.print()
            console.print(f"[green]✓ Updated:[/green] {updated}")
            console.print(f"[dim]⊘ Skipped:[/dim] {skipped}")
            if timeouts:
                console.print(f"[yellow]⏱ Timeouts:[/yellow] {timeouts}")
            if errors:
                console.print(f"[red]✗ Errors:[/red] {errors}")
            if error_details and len(error_details) <= 10:
                console.print("\n[bold]Failed files:[/bold]")
                for e in error_details:
                    console.print(f"  [dim]{e['artist'][:20]} - {e['title'][:25]}[/dim]: {e['error']}")
            elif error_details:
                from collections import Counter
                error_types = Counter(e['error'].split(':')[0] if e['error'] else 'Unknown' for e in error_details)
                console.print("\n[bold]Error breakdown:[/bold]")
                for err_type, count in error_types.most_common():
                    console.print(f"  {err_type}: {count}")
            return
        except Exception as e:
            console.print(f"[red]Error updating metadata: {e}[/red]")
            import traceback
            traceback.print_exc()
            return

    # Handle --update-artwork flag
    if update_artwork:
        try:
            if not MUTAGEN_AVAILABLE:
                console.print("[red]Error: mutagen library not installed.[/red]")
                console.print("Install with: pip install mutagen")
                return

            import requests
            from mutagen.id3 import ID3, APIC, ID3NoHeaderError
            from mutagen.mp3 import MP3

            # Get completed downloads
            completed = db.get_downloads_by_status('completed')
            if not completed:
                console.print("[yellow]No completed downloads found.[/yellow]")
                return

            # Filter to only tracks with file paths and deezer_ids
            work_items = [t for t in completed if t.get('file_path') and t.get('deezer_id') and Path(t['file_path']).exists()]

            if not work_items:
                console.print("[yellow]No files found to update artwork.[/yellow]")
                return

            console.print(f"[bold]Updating artwork on {len(work_items)} files...[/bold]\n")

            # Artwork size from deemix config (use 1400 as default high-res)
            artwork_size = 1400

            updated = 0
            skipped = 0
            errors = 0

            with Progress(
                SpinnerColumn(),
                TextColumn("[bold blue]{task.description}"),
                BarColumn(),
                TaskProgressColumn(),
                TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
                console=console
            ) as progress:
                task = progress.add_task("Updating artwork...", total=len(work_items))

                for item in work_items:
                    file_path = item['file_path']
                    deezer_id = item['deezer_id']
                    artist = item.get('artist', 'Unknown')[:15]
                    title = item.get('title', 'Unknown')[:20]

                    progress.update(task, description=f"{artist} - {title}")

                    try:
                        # Get track info from Deezer API to get album cover
                        resp = requests.get(f"https://api.deezer.com/track/{deezer_id}", timeout=10)
                        if resp.status_code != 200:
                            skipped += 1
                            progress.advance(task)
                            continue

                        track_data = resp.json()
                        album_cover = track_data.get('album', {}).get('cover_xl')

                        if not album_cover:
                            # Try to construct high-res URL from md5
                            md5 = track_data.get('album', {}).get('md5_image')
                            if md5:
                                album_cover = f"https://e-cdns-images.dzcdn.net/images/cover/{md5}/{artwork_size}x{artwork_size}-000000-80-0-0.jpg"

                        if not album_cover:
                            skipped += 1
                            progress.advance(task)
                            continue

                        # Download the artwork
                        img_resp = requests.get(album_cover, timeout=15)
                        if img_resp.status_code != 200:
                            skipped += 1
                            progress.advance(task)
                            continue

                        artwork_data = img_resp.content

                        # Update the MP3 file
                        try:
                            tags = ID3(file_path)
                        except ID3NoHeaderError:
                            audio = MP3(file_path)
                            audio.add_tags()
                            audio.save()
                            tags = ID3(file_path)

                        # Remove existing artwork
                        tags.delall("APIC")

                        # Add new high-res artwork
                        tags.add(APIC(
                            encoding=3,  # UTF-8
                            mime='image/jpeg',
                            type=3,  # Cover (front)
                            desc='Cover',
                            data=artwork_data
                        ))

                        tags.save()
                        updated += 1

                    except Exception as e:
                        errors += 1

                    progress.advance(task)

            console.print()
            console.print(f"[green]✓ Updated:[/green] {updated}")
            console.print(f"[dim]⊘ Skipped:[/dim] {skipped}")
            if errors:
                console.print(f"[red]✗ Errors:[/red] {errors}")
            return

        except Exception as e:
            console.print(f"[red]Error updating artwork: {e}[/red]")
            import traceback
            traceback.print_exc()
            return

    # Handle --set-path flag
    if new_path:
        path = Path(new_path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        db.set_metadata('download_path', str(path))
        console.print(f"[green]✓ Download path set to: {path}[/green]")
        if not (playlist_name or retry_failed or force):
            return

    # Get or prompt for download path
    download_path = output_path
    if not download_path:
        download_path = db.get_metadata('download_path')

    if not download_path:
        # First time - prompt for path
        console.print(f"[bold cyan]{Icons.DOWNLOAD} First-time Download Setup[/bold cyan]\n")
        console.print("Where should downloaded music be saved?\n")

        default_path = str(get_default_download_path())
        download_path = Prompt.ask(
            "Download location",
            default=default_path
        )

        # Save for future use
        path = Path(download_path).expanduser().resolve()
        path.mkdir(parents=True, exist_ok=True)
        db.set_metadata('download_path', str(path))
        console.print(f"[green]✓ Download path saved: {path}[/green]\n")
        download_path = str(path)

    # Get ARL token
    arl_token = os.environ.get('DEEZER_ARL')
    if not arl_token:
        console.print("[red]Error: Deezer ARL token not found.[/red]")
        console.print("Run [cyan]musicdiff setup[/cyan] to configure Deezer credentials.")
        sys.exit(1)

    # Initialize downloader
    try:
        downloader = DeemixDownloader(
            db=db,
            arl_token=arl_token,
            download_path=download_path,
            quality=quality
        )
    except DeemixNotFoundError as e:
        console.print(f"[red]Error: {e}[/red]")
        console.print("\n[bold]To install deemix:[/bold]")
        console.print("  cd ~/Documents/deemix && pnpm install && pnpm build")
        sys.exit(1)
    except ValueError as e:
        console.print(f"[red]Error: {e}[/red]")
        sys.exit(1)

    # Handle --retry-failed
    if retry_failed:
        failed = db.get_failed_downloads(max_attempts=3)
        if not failed:
            console.print("[green]No failed downloads to retry![/green]")
            return

        console.print(f"[bold]Retrying {len(failed)} failed downloads...[/bold]\n")

        if dry_run:
            for track in failed:
                console.print(f"  Would retry: {track['artist']} - {track['title']}")
            return

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            console=console
        ) as progress:
            task = progress.add_task("Retrying downloads...", total=len(failed))

            def progress_callback(current, total, track):
                progress.update(task, completed=current,
                               description=f"Retrying: {track.get('artist', '')} - {track.get('title', '')[:30]}")

            stats = downloader.download_tracks(failed, progress_callback)

        console.print(f"\n[green]✓ Retry complete: {stats.completed} succeeded, {stats.failed} failed[/green]")
        return

    # Handle --verify flag: check for missing files
    if verify_files:
        console.print("[bold]Verifying downloaded files...[/bold]\n")

        # Get all completed downloads
        conn = __import__('sqlite3').connect(db.db_path)
        conn.row_factory = __import__('sqlite3').Row
        cursor = conn.cursor()
        completed = cursor.execute(
            "SELECT deezer_id, artist, title, file_path FROM download_status WHERE status = 'completed'"
        ).fetchall()
        conn.close()

        missing_count = 0
        no_path_count = 0

        for track in completed:
            artist = track['artist'] or ''
            title = track['title'] or ''
            file_path = track['file_path']

            if file_path:
                # We have a stored path - check if file exists
                if not Path(file_path).exists():
                    db.update_download_status(track['deezer_id'], 'pending')
                    missing_count += 1
                    console.print(f"  [yellow]Missing:[/yellow] {artist} - {title}")
            else:
                # No path stored - can't verify, count but don't re-download
                no_path_count += 1

        if missing_count > 0:
            console.print(f"\n[yellow]Found {missing_count} missing files - will re-download[/yellow]")
        if no_path_count > 0:
            console.print(f"[dim]({no_path_count} tracks have no stored path - run with --force to re-download all)[/dim]")
        if missing_count == 0 and no_path_count == 0:
            console.print("[green]All files verified - nothing missing![/green]")
            return
        if missing_count == 0:
            console.print("[green]All verifiable files present![/green]")
            return
        console.print()

    # Handle --scan flag: match existing files to database entries
    if scan_files:
        console.print("[bold]Scanning for existing files...[/bold]\n")
        import glob as glob_module

        # First, add tracks from selected playlists to download_status if not already there
        selected_playlists = db.get_selected_playlists()
        if selected_playlists:
            try:
                spotify = get_spotify_client()
                new_tracks = 0
                with Progress(
                    SpinnerColumn(),
                    TextColumn("[bold cyan]{task.description}"),
                    console=console
                ) as progress:
                    task = progress.add_task("Loading playlists...", total=len(selected_playlists))
                    for playlist in selected_playlists:
                        progress.update(task, description=f"Loading: {playlist['name'][:30]}...", advance=1)
                        try:
                            full_playlist = spotify.fetch_playlist_by_id(playlist['spotify_id'])
                            for i, track in enumerate(full_playlist.tracks):
                                if not track.isrc:
                                    continue
                                # Look up by spotify_id since Spotify tracks don't have deezer_id
                                existing = db.get_download_by_spotify_id(track.spotify_id) if track.spotify_id else None
                                if not existing:
                                    # Look up deezer_id from track cache by ISRC
                                    cached = db.get_track_by_isrc(track.isrc) if track.isrc else None
                                    deezer_id = cached.get('deezer_id') if cached else None
                                    db.add_download_record(
                                        deezer_id=deezer_id or f"spotify_{track.spotify_id}",
                                        spotify_id=track.spotify_id,
                                        isrc=track.isrc,
                                        title=track.title,
                                        artist=track.artist,
                                        playlist_spotify_id=playlist['spotify_id'],
                                        position=i + 1,
                                        quality='320'
                                    )
                                    new_tracks += 1
                                else:
                                    # Update position for existing tracks (use deezer_id from db record)
                                    db.update_download_position(existing['deezer_id'], i + 1)
                        except Exception as e:
                            console.print(f"[red]Error loading {playlist['name']}: {e}[/red]")
                if new_tracks > 0:
                    console.print(f"[green]Added {new_tracks} new tracks to database[/green]\n")
            except Exception as e:
                console.print(f"[red]Spotify error: {e}[/red]")

        # Get all mp3 files in download path
        search_pattern = str(Path(download_path) / '**' / '*.mp3')
        all_files = glob_module.glob(search_pattern, recursive=True)
        console.print(f"Found {len(all_files)} mp3 files in {download_path}\n")

        if not all_files:
            console.print("[yellow]No mp3 files found to scan.[/yellow]")
            return

        # Build a lookup structure for faster matching
        # Key: (cleaned_filename_without_ext) -> full_path
        def clean_for_match(s):
            return ''.join(c for c in s.lower() if c.isalnum() or c == ' ').strip()

        file_lookup = {}
        for f in all_files:
            stem = Path(f).stem  # filename without extension
            clean_stem = clean_for_match(stem)
            file_lookup[clean_stem] = f
            # Also index by just the part after " - " (the title part)
            if ' - ' in stem:
                title_part = stem.split(' - ', 1)[1]
                clean_title = clean_for_match(title_part)
                if clean_title not in file_lookup:
                    file_lookup[clean_title] = f

        # Get all downloads (completed, pending, or failed) to try matching
        conn = __import__('sqlite3').connect(db.db_path)
        conn.row_factory = __import__('sqlite3').Row
        cursor = conn.cursor()
        tracks = cursor.execute(
            "SELECT deezer_id, artist, title, file_path, status FROM download_status"
        ).fetchall()
        conn.close()

        matched = 0
        already_set = 0
        not_found = 0

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
            console=console
        ) as progress:
            task = progress.add_task("Matching files...", total=len(tracks))

            for i, track in enumerate(tracks):
                artist = track['artist'] or ''
                title = track['title'] or ''
                existing_path = track['file_path']

                progress.update(task, description=f"Scanning: {artist[:20]} - {title[:25]}", completed=i+1)

                # Skip if already has a valid path
                if existing_path and Path(existing_path).exists():
                    already_set += 1
                    continue

                # Try to find matching file
                primary_artist = artist.split(',')[0].strip()

                # Method 1: Try "Artist - Title" pattern
                search_key = clean_for_match(f"{primary_artist} - {title}")
                if search_key in file_lookup:
                    db.update_download_status(track['deezer_id'], 'completed', file_path=file_lookup[search_key])
                    matched += 1
                    continue

                # Method 2: Try just the title
                search_key = clean_for_match(title)
                if search_key in file_lookup:
                    db.update_download_status(track['deezer_id'], 'completed', file_path=file_lookup[search_key])
                    matched += 1
                    continue

                # Method 3: Fuzzy match - check if artist and title words appear in any filename
                found = False
                artist_words = set(clean_for_match(primary_artist).split())
                title_words = set(clean_for_match(title).split())
                # Remove very short words
                title_words = {w for w in title_words if len(w) > 2}

                for clean_stem, file_path in file_lookup.items():
                    stem_words = set(clean_stem.split())
                    # Check if most artist words and title words are in filename
                    artist_match = len(artist_words & stem_words) >= len(artist_words) * 0.5 if artist_words else True
                    title_match = len(title_words & stem_words) >= len(title_words) * 0.6 if title_words else False

                    if artist_match and title_match:
                        db.update_download_status(track['deezer_id'], 'completed', file_path=file_path)
                        matched += 1
                        found = True
                        break

                if not found:
                    not_found += 1

        console.print(f"\n[green]✓ Matched:[/green] {matched} files")
        console.print(f"[dim]⊘ Already set:[/dim] {already_set}")
        console.print(f"[yellow]✗ Not found:[/yellow] {not_found}")

        if matched > 0:
            console.print(f"\n[green]Successfully linked {matched} existing files to database![/green]")
        return

    # Get tracks to download
    # First, reset any stuck 'downloading' status
    reset_count = db.reset_downloading_to_pending()
    if reset_count > 0:
        console.print(f"[dim]Reset {reset_count} interrupted downloads[/dim]")

    # Get synced playlists to find tracks
    synced_playlists = db.get_all_synced_playlists()
    selected_playlists = db.get_selected_playlists()

    if not selected_playlists:
        console.print("[yellow]No playlists selected for sync.[/yellow]")
        console.print("Run [cyan]musicdiff select[/cyan] to choose playlists first.")
        return

    # Filter by playlist name if specified
    if playlist_name:
        selected_playlists = [p for p in selected_playlists
                             if playlist_name.lower() in p['name'].lower()]
        if not selected_playlists:
            console.print(f"[yellow]No playlist matching '{playlist_name}' found.[/yellow]")
            return

    # Queue tracks from selected playlists
    console.print("[bold]Preparing download queue...[/bold]\n")

    # Get Spotify client to fetch track details
    try:
        spotify = get_spotify_client()
    except SystemExit:
        return

    total_queued = 0

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold cyan]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Loading tracks...", total=len(selected_playlists))

        for playlist in selected_playlists:
            progress.update(task, description=f"Loading: {playlist['name'][:40]}...")

            # Fetch full playlist with tracks from Spotify
            try:
                full_playlist = spotify.fetch_playlist_by_id(playlist['spotify_id'])
            except Exception as e:
                console.print(f"[yellow]⚠ Failed to fetch {playlist['name']}: {e}[/yellow]")
                progress.update(task, advance=1)
                continue

            # Queue tracks that have Deezer IDs
            for i, track in enumerate(full_playlist.tracks):
                # Look up Deezer ID from our track cache
                cached = db.get_track_by_isrc(track.isrc) if track.isrc else None

                if cached and cached.get('deezer_id'):
                    # Check if already in queue
                    existing = db.get_download_by_deezer_id(cached['deezer_id'])

                    if existing:
                        if existing.get('status') == 'completed':
                            file_path = existing.get('file_path')
                            # If file_path is set, verify it exists - if not, reset to pending
                            if file_path and not Path(file_path).exists():
                                db.update_download_status(cached['deezer_id'], 'pending')
                                total_queued += 1
                                continue
                            # File exists (or no path stored) - skip unless --force
                            if not force:
                                continue
                            # --force: reset to pending for re-download
                            db.update_download_status(cached['deezer_id'], 'pending')
                            total_queued += 1
                            continue
                        # Skip if already queued (pending/downloading/failed)
                        continue

                    # Add to download queue
                    db.add_download_record(
                        deezer_id=cached['deezer_id'],
                        spotify_id=track.spotify_id,
                        isrc=track.isrc,
                        title=track.title,
                        artist=track.artist,
                        playlist_spotify_id=playlist['spotify_id'],
                        position=i + 1,
                        quality=quality
                    )
                    total_queued += 1

            progress.update(task, advance=1)

    if total_queued == 0:
        # Check if there are pending downloads
        pending = db.get_pending_downloads()
        if pending:
            console.print(f"[cyan]Found {len(pending)} tracks already in queue[/cyan]")
        else:
            console.print("[green]All tracks already downloaded or no Deezer matches found![/green]")
            console.print("[dim]Run 'musicdiff sync' first to match tracks with Deezer.[/dim]")
            return
    else:
        console.print(f"[green]✓ Queued {total_queued} new tracks for download[/green]")

    # Get pending downloads
    pending = db.get_pending_downloads()

    if not pending:
        console.print("[green]Nothing to download![/green]")
        return

    console.print(f"\n[bold]Ready to download {len(pending)} tracks[/bold]")
    console.print(f"  Quality: {quality}")
    console.print(f"  Location: {download_path}\n")

    if dry_run:
        console.print("[dim]DRY RUN - Would download:[/dim]\n")
        for i, track in enumerate(pending[:20]):  # Show first 20
            console.print(f"  {i+1}. {track['artist']} - {track['title']}")
        if len(pending) > 20:
            console.print(f"  ... and {len(pending) - 20} more")
        return

    # Confirm download
    if not Confirm.ask(f"Start downloading {len(pending)} tracks?", default=True):
        console.print("[yellow]Download cancelled[/yellow]")
        return

    # Download with progress
    # Group tracks by playlist for correct metadata tagging
    from collections import defaultdict
    tracks_by_playlist = defaultdict(list)
    for track in pending:
        playlist_id = track.get('playlist_spotify_id') or 'unknown'
        tracks_by_playlist[playlist_id].append(track)

    console.print()

    # Get playlist names
    playlist_names = {}
    for playlist_id in tracks_by_playlist.keys():
        if playlist_id != 'unknown':
            plist = db.get_playlist_selection(playlist_id)
            if plist:
                playlist_names[playlist_id] = plist.get('name', '')

    total_tracks = len(pending)
    completed_count = 0
    all_stats = DownloadStats()

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TextColumn("[dim]{task.completed}/{task.total}[/dim]"),
        console=console
    ) as progress:
        task = progress.add_task("Downloading...", total=total_tracks)

        # Download each playlist group with correct positions
        for playlist_id, tracks in tracks_by_playlist.items():
            playlist_name = playlist_names.get(playlist_id, '')

            # Create playlist-specific folder
            if playlist_name:
                folder_name = sanitize_folder_name(playlist_name)
                playlist_folder = Path(download_path) / folder_name
                playlist_folder.mkdir(parents=True, exist_ok=True)
                downloader.set_download_path(str(playlist_folder))
            else:
                # Fallback to base download path if no playlist name
                downloader.set_download_path(download_path)

            # Add position to each track for metadata
            for idx, track in enumerate(tracks):
                track['_playlist_position'] = idx + 1

            def progress_callback(current, total, track):
                nonlocal completed_count
                completed_count += 1
                artist = track.get('artist', 'Unknown')[:20]
                title = track.get('title', 'Unknown')[:30]
                progress.update(task, completed=completed_count,
                               description=f"Downloading: {artist} - {title}")

            stats = downloader.download_tracks(
                tracks,
                progress_callback,
                playlist_name=playlist_name,
                apply_playlist_tags=True
            )

            all_stats.completed += stats.completed
            all_stats.failed += stats.failed
            all_stats.skipped += stats.skipped
            all_stats.errors.extend(stats.errors)

    stats = all_stats

    # Show summary
    console.print()
    console.print("[bold]Download Complete![/bold]\n")
    console.print(f"  [green]✓ Completed:[/green] {stats.completed}")
    console.print(f"  [red]✗ Failed:[/red] {stats.failed}")
    console.print(f"  [dim]⊘ Skipped:[/dim] {stats.skipped}")

    if stats.errors:
        console.print("\n[bold red]Errors:[/bold red]")
        for error in stats.errors[:5]:  # Show first 5 errors
            console.print(f"  • {error}")
        if len(stats.errors) > 5:
            console.print(f"  ... and {len(stats.errors) - 5} more errors")
        console.print("\n[dim]Run 'musicdiff download --retry-failed' to retry[/dim]")

    if stats.completed > 0:
        console.print(f"\n[green]{Icons.MUSIC} {stats.completed} tracks saved to {download_path}[/green]")

        # Auto-run scan and metadata update after successful download
        if not no_auto_scan:
            console.print("\n[bold]Auto-scanning downloaded files...[/bold]")
            _run_scan(db, download_path, console)

        if not no_auto_metadata:
            console.print("\n[bold]Auto-updating metadata...[/bold]")
            _run_metadata_update(db, console)


def _run_scan(db, download_path, console):
    """Scan download folder and match files to database entries."""
    import glob as glob_module

    # Get all mp3 files in download path
    search_pattern = str(Path(download_path) / '**' / '*.mp3')
    all_files = glob_module.glob(search_pattern, recursive=True)

    if not all_files:
        console.print("[dim]No mp3 files found to scan.[/dim]")
        return

    # Build a lookup structure for faster matching
    def clean_for_match(s):
        return ''.join(c for c in s.lower() if c.isalnum() or c == ' ').strip()

    file_lookup = {}
    for f in all_files:
        stem = Path(f).stem
        clean_stem = clean_for_match(stem)
        file_lookup[clean_stem] = f
        if ' - ' in stem:
            title_part = stem.split(' - ', 1)[1]
            clean_title = clean_for_match(title_part)
            if clean_title not in file_lookup:
                file_lookup[clean_title] = f

    # Get all downloads to try matching
    conn = __import__('sqlite3').connect(db.db_path)
    conn.row_factory = __import__('sqlite3').Row
    cursor = conn.cursor()
    tracks = cursor.execute(
        "SELECT deezer_id, artist, title, file_path, status FROM download_status"
    ).fetchall()
    conn.close()

    matched = 0

    for track in tracks:
        artist = track['artist'] or ''
        title = track['title'] or ''
        existing_path = track['file_path']

        # Skip if already has a valid path
        if existing_path and Path(existing_path).exists():
            continue

        primary_artist = artist.split(',')[0].strip()

        # Try "Artist - Title" pattern
        search_key = clean_for_match(f"{primary_artist} - {title}")
        if search_key in file_lookup:
            db.update_download_status(track['deezer_id'], 'completed', file_path=file_lookup[search_key])
            matched += 1
            continue

        # Try just the title
        search_key = clean_for_match(title)
        if search_key in file_lookup:
            db.update_download_status(track['deezer_id'], 'completed', file_path=file_lookup[search_key])
            matched += 1

    if matched > 0:
        console.print(f"[green]✓ Matched {matched} files to database[/green]")


def _run_metadata_update(db, console):
    """Update metadata on completed downloads."""
    if not MUTAGEN_AVAILABLE:
        console.print("[yellow]Skipping metadata update (mutagen not installed)[/yellow]")
        return

    from collections import defaultdict
    import subprocess

    # Get completed downloads
    completed = db.get_downloads_by_status('completed')
    if not completed:
        return

    # Group by playlist and build work items
    tracks_by_playlist = defaultdict(list)
    for track in completed:
        playlist_id = track.get('playlist_spotify_id') or 'unknown'
        tracks_by_playlist[playlist_id].append(track)

    # Build list of work items
    work_items = []
    for playlist_id, tracks in tracks_by_playlist.items():
        plist = db.get_playlist_selection(playlist_id) if playlist_id != 'unknown' else None
        playlist_name = plist['name'] if plist else ''
        for track in tracks:
            stored_position = track.get('position', 0)
            file_path = track.get('file_path')
            if file_path and Path(file_path).exists() and playlist_name:
                work_items.append({
                    'file_path': file_path,
                    'playlist_name': playlist_name,
                    'position': stored_position if stored_position > 0 else 1,
                })

    if not work_items:
        return

    from concurrent.futures import ThreadPoolExecutor, as_completed

    updated = 0

    def update_one_file(item):
        file_path = item['file_path']
        playlist_name = item['playlist_name']
        position = item['position']

        script = f'''
import sys
from mutagen.id3 import ID3, ID3NoHeaderError, TCOM, TRCK, TCMP
from mutagen.mp3 import MP3
try:
    try:
        tags = ID3({repr(file_path)})
    except ID3NoHeaderError:
        audio = MP3({repr(file_path)})
        audio.add_tags()
        audio.save()
        tags = ID3({repr(file_path)})
    tags.delall("TCOM")
    tags.add(TCOM(encoding=3, text=[{repr(playlist_name)}]))
    tags.delall("TRCK")
    tags.add(TRCK(encoding=3, text=["{position}"]))
    tags.delall("TCMP")
    tags.add(TCMP(encoding=3, text=["1"]))
    tags.save()
except Exception as e:
    print(str(e), file=sys.stderr)
    sys.exit(1)
'''
        try:
            result = subprocess.run(
                [sys.executable, '-c', script],
                timeout=5,
                capture_output=True,
                text=True
            )
            return result.returncode == 0
        except subprocess.TimeoutExpired:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(update_one_file, item) for item in work_items]
        for future in as_completed(futures):
            if future.result():
                updated += 1

    if updated > 0:
        console.print(f"[green]✓ Updated metadata on {updated} files[/green]")


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


@cli.command(name='nts-import')
@click.argument('nts_url')
@click.option('--dry-run', is_flag=True, help='Preview without creating playlist')
@click.option('--prefix', default='NTS: ', help='Playlist name prefix (default: "NTS: ")')
def nts_import(nts_url, dry_run, prefix):
    """Import NTS show tracklist to Spotify playlist.

    Fetches an NTS radio show tracklist and creates a matching Spotify playlist.
    Searches for each track on Spotify and adds all matches to a new playlist.

    \b
    Example:
        musicdiff nts-import "https://www.nts.live/shows/covco/episodes/..."
        musicdiff nts-import "URL" --dry-run
        musicdiff nts-import "URL" --prefix "NTS Radio: "
    """
    from musicdiff.nts import NTSClient
    from rich.table import Table

    console.print()

    # 1. Fetch NTS episode
    console.print("[bold cyan]Fetching NTS episode...[/bold cyan]")

    try:
        nts_client = NTSClient()
        episode = nts_client.get_episode_from_url(nts_url)
    except ValueError as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗ Failed to fetch episode: {e}[/red]")
        sys.exit(1)

    console.print(f"[green]✓[/green] Episode: {episode.name}")
    console.print(f"[dim]  Broadcast: {episode.broadcast_date}[/dim]")
    console.print(f"[dim]  Tracks: {len(episode.tracklist)}[/dim]\n")

    if not episode.tracklist:
        console.print("[yellow]⚠ No tracks found in this episode[/yellow]")
        return

    # 2. Authenticate with Spotify
    console.print("[bold cyan]Connecting to Spotify...[/bold cyan]")
    try:
        spotify_client = get_spotify_client()
        console.print("[green]✓[/green] Connected to Spotify\n")
    except SystemExit:
        return

    # 3. Search tracks on Spotify with progress bar
    console.print("[bold cyan]Searching tracks on Spotify...[/bold cyan]")

    matched = []
    skipped = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        console=console
    ) as progress:
        task = progress.add_task("[cyan]Matching tracks...", total=len(episode.tracklist))

        for track in episode.tracklist:
            uri = spotify_client.search_track_uri(track.artist, track.title)

            if uri:
                matched.append({'track': track, 'uri': uri})
            else:
                skipped.append(track)

            progress.update(task, advance=1)

    # 4. Display summary
    console.print()
    total = len(episode.tracklist)
    match_rate = (len(matched) / total * 100) if total > 0 else 0

    console.print("[bold]Results:[/bold]")
    console.print(f"  Matched: [green]{len(matched)}[/green]/{total} tracks ([green]{match_rate:.1f}%[/green])")
    console.print(f"  Skipped: [yellow]{len(skipped)}[/yellow] tracks")

    # Show skipped tracks table
    if skipped:
        console.print("\n[yellow]Skipped Tracks:[/yellow]")
        table = Table(show_header=True, header_style="bold yellow")
        table.add_column("Artist", style="dim", no_wrap=False)
        table.add_column("Title", no_wrap=False)

        for track in skipped[:10]:  # Show first 10
            table.add_row(track.artist, track.title)

        if len(skipped) > 10:
            table.add_row("...", f"({len(skipped)-10} more)")

        console.print(table)

    # 5. Create playlist (if not dry-run)
    console.print()

    if dry_run:
        console.print(f"[yellow]{Icons.SEARCH} Dry run - no playlist created[/yellow]")
        return

    if not matched:
        console.print("[red]✗ No tracks found on Spotify - cannot create playlist[/red]")
        sys.exit(1)

    # Create the playlist
    playlist_name = f"{prefix}{episode.name}"
    console.print(f"[bold cyan]Creating playlist: {playlist_name}[/bold cyan]")

    try:
        playlist_id = spotify_client.create_playlist(
            name=playlist_name,
            description=f"Imported from NTS Live - {episode.broadcast_date}",
            public=False
        )

        # Add tracks
        track_uris = [m['uri'] for m in matched]
        spotify_client.add_tracks_to_playlist(playlist_id, track_uris)

        console.print(f"[bold green]✓ Playlist created successfully![/bold green]")
        console.print(f"[dim]  {len(matched)} tracks added[/dim]")
        console.print(f"[dim]  https://open.spotify.com/playlist/{playlist_id}[/dim]")

    except Exception as e:
        console.print(f"[red]✗ Failed to create playlist: {e}[/red]")
        sys.exit(1)


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()
