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

    def _ensure_directory(self):
        """Create database directory if it doesn't exist."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)

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

        # Initialize schema version
        cursor.execute("""
            INSERT OR IGNORE INTO metadata (key, value)
            VALUES ('schema_version', '2')
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

    def close(self):
        """Close database connection."""
        # Connection is created per-operation, so no persistent connection to close
        pass


if __name__ == '__main__':
    # Test database creation
    db = Database()
    db.init_schema()
    print(f"Database initialized at {db.db_path}")
