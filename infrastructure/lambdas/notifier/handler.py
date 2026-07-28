"""Pipeline run notifier.

Invoked by an EventBridge rule whenever an ECS task in the pipeline cluster
STOPS. Observing the stop from outside the container means every outcome is
seen — including OOM kills and crashes the container could never report.

For each stop it:
1. classifies the outcome from the task's exit code / stop reason,
2. writes an authoritative run record to s3://<bucket>/_meta/runs/<task-id>/run.json,
   merging the richer manifest the container writes on success,
3. posts the outcome to Slack (gated by SLACK_ALERTS_ENABLED — prod only).

Uses only stdlib + boto3 (provided by the Lambda runtime): no packaging step.
"""

import json
import logging
import os
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ENVIRONMENT = os.environ.get("ENVIRONMENT", "dev")
DATA_BUCKET = os.environ.get("DATA_BUCKET", f"asf-mission-data-{ENVIRONMENT}")
LOG_GROUP_NAME = os.environ.get("LOG_GROUP_NAME", f"/ecs/asf-mission-data-{ENVIRONMENT}")
SLACK_SECRET_NAME = os.environ.get("SLACK_SECRET_NAME", f"slack/{ENVIRONMENT}/asf/bot-token")
SLACK_ALERTS_ENABLED = os.environ.get("SLACK_ALERTS_ENABLED", "false").lower() == "true"
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")

LOG_TAIL_LINES = 30

# Expected calendar/source conditions rendered as a human line instead of a
# raw traceback — these validators hard-fail when the next publication isn't
# out yet, which is not a code bug.
KNOWN_VALIDATOR_MESSAGES = {
    "LatestPriceCapValidator": "the fetched price cap period is not the expected latest one — the new cap doesn't appear to be published yet",
    "LatestPriceCapFileUrlValidator": "the file URL date is not the expected latest one — the new cap doesn't appear to be published yet",
}

_slack_credentials: dict[str, str] | None = None


def get_app_container(detail: dict[str, Any]) -> dict[str, Any]:
    for container in detail.get("containers", []):
        if container.get("name") == "app":
            return container
    return {}


def get_pipeline_and_stage(detail: dict[str, Any]) -> tuple[str, str]:
    """Recover pipeline/stage from the command override: [pipeline, "--stage", stage].

    Works for manual and scheduled runs alike — no tags needed.
    """
    for override in detail.get("overrides", {}).get("containerOverrides", []):
        command = override.get("command") or []
        if command:
            pipeline = command[0]
            stage = command[command.index("--stage") + 1] if "--stage" in command else "all"
            return pipeline, stage
    return "unknown", "unknown"


def classify_outcome(detail: dict[str, Any]) -> dict[str, str]:
    """Map the stopped task's signals to an outcome. The exit code is the source of truth."""
    stop_code = detail.get("stopCode", "")
    stopped_reason = detail.get("stoppedReason", "")
    app = get_app_container(detail)
    exit_code = app.get("exitCode")
    container_reason = app.get("reason", "")

    if stop_code in ("TerminationNotice", "SpotInterruption"):
        return {
            "status": "interrupted",
            "emoji": "🔄",
            "reason": "Spot capacity reclaimed — not a failure",
        }
    if "OutOfMemory" in stopped_reason or "OutOfMemory" in container_reason:
        return {
            "status": "failure",
            "emoji": "❌",
            "reason": "Out of memory — task killed",
        }
    if exit_code == 0:
        return {"status": "success", "emoji": "✅", "reason": "Exited cleanly"}
    if exit_code is None:
        return {
            "status": "failure",
            "emoji": "❌",
            "reason": f"Task stopped without exit code: {stopped_reason or stop_code}",
        }
    return {
        "status": "failure",
        "emoji": "❌",
        "reason": f"Exited with code {exit_code}",
    }


def parse_event_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def get_duration_seconds(detail: dict[str, Any]) -> float | None:
    started = parse_event_time(detail.get("startedAt"))
    stopped = parse_event_time(detail.get("stoppedAt"))
    if started and stopped:
        return round((stopped - started).total_seconds(), 1)
    return None


def get_task_tags(cluster_arn: str, task_arn: str) -> dict[str, str]:
    """Tags carry the human attribution; absence of triggered_by = scheduled run."""
    ecs = boto3.client("ecs")
    try:
        response = ecs.describe_tasks(cluster=cluster_arn, tasks=[task_arn], include=["TAGS"])
        tasks = response.get("tasks", [])
        if tasks:
            return {t["key"]: t["value"] for t in tasks[0].get("tags", [])}
    except Exception:
        logger.warning("Could not describe task %s for tags", task_arn, exc_info=True)
    return {}


def get_log_stream_name(task_id: str) -> str:
    # awslogs produces prefix/container/task-id, i.e. pipeline/app/<task-id>
    return f"pipeline/app/{task_id}"


def get_log_tail(task_id: str, limit: int = LOG_TAIL_LINES) -> list[str]:
    logs = boto3.client("logs")
    try:
        response = logs.get_log_events(
            logGroupName=LOG_GROUP_NAME,
            logStreamName=get_log_stream_name(task_id),
            limit=limit,
            startFromHead=False,
        )
        return [event["message"].rstrip() for event in response.get("events", [])]
    except Exception:
        logger.warning("Could not fetch log tail for task %s", task_id, exc_info=True)
        return []


def get_cloudwatch_link(task_id: str) -> str:
    # The console double-encodes path separators: / becomes $252F
    def encode(value: str) -> str:
        return urllib.parse.quote(value, safe="").replace("%", "$25")

    return (
        f"https://{AWS_REGION}.console.aws.amazon.com/cloudwatch/home?region={AWS_REGION}"
        f"#logsV2:log-groups/log-group/{encode(LOG_GROUP_NAME)}/log-events/{encode(get_log_stream_name(task_id))}"
    )


