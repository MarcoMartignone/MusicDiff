"""
Rekordbox integration for MusicDiff.

This module provides functionality to add tracks to Rekordbox Collection
and apply "My Tags" for smart playlist filtering.

SAFETY: This module modifies the Rekordbox database. It includes:
- Automatic backup before any writes
- Check that Rekordbox is not running
- Dry-run mode for previewing changes
"""

import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any

# Optional import - pyrekordbox may not be installed
try:
    from pyrekordbox import Rekordbox6Database
    from pyrekordbox.db6 import tables as rb_tables
    PYREKORDBOX_AVAILABLE = True
except ImportError:
    PYREKORDBOX_AVAILABLE = False
    Rekordbox6Database = None
    rb_tables = None


# Custom exceptions
class RekordboxError(Exception):
    """Base exception for Rekordbox-related errors."""
    pass


class RekordboxNotAvailableError(RekordboxError):
    """Raised when pyrekordbox is not installed."""
    pass


class RekordboxRunningError(RekordboxError):
    """Raised when Rekordbox application is currently running."""
    pass


class RekordboxDatabaseError(RekordboxError):
    """Raised when there's an issue with the Rekordbox database."""
    pass


@dataclass
class TagResult:
    """Result of a tag operation."""
    success: bool
    track_added_to_collection: bool = False
    tag_created: bool = False
    smart_playlist_created: bool = False
    tag_applied: bool = False
    content_id: Optional[str] = None
    tag_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BatchTagResult:
    """Result of batch tag operations."""
    total: int = 0
    successful: int = 0
    failed: int = 0
    skipped: int = 0
    tracks_added: int = 0
    tags_created: int = 0
    smart_playlists_created: int = 0
    errors: List[str] = field(default_factory=list)


def get_default_rekordbox_db_path() -> Path:
    """Get the default Rekordbox database path for macOS."""
    return Path.home() / "Library" / "Pioneer" / "rekordbox" / "master.db"


def get_rekordbox_backup_dir() -> Path:
    """Get the directory for Rekordbox database backups."""
    backup_dir = Path.home() / ".musicdiff" / "rekordbox_backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    return backup_dir


