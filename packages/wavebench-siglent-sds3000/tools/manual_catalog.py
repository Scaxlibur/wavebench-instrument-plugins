#!/usr/bin/env python3
"""Build the SDS3000 command catalog from ignored local manual conversions.

The generated catalog records identifiers and audit metadata only. It does not
copy vendor descriptions, examples, or other manual prose into the repository.
"""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
from hashlib import sha256
from html import unescape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
from typing import Any, Iterable


ALLOWED_DISPOSITIONS = frozenset(
    {
        "implemented",
        "partially-implemented",
        "planned",
        "core-gap-rfc",
        "firmware-unverified",
        "option-absent",
        "model-not-applicable",
        "unsafe-quarantined",
    }
)

EXPECTED_KIND_COUNTS = {
    "legacy_command": 164,
    "automation_object": 100,
    "automation_action": 216,
    "automation_cvar": 14,
    "automation_method": 4,
    "result_property": 80,
}

_PART_4 = "Part 4: Automation Control Variable Reference"
_PART_5 = "Part 5: Automation Result Interface Reference"
_PART_6 = "Part 6: IEEE 488.2 Programming Reference"
_PART_7 = "Part 7: IEEE 488.2 Command Reference"


class CatalogError(RuntimeError):
    """Raised when the source manual cannot reproduce the frozen denominator."""


class _TableParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.rows: list[list[str]] = []
        self._row: list[str] | None = None
        self._cell: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        del attrs
        if tag == "tr":
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell = []

    def handle_data(self, data: str) -> None:
        if self._cell is not None:
            self._cell.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"td", "th"} and self._cell is not None:
            assert self._row is not None
            self._row.append(" ".join(unescape("".join(self._cell)).split()))
            self._cell = None
        elif tag == "tr" and self._row is not None:
            self.rows.append(self._row)
            self._row = None


def parse_html_table(body: str) -> list[list[str]]:
    parser = _TableParser()
    parser.feed(body)
    return parser.rows


def canonical_automation_path(value: str) -> str:
    path = unescape(value).strip()
    path = path.replace("appPreferences", "app.Preferences")
    path = path.replace("app..", "app.")
    path = re.sub(r"^app\s+", "app.", path)
    path = re.sub(r"\s*\.\s*", ".", path)
    if path.endswith("."):
        path += "<Type>"
    return path


@dataclass(frozen=True)
class Segment:
    segment_id: str
    logical_first: int
    items: tuple[dict[str, Any], ...]
    page_numbers: dict[int, str]

    def source(self, item: dict[str, Any]) -> dict[str, Any]:
        page_index = int(item["page_idx"])
        return {
            "segment": self.segment_id,
            "logical_page": self.logical_first + page_index,
            "printed_page": self.page_numbers.get(page_index),
        }


def _find_section(items: tuple[dict[str, Any], ...], title: str) -> int:
    for index, item in enumerate(items):
        if item.get("text") == title and item.get("text_level"):
            return index
    raise CatalogError(f"missing section: {title}")


def _load_segments(package_root: Path, baseline: dict[str, Any]) -> list[Segment]:
    vendor_root = package_root / "doc" / "vendor-local"
    segments: list[Segment] = []
    for metadata in baseline["manual"]["segments"]:
        matches = list(vendor_root.rglob(metadata["origin_basename"]))
        if len(matches) != 1:
            raise CatalogError(
                f"expected one local source for {metadata['id']}, found {len(matches)}"
            )
        origin = matches[0]
        data = origin.read_bytes()
        if len(data) != metadata["byte_count"]:
            raise CatalogError(f"byte count changed for {metadata['id']}")
        if sha256(data).hexdigest() != metadata["sha256"]:
            raise CatalogError(f"SHA-256 changed for {metadata['id']}")

        stem = origin.name.removesuffix("_origin.pdf")
        content_path = origin.with_name(f"{stem}_content_list.json")
        items = tuple(json.loads(content_path.read_text(encoding="utf-8")))
        page_numbers = {
            int(item["page_idx"]): str(item["text"])
            for item in items
            if item.get("type") == "page_number" and item.get("text")
        }
        segments.append(
            Segment(
                segment_id=metadata["id"],
                logical_first=int(metadata["logical_page_first"]),
                items=items,
                page_numbers=page_numbers,
            )
        )
    return segments


