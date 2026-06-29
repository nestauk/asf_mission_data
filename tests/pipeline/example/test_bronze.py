import json
from pathlib import Path
from typing import Any

import pytest

from asf_mission_data.pipeline.example import bronze, pipeline
from asf_mission_data.pipeline.example.config import SOURCE_URL


def test_latest_file_content_fetches_bytes(
    monkeypatch: pytest.MonkeyPatch,
    sample_bank_holidays_bytes: bytes,
) -> None:
    monkeypatch.setattr(bronze.utils, "fetch_raw_content", lambda url: sample_bank_holidays_bytes)

    assert bronze.latest_file_content(SOURCE_URL) == sample_bank_holidays_bytes


def test_run_bronze_pipeline_persists_latest_file_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
    local_data_root: str,
    sample_bank_holidays_bytes: bytes,
) -> None:
    monkeypatch.setattr(pipeline, "fetch_raw_data", lambda: sample_bank_holidays_bytes)

    pipeline.run_bronze_pipeline()

    latest_file = Path(local_data_root) / "data/bronze/example/latest/file/bank-holidays.json"
    latest_metadata = Path(local_data_root) / "data/bronze/example/latest/metadata/bank-holidays.json.metadata.json"

    assert latest_file.read_bytes() == sample_bank_holidays_bytes

    metadata: dict[str, Any] = json.loads(latest_metadata.read_text())
    assert metadata["source_url"] == bronze.SOURCE_URL
    assert metadata["size_bytes"] == len(sample_bank_holidays_bytes)
    assert metadata["ingested_at"]
