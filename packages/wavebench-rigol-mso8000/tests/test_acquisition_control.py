from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError, OperationTimeout
from wavebench.instruments.scope_extensions import (
    ScopeAcquisitionControlBaseline,
    ScopeAcquisitionControlSnapshot,
    ScopeAcquisitionRunState,
)
from wavebench.services.scope_extension_service import ScopeExtensionService
from wavebench.transport.contracts import ReplayPolicy
from wavebench.transport.guarded import GuardedAuditedTransport

from wavebench_rigol_mso8000 import descriptor as plugin_descriptor
from wavebench_rigol_mso8000.driver import MSO8104Scope


class AcquisitionControlTransport:
    resource = "test"

    def __init__(
        self,
        *,
        status: str = "STOP",
        statuses: list[str] | None = None,
        trigger_sweep: str = "NORM",
        acquisition_type: str = "NORM",
    ) -> None:
        self.status = status
        self.statuses = list(statuses or [])
        self.trigger_sweep = trigger_sweep
        self.acquisition_type = acquisition_type
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.fail_writes: set[str] = set()
        self.close_calls = 0

    def record_event(self, direction: str, text: str) -> None:
        del direction, text

    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        del replay
        self.queries.append(command)
        if command == ":TRIGger:STATus?":
            if self.statuses:
                return self.statuses.pop(0)
            return self.status
        if command == ":TRIGger:SWEep?":
            return self.trigger_sweep
        if command == ":ACQuire:TYPE?":
            return self.acquisition_type
        if command == "*IDN?":
            return "RIGOL TECHNOLOGIES,MSO8104,TEST,00.02.02"
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command in self.fail_writes:
            raise InstrumentError(f"injected write failure: {command}")
        if command == ":STOP":
            self.status = "STOP"
        elif command == ":RUN":
            self.status = "RUN"
        elif command == ":SINGle":
            self.trigger_sweep = "SING"
        elif command == ":TRIGger:SWEep AUTO":
            self.trigger_sweep = "AUTO"
        elif command == ":TRIGger:SWEep NORMal":
            self.trigger_sweep = "NORM"
        elif command == ":TRIGger:SWEep SINGle":
            self.trigger_sweep = "SING"
        elif command == ":ACQuire:TYPE NORMal":
            self.acquisition_type = "NORM"
        elif command == ":ACQuire:TYPE PEAK":
            self.acquisition_type = "PEAK"
        elif command == ":ACQuire:TYPE AVERages":
            self.acquisition_type = "AVER"
        elif command == ":ACQuire:TYPE HRESolution":
            self.acquisition_type = "HRES"
        else:
            raise AssertionError(f"unexpected write: {command}")

    def close(self) -> None:
        self.close_calls += 1


def _baseline(
    *,
    status: str = "STOP",
    trigger_sweep: str = "NORM",
    acquisition_type: str = "NORM",
) -> ScopeAcquisitionControlBaseline:
    phase = {
        "STOP": "stopped",
        "WAIT": "waiting",
        "RUN": "acquiring",
    }.get(status, "unknown")
    trigger_mode = {
        "AUTO": "auto",
        "NORM": "normal",
        "SING": "single",
    }[trigger_sweep]
    return ScopeAcquisitionControlBaseline(
        context_id="context",
        session_epoch="epoch",
        baseline_nonce="nonce",
        snapshot=ScopeAcquisitionControlSnapshot(
            run_state=ScopeAcquisitionRunState(phase, trigger_mode, status),
            trigger_state_token=trigger_sweep,
            acquisition_state_token=acquisition_type,
        ),
        restore_order=("scope.run_state", "scope.trigger", "scope.acquisition"),
    )


@pytest.mark.parametrize(
    ("status", "phase"),
    [
        ("STOP", "stopped"),
        ("WAIT", "waiting"),
        ("RUN", "acquiring"),
        ("TD", "acquiring"),
        ("AUTO", "acquiring"),
    ],
)
def test_acquisition_run_state_uses_one_direct_trigger_status_query(
    status: str,
    phase: str,
) -> None:
    transport = AcquisitionControlTransport(status=status)

    state = MSO8104Scope(transport=transport).get_acquisition_run_state()

    assert state == ScopeAcquisitionRunState(phase, "unknown", status)
    assert transport.queries == [":TRIGger:STATus?"]
    assert transport.writes == []


