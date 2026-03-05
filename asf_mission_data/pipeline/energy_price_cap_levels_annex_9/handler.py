# Lambda entry point
# Driver construction for hamilton

import logging
from datetime import datetime, timezone
from importlib.metadata import version

from hamilton import driver

from asf_mission_data import storage
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9 import bronze
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    ENERGY_PRICE_CAP_LEVELS_ANNEX_9,
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)


# TODO refactor to be more generic and move to common module
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
                "pipeline_name": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["pipeline_name"],
                "collection_url": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["collection_url"],
                "file_link_text": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["file_link_text"],
                "publisher": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["publisher"],
                "pipeline_version": version("asf-mission-data"),
                "bronze_ingest_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
            }
        )
        .build()
    )
    return dr


def run_bronze_pipeline():
    """Run the bronze layer of the energy price cap Annex 9 ETL pipeline.

    This function performs the bronze layer workflow:
        1. Extracting and saving latest raw data file.
        2. Saving provenance metadata for raw data.
        3. Generating and saving DAG visualisation of raw file extraction.
    """

    dr = build_bronze_driver()

    node_targets = [
        "bronze_energy_price_cap_annex_9_file",
        "latest_file_name",
        "latest_price_cap_period",
    ]
    results = dr.execute(node_targets)

    # generate dag image
    dag_png = dr.visualize_execution(
        ["bronze_energy_price_cap_annex_9_file"],
        None,
        render_kwargs={},
    ).pipe(format="png")

    # extract parameters for dag file name
    latest_file_name = results["latest_file_name"]
    price_cap_period_prefix = results["latest_price_cap_period"].replace(" ", "_")

    # save dag image
    storage.save_bronze_dag(
        pipeline_name=ENERGY_PRICE_CAP_LEVELS_ANNEX_9["pipeline_name"],
        accompanying_file_name=latest_file_name,
        dag_image=dag_png,
        date_stamp=price_cap_period_prefix,
    )


if __name__ == "__main__":
    run_bronze_pipeline()
