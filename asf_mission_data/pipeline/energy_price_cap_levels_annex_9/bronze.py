import json
import re
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from asf_mission_data import storage, utils

# Path parameters
BASE_PATH = storage.get_data_path("energy_price_cap_levels_annex_9/bronze")
is_s3 = utils.is_s3_uri(BASE_PATH)
if is_s3:
    BUCKET, BASE_PREFIX = utils.parse_s3_uri(BASE_PATH)
    S3_PREFIX_LATEST = f"{BASE_PREFIX}/latest"
    S3_PREFIX_HISTORICAL = f"{BASE_PREFIX}/historical"
else:
    LOCAL_DIR_LATEST = f"{BASE_PATH}/latest"
    LOCAL_DIR_HISTORICAL = f"{BASE_PATH}/historical"


# Regex pattern for expected price cap period dates format
PRICE_CAP_PERIOD_PATTERN = re.compile(
    r"\d{1,2}\s+[A-Za-z]+\s+to\s+\d{1,2}\s+[A-Za-z]+\s+\d{4}"
)


def latest_collection_page_html_soup(collection_url: str) -> BeautifulSoup:
    """Fetch and parse the HTML content of a data publisher's collection page.

    Args:
        collection_url (str): URL of page containing links to downloadable data files.

    Returns:
        BeautifulSoup: Parsed HTML content of the page.
    """
    return BeautifulSoup(utils.fetch_raw_content(collection_url), "html.parser")


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

    for heading in latest_collection_page_html_soup.find_all(["h2", "h3"]):
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


def saved_bronze_excel_file(
    latest_file_content: bytes,
    latest_file_name: str,
    latest_price_cap_period: str,
) -> tuple[str, str]:
    """Save the latest Excel file to both "latest" and "historical" storage locations.

    Depending on storage configuration (`is_s3`), the function either:
    - S3 storage: Uploads file to S3 bucket under a "latest" key (replacing any existing objects)
        and a "historical" key organised by price cap period.
    - Local storage: writes file to local directories under a "latest" subdirectory (replacing any existing files)
        and a "historical" subdirectory organised by price cap period.

    Args:
        latest_file_content (bytes): Content of Excel file in bytes.
        latest_file_name (str): Name of file, including extension.
        latest_price_cap_period (str): Price cap period string, extracted directly from Ofgem collection page.

    Returns:
        tuple[str, str]: Tuple containing the paths or S3 URIs of the saved files to "latest" and to "historical".
    """
    price_cap_period_prefix = latest_price_cap_period.replace(" ", "_")
    if is_s3:
        latest_key = f"{S3_PREFIX_LATEST}/raw/{latest_file_name}"
        historical_key = (
            f"{S3_PREFIX_HISTORICAL}/{price_cap_period_prefix}/raw/{latest_file_name}"
        )

        storage.delete_s3_objects_with_prefix(
            bucket=BUCKET, prefix=f"{S3_PREFIX_LATEST}/raw"
        )
        storage.save_s3_object(
            bucket=BUCKET,
            key=latest_key,
            content=latest_file_content,
        )
        storage.save_s3_object(
            bucket=BUCKET,
            key=historical_key,
            content=latest_file_content,
        )
        return f"s3://{BUCKET}/{latest_key}", f"s3://{BUCKET}/{historical_key}"
    else:
        latest_path = f"{LOCAL_DIR_LATEST}/raw/{latest_file_name}"
        historical_path = (
            f"{LOCAL_DIR_HISTORICAL}/{price_cap_period_prefix}/raw/{latest_file_name}"
        )

        storage.delete_files_in_directory(f"{LOCAL_DIR_LATEST}/raw")
        storage.save_local_file(
            file_path=latest_path,
            content=latest_file_content,
        )
        storage.save_local_file(
            file_path=historical_path,
            content=latest_file_content,
        )
        return latest_path, historical_path


