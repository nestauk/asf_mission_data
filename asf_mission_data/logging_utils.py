"""Shared logging helpers for pipeline modules."""

import logging
import sys
from pathlib import Path

DEFAULT_LOG_FORMAT = "%(asctime)s [%(levelname)s] %(name)s - %(message)s"


def setup_logging(
    logger_name: str,
    log_filename: str | None = None,
    log_format: str = DEFAULT_LOG_FORMAT,
    log_level: str = "INFO",
) -> logging.Logger:
    """Create a configured logger for local runs and ECS tasks.

    Logs go to stdout by default so container platforms can collect them.
    An optional file handler can be added for local debugging.
    """

    logger = logging.getLogger(logger_name)

    level = getattr(logging, log_level.upper(), None)
    if not isinstance(level, int):
        raise ValueError(f"Invalid log level: {log_level}")

    logger.setLevel(level)
    # Stop messages bubbling up to the root logger and appearing twice.
    logger.propagate = False

    if logger.handlers:
        # Clear direct handlers so repeated setup calls stay idempotent.
        logger.handlers.clear()

    formatter = logging.Formatter(log_format)

    # Stdout is the main log destination for ECS/Fargate tasks.
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)
    logger.addHandler(stream_handler)

    if log_filename:
        # Append rather than overwrite so local debug logs are not lost on rerun.
        file_handler = logging.FileHandler(Path(log_filename), mode="a")
        file_handler.setFormatter(formatter)
        # File log is always at DEBUG level, to capture all details for local debugging.
        file_handler.setLevel(logging.DEBUG)
        logger.addHandler(file_handler)

    return logger
