"""Typed environment configuration for ChatBoard."""

from __future__ import annotations

from pathlib import Path
import os
from typing import Any

from chatenv import BaseEnvConfig, EnvField, get_paths


DEFAULT_WORKSPACE_ROOT = Path.home() / "Playground"
DEFAULT_SERVICE_URL = "http://127.0.0.1:8000/"


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


def _field_value(field: EnvField) -> str:
    value = os.environ.get(field.env_key)
    if value is None:
        value = field.value
    return "" if value is None else str(value).strip()


def load_runtime_config() -> dict[str, Any]:
    """Load ChatBoard runtime config from ChatEnv with process-env overrides."""

    BaseEnvConfig.load_all(get_paths().envs_dir)
    workspace = _field_value(ChatboardConfig.CHATBOARD_WORKSPACE_ROOT) or str(DEFAULT_WORKSPACE_ROOT)
    service_url = _field_value(ChatboardConfig.CHATBOARD_SERVICE_URL) or DEFAULT_SERVICE_URL
    return {
        "service_url": service_url,
        "workspace_root": Path(workspace).expanduser().resolve(),
        "username": _field_value(ChatboardConfig.CHATBOARD_USERNAME) or None,
        "password": _field_value(ChatboardConfig.CHATBOARD_PASSWORD) or None,
        "api_key": _field_value(ChatboardConfig.CHATBOARD_API_KEY) or None,
        "auth_secret": _field_value(ChatboardConfig.CHATBOARD_AUTH_SECRET) or None,
    }


def workspace_root_from_chatenv() -> Path:
    """Load and resolve the active ChatBoard workspace from ChatEnv."""

    return load_runtime_config()["workspace_root"]


def service_url_from_chatenv() -> str:
    """Load the active ChatBoard service base URL from ChatEnv."""

    return str(load_runtime_config()["service_url"])


__all__ = [
    "ChatboardConfig",
    "DEFAULT_SERVICE_URL",
    "DEFAULT_WORKSPACE_ROOT",
    "load_runtime_config",
    "service_url_from_chatenv",
    "workspace_root_from_chatenv",
]