def test_acquisition_control_snapshot_preserves_only_changed_trigger_and_acquisition_tokens() -> None:
    transport = AcquisitionControlTransport(
        status="STOP",
        trigger_sweep="AUTO",
        acquisition_type="PEAK",
    )

    snapshot = MSO8104Scope(transport=transport).snapshot_acquisition_control()

    assert snapshot == ScopeAcquisitionControlSnapshot(
        run_state=ScopeAcquisitionRunState("stopped", "auto", "STOP"),
        trigger_state_token="AUTO",
        acquisition_state_token="PEAK",
    )
    assert transport.queries == [
        ":TRIGger:STATus?",
        ":TRIGger:SWEep?",
        ":ACQuire:TYPE?",
    ]
    assert transport.writes == []


def test_start_normal_verifies_sweep_and_observed_running_phase() -> None:
    transport = AcquisitionControlTransport(statuses=["WAIT"])
    scope = MSO8104Scope(transport=transport)

    state = scope.start_continuous(trigger_mode="normal", baseline=_baseline())

    assert state == ScopeAcquisitionRunState("waiting", "normal", "WAIT")
    assert transport.writes == [":TRIGger:SWEep NORMal", ":RUN"]
    assert transport.queries == [":TRIGger:SWEep?", ":TRIGger:STATus?"]
    assert scope.acquisition_writes_blocked is False


def test_start_rejects_unsupported_mode_without_io() -> None:
    transport = AcquisitionControlTransport()

    with pytest.raises(ConfigError, match="only normal"):
        MSO8104Scope(transport=transport).start_continuous(
            trigger_mode="auto",
            baseline=_baseline(),
        )

    assert transport.queries == []
    assert transport.writes == []


def test_start_latches_when_postcondition_is_not_proven() -> None:
    transport = AcquisitionControlTransport(statuses=["STOP"])
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="outcome is uncertain"):
        scope.start_continuous(trigger_mode="normal", baseline=_baseline())

    assert transport.writes == [":TRIGger:SWEep NORMal", ":RUN"]
    assert scope.acquisition_writes_blocked is True


def test_stop_is_idempotent_when_current_status_is_stopped() -> None:
    transport = AcquisitionControlTransport(status="STOP")

    state = MSO8104Scope(transport=transport).stop_acquisition()

    assert state == ScopeAcquisitionRunState("stopped", "unknown", "STOP")
    assert transport.queries == [":TRIGger:STATus?"]
    assert transport.writes == []


def test_stop_writes_once_then_requires_stopped_readback() -> None:
    transport = AcquisitionControlTransport(status="WAIT")

    state = MSO8104Scope(transport=transport).stop_acquisition()

    assert state == ScopeAcquisitionRunState("stopped", "unknown", "STOP")
    assert transport.queries == [":TRIGger:STATus?", ":TRIGger:STATus?"]
    assert transport.writes == [":STOP"]


def test_single_requires_post_arm_transition_before_terminal_stop() -> None:
    transport = AcquisitionControlTransport(statuses=["WAIT", "RUN", "STOP"])
    scope = MSO8104Scope(
        transport=transport,
        trigger_poll_interval_s=0.0,
        _clock=lambda: 0.0,
        _sleep=lambda _: None,
    )

    completion = scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert completion.proof == "state_transition"
    assert completion.proof_baseline_stage == "original_atomic_arm"
    assert completion.original_state == _baseline().snapshot.run_state
    assert completion.observed_states == (
        ScopeAcquisitionRunState("waiting", "single", "WAIT"),
        ScopeAcquisitionRunState("acquiring", "single", "RUN"),
        ScopeAcquisitionRunState("stopped", "single", "STOP"),
    )
    assert transport.writes == [":SINGle"]
    assert transport.queries == [
        ":TRIGger:SWEep?",
        ":TRIGger:STATus?",
        ":TRIGger:STATus?",
        ":TRIGger:STATus?",
    ]


def test_single_fails_closed_if_stop_is_the_first_observed_status() -> None:
    transport = AcquisitionControlTransport(statuses=["STOP"])
    scope = MSO8104Scope(transport=transport, _clock=lambda: 0.0)

    with pytest.raises(DataError, match="unproven"):
        scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert transport.writes == [":SINGle"]
    assert scope.acquisition_writes_blocked is True


