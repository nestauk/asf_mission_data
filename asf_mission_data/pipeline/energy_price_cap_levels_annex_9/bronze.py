import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Type
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from hamilton.data_quality.base import DataValidator, ValidationResult
from hamilton.function_modifiers import check_output_custom

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    PRICE_CAP_PERIOD_PUBLICATION_DATES,
    PRICE_CAP_PERIOD_STRING_PATTERN,
)

logger = logging.getLogger(__name__)


def latest_collection_page_html_soup(collection_url: str) -> BeautifulSoup:
    """Fetch and parse the HTML content of a data publisher's collection page.

    Args:
        collection_url (str): URL of page containing links to downloadable data files.

    Returns:
        BeautifulSoup: Parsed HTML content of the page.
    """
    return BeautifulSoup(utils.fetch_raw_content(collection_url), "html.parser")


# TODO move to a more appropriate module later
class LatestPriceCapFileUrlValidator(DataValidator):
    """Checks that the price cap file url retrieved is the expected one.

    This is based on the ofgem url structure including the publication month and year.
    """

    def __init__(
        self,
        price_cap_period_publication_dates: dict[str, str],
        importance: str = "fail",
    ):
        super(LatestPriceCapFileUrlValidator, self).__init__(importance=importance)
        self.price_cap_period_publication_dates = price_cap_period_publication_dates

    def applies_to(self, datatype: Type) -> bool:
        """Whether or not this data validator can apply to
        the specified dataset

         :param datatype:
         :return: True if it can be run on the specified type.
        """
        return datatype is str

    def description(self) -> str:
        """Gives a description of this validator.
        :return: The description of the validator as a string
        """
        return "Checks that the price cap file url retrieved is the expected one given the execution date."

    @classmethod
    def name(cls) -> str:
        """Returns the name for this validator."""
        return "LatestPriceCapFileUrlValidator"

    def validate(self, data: str) -> ValidationResult:
        """Actually performs the validation.

        :param data: data to validate
        :return: The result of validation
        """
        # Anticipated date pattern is YYYY-MM
        match = re.search(r"(\d{4}-\d{2})", data)

        if match:
            extracted_date = match.group(1)
        else:
            return ValidationResult(
                passes=False,
                message=f"Unexpected price cap file url, no date component in: {data}",
            )

        # Get expected publication dates is same format as file url date
        PUBLICATION_DATES = (
            datetime.fromisoformat(v)
            for v in self.price_cap_period_publication_dates.values()
        )

        # Get expected price cap period
        now = datetime.now()
        latest_publication_date = max((v for v in PUBLICATION_DATES if v <= now))

        # Match anticipated date format
        latest_publication_date_str = latest_publication_date.strftime(format="%Y-%m")

        valid = extracted_date == latest_publication_date_str

        return ValidationResult(
            passes=valid,
            message=f"Expected file url date: {latest_publication_date_str}, saw date {extracted_date}",
        )


@check_output_custom(LatestPriceCapFileUrlValidator(PRICE_CAP_PERIOD_PUBLICATION_DATES))
def latest_file_url(
    latest_collection_page_html_soup: BeautifulSoup,
    file_link_text: str,
    collection_url: str,
) -> str:
    """Locate the URL of the latest data file from a parsed collection page.

    Searches for an anchor tag whose visible text contains the specified
    substring 'file_link_text' and returns the URL of the first match.

    Args:
        latest_collection_page_html_soup (BeautifulSoup): Parsed HTML of the collection page.
        file_link_text (str): Substring expected to appear in the link text of target data file.
        collection_url (str): URL of page containing links to downloadable data files.

    Raises:
        ValueError: If no matching link is found on the page.

    Returns:
        str: URL of the first matching data file link.
    """

    for a in latest_collection_page_html_soup.find_all("a", href=True):
        if file_link_text in a.get_text():
            return urljoin(collection_url, a["href"])

    raise ValueError(f"Could not find dataset '{file_link_text}' at {collection_url}")


# TODO move to a more appropriate module later
class LatestPriceCapValidator(DataValidator):
    """Checks that the price cap period retrieved is the expected one."""

    def __init__(
        self,
        price_cap_period_publication_dates: dict[str, str],
        importance: str = "fail",
    ):
        super(LatestPriceCapValidator, self).__init__(importance=importance)
        self.price_cap_period_publication_dates = price_cap_period_publication_dates

    def applies_to(self, datatype: Type) -> bool:
        """Whether or not this data validator can apply to
        the specified dataset

         :param datatype:
         :return: True if it can be run on the specified type.
        """
        return datatype is str

    def description(self) -> str:
        """Gives a description of this validator.
        :return: The description of the validator as a string
        """
        return "Checks that the price cap period retrieved is the expected one given the execution date."

    @classmethod
    def name(cls) -> str:
        """Returns the name for this validator."""
        return "LatestPriceCapValidator"

    def validate(self, data: str) -> ValidationResult:
        """Actually performs the validation.

        :param data: data to validate
        :return: The result of validation
        """
        extracted_period_interval = (
            utils.convert_energy_price_cap_period_string_to_interval(data)
        )
        INTERVAL_PUBLICATION_DATES = {
            utils.convert_energy_price_cap_period_string_to_interval(
                k
            ): datetime.fromisoformat(v)
            for k, v in self.price_cap_period_publication_dates.items()
        }

        if extracted_period_interval not in INTERVAL_PUBLICATION_DATES:
            return ValidationResult(
                passes=False,
                message=f"Unrecognised price cap period: {extracted_period_interval}",
            )

        # Look up publication date of extracted price cap period
        publication_date = INTERVAL_PUBLICATION_DATES.get(extracted_period_interval)

        # Get expected price cap period
        now = datetime.now()
        latest_interval = max(
            (k for k, v in INTERVAL_PUBLICATION_DATES.items() if v <= now),
            key=INTERVAL_PUBLICATION_DATES.get,
        )
        latest_publication_date = INTERVAL_PUBLICATION_DATES[latest_interval]

        valid = publication_date == latest_publication_date

        return ValidationResult(
            passes=valid,
            message=f"Expected publication date: {latest_publication_date.strftime(format='%d-%m-%Y')}, "
            "saw publication date {publication_date.strftime(format='%d-%m-%Y')}",
        )


