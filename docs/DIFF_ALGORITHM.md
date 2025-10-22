# Diff Algorithm Documentation

## Overview

The diff engine (`diff.py`) implements a 3-way merge algorithm to detect and categorize changes between Spotify, Apple Music, and the local state database. This is the core of MusicDiff's synchronization logic.

## The 3-Way Merge

Similar to Git's merge algorithm, MusicDiff compares three states:

```
       Local State (Base)
           /      \
          /        \
    Spotify      Apple Music
   (Remote 1)    (Remote 2)
```

**Key Principle**: Changes are detected by comparing each platform against the local state (last sync), not against each other.

## Change Categories

### 1. Auto-Merge (Safe)

Changes on one platform only, unchanged on the other.

**Examples:**
- Spotify: Added track to playlist | Local: unchanged | Apple: unchanged
  → **Action**: Add track to Apple Music playlist

- Apple: Liked 5 songs | Local: unchanged | Spotify: unchanged
  → **Action**: Like same 5 songs on Spotify

### 2. Conflict (Requires User Input)

Both platforms changed the same entity differently.

**Examples:**
- Spotify: Added track A to playlist | Local: original | Apple: Added track B to playlist
  → **Action**: Show diff UI, user decides

- Spotify: Deleted playlist | Local: exists | Apple: Modified playlist
  → **Action**: Ask user (delete everywhere or keep Apple version?)

### 3. No Change

Both platforms match local state.

**Action**: Skip, no sync needed.

## Algorithm Implementation

### High-Level Flow

```python
def compute_diff(local_state, spotify_state, apple_state) -> DiffResult:
    """
    Compute 3-way diff between platforms and local state.

    Returns:
        DiffResult with auto-merge changes and conflicts
    """

    # 1. Detect Spotify changes
    spotify_changes = diff(local_state, spotify_state)

    # 2. Detect Apple Music changes
    apple_changes = diff(local_state, apple_state)

    # 3. Categorize changes
    auto_merge = []
    conflicts = []

    for entity in all_entities:
        spotify_change = spotify_changes.get(entity)
        apple_change = apple_changes.get(entity)

        if spotify_change and not apple_change:
            # Changed on Spotify only
            auto_merge.append(Change(entity, 'spotify', spotify_change))

        elif apple_change and not spotify_change:
            # Changed on Apple only
            auto_merge.append(Change(entity, 'apple', apple_change))

        elif spotify_change and apple_change:
            # Changed on both - conflict!
            conflicts.append(Conflict(entity, spotify_change, apple_change))

        # else: No change on either platform

    return DiffResult(auto_merge, conflicts)
```

## Entity-Specific Algorithms

### Playlist Diff

Playlists have complex state: name, description, and tracks (ordered list).

#### Detection Strategy

```python
def diff_playlist(local: Playlist, remote: Playlist) -> Optional[PlaylistChange]:
    """Detect changes to a playlist."""

    changes = {}

    # Check metadata
    if local.name != remote.name:
        changes['name'] = (local.name, remote.name)

    if local.description != remote.description:
        changes['description'] = (local.description, remote.description)

    # Check tracks (order matters!)
    local_track_ids = [t.isrc for t in local.tracks]
    remote_track_ids = [t.isrc for t in remote.tracks]

    if local_track_ids != remote_track_ids:
        # Compute track diff
        track_diff = compute_track_diff(local_track_ids, remote_track_ids)
        changes['tracks'] = track_diff

    if not changes:
        return None  # No changes

    return PlaylistChange(changes)
```

#### Track Order Diff

For playlists, track order matters. We use a list diff algorithm.

```python
def compute_track_diff(local_tracks: List[str], remote_tracks: List[str]) -> TrackDiff:
    """Compute diff between two track lists."""

    local_set = set(local_tracks)
    remote_set = set(remote_tracks)

    added = remote_set - local_set
    removed = local_set - remote_set

    # Check for reordering (same tracks, different order)
    if local_set == remote_set and local_tracks != remote_tracks:
        reordered = True
    else:
        reordered = False

    return TrackDiff(
        added=list(added),
        removed=list(removed),
        reordered=reordered,
        new_order=remote_tracks if reordered else None
    )
```

