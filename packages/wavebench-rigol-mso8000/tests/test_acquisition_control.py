from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError, OperationTimeout
from wavebench.instruments.scope_extensions import (
    ScopeAcquisitionControlBaseline,
    ScopeAcquisitionControlSnapshot,
    ScopeContinuousAcquisitionRequest,
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
        single_write_trigger_sweep: str = "SING",
        acquisition_type: str = "NORM",
    ) -> None:
        self.status = status
        self.statuses = list(statuses or [])
        self.trigger_sweep = trigger_sweep
        self.single_write_trigger_sweep = single_write_trigger_sweep
        self.acquisition_type = acquisition_type
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.events: list[tuple[str, str]] = []
        self.fail_writes: set[str] = set()
        self.fail_query_on_calls: dict[str, set[int]] = {}
        self._query_call_counts: dict[str, int] = {}
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
        self.events.append(("query", command))
        call_count = self._query_call_counts.get(command, 0) + 1
        self._query_call_counts[command] = call_count
        if call_count in self.fail_query_on_calls.get(command, set()):
            raise InstrumentError(f"injected query failure: {command}")
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
        self.events.append(("write", command))
        if command in self.fail_writes:
            raise InstrumentError(f"injected write failure: {command}")
        if command == ":STOP":
            self.status = "STOP"
        elif command == ":RUN":
            self.status = "RUN"
        elif command == ":SINGle":
            self.trigger_sweep = self.single_write_trigger_sweep
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
        ("TD", "unknown"),
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


def test_single_uses_state_transition_after_verified_single_mode_wait() -> None:
    transport = AcquisitionControlTransport(statuses=["WAIT", "STOP"])
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
        ScopeAcquisitionRunState("stopped", "single", "STOP"),
    )
    assert transport.writes == [":SINGle"]
    assert transport.events == [
        ("write", ":SINGle"),
        ("query", ":TRIGger:SWEep?"),
        ("query", ":TRIGger:STATus?"),
        ("query", ":TRIGger:STATus?"),
    ]


def test_single_uses_state_transition_after_verified_single_mode_td() -> None:
    transport = AcquisitionControlTransport(statuses=["TD", "STOP"])
    scope = MSO8104Scope(
        transport=transport,
        trigger_poll_interval_s=0.0,
        _clock=lambda: 0.0,
        _sleep=lambda _: None,
    )

    completion = scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert completion.proof == "state_transition"
    assert completion.observed_states == (
        ScopeAcquisitionRunState("arming", "single", "TD"),
        ScopeAcquisitionRunState("stopped", "single", "STOP"),
    )
    assert transport.events == [
        ("write", ":SINGle"),
        ("query", ":TRIGger:SWEep?"),
        ("query", ":TRIGger:STATus?"),
        ("query", ":TRIGger:STATus?"),
    ]


def test_single_queries_initial_status_before_waiting_to_poll() -> None:
    transport = AcquisitionControlTransport(statuses=["WAIT", "STOP"])
    sleeps: list[float] = []
    scope = MSO8104Scope(
        transport=transport,
        trigger_poll_interval_s=0.05,
        _clock=lambda: 0.0,
        _sleep=sleeps.append,
    )

    completion = scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert completion.state.phase == "stopped"
    assert sleeps == [0.05]
    assert transport.queries == [
        ":TRIGger:SWEep?",
        ":TRIGger:STATus?",
        ":TRIGger:STATus?",
    ]


def test_single_expires_before_mode_readback_without_a_query() -> None:
    transport = AcquisitionControlTransport()
    clock_values = iter((0.0, 1.0))
    scope = MSO8104Scope(
        transport=transport,
        _clock=lambda: next(clock_values),
    )

    with pytest.raises(OperationTimeout, match="before mode readback"):
        scope.acquire_single(baseline=_baseline(), deadline=0.5)

    assert transport.writes == [":SINGle"]
    assert transport.queries == []


def test_single_expires_after_mode_readback_before_initial_status() -> None:
    transport = AcquisitionControlTransport()
    clock_values = iter((0.0, 0.0, 1.0))
    scope = MSO8104Scope(
        transport=transport,
        _clock=lambda: next(clock_values),
    )

    with pytest.raises(OperationTimeout, match="before initial status"):
        scope.acquire_single(baseline=_baseline(), deadline=0.5)

    assert transport.writes == [":SINGle"]
    assert transport.queries == [":TRIGger:SWEep?"]


