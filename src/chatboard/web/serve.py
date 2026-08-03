"""Run the ChatBoard web server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

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
    workspace_root = resolve_workspace_root(root)
    if password and password_file:
        raise click.ClickException("use either --password or --password-file, not both")
    login_password = _read_password_file(Path(password_file)) if password_file else password
    env = os.environ.copy()
    env["CHATBOARD_WORKSPACE_ROOT"] = str(workspace_root)
    if login_password is not None:
        if not login_password:
            raise click.ClickException("login password cannot be empty")
        env["CHATBOARD_PASSWORD"] = login_password
    if username is not None:
        if not username:
            raise click.ClickException("login username cannot be empty")
        env["CHATBOARD_USERNAME"] = username
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
    click.echo(click.style("▶ ChatBoard", bold=True) + f" http://{host}:{port}")
    click.echo(f"  workspace: {env.get('CHATBOARD_WORKSPACE_ROOT', '~/Playground')}")
    click.echo(f"  login: {'enabled' if env.get('CHATBOARD_PASSWORD') else 'disabled'}")
    raise SystemExit(subprocess.call(args, env=env))
