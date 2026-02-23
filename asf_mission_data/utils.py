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


def is_s3_uri(target_location: str) -> bool:
    """Check if target location is an S3 URI.

    Args:
        path (str): Path string to check.

    Returns:
        bool: True if path starts with "s3://", indicating it refers to an S3 location.
    """
    return target_location.startswith("s3://")


def parse_s3_uri(s3_uri: str) -> tuple[str, str]:
    """Parse an S3 URI into bucket name and key prefix.

    Args:
        s3_uri (str): Full S3 URI (e.g. "s3://bucket/key").

    Raises:
        ValueError: If the input is not a valid S3 URI.

    Returns:
        tuple[str, str]: A tuple containing S3 bucket name, and object key prefix.
    """

    if not s3_uri.startswith("s3://"):
        raise ValueError(f"Invalid S3 URI: {s3_uri}")

    _, path = s3_uri.split("s3://", 1)
    parts = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix
