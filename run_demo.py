#!/usr/bin/env python3
"""Root CLI entrypoint for the basketball spatial-analysis demo."""
from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
DEMO_SCRIPT = ROOT / "codebase/scripts/run_demo.py"

if __name__ == "__main__":
    venv_py = ROOT / "codebase/.venv/Scripts/python.exe"
    python_bin = str(venv_py) if venv_py.is_file() else sys.executable
    user_args = sys.argv[1:]
    if not user_args:
        user_args = ["--preset", "default", "--mode", "view"]

    cmd = [python_bin, str(DEMO_SCRIPT)] + user_args
    env = os.environ.copy()
    env["PYTHONPATH"] = str(ROOT / "codebase/src") + os.pathsep + str(ROOT / "codebase/scripts")
    env["PYTHONIOENCODING"] = "utf-8"
    ret = subprocess.run(cmd, env=env)
    sys.exit(ret.returncode)
