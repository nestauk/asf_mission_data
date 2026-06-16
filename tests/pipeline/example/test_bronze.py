# import json
# from pathlib import Path
# from types import TracebackType
# from typing import Any

# import pytest

# from asf_mission_data.pipeline.example import bronze, pipeline


# class _FakeResponse:
#     def __init__(self, data: bytes) -> None:
#         self._data = data

#     def read(self) -> bytes:
#         return self._data

#     def __enter__(self) -> "_FakeResponse":
#         return self

#     def __exit__(
#         self,
#         exc_type: type[BaseException] | None,
#         exc: BaseException | None,
#         tb: TracebackType | None,
#     ) -> None:
#         return None


# def test_fetch_raw_data_downloads_bytes(
#     monkeypatch: pytest.MonkeyPatch,
#     sample_bank_holidays_bytes: bytes,
# ) -> None:
#     def fake_urlopen(url: str) -> _FakeResponse:
#         assert url == bronze.SOURCE_URL
#         return _FakeResponse(sample_bank_holidays_bytes)

#     monkeypatch.setattr(bronze.urllib.request, "urlopen", fake_urlopen)

#     assert bronze.fetch_raw_data() == sample_bank_holidays_bytes


# def test_run_bronze_pipeline_persists_latest_file_and_metadata(
#     monkeypatch: pytest.MonkeyPatch,
#     local_data_root: str,
#     sample_bank_holidays_bytes: bytes,
# ) -> None:
#     monkeypatch.setattr(pipeline, "fetch_raw_data", lambda: sample_bank_holidays_bytes)

#     pipeline.run_bronze_pipeline()

#     latest_file = Path(local_data_root) / "data/bronze/example/latest/file/bank-holidays.json"
#     latest_metadata = Path(local_data_root) / "data/bronze/example/latest/metadata/bank-holidays.json.metadata.json"

#     assert latest_file.read_bytes() == sample_bank_holidays_bytes

#     metadata: dict[str, Any] = json.loads(latest_metadata.read_text())
#     assert metadata["source_url"] == bronze.SOURCE_URL
#     assert metadata["size_bytes"] == len(sample_bank_holidays_bytes)
#     assert metadata["ingested_at"]
