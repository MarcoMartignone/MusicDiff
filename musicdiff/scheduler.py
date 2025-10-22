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
        self.pid_file = Path.home() / '.musicdiff' / 'daemon.pid'

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
        """Fork process and run as daemon."""
        # TODO: Implement proper daemonization
        # 1. Fork twice
        # 2. Redirect stdout/stderr to log file
        # 3. Write PID file
        # 4. Setup signal handlers
        # 5. Run main loop

        raise NotImplementedError("Daemonization not yet implemented")

    def _run_foreground(self):
        """Run daemon in foreground."""
        self._write_pid_file()
        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)
        self._run()

    def _run(self):
        """Main daemon loop."""
        self.running = True
        print(f"[{datetime.now()}] MusicDiff daemon started (interval: {self.interval}s)")

        while self.running:
            try:
                print(f"[{datetime.now()}] Starting automatic sync...")
                result = self.sync_engine.sync(mode=SyncMode.AUTO)
                print(f"[{datetime.now()}] Sync completed: {result.changes_applied} changes")

            except Exception as e:
                print(f"[{datetime.now()}] Sync failed: {e}")

            # Sleep until next sync
            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

        self._cleanup()

    def stop(self):
        """Stop the daemon."""
        pid = self._read_pid()
        if not pid:
            raise RuntimeError("Daemon is not running")

        os.kill(pid, signal.SIGTERM)

    def is_running(self) -> bool:
        """Check if daemon is running."""
        pid = self._read_pid()
        if not pid:
            return False

        try:
            os.kill(pid, 0)
            return True
        except OSError:
            self._remove_pid_file()
            return False

    def _write_pid_file(self):
        """Write current PID to file."""
        self.pid_file.parent.mkdir(parents=True, exist_ok=True)
        self.pid_file.write_text(str(os.getpid()))

    def _read_pid(self) -> int:
        """Read PID from file."""
        if not self.pid_file.exists():
            return None
        try:
            return int(self.pid_file.read_text().strip())
        except (ValueError, IOError):
            return None

    def _remove_pid_file(self):
        """Remove PID file."""
        if self.pid_file.exists():
            self.pid_file.unlink()

    def _handle_sigterm(self, signum, frame):
        """Handle SIGTERM signal."""
        print(f"[{datetime.now()}] Received shutdown signal")
        self.running = False

    def _cleanup(self):
        """Cleanup on shutdown."""
        self._remove_pid_file()
        print(f"[{datetime.now()}] Daemon stopped")
