"""Bounded real HTTP login smoke; no live workspace, browser or executor."""
import socket
import threading
import time

import httpx
import uvicorn

from chatboard.api import app
from chatboard.auth import SESSION_COOKIE


def test_login_over_real_loopback_http(monkeypatch):
    monkeypatch.setenv("CHATBOARD_PASSWORD", "tcp-fixture-password")
    monkeypatch.setenv("CHATBOARD_AUTH_SECRET", "tcp-fixture-signing-key")
    server = uvicorn.Server(uvicorn.Config(app, log_level="error", access_log=False, lifespan="off"))
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
        thread = threading.Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
        thread.start()
        try:
            with httpx.Client(base_url=origin, trust_env=False, timeout=2) as client:
                deadline = time.monotonic() + 5
                while True:
                    try:
                        response = client.get("/api/health")
                        assert response.status_code == 200
                        break
                    except httpx.TransportError:
                        assert time.monotonic() < deadline, "loopback server did not become ready"
                        time.sleep(0.02)
                assert client.get("/").status_code == 303
                page = client.get("/login?next=/")
                assert page.status_code == 200 and 'class="chatlogin"' in page.text
                for asset in ("/auth-assets/login.css", "/auth-assets/login.js", "/assets/app.js"):
                    assert client.get(asset).status_code == 200
                assert client.post("/api/login", json={"password": "wrong"}).status_code == 401
                login = client.post("/api/login", headers={"Origin": origin}, json={"password": "tcp-fixture-password"})
                assert login.status_code == 200
                cookie = client.cookies[SESSION_COOKIE]
                assert cookie.startswith("v2.")
                assert "HttpOnly" in login.headers["set-cookie"] and "SameSite=lax" in login.headers["set-cookie"]
                session = client.get("/api/session")
                assert session.headers["cache-control"] == "no-store"
                csrf = session.json()["csrf_token"]
                assert session.json()["authenticated"] is True and csrf
                assert client.get("/api/pages").status_code == 200
                body = {"id": "tcp-fixture", "name": "TCP fixture", "url": "http://127.0.0.1:9/"}
                assert client.post("/api/backend-profiles", json=body).status_code == 403
                assert client.post("/api/backend-profiles", headers={"Origin": origin, "X-CSRF-Token": "wrong"}, json=body).status_code == 403
                headers = {"Origin": origin, "X-CSRF-Token": csrf}
                assert client.post("/api/backend-profiles", headers=headers, json=body).status_code == 200
                assert client.post("/api/logout", headers={**headers, "Origin": "https://evil.example"}).status_code == 403
                assert client.post("/api/logout", headers=headers).status_code == 200
                assert SESSION_COOKIE not in client.cookies
                client.cookies.set(SESSION_COOKIE, cookie)
                assert client.get("/api/pages").status_code == 401
        finally:
            server.should_exit = True
            thread.join(timeout=5)
            assert not thread.is_alive(), "loopback server failed to stop"
