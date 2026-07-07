"""Run the ChatBoard web server."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import click


def serve(host: str = "127.0.0.1", port: int = 8000, root: str | Path | None = None, reload: bool = False) -> None:
    env = os.environ.copy()
    if root is not None:
        env["CHATBOARD_WORKSPACE_ROOT"] = str(Path(root).expanduser().resolve())
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
