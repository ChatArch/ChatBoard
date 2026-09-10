"""ChatLogin host contracts: real sessions, CSRF and independent executor gate."""
import os
import hashlib
import hmac
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from chatlogin import CallbackBackend, Principal, SessionManager, SQLiteSessionStore

import chatboard.auth as auth
from chatboard.api import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("CHATBOARD_PASSWORD", "fixture-password")
    with TestClient(app) as client:
        yield client


def sign_in(client):
    response = client.post("/api/login", json={"password": "fixture-password"})
    assert response.status_code == 200
    return response


def csrf_headers(client):
    response = client.get("/api/session")
    assert response.status_code == 200
    assert response.headers["cache-control"] == "no-store"
    return {"Origin": "http://testserver", "X-CSRF-Token": response.json()["csrf_token"]}


def test_real_chatlogin_backend_and_durable_store(client):
    sign_in(client)
    assert isinstance(auth.credential_backend(), CallbackBackend)
    manager = auth.session_manager()
    assert isinstance(manager, SessionManager)
    assert isinstance(manager.store, SQLiteSessionStore)
    assert manager.store.max_sessions == 1024
    assert manager.store.database == Path(os.environ["CHATARCH_HOME"]) / "chatboard/sessions.sqlite3"
    cookie = client.cookies[auth.SESSION_COOKIE]
    token = auth.unwrap_session_cookie(cookie)
    assert cookie.startswith("v2.")
    assert token and "." not in token
    assert manager.resolve(token).principal == Principal("chatboard", "ChatBoard")
    second = SessionManager(SQLiteSessionStore(manager.store.database, max_sessions=1024), instance="chatboard")
    assert second.resolve(token) is not None


def test_logout_revokes_replay(client):
    sign_in(client)
    token = client.cookies[auth.SESSION_COOKIE]
    core_token = auth.unwrap_session_cookie(token)
    assert auth.session_manager().resolve(core_token) is not None
    assert client.post("/api/logout", headers=csrf_headers(client)).status_code == 200
    assert auth.session_manager().resolve(core_token) is None
    replay = TestClient(app)
    replay.cookies.set(auth.SESSION_COOKIE, token)
    assert replay.get("/api/pages").status_code == 401


def test_cookie_writes_require_csrf_and_same_origin(client):
    sign_in(client)
    headers = csrf_headers(client)
    assert client.post("/api/logout").status_code == 403
    assert client.post("/api/logout", headers={"Origin": "http://testserver", "X-CSRF-Token": "wrong"}).status_code == 403
    headers["Origin"] = "https://evil.example"
    assert client.post("/api/logout", headers=headers).status_code == 403
    assert client.get("/api/session", headers={"Origin": "https://evil.example"}).status_code == 403


def test_cookie_cannot_bypass_csrf_using_wrong_api_token(client):
    sign_in(client)
    assert client.post("/api/logout", headers={"Authorization": "Bearer wrong"}).status_code == 403


def test_api_token_writes_still_work(client, monkeypatch):
    monkeypatch.setenv("CHATBOARD_API_KEY", "fixture-api-token")
    # API-token requests need neither a session nor browser Origin/CSRF headers.
    response = client.post("/api/backend-profiles", headers={"X-ChatBoard-Token": "fixture-api-token"},
                           json={"id": "test", "name": "Test", "url": "http://127.0.0.1:8001/"})
    assert response.status_code == 200


def test_session_expiry_uses_chatlogin_clock(client, tmp_path, monkeypatch):
    now = [1000.0]
    manager = SessionManager(SQLiteSessionStore(tmp_path / "expiry.sqlite3"), instance="chatboard", ttl=60, clock=lambda: now[0])
    monkeypatch.setattr(auth, "session_manager", lambda: manager, raising=False)
    sign_in(client)
    assert client.get("/api/pages").status_code == 200
    now[0] += 60
    assert client.get("/api/pages").status_code == 401