def _stable_id(kind: str, name: str) -> str:
    prefixes = {
        "legacy_command": "legacy",
        "automation_object": "automation-object",
        "automation_action": "automation-action",
        "automation_cvar": "automation-cvar",
        "automation_method": "automation-method",
        "result_property": "result-property",
    }
    return f"{prefixes[kind]}:{name}"


def _record(
    *,
    kind: str,
    name: str,
    directions: Iterable[str],
    disposition: str,
    safety: str,
    source: dict[str, Any],
    wavebench_capabilities: Iterable[str] = (),
    **extra: Any,
) -> dict[str, Any]:
    return {
        "id": _stable_id(kind, name),
        "kind": kind,
        "name": name,
        "directions": list(dict.fromkeys(directions)),
        "disposition": disposition,
        "safety": safety,
        "wavebench_capabilities": list(dict.fromkeys(wavebench_capabilities)),
        "source": source,
        **extra,
    }


_UNSAFE_LEGACY = frozenset(
    {
        "*CAL?",
        "*RCL",
        "*RST",
        "*SAV",
        "*TST?",
        "ACAL",
        "COUT",
        "DATE",
        "DELF",
        "DIR",
        "MAIL",
        "PNSU?",
        "PRCA?",
        "PRDG",
        "RCPN",
        "REC",
        "STO",
        "STPN",
        "STST",
        "TRFL",
        "VBS",
    }
)

_PLANNED_LEGACY = frozenset(
    {
        "ARM",
        "ASET",
        "CFMT",
        "CHDR",
        "CORD",
        "CRVA?",
        "INSP?",
        "PAST?",
        "STOP",
        "TMPL?",
        "WAIT",
        "WF",
        "WFSU",
    }
)

_CORE_GAP_LEGACY = frozenset(
    {
        "OFST",
        "SCDP",
        "TDIV",
        "TRCP",
        "TRDL",
        "TRLV",
        "TRMD",
        "TRSE",
        "TRSL",
        "VDIV",
    }
)

_LEGACY_CAPABILITIES: dict[str, tuple[str, ...]] = {
    "*IDN?": ("scope.idn",),
    "ALST?": ("scope.errors",),
    "ASET": ("scope.autoscale",),
    "ARM": ("scope.capture_waveform", "scope.capture_waveforms"),
    "CPL": ("scope.channel_coupling",),
    "CMR?": ("scope.errors",),
    "CFMT": ("scope.fetch_waveform",),
    "CHDR": ("scope.fetch_waveform",),
    "CORD": ("scope.fetch_waveform",),
    "CRVA?": ("scope.cursor_readout",),
    "DDR?": ("scope.errors",),
    "EXR?": ("scope.errors",),
    "PAST?": ("scope.measurement_statistics",),
    "SCDP": ("scope.screenshot",),
    "WF": ("scope.fetch_waveform",),
    "WFSU": ("scope.fetch_waveform",),
}


def _legacy_classification(short: str, subsystem: str) -> tuple[str, str]:
    if short in {"CMR?", "DDR?", "EXR?"}:
        return "implemented", "stateful-read"
    if short in {"*IDN?", "CPL"}:
        return "implemented", "read-only"
    if short in {"CFMT", "CHDR", "CORD", "WFSU"}:
        return "implemented", "state-change"
    if short == "WF":
        return "partially-implemented", "state-change"
    if subsystem in {"DDA", "ET-PMT"}:
        return "option-absent", "not-tested"
    if short in _UNSAFE_LEGACY:
        return "unsafe-quarantined", "destructive-or-external"
    if short in _CORE_GAP_LEGACY:
        return "core-gap-rfc", "state-change"
    if short in _PLANNED_LEGACY:
        return "planned", "state-change" if not short.endswith("?") else "read-only"
    return "firmware-unverified", "state-change" if not short.endswith("?") else "read-only"


_UNSAFE_AUTOMATION_TERMS = (
    "calibrat",
    "copy",
    "default",
    "delete",
    "eject",
    "email",
    "exit",
    "export",
    "file",
    "import",
    "install",
    "print",
    "quit",
    "recall",
    "remove",
    "reset",
    "save",
    "shutdown",
)


