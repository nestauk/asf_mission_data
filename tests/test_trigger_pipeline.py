import argparse

import pytest
import pytest_mock

from scripts import trigger_pipeline


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
)

ECR_BASE = "123.dkr.ecr.eu-west-2.amazonaws.com/asf-mission-data"
DIGEST_A = "sha256:" + "a" * 64
DIGEST_B = "sha256:" + "b" * 64


def fake_task_definition(image: str, revision: int = 7) -> dict:
    return {
        "taskDefinition": {
            "taskDefinitionArn": f"arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:{revision}",
            "family": "asf-mission-data-dev",
            "taskRoleArn": "arn:aws:iam::123:role/TaskRole",
            "executionRoleArn": "arn:aws:iam::123:role/ExecRole",
            "networkMode": "awsvpc",
            "containerDefinitions": [{"name": "app", "image": image}],
            "requiresCompatibilities": ["FARGATE"],
            "cpu": "256",
            "memory": "512",
        }
    }


def fake_ecr_client(mocker: pytest_mock.MockerFixture, digest: str):
    ecr_client = mocker.Mock()
    ecr_client.batch_get_image.return_value = {"images": [{"imageId": {"imageDigest": digest}}]}
    return ecr_client


def patch_boto3_clients(mocker: pytest_mock.MockerFixture, ecs_client, ecr_client=None) -> None:
    def boto3_client(service_name: str, region_name: str):
        if service_name == "ecs":
            return ecs_client
        if service_name == "ecr" and ecr_client is not None:
            return ecr_client
        raise AssertionError(f"Unexpected service: {service_name}")

    mocker.patch("scripts.trigger_pipeline.boto3.client", side_effect=boto3_client)


def test_run_task_uses_explicit_capacity_provider(
    mocker: pytest_mock.MockerFixture,
) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123456789012:task/asf-mission-data-dev/task-123"}],
        "failures": [],
    }
    boto_client = mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    trigger_pipeline.run_task("example", "all", "FARGATE", "asf-mission-data-dev", FAKE_INFRA)

    boto_client.assert_called_once_with("ecs", region_name=trigger_pipeline.AWS_REGION)
    ecs_client.run_task.assert_called_once()
    params = ecs_client.run_task.call_args.kwargs
    assert params["capacityProviderStrategy"] == [{"capacityProvider": "FARGATE", "weight": 1}]
    assert params["overrides"]["containerOverrides"][0]["command"] == [
        "example",
        "--stage",
        "all",
    ]


def test_resolve_task_definition_registers_digest_when_family_pinned_by_tag(mocker):
    """
    A tag-pinned revision (the state cdk deploy leaves behind) can't be
    verified against the requested tag, so it is replaced by a revision
    pinned to the tag's resolved digest.
    """
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = fake_task_definition(f"{ECR_BASE}:dev-latest")
    ecs_client.register_task_definition.return_value = {
        "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8"}
    }
    patch_boto3_clients(mocker, ecs_client, fake_ecr_client(mocker, DIGEST_A))

    result = trigger_pipeline.resolve_task_definition("dev-latest", FAKE_INFRA)

    registered_containers = ecs_client.register_task_definition.call_args.kwargs["containerDefinitions"]
    assert registered_containers[0]["image"] == f"{ECR_BASE}@{DIGEST_A}"
    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8",
        app_image=f"{ECR_BASE}@{DIGEST_A}",
    )
    ecs_client.describe_task_definition.assert_called_once_with(taskDefinition=FAKE_INFRA.task_family)


def test_resolve_task_definition_registers_digest_for_feature_tag(mocker):
    """
    When a feature branch tag is requested, it resolves that tag's digest,
    registers a new revision pinned to it, and returns the new ARN
    """
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = fake_task_definition(f"{ECR_BASE}:dev-latest")
    ecs_client.register_task_definition.return_value = {
        "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8"}
    }
    ecr_client = fake_ecr_client(mocker, DIGEST_B)
    patch_boto3_clients(mocker, ecs_client, ecr_client)

    result = trigger_pipeline.resolve_task_definition("56-feature-new-pipeline-latest", FAKE_INFRA)

    # the digest of the requested tag was looked up in the right repository
    ecr_client.batch_get_image.assert_called_once_with(
        repositoryName="asf-mission-data",
        imageIds=[{"imageTag": "56-feature-new-pipeline-latest"}],
    )
    # the registered image is pinned by digest, immune to tag mutation
    registered_containers = ecs_client.register_task_definition.call_args.kwargs["containerDefinitions"]
    assert registered_containers[0]["image"] == f"{ECR_BASE}@{DIGEST_B}"
    # returned the new ARN
    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8",
        app_image=f"{ECR_BASE}@{DIGEST_B}",
    )


