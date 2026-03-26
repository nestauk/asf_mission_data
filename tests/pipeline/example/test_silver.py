from pathlib import Path

import pandas as pd
import pandera.errors
import pytest

from asf_mission_data import storage
from asf_mission_data.pipeline.example import pipeline, silver
from asf_mission_data.pipeline.example.schemas import (
    SILVER_BANK_HOLIDAYS_SCHEMA,
)


def test_flattened_bank_holidays_df_creates_one_row_per_event(
    sample_bank_holidays_json: dict,
) -> None:
    df = silver.flattened_bank_holidays_df(sample_bank_holidays_json)

    assert list(df.columns) == [
        "division",
        "title",
        "date",
        "notes",
        "bunting",
    ]
    assert len(df) == 3
    assert set(df["division"]) == {"england-and-wales", "scotland"}


def test_parsed_bank_holidays_df_parses_dates_and_adds_year(
    sample_bank_holidays_json: dict,
) -> None:
    flattened_df = silver.flattened_bank_holidays_df(sample_bank_holidays_json)

    df = silver.parsed_bank_holidays_df(flattened_df)

    assert pd.api.types.is_datetime64_any_dtype(df["date"])
    assert list(df["year"]) == [2025, 2025, 2025]


def test_silver_bank_holidays_date_stamp_uses_bronze_ingest_time() -> None:
    date_stamp = silver.silver_bank_holidays_date_stamp(
        {
            "ingested_at": "2025-06-01 09:30:00",
        }
    )

    assert date_stamp == "ingested=2025-06-01T09-30-00Z"


def test_silver_schema_rejects_invalid_division() -> None:
    invalid_df = pd.DataFrame(
        [
            {
                "division": "wales-only",
                "title": "Invented Holiday",
                "date": pd.Timestamp("2025-01-01"),
                "notes": "",
                "bunting": True,
                "year": 2025,
            }
        ]
    )

    with pytest.raises(pandera.errors.SchemaError):
        SILVER_BANK_HOLIDAYS_SCHEMA.validate(invalid_df)


def test_run_silver_pipeline_reads_latest_bronze_and_writes_parquet(
    local_data_root: str,
    sample_bank_holidays_json: dict,
) -> None:
    storage.ingest_to_bronze(
        dataset_prefix="example",
        file=sample_bank_holidays_json,
        filename="bank-holidays.json",
        date_stamp="ingested=2025-06-01 09:30:00",
        metadata={
            "source_url": "https://www.gov.uk/bank-holidays.json",
            "ingested_at": "2025-06-01 09:30:00",
            "size_bytes": 123,
        },
    )

    pipeline.run_silver_pipeline()

    silver_path = Path(local_data_root) / "data/silver/example/latest/bank_holidays/bank_holidays.parquet"
    silver_df = pd.read_parquet(silver_path)

    validated_df = SILVER_BANK_HOLIDAYS_SCHEMA.validate(silver_df)
    assert len(validated_df) == 3
    assert set(validated_df["year"]) == {2025}
