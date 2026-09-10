"""Execute the shipped fetch boundary using Node's real Headers/URL runtime."""
import os
from pathlib import Path
import shutil
import subprocess

import pytest


def test_frontend_fetch_runtime():
    node = os.environ.get("NODE_BINARY") or shutil.which("node")
    if node is None:
        if os.environ.get("CI"):
            pytest.fail("CI requires Node.js for the frontend fetch regression")
        pytest.skip("Node.js unavailable; CI installs Node.js for this gate")
    result = subprocess.run([node, "tests/frontend_fetch.cjs"], text=True, capture_output=True,
                            cwd=Path(__file__).resolve().parents[1], timeout=15)
    assert result.returncode == 0, result.stdout + result.stderr
