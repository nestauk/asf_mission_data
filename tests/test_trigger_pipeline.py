import argparse

import pytest
import pytest_mock

from scripts import trigger_pipeline


@pytest.fixture
def run_id():
    run_id = "run-123"

    return run_id


@pytest.fixture
def run_task_metadata(run_id):
    metadata = trigger_pipeline.build_run_metadata(
        run_id=run_id,
        pipeline="energy_price_cap_levels_annex_9",
        stage="all",
        environment="dev",
        triggered_by="alex",
    )
    return metadata


def test_parse_args_defaults_to_standard_fargate(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("ECS_CAPACITY_PROVIDER", raising=False)
    monkeypatch.delenv("ASF_ENVIRONMENT", raising=False)
    monkeypatch.setattr(
        "sys.argv",
        ["trigger_pipeline.py", "example", "--stage", "silver"],
    )

    args = trigger_pipeline.parse_args()

    assert isinstance(args, argparse.Namespace)
    assert args.pipeline == "example"
    assert args.stage == "silver"
    assert args.capacity_provider == "FARGATE"
    assert args.environment == "dev"
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


FAKE_INFRA = trigger_pipeline.InfraConfig(
    cluster="arn:aws:ecs:eu-west-2:123456789012:cluster/asf-mission-data-dev",
    task_family="asf-mission-data-dev",
    subnet_ids=["subnet-abc", "subnet-def"],
    security_group_ids=["sg-0539fd44b1f27895b"],
    data_bucket="asf-mission-data-dev",
)


def test_run_task_uses_explicit_capacity_provider(
    mocker: pytest_mock.MockerFixture,
    run_task_metadata: dict[str, str],
) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123456789012:task/asf-mission-data-dev/task-123"}],
        "failures": [],
    }
    boto_client = mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    trigger_pipeline.run_task(
        metadata=run_task_metadata,
        capacity_provider="FARGATE",
        task_definition="asf-mission-data-dev",
        infra=FAKE_INFRA,
    )

    boto_client.assert_called_once_with("ecs", region_name=trigger_pipeline.AWS_REGION)
    ecs_client.run_task.assert_called_once()
    params = ecs_client.run_task.call_args.kwargs
    assert params["capacityProviderStrategy"] == [{"capacityProvider": "FARGATE", "weight": 1}]
    assert params["overrides"]["containerOverrides"][0]["command"] == [
        run_task_metadata["pipeline"],
        "--stage",
        run_task_metadata["stage"],
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

    result = trigger_pipeline.resolve_task_definition("dev-latest", FAKE_INFRA, "dev")

    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:6",
        app_image="123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data:dev-latest",
    )
    boto_client.assert_called_once_with("ecs", region_name=trigger_pipeline.AWS_REGION)
    ecs_client.describe_task_definition.assert_called_once_with(taskDefinition=FAKE_INFRA.task_family)


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

    result = trigger_pipeline.resolve_task_definition("56-feature-new-pipeline-latest", FAKE_INFRA, "dev")

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


def test_parse_args_image_tag_defaults_to_environment(monkeypatch):
    """
    When no --image-tag is given, it defaults to {environment}-latest
    """
    monkeypatch.setattr("sys.argv", ["trigger_pipeline.py", "example", "--environment", "prod"])

    args = trigger_pipeline.parse_args()

    assert args.image_tag == "prod-latest"


def test_parse_args_image_tag_override(monkeypatch):
    """
    When --image-tag is given explicitly, it overrides the default
    """
    monkeypatch.setattr(
        "sys.argv",
        [
            "trigger_pipeline.py",
            "example",
            "--image-tag",
            "56-feature-new-pipeline-latest",
        ],
    )

    args = trigger_pipeline.parse_args()

    assert args.image_tag == "56-feature-new-pipeline-latest"


def test_get_app_container_image_raises_when_app_container_missing() -> None:
    with pytest.raises(ValueError, match="does not contain an 'app' container"):
        trigger_pipeline.get_app_container_image(
            [
                {
                    "name": "sidecar",
                    "image": "123.dkr.ecr.eu-west-2.amazonaws.com/sidecar:latest",
                }
            ]
        )


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
        "failures": [
            {
                "failureCode": "ImageNotFound",
                "failureReason": "Requested image not found",
            }
        ],
    }

    def boto3_client(service_name: str, region_name: str):
        if service_name == "ecs":
            return ecs_client
        if service_name == "ecr":
            return ecr_client
        raise AssertionError(f"Unexpected service: {service_name}")

    mocker.patch("scripts.trigger_pipeline.boto3.client", side_effect=boto3_client)

    with pytest.raises(ValueError, match="Could not find the image tag '44-feat-image'"):
        trigger_pipeline.resolve_task_definition("44-feat-image", FAKE_INFRA, "dev")

    ecs_client.register_task_definition.assert_not_called()


def test_trigger_passes_same_run_id_to_tags_and_container(
    mocker: pytest_mock.MockerFixture,
    run_id: str,
    run_task_metadata: dict[str, str],
) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123:task/cluster/task-123"}],
        "failures": [],
    }
    mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    trigger_pipeline.run_task(
        metadata=run_task_metadata,
        capacity_provider="FARGATE",
        task_definition="asf-mission-data-dev",
        infra=FAKE_INFRA,
    )

    request = ecs_client.run_task.call_args.kwargs

    tags = {tag["key"]: tag["value"] for tag in request["tags"]}

    app_override = next(override for override in request["overrides"]["containerOverrides"] if override["name"] == "app")

    env = {item["name"]: item["value"] for item in app_override["environment"]}

    assert tags["run_id"] == run_id
    assert env["ASF_RUN_ID"] == run_id


def test_run_task_raises_when_ecs_cant_launch(
    mocker: pytest_mock.MockerFixture,
    run_task_metadata: dict[str, str],
) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [],
        "failures": [{"reason": "RESOURCE:MEMORY"}],
    }
    mocker.patch(
        "scripts.trigger_pipeline.boto3.client",
        return_value=ecs_client,
    )

    with pytest.raises(RuntimeError, match="RESOURCE:MEMORY"):
        trigger_pipeline.run_task(
            metadata=run_task_metadata,
            capacity_provider="FARGATE",
            task_definition="asf-mission-data-dev",
            infra=FAKE_INFRA,
        )
