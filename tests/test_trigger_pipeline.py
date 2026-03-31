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


def test_parse_args_accepts_wait_and_follow_logs(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "sys.argv",
        ["trigger_pipeline.py", "example", "--wait", "--follow-logs"],
    )

    args = trigger_pipeline.parse_args()

    assert args.wait is True
    assert args.follow_logs is True


def test_run_task_uses_explicit_capacity_provider(
    mocker: pytest_mock.MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123456789012:task/asf-mission-data-dev/task-123"}],
        "failures": [],
    }
    boto_client = mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    result = trigger_pipeline.run_task("example", "all", "FARGATE")

    assert result == 0
    boto_client.assert_called_once_with("ecs", region_name=trigger_pipeline.AWS_REGION)
    ecs_client.run_task.assert_called_once()
    params = ecs_client.run_task.call_args.kwargs
    assert params["capacityProviderStrategy"] == [{"capacityProvider": "FARGATE", "weight": 1}]
    assert params["overrides"]["containerOverrides"][0]["command"] == ["example", "--stage", "all"]
    assert f"Log stream:   {trigger_pipeline.LOG_STREAM_PREFIX}/{trigger_pipeline.CONTAINER_NAME}/task-123" in capsys.readouterr().out


def test_run_task_writes_github_outputs(
    tmp_path,
    monkeypatch: pytest.MonkeyPatch,
    mocker: pytest_mock.MockerFixture,
) -> None:
    output_path = tmp_path / "github_output.txt"
    summary_path = tmp_path / "github_summary.md"
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary_path))

    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123456789012:task/asf-mission-data-dev/task-456"}],
        "failures": [],
    }
    mocker.patch("scripts.trigger_pipeline.boto3.client", return_value=ecs_client)

    result = trigger_pipeline.run_task("example", "silver", "FARGATE")

    assert result == 0
    assert "task_id=task-456\n" in output_path.read_text(encoding="utf-8")
    assert "log_stream=pipeline/app/task-456\n" in output_path.read_text(encoding="utf-8")
    assert "### Pipeline task launched" in summary_path.read_text(encoding="utf-8")
    assert "CloudWatch log stream: `pipeline/app/task-456`" in summary_path.read_text(encoding="utf-8")


def test_run_task_waits_and_follows_logs(
    mocker: pytest_mock.MockerFixture,
    capsys: pytest.CaptureFixture[str],
) -> None:
    ecs_client = mocker.Mock()
    ecs_client.run_task.return_value = {
        "tasks": [{"taskArn": "arn:aws:ecs:eu-west-2:123456789012:task/asf-mission-data-dev/task-789"}],
        "failures": [],
    }
    ecs_client.describe_tasks.return_value = {
        "tasks": [{"lastStatus": "STOPPED", "containers": [{"name": "app", "exitCode": 0}]}],
        "failures": [],
    }

    logs_client = mocker.Mock()
    logs_client.get_log_events.return_value = {
        "events": [{"timestamp": 0, "message": "pipeline finished\n"}],
        "nextForwardToken": "token-1",
    }

    def boto_client(service_name: str, region_name: str) -> object:
        if service_name == "ecs":
            return ecs_client
        if service_name == "logs":
            return logs_client
        raise AssertionError(f"Unexpected service: {service_name}")

    mocker.patch("scripts.trigger_pipeline.boto3.client", side_effect=boto_client)

    result = trigger_pipeline.run_task("example", "gold", "FARGATE", wait=True, follow_logs=True)

    assert result == 0
    output = capsys.readouterr().out
    assert "Waiting for task to finish..." in output
    assert "pipeline finished" in output
    assert "Task status:  STOPPED" in output
