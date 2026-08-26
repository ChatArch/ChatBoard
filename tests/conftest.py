from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


CHATBOARD_ENV_KEYS = [
    "CHATBOARD_HOME",
    "CHATBOARD_SERVICE_URL",
    "CHATBOARD_DEFAULT_BACKEND_NAME",
    "CHATBOARD_DEFAULT_BACKEND_URL",
    "CHATBOARD_DEFAULT_BACKEND_TOKEN",
    "CHATBOARD_BACKENDS_FILE",
    "CHATBOARD_BACKENDS_JSON",
    "CHATBOARD_WORKSPACE_ROOT",
    "CHATBOARD_USERNAME",
    "CHATBOARD_PASSWORD",
    "CHATBOARD_API_KEY",
    "CHATBOARD_EXECUTOR_API_KEY",
    "CHATBOARD_AUTH_SECRET",
    "CHATBOARD_SESSION_TTL_SECONDS",
    "CHATBOARD_COOKIE_SECURE",
]


@pytest.fixture(autouse=True)
def isolate_chatenv_home(monkeypatch, tmp_path):
    """Keep tests from reading the developer's real ChatEnv profiles."""

    monkeypatch.setenv("CHATARCH_HOME", str(tmp_path / ".chatarch"))
    for key in CHATBOARD_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)
