import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from hamilton.function_modifiers import check_output_custom

from asf_mission_data import storage, utils
from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.heat_pump_deployment_statistics.validators import ExcelFileExtensionValidator, WithinThreeCalendarMonthsValidator

logger = setup_logging(__name__)


def latest_collection_page_html_soup(collection_url: str) -> BeautifulSoup:
    """Fetch and parse the HTML content of collection page."""
    return BeautifulSoup(utils.fetch_raw_content(collection_url), "html.parser")


def latest_release_page_url(collection_url: str, latest_collection_page_html_soup: BeautifulSoup, page_link_text: str) -> str:
    """Find link to latest release page on the collection page."""
    for a in latest_collection_page_html_soup.find_all("a", href=True):
        if page_link_text in a.get_text():
            return urljoin(collection_url, a["href"])

    raise ValueError(f"Could not find statistical release page '{page_link_text}' at {collection_url}")


def latest_release_page_html_soup(latest_release_page_url: str) -> BeautifulSoup:
    """Fetch and parse the HTML content of latest release page."""
    return BeautifulSoup(utils.fetch_raw_content(latest_release_page_url), "html.parser")


def latest_file_url(latest_release_page_url: str, latest_release_page_html_soup: BeautifulSoup, file_link_text: str) -> str:
    """Find link to download latest released data file."""
    for a in latest_release_page_html_soup.find_all("a", href=True):
        if file_link_text in a.get_text():
            return urljoin(latest_release_page_url, a["href"])

    raise ValueError(f"Could not find dataset '{file_link_text}' at {latest_release_page_url}")


def latest_file_content(latest_file_url: str) -> bytes:
    """Fetch the raw content of the latest data file from given URL."""
    return utils.fetch_raw_content(latest_file_url)


@check_output_custom(ExcelFileExtensionValidator())
def latest_filename(latest_file_url: str) -> str:
    """Extract file name of downloaded data file."""
    return Path(latest_file_url).name


@check_output_custom(WithinThreeCalendarMonthsValidator())
def latest_publication_date(latest_release_page_html_soup: BeautifulSoup) -> str:
    """Extract publication date of downloaded data file."""
    match = re.search(r"Published\s+(\d{1,2}\s+\w+\s+\d{4})", latest_release_page_html_soup.get_text())
    if match:
        return match.group(1)


def bronze_metadata(
    publisher: str,
    collection_url: str,
    latest_release_page_url: str,
    latest_file_url: str,
    latest_filename: str,
    latest_publication_date: str,
    bronze_ingest_timestamp: str,
    pipeline_version: str,
) -> dict[str, str]:
    """Return dictionary of metadata items."""
    return {
        "publisher": publisher,  # config
        "collection_url": collection_url,  # config
        "page_url": latest_release_page_url,  # node
        "file_url": latest_file_url,  # node
        "filename": latest_filename,  # node
        "publication_date": latest_publication_date,  # node
        "bronze_ingest_timestamp": bronze_ingest_timestamp,  # datetime.now in driver config
        "pipeline_version": pipeline_version,  # version in driver config
        "citation": f"Source: {publisher}, {latest_filename}. Published {latest_publication_date}, {latest_release_page_url}.",
    }


def bronze_heat_pump_deployment_statistics_file(
    dataset_prefix: str,
    latest_file_content: bytes,
    latest_filename: str,
    latest_publication_date: str,
    bronze_metadata: dict,
) -> None:
    """Ingest downloaded data file and accompanying metadata to bronze-layer storage."""
    storage.ingest_to_bronze(
        layer_prefix="bronze",
        dataset_prefix=dataset_prefix,
        file=latest_file_content,
        filename=latest_filename,
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
        metadata=bronze_metadata,
    )
