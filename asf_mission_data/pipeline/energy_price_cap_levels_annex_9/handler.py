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

    Notes:
        - Only the bronze layer is executed; silver/gold transformations are not included.
        - DAG images are saved to `docs/dag-images` with file names based on the latest raw file name.
    """

    dr = build_bronze_driver()

    dr.execute(["saved_file_path"])

    latest_file_name = dr.execute(["latest_file_name"])["latest_file_name"]

    dag_output_dir = "docs/dag-images"

    dr.visualize_execution(
        ["saved_file_path"],
        f"{dag_output_dir}/{latest_file_name}.dag.png",
        render_kwargs={},
    )

    dr.execute(["saved_provenance_metadata_file_path"])

    dr.visualize_execution(
        ["saved_provenance_metadata_file_path"],
        f"{dag_output_dir}/{latest_file_name}.metadata.dag.png",
        render_kwargs={},
    )


if __name__ == "__main__":
    run_bronze_pipeline()
