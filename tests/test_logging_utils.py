import logging

import pytest

from asf_mission_data.logging_utils import configure_logging


@pytest.fixture
def restore_logging_state():
    """
    Snapshot and restore logging state

    configure_logging() clears root handlers
    and changes logger levels globally. The
    tests should restore the previous root level,
    handlers, third-party logger levels, and
    any other logging state after each test to
    avoid side effects.
    """
    root = logging.getLogger()
    original_root_level = root.level
    original_handlers = root.handlers[:]

    third_party_loggers = [
        "boto3",
        "botocore",
        "fsspec",
        "graphviz",
        "hamilton",
        "s3fs",
        "urllib3",
    ]
    original_levels = {name: logging.getLogger(name).level for name in third_party_loggers}

    yield

    root.handlers.clear()
    root.handlers.extend(original_handlers)
    root.setLevel(original_root_level)

    for name, level in original_levels.items():
        logging.getLogger(name).setLevel(level)


def test_configure_logging_sets_root_level(restore_logging_state):
    """Test that configure_logging sets the root logger level correctly."""

    configure_logging(log_level="WARNING")

    assert logging.getLogger().level == logging.WARNING


def test_configure_logging_rejects_invalid_level(restore_logging_state):
    """Test that configure_logging raises ValueError for an invalid log level."""

    with pytest.raises(ValueError, match="Invalid log level"):
        configure_logging(log_level="INVALID_LEVEL")


def test_configure_logging_doesnt_accumulate_handlers(restore_logging_state):
    """Multiple calls shouldn't add multiple handlers"""

    configure_logging(log_level="INFO")
    configure_logging(log_level="DEBUG")

    root = logging.getLogger()

    assert len(root.handlers) == 1
    assert isinstance(root.handlers[0], logging.StreamHandler)
    assert root.level == logging.DEBUG


def test_configure_logging_suppresses_noisy_third_party_loggers(
    restore_logging_state,
):
    """Test that the noisy third party loggers are being quiet!"""
    configure_logging(log_level="INFO")

    for name in [
        "boto3",
        "botocore",
        "fsspec",
        "graphviz",
        "hamilton",
        "s3fs",
        "urllib3",
    ]:
        assert logging.getLogger(name).level == logging.WARNING
