"""
Deemix downloader integration for MusicDiff.

This module provides functionality to download tracks from Deezer using
the deemix CLI as a subprocess.
"""

import os
import shutil
import subprocess
import time
import glob as glob_module
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, List, Optional, Dict

try:
    from mutagen.mp3 import MP3
    from mutagen.id3 import ID3, TCMP, TCOM, TRCK, ID3NoHeaderError
    MUTAGEN_AVAILABLE = True
except ImportError:
    MUTAGEN_AVAILABLE = False

from .database import Database


# Custom exceptions
class DeemixError(Exception):
    """Base exception for deemix-related errors."""
    pass


class DeemixNotFoundError(DeemixError):
    """Raised when deemix CLI is not installed or accessible."""
    pass


class DeemixAuthError(DeemixError):
    """Raised when ARL authentication fails."""
    pass


class TrackNotFoundError(DeemixError):
    """Raised when a track is not available on Deezer."""
    pass


class DownloadError(DeemixError):
    """Raised when a download fails."""

    def __init__(self, message: str, track_id: str = None, attempts: int = 0):
        self.track_id = track_id
        self.attempts = attempts
        super().__init__(message)


@dataclass
class DownloadResult:
    """Result of a single track download attempt."""
    deezer_id: str
    success: bool
    file_path: Optional[str] = None
    error: Optional[str] = None
    duration_seconds: float = 0.0


@dataclass
class DownloadStats:
    """Statistics for a batch download operation."""
    total: int = 0
    completed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: List[str] = field(default_factory=list)


