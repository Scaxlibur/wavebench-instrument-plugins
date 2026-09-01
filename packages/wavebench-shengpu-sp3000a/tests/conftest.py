from __future__ import annotations

from pathlib import Path
import sys


PACKAGE_SRC = Path(__file__).resolve().parents[1] / "src"
TESTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(PACKAGE_SRC))
sys.path.insert(0, str(TESTS_DIR))
