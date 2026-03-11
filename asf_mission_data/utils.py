import logging
import re
from datetime import datetime

import pandas as pd
import requests

from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    PRICE_CAP_PERIOD_INTERVAL_PATTERN,
)

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


def convert_energy_price_cap_period_string_to_interval(period_str: str) -> pd.Interval:
    """Convert a price cap period string into a pandas Interval.

    The function parses strings of the form:
        "1 April to 30 June 2026"
    using a configured regex pattern with named capture groups and
    converts the extracted start/end dates into a pandas.Interval.

    The interval is constructed as:
        [start_date, end_date_end_of_day]
    where:
        - start_date is parsed from the extracted start components
        - end_date is shifted to the end of its day (23:59:59.999999)
          to make the interval inclusive of the full period

    Args:
        period_str (str): Price cap period string to convert.

    Raises:
        ValueError: If the input string does not match the regex pattern.

    Returns:
        pd.Interval: Interval representing the full price cap period.
    """

    match = re.match(PRICE_CAP_PERIOD_INTERVAL_PATTERN, period_str)
    if match:
        parts = match.groupdict()
        start_dt = pd.to_datetime(f"{parts['start_day']} {parts['start_month']} {parts['year']}")
        end_dt = pd.to_datetime(f"{parts['end_day']} {parts['end_month']} {parts['year']}") + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        return pd.Interval(start_dt, end_dt, closed="both")
    else:
        logger.error(
            "Price cap period string '%s' does not match expected regex pattern",
            period_str,
        )
        raise ValueError("Price cap period string format does not match expected regex pattern.")


def normalise_energy_price_cap_period_string(period_str: str) -> str:
    """Normalise an energy price cap period string into a canonical storage-safe format.

    The input string is expected to represent a date range such as:
        "1 April to 30 June 2026"
        "1 January 2026 to 31 March 2026"

    The function converts the range into an ISO-style date format
    suitable for partitions or dataset version identifiers.

    Example:
        "1 April to 30 June 2026" -> "2026-04-01_to_2026-06-30"

    Args:
        period_str (str): Human-readable energy price cap period string.

    Returns:
        str: A normalised date range string formatted as:
        "YYYY-MM-DD_to_YYYY-MM-DD".
    """
    start_str, end_str = period_str.split(" to ")
    end = datetime.strptime(end_str, "%d %B %Y")

    if start_str.count(" ") == 1:
        start_str = f"{start_str} {end.year}"

    start = datetime.strptime(start_str, "%d %B %Y")

    return f"{start:%Y-%m-%d}_to_{end:%Y-%m-%d}"
