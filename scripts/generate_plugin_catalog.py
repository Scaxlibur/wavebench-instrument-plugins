#!/usr/bin/env python3
"""Generate the plugin catalog from package metadata and descriptor source."""

from __future__ import annotations

import argparse
import ast
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any


ENTRY_POINT_GROUP = "wavebench.instruments"
OUTPUTS = {
    "zh": Path("doc/reference/plugin-catalog.md"),
    "en": Path("doc/reference/plugin-catalog-en.md"),
}
DESCRIPTOR_FIELDS = {
    "driver_id",
    "kind",
    "display_name",
    "manufacturer",
    "models",
    "capabilities",
    "backends",
    "resource_schemes",
    "summary",
    "wavebench_min_version",
    "wavebench_max_version",
    "distribution",
    "version",
    "source",
}
REQUIRED_DESCRIPTOR_FIELDS = DESCRIPTOR_FIELDS - {"resource_schemes"}
KIND_ZH = {
    "dmm": "数字万用表",
    "power": "直流电源",
    "rf_source": "射频信号源",
    "scope": "示波器",
    "source": "信号源",
    "sweep_analyzer": "扫频仪",
}


class CatalogError(RuntimeError):
    """Raised when package metadata cannot be rendered without guessing."""


@dataclass(frozen=True)
class PluginRecord:
    package_dir: str
    distribution: str
    version: str
    requires_python: str
    wavebench_requirement: str
    entry_point: str
    driver_id: str
    kind: str
    display_name: str
    manufacturer: str
    models: tuple[str, ...]
    capabilities: tuple[str, ...]
    backends: tuple[str, ...]
    resource_schemes: tuple[str, ...]


def _repository_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _call_name(node: ast.expr) -> str | None:
    return node.id if isinstance(node, ast.Name) else None


def _value(node: ast.expr, environment: dict[str, Any]) -> Any:
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, ast.Name):
        try:
            return environment[node.id]
        except KeyError as error:
            raise CatalogError(f"unsupported descriptor name: {node.id}") from error
    if isinstance(node, ast.Attribute):
        base = _value(node.value, environment)
        if isinstance(base, dict) and node.attr in base:
            return base[node.attr]
        raise CatalogError(f"unsupported descriptor attribute: {ast.unparse(node)}")
    if isinstance(node, (ast.Tuple, ast.List)):
        values: list[Any] = []
        for element in node.elts:
            if isinstance(element, ast.Starred):
                expanded = _value(element.value, environment)
                if not isinstance(expanded, (tuple, list)):
                    raise CatalogError("descriptor starred value is not a sequence")
                values.extend(expanded)
            else:
                values.append(_value(element, environment))
        return tuple(values)
    if isinstance(node, ast.GeneratorExp):
        return _generator_value(node, environment)
    if isinstance(node, ast.Compare):
        return _compare_value(node, environment)
    raise CatalogError(f"unsupported descriptor expression: {ast.unparse(node)}")


def _generator_value(node: ast.GeneratorExp, environment: dict[str, Any]) -> tuple[Any, ...]:
    if len(node.generators) != 1:
        raise CatalogError("descriptor generator must contain one comprehension")
    generator = node.generators[0]
    if generator.is_async or not isinstance(generator.target, ast.Name):
        raise CatalogError("unsupported descriptor generator target")
    values = _value(generator.iter, environment)
    result: list[Any] = []
    for item in values:
        local = {**environment, generator.target.id: item}
        if all(_value(condition, local) for condition in generator.ifs):
            result.append(_value(node.elt, local))
    return tuple(result)


def _compare_value(node: ast.Compare, environment: dict[str, Any]) -> bool:
    if len(node.ops) != 1 or len(node.comparators) != 1:
        raise CatalogError("descriptor comparison must contain one operator")
    left = _value(node.left, environment)
    right = _value(node.comparators[0], environment)
    operator = node.ops[0]
    if isinstance(operator, ast.Eq):
        return left == right
    if isinstance(operator, ast.NotEq):
        return left != right
    raise CatalogError(f"unsupported descriptor comparison: {ast.unparse(node)}")


