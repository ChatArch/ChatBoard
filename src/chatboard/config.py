"""Typed environment configuration for ChatBoard."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from typing import Any

from chatenv import BaseEnvConfig, EnvField, get_paths


DEFAULT_WORKSPACE_ROOT = Path.home() / "Playground"
DEFAULT_SERVICE_URL = "http://127.0.0.1:8000/"
CHATBOARD_STATE_DIR_NAME = "chatboard"


class ChatboardConfig(BaseEnvConfig):
    """ChatBoard ChatEnv configuration."""

    _title = "ChatBoard Configuration"
    _aliases = ["chatboard", "chatbd"]
    _storage_dir = "Chatboard"

    @classmethod
    def test(cls) -> None:
        """Validate schema registration without external side effects."""

        print(f"Testing {cls._title}...")
        print("Schema loaded; no network test is required.")

    CHATBOARD_SERVICE_URL = EnvField(
        "CHATBOARD_SERVICE_URL",
        default=DEFAULT_SERVICE_URL,
        desc="ChatBoard service base URL.",
    )

    CHATBOARD_HOME = EnvField(
        "CHATBOARD_HOME",
        desc="ChatArch-owned ChatBoard state root. Defaults to $CHATARCH_HOME/chatboard or ~/.chatarch/chatboard.",
    )

    CHATBOARD_DEFAULT_BACKEND_NAME = EnvField(
        "CHATBOARD_DEFAULT_BACKEND_NAME",
        default="default",
        desc="Default backend profile name shown in the Web UI.",
    )

    CHATBOARD_DEFAULT_BACKEND_URL = EnvField(
        "CHATBOARD_DEFAULT_BACKEND_URL",
        desc="Default backend base URL for the Web UI backend switcher.",
    )

    CHATBOARD_DEFAULT_BACKEND_TOKEN = EnvField(
        "CHATBOARD_DEFAULT_BACKEND_TOKEN",
        desc="Default backend API token used by the server-side backend proxy.",
        is_sensitive=True,
    )

    CHATBOARD_BACKENDS_FILE = EnvField(
        "CHATBOARD_BACKENDS_FILE",
        desc="Path to the server-side backend profile store JSON file.",
    )

    CHATBOARD_BACKENDS_JSON = EnvField(
        "CHATBOARD_BACKENDS_JSON",
        desc="Inline server-side backend profile store JSON.",
        is_sensitive=True,
    )

    CHATBOARD_WORKSPACE_ROOT = EnvField(
        "CHATBOARD_WORKSPACE_ROOT",
        default=str(DEFAULT_WORKSPACE_ROOT),
        desc="Default ChatArch workspace root.",
    )

    CHATBOARD_USERNAME = EnvField(
        "CHATBOARD_USERNAME",
        desc="Optional login account name.",
    )

    CHATBOARD_PASSWORD = EnvField(
        "CHATBOARD_PASSWORD",
        desc="Optional Web/API login password.",
        is_sensitive=True,
    )

    CHATBOARD_API_KEY = EnvField(
        "CHATBOARD_API_KEY",
        desc="Bearer/API-key token for non-browser automation.",
        is_sensitive=True,
    )

    CHATBOARD_AUTH_SECRET = EnvField(
        "CHATBOARD_AUTH_SECRET",
        desc="Session cookie signing secret. Defaults to the login password.",
        is_sensitive=True,
    )

    CHATBOARD_SESSION_TTL_SECONDS = EnvField(
        "CHATBOARD_SESSION_TTL_SECONDS",
        default="43200",
        desc="Session cookie lifetime in seconds. Minimum effective runtime is 60 seconds.",
    )

    CHATBOARD_COOKIE_SECURE = EnvField(
        "CHATBOARD_COOKIE_SECURE",
        desc="Set to true/1/yes/on when ChatBoard is served through HTTPS.",
    )


def _field_value(field: EnvField) -> str:
    value = os.environ.get(field.env_key)
    if value is None:
        value = field.value
    return "" if value is None else str(value).strip()


@dataclass(frozen=True)
class ChatboardPaths:
    """Resolved ChatArch-owned local paths for ChatBoard runtime state."""

    chatarch_home: Path
    chatenv_provider_dir: Path
    chatboard_home: Path
    backend_profiles_file: Path

    def safe_summary(self) -> dict[str, str]:
        """Return paths only; no secret values are included."""

        return {
            "chatarch_home": str(self.chatarch_home),
            "chatenv_provider_dir": str(self.chatenv_provider_dir),
            "chatboard_home": str(self.chatboard_home),
            "backend_profiles_file": str(self.backend_profiles_file),
        }


def default_chatboard_home() -> Path:
    """Return ChatBoard's default ChatArch-owned state root."""

    return get_paths().home_dir / CHATBOARD_STATE_DIR_NAME


