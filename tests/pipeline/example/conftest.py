# """Shared pytest fixtures for the example pipeline tests.

# `conftest.py` is a special pytest filename: pytest loads it automatically for
# tests in the same directory tree. That makes it the right place for reusable
# sample data and common setup that test modules can use without importing.
# """

# import json
# from pathlib import Path
# from typing import Any

# import pytest


# @pytest.fixture
# def sample_bank_holidays_json() -> dict[str, Any]:
#     return {
#         "england-and-wales": {
#             "division": "england-and-wales",
#             "events": [
#                 {
#                     "title": "New Year's Day",
#                     "date": "2025-01-01",
#                     "notes": "",
#                     "bunting": True,
#                 },
#                 {
#                     "title": "Early May bank holiday",
#                     "date": "2025-05-05",
#                     "notes": "VE Day anniversary",
#                     "bunting": False,
#                 },
#             ],
#         },
#         "scotland": {
#             "division": "scotland",
#             "events": [
#                 {
#                     "title": "2nd January",
#                     "date": "2025-01-02",
#                     "notes": "",
#                     "bunting": True,
#                 }
#             ],
#         },
#     }


# @pytest.fixture
# def sample_bank_holidays_bytes(sample_bank_holidays_json: dict[str, Any]) -> bytes:
#     return json.dumps(sample_bank_holidays_json).encode("utf-8")


# @pytest.fixture
# def local_data_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
#     monkeypatch.setenv("DATA_MODE", "LOCAL")
#     monkeypatch.setenv("DATA_ROOT", str(tmp_path))
#     return str(tmp_path)
