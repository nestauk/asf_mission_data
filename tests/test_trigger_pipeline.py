import argparse

import pytest
import pytest_mock

from scripts import trigger_pipeline


def test_parse_args_defaults_to_standard_fargate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ECS_CAPACITY_PROVIDER", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["trigger_pipeline.py", "example", "--stage", "silver"],
    )

    args = trigger_pipeline.parse_args()

    assert isinstance(args, argparse.Namespace)
    assert args.pipeline == "example"
    assert args.stage == "silver"
    assert args.capacity_provider == "FARGATE"
    assert args.image_tag == "dev-latest"


def test_run_task_uses_explicit_capacity_provider(
    mocker: pytest_mock.MockerFixture,
) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123456789012:task/asf-mission-data-dev/task-123"}],
        "failures": [],
    }
    boto_client = mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    trigger_pipeline.run_task("example", "all", "FARGATE", "asf-mission-data-dev")

    boto_client.assert_called_once_with("ecs", region_name=trigger_pipeline.AWS_REGION)
    ecs_client.run_task.assert_called_once()
    params = ecs_client.run_task.call_args.kwargs
    assert params["capacityProviderStrategy"] == [{"capacityProvider": "FARGATE", "weight": 1}]
    assert params["overrides"]["containerOverrides"][0]["command"] == [
        "example",
        "--stage",
        "all",
    ]


def test_resolve_task_definition_returns_task_family_for_dev_latest(mocker):
    """
    When tag is dev-latest, no API calls are made and TASK_FAMILY is returned
    """
    boto_client = mocker.patch("scripts.trigger_pipeline.boto3.client")

    result = trigger_pipeline.resolve_task_definition("dev-latest")

    assert result == trigger_pipeline.TASK_FAMILY
    boto_client.assert_not_called()


def test_resolve_task_definition_registers_new_revision_for_feature_tag(
    mocker,
):
    """
    When tag is a feature branch tag, it describes the current task def,
    swaps the image tag, registers a new revision, and returns the new ARN
    """
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = {
        "taskDefinition": {
            "family": "asf-mission-data-dev",
            "taskRoleArn": "arn:aws:iam::123:role/TaskRole",
            "executionRoleArn": "arn:aws:iam::123:role/ExecRole",
            "networkMode": "awsvpc",
            "containerDefinitions": [
                {
                    "name": "app",
                    "image": "123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:dev-latest",
                }
            ],
            "requiresCompatibilities": ["FARGATE"],
            "cpu": "256",
            "memory": "512",
        }
    }
    ecs_client.register_task_definition.return_value = {
        "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:7"}
    }
    mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    result = trigger_pipeline.resolve_task_definition("56-feature-new-pipeline-latest")

    # correct image was registered
    registered_containers = ecs_client.register_task_definition.call_args.kwargs["containerDefinitions"]
    assert registered_containers[0]["image"] == "123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:56-feature-new-pipeline-latest"
    # returned the new ARN
    assert result == "arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:7"


def test_parse_args_reads_image_tag_from_env(monkeypatch):
    """
    When IMAGE_TAG env var is set, parse_args picks it up as the default
    """
    monkeypatch.setenv("IMAGE_TAG", "56-feature-new-pipeline-latest")
    monkeypatch.setattr("sys.argv", ["trigger_pipeline.py", "example"])

    args = trigger_pipeline.parse_args()

    assert args.image_tag == "56-feature-new-pipeline-latest"
