"""
Database management for MusicDiff local state.

See docs/DATABASE.md for detailed documentation.
"""

import sqlite3
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

    def init_schema(self):
        """Initialize database schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Enable foreign keys
        cursor.execute("PRAGMA foreign_keys = ON")

        # Tracks table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS tracks (
                isrc TEXT PRIMARY KEY,
                spotify_id TEXT UNIQUE,
                apple_id TEXT UNIQUE,
                apple_catalog_id TEXT,
                title TEXT NOT NULL,
                artist TEXT NOT NULL,
                album TEXT NOT NULL,
                duration_ms INTEGER NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_spotify_id ON tracks(spotify_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_apple_id ON tracks(apple_id)")

        # Playlists table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlists (
                id TEXT PRIMARY KEY,
                spotify_id TEXT UNIQUE,
                apple_id TEXT UNIQUE,
                name TEXT NOT NULL,
                description TEXT DEFAULT '',
                public BOOLEAN DEFAULT 0,
                spotify_snapshot_id TEXT,
                track_count INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_spotify ON playlists(spotify_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_playlist_apple ON playlists(apple_id)")

        # Playlist tracks junction table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS playlist_tracks (
                playlist_id TEXT NOT NULL,
                track_isrc TEXT NOT NULL,
                position INTEGER NOT NULL,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (playlist_id, track_isrc),
                FOREIGN KEY (playlist_id) REFERENCES playlists(id) ON DELETE CASCADE,
                FOREIGN KEY (track_isrc) REFERENCES tracks(isrc) ON DELETE CASCADE
            )
        """)

        # Liked songs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS liked_songs (
                track_isrc TEXT PRIMARY KEY,
                spotify_liked BOOLEAN DEFAULT 0,
                apple_liked BOOLEAN DEFAULT 0,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (track_isrc) REFERENCES tracks(isrc) ON DELETE CASCADE
            )
        """)

        # Albums table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS albums (
                id TEXT PRIMARY KEY,
                spotify_id TEXT UNIQUE,
                apple_id TEXT UNIQUE,
                name TEXT NOT NULL,
                artist TEXT NOT NULL,
                release_date TEXT,
                total_tracks INTEGER,
                added_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Sync log table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sync_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                status TEXT NOT NULL,
                changes_applied INTEGER DEFAULT 0,
                conflicts_count INTEGER DEFAULT 0,
                duration_seconds REAL,
                details TEXT,
                auto_sync BOOLEAN DEFAULT 0
            )
        """)

        cursor.execute("CREATE INDEX IF NOT EXISTS idx_sync_timestamp ON sync_log(timestamp)")

        # Conflicts table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS conflicts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                type TEXT NOT NULL,
                entity_id TEXT NOT NULL,
                spotify_data TEXT,
                apple_data TEXT,
                local_data TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                resolved_at TIMESTAMP,
                resolution TEXT
            )
        """)

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
            VALUES ('schema_version', '1')
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

    # TODO: Implement remaining methods
    # - upsert_track()
    # - get_track_by_isrc()
    # - upsert_playlist()
    # - get_all_playlists()
    # - set_playlist_tracks()
    # - set_liked_songs()
    # - add_sync_log()
    # - get_sync_history()
    # - add_conflict()
    # - get_unresolved_conflicts()
    # etc.

    def close(self):
        """Close database connection."""
        # Connection is created per-operation, so no persistent connection to close
        pass


if __name__ == '__main__':
    # Test database creation
    db = Database()
    db.init_schema()
    print(f"Database initialized at {db.db_path}")
