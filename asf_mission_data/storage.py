"""Storage path utilities for local and S3 data access."""

import json
import logging
import os

import fsspec
import pandas as pd

logger = logging.getLogger(__name__)

VALID_DATA_ROOTS = {
    "LOCAL": None,
    "DEV": "s3://asf-mission-data-dev",
    "PROD": "s3://asf-mission-data-prod",
}

DEFAULT_DATA_MODE = "DEV"
DEFAULT_HEARTBEAT_ROOT = "s3://asf-heartbeats-dev"


def get_data_path(relative_path: str) -> str:
    """Get full path for data storage.

    Set DATA_ROOT environment variable to control where data is stored:
    - Local dev: DATA_ROOT=/tmp/pipeline-dev
    - AWS dev: DATA_ROOT=s3://asf-mission-data-dev
    - AWS prod: DATA_MODE=PROD and DATA_ROOT=s3://asf-mission-data-prod

    Example:
        >>> get_data_path("bronze/energy-cap/data.parquet")
        '/tmp/pipeline-dev/bronze/energy-cap/data.parquet'
    """
    base = os.environ.get("DATA_ROOT", VALID_DATA_ROOTS[DEFAULT_DATA_MODE])
    return f"{base}/{relative_path}"


def get_heartbeat_path(pipeline_name: str) -> str:
    """Get path for pipeline heartbeat file.

    Uses HEARTBEAT_ROOT if set, otherwise falls back to DATA_ROOT,
    otherwise defaults to the dev heartbeats bucket.
    """
    base = os.environ.get(
        "HEARTBEAT_ROOT",
        os.environ.get("DATA_ROOT", DEFAULT_HEARTBEAT_ROOT),
    )
    return f"{base}/heartbeats/{pipeline_name}.json"


def _initialise_environment():
    """Validate and load storage configuration from environment variables.

    Reads from:
        DATA_MODE:
            Execution mode, must be one of: LOCAL, DEV, PROD.
        Data_ROOT:
            Storage root location, where local mode -> local directory path
            and dev/prod mode -> S3 bucket URI

    Validation rules:
        - DATA_MODE must be supported
        - DATA_ROOT must match the expected value for the selected mode
        - LOCAL mode cannot point to cloud storage.

    Returns:
        tuple[str, str]: DATA_MODE, DATA_ROOT

    Raises:
        ValueError:
            If DATA_MODE is invalid or DATA_ROOT does not match the expected
            configuration for the selected mode.
    """

    data_mode = os.getenv("DATA_MODE", DEFAULT_DATA_MODE)
    if data_mode not in VALID_DATA_ROOTS:
        raise ValueError(f"Invalid DATA_MODE: {data_mode}")

    default_root = VALID_DATA_ROOTS[data_mode]
    data_root = os.getenv("DATA_ROOT", default_root if default_root is not None else "")

    if data_mode in ("DEV", "PROD"):
        if data_root != VALID_DATA_ROOTS[data_mode]:
            raise ValueError(f"Mismatch: {data_mode} requires {VALID_DATA_ROOTS[data_mode]}")

    elif data_mode == "LOCAL":
        if not data_root:
            raise ValueError("LOCAL requires DATA_ROOT to be set to a local directory.")
        if data_root.startswith("s3://"):
            raise ValueError(f"Local mode cannot point to cloud storage {data_root}.")

    return data_mode, data_root


def persist(uri: str, content: bytes | dict) -> None:
    """Persist content to a local or cloud storage location.
    Supports URI schemes like local file paths or S3 URIs.

    Behaviour:
        - If `content` is a dict, it is serialised to JSON with
          indentation for readability.
        - Automatically creates parent directories/prefixes if they
          do not already exist.
        - Uses ffspec to support multiple storage backends.

    Args:
        uri (str): Target storage location.
        content (bytes | dict): Data to persist. Dictionaries are serialised to JSON.
            Bytes are written directly.
    """

    if isinstance(content, dict):
        content = json.dumps(content, indent=2)

    mode = "wb" if isinstance(content, bytes) else "w"

    fs, path = fsspec.core.url_to_fs(uri)

    parent = os.path.dirname(path)
    if parent:
        fs.mkdirs(parent, exist_ok=True)

    with fs.open(path, mode) as f:
        f.write(content)

    logger.info("Saved: %s", uri)


