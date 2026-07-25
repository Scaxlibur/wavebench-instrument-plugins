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


def test_managed_install_routes_canonical_and_remove_restores_builtin(tmp_path: Path):
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
    wheel = next(wheelhouse.glob("wavebench_rohde_schwarz_rtm2000-0.5.0-*.whl"))
    venv_dir = tmp_path / "venv"
    _run([sys.executable, "-m", "venv", str(venv_dir)], cwd=tmp_path)
    python = venv_dir / "bin" / "python"
    purelib = _run(
        [str(python), "-c", "import sysconfig; print(sysconfig.get_paths()['purelib'])"],
        cwd=tmp_path,
    ).stdout.strip()
    _write_isolated_runtime_bridge(purelib=Path(purelib), workspace=tmp_path)

    lifecycle = PluginLifecycle(python_executable=python)
    assert lifecycle.install(wheel).status == "installed"
    assert lifecycle.info("rohde-schwarz.rtm2032").status == "healthy"
    load_script = """
from wavebench.instruments.registry import build_instrument_registry
from wavebench.transport.rsinstrument_transport import RsInstrumentTransport

def forbidden(*args, **kwargs):
    raise AssertionError("managed plugin load attempted instrument I/O")

RsInstrumentTransport.open = forbidden
registry = build_instrument_registry()
canonical = registry.resolve("rohde-schwarz.rtm2032", expected_kind="scope")
alias = registry.resolve("rtm2032", expected_kind="scope")
assert canonical.origin == "entry_point"
assert canonical.distribution == "wavebench-rohde-schwarz-rtm2000"
assert canonical.backends == (
    "rsinstrument-socket",
    "rsinstrument",
    "rsinstrument-rsvisa",
    "rsinstrument-pyvisa-py",
)
assert canonical.resource_schemes == ("tcpip",)
assert canonical.version == "0.5.0"
assert alias.origin == "builtin"
assert alias.driver_id == "rohde-schwarz.rtm2032"
"""
    _run([str(python), "-I", "-c", load_script], cwd=tmp_path)

    assert lifecycle.remove("rohde-schwarz.rtm2032").status == "removed"
    assert lifecycle.installed() == ()
    restore_script = """
from wavebench.instruments.registry import build_instrument_registry

registry = build_instrument_registry()
canonical = registry.resolve("rohde-schwarz.rtm2032", expected_kind="scope")
alias = registry.resolve("rtm2032", expected_kind="scope")
assert canonical.origin == "builtin"
assert alias.origin == "builtin"
"""
    _run([str(python), "-I", "-c", restore_script], cwd=tmp_path)