def translate_known_failure(log_tail: list[str]) -> str | None:
    text = "\n".join(log_tail)
    for validator, message in KNOWN_VALIDATOR_MESSAGES.items():
        if validator in text:
            return f"Expected condition ({validator}): {message}."
    return None


def read_container_manifest(task_id: str) -> dict[str, Any]:
    s3 = boto3.client("s3")
    key = f"_meta/runs/{task_id}/manifest.json"
    try:
        response = s3.get_object(Bucket=DATA_BUCKET, Key=key)
        return json.loads(response["Body"].read())
    except s3.exceptions.NoSuchKey:
        return {}
    except Exception:
        logger.warning(
            "Could not read container manifest s3://%s/%s",
            DATA_BUCKET,
            key,
            exc_info=True,
        )
        return {}


def write_run_record(task_id: str, record: dict[str, Any]) -> None:
    s3 = boto3.client("s3")
    key = f"_meta/runs/{task_id}/run.json"
    s3.put_object(
        Bucket=DATA_BUCKET,
        Key=key,
        Body=json.dumps(record, indent=2, default=str),
        ContentType="application/json",
    )
    logger.info("Run record written: s3://%s/%s", DATA_BUCKET, key)


def build_run_record(
    detail: dict[str, Any],
    outcome: dict[str, str],
    tags: dict[str, str],
    manifest: dict[str, Any],
    pipeline: str,
    stage: str,
    task_id: str,
) -> dict[str, Any]:
    """The authoritative row for every stop; the container manifest enriches it."""
    app = get_app_container(detail)
    return {
        **manifest,
        "run_id": task_id,
        "pipeline": pipeline,
        "stage": stage,
        "environment": ENVIRONMENT,
        "status": outcome["status"],
        "status_reason": outcome["reason"],
        "exit_code": app.get("exitCode"),
        "stop_code": detail.get("stopCode"),
        "stopped_reason": detail.get("stoppedReason"),
        "started_at": detail.get("startedAt"),
        "stopped_at": detail.get("stoppedAt"),
        "duration_seconds": get_duration_seconds(detail),
        "triggered_by": tags.get("triggered_by", "schedule"),
        "github_run_id": tags.get("github_run_id"),
        "image_tag": tags.get("image_tag"),
        "started_by": detail.get("startedBy"),
    }


def get_slack_credentials() -> dict[str, str]:
    global _slack_credentials
    if _slack_credentials is None:
        secrets = boto3.client("secretsmanager")
        response = secrets.get_secret_value(SecretId=SLACK_SECRET_NAME)
        _slack_credentials = json.loads(response["SecretString"])
    return _slack_credentials


def build_slack_message(record: dict[str, Any], log_tail: list[str], task_id: str) -> str:
    """Success is one quiet line; failure is loud with the traceback tail and a deep link."""
    pipeline, stage = record["pipeline"], record["stage"]
    status = record["status"]
    duration = record.get("duration_seconds")
    duration_text = f" · {duration}s" if duration is not None else ""
    triggered_by = record.get("triggered_by", "schedule")

    if status == "success":
        domain = record.get("price_cap_period") or record.get("publication_date")
        domain_text = f" — {domain}" if domain else ""
        return f"✅ {pipeline} · {stage} · {ENVIRONMENT}{domain_text}{duration_text} · @{triggered_by}"

    if status == "interrupted":
        return f"🔄 {pipeline} · {stage} · {ENVIRONMENT} — {record['status_reason']} (task {task_id}). It can be safely re-run."

    lines = [
        f"❌ *{pipeline} · {stage} · {ENVIRONMENT} — {record['status_reason']}*",
        f"Triggered by: {triggered_by}{duration_text}",
    ]
    known = translate_known_failure(log_tail)
    if known:
        lines.append(known)
    if log_tail:
        tail_text = "\n".join(log_tail[-LOG_TAIL_LINES:])[-2500:]
        lines.append(f"```{tail_text}```")
    lines.append(f"<{get_cloudwatch_link(task_id)}|Full logs in CloudWatch>")
    return "\n".join(lines)


def post_to_slack(message: str) -> None:
    credentials = get_slack_credentials()
    payload = {
        "channel": credentials["channel"],
        "text": message,
        "unfurl_links": False,
    }
    request = urllib.request.Request(
        "https://slack.com/api/chat.postMessage",
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {credentials['bot_token']}",
            "Content-Type": "application/json; charset=utf-8",
        },
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        body = json.loads(response.read())
    if not body.get("ok"):
        raise RuntimeError(f"Slack chat.postMessage failed: {body.get('error')}")


def lambda_handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    detail = event.get("detail", {})
    task_arn = detail.get("taskArn", "")
    task_id = task_arn.split("/")[-1]
    cluster_arn = detail.get("clusterArn", "")

    pipeline, stage = get_pipeline_and_stage(detail)
    outcome = classify_outcome(detail)
    tags = get_task_tags(cluster_arn, task_arn)
    manifest = read_container_manifest(task_id) if outcome["status"] == "success" else {}

    record = build_run_record(detail, outcome, tags, manifest, pipeline, stage, task_id)
    logger.info(
        "Task %s (%s · %s): %s — %s",
        task_id,
        pipeline,
        stage,
        outcome["status"],
        outcome["reason"],
    )

    # The authoritative record is written for every stop, alerting or not
    write_run_record(task_id, record)

    if SLACK_ALERTS_ENABLED:
        log_tail = get_log_tail(task_id) if outcome["status"] == "failure" else []
        post_to_slack(build_slack_message(record, log_tail, task_id))

    return {"status": outcome["status"], "task_id": task_id}
