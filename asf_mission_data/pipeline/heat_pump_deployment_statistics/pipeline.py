# Pipeline entry point
"""
This needs to define the main function
that orchestrates the execution of the
pipeline stages.
"""

from datetime import datetime, timezone
from importlib.metadata import version

from hamilton import driver

from asf_mission_data import storage, utils
from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.heat_pump_deployment_statistics import bronze, silver
from asf_mission_data.pipeline.heat_pump_deployment_statistics.config import (
    HEAT_PUMP_DEPLOYMENT_STATISTICS,
)

logger = setup_logging(__name__)


def build_bronze_driver() -> driver.Driver:

    dr = (
        driver.Builder()
        .with_modules(bronze)
        .with_config(
            {
                "dataset_prefix": HEAT_PUMP_DEPLOYMENT_STATISTICS["dataset_prefix"],
                "collection_url": HEAT_PUMP_DEPLOYMENT_STATISTICS["collection_url"],
                "page_link_text": HEAT_PUMP_DEPLOYMENT_STATISTICS["page_link_text"],
                "file_link_text": HEAT_PUMP_DEPLOYMENT_STATISTICS["file_link_text"],
                "publisher": HEAT_PUMP_DEPLOYMENT_STATISTICS["publisher"],
                "pipeline_version": version("asf-mission-data"),
                "bronze_ingest_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        .build()
    )
    return dr


def run_bronze_pipeline() -> None:

    dr = build_bronze_driver()

    node_targets = ["bronze_heat_pump_deployment_statistics_file", "latest_filename", "latest_publication_date"]
    results = dr.execute(node_targets)

    # generate dag image
    dag_png = dr.visualize_execution(
        ["bronze_heat_pump_deployment_statistics_file"],
        None,
        render_kwargs={},
    ).pipe(format="png")

    # save dag image
    storage.save_dag(
        layer_prefix="bronze",
        dataset_prefix=HEAT_PUMP_DEPLOYMENT_STATISTICS["dataset_prefix"],
        accompanying_filename=results["latest_filename"],
        dag_image=dag_png,
        date_stamp=f"published={utils.normalise_date_string(results['latest_publication_date'])}",
    )


def build_silver_driver(sheet_name: str) -> driver.Driver:

    dr = (
        driver.Builder()
        .with_modules(silver)
        .with_config({"dataset_prefix": HEAT_PUMP_DEPLOYMENT_STATISTICS["dataset_prefix"], "sheet_name": sheet_name})
        .build()
    )
    return dr


def run_silver_pipeline() -> None:

    tables = [
        ("Table 1.1", "silver_heat_pump_deployment_statistics_table_1_1_parquet"),
        ("Table 1.2", "silver_heat_pump_deployment_statistics_table_1_2_parquet"),
    ]

    for sheet_name, output_node in tables:
        driver = build_silver_driver(sheet_name=sheet_name)

        results = driver.execute([output_node, "latest_publication_date"])

        dag_png = driver.visualize_execution([output_node]).pipe(format="png")

        storage.save_dag(
            layer_prefix="silver",
            dataset_prefix=HEAT_PUMP_DEPLOYMENT_STATISTICS["dataset_prefix"],
            accompanying_filename=sheet_name.lower().replace(".", "_").replace(" ", "_"),
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
