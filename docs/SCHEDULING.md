# Scheduling Documentation

## Overview

The Scheduling module (`scheduler.py`) enables MusicDiff to run automatic syncs at regular intervals via daemon mode. This allows hands-free synchronization that runs in the background.

## Daemon Mode

### Starting the Daemon

```bash
# Start daemon with default interval (24 hours)
musicdiff daemon

# Start with custom interval (6 hours = 21600 seconds)
musicdiff daemon --interval 21600

# Run in foreground (for debugging)
musicdiff daemon --foreground
```

### Implementation

```python
import time
import signal
import sys
from datetime import datetime
from pathlib import Path

class SyncDaemon:
    def __init__(self, sync_engine, interval: int = 86400):
        self.sync_engine = sync_engine
        self.interval = interval  # seconds
        self.running = False
        self.pid_file = Path.home() / '.musicdiff' / 'daemon.pid'

    def start(self, foreground: bool = False):
        """Start the daemon."""

        # Check if already running
        if self.is_running():
            raise RuntimeError("Daemon is already running")

        if foreground:
            self._run_foreground()
        else:
            self._daemonize()

    def _daemonize(self):
        """Fork process and run as daemon."""

        # First fork
        try:
            pid = os.fork()
            if pid > 0:
                # Exit parent process
                sys.exit(0)
        except OSError as e:
            raise RuntimeError(f"Fork failed: {e}")

        # Decouple from parent environment
        os.chdir('/')
        os.setsid()
        os.umask(0)

        # Second fork
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError as e:
            raise RuntimeError(f"Fork failed: {e}")

        # Redirect standard file descriptors
        sys.stdout.flush()
        sys.stderr.flush()

        log_file = Path.home() / '.musicdiff' / 'daemon.log'

        with open('/dev/null', 'r') as devnull:
            os.dup2(devnull.fileno(), sys.stdin.fileno())

        with open(log_file, 'a') as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())

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

        signal.signal(signal.SIGTERM, self._handle_sigterm)
        signal.signal(signal.SIGINT, self._handle_sigterm)

        self._run()

    def _run(self):
        """Main daemon loop."""

        self.running = True
        print(f"[{datetime.now()}] MusicDiff daemon started (interval: {self.interval}s)")

        while self.running:
            try:
                # Perform sync
                print(f"[{datetime.now()}] Starting automatic sync...")

                result = self.sync_engine.sync(mode=SyncMode.AUTO)

                if result.success:
                    print(f"[{datetime.now()}] Sync completed: {result.changes_applied} changes")
                else:
                    print(f"[{datetime.now()}] Sync partial: {result.changes_applied} changes, {len(result.failed_changes)} failed")

                if result.conflicts_count > 0:
                    print(f"[{datetime.now()}] {result.conflicts_count} conflicts detected (run 'musicdiff resolve')")

            except Exception as e:
                print(f"[{datetime.now()}] Sync failed: {e}")

            # Sleep until next sync
            print(f"[{datetime.now()}] Next sync in {self.interval} seconds")

            for _ in range(self.interval):
                if not self.running:
                    break
                time.sleep(1)

        # Cleanup
        self._cleanup()

    def stop(self):
        """Stop the daemon."""

        pid = self._read_pid()
        if not pid:
            raise RuntimeError("Daemon is not running")

        # Send SIGTERM
        os.kill(pid, signal.SIGTERM)

        # Wait for daemon to stop
        for _ in range(10):
            if not self.is_running():
                print("Daemon stopped")
                return
            time.sleep(1)

        # Force kill if still running
        os.kill(pid, signal.SIGKILL)
        self._remove_pid_file()

    def is_running(self) -> bool:
        """Check if daemon is running."""

        pid = self._read_pid()
        if not pid:
            return False

        # Check if process exists
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
        """Handle SIGTERM signal (graceful shutdown)."""
        print(f"[{datetime.now()}] Received shutdown signal")
        self.running = False

    def _cleanup(self):
        """Cleanup on shutdown."""
        self._remove_pid_file()
        print(f"[{datetime.now()}] Daemon stopped")
```

---

## System Integration

### macOS (launchd)

Create a `launchd` plist to run MusicDiff daemon on startup.

**File:** `~/Library/LaunchAgents/com.musicdiff.daemon.plist`

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.musicdiff.daemon</string>

    <key>ProgramArguments</key>
    <array>
        <string>/usr/local/bin/musicdiff</string>
        <string>daemon</string>
        <string>--interval</string>
        <string>86400</string>
    </array>

    <key>RunAtLoad</key>
    <true/>

    <key>KeepAlive</key>
    <false/>

    <key>StandardOutPath</key>
    <string>/Users/YOUR_USERNAME/.musicdiff/daemon.log</string>

    <key>StandardErrorPath</key>
    <string>/Users/YOUR_USERNAME/.musicdiff/daemon.err</string>
</dict>
</plist>
```

**Install:**
```bash
launchctl load ~/Library/LaunchAgents/com.musicdiff.daemon.plist
```

**Uninstall:**
```bash
launchctl unload ~/Library/LaunchAgents/com.musicdiff.daemon.plist
```

---

### Linux (systemd)

Create a systemd service.

**File:** `~/.config/systemd/user/musicdiff.service`

```ini
[Unit]
Description=MusicDiff Sync Daemon
After=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/musicdiff daemon --interval 86400
Restart=on-failure
RestartSec=60

StandardOutput=append:/home/YOUR_USERNAME/.musicdiff/daemon.log
StandardError=append:/home/YOUR_USERNAME/.musicdiff/daemon.err

