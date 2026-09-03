from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "audit_docs.py"
SPEC = importlib.util.spec_from_file_location("wavebench_plugin_docs_audit", SCRIPT)
assert SPEC and SPEC.loader
AUDIT = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = AUDIT
SPEC.loader.exec_module(AUDIT)


def test_parser_ignores_fences_and_builds_duplicate_anchors():
    lines = (
        "# 文档 API",
        "[有效](guide.md#运行-check)",
        "```markdown",
        "[忽略](missing.md)",
        "# 也忽略",
        "```",
        "## 运行 `check`",
        "## 运行 `check`",
    )

    visible = AUDIT.visible_markdown_lines(lines)
    headings, anchors = AUDIT.markdown_structure(visible)
    document = AUDIT.Document(
        path=Path("README.md"),
        relative=Path("README.md"),
        canonical=Path("README.md"),
        lines=lines,
        visible_lines=visible,
        headings=headings,
        anchors=anchors,
    )

    assert [heading.title for heading in headings] == ["文档 API", "运行 `check`", "运行 `check`"]
    assert {"文档-api", "运行-check", "运行-check-1"} <= anchors
    assert AUDIT.markdown_links(document) == [(2, "guide.md#运行-check")]


def test_four_space_indentation_does_not_open_a_fence():
    lines = ("    ```", "[still visible](missing.md)")

    assert AUDIT.visible_markdown_lines(lines) == ((1, "    ```"), (2, "[still visible](missing.md)"))


def test_discovers_monorepo_docs_and_skips_vendor_material(tmp_path):
    expected = (
        tmp_path / "README.md",
        tmp_path / "doc" / "index.md",
        tmp_path / "packages" / "example" / "README.md",
        tmp_path / "packages" / "example" / "doc" / "reference.md",
        tmp_path / "packages" / "example" / "doc" / "vendor-local" / "README.md",
    )
    ignored = (
        tmp_path / "packages" / "example" / "doc" / "vendor-local" / "manual.md",
        tmp_path / "packages" / "example" / ".pytest_cache" / "README.md",
    )
    for path in (*expected, *ignored):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n", encoding="utf-8")

    assert AUDIT.discover_markdown(tmp_path) == sorted(expected)


def test_link_check_distinguishes_missing_targets_and_anchors(tmp_path):
    readme = tmp_path / "README.md"
    guide = tmp_path / "guide.md"
    readme.write_text(
        "# Index\n[missing](missing.md)\n[bad anchor](guide.md#missing)\n[good](guide.md#section)\n",
        encoding="utf-8",
    )
    guide.write_text("# Guide\n## Section\n", encoding="utf-8")
    documents = [AUDIT.load_document(path, tmp_path) for path in (readme, guide)]

    findings, inbound = AUDIT.check_links(documents, tmp_path)

    assert [(finding.level, finding.line) for finding in findings] == [
        ("error", 2),
        ("warning", 3),
    ]
    assert inbound[guide.resolve()] == {readme.resolve()}


def test_reference_and_html_links_are_checked(tmp_path):
    readme = tmp_path / "README.md"
    readme.write_text(
        "# Index\n[reference][guide]\n[guide]: missing-reference.md\n"
        '<a href="missing-html.md">missing</a>\n',
        encoding="utf-8",
    )
    document = AUDIT.load_document(readme, tmp_path)

    findings, _ = AUDIT.check_links([document], tmp_path)

    assert [(finding.line, finding.message.rsplit(": ", 1)[-1]) for finding in findings] == [
        (3, "missing-reference.md"),
        (4, "missing-html.md"),
    ]


def test_explicit_html_ids_are_case_sensitive(tmp_path):
    index = tmp_path / "README.md"
    target = tmp_path / "target.md"
    index.write_text(
        "# Index\n[exact](target.md#My-ID)\n[wrong case](target.md#my-id)\n"
        "[reverse wrong case](target.md#LOWER-ID)\n",
        encoding="utf-8",
    )
    target.write_text('# Target\n<a id="My-ID"></a>\n<a id="lower-id"></a>\n', encoding="utf-8")
    documents = [AUDIT.load_document(path, tmp_path) for path in (index, target)]

    findings, _ = AUDIT.check_links(documents, tmp_path)

    assert [(finding.level, finding.line) for finding in findings] == [
        ("warning", 3),
        ("warning", 4),
    ]


def test_sensitive_resource_check_ignores_firmware_and_documentation_ips(tmp_path):
    path = tmp_path / "README.md"
    path.write_text(
        "# Docs\nfirmware `8.5.0.0`\nTCPIP::192.0.2.10::INSTR\nTCPIP::192.168.1.42::INSTR\n"
        "firmware is current; lab address is 10.0.0.42\n"
        "minimum firmware is `1.1.3.1`\n",
        encoding="utf-8",
    )

    findings = AUDIT.check_sensitive_resources([AUDIT.load_document(path, tmp_path)])

    assert not any("8.5.0.0" in finding.message for finding in findings)
    assert not any("192.0.2.10" in finding.message for finding in findings)
    assert any("192.168.1.42" in finding.message for finding in findings)
    assert any("10.0.0.42" in finding.message for finding in findings)
    assert not any("1.1.3.1" in finding.message for finding in findings)


def test_archive_pages_are_exempt_from_long_page_warning(tmp_path):
    archive = tmp_path / "packages" / "example" / "doc" / "archive" / "record.md"
    current = tmp_path / "packages" / "example" / "doc" / "reference.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("# Archive\n\nHistorical detail\n", encoding="utf-8")
    current.write_text("# Current\n\nCurrent detail\n", encoding="utf-8")
    documents = [AUDIT.load_document(path, tmp_path) for path in (archive, current)]

    findings = AUDIT.check_structure(documents, {}, max_lines=1)

    assert not any(
        finding.path == "packages/example/doc/archive/record.md" and "long page" in finding.message
        for finding in findings
    )
    assert any(
        finding.path == "packages/example/doc/reference.md" and "long page" in finding.message
        for finding in findings
    )


def test_duplicate_titles_are_scoped_to_non_entry_pages_in_one_directory(tmp_path):
    first = tmp_path / "doc" / "first.md"
    second = tmp_path / "doc" / "second.md"
    other = tmp_path / "other" / "same.md"
    readme = tmp_path / "doc" / "README.md"
    for path in (first, second, other, readme):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("# Same title\n", encoding="utf-8")
    documents = [AUDIT.load_document(path, tmp_path) for path in (first, second, other, readme)]

    findings = AUDIT.check_structure(documents, {}, max_lines=600)
    duplicate_paths = {
        finding.path for finding in findings if "duplicate H1" in finding.message
    }

    assert duplicate_paths == {"doc/first.md", "doc/second.md"}
