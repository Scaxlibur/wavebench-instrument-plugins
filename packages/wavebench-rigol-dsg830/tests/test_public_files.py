from __future__ import annotations

from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_public_package_files_and_local_manual_placeholder_exist() -> None:
    for relative_path in (
        "LICENSE",
        "README.md",
        "README_EN.md",
        "doc/vendor-local/README.md",
    ):
        assert (PACKAGE_ROOT / relative_path).is_file()
