# Pipeline entry point
"""
This needs to define the main function
that orchestrates the execution of the
pipeline stages.
"""

from datetime import datetime, timezone

from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.example.bronze import SOURCE_URL, fetch_raw_data
from asf_mission_data.storage import ingest_to_bronze

logger = setup_logging(__name__)


def run_bronze_pipeline():
    raw_data = fetch_raw_data()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    ingest_to_bronze(
        dataset_prefix="example",
        file=raw_data,
        filename="bank-holidays.json",
        date_stamp=f"ingested={timestamp}",
        metadata={
            "source_url": SOURCE_URL,
            "ingested_at": timestamp,
            "size_bytes": len(raw_data),
        },
    )

    logger.info("Bronze stage complete")


def run(stage: str = "bronze", extra_args: list | None = None) -> None:
    if stage in ("bronze", "all"):
        logger.info("Starting pipeline")
        run_bronze_pipeline()
        logger.info("Completed pipeline")
