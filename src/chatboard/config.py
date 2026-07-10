"Typed environment configuration for ChatBoard."

from pathlib import Path

from chatenv import BaseEnvConfig, EnvField, get_paths


DEFAULT_WORKSPACE_ROOT = Path.home() / "Playground"


class ChatboardConfig(BaseEnvConfig):
    "ChatBoard ChatEnv configuration."

    _title = "ChatBoard Configuration"
    _aliases = ["chatboard", "chatbd"]
    _storage_dir = "Chatboard"

    @classmethod
    def test(cls) -> None:
        """Validate schema registration without external side effects."""

        print(f"Testing {cls._title}...")
        print("Schema loaded; no network test is required.")

    CHATBOARD_WORKSPACE_ROOT = EnvField(
        "CHATBOARD_WORKSPACE_ROOT",
        default=str(DEFAULT_WORKSPACE_ROOT),
        desc="Default ChatArch workspace root.",
    )

    CHATBOARD_API_KEY = EnvField(
        "CHATBOARD_API_KEY",
        desc="API key",
        is_sensitive=True,
    )


def workspace_root_from_chatenv() -> Path:
    """Load and resolve the active ChatBoard workspace from ChatEnv."""

    BaseEnvConfig.load_all(get_paths().envs_dir)
    value = ChatboardConfig.CHATBOARD_WORKSPACE_ROOT.value or DEFAULT_WORKSPACE_ROOT
    return Path(str(value)).expanduser().resolve()


__all__ = ["ChatboardConfig", "workspace_root_from_chatenv"]