def delete_prefix(uri_prefix: str) -> None:
    """Recursively delete all files under a storage prefix.
    Supports both local file paths and S3 prefixes.

    Behaviour:
        - If prefix does not exist, logs and exits.
        - If prefix exists but contains no files, logs and exits.
        - If files are found, deletes everything under the prefix.

    Args:
        uri_prefix (str): Storage prefix to delete. Examples: "s3://bucket/pipeline/bronze/latest/"
    """

    fs, path = fsspec.core.url_to_fs(uri_prefix)

    if not fs.exists(path):
        logger.warning("Prefix does not exist: %s", uri_prefix)
        return

    targets = fs.glob(path + "*")

    if not targets:
        logger.warning("No files found under prefix: %s", uri_prefix)
        return

    fs.rm(path, recursive=True)

    logger.info(
        "Deleted %d item(s) under prefix: %s",
        len(targets),
        uri_prefix,
    )


def ingest_to_bronze(
    dataset_prefix: str,
    file: bytes | str,
    filename: str,
    date_stamp: str,
    metadata: dict,
    layer_prefix: str = "bronze",
) -> None:
    """Persists raw dataset files and associated metadata to the bronze storage layer.

    Behaviour:
        1. Persist the incoming dataset and metadata to the historical archive.
        2. Remove any existing files in the "latest" directory.
        3. Persist the dataset and metadata as the current "latest" version.

    Storage paths are constructed dynamically using the configured DATA_ROOT
    and can be local or remote storage via URI.

    Storage structure:
        <data_root>/data/<layer_prefix>/<dataset_prefix>/
            historical/
                <date_stamp>/
                    file/<filename>
                    metadata/<filename>.metadata.json
            latest/
                file/<filename>
                metadata/<filename>.metadata.json

    Args:
        dataset_prefix (str): Dataset identifier used to namespace storage.
        file (bytes | str): Raw dataset content to persist.
        filename (str): Name of the dataset file.
        date_stamp (str): Canonical timestamp or partition identifier for historical archiving.
        metadata (dict): Provenance metadata associated with dataset.
        layer_prefix (str): Storage namespace representing the data layer (e.g. "bronze").
            Defaults to "bronze".
    """

    _, data_root = _initialise_environment()

    base_path = f"{data_root}/data/{layer_prefix}/{dataset_prefix}"
    historical_file = f"{base_path}/historical/{date_stamp}/file/{filename}"
    historical_metadata = f"{base_path}/historical/{date_stamp}/metadata/{filename}.metadata.json"
    latest_file = f"{base_path}/latest/file/{filename}"
    latest_metadata = f"{base_path}/latest/metadata/{filename}.metadata.json"

    persist(historical_file, file)
    persist(historical_metadata, metadata)

    delete_prefix(f"{base_path}/latest/file/")
    delete_prefix(f"{base_path}/latest/metadata/")
    persist(latest_file, file)
    persist(latest_metadata, metadata)


def save_dag(
    layer_prefix: str,
    dataset_prefix: str,
    accompanying_filename: str,
    dag_image: bytes,
    date_stamp: str,
) -> None:
    """Persist a pipeline DAG visualisation artifact for a dataset.

    The function stores a PNG representation of the pipeline DAG to the
    artifacts storage area. The DAG is archived under a date-based partition
    to support traceability and reproducibility of pipeline structure at the
    time of ingestion.

    Storage layout:

        <data_root>/artifacts/dags/<layer_prefix>/<dataset_prefix>/
            <date_stamp>/<accompanying_filename>.dag.png
    Args:
        layer_prefix (str): Storage namespace representing the data layer
            (e.g. "bronze", "silver", "gold").
        dataset_prefix (str): Dataset identifier used to namespace storage.
        accompanying_filename (str): Name of dataset the DAG is associated with.
            Used to construct the DAG file name.
        dag_image (bytes): PNG image representing the DAG visualisation.
            Constructed by the Hamilton driver.
        date_stamp (str): Canonical timestamp or partition identifier for historical storage.
    """

    _, data_root = _initialise_environment()

    base_path = f"{data_root}/artifacts/dags/{layer_prefix}/{dataset_prefix}"
    historical_file = f"{base_path}/{date_stamp}/{accompanying_filename}.dag.png"
    persist(historical_file, dag_image)


