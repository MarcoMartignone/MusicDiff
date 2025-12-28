"""
Database management for MusicDiff local state.

See docs/DATABASE.md for detailed documentation.
"""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict
from datetime import datetime


class Database:
    """SQLite database manager for MusicDiff."""

    def __init__(self, db_path: str = None):
        """Initialize database connection.

        Args:
            db_path: Path to SQLite database file. Defaults to ~/.musicdiff/musicdiff.db
        """
        if db_path is None:
            db_path = str(Path.home() / '.musicdiff' / 'musicdiff.db')

        self.db_path = db_path
        self._ensure_directory()

        # Run migrations on every startup to ensure schema is up to date
        self._run_migrations()

    def _ensure_directory(self):
        """Create database directory if it doesn't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

    def _run_migrations(self):
        """Run database migrations if needed."""
        # Only run migrations if database file exists
        if not Path(self.db_path).exists():
            return

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Run migrations
        self._migrate_schema(conn, cursor)

        conn.close()

    def _column_exists(self, cursor, table_name: str, column_name: str) -> bool:
        """Check if a column exists in a table."""
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = [row[1] for row in cursor.fetchall()]
        return column_name in columns

    def _migrate_schema(self, conn, cursor):
        """Migrate database schema from old versions."""
        # Check if tracks table exists
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='tracks'")
        tracks_exists = cursor.fetchone() is not None

        if tracks_exists:
            # Check if we need to migrate from apple_id to deezer_id
            has_deezer_id = self._column_exists(cursor, 'tracks', 'deezer_id')
            has_apple_id = self._column_exists(cursor, 'tracks', 'apple_id')

            if has_apple_id and not has_deezer_id:
                # Migrate from old Apple Music schema to Deezer schema
                print("Migrating database schema from Apple Music to Deezer...")

                # SQLite doesn't support DROP COLUMN, so we need to recreate the table
                cursor.execute("""
                    CREATE TABLE tracks_new (
                        isrc TEXT PRIMARY KEY,
                        spotify_id TEXT UNIQUE,
                        deezer_id TEXT UNIQUE,
                        title TEXT NOT NULL,
                        artist TEXT NOT NULL,
                        album TEXT NOT NULL,
                        duration_ms INTEGER NOT NULL,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Copy data from old table (without apple_id column)
                cursor.execute("""
                    INSERT INTO tracks_new (isrc, spotify_id, title, artist, album, duration_ms, created_at, updated_at)
                    SELECT isrc, spotify_id, title, artist, album, duration_ms, created_at, updated_at
                    FROM tracks
                """)

                # Drop old table and rename new one
                cursor.execute("DROP TABLE tracks")
                cursor.execute("ALTER TABLE tracks_new RENAME TO tracks")

                conn.commit()
                print("Migration complete!")
            elif not has_deezer_id:
                # Table exists but missing deezer_id column (and no apple_id)
                # This shouldn't happen, but let's handle it
                cursor.execute("ALTER TABLE tracks ADD COLUMN deezer_id TEXT UNIQUE")
                conn.commit()

        # Check if sync_log table exists and needs migration
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='sync_log'")
        sync_log_exists = cursor.fetchone() is not None

        if sync_log_exists:
            # Check if we need to add missing columns
            has_playlists_synced = self._column_exists(cursor, 'sync_log', 'playlists_synced')

            if not has_playlists_synced:
                print("Migrating sync_log table to add missing columns...")
                # Add the missing columns
                cursor.execute("ALTER TABLE sync_log ADD COLUMN playlists_synced INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE sync_log ADD COLUMN playlists_created INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE sync_log ADD COLUMN playlists_updated INTEGER DEFAULT 0")
                cursor.execute("ALTER TABLE sync_log ADD COLUMN playlists_deleted INTEGER DEFAULT 0")
                conn.commit()
                print("sync_log migration complete!")

        # Check if download_status table needs position column
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='download_status'")
        download_status_exists = cursor.fetchone() is not None

        if download_status_exists:
            has_position = self._column_exists(cursor, 'download_status', 'position')
            if not has_position:
                print("Adding position column to download_status table...")
                cursor.execute("ALTER TABLE download_status ADD COLUMN position INTEGER DEFAULT 0")
                conn.commit()
                print("download_status migration complete!")

    def init_schema(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Run migrations first
        self._migrate_schema(conn, cursor)

        # Tracks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                isrc TEXT PRIMARY KEY,
                spotify_id TEXT UNIQUE,
                deezer_id TEXT UNIQUE,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_spotify_id ON tracks(spotify_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_deezer_id ON tracks(deezer_id)")

        # Playlist selections table - stores which Spotify playlists user wants to sync
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_selections (
                spotify_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                track_count INTEGER DEFAULT 0,
                selected BOOLEAN DEFAULT 1,
                last_synced TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Synced playlists table - tracks what's currently on Deezer
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS synced_playlists (
                spotify_id TEXT PRIMARY KEY,
                deezer_id TEXT NOT NULL,
                name TEXT NOT NULL,
                track_count INTEGER DEFAULT 0,
                synced_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (spotify_id) REFERENCES playlist_selections(spotify_id) ON DELETE CASCADE
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_synced_deezer ON synced_playlists(deezer_id)")

        # Sync log table - simplified for one-way sync
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                playlists_synced INTEGER DEFAULT 0,
                playlists_created INTEGER DEFAULT 0,
                playlists_updated INTEGER DEFAULT 0,
                playlists_deleted INTEGER DEFAULT 0,
                duration_seconds REAL,
                details TEXT,
                auto_sync BOOLEAN DEFAULT 0
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_timestamp ON sync_log(timestamp)")

        # Metadata table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Download status table - tracks download state for individual tracks
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS download_status (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                deezer_id TEXT NOT NULL UNIQUE,
                spotify_id TEXT,
                isrc TEXT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                playlist_spotify_id TEXT,
                position INTEGER DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending',
                quality TEXT DEFAULT '320',
                file_path TEXT,
                error_message TEXT,
                attempts INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_download_deezer ON download_status(deezer_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_download_status ON download_status(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_download_playlist ON download_status(playlist_spotify_id)")

        # Rekordbox tag queue table - tracks pending Rekordbox tag applications
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS rekordbox_tag_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path TEXT UNIQUE NOT NULL,
                playlist_name TEXT NOT NULL,
                deezer_id TEXT,
                title TEXT,
                artist TEXT,
                album TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                rekordbox_content_id TEXT,
                rekordbox_tag_id TEXT,
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                applied_at TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rekordbox_status ON rekordbox_tag_queue(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_rekordbox_playlist ON rekordbox_tag_queue(playlist_name)")

        # Initialize schema version
        cursor.execute("""
            INSERT OR IGNORE INTO metadata (key, value)
            VALUES ('schema_version', '4')
        """)

        conn.commit()
        conn.close()

    def get_metadata(self, key: str) -> Optional[str]:
        """Get metadata value by key."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT value FROM metadata WHERE key = ?",
            (key,)
        ).fetchone()

        conn.close()
        return result[0] if result else None

    def set_metadata(self, key: str, value: str):
        """Set metadata key-value pair."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO metadata (key, value, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(key) DO UPDATE SET
                value = excluded.value,
                updated_at = CURRENT_TIMESTAMP
        """, (key, value))

        conn.commit()
        conn.close()

    # Track operations

    def upsert_track(self, track: Dict) -> None:
        """Insert or update track data.

        Args:
            track: Dict with keys: isrc, spotify_id, deezer_id,
                   title, artist, album, duration_ms
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tracks (isrc, spotify_id, deezer_id,
                               title, artist, album, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(isrc) DO UPDATE SET
                spotify_id = COALESCE(excluded.spotify_id, spotify_id),
                deezer_id = COALESCE(excluded.deezer_id, deezer_id),
                title = excluded.title,
                artist = excluded.artist,
                album = excluded.album,
                duration_ms = excluded.duration_ms,
                updated_at = CURRENT_TIMESTAMP
        """, (
            track.get('isrc'),
            track.get('spotify_id'),
            track.get('deezer_id'),
            track.get('title', ''),
            track.get('artist', ''),
            track.get('album', ''),
            track.get('duration_ms', 0)
        ))

        conn.commit()
        conn.close()

    def get_track_by_isrc(self, isrc: str) -> Optional[Dict]:
        """Get track by ISRC code."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM tracks WHERE isrc = ?",
            (isrc,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def get_track_by_spotify_id(self, spotify_id: str) -> Optional[Dict]:
        """Get track by Spotify ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM tracks WHERE spotify_id = ?",
            (spotify_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def get_track_by_deezer_id(self, deezer_id: str) -> Optional[Dict]:
        """Get track by Deezer ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM tracks WHERE deezer_id = ?",
            (deezer_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    # Playlist selection operations

    def upsert_playlist_selection(self, spotify_id: str, name: str, track_count: int = 0, selected: bool = True) -> None:
        """Insert or update playlist selection.

        Args:
            spotify_id: Spotify playlist ID
            name: Playlist name
            track_count: Number of tracks
            selected: Whether playlist is selected for sync
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO playlist_selections (spotify_id, name, track_count, selected)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(spotify_id) DO UPDATE SET
                name = excluded.name,
                track_count = excluded.track_count,
                selected = excluded.selected,
                updated_at = CURRENT_TIMESTAMP
        """, (spotify_id, name, track_count, selected))

        conn.commit()
        conn.close()

    def get_all_playlist_selections(self) -> List[Dict]:
        """Get all playlist selections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM playlist_selections
            ORDER BY name
        """).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def get_selected_playlists(self) -> List[Dict]:
        """Get only selected playlists."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM playlist_selections
            WHERE selected = 1
            ORDER BY name
        """).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def get_playlist_selection(self, spotify_id: str) -> Optional[Dict]:
        """Get a playlist selection by Spotify ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM playlist_selections WHERE spotify_id = ?",
            (spotify_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def update_playlist_selection(self, spotify_id: str, selected: bool) -> None:
        """Update playlist selection status.

        Args:
            spotify_id: Spotify playlist ID
            selected: New selection status
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE playlist_selections
            SET selected = ?, updated_at = CURRENT_TIMESTAMP
            WHERE spotify_id = ?
        """, (selected, spotify_id))

        conn.commit()
        conn.close()

    def mark_playlist_synced(self, spotify_id: str) -> None:
        """Mark playlist as synced (update last_synced timestamp).

        Args:
            spotify_id: Spotify playlist ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE playlist_selections
            SET last_synced = CURRENT_TIMESTAMP
            WHERE spotify_id = ?
        """, (spotify_id,))

        conn.commit()
        conn.close()

    # Synced playlists operations

    def upsert_synced_playlist(self, spotify_id: str, deezer_id: str, name: str, track_count: int = 0) -> None:
        """Insert or update synced playlist record.

        Args:
            spotify_id: Spotify playlist ID
            deezer_id: Deezer playlist ID
            name: Playlist name
            track_count: Number of tracks
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO synced_playlists (spotify_id, deezer_id, name, track_count, synced_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(spotify_id) DO UPDATE SET
                deezer_id = excluded.deezer_id,
                name = excluded.name,
                track_count = excluded.track_count,
                synced_at = CURRENT_TIMESTAMP
        """, (spotify_id, deezer_id, name, track_count))

        conn.commit()
        conn.close()

    def get_synced_playlist(self, spotify_id: str) -> Optional[Dict]:
        """Get synced playlist by Spotify ID.

        Args:
            spotify_id: Spotify playlist ID

        Returns:
            Synced playlist dict or None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM synced_playlists WHERE spotify_id = ?",
            (spotify_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def get_all_synced_playlists(self) -> List[Dict]:
        """Get all synced playlists."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("SELECT * FROM synced_playlists").fetchall()

        conn.close()
        return [dict(row) for row in results]

    def delete_synced_playlist(self, spotify_id: str) -> None:
        """Delete synced playlist record.

        Args:
            spotify_id: Spotify playlist ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM synced_playlists WHERE spotify_id = ?", (spotify_id,))

        conn.commit()
        conn.close()

    # Sync log operations

    def add_sync_log(self, status: str, playlists_synced: int = 0, playlists_created: int = 0,
                     playlists_updated: int = 0, playlists_deleted: int = 0,
                     details: Dict = None, duration: float = 0, auto_sync: bool = False) -> None:
        """Add sync log entry.

        Args:
            status: 'success', 'partial', or 'failed'
            playlists_synced: Total number of playlists synced
            playlists_created: Number of playlists created on Deezer
            playlists_updated: Number of playlists updated on Deezer
            playlists_deleted: Number of playlists deleted from Deezer
            details: Dict with detailed sync information
            duration: Sync duration in seconds
            auto_sync: Whether this was an automatic sync
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sync_log (status, playlists_synced, playlists_created, playlists_updated,
                                 playlists_deleted, details, duration_seconds, auto_sync)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (status, playlists_synced, playlists_created, playlists_updated, playlists_deleted,
              json.dumps(details) if details else None, duration, auto_sync))

        conn.commit()
        conn.close()

    def get_sync_history(self, limit: int = 10) -> List[Dict]:
        """Get sync history.

        Args:
            limit: Number of entries to return

        Returns:
            List of sync log entries
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM sync_log
            ORDER BY timestamp DESC
            LIMIT ?
        """, (limit,)).fetchall()

        conn.close()

        logs = []
        for row in results:
            log = dict(row)
            if log.get('details'):
                log['details'] = json.loads(log['details'])
            logs.append(log)

        return logs

    # Download status operations

    def add_download_record(self, deezer_id: str, spotify_id: str = None, isrc: str = None,
                            title: str = '', artist: str = '', playlist_spotify_id: str = None,
                            position: int = 0, quality: str = '320') -> None:
        """Add a new download record or update existing one.

        Args:
            deezer_id: Deezer track ID
            spotify_id: Spotify track ID (optional)
            isrc: ISRC code (optional)
            title: Track title
            artist: Track artist
            playlist_spotify_id: Spotify playlist ID (optional)
            position: Position in playlist (1-based)
            quality: Download quality (128, 320, flac)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO download_status (deezer_id, spotify_id, isrc, title, artist,
                                         playlist_spotify_id, position, quality, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(deezer_id) DO UPDATE SET
                spotify_id = COALESCE(excluded.spotify_id, spotify_id),
                isrc = COALESCE(excluded.isrc, isrc),
                title = excluded.title,
                artist = excluded.artist,
                playlist_spotify_id = COALESCE(excluded.playlist_spotify_id, playlist_spotify_id),
                position = excluded.position,
                quality = excluded.quality,
                updated_at = CURRENT_TIMESTAMP
        """, (deezer_id, spotify_id, isrc, title, artist, playlist_spotify_id, position, quality))

        conn.commit()
        conn.close()

    def update_download_status(self, deezer_id: str, status: str, file_path: str = None,
                               error_message: str = None) -> None:
        """Update download status for a track.

        Args:
            deezer_id: Deezer track ID
            status: New status (pending, downloading, completed, failed, skipped)
            file_path: Path to downloaded file (optional)
            error_message: Error message if failed (optional)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status == 'completed':
            cursor.execute("""
                UPDATE download_status
                SET status = ?, file_path = ?, error_message = NULL,
                    updated_at = CURRENT_TIMESTAMP, completed_at = CURRENT_TIMESTAMP
                WHERE deezer_id = ?
            """, (status, file_path, deezer_id))
        else:
            cursor.execute("""
                UPDATE download_status
                SET status = ?, file_path = ?, error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE deezer_id = ?
            """, (status, file_path, error_message, deezer_id))

        conn.commit()
        conn.close()

    def update_download_position(self, deezer_id: str, position: int) -> None:
        """Update position for a track in download_status.

        Args:
            deezer_id: Deezer track ID
            position: New position (1-based)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE download_status
            SET position = ?, updated_at = CURRENT_TIMESTAMP
            WHERE deezer_id = ?
        """, (position, deezer_id))
        conn.commit()
        conn.close()

    def get_pending_downloads(self, playlist_spotify_id: str = None) -> List[Dict]:
        """Get all pending downloads, optionally filtered by playlist.

        Args:
            playlist_spotify_id: Filter by playlist (optional)

        Returns:
            List of pending download records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if playlist_spotify_id:
            results = cursor.execute("""
                SELECT * FROM download_status
                WHERE status = 'pending' AND playlist_spotify_id = ?
                ORDER BY created_at
            """, (playlist_spotify_id,)).fetchall()
        else:
            results = cursor.execute("""
                SELECT * FROM download_status
                WHERE status = 'pending'
                ORDER BY created_at
            """).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def get_failed_downloads(self, max_attempts: int = 3) -> List[Dict]:
        """Get failed downloads that haven't exceeded max retry attempts.

        Args:
            max_attempts: Maximum number of attempts before giving up

        Returns:
            List of failed download records eligible for retry
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM download_status
            WHERE status = 'failed' AND attempts < ?
            ORDER BY updated_at
        """, (max_attempts,)).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def get_download_by_deezer_id(self, deezer_id: str) -> Optional[Dict]:
        """Get download record by Deezer ID.

        Args:
            deezer_id: Deezer track ID

        Returns:
            Download record or None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM download_status WHERE deezer_id = ?",
            (deezer_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def get_download_by_spotify_id(self, spotify_id: str) -> Optional[Dict]:
        """Get download record by Spotify ID.

        Args:
            spotify_id: Spotify track ID

        Returns:
            Download record or None
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM download_status WHERE spotify_id = ?",
            (spotify_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def increment_download_attempts(self, deezer_id: str) -> None:
        """Increment the attempt counter for a download.

        Args:
            deezer_id: Deezer track ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE download_status
            SET attempts = attempts + 1, updated_at = CURRENT_TIMESTAMP
            WHERE deezer_id = ?
        """, (deezer_id,))

        conn.commit()
        conn.close()

    def mark_download_complete(self, deezer_id: str, file_path: str) -> None:
        """Mark a download as completed.

        Args:
            deezer_id: Deezer track ID
            file_path: Path to the downloaded file
        """
        self.update_download_status(deezer_id, 'completed', file_path=file_path)

    def get_download_stats(self) -> Dict:
        """Get download statistics.

        Returns:
            Dict with counts: pending, downloading, completed, failed, skipped, total
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        result = cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'downloading' THEN 1 ELSE 0 END) as downloading,
                SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) as completed,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed,
                SUM(CASE WHEN status = 'skipped' THEN 1 ELSE 0 END) as skipped
            FROM download_status
        """).fetchone()

        conn.close()

        return {
            'total': result[0] or 0,
            'pending': result[1] or 0,
            'downloading': result[2] or 0,
            'completed': result[3] or 0,
            'failed': result[4] or 0,
            'skipped': result[5] or 0
        }

    def get_downloads_by_status(self, status: str) -> List[Dict]:
        """Get all downloads with a specific status.

        Args:
            status: Status to filter by (pending, downloading, completed, failed, skipped)

        Returns:
            List of download records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM download_status
            WHERE status = ?
            ORDER BY updated_at DESC
        """, (status,)).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def clear_download_history(self, status: str = None) -> int:
        """Clear download history.

        Args:
            status: Only clear records with this status (optional).
                    If None, clears all records.

        Returns:
            Number of records deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status:
            cursor.execute("DELETE FROM download_status WHERE status = ?", (status,))
        else:
            cursor.execute("DELETE FROM download_status")

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted

    def reset_downloading_to_pending(self) -> int:
        """Reset any 'downloading' status back to 'pending'.

        Useful for recovering from interrupted downloads.

        Returns:
            Number of records reset
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE download_status
            SET status = 'pending', updated_at = CURRENT_TIMESTAMP
            WHERE status = 'downloading'
        """)

        reset = cursor.rowcount
        conn.commit()
        conn.close()
        return reset

    def close(self):
        """Close database connection."""
        # Connection is created per-operation, so no persistent connection to close
        pass

    # Rekordbox tag queue operations

    def queue_rekordbox_tag(self, file_path: str, playlist_name: str, deezer_id: str = None,
                            title: str = None, artist: str = None, album: str = None) -> None:
        """Add a track to the Rekordbox tag queue.

        Args:
            file_path: Path to the audio file
            playlist_name: Name of the playlist (used as tag name)
            deezer_id: Deezer track ID (optional)
            title: Track title (optional)
            artist: Track artist (optional)
            album: Track album (optional)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO rekordbox_tag_queue (file_path, playlist_name, deezer_id, title, artist, album, status)
            VALUES (?, ?, ?, ?, ?, ?, 'pending')
            ON CONFLICT(file_path) DO UPDATE SET
                playlist_name = excluded.playlist_name,
                deezer_id = COALESCE(excluded.deezer_id, deezer_id),
                title = COALESCE(excluded.title, title),
                artist = COALESCE(excluded.artist, artist),
                album = COALESCE(excluded.album, album),
                status = 'pending',
                error_message = NULL,
                updated_at = CURRENT_TIMESTAMP
        """, (file_path, playlist_name, deezer_id, title, artist, album))

        conn.commit()
        conn.close()

    def get_pending_rekordbox_tags(self, playlist_name: str = None) -> List[Dict]:
        """Get all pending Rekordbox tag applications.

        Args:
            playlist_name: Filter by playlist name (optional)

        Returns:
            List of pending tag queue records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        if playlist_name:
            results = cursor.execute("""
                SELECT * FROM rekordbox_tag_queue
                WHERE status = 'pending' AND playlist_name = ?
                ORDER BY created_at
            """, (playlist_name,)).fetchall()
        else:
            results = cursor.execute("""
                SELECT * FROM rekordbox_tag_queue
                WHERE status = 'pending'
                ORDER BY created_at
            """).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def update_rekordbox_tag_status(self, file_path: str, status: str,
                                     content_id: str = None, tag_id: str = None,
                                     error_message: str = None) -> None:
        """Update Rekordbox tag queue status.

        Args:
            file_path: Path to the audio file
            status: New status (pending, applied, not_found, failed)
            content_id: Rekordbox content ID (optional)
            tag_id: Rekordbox tag ID (optional)
            error_message: Error message if failed (optional)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status == 'applied':
            cursor.execute("""
                UPDATE rekordbox_tag_queue
                SET status = ?, rekordbox_content_id = ?, rekordbox_tag_id = ?,
                    error_message = NULL, updated_at = CURRENT_TIMESTAMP,
                    applied_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """, (status, content_id, tag_id, file_path))
        else:
            cursor.execute("""
                UPDATE rekordbox_tag_queue
                SET status = ?, rekordbox_content_id = ?, rekordbox_tag_id = ?,
                    error_message = ?, updated_at = CURRENT_TIMESTAMP
                WHERE file_path = ?
            """, (status, content_id, tag_id, error_message, file_path))

        conn.commit()
        conn.close()

    def get_rekordbox_tag_stats(self) -> Dict:
        """Get Rekordbox tag queue statistics.

        Returns:
            Dict with counts: pending, applied, not_found, failed, total
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        result = cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) as pending,
                SUM(CASE WHEN status = 'applied' THEN 1 ELSE 0 END) as applied,
                SUM(CASE WHEN status = 'not_found' THEN 1 ELSE 0 END) as not_found,
                SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
            FROM rekordbox_tag_queue
        """).fetchone()

        conn.close()

        return {
            'total': result[0] or 0,
            'pending': result[1] or 0,
            'applied': result[2] or 0,
            'not_found': result[3] or 0,
            'failed': result[4] or 0
        }

    def get_rekordbox_tags_by_status(self, status: str) -> List[Dict]:
        """Get all Rekordbox tag queue entries with a specific status.

        Args:
            status: Status to filter by (pending, applied, not_found, failed)

        Returns:
            List of tag queue records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM rekordbox_tag_queue
            WHERE status = ?
            ORDER BY updated_at DESC
        """, (status,)).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def get_rekordbox_tags_by_playlist(self, playlist_name: str) -> List[Dict]:
        """Get all Rekordbox tag queue entries for a playlist.

        Args:
            playlist_name: Playlist name to filter by

        Returns:
            List of tag queue records
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM rekordbox_tag_queue
            WHERE playlist_name = ?
            ORDER BY created_at
        """, (playlist_name,)).fetchall()

        conn.close()
        return [dict(row) for row in results]

    def clear_rekordbox_tag_queue(self, status: str = None, playlist_name: str = None) -> int:
        """Clear Rekordbox tag queue entries.

        Args:
            status: Only clear records with this status (optional)
            playlist_name: Only clear records for this playlist (optional)

        Returns:
            Number of records deleted
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if status and playlist_name:
            cursor.execute(
                "DELETE FROM rekordbox_tag_queue WHERE status = ? AND playlist_name = ?",
                (status, playlist_name)
            )
        elif status:
            cursor.execute("DELETE FROM rekordbox_tag_queue WHERE status = ?", (status,))
        elif playlist_name:
            cursor.execute("DELETE FROM rekordbox_tag_queue WHERE playlist_name = ?", (playlist_name,))
        else:
            cursor.execute("DELETE FROM rekordbox_tag_queue")

        deleted = cursor.rowcount
        conn.commit()
        conn.close()
        return deleted


if __name__ == '__main__':
    # Test database creation
    db = Database()
    db.init_schema()
    print(f"Database initialized at {db.db_path}")
