
# Adding a new pipeline

This guide walks through adding a new data pipeline to this repo.

## New pipeline vs. extending an existing one
A new pipeline is needed when data from a new source needs to be ingested: **a new pipeline per distinct data source**, not per dataset variation from a source already ingested.
- Extending an existing pipeline (adding a new table/output) fits inside its existing bronze/silver/gold stages if it comes from the same source and shares fetch logic.
- A genuinely new source (new publisher, new URL, new fetch/parsing logic) warrants a new pipeline directory.

## General pipeline structure

A pipeline has two or three stages:

- **Bronze** – fetch and store raw data
- **Silver** – clean and transform data
- **Gold** (optional) – aggregated outputs

Every pipeline must include at least the bronze and silver stages. All data written to S3 must be in Parquet format, so it can be read into DuckLake. Each pipeline runs as an ECS task on AWS.

This guide covers building and registering the pipeline. For running it locally or in AWS once it's built, see [`running-pipelines.md`](../docs/running-pipelines.md).

### Hamilton

All pipeline stages are written as **[Hamilton](https://hamilton.dagworks.io/)** dataflows. The core pattern is the same throughout: **each function is a node, and its argument names declare its dependencies.** Hamilton reads the module, matches argument names to other function names, and resolves the execution order automatically.

e.g., in the `example` pipeline silver stage:

```python
def bronze_bank_holidays_json(bronze_bank_holidays_uri: str) -> dict:
    return storage.read_json(bronze_bank_holidays_uri)

def flattened_bank_holidays_df(bronze_bank_holidays_json: dict) -> pd.DataFrame:
    ...

def parsed_bank_holidays_df(flattened_bank_holidays_df: pd.DataFrame) -> pd.DataFrame:
    ...

@check_output(schema=SILVER_BANK_HOLIDAYS_SCHEMA, importance="fail")
def validated_bank_holidays_df(parsed_bank_holidays_df: pd.DataFrame) -> pd.DataFrame:
    ...
```

The `@check_output` decorator on `validated_bank_holidays_df` fails the pipeline if the node's output doesn't match `SILVER_BANK_HOLIDAYS_SCHEMA`.

Calling for `validated_bank_holidays_df` triggers the full chain: `parsed_bank_holidays_df`, then `flattened_bank_holidays_df`, then `bronze_bank_holidays_json`, and so on. Hamilton works backwards from the target you name, running only what's needed to produce it.

Some arguments, like `bronze_bank_holidays_uri` above, aren't produced by another function; they're constants such as `dataset_prefix` or `collection_url`. These are supplied via `with_config()` when building the driver in `pipeline.py`:

```python
dr = driver.Builder().with_modules(silver).with_config({
    "dataset_prefix": DATASET_PREFIX,
}).build()
```

Config values are matched by name the same way function outputs are, so `dataset_prefix` in the config satisfies any function argument named `dataset_prefix`.

The driver is then executed against named output nodes:

```python
results = driver.execute(["silver_bank_holidays_parquet", "latest_publication_date"])
```

For a bit more background on why we use Hamilton, see the [project README](../README.md).


## Pipeline creation steps
Main steps (with further detail under each section below):
1. **Scaffold the pipeline** - create the pipeline directory and its files
2. **Register the pipeline** - add an entry to `pipelines.yaml`
3. **Implement bronze** - fetch and store raw data
4. **Implement silver** - clean, validate and persist transformed data
5. **Implement gold (optional)** - transform silver data further into aggregated outputs
6. **Create pipeline entrypoint** - assemble the stages in `pipeline.py`
7. **Write tests (recommended)** - cover fetch, transform, and validation logic
8. **Verify locally** - run all stages and check outputs
9. **Write a pipeline README** - complete `templates/pipelines/README.md`
10. **Open a PR** - land it on `dev`, then promote to `prod`

## 1. Scaffold the pipeline

Create a directory for your pipeline under `asf_mission_data/pipeline/`:

```
asf_mission_data/pipeline/<pipeline_name>/
├── __init__.py       # empty, marks this as a Python package
├── config.py         # constants: URLs, dataset prefix, publisher, table names
├── bronze.py         # Hamilton nodes for fetching and storing raw data
├── silver.py         # Hamilton nodes for cleaning and transforming data
├── pipeline.py       # builds drivers and defines run() entry point
├── schemas.py        # pandera schemas for validating silver output
├── validators.py     # custom Hamilton validators (if needed)
└── README.md         # see step 9
```

`gold.py` follows the same pattern as `silver.py` and is only needed if the pipeline produces aggregated outputs.

`validators.py` is only needed if you write custom `@check_output_custom` validators. If you only use the built-in `@check_output` decorator with a pandera schema, you don't need it.

## 2. Register the pipeline

Add an entry to [`pipelines.yaml`](../pipelines.yaml) at the root of the repo:

```yaml
pipelines:
  your_pipeline_name:
    owner: your_name
    schedule: TBC # TODO
    description: One sentence describing what data this pipeline fetches
    source_url: https://example.gov.uk/the-source-page
    stages: [bronze, silver]
    stack_name: tbc # TODO
```

The pipeline name must be a unique key and must match the directory name you created under `asf_mission_data/pipeline/`. It is also the value you pass to `--pipeline` when running the pipeline via GitHub Actions or the trigger script.

Include `gold` in `stages` if your pipeline has a gold stage.

`pipelines.yaml` is config, not documentation. It's read directly by GitHub Actions and by the EventBridge schedule, so `schedule` and `stages` must be accurate for the pipeline to run correctly. `description` here should stay to one sentence, since it's surfaced in tooling rather than read as prose. Fuller documentation (what the pipeline does, quirks in the source, update frequency in human terms) belongs in the pipeline's own `README.md` (see step 9).

<!-- TODO: once infrastructure is finalised on how `stack_name` and `schedule` are used, update these instructions -->

## 3. Implement bronze

Bronze fetches raw data from the source and stores it unchanged, no transformation happens here.

### `config.py`

Put all constants here: source URLs, the dataset prefix, publisher name, and any other fixed values the pipeline needs.

```python
DATASET_PREFIX = "heat_pump_deployment_statistics"
PUBLISHER = "Department for Energy Security and Net Zero"
COLLECTION_URL = "https://www.gov.uk/government/collections/heat-pump-deployment-statistics"
```

These are passed into the Hamilton driver via `with_config()` in `pipeline.py`, which makes them available as arguments in any node.

### `bronze.py`

The bronze module typically follows this shape:

1. **Discover the source** - fetch an API response or scrape a page to find where the latest file is
2. **Extract what you need** - file URL, filename, publication date
3. **Fetch the file** - download raw bytes
4. **Build metadata** - a `bronze_metadata` node that records provenance
5. **Persist** - a terminal node that calls `storage.ingest_to_bronze()` which ingests the bronze file itself alongside its accompanying metadata

**Steps 1–2** sometimes need validation - for example, checking a discovered file has the right extension or that its publication date is recent. Add a custom validator to `validators.py` and apply it with `@check_output_custom`:

```python
@check_output_custom(ExcelFileExtensionValidator())
def latest_filename(latest_file_url: str) -> str:
    return Path(latest_file_url).name
```

See [heat_pump_deployment_statistics/validators.py](../asf_mission_data/pipeline/heat_pump_deployment_statistics/validators.py) for how to implement one.

**Step 4 - metadata:** The `bronze_metadata` node should capture enough to reconstruct where the data came from. This is the core set of fields, but should be amended to what makes most sense for the pipeline you're writing. This metadata dictionary is expected to flow through to sit alongside downstream silver and gold data too.

```python
def bronze_metadata(
    publisher: str,
    collection_url: str,
    latest_file_url: str,
    latest_filename: str,
    latest_publication_date: str,
    bronze_ingest_timestamp: str,
    pipeline_version: str,
) -> dict[str, str]:
    return {
        "publisher": publisher,
        "collection_url": collection_url,
        "file_url": latest_file_url,
        "filename": latest_filename,
        "publication_date": latest_publication_date,
        "bronze_ingest_timestamp": bronze_ingest_timestamp,
        "pipeline_version": pipeline_version,
        "citation": f"Source: {publisher}, {latest_filename}. Published {latest_publication_date}.",
    }
```

**Step 5 - persist:** The terminal node is the final ingestion step for the bronze file and its metadata.

```python
def bronze_<pipeline_name>_file(
    dataset_prefix: str,
    latest_file_content: bytes,
    latest_filename: str,
    latest_publication_date: str,
    bronze_metadata: dict,
) -> None:
    storage.ingest_to_bronze(
        layer_prefix="bronze",
        dataset_prefix=dataset_prefix,
        file=latest_file_content,
        filename=latest_filename,
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
        metadata=bronze_metadata,
    )
```

See [heat_pump_deployment_statistics/bronze.py](../asf_mission_data/pipeline/heat_pump_deployment_statistics/bronze.py) for a complete worked example.

## 4. Implement silver

Silver reads raw data from the bronze layer, transforms it into clean, structured tables, and persists them as parquet. The exact structure of nodes will depend on what the source data looks like.

### `silver.py`

The silver module typically follows this shape:

1. **Locate and load bronze** - use `storage.locate_latest()` to find the latest bronze file, then read it with the matching `storage.read_*()` function for its file type (e.g. `storage.read_json()`, `storage.read_excel_sheet()`)
2. **Read publication date from bronze metadata** - use this to date-stamp the silver output
3. **Transform** - parse, clean, reshape the raw data into a tidy DataFrame; metadata is added as a separate column where each row contains the metadata dictionary
4. **Validate** - apply `@check_output` with a schema from `schemas.py`
5. **Persist** - call `storage.ingest_to_silver()` in the terminal node

### `schemas.py`

Define a pandera schema for each output table here. These are referenced by `@check_output` in step 4 above, and validated before the DataFrame is persisted:

```python
import pandera as pa

SILVER_BANK_HOLIDAYS_SCHEMA = pa.DataFrameSchema({
    "division": pa.Column(str),
    "title": pa.Column(str),
    "date": pa.Column(pa.DateTime),
    ...
})
```

**Step 5 - persist:** The terminal node follows the same pattern as bronze: it returns the DataFrame for convenience, but its main job is writing to storage. Unlike bronze, `storage.ingest_to_silver()` does not take the metadata as an argument as the metadata is expected to be a written into a separate column in the silver data.

```python
def silver_<pipeline_name>_parquet(
    validated_df: pd.DataFrame,
    dataset_prefix: str,
    latest_publication_date: str,
) -> pd.DataFrame:
    storage.ingest_to_silver(
        dataset_prefix=dataset_prefix,
        df=validated_df,
        df_name="<table_name>",
        date_stamp=f"published={utils.normalise_date_string(latest_publication_date)}",
    )
    return validated_df
```

See [heat_pump_deployment_statistics/silver.py](../asf_mission_data/pipeline/heat_pump_deployment_statistics/silver.py) for a worked example, including a pipeline with multiple output tables.

## 5. Implement gold (optional)

Gold produces aggregated, dashboard-ready outputs derived from the silver layer. Only add a gold stage if the pipeline needs outputs that go beyond the cleaned silver tables; for example, derived metrics, ratios, or reshaped views.

### `gold.py`

The pattern is identical to silver, except gold reads from silver storage instead of bronze:

1. **Load silver** - use `storage.locate_latest()` to find the latest silver file(s), then use `storage.read_parquet()`
2. **Transform** - aggregate, derive metrics, or reshape into the gold output
3. **Validate** - apply `@check_output` with a schema from `schemas.py`
4. **Persist** - call `storage.ingest_to_gold()` in the terminal node


Schemas for gold tables go in the same `schemas.py` file as silver schemas.

See [energy_price_cap_levels_annex_9/gold.py](../asf_mission_data/pipeline/energy_price_cap_levels_annex_9/gold.py) for a worked example with multiple output tables.

## 6. Create pipeline entrypoint

`pipeline.py` wires the Hamilton modules together into runnable stages. It has three responsibilities: building drivers, running stages, and exposing a `run()` entry point the CLI calls.

### Building drivers

Each stage gets its own `build_<stage>_driver()` function. Pass the stage module to `with_modules()` and all config values to `with_config()`:

```python
def build_bronze_driver() -> driver.Driver:
    return (
        driver.Builder()
        .with_modules(bronze)
        .with_config({
            "dataset_prefix": DATASET_PREFIX,
            "publisher": PUBLISHER,
            "collection_url": COLLECTION_URL,
            "pipeline_version": version("asf-mission-data"),
            "bronze_ingest_timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S"),
        })
        .build()
    )
```

If a stage produces multiple output tables from the same source (e.g. several sheets in one spreadsheet), the driver-builder function can take a parameter and fold it into the config, so the same driver logic can be reused per table:

```python
def build_silver_driver(sheet_name: str) -> driver.Driver:
    return (
        driver.Builder()
        .with_modules(silver)
        .with_config({"dataset_prefix": DATASET_PREFIX, "sheet_name": sheet_name})
        .build()
    )
```

### Running stages

Each `run_<stage>_pipeline()` function executes the driver against its target nodes, then generates and saves a DAG visualisation:

```python
def run_bronze_pipeline() -> None:
    dr = build_bronze_driver()
    results = dr.execute(["bronze_<pipeline_name>_file", "latest_filename", "latest_publication_date"])

    dag_png = dr.visualize_execution(["bronze_<pipeline_name>_file"], None, render_kwargs={}).pipe(format="png")
    storage.save_dag(
        layer_prefix="bronze",
        dataset_prefix=DATASET_PREFIX,
        accompanying_filename=results["latest_filename"],
        dag_image=dag_png,
        date_stamp=f"published={utils.normalise_date_string(results['latest_publication_date'])}",
    )
```

For a multi-table stage, loop over each table and run the driver once per output node, saving a separate DAG image each time:

```python
def run_silver_pipeline() -> None:
    for sheet_name, output_node in SILVER_TABLES_NODES_MAP.items():
        dr = build_silver_driver(sheet_name=sheet_name)
        results = dr.execute([output_node, "latest_publication_date"])

        dag_png = dr.visualize_execution([output_node]).pipe(format="png")
        storage.save_dag(
            layer_prefix="silver",
            dataset_prefix=DATASET_PREFIX,
            accompanying_filename=sheet_name.lower().replace(".", "_").replace(" ", "_"),
            dag_image=dag_png,
            date_stamp=f"published={utils.normalise_date_string(results['latest_publication_date'])}",
        )
```

`SILVER_TABLES_NODES_MAP` (defined in `config.py`) maps each source table to a sheet name, in this example, to its corresponding Hamilton output node name.

### Entrypoint

The `run()` function is called by the CLI and routes to the appropriate stage. `logger.info()` calls at each stage so stage boundaries are visible in pipeline logs:

```python
def run(stage: str = "bronze", extra_args: list[str] | None = None) -> None:
    if stage in ("bronze", "all"):
        logger.info("Starting bronze stage")
        run_bronze_pipeline()
        logger.info("Completed bronze stage")

    if stage in ("silver", "all"):
        logger.info("Starting silver stage")
        run_silver_pipeline()
        logger.info("Completed silver stage")
```

Add a matching `if stage in ("gold", "all"):` branch if your pipeline has a gold stage.

See [heat_pump_deployment_statistics/pipeline.py](../asf_mission_data/pipeline/heat_pump_deployment_statistics/pipeline.py) for a complete worked example.

## 7. Write tests (recommended)

Tests are not required to merge a new pipeline, but they guard against regressions as the codebase evolves. Different failures happen in different places, so tests should cover each layer separately:

| Layer | Catches | Minimum coverage |
|---|---|---|
| Bronze | broken downloads, missing metadata, wrong storage paths | one test mocking the upstream fetch; one test checking the file/metadata land at the expected path |
| Silver | parsing and transformation bugs | one test per non-trivial transform |
| Gold | aggregation and derivation bugs | one test per non-trivial transform (same approach as silver; no worked example yet, for now see silver's test file for the pattern to follow) |
| Schema | bad data reaching the canonical output | one test that rejects invalid data against the schema |
| Integration | wiring mistakes between storage, Hamilton, and parquet writes | one local test running the real pipeline against `tmp_path`, without S3 |

The example pipeline includes a complete test template to copy from:

- `tests/pipeline/example/test_bronze.py`: mocking an external source, asserting the raw file and metadata are written correctly
- `tests/pipeline/example/test_silver.py`: testing transform functions, validating a dataframe schema, and running a local integration test against a temporary directory
- `tests/pipeline/example/conftest.py`: sharing sample input data and setting `DATA_MODE=LOCAL` for tests

Run just the example pipeline tests with:

```bash
uv run pytest tests/pipeline/example
```

Run the full suite with:

```bash
uv run pytest
```

## 8. Verify locally

Run the full pipeline locally before opening a PR:

```bash
export DATA_MODE=LOCAL
export DATA_ROOT=/tmp/pipeline-dev

uv run python -m asf_mission_data.run <pipeline_name> --stage all
```

Check that the expected files landed under `$DATA_ROOT`:

```
data/
├── bronze/<pipeline_name>/
│   ├── latest/
│   │   ├── file/
│   │   └── metadata/
│   └── historical/<timestamp>/
│       ├── file/
│       └── metadata/
├── silver/<pipeline_name>/
│   ├── latest/<table_name>/
│   └── historical/<timestamp>/<table_name>/
└── gold/<pipeline_name>/
    ├── latest/<table_name>/
    └── historical/<timestamp>/<table_name>/
```

DAG visualisations are saved alongside each stage's output - inspect them under:

```
artifacts/dags/
├── bronze/<pipeline_name>/<timestamp>/
├── silver/<pipeline_name>/<timestamp>/
└── gold/<pipeline_name>/<timestamp>/
```

Run stages individually with `--stage bronze` or `--stage silver` instead of `--stage all`. See [`running-pipelines.md`](../docs/running-pipelines.md) for the full local and AWS run reference.

## 9. Write a pipeline README

A pipeline's `README.md` is the human-readable reference for what it produces: a plain-language description of the data, a full list of the files and tables it outputs and what they're called in S3, and any source-specific quirks a maintainer should know about.

Every pipeline directory needs one. Copy the template from [`docs/templates/pipelines/README.md`](../docs/templates/pipelines/README.md) into your pipeline directory and fill it in.

The template covers:

- **Header fields** - source, update cadence, the pipeline's registered name (must match `pipelines.yaml` and the directory name), and its S3 storage prefix (`config.DATASET_PREFIX`)
- **One section per stage** (bronze/silver/gold) - for bronze, the source, fetch method, output format, and any validators; for silver and gold, one subsection per output table describing its input, output, and validators. Delete any stage or table subsection that doesn't apply to your pipeline
- **Notes** - an optional section for lookup tables, constants, or field definitions a reader would want on hand. Delete it if there's nothing to add
- **Last updated** - update this whenever the README changes

This is separate from the `description` field in `pipelines.yaml` (step 2) that field drives tooling and should stay a single sentence; this README is for maintainers and can go into more depth.

See [heat_pump_deployment_statistics/README.md](../asf_mission_data/pipeline/heat_pump_deployment_statistics/README.md) for a filled-in example.

## 10. Open a PR

A new pipeline isn't done until it's running in prod. Follow the process in [CONTRIBUTING.md](../docs/CONTRIBUTING.md): a PR into `dev`, then a `dev` → `prod` promotion PR. Since this is the pipeline's first promotion, tick "New pipeline" in the prod PR template's checklist.

---

*Last updated: 1 July 2026 by Elysia Lucas*
