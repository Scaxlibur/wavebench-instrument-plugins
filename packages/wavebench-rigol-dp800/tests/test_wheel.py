from __future__ import annotations

from importlib.metadata import PathDistribution
from pathlib import Path
import subprocess
import sys
import tarfile
from zipfile import ZipFile


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_wheel_contains_license_and_single_entry_point(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "wheel",
            "--no-build-isolation",
            "--no-deps",
            "--no-index",
            "--disable-pip-version-check",
            "--wheel-dir",
            str(wheelhouse),
            str(PACKAGE_ROOT),
        ],
        cwd=tmp_path,
        text=True,
        capture_output=True,
        check=True,
    )
    wheel = next(wheelhouse.glob("wavebench_rigol_dp800-0.3.0-*.whl"))

    with ZipFile(wheel) as archive:
        names = archive.namelist()
        archive.extractall(tmp_path / "unpacked")

    assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
    dist_info = next((tmp_path / "unpacked").glob("*.dist-info"))
    distribution = PathDistribution(dist_info)
    entry_points = [
        item for item in distribution.entry_points if item.group == "wavebench.instruments"
    ]

    assert distribution.metadata["License-Expression"] == "MIT"
    assert [(item.name, item.value) for item in entry_points] == [
        ("rigol.dp800", "wavebench_rigol_dp800:descriptor")
    ]


def test_sdist_excludes_vendor_manuals(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    subprocess.run(
        [
            sys.executable,
            "-m",
            "hatchling",
            "build",
            "-t",
            "sdist",
            "-d",
            str(dist_dir),
        ],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    sdist = next(dist_dir.glob("wavebench_rigol_dp800-0.3.0.tar.gz"))

    with tarfile.open(sdist) as archive:
        names = archive.getnames()

    assert not any("/doc/vendor-local/" in name for name in names)
    for public_doc in (
        "DP800_COVERAGE_MATRIX.md",
        "DP800_COVERAGE_MATRIX_EN.md",
        "DP800_COVERAGE_MILESTONES.md",
        "DP800_COVERAGE_MILESTONES_EN.md",
    ):
        assert any(name.endswith(f"/doc/{public_doc}") for name in names)
