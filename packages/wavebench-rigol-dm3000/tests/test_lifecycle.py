from __future__ import annotations

from pathlib import Path
import sys

from _rigol_dm3000_wheel_helpers import _run, _write_isolated_runtime_bridge
from wavebench.plugins.lifecycle import PluginLifecycle


PACKAGE_ROOT = Path(__file__).resolve().parents[1]

def test_managed_install_routes_canonical_and_remove_restores_builtin(tmp_path: Path) -> None:
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
    wheel = next(wheelhouse.glob("wavebench_rigol_dm3000-0.5.0-*.whl"))
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
    installed = lifecycle.info("rigol.dm3000")

    assert result.status == "installed"
    assert installed.distribution == "wavebench-rigol-dm3000"
    assert installed.version == "0.5.0"
    assert installed.status == "healthy"
    load_script = """
from wavebench.errors import ConfigError
from wavebench.instruments.factory import open_instrument_driver
from wavebench.instruments.registry import build_instrument_registry
from wavebench.logging import CommandLogger
from wavebench.transport.pyvisa_transport import PyVisaTransport

def forbidden(*args, **kwargs):
    raise AssertionError("managed plugin load attempted instrument I/O")

PyVisaTransport.open = forbidden
registry = build_instrument_registry()
canonical = registry.resolve("rigol.dm3000", expected_kind="dmm")
dm3058_alias = registry.resolve("dm3058", expected_kind="dmm")
assert canonical.origin == "entry_point"
assert canonical.distribution == "wavebench-rigol-dm3000"
assert canonical.backends == ("pyvisa",)
assert dm3058_alias.origin == "builtin"
assert dm3058_alias.backends == ("serial", "pyvisa")
try:
    open_instrument_driver(
        driver_reference="rigol.dm3000",
        expected_kind="dmm",
        resource="/dev/serial/by-id/example",
        configured_backend="serial",
        timeout_ms=1000,
        opc_timeout_ms=1000,
        read_retry_attempts=1,
        read_retry_delay_ms=10,
        logger=CommandLogger(),
    )
except ConfigError as exc:
    assert "configured backend 'serial' is not supported" in str(exc)
else:
    raise AssertionError("LAN-only canonical driver accepted serial backend")
"""
    _run([str(python), "-I", "-c", load_script], cwd=tmp_path)

    assert lifecycle.remove("rigol.dm3000").status == "removed"
    assert lifecycle.installed() == ()
    restore_script = """
from wavebench.instruments.registry import build_instrument_registry

descriptor = build_instrument_registry().resolve("rigol.dm3000", expected_kind="dmm")
assert descriptor.origin == "builtin"
assert descriptor.backends == ("serial", "pyvisa")
"""
    _run([str(python), "-I", "-c", restore_script], cwd=tmp_path)
