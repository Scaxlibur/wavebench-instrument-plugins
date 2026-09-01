from __future__ import annotations

from importlib.metadata import PathDistribution
from pathlib import Path
import subprocess
import sys
import tarfile
from zipfile import ZipFile


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_sdist_excludes_local_vendor_manuals(tmp_path: Path) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "hatchling",
            "build",
            "-t",
            "sdist",
            "-d",
            str(tmp_path),
        ],
        cwd=PACKAGE_ROOT,
        text=True,
        capture_output=True,
        check=True,
    )
    artifacts = list(tmp_path.glob("wavebench_rohde_schwarz_rtm2000-*.tar.gz"))
    assert len(artifacts) == 1
    with tarfile.open(artifacts[0]) as archive:
        members = archive.getnames()
    assert not any("/doc/vendor-local/" in member for member in members)


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
    wheel = next(wheelhouse.glob("wavebench_rohde_schwarz_rtm2000-0.14.0-*.whl"))

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
    assert distribution.version == "0.14.0"
    assert [(item.name, item.value) for item in entry_points] == [
        (
            "rohde-schwarz.rtm2032",
            "wavebench_rohde_schwarz_rtm2000:descriptor",
        )
    ]
