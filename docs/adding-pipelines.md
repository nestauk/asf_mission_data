
MOVED OUT FROM README

## Testing pipelines

For new bronze/silver pipelines in this repo, the recommended baseline is:

- keep bronze tests focused on fetching and storing raw data correctly
- keep silver tests focused on transformation logic and data contracts
- add one local integration test that proves the real pipeline wiring works end to end without using S3

The example pipeline includes a complete test template:

- `tests/pipeline/example/test_bronze.py` shows how to mock an external source and assert the raw file plus metadata are written correctly
- `tests/pipeline/example/test_silver.py` shows how to test silver transform functions, validate a dataframe schema, and run a local integration test against a temporary directory
- `tests/pipeline/example/conftest.py` shows how to share sample input data and set `DATA_MODE=LOCAL` for tests

When adding a new pipeline, aim to include at least:

1. one bronze unit test that mocks the upstream fetch
2. one bronze persistence test that checks the expected file and metadata paths
3. unit tests for each non-trivial silver transform
4. one schema or contract test that rejects invalid data
5. one local integration test that runs the real pipeline against `tmp_path`

This split matters because different failures happen in different places:

- bronze tests catch broken downloads, missing metadata, and incorrect storage paths
- silver unit tests catch parsing and transformation bugs
- schema tests catch subtle bad data before it reaches the canonical output
- integration tests catch wiring mistakes between storage, Hamilton, and parquet writes

Run just the example pipeline tests with:

```bash
uv run pytest tests/pipeline/example
```

Run the full suite with:

```bash
uv run pytest
```