def test_single_does_not_treat_auto_status_as_single_completion_evidence() -> None:
    transport = AcquisitionControlTransport(statuses=["AUTO"])
    scope = MSO8104Scope(transport=transport, _clock=lambda: 0.0)

    with pytest.raises(DataError, match="unproven"):
        scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert transport.writes == [":SINGle"]
    assert scope.acquisition_writes_blocked is True


def test_single_honors_expired_deadline_without_instrument_io() -> None:
    transport = AcquisitionControlTransport()
    scope = MSO8104Scope(transport=transport, _clock=lambda: 2.0)

    with pytest.raises(OperationTimeout, match="before arming"):
        scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert transport.queries == []
    assert transport.writes == []


def test_restore_writes_stop_then_baseline_trigger_and_acquisition_without_queries() -> None:
    transport = AcquisitionControlTransport()
    baseline = _baseline(trigger_sweep="AUTO", acquisition_type="AVER")

    result = MSO8104Scope(transport=transport).restore_acquisition_control(baseline)

    assert result.status == "completed"
    assert result.attempted_fields == (
        "scope.run_state",
        "scope.trigger",
        "scope.acquisition",
    )
    assert result.restored_fields == result.attempted_fields
    assert transport.writes == [
        ":STOP",
        ":TRIGger:SWEep AUTO",
        ":ACQuire:TYPE AVERages",
    ]
    assert transport.queries == []


def test_restore_returns_partial_failure_evidence_for_core_cleanup() -> None:
    transport = AcquisitionControlTransport()
    transport.fail_writes.add(":TRIGger:SWEep NORMal")

    result = MSO8104Scope(transport=transport).restore_acquisition_control(_baseline())

    assert result.status == "failed"
    assert result.attempted_fields == ("scope.run_state", "scope.trigger")
    assert result.restored_fields == ("scope.run_state",)
    assert result.error_code == "restore_write_failed"
    assert transport.queries == []


def test_restore_verification_is_a_fresh_three_query_snapshot() -> None:
    transport = AcquisitionControlTransport(
        status="STOP",
        trigger_sweep="NORM",
        acquisition_type="NORM",
    )

    snapshot = MSO8104Scope(transport=transport).verify_acquisition_control_restored(
        _baseline()
    )

    assert snapshot == _baseline().snapshot
    assert transport.queries == [
        ":TRIGger:STATus?",
        ":TRIGger:SWEep?",
        ":ACQuire:TYPE?",
    ]
    assert transport.writes == []


def test_closed_driver_rejects_acquisition_state_before_io() -> None:
    transport = AcquisitionControlTransport()
    scope = MSO8104Scope(transport=transport)
    scope.close()

    with pytest.raises(InstrumentError, match="closed"):
        scope.get_acquisition_run_state()

    assert transport.queries == []
    assert transport.writes == []


def _extension_service(
    backend: AcquisitionControlTransport,
) -> tuple[ScopeExtensionService, MSO8104Scope, GuardedAuditedTransport]:
    transport = GuardedAuditedTransport(backend)
    driver = MSO8104Scope(
        transport=transport,
        trigger_poll_interval_s=0.0,
        _clock=lambda: 0.0,
        _sleep=lambda _: None,
    )
    return (
        ScopeExtensionService(
            driver=driver,
            descriptor=plugin_descriptor(),
            session_state=transport.session_state,
            connection_timeout_ms=1_000,
        ),
        driver,
        transport,
    )


def test_current_core_service_accepts_single_transition_proof() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP", "WAIT", "STOP"])
    service, driver, transport = _extension_service(backend)

    result = service.acquire_single()

    assert result.value.proof == "state_transition"
    assert result.value.state == ScopeAcquisitionRunState("stopped", "single", "STOP")
    assert backend.writes == [":SINGle"]
    assert driver.acquisition_writes_blocked is False
    assert transport.session_state.health.value == "healthy"


def test_current_core_service_restores_after_unproven_single() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP", "STOP"])
    service, driver, transport = _extension_service(backend)

    with pytest.raises(DataError, match="unproven"):
        service.acquire_single()

    assert backend.writes == [
        ":SINGle",
        ":STOP",
        ":TRIGger:SWEep NORMal",
        ":ACQuire:TYPE NORMal",
    ]
    assert driver.acquisition_writes_blocked is True
    assert transport.session_state.health.value == "healthy"
