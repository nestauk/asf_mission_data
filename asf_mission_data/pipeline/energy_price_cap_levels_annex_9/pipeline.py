"""
Main functions that orchestrate the execution of the pipeline stages for Energy Price Cap Levels Annex 9.
"""

import re
from datetime import datetime, timezone
from importlib.metadata import version
from pathlib import Path

from hamilton import driver
from jinja2 import Environment, FileSystemLoader

from asf_mission_data import storage, utils
from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9 import bronze, gold, silver
from asf_mission_data.pipeline.energy_price_cap_levels_annex_9.config import (
    COLLECTION_URL,
    DATASET_PREFIX,
    FILE_LINK_TEXT,
    GOLD_TABLES_NODES_MAP,
    PUBLISHER,
    SILVER_TABLES_NODES_MAP,
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
                "dataset_prefix": DATASET_PREFIX,
                "collection_url": COLLECTION_URL,
                "file_link_text": FILE_LINK_TEXT,
                "publisher": PUBLISHER,
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
        dataset_prefix=DATASET_PREFIX,
        accompanying_filename=latest_filename,
        dag_image=dag_png,
        date_stamp=f"period={utils.normalise_energy_price_cap_period_string(results['latest_price_cap_period'])}",
    )


def build_silver_driver(sheet_name: str) -> driver.Driver:
    """Construct a general Hamilton driver configured to execute silver layer DAG for a specific table in
    the Energy Price Cap Annex 9 pipeline.
    """
    dr = driver.Builder().with_modules(silver).with_config({"dataset_prefix": DATASET_PREFIX, "sheet_name": sheet_name}).build()
    return dr


def run_silver_pipeline() -> None:
    """Run the silver layer of the Energy Price Cap Annex 9 pipeline for 1c Consumption adjusted levels table.

    Extracts latest bronze file, transforms into silver tables and loads to silver-layer storage.
    DAG visualiation images are also generated and loaded to storage.
    """

    for sheet_name, output_node in SILVER_TABLES_NODES_MAP.items():
        driver = build_silver_driver(sheet_name=sheet_name)

        results = driver.execute([output_node, "latest_price_cap_period"])

        dag_png = driver.visualize_execution([output_node]).pipe(format="png")

        storage.save_dag(
            layer_prefix="silver",
            dataset_prefix=DATASET_PREFIX,
            accompanying_filename=sheet_name.lower().replace(".", "_").replace(" ", "_"),
            dag_image=dag_png,
            date_stamp=f"period={utils.normalise_energy_price_cap_period_string(results['latest_price_cap_period'])}",
        )


def build_gold_driver(silver_table_prefix: str) -> driver.Driver:
    """Construct a general Hamilton driver configured to execute gold layer DAGs from a specified silver table in
    the Energy Price Cap Annex 9 pipeline.
    """
    dr = driver.Builder().with_modules(gold).with_config({"dataset_prefix": DATASET_PREFIX, "silver_table_prefix": silver_table_prefix}).build()
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

    for silver_table_prefix, output_nodes in GOLD_TABLES_NODES_MAP.items():
        driver = build_gold_driver(silver_table_prefix=silver_table_prefix)

        results = driver.execute(output_nodes + ["latest_price_cap_period"])

        for node in output_nodes:
            dag_png = driver.visualize_execution([node]).pipe(format="png")
            accompanying_filename = node.replace("_parquet", "")
            storage.save_dag(
                layer_prefix="gold",
                dataset_prefix=DATASET_PREFIX,
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

    bronze_dr = build_bronze_driver()
    bronze_outputs = bronze_dr.execute(["latest_filename"])
    bronze_filename = bronze_outputs["latest_filename"]

    def _to_pascal(text):
        # Removes non-alphanumeric chars and capitalizes each word
        return "".join(word.capitalize() for word in re.split(r"[^a-zA-Z0-9]", text))

    def _to_snake(text):
        # Lowers text and replaces spaces/special chars with underscores
        return re.sub(r"[^a-zA-Z0-9]", "_", text.lower())

    silver_tables = {
        f"Silver table {i}": {
            "Table name": sheet,
            "S3 filename": f"{_to_snake(sheet)}.parquet",
            "DuckLake table name": f"EnergyPriceCapLevelsAnnex9_silver_{_to_pascal(sheet)}",
            "Superset dataset name": f"EnergyPriceCapLevelsAnnex9_silver_{_to_pascal(sheet)}",
        }
        for i, sheet in enumerate(SILVER_TABLES_NODES_MAP.keys(), 1)
    }

    def _clean_gold_name(text):
        # Removes the 'gold_' prefix and '_parquet' suffix
        return text.replace("gold_", "").replace("_parquet", "")

    gold_tables = {
        f"Gold table {i}": {
            "Source silver table": f"{silver_table}.parquet",
            "S3 filename": f"{_clean_gold_name(gold_table)}.parquet",
            "DuckLake table name": f"EnergyPriceCapLevelsAnnex9_gold_{_to_pascal(_clean_gold_name(gold_table))}",
            "Superset dataset name": f"EnergyPriceCapLevelsAnnex9_gold_{_to_pascal(_clean_gold_name(gold_table))}",
        }
        for silver_table, gold_list in GOLD_TABLES_NODES_MAP.items()
        for i, gold_table in enumerate(gold_list, 1)
    }

    environment = Environment(loader=FileSystemLoader("templates/"))
    template = environment.get_template("dataset_registry.txt")

    path = Path(f"asf_mission_data/pipeline/{pipeline}/dataset_registry.md")
    path.parent.mkdir(parents=True, exist_ok=True)
    content = template.render(bronze_filename=bronze_filename, silver_tables=silver_tables, gold_tables=gold_tables)
    path.write_text(content, encoding="utf-8")
    logger.info(f"Wrote {path}")
