# Pipeline entry point
"""
This needs to define the main function
that orchestrates the execution of the
pipeline stages.
"""

from datetime import datetime, timezone

from hamilton import driver

from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.example import silver
from asf_mission_data.pipeline.example.bronze import SOURCE_URL, fetch_raw_data
from asf_mission_data.storage import ingest_to_bronze

logger = setup_logging(__name__)

DATASET_PREFIX = "example"


def run_bronze_pipeline():
    raw_data = fetch_raw_data()

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

    ingest_to_bronze(
        dataset_prefix=DATASET_PREFIX,
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


def build_silver_driver() -> driver.Driver:
    """Construct a Hamilton driver for the silver layer."""
    dr = (
        driver.Builder()
        .with_modules(silver)
        .with_config(
            {
                "dataset_prefix": DATASET_PREFIX,
            }
        )
        .build()
    )
    return dr


def run_silver_pipeline():
    dr = build_silver_driver()

    node_targets = [
        "silver_bank_holidays_parquet",
    ]
    dr.execute(node_targets)

    logger.info("Silver stage complete")


def run(stage: str = "bronze", extra_args: list | None = None) -> None:
    if stage in ("bronze", "all"):
        logger.info("Starting bronze stage")
        run_bronze_pipeline()
        logger.info("Completed bronze stage")

    if stage in ("silver", "all"):
        logger.info("Starting silver stage")
        run_silver_pipeline()
        logger.info("Completed silver stage")
