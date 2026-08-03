"""Optional password gate for the ChatBoard web server."""

from __future__ import annotations

import hmac
import os
import time
from hashlib import sha256

from fastapi import Request, Response

SESSION_COOKIE = "chatboard_session"
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60


def auth_password() -> str | None:
    password = os.environ.get("CHATBOARD_PASSWORD")
    return password if password else None


def auth_username() -> str | None:
    username = os.environ.get("CHATBOARD_USERNAME")
    return username if username else None


def auth_enabled() -> bool:
    return auth_password() is not None


def session_ttl_seconds() -> int:
    raw = os.environ.get("CHATBOARD_SESSION_TTL_SECONDS")
    if not raw:
        return DEFAULT_SESSION_TTL_SECONDS
    try:
        return max(60, int(raw))
    except ValueError:
        return DEFAULT_SESSION_TTL_SECONDS


def _auth_secret() -> str:
    return os.environ.get("CHATBOARD_AUTH_SECRET") or auth_password() or "chatboard-local"


def _sign(payload: str) -> str:
    return hmac.new(_auth_secret().encode("utf-8"), payload.encode("utf-8"), sha256).hexdigest()


def verify_password(candidate: str) -> bool:
    password = auth_password()
    return password is not None and hmac.compare_digest(candidate, password)


def verify_credentials(username: str, password: str) -> bool:
    expected_username = auth_username()
    if expected_username is not None and not hmac.compare_digest(username, expected_username):
        return False
    return verify_password(password)


def create_session_token(now: float | None = None) -> str:
    issued_at = str(int(now or time.time()))
    return f"{issued_at}.{_sign(issued_at)}"


def validate_session_token(token: str | None, now: float | None = None) -> bool:
    if not auth_enabled():
        return True
    if not token or "." not in token:
        return False
    issued_at, signature = token.rsplit(".", 1)
    if not issued_at.isdigit():
        return False
    if not hmac.compare_digest(signature, _sign(issued_at)):
        return False
    age = int(now or time.time()) - int(issued_at)
    return 0 <= age <= session_ttl_seconds()


def request_is_authenticated(request: Request) -> bool:
    return validate_session_token(request.cookies.get(SESSION_COOKIE))


def _cookie_secure() -> bool:
    return os.environ.get("CHATBOARD_COOKIE_SECURE", "").lower() in {"1", "true", "yes", "on"}


def set_session_cookie(response: Response) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        create_session_token(),
        max_age=session_ttl_seconds(),
        httponly=True,
        secure=_cookie_secure(),
        samesite="lax",
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")
