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
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9 import bronze, gold, silver
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    ENERGY_PRICE_CAP_LEVELS_ANNEX_9,
)

logger = setup_logging(__name__)


def build_bronze_driver() -> driver.Driver:
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
                "dataset_prefix": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"],
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


def run_bronze_pipeline() -> None:
    """Run the bronze layer of the energy price cap Annex 9 ETL pipeline.

    This function performs the bronze layer workflow:
        1. Extracting and saving latest raw data file.
        2. Saving provenance metadata for raw data.
        3. Generating and saving DAG visualisation of raw file extraction.
    """

    dr = build_bronze_driver()

    node_targets = [
        "bronze_energy_price_cap_annex_9_file",
        "latest_filename",
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
    latest_filename = results["latest_filename"]

    # save dag image
    storage.save_dag(
        layer_prefix="bronze",
        dataset_prefix=ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"],
        accompanying_filename=latest_filename,
        dag_image=dag_png,
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(results['latest_price_cap_period'])}",
    )


def build_silver_1c_consumption_adjusted_levels_driver() -> driver.Driver:
    """Construct a Hamilton driver for the silver layer processing of tariff tables.

    This driver is configured with the `silver` nodes module and the relevant
    sheet name from the configuration to execute the ETL workflow for silver-layer
    datasets.

    Returns:
        driver.Builder: Configured Hamilton driver ready to execute the silver ETL graph.
    """

    sheet_name = "1c Consumption adjusted levels"  # TODO refactor

    dr = (
        driver.Builder()
        .with_modules(silver)
        .with_config({"dataset_prefix": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"], "sheet_name": sheet_name})
        .build()
    )
    return dr


def run_silver_pipeline() -> None:
    """Execute the silver layer workflow for tariff tables in the Energy Price Cap Levels Annex 9 pipeline.

    Workflow steps:
        1. Run the ETL workflow for silver tariff tables.
        2. Persist the resulting Parquet dataset.
        3. Generate a DAG visualisation for the silver ETL nodes and save it
           for traceability.

    Note:
        Additional silver-layer drivers can be added to this function as more
        silver datasets are processed.
    """

    # ----- Silver dataset: 1c consumption adjusted levels -----

    consumption_adjusted_levels_dr = build_silver_1c_consumption_adjusted_levels_driver()
    sheet_name = "1c Consumption adjusted levels"  # TODO refactor

    node_targets = [
        "silver_energy_price_cap_annex_9_1c_consumption_adjusted_levels_parquet",
        "latest_price_cap_period",
    ]
    results = consumption_adjusted_levels_dr.execute(node_targets)

    # generate dag image
    dag_png = consumption_adjusted_levels_dr.visualize_execution(
        ["silver_energy_price_cap_annex_9_1c_consumption_adjusted_levels_parquet"],
        None,
        render_kwargs={},
    ).pipe(format="png")

    # save dag image
    storage.save_dag(
        layer_prefix="silver",
        dataset_prefix=ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"],
        accompanying_filename=sheet_name.lower().replace(" ", "_"),
        dag_image=dag_png,
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(results['latest_price_cap_period'])}",
    )


# -------------------------------------------------------------
# Gold
# -------------------------------------------------------------


# TODO refactor to be more generic and move to common module
# NOTE this is for gold tables from 1c consumption adjusted levels sheet only
def build_gold_driver() -> driver.Builder:
    """Construct a Hamilton driver for the gold layer of the Energy Price Cap
        Annex 9 pipeline.

    This driver is configured with the `gold` nodes module and the relevant
    sheet name from the configuration to execute the ETL workflow for gold-layer
    datasets.

    Returns:
        driver.Builder: Configured Hamilton driver ready to execute the gold ETL graph.
    """

    dr = (
        driver.Builder()
        .with_modules(gold)
        .with_config(
            {"dataset_prefix": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"], "silver_table_prefix": "1c_consumption_adjusted_levels"}
        )
        .build()
    )
    return dr


def run_gold_pipeline():
    """Execute the gold layer worflow for the Energy Price Cap Levels Annex 9 pipeline.

    Gold datasets generated:
        - Consumption-adjusted tariff levels including VAT as an explicit component
        - Tariff component standing charges (p/day) and unit prices (p/kWh) for each fuel,
            payment method and price cap period.
        - Price ratios for electricity (single-rate) and gas,
            for each payment method and price cap period.
        - Annual bill contriutions from standing charges and consumption-based costs for
            each fuel, payment method and price cap period.
    """

    gold_dr = build_gold_driver()
    gold_dr.execute(["gold_1c_consumption_adjusted_levels_with_vat_parquet"])
    gold_dr.execute(["gold_tariff_component_rates_parquet"])
    gold_dr.execute(["gold_price_ratios_parquet"])
    gold_dr.execute(["gold_annual_bill_fixed_and_variable_component_contributions_parquet"])

    # TODO decide whether we need this if we want to save DAG images for gold
    # latest_price_cap_period_str = gold_dr.execute("latest_price_cap_period")["latest_price_cap_period"]


# -------------------------------------------------------------
# Pipeline execution entry point
# -------------------------------------------------------------


def run(stage: str = "bronze", extra_args: list[str] | None = None) -> None:
    if stage in ("bronze", "all"):
        logger.info("Starting bronze stage")
        run_bronze_pipeline()
        logger.info("Completed bronze stage")

    if stage in ("silver", "all"):
        logger.info("Starting silver stage")
        run_silver_pipeline()
        logger.info("Completed silver stage")
