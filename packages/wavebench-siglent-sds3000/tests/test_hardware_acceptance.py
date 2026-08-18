from __future__ import annotations

import json
from pathlib import Path
import re


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
EVIDENCE_PATH = PACKAGE_ROOT / "doc" / "hardware-acceptance.json"


def test_redacted_hardware_acceptance_meets_m5_limits() -> None:
    evidence = json.loads(EVIDENCE_PATH.read_text(encoding="utf-8"))

    assert evidence["schema_version"] == 1
    assert evidence["accepted_model"] == "SDS3054"
    assert evidence["accepted_firmware"] == "8.4.1"
    assert evidence["m4_waveform_transfer"]["transfer_state_restored"] is True
    capture = evidence["m5_dual_channel_capture"]
    assert capture["one_acquisition_per_round"] is True
    limits = capture["acceptance_limits"]
    assert len(capture["rounds"]) == 3
    for round_result in capture["rounds"]:
        assert round_result["scope_state_restored"] is True
        for channel in ("1", "2"):
            result = round_result["channels"][channel]
            assert result["samples"] == 100002
            assert abs(result["frequency_hz"] - 1000.0) / 1000.0 <= limits[
                "frequency_relative_tolerance"
            ]
            assert abs(result["vpp_v"] - 1.0) <= limits["vpp_relative_tolerance"]
        assert round_result["vpp_difference_ratio"] <= limits[
            "maximum_channel_vpp_difference_ratio"
        ]
        assert round_result["correlation"] >= limits["minimum_correlation"]

    audit = capture["audit_per_round"]
    assert audit["write_requests"] == audit["write_completed"]
    assert audit["blocked_requests"] == 0
    assert audit["binary_write_requests"] == 0
    assert evidence["postconditions"]["source_output"] == "OFF"
    assert evidence["postconditions"]["source_profile_restored"] is True
    assert evidence["postconditions"]["independent_read_only_postcheck_writes"] == 0


def test_public_hardware_evidence_contains_no_private_artifacts() -> None:
    serialized = EVIDENCE_PATH.read_text(encoding="utf-8")
    evidence = json.loads(serialized)
    redaction = evidence["redaction"]

    assert all(value is False for value in redaction.values())
    assert re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", serialized) is None
    assert re.search(r"(?i)\b(?:[0-9a-f]{2}[:-]){5}[0-9a-f]{2}\b", serialized) is None
    assert re.search(r"(?i)\b(?:[0-9a-f]{1,4}:){2,}[0-9a-f]{0,4}\b", serialized) is None
    assert re.search(r"(?i)\b(?:VICP|TCPIP\d*|USB\d*|GPIB\d*)::", serialized) is None
    assert re.search(r"\bSDS3000B[A-Z0-9]{6,}\b", serialized) is None
    assert re.search(
        r"(?i)\b[a-z0-9][a-z0-9-]{1,62}\.(?:internal|lan|local)\b",
        serialized,
    ) is None
    assert "commands.log" not in serialized
    assert "restore-journal" not in serialized
    assert "voltages_v" not in serialized