def _descriptor_fields(tree: ast.Module, function_name: str, cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    if function_name in cache:
        return cache[function_name]
    function = next(
        (
            node
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == function_name
        ),
        None,
    )
    if function is None or isinstance(function, ast.AsyncFunctionDef):
        raise CatalogError(f"descriptor factory not found: {function_name}")

    environment: dict[str, Any] = {}
    for statement in function.body:
        if (
            isinstance(statement, ast.Assign)
            and len(statement.targets) == 1
            and isinstance(statement.targets[0], ast.Name)
            and isinstance(statement.value, ast.Call)
        ):
            called = _call_name(statement.value.func)
            if called and not statement.value.args and not statement.value.keywords:
                environment[statement.targets[0].id] = _descriptor_fields(tree, called, cache)
        if isinstance(statement, ast.Return) and isinstance(statement.value, ast.Call):
            fields = _returned_descriptor(statement.value, environment)
            missing = REQUIRED_DESCRIPTOR_FIELDS - fields.keys()
            if missing:
                raise CatalogError(
                    f"descriptor {function_name} is missing fields: {', '.join(sorted(missing))}"
                )
            fields.setdefault("resource_schemes", ())
            cache[function_name] = fields
            return fields
    raise CatalogError(f"descriptor factory has no supported return: {function_name}")


def _returned_descriptor(call: ast.Call, environment: dict[str, Any]) -> dict[str, Any]:
    called = _call_name(call.func)
    if called == "InstrumentDescriptor":
        fields: dict[str, Any] = {}
    elif called == "replace" and call.args:
        base = _value(call.args[0], environment)
        if not isinstance(base, dict):
            raise CatalogError("descriptor replace base is not a descriptor")
        fields = dict(base)
    else:
        raise CatalogError(f"unsupported descriptor constructor: {ast.unparse(call.func)}")

    for keyword in call.keywords:
        if keyword.arg in DESCRIPTOR_FIELDS:
            fields[keyword.arg] = _value(keyword.value, environment)
    return fields


def _exported_factory(init_path: Path, factory_name: str) -> bool:
    tree = ast.parse(init_path.read_text(encoding="utf-8"), filename=str(init_path))
    return any(
        isinstance(node, ast.ImportFrom)
        and node.level == 1
        and node.module == "descriptor"
        and any(alias.name == factory_name for alias in node.names)
        for node in tree.body
    )


def _version_tuple(value: str) -> tuple[int, int, int]:
    parts = value.split(".")
    if not 1 <= len(parts) <= 3 or any(not part.isdigit() for part in parts):
        raise CatalogError(f"unsupported version constraint: {value}")
    return tuple(int(part) for part in (*parts, *("0" for _ in range(3 - len(parts)))))  # type: ignore[return-value]


def _requirement_bounds(requirement: str) -> tuple[tuple[int, int, int], tuple[int, int, int]]:
    minimum = re.search(r"(?:^|,)>=(\d+(?:\.\d+){0,2})(?:,|$)", requirement)
    maximum = re.search(r"(?:^|,)<(\d+(?:\.\d+){0,2})(?:,|$)", requirement)
    if not minimum or not maximum:
        raise CatalogError(f"WaveBench requirement needs >= and < bounds: {requirement}")
    return _version_tuple(minimum.group(1)), _version_tuple(maximum.group(1))


def _project_record(package_root: Path) -> list[PluginRecord]:
    pyproject_path = package_root / "pyproject.toml"
    with pyproject_path.open("rb") as handle:
        data = tomllib.load(handle)
    project = data.get("project")
    if not isinstance(project, dict):
        raise CatalogError(f"missing [project]: {pyproject_path}")

    distribution = project.get("name")
    version = project.get("version")
    requires_python = project.get("requires-python")
    dependencies = project.get("dependencies")
    groups = project.get("entry-points")
    entries = groups.get(ENTRY_POINT_GROUP) if isinstance(groups, dict) else None
    if not all(isinstance(value, str) for value in (distribution, version, requires_python)):
        raise CatalogError(f"invalid project name/version/requires-python: {pyproject_path}")
    if not isinstance(dependencies, list) or not all(isinstance(item, str) for item in dependencies):
        raise CatalogError(f"invalid project dependencies: {pyproject_path}")
    if not isinstance(entries, dict) or not entries:
        raise CatalogError(f"missing {ENTRY_POINT_GROUP} entry points: {pyproject_path}")
    wavebench_requirements = [item for item in dependencies if item.startswith("wavebench")]
    if len(wavebench_requirements) != 1:
        raise CatalogError(f"expected one WaveBench dependency: {pyproject_path}")
    wavebench_requirement = wavebench_requirements[0].removeprefix("wavebench")
    dependency_bounds = _requirement_bounds(wavebench_requirement)

    descriptor_trees: dict[Path, ast.Module] = {}
    descriptor_caches: dict[Path, dict[str, dict[str, Any]]] = {}
    records: list[PluginRecord] = []
    for entry_name, target in sorted(entries.items()):
        if not isinstance(entry_name, str) or not isinstance(target, str) or ":" not in target:
            raise CatalogError(f"invalid entry point in {pyproject_path}: {entry_name!r}")
        module_name, factory_name = target.split(":", 1)
        module_root = package_root / "src" / Path(*module_name.split("."))
        init_path = module_root / "__init__.py"
        descriptor_path = module_root / "descriptor.py"
        if not init_path.is_file() or not descriptor_path.is_file():
            raise CatalogError(f"entry-point module source not found: {target}")
        if not _exported_factory(init_path, factory_name):
            raise CatalogError(f"entry-point factory is not re-exported: {target}")
        tree = descriptor_trees.setdefault(
            descriptor_path,
            ast.parse(descriptor_path.read_text(encoding="utf-8"), filename=str(descriptor_path)),
        )
        cache = descriptor_caches.setdefault(descriptor_path, {})
        fields = _descriptor_fields(tree, factory_name, cache)

        if fields["driver_id"] != entry_name:
            raise CatalogError(f"driver ID differs from entry point: {entry_name} != {fields['driver_id']}")
        if fields["distribution"] != distribution or fields["version"] != version:
            raise CatalogError(f"descriptor package metadata drift: {entry_name}")
        if fields["source"] != f"entry_point:{entry_name}":
            raise CatalogError(f"descriptor source differs from entry point: {entry_name}")
        descriptor_bounds = (
            _version_tuple(fields["wavebench_min_version"]),
            _version_tuple(fields["wavebench_max_version"]),
        )
        if descriptor_bounds != dependency_bounds:
            raise CatalogError(f"WaveBench compatibility drift: {entry_name}")

        records.append(
            PluginRecord(
                package_dir=package_root.name,
                distribution=distribution,
                version=version,
                requires_python=requires_python,
                wavebench_requirement=wavebench_requirement,
                entry_point=target,
                driver_id=fields["driver_id"],
                kind=fields["kind"],
                display_name=fields["display_name"],
                manufacturer=fields["manufacturer"],
                models=tuple(fields["models"]),
                capabilities=tuple(fields["capabilities"]),
                backends=tuple(fields["backends"]),
                resource_schemes=tuple(fields["resource_schemes"]),
            )
        )
    return records


def discover_records(root: Path) -> tuple[PluginRecord, ...]:
    packages_root = root / "packages"
    records: list[PluginRecord] = []
    for package_root in sorted(packages_root.iterdir()):
        if package_root.is_dir() and (package_root / "pyproject.toml").is_file():
            records.extend(_project_record(package_root))
    if not records:
        raise CatalogError("no plugin packages found")
    return tuple(sorted(records, key=lambda item: (item.distribution, item.driver_id)))


def _joined(values: tuple[str, ...]) -> str:
    return ", ".join(f"`{value}`" for value in values) if values else "—"


def render(records: tuple[PluginRecord, ...], language: str) -> str:
    if language not in {"zh", "en"}:
        raise CatalogError(f"unsupported language: {language}")
    english = language == "en"
    lines = [
        "# WaveBench plugin catalog" if english else "# WaveBench 插件目录",
        "",
        "[中文](plugin-catalog.md)" if english else "[English](plugin-catalog-en.md)",
        "",
    ]
    if english:
        lines.extend(
            [
                "This Reference is generated from each package's `pyproject.toml` and production descriptor.",
                "Regenerate it with `python scripts/generate_plugin_catalog.py`; verify drift with",
                "`python scripts/generate_plugin_catalog.py --check`.",
                "",
                "> A metadata version identifies the package source contract in this repository; it is not a",
                "> PyPI, Git tag, or GitHub Release claim. Declared capabilities are top-level descriptor",
                "> entries. Model, firmware, option, and profile restrictions remain in the package Reference",
                "> and the runtime capability query.",
                "",
                "## Packages and entry points",
                "",
                "| Package | Metadata version | Driver ID | Type | Models | Python | WaveBench |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
    else:
        lines.extend(
            [
                "本 Reference 由各包的 `pyproject.toml` 和 production descriptor 生成。运行",
                "`python scripts/generate_plugin_catalog.py` 更新，运行",
                "`python scripts/generate_plugin_catalog.py --check` 检查漂移。",
                "",
                "> 元数据版本表示本仓库内的包源码合同，不代表 PyPI、Git tag 或 GitHub Release 状态。",
                "> capability 列表只表示 descriptor 顶层声明；型号、固件、选件和 profile 限制仍以包级",
                "> Reference 与运行时 capability 查询为准。",
                "",
                "## 包与入口点",
                "",
                "| 包 | 元数据版本 | Driver ID | 类型 | 型号 | Python | WaveBench |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )

    for record in records:
        readme = "README_EN.md" if english else "README.md"
        link = f"../../packages/{record.package_dir}/{readme}"
        kind = record.kind if english else KIND_ZH.get(record.kind, record.kind)
        models = ", ".join(record.models)
        lines.append(
            f"| [`{record.distribution}`]({link}) | `{record.version}` | `{record.driver_id}` | "
            f"{kind} | {models} | `{record.requires_python}` | `wavebench{record.wavebench_requirement}` |"
        )

    lines.extend(["", "## Declared capabilities" if english else "## 已声明 capability", ""])
    for record in records:
        lines.extend(
            [
                f"### `{record.driver_id}`",
                "",
                (f"- Display name: {record.display_name}" if english else f"- 显示名称：{record.display_name}"),
                (f"- Backends: {_joined(record.backends)}" if english else f"- Backend：{_joined(record.backends)}"),
                (
                    f"- Resource schemes: {_joined(record.resource_schemes)}"
                    if english
                    else f"- Resource scheme：{_joined(record.resource_schemes)}"
                ),
                "- Capabilities:",
                "",
            ]
        )
        lines.extend(f"  - `{capability}`" for capability in record.capabilities)
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def write_outputs(root: Path, rendered: dict[str, str], *, check: bool) -> None:
    stale: list[Path] = []
    for language, relative in OUTPUTS.items():
        destination = root / relative
        body = rendered[language]
        if check:
            if not destination.is_file() or destination.read_text(encoding="utf-8") != body:
                stale.append(relative)
            continue
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.tmp")
        temporary.write_text(body, encoding="utf-8")
        temporary.replace(destination)
    if stale:
        raise CatalogError("generated catalog is stale: " + ", ".join(map(str, stale)))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=_repository_root())
    parser.add_argument("--check", action="store_true", help="fail instead of writing when output differs")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        records = discover_records(root)
        write_outputs(
            root,
            {language: render(records, language) for language in OUTPUTS},
            check=args.check,
        )
    except (CatalogError, OSError, SyntaxError, tomllib.TOMLDecodeError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
