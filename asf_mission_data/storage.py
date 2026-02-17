"""Storage path utilities for local and S3 data access."""

import os
import boto3
import logging
from pathlib import Path

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


def _is_s3_path(path: str) -> bool:
    """Check if path is an S3 URI.

    Args:
        path (str): Path string to check.

    Returns:
        bool: True if path starts with "s3://", indicating it refers to an S3 location.
    """
    return str(path).startswith("s3://")


def _parse_s3_path(s3_path: str) -> tuple[str, str]:
    """Parse an S3 URI into bucket name and key prefix.

    Args:
        s3_path (str): Full S3 URI.

    Returns:
        tuple[str, str]: A tuple containing:
            - bucket(str): S3 bucket name
            - prefix (str): Object key prefix (may be empty if no prefix provided)
    """
    _, path = s3_path.split("s3://", 1)
    parts = path.split("/", 1)
    bucket = parts[0]
    prefix = parts[1] if len(parts) > 1 else ""
    return bucket, prefix


def _cleanup_local_folder(folder: Path, delete_extension: str | None) -> None:
    """Delete files in a local folder matching a given extension.

    Args:
        folder (Path): Path to the local directory where files may be deleted.
        delete_extension (str | None): File extension to match when deleting.
            If None, all files in folder are deleted.
    Returns:
        None

    Notes:
        - Only regular files are deleted (subdirectories are ignored)
        - If no files match the criteria, nothing is deleted
    """
    deleted_files = []
    for existing_file in folder.iterdir():
        if existing_file.is_file() and (
            delete_extension is None or existing_file.name.endswith(delete_extension)
        ):
            existing_file.unlink()
            deleted_files.append(existing_file.name)
    if deleted_files:
        logger.info("Deleted old files in %s: %s", folder, ", ".join(deleted_files))


def _cleanup_s3_folder(
    s3_client: boto3.client,
    bucket: str,
    prefix: str,
    delete_extension: str | None,
) -> None:
    """Delete objects in an S3 prefix, optionally filtered by file extension.

    This function lists all objects under the given S3 `prefix` and deletes:
    - All objects if `delete_extension` is None, or
    - Only objects whose keys end with `delete_extension`.

    It is typically used to clean the "LATEST" directory before saving
    a new version of a file.

    Logs the full S3 URIs of deleted objects.

    Args:
        s3_client (boto3.client): Boto3 S3 client instance.
        bucket (str): Name of the S3 bucket.
        prefix (str): Key prefix representing the logical folder to clean.
        delete_extension (str | None): File extension filter (e.g., ".xlsx").
            If None, all objects under the prefix are deleted.

    Returns:
        None
    """
    paginator = s3_client.get_paginator("list_objects_v2")

    deleted_keys = []

    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            key = obj["Key"]

            if delete_extension is None or key.endswith(delete_extension):
                s3_client.delete_object(Bucket=bucket, Key=key)
                deleted_keys.append(key)

    if deleted_keys:
        deleted_uris = [f"s3://{bucket}/{k}" for k in deleted_keys]
        logger.info(
            "Deleted %d object(s): %s",
            len(deleted_keys),
            ", ".join(deleted_uris),
        )


def _save_local_file(file_path: Path, content: bytes | str, mode: str) -> None:
    """Save content to a local file path.

    Ensures parent directory exists before writing. Supports both binary and text content.

    Args:
        file_path (Path): Local file path where content will be saved.
        content (bytes | str): File  content to write.
        mode (str): File open mode. Must match file content:
            - "wb" for binary files
            - "w" for text

    Returns:
        None
    """
    file_path.parent.mkdir(parents=True, exist_ok=True)
    with open(file_path, mode, encoding="utf-8" if "b" not in mode else None) as f:
        f.write(content)

    logger.info("Saved local file: %s", file_path)


def _save_s3_file(
    s3_client: boto3.client, bucket: str, key: str, content: bytes | str, mode: str
) -> None:
    """Save content to an S3 bucket at the specified key.

    Args:
        s3_client (boto3.client): Boto3 S3 client instance.
        bucket (str): Name of S3 bucket.
        key (str): Object key in the bucket.
        content (bytes | str): Content to save.
        mode (str): Mode for content.
    """
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=content if "b" in mode else content.encode("utf-8"),
    )
    logger.info("File saved at s3://%s/%s", bucket, key)


def save_file_with_cleanup(
    content: bytes | str,
    base_path: str | Path,
    subdirs: list[str],
    file_name: str,
    delete_extension: str | None = None,
    cleanup_subdir: str | None = None,
    mode: str = "wb",
) -> dict[str, Path]:
    """Save a file to multiple subdirectories, optionally deleting old files in a specified folder.
    Supports both local paths and S3 URIs.

    Args:
        content (bytes | str): File content to save.
        base_path (str | Path): Base folder path under which subdirectories exist.
        subdirs (list[str]): List of subdirectories under `base_path` where the file should be saved.
        file_name (str): Name of the file to save.
        delete_extension (str | None, optional): If specified, only files ending with this extension
            will be deleted in the cleanup subdirectory. If None, all files in the cleanup subdirectory
            are deleted. Defaults to None.
        cleanup_subdir (str | None, optional): Name of the subdirectory where old files should be deleted.
            If None, no files are deleted. Defaults to None.
        mode (str, optional): File open mode. Use "wb" for bytes and "w" for text/JSON files. Defaults to "wb".

    Returns:
        dict[str, Path]: Mapping of subdirectory names to the full path of the saved file.

    Prints:
        Logs deleted files and saved file paths.
    """

    is_s3 = _is_s3_path(base_path)

    saved_paths = {}

    if is_s3:
        s3_client = boto3.client("s3")
        bucket, base_prefix = _parse_s3_path(base_path)
    else:
        base_path = Path(base_path)
        base_path.mkdir(parents=True, exist_ok=True)

    for subdir in subdirs:

        if is_s3:
            key_prefix = f"{base_prefix}/{subdir}".strip("/")
            if cleanup_subdir and subdir == cleanup_subdir:
                _cleanup_s3_folder(s3_client, bucket, key_prefix, delete_extension)
            key = f"{key_prefix}/{file_name}".strip("/")
            _save_s3_file(s3_client, bucket, key, content, mode)
            saved_paths[subdir] = f"s3://{bucket}/{key}"

        else:
            folder = base_path / subdir
            folder.mkdir(parents=True, exist_ok=True)
            if cleanup_subdir and subdir == cleanup_subdir:
                _cleanup_local_folder(folder, delete_extension)
            file_path = folder / file_name
            _save_local_file(file_path, content, mode)
            saved_paths[subdir] = str(file_path)

    return saved_paths
