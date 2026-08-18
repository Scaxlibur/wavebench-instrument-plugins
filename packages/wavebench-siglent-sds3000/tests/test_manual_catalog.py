from __future__ import annotations

import json
from pathlib import Path
import sys
from collections import Counter

import pytest
from wavebench.instruments.capabilities import CAPABILITY_METHODS
from wavebench_siglent_sds3000 import descriptor as plugin_descriptor


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PACKAGE_ROOT))

from tools.manual_catalog import (  # noqa: E402
    ALLOWED_DISPOSITIONS,
    EXPECTED_KIND_COUNTS,
    build_catalog,
    canonical_automation_path,
    parse_html_table,
)


CATALOG_PATH = PACKAGE_ROOT / "doc" / "command-catalog.json"
BASELINE_PATH = PACKAGE_ROOT / "doc" / "manual-baseline.json"
CAPABILITY_MATRIX_PATH = PACKAGE_ROOT / "doc" / "wavebench-capability-matrix.json"


def test_parses_converter_html_tables_without_vendor_dependencies() -> None:
    body = (
        "<table><tr><td>Short</td><td>Long</td></tr><tr><td>*IDN?</td><td>*IDN?</td></tr></table>"
    )

    assert parse_html_table(body) == [
        ["Short", "Long"],
        ["*IDN?", "*IDN?"],
    ]


@pytest.mark.parametrize(
    ("raw", "canonical"),
    [
        ("appPreferences.Display", "app.Preferences.Display"),
        ("app..PassFail.Qn", "app.PassFail.Qn"),
        ("app Zoom.ResetAll", "app.Zoom.ResetAll"),
        ("app.Acquisition.Trigger.", "app.Acquisition.Trigger.<Type>"),
    ],
)
def test_normalizes_known_manual_path_artifacts(raw: str, canonical: str) -> None:
    assert canonical_automation_path(raw) == canonical


def test_committed_catalog_freezes_the_complete_explicit_denominator() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    baseline = json.loads(BASELINE_PATH.read_text(encoding="utf-8"))

    assert catalog["schema_version"] == 2
    assert catalog["entity_count"] == 578
    assert catalog["callable_entity_count"] == 478
    assert catalog["counts_by_kind"] == EXPECTED_KIND_COUNTS
    assert catalog["manual_segment_sha256"] == [
        segment["sha256"] for segment in baseline["manual"]["segments"]
    ]

    identifiers = [entity["id"] for entity in catalog["entities"]]
    assert len(identifiers) == len(set(identifiers)) == catalog["entity_count"]
    assert {entity["disposition"] for entity in catalog["entities"]} <= ALLOWED_DISPOSITIONS
    assert all(
        entity["directions"] or entity["kind"] == "automation_object"
        for entity in catalog["entities"]
    )
    assert sum(catalog["counts_by_disposition"].values()) == catalog["entity_count"]
    assert catalog["counts_by_disposition"] == {
        "core-gap-rfc": 8,
        "firmware-unverified": 340,
        "implemented": 16,
        "model-not-applicable": 2,
        "option-absent": 78,
        "partially-implemented": 2,
        "planned": 0,
        "unsafe-quarantined": 132,
    }


def test_catalog_does_not_copy_vendor_prose() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))

    forbidden_keys = {"description", "example", "response_text", "manual_text"}
    assert all(not (forbidden_keys & entity.keys()) for entity in catalog["entities"])


def test_only_known_part7_body_anomaly_is_missing() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    missing = [
        entity["short"]
        for entity in catalog["entities"]
        if "body-heading-not-present" in entity.get("manual_anomalies", [])
    ]

    assert missing == ["DPSU"]


def test_idn_catalog_entry_tracks_the_implemented_capability() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    identity = next(entity for entity in catalog["entities"] if entity.get("short") == "*IDN?")

    assert identity["disposition"] == "implemented"
    assert identity["directions"] == ["query"]
    assert identity["wavebench_capabilities"] == ["scope.idn"]


def test_m5_implemented_legacy_entries_match_the_text_transfer_and_capture_protocols() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    implemented = {
        entity["short"]
        for entity in catalog["entities"]
        if entity["kind"] == "legacy_command" and entity["disposition"] == "implemented"
    }

    assert implemented == {
        "*IDN?",
        "ARM",
        "CFMT",
        "CHDR",
        "CMR?",
        "CORD",
        "CPL",
        "DDR?",
        "EXR?",
        "STOP",
        "TDIV",
        "TRA",
        "TRMD",
        "VDIV",
        "WAIT",
        "WFSU",
    }


def test_m4_waveform_query_is_not_misreported_as_waveform_write_support() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    waveform = next(entity for entity in catalog["entities"] if entity.get("short") == "WF")

    assert waveform["disposition"] == "partially-implemented"
    assert waveform["direction_dispositions"] == {
        "command": "unsafe-quarantined",
        "query": "implemented",
    }
    assert waveform["wavebench_capabilities"] == [
        "scope.fetch_waveform",
        "scope.capture_waveform",
        "scope.capture_waveforms",
    ]


def test_m5_opc_query_is_not_misreported_as_opc_command_support() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    operation_complete = next(
        entity for entity in catalog["entities"] if entity.get("short") == "*OPC"
    )

    assert operation_complete["disposition"] == "partially-implemented"
    assert operation_complete["direction_dispositions"] == {
        "command": "firmware-unverified",
        "query": "implemented",
    }
    assert operation_complete["wavebench_capabilities"] == [
        "scope.capture_waveform",
        "scope.capture_waveforms",
    ]


def test_m6_matrix_disposes_every_wavebench_scope_capability() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    matrix = json.loads(CAPABILITY_MATRIX_PATH.read_text(encoding="utf-8"))
    entries = matrix["capabilities"]
    scope_capabilities = [
        capability for capability in CAPABILITY_METHODS if capability.startswith("scope.")
    ]

    assert matrix["schema_version"] == 1
    assert matrix["wavebench_version"] == "0.8.22"
    assert matrix["scope_capability_count"] == len(scope_capabilities) == 19
    assert [entry["capability"] for entry in entries] == scope_capabilities
    assert len({entry["capability"] for entry in entries}) == len(entries)

    dispositions = Counter(entry["disposition"] for entry in entries)
    assert matrix["counts_by_disposition"] == dict(sorted(dispositions.items()))
    declared = {entry["capability"] for entry in entries if entry["declared"]}
    implemented = {
        entry["capability"] for entry in entries if entry["disposition"] == "implemented"
    }
    assert declared == implemented == set(plugin_descriptor().capabilities)
    assert matrix["declared_capability_count"] == len(declared) == 6

    catalog_ids = {entity["id"] for entity in catalog["entities"]}
    assert all(entry["manual_entities"] for entry in entries)
    assert {
        entity
        for entry in entries
        for entity in entry["manual_entities"]
    } <= catalog_ids


def test_local_manual_regenerates_the_committed_catalog() -> None:
    origins = list((PACKAGE_ROOT / "doc" / "vendor-local").rglob("*_origin.pdf"))
    if len(origins) != 3:
        pytest.skip("ignored local manual segments are not available")

    committed = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    assert build_catalog(PACKAGE_ROOT) == committed
