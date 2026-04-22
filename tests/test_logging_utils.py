import logging
from pathlib import Path

import pytest

from asf_mission_data.logging_utils import setup_logging


def test_setup_logging_configures_requested_level() -> None:
    logger = setup_logging("tests.logging.level", log_level="WARNING")

    assert logger.level == logging.WARNING
    assert logger.propagate is False
    assert len(logger.handlers) == 1


def test_setup_logging_resets_existing_handlers() -> None:
    logger = logging.getLogger("tests.logging.reset")
    logger.addHandler(logging.NullHandler())

    configured_logger = setup_logging("tests.logging.reset")

    assert configured_logger is logger
    assert len(configured_logger.handlers) == 1
    assert isinstance(configured_logger.handlers[0], logging.StreamHandler)


def test_setup_logging_adds_optional_file_handler(tmp_path: Path) -> None:
    log_file = tmp_path / "pipeline.log"
    logger = setup_logging("tests.logging.file", log_filename=str(log_file))

    logger.info("hello from the file handler")

    assert len(logger.handlers) == 2
    assert "hello from the file handler" in log_file.read_text()


def test_setup_logging_rejects_invalid_level() -> None:
    with pytest.raises(ValueError, match="Invalid log level"):
        setup_logging("tests.logging.invalid", log_level="LOUD")
