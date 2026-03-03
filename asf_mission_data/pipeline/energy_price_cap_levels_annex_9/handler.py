# Lambda entry point
# Driver construction for hamilton

import logging
from datetime import datetime, timezone
from importlib.metadata import version

from hamilton import driver

from asf_mission_data.pipeline.energy_price_cap_levels_annex_9 import bronze
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    ENERGY_PRICE_CAP_LEVELS_ANNEX_9,
    PRICE_CAP_PERIOD_PUBLICATION_DATES,
)
from asf_mission_data import storage, utils

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
                "bronze_ingest_timestamp": datetime.now(timezone.utc).strftime(
                    "%Y-%m-%d %H:%M:%S"
                ),
            }
        )
        .build()
    )
    return dr


# TODO move this to a more appropriate module
def _validate_price_cap_period(
    dr: driver,
    price_cap_period_node_name: str = "latest_price_cap_period",
) -> None:
    """Validate that the extracted price cap period matches the most recently published
    period according to the configured publication schedule.

    The function executes the specified Hamilton node to retrieve the latest extracted
    price cap period string, converts it into a standardised pandas Interval, and
    verifies that:
        1. The period is known in the configured publication mapping.
        2. Its publication date corresponds to the most recent publication date
           that has already occurred.

    If the extracted period does not match the expected active period derived from
    the publication schedule, the pipeline is aborted.

    Args:
        dr (driver): Hamilton driver configured for the energy price cap pipeline.
        price_cap_period_node_name (str, optonal): Name of the Hamilton node that returns the
            extracted price cap period string. Defaults to "latest_price_cap_period".

    Raises:
        ValueError:
            - If the extracted period is unknown (not present in the publication mapping).
            - If the extracted period does not correspond to the most recently
              published period according to the schedule.
    """

    # Only execute the node that gives us the latest period
    results = dr.execute([price_cap_period_node_name])
    extracted_period_str = results[price_cap_period_node_name]
    logger.info("Latest extracted price cap period: %s", extracted_period_str)

    # Convert price cap period strings to standardised pd.Intervals
    extracted_period_interval = (
        utils.convert_energy_price_cap_period_string_to_interval(extracted_period_str)
    )
    INTERVAL_PUBLICATION_DATES = {
        utils.convert_energy_price_cap_period_string_to_interval(k): v
        for k, v in PRICE_CAP_PERIOD_PUBLICATION_DATES.items()
    }
    if extracted_period_interval not in INTERVAL_PUBLICATION_DATES:
        logger.error("Unknown price cap period: %s", extracted_period_interval)
        raise ValueError("Pipeline aborted: unknown price cap period.")

    # Look up publication date of extracted price cap period
    publication_date_str = INTERVAL_PUBLICATION_DATES.get(extracted_period_interval)
    publication_date = datetime.fromisoformat(publication_date_str)

    now = datetime.now()
    # Find most recent publication date that has already occurred
    latest_publication_date = max(
        datetime.fromisoformat(date)
        for date in PRICE_CAP_PERIOD_PUBLICATION_DATES.values()
        if datetime.fromisoformat(date) <= now
    )
    expected_period = [
        k
        for k, v in PRICE_CAP_PERIOD_PUBLICATION_DATES.items()
        if datetime.fromisoformat(v) == latest_publication_date
    ][0]
    logger.info("Expected price cap period: %s", expected_period)

    if publication_date != latest_publication_date:
        logger.error(
            "Validation Failed: Extracted period '%s', but based on the configured schedule "
            "(last pub date: %s), we expected '%s'.",
            extracted_period_str,
            latest_publication_date.date(),
            expected_period,
        )
        raise ValueError(
            "Pipeline aborted: extracted price cap period does not match what is expected "
            "to be the most recently published according to the publication schedule."
        )

    logger.info("Price cap period validation passed.")


def run_bronze_pipeline():
    """Run the bronze layer of the energy price cap Annex 9 ETL pipeline.

    This function performs the bronze layer workflow:
        1. Extracting and saving latest raw data file.
        2. Saving provenance metadata for raw data.
        3. Generating and saving DAG visualisation of raw file extraction.
    """

    dr = build_bronze_driver()

    _validate_price_cap_period(dr, "latest_price_cap_period")

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