def state_paths(*, chatboard_home: str | Path | None = None, backends_file: str | Path | None = None) -> ChatboardPaths:
    """Resolve ChatBoard runtime paths under ChatArch home by default."""

    paths = get_paths()
    home = Path(chatboard_home).expanduser() if chatboard_home else default_chatboard_home()
    registry = Path(backends_file).expanduser() if backends_file else home / "backends.json"
    return ChatboardPaths(
        chatarch_home=paths.home_dir,
        chatenv_provider_dir=paths.envs_dir / str(ChatboardConfig._storage_dir),
        chatboard_home=home,
        backend_profiles_file=registry,
    )


def load_runtime_config() -> dict[str, Any]:
    """Load ChatBoard runtime config from ChatEnv with process-env overrides."""

    BaseEnvConfig.load_all(get_paths().envs_dir)
    workspace = _field_value(ChatboardConfig.CHATBOARD_WORKSPACE_ROOT) or str(DEFAULT_WORKSPACE_ROOT)
    service_url = _field_value(ChatboardConfig.CHATBOARD_SERVICE_URL) or DEFAULT_SERVICE_URL
    resolved_paths = state_paths(
        chatboard_home=_field_value(ChatboardConfig.CHATBOARD_HOME) or None,
        backends_file=_field_value(ChatboardConfig.CHATBOARD_BACKENDS_FILE) or None,
    )
    default_backend_url = _field_value(ChatboardConfig.CHATBOARD_DEFAULT_BACKEND_URL) or service_url
    return {
        "service_url": service_url,
        "chatboard_home": resolved_paths.chatboard_home,
        "default_backend_name": _field_value(ChatboardConfig.CHATBOARD_DEFAULT_BACKEND_NAME) or "default",
        "default_backend_url": default_backend_url,
        "default_backend_token": _field_value(ChatboardConfig.CHATBOARD_DEFAULT_BACKEND_TOKEN) or None,
        "backends_file": str(resolved_paths.backend_profiles_file),
        "backends_json": _field_value(ChatboardConfig.CHATBOARD_BACKENDS_JSON) or None,
        "workspace_root": Path(workspace).expanduser().resolve(),
        "username": _field_value(ChatboardConfig.CHATBOARD_USERNAME) or None,
        "password": _field_value(ChatboardConfig.CHATBOARD_PASSWORD) or None,
        "api_key": _field_value(ChatboardConfig.CHATBOARD_API_KEY) or None,
        "auth_secret": _field_value(ChatboardConfig.CHATBOARD_AUTH_SECRET) or None,
        "session_ttl_seconds": _field_value(ChatboardConfig.CHATBOARD_SESSION_TTL_SECONDS) or None,
        "cookie_secure": _field_value(ChatboardConfig.CHATBOARD_COOKIE_SECURE) or None,
    }


def workspace_root_from_chatenv() -> Path:
    """Load and resolve the active ChatBoard workspace from ChatEnv."""

    return load_runtime_config()["workspace_root"]


def service_url_from_chatenv() -> str:
    """Load the active ChatBoard service base URL from ChatEnv."""

    return str(load_runtime_config()["service_url"])


__all__ = [
    "CHATBOARD_STATE_DIR_NAME",
    "ChatboardConfig",
    "ChatboardPaths",
    "DEFAULT_SERVICE_URL",
    "DEFAULT_WORKSPACE_ROOT",
    "default_chatboard_home",
    "load_runtime_config",
    "service_url_from_chatenv",
    "state_paths",
    "workspace_root_from_chatenv",
]