class DeemixDownloader:
    """Downloads tracks from Deezer using deemix CLI."""

    # Retry configuration
    MAX_RETRY_ATTEMPTS = 3
    RETRY_DELAYS = [5, 15, 30]  # Seconds between retries

    def __init__(
        self,
        db: Database,
        arl_token: str,
        download_path: str,
        quality: str = '320',
        deemix_path: str = None
    ):
        """Initialize the downloader.

        Args:
            db: Database instance for tracking downloads
            arl_token: Deezer ARL authentication token
            download_path: Directory to save downloaded files
            quality: Audio quality (128, 320, flac)
            deemix_path: Optional path to deemix CLI executable
        """
        self.db = db
        self.arl_token = arl_token
        self.download_path = Path(download_path)
        self.quality = self._validate_quality(quality)
        self.deemix_path = deemix_path or self._find_deemix()
        # Use deemix's default config folder location
        self._config_folder = self._get_deemix_config_folder()

    def set_download_path(self, path: str) -> None:
        """Set the download path for subsequent downloads.

        Args:
            path: Directory to save downloaded files
        """
        self.download_path = Path(path)
        self.download_path.mkdir(parents=True, exist_ok=True)

    @staticmethod
    def _validate_quality(quality: str) -> str:
        """Validate and normalize quality setting."""
        valid = {'128', '320', 'flac'}
        quality = quality.lower().strip()
        if quality not in valid:
            raise ValueError(f"Invalid quality '{quality}'. Must be one of: {', '.join(valid)}")
        return quality

    @staticmethod
    def _get_deemix_config_folder() -> Path:
        """Get deemix's default config folder location.

        Matches the logic in deemix's utils.getConfigFolder()
        """
        import platform
        system = platform.system()

        if system == 'Darwin':  # macOS
            return Path.home() / 'Library' / 'Application Support' / 'deemix'
        elif system == 'Windows':
            appdata = os.environ.get('APPDATA', '')
            if appdata:
                return Path(appdata) / 'deemix'
            return Path.home() / 'deemix'
        else:  # Linux and others
            xdg_config = os.environ.get('XDG_CONFIG_HOME', '')
            if xdg_config:
                return Path(xdg_config) / 'deemix'
            return Path.home() / '.config' / 'deemix'

    def _find_deemix(self) -> str:
        """Find deemix CLI executable.

        Returns:
            Path to deemix executable

        Raises:
            DeemixNotFoundError: If deemix is not found
        """
        # Check environment variable first
        env_path = os.environ.get('MUSICDIFF_DEEMIX_PATH')
        if env_path and Path(env_path).exists():
            return env_path

        # Check common locations
        locations = [
            shutil.which('deemix'),  # System PATH
            shutil.which('deemix-cli'),  # Alternative name
            # Local development paths (built output)
            Path.home() / 'Documents' / 'deemix' / 'packages' / 'cli' / 'dist' / 'main.cjs',
            Path.home() / 'Documents' / 'deemix' / 'packages' / 'cli' / 'dist' / 'main.js',
        ]

        for loc in locations:
            if loc:
                path = Path(loc) if isinstance(loc, str) else loc
                if path.exists():
                    return str(path)

        raise DeemixNotFoundError(
            "deemix CLI not found. Please install it:\n"
            "  cd ~/Documents/deemix && pnpm install && pnpm build\n"
            "Or set MUSICDIFF_DEEMIX_PATH in your environment."
        )

    def check_deemix_installed(self) -> bool:
        """Check if deemix CLI is installed and accessible.

        Returns:
            True if deemix is available, False otherwise
        """
        try:
            self._find_deemix()
            return True
        except DeemixNotFoundError:
            return False

    def setup_arl_file(self) -> None:
        """Write ARL token to deemix config folder.

        Deemix reads the ARL from a .arl file in its config directory.
        """
        if not self.arl_token:
            raise DeemixAuthError("No ARL token provided. Run 'musicdiff setup' to configure.")

        # Create config folder if needed
        self._config_folder.mkdir(parents=True, exist_ok=True)

        # Write ARL file
        arl_file = self._config_folder / '.arl'
        arl_file.write_text(self.arl_token.strip())

    def _build_command(self, url: str) -> List[str]:
        """Build the deemix command for a given URL.

        Args:
            url: Deezer track URL

        Returns:
            Command as list of strings
        """
        # Ensure download directory exists
        self.download_path.mkdir(parents=True, exist_ok=True)

        # Check if deemix_path is a .js or .cjs file (needs node to run)
        if self.deemix_path.endswith('.js') or self.deemix_path.endswith('.cjs'):
            cmd = ['node', self.deemix_path]
        else:
            cmd = [self.deemix_path]

        cmd.extend([
            url,
            '-p', str(self.download_path),
            '-b', self.quality,
        ])

        return cmd

    def _format_track_url(self, deezer_id: str) -> str:
        """Format a Deezer track URL from track ID.

        Args:
            deezer_id: Deezer track ID

        Returns:
            Full Deezer track URL
        """
        return f"https://www.deezer.com/track/{deezer_id}"

    def _parse_deemix_output(self, stdout: str, stderr: str) -> Dict:
        """Parse deemix output for status information.

        Args:
            stdout: Standard output from deemix
            stderr: Standard error from deemix

        Returns:
            Dict with parsed information
        """
        result = {
            'success': False,
            'error': None,
            'file_path': None
        }

        output = stdout + stderr

        # Check for common error patterns
        if 'not logged in' in output.lower() or 'invalid arl' in output.lower():
            result['error'] = 'Authentication failed. Please update your ARL token.'
        elif 'track not found' in output.lower() or 'not available' in output.lower():
            result['error'] = 'Track not available on Deezer'
        elif 'rate limit' in output.lower():
            result['error'] = 'Rate limited by Deezer. Please wait before retrying.'
        elif 'error' in output.lower() and 'download complete' not in output.lower():
            # Extract error message (but ignore if download completed)
            for line in output.split('\n'):
                if 'error' in line.lower():
                    result['error'] = line.strip()
                    break
            if not result['error']:
                result['error'] = 'Unknown error during download'
        else:
            # Assume success if no errors detected
            result['success'] = True

        return result

    def _find_downloaded_file(self, artist: str, title: str) -> Optional[str]:
        """Find a recently downloaded file matching artist and title.

        Args:
            artist: Track artist
            title: Track title

        Returns:
            Path to the file if found, None otherwise
        """
        # Clean up text for filename matching
        def clean(s):
            return ''.join(c for c in s if c.isalnum() or c in ' -_').strip().lower()

        search_pattern = str(self.download_path / '**' / '*.mp3')
        files = glob_module.glob(search_pattern, recursive=True)

        # Sort by modification time (newest first)
        files.sort(key=lambda f: os.path.getmtime(f), reverse=True)

        # Get primary artist (first before comma) and clean both
        primary_artist = artist.split(',')[0].strip() if artist else ''
        clean_artist = clean(primary_artist)
        clean_title = clean(title)

        # Only check files modified in the last 5 minutes (recently downloaded)
        now = time.time()
        recent_files = [f for f in files if now - os.path.getmtime(f) < 300]

        for f in recent_files[:100]:
            filename = clean(Path(f).stem)

            # Method 1: Both artist and title found in filename
            if clean_artist[:10] in filename and clean_title[:10] in filename:
                return f

            # Method 2: First word of artist + significant title words
            artist_first = clean_artist.split()[0] if clean_artist else ''
            title_words = [w for w in clean_title.split() if len(w) > 3]
            if artist_first and filename.startswith(artist_first):
                matches = sum(1 for w in title_words if w in filename)
                if matches >= len(title_words) * 0.5:
                    return f

        # No fallback - if we can't match properly, don't store a wrong path
        return None

    def download_track(self, deezer_id: str) -> DownloadResult:
        """Download a single track.

        Args:
            deezer_id: Deezer track ID

        Returns:
            DownloadResult with success/failure info
        """
        start_time = time.time()
        url = self._format_track_url(deezer_id)

        try:
            # Ensure ARL is set up
            self.setup_arl_file()

            # Build and run command
            cmd = self._build_command(url)

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=300,  # 5 minute timeout
            )

            duration = time.time() - start_time
            parsed = self._parse_deemix_output(result.stdout, result.stderr)

            if result.returncode == 0 and parsed['success']:
                return DownloadResult(
                    deezer_id=deezer_id,
                    success=True,
                    file_path=parsed.get('file_path'),
                    duration_seconds=duration
                )
            else:
                return DownloadResult(
                    deezer_id=deezer_id,
                    success=False,
                    error=parsed.get('error', f'Exit code: {result.returncode}'),
                    duration_seconds=duration
                )

        except subprocess.TimeoutExpired:
            duration = time.time() - start_time
            return DownloadResult(
                deezer_id=deezer_id,
                success=False,
                error='Download timed out after 5 minutes',
                duration_seconds=duration
            )
        except FileNotFoundError:
            raise DeemixNotFoundError(f"deemix not found at: {self.deemix_path}")
        except Exception as e:
            duration = time.time() - start_time
            return DownloadResult(
                deezer_id=deezer_id,
                success=False,
                error=str(e),
                duration_seconds=duration
            )

    def download_track_with_retry(self, deezer_id: str) -> DownloadResult:
        """Download a track with automatic retry on failure.

        Args:
            deezer_id: Deezer track ID

        Returns:
            DownloadResult from final attempt
        """
        last_result = None

        for attempt in range(self.MAX_RETRY_ATTEMPTS):
            # Update database status
            self.db.update_download_status(deezer_id, 'downloading')
            self.db.increment_download_attempts(deezer_id)

            result = self.download_track(deezer_id)
            last_result = result

            if result.success:
                self.db.mark_download_complete(deezer_id, result.file_path or '')
                return result

            # Check if error is retryable
            if result.error and any(x in result.error.lower() for x in ['rate limit', 'timeout', 'network']):
                if attempt < self.MAX_RETRY_ATTEMPTS - 1:
                    time.sleep(self.RETRY_DELAYS[attempt])
                    continue

            # Non-retryable error or max attempts reached
            break

        # Final failure
        self.db.update_download_status(
            deezer_id,
            'failed',
            error_message=last_result.error if last_result else 'Unknown error'
        )
        return last_result

    def download_tracks(
        self,
        tracks: List[Dict],
        progress_callback: Callable[[int, int, Dict], None] = None,
        playlist_name: str = None,
        apply_playlist_tags: bool = True
    ) -> DownloadStats:
        """Download multiple tracks.

        Args:
            tracks: List of track dicts with at least 'deezer_id' key
            progress_callback: Optional callback(current, total, track) for progress updates
            playlist_name: Name of playlist (used for metadata tagging)
            apply_playlist_tags: Whether to apply playlist metadata to downloaded files

        Returns:
            DownloadStats with results summary
        """
        stats = DownloadStats(total=len(tracks))

        for i, track in enumerate(tracks):
            deezer_id = track.get('deezer_id')
            if not deezer_id:
                stats.skipped += 1
                continue

            # Check if already completed
            existing = self.db.get_download_by_deezer_id(deezer_id)
            if existing and existing.get('status') == 'completed':
                file_path = existing.get('file_path')
                # If file_path is set but file doesn't exist, reset and re-download
                if file_path and not Path(file_path).exists():
                    self.db.update_download_status(deezer_id, 'pending')
                    # Continue to download below
                else:
                    # File exists or no path stored - skip
                    stats.skipped += 1
                    if progress_callback:
                        progress_callback(i + 1, len(tracks), track)
                    continue

            # Report progress
            if progress_callback:
                progress_callback(i + 1, len(tracks), track)

            # Download with retry
            result = self.download_track_with_retry(deezer_id)

            if result.success:
                stats.completed += 1

                # Find the downloaded file
                artist = track.get('artist', '')
                title = track.get('title', '')
                file_path = result.file_path or self._find_downloaded_file(artist, title)

                # Always store the file path if found
                if file_path:
                    self.db.update_download_status(deezer_id, 'completed', file_path=file_path)

                # Apply playlist metadata if enabled
                if apply_playlist_tags and MUTAGEN_AVAILABLE and file_path:
                    # Get playlist name from track or parameter
                    plist_name = playlist_name
                    if not plist_name and track.get('playlist_spotify_id'):
                        # Look up playlist name from database
                        plist = self.db.get_playlist_selection(track.get('playlist_spotify_id'))
                        if plist:
                            plist_name = plist.get('name', '')

                    if plist_name:
                        # Use track's position if set, otherwise use batch index
                        position = track.get('_playlist_position', i + 1)
                        apply_playlist_metadata(
                            file_path=file_path,
                            playlist_name=plist_name,
                            playlist_position=position,
                            mark_as_compilation=True
                        )
            else:
                stats.failed += 1
                stats.errors.append(f"{track.get('artist', 'Unknown')} - {track.get('title', 'Unknown')}: {result.error}")

        return stats

    def get_pending_tracks(self, playlist_spotify_id: str = None) -> List[Dict]:
        """Get tracks pending download.

        Args:
            playlist_spotify_id: Filter by playlist (optional)

        Returns:
            List of pending track records
        """
        return self.db.get_pending_downloads(playlist_spotify_id)

    def retry_failed(self, max_attempts: int = 3) -> DownloadStats:
        """Retry all failed downloads.

        Args:
            max_attempts: Only retry tracks with fewer than this many attempts

        Returns:
            DownloadStats with retry results
        """
        failed = self.db.get_failed_downloads(max_attempts)
        return self.download_tracks(failed)

    def queue_tracks_from_playlist(
        self,
        spotify_playlist_id: str,
        tracks: List[Dict],
        quality: str = None
    ) -> int:
        """Queue tracks from a playlist for download.

        Args:
            spotify_playlist_id: Spotify playlist ID
            tracks: List of track dicts with deezer_id, spotify_id, isrc, title, artist
            quality: Override quality for these tracks

        Returns:
            Number of new tracks queued
        """
        queued = 0
        quality = quality or self.quality

        for track in tracks:
            deezer_id = track.get('deezer_id')
            if not deezer_id:
                continue

            # Check if already in queue
            existing = self.db.get_download_by_deezer_id(deezer_id)
            if existing:
                continue

            # Add to queue
            self.db.add_download_record(
                deezer_id=deezer_id,
                spotify_id=track.get('spotify_id'),
                isrc=track.get('isrc'),
                title=track.get('title', 'Unknown'),
                artist=track.get('artist', 'Unknown'),
                playlist_spotify_id=spotify_playlist_id,
                quality=quality
            )
            queued += 1

        return queued