@check_output_custom(LatestPriceCapValidator(PRICE_CAP_PERIOD_PUBLICATION_DATES))
def latest_price_cap_period(latest_collection_page_html_soup: BeautifulSoup) -> str:
    """Extract the latest energy price cap period from given collection page.

    Searches all <h2> and <h3> headings in the given BeautifulSoup object for
    a text pattern matching the price cap period (e.g., "1 January to 31 March 2026")
    and returns the first match.

    Args:
        latest_collect_page_html_soup (BeautifulSoup): Parsed HTML of the collection page.

    Raises:
        ValueError: If no matching period is found on the page.

    Returns:
        str: Latest price cap period (e.g., "1 January to 31 March 2026").
    """

    # Search for price cap period string header based on expected regex pattern
    for heading in latest_collection_page_html_soup.find_all(["h2", "h3"]):
        match = re.compile(PRICE_CAP_PERIOD_STRING_PATTERN).search(
            heading.get_text(strip=True)
        )
        if match:
            return match.group(0)

    raise ValueError("Could not find latest price cap period on page.")


def latest_file_content(latest_file_url: str) -> bytes:
    """Fetch the raw content of the latest data file from given URL.

    Used in the extract stage of the ETL pipeline.

    Args:
        latest_file_url (str): URL of latest data file.

    Returns:
        bytes: Raw content of file.
    """
    return utils.fetch_raw_content(latest_file_url)


def latest_file_name(
    latest_file_url: str,
) -> str:
    """Extract the file name from data file URL.

    This function takes the URL of the latest data file and returns just the file name portion.

    Args:
        latest_file_url (str): URL pointing to data file.

    Returns:
        str: File name (e.g., "Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.8.xlsx")
    """

    return Path(latest_file_url).name


# TODO refactor to general metadata module
def bronze_metadata(
    publisher: str,
    collection_url: str,
    latest_file_url: str,
    latest_file_name: str,
    latest_price_cap_period: str,
    bronze_ingest_timestamp: str,
    pipeline_version: str,
) -> dict[str, str]:
    """Generate provenance metadata for a dataset file.

    This metadata captures key information about the source, ingestion,
    and version of the dataset. It is used in the Ofgem energy price cap
    ETL pipeline at the bronze stage for auditing and reproducibility.

    Args:
        publisher (str): Name of the data publisher (e.g., "Ofgem").
        collection_url (str): URL of the collection page containing links to download data files.
        latest_file_url (str): URL of the latest data file.
        latest_file_name (str): Name of the data file.
        latest_price_cap_period (str): The latest price cap period covered by the data file.
        bronze_ingest_timestamp (str): Timestamp when the dataset was ingested.
        pipeline_version (str): Version of the ETL pipeline that ingested the dataset.

    Returns:
        dict[str, str]: Provenance metadata containing the above fields, plus a human-readable citation.
    """

    return {
        "publisher": publisher,
        "collection_url": collection_url,
        "file_url": latest_file_url,
        "file_name": latest_file_name,
        "price_cap_period": latest_price_cap_period,
        "bronze_ingest_timestamp": bronze_ingest_timestamp,
        "pipeline_version": pipeline_version,
        "citation": f"Source: {publisher}, {latest_file_name}, {latest_price_cap_period}. {collection_url}.",
    }


def bronze_energy_price_cap_annex_9_file(
    pipeline_name: str,
    latest_file_content: bytes,
    latest_file_name: str,
    latest_price_cap_period: str,
    bronze_metadata: dict,
) -> None:
    """Ingest the latest energy price cap Annex 9 dataset into the bronze layer.

    This node persists the extracted raw dataset and its associated provenance
    metadata into the bronze storage layer.

    Performs the following actions:
        1. Persists bronze file and metadata to 'historical' price cap period partition.
        2. Deletes any existing 'latest' bronze files and metadata.
        3. Stores bronze file and metadata under:
            - historical/<price_cap_period>/
            - latest

    Storage structure:

        <data_root>/<pipeline_name>/bronze/
                ├── historical/<price_cap_period>/file/
                ├── historical/<price_cap_period>/metadata/
                └── latest/
                    ├── file/
                    └── metadata/

    Args:
        pipeline_name (str): Name of pipeline used to namespace bronze storage.
        latest_file_content (bytes): Latest dataset file to persist.
        latest_file_name (str): Latest file name to persist.
        latest_price_cap_period (str): The latest price cap period covered by
            the latest data file.
        bronze_metadata (dict): Associated provenance metadata.
    """

    price_cap_period_prefix = latest_price_cap_period.replace(" ", "_")

    storage.ingest_to_bronze(
        pipeline_name=pipeline_name,
        file=latest_file_content,
        file_name=latest_file_name,
        date_stamp=price_cap_period_prefix,
        metadata=bronze_metadata,
    )