def test_resolve_task_definition_repoints_family_pinned_to_stale_tag(mocker):
    """
    Regression test for docs/bug_reports/2026-10-06-stale-image-on-default-tag-pipeline-runs.md:
    when the active revision is pinned to an old branch tag, requesting the
    default tag must register a new revision pointing at that tag's digest,
    not silently reuse the stale image.
    """
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = fake_task_definition(f"{ECR_BASE}:chore-test-dev-rebuild-latest")
    ecs_client.register_task_definition.return_value = {
        "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8"}
    }
    patch_boto3_clients(mocker, ecs_client, fake_ecr_client(mocker, DIGEST_A))

    result = trigger_pipeline.resolve_task_definition("dev-latest", FAKE_INFRA)

    registered_containers = ecs_client.register_task_definition.call_args.kwargs["containerDefinitions"]
    assert registered_containers[0]["image"] == f"{ECR_BASE}@{DIGEST_A}"
    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8",
        app_image=f"{ECR_BASE}@{DIGEST_A}",
    )


def test_resolve_task_definition_reuses_revision_pinned_to_matching_digest(mocker):
    """
    Re-running a tag whose digest the active revision already pins must reuse
    that revision instead of registering a redundant copy.
    """
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = fake_task_definition(f"{ECR_BASE}@{DIGEST_A}")
    patch_boto3_clients(mocker, ecs_client, fake_ecr_client(mocker, DIGEST_A))

    result = trigger_pipeline.resolve_task_definition("dev-latest", FAKE_INFRA)

    ecs_client.register_task_definition.assert_not_called()
    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:7",
        app_image=f"{ECR_BASE}@{DIGEST_A}",
    )


def test_resolve_task_definition_repins_when_tag_points_at_new_digest(mocker):
    """
    The scenario a tag-string comparison can't catch: the active revision is
    digest-pinned from an earlier run of the same tag, but the tag has since
    been re-pointed at a newer image. A new revision must be registered.
    """
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = fake_task_definition(f"{ECR_BASE}@{DIGEST_A}")
    ecs_client.register_task_definition.return_value = {
        "taskDefinition": {"taskDefinitionArn": "arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8"}
    }
    patch_boto3_clients(mocker, ecs_client, fake_ecr_client(mocker, DIGEST_B))

    result = trigger_pipeline.resolve_task_definition("dev-latest", FAKE_INFRA)

    registered_containers = ecs_client.register_task_definition.call_args.kwargs["containerDefinitions"]
    assert registered_containers[0]["image"] == f"{ECR_BASE}@{DIGEST_B}"
    assert result == trigger_pipeline.ResolvedTaskDefinition(
        task_definition="arn:aws:ecs:eu-west-2:123:task-definition/asf-mission-data-dev:8",
        app_image=f"{ECR_BASE}@{DIGEST_B}",
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
    monkeypatch.setattr("sys.argv", ["trigger_pipeline.py", "example", "--image-tag", "56-feature-new-pipeline-latest"])

    args = trigger_pipeline.parse_args()

    assert args.image_tag == "56-feature-new-pipeline-latest"


def test_get_app_container_image_raises_when_app_container_missing() -> None:
    with pytest.raises(ValueError, match="does not contain an 'app' container"):
        trigger_pipeline.get_app_container_image([{"name": "sidecar", "image": "123.dkr.ecr.eu-west-2.amazonaws.com/sidecar:latest"}])


def test_get_ecr_repository_name_returns_repository_segment() -> None:
    assert trigger_pipeline.get_ecr_repository_name(f"{ECR_BASE}:dev-latest") == "asf-mission-data"


def test_get_ecr_repository_name_handles_digest_pinned_uri() -> None:
    assert trigger_pipeline.get_ecr_repository_name(f"{ECR_BASE}@{DIGEST_A}") == "asf-mission-data"


def test_resolve_task_definition_raises_for_missing_image_tag(mocker) -> None:
    ecs_client = mocker.Mock()
    ecs_client.describe_task_definition.return_value = fake_task_definition(f"{ECR_BASE}:dev-latest")
    ecr_client = mocker.Mock()
    ecr_client.batch_get_image.return_value = {
        "images": [],
        "failures": [{"failureCode": "ImageNotFound", "failureReason": "Requested image not found"}],
    }
    patch_boto3_clients(mocker, ecs_client, ecr_client)

    with pytest.raises(ValueError, match="Could not find the image tag '44-feat-image'"):
        trigger_pipeline.resolve_task_definition("44-feat-image", FAKE_INFRA)

    ecs_client.register_task_definition.assert_not_called()
