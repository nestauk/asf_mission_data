"""Run-level observability: validation harvesting, run manifest, and heartbeat.

Each pipeline run accumulates state in a module-level RunContext:

- Hamilton drivers attach the validation collector via
  ``.with_adapters(*observability.driver_adapters())`` so every validator's
  ValidationResult is captured instead of being lost in suppressed logs.
- Pipelines call ``observability.record(...)`` to add domain fields the
  drivers already compute (e.g. price cap period, filename).
- On success the entry point calls ``write_success_manifest()``, which writes
  the rich run manifest to ``_meta/runs/`` and a liveness heartbeat.

Failures need nothing here: exceptions propagate to a non-zero exit and the
notifier Lambda (watching ECS task stops from outside the container) writes
the authoritative failure record.
"""

import json
import logging
import os
import urllib.request
import uuid
from datetime import datetime, timezone
from importlib.metadata import version
from typing import Any

from hamilton.lifecycle import NodeExecutionHook

from asf_mission_data import storage

logger = logging.getLogger(__name__)

IS_DATA_VALIDATOR_TAG = "hamilton.data_quality.contains_dq_results"
DATA_VALIDATOR_SOURCE_NODE_TAG = "hamilton.data_quality.source_node"


class ValidationResultsCollector(NodeExecutionHook):
    """Captures each Hamilton validator's ValidationResult as it executes.

    Importance is not exposed to lifecycle hooks, but it is implied: a failing
    ``importance="fail"`` validator halts the run before the success manifest
    is written, so any ``passed: false`` entry in a success manifest is
    warn-level by definition.
    """

    def __init__(self) -> None:
        self.results: list[dict[str, Any]] = []

    def run_before_node_execution(self, **future_kwargs: Any) -> None:
        pass

    def run_after_node_execution(
        self,
        *,
        node_name: str,
        node_tags: dict[str, Any],
        result: Any,
        success: bool,
        **future_kwargs: Any,
    ) -> None:
        if not node_tags.get(IS_DATA_VALIDATOR_TAG) or not success:
            return
        source_node = node_tags.get(DATA_VALIDATOR_SOURCE_NODE_TAG, "")
        # Validator nodes are named "<source_node>_<ValidatorName>"
        validator = node_name.removeprefix(f"{source_node}_") if source_node else node_name
        self.results.append(
            {
                "validator": validator,
                "node": source_node,
                "passed": bool(getattr(result, "passes", False)),
                "message": getattr(result, "message", ""),
            }
        )


class RunContext:
    """Accumulates run metadata across the lifetime of one pipeline process."""

    def __init__(self) -> None:
        self.validation_collector = ValidationResultsCollector()
        self.domain_fields: dict[str, Any] = {}
        self.started_at = datetime.now(timezone.utc)


_run_context = RunContext()


def get_run_context() -> RunContext:
    return _run_context


def reset_run_context() -> None:
    """Start a fresh context (used by tests; each container runs one pipeline)."""
    global _run_context
    _run_context = RunContext()


def driver_adapters() -> list[NodeExecutionHook]:
    """Adapters every pipeline driver should attach: ``.with_adapters(*driver_adapters())``."""
    return [_run_context.validation_collector]


def record(**fields: Any) -> None:
    """Record domain fields (e.g. price_cap_period, filename) for the run manifest."""
    _run_context.domain_fields.update(fields)


def get_task_id() -> str | None:
    """The ECS task id, from the container metadata endpoint. None outside ECS.

    The notifier Lambda joins its authoritative stop record to this manifest
    by task id, so both sides must agree on it.
    """
    metadata_uri = os.environ.get("ECS_CONTAINER_METADATA_URI_V4")
    if not metadata_uri:
        return None
    try:
        with urllib.request.urlopen(f"{metadata_uri}/task", timeout=2) as response:
            task_arn = json.load(response)["TaskARN"]
        return str(task_arn).split("/")[-1]
    except Exception:
        logger.warning("Could not read task metadata from %s", metadata_uri, exc_info=True)
        return None


def get_manifest_path(run_id: str) -> str:
    """Manifest location, kept well clear of the medallion business data under data/."""
    return storage.get_data_path(f"_meta/runs/{run_id}/manifest.json")


def build_success_manifest(pipeline: str, stage: str, run_id: str) -> dict[str, Any]:
    context = get_run_context()
    completed_at = datetime.now(timezone.utc)
    return {
        "run_id": run_id,
        "pipeline": pipeline,
        "stage": stage,
        "environment": os.environ.get("ASF_ENVIRONMENT", "local"),
        "status": "success",
        "pipeline_version": version("asf-mission-data"),
        "started_at": context.started_at.isoformat(),
        "completed_at": completed_at.isoformat(),
        "duration_seconds": round((completed_at - context.started_at).total_seconds(), 1),
        **context.domain_fields,
        "validations": context.validation_collector.results,
    }


def write_success_manifest(pipeline: str, stage: str) -> None:
    """Write the run manifest and heartbeat. Called once, after the pipeline succeeds.

    Best-effort: a pipeline that has produced good data should not exit
    non-zero because a metadata write failed.
    """
    run_id = get_task_id() or f"local-{uuid.uuid4()}"
    manifest = build_success_manifest(pipeline, stage, run_id)
    try:
        storage.persist(get_manifest_path(run_id), manifest)
        storage.persist(
            storage.get_heartbeat_path(pipeline),
            {
                "pipeline": pipeline,
                "stage": stage,
                "status": "success",
                "run_id": run_id,
                "completed_at": manifest["completed_at"],
            },
        )
        logger.info("Run manifest written: %s", get_manifest_path(run_id))
    except Exception:
        logger.error(
            "Failed to write run manifest/heartbeat for run %s",
            run_id,
            exc_info=True,
        )
