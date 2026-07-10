"""Run the ChatBoard web server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click

from chatboard.paths import resolve_workspace_root


def serve(host: str = "127.0.0.1", port: int = 8000, root: str | Path | None = None, reload: bool = False) -> None:
    workspace_root = resolve_workspace_root(root)
    env = os.environ.copy()
    env["CHATBOARD_WORKSPACE_ROOT"] = str(workspace_root)
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
    raise SystemExit(subprocess.call(args, env=env))
