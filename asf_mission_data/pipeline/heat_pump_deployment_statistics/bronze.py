"""Hamilton nodes for bronze-layer of the Heat Pump Deployment Statistics pipeline"""

from datetime import datetime
from pathlib import Path

from hamilton.function_modifiers import check_output_custom

from asf_mission_data import storage, utils
from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.heat_pump_deployment_statistics.validators import ExcelFileExtensionValidator, WithinThreeCalendarMonthsValidator

logger = setup_logging(__name__)


def latest_release_api_response(collection_url: str) -> dict:
    """Fetch the latest release metadata from the GOV.UK Content API."""
    collection_data = utils.fetch_govuk_content(collection_url)
    documents = utils.safe_get_govuk_response(collection_data, "links", "documents")
    latest = sorted(documents, key=lambda x: x["public_updated_at"], reverse=True)[0]
    return utils.fetch_govuk_content(latest["web_url"])


def latest_release_page_url(latest_release_api_response: dict) -> str:
    """Extract the URL of the latest release page."""
    return utils.safe_get_govuk_response(latest_release_api_response, "links", "available_translations", 0, "web_url")


def latest_file_url(
    latest_release_api_response: dict, file_content_type: str = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
) -> str:
    """Extract the latest Excel file URL from the GOV.UK Content API response."""
    attachments = utils.safe_get_govuk_response(latest_release_api_response, "details", "attachments")
    try:
        return next(a["url"] for a in attachments if a["content_type"] == file_content_type)
    except StopIteration as e:
        raise ValueError(f"Could not find attachment with content type '{file_content_type}'") from e


def latest_file_content(latest_file_url: str) -> bytes:
    """Fetch the raw content of the latest data file from given URL."""
    return utils.fetch_raw_content(latest_file_url)


@check_output_custom(ExcelFileExtensionValidator())
def latest_filename(latest_file_url: str) -> str:
    """Extract file name of downloaded data file."""
    return Path(latest_file_url).name


@check_output_custom(WithinThreeCalendarMonthsValidator())
def latest_publication_date(latest_release_api_response: dict) -> str:
    """Extract publication date of the latest release."""
    change_history = utils.safe_get_govuk_response(latest_release_api_response, "details", "change_history")
    if not change_history:
        raise ValueError("No change history (i.e. publication date) found in API response for latest release.")
    raw = utils.safe_get_govuk_response(change_history, 0, "public_timestamp")
    return datetime.strptime(raw, "%Y-%m-%dT%H:%M:%SZ").strftime("%d %B %Y")


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