def _automation_classification(
    kind: str, path: str, type_name: str, description: str
) -> tuple[str, str]:
    combined = f"{path} {description}".lower()
    if kind == "automation_object":
        if "option" in combined:
            return "option-absent", "not-callable"
        if "only available" in combined or "not available on wavesurfer" in combined:
            return "model-not-applicable", "not-callable"
        return "firmware-unverified", "not-callable"
    if any(term in combined for term in _UNSAFE_AUTOMATION_TERMS):
        return "unsafe-quarantined", "destructive-or-external"
    if path in {
        "app.AutoSetup",
        "app.Acquisition.Acquire",
        "app.Acquisition.ForceTrigger",
        "app.Acquisition.IsTriggerReady",
        "app.ClearSweeps",
    }:
        return "planned", "read-only" if "IsTriggerReady" in path else "state-change"
    if type_name.lower() == "action" or kind in {"automation_action", "automation_method"}:
        return "firmware-unverified", "state-change"
    if "read-only" in description.lower():
        return "firmware-unverified", "read-only"
    return "firmware-unverified", "state-change"


def _automation_capabilities(path: str) -> tuple[str, ...]:
    mapping = {
        "app.AutoSetup": ("scope.autoscale",),
        "app.Acquisition.Acquire": ("scope.capture_waveform", "scope.capture_waveforms"),
        "app.Acquisition.ForceTrigger": ("scope.capture_waveform", "scope.capture_waveforms"),
        "app.Acquisition.IsTriggerReady": ("scope.acquisition_status",),
        "app.ClearSweeps": ("scope.capture_average",),
    }
    return mapping.get(path, ())


def _extract_part4(segment: Segment) -> list[dict[str, Any]]:
    items = segment.items
    start = _find_section(items, _PART_4)
    end = _find_section(items, _PART_5)
    records: list[dict[str, Any]] = []
    root_source = segment.source(items[start])
    disposition, safety = _automation_classification("automation_object", "app", "", "")
    records.append(
        _record(
            kind="automation_object",
            name="app",
            directions=(),
            disposition=disposition,
            safety=safety,
            source={**root_source, "part": 4},
        )
    )

    scope = "app"
    last_heading = ""
    for item in items[start:end]:
        if item.get("type") == "text" and item.get("text_level"):
            heading = str(item["text"])
            last_heading = heading
            if (
                heading.startswith("app")
                and "(" not in heading
                and heading != "app.Quit"
                and " and " not in heading
            ):
                scope = canonical_automation_path(heading)
            if heading == "app.Quit" or (heading.startswith("app.") and "(" in heading):
                path = canonical_automation_path(re.sub(r"\(.*", "", heading))
                disposition, safety = _automation_classification(
                    "automation_method", path, "Method", ""
                )
                records.append(
                    _record(
                        kind="automation_method",
                        name=path,
                        directions=("command",),
                        disposition=disposition,
                        safety=safety,
                        source={**segment.source(item), "part": 4},
                        wavebench_capabilities=_automation_capabilities(path),
                    )
                )
            continue

        if item.get("type") == "text":
            text = str(item.get("text", ""))
            if last_heading == "Methods":
                match = re.match(r"(app(?:\.[A-Za-z0-9_]+)+)\s+([A-Za-z0-9_]+)\s*\(", text)
                if match:
                    path = canonical_automation_path(f"{match.group(1)}.{match.group(2)}")
                    disposition, safety = _automation_classification(
                        "automation_method", path, "Method", text
                    )
                    records.append(
                        _record(
                            kind="automation_method",
                            name=path,
                            directions=("command",),
                            disposition=disposition,
                            safety=safety,
                            source={**segment.source(item), "part": 4},
                            wavebench_capabilities=_automation_capabilities(path),
                        )
                    )
            if last_heading == "Other CVARs of Note":
                for match in re.finditer(r"\bCVAR\s+(app(?:\.[A-Za-z0-9_]+)+)", text):
                    path = canonical_automation_path(match.group(1))
                    disposition, safety = _automation_classification(
                        "automation_cvar", path, "Boolean", text
                    )
                    records.append(
                        _record(
                            kind="automation_cvar",
                            name=path,
                            directions=("query",),
                            disposition=disposition,
                            safety=safety,
                            source={**segment.source(item), "part": 4},
                            wavebench_capabilities=_automation_capabilities(path),
                            value_type="Boolean",
                        )
                    )
            continue

        body = item.get("table_body") if item.get("type") == "table" else None
        if not body:
            continue
        rows = parse_html_table(str(body))
        if not rows:
            continue
        header = rows[0]
        if header[:2] == ["Object", "Description"]:
            table_kind = "automation_object"
        elif header[:2] == ["Action", "Description"]:
            table_kind = "automation_action"
        elif header[:3] == ["Name", "Type", "Description"]:
            table_kind = "cvar_table"
        else:
            continue

        for row in rows[1:]:
            if table_kind == "automation_object":
                path, type_name = canonical_automation_path(row[0]), "Object"
                description = row[1] if len(row) > 1 else ""
                kind = table_kind
                directions: tuple[str, ...] = ()
            elif table_kind == "automation_action":
                path, type_name = canonical_automation_path(row[0]), "Action"
                description = row[1] if len(row) > 1 else ""
                kind = table_kind
                directions = ("command",)
            else:
                if len(row) < 2:
                    raise CatalogError(f"malformed Part 4 CVAR row: {row!r}")
                type_name = row[1]
                description = row[2] if len(row) > 2 else ""
                path = (
                    canonical_automation_path(row[0])
                    if row[0].startswith("app")
                    else canonical_automation_path(f"{scope}.{row[0]}")
                )
                kind = "automation_action" if type_name.lower() == "action" else "automation_cvar"
                if kind == "automation_action":
                    directions = ("command",)
                elif "read-only" in description.lower():
                    directions = ("query",)
                else:
                    directions = ("command", "query")

            disposition, safety = _automation_classification(kind, path, type_name, description)
            extra = {"value_type": type_name} if kind == "automation_cvar" else {}
            records.append(
                _record(
                    kind=kind,
                    name=path,
                    directions=directions,
                    disposition=disposition,
                    safety=safety,
                    source={**segment.source(item), "part": 4},
                    wavebench_capabilities=_automation_capabilities(path),
                    **extra,
                )
            )
    return records


