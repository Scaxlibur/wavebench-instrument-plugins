from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import pytest


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("wavebench_plugin_dev_env", ROOT / "scripts/dev_env.py")
assert SPEC is not None and SPEC.loader is not None
DEV_ENV = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = DEV_ENV
SPEC.loader.exec_module(DEV_ENV)


def test_discovers_only_installable_plugin_packages():
    projects = DEV_ENV.discover_installable_plugins(ROOT)

    assert [project.distribution for project in projects] == [
        "wavebench-rigol-dg4000",
        "wavebench-rigol-ds1000z",
    ]
    assert [project.driver_ids for project in projects] == [
        ("rigol.dg4202",),
        ("rigol.ds1000z",),
    ]


def test_expected_state_tracks_core_and_plugin_metadata():
    state = DEV_ENV.build_expected_state(ROOT, ROOT.parent / "wavebench")

    assert state["schema_version"] == 1
    assert state["build_requirements"] == ["hatchling>=1.25"]
    assert state["wavebench"]["distribution"] == "wavebench"
    assert state["wavebench"]["version"] == "0.7.0"
    assert len(state["wavebench"]["pyproject_sha256"]) == 64
    assert len(state["plugins"]) == 2
    assert all(len(plugin["pyproject_sha256"]) == 64 for plugin in state["plugins"])


def test_sync_command_uses_standard_editable_installs():
    state = DEV_ENV.build_expected_state(ROOT, ROOT.parent / "wavebench")
    command = DEV_ENV.build_sync_command(Path("/tmp/dev/bin/python"), state)

    assert command[:4] == ["/tmp/dev/bin/python", "-m", "pip", "install"]
    assert "hatchling>=1.25" in command
    editable_targets = [
        command[index + 1] for index, item in enumerate(command) if item == "--editable"
    ]
    assert editable_targets[0].endswith("/wavebench[dev]")
    assert editable_targets[1:] == [
        f"{ROOT / 'packages/wavebench-rigol-dg4000'}[dev]",
        f"{ROOT / 'packages/wavebench-rigol-ds1000z'}[dev]",
    ]
    assert all("wavebench-shengpu-sp3000a" not in item for item in command)
    assert "--no-deps" not in command
    assert "--no-index" not in command


def test_rejects_managed_plugin_state(tmp_path):
    state_root = tmp_path / ".wavebench"
    state_root.mkdir()
    (state_root / "plugin-installs-v1.json").write_text("{}\n", encoding="utf-8")

    with pytest.raises(DEV_ENV.DevEnvironmentError, match="受管插件账本"):
        DEV_ENV._assert_not_managed_environment(tmp_path)


def test_identifies_only_plugins_removed_from_recorded_state():
    expected = DEV_ENV.build_expected_state(ROOT, ROOT.parent / "wavebench")
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