def test_login_rotation_requires_csrf_and_revokes_previous(client):
    sign_in(client)
    token = client.cookies[auth.SESSION_COOKIE]
    core_token = auth.unwrap_session_cookie(token)
    assert client.post("/api/login", json={"password": "fixture-password"}).status_code == 403
    rotated = client.post("/api/login", headers=csrf_headers(client), json={"password": "fixture-password", "next": "//evil.example"})
    assert rotated.status_code == 200
    assert rotated.json()["next"] == "/"
    assert token != client.cookies[auth.SESSION_COOKIE]
    assert auth.session_manager().resolve(core_token) is None


@pytest.mark.parametrize("setting", ["CHATBOARD_PASSWORD", "CHATBOARD_AUTH_SECRET"])
def test_configured_key_rotation_invalidates_existing_cookie(client, monkeypatch, setting):
    if setting == "CHATBOARD_AUTH_SECRET":
        monkeypatch.setenv(setting, "fixture-signing-key")
    sign_in(client)
    assert client.get("/api/pages").status_code == 200
    monkeypatch.setenv(setting, "fixture-rotated-key")
    assert client.get("/api/pages").status_code == 401
    assert client.get("/api/session").json()["csrf_token"] is None
    password = "fixture-rotated-key" if setting == "CHATBOARD_PASSWORD" else "fixture-password"
    assert client.post("/api/login", json={"password": password}).status_code == 200
    assert client.get("/api/pages").status_code == 200


def test_explicit_key_precedes_password_and_cookie_is_only_envelope(client, monkeypatch):
    monkeypatch.setenv("CHATBOARD_AUTH_SECRET", "fixture-signing-key")
    sign_in(client)
    cookie = client.cookies[auth.SESSION_COOKIE]
    version, token, signature = cookie.split(".")
    assert version == "v2"
    assert signature == hmac.new(b"fixture-signing-key", token.encode(), hashlib.sha256).hexdigest()
    assert auth.session_manager().resolve(token) is not None
    monkeypatch.setenv("CHATBOARD_PASSWORD", "fixture-new-password")
    assert client.get("/api/pages").status_code == 200


def test_raw_forged_and_legacy_cookies_fail_closed(client, monkeypatch):
    monkeypatch.setenv("CHATBOARD_AUTH_SECRET", "fixture-signing-key")
    sign_in(client)
    cookie = client.cookies[auth.SESSION_COOKIE]
    version, token, signature = cookie.split(".")
    forged = hmac.new(b"wrong-key", token.encode(), hashlib.sha256).hexdigest()
    for invalid in (token, f"v2.{token}.{forged}", f"v1.{token}.{signature}",
                    cookie + ".extra", f"v2..{signature}", f"123456.{signature}",
                    f"v2.{token}.not-a-signature"):
        client.cookies.clear()
        client.cookies.set(auth.SESSION_COOKIE, invalid)
        assert client.get("/api/pages").status_code == 401
    assert auth.unwrap_session_cookie("v2.é." + signature) is None
    assert auth.session_manager().resolve(token) is not None


@pytest.mark.parametrize("outer", ["cookie", "api-key"])
def test_outer_auth_does_not_grant_executor_permission(client, monkeypatch, tmp_path, outer):
    monkeypatch.setenv("CHATBOARD_EXECUTOR_API_KEY", "fixture-executor-token")
    if outer == "cookie":
        sign_in(client)
        headers = csrf_headers(client)
    else:
        monkeypatch.setenv("CHATBOARD_API_KEY", "fixture-api-token")
        headers = {"X-ChatBoard-Token": "fixture-api-token"}
    payload = {"executor": "codex", "mode": "real", "prompt": "Never launch", "workdir": "."}
    assert client.post("/api/runs", json=payload, headers=headers, params={"root": str(tmp_path)}).status_code == 403
    payload["mode"] = "dry-run"
    planned = client.post("/api/runs", json=payload, headers=headers, params={"root": str(tmp_path)})
    assert planned.status_code == 200
    run_id = planned.json()["run"]["run_id"]
    assert client.post(f"/api/runs/{run_id}/collect", headers=headers, params={"root": str(tmp_path)}).status_code == 403
    headers["X-ChatBoard-Executor-Token"] = "fixture-executor-token"
    assert client.post(f"/api/runs/{run_id}/collect", headers=headers, params={"root": str(tmp_path)}).status_code == 200