def saved_bronze_metadata(
    latest_file_name: str,
    bronze_metadata: dict[str, str],
    latest_price_cap_period: str,
) -> tuple[str, str]:
    """Save the provenance metadata for the latest Excel file to both "latest" and "historical" storage locations.

    Depending on storage configuration (`is_s3`), the function either:
    - S3 storage: Uploads file to S3 bucket under a "latest" key (replacing any existing objects)
        and a "historical" key organised by price cap period.
    - Local storage: writes file to local directories under a "latest" subdirectory (replacing any existing files)
        and a "historical" subdirectory organised by price cap period.

    Args:
        latest_file_name (str): Name of latest Excel file, including extension.
        bronze_metadata (dict[str, str]): Dictionary of metadata about latest Excel file.
        latest_price_cap_period (str): Price cap period string, extracted directly from Ofgem collection page.

    Returns:
        tuple[str, str]: Tuple containing the paths or S3 URIs of the saved metadata files to "latest" and to "historical".
    """

    metadata_file_name = f"{latest_file_name}.metadata.json"
    metadata_json = json.dumps(bronze_metadata, indent=4)

    price_cap_period_prefix = latest_price_cap_period.replace(" ", "_")

    if is_s3:
        latest_key = f"{S3_PREFIX_LATEST}/metadata/{metadata_file_name}"
        historical_key = f"{S3_PREFIX_HISTORICAL}/{price_cap_period_prefix}/metadata/{metadata_file_name}"

        storage.delete_s3_objects_with_prefix(
            bucket=BUCKET, prefix=f"{S3_PREFIX_LATEST}/metadata"
        )
        storage.save_s3_object(
            bucket=BUCKET,
            key=latest_key,
            content=metadata_json,
        )
        storage.save_s3_object(
            bucket=BUCKET,
            key=historical_key,
            content=metadata_json,
        )

        return f"s3://{BUCKET}/{latest_key}", f"s3://{BUCKET}/{historical_key}"

    else:
        latest_path = f"{LOCAL_DIR_LATEST}/metadata/{metadata_file_name}"
        historical_path = f"{LOCAL_DIR_HISTORICAL}/{price_cap_period_prefix}/metadata/{metadata_file_name}"

        storage.delete_files_in_directory(f"{LOCAL_DIR_LATEST}/metadata")

        storage.save_local_file(
            file_path=latest_path,
            content=metadata_json,
        )
        storage.save_local_file(
            file_path=historical_path,
            content=metadata_json,
        )
        return latest_path, historical_path


def saved_dag_visualisation(
    accompanying_file_name: str,
    subdir_or_prefix: str,
    dag_image: bytes,
    latest_price_cap_period: str,
) -> tuple[str, str]:
    """Save DAG visualisation image representing the workflow that produces a specific file.

    The `accompanying_file_name` identifies the file that the DAG describes.

    Depending on storage configuration (`is_s3`), the function either:
    - S3 storage: Uploads image to S3 bucket under a "latest" key (replacing any existing objects)
        and a "historical" key organised by price cap period.
    - Local storage: writes image to local directories under a "latest" subdirectory (replacing any existing files)
        and a "historical" subdirectory organised by price cap period.

    Args:
        accompanying_file_name (str): Name of the file that the DAG visualises.
        subdir_or_prefix (str): Subdirectory (local)o key prefix (S3) under which the DAG
            image should be saved. Typically the subdirectory/prefix where the accompanying file is located.
        dag_image (bytes): DAG visualisation image.
        latest_price_cap_period (str): Price cap period string, extracted directly from Ofgem collection page.

    Returns:
        tuple[str, str]: Tuple containing the paths or S3 URIs of the saved DAG images to "latest" and to "historical".
    """
    dag_file_name = f"{accompanying_file_name}.dag.png"
    price_cap_period_prefix = latest_price_cap_period.replace(" ", "_")

    if is_s3:
        latest_key = f"{S3_PREFIX_LATEST}/{subdir_or_prefix}/dag_image/{dag_file_name}"
        historical_key = f"{S3_PREFIX_HISTORICAL}/{price_cap_period_prefix}/{subdir_or_prefix}/dag_image/{dag_file_name}"

        storage.delete_s3_objects_with_prefix(
            bucket=BUCKET, prefix=f"{S3_PREFIX_LATEST}/{subdir_or_prefix}/dag_image"
        )

        storage.save_s3_object(
            bucket=BUCKET,
            key=latest_key,
            content=dag_image,
        )
        storage.save_s3_object(
            bucket=BUCKET,
            key=historical_key,
            content=dag_image,
        )

        return f"s3://{BUCKET}/{latest_key}", f"s3://{BUCKET}/{historical_key}"

    else:
        latest_path = f"{LOCAL_DIR_LATEST}/{subdir_or_prefix}/dag_image/{dag_file_name}"
        historical_path = f"{LOCAL_DIR_HISTORICAL}/{price_cap_period_prefix}/{subdir_or_prefix}/dag_image/{dag_file_name}"

        storage.delete_files_in_directory(
            f"{LOCAL_DIR_LATEST}/{subdir_or_prefix}/dag_image"
        )

        storage.save_local_file(
            file_path=latest_path,
            content=dag_image,
        )
        storage.save_local_file(
            file_path=historical_path,
            content=dag_image,
        )

        return latest_path, historical_path
