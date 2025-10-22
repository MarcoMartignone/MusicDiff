"""
Daemon mode and scheduled syncs.

See docs/SCHEDULING.md for detailed documentation.
"""

import os
import signal
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Optional
from musicdiff.sync import SyncMode


class SyncDaemon:
    """Manages daemon mode for scheduled syncs."""

    def __init__(self, sync_engine, interval: int = 86400):
        """Initialize daemon.

        Args:
            sync_engine: SyncEngine instance
            interval: Sync interval in seconds (default: 86400 = 24 hours)
        """
        self.sync_engine = sync_engine
        self.interval = interval
        self.running = False

        # Setup paths
        self.config_dir = Path.home() / '.musicdiff'
        self.config_dir.mkdir(parents=True, exist_ok=True)

        self.pid_file = self.config_dir / 'daemon.pid'
        self.log_file = self.config_dir / 'daemon.log'
        self.err_file = self.config_dir / 'daemon.err'

    def start(self, foreground: bool = False):
        """Start the daemon.

        Args:
            foreground: If True, run in foreground (for debugging)
        """
        # Check if already running
        if self.is_running():
            raise RuntimeError("Daemon is already running")

        if foreground:
            self._run_foreground()
        else:
            self._daemonize()

    def _daemonize(self):
        """Fork process and run as daemon.

        This implements proper Unix daemonization with double-fork to prevent
        zombie processes and detach from the controlling terminal.
        """
        # First fork - create child process
        try:
            pid = os.fork()
            if pid > 0:
                # Exit parent process
                sys.exit(0)
        except OSError as e:
            raise RuntimeError(f"First fork failed: {e}")

        # Decouple from parent environment
        os.chdir('/')  # Change working directory to root
        os.setsid()    # Create new session and become session leader
        os.umask(0)    # Clear file creation mask

        # Second fork - prevent process from acquiring a controlling terminal
        try:
            pid = os.fork()
            if pid > 0:
                # Exit first child
                sys.exit(0)
        except OSError as e:
            raise RuntimeError(f"Second fork failed: {e}")

        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        # Redirect stdin to /dev/null
        with open('/dev/null', 'r') as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        # Redirect stdout to log file
        with open(self.log_file, 'a') as log:
            os.dup2(log.fileno(), sys.stdout.fileno())

        # Redirect stderr to error file
        with open(self.err_file, 'a') as err:
            os.dup2(err.fileno(), sys.stderr.fileno())

        # Write PID file
        self._write_pid_file()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

        # Run daemon loop
        self._run()

    def _run_foreground(self):
        """Run daemon in foreground (for debugging)."""
        self._write_pid_file()

        # Setup signal handlers
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

        # Run daemon loop
        self._run()

    def _run(self):
        """Main daemon loop.

        Runs syncs at regular intervals until stopped. Handles errors gracefully
        and logs all activity.
        """
        self.running = True

        # Log startup
        self._log(f"MusicDiff daemon started")
        self._log(f"  Sync interval: {self.interval} seconds ({self.interval / 3600:.1f} hours)")
        self._log(f"  PID: {os.getpid()}")

        while self.running:
            try:
                # Perform sync
                self._log("Starting automatic sync...")
                start_time = time.time()

                result = self.sync_engine.sync(mode=SyncMode.AUTO)

                duration = time.time() - start_time

                # Log result
                if result.success:
                    self._log(f"Sync completed successfully in {duration:.1f}s")
                    self._log(f"  Changes applied: {result.changes_applied}")
                else:
                    self._log(f"Sync partial in {duration:.1f}s")
                    self._log(f"  Changes applied: {result.changes_applied}")
                    self._log(f"  Failed changes: {len(result.failed_changes)}")

                # Log conflicts
                if result.conflicts_count > 0:
                    self._log(f"  Conflicts detected: {result.conflicts_count}")
                    self._log(f"  Run 'musicdiff resolve' to handle conflicts")

                # Log failures if any
                if result.failed_changes:
                    self._log("Failed changes:")
                    for change, error in result.failed_changes[:5]:  # Show first 5
                        self._log(f"  - {change.entity_type} {change.entity_id}: {error}")
                    if len(result.failed_changes) > 5:
                        self._log(f"  ... and {len(result.failed_changes) - 5} more")

            except KeyboardInterrupt:
                # Graceful shutdown on Ctrl+C
                self._log("Received keyboard interrupt")
                self.running = False
                break

            except Exception as e:
                # Log error but continue running
                self._log(f"Sync failed with error: {e}")
                import traceback
                self._log(traceback.format_exc())

            if not self.running:
                break

            # Sleep until next sync
            next_sync = datetime.fromtimestamp(time.time() + self.interval)
            self._log(f"Next sync at {next_sync.strftime('%Y-%m-%d %H:%M:%S')}")

            # Sleep in small increments to allow graceful shutdown
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

        # Cleanup
        self._cleanup()

    def stop(self):
        """Stop the daemon.

        Sends SIGTERM to the daemon process and waits for it to stop gracefully.
        If it doesn't stop within 10 seconds, forcefully kills it.
        """
        pid = self._read_pid()
        if not pid:
            raise RuntimeError("Daemon is not running")

        print(f"Stopping daemon (PID {pid})...")

        # Send SIGTERM for graceful shutdown
        try:
            os.kill(pid, signal.SIGTERM)
        except OSError as e:
            raise RuntimeError(f"Failed to stop daemon: {e}")

        # Wait for daemon to stop (up to 10 seconds)
        for i in range(10):
            if not self.is_running():
                print("Daemon stopped successfully")
                return
            time.sleep(1)

        # Force kill if still running
        print("Daemon did not stop gracefully, forcing...")
        try:
            os.kill(pid, signal.SIGKILL)
            self._remove_pid_file()
            print("Daemon killed")
        except OSError:
            # Process might already be dead
            self._remove_pid_file()

    def status(self) -> dict:
        """Get daemon status.

        Returns:
            Dictionary with daemon status information
        """
        if not self.is_running():
            return {
                'running': False,
                'pid': None,
                'uptime': None
            }

        pid = self._read_pid()

        # Try to get process creation time (Unix-specific)
        try:
            import psutil
            process = psutil.Process(pid)
            create_time = datetime.fromtimestamp(process.create_time())
            uptime = datetime.now() - create_time

            return {
                'running': True,
                'pid': pid,
                'uptime': str(uptime).split('.')[0],  # Remove microseconds
                'interval': self.interval,
                'log_file': str(self.log_file)
            }
        except (ImportError, Exception):
            # psutil not available or other error
            return {
                'running': True,
                'pid': pid,
                'uptime': 'unknown',
                'interval': self.interval,
                'log_file': str(self.log_file)
            }

    def is_running(self) -> bool:
        """Check if daemon is running.

        Returns:
            True if daemon process is running, False otherwise
        """
        pid = self._read_pid()
        if not pid:
            return False

        # Check if process exists by sending signal 0
        try:
            os.kill(pid, 0)
            return True
        except OSError:
            # Process doesn't exist, remove stale PID file
            self._remove_pid_file()
            return False

    def _write_pid_file(self):
        """Write current PID to file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))

    def _read_pid(self) -> Optional[int]:
        """Read PID from file.

        Returns:
            PID as integer, or None if file doesn't exist or is invalid
        """
        if not self.pid_file.exists():
            return None

        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, IOError):
            return None

    def _remove_pid_file(self):
        """Remove PID file."""
        if self.pid_file.exists():
            try:
                self.pid_file.unlink()
            except OSError:
                pass  # Ignore errors during cleanup

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM signal (graceful shutdown).

        Args:
            signum: Signal number
            frame: Current stack frame
        """
        self._log(f"Received shutdown signal ({signum})")
        self.running = False

    def _cleanup(self):
        """Cleanup on shutdown.

        Removes PID file and logs shutdown message.
        """
        self._remove_pid_file()
        self._log("Daemon stopped cleanly")

    def _log(self, message: str):
        """Log a message with timestamp.

        Args:
            message: Message to log
        """
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        print(f"[{timestamp}] {message}")
        sys.stdout.flush()  # Ensure log is written immediately
