"""Run an ASF pipeline on ECS Fargate.

Usage:
    python scripts/trigger_pipeline.py example --stage all
    python scripts/trigger_pipeline.py <pipeline_name> --stage bronze
    python scripts/trigger_pipeline.py <pipeline_name> --environment prod
    python scripts/trigger_pipeline.py <pipeline_name> --capacity-provider FARGATE_SPOT
"""

import argparse
import json
import os
import sys
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any

import boto3
from botocore.exceptions import BotoCoreError, ClientError

AWS_REGION = os.environ.get("AWS_REGION", "eu-west-2")


@dataclass(frozen=True)
class InfraConfig:
    cluster: str
    task_family: str
    subnet_ids: list[str]
    security_group_ids: list[str]
    data_bucket: str


@dataclass(frozen=True)
class ResolvedTaskDefinition:
    task_definition: str
    app_image: str


@dataclass(frozen=True)
class RunRecord:
    run_id: str
    pipeline: str
    stage: str
    environment: str
    status: str
    status_reason: str
    retryable: bool
    action_required: bool
    triggered_by: str

    # These fields may be unavailable depending on how or why the task stopped.
    failure_category: str | None = None
    exit_code: int | None = None
    stop_code: str | None = None
    stopped_reason: str | None = None
    started_at: str | None = None
    stopped_at: str | None = None
    duration_seconds: float | None = None
    ecs_task_id: str | None = None
    ecs_task_arn: str | None = None

    # These fields are present only when the run originated from a context
    # that supplied the corresponding deployment metadata
    github_run_id: str | None = None
    git_sha: str | None = None
    image_tag: str | None = None
    task_definition_arn: str | None = None
    app_image: str | None = None

    schema_version: int = 1
    recorded_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON dictionary representation of the record"""
        return asdict(self)


def write_run_record(bucket: str, record: RunRecord) -> None:
    """Write a run record to S3 whether the run works or it fails"""
    s3 = boto3.client("s3", region_name=AWS_REGION)
    s3.put_object(
        Bucket=bucket,
        Key=f"_meta/runs/{record.run_id}.json",
        Body=json.dumps(record.to_dict(), indent=2),
        ContentType="application/json",
    )


def github_actions_enabled() -> bool:
    return os.environ.get("GITHUB_ACTIONS") == "true"


def escape_github_actions_value(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def emit_github_actions_annotation(level: str, message: str) -> None:
    if not github_actions_enabled():
        return

    print(f"::{level}::{escape_github_actions_value(message)}")


def get_infra_config(environment: str) -> InfraConfig:
    """Look up infrastructure values from CloudFormation stack outputs."""
    cfn = boto3.client("cloudformation", region_name=AWS_REGION)
    stack_name = f"asf-core-{environment}"
    response = cfn.describe_stacks(StackName=stack_name)
    outputs = {o["OutputKey"]: o["OutputValue"] for o in response["Stacks"][0]["Outputs"]}
    return InfraConfig(
        cluster=outputs["ClusterArn"],
        task_family=f"asf-mission-data-{environment}",
        subnet_ids=outputs["SubnetIds"].split(","),
        security_group_ids=[outputs["SecurityGroupId"]],
        data_bucket=outputs["DataBucketName"],
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a pipeline on ECS Fargate.")
    parser.add_argument("pipeline", help="Pipeline name (must match a key in pipelines.yaml)")
    parser.add_argument(
        "--environment",
        choices=["dev", "prod"],
        default=os.environ.get("ASF_ENVIRONMENT", "dev"),
        help="Target environment (default: ASF_ENVIRONMENT env var or dev)",
    )
    parser.add_argument(
        "--stage",
        choices=["all", "bronze", "silver", "gold"],
        default="all",
        help="Which stage to run (default: all)",
    )
    parser.add_argument(
        "--image-tag",
        default=None,
        help="ECR image tag to run (default: {environment}-latest)",
    )
    parser.add_argument(
        "--capacity-provider",
        choices=["FARGATE", "FARGATE_SPOT"],
        default=os.environ.get("ECS_CAPACITY_PROVIDER", "FARGATE"),
        help="Which ECS capacity provider to use (default: ECS_CAPACITY_PROVIDER or FARGATE)",
    )
    args = parser.parse_args()
    if args.image_tag is None:
        args.image_tag = f"{args.environment}-latest"
    return args


def get_app_container_image(
    container_definitions: list[dict[str, Any]],
) -> str:
    for container in container_definitions:
        if container["name"] == "app":
            return container["image"]

    raise ValueError("Task definition does not contain an 'app' container")


def get_ecr_repository_name(image_uri: str) -> str:
    image_without_tag = image_uri.rsplit(":", 1)[0]
    return image_without_tag.rsplit("/", 1)[-1]


def ensure_image_tag_exists(image_uri: str, image_tag: str) -> None:
    ecr_client = boto3.client("ecr", region_name=AWS_REGION)
    repository_name = get_ecr_repository_name(image_uri)
    response = ecr_client.batch_get_image(
        repositoryName=repository_name,
        imageIds=[{"imageTag": image_tag}],
    )

    if response.get("images"):
        return

    failures = response.get("failures", [])
    if failures:
        failure_codes = ", ".join(sorted({failure["failureCode"] for failure in failures}))
        raise ValueError(f"Could not find the image tag '{image_tag}' in ECR repository '{repository_name}' (failure: {failure_codes})")

    raise ValueError(f"Could not find the image tag '{image_tag}' in ECR repository '{repository_name}'")


def resolve_task_definition(image_tag: str, infra: InfraConfig, environment: str) -> ResolvedTaskDefinition:
    ecsclient = boto3.client("ecs", region_name=AWS_REGION)
    response = ecsclient.describe_task_definition(taskDefinition=infra.task_family)
    current = response["taskDefinition"]

    if image_tag == f"{environment}-latest":
        return ResolvedTaskDefinition(
            task_definition=current["taskDefinitionArn"],
            app_image=get_app_container_image(current["containerDefinitions"]),
        )

    # Get the current task definition so we can copy its settings
    # and derive the ECR registry URL without hardcoding it

    current_app_image = get_app_container_image(current["containerDefinitions"])
    ensure_image_tag_exists(current_app_image, image_tag)

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
    emit_github_actions_annotation(
        "notice",
        f"Registered new task definition revision: {task_def_arn}",
    )
    return ResolvedTaskDefinition(
        task_definition=task_def_arn,
        app_image=get_app_container_image(updated_containers),
    )


def build_run_metadata(
    *,
    run_id: str,
    pipeline: str,
    stage: str,
    environment: str,
    triggered_by: str,
    github_run_id: str | None = None,
    git_sha: str | None = None,
    image_tag: str | None = None,
) -> dict[str, str]:
    """Build the metadata describing one pipeline run.

    This dictionary is the single source of truth for metadata that needs to
    be sent to both ECS task tags and the application container environment.

    Optional values are omitted so they aren't sent to AWS as null values.
    """
    values = {
        "run_id": run_id,
        "pipeline": pipeline,
        "stage": stage,
        "environment": environment,
        "triggered_by": triggered_by,
        "github_run_id": github_run_id,
        "git_sha": git_sha,
        "image_tag": image_tag,
    }

    return {key: value for key, value in values.items() if value is not None}


def build_task_tags(metadata: dict[str, str]) -> list[dict[str, str]]:
    """Convert the metadata dict into the format expected for ECS task tags"""
    return [{"key": key, "value": value} for key, value in metadata.items()]


def build_environment_overrides(
    metadata: dict[str, str],
) -> list[dict[str, str]]:
    """Convert run metadata into ECS container environment overrides.

    The application receives the same run metadata as the ECS task, but with
    explicit ASF-prefixed environment variable names to avoid collisions with
    unrelated environment variables.
    """
    env_names = {
        "run_id": "ASF_RUN_ID",
        "pipeline": "ASF_PIPELINE",
        "stage": "ASF_STAGE",
        "environment": "ASF_ENVIRONMENT",
        "triggered_by": "ASF_TRIGGERED_BY",
        "github_run_id": "ASF_GITHUB_RUN_ID",
        "git_sha": "ASF_GIT_SHA",
        "image_tag": "ASF_IMAGE_TAG",
    }

    return [
        {
            "name": env_names[key],
            "value": value,
        }
        for key, value in metadata.items()
    ]


def run_task(
    metadata: dict[str, str],
    capacity_provider: str,
    task_definition: str,
    infra: InfraConfig,
) -> str:
    """Launch one pipeline run as an ECS Fargate task.

    The supplied metadata is the canonical description of the pipeline run.
    This function is responsible for translating it into ECS task tags,
    container environment variables, and the command override used to launch
    the application.
    """
    tags = build_task_tags(metadata)
    environment_overrides = build_environment_overrides(metadata)

    # Pipeline and stage are part of the metadata, so the command
    # being executed can't drift from the metadata attached to the task
    pipeline = metadata["pipeline"]
    stage = metadata["stage"]

    params: dict[str, Any] = {
        "cluster": infra.cluster,
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
                "subnets": infra.subnet_ids,
                "securityGroups": infra.security_group_ids,
                "assignPublicIp": "ENABLED",
            }
        },
        "overrides": {
            "containerOverrides": [
                {
                    "name": "app",
                    "command": [pipeline, "--stage", stage],
                    "environment": environment_overrides,
                }
            ]
        },
        "tags": tags,
    }

    client = boto3.client("ecs", region_name=AWS_REGION)
    try:
        response = client.run_task(**params)
    except (BotoCoreError, ClientError) as exc:
        raise RuntimeError(f"Error calling ECS: {exc}") from exc

    failures = response.get("failures", [])
    if failures:
        reasons = "; ".join([f["reason"] for f in failures])
        raise RuntimeError(f"Task failed to launch: {reasons}")

    task_arn = response["tasks"][0]["taskArn"]
    task_id = task_arn.split("/")[-1]
    cluster_name = infra.cluster.split("/")[-1]
    print(f"Task started: {task_id}")
    print(f"Capacity:     {capacity_provider}")
    print(
        f"Watch it:     aws ecs describe-tasks --cluster {cluster_name} --tasks {task_id}"  # noqa: E501
    )
    print(f"Logs:         aws logs tail /ecs/{cluster_name} --follow")
    return task_arn


if __name__ == "__main__":
    args = parse_args()
    run_id = str(uuid.uuid4())
    try:
        infra = get_infra_config(args.environment)
    except (BotoCoreError, ClientError) as exc:
        emit_github_actions_annotation("error", f"Error looking up infrastructure: {exc}")
        print(
            f"Error looking up infrastructure for '{args.environment}': {exc}",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        resolved = resolve_task_definition(args.image_tag, infra, args.environment)
    except (BotoCoreError, ClientError, ValueError) as exc:
        emit_github_actions_annotation("error", f"Error resolving task definition: {exc}")
        print(f"Error resolving task definition: {exc}", file=sys.stderr)
        sys.exit(1)

    emit_github_actions_annotation("notice", f"Task definition: {resolved.task_definition}")
    emit_github_actions_annotation("notice", f"Container image: {resolved.app_image}")
    print(f"Task definition: {resolved.task_definition}")
    print(f"Container image: {resolved.app_image}")

    # Github metadata is only available when running in a GitHub Actions workflow, so we default to "manual" for local runs.
    triggered_by = os.environ.get("GITHUB_ACTOR", "manual")
    print(f"Triggered by: {triggered_by}")
    github_run_id = os.environ.get("GITHUB_RUN_ID")
    if github_run_id:
        print(f"GitHub run ID: {github_run_id}")
    git_sha = os.environ.get("GITHUB_SHA")
    if git_sha:
        print(f"Git SHA: {git_sha}")
    print(f"Image tag: {args.image_tag}")
    # Build the canonical description of this pipeline run once, before handing
    # it to the AWS-specific launch code
    run_metadata = build_run_metadata(
        run_id=run_id,
        pipeline=args.pipeline,
        stage=args.stage,
        environment=args.environment,
        triggered_by=triggered_by,
        github_run_id=github_run_id,
        git_sha=git_sha,
        image_tag=args.image_tag,
    )

    try:
        task_arn = run_task(
            metadata=run_metadata,
            capacity_provider=args.capacity_provider,
            task_definition=resolved.task_definition,
            infra=infra,
        )
    except RuntimeError as exc:
        emit_github_actions_annotation("error", str(exc))
        print(str(exc), file=sys.stderr)
        record = RunRecord(
            run_id=run_id,
            pipeline=args.pipeline,
            stage=args.stage,
            environment=args.environment,
            status="infrastructure_failure",
            failure_category="launch_rejected",
            status_reason=str(exc),
            retryable=True,
            action_required=True,
            triggered_by=triggered_by,
            github_run_id=github_run_id,
            git_sha=git_sha,
            image_tag=args.image_tag,
            task_definition_arn=resolved.task_definition,
        )
        try:
            write_run_record(infra.data_bucket, record)
        except (BotoCoreError, ClientError) as s3_exc:
            print(
                f"Warning: could not write run record: {s3_exc}",
                file=sys.stderr,
            )
        sys.exit(1)

    print(f"RUN_ID={run_id}")