class RekordboxClient:
    """
    Client for interacting with Rekordbox database.

    IMPORTANT: Always use with caution. This modifies the Rekordbox database.
    - Always close Rekordbox before using write operations
    - Use dry_run=True to preview changes without modifying
    - Backups are created automatically before writes
    """

    def __init__(self, db_path: str = None, dry_run: bool = False):
        """
        Initialize the Rekordbox client.

        Args:
            db_path: Path to Rekordbox master.db. Uses default if not specified.
            dry_run: If True, don't actually modify the database (preview mode).
        """
        self.db_path = Path(db_path) if db_path else get_default_rekordbox_db_path()
        self.dry_run = dry_run
        self._db = None
        self._backup_created = False
        # Lookup caches for O(1) access (built lazily on first use)
        self._path_to_content = None      # {path: content_object}
        self._tag_name_to_tag = None      # {name: tag_object}
        self._existing_tag_links = None   # {(content_id, tag_id)}

    def check_available(self) -> bool:
        """
        Check if pyrekordbox is installed and database exists.

        Returns:
            True if available, False otherwise.
        """
        if not PYREKORDBOX_AVAILABLE:
            return False
        if not self.db_path.exists():
            return False
        return True

    def get_availability_message(self) -> str:
        """Get a detailed message about availability status."""
        if not PYREKORDBOX_AVAILABLE:
            return (
                "pyrekordbox is not installed.\n"
                "Install with: pip install pyrekordbox\n"
                "Also requires: brew install sqlcipher"
            )
        if not self.db_path.exists():
            return f"Rekordbox database not found at: {self.db_path}"
        return "Rekordbox integration is available."

    def check_rekordbox_running(self) -> bool:
        """
        Check if Rekordbox application is currently running.

        Returns:
            True if Rekordbox is running, False otherwise.
        """
        try:
            # Check for rekordbox process on macOS
            result = subprocess.run(
                ['pgrep', '-x', 'rekordbox'],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            # If pgrep fails, try ps
            try:
                result = subprocess.run(
                    ['ps', 'aux'],
                    capture_output=True,
                    text=True,
                    timeout=5
                )
                return 'rekordbox' in result.stdout.lower()
            except Exception:
                # Can't determine, assume not running
                return False

    def create_backup(self) -> Optional[Path]:
        """
        Create a backup of the Rekordbox database.

        Returns:
            Path to backup file, or None if backup failed.
        """
        if not self.db_path.exists():
            return None

        backup_dir = get_rekordbox_backup_dir()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_path = backup_dir / f"master_backup_{timestamp}.db"

        try:
            shutil.copy2(self.db_path, backup_path)
            self._backup_created = True
            return backup_path
        except Exception as e:
            raise RekordboxDatabaseError(f"Failed to create backup: {e}")

    def _ensure_safe_to_write(self):
        """Ensure it's safe to write to the database."""
        if self.check_rekordbox_running():
            raise RekordboxRunningError(
                "Rekordbox is currently running. Please close it before modifying the database."
            )

    def _get_db(self):
        """Get database connection, creating backup on first write access."""
        if self._db is None:
            if not self.check_available():
                raise RekordboxNotAvailableError(self.get_availability_message())

            try:
                self._db = Rekordbox6Database()
            except Exception as e:
                raise RekordboxDatabaseError(f"Failed to open Rekordbox database: {e}")

        return self._db

    def _ensure_backup_for_write(self):
        """Ensure a backup exists before any write operation."""
        if not self._backup_created and not self.dry_run:
            self.create_backup()

    def close(self):
        """Close the database connection."""
        if self._db is not None:
            try:
                self._db.close()
            except Exception:
                pass
            self._db = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def _build_caches(self):
        """
        Build lookup caches for O(1) access.

        Called lazily on first use. Loads all data once into memory
        for fast lookups instead of iterating through the DB each time.
        """
        db = self._get_db()

        # Cache 1: Path -> Content (with symlink alternatives)
        self._path_to_content = {}
        for content in db.get_content():
            if content.FolderPath:
                path = str(content.FolderPath)
                self._path_to_content[path] = content
                # Also add symlink alternative for path matching
                if '/Documents/MUSIC_LINK/' in path:
                    alt_path = path.replace(
                        '/Documents/MUSIC_LINK/',
                        '/Library/CloudStorage/SynologyDrive-MarcoMartignone/MUSIC/'
                    )
                    self._path_to_content[alt_path] = content

        # Cache 2: Tag name -> Tag object
        self._tag_name_to_tag = {}
        for tag in db.query(rb_tables.DjmdMyTag).all():
            self._tag_name_to_tag[tag.Name] = tag

        # Cache 3: Existing tag links as set for O(1) membership check
        self._existing_tag_links = set()
        for link in db.query(rb_tables.DjmdSongMyTag).all():
            self._existing_tag_links.add((str(link.ContentID), str(link.MyTagID)))

    # ==================== READ OPERATIONS ====================

    def find_track_by_path(self, file_path: str) -> Optional[Any]:
        """
        Find a track in Rekordbox by its file path.

        Uses cached path lookup for O(1) performance.
        Handles symlinks automatically via cache built in _build_caches().

        Args:
            file_path: Full path to the audio file.

        Returns:
            DjmdContent object if found, None otherwise.
        """
        # Build caches on first use
        if self._path_to_content is None:
            self._build_caches()

        # Direct O(1) lookup
        return self._path_to_content.get(file_path)

    def get_tag_by_name(self, tag_name: str) -> Optional[Any]:
        """
        Find a My Tag by name.

        Uses cached lookup for O(1) performance.

        Args:
            tag_name: Name of the tag to find.

        Returns:
            DjmdMyTag object if found, None otherwise.
        """
        # Build caches on first use
        if self._tag_name_to_tag is None:
            self._build_caches()

        # Direct O(1) lookup
        return self._tag_name_to_tag.get(tag_name)

    def list_all_tags(self) -> List[Dict[str, Any]]:
        """
        List all My Tags defined in Rekordbox.

        Returns:
            List of tag dictionaries with id, name, etc.
        """
        db = self._get_db()

        try:
            tags = []
            for tag in db.query(rb_tables.DjmdMyTag).all():
                tags.append({
                    'id': tag.ID,
                    'name': tag.Name,
                    'parent_id': getattr(tag, 'ParentID', None),
                    'seq': getattr(tag, 'Seq', None),
                })
            return tags
        except Exception as e:
            raise RekordboxDatabaseError(f"Error listing tags: {e}")

    def get_smart_playlist_by_name(self, name: str) -> Optional[Any]:
        """
        Find a smart playlist by name.

        Args:
            name: Name of the smart playlist.

        Returns:
            DjmdPlaylist object if found, None otherwise.
        """
        db = self._get_db()

        try:
            for playlist in db.query(rb_tables.DjmdPlaylist).all():
                # Attribute 4 indicates smart playlist
                if playlist.Name == name and getattr(playlist, 'Attribute', 0) == 4:
                    return playlist
            return None
        except Exception as e:
            raise RekordboxDatabaseError(f"Error searching for smart playlist: {e}")

    def list_smart_playlists(self) -> List[Dict[str, Any]]:
        """
        List all smart playlists in Rekordbox.

        Returns:
            List of smart playlist dictionaries.
        """
        db = self._get_db()

        try:
            playlists = []
            for playlist in db.query(rb_tables.DjmdPlaylist).all():
                if getattr(playlist, 'Attribute', 0) == 4:
                    playlists.append({
                        'id': playlist.ID,
                        'name': playlist.Name,
                    })
            return playlists
        except Exception as e:
            raise RekordboxDatabaseError(f"Error listing smart playlists: {e}")

    def get_track_tags(self, content_id: str) -> List[str]:
        """
        Get all My Tags applied to a track.

        Args:
            content_id: The content ID of the track.

        Returns:
            List of tag names applied to the track.
        """
        db = self._get_db()

        try:
            tags = []
            for song_tag in db.query(rb_tables.DjmdSongMyTag).all():
                if str(song_tag.ContentID) == str(content_id):
                    # Find the tag name
                    tag = db.query(rb_tables.DjmdMyTag).filter(
                        rb_tables.DjmdMyTag.ID == song_tag.MyTagID
                    ).first()
                    if tag:
                        tags.append(tag.Name)
            return tags
        except Exception as e:
            raise RekordboxDatabaseError(f"Error getting track tags: {e}")

    # ==================== WRITE OPERATIONS ====================
    # These operations modify the database and require extra care

    def add_track_to_collection(
        self,
        file_path: str,
        title: str = None,
        artist: str = None,
        album: str = None
    ) -> Optional[str]:
        """
        Add a track to the Rekordbox Collection.

        CAUTION: This modifies the Rekordbox database.

        Args:
            file_path: Full path to the audio file.
            title: Track title (extracted from file if not provided).
            artist: Artist name (extracted from file if not provided).
            album: Album name (extracted from file if not provided).

        Returns:
            Content ID of the added track, or None if dry_run.
        """
        self._ensure_safe_to_write()
        self._ensure_backup_for_write()

        if self.dry_run:
            return None

        db = self._get_db()
        file_path = Path(file_path).resolve()

        # Check if already exists
        existing = self.find_track_by_path(str(file_path))
        if existing:
            return str(existing.ID)

        # Verify file exists
        if not file_path.exists():
            raise RekordboxDatabaseError(f"File not found: {file_path}")

        try:
            # Use pyrekordbox's add_content method
            kwargs = {}
            if title:
                kwargs['Title'] = title

            content = db.add_content(str(file_path), **kwargs)
            db.commit()
            return str(content.ID)
        except ValueError as e:
            # pyrekordbox raises ValueError for invalid files or duplicates
            raise RekordboxDatabaseError(f"Cannot add track: {e}")
        except Exception as e:
            raise RekordboxDatabaseError(f"Error adding track: {e}")

    def get_or_create_tag(self, tag_name: str) -> Optional[str]:
        """
        Get existing tag or create a new one.

        Args:
            tag_name: Name of the tag.

        Returns:
            Tag ID, or None if dry_run and tag doesn't exist.
        """
        import uuid as uuid_module

        # First check if tag exists (uses cache)
        existing = self.get_tag_by_name(tag_name)
        if existing:
            return str(existing.ID)

        # Need to create - check safety
        self._ensure_safe_to_write()
        self._ensure_backup_for_write()

        if self.dry_run:
            return None

        db = self._get_db()

        try:
            # Generate IDs
            new_id = db.generate_unused_id(rb_tables.DjmdMyTag)
            usn = db.autoincrement_usn()
            new_uuid = str(uuid_module.uuid4())
            now = datetime.now()

            # Get max Seq from cache (already built)
            max_seq = 0
            if self._tag_name_to_tag:
                for tag in self._tag_name_to_tag.values():
                    if tag.Seq and tag.Seq > max_seq:
                        max_seq = tag.Seq
            new_seq = max_seq + 1

            # Create the tag (ParentID=4 means under "Playlist" category)
            # Rekordbox has parent categories: 1=Genre, 2=Components, 3=Situation, 4=Playlist
            new_tag = rb_tables.DjmdMyTag(
                ID=str(new_id),
                Seq=new_seq,
                Name=tag_name,
                Attribute=0,  # Regular tag
                ParentID='4',  # Under "Playlist" category
                UUID=new_uuid,
                rb_data_status=0,
                rb_local_data_status=0,
                rb_local_deleted=0,
                rb_local_synced=0,
                usn=usn,
                rb_local_usn=usn,
                created_at=now,
                updated_at=now
            )

            db.add(new_tag)
            db.commit()

            # Update cache
            if self._tag_name_to_tag is not None:
                self._tag_name_to_tag[tag_name] = new_tag

            return str(new_id)
        except Exception as e:
            raise RekordboxDatabaseError(f"Error creating tag: {e}")

    def get_or_create_smart_playlist(self, name: str, tag_id: str) -> Optional[str]:
        """
        Get existing smart playlist or create one that filters by tag.

        Args:
            name: Name of the smart playlist.
            tag_id: ID of the tag to filter by.

        Returns:
            Playlist ID, or None if dry_run and doesn't exist.
        """
        # First check if exists
        existing = self.get_smart_playlist_by_name(name)
        if existing:
            return str(existing.ID)

        # Need to create - check safety
        self._ensure_safe_to_write()
        self._ensure_backup_for_write()

        if self.dry_run:
            return None

        db = self._get_db()

        try:
            # Import smartlist module
            from pyrekordbox.db6 import smartlist

            # Create a SmartList that filters by myTag CONTAINS tag_id
            # Rekordbox expects the tag ID, not the tag name
            sl = smartlist.SmartList()
            sl.add_condition(
                prop='myTag',
                operator=smartlist.Operator.CONTAINS.value,
                value_left=str(tag_id),  # Must be tag ID, not name
                value_right='',
                unit=''
            )

            # Create the smart playlist
            playlist = db.create_smart_playlist(name=name, smart_list=sl)
            db.commit()
            return str(playlist.ID)
        except Exception as e:
            raise RekordboxDatabaseError(f"Error creating smart playlist: {e}")

    def apply_tag_to_track(self, content_id: str, tag_id: str) -> bool:
        """
        Apply a My Tag to a track.

        Uses cached lookup for O(1) check if already applied.

        Args:
            content_id: The content ID of the track.
            tag_id: The ID of the tag to apply.

        Returns:
            True if successful (or dry_run), False otherwise.
        """
        import uuid as uuid_module

        # Build caches on first use
        if self._existing_tag_links is None:
            self._build_caches()

        # O(1) check if already applied
        key = (str(content_id), str(tag_id))
        if key in self._existing_tag_links:
            return True  # Already applied

        self._ensure_safe_to_write()
        self._ensure_backup_for_write()

        if self.dry_run:
            return True

        db = self._get_db()

        try:
            # Generate IDs
            new_id = db.generate_unused_id(rb_tables.DjmdSongMyTag)
            usn = db.autoincrement_usn()
            new_uuid = str(uuid_module.uuid4())
            now = datetime.now()

            # Use simple incrementing track number (order doesn't matter much)
            track_no = len(self._existing_tag_links) + 1

            # Create the song-tag relationship
            song_tag = rb_tables.DjmdSongMyTag(
                ID=str(new_id),
                MyTagID=str(tag_id),
                ContentID=str(content_id),
                TrackNo=track_no,
                UUID=new_uuid,
                rb_data_status=0,
                rb_local_data_status=0,
                rb_local_deleted=0,
                rb_local_synced=0,
                usn=usn,
                rb_local_usn=usn,
                created_at=now,
                updated_at=now
            )

            db.add(song_tag)
            db.commit()

            # Update cache
            self._existing_tag_links.add(key)
            return True
        except Exception as e:
            raise RekordboxDatabaseError(f"Error applying tag: {e}")

    def process_track(
        self,
        file_path: str,
        playlist_name: str,
        metadata: Dict[str, str] = None
    ) -> TagResult:
        """
        Process a track: add to collection, create tag, create smart playlist, apply tag.

        This is the main method for the full workflow.

        Args:
            file_path: Path to the audio file.
            playlist_name: Name for the tag and smart playlist.
            metadata: Optional dict with title, artist, album.

        Returns:
            TagResult with details of what was done.
        """
        result = TagResult(success=False)
        metadata = metadata or {}

        try:
            # Step 1: Check if track exists, add if not
            content = self.find_track_by_path(file_path)
            if content:
                result.content_id = str(content.ID)
            else:
                content_id = self.add_track_to_collection(
                    file_path,
                    title=metadata.get('title'),
                    artist=metadata.get('artist'),
                    album=metadata.get('album')
                )
                result.content_id = content_id
                result.track_added_to_collection = True

            # Step 2: Get or create the tag
            tag = self.get_tag_by_name(playlist_name)
            if tag:
                result.tag_id = str(tag.ID)
            else:
                tag_id = self.get_or_create_tag(playlist_name)
                result.tag_id = tag_id
                result.tag_created = True

            # Step 3: Get or create smart playlist (filters by tag ID)
            smart_playlist = self.get_smart_playlist_by_name(playlist_name)
            if not smart_playlist and result.tag_id:
                self.get_or_create_smart_playlist(playlist_name, result.tag_id)
                result.smart_playlist_created = True

            # Step 4: Apply tag to track
            if result.content_id and result.tag_id:
                self.apply_tag_to_track(result.content_id, result.tag_id)
                result.tag_applied = True

            result.success = True

        except NotImplementedError as e:
            result.error = str(e)
        except RekordboxError as e:
            result.error = str(e)
        except Exception as e:
            result.error = f"Unexpected error: {e}"

        return result