def _extract_part5(segment: Segment) -> list[dict[str, Any]]:
    items = segment.items
    start = _find_section(items, _PART_5)
    end = _find_section(items, _PART_6)
    toc_entries: list[tuple[str, str]] = []
    toc_pattern = re.compile(r"\s*([A-Za-z][A-Za-z0-9]*)\s+(?:\.{2,}\s+)?(5-\d+)\s*")
    for item in items[start:end]:
        if int(item.get("page_idx", 10_000)) > 138:
            break
        if item.get("type") != "text" or item.get("text_level"):
            continue
        for line in str(item.get("text", "")).splitlines():
            match = toc_pattern.fullmatch(line)
            if match:
                toc_entries.append((match.group(1), match.group(2)))

    headings = {
        str(item["text"]): item
        for item in items[start:end]
        if item.get("type") == "text" and item.get("text_level")
    }
    records = []
    for name, printed_page in toc_entries:
        item = headings.get(name)
        if item is None:
            raise CatalogError(f"Part 5 property has no body heading: {name}")
        records.append(
            _record(
                kind="result_property",
                name=name,
                directions=("query",),
                disposition="firmware-unverified",
                safety="read-only",
                source={
                    **segment.source(item),
                    "part": 5,
                    "toc_printed_page": printed_page,
                },
            )
        )
    return records


def _token(value: str, *, keep_query: bool = True, keep_star: bool = True) -> str:
    text = value.replace("\\_", "_").upper()
    text = re.sub(r"\([^)]*\)", "", text)
    if not keep_query:
        text = text.replace("?", "")
    if not keep_star:
        text = text.replace("*", "")
    allowed = "A-Z0-9"
    if keep_query:
        allowed += "?"
    if keep_star:
        allowed += "*"
    return re.sub(rf"[^{allowed}]", "", text)


@dataclass(frozen=True)
class _Heading:
    segment: Segment
    index: int
    item: dict[str, Any]
    components: tuple[str, ...]


