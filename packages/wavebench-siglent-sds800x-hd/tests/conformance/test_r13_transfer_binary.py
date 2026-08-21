from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest


pytest.importorskip(
    "wavebench.instruments.scope_extensions",
    reason="WaveBench scope R1.3 public contract is unavailable",
)

from wavebench.errors import DataError, TransportIOError
from wavebench.instruments import ScopeTraceData, ScopeTraceRef
from wavebench.transport.binary import parse_definite_block_response
from wavebench.transport.session import SessionHealth

from ._r13_transfer_fixture import INITIAL_TRACE_STATE, ieee_block, make_trace_service


def test_sds_definite_block_vector_has_exact_framing_accounting() -> None:
    payload = np.asarray([-32768, 10], dtype="<i2").tobytes()

    result = parse_definite_block_response(ieee_block(payload), max_bytes=len(payload))

    assert result.data == payload
    assert result.declared_length == 4
    assert result.framing_header_bytes == 3
    assert result.consumed_bytes == 7
    with pytest.raises(TransportIOError) as raised:
        parse_definite_block_response(ieee_block(payload)[:-1], max_bytes=len(payload))
    assert raised.value.reason_code == "binary_truncated"


def test_sds_trace_success_restores_all_typed_transfer_fields() -> None:
    service, driver, transport, backend = make_trace_service()

    result = service.fetch_trace(ScopeTraceRef("analog", index=1), points=4)

    assert isinstance(result.value, ScopeTraceData)
    np.testing.assert_allclose(result.value.values, [-0.002, -0.001, 0.001, 0.002])
    assert backend.trace_state == INITIAL_TRACE_STATE
    assert backend.binary_queries == [":WAVeform:DATA?", ":WAVeform:DATA?"]
    assert driver.restore_calls == 1
    assert transport.session_state.health is SessionHealth.HEALTHY
    assert [phase["phase"] for phase in result.diagnostics["phases"]] == [
        "preflight",
        "main",
        "success_restore",
        "cleanup_verification",
    ]
    budget = result.diagnostics["binary_budget"]
    assert budget["remaining_query_count"] == 254
    assert budget["remaining_operation_bytes"] == 67_108_856
    baseline = result.diagnostics["baselines"][0]
    assert baseline["consumption"] == "consumed"
    assert baseline["restore_succeeded"] is True
    assert baseline["verification_succeeded"] is True
    assert len(baseline["nonce_digest"]) == 16
    assert "baseline_nonce" not in baseline


def test_sds_post_transfer_failure_keeps_primary_and_recovers_fresh_state() -> None:
    service, driver, transport, backend = make_trace_service()
    driver.fail_after_binary = True

    with pytest.raises(DataError, match="post-transfer decode failure") as raised:
        service.fetch_trace(ScopeTraceRef("analog", index=1), points=4)

    assert backend.trace_state == INITIAL_TRACE_STATE
    assert driver.restore_calls == 1
    assert transport.session_state.health is SessionHealth.HEALTHY
    diagnostics = raised.value.scope_operation_diagnostics
    assert diagnostics["cleanup_error"] is None
    assert diagnostics["trace_cleanup"]["restore"]["status"] == "completed"
    assert diagnostics["trace_cleanup"]["verification"]["status"] == "verified"


def test_sds_restore_gap_does_not_hide_primary_and_poison_is_fail_closed() -> None:
    service, driver, transport, backend = make_trace_service()
    driver.fail_after_binary = True
    driver.restore_skip_field = "scope.waveform_byte_order"

    with pytest.raises(DataError, match="post-transfer decode failure") as raised:
        service.fetch_trace(ScopeTraceRef("analog", index=1), points=4)

    assert backend.trace_state["scope.waveform_byte_order"] == "LSB"
    assert transport.session_state.health is SessionHealth.POISONED
    diagnostics = raised.value.scope_operation_diagnostics
    assert diagnostics["cleanup_error"] is not None
    assert diagnostics["trace_cleanup"]["restore"]["status"] == "failed"
    assert diagnostics["trace_cleanup"]["verification"]["status"] == "mismatch"


def test_redacted_hardware_evidence_separates_new_screenshot_from_legacy_waveform() -> None:
    path = Path(__file__).parent / "fixtures" / "sds804x_hd_tcpip_redacted.json"
    evidence = json.loads(path.read_text(encoding="utf-8"))

    assert evidence["instrument"]["firmware"] == "4.8.12.1.1.6.5"
    assert evidence["waveform_multiblock"]["chunk_points"] == [5_000_000, 5_000_000]
    assert evidence["waveform_multiblock"]["backend_query_binary_conformant"] is False
    assert evidence["screenshot"]["message_boundary_backend_conformant"] is True
    assert evidence["screenshot"]["post_message_failure_next_query"] == "synchronized"
    assert evidence["acquisition"]["single_failure_cleanup"] == "verified"
    assert evidence["acquisition"]["count_role"] == "diagnostic_only"
    serialized = json.dumps(evidence, ensure_ascii=False).lower()
    for forbidden in ("serial_number", "ip_address", "raw_waveform", "raw_png"):
        assert forbidden not in serialized