def test_single_does_not_query_after_poll_sleep_reaches_deadline() -> None:
    transport = AcquisitionControlTransport(statuses=["WAIT"])
    clock_values = iter((0.0, 0.0, 0.0, 0.0, 1.0))
    sleeps: list[float] = []
    scope = MSO8104Scope(
        transport=transport,
        trigger_poll_interval_s=0.05,
        _clock=lambda: next(clock_values),
        _sleep=sleeps.append,
    )

    with pytest.raises(OperationTimeout, match="did not reach STOP"):
        scope.acquire_single(baseline=_baseline(), deadline=0.5)

    assert transport.writes == [":SINGle"]
    assert transport.queries == [":TRIGger:SWEep?", ":TRIGger:STATus?"]
    assert sleeps == [0.05]


def test_single_accepts_terminal_stop_after_verified_single_mode_readback() -> None:
    transport = AcquisitionControlTransport(statuses=["STOP"])
    scope = MSO8104Scope(transport=transport, _clock=lambda: 0.0)

    completion = scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert completion.proof == "single_mode_readback_then_stopped"
    assert completion.post_arm_trigger_mode == "single"
    assert completion.observed_states == (
        ScopeAcquisitionRunState("stopped", "single", "STOP"),
    )
    assert transport.writes == [":SINGle"]
    assert transport.events == [
        ("write", ":SINGle"),
        ("query", ":TRIGger:SWEep?"),
        ("query", ":TRIGger:STATus?"),
    ]
    assert scope.acquisition_writes_blocked is False


@pytest.mark.parametrize("status", ["AUTO", "RUN"])
def test_single_rejects_unexpected_status_after_single_mode_readback(status: str) -> None:
    transport = AcquisitionControlTransport(statuses=[status])
    scope = MSO8104Scope(transport=transport, _clock=lambda: 0.0)

    with pytest.raises(DataError, match="unexpected trigger status"):
        scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert transport.writes == [":SINGle"]
    assert transport.queries == [":TRIGger:SWEep?", ":TRIGger:STATus?"]
    assert scope.acquisition_writes_blocked is True


def test_single_rejects_mode_readback_mismatch_before_status_query() -> None:
    transport = AcquisitionControlTransport(single_write_trigger_sweep="NORM")
    scope = MSO8104Scope(transport=transport, _clock=lambda: 0.0)

    with pytest.raises(DataError, match="did not confirm SINGLE"):
        scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert transport.events == [
        ("write", ":SINGle"),
        ("query", ":TRIGger:SWEep?"),
    ]
    assert scope.acquisition_writes_blocked is True


def test_single_latches_when_mode_readback_transport_fails() -> None:
    transport = AcquisitionControlTransport()
    transport.fail_query_on_calls[":TRIGger:SWEep?"] = {1}
    scope = MSO8104Scope(transport=transport, _clock=lambda: 0.0)

    with pytest.raises(InstrumentError, match="outcome is uncertain"):
        scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert transport.events == [
        ("write", ":SINGle"),
        ("query", ":TRIGger:SWEep?"),
    ]
    assert scope.acquisition_writes_blocked is True


def test_single_latches_when_initial_status_transport_fails() -> None:
    transport = AcquisitionControlTransport()
    transport.fail_query_on_calls[":TRIGger:STATus?"] = {1}
    scope = MSO8104Scope(transport=transport, _clock=lambda: 0.0)

    with pytest.raises(InstrumentError, match="outcome is uncertain"):
        scope.acquire_single(baseline=_baseline(), deadline=1.0)

    assert transport.writes == [":SINGle"]
    assert transport.queries == [":TRIGger:SWEep?", ":TRIGger:STATus?"]
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


@pytest.mark.parametrize(
    ("failed_command", "attempted", "restored"),
    [
        (":STOP", ("scope.run_state",), ()),
        (
            ":TRIGger:SWEep NORMal",
            ("scope.run_state", "scope.trigger"),
            ("scope.run_state",),
        ),
        (
            ":ACQuire:TYPE NORMal",
            ("scope.run_state", "scope.trigger", "scope.acquisition"),
            ("scope.run_state", "scope.trigger"),
        ),
    ],
)
def test_restore_returns_partial_failure_evidence_for_each_write_position(
    failed_command: str,
    attempted: tuple[str, ...],
    restored: tuple[str, ...],
) -> None:
    transport = AcquisitionControlTransport()
    transport.fail_writes.add(failed_command)

    result = MSO8104Scope(transport=transport).restore_acquisition_control(_baseline())

    assert result.status == "failed"
    assert result.attempted_fields == attempted
    assert result.restored_fields == restored
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


