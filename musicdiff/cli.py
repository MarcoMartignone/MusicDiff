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
from musicdiff.apple import AppleMusicClient
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


def get_apple_client() -> AppleMusicClient:
    """Get authenticated Apple Music client."""
    # Get credentials from environment
    team_id = os.environ.get('APPLE_TEAM_ID')
    key_id = os.environ.get('APPLE_KEY_ID')
    private_key_path = os.environ.get('APPLE_PRIVATE_KEY_PATH')
    user_token = os.environ.get('APPLE_USER_TOKEN')

    if not all([team_id, key_id, private_key_path]):
        console.print("[red]Error: Apple Music credentials not found.[/red]")
        console.print("Set APPLE_TEAM_ID, APPLE_KEY_ID, and APPLE_PRIVATE_KEY_PATH")
        console.print("Or run 'musicdiff init' to configure")
        sys.exit(1)

    # Generate developer token
    try:
        dev_token = AppleMusicClient.generate_developer_token(
            team_id=team_id,
            key_id=key_id,
            private_key_path=private_key_path
        )
    except Exception as e:
        console.print(f"[red]Error generating Apple Music developer token: {e}[/red]")
        sys.exit(1)

    client = AppleMusicClient(developer_token=dev_token)

    # Set user token if available
    if user_token:
        if not client.authenticate_user(user_token):
            console.print("[red]Error: Apple Music user token invalid[/red]")
            sys.exit(1)
    else:
        console.print("[yellow]Warning: No Apple Music user token set.[/yellow]")
        console.print("Set APPLE_USER_TOKEN environment variable")

    return client


