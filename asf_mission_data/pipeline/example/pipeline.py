# Pipeline entry point
"""
This needs to define the main function
that orchestrates the execution of the
pipeline stages.
"""

import logging
from datetime import datetime, timezone
from importlib.metadata import version

from hamilton import driver

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.example import bronze, silver
from asf_mission_data.pipeline.example.config import DATASET_PREFIX, PAGE_URL, PUBLISHER, SILVER_TABLES_NODES_MAP, SOURCE_URL

logger = logging.getLogger(__name__)


def build_bronze_driver() -> driver.Driver:
    """Construct a Hamilton driver for the bronze layer."""

    dr = (
        driver.Builder()
        .with_modules(bronze)
        .with_config(
            {
                "dataset_prefix": DATASET_PREFIX,
                "publisher": PUBLISHER,
                "page_url": PAGE_URL,
                "source_url": SOURCE_URL,
                "pipeline_version": version("asf-mission-data"),
                "bronze_ingest_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        .build()
    )
    return dr


def run_bronze_pipeline() -> None:
    """Run the bronze layer of the example Bank Holidays pipeline.

    Extracts and loads latest raw data file to storage.
    DAG visualisation image is also generated and loaded to storage.
    """
    dr = build_bronze_driver()

    node_targets = [
        "bronze_bank_holidays_file",
        "latest_filename",
        "latest_publication_date",
    ]
    results = dr.execute(node_targets)

    # generate dag image
    dag_png = dr.visualize_execution(
        ["bronze_bank_holidays_file"],
        None,
        render_kwargs={},
    ).pipe(format="png")

    # save dag image
    storage.save_dag(
        layer_prefix="bronze",
        dataset_prefix=DATASET_PREFIX,
        accompanying_filename=results["latest_filename"],
        dag_image=dag_png,
        date_stamp=f"published={utils.normalise_date_string(results['latest_publication_date'])}",
    )


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


def run_silver_pipeline() -> None:
    """Run the silver layer of the example Bank Holidays pipeline.

    Extracts latest bronze file, transforms into silver table(s) and loads to silver-layer storage.
    DAG visualiation images are also generated and loaded to storage.
    """

    for table_name, output_node in SILVER_TABLES_NODES_MAP.items():
        driver = build_silver_driver()

        results = driver.execute([output_node, "latest_publication_date"])

        dag_png = driver.visualize_execution([output_node]).pipe(format="png")

        storage.save_dag(
            layer_prefix="silver",
            dataset_prefix=DATASET_PREFIX,
            accompanying_filename=table_name.lower().replace(".", "_").replace(" ", "_"),
            dag_image=dag_png,
            date_stamp=f"published={utils.normalise_date_string(results['latest_publication_date'])}",
        )


def run(stage: str = "bronze", extra_args: list[str] | None = None) -> None:
    if stage in ("bronze", "all"):
        logger.info("Starting bronze stage")
        run_bronze_pipeline()
        logger.info("Completed bronze stage")

    if stage in ("silver", "all"):
        logger.info("Starting silver stage")
        run_silver_pipeline()
        logger.info("Completed silver stage")
