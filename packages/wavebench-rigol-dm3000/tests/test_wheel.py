from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
import sysconfig

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


def test_wheel_install_routes_canonical_and_uninstall_restores_builtin(tmp_path: Path) -> None:
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
from wavebench.instruments.registry import build_instrument_registry
from wavebench.transport.pyvisa_transport import PyVisaTransport

def forbidden(*args, **kwargs):
    raise AssertionError("descriptor load attempted instrument I/O")

PyVisaTransport.open = forbidden
registry = build_instrument_registry()
canonical = registry.resolve("rigol.dm3000", expected_kind="dmm")
dm3000_alias = registry.resolve("dm3000", expected_kind="dmm")
dm3058_alias = registry.resolve("dm3058", expected_kind="dmm")
assert canonical.origin == "entry_point"
assert canonical.distribution == "wavebench-rigol-dm3000"
assert canonical.backends == ("pyvisa",)
assert dm3000_alias.origin == "builtin"
assert dm3058_alias.origin == "builtin"
assert dm3000_alias.backends == ("serial", "pyvisa")
assert dm3058_alias.backends == ("serial", "pyvisa")
"""
    _run([str(python), "-I", "-c", discovery_script], cwd=tmp_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "uninstall",
            "--yes",
            "wavebench-rigol-dm3000",
        ],
        cwd=tmp_path,
    )
    uninstall_script = """
from wavebench.instruments.registry import build_instrument_registry

registry = build_instrument_registry()
canonical = registry.resolve("rigol.dm3000", expected_kind="dmm")
assert canonical.origin == "builtin"
assert canonical.backends == ("serial", "pyvisa")
"""
    _run([str(python), "-I", "-c", uninstall_script], cwd=tmp_path)
