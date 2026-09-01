from __future__ import annotations

from pathlib import Path
import sys

from _shengpu_sp3000a_wheel_helpers import _run, _write_isolated_runtime_bridge
from wavebench.plugins.lifecycle import PluginLifecycle


PACKAGE_ROOT = Path(__file__).resolve().parents[1]

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
    wheel = next(wheelhouse.glob("wavebench_shengpu_sp3000a-0.2.0-*.whl"))
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
    assert installed.version == "0.2.0"
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
