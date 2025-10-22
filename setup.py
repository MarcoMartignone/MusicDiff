#!/usr/bin/env python3
"""
MusicDiff Interactive Setup Wizard

This script guides you through setting up MusicDiff with step-by-step
instructions for getting API credentials from Spotify and Apple Music.
"""

import os
import sys
import time
import webbrowser
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich.progress import Progress, SpinnerColumn, TextColumn

console = Console()


def clear_screen():
    """Clear the terminal screen."""
    os.system('clear' if os.name != 'nt' else 'cls')


def show_welcome():
    """Show welcome screen."""
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


def choose_platforms():
    """Let user choose which platforms to set up."""
    clear_screen()
    console.print()
    console.print("[bold]Which music platforms do you use?[/bold]")
    console.print()
    console.print("1. [green]Spotify only[/green] (easiest, free)")
    console.print("2. [cyan]Spotify + Apple Music[/cyan] (requires Apple Developer account)")
    console.print()

    choice = Prompt.ask(
        "Choose option",
        choices=["1", "2"],
        default="1"
    )

    return {
        'spotify': True,
        'apple': choice == "2"
    }


def setup_spotify():
    """Guide user through Spotify setup."""
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold green]📗 Spotify Setup - Step 1 of 3[/bold green]\n\n"
        "We need to create a Spotify app to get API credentials.\n"
        "Don't worry - this is free and takes 2 minutes!",
        border_style="green"
    ))
    console.print()

    # Step 1: Open browser
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

    # Step 2: Instructions for creating app
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

    # Step 3: Get credentials
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

    # Collect credentials
    client_id = Prompt.ask("[bold]Enter your Spotify Client ID[/bold]")
    client_secret = Prompt.ask("[bold]Enter your Spotify Client Secret[/bold]", password=True)

    # Ask about redirect URI
    console.print()
    use_https = Confirm.ask(
        "Did you use [cyan]https://[/cyan]localhost:8888/callback (instead of http)?",
        default=True
    )
    redirect_uri = "https://localhost:8888/callback" if use_https else "http://localhost:8888/callback"

    return {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri
    }


def test_spotify_credentials(client_id, client_secret, redirect_uri):
    """Test Spotify credentials."""
    console.print()
    console.print("[bold]Testing Spotify credentials...[/bold]")

    try:
        # Set environment variables temporarily
        os.environ['SPOTIFY_CLIENT_ID'] = client_id
        os.environ['SPOTIFY_CLIENT_SECRET'] = client_secret
        os.environ['SPOTIFY_REDIRECT_URI'] = redirect_uri

        # Import and test
        from musicdiff.spotify import SpotifyClient

        with Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]Authenticating with Spotify..."),
            console=console
        ) as progress:
            progress.add_task("auth", total=None)

            client = SpotifyClient(client_id, client_secret, redirect_uri)
            success = client.authenticate()

        if success:
            user = client.sp.current_user()
            console.print(f"[green]✓ Successfully authenticated as {user['display_name']}![/green]")
            return True
        else:
            console.print("[red]✗ Authentication failed[/red]")
            return False

    except Exception as e:
        console.print(f"[red]✗ Error: {e}[/red]")
        return False


def setup_apple():
    """Guide user through Apple Music setup."""
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

    if not Confirm.ask("Do you have an Apple Developer account?", default=False):
        console.print()
        console.print("[yellow]Skipping Apple Music setup.[/yellow]")
        console.print("You can run this wizard again later to add Apple Music.")
        time.sleep(2)
        return None

    # Step 1: Create MusicKit Identifier
    clear_screen()
    console.print()
    console.print(Panel.fit(
        "[bold red]📕 Apple Music - Step 1 of 4[/bold red]\n\n"
        "Create a MusicKit Identifier",
        border_style="red"
    ))
    console.print()

    if Confirm.ask("Open Apple Developer portal?", default=True):
        console.print("Opening Apple Developer...")
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

    # Get Key ID
    console.print("After downloading, you should see a [bold]Key ID[/bold] (10 characters)")
    key_id = Prompt.ask("Enter your Apple Music Key ID")

    # Get Team ID
    console.print()
    console.print("Find your [bold]Team ID[/bold]:")
    console.print("  • Go to https://developer.apple.com/account")
    console.print("  • Look in the membership section (10 characters)")
    team_id = Prompt.ask("Enter your Apple Team ID")

    # Get .p8 file path
    console.print()
    console.print("Locate your downloaded [bold].p8 file[/bold]")
    console.print("(probably in your Downloads folder)")

    while True:
        p8_path = Prompt.ask("Enter the full path to your .p8 file")
        p8_path = os.path.expanduser(p8_path)

        if os.path.exists(p8_path):
            # Copy to config directory
            config_dir = Path.home() / 'Documents' / 'MusicDiff' / '.musicdiff'
            config_dir.mkdir(parents=True, exist_ok=True)

            import shutil
            dest_path = config_dir / 'apple_music_key.p8'
            shutil.copy(p8_path, dest_path)
            console.print(f"[green]✓ Copied key to {dest_path}[/green]")
            break
        else:
            console.print(f"[red]File not found: {p8_path}[/red]")
            console.print("Try dragging the file into the terminal, or enter the full path")

    # Step 4: Get User Token
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

    has_token = Confirm.ask("Do you have a user token now?", default=False)

    if has_token:
        user_token = Prompt.ask("Enter your Apple Music user token", password=True)
    else:
        console.print()
        console.print("[yellow]No problem! You can add the user token later.[/yellow]")
        console.print("Just run: export APPLE_USER_TOKEN='your_token'")
        user_token = None

    return {
        'team_id': team_id,
        'key_id': key_id,
        'private_key_path': str(dest_path),
        'user_token': user_token
    }


