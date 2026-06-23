"""Hamilton nodes for bronze-layer of the Energy Price Cap Levels Annex 9 pipeline"""

import logging
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from hamilton.function_modifiers import check_output_custom

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    PRICE_CAP_PERIOD_PUBLICATION_DATES,
    PRICE_CAP_PERIOD_STRING_PATTERN,
)
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.validators import (
    LatestPriceCapFileUrlValidator,
    LatestPriceCapValidator,
)

logger = logging.getLogger(__name__)


def latest_collection_page_html_soup(collection_url: str) -> BeautifulSoup:
    """Fetch and parse the HTML content of Ofgem data collection page."""
    content = utils.fetch_raw_content(collection_url)
    if not content:
        raise ValueError(f"Empty response from collection page: {collection_url}")
    return BeautifulSoup(content, "html.parser")


@check_output_custom(LatestPriceCapFileUrlValidator(PRICE_CAP_PERIOD_PUBLICATION_DATES))
def latest_file_url(
    latest_collection_page_html_soup: BeautifulSoup,
    file_link_text: str,
    collection_url: str,
) -> str:
    """Locate the URL of the latest data file from a parsed collection page.

    Searches for an anchor tag whose visible text contains the specified
    substring 'file_link_text' and returns the URL of the first match.
    """

    for a in latest_collection_page_html_soup.find_all("a", href=True):
        if file_link_text in a.get_text():
            file_url = urljoin(collection_url, a["href"])
            logger.info("Selected Annex 9 source file URL: %s", file_url)
            return file_url

    raise ValueError(f"Could not find dataset '{file_link_text}' at {collection_url}")


@check_output_custom(LatestPriceCapValidator(PRICE_CAP_PERIOD_PUBLICATION_DATES))
def latest_price_cap_period(
    latest_collection_page_html_soup: BeautifulSoup,
) -> str:
    """Extract the latest energy price cap period from given collection page.

    Searches all <h2> and <h3> headings in the given BeautifulSoup object for
    a text pattern matching the price cap period (e.g., "1 January to 31 March 2026")
    and returns the first match.
    """

    # Search for price cap period string header based on expected regex pattern
    for heading in latest_collection_page_html_soup.find_all(["h2", "h3"]):
        match = re.compile(PRICE_CAP_PERIOD_STRING_PATTERN).search(heading.get_text(strip=True))
        if match:
            period = match.group(0)
            logger.info("Detected latest price cap period: %s", period)
            return period

    raise ValueError("Could not find latest price cap period on page.")


def latest_file_content(latest_file_url: str) -> bytes:
    """Fetch the raw content of the latest data file from given URL."""
    content = utils.fetch_raw_content(latest_file_url)
    if not content:
        raise ValueError(f"Empty response fetching file: {latest_file_url}")
    return content


def latest_filename(
    latest_file_url: str,
) -> str:
    """Extract the file name from data file URL."""
    filename = Path(latest_file_url).name
    if not filename:
        raise ValueError(f"Could not extract filename from URL: {latest_file_url}")
    logger.info("Selected Annex 9 workbook: %s", filename)
    return filename


def bronze_metadata(
    publisher: str,
    collection_url: str,
    latest_file_url: str,
    latest_filename: str,
    latest_price_cap_period: str,
    bronze_ingest_timestamp: str,
    pipeline_version: str,
) -> dict[str, str]:
    """Generate dictionary of provenance metadata.

    Captures key information about the source, ingestion,
    and version of the dataset. It is used in the Ofgem energy price cap
    ETL pipeline at the bronze stage for auditing and reproducibility.
    """

    return {
        "publisher": publisher,
        "collection_url": collection_url,
        "file_url": latest_file_url,
        "file_name": latest_filename,
        "price_cap_period": latest_price_cap_period,
        "bronze_ingest_timestamp": bronze_ingest_timestamp,
        "pipeline_version": pipeline_version,
        "citation": f"Source: {publisher}, {latest_filename}, {latest_price_cap_period}. {collection_url}.",
    }


def bronze_energy_price_cap_annex_9_file(
    dataset_prefix: str,
    latest_file_content: bytes,
    latest_filename: str,
    latest_price_cap_period: str,
    bronze_metadata: dict,
) -> None:
    """Ingest downloaded data file and accompanying metadata to bronze-layer storage."""

    date_stamp = f"period={utils.normalise_energy_price_cap_period_string(latest_price_cap_period)}"

    logger.info(
        "Writing Annex 9 bronze dataset: filename=%s, period=%s",
        latest_filename,
        date_stamp,
    )
    storage.ingest_to_bronze(
        layer_prefix="bronze",
        dataset_prefix=dataset_prefix,
        file=latest_file_content,
        filename=latest_filename,
        date_stamp=date_stamp,
        metadata=bronze_metadata,
    )
