from __future__ import annotations

from importlib.metadata import PathDistribution
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tarfile
from zipfile import ZipFile

import wavebench


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = "0.1.0"


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )


def _write_isolated_runtime_bridge(*, purelib: Path, workspace: Path) -> None:
    bridge = workspace / "runtime-bridge"
    bridge.mkdir()
    for source in Path(sysconfig.get_paths()["purelib"]).iterdir():
        name = source.name
        if name.startswith("wavebench") or name.endswith(
            (".dist-info", ".egg-info", ".pth", ".egg")
        ):
            continue
        os.symlink(source, bridge / name, target_is_directory=source.is_dir())
    Path(purelib, "wavebench-test-runtime.pth").write_text(
        str(Path(wavebench.__file__).resolve().parents[1]) + "\n" + str(bridge) + "\n",
        encoding="utf-8",
    )


def _build_wheel(destination: Path) -> Path:
    destination.mkdir()
    _run(
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
            str(destination),
            str(PACKAGE_ROOT),
        ],
        cwd=destination.parent,
    )
    return next(destination.glob(f"wavebench_siglent_sds3000-{PACKAGE_VERSION}-*.whl"))


def test_wheel_contains_license_and_single_entry_point(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path / "wheelhouse")
    unpacked = tmp_path / "unpacked"
    with ZipFile(wheel) as archive:
        names = archive.namelist()
        archive.extractall(unpacked)

    assert any(name.endswith(".dist-info/licenses/LICENSE") for name in names)
    dist_info = next(unpacked.glob("*.dist-info"))
    distribution = PathDistribution(dist_info)
    entry_points = [
        item for item in distribution.entry_points if item.group == "wavebench.instruments"
    ]

    assert distribution.metadata["License-Expression"] == "MIT"
    assert distribution.version == PACKAGE_VERSION
    requirements = distribution.metadata.get_all("Requires-Dist") or []
    assert any(
        requirement.replace(" ", "") == "wavebench<0.9,>=0.8.22" for requirement in requirements
    )
    assert [(item.name, item.value) for item in entry_points] == [
        ("siglent.sds3000", "wavebench_siglent_sds3000:descriptor")
    ]


def test_sdist_excludes_vendor_material_and_contains_public_audit(tmp_path: Path) -> None:
    _run(
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
    )
    sdist = next(tmp_path.glob(f"wavebench_siglent_sds3000-{PACKAGE_VERSION}.tar.gz"))
    with tarfile.open(sdist) as archive:
        names = archive.getnames()

    assert not any("/doc/vendor-local/" in name for name in names)
    assert any(name.endswith("/doc/manual-baseline.json") for name in names)
    assert any(name.endswith("/doc/command-catalog.json") for name in names)


def test_install_discovery_reinstall_and_uninstall_without_io(tmp_path: Path) -> None:
    wheel = _build_wheel(tmp_path / "wheelhouse")
    venv_dir = tmp_path / "venv"
    _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=tmp_path)
    python = venv_dir / "bin" / "python"
    purelib = _run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        cwd=tmp_path,
    ).stdout.strip()
    _write_isolated_runtime_bridge(purelib=Path(purelib), workspace=tmp_path)

    install_command = [
        str(python),
        "-m",
        "pip",
        "install",
        "--isolated",
        "--no-deps",
        "--no-index",
        "--disable-pip-version-check",
        str(wheel),
    ]
    _run(install_command, cwd=tmp_path)
    discovery_script = """
from importlib.metadata import entry_points
from wavebench.transport.pyvisa_transport import PyVisaTransport

def forbidden(*args, **kwargs):
    raise AssertionError("plugin descriptor import attempted instrument I/O")

PyVisaTransport.open = forbidden
points = list(entry_points().select(group="wavebench.instruments"))
assert [point.name for point in points] == ["siglent.sds3000"]
descriptor = points[0].load()()
assert descriptor.driver_id == "siglent.sds3000"
assert descriptor.distribution == "wavebench-siglent-sds3000"
assert descriptor.capabilities == ("scope.idn",)
"""
    _run([str(python), "-I", "-c", discovery_script], cwd=tmp_path)
    _run([*install_command[:-1], "--force-reinstall", str(wheel)], cwd=tmp_path)
    _run(
        [str(python), "-m", "pip", "uninstall", "--yes", "wavebench-siglent-sds3000"],
        cwd=tmp_path,
    )
    _run(
        [
            str(python),
            "-I",
            "-c",
            (
                "from importlib.metadata import entry_points; "
                "assert not entry_points().select(group='wavebench.instruments')"
            ),
        ],
        cwd=tmp_path,
    )
