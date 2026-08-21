from __future__ import annotations

import pytest


pytest.importorskip(
    "wavebench.services.scope_extension_service",
    reason="WaveBench scope R1.3 internal infrastructure is unavailable",
)

from wavebench.errors import DataError
from wavebench.instruments.scope_extensions import (
    ScopeAcquisitionCompletion,
    ScopeScreenshot,
)
from wavebench.transport.session import SessionHealth

from ._r13_control_fixture import SCREENSHOT_REQUEST, make_control_service, png


def test_sds_message_screenshot_strips_only_profile_content_trailing() -> None:
    service, driver, transport, backend = make_control_service()

    result = service.screenshot_v2(SCREENSHOT_REQUEST)

    assert isinstance(result.value, ScopeScreenshot)
    assert result.value.data == png()
    assert backend.screenshot_payload == result.value.data + b"\x00"
    assert backend.binary_queries == [":PRINt? PNG,NORMal"]
    assert backend.writes == []
    assert driver.screenshot_recovery_calls == 0
    assert transport.session_state.health is SessionHealth.HEALTHY
    assert [phase["phase"] for phase in result.diagnostics["phases"]] == [
        "preflight",
        "main",
    ]
    assert result.diagnostics["baselines"] == []
    assert result.diagnostics["binary_budget"]["remaining_query_count"] == 0


def test_sds_stateless_screenshot_content_failure_requires_zero_recovery_io() -> None:
    service, driver, transport, backend = make_control_service()
    backend.screenshot_payload = png() + b"\x01"

    with pytest.raises(DataError, match="content trailing"):
        service.screenshot_v2(SCREENSHOT_REQUEST)

    assert backend.writes == []
    assert driver.screenshot_recovery_calls == 0
    assert transport.session_state.health is SessionHealth.HEALTHY


def test_sds_single_accepts_state_transition_without_promoting_count() -> None:
    service, driver, transport, backend = make_control_service()

    result = service.acquire_single()

    assert isinstance(result.value, ScopeAcquisitionCompletion)
    assert result.value.proof == "state_transition"
    assert [state.phase for state in result.value.observed_states] == ["arming", "stopped"]
    assert result.value.state.acquisition_count == 1
    assert result.value.baseline_count is None
    assert result.value.completed_count is None
    assert driver.acquisition_restore_calls == 0
    assert transport.session_state.health is SessionHealth.HEALTHY
    assert backend.writes[:2] == [":TRIGger:MODE SINGLE", ":TRIGger:RUN"]
    assert "*OPC?" not in backend.queries
    baseline = result.diagnostics["baselines"][0]
    assert baseline["consumption"] == "consumed"
    assert baseline["restore_succeeded"] is None


@pytest.mark.parametrize(
    ("proof", "message"),
    [
        ("no_transition", "state-transition proof"),
        ("count_without_epoch", "count proof"),
        ("identity_without_semantics", "identity proof"),
    ],
)
def test_sds_invalid_single_proofs_restore_control_baseline(
    proof: str,
    message: str,
) -> None:
    service, driver, transport, backend = make_control_service()
    driver.single_proof = proof

    with pytest.raises(ValueError, match=message) as raised:
        service.acquire_single()

    assert driver.acquisition_restore_calls == 1
    assert backend.trigger_status == "Stop"
    assert backend.trigger_mode == "NORMAL"
    assert backend.acquisition_mode == "SAMPLING"
    assert transport.session_state.health is SessionHealth.HEALTHY
    cleanup = raised.value.scope_operation_diagnostics["cleanup"]
    assert cleanup["restore"]["status"] == "completed"
    assert cleanup["verification"]["status"] == "verified"
