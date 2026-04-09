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


def test_emit_github_actions_annotation_prints_notice_when_enabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    trigger_pipeline.emit_github_actions_annotation("notice", "Task definition: abc")

    captured = capsys.readouterr()
    assert captured.out == "::notice::Task definition: abc\n"


def test_emit_github_actions_annotation_escapes_special_characters(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.setenv("GITHUB_ACTIONS", "true")

    trigger_pipeline.emit_github_actions_annotation("error", "bad % value\nnext line")

    captured = capsys.readouterr()
    assert captured.out == "::error::bad %25 value%0Anext line\n"


def test_emit_github_actions_annotation_is_noop_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    monkeypatch.delenv("GITHUB_ACTIONS", raising=False)

    trigger_pipeline.emit_github_actions_annotation("notice", "Task definition: abc")

    captured = capsys.readouterr()
    assert captured.out == ""


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
    When tag is dev-latest, the active task definition and image are returned
    """
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = {
        "taskDefinition": {
            "taskDefinitionArn": "arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:6",
            "containerDefinitions": [
                {
                    "name": "app",
                    "image": "123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:dev-latest",
                }
            ],
        }
    }
    boto_client = mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    result = trigger_pipeline.resolve_task_definition("dev-latest")

    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:6",
        app_image="123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:dev-latest",
    )
    boto_client.assert_called_once_with("ecs", region_name=trigger_pipeline.AWS_REGION)
    ecs_client.describe_task_definition.assert_called_once_with(taskDefinition=trigger_pipeline.TASK_FAMILY)


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
    ecr_client = mocker.Mock()
    ecr_client.batch_get_image.return_value = {"images": [{"imageId": {"imageTag": "56-feature-new-pipeline-latest"}}]}

    def boto3_client(service_name: str, region_name: str):
        if service_name == "ecs":
            return ecs_client
        if service_name == "ecr":
            return ecr_client
        raise AssertionError(f"Unexpected service: {service_name}")

    mocker.patch("scripts.trigger_pipeline.boto3.client", side_effect=boto3_client)

    result = trigger_pipeline.resolve_task_definition("56-feature-new-pipeline-latest")

    # correct image was registered
    registered_containers = ecs_client.register_task_definition.call_args.kwargs["containerDefinitions"]
    assert registered_containers[0]["image"] == "123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:56-feature-new-pipeline-latest"
    ecr_client.batch_get_image.assert_called_once_with(
        repositoryName="asf-mission-data",
        imageIds=[{"imageTag": "56-feature-new-pipeline-latest"}],
    )
    # returned the new ARN
    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:7",
        app_image="123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:56-feature-new-pipeline-latest",
    )


def test_parse_args_reads_image_tag_from_env(monkeypatch):
    """
    When IMAGE_TAG env var is set, parse_args picks it up as the default
    """
    monkeypatch.setenv("IMAGE_TAG", "56-feature-new-pipeline-latest")
    monkeypatch.setattr("sys.argv", ["trigger_pipeline.py", "example"])

    args = trigger_pipeline.parse_args()

    assert args.image_tag == "56-feature-new-pipeline-latest"


def test_get_app_container_image_raises_when_app_container_missing() -> None:
    with pytest.raises(ValueError, match="does not contain an 'app' container"):
        trigger_pipeline.get_app_container_image([{"name": "sidecar", "image": "123.dkr.ecr.eu-west-2.amazonaws.com/sidecar:latest"}])


def test_get_ecr_repository_name_returns_repository_segment() -> None:
    assert trigger_pipeline.get_ecr_repository_name("123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:dev-latest") == "asf-mission-data"


def test_resolve_task_definition_raises_for_missing_image_tag(mocker) -> None:
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = {
        "taskDefinition": {
            "family": "asf-mission-data-dev",
            "containerDefinitions": [
                {
                    "name": "app",
                    "image": "123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:dev-latest",
                }
            ],
        }
    }
    ecr_client = mocker.Mock()
    ecr_client.batch_get_image.return_value = {
        "images": [],
        "failures": [{"failureCode": "ImageNotFound", "failureReason": "Requested image not found"}],
    }

    def boto3_client(service_name: str, region_name: str):
        if service_name == "ecs":
            return ecs_client
        if service_name == "ecr":
            return ecr_client
        raise AssertionError(f"Unexpected service: {service_name}")

    mocker.patch("scripts.trigger_pipeline.boto3.client", side_effect=boto3_client)

    with pytest.raises(ValueError, match="Image tag '44-feat-image' was not found"):
        trigger_pipeline.resolve_task_definition("44-feat-image")

    ecs_client.register_task_definition.assert_not_called()