[Install]
WantedBy=default.target
```

**Install:**
```bash
systemctl --user enable musicdiff
systemctl --user start musicdiff
```

**Status:**
```bash
systemctl --user status musicdiff
```

---

## Scheduling Strategies

### 1. Fixed Interval

Sync every N seconds.

```python
# Sync every 24 hours
daemon = SyncDaemon(sync_engine, interval=86400)
```

**Pros:** Simple, predictable
**Cons:** May sync at inconvenient times

---

### 2. Cron-Style Scheduling

Sync at specific times (e.g., 2am daily).

```python
from apscheduler.schedulers.blocking import BlockingScheduler

class CronDaemon:
    def __init__(self, sync_engine):
        self.sync_engine = sync_engine
        self.scheduler = BlockingScheduler()

    def start(self):
        """Start scheduler with cron jobs."""

        # Sync daily at 2:00 AM
        self.scheduler.add_job(
            self._sync,
            'cron',
            hour=2,
            minute=0
        )

        self.scheduler.start()

    def _sync(self):
        """Perform sync."""
        result = self.sync_engine.sync(mode=SyncMode.AUTO)
        print(f"Sync completed: {result.changes_applied} changes")
```

---

### 3. Smart Scheduling

Sync based on activity detection.

```python
class SmartDaemon:
    def __init__(self, sync_engine):
        self.sync_engine = sync_engine
        self.last_sync = None

    def should_sync(self) -> bool:
        """Determine if sync should run."""

        # Don't sync if last sync was less than 6 hours ago
        if self.last_sync:
            hours_since = (datetime.now() - self.last_sync).total_seconds() / 3600
            if hours_since < 6:
                return False

        # Check if user is idle (system idle detection)
        if not self.is_user_idle():
            return False

        # Check if on Wi-Fi (avoid syncing on cellular)
        if not self.is_on_wifi():
            return False

        return True
```

---

## Notifications

### Email Notifications

Send email when conflicts are detected.

```python
import smtplib
from email.message import EmailMessage

class EmailNotifier:
    def __init__(self, smtp_server: str, username: str, password: str):
        self.smtp_server = smtp_server
        self.username = username
        self.password = password

    def notify_conflicts(self, conflicts: List[Conflict]):
        """Send email notification about conflicts."""

        msg = EmailMessage()
        msg['Subject'] = f'MusicDiff: {len(conflicts)} conflicts detected'
        msg['From'] = self.username
        msg['To'] = self.username

        body = f"MusicDiff detected {len(conflicts)} conflicts during sync:\n\n"
        for conflict in conflicts:
            body += f"  • {conflict.entity_type}: {conflict.entity_id}\n"

        body += "\nRun 'musicdiff resolve' to handle conflicts."

        msg.set_content(body)

        # Send email
        with smtplib.SMTP_SSL(self.smtp_server, 465) as smtp:
            smtp.login(self.username, self.password)
            smtp.send_message(msg)
```

---

### Desktop Notifications

Show system notifications on macOS/Linux.

```python
# macOS
def show_notification_macos(title: str, message: str):
    """Show notification on macOS."""
    os.system(f"""
        osascript -e 'display notification "{message}" with title "{title}"'
    """)

# Linux (using notify-send)
def show_notification_linux(title: str, message: str):
    """Show notification on Linux."""
    os.system(f'notify-send "{title}" "{message}"')
```

---

## Logging

Log all daemon activity.

```python
import logging
from logging.handlers import RotatingFileHandler

def setup_daemon_logging():
    """Setup logging for daemon."""

    log_file = Path.home() / '.musicdiff' / 'daemon.log'
    log_file.parent.mkdir(parents=True, exist_ok=True)

    # Rotating file handler (max 10MB, keep 5 backups)
    handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,
        backupCount=5
    )

    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger('musicdiff')
    logger.addHandler(handler)
    logger.setLevel(logging.INFO)

    return logger
```

---

## Configuration

Daemon settings in `~/.musicdiff/config.yaml`:

```yaml
daemon:
  enabled: true
  interval: 86400  # 24 hours
  schedule: "0 2 * * *"  # Cron format (optional)

  # Auto-sync mode settings
  auto_accept_non_conflicts: true
  skip_conflicts: true

  # Notifications
  notify_on_conflicts: true
  notification_method: "email"  # email, desktop, both

  email:
    smtp_server: "smtp.gmail.com"
    username: "your-email@gmail.com"
    password: "app-password"
```

---

## Testing

Mock time for testing scheduled syncs.

```python
from unittest.mock import patch
import time

def test_daemon_sync_interval():
    daemon = SyncDaemon(mock_sync_engine, interval=10)

    with patch('time.sleep') as mock_sleep:
        daemon.start(foreground=True)

        # Verify sleep was called with correct interval
        mock_sleep.assert_called_with(10)
```

---

## Best Practices

1. **Error Handling**: Don't crash on single sync failure, retry next cycle
2. **Logging**: Log all sync attempts and results
3. **Resource Usage**: Avoid syncing during high system load
4. **Network Awareness**: Check connectivity before syncing
5. **Graceful Shutdown**: Handle SIGTERM for clean daemon stop

## References

- [Python Daemon Best Practices](https://www.python.org/dev/peps/pep-3143/)
- [APScheduler Documentation](https://apscheduler.readthedocs.io/)
- [systemd Service Files](https://www.freedesktop.org/software/systemd/man/systemd.service.html)
- [launchd plist](https://www.launchd.info/)
