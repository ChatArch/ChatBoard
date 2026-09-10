from pathlib import Path
import os
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if os.environ.get("CHATARCH_TEST_INSTALLED") != "1" and str(SRC) not in sys.path:
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
    for key in set(CHATBOARD_ENV_KEYS) | {key for key in os.environ if key.startswith("CHATBOARD_")}:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("CHATBOARD_WORKSPACE_ROOT", str(tmp_path / "workspace"))
    (tmp_path / "workspace").mkdir()
