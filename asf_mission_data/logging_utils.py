"""Shared logging configuration. Call configure_logging once from the entry point
(the first Python file that runs when you launch a pipeline.)"""

import logging
import sys

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
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)
    logging.getLogger("fsspec").setLevel(logging.WARNING)
    logging.getLogger("graphviz").setLevel(logging.WARNING)
    logging.getLogger("hamilton").setLevel(logging.WARNING)
    logging.getLogger("s3fs").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
