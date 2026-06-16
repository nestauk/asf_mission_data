"""
Where silver stage code should live.
The example pipeline transforms raw bank holidays JSON
into a DataFrame, validates it, and persists as parquet
"""

import logging
from typing import Any, cast

import pandas as pd
from hamilton.function_modifiers import check_output

from asf_mission_data import storage
from asf_mission_data.pipeline.example.schemas import (
    SILVER_BANK_HOLIDAYS_SCHEMA,
)

logger = logging.getLogger(__name__)


def bronze_bank_holidays_uri(dataset_prefix: str) -> str:
    """Locate the latest bronze bank holidays JSON file."""
    uri = storage.locate_latest_bronze(dataset_prefix, "file")
    if uri is None:
        raise FileNotFoundError(f"No latest bronze file found for dataset prefix '{dataset_prefix}'.")
    logger.info("Located bronze file: %s", uri)
    return uri


def bronze_bank_holidays_json(bronze_bank_holidays_uri: str) -> dict[str, Any]:
    """Load the raw bank holidays JSON from bronze storage."""
    return cast(dict[str, Any], storage.read_json(bronze_bank_holidays_uri))


def bronze_bank_holidays_metadata(dataset_prefix: str) -> dict[str, Any]:
    """Load metadata for the latest bronze bank holidays ingest."""
    uri = storage.locate_latest_bronze(dataset_prefix, "metadata")
    if uri is None:
        raise FileNotFoundError(f"No latest bronze metadata found for dataset prefix '{dataset_prefix}'.")
    logger.info("Located bronze metadata: %s", uri)
    return cast(dict[str, Any], storage.read_json(uri))


def silver_bank_holidays_date_stamp(
    bronze_bank_holidays_metadata: dict[str, Any],
) -> str:
    """Build a stable historical silver partition from the bronze ingest timestamp."""
    ingested_at = bronze_bank_holidays_metadata.get("ingested_at")
    if not ingested_at:
        raise ValueError("Expected 'ingested_at' in bronze metadata for silver historical storage.")

    ingested_at_dt = pd.to_datetime(ingested_at, utc=True)
    if pd.isna(ingested_at_dt):
        raise ValueError(f"Could not parse bronze ingest timestamp: {ingested_at}")

    return f"ingested={ingested_at_dt.strftime('%Y-%m-%dT%H-%M-%SZ')}"


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
    silver_bank_holidays_date_stamp: str,
) -> pd.DataFrame:
    """Persist the validated DataFrame to the silver layer as parquet."""
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=validated_bank_holidays_df,
        df_name="bank_holidays",
        date_stamp=silver_bank_holidays_date_stamp,
    )
    logger.info("Silver stage persisted %d rows", len(validated_bank_holidays_df))
    return validated_bank_holidays_df