**Conflict Resolution:**

When both platforms modify the same playlist:

1. Show side-by-side comparison
2. Highlight differences (added/removed/reordered)
3. User chooses:
   - Keep Spotify version
   - Keep Apple version
   - Manual merge (interactive track-by-track selection)

---

### Liked Songs Diff

Liked songs are an unordered set.

```python
def diff_liked_songs(local: Set[str], remote: Set[str]) -> Optional[LikedSongsChange]:
    """Detect changes to liked songs."""

    added = remote - local
    removed = local - remote

    if not added and not removed:
        return None

    return LikedSongsChange(added=list(added), removed=list(removed))
```

**Conflict Scenarios:**

- **Spotify**: Liked songs [A, B, C, D]
- **Local**: Liked songs [A, B, C]
- **Apple**: Liked songs [A, B, C, E]

**Analysis:**
- Spotify added: D
- Apple added: E

**Resolution**: Not a conflict! Both are auto-merge.
- Sync result: [A, B, C, D, E] on both platforms

**True Conflict Example:**
- **Spotify**: Removed C
- **Local**: [A, B, C]
- **Apple**: Added D

**Analysis:**
- Spotify removed: C
- Apple added: D

**Resolution**: Also not a conflict (different songs).

**Actual Conflict:**
- **Spotify**: Removed C
- **Local**: [A, B, C]
- **Apple**: Also removed C

Not a conflict - they agree! Skip.

**Real Conflict Case:**
- **Spotify**: Liked song C
- **Local**: C not liked
- **Apple**: Unliked song C (was liked before)

This is rare but possible. Resolution: Ask user.

---

### Album Diff

Albums are simpler - just a set of saved albums.

```python
def diff_albums(local: Set[str], remote: Set[str]) -> Optional[AlbumChange]:
    """Detect changes to saved albums."""

    added = remote - local
    removed = local - remote

    if not added and not removed:
        return None

    return AlbumChange(added=list(added), removed=list(removed))
```

---

## Change Types

### Enum: `ChangeType`

```python
class ChangeType(Enum):
    PLAYLIST_CREATED = "playlist_created"
    PLAYLIST_UPDATED = "playlist_updated"
    PLAYLIST_DELETED = "playlist_deleted"
    LIKED_SONG_ADDED = "liked_song_added"
    LIKED_SONG_REMOVED = "liked_song_removed"
    ALBUM_ADDED = "album_added"
    ALBUM_REMOVED = "album_removed"
```

### Class: `Change`

```python
@dataclass
class Change:
    entity_type: str        # 'playlist', 'liked_song', 'album'
    entity_id: str
    change_type: ChangeType
    source_platform: str    # 'spotify' or 'apple'
    target_platform: str    # 'apple' or 'spotify'
    data: dict              # Platform-specific data for applying change
```

### Class: `Conflict`

```python
@dataclass
class Conflict:
    entity_type: str
    entity_id: str
    spotify_change: Change
    apple_change: Change
    resolution: Optional[str] = None  # User's choice: 'spotify', 'apple', 'manual'
```

### Class: `DiffResult`

```python
@dataclass
class DiffResult:
    auto_merge: List[Change]
    conflicts: List[Conflict]

    def summary(self) -> str:
        return f"{len(self.auto_merge)} auto-merge changes, {len(self.conflicts)} conflicts"
```

## Special Cases

### Case 1: Track Unavailable

**Scenario**: Track exists on Spotify but not available on Apple Music.