def test_current_core_service_accepts_terminal_stop_proof() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP", "STOP"])
    service, driver, transport = _extension_service(backend)

    result = service.acquire_single()

    assert result.value.proof == "single_mode_readback_then_stopped"
    assert result.value.post_arm_trigger_mode == "single"
    assert result.value.observed_states == (result.value.state,)
    assert backend.events[-3:] == [
        ("write", ":SINGle"),
        ("query", ":TRIGger:SWEep?"),
        ("query", ":TRIGger:STATus?"),
    ]
    assert driver.acquisition_writes_blocked is False
    assert transport.session_state.health.value == "healthy"


def test_current_core_service_starts_then_stops_normal_acquisition() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP", "WAIT"])
    service, driver, transport = _extension_service(backend)

    started = service.start_acquisition(
        ScopeContinuousAcquisitionRequest(trigger_mode="normal")
    )
    stopped = service.stop_acquisition()

    assert started.value == ScopeAcquisitionRunState("waiting", "normal", "WAIT")
    assert stopped.value == ScopeAcquisitionRunState("stopped", "unknown", "STOP")
    assert backend.writes == [":TRIGger:SWEep NORMal", ":RUN", ":STOP"]
    assert driver.acquisition_writes_blocked is False
    assert transport.session_state.health.value == "healthy"


def test_current_core_service_restores_after_unproven_start() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP", "STOP"])
    service, driver, transport = _extension_service(backend)

    with pytest.raises(InstrumentError, match="outcome is uncertain"):
        service.start_acquisition(ScopeContinuousAcquisitionRequest(trigger_mode="normal"))

    assert backend.writes == [
        ":TRIGger:SWEep NORMal",
        ":RUN",
        ":STOP",
        ":TRIGger:SWEep NORMal",
        ":ACQuire:TYPE NORMal",
    ]
    assert driver.acquisition_writes_blocked is True
    assert transport.session_state.health.value == "healthy"


def test_current_core_service_restores_after_single_mode_readback_mismatch() -> None:
    backend = AcquisitionControlTransport(
        statuses=["STOP"],
        single_write_trigger_sweep="NORM",
    )
    service, driver, transport = _extension_service(backend)

    with pytest.raises(DataError, match="did not confirm SINGLE"):
        service.acquire_single()

    assert backend.writes == [
        ":SINGle",
        ":STOP",
        ":TRIGger:SWEep NORMal",
        ":ACQuire:TYPE NORMal",
    ]
    assert driver.acquisition_writes_blocked is True
    assert transport.session_state.health.value == "healthy"


def test_current_core_service_does_not_restore_after_poisoned_initial_status_failure() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP"])
    backend.fail_query_on_calls[":TRIGger:STATus?"] = {2}
    service, driver, transport = _extension_service(backend)

    with pytest.raises(InstrumentError, match="outcome is uncertain"):
        service.acquire_single()

    assert backend.writes == [":SINGle"]
    assert driver.acquisition_writes_blocked is True
    assert transport.session_state.health.value == "poisoned"


def test_current_core_service_accepts_td_state_transition() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP", "TD", "STOP"])
    service, driver, transport = _extension_service(backend)

    result = service.acquire_single()

    assert result.value.proof == "state_transition"
    assert result.value.observed_states == (
        ScopeAcquisitionRunState("arming", "single", "TD"),
        ScopeAcquisitionRunState("stopped", "single", "STOP"),
    )
    assert backend.writes == [":SINGle"]
    assert driver.acquisition_writes_blocked is False
    assert transport.session_state.health.value == "healthy"


def test_current_core_service_restores_after_unproven_initial_status() -> None:
    backend = AcquisitionControlTransport(statuses=["STOP", "RUN"])
    service, driver, transport = _extension_service(backend)

    with pytest.raises(DataError, match="unexpected trigger status"):
        service.acquire_single()

    assert backend.writes == [
        ":SINGle",
        ":STOP",
        ":TRIGger:SWEep NORMal",
        ":ACQuire:TYPE NORMal",
    ]
    assert driver.acquisition_writes_blocked is True
    assert transport.session_state.health.value == "healthy"
