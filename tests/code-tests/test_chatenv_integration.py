import json
from pathlib import Path
import tomllib

from chatenv import EnvStore, TokenStore
from chatenv.token_refreshers import TokenRefreshResult

from chatboard.auth import api_token_enabled, api_token_from_chatenv, verify_api_token
from chatboard.config import ChatboardConfig, load_runtime_config, service_url_from_chatenv, workspace_root_from_chatenv
from chatboard.tokens import refresh_token


def test_pyproject_exposes_chatenv_config_and_token_refresh_entry_points():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))
    entry_points = pyproject["project"]["entry-points"]

    assert entry_points["chatenv.configs"]["chatboard"] == "chatboard.config"
    assert entry_points["chatenv.token_refreshers"]["Chatboard"] == "chatboard.tokens:refresh_token"


def test_chatenv_profile_separates_service_address_login_and_api_token(tmp_path, monkeypatch):
    home = tmp_path / ".chatarch"
    workspace = tmp_path / "workspace"
    store = EnvStore(home / "envs")
    store.save_active(
        ChatboardConfig,
        {
            "CHATBOARD_SERVICE_URL": "https://board.public.wzhecnu.cn/",
            "CHATBOARD_WORKSPACE_ROOT": str(workspace),
            "CHATBOARD_USERNAME": "operator",
            "CHATBOARD_PASSWORD": "login-password",
            "CHATBOARD_API_KEY": "api-token-value",
        },
    )
    monkeypatch.setenv("CHATARCH_HOME", str(home))
    monkeypatch.delenv("CHATBOARD_SERVICE_URL", raising=False)
    monkeypatch.delenv("CHATBOARD_WORKSPACE_ROOT", raising=False)
    monkeypatch.delenv("CHATBOARD_USERNAME", raising=False)
    monkeypatch.delenv("CHATBOARD_PASSWORD", raising=False)
    monkeypatch.delenv("CHATBOARD_API_KEY", raising=False)

    config = load_runtime_config()

    assert config["service_url"] == "https://board.public.wzhecnu.cn/"
    assert config["workspace_root"] == workspace.resolve()
    assert config["username"] == "operator"
    assert config["password"] == "login-password"
    assert config["api_key"] == "api-token-value"
    assert workspace_root_from_chatenv() == workspace.resolve()
    assert service_url_from_chatenv() == "https://board.public.wzhecnu.cn/"
    assert api_token_from_chatenv() == "api-token-value"
    assert api_token_enabled() is True
    assert verify_api_token("api-token-value") is True
    assert verify_api_token("wrong") is False


def test_process_env_overrides_chatenv_profile_for_runtime_auth(tmp_path, monkeypatch):
    home = tmp_path / ".chatarch"
    store = EnvStore(home / "envs")
    store.save_active(
        ChatboardConfig,
        {
            "CHATBOARD_PASSWORD": "profile-password",
            "CHATBOARD_API_KEY": "profile-token",
        },
    )
    monkeypatch.setenv("CHATARCH_HOME", str(home))
    monkeypatch.setenv("CHATBOARD_PASSWORD", "process-password")
    monkeypatch.setenv("CHATBOARD_API_KEY", "process-token")

    config = load_runtime_config()

    assert config["password"] == "process-password"
    assert config["api_key"] == "process-token"
    assert verify_api_token("process-token") is True
    assert verify_api_token("profile-token") is False


def test_chatboard_refresh_provider_writes_runtime_cookie_token_without_exposing_values(tmp_path, monkeypatch):
    home = tmp_path / ".chatarch"
    store = EnvStore(home / "envs")
    store.save_profile(
        ChatboardConfig,
        "ops",
        {
            "CHATBOARD_SERVICE_URL": "https://board.public.wzhecnu.cn/",
            "CHATBOARD_USERNAME": "operator",
            "CHATBOARD_PASSWORD": "login-password",
        },
    )
    monkeypatch.setenv("CHATARCH_HOME", str(home))

    class FakeResponse:
        status_code = 200
        headers = {"set-cookie": "chatboard_session=session-value; HttpOnly; Path=/"}

        def raise_for_status(self):
            return None

        def json(self):
            return {"ok": True}

    calls = []

    def fake_post(url, *, json, timeout):
        calls.append({"url": url, "json": json, "timeout": timeout})
        return FakeResponse()

    result = refresh_token(service="Chatboard", profile="ops", home=home, post=fake_post)

    assert isinstance(result, TokenRefreshResult)
    assert calls == [
        {
            "url": "https://board.public.wzhecnu.cn/api/login",
            "json": {"username": "operator", "password": "login-password"},
            "timeout": 15,
        }
    ]
    assert result.token_type == "web_session"
    assert result.values == {"cookie": "chatboard_session=session-value"}
    assert result.summary == {
        "service_url": "https://board.public.wzhecnu.cn/",
        "username": "operator",
        "cookie_name": "chatboard_session",
    }
    assert "login-password" not in json.dumps(dict(result.summary or {}))


def test_chatboard_api_key_can_be_imported_as_runtime_token_metadata(tmp_path):
    home = tmp_path / ".chatarch"
    status = TokenStore(home=home).write(
        "Chatboard",
        "automation",
        values={"api_key": "api-token-value"},
        token_type="api_key",
        summary={"service_url": "https://board.public.wzhecnu.cn/", "scope": "board-api"},
        source="import",
    )

    assert status["token_present"] is True
    assert status["summary"] == {"service_url": "https://board.public.wzhecnu.cn/", "scope": "board-api"}
    assert "api-token-value" not in json.dumps(status)
    assert TokenStore(home=home).read("Chatboard", "automation")["values"] == {"api_key": "api-token-value"}
