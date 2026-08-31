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
from wavebench.plugins.package_inspect import inspect_plugin_wheel


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = "0.7.0"


def test_wheel_contains_license_and_single_entry_point(tmp_path: Path) -> None:
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
    wheel = next(wheelhouse.glob(f"wavebench_rigol_dg4000-{PACKAGE_VERSION}-*.whl"))

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
    requires_dist = distribution.metadata.get_all("Requires-Dist") or []
    assert any(
        requirement.replace(" ", "") == "wavebench<0.9,>=0.8.25"
        for requirement in requires_dist
    )
    assert [(item.name, item.value) for item in entry_points] == [
        ("rigol.dg4202", "wavebench_rigol_dg4000:descriptor")
    ]


def test_wheel_contains_verified_source_conformance_manifests(tmp_path: Path) -> None:
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
    wheel = next(wheelhouse.glob(f"wavebench_rigol_dg4000-{PACKAGE_VERSION}-*.whl"))

    package = inspect_plugin_wheel(wheel)

    assert package.source_conformance_wheel_sha256 == (
        "sha256:b03d395871a8d4fc7726ffb4acd541cf643ff4dd32bcbbb2558e486e50c10eaa"
    )
    assert {
        (item.manifest_id, item.claimed_level.value, item.channels)
        for item in package.source_conformance_manifests
    } == {
        ("dg4202-basic-configure-a3", "A3", (1, 2)),
        ("dg4202-basic-read-a1", "A1", (1, 2)),
        ("dg4202-counter-configure-a2", "A2", ()),
        ("dg4202-counter-enable-a2", "A2", ()),
        ("dg4202-counter-measure-a3", "A3", ()),
        ("dg4202-output-disable-a2", "A2", (1, 2)),
        ("dg4202-output-enable-a2", "A2", (1, 2)),
        ("dg4202-output-read-a1", "A1", (1, 2)),
    }


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
    sdist = next(dist_dir.glob(f"wavebench_rigol_dg4000-{PACKAGE_VERSION}.tar.gz"))

    with tarfile.open(sdist) as archive:
        names = archive.getnames()

    assert not any("/doc/vendor-local/" in name for name in names)
    for public_doc in (
        "DG4000_COVERAGE_MATRIX.md",
        "DG4000_COVERAGE_MATRIX_EN.md",
        "DG4000_COVERAGE_MILESTONES.md",
        "DG4000_COVERAGE_MILESTONES_EN.md",
    ):
        assert any(name.endswith(f"/doc/{public_doc}") for name in names)


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
    plugin_wheel = next(
        wheelhouse.glob(f"wavebench_rigol_dg4000-{PACKAGE_VERSION}-*.whl")
    )
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
