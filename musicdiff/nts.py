"""
NTS Radio API integration.

Fetches episode metadata and tracklists from NTS Live (https://www.nts.live).
"""

from typing import List, Optional, Tuple
from dataclasses import dataclass, field
import requests
import re
import time


@dataclass
class NTSTrack:
    """Represents a track from an NTS show."""
    artist: str
    title: str
    uid: str
    offset: Optional[int] = None
    duration: Optional[int] = None


@dataclass
class NTSEpisode:
    """Represents an NTS episode with its tracklist."""
    name: str
    show_alias: str
    episode_alias: str
    broadcast_date: str
    description: str
    tracklist: List[NTSTrack] = field(default_factory=list)


def parse_nts_url(url: str) -> Tuple[str, str]:
    """
    Parse an NTS show URL to extract show and episode aliases.

    Args:
        url: NTS show URL (e.g., https://www.nts.live/shows/covco/episodes/covco-8th-december-2016)

    Returns:
        Tuple of (show_alias, episode_alias)

    Raises:
        ValueError: If URL format is invalid
    """
    pattern = r'(?:https?://)?(?:www\.)?nts\.live/shows/([^/]+)/episodes/([^/?]+)'
    match = re.match(pattern, url)

    if not match:
        raise ValueError(
            f"Invalid NTS URL format. Expected format: "
            f"https://www.nts.live/shows/<show>/episodes/<episode>\n"
            f"Got: {url}"
        )

    show_alias = match.group(1)
    episode_alias = match.group(2)

    return show_alias, episode_alias


class NTSClient:
    """Client for interacting with NTS Radio API."""

    BASE_URL = "https://www.nts.live"
    TIMEOUT = 30  # seconds
    MAX_RETRIES = 3
    RETRY_DELAY = 1  # seconds

    def __init__(self, base_url: str = None, timeout: int = None):
        """
        Initialize NTS client.

        Args:
            base_url: Override default NTS API base URL (for testing)
            timeout: Request timeout in seconds
        """
        self.base_url = base_url or self.BASE_URL
        self.timeout = timeout or self.TIMEOUT

    def _make_request(self, endpoint: str, retry_count: int = 0) -> dict:
        """
        Make HTTP GET request with retry logic.

        Args:
            endpoint: API endpoint path
            retry_count: Current retry attempt number

        Returns:
            Parsed JSON response

        Raises:
            requests.exceptions.HTTPError: If request fails after retries
            requests.exceptions.Timeout: If request times out
            requests.exceptions.RequestException: For other request errors
        """
        url = f"{self.base_url}{endpoint}"

        try:
            response = requests.get(url, timeout=self.timeout)
            response.raise_for_status()
            return response.json()

        except requests.exceptions.Timeout:
            if retry_count < self.MAX_RETRIES:
                delay = self.RETRY_DELAY * (2 ** retry_count)  # Exponential backoff
                time.sleep(delay)
                return self._make_request(endpoint, retry_count + 1)
            raise

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                raise ValueError(
                    f"Episode not found. Please check the URL and try again.\n"
                    f"Endpoint: {endpoint}"
                )
            elif e.response.status_code >= 500:
                # Server error - retry
                if retry_count < self.MAX_RETRIES:
                    delay = self.RETRY_DELAY * (2 ** retry_count)
                    time.sleep(delay)
                    return self._make_request(endpoint, retry_count + 1)
            raise

        except requests.exceptions.RequestException:
            if retry_count < self.MAX_RETRIES:
                delay = self.RETRY_DELAY * (2 ** retry_count)
                time.sleep(delay)
                return self._make_request(endpoint, retry_count + 1)
            raise

    def fetch_episode_metadata(self, show_alias: str, episode_alias: str) -> dict:
        """
        Fetch episode metadata from NTS API.

        Args:
            show_alias: Show identifier (e.g., "covco")
            episode_alias: Episode identifier (e.g., "covco-8th-december-2016")

        Returns:
            Raw episode metadata dictionary

        Raises:
            ValueError: If episode not found
            requests.exceptions.RequestException: For network errors
        """
        endpoint = f"/api/v2/shows/{show_alias}/episodes/{episode_alias}"
        return self._make_request(endpoint)

    def fetch_tracklist(self, show_alias: str, episode_alias: str) -> List[NTSTrack]:
        """
        Fetch tracklist for an episode.

        Args:
            show_alias: Show identifier (e.g., "covco")
            episode_alias: Episode identifier (e.g., "covco-8th-december-2016")

        Returns:
            List of NTSTrack objects (empty list if no tracks)

        Raises:
            ValueError: If episode not found
            requests.exceptions.RequestException: For network errors
        """
        endpoint = f"/api/v2/shows/{show_alias}/episodes/{episode_alias}/tracklist"

        try:
            data = self._make_request(endpoint)
        except ValueError:
            # Episode exists but no tracklist - return empty list
            return []

        tracks = []
        results = data.get('results', [])

        for track_data in results:
            track = NTSTrack(
                artist=track_data.get('artist', 'Unknown Artist'),
                title=track_data.get('title', 'Unknown Title'),
                uid=track_data.get('uid', ''),
                offset=track_data.get('offset'),
                duration=track_data.get('duration')
            )
            tracks.append(track)

        return tracks

    def get_episode_from_url(self, url: str) -> NTSEpisode:
        """
        Fetch complete episode data from an NTS URL.

        Args:
            url: NTS show URL (e.g., https://www.nts.live/shows/covco/episodes/...)

        Returns:
            NTSEpisode object with metadata and tracklist

        Raises:
            ValueError: If URL is invalid or episode not found
            requests.exceptions.RequestException: For network errors
        """
        # Parse URL
        show_alias, episode_alias = parse_nts_url(url)

        # Fetch metadata and tracklist
        metadata = self.fetch_episode_metadata(show_alias, episode_alias)
        tracklist = self.fetch_tracklist(show_alias, episode_alias)

        # Create episode object
        episode = NTSEpisode(
            name=metadata.get('name', 'Unknown Episode'),
            show_alias=show_alias,
            episode_alias=episode_alias,
            broadcast_date=metadata.get('broadcast', ''),
            description=metadata.get('description', ''),
            tracklist=tracklist
        )

        return episode
