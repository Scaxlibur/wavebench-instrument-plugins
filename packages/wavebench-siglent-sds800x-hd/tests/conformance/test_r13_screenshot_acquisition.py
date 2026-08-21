from __future__ import annotations

from dataclasses import replace
import time

import pytest


pytest.importorskip(
    "wavebench.instruments.scope_extensions",
    reason="WaveBench scope R1.3 public contract is unavailable",
)

from wavebench.errors import DataError, OperationTimeout
from wavebench.instruments import (
    ScopeAcquisitionCompletion,
    ScopeContinuousAcquisitionRequest,
    ScopeScreenshot,
    ScopeScreenshotRequest,
)
from wavebench.services import ScopeExtensionService
from wavebench.transport.guarded import GuardedAuditedTransport
from wavebench.transport.session import SessionHealth

from wavebench_siglent_sds800x_hd import descriptor
from wavebench_siglent_sds800x_hd.driver import SDS800XHDScope

from ._r13_control_fixture import (
    SCREENSHOT_REQUEST,
    SDSR13ControlBackend,
    make_control_service,
    png,
)


def _production_service() -> tuple[
    ScopeExtensionService,
    SDS800XHDScope,
    GuardedAuditedTransport,
    SDSR13ControlBackend,
]:
    backend = SDSR13ControlBackend()
    transport = GuardedAuditedTransport(backend)  # type: ignore[arg-type]
    driver = SDS800XHDScope(transport, capture_poll_interval_s=0)
    service = ScopeExtensionService(
        driver=driver,
        descriptor=descriptor(),
        session_state=transport.session_state,
        connection_timeout_ms=1_000,
    )
    return service, driver, transport, backend


def test_sds_message_screenshot_strips_only_profile_content_trailing() -> None:
    service, driver, transport, backend = make_control_service()

    result = service.screenshot_v2(SCREENSHOT_REQUEST)

    assert isinstance(result.value, ScopeScreenshot)
    assert result.value.data == png()
    assert backend.screenshot_payload == result.value.data + b"\x0a"
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


def test_production_driver_screenshot_uses_public_service_contract() -> None:
    service, _, transport, backend = _production_service()

    result = service.screenshot_v2(
        ScopeScreenshotRequest(menu_mode="device", color_mode="color")
    )

    assert isinstance(result.value, ScopeScreenshot)
    assert result.value.data == png()
    assert backend.binary_queries == [":PRINt? PNG,NORMal"]
    assert transport.session_state.health is SessionHealth.HEALTHY


def test_production_driver_screenshot_failure_leaves_next_query_synchronized() -> None:
    service, _, transport, backend = _production_service()
    backend.screenshot_payload = png() + b"\x01"

    with pytest.raises(DataError, match="content trailing"):
        service.screenshot_v2(
            ScopeScreenshotRequest(menu_mode="device", color_mode="color")
        )

    assert service.acquisition_run_state().value.phase == "stopped"
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


def test_production_driver_single_uses_state_transition_proof() -> None:
    service, _, transport, backend = _production_service()

    result = service.acquire_single()

    assert isinstance(result.value, ScopeAcquisitionCompletion)
    assert result.value.proof == "state_transition"
    assert [state.phase for state in result.value.observed_states] == ["arming", "stopped"]
    assert backend.trigger_mode == "SINGLE"
    assert transport.session_state.health is SessionHealth.HEALTHY


def test_production_driver_missing_transition_restores_real_setting_tokens() -> None:
    service, _, transport, backend = _production_service()
    backend.status_sequence_on_run = ("Stop",)
    backend.status_sequence_on_stop = ("Ready", "Stop")

    with pytest.raises(ValueError, match="state-transition proof"):
        service.acquire_single()

    assert backend.trigger_status == "Stop"
    assert backend.trigger_mode == "NORMAL"
    assert backend.acquisition_mode == "YT"
    assert backend.writes[-4:] == [
        ":TRIGger:STOP",
        ":ACQuire:MODE YT",
        ":TRIGger:MODE NORMAL",
        ":TRIGger:STOP",
    ]
    assert transport.session_state.health is SessionHealth.HEALTHY


@pytest.mark.parametrize("mode", ["auto", "normal"])
def test_production_driver_continuous_start_and_stop(mode: str) -> None:
    service, _, transport, backend = _production_service()
    backend.status_sequence_on_run = ("Arm",)

    started = service.start_acquisition(ScopeContinuousAcquisitionRequest(mode)).value
    stopped = service.stop_acquisition().value

    assert started.phase == "arming"
    assert started.trigger_mode == mode
    assert stopped.phase == "stopped"
    assert transport.session_state.health is SessionHealth.HEALTHY


def test_production_driver_invalid_start_restores_and_allows_next_operation() -> None:
    service, driver, transport, _ = _production_service()
    original = driver.start_continuous

    def invalid_start(*, trigger_mode, baseline):
        return replace(
            original(trigger_mode=trigger_mode, baseline=baseline),
            phase="stopped",
        )

    driver.start_continuous = invalid_start  # type: ignore[method-assign]
    try:
        with pytest.raises(DataError, match="postcondition") as raised:
            service.start_acquisition(ScopeContinuousAcquisitionRequest("auto"))
    finally:
        driver.start_continuous = original  # type: ignore[method-assign]

    assert raised.value.scope_operation_diagnostics["cleanup"]["verification"][
        "status"
    ] == "verified"
    assert service.acquisition_run_state().value.phase == "stopped"
    assert transport.session_state.health is SessionHealth.HEALTHY


def test_production_driver_single_timeout_restores_and_verifies() -> None:
    service, driver, transport, backend = _production_service()
    driver.capture_poll_interval_s = 0.005
    backend.status_sequence_on_run = tuple("Arm" for _ in range(100))

    with pytest.raises(OperationTimeout, match="timed out") as raised:
        service.acquire_single(deadline=time.monotonic() + 0.02)

    assert raised.value.scope_operation_diagnostics["cleanup"]["verification"][
        "status"
    ] == "verified"
    assert transport.session_state.health is SessionHealth.HEALTHY


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
    assert backend.acquisition_mode == "YT"
    assert transport.session_state.health is SessionHealth.HEALTHY
    cleanup = raised.value.scope_operation_diagnostics["cleanup"]
    assert cleanup["restore"]["status"] == "completed"
    assert cleanup["verification"]["status"] == "verified"
