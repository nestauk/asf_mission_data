import logging
import requests

logger = logging.getLogger(__name__)


class SourceFetchError(Exception):
    """Raised when fetching data from a source URL fails."""

    pass


def fetch_raw_content(url: str, timeout: int = 30) -> bytes:
    """Fetch raw binary content from a given URL.

    Makes an HTTP GET request to the given URL and returns the response as raw bytes.
    Raises `SourceFetchError` if the request fails or returns a non-success status code..

    Args:
        url (str): URL to fetch content from.
        timeout (int): Request timeout in seconds (default is 30).

    Raises:
        SourceFetchError: If the request fails or returns an unsuccessful HTTP status code.

    Returns:
        bytes: Raw response content.
    """

    logger.info("Fetching content from %s", url)

    try:
        response = requests.get(url, timeout=timeout)
        response.raise_for_status()
        logger.info("Fetched %d bytes from %s", len(response.content), url)
        return response.content
    except requests.exceptions.RequestException as e:
        logger.error("Failed to fetch %s: %s", url, e)
        raise SourceFetchError(f"Failed to fetch {url}") from e
