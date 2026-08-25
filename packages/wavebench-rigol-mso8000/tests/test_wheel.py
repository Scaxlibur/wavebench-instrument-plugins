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
PACKAGE_VERSION = "0.9.0"


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )


def _build_wheel(wheelhouse: Path) -> Path:
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
            str(wheelhouse),
            str(PACKAGE_ROOT),
        ],
        cwd=wheelhouse.parent,
    )
    return next(wheelhouse.glob(f"wavebench_rigol_mso8000-{PACKAGE_VERSION}-*.whl"))


def _write_isolated_runtime_bridge(*, purelib: Path, workspace: Path) -> None:
    bridge = workspace / "runtime-bridge"
    bridge.mkdir()
    for source in Path(sysconfig.get_paths()["purelib"]).iterdir():
        name = source.name
        if (
            name.startswith("wavebench")
            or name.endswith((".dist-info", ".egg-info", ".pth", ".egg"))
        ):
            continue
        os.symlink(source, bridge / name, target_is_directory=source.is_dir())
    Path(purelib, "wavebench-test-runtime.pth").write_text(
        str(Path(wavebench.__file__).resolve().parents[1]) + "\n" + str(bridge) + "\n",
        encoding="utf-8",
    )


def test_wheel_metadata_license_and_single_entry_point(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _build_wheel(wheelhouse)

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
    assert distribution.version == PACKAGE_VERSION
    assert (distribution.metadata.get_all("Requires-Dist") or []).count(
        "wavebench<0.9,>=0.8.24"
    ) == 1
    assert [(item.name, item.value) for item in entry_points] == [
        ("rigol.mso8104", "wavebench_rigol_mso8000:descriptor")
    ]
    assert not any("vendor-local" in name for name in names)


def test_sdist_excludes_vendor_manuals_and_contains_public_docs(tmp_path: Path) -> None:
    dist_dir = tmp_path / "dist"
    _run(
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
    )
    sdist = next(dist_dir.glob(f"wavebench_rigol_mso8000-{PACKAGE_VERSION}.tar.gz"))

    with tarfile.open(sdist) as archive:
        names = archive.getnames()

    assert not any("/doc/vendor-local/" in name for name in names)
    for public_doc in (
        "MSO8104_COVERAGE_MATRIX.md",
        "MSO8104_COVERAGE_MATRIX_EN.md",
        "MSO8104_COVERAGE_MILESTONES.md",
        "MSO8104_COVERAGE_MILESTONES_EN.md",
        "MSO8104_HARDWARE_ACCEPTANCE.md",
        "MSO8104_HARDWARE_ACCEPTANCE_EN.md",
    ):
        assert any(name.endswith(f"/doc/{public_doc}") for name in names)


def test_wheel_install_discovery_and_uninstall_without_instrument_io(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    wheel = _build_wheel(wheelhouse)
    venv_dir = tmp_path / "venv"
    _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=tmp_path)
    python = venv_dir / "bin" / "python"
    purelib = _run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        cwd=tmp_path,
    ).stdout.strip()
    _write_isolated_runtime_bridge(purelib=Path(purelib), workspace=tmp_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "install",
            "--isolated",
            "--no-deps",
            "--no-index",
            "--disable-pip-version-check",
            str(wheel),
        ],
        cwd=tmp_path,
    )
    discovery_script = """
from importlib.metadata import entry_points
from wavebench.transport.pyvisa_transport import PyVisaTransport

def forbidden(*args, **kwargs):
    raise AssertionError("plugin descriptor import attempted instrument I/O")

PyVisaTransport.open = forbidden
points = list(entry_points().select(group="wavebench.instruments"))
assert [point.name for point in points] == ["rigol.mso8104"]
descriptor = points[0].load()()
assert descriptor.driver_id == "rigol.mso8104"
assert descriptor.distribution == "wavebench-rigol-mso8000"
assert descriptor.capabilities == (
    "scope.idn",
    "scope.fetch_waveform",
    "scope.channel_coupling",
    "scope.channel_input_state_v2",
    "scope.autoscale",
    "scope.math_metadata",
    "scope.measurement_statistics_v2",
    "scope.fft_status_v2",
    "scope.acquisition_status_v2",
    "scope.acquisition_run_state",
    "scope.acquisition_control",
    "scope.digital_status_v2",
    "scope.snapshot_v2",
    "scope.cursor_readout",
    "scope.cursor_readout_v2",
)
"""
    _run([str(python), "-I", "-c", discovery_script], cwd=tmp_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "uninstall",
            "--yes",
            "wavebench-rigol-mso8000",
        ],
        cwd=tmp_path,
    )
    uninstall_script = """
from importlib.metadata import entry_points
from wavebench.errors import ConfigError
from wavebench.instruments.registry import build_instrument_registry

assert not entry_points().select(group="wavebench.instruments")
try:
    build_instrument_registry().resolve("rigol.mso8104", expected_kind="scope")
except ConfigError as exc:
    assert "not installed" in str(exc)
else:
    raise AssertionError("removed MSO8104 plugin still resolved")
"""
    _run([str(python), "-I", "-c", uninstall_script], cwd=tmp_path)
