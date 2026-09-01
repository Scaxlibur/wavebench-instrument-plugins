from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_package_module_exists() -> None:
    assert (PACKAGE_ROOT / "src" / "wavebench_rigol_dsg830" / "__init__.py").is_file()
