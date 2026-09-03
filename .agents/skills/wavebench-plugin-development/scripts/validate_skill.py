#!/usr/bin/env python3
"""Validate the repository-local plugin-development skill without dependencies."""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


SKILL_NAME = "wavebench-plugin-development"
MAX_BODY_LINES = 220
MAX_BODY_TOKENS = 3500
EXPECTED_REFERENCES = {
    "instrument-driver-workflow.md",
    "repository-contract.md",
    "development-validation.md",
    "packaging-and-lifecycle.md",
    "conformance-and-hardware-evidence.md",
    "eval-prompts.md",
}

LINK_RE = re.compile(r"\]\(([^)]+)\)")
UNIX_HOME_PREFIX = "/" + "home/"
ABSOLUTE_PATH_RE = re.compile(
    rf"(?:^|[\s(])(?:{re.escape(UNIX_HOME_PREFIX)}|[A-Za-z]:[\\/])"
)
SECRET_RE = re.compile(
    r"(?i)(?:-----begin [^-]+ key-----|\bAKIA[0-9A-Z]{16}\b|"
    r"\b(?:api[_-]?key|secret|password|token)\s*[:=]\s*['\"]?[A-Za-z0-9+/=_-]{12,})"
)
DANGEROUS_RE = re.compile(
    r"(?i)(?:curl\b[^\n|]*\|\s*(?:ba|z)?sh|wget\b[^\n|]*\|\s*(?:ba|z)?sh|"
    r"git\s+(?:reset\s+--hard|push\s+--force)|rm\s+-rf\s+/|chmod\s+777)"
)
TODO_WORD = "TO" + "DO"
TBD_WORD = "T" + "BD"
PLACEHOLDER_RE = re.compile(
    rf"(?i)(?:\[{TODO_WORD}(?:[^]]*)?\]|\b(?:{TODO_WORD}|{TBD_WORD})\b)"
)


@dataclass(frozen=True)
class Finding:
    level: str
    message: str


def parse_frontmatter(text: str) -> tuple[dict[str, str], str, list[Finding]]:
    if not text.startswith("---\n"):
        return {}, text, [Finding("error", "SKILL.md 必须以 YAML frontmatter 开始")]
    end = text.find("\n---", 4)
    if end < 0:
        return {}, text, [Finding("error", "frontmatter 缺少结束标记")]

    raw = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    fields: dict[str, str] = {}
    lines = raw.splitlines()
    index = 0
    while index < len(lines):
        match = re.match(r"^([A-Za-z][A-Za-z0-9_-]*):(?:\s*(.*))?$", lines[index])
        if not match:
            index += 1
            continue
        key, value = match.group(1), (match.group(2) or "").strip()
        if value in {">-", ">", "|-", "|"}:
            folded: list[str] = []
            index += 1
            while index < len(lines) and (lines[index].startswith(" ") or not lines[index]):
                folded.append(lines[index].strip())
                index += 1
            fields[key] = " ".join(part for part in folded if part)
            continue
        fields[key] = value.strip("'\"")
        index += 1
    return fields, body, []


def repository_root(skill_dir: Path) -> Path | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(skill_dir), "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None
    return Path(result.stdout.strip())


def tracked_by_git(root: Path, path: Path) -> bool:
    try:
        subprocess.run(
            ["git", "-C", str(root), "ls-files", "--error-unmatch", str(path.relative_to(root))],
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError, ValueError):
        return False
    return True


