# Scheduling and Daemon Mode Documentation

## Overview

**Status:** Future Enhancement (Not Yet Implemented)

Daemon mode will enable automatic, scheduled syncs in the background, keeping Deezer playlists continuously updated with changes from Spotify.

## Planned Features

### Daemon Process

Background service that runs continuously and performs syncs at regular intervals.

```bash
# Start daemon (default: sync every 24 hours)
musicdiff daemon

# Start with custom interval (6 hours)
musicdiff daemon --interval 21600

# Stop daemon
musicdiff daemon --stop

# Check daemon status
musicdiff daemon --status
```

### Configuration

Daemon settings will be configurable:

```yaml
daemon:
  enabled: true
  interval_seconds: 86400  # 24 hours
  log_file: ~/.musicdiff/daemon.log
  pid_file: ~/.musicdiff/daemon.pid
  on_failure: log  # log, notify, or stop
```

### Logging

Daemon will maintain detailed logs:
- Sync start/completion times
- Playlists synced
- Errors encountered
- Track match statistics

**Log Location:** `~/.musicdiff/daemon.log`

### Notifications

Optional notifications for sync events:
- Sync completed successfully
- Errors during sync
- New playlists detected
- Tracks couldn't be matched

**Methods:**
- System notifications (macOS/Linux)
- Email (configurable SMTP)
- Webhook (for custom integrations)

## Implementation Plan

### Phase 1: Basic Daemon

- Background process using Python's `daemon` library
- PID file for process management
- Basic interval-based scheduling
- Logging to file

### Phase 2: Robust Scheduling

- Cron-like scheduling (specific times)
- Retry logic for failed syncs
- Rate limiting to avoid API abuse
- Smart sync (only if playlists changed)

### Phase 3: Advanced Features

- Notification system
- Web dashboard for monitoring
- Incremental sync (only changed playlists)
- Priority playlists (sync more frequently)

## Current Workaround

Until daemon mode is implemented, use system cron jobs:

**macOS/Linux:**

```bash
# Edit crontab
crontab -e

# Add line to sync every 6 hours
0 */6 * * * source /path/to/.musicdiff/.env && /path/to/venv/bin/musicdiff sync >> /path/to/sync.log 2>&1
```

**Example cron schedules:**
```bash
# Every 6 hours
0 */6 * * * ...

# Every day at 2 AM
0 2 * * * ...

# Every Monday at midnight
0 0 * * 1 ...
```

## Future Enhancements

- **Conflict Detection**: Detect manual changes on Deezer and notify user
- **Smart Sync**: Only sync if Spotify playlist changed (snapshot ID check)
- **Selective Sync**: Different schedules for different playlists
- **Bandwidth Control**: Limit API calls per hour
- **Health Monitoring**: Alert if daemon stops or sync consistently fails
