# import pytest

# from asf_mission_data.storage import _initialise_environment, get_data_path, get_heartbeat_path


# def test_initialise_environment_defaults_to_dev_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
#     monkeypatch.delenv("DATA_MODE", raising=False)
#     monkeypatch.delenv("DATA_ROOT", raising=False)

#     data_mode, data_root = _initialise_environment()

#     assert data_mode == "DEV"
#     assert data_root == "s3://asf-mission-data-dev"


# def test_initialise_environment_accepts_matching_dev_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
#     monkeypatch.setenv("DATA_MODE", "DEV")
#     monkeypatch.setenv("DATA_ROOT", "s3://asf-mission-data-dev")

#     data_mode, data_root = _initialise_environment()

#     assert data_mode == "DEV"
#     assert data_root == "s3://asf-mission-data-dev"


# def test_initialise_environment_requires_local_root(monkeypatch: pytest.MonkeyPatch) -> None:
#     monkeypatch.setenv("DATA_MODE", "LOCAL")
#     monkeypatch.delenv("DATA_ROOT", raising=False)

#     with pytest.raises(ValueError, match="LOCAL requires DATA_ROOT"):
#         _initialise_environment()


# def test_initialise_environment_rejects_cloud_root_for_local_mode(
#     monkeypatch: pytest.MonkeyPatch,
# ) -> None:
#     monkeypatch.setenv("DATA_MODE", "LOCAL")
#     monkeypatch.setenv("DATA_ROOT", "s3://asf-mission-data-dev")

#     with pytest.raises(ValueError, match="Local mode cannot point to cloud storage"):
#         _initialise_environment()


# def test_get_data_path_defaults_to_dev_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
#     monkeypatch.delenv("DATA_ROOT", raising=False)

#     assert get_data_path("data/example/file.csv") == "s3://asf-mission-data-dev/data/example/file.csv"


# def test_get_heartbeat_path_defaults_to_dev_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
#     monkeypatch.delenv("HEARTBEAT_ROOT", raising=False)
#     monkeypatch.delenv("DATA_ROOT", raising=False)

#     assert get_heartbeat_path("example") == "s3://asf-heartbeats-dev/heartbeats/example.json"