def get_sync_engine() -> SyncEngine:
    """Get initialized sync engine."""
    db = get_database()
    spotify = get_spotify_client()
    apple = get_apple_client()
    ui = UI()

    return SyncEngine(spotify, apple, db, ui)


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
def setup():
    """Interactive setup wizard - create API credentials and configure MusicDiff.

    This wizard guides you through:
    - Creating Spotify API credentials (free, 5 minutes)
    - Optionally setting up Apple Music (requires Apple Developer account)
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
        "music libraries between Spotify and Apple Music.\n\n"
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
    console.print("2. [cyan]Spotify + Apple Music[/cyan] (requires Apple Developer account)")
    console.print()

    choice = Prompt.ask("Choose option", choices=["1", "2"], default="1")
    setup_apple_music = choice == "2"

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

    # Apple Music Setup
    apple_team_id = None
    apple_key_id = None
    apple_key_path = None
    apple_user_token = None

    if setup_apple_music:
        clear_screen()
        console.print()
        console.print(Panel.fit(
            "[bold red]📕 Apple Music Setup[/bold red]\n\n"
            "[yellow]⚠️  Requirements:[/yellow]\n"
            "• Apple Developer Account ($99/year)\n"
            "• 10-15 minutes for setup\n\n"
            "If you don't have an Apple Developer account,\n"
            "you can skip this and only use Spotify.",
            border_style="red"
        ))
        console.print()

        if Confirm.ask("Do you have an Apple Developer account?", default=False):
            # Step 1: Create MusicKit ID
            clear_screen()
            console.print()
            console.print(Panel.fit(
                "[bold red]📕 Apple Music - Step 1 of 4[/bold red]\n\n"
                "Create a MusicKit Identifier",
                border_style="red"
            ))
            console.print()

            if Confirm.ask("Open Apple Developer portal?", default=True):
                webbrowser.open("https://developer.apple.com/account/resources/identifiers/list/musicId")
                time.sleep(2)

            console.print()
            console.print("1. Click the [cyan bold]'+'[/cyan bold] button")
            console.print("2. Select [cyan bold]'MusicKit Identifier'[/cyan bold]")
            console.print("3. Enter description: [cyan bold]MusicDiff[/cyan bold]")
            console.print("4. Click [cyan bold]'Continue'[/cyan bold] → [cyan bold]'Register'[/cyan bold]")
            console.print()
            console.print("[dim]Press Enter when done...[/dim]")
            input()

            # Step 2: Create Private Key
            clear_screen()
            console.print()
            console.print(Panel.fit(
                "[bold red]📕 Apple Music - Step 2 of 4[/bold red]\n\n"
                "Create a Private Key for MusicKit",
                border_style="red"
            ))
            console.print()

            if Confirm.ask("Open Auth Keys page?", default=True):
                webbrowser.open("https://developer.apple.com/account/resources/authkeys/list")
                time.sleep(2)

            console.print()
            console.print("1. Click the [cyan bold]'+'[/cyan bold] button")
            console.print("2. Name: [cyan bold]MusicDiff Key[/cyan bold]")
            console.print("3. Check [cyan bold]'MusicKit'[/cyan bold]")
            console.print("4. Click [cyan bold]'Continue'[/cyan bold] → [cyan bold]'Register'[/cyan bold]")
            console.print("5. [bold red]Download the .p8 file[/bold red] (you can only download once!)")
            console.print()
            console.print("[dim]Press Enter after downloading the .p8 file...[/dim]")
            input()

            # Step 3: Collect credentials
            clear_screen()
            console.print()
            console.print(Panel.fit(
                "[bold red]📕 Apple Music - Step 3 of 4[/bold red]\n\n"
                "Enter your Apple Music credentials",
                border_style="red"
            ))
            console.print()

            console.print("After downloading, you should see a [bold]Key ID[/bold] (10 characters)")
            apple_key_id = Prompt.ask("Enter your Apple Music Key ID")

            console.print()
            console.print("Find your [bold]Team ID[/bold]:")
            console.print("  • Go to https://developer.apple.com/account")
            console.print("  • Look in the membership section (10 characters)")
            apple_team_id = Prompt.ask("Enter your Apple Team ID")

            console.print()
            console.print("Locate your downloaded [bold].p8 file[/bold]")
            console.print("(probably in your Downloads folder)")

            while True:
                p8_path = Prompt.ask("Enter the full path to your .p8 file")
                p8_path = os.path.expanduser(p8_path)

                if os.path.exists(p8_path):
                    config_dir = get_config_dir()
                    dest_path = config_dir / 'apple_music_key.p8'
                    shutil.copy(p8_path, dest_path)
                    apple_key_path = str(dest_path)
                    console.print(f"[green]✓ Copied key to {dest_path}[/green]")
                    break
                else:
                    console.print(f"[red]File not found: {p8_path}[/red]")

            # Step 4: User Token
            clear_screen()
            console.print()
            console.print(Panel.fit(
                "[bold red]📕 Apple Music - Step 4 of 4[/bold red]\n\n"
                "Get Your User Token",
                border_style="red"
            ))
            console.print()
            console.print("[yellow]Getting an Apple Music user token is complex.[/yellow]")
            console.print()
            console.print("Quick method (requires Chrome DevTools):")
            console.print("1. Open https://music.apple.com in your browser")
            console.print("2. Make sure you're logged in")
            console.print("3. Open DevTools (F12 or Cmd+Option+I)")
            console.print("4. Go to the Console tab")
            console.print("5. Paste: [cyan]MusicKit.getInstance().musicUserToken[/cyan]")
            console.print("6. Press Enter and copy the token (starts with 'eyJ...')")
            console.print()

            if Confirm.ask("Do you have a user token now?", default=False):
                apple_user_token = Prompt.ask("Enter your Apple Music user token", password=True)
            else:
                console.print()
                console.print("[yellow]No problem! You can add the user token later.[/yellow]")
                console.print("Just add it to your .env file")

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

        if apple_team_id:
            f.write("# Apple Music Credentials\n")
            f.write(f"export APPLE_TEAM_ID=\"{apple_team_id}\"\n")
            f.write(f"export APPLE_KEY_ID=\"{apple_key_id}\"\n")
            f.write(f"export APPLE_PRIVATE_KEY_PATH=\"{apple_key_path}\"\n")
            if apple_user_token:
                f.write(f"export APPLE_USER_TOKEN=\"{apple_user_token}\"\n")
            else:
                f.write("# export APPLE_USER_TOKEN=\"\"  # Add this later\n")
        else:
            f.write("# Apple Music - Not configured\n")

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
    if apple_team_id:
        console.print("  [green]✓[/green] Apple Music API credentials")
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

    # Apple Music
    if all([os.environ.get('APPLE_TEAM_ID'), os.environ.get('APPLE_KEY_ID'),
            os.environ.get('APPLE_PRIVATE_KEY_PATH')]):
        console.print("✓ Apple Music credentials found")
    else:
        console.print("[yellow]⚠ Apple Music credentials not set[/yellow]")
        console.print("  Set APPLE_TEAM_ID, APPLE_KEY_ID, and APPLE_PRIVATE_KEY_PATH")

    console.print("\n[green bold]✓ Initialization complete![/green bold]")
    console.print("\nNext steps:")
    console.print("  1. Set all required environment variables")
    console.print("  2. Run 'musicdiff status' to check your setup")
    console.print("  3. Run 'musicdiff sync' to start syncing")


@cli.command()
def status():
    """Show current sync status and pending changes."""
    console.print("[bold]MusicDiff Status[/bold]\n")

    # Check if initialized
    db_path = get_config_dir() / 'musicdiff.db'
    if not db_path.exists():
        console.print("[yellow]MusicDiff not initialized. Run 'musicdiff init' first.[/yellow]")
        return

    db = Database(str(db_path))

    # Get last sync info
    logs = db.get_sync_history(limit=1)
    if logs:
        last_sync = logs[0]
        console.print(f"Last Sync: {last_sync['timestamp']}")
        console.print(f"  Status: {last_sync['status']}")
        console.print(f"  Changes: {last_sync['changes']}")
        console.print(f"  Conflicts: {last_sync['conflicts']}")
    else:
        console.print("Last Sync: Never")

    # Get unresolved conflicts
    conflicts = db.get_unresolved_conflicts()
    if conflicts:
        console.print(f"\n[yellow]Unresolved Conflicts: {len(conflicts)}[/yellow]")
        console.print("Run 'musicdiff resolve' to handle conflicts")

    # Check daemon status
    try:
        sync_engine = get_sync_engine()
        daemon = SyncDaemon(sync_engine)
        status = daemon.status()

        console.print(f"\nDaemon: {'[green]Running[/green]' if status['running'] else '[dim]Not running[/dim]'}")
        if status['running']:
            console.print(f"  PID: {status['pid']}")
            console.print(f"  Uptime: {status['uptime']}")
            console.print(f"  Interval: {status['interval']}s")
    except Exception:
        pass


@cli.command()
@click.option('--spotify-only', is_flag=True, help='Fetch from Spotify only')
@click.option('--apple-only', is_flag=True, help='Fetch from Apple Music only')
def fetch(spotify_only, apple_only):
    """Fetch latest library state from both platforms."""
    console.print("[bold cyan]Fetching library data...[/bold cyan]\n")

    if not spotify_only:
        console.print("Fetching from Spotify...")
        spotify = get_spotify_client()
        playlists = spotify.fetch_playlists()
        liked = spotify.fetch_liked_songs()
        albums = spotify.fetch_saved_albums()
        console.print(f"  ✓ {len(playlists)} playlists, {len(liked)} liked songs, {len(albums)} albums")

    if not apple_only:
        console.print("Fetching from Apple Music...")
        apple = get_apple_client()
        playlists = apple.fetch_library_playlists()
        liked = apple.fetch_library_songs()
        albums = apple.fetch_library_albums()
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
    if dry_run:
        console.print("[dim]DRY RUN - No changes will be applied[/dim]\n")

    # Determine sync mode
    if conflicts_only:
        mode = SyncMode.CONFLICTS_ONLY
    elif auto:
        mode = SyncMode.AUTO
    elif dry_run:
        mode = SyncMode.DRY_RUN
    else:
        mode = SyncMode.INTERACTIVE

    # Get sync engine and run sync
    sync_engine = get_sync_engine()
    result = sync_engine.sync(mode=mode)

    # Result is already displayed by sync engine UI
    console.print()  # Add spacing


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
        console.print(f"  Changes: {entry['changes']}, Conflicts: {entry['conflicts']}")

        if verbose and entry['details']:
            import json
            details = json.loads(entry['details'])
            console.print(f"  Duration: {details.get('duration', 'N/A')}s")
            if details.get('failed_changes'):
                console.print(f"  Failed: {details['failed_changes']}")
        console.print()


@cli.command()
def resolve():
    """Resume conflict resolution for pending conflicts."""
    console.print("[bold]Resolving conflicts...[/bold]\n")

    # Use conflicts-only mode
    sync_engine = get_sync_engine()
    result = sync_engine.sync(mode=SyncMode.CONFLICTS_ONLY)

    console.print(f"\n{result.summary()}")


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
            console.print("\nApple Music:")
            console.print("  APPLE_TEAM_ID")
            console.print("  APPLE_KEY_ID")
            console.print("  APPLE_PRIVATE_KEY_PATH")
            console.print("  APPLE_USER_TOKEN")
        return

    # TODO: Implement config get/set with YAML
    console.print("[yellow]Config get/set not yet implemented[/yellow]")
    console.print("Use environment variables for now")


def main():
    """Entry point for the CLI."""
    cli(obj={})


if __name__ == '__main__':
    main()