def _heading_score(short: str, long_name: str, heading: _Heading) -> int:
    exact = {_token(part) for part in heading.components}
    base = {_token(part, keep_query=False) for part in heading.components}
    bare = {_token(part, keep_query=False, keep_star=False) for part in heading.components}
    score = 0
    if _token(long_name) in exact:
        score += 8
    if _token(short) in exact:
        score += 6
    if _token(long_name, keep_query=False) in base:
        score += 4
    if _token(short, keep_query=False) in base:
        score += 3
    if _token(short, keep_query=False, keep_star=False) in bare:
        score += 2
    if score and len(heading.components) > 1:
        score += 1
    return score


def _match_heading(short: str, long_name: str, headings: list[_Heading]) -> _Heading | None:
    scored = [(_heading_score(short, long_name, heading), heading) for heading in headings]
    best = max((score for score, _ in scored), default=0)
    if best == 0:
        return None
    matches = [heading for score, heading in scored if score == best]
    if len(matches) != 1:
        labels = [str(match.item.get("text")) for match in matches]
        raise CatalogError(f"ambiguous Part 7 body for {short}: {labels}")
    return matches[0]


def _legacy_directions(
    row: list[str], heading: _Heading | None, end_index: int | None
) -> list[str]:
    short, long_name, _, summary = row
    if heading is None:
        lower = summary.lower()
        directions = []
        if "command" in lower or not short.endswith("?"):
            directions.append("command")
        if "query" in lower or short.endswith("?") or long_name.endswith("?"):
            directions.append("query")
        return directions

    stop = end_index if end_index is not None else len(heading.segment.items)
    section_text = [
        str(item.get("text", ""))
        for item in heading.segment.items[heading.index : stop]
        if item.get("type") == "text"
    ]
    directions = []
    if any(_token(text, keep_query=False) == "COMMANDSYNTAX" for text in section_text):
        directions.append("command")
    if any(_token(text, keep_query=False) == "QUERYSYNTAX" for text in section_text):
        directions.append("query")
    if not directions:
        directions.append("query" if short.endswith("?") or long_name.endswith("?") else "command")
    return directions


def _extract_part7(segments: list[Segment]) -> list[dict[str, Any]]:
    segment = next(candidate for candidate in segments if candidate.logical_first == 201)
    items = segment.items
    start = _find_section(items, _PART_7)
    subsystem_index = next(
        index
        for index, item in enumerate(items[start + 1 :], start + 1)
        if item.get("text") == "Commands and Queries by Subsystem" and item.get("text_level")
    )
    index_rows: list[tuple[list[str], dict[str, Any]]] = []
    expected_header = [
        "Short",
        "Long",
        "Subsystem",
        "What The Command or Query Does",
    ]
    for item in items[start:subsystem_index]:
        body = item.get("table_body") if item.get("type") == "table" else None
        if not body:
            continue
        rows = parse_html_table(str(body))
        if rows and rows[0] == expected_header:
            index_rows.extend((row, item) for row in rows[1:])

    headings: list[_Heading] = []
    for candidate in segments:
        for index, item in enumerate(candidate.items):
            printed = candidate.page_numbers.get(int(item.get("page_idx", -1)), "")
            printed_match = re.fullmatch(r"7-(\d+)", printed)
            if not printed_match or int(printed_match.group(1)) < 15:
                continue
            if item.get("type") != "text" or item.get("text_level") not in {1, 2}:
                continue
            headings.append(
                _Heading(
                    segment=candidate,
                    index=index,
                    item=item,
                    components=tuple(str(item["text"]).split(",")),
                )
            )

    matches: list[_Heading | None] = [
        _match_heading(row[0], row[1], headings) for row, _ in index_rows
    ]
    matched_indexes: dict[str, list[int]] = {}
    for heading in matches:
        if heading is not None:
            matched_indexes.setdefault(heading.segment.segment_id, []).append(heading.index)
    for indexes in matched_indexes.values():
        indexes.sort()

    records = []
    for (row, index_item), heading in zip(index_rows, matches, strict=True):
        if len(row) != 4:
            raise CatalogError(f"malformed Part 7 index row: {row!r}")
        short, long_name, subsystem, _ = row
        end_index = None
        if heading is not None:
            for candidate_index in matched_indexes[heading.segment.segment_id]:
                if candidate_index > heading.index:
                    end_index = candidate_index
                    break
        directions = _legacy_directions(row, heading, end_index)
        disposition, safety = _legacy_classification(short, subsystem)
        source = {
            **segment.source(index_item),
            "part": 7,
            "index_printed_page": segment.page_numbers.get(int(index_item["page_idx"])),
        }
        anomalies: list[str] = []
        if heading is None:
            source["body"] = None
            anomalies.append("body-heading-not-present")
        else:
            source["body"] = heading.segment.source(heading.item)
            exact_parts = {_token(part) for part in heading.components}
            if _token(short) not in exact_parts or _token(long_name) not in exact_parts:
                anomalies.append("index-body-token-mismatch")

        records.append(
            _record(
                kind="legacy_command",
                name=long_name,
                directions=directions,
                disposition=disposition,
                safety=safety,
                source=source,
                wavebench_capabilities=_LEGACY_CAPABILITIES.get(short, ()),
                short=short,
                subsystem=subsystem,
                manual_anomalies=anomalies,
                direction_dispositions=(
                    {"command": "unsafe-quarantined", "query": "implemented"}
                    if short == "WF"
                    else {direction: disposition for direction in directions}
                ),
            )
        )
    return records


