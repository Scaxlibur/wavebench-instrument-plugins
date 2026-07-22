#!/usr/bin/env python3
"""Create and verify the repository's standard editable development environment."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib


ENTRY_POINT_GROUP = "wavebench.instruments"
STATE_SCHEMA_VERSION = 1
STATE_FILE = ".wavebench-plugin-dev-state-v1.json"
MARKER_FILE = ".wavebench-plugin-dev-env"
MANAGED_STATE_NAMES = (
    "plugin-installs-v1.json",
    "plugin-transaction-v1.json",
)


class DevEnvironmentError(RuntimeError):
    """Raised for an invalid or unsafe development-environment operation."""


@dataclass(frozen=True)
class EditableProject:
    path: Path
    distribution: str
    version: str
    driver_ids: tuple[str, ...]
    build_requirements: tuple[str, ...]
    pyproject_sha256: str


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _load_project(path: Path, *, require_entry_point: bool) -> EditableProject:
    pyproject = path / "pyproject.toml"
    if not pyproject.is_file():
        raise DevEnvironmentError(f"missing pyproject.toml / 缺少 pyproject.toml: {path}")
    with pyproject.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project")
    if not isinstance(project, dict):
        raise DevEnvironmentError(f"missing [project] table / 缺少 [project] 表: {pyproject}")
    distribution = project.get("name")
    version = project.get("version")
    if not isinstance(distribution, str) or not isinstance(version, str):
        raise DevEnvironmentError(
            f"project name/version must be strings / 项目名称和版本必须是字符串: {pyproject}"
        )
    groups = project.get("entry-points", {})
    entries = groups.get(ENTRY_POINT_GROUP, {}) if isinstance(groups, dict) else {}
    if not isinstance(entries, dict):
        raise DevEnvironmentError(
            f"invalid {ENTRY_POINT_GROUP} table / 无效的入口点表: {pyproject}"
        )
    driver_ids = tuple(sorted(str(name) for name in entries))
    if require_entry_point and not driver_ids:
        raise DevEnvironmentError(
            f"installable package has no {ENTRY_POINT_GROUP} entry point / "
            f"可安装包缺少仪器入口点: {pyproject}"
        )
    build_system = data.get("build-system", {})
    raw_build_requirements = (
        build_system.get("requires", []) if isinstance(build_system, dict) else []
    )
    if not isinstance(raw_build_requirements, list) or not all(
        isinstance(item, str) for item in raw_build_requirements
    ):
        raise DevEnvironmentError(
            f"invalid [build-system].requires / 无效的构建依赖: {pyproject}"
        )
    return EditableProject(
        path=path.resolve(),
        distribution=distribution,
        version=version,
        driver_ids=driver_ids,
        build_requirements=tuple(raw_build_requirements),
        pyproject_sha256=_sha256(pyproject),
    )


def discover_installable_plugins(repository_root: Path) -> tuple[EditableProject, ...]:
    packages_root = repository_root / "packages"
    plugins = []
    for candidate in sorted(packages_root.iterdir()):
        if candidate.is_dir() and (candidate / "pyproject.toml").is_file():
            plugins.append(_load_project(candidate, require_entry_point=True))
    if not plugins:
        raise DevEnvironmentError(
            "no installable plugin packages found / 未发现带 pyproject.toml 的可安装插件包"
        )
    return tuple(plugins)


def build_expected_state(
    repository_root: Path,
    wavebench_root: Path,
) -> dict[str, object]:
    core = _load_project(wavebench_root, require_entry_point=False)
    if core.distribution != "wavebench":
        raise DevEnvironmentError(
            f"expected WaveBench core project, found {core.distribution!r} / "
            "指定目录不是 WaveBench 核心仓库"
        )
    plugins = discover_installable_plugins(repository_root)
    build_requirements = sorted(
        {requirement for item in (core, *plugins) for requirement in item.build_requirements}
    )
    return {
        "schema_version": STATE_SCHEMA_VERSION,
        "build_requirements": build_requirements,
        "wavebench": {
            "path": str(core.path),
            "distribution": core.distribution,
            "version": core.version,
            "pyproject_sha256": core.pyproject_sha256,
        },
        "plugins": [
            {
                "path": str(plugin.path),
                "distribution": plugin.distribution,
                "version": plugin.version,
                "driver_ids": list(plugin.driver_ids),
                "pyproject_sha256": plugin.pyproject_sha256,
            }
            for plugin in plugins
        ],
    }


def build_sync_command(venv_python: Path, state: dict[str, object]) -> list[str]:
    core = state["wavebench"]
    assert isinstance(core, dict)
    plugins = state["plugins"]
    assert isinstance(plugins, list)
    command = [
        str(venv_python),
        "-m",
        "pip",
        "install",
        "--disable-pip-version-check",
        "--upgrade-strategy",
        "only-if-needed",
    ]
    requirements = state["build_requirements"]
    assert isinstance(requirements, list)
    command.extend(str(requirement) for requirement in requirements)
    command.extend(("--editable", f"{core['path']}[dev]"))
    for plugin in plugins:
        assert isinstance(plugin, dict)
        command.extend(("--editable", f"{plugin['path']}[dev]"))
    return command


def removed_plugin_distributions(
    recorded: dict[str, object] | None,
    expected: dict[str, object],
) -> tuple[str, ...]:
    if not recorded:
        return ()
    recorded_plugins = recorded.get("plugins", [])
    expected_plugins = expected.get("plugins", [])
    if not isinstance(recorded_plugins, list) or not isinstance(expected_plugins, list):
        raise DevEnvironmentError(
            "invalid development environment state / 无效的开发环境状态"
        )
    old = {
        str(plugin["distribution"])
        for plugin in recorded_plugins
        if isinstance(plugin, dict) and isinstance(plugin.get("distribution"), str)
    }
    current = {
        str(plugin["distribution"])
        for plugin in expected_plugins
        if isinstance(plugin, dict) and isinstance(plugin.get("distribution"), str)
    }
    return tuple(sorted(old - current))


def _venv_python(venv: Path) -> Path:
    relative = Path("Scripts/python.exe") if sys.platform == "win32" else Path("bin/python")
    return venv / relative


def _assert_not_managed_environment(venv: Path) -> None:
    state_root = venv / ".wavebench"
    conflicts = [name for name in MANAGED_STATE_NAMES if (state_root / name).exists()]
    if conflicts:
        raise DevEnvironmentError(
            "refusing to mix editable development installs with WaveBench managed state: "
            f"{', '.join(conflicts)} / 拒绝与受管插件账本或事务混用"
        )


def _write_json_atomic(path: Path, payload: dict[str, object]) -> None:
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_text(
        json.dumps(payload, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def _probe_environment(venv_python: Path, state: dict[str, object]) -> dict[str, object]:
    script = r'''
import json
import os
import re
from importlib import metadata
from pathlib import Path
from packaging.requirements import Requirement
from urllib.parse import unquote, urlparse

from wavebench.instruments.registry import build_instrument_registry


def normalize(value):
    return re.sub(r"[-_.]+", "-", value).lower()


expected = json.loads(os.environ["WAVEBENCH_DEV_EXPECTED"])
for text in expected["build_requirements"]:
    requirement = Requirement(text)
    installed_version = metadata.version(requirement.name)
    if requirement.specifier and installed_version not in requirement.specifier:
        raise RuntimeError(
            f"build requirement {requirement} is not satisfied by {installed_version}"
        )
projects = [expected["wavebench"], *expected["plugins"]]
installed = {}
for project in projects:
    distribution = metadata.distribution(project["distribution"])
    if distribution.version != project["version"]:
        raise RuntimeError(
            f"{project['distribution']} version {distribution.version} != {project['version']}"
        )
    direct_url_text = distribution.read_text("direct_url.json")
    if not direct_url_text:
        raise RuntimeError(f"{project['distribution']} has no direct_url.json")
    direct_url = json.loads(direct_url_text)
    if direct_url.get("dir_info", {}).get("editable") is not True:
        raise RuntimeError(f"{project['distribution']} is not installed editable")
    parsed = urlparse(direct_url.get("url", ""))
    if parsed.scheme != "file":
        raise RuntimeError(f"{project['distribution']} has a non-file editable source")
    installed_path = Path(unquote(parsed.path)).resolve()
    expected_path = Path(project["path"]).resolve()
    if installed_path != expected_path:
        raise RuntimeError(
            f"{project['distribution']} points to {installed_path}, expected {expected_path}"
        )
    installed[project["distribution"]] = distribution.version

entry_points = {}
for entry_point in metadata.entry_points(group="wavebench.instruments"):
    distribution = getattr(entry_point, "dist", None)
    entry_points.setdefault(entry_point.name, []).append(
        None if distribution is None else distribution.metadata.get("Name")
    )

expected_entry_points = {
    driver_id: normalize(plugin["distribution"])
    for plugin in expected["plugins"]
    for driver_id in plugin["driver_ids"]
}
actual_entry_points = {
    driver_id: [normalize(item or "") for item in owners]
    for driver_id, owners in entry_points.items()
}
expected_owners = {driver_id: [owner] for driver_id, owner in expected_entry_points.items()}
if actual_entry_points != expected_owners:
    raise RuntimeError(
        f"instrument entry points {actual_entry_points!r} != {expected_owners!r}"
    )

registry = build_instrument_registry(include_entry_points=True)
resolved = {}
for plugin in expected["plugins"]:
    for driver_id in plugin["driver_ids"]:
        owners = entry_points.get(driver_id, [])
        if [normalize(item or "") for item in owners] != [normalize(plugin["distribution"])]:
            raise RuntimeError(
                f"entry point {driver_id} owners {owners!r} != {plugin['distribution']!r}"
            )
        descriptor = registry.resolve(driver_id)
        if descriptor.origin != "entry_point":
            raise RuntimeError(f"{driver_id} resolved to {descriptor.origin}, not entry_point")
        if normalize(descriptor.distribution or "") != normalize(plugin["distribution"]):
            raise RuntimeError(
                f"{driver_id} resolved distribution {descriptor.distribution!r}"
            )
        resolved[driver_id] = descriptor.distribution

print(json.dumps({"installed": installed, "resolved": resolved}, sort_keys=True))
'''
    environment = dict(os.environ)
    environment["WAVEBENCH_DEV_EXPECTED"] = json.dumps(state, sort_keys=True)
    result = subprocess.run(
        [str(venv_python), "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=environment,
    )
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or "unknown probe failure"
        raise DevEnvironmentError(
            f"development environment probe failed / 开发环境探测失败:\n{detail}"
        )
    return json.loads(result.stdout)


def sync_environment(args: argparse.Namespace) -> None:
    repository_root = _repository_root()
    wavebench_root = args.wavebench_root.resolve()
    venv = args.venv.resolve()
    expected = build_expected_state(repository_root, wavebench_root)
    created = False
    if not venv.exists():
        subprocess.run([str(args.python), "-m", "venv", str(venv)], check=True)
        created = True
    elif not (venv / MARKER_FILE).is_file() and not args.adopt_existing:
        raise DevEnvironmentError(
            f"existing environment is not marked as this repository's dev environment: {venv}; "
            "pass --adopt-existing only after reviewing it / 已有环境未标记，审阅后方可显式接管"
        )
    try:
        _assert_not_managed_environment(venv)
        venv_python = _venv_python(venv)
        if not venv_python.is_file():
            raise DevEnvironmentError(f"virtualenv Python not found / 未找到虚拟环境 Python: {venv}")
        print(
            "Syncing editable WaveBench and plugin packages; pip may access configured indexes.\n"
            "正在同步 editable 核心与插件；pip 可能访问已配置的软件源。"
        )
        recorded = None
        if (venv / STATE_FILE).is_file():
            recorded = json.loads((venv / STATE_FILE).read_text(encoding="utf-8"))
        removed = removed_plugin_distributions(recorded, expected)
        if removed:
            subprocess.run(
                [str(venv_python), "-m", "pip", "uninstall", "--yes", *removed],
                check=True,
            )
        subprocess.run(build_sync_command(venv_python, expected), check=True)
        probe = _probe_environment(venv_python, expected)
        (venv / MARKER_FILE).write_text("wavebench-plugin-dev-env-v1\n", encoding="utf-8")
        _write_json_atomic(venv / STATE_FILE, expected)
    except Exception:
        if created:
            shutil.rmtree(venv, ignore_errors=True)
        raise
    print(
        f"Editable development environment is ready: {venv}\n"
        f"Editable 开发环境已就绪：{venv}\n"
        f"Resolved drivers / 已解析驱动：{', '.join(sorted(probe['resolved']))}"
    )


def check_environment(args: argparse.Namespace) -> None:
    repository_root = _repository_root()
    wavebench_root = args.wavebench_root.resolve()
    venv = args.venv.resolve()
    expected = build_expected_state(repository_root, wavebench_root)
    if not (venv / MARKER_FILE).is_file() or not (venv / STATE_FILE).is_file():
        raise DevEnvironmentError(
            "development environment has not been synchronized; run sync / "
            "开发环境尚未同步，请先运行 sync"
        )
    _assert_not_managed_environment(venv)
    recorded = json.loads((venv / STATE_FILE).read_text(encoding="utf-8"))
    if recorded != expected:
        raise DevEnvironmentError(
            "project metadata or package set changed; run sync again / "
            "项目元数据或正式包集合已变化，请重新运行 sync"
        )
    probe = _probe_environment(_venv_python(venv), expected)
    print(
        f"Editable development environment is healthy: {venv}\n"
        f"Editable 开发环境健康：{venv}\n"
        f"Resolved drivers / 已解析驱动：{', '.join(sorted(probe['resolved']))}"
    )


def build_parser() -> argparse.ArgumentParser:
    repository_root = _repository_root()
    parser = argparse.ArgumentParser(
        description=(
            "Create or verify the standard editable WaveBench plugin development environment. "
            "/ 创建或检查标准 editable 插件开发环境。"
        )
    )
    parser.add_argument(
        "--venv",
        type=Path,
        default=repository_root / ".venv",
        help="development virtualenv path / 开发虚拟环境路径",
    )
    parser.add_argument(
        "--wavebench-root",
        type=Path,
        default=repository_root.parent / "wavebench",
        help="WaveBench core source checkout / WaveBench 核心源码目录",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    sync = subparsers.add_parser(
        "sync", help="create/update editable installs / 创建或更新 editable 安装"
    )
    sync.add_argument(
        "--python",
        type=Path,
        default=Path(sys.executable),
        help="base Python used to create a new virtualenv / 用于创建新环境的基础 Python",
    )
    sync.add_argument(
        "--adopt-existing",
        action="store_true",
        help="explicitly adopt an unmarked existing virtualenv / 显式接管未标记的现有虚拟环境",
    )
    sync.set_defaults(handler=sync_environment)
    check = subparsers.add_parser(
        "check", help="verify metadata, editable installs, and entry points / 检查元数据与入口点"
    )
    check.set_defaults(handler=check_environment)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        args.handler(args)
    except (DevEnvironmentError, OSError, subprocess.CalledProcessError) as exc:
        print(f"Development environment error / 开发环境错误: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
