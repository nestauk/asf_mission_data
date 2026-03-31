"""Run an ASF pipeline on ECS Fargate.

Usage:
    python scripts/trigger_pipeline.py example --stage all
    python scripts/trigger_pipeline.py <pipeline_name> --stage bronze
    python scripts/trigger_pipeline.py <pipeline_name> --capacity-provider FARGATE_SPOT
    python scripts/trigger_pipeline.py <pipeline_name> --wait --follow-logs
"""

import argparse
import os
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

CLUSTER = os.environ.get("ECS_CLUSTER", "asf-mission-data-dev")
TASK_FAMILY = os.environ.get("ECS_TASK_FAMILY", "asf-mission-data-dev")
SUBNET_IDS = os.environ.get("ECS_SUBNETS", "subnet-5cc6e511,subnet-eb6fcb82,subnet-1de6f466").split(",")
SECURITY_GROUP_IDS = os.environ.get("ECS_SECURITY_GROUPS", "sg-0df80dcbbc597eabb").split(",")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")
LOG_GROUP = os.environ.get("ECS_LOG_GROUP", f"/ecs/{CLUSTER}")
LOG_STREAM_PREFIX = os.environ.get("ECS_LOG_STREAM_PREFIX", "pipeline")
CONTAINER_NAME = os.environ.get("ECS_CONTAINER_NAME", "app")
POLL_INTERVAL_SECONDS = float(os.environ.get("ECS_POLL_INTERVAL_SECONDS", "5"))


@dataclass(frozen=True)
class TaskLaunch:
    task_arn: str
    task_id: str
    cluster: str
    capacity_provider: str
    log_group: str
    log_stream: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pipeline on ECS Fargate.")
    parser.add_argument("pipeline", help="Pipeline name (must match a key in pipelines.yaml)")
    parser.add_argument(
        "--stage",
        choices=["all", "bronze", "silver", "gold"],
        default="all",
        help="Which stage to run (default: all)",
    )
    parser.add_argument(
        "--capacity-provider",
        choices=["FARGATE", "FARGATE_SPOT"],
        default=os.environ.get("ECS_CAPACITY_PROVIDER", "FARGATE"),
        help="Which ECS capacity provider to use (default: ECS_CAPACITY_PROVIDER or FARGATE)",
    )
    parser.add_argument(
        "--wait",
        action="store_true",
        help="Wait for the ECS task to stop and return a non-zero exit code if it fails",
    )
    parser.add_argument(
        "--follow-logs",
        action="store_true",
        help="Stream CloudWatch logs while waiting for the ECS task to finish",
    )
    return parser.parse_args()


def build_log_stream_name(task_id: str) -> str:
    return f"{LOG_STREAM_PREFIX}/{CONTAINER_NAME}/{task_id}"


def append_github_summary(lines: list[str]) -> None:
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return

    with open(summary_path, "a", encoding="utf-8") as summary_file:
        for line in lines:
            summary_file.write(f"{line}\n")


def write_github_output(launch: TaskLaunch) -> None:
    output_path = os.environ.get("GITHUB_OUTPUT")
    if output_path:
        with open(output_path, "a", encoding="utf-8") as output_file:
            output_file.write(f"task_arn={launch.task_arn}\n")
            output_file.write(f"task_id={launch.task_id}\n")
            output_file.write(f"cluster={launch.cluster}\n")
            output_file.write(f"capacity_provider={launch.capacity_provider}\n")
            output_file.write(f"log_group={launch.log_group}\n")
            output_file.write(f"log_stream={launch.log_stream}\n")

    append_github_summary(
        [
            "### Pipeline task launched",
            f"- Task ID: `{launch.task_id}`",
            f"- Cluster: `{launch.cluster}`",
            f"- Capacity provider: `{launch.capacity_provider}`",
            f"- CloudWatch log group: `{launch.log_group}`",
            f"- CloudWatch log stream: `{launch.log_stream}`",
            "",
        ]
    )


def launch_task(pipeline: str, stage: str, capacity_provider: str) -> TaskLaunch:
    params: dict[str, Any] = {
        "cluster": CLUSTER,
        "taskDefinition": TASK_FAMILY,
        "count": 1,
        "capacityProviderStrategy": [
            {
                "capacityProvider": capacity_provider,
                "weight": 1,
            }
        ],
        "networkConfiguration": {
            "awsvpcConfiguration": {
                "subnets": SUBNET_IDS,
                "securityGroups": SECURITY_GROUP_IDS,
                "assignPublicIp": "ENABLED",
            }
        },
        "overrides": {
            "containerOverrides": [
                {
                    "name": "app",
                    "command": [pipeline, "--stage", stage],
                }
            ]
        },
    }

    client = boto3.client("ecs", region_name=AWS_REGION)
    try:
        response = client.run_task(**params)
    except (BotoCoreError, ClientError) as exc:
        print(f"Error calling ECS: {exc}", file=sys.stderr)
        sys.exit(1)

    failures = response.get("failures", [])
    if failures:
        for f in failures:
            print(f"Task failed to launch: {f['reason']}", file=sys.stderr)
        sys.exit(1)

    task_arn = response["tasks"][0]["taskArn"]
    task_id = task_arn.split("/")[-1]
    return TaskLaunch(
        task_arn=task_arn,
        task_id=task_id,
        cluster=CLUSTER,
        capacity_provider=capacity_provider,
        log_group=LOG_GROUP,
        log_stream=build_log_stream_name(task_id),
    )


