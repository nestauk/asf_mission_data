import requests


def fetch_raw_content(url: str) -> bytes:
    """Fetch raw binary content from a given URL.

    Makes an HTTP GET request to the given URL and returns the response as raw bytes.
    Raises an exception if the request fails or returns a non-success status code.

    Args:
        url (str): URL to fetch content from.

    Raises:
        requests.exceptions.RequestException: If the request fails or returns
            an unsuccessful HTTP status code.

    Returns:
        bytes: Raw response content.
    """
    response = requests.get(url)
    response.raise_for_status()
    return response.content
