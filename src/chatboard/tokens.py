"""ChatEnv runtime token refresh provider for ChatBoard."""

from __future__ import annotations

from http.cookies import SimpleCookie
from pathlib import Path
from typing import Any, Callable, Mapping
from urllib import request as urllib_request
import json

from chatenv import EnvStore, TokenRefreshResult

from chatboard.auth import SESSION_COOKIE
from chatboard.config import ChatboardConfig

DEFAULT_REFRESH_TIMEOUT = 15


def _load_profile(env_store: EnvStore, profile: str) -> dict[str, str]:
    if profile == "default":
        return env_store.load_active(ChatboardConfig)
    return env_store.load_profile(ChatboardConfig, profile)


def _json_post(url: str, *, json: Mapping[str, Any], timeout: int):
    body = __import__("json").dumps(dict(json)).encode("utf-8")
    request = urllib_request.Request(
        url,
        data=body,
        headers={"content-type": "application/json"},
        method="POST",
    )
    response = urllib_request.urlopen(request, timeout=timeout)  # noqa: S310 - user-configured service URL.
    return _UrllibResponse(response)


class _UrllibResponse:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.status_code = int(getattr(response, "status", 0) or response.getcode())
        self.headers = response.headers
        self._body = response.read().decode("utf-8", errors="replace")

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise ValueError(f"ChatBoard login failed with HTTP {self.status_code}")

    def json(self) -> Any:
        return json.loads(self._body or "{}")


def _base_url(service_url: str) -> str:
    service_url = service_url.strip()
    return service_url if service_url.endswith("/") else service_url + "/"


def _session_cookie(set_cookie: str) -> str:
    cookie = SimpleCookie()
    cookie.load(set_cookie)
    morsel = cookie.get(SESSION_COOKIE)
    if morsel is None or not morsel.value:
        raise ValueError("ChatBoard login response did not include a chatboard_session cookie")
    return f"{SESSION_COOKIE}={morsel.value}"


def refresh_token(
    *,
    service: str,
    profile: str,
    home: str | Path,
    env_store: EnvStore | None = None,
    post: Callable[..., Any] | None = None,
    **_: Any,
) -> TokenRefreshResult:
    """Log in with a ChatEnv profile and return an opaque browser session cookie."""

    env_store = env_store or EnvStore(Path(home) / "envs")
    values = _load_profile(env_store, profile)
    service_url = _base_url(values.get("CHATBOARD_SERVICE_URL") or "")
    username = values.get("CHATBOARD_USERNAME") or ""
    password = values.get("CHATBOARD_PASSWORD") or ""
    if not service_url:
        raise ValueError("CHATBOARD_SERVICE_URL is required for ChatBoard token refresh")
    if not password:
        raise ValueError("CHATBOARD_PASSWORD is required for ChatBoard token refresh")

    post = post or _json_post
    try:
        response = post(
            service_url + "api/login",
            json={"username": username, "password": password},
            timeout=DEFAULT_REFRESH_TIMEOUT,
        )
        response.raise_for_status()
    except Exception as exc:
        if isinstance(exc, ValueError):
            raise
        raise ValueError(f"ChatBoard token refresh failed: {type(exc).__name__}") from exc
    cookie = _session_cookie(str(response.headers.get("set-cookie", "")))
    return TokenRefreshResult(
        values={"cookie": cookie},
        token_type="web_session",
        summary={
            "service_url": service_url,
            "username": username,
            "cookie_name": SESSION_COOKIE,
        },
    )


__all__ = ["refresh_token"]