def get_default_download_path() -> Path:
    """Get the default download path for music files.

    Returns:
        Path to Music/MusicDiff folder
    """
    music_dir = Path.home() / 'Music'
    if not music_dir.exists():
        # Fallback for systems without Music folder
        music_dir = Path.home() / 'Downloads'
    return music_dir / 'MusicDiff'


def apply_playlist_metadata(
    file_path: str,
    playlist_name: str,
    playlist_position: int,
    mark_as_compilation: bool = True
) -> bool:
    """Apply playlist-specific metadata to a downloaded MP3 file.

    Updates the following tags:
    - TCOM (Composer): Set to playlist name
    - TRCK (Track Number): Set to playlist position
    - TCMP (Compilation): Set to 1 if mark_as_compilation is True

    Args:
        file_path: Path to the MP3 file
        playlist_name: Name of the playlist
        playlist_position: Position in the playlist (1-based)
        mark_as_compilation: Whether to mark as compilation

    Returns:
        True if successful, False otherwise
    """
    if not MUTAGEN_AVAILABLE:
        return False

    try:
        # Load existing tags
        try:
            tags = ID3(file_path)
        except ID3NoHeaderError:
            # Create ID3 header if missing
            audio = MP3(file_path)
            audio.add_tags()
            audio.save()
            tags = ID3(file_path)

        # Set composer to playlist name
        tags.delall('TCOM')
        tags.add(TCOM(encoding=3, text=[playlist_name]))

        # Set track number to playlist position
        tags.delall('TRCK')
        tags.add(TRCK(encoding=3, text=[str(playlist_position)]))

        # Mark as compilation
        if mark_as_compilation:
            tags.delall('TCMP')
            tags.add(TCMP(encoding=3, text=['1']))

        tags.save()
        return True

    except Exception:
        return False
