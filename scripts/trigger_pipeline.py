"""Run an ASF pipeline on ECS Fargate.

Usage:
    python scripts/trigger_pipeline.py example --stage all
    python scripts/trigger_pipeline.py energy_price_cap --stage bronze
"""

import argparse
import sys

import boto3
from botocore.exceptions import BotoCoreError, ClientError

CLUSTER = "asf-mission-data-dev"
TASK_FAMILY = "asf-mission-data-dev"
SUBNET_IDS = ["subnet-5cc6e511", "subnet-eb6fcb82", "subnet-1de6f466"]
SECURITY_GROUP_IDS = ["sg-0df80dcbbc597eabb"]
AWS_REGION = "eu-west-2"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pipeline on ECS Fargate.")
    parser.add_argument("pipeline", help="Pipeline name (must match a key in pipelines.yaml)")
    parser.add_argument(
        "--stage",
        choices=["all", "bronze", "silver", "gold"],
        default="all",
        help="Which stage to run (default: all)",
    )
    return parser.parse_args()


def run_task(pipeline, stage) -> None:
    params: dict = {
        "cluster": CLUSTER,
        "taskDefinition": TASK_FAMILY,
        "count": 1,
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
    print(
        f"Watch it:     aws ecs describe-tasks --cluster {CLUSTER} --tasks {task_id}"  # noqa: E501
    )
    print(f"Logs:         aws logs tail /ecs/{CLUSTER} --follow")


if __name__ == "__main__":
    args = parse_args()
    run_task(args.pipeline, args.stage)
