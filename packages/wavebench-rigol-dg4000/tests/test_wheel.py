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
from wavebench.instruments.source_extensions import source_v2_digest
from wavebench.plugins.lifecycle import PluginLifecycle
from wavebench.plugins.package_inspect import inspect_plugin_wheel

from wavebench_rigol_dg4000 import descriptor, descriptor_v2


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = "0.7.0"
_SOURCE_DESCRIPTOR_DIGEST = "sha256:2956d875216721d37a0a9ff12ecf79a4d6b6bb1669bbd7fa3c504f56999e35ae"
_SOURCE_V2_DESCRIPTOR_DIGEST = "sha256:a0d0f347a9eea02d00ed0b6cc99884dd1fb3d5bdfb88c334683a009441c246a8"


def test_wheel_contains_license_and_expected_entry_points(tmp_path: Path) -> None:
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
        ("rigol.dg4202", "wavebench_rigol_dg4000:descriptor"),
        ("rigol.dg4202-v2", "wavebench_rigol_dg4000:descriptor_v2"),
        (
            "rigol.dg4202-v2-workspace",
            "wavebench_rigol_dg4000:descriptor_v2_workspace",
        ),
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
        "sha256:5eb021402156069ff367b4e1f8ea34dae963fcd9844bb1fa1ba6120ce872fe10"
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
        ("dg4202-v2-sweep-configure-a4", "A4", (1, 2)),
        ("dg4202-v2-sweep-fire-a4", "A4", (1, 2)),
    }


def test_source_v2_descriptor_digest_remains_bound_to_release_evidence() -> None:
    assert source_v2_digest(descriptor().source_extensions) == _SOURCE_DESCRIPTOR_DIGEST
    assert source_v2_digest(descriptor_v2().source_extensions) == _SOURCE_V2_DESCRIPTOR_DIGEST


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


def test_wheel_install_migration_doctor_routing_and_uninstall_fallback(tmp_path: Path) -> None:
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
    lifecycle = PluginLifecycle(python_executable=python)
    assert lifecycle.install(plugin_wheel).status == "installed"
    assert [
        (item.driver_id, item.status)
        for item in lifecycle.installed()
    ] == [
        ("rigol.dg4202", "healthy"),
        ("rigol.dg4202-v2", "healthy"),
        ("rigol.dg4202-v2-workspace", "healthy"),
    ]
    discovery_script = """
from importlib.metadata import entry_points
from wavebench.instruments.registry import build_instrument_registry
from wavebench.transport.pyvisa_transport import PyVisaTransport

def forbidden(*args, **kwargs):
    raise AssertionError("plugin descriptor import attempted instrument I/O")

PyVisaTransport.open = forbidden
points = list(entry_points().select(group="wavebench.instruments"))
assert [point.name for point in points] == [
    "rigol.dg4202",
    "rigol.dg4202-v2",
    "rigol.dg4202-v2-workspace",
]
descriptors = {point.name: point.load()() for point in points}
assert descriptors["rigol.dg4202"].distribution == "wavebench-rigol-dg4000"
assert descriptors["rigol.dg4202-v2"].distribution == "wavebench-rigol-dg4000"
assert descriptors["rigol.dg4202-v2-workspace"].distribution == "wavebench-rigol-dg4000"
registry = build_instrument_registry()
canonical = registry.resolve("rigol.dg4202", expected_kind="source")
advanced = registry.resolve("rigol.dg4202-v2", expected_kind="source")
workspace = registry.resolve("rigol.dg4202-v2-workspace", expected_kind="source")
alias = registry.resolve("dg4202", expected_kind="source")
assert canonical.origin == "entry_point"
assert canonical.distribution == "wavebench-rigol-dg4000"
assert advanced.origin == "entry_point"
assert advanced.distribution == "wavebench-rigol-dg4000"
assert workspace.origin == "entry_point"
assert workspace.distribution == "wavebench-rigol-dg4000"
assert alias.origin == "builtin"
"""
    _run([str(python), "-I", "-c", discovery_script], cwd=tmp_path)
    _run(
        [str(python), "-I", "-m", "wavebench", "plugin", "doctor", "--load"],
        cwd=tmp_path,
    )
    assert lifecycle.remove("rigol.dg4202-v2").status == "removed"
    assert lifecycle.installed() == ()
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
