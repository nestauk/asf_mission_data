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


def save_s3_object(
    bucket: str,
    key: str,
    content: bytes | str,
) -> None:
    """Upload a file to an S3 bucket.

    Creates an S3 client and saves the given content (bytes or string) to
    the specified bucket and key.

    Args:
        bucket (str): Name of target S3 bucket.
        key (str): Key where content will be saved to.
        content (bytes | str): Data to upload, can be a bytes or string.
    """
    s3_client = boto3.client("s3")
    s3_client.put_object(Bucket=bucket, Key=key, Body=content)
    logger.info("File saved at s3://%s/%s", bucket, key)


def delete_s3_objects_with_prefix(bucket: str, prefix: str) -> None:
    """Deletes all S3 objects at a given prefix.

    Lists all objects under specified prefix and deletes them. If no
    objects are found, it logs a message and does nothing.

    Args:
        bucket (str): Name of target S3 bucket.
        prefix (str): Prefix identifying objects to delete.
    """
    s3_client = boto3.client("s3")
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

    if "Contents" not in response:
        logger.info(f"No existing files to delete in s3://{bucket}/{prefix}")
        return

    for object in response["Contents"]:
        s3_client.delete_object(Bucket=bucket, Key=object["Key"])
        logger.info(f"Deleted: {object['Key']}")


def save_local_file(file_path: str, content: bytes | str) -> None:
    """Save content to a local file.

    Ensures that parent directories of given file path exist,
    writes the provided content to the file in either text or binary
    mode and logs the file save operation.

    Args:
        file_path (str): Full path where content should be saved.
        content (bytes | str): Data to write to the file.
    """
    file_path = Path(file_path)
    file_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "wb" if isinstance(content, bytes) else "w"
    with open(file_path, mode) as f:
        f.write(content)
    logger.info("Saved local file: %s", file_path)


def delete_files_in_directory(directory_path: str) -> None:
    """Deletes all files in a specified local directory.

    Iterates through the given directory and deletes all files.
    Subdirectories are ignored. If the directory doesn't exist, the
    function does nothing.

    Args:
        directory_path (str): Path to directory where files should be deleted.
    """
    dir = Path(directory_path)

    if not dir.exists():
        return

    for item in dir.iterdir():
        if item.is_file():
            item.unlink()
            logger.info("Deleted local file: %s", item)
