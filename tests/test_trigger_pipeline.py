import argparse

import pytest
import pytest_mock

from scripts import trigger_pipeline


def test_parse_args_defaults_to_standard_fargate(monkeypatch: pytest.MonkeyPatch) -> None:
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


def test_run_task_uses_explicit_capacity_provider(mocker: pytest_mock.MockerFixture) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123456789012:task/asf-mission-data-dev/task-123"}],
        "failures": [],
    }
    boto_client = mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    trigger_pipeline.run_task("example", "all", "FARGATE")

    boto_client.assert_called_once_with("ecs", region_name=trigger_pipeline.AWS_REGION)
    ecs_client.run_task.assert_called_once()
    params = ecs_client.run_task.call_args.kwargs
    assert params["capacityProviderStrategy"] == [{"capacityProvider": "FARGATE", "weight": 1}]
    assert params["overrides"]["containerOverrides"][0]["command"] == ["example", "--stage", "all"]
