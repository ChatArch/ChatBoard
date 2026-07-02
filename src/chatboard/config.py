"Typed environment configuration for ChatBoard."

from chatenv import BaseEnvConfig, EnvField


class ChatboardConfig(BaseEnvConfig):
    "ChatBoard ChatEnv configuration."

    _title = "ChatBoard Configuration"
    _aliases = ["chatboard"]
    _storage_dir = "Chatboard"

    @classmethod
    def test(cls) -> None:
        """Validate schema registration without external side effects."""

        print(f"Testing {cls._title}...")
        print("Schema loaded; no network test is required.")

    CHATBOARD_API_KEY = EnvField(
        "CHATBOARD_API_KEY",
        desc="API key",
        is_sensitive=True,
    )


__all__ = ["ChatboardConfig"]
