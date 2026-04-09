"""Run an ASF pipeline on ECS Fargate.

Usage:
    python scripts/trigger_pipeline.py example --stage all
    python scripts/trigger_pipeline.py <pipeline_name> --stage bronze
    python scripts/trigger_pipeline.py <pipeline_name> --capacity-provider FARGATE_SPOT
"""

import argparse
import os
import sys
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

CLUSTER = os.environ.get("ECS_CLUSTER", "asf-mission-data-dev")
TASK_FAMILY = os.environ.get("ECS_TASK_FAMILY", "asf-mission-data-dev")
SUBNET_IDS = os.environ.get("ECS_SUBNETS", "subnet-5cc6e511,subnet-eb6fcb82,subnet-1de6f466").split(",")
SECURITY_GROUP_IDS = os.environ.get("ECS_SECURITY_GROUPS", "sg-0df80dcbbc597eabb").split(",")
AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pipeline on ECS Fargate.")
    parser.add_argument("pipeline", help="Pipeline name (must match a key in pipelines.yaml)")
    parser.add_argument(
        "--stage",
        choices=["all", "bronze", "silver", "gold"],
        default="all",
        help="Which stage to run (default: all)",
    )
    # os.environ.get fallback is for local users who prefer setting env vars over typing long flags
    # CLI arg takes precedence, env var is the fallback, dev-latest is last resort
    parser.add_argument(
        "--image-tag",
        default=os.environ.get("IMAGE_TAG", "dev-latest"),
        help="ECR image tag to run (default: IMAGE_TAG env var or dev-latest)",
    )
    parser.add_argument(
        "--capacity-provider",
        choices=["FARGATE", "FARGATE_SPOT"],
        default=os.environ.get("ECS_CAPACITY_PROVIDER", "FARGATE"),
        help="Which ECS capacity provider to use (default: ECS_CAPACITY_PROVIDER or FARGATE)",
    )
    return parser.parse_args()


def resolve_task_definition(image_tag: str) -> str:
    if image_tag == "dev-latest":
        return TASK_FAMILY  # Use the default task family which points to dev-latest

    ecsclient = boto3.client("ecs", region_name=AWS_REGION)

    # Get the current task definition so we can copy its settings
    # and derive the ECR registry URL without hardcoding it
    response = ecsclient.describe_task_definition(taskDefinition=TASK_FAMILY)
    current = response["taskDefinition"]

    updated_containers = []
    for container in current["containerDefinitions"]:
        if container["name"] == "app":
            base_uri = container["image"].rsplit(":", 1)[0]
            container = {**container, "image": f"{base_uri}:{image_tag}"}
        updated_containers.append(container)

    new_revision = ecsclient.register_task_definition(
        family=current["family"],
        taskRoleArn=current.get("taskRoleArn"),
        executionRoleArn=current.get("executionRoleArn"),
        networkMode=current.get("networkMode"),
        containerDefinitions=updated_containers,
        requiresCompatibilities=current.get("requiresCompatibilities"),
        cpu=current.get("cpu"),
        memory=current.get("memory"),
    )

    task_def_arn = new_revision["taskDefinition"]["taskDefinitionArn"]
    print(f"Registered new task definition revision: {task_def_arn}")
    return task_def_arn


def run_task(pipeline: str, stage: str, capacity_provider: str, task_definition: str) -> None:
    params: dict[str, Any] = {
        "cluster": CLUSTER,
        "taskDefinition": task_definition,
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
    print(f"Task started: {task_id}")
    print(f"Capacity:     {capacity_provider}")
    print(
        f"Watch it:     aws ecs describe-tasks --cluster {CLUSTER} --tasks {task_id}"  # noqa: E501
    )
    print(f"Logs:         aws logs tail /ecs/{CLUSTER} --follow")


if __name__ == "__main__":
    args = parse_args()
    task_definition = resolve_task_definition(args.image_tag)
    run_task(args.pipeline, args.stage, args.capacity_provider, task_definition)
