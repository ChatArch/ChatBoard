import pytest

from chatboard.web import serve as serve_module


def _runtime_config(root):
    return {
        "workspace_root": root,
        "service_url": "http://127.0.0.1:8010/",
        "password": "secret",
        "username": "rexwzh@lookeng.cn",
        "api_key": "api-secret",
        "auth_secret": "auth-secret",
        "session_ttl_seconds": "86400",
        "cookie_secure": "true",
    }


def test_serve_startup_summary_uses_chatstyle_render_helpers(monkeypatch, tmp_path):
    calls = []
    process_calls = []

    monkeypatch.setattr(serve_module, "load_runtime_config", lambda: _runtime_config(tmp_path))
    monkeypatch.setattr(serve_module, "render_heading", lambda title, subtitle=None: calls.append(("heading", title, subtitle)))
    monkeypatch.setattr(serve_module, "render_key_values", lambda items, **kwargs: calls.append(("key_values", dict(items), kwargs)))
    monkeypatch.setattr(serve_module.subprocess, "call", lambda args, env=None: process_calls.append((args, env)) or 0)

    with pytest.raises(SystemExit) as exc:
        serve_module.serve(host="127.0.0.1", port=8765)

    assert exc.value.code == 0
    assert calls == [
        ("heading", "ChatBoard", "http://127.0.0.1:8765"),
        ("key_values", {"workspace": str(tmp_path.resolve()), "login": "enabled"}, {"err": True}),
    ]
    assert process_calls
    args, env = process_calls[0]
    assert args[:4] == [serve_module.sys.executable, "-m", "uvicorn", "chatboard.api:app"]
    assert env["CHATBOARD_WORKSPACE_ROOT"] == str(tmp_path.resolve())
    assert env["CHATBOARD_USERNAME"] == "rexwzh@lookeng.cn"
    assert env["CHATBOARD_PASSWORD"] == "secret"
    assert env["CHATBOARD_SESSION_TTL_SECONDS"] == "86400"
    assert env["CHATBOARD_COOKIE_SECURE"] == "true"
