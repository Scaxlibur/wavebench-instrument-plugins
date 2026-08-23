from __future__ import annotations

from importlib.metadata import PathDistribution
import os
from pathlib import Path
import subprocess
import sys
import sysconfig
import tarfile
import tomllib
from zipfile import ZipFile

import wavebench

from wavebench_siglent_sdg2000x import descriptor


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
PACKAGE_VERSION = "0.8.2"


def _run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, text=True, capture_output=True, check=True)


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
    return next(wheelhouse.glob(f"wavebench_siglent_sdg2000x-{PACKAGE_VERSION}-*.whl"))


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


def test_wheel_contains_license_dependency_and_single_entry_point(tmp_path: Path) -> None:
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
    requires_dist = distribution.metadata.get_all("Requires-Dist") or []
    assert any(
        requirement.replace(" ", "") == "wavebench<0.9,>=0.8.24"
        for requirement in requires_dist
    )
    assert [(item.name, item.value) for item in entry_points] == [
        ("siglent.sdg2000x", "wavebench_siglent_sdg2000x:descriptor")
    ]


def test_source_v2_release_version_is_consistent_in_metadata_descriptor_and_docs() -> None:
    with Path(PACKAGE_ROOT, "pyproject.toml").open("rb") as file:
        metadata = tomllib.load(file)

    assert metadata["project"]["version"] == PACKAGE_VERSION
    assert descriptor().version == PACKAGE_VERSION
    for relative_path in (
        "README.md",
        "README_EN.md",
        "doc/SDG2000X_COVERAGE_MATRIX.md",
        "doc/SDG2000X_COVERAGE_MATRIX_EN.md",
        "doc/SDG2000X_SOURCE_V2_A0.md",
        "doc/SDG2000X_SOURCE_V2_A0_EN.md",
        "doc/SDG2000X_SOURCE_V2_RELEASE_AUDIT.md",
        "doc/SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md",
    ):
        assert f"`{PACKAGE_VERSION}`" in Path(PACKAGE_ROOT, relative_path).read_text(
            encoding="utf-8"
        )


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
    sdist = next(dist_dir.glob(f"wavebench_siglent_sdg2000x-{PACKAGE_VERSION}.tar.gz"))

    with tarfile.open(sdist) as archive:
        names = archive.getnames()

    assert not any("/doc/vendor-local/" in name for name in names)
    for public_doc in (
        "SDG2000X_COVERAGE_MATRIX.md",
        "SDG2000X_COVERAGE_MATRIX_EN.md",
        "SDG2000X_COVERAGE_MILESTONES.md",
        "SDG2000X_COVERAGE_MILESTONES_EN.md",
        "SDG2000X_PROTOCOL_AUDIT.md",
        "SDG2000X_PROTOCOL_AUDIT_EN.md",
        "SDG2000X_READONLY_ACCEPTANCE.md",
        "SDG2000X_READONLY_ACCEPTANCE_EN.md",
        "SDG2000X_OUTPUT_ACCEPTANCE.md",
        "SDG2000X_OUTPUT_ACCEPTANCE_EN.md",
        "SDG2000X_SOURCE_V2_A0.md",
        "SDG2000X_SOURCE_V2_A0_EN.md",
        "SDG2000X_SOURCE_V2_RELEASE_AUDIT.md",
        "SDG2000X_SOURCE_V2_RELEASE_AUDIT_EN.md",
    ):
        assert any(name.endswith(f"/doc/{public_doc}") for name in names)


def test_wheel_install_discovery_and_uninstall_without_instrument_io(tmp_path: Path) -> None:
    wheelhouse = tmp_path / "wheelhouse"
    wheelhouse.mkdir()
    plugin_wheel = _build_wheel(wheelhouse)
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
from wavebench.instruments.source_extension_capabilities import (
    validate_source_descriptor,
    validate_source_plugin_dependencies,
)
from wavebench.transport.pyvisa_transport import PyVisaTransport

def forbidden(*args, **kwargs):
    raise AssertionError("plugin descriptor import attempted instrument I/O")

PyVisaTransport.open = forbidden
points = list(entry_points().select(group="wavebench.instruments"))
assert [point.name for point in points] == ["siglent.sdg2000x"]
item = points[0].load()()
assert item.driver_id == "siglent.sdg2000x"
assert item.distribution == "wavebench-siglent-sdg2000x"
assert item.version == "0.8.2"
assert item.capabilities == (
    "source.idn",
    "source.status",
    "source.set_frequency",
    "source.set_function",
    "source.set_amplitude_vpp",
    "source.set_square_duty_cycle",
    "source.output",
    "source.arbitrary_probe",
    "source.snapshot_v2",
    "source.basic_configure_v2",
    "source.output_v2",
    "source.harmonics_disable_v2",
)
validate_source_descriptor(item)
validate_source_plugin_dependencies(
    item,
    ("wavebench>=0.8.24,<0.9",),
)
resolved = build_instrument_registry().resolve(
    "siglent.sdg2000x", expected_kind="source"
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
            "wavebench-siglent-sdg2000x",
        ],
        cwd=tmp_path,
    )
    uninstall_script = """
from importlib.metadata import entry_points

assert not entry_points().select(group="wavebench.instruments")
"""
    _run([str(python), "-I", "-c", uninstall_script], cwd=tmp_path)
