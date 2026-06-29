"""
Where silver stage code should live.
The example pipeline transforms raw bank holidays JSON
into a DataFrame, validates it, and persists as parquet
"""

import logging
from typing import Any, cast

import pandas as pd
from hamilton.function_modifiers import check_output

from asf_mission_data import storage, utils
from asf_mission_data.pipeline.example.schemas import (
    SILVER_BANK_HOLIDAYS_SCHEMA,
)

logger = logging.getLogger(__name__)


def bronze_bank_holidays_uri(dataset_prefix: str) -> str:
    """Locate the latest bronze bank holidays JSON file."""
    uri = storage.locate_latest(dataset_prefix, "file", "bronze")
    if uri is None:
        raise FileNotFoundError(f"No latest bronze file found for dataset prefix '{dataset_prefix}'.")
    logger.info("Located bronze file: %s", uri)
    return uri


def bronze_bank_holidays_json(bronze_bank_holidays_uri: str) -> dict[str, Any]:
    """Load the raw bank holidays JSON from bronze storage."""
    return cast(dict[str, Any], storage.read_json(bronze_bank_holidays_uri))


def bronze_bank_holidays_metadata(dataset_prefix: str) -> dict[str, Any]:
    """Load metadata for the latest bronze bank holidays ingest."""
    uri = storage.locate_latest(dataset_prefix, "metadata", "bronze")
    if uri is None:
        raise FileNotFoundError(f"No latest bronze metadata found for dataset prefix '{dataset_prefix}'.")
    logger.info("Located bronze metadata: %s", uri)
    return cast(dict[str, Any], storage.read_json(uri))


def latest_publication_date(
    bronze_bank_holidays_metadata: dict[str, Any],
) -> str:
    """Return publication date of latest bronze file from metadata."""
    return bronze_bank_holidays_metadata.get("publication_date")


def flattened_bank_holidays_df(
    bronze_bank_holidays_json: dict[str, Any],
) -> pd.DataFrame:
    """Flatten nested JSON into one row per holiday per division.

    The source JSON has the structure:
        { "england-and-wales": { "division": "...", "events": [...] },
          "scotland": { ... },
          "northern-ireland": { ... } }

    Each event has: title, date, notes, bunting.
    """
    rows = []
    for division_key, division_data in bronze_bank_holidays_json.items():
        division_name = division_data.get("division", division_key)
        for event in division_data.get("events", []):
            rows.append(
                {
                    "division": division_name,
                    "title": event["title"],
                    "date": event["date"],
                    "notes": event.get("notes", ""),
                    "bunting": event.get("bunting", False),
                }
            )

    df = pd.DataFrame(rows)
    logger.info("Flattened %d holiday records across divisions", len(df))
    return df


def parsed_bank_holidays_df(
    flattened_bank_holidays_df: pd.DataFrame,
) -> pd.DataFrame:
    """Parse date strings to datetime and derive year column."""
    df = flattened_bank_holidays_df.copy()
    df["date"] = pd.to_datetime(df["date"], format="%Y-%m-%d")
    df["year"] = df["date"].dt.year
    return df


@check_output(schema=SILVER_BANK_HOLIDAYS_SCHEMA, importance="fail")
def validated_bank_holidays_df(
    parsed_bank_holidays_df: pd.DataFrame,
) -> pd.DataFrame:
    """Validate the DataFrame against the silver schema."""
    df = parsed_bank_holidays_df.copy()
    df["bunting"] = df["bunting"].astype(bool)
    df["notes"] = df["notes"].astype(str)
    df["title"] = df["title"].astype(str)
    df["division"] = df["division"].astype(str)
    return df


def silver_bank_holidays_parquet(
    validated_bank_holidays_df: pd.DataFrame,
    dataset_prefix: str,
    latest_publication_date: str,
) -> pd.DataFrame:
    """Persist the validated DataFrame to the silver layer as parquet."""
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=validated_bank_holidays_df,
        df_name="bank_holidays",
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
    )
    logger.info("Silver stage persisted %d rows", len(validated_bank_holidays_df))
    return validated_bank_holidays_df
