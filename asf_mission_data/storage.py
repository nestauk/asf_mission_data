"""Storage path utilities for local and S3 data access."""

import json
import logging
import os

import fsspec

logger = logging.getLogger(__name__)


def get_data_path(relative_path: str) -> str:
    """Get full path for data storage.

    Set DATA_ROOT environment variable to control where data is stored:
    - Local dev: DATA_ROOT=/tmp/pipeline-dev
    - AWS dev: DATA_ROOT=s3://asf-mission-data-dev
    - AWS prod: Leave unset (defaults to prod bucket)

    Example:
        >>> get_data_path("bronze/energy-cap/data.parquet")
        '/tmp/pipeline-dev/bronze/energy-cap/data.parquet'
    """
    base = os.environ.get("DATA_ROOT", "s3://asf-mission-data-prod")
    return f"{base}/{relative_path}"


def get_heartbeat_path(pipeline_name: str) -> str:
    """Get path for pipeline heartbeat file.

    Uses HEARTBEAT_ROOT if set, otherwise falls back to DATA_ROOT,
    otherwise defaults to the prod heartbeats bucket.
    """
    base = os.environ.get(
        "HEARTBEAT_ROOT",
        os.environ.get("DATA_ROOT", "s3://asf-heartbeats-prod"),
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

    valid_modes = {
        "LOCAL": "",
        "DEV": "s3://asf-mission-data-dev",
        "PROD": "s3://asf-mission-data-prod",
        # "DEV-TEST": "s3://asf-mission-data-tool",
    }

    data_mode = os.getenv("DATA_MODE", "PROD")
    data_root = os.getenv("DATA_ROOT")

    if data_mode not in valid_modes:
        raise ValueError(f"Invalid DATA_MODE: {data_mode}")

    if data_mode in ("DEV", "PROD"):
        if data_root != valid_modes[data_mode]:
            raise ValueError(f"Mismatch: {data_mode} requires {valid_modes[data_mode]}")

    elif data_mode == "LOCAL":
        if data_root in (valid_modes["DEV"], valid_modes["PROD"]):
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

    data_mode, data_root = _initialise_environment()

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

    data_mode, data_root = _initialise_environment()

    base_path = f"{data_root}/artifacts/dags/{layer_prefix}/{dataset_prefix}"
    historical_file = f"{base_path}/{date_stamp}/{accompanying_filename}.dag.png"
    persist(historical_file, dag_image)
