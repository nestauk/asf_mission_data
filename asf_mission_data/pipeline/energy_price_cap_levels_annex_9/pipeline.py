"""
Main functions that orchestrate the execution of the pipeline stages for Energy Price Cap Levels Annex 9.
"""

from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from hamilton import driver
from jinja2 import Environment, FileSystemLoader

from asf_mission_data import storage, utils
from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9 import bronze, gold, silver
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    ENERGY_PRICE_CAP_LEVELS_ANNEX_9,
)

logger = setup_logging(__name__)


def build_bronze_driver() -> driver.Driver:
    """Construct Hamilton driver configured to execute the bronze layer DAG for the
    Energy Price Cap Annex 9 pipeline.
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
    """Run the bronze layer of the Energy Price Cap Annex 9 pipeline.

    Extracts and loads latest raw data file to storage.
    DAG visualiation image is also generated and loaded to storage.
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


def build_silver_driver(sheet_name: str) -> driver.Driver:
    """Construct a general Hamilton driver configured to execute silver layer DAG for a specific table in
    the Energy Price Cap Annex 9 pipeline.
    """
    dr = (
        driver.Builder()
        .with_modules(silver)
        .with_config({"dataset_prefix": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"], "sheet_name": sheet_name})
        .build()
    )
    return dr


def run_silver_pipeline() -> None:
    """Run the silver layer of the Energy Price Cap Annex 9 pipeline for 1c Consumption adjusted levels table.

    Extracts latest bronze file, transforms into silver tables and loads to silver-layer storage.
    DAG visualiation images are also generated and loaded to storage.
    """

    # add to this as more Annex 9 silver tables are processed
    tables = [("1c Consumption adjusted levels", "silver_energy_price_cap_annex_9_1c_consumption_adjusted_levels_parquet")]

    for sheet_name, output_node in tables:
        driver = build_silver_driver(sheet_name=sheet_name)

        results = driver.execute([output_node, "latest_price_cap_period"])

        dag_png = driver.visualize_execution([output_node]).pipe(format="png")

        storage.save_dag(
            layer_prefix="silver",
            dataset_prefix=ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"],
            accompanying_filename=sheet_name.lower().replace(".", "_").replace(" ", "_"),
            dag_image=dag_png,
            date_stamp=f"period={utils.normalise_energy_price_cap_period_string(results['latest_price_cap_period'])}",
        )


def build_gold_driver(silver_table_prefix: str) -> driver.Driver:
    """Construct a general Hamilton driver configured to execute gold layer DAGs from a specified silver table in
    the Energy Price Cap Annex 9 pipeline.
    """
    dr = (
        driver.Builder()
        .with_modules(gold)
        .with_config({"dataset_prefix": ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"], "silver_table_prefix": silver_table_prefix})
        .build()
    )
    return dr


def run_gold_pipeline() -> None:
    """Run the gold layer for the Energy Price Cap Levels Annex 9 pipeline.

    Gold datasets generated:
        1. Consumption-adjusted tariff levels including VAT as an explicit component
        2. Tariff component standing charges (p/day) and unit prices (p/kWh) for each fuel,
            payment method and price cap period.
        3. Price ratios for electricity (single-rate) and gas,
            for each payment method and price cap period.
        4. Annual bill contriutions from standing charges and consumption-based costs for
            each fuel, payment method and price cap period.
    """

    # add to this as more Annex 9 silver and gold tables are processed
    tables = [
        (
            "1c_consumption_adjusted_levels",
            [
                "gold_1c_consumption_adjusted_levels_with_vat_parquet",
                "gold_tariff_component_rates_parquet",
                "gold_price_ratios_parquet",
                "gold_annual_bill_fixed_and_variable_component_contributions_parquet",
            ],
        )
    ]

    for silver_table_prefix, output_nodes in tables:
        driver = build_gold_driver(silver_table_prefix=silver_table_prefix)

        results = driver.execute(output_nodes + ["latest_price_cap_period"])

        for node in output_nodes:
            dag_png = driver.visualize_execution([node]).pipe(format="png")
            accompanying_filename = node.replace("_parquet", "")
            storage.save_dag(
                layer_prefix="gold",
                dataset_prefix=ENERGY_PRICE_CAP_LEVELS_ANNEX_9["dataset_prefix"],
                accompanying_filename=accompanying_filename,
                dag_image=dag_png,
                date_stamp=f"period={utils.normalise_energy_price_cap_period_string(results['latest_price_cap_period'])}",
            )


def run(stage: str = "bronze", extra_args: list[str] | None = None) -> None:
    """Pipeline execution entry point."""
    if stage in ("bronze", "all"):
        logger.info("Starting bronze stage")
        run_bronze_pipeline()
        logger.info("Completed bronze stage")

    if stage in ("silver", "all"):
        logger.info("Starting silver stage")
        run_silver_pipeline()
        logger.info("Completed silver stage")

    if stage in ("gold", "all"):
        logger.info("Starting gold stage")
        run_gold_pipeline()
        logger.info("Completed gold stage")


# TODO decide if this is the right place
def render_registry(pipeline: str):

    bronze_filename = (
        "Annex-9-Levelisation-allowance-methodology-and-levelised-cap-levels-v1.9.xlsx"  # TODO how to read from bronze latest_filename
    )

    # TODO refactor away from manual definition
    silver_tables = {
        "silver_table_1": {
            "sheet_name": "1c Consumption adjusted levels",
            "s3_name": "1c_consumption_adjusted_levels.parquet",  # this is sheet name in snake case
            "ducklake_name": "EnergyPriceCapLevelsAnnex9_silver_1cConsumptionAdjustedLevels",
            # {pascal case pipeline}_{stage}_{sheet name in pascal case}
            "superset_name": "EnergyPriceCapLevelsAnnex9_silver_1cConsumptionAdjustedLevels",
            # {pascal case pipeline}_{stage}_{sheet name in pascal case}
        }
    }

    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("dataset_registry.txt")

    path = Path(f"asf_mission_data/pipeline/{pipeline}/dataset_registry.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = template.render(bronze_filename=bronze_filename, silver_tables=silver_tables)
    path.write_text(content, encoding="utf-8")
    logger.info(f"Wrote {path}")
