from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import sys
import tomllib

import pytest


ROOT = Path(__file__).resolve().parents[1]
WAVEBENCH_ROOT = Path(
    os.environ.get("WAVEBENCH_CORE_ROOT", str(ROOT.parent / "wavebench"))
).resolve()
SPEC = importlib.util.spec_from_file_location("wavebench_plugin_dev_env", ROOT / "scripts/dev_env.py")
assert SPEC is not None and SPEC.loader is not None
DEV_ENV = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEV_ENV
SPEC.loader.exec_module(DEV_ENV)


def test_discovers_only_installable_plugin_packages():
    projects = DEV_ENV.discover_installable_plugins(ROOT)

    assert [project.distribution for project in projects] == [
        "wavebench-rigol-dg4000",
        "wavebench-rigol-dm3000",
        "wavebench-rigol-dp800",
        "wavebench-rigol-ds1000z",
        "wavebench-rigol-dsg830",
        "wavebench-rigol-mso8000",
        "wavebench-rohde-schwarz-rtm2000",
        "wavebench-shengpu-sp3000a",
        "wavebench-siglent-sdg2000x",
        "wavebench-siglent-sds3000",
        "wavebench-siglent-sds800x-hd",
    ]
    assert [project.driver_ids for project in projects] == [
        ("rigol.dg4202", "rigol.dg4202-v2", "rigol.dg4202-v2-workspace"),
        ("rigol.dm3000",),
        ("rigol.dp800",),
        ("rigol.ds1000z",),
        ("rigol.dsg830",),
        ("rigol.mso8104",),
        ("rohde-schwarz.rtm2032",),
        ("shengpu.sp30120",),
        ("siglent.sdg2000x",),
        ("siglent.sds3000",),
        ("siglent.sds800x-hd",),
    ]


def test_expected_state_tracks_core_and_plugin_metadata():
    state = DEV_ENV.build_expected_state(ROOT, WAVEBENCH_ROOT)

    assert state["schema_version"] == 1
    assert state["build_requirements"] == ["hatchling>=1.25"]
    assert state["wavebench"]["distribution"] == "wavebench"
    assert state["wavebench"]["version"] == tomllib.loads(
        (WAVEBENCH_ROOT / "pyproject.toml").read_text(encoding="utf-8")
    )["project"]["version"]
    assert len(state["wavebench"]["pyproject_sha256"]) == 64
    assert len(state["plugins"]) == 11
    assert all(len(plugin["pyproject_sha256"]) == 64 for plugin in state["plugins"])


def test_sync_command_uses_standard_editable_installs(tmp_path):
    state = DEV_ENV.build_expected_state(ROOT, WAVEBENCH_ROOT)
    python = tmp_path / "python"
    command = DEV_ENV.build_sync_command("uv", python, state)

    assert command[:5] == ["uv", "pip", "install", "--python", str(python)]
    assert "hatchling>=1.25" in command
    editable_targets = [
        command[index + 1] for index, item in enumerate(command) if item == "--editable"
    ]
    assert editable_targets[0] == f"{WAVEBENCH_ROOT}[dev]"
    assert editable_targets[1:] == [
        f"{ROOT / 'packages/wavebench-rigol-dg4000'}[dev]",
        f"{ROOT / 'packages/wavebench-rigol-dm3000'}[dev]",
        f"{ROOT / 'packages/wavebench-rigol-dp800'}[dev]",
        f"{ROOT / 'packages/wavebench-rigol-ds1000z'}[dev]",
        f"{ROOT / 'packages/wavebench-rigol-dsg830'}[dev]",
        f"{ROOT / 'packages/wavebench-rigol-mso8000'}[dev]",
        f"{ROOT / 'packages/wavebench-rohde-schwarz-rtm2000'}[dev]",
        f"{ROOT / 'packages/wavebench-shengpu-sp3000a'}[dev]",
        f"{ROOT / 'packages/wavebench-siglent-sdg2000x'}[dev]",
        f"{ROOT / 'packages/wavebench-siglent-sds3000'}[dev]",
        f"{ROOT / 'packages/wavebench-siglent-sds800x-hd'}[dev]",
    ]
    assert "--no-deps" not in command
    assert "--no-index" not in command


@pytest.mark.parametrize("state_name", DEV_ENV.MANAGED_STATE_NAMES)
def test_rejects_managed_plugin_state(tmp_path, state_name):
    state_root = tmp_path / ".wavebench"
    state_root.mkdir()
    (state_root / state_name).write_text("{}\n", encoding="utf-8")

    with pytest.raises(DEV_ENV.DevEnvironmentError, match="受管插件账本"):
        DEV_ENV._assert_not_managed_environment(tmp_path)


def test_missing_uv_does_not_create_environment(tmp_path, monkeypatch):
    target = tmp_path / "new environment"
    args = DEV_ENV.build_parser().parse_args(["--venv", str(target), "sync"])
    monkeypatch.setattr(DEV_ENV.shutil, "which", lambda _name: None)

    with pytest.raises(DEV_ENV.DevEnvironmentError, match="uv is required"):
        DEV_ENV.sync_environment(args)

    assert not target.exists()


def test_identifies_only_plugins_removed_from_recorded_state():
    expected = DEV_ENV.build_expected_state(ROOT, WAVEBENCH_ROOT)
    recorded = {
        **expected,
        "plugins": [
            *expected["plugins"],
            {"distribution": "wavebench-example-removed"},
        ],
    }

    assert DEV_ENV.removed_plugin_distributions(recorded, expected) == (
        "wavebench-example-removed",
    )
