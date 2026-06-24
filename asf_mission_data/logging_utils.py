"""Shared logging configuration. Call configure_logging once from the entry point
(the first Python file that runs when you launch a pipeline.)"""

import logging
import sys
import warnings

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def configure_logging(
    log_level: str = "INFO",
    log_format: str = DEFAULT_LOG_FORMAT,
) -> None:
    """Set up logging for the entire application.

    Call this once at startup (in run.py). Every module
    that does logging.getLogger(__name__) will automatically
    have its messages handled by the root logger configured in
    this code."""

    # Suppress a known Pandera dependency warning from typeguard<3.
    # Keeping this narrow so other Pandera warnings remain
    warnings.filterwarnings(
        "ignore",
        message=r"Using typeguard < 3\..*",
    )
    root = logging.getLogger()
    level = getattr(logging, log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    root.setLevel(level)
    root.handlers.clear()
    formatter = logging.Formatter(log_format)

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root.addHandler(handler)

    # Shut up the noisy third-party libraries
    # Running the pipelines produced a lot of debug
    # output from third-party libraries, which made it too hard
    # to get the important info from the logs.

    logging.getLogger("aioboto3").setLevel(logging.WARNING)
    logging.getLogger("aiobotocore").setLevel(logging.WARNING)
    logging.getLogger("aiohttp").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("fsspec").setLevel(logging.WARNING)
    logging.getLogger("graphviz").setLevel(logging.WARNING)
    logging.getLogger("hamilton").setLevel(logging.WARNING)
    logging.getLogger("s3fs").setLevel(logging.WARNING)
    logging.getLogger("s3transfer").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
