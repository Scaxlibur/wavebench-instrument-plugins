from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import sysconfig

import wavebench
from wavebench.plugins.lifecycle import PluginLifecycle


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


def test_managed_install_healthy_load_and_remove_round_trip(tmp_path: Path) -> None:
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
    wheel = next(wheelhouse.glob("wavebench_shengpu_sp3000a-0.1.0-*.whl"))
    venv_dir = tmp_path / "venv"
    _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=tmp_path)
    python = venv_dir / "bin" / "python"
    purelib = _run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        cwd=tmp_path,
    ).stdout.strip()
    _write_isolated_runtime_bridge(purelib=Path(purelib), workspace=tmp_path)

    lifecycle = PluginLifecycle(python_executable=python)
    result = lifecycle.install(wheel)
    installed = lifecycle.info("shengpu.sp30120")

    assert result.status == "installed"
    assert installed.distribution == "wavebench-shengpu-sp3000a"
    assert installed.version == "0.1.0"
    assert installed.status == "healthy"
    load_script = """
from wavebench.instruments.registry import build_instrument_registry
from wavebench.transport.serial_transport import SerialTransport

def forbidden(*args, **kwargs):
    raise AssertionError("managed plugin load attempted instrument I/O")

SerialTransport.open = forbidden
descriptor = build_instrument_registry().resolve(
    "shengpu.sp30120", expected_kind="sweep_analyzer"
)
assert descriptor.origin == "entry_point"
assert descriptor.distribution == "wavebench-shengpu-sp3000a"
"""
    _run([str(python), "-I", "-c", load_script], cwd=tmp_path)

    assert lifecycle.remove("shengpu.sp30120").status == "removed"
    assert lifecycle.installed() == ()
    no_entry_point_script = """
from importlib.metadata import entry_points

assert not entry_points().select(group="wavebench.instruments")
"""
    _run([str(python), "-I", "-c", no_entry_point_script], cwd=tmp_path)
