"""Server-side backend profile store and proxy helpers."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

from chatboard.config import load_runtime_config

ALLOWED_BACKEND_SCHEMES = {"http", "https"}
DEFAULT_PROXY_TIMEOUT_SECONDS = 8


@dataclass(frozen=True)
class BackendProfile:
    id: str
    name: str
    url: str
    api_key: str | None = None
    enabled: bool = True
    is_default: bool = False

    def redacted(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "url": self.url,
            "enabled": self.enabled,
            "is_default": self.is_default,
            "has_token": bool(self.api_key),
        }


class BackendRegistryError(ValueError):
    """Raised when backend registry input is invalid."""


def normalize_backend_url(value: str, *, base_url: str | None = None) -> str:
    """Normalize a backend base URL, accepting bare host:port input."""

    raw = str(value or "").strip()
    if not raw:
        raise BackendRegistryError("backend url is required")
    if raw.startswith("//"):
        raw = f"https:{raw}"
    if "://" not in raw and _looks_like_host_port(raw):
        raw = f"http://{raw}"
    parsed = urlparse(raw if "://" in raw else urljoin(base_url or "http://127.0.0.1", raw))
    if parsed.scheme not in ALLOWED_BACKEND_SCHEMES:
        raise BackendRegistryError("backend url must use http or https")
    if not parsed.netloc:
        raise BackendRegistryError("backend url must include a host")
    return parsed.geturl().rstrip("/")


def backend_api_url(base_url: str, api_path: str) -> str:
    """Build a target backend API URL without duplicating an /api prefix."""

    base = normalize_backend_url(base_url)
    route = api_path if api_path.startswith("/") else f"/{api_path}"
    parsed = urlparse(base)
    base_path = parsed.path.rstrip("/")
    if base_path.endswith("/api"):
        route = route[4:] if route.startswith("/api/") else "" if route == "/api" else route
    return f"{base}{route}"


def load_backend_profiles() -> list[BackendProfile]:
    """Load backend profiles from file/json config with an env-backed default fallback."""

    config = load_runtime_config()
    profiles = _profiles_from_config(config)
    if not profiles:
        default_url = str(config.get("default_backend_url") or config.get("service_url") or "").strip()
        if default_url:
            profiles = [
                BackendProfile(
                    id="default",
                    name=str(config.get("default_backend_name") or "default"),
                    url=normalize_backend_url(default_url),
                    api_key=config.get("default_backend_token"),
                    enabled=True,
                    is_default=True,
                )
            ]
    return _ensure_single_default(profiles)


def save_backend_profiles(profiles: list[BackendProfile]) -> None:
    """Persist backend profiles to CHATBOARD_BACKENDS_FILE."""

    config = load_runtime_config()
    path = config.get("backends_file")
    if not path:
        raise BackendRegistryError("CHATBOARD_BACKENDS_FILE is required to modify backend profiles")
    file_path = Path(path).expanduser()
    file_path.parent.mkdir(parents=True, exist_ok=True)
    data = {
        "schema": "chatboard.backend-profiles.v1",
        "profiles": [
            {
                "id": profile.id,
                "name": profile.name,
                "url": profile.url,
                "api_key": profile.api_key or "",
                "enabled": profile.enabled,
                "is_default": profile.is_default,
            }
            for profile in _ensure_single_default(profiles)
        ],
    }
    file_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def get_backend_profile(profile_id: str) -> BackendProfile:
    for profile in load_backend_profiles():
        if profile.id == profile_id and profile.enabled:
            return profile
    raise KeyError(profile_id)


def upsert_backend_profile(payload: dict[str, Any]) -> BackendProfile:
    profile_id = _clean_id(str(payload.get("id") or ""))
    if not profile_id:
        raise BackendRegistryError("backend id is required")
    name = str(payload.get("name") or profile_id).strip() or profile_id
    url = normalize_backend_url(str(payload.get("url") or ""))
    existing = next((profile for profile in load_backend_profiles() if profile.id == profile_id), None)
    token_was_provided = "api_key" in payload or "token" in payload
    token = str(payload.get("api_key") or payload.get("token") or "").strip() or None if token_was_provided else existing.api_key if existing else None
    enabled = bool(payload.get("enabled", True))
    make_default = bool(payload.get("is_default", False))
    next_profile = BackendProfile(id=profile_id, name=name, url=url, api_key=token, enabled=enabled, is_default=make_default)
    profiles = [profile for profile in load_backend_profiles() if profile.id != profile_id]
    if make_default:
        profiles = [BackendProfile(**{**profile.__dict__, "is_default": False}) for profile in profiles]
    profiles.append(next_profile)
    save_backend_profiles(profiles)
    return next_profile


def delete_backend_profile(profile_id: str) -> None:
    if profile_id == "default":
        raise BackendRegistryError("default backend cannot be deleted")
    profiles = [profile for profile in load_backend_profiles() if profile.id != profile_id]
    save_backend_profiles(profiles)


def set_default_backend(profile_id: str) -> BackendProfile:
    profiles = load_backend_profiles()
    found: BackendProfile | None = None
    next_profiles: list[BackendProfile] = []
    for profile in profiles:
        is_default = profile.id == profile_id
        if is_default:
            found = BackendProfile(**{**profile.__dict__, "is_default": True})
            next_profiles.append(found)
        else:
            next_profiles.append(BackendProfile(**{**profile.__dict__, "is_default": False}))
    if found is None:
        raise KeyError(profile_id)
    save_backend_profiles(next_profiles)
    return found


def _profiles_from_config(config: dict[str, Any]) -> list[BackendProfile]:
    raw = ""
    file_path = config.get("backends_file")
    if file_path and Path(file_path).expanduser().exists():
        raw = Path(file_path).expanduser().read_text(encoding="utf-8")
    elif config.get("backends_json"):
        raw = str(config["backends_json"])
    if not raw.strip():
        return []
    data = json.loads(raw)
    profiles = data.get("profiles", data if isinstance(data, list) else [])
    return [_profile_from_mapping(item) for item in profiles]


def _profile_from_mapping(item: dict[str, Any]) -> BackendProfile:
    profile_id = _clean_id(str(item.get("id") or ""))
    if not profile_id:
        raise BackendRegistryError("backend id is required")
    return BackendProfile(
        id=profile_id,
        name=str(item.get("name") or profile_id).strip() or profile_id,
        url=normalize_backend_url(str(item.get("url") or "")),
        api_key=str(item.get("api_key") or item.get("token") or "").strip() or None,
        enabled=bool(item.get("enabled", True)),
        is_default=bool(item.get("is_default", False)),
    )


def _ensure_single_default(profiles: list[BackendProfile]) -> list[BackendProfile]:
    first_enabled = next((profile for profile in profiles if profile.enabled), None)
    explicit_default = next((profile for profile in profiles if profile.enabled and profile.is_default), None)
    default_target = explicit_default or first_enabled
    default_seen = False
    result: list[BackendProfile] = []
    for profile in profiles:
        is_default = bool(default_target is not None and profile == default_target and profile.enabled and not default_seen)
        if is_default:
            default_seen = True
        result.append(BackendProfile(**{**profile.__dict__, "is_default": is_default}))
    return result


def _looks_like_host_port(value: str) -> bool:
    first = value.split("/", 1)[0]
    return ":" in first and not first.startswith(('.', '/'))


def _clean_id(value: str) -> str:
    return "".join(ch for ch in value.strip().lower() if ch.isalnum() or ch in {"-", "_"})