def validate(skill_dir: Path, strict_git: bool) -> list[Finding]:
    findings: list[Finding] = []
    skill_md = skill_dir / "SKILL.md"
    openai_yaml = skill_dir / "agents" / "openai.yaml"
    references = skill_dir / "references"
    validator_path = skill_dir / "scripts" / "validate_skill.py"

    if skill_dir.name != SKILL_NAME:
        findings.append(Finding("error", f"Skill 目录必须命名为 {SKILL_NAME}"))
    if not skill_md.is_file():
        return findings + [Finding("error", "缺少 SKILL.md")]

    skill_text = skill_md.read_text(encoding="utf-8")
    fields, body, parse_findings = parse_frontmatter(skill_text)
    findings.extend(parse_findings)
    if fields.get("name") != SKILL_NAME:
        findings.append(Finding("error", "frontmatter name 与 Skill 名称不一致"))
    description = fields.get("description", "")
    if not description or len(description) > 1024:
        findings.append(Finding("error", "description 必须存在且不超过 1024 个字符"))

    body_lines = body.splitlines()
    body_tokens = len(re.findall(r"\S+", body)) + len(re.findall(r"[\u4e00-\u9fff]", body))
    if len(body_lines) > MAX_BODY_LINES:
        findings.append(Finding("error", f"SKILL.md 正文超过 {MAX_BODY_LINES} 行"))
    if body_tokens > MAX_BODY_TOKENS:
        findings.append(Finding("error", f"SKILL.md 正文约 {body_tokens} tokens，超过 {MAX_BODY_TOKENS}"))

    if not references.is_dir():
        findings.append(Finding("error", "缺少 references/"))
        reference_files: list[Path] = []
    else:
        reference_files = sorted(references.glob("*.md"))
        actual = {path.name for path in reference_files}
        if actual != EXPECTED_REFERENCES:
            missing = EXPECTED_REFERENCES - actual
            extra = actual - EXPECTED_REFERENCES
            if missing:
                findings.append(Finding("error", f"缺少 reference：{', '.join(sorted(missing))}"))
            if extra:
                findings.append(Finding("error", f"存在未规划 reference：{', '.join(sorted(extra))}"))
        if any(path.is_dir() for path in references.rglob("*")):
            findings.append(Finding("error", "references/ 必须保持单层"))

    linked_references: set[str] = set()
    for target in LINK_RE.findall(body):
        target = target.split("#", 1)[0].strip()
        if not target.startswith("references/"):
            continue
        relative = Path(target)
        if len(relative.parts) != 2:
            findings.append(Finding("error", f"入口 reference 链接不是单层路径：{target}"))
        elif not (skill_dir / relative).is_file():
            findings.append(Finding("error", f"入口 reference 不存在：{target}"))
        else:
            linked_references.add(relative.name)
    unlinked = EXPECTED_REFERENCES - linked_references
    if unlinked:
        findings.append(Finding("error", f"SKILL.md 未直接链接：{', '.join(sorted(unlinked))}"))

    references_root = references.resolve()
    for path in reference_files:
        for target in LINK_RE.findall(path.read_text(encoding="utf-8")):
            clean = target.split("#", 1)[0].strip()
            if not clean or clean.startswith(("http://", "https://", "mailto:")):
                continue
            resolved = (path.parent / clean).resolve()
            if resolved.parent == references_root and resolved.suffix == ".md":
                findings.append(
                    Finding("error", f"reference 不得递归链接 reference：{path.name} -> {clean}")
                )

    if not openai_yaml.is_file():
        findings.append(Finding("error", "缺少 agents/openai.yaml"))
        yaml_text = ""
    else:
        yaml_text = openai_yaml.read_text(encoding="utf-8")
        if "\t" in yaml_text:
            findings.append(Finding("error", "openai.yaml 不得使用制表符缩进"))
        allowed_lines = (
            re.compile(r"^interface:$"),
            re.compile(r"^  (?:display_name|short_description|default_prompt):\s*['\"].+['\"]$"),
            re.compile(r"^policy:$"),
            re.compile(r"^  allow_implicit_invocation:\s*true$"),
        )
        unexpected = [
            line
            for line in yaml_text.splitlines()
            if line.strip() and not any(pattern.fullmatch(line) for pattern in allowed_lines)
        ]
        if unexpected:
            findings.append(Finding("error", "openai.yaml 包含未知字段或无效缩进"))
        meaningful_lines = [line for line in yaml_text.splitlines() if line.strip()]
        if len(meaningful_lines) != 6:
            findings.append(Finding("error", "openai.yaml 必须恰好包含当前六个元数据字段"))
        matches = {
            key: re.search(rf"^\s+{key}:\s*['\"](.+?)['\"]\s*$", yaml_text, re.MULTILINE)
            for key in ("display_name", "short_description", "default_prompt")
        }
        for key, match in matches.items():
            if not match:
                findings.append(Finding("error", f"openai.yaml 缺少已引用的 {key}"))
        if matches["short_description"]:
            length = len(matches["short_description"].group(1))
            if not 25 <= length <= 64:
                findings.append(Finding("error", f"short_description 长度为 {length}，应为 25–64"))
        if matches["default_prompt"] and f"${SKILL_NAME}" not in matches["default_prompt"].group(1):
            findings.append(Finding("error", f"default_prompt 必须包含 ${SKILL_NAME}"))
        if not re.search(r"^\s+allow_implicit_invocation:\s*true\s*$", yaml_text, re.MULTILINE):
            findings.append(Finding("error", "必须显式允许隐式触发"))

    script_files = sorted((skill_dir / "scripts").glob("*.py"))
    if validator_path not in script_files:
        findings.append(Finding("error", "缺少 scripts/validate_skill.py"))

    scan_files = [skill_md, *reference_files, *script_files]
    if openai_yaml.is_file():
        scan_files.append(openai_yaml)
    for path in scan_files:
        text = path.read_text(encoding="utf-8")
        for label, pattern in (
            ("未完成占位符", PLACEHOLDER_RE),
            ("主机绝对路径", ABSOLUTE_PATH_RE),
            ("疑似秘密", SECRET_RE),
            ("危险命令", DANGEROUS_RE),
        ):
            if pattern.search(text):
                findings.append(Finding("error", f"{path.relative_to(skill_dir)} 包含{label}"))

    root = repository_root(skill_dir)
    required_files = [skill_md, openai_yaml, *reference_files, validator_path]
    if root is None:
        findings.append(Finding("warning", "无法确定 Git 仓库，跳过追踪检查"))
    else:
        untracked = [path for path in required_files if path.is_file() and not tracked_by_git(root, path)]
        if untracked:
            level = "error" if strict_git else "warning"
            names = ", ".join(str(path.relative_to(skill_dir)) for path in untracked)
            findings.append(Finding(level, f"Skill 文件尚未被 Git 跟踪：{names}"))

    return findings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("skill_dir", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--strict-git", action="store_true", help="未跟踪文件视为错误")
    args = parser.parse_args()

    findings = validate(args.skill_dir.resolve(), args.strict_git)
    for finding in findings:
        print(f"{finding.level.upper()}: {finding.message}")
    errors = [finding for finding in findings if finding.level == "error"]
    if errors:
        print(f"FAIL: {len(errors)} 个错误")
        return 1
    print("PASS: wavebench-plugin-development Skill 结构检查通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
