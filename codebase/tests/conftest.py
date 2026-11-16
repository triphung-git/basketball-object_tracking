"""Pytest root configuration for codebase test suite."""
from __future__ import annotations

import os
from pathlib import Path
import sys

CODEBASE_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = CODEBASE_ROOT / "src"
SCRIPTS_DIR = CODEBASE_ROOT / "scripts"

if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
