import json
from pathlib import Path

import re
from bs4 import BeautifulSoup
from urllib.parse import urljoin

from asf_mission_data import storage, utils

# Regex pattern for expected price cap period dates format
PRICE_CAP_PERIOD_PATTERN = re.compile(
    r"\d{1,2}\s+[A-Za-z]+\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}"
)


def latest_file_url(collection_url: str, file_link_text: str) -> str:
    """Locate the latest dataset file URL from a publisher collection page.

    Fetches and parses the HTML content at the given collection URL and searches
    for an anchor tag where visible text contains the specified 'file_link_text'.
    Returns the URL of the first match.

    Args:
        collection_url (str): URL of page containing links to downloadable data files.
        file_link_text (str): Substring expected to appear in the link text of target data file.

    Raises:
        ValueError: If no matching link is found on the page.

    Returns:
        str: URL of the first matching data file link.
    """

    soup = BeautifulSoup(utils.fetch_raw_content(collection_url), "html.parser")

    for a in soup.find_all("a", href=True):
        if file_link_text in a.get_text():
            return urljoin(collection_url, a["href"])

    raise ValueError(f"Could not find dataset '{file_link_text}' at {collection_url}")


def latest_price_cap_period(collection_url: str) -> str:
    """Extract the latest energy price cap period from given collection page.

    Fetches the HTML content at given collection URL, searches all h2 and h3 headings for
    a text pattern matching "D Month to D Month YYYy" and returns the first match.

    Args:
        collection_url (str): URL of page containing links to downloadable data files.

    Raises:
        ValueError: If no matching period is found on the page.

    Returns:
        str: Latest price cap period (e.g., "1 January to 31 March 2026").
    """

    soup = BeautifulSoup(utils.fetch_raw_content(collection_url), "html.parser")

    for heading in soup.find_all(["h2", "h3"]):
        match = PRICE_CAP_PERIOD_PATTERN.search(heading.get_text(strip=True))
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


def provenance_metadata(
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
        "citation": f"Source: {publisher}, {latest_file_name}, "
        f"{latest_price_cap_period}. {collection_url}.",
    }


def saved_file_path(
    latest_file_content: bytes,
    latest_file_name: str,
    latest_price_cap_period: str,
) -> dict[str, Path]:
    """Save the latest raw data file to both the LATEST and historical directories.

    This function ensures that:
    - The file is saved in the "LATEST" subdirectory, replacing any raw .xlsx files.
    - The file is also saved in a "historical/{latest_price_cap_period}" subdirectory to
        preserve past versions.
    - Only files ending with ".xlsx" in LATEST are deleted before saving the new file.
        This is to prevent deleting metadata files, which are treated separately.

    Args:
        latest_file_content (bytes): Raw content of latest data file.
        latest_file_name (str): Name of latest data file (e.g., "Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.8.xlsx").
        latest_price_cap_period (str): Price cap period string (e.g., "1 January to 31 March 2026") used to create this historical subdirectory.

    Returns:
        dict[str, Path]: Paths to the saved files, keyed by:
            - "latest": Path to file in the LATEST directory.
            - "historical": Path to the file in the historical directory.
    """

    base_path = storage.get_data_path("energy_price_cap_levels_annex_9/bronze")

    saved_paths = storage.save_file_with_cleanup(
        content=latest_file_content,
        base_path=base_path,
        subdirs=["LATEST", f"historical/{latest_price_cap_period}"],
        file_name=latest_file_name,
        delete_extension=".xlsx",
        cleanup_subdir="LATEST",
        mode="wb",
    )
    return {
        "latest": saved_paths["LATEST"],
        "historical": saved_paths[f"historical/{latest_price_cap_period}"],
    }


def saved_provenance_metadata_file_path(
    latest_file_name: str,
    provenance_metadata: dict[str, str],
    latest_price_cap_period: str,
) -> dict[str, str]:
    """Save the latest metadata file accompanying the latest raw data file to both the LATEST and historical directories.

    This function ensures that:
    - The file is saved in the "LATEST" subdirectory, replacing any metadata files.
    - The file is also saved in a "historical/{latest_price_cap_period}" subdirectory to
        preserve past versions.
    - Only files ending with ".metadata.json" in LATEST are deleted before saving the new file.
        This is to prevent deleting raw data files, which are treated separately.

    Args:
        latest_file_name (str): Name of latest data file (e.g., "Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.8.xlsx").
        provenance_metadata (dict[str, str]): Dictionary of metadata about the data file.
        latest_price_cap_period (str): Price cap period string (e.g., "1 January to 31 March 2026") used to create this historical subdirectory.

    Returns:
        dict[str, Path]: Paths to the saved metadata files, keyed by:
            - "latest": Path to file in the LATEST directory.
            - "historical": Path to the file in the historical directory.
    """

    base_path = storage.get_data_path("energy_price_cap_levels_annex_9/bronze")
    metadata_file_name = f"{latest_file_name}.metadata.json"

    saved_paths = storage.save_file_with_cleanup(
        content=json.dumps(provenance_metadata, indent=4),
        base_path=base_path,
        subdirs=["LATEST", f"historical/{latest_price_cap_period}"],
        file_name=metadata_file_name,
        delete_extension=".metadata.json",
        cleanup_subdir="LATEST",
        mode="w",
    )

    return {
        "latest": saved_paths["LATEST"],
        "historical": saved_paths[f"historical/{latest_price_cap_period}"],
    }
