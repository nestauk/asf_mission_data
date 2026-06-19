from asf_mission_data.storage import get_data_root


def test_default_data_mode_is_local(monkeypatch):
    monkeypatch.delenv("DATA_MODE", raising=False)
    monkeypatch.delenv("DATA_ROOT", raising=False)

    assert get_data_root() == "/tmp/asf-pipeline-dev"
