"""
Where silver stage code should live.
The example pipeline transforms raw bank holidays JSON
into a DataFrame, validates it, and persists as parquet.
"""

import pandas as pd
from hamilton.function_modifiers import check_output

from asf_mission_data import storage
from asf_mission_data.logging_utils import setup_logging
from asf_mission_data.pipeline.example.schemas import (
    SILVER_BANK_HOLIDAYS_SCHEMA,
)

logger = setup_logging(__name__)


def bronze_bank_holidays_uri(dataset_prefix: str) -> str:
    """Locate the latest bronze bank holidays JSON file."""
    uri = storage.locate_latest_bronze(dataset_prefix, "file")
    logger.info("Located bronze file: %s", uri)
    return uri


def bronze_bank_holidays_json(bronze_bank_holidays_uri: str) -> dict:
    """Load the raw bank holidays JSON from bronze storage."""
    return storage.read_json(bronze_bank_holidays_uri)


def flattened_bank_holidays_df(
    bronze_bank_holidays_json: dict,
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


@check_output(schema=SILVER_BANK_HOLIDAYS_SCHEMA)
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
) -> pd.DataFrame:
    """Persist the validated DataFrame to the silver layer as parquet."""
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=validated_bank_holidays_df,
        df_name="bank_holidays",
        date_stamp="latest",
    )
    logger.info("Silver stage persisted %d rows", len(validated_bank_holidays_df))
    return validated_bank_holidays_df
