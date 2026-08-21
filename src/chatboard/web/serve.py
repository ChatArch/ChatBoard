"""Run the ChatBoard web server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click
from chatstyle import render_heading, render_key_values

from chatboard.config import load_runtime_config
from chatboard.paths import resolve_workspace_root


def _read_password_file(path: Path) -> str:
    try:
        password = path.expanduser().read_text(encoding="utf-8").rstrip("\r\n")
    except OSError as exc:
        raise click.ClickException(f"cannot read password file: {path}") from exc
    if not password:
        raise click.ClickException(f"password file is empty: {path}")
    return password


def serve(
    host: str = "127.0.0.1",
    port: int = 8000,
    root: str | Path | None = None,
    reload: bool = False,
    username: str | None = None,
    password: str | None = None,
    password_file: str | Path | None = None,
) -> None:
    runtime_config = load_runtime_config()
    workspace_root = resolve_workspace_root(root or runtime_config["workspace_root"])
    if password and password_file:
        raise click.ClickException("use either --password or --password-file, not both")
    login_password = _read_password_file(Path(password_file)) if password_file else password or runtime_config["password"]
    login_username = username or runtime_config["username"]
    env = os.environ.copy()
    env["CHATBOARD_WORKSPACE_ROOT"] = str(workspace_root)
    env["CHATBOARD_SERVICE_URL"] = runtime_config["service_url"]
    if login_password is not None:
        if not login_password:
            raise click.ClickException("login password cannot be empty")
        env["CHATBOARD_PASSWORD"] = login_password
    if login_username is not None:
        if not login_username:
            raise click.ClickException("login username cannot be empty")
        env["CHATBOARD_USERNAME"] = login_username
    if runtime_config["api_key"]:
        env.setdefault("CHATBOARD_API_KEY", runtime_config["api_key"])
    if runtime_config["auth_secret"]:
        env.setdefault("CHATBOARD_AUTH_SECRET", runtime_config["auth_secret"])
    if runtime_config["session_ttl_seconds"]:
        env.setdefault("CHATBOARD_SESSION_TTL_SECONDS", runtime_config["session_ttl_seconds"])
    if runtime_config["cookie_secure"]:
        env.setdefault("CHATBOARD_COOKIE_SECURE", runtime_config["cookie_secure"])
    args = [
        sys.executable,
        "-m",
        "uvicorn",
        "chatboard.api:app",
        f"--host={host}",
        f"--port={port}",
    ]
    if reload:
        args.append("--reload")
    render_heading("ChatBoard", f"http://{host}:{port}")
    render_key_values(
        {
            "workspace": env.get("CHATBOARD_WORKSPACE_ROOT", "~/Playground"),
            "login": "enabled" if env.get("CHATBOARD_PASSWORD") else "disabled",
        },
        err=True,
    )
    raise SystemExit(subprocess.call(args, env=env))
