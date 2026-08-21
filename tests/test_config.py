from pathlib import Path

from chatboard.config import load_runtime_config, state_paths


CHATBOARD_KEYS = [
    "CHATBOARD_HOME",
    "CHATBOARD_BACKENDS_FILE",
    "CHATBOARD_BACKENDS_JSON",
    "CHATBOARD_REGISTRY_TOKEN",
    "CHATBOARD_DEFAULT_BACKEND_TOKEN",
    "CHATBOARD_USERNAME",
    "CHATBOARD_PASSWORD",
    "CHATBOARD_API_KEY",
]


def test_runtime_paths_default_to_chatarch_home(tmp_path, monkeypatch):
    for key in CHATBOARD_KEYS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))

    paths = state_paths()
    config = load_runtime_config()

    assert paths.chatarch_home == tmp_path / "chatarch-home"
    assert paths.chatenv_provider_dir == tmp_path / "chatarch-home/envs/Chatboard"
    assert paths.chatboard_home == tmp_path / "chatarch-home/chatboard"
    assert paths.backend_registry_file == tmp_path / "chatarch-home/chatboard/backends.json"
    assert config["chatboard_home"] == tmp_path / "chatarch-home/chatboard"
    assert config["backends_file"] == str(tmp_path / "chatarch-home/chatboard/backends.json")


def test_runtime_paths_allow_explicit_chatenv_overrides(tmp_path, monkeypatch):
    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / "chatarch-home"))
    monkeypatch.setenv("CHATBOARD_HOME", str(tmp_path / "custom-home"))
    monkeypatch.setenv("CHATBOARD_BACKENDS_FILE", str(tmp_path / "registry/backends.json"))

    config = load_runtime_config()

    assert config["chatboard_home"] == Path(tmp_path / "custom-home")
    assert config["backends_file"] == str(tmp_path / "registry/backends.json")