def _validate_catalog(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(record["kind"]) for record in records)
    if dict(counts) != EXPECTED_KIND_COUNTS:
        raise CatalogError(
            f"catalog denominator changed: expected {EXPECTED_KIND_COUNTS}, got {dict(counts)}"
        )
    identifiers = [str(record["id"]) for record in records]
    if len(identifiers) != len(set(identifiers)):
        duplicates = sorted(
            identifier for identifier, count in Counter(identifiers).items() if count > 1
        )
        raise CatalogError(f"duplicate stable IDs: {duplicates}")
    unknown = sorted(
        {
            str(record["disposition"])
            for record in records
            if record["disposition"] not in ALLOWED_DISPOSITIONS
        }
    )
    if unknown:
        raise CatalogError(f"unclassified dispositions: {unknown}")
    if any(
        record["kind"] != "automation_object" and not record["directions"] for record in records
    ):
        raise CatalogError("callable catalog entity without a direction")
    for record in records:
        if record["kind"] != "legacy_command":
            continue
        per_direction = record.get("direction_dispositions")
        if not isinstance(per_direction, dict) or set(per_direction) != set(record["directions"]):
            raise CatalogError(f"invalid direction dispositions for {record['id']}")
        if any(value not in ALLOWED_DISPOSITIONS for value in per_direction.values()):
            raise CatalogError(f"unknown direction disposition for {record['id']}")
    return {kind: counts[kind] for kind in EXPECTED_KIND_COUNTS}


def build_catalog(package_root: Path) -> dict[str, Any]:
    baseline_path = package_root / "doc" / "manual-baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    segments = _load_segments(package_root, baseline)
    first = next(segment for segment in segments if segment.logical_first == 1)
    records = [
        *_extract_part7(segments),
        *_extract_part4(first),
        *_extract_part5(first),
    ]
    records.sort(key=lambda record: str(record["id"]))
    counts = _validate_catalog(records)
    disposition_counts = Counter(record["disposition"] for record in records)
    return {
        "schema_version": 2,
        "manual_publication": baseline["manual"]["publication"],
        "manual_segment_sha256": [segment["sha256"] for segment in baseline["manual"]["segments"]],
        "device_baseline": baseline["device_baseline"],
        "entity_count": len(records),
        "callable_entity_count": len(records) - counts["automation_object"],
        "counts_by_kind": counts,
        "counts_by_disposition": {
            disposition: disposition_counts.get(disposition, 0)
            for disposition in sorted(ALLOWED_DISPOSITIONS)
        },
        "entities": records,
    }


def _serialized(catalog: dict[str, Any]) -> str:
    return json.dumps(catalog, ensure_ascii=False, indent=2) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--package-root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("doc/command-catalog.json"),
        help="output path relative to the package root",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="fail instead of writing when the committed catalog differs",
    )
    args = parser.parse_args(argv)
    package_root = args.package_root.resolve()
    output = args.output if args.output.is_absolute() else package_root / args.output
    rendered = _serialized(build_catalog(package_root))
    if args.check:
        if not output.exists() or output.read_text(encoding="utf-8") != rendered:
            raise CatalogError(f"catalog is stale: {output}")
    else:
        output.write_text(rendered, encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