def test_login_cross_site_and_untrusted_forwarded_rejected(client):
    for headers in ({"Origin": "https://evil.example"}, {"Sec-Fetch-Site": "cross-site"},
                    {"Origin": "https://evil.example", "X-Forwarded-Host": "evil.example", "X-Forwarded-Proto": "https"}):
        assert client.post("/api/login", headers=headers, json={"password": "fixture-password"}).status_code == 403


def test_login_errors_do_not_issue_session(client, monkeypatch):
    monkeypatch.setenv("CHATBOARD_USERNAME", "operator")
    for data in ({"account": "operator", "password": "wrong"}, {"username": "wrong", "password": "fixture-password"}):
        assert client.post("/api/login", json=data).status_code == 401
        assert auth.SESSION_COOKIE not in client.cookies
    assert client.post("/api/login", json={"account": "operator", "password": "fixture-password"}).status_code == 200


def test_shared_ui_optional_username_theme_and_assets(client, monkeypatch):
    monkeypatch.setenv("CHATBOARD_LOGIN_PALETTE", "forest")
    page = client.get("/login?next=/tasks")
    assert 'class="chatlogin"' in page.text
    assert 'data-palette="forest"' in page.text
    assert 'data-next="/tasks"' in page.text
    assert 'name="username" type="hidden"' in page.text
    assert '/auth-assets/login.js' in page.text
    assert client.get("/auth-assets/login.js").status_code == 200
    assert client.get("/auth-assets/login.css").status_code == 200
    assert client.get("/auth-assets/credentials.py").status_code == 404
    assert client.get("/openapi.json", follow_redirects=False).status_code == 303


def test_disabled_and_api_only_contract(monkeypatch):
    client = TestClient(app)
    assert client.get("/api/pages").status_code == 200
    assert client.post("/api/logout").status_code == 200
    monkeypatch.setenv("CHATBOARD_API_KEY", "fixture-api-token")
    assert client.get("/").status_code == 200
    assert client.get("/api/pages").status_code == 401
    assert client.get("/api/pages", headers={"Authorization": "Bearer fixture-api-token"}).status_code == 200


def test_executor_token_does_not_replace_outer_gate(client, monkeypatch):
    monkeypatch.setenv("CHATBOARD_EXECUTOR_API_KEY", "fixture-executor-token")
    assert client.post("/api/runs", headers={"X-ChatBoard-Executor-Token": "fixture-executor-token"}, json={}).status_code == 401


def test_configured_public_origin_survives_proxy_host_rewrite(client, monkeypatch):
    public = "https://board.example.test"
    monkeypatch.setenv("CHATBOARD_SERVICE_URL", public + "/")
    headers = {"Host": "bridge.example.test", "Origin": public}
    response = client.post("/api/login", headers=headers, json={"password": "fixture-password"})
    assert response.status_code == 200
    session = client.get("/api/session", headers=headers)
    assert session.status_code == 200
    assert client.post("/api/logout", headers={**headers, "X-CSRF-Token": session.json()["csrf_token"]}).status_code == 200


def test_forwarded_headers_cannot_add_a_public_origin(client, monkeypatch):
    monkeypatch.setenv("CHATBOARD_SERVICE_URL", "https://board.example.test/")
    headers = {"Host": "bridge.example.test", "Origin": "https://wrong.example.test",
               "X-Forwarded-Host": "wrong.example.test", "X-Forwarded-Proto": "https"}
    assert client.post("/api/login", headers=headers, json={"password": "fixture-password"}).status_code == 403


def test_frontend_has_single_csrf_fetch_boundary():
    script = Path("src/chatboard/web_static/assets/app.js").read_text()
    assert "async function frontendFetch(" in script
    assert "X-CSRF-Token" in script
    assert "fetch('/api/session'" in script
    assert "await frontendFetch(`/api/backend-profiles/" in script