def print_launch_summary(launch: TaskLaunch) -> None:
    print(f"Task started: {launch.task_id}")
    print(f"Capacity:     {launch.capacity_provider}")
    print(f"Log group:    {launch.log_group}")
    print(f"Log stream:   {launch.log_stream}")
    print(f"Watch it:     aws ecs describe-tasks --cluster {launch.cluster} --tasks {launch.task_id}")
    print(f"Logs:         aws logs tail {launch.log_group} --log-stream-names {launch.log_stream} --follow")


def describe_task(ecs_client: Any, task_arn: str) -> dict[str, Any]:
    response = ecs_client.describe_tasks(cluster=CLUSTER, tasks=[task_arn])
    failures = response.get("failures", [])
    if failures:
        raise RuntimeError(f"Unable to describe task: {failures[0]['reason']}")

    tasks = response.get("tasks", [])
    if not tasks:
        raise RuntimeError("Unable to describe task: ECS returned no tasks")

    return tasks[0]


def print_new_log_events(logs_client: Any, log_group: str, log_stream: str, next_token: str | None) -> str | None:
    params: dict[str, Any] = {
        "logGroupName": log_group,
        "logStreamName": log_stream,
        "startFromHead": True,
    }
    if next_token:
        params["nextToken"] = next_token

    try:
        response = logs_client.get_log_events(**params)
    except logs_client.exceptions.ResourceNotFoundException:
        return next_token

    for event in response.get("events", []):
        timestamp = datetime.fromtimestamp(event["timestamp"] / 1000, tz=UTC).strftime("%Y-%m-%d %H:%M:%S")
        message = event["message"].rstrip("\n")
        for line in message.splitlines() or [""]:
            print(f"[{timestamp} UTC] {line}")

    return response.get("nextForwardToken", next_token)


def report_task_result(task: dict[str, Any]) -> int:
    last_status = task.get("lastStatus", "UNKNOWN")
    stop_code = task.get("stopCode")
    stopped_reason = task.get("stoppedReason")
    containers = task.get("containers", [])

    print(f"Task status:  {last_status}")
    if stop_code:
        print(f"Stop code:    {stop_code}")
    if stopped_reason:
        print(f"Stop reason:  {stopped_reason}")

    if not containers:
        print("Task stopped without container details", file=sys.stderr)
        append_github_summary(["### Pipeline task result", "- Status: failed", "- Reason: ECS returned no container details", ""])
        return 1

    failed_containers: list[str] = []
    for container in containers:
        name = container.get("name", "<unknown>")
        exit_code = container.get("exitCode")
        reason = container.get("reason")
        detail = f"{name}: exit_code={exit_code}"
        if reason:
            detail = f"{detail}, reason={reason}"
        print(f"Container:    {detail}")
        if exit_code != 0:
            failed_containers.append(detail)

    if failed_containers:
        append_github_summary(["### Pipeline task result", "- Status: failed", f"- Details: `{' | '.join(failed_containers)}`", ""])
        return 1

    append_github_summary(["### Pipeline task result", "- Status: succeeded", ""])
    return 0


def wait_for_task(launch: TaskLaunch, follow_logs: bool) -> int:
    ecs_client = boto3.client("ecs", region_name=AWS_REGION)
    logs_client = boto3.client("logs", region_name=AWS_REGION) if follow_logs else None
    next_token: str | None = None
    last_status: str | None = None

    print("Waiting for task to finish...")
    while True:
        task = describe_task(ecs_client, launch.task_arn)
        current_status = task.get("lastStatus", "UNKNOWN")
        if current_status != last_status:
            print(f"Observed:     {current_status}")
            last_status = current_status

        if logs_client is not None:
            next_token = print_new_log_events(logs_client, launch.log_group, launch.log_stream, next_token)

        if current_status == "STOPPED":
            if logs_client is not None:
                next_token = print_new_log_events(logs_client, launch.log_group, launch.log_stream, next_token)
            return report_task_result(task)

        time.sleep(POLL_INTERVAL_SECONDS)


def run_task(pipeline: str, stage: str, capacity_provider: str, wait: bool = False, follow_logs: bool = False) -> int:
    wait = wait or follow_logs
    launch = launch_task(pipeline, stage, capacity_provider)
    print_launch_summary(launch)
    write_github_output(launch)

    if not wait:
        return 0

    try:
        return wait_for_task(launch, follow_logs=follow_logs)
    except (BotoCoreError, ClientError, RuntimeError) as exc:
        print(f"Error while monitoring ECS task: {exc}", file=sys.stderr)
        append_github_summary(["### Pipeline task result", "- Status: failed", f"- Reason: `{exc}`", ""])
        return 1


if __name__ == "__main__":
    args = parse_args()
    sys.exit(run_task(args.pipeline, args.stage, args.capacity_provider, wait=args.wait, follow_logs=args.follow_logs))
