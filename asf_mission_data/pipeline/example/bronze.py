# Bronze functions
"""
Bronze stage of the pipeline: Ingest raw data into the bronze layer.

Example downloads the UK government bank holidays JSON as a smoke test
for internet access and S3 writes.
"""

import logging
from datetime import datetime

from bs4 import BeautifulSoup

from asf_mission_data import storage, utils

logger = logging.getLogger(__name__)

SOURCE_URL = "https://www.gov.uk/bank-holidays.json"


def latest_file_content(source_url: str) -> bytes:
    """Download bank holidays JSON from gov.uk."""
    return utils.fetch_raw_content(source_url)


def latest_filename(source_url: str) -> str:
    """Extract the filename from the source URL."""
    return source_url.split("/")[-1]


def latest_publication_date(page_url: str) -> str:
    """Extract the publication date from the GOV.UK bank holidays page.
    Scrapes the 'Last updated' date from the page.
    """
    content = utils.fetch_raw_content(page_url)
    soup = BeautifulSoup(content, "html.parser")

    last_updated_tag = soup.find(string="Last updated")
    if not last_updated_tag:
        raise ValueError(f"Could not find 'Last updated' on page: {page_url}")

    date_string = last_updated_tag.find_next().get_text(strip=True)
    logger.info("Detected bank holidays publication date: %s", date_string)

    return datetime.strptime(date_string, "%d %B %Y").strftime("%d %B %Y")


def bronze_metadata(
    publisher: str,
    page_url: str,
    source_url: str,
    latest_publication_date: str,
    bronze_ingest_timestamp: str,
    pipeline_version: str,
) -> dict[str, str]:
    """Return dictionary of metadata items."""
    return {
        "publisher": publisher,  # config
        "page_url": page_url,  # config
        "source_url": source_url,  # config
        "publication_date": latest_publication_date,  # node
        "bronze_ingest_timestamp": bronze_ingest_timestamp,  # datetime.now in driver config
        "pipeline_version": pipeline_version,  # version in driver config
        "citation": f"Source: {publisher}, UK Bank Holidays. Published {latest_publication_date}, {source_url}.",
    }


def bronze_bank_holidays_file(
    dataset_prefix: str,
    latest_file_content: bytes,
    latest_filename: str,
    latest_publication_date: str,
    bronze_metadata: dict,
) -> None:
    """Ingest downloaded data file and accompanying metadata to bronze-layer storage."""
    logger.info(
        "Writing UK bank holidays dataset: filename=%s publication_date=%s",
        latest_filename,
        latest_publication_date,
    )
    storage.ingest_to_bronze(
        layer_prefix="bronze",
        dataset_prefix=dataset_prefix,
        file=latest_file_content,
        filename=latest_filename,
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
        metadata=bronze_metadata,
    )
