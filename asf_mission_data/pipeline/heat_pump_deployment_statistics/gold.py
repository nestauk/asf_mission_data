"""Hamilton nodes for gold-layer of the Heat Pump Deployment Statistics pipeline."""

import logging

import pandas as pd
from hamilton.function_modifiers import (
    check_output,
)

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.heat_pump_deployment_statistics.schemas import GOLD_TABLE_1_1_SCHEMA, GOLD_TABLE_1_2_SCHEMA

logger = logging.getLogger(__name__)


# ----------------------------------
# Common helpers
# ----------------------------------


def _add_quarterly_change(df: pd.DataFrame, groupby_col: str) -> pd.DataFrame:
    """Sort by quarter and add change / pct-change from the previous quarter, per group."""
    df = df.sort_values("installation_quarter_start")
    prev_value = df.groupby([groupby_col])["value"].shift(1)

    df["change_from_previous_quarter"] = df["value"] - prev_value
    df["pct_change_from_previous_quarter"] = df.groupby([groupby_col])["value"].pct_change().mul(100).round(2)

    # 0 -> 0 gives NaN (0/0 undefined); treat as 0% change, but only when a
    # previous quarter actually exists — leave first-quarter rows as NaN,
    # consistent with change_from_previous_quarter.
    flat_zero = prev_value.notna() & (prev_value == 0) & (df["value"] == 0)
    df.loc[flat_zero, "pct_change_from_previous_quarter"] = 0.0

    return df


# ----------------------------------
# Table 1.1
# ----------------------------------


def silver_heat_pump_deployment_statistics_table_1_1_dataset(dataset_prefix: str, silver_table_prefix: str) -> str:
    """Latest silver-level dataset for Table 1.1."""
    return storage.locate_latest(dataset_prefix, silver_table_prefix, "silver")


def silver_table_1_1_df(silver_heat_pump_deployment_statistics_table_1_1_dataset: str) -> pd.DataFrame:
    """Silver Table 1.1 dataset loaded as pandas DataFrame."""
    return storage.read_parquet(silver_heat_pump_deployment_statistics_table_1_1_dataset)


def table_1_1_latest_publication_date(
    silver_table_1_1_df: pd.DataFrame,
) -> str:
    """Return publication date of latestfile from metadata."""
    metadata_dict = silver_table_1_1_df["metadata"].iloc[0]
    publication_date = metadata_dict.get("publication_date")
    if not publication_date:
        raise KeyError("'publication_date' missing from silver metadata.")
    return publication_date


@check_output(
    schema=GOLD_TABLE_1_1_SCHEMA,
    importance="fail",
)
def gold_table_1_1_df(
    silver_table_1_1_df: pd.DataFrame,
) -> pd.DataFrame:
    """Augments silver table with quarter-on-quarter changes (absolute and percentage)."""
    df = silver_table_1_1_df.copy()
    df = _add_quarterly_change(df, "type")
    logger.info(
        "Produced gold table 'table_1_1': rows=%d",
        len(df),
    )
    return df


def gold_table_1_1_parquet(
    gold_table_1_1_df: pd.DataFrame,
    dataset_prefix: str,
    table_1_1_latest_publication_date: str,
) -> None:
    """Persist the gold-layer table as a parquet file."""
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_table_1_1_df,
        df_name="table_1_1",
        date_stamp=f"published={utils.normalise_date_string(table_1_1_latest_publication_date)}",
    )


# ----------------------------------
# Table 1.2
# ----------------------------------


def silver_heat_pump_deployment_statistics_table_1_2_dataset(dataset_prefix: str, silver_table_prefix: str) -> str:
    """Latest silver-level dataset for Table 1.2."""
    return storage.locate_latest(dataset_prefix, silver_table_prefix, "silver")


def silver_table_1_2_df(silver_heat_pump_deployment_statistics_table_1_2_dataset: str) -> pd.DataFrame:
    """Silver Table 1.2 dataset loaded as pandas DataFrame."""
    return storage.read_parquet(silver_heat_pump_deployment_statistics_table_1_2_dataset)


def table_1_2_latest_publication_date(
    silver_table_1_2_df: pd.DataFrame,
) -> str:
    """Return publication date of latestfile from metadata."""
    metadata_dict = silver_table_1_2_df["metadata"].iloc[0]
    publication_date = metadata_dict.get("publication_date")
    if not publication_date:
        raise KeyError("'publication_date' missing from silver metadata.")
    return publication_date


@check_output(
    schema=GOLD_TABLE_1_2_SCHEMA,
    importance="fail",
)
def gold_table_1_2_df(
    silver_table_1_2_df: pd.DataFrame,
) -> pd.DataFrame:
    """Augments silver table with quarter-on-quarter changes (absolute and percentage)."""
    df = silver_table_1_2_df.copy()
    df = _add_quarterly_change(df, "country_or_region")
    logger.info(
        "Produced gold table 'table_1_2': rows=%d",
        len(df),
    )
    return df


def gold_table_1_2_parquet(
    gold_table_1_2_df: pd.DataFrame,
    dataset_prefix: str,
    table_1_2_latest_publication_date: str,
) -> None:
    """Persist the gold-layer table as a parquet file."""
    storage.ingest_to_gold(
        dataset_prefix=dataset_prefix,
        df=gold_table_1_2_df,
        df_name="table_1_2",
        date_stamp=f"published={utils.normalise_date_string(table_1_2_latest_publication_date)}",
    )