def save_credentials(spotify_creds, apple_creds):
    """Save credentials to .env file."""
    env_file = Path.home() / 'Documents' / 'MusicDiff' / '.env'

    console.print()
    console.print("[bold]Saving credentials...[/bold]")

    with open(env_file, 'w') as f:
        f.write("# MusicDiff Environment Variables\n")
        f.write(f"# Generated on {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write("\n")

        # Spotify
        f.write("# Spotify Credentials\n")
        f.write(f"export SPOTIFY_CLIENT_ID=\"{spotify_creds['client_id']}\"\n")
        f.write(f"export SPOTIFY_CLIENT_SECRET=\"{spotify_creds['client_secret']}\"\n")
        f.write(f"export SPOTIFY_REDIRECT_URI=\"{spotify_creds['redirect_uri']}\"\n")
        f.write("\n")

        # Apple Music
        if apple_creds:
            f.write("# Apple Music Credentials\n")
            f.write(f"export APPLE_TEAM_ID=\"{apple_creds['team_id']}\"\n")
            f.write(f"export APPLE_KEY_ID=\"{apple_creds['key_id']}\"\n")
            f.write(f"export APPLE_PRIVATE_KEY_PATH=\"{apple_creds['private_key_path']}\"\n")
            if apple_creds.get('user_token'):
                f.write(f"export APPLE_USER_TOKEN=\"{apple_creds['user_token']}\"\n")
            else:
                f.write("# export APPLE_USER_TOKEN=\"\"  # Add this later\n")
        else:
            f.write("# Apple Music - Not configured\n")
            f.write("# export APPLE_TEAM_ID=\"\"\n")
            f.write("# export APPLE_KEY_ID=\"\"\n")
            f.write("# export APPLE_PRIVATE_KEY_PATH=\"\"\n")
            f.write("# export APPLE_USER_TOKEN=\"\"\n")

    console.print(f"[green]✓ Credentials saved to {env_file}[/green]")
    return env_file


def show_completion(env_file, has_apple):
    """Show completion screen with next steps."""
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
    if has_apple:
        console.print("  [green]✓[/green] Apple Music API credentials")
    console.print(f"  [green]✓[/green] Configuration saved to {env_file}")
    console.print()

    console.print("[bold]Next steps:[/bold]")
    console.print()
    console.print("1. Load your credentials:")
    console.print(f"   [cyan]source {env_file}[/cyan]")
    console.print()
    console.print("2. Activate the virtual environment:")
    console.print("   [cyan]source venv/bin/activate[/cyan]")
    console.print()
    console.print("3. Initialize MusicDiff:")
    console.print("   [cyan]musicdiff init[/cyan]")
    console.print()
    console.print("4. Start syncing!")
    console.print("   [cyan]musicdiff sync[/cyan]")
    console.print()

    console.print("[dim]Tip: Add 'source ~/Documents/MusicDiff/.env' to your ~/.zshrc or ~/.bashrc[/dim]")
    console.print("[dim]to automatically load credentials in new terminal sessions.[/dim]")
    console.print()


def main():
    """Main setup wizard."""
    try:
        # Welcome
        show_welcome()

        # Choose platforms
        platforms = choose_platforms()

        # Setup Spotify
        spotify_creds = setup_spotify()

        # Test Spotify credentials
        if not test_spotify_credentials(
            spotify_creds['client_id'],
            spotify_creds['client_secret'],
            spotify_creds['redirect_uri']
        ):
            console.print()
            if not Confirm.ask("Spotify authentication failed. Continue anyway?", default=False):
                console.print("[red]Setup cancelled.[/red]")
                return

        # Setup Apple Music (if requested)
        apple_creds = None
        if platforms['apple']:
            apple_creds = setup_apple()

        # Save credentials
        env_file = save_credentials(spotify_creds, apple_creds)

        # Show completion
        show_completion(env_file, apple_creds is not None)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]Setup cancelled by user.[/yellow]")
        sys.exit(1)
    except Exception as e:
        console.print(f"\n\n[red]Error during setup: {e}[/red]")
        import traceback
        console.print(traceback.format_exc())
        sys.exit(1)


if __name__ == '__main__':
    main()
