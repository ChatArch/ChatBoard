"""ChatLogin-backed optional password gate; API and executor tokens stay separate."""
from __future__ import annotations

from functools import lru_cache
from hashlib import sha256
import hmac
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from chatlogin import CallbackBackend, Principal, Session, SessionManager, SQLiteSessionStore, require_csrf
from chatlogin import AccessDenied
from fastapi import Request, Response

from chatboard.config import load_runtime_config

SESSION_COOKIE = "chatboard_session"
DEFAULT_SESSION_TTL_SECONDS = 12 * 60 * 60


def auth_password() -> str | None:
    return os.environ.get("CHATBOARD_PASSWORD") or load_runtime_config()["password"] or None


def auth_username() -> str | None:
    return os.environ.get("CHATBOARD_USERNAME") or load_runtime_config()["username"] or None


def auth_enabled() -> bool:
    return auth_password() is not None


def api_token_from_chatenv() -> str | None:
    return os.environ.get("CHATBOARD_API_KEY") or load_runtime_config()["api_key"] or None


def api_token_enabled() -> bool:
    return api_token_from_chatenv() is not None


def executor_api_token_from_chatenv() -> str | None:
    token = os.environ.get("CHATBOARD_EXECUTOR_API_KEY") or load_runtime_config().get("executor_api_key")
    return str(token) if token else None


def executor_api_token_enabled() -> bool:
    return executor_api_token_from_chatenv() is not None


def _matches(candidate: str | None, expected: str | None) -> bool:
    return expected is not None and candidate is not None and hmac.compare_digest(candidate.encode(), expected.encode())


def verify_executor_api_token(candidate: str | None) -> bool:
    return _matches(candidate, executor_api_token_from_chatenv())


def verify_api_token(candidate: str | None) -> bool:
    return _matches(candidate, api_token_from_chatenv())


def session_ttl_seconds() -> int:
    raw = os.environ.get("CHATBOARD_SESSION_TTL_SECONDS") or load_runtime_config()["session_ttl_seconds"]
    try:
        return max(60, int(raw))
    except (ValueError, TypeError):
        return DEFAULT_SESSION_TTL_SECONDS


def credential_backend() -> CallbackBackend:
    """Adapt the existing ChatEnv shared password, without adding a user database."""
    expected_username, expected_password = auth_username(), auth_password()

    def authenticate(username: str, password: str) -> Principal | None:
        if expected_username is not None and not _matches(username, expected_username):
            return None
        if not _matches(password, expected_password):
            return None
        return Principal("chatboard", expected_username or "ChatBoard")

    return CallbackBackend(authenticate)


def authenticate_credentials(username: str, password: str) -> Principal | None:
    # ChatLogin expects a nonempty identifier; password-only mode has one fixed identity.
    account = username if auth_username() is not None else "chatboard"
    return credential_backend().authenticate(account, password)


def verify_credentials(username: str, password: str) -> bool:
    return authenticate_credentials(username, password) is not None


@lru_cache(maxsize=8)
def _session_store(database: Path) -> SQLiteSessionStore:
    return SQLiteSessionStore(database, max_sessions=1024)


def session_manager() -> SessionManager:
    """Durable, bounded sessions in the host's ChatArch-owned runtime directory."""
    database = Path(load_runtime_config()["chatboard_home"]) / "sessions.sqlite3"
    return SessionManager(_session_store(database), instance="chatboard", ttl=session_ttl_seconds())


def _auth_secret() -> str:
    # Preserve the existing signing-key precedence and rotation semantics.
    return os.environ.get("CHATBOARD_AUTH_SECRET") or load_runtime_config()["auth_secret"] or auth_password() or "chatboard-local"


def _sign(token: str) -> str:
    return hmac.new(_auth_secret().encode("utf-8"), token.encode("ascii"), sha256).hexdigest()


def unwrap_session_cookie(cookie: str | None) -> str | None:
    """Validate only the transport envelope; ChatLogin owns all session state.

    Never persist a password fingerprint in the SQLite namespace. Old timestamp
    cookies require one new login, and raw core tokens are not browser cookies.
    """
    match = re.fullmatch(r"v2\.([A-Za-z0-9_-]{43})\.([0-9a-f]{64})", cookie or "")
    if match is None:
        return None
    token, signature = match.groups()
    return token if hmac.compare_digest(signature, _sign(token)) else None


def request_session(request: Request) -> Session | None:
    token = unwrap_session_cookie(request.cookies.get(SESSION_COOKIE))
    if not auth_enabled() or not token:
        return None
    return session_manager().resolve(token)


def request_api_token_is_valid(request: Request) -> bool:
    token = request.headers.get("X-ChatBoard-Token")
    authorization = request.headers.get("Authorization", "")
    if authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    return verify_api_token(token)


def request_is_authenticated(request: Request) -> bool:
    if request_api_token_is_valid(request):
        return True
    if not auth_enabled():
        return not api_token_enabled()
    return request_session(request) is not None


def _cookie_secure() -> bool:
    value = os.environ.get("CHATBOARD_COOKIE_SECURE")
    if value is None:
        value = load_runtime_config()["cookie_secure"] or ""
    return str(value).lower() in {"1", "true", "yes", "on"}


def _origin_key(value: str, *, allow_path: bool = False) -> tuple[str, str, int] | None:
    try:
        if not isinstance(value, str) or any(ord(c) <= 32 or ord(c) == 127 for c in value):
            return None
        parsed = urlsplit(value)
        if (parsed.scheme not in {"http", "https"} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or (not allow_path and (parsed.path or parsed.query or parsed.fragment))):
            return None
        port = parsed.port if parsed.port is not None else (443 if parsed.scheme == "https" else 80)
        return parsed.scheme, parsed.hostname, port
    except ValueError:
        return None


def require_same_origin(request: Request, *, required: bool = False) -> None:
    """Allow the direct origin and the trusted configured public service origin.

    SERVICE_URL supplies the canonical origin when a trusted proxy rewrites Host
    between public/local entrypoints. Client Forwarded headers add no origins.
    """
    origins = request.headers.getlist("origin")
    if len(origins) > 1 or request.headers.get("sec-fetch-site") == "cross-site":
        raise AccessDenied(403, "same-origin request required")
    origin = origins[0] if origins else None
    if origin is None and not required:
        return  # Non-browser initial JSON login remains supported.
    hosts = request.headers.getlist("host")
    direct = _origin_key(f"{'https' if _cookie_secure() else request.url.scheme}://{hosts[0]}") if len(hosts) == 1 else None
    configured = _origin_key(load_runtime_config()["service_url"], allow_path=True)
    source = _origin_key(origin or "")
    allowed = {key for key in (direct, configured) if key is not None}
    if direct is None or source is None or source not in allowed:
        raise AccessDenied(403, "same-origin request required")


def protect_cookie_write(request: Request) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"} or not auth_enabled() or request_api_token_is_valid(request):
        return
    session = request_session(request)
    if session is not None:
        require_same_origin(request, required=True)
        require_csrf(session, request.headers.get("X-CSRF-Token"))


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(SESSION_COOKIE, f"v2.{token}.{_sign(token)}", max_age=session_ttl_seconds(),
                        httponly=True, secure=_cookie_secure(), samesite="lax", path="/")


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/", httponly=True, secure=_cookie_secure(), samesite="lax")
