"""
Main functions that orchestrate the execution of the pipeline stages.
"""

import logging
from datetime import datetime, timezone
from importlib.metadata import version

from hamilton import driver

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.boiler_upgrade_scheme_statistics import bronze
from asf_mission_data.pipeline.boiler_upgrade_scheme_statistics.config import (
    COLLECTION_URL,
    DATASET_PREFIX,
    PUBLISHER,
)

logger = logging.getLogger(__name__)


def build_bronze_driver() -> driver.Driver:
    """Construct Hamilton driver configured to execute the bronze layer DAG for the
    Boiler Upgrade Scheme Statistics pipeline.
    """

    dr = (
        driver.Builder()
        .with_modules(bronze)
        .with_config(
            {
                "dataset_prefix": DATASET_PREFIX,
                "collection_url": COLLECTION_URL,
                "publisher": PUBLISHER,
                "pipeline_version": version("asf-mission-data"),
                "bronze_ingest_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        .build()
    )
    return dr


def run_bronze_pipeline() -> None:
    """Run the bronze layer of the Boiler Upgrade Scheme Statistics pipeline.

    Extracts and loads latest raw data file to storage.
    DAG visualiation image is also generated and loaded to storage.
    """
    dr = build_bronze_driver()

    node_targets = [
        "bronze_boiler_upgrade_scheme_statistics_file",
        "latest_filename",
        "latest_publication_date",
    ]
    results = dr.execute(node_targets)

    # generate dag image
    dag_png = dr.visualize_execution(
        ["bronze_boiler_upgrade_scheme_statistics_file"],
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


def run(stage: str = "bronze", extra_args: list[str] | None = None) -> None:
    """Pipeline execution entry point."""
    if stage in ("bronze", "all"):
        logger.info("Starting bronze stage")
        run_bronze_pipeline()
        logger.info("Completed bronze stage")
