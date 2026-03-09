import logging
import re

import pandas as pd
import requests
from pandas.tseries.offsets import MonthEnd

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


def convert_energy_price_cap_charge_restriction_period_string_to_interval(
    period_str: str,
) -> pd.Interval:
    """Convert a charge restriction period string into a pandas Interval.

    Parses strings describing energy price cap charge restriction periods, e.g.:
        "April 2026 - June 2026" or "April 2026 to June 2026"

    The resulting interval is inclusive of the full months, with:
        - start date: first day of the start month
        - end date: last second of the last day of the end month

    Args:
        period_str (str): Charge restriction period string to convert.

    Returns:
        pd.Interval: Interval covering the full charge restriction period, closed on both ends.
    """

    charge_restriction_period_interval_pattern = (
        r"(?P<start_month>[A-Za-z]+)\s+(?P<start_year>\d{4})\s*"
        r"(?:-|to)\s*"
        r"(?P<end_month>[A-Za-z]+)\s+(?P<end_year>\d{4})"
    )

    match = re.search(charge_restriction_period_interval_pattern, period_str.strip(), re.IGNORECASE)

    if match:
        parts = match.groupdict()
        start_dt = pd.to_datetime(f"{parts['start_month']} {parts['start_year']}")
        end_base_dt = pd.to_datetime(f"{parts['end_month']} {parts['end_year']}")
        end_final_dt = end_base_dt + MonthEnd(0) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1)

        return pd.Interval(left=start_dt, right=end_final_dt, closed="both")

    else:
        logger.error(
            "Charge restriction period string '%s' does not match expected regex pattern.",
            period_str,
        )
        raise ValueError("Charge restriction period string '%s' does not match expected regex pattern.")