**Detection**:
```python
def check_track_availability(track: Track, target_platform: str) -> bool:
    """Check if track is available on target platform."""

    if target_platform == 'apple':
        apple_track = apple_client.search_track(isrc=track.isrc)
        return apple_track is not None

    elif target_platform == 'spotify':
        spotify_track = spotify_client.search_track(isrc=track.isrc)
        return spotify_track is not None
```

**Resolution Options**:
1. **Skip**: Don't sync this track
2. **Mark as conflict**: Show to user, let them decide
3. **Find alternative**: Search for similar track (future enhancement)

MusicDiff chooses **Option 2** (mark as conflict).

---

### Case 2: Playlist Created on Both Platforms

**Scenario**: User created "Workout Mix" on both platforms independently.

**Detection**:
- Both playlists absent from local state
- Same name (case-insensitive match)

**Resolution**:
- Treat as two separate playlists (don't auto-link)
- User can manually merge via conflict resolution

---

### Case 3: Deleted on One Platform

**Scenario**:
- **Spotify**: Deleted playlist
- **Local**: Playlist exists
- **Apple**: Unchanged

**Analysis**: Spotify deleted → Apply to Apple (auto-merge)

**Edge Case**:
- **Spotify**: Deleted playlist
- **Local**: Playlist exists
- **Apple**: Modified playlist

**Analysis**: Conflict! User must choose.

---

## Performance Optimizations

### 1. Incremental Diff

Only diff entities that changed since last sync.

```python
def incremental_diff(last_sync_timestamp: datetime) -> DiffResult:
    """Only diff entities modified since last sync."""

    # Check Spotify snapshot IDs
    spotify_playlists = [p for p in spotify_client.fetch_playlists()
                         if p.snapshot_id != local_db.get_snapshot(p.id)]

    # Only diff changed playlists
    for playlist in spotify_playlists:
        # ... compute diff
```

### 2. Parallel Processing

Diff playlists in parallel for large libraries.

```python
from concurrent.futures import ThreadPoolExecutor

def diff_all_playlists(local, spotify, apple) -> List[PlaylistChange]:
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = []
        for playlist_id in all_playlist_ids:
            future = executor.submit(
                diff_playlist,
                local.get(playlist_id),
                spotify.get(playlist_id),
                apple.get(playlist_id)
            )
            futures.append(future)

        return [f.result() for f in futures if f.result() is not None]
```

### 3. Hash-Based Change Detection

Use content hashing to quickly detect changes.

```python
def playlist_hash(playlist: Playlist) -> str:
    """Generate hash of playlist content."""
    content = f"{playlist.name}|{playlist.description}|{'|'.join(playlist.track_isrcs)}"
    return hashlib.sha256(content.encode()).hexdigest()

# Store hash in database, compare on fetch
if playlist_hash(spotify_playlist) != local_db.get_hash(playlist.id):
    # Playlist changed, compute full diff
```

## Testing Strategy

### Unit Tests

```python
def test_auto_merge_spotify_change():
    local = Playlist(name="Test", tracks=["A", "B"])
    spotify = Playlist(name="Test", tracks=["A", "B", "C"])  # Added C
    apple = Playlist(name="Test", tracks=["A", "B"])         # Unchanged

    result = compute_diff(local, spotify, apple)

    assert len(result.auto_merge) == 1
    assert len(result.conflicts) == 0
    assert result.auto_merge[0].change_type == ChangeType.PLAYLIST_UPDATED

def test_conflict_both_platforms_changed():
    local = Playlist(name="Test", tracks=["A", "B"])
    spotify = Playlist(name="Test", tracks=["A", "B", "C"])  # Added C
    apple = Playlist(name="Test", tracks=["A", "B", "D"])    # Added D

    result = compute_diff(local, spotify, apple)

    assert len(result.auto_merge) == 0
    assert len(result.conflicts) == 1
```

## References

- [Git's 3-Way Merge](https://git-scm.com/docs/git-merge#_three_way_merge)
- [Diff Algorithms Explained](https://blog.jcoglan.com/2017/02/12/the-myers-diff-algorithm-part-1/)
