"""Web asset paths for ChatBoard."""

from __future__ import annotations

from pathlib import Path


def package_static_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "web_static"