def locate_latest_bronze(
    dataset_prefix: str,
    file_or_metadata: str = "file",
    layer_prefix: str = "bronze",
) -> str:
    """Locate the latest bronze dataset file or metadata for a given pipeline.

    Args:
        dataset_prefix (str): Dataset identifier used to namespace storage.
        file_or_metadata (str, optional): Either 'file' or 'metadata'.
            Defaults to "file".
        layer_prefix (str): Storage namespace representing the data layer (e.g. "bronze").
            Defaults to "bronze".

    Raises:
        ValueError: If `file_or_metadata` is not 'file' or 'metadata'.

    Returns:
        str: URI of the latest bronze file or metadata, or None if not found.
    """

    if file_or_metadata not in ["file", "metadata"]:
        raise ValueError(f"Invalid file type {file_or_metadata} to be located, must be 'file' or 'metadata'.")

    _, data_root = _initialise_environment()

    uri_prefix = f"{data_root}/data/{layer_prefix}/{dataset_prefix}/latest/{file_or_metadata}"

    fs, path = fsspec.core.url_to_fs(uri_prefix)

    if not fs.exists(path):
        logger.info("Prefix does not exist: %s", uri_prefix)
        return

    files = fs.glob(path + "/*")

    files = [f for f in files if fs.isfile(f)]

    if not files:
        logger.info("No files found under prefix: %s", uri_prefix)
        return

    logger.info(
        "Found %d item(s) under prefix: %s",
        len(files),
        uri_prefix,
    )

    return fs.unstrip_protocol(files[0])


def read_excel_sheet(excel_uri: str, sheet_name: str) -> pd.DataFrame:
    """Read a specific sheet from an Excel file into a pandas DataFrame.

    Args:
        excel_uri (str): URI or path to the Excel file.
        sheet_name (str): Name of the sheet to read.

    Returns:
        pd.DataFrame: DataFrame containing the sheet data.
    """
    try:
        df = pd.read_excel(excel_uri, sheet_name, engine="openpyxl")
        logger.info(f"Successfully loaded '{sheet_name}' from {excel_uri} as a dataframe.")
        return df
    except Exception as e:
        logger.error(f"Failed to load tab '{sheet_name}' from Excel file '{excel_uri}' as dataframe: {e}")
        raise e


def read_json(json_uri: str) -> any:
    """Read a JSON file from local or remote storage.

    Args:
        json_uri (str): URI or path to the JSON file.

    Returns:
        any: Parsed JSON content.
    """

    try:
        with fsspec.open(json_uri, mode="r") as f:
            data = json.load(f)

        logger.info("Successfully loaded JSON from %s", json_uri)
        return data

    except FileNotFoundError:
        logger.error("JSON file not found: %s", json_uri)
        raise

    except Exception:
        logger.exception("Unexpected error while reading JSON: %s", json_uri)
        raise


def persist_df_parquet(uri: str, df: pd.DataFrame) -> None:
    """Persist a pandas DataFrame as a Parquet file.

    Args:
        uri (str): Destination URI or path.
        df (pd.DataFrame): DataFrame to save.
    """
    fs, path = fsspec.core.url_to_fs(uri)

    parent = os.path.dirname(path)
    if parent:
        fs.mkdirs(parent, exist_ok=True)

    with fs.open(path, "wb") as f:
        df.to_parquet(f, engine="pyarrow", index=False)

    logger.info("Saved parquet: %s", uri)


def ingest_to_silver(
    dataset_prefix: str,
    df: pd.DataFrame,
    df_name: str,
    date_stamp: str,
    layer_prefix: str = "silver",
) -> None:
    """Save a DataFrame to the silver storage layer.

    Behaviour:
        - Stores a historical version with timestamp.
        - Updates the 'latest' version by replacing previous files.

    Args:
        dataset_prefix (str): Dataset identifier used to namespace storage.
        df (pd.DataFrame): DataFrame to persist.
        df_name (str): Name of the DataFrame (used in storage paths).
        date_stamp (str): Canonical timestamp for historical storage.
        layer_prefix (str): Storage namespace representing the data layer (e.g. "silver").
            Defaults to "silver".
    """

    _, data_root = _initialise_environment()

    base_path = f"{data_root}/data/{layer_prefix}/{dataset_prefix}"
    historical_file = f"{base_path}/historical/{date_stamp}/{df_name}/{df_name}.parquet"
    latest_file = f"{base_path}/latest/{df_name}/{df_name}.parquet"

    persist_df_parquet(historical_file, df)

    delete_prefix(f"{base_path}/latest/{df_name}")
    persist_df_parquet(latest_file, df)
