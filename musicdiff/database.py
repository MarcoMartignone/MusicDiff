"""
Database management for MusicDiff local state.

See docs/DATABASE.md for detailed documentation.
"""

import sqlite3
import json
import uuid
from pathlib import Path
from typing import Optional, List, Dict, Tuple
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

    # Track operations

    def upsert_track(self, track: Dict) -> None:
        """Insert or update track data.

        Args:
            track: Dict with keys: isrc, spotify_id, apple_id, apple_catalog_id,
                   title, artist, album, duration_ms
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tracks (isrc, spotify_id, apple_id, apple_catalog_id,
                               title, artist, album, duration_ms)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(isrc) DO UPDATE SET
                spotify_id = COALESCE(excluded.spotify_id, spotify_id),
                apple_id = COALESCE(excluded.apple_id, apple_id),
                apple_catalog_id = COALESCE(excluded.apple_catalog_id, apple_catalog_id),
                title = excluded.title,
                artist = excluded.artist,
                album = excluded.album,
                duration_ms = excluded.duration_ms,
                updated_at = CURRENT_TIMESTAMP
        """, (
            track.get('isrc'),
            track.get('spotify_id'),
            track.get('apple_id'),
            track.get('apple_catalog_id'),
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

    def get_track_by_apple_id(self, apple_id: str) -> Optional[Dict]:
        """Get track by Apple Music ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM tracks WHERE apple_id = ?",
            (apple_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    # Playlist operations

    def upsert_playlist(self, playlist: Dict) -> str:
        """Insert or update playlist.

        Args:
            playlist: Dict with keys: id (optional), spotify_id, apple_id, name,
                     description, public, spotify_snapshot_id

        Returns:
            Playlist ID (UUID)
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        playlist_id = playlist.get('id') or str(uuid.uuid4())

        cursor.execute("""
            INSERT INTO playlists (id, spotify_id, apple_id, name, description,
                                  public, spotify_snapshot_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                spotify_id = COALESCE(excluded.spotify_id, spotify_id),
                apple_id = COALESCE(excluded.apple_id, apple_id),
                name = excluded.name,
                description = excluded.description,
                public = excluded.public,
                spotify_snapshot_id = COALESCE(excluded.spotify_snapshot_id, spotify_snapshot_id),
                updated_at = CURRENT_TIMESTAMP
        """, (
            playlist_id,
            playlist.get('spotify_id'),
            playlist.get('apple_id'),
            playlist.get('name', ''),
            playlist.get('description', ''),
            playlist.get('public', False),
            playlist.get('spotify_snapshot_id')
        ))

        conn.commit()
        conn.close()
        return playlist_id

    def get_playlist(self, playlist_id: str) -> Optional[Dict]:
        """Get playlist by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM playlists WHERE id = ?",
            (playlist_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def get_playlist_by_spotify_id(self, spotify_id: str) -> Optional[Dict]:
        """Get playlist by Spotify ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = cursor.execute(
            "SELECT * FROM playlists WHERE spotify_id = ?",
            (spotify_id,)
        ).fetchone()

        conn.close()
        return dict(result) if result else None

    def get_all_playlists(self) -> List[Dict]:
        """Get all playlists."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("SELECT * FROM playlists").fetchall()

        conn.close()
        return [dict(row) for row in results]

    def delete_playlist(self, playlist_id: str) -> None:
        """Delete playlist."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("DELETE FROM playlists WHERE id = ?", (playlist_id,))

        conn.commit()
        conn.close()

    def set_playlist_tracks(self, playlist_id: str, track_isrcs: List[str]) -> None:
        """Replace all tracks in a playlist.

        Args:
            playlist_id: Playlist ID
            track_isrcs: List of track ISRCs in order
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Delete existing tracks
        cursor.execute("DELETE FROM playlist_tracks WHERE playlist_id = ?", (playlist_id,))

        # Insert new tracks with positions
        for position, track_isrc in enumerate(track_isrcs):
            cursor.execute("""
                INSERT INTO playlist_tracks (playlist_id, track_isrc, position)
                VALUES (?, ?, ?)
            """, (playlist_id, track_isrc, position))

        # Update track count
        cursor.execute("""
            UPDATE playlists SET track_count = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (len(track_isrcs), playlist_id))

        conn.commit()
        conn.close()

    def get_playlist_tracks(self, playlist_id: str) -> List[str]:
        """Get track ISRCs for a playlist in order."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT track_isrc FROM playlist_tracks
            WHERE playlist_id = ?
            ORDER BY position
        """, (playlist_id,)).fetchall()

        conn.close()
        return [row[0] for row in results]

    # Liked songs operations

    def set_liked_songs(self, track_isrcs: List[str], platform: str) -> None:
        """Set liked songs for a platform.

        Args:
            track_isrcs: List of track ISRCs
            platform: 'spotify' or 'apple'
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Clear existing liked status for this platform
        if platform == 'spotify':
            cursor.execute("DELETE FROM liked_songs WHERE spotify_liked = 1")
        else:
            cursor.execute("DELETE FROM liked_songs WHERE apple_liked = 1")

        # Insert liked songs
        for isrc in track_isrcs:
            if platform == 'spotify':
                cursor.execute("""
                    INSERT INTO liked_songs (track_isrc, spotify_liked)
                    VALUES (?, 1)
                    ON CONFLICT(track_isrc) DO UPDATE SET spotify_liked = 1
                """, (isrc,))
            else:
                cursor.execute("""
                    INSERT INTO liked_songs (track_isrc, apple_liked)
                    VALUES (?, 1)
                    ON CONFLICT(track_isrc) DO UPDATE SET apple_liked = 1
                """, (isrc,))

        conn.commit()
        conn.close()

    def get_liked_songs(self, platform: Optional[str] = None) -> List[str]:
        """Get liked song ISRCs.

        Args:
            platform: 'spotify', 'apple', or None for both

        Returns:
            List of track ISRCs
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        if platform == 'spotify':
            results = cursor.execute(
                "SELECT track_isrc FROM liked_songs WHERE spotify_liked = 1"
            ).fetchall()
        elif platform == 'apple':
            results = cursor.execute(
                "SELECT track_isrc FROM liked_songs WHERE apple_liked = 1"
            ).fetchall()
        else:
            results = cursor.execute(
                "SELECT track_isrc FROM liked_songs WHERE spotify_liked = 1 OR apple_liked = 1"
            ).fetchall()

        conn.close()
        return [row[0] for row in results]

    # Sync log operations

    def add_sync_log(self, status: str, changes: int, conflicts: int,
                     details: Dict, duration: float = 0, auto_sync: bool = False) -> None:
        """Add sync log entry.

        Args:
            status: 'success', 'partial', or 'failed'
            changes: Number of changes applied
            conflicts: Number of conflicts detected
            details: Dict with detailed change information
            duration: Sync duration in seconds
            auto_sync: Whether this was an automatic sync
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO sync_log (status, changes_applied, conflicts_count,
                                 details, duration_seconds, auto_sync)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (status, changes, conflicts, json.dumps(details), duration, auto_sync))

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

    # Conflict operations

    def add_conflict(self, conflict_type: str, entity_id: str,
                    spotify_data: Dict, apple_data: Dict,
                    local_data: Optional[Dict] = None) -> int:
        """Add a conflict.

        Args:
            conflict_type: 'playlist', 'liked_song', 'album'
            entity_id: ID of the conflicting entity
            spotify_data: Spotify state as dict
            apple_data: Apple Music state as dict
            local_data: Local state as dict (optional)

        Returns:
            Conflict ID
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO conflicts (type, entity_id, spotify_data, apple_data, local_data)
            VALUES (?, ?, ?, ?, ?)
        """, (
            conflict_type,
            entity_id,
            json.dumps(spotify_data),
            json.dumps(apple_data),
            json.dumps(local_data) if local_data else None
        ))

        conflict_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return conflict_id

    def get_unresolved_conflicts(self) -> List[Dict]:
        """Get all unresolved conflicts."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        results = cursor.execute("""
            SELECT * FROM conflicts
            WHERE resolved_at IS NULL
            ORDER BY created_at
        """).fetchall()

        conn.close()

        conflicts = []
        for row in results:
            conflict = dict(row)
            conflict['spotify_data'] = json.loads(conflict['spotify_data'])
            conflict['apple_data'] = json.loads(conflict['apple_data'])
            if conflict.get('local_data'):
                conflict['local_data'] = json.loads(conflict['local_data'])
            conflicts.append(conflict)

        return conflicts

    def resolve_conflict(self, conflict_id: int, resolution: str) -> None:
        """Mark conflict as resolved.

        Args:
            conflict_id: Conflict ID
            resolution: Resolution choice ('spotify', 'apple', 'manual', 'skip')
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE conflicts
            SET resolved_at = CURRENT_TIMESTAMP, resolution = ?
            WHERE id = ?
        """, (resolution, conflict_id))

        conn.commit()
        conn.close()

    def close(self):
        """Close database connection."""
        # Connection is created per-operation, so no persistent connection to close
        pass


if __name__ == '__main__':
    # Test database creation
    db = Database()
    db.init_schema()
    print(f"Database initialized at {db.db_path}")
