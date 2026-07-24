from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tarfile

import wavebench


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)


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


def test_sdist_excludes_local_vendor_manuals(tmp_path: Path) -> None:
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
    artifacts = list(tmp_path.glob("wavebench_shengpu_sp3000a-*.tar.gz"))
    assert len(artifacts) == 1
    with tarfile.open(artifacts[0]) as archive:
        members = archive.getnames()
    assert not any("/doc/vendor-local/" in member for member in members)


def test_wheel_install_discovery_and_uninstall_without_instrument_io(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
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
        cwd=tmp_path,
    )
    plugin_wheel = next(wheelhouse.glob("wavebench_shengpu_sp3000a-0.1.0-*.whl"))
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
            str(plugin_wheel),
        ],
        cwd=tmp_path,
    )
    discovery_script = """
from importlib.metadata import entry_points
from wavebench.instruments.registry import build_instrument_registry
from wavebench.transport.serial_transport import SerialTransport

def forbidden(*args, **kwargs):
    raise AssertionError("plugin descriptor import attempted instrument I/O")

SerialTransport.open = forbidden
points = list(entry_points().select(group="wavebench.instruments"))
assert [point.name for point in points] == ["shengpu.sp30120"]
descriptor = points[0].load()()
assert descriptor.driver_id == "shengpu.sp30120"
assert descriptor.distribution == "wavebench-shengpu-sp3000a"
resolved = build_instrument_registry().resolve(
    "shengpu.sp30120", expected_kind="sweep_analyzer"
)
assert resolved.origin == "entry_point"
"""
    _run([str(python), "-I", "-c", discovery_script], cwd=tmp_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "uninstall",
            "--yes",
            "wavebench-shengpu-sp3000a",
        ],
        cwd=tmp_path,
    )
    uninstall_script = """
from importlib.metadata import entry_points

assert not entry_points().select(group="wavebench.instruments")
"""
    _run([str(python), "-I", "-c", uninstall_script], cwd=tmp_path)
