# Lambda entry point
# Driver construction for hamilton

import logging
from datetime import datetime, timezone
from importlib.metadata import version

from hamilton import driver

from asf_mission_data.pipeline.energy_price_cap_levels_annex_9 import bronze
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    ENERGY_PRICE_CAP_LEVELS_ANNEX_9,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


def build_bronze_driver() -> driver.Builder:
    """Construct a Hamilton driver configured for the  bronze layer of the
    energy price cap Annex 9 pipeline.

    This function builds and returns a Hamilton `driver.Builder` instance
    configured with the `bronze` nodes module and necessary pipeline parameters.

    Returns:
        driver.Builder: Hamilton driver ready to execute the ETL graph defined in
            the `bronze` module.
    """

    dr = (
        driver.Builder()
        .with_modules(bronze)
        .with_config(
            {
                "collection_url": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["collection_url"],
                "file_link_text": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["file_link_text"],
                "publisher": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["publisher"],
                "pipeline_version": version("asf-mission-data"),
                "bronze_ingest_timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )
        .build()
    )
    return dr


def run_bronze_pipeline():
    """Run the bronze layer of the energy price cap Annex 9 ETL pipeline.

    This function performs the bronze layer workflow:
        1. Extracting and saving latest raw data file.
        2. Generating DAG visualisation of raw file extraction.
        3. Saving provenance metadata for raw data.
        4. Generating DAG visualisation of metadata workflow.
    """

    dr = build_bronze_driver()

    dr.execute(["saved_bronze_excel_file", "saved_bronze_metadata"])

    # save dag images
    latest_file_name = dr.execute(["latest_file_name"])["latest_file_name"]
    latest_price_cap_period = dr.execute(["latest_price_cap_period"])[
        "latest_price_cap_period"
    ]
    raw_file_dag_png = dr.visualize_execution(
        ["saved_bronze_excel_file"], None, render_kwargs={}
    ).pipe(format="png")
    metadata_dag_png = dr.visualize_execution(
        ["saved_bronze_metadata"], None, render_kwargs={}
    ).pipe(format="png")
    bronze.saved_dag_visualisation(
        accompanying_file_name=latest_file_name,
        subdir_or_prefix="raw",
        dag_image=raw_file_dag_png,
        latest_price_cap_period=latest_price_cap_period,
    )
    bronze.saved_dag_visualisation(
        accompanying_file_name=latest_file_name,
        subdir_or_prefix="metadata",
        dag_image=metadata_dag_png,
        latest_price_cap_period=latest_price_cap_period,
    )


if __name__ == "__main__":
    run_bronze_pipeline()
