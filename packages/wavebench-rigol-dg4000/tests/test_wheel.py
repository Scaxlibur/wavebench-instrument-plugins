from __future__ import annotations

from pathlib import Path
import subprocess
import sys
import sysconfig

import wavebench


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        text=True,
        capture_output=True,
        check=True,
    )


def test_wheel_install_migration_routing_and_uninstall_fallback(tmp_path: Path) -> None:
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
    plugin_wheel = next(wheelhouse.glob("wavebench_rigol_dg4000-0.1.0-*.whl"))
    venv_dir = tmp_path / "venv"
    _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=tmp_path)
    python = venv_dir / "bin" / "python"
    purelib = _run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        cwd=tmp_path,
    ).stdout.strip()
    Path(purelib, "wavebench-test-runtime.pth").write_text(
        str(Path(wavebench.__file__).resolve().parents[1])
        + "\n"
        + sysconfig.get_paths()["purelib"]
        + "\n",
        encoding="utf-8",
    )
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
from wavebench.transport.pyvisa_transport import PyVisaTransport

def forbidden(*args, **kwargs):
    raise AssertionError("plugin descriptor import attempted instrument I/O")

PyVisaTransport.open = forbidden
points = list(entry_points().select(group="wavebench.instruments"))
assert [point.name for point in points] == ["rigol.dg4202"]
descriptor = points[0].load()()
assert descriptor.distribution == "wavebench-rigol-dg4000"
registry = build_instrument_registry()
canonical = registry.resolve("rigol.dg4202", expected_kind="source")
alias = registry.resolve("dg4202", expected_kind="source")
assert canonical.origin == "entry_point"
assert canonical.distribution == "wavebench-rigol-dg4000"
assert alias.origin == "builtin"
"""
    _run([str(python), "-I", "-c", discovery_script], cwd=tmp_path)
    _run(
        [
            str(python),
            "-m",
            "pip",
            "uninstall",
            "--yes",
            "wavebench-rigol-dg4000",
        ],
        cwd=tmp_path,
    )
    uninstall_script = """
from importlib.metadata import entry_points
from wavebench.instruments.registry import build_instrument_registry

assert not entry_points().select(group="wavebench.instruments")
registry = build_instrument_registry()
canonical = registry.resolve("rigol.dg4202", expected_kind="source")
alias = registry.resolve("dg4202", expected_kind="source")
assert canonical.origin == "builtin"
assert alias.origin == "builtin"
"""
    _run([str(python), "-I", "-c", uninstall_script], cwd=tmp_path)
