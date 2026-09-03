"""Production RTM2000 scope-focus contract and recovery tests."""

from __future__ import annotations

from dataclasses import replace

import pytest

from wavebench.errors import DataError, TransportIOError
from wavebench.instruments import (
    ScopeFocusBaseline,
    ScopeFocusChannelState,
    ScopeFocusRequest,
    ScopeFocusRestoreResult,
    ScopeFocusState,
    ScopeFocusVerticalScale,
)
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.services.scope_extension_service import ScopeExtensionService
from wavebench.transport import (
    CommandTransmission,
    ReplayPolicy,
    ResponseProgress,
    Synchronization,
    TransportPhase,
)
from wavebench.transport.guarded import GuardedAuditedTransport
from wavebench_rohde_schwarz_rtm2000 import descriptor as plugin_descriptor
from wavebench_rohde_schwarz_rtm2000.driver import RTM2032Scope
from wavebench_rohde_schwarz_rtm2000.profiles import RTM2000_FOCUS_PROFILE_V2


_CAPABILITY = "scope.focus_configure_v2"
_RESTORE_ORDER = (
    "scope.timebase",
    "scope.channel_vertical",
    "scope.channel_display",
)
_PROFILE = RTM2000_FOCUS_PROFILE_V2


class FocusTransport:
    resource = "test"

    def __init__(
        self,
        *,
        time_range_s: float = 0.01,
        time_position_s: float = 0.001,
        channel_1: tuple[bool, float, float, float, float] = (
            True,
            8.0,
            1.0,
            0.25,
            0.1,
        ),
        channel_2: tuple[bool, float, float, float, float] = (
            False,
            4.0,
            0.5,
            -0.5,
            -0.2,
        ),
        ignore_scale_write: bool = False,
        scale_changes_position: bool = False,
        ignore_position_restore: bool = False,
        fail_main_write_at: int | None = None,
        response_overrides: dict[str, str] | None = None,
    ) -> None:
        self.time_range_s = time_range_s
        self.time_position_s = time_position_s
        self.channels = {
            1: self._channel_dict(channel_1),
            2: self._channel_dict(channel_2),
        }
        self.initial_time_range_s = time_range_s
        self.initial_time_position_s = time_position_s
        self.initial_channels = {channel: dict(state) for channel, state in self.channels.items()}
        self.ignore_scale_write = ignore_scale_write
        self.scale_changes_position = scale_changes_position
        self.ignore_position_restore = ignore_position_restore
        self.fail_main_write_at = fail_main_write_at
        self.write_calls = 0
        self.failure_triggered = False
        self.response_overrides = dict(response_overrides or {})
        self.events: list[tuple[str, str]] = []
        self.close_calls = 0

    @staticmethod
    def _channel_dict(
        values: tuple[bool, float, float, float, float],
    ) -> dict[str, bool | float]:
        enabled, range_v, scale, position, offset = values
        return {
            "enabled": enabled,
            "range": range_v,
            "scale": scale,
            "position": position,
            "offset": offset,
        }

    def record_event(self, direction: str, text: str) -> None:
        del direction, text

    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        assert replay is ReplayPolicy.NO_REPLAY
        self.events.append(("query", command))
        if command in self.response_overrides:
            return self.response_overrides[command]
        if command == "*IDN?":
            return "Rohde&Schwarz,RTM2032,redacted,06.010"
        if command == "TIMebase:RANGE?":
            return f"{self.time_range_s:.12g}"
        if command == "TIMebase:POSition?":
            return f"{self.time_position_s:.12g}"
        for channel, state in self.channels.items():
            prefix = f"CHANnel{channel}"
            responses = {
                f"{prefix}:STATE?": "1" if state["enabled"] else "0",
                f"{prefix}:RANGE?": f"{state['range']:.12g}",
                f"{prefix}:SCALe?": f"{state['scale']:.12g}",
                f"{prefix}:POSITION?": f"{state['position']:.12g}",
                f"{prefix}:OFFSET?": f"{state['offset']:.12g}",
            }
            if command in responses:
                return responses[command]
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command: str) -> None:
        self.events.append(("write", command))
        self.write_calls += 1
        prefix, raw = command.rsplit(" ", 1)
        if prefix == "TIMebase:RANGe":
            self.time_range_s = float(raw)
            self._fail_after_completed_main_write()
            return
        if prefix == "TIMebase:POSition":
            if not self.ignore_position_restore:
                self.time_position_s = float(raw)
            self._fail_after_completed_main_write()
            return
        for channel, state in self.channels.items():
            channel_prefix = f"CHANnel{channel}"
            if prefix == f"{channel_prefix}:RANGe":
                state["range"] = float(raw)
                self._fail_after_completed_main_write()
                return
            if prefix == f"{channel_prefix}:SCALe":
                if not self.ignore_scale_write:
                    state["scale"] = float(raw)
                    state["range"] = float(raw) * 8
                    if self.scale_changes_position:
                        state["position"] = 0.0
                self._fail_after_completed_main_write()
                return
            if prefix == f"{channel_prefix}:POSition":
                if not self.ignore_position_restore:
                    state["position"] = float(raw)
                self._fail_after_completed_main_write()
                return
            if prefix == f"{channel_prefix}:OFFSet":
                state["offset"] = float(raw)
                self._fail_after_completed_main_write()
                return
            if prefix == f"{channel_prefix}:STATE":
                state["enabled"] = raw == "ON"
                self._fail_after_completed_main_write()
                return
        raise AssertionError(f"unexpected write: {command}")

    def _fail_after_completed_main_write(self) -> None:
        if self.failure_triggered or self.fail_main_write_at != self.write_calls:
            return
        self.failure_triggered = True
        raise TransportIOError(
            "simulated synchronized write completion failure",
            operation="write",
            phase=TransportPhase.SENDING,
            replay_policy=ReplayPolicy.NO_REPLAY,
            command_transmission=CommandTransmission.SENT,
            response_progress=ResponseProgress.NONE,
            synchronization=Synchronization.PROVEN,
            attempts=1,
            reason_code="simulated_focus_write_failure",
        )

    def close(self) -> None:
        self.close_calls += 1

    def matches_initial(self) -> bool:
        return (
            self.time_range_s == self.initial_time_range_s
            and self.time_position_s == self.initial_time_position_s
            and self.channels == self.initial_channels
        )


def _state(backend: FocusTransport) -> ScopeFocusState:
    return ScopeFocusState(
        time_range_s=backend.time_range_s,
        time_position_s=backend.time_position_s,
        channels=tuple(
            ScopeFocusChannelState(
                channel=channel,
                enabled=bool(state["enabled"]),
                range_v=float(state["range"]),
                scale_v_per_div=float(state["scale"]),
                position=float(state["position"]),
                offset_v=float(state["offset"]),
            )
            for channel, state in backend.channels.items()
        ),
    )


def _baseline(backend: FocusTransport) -> ScopeFocusBaseline:
    return ScopeFocusBaseline(
        context_id="context",
        session_epoch="epoch",
        baseline_nonce="nonce",
        snapshot=_state(backend),
        restore_order=_RESTORE_ORDER,
    )


def _service(
    backend: FocusTransport,
) -> tuple[ScopeExtensionService, GuardedAuditedTransport]:
    transport = GuardedAuditedTransport(backend)
    driver = RTM2032Scope(transport=transport)
    descriptor = plugin_descriptor()
    validate_declared_capabilities(descriptor, driver)
    return (
        ScopeExtensionService(
            driver=driver,
            descriptor=descriptor,
            session_state=transport.session_state,
            connection_timeout_ms=1_000,
        ),
        transport,
    )


def test_production_descriptor_exposes_focus_profile_without_io() -> None:
    descriptor = plugin_descriptor()
    assert _CAPABILITY in descriptor.capabilities
    assert descriptor.wavebench_min_version == "0.8.26"
    assert descriptor.scope_extensions is not None
    assert descriptor.scope_extensions.focus_profile_v2 is _PROFILE

    backend = FocusTransport()
    transport = GuardedAuditedTransport(backend)
    driver = RTM2032Scope(transport=transport)
    validate_declared_capabilities(descriptor, driver)
    assert backend.events == []


def test_driver_focus_queries_configures_and_restores_full_view() -> None:
    backend = FocusTransport()
    driver = RTM2032Scope(transport=backend)
    baseline = _baseline(backend)
    request = ScopeFocusRequest(
        channels=(2,),
        time_range_s=0.02,
        vertical_scales=(ScopeFocusVerticalScale(2, 0.25),),
        hide_others=True,
    )

    assert driver.get_focus_state_v2() == baseline.snapshot
    driver.configure_focus_v2(request, baseline=baseline)
    result = driver.restore_focus_v2(baseline)

    assert result == ScopeFocusRestoreResult(
        status="completed",
        attempted_fields=_RESTORE_ORDER,
        restored_fields=_RESTORE_ORDER,
    )
    result.validate_for(baseline)
    assert [event for event in backend.events if event[0] == "query"] == [
        ("query", "TIMebase:RANGE?"),
        ("query", "TIMebase:POSition?"),
        ("query", "CHANnel1:STATE?"),
        ("query", "CHANnel1:RANGE?"),
        ("query", "CHANnel1:SCALe?"),
        ("query", "CHANnel1:POSITION?"),
        ("query", "CHANnel1:OFFSET?"),
        ("query", "CHANnel2:STATE?"),
        ("query", "CHANnel2:RANGE?"),
        ("query", "CHANnel2:SCALe?"),
        ("query", "CHANnel2:POSITION?"),
        ("query", "CHANnel2:OFFSET?"),
    ]
    assert [event for event in backend.events if event[0] == "write"] == [
        ("write", "TIMebase:RANGe 0.02"),
        ("write", "CHANnel2:SCALe 0.25"),
        ("write", "CHANnel1:STATE OFF"),
        ("write", "CHANnel2:STATE ON"),
        ("write", "TIMebase:RANGe 0.01"),
        ("write", "TIMebase:POSition 0.001"),
        ("write", "CHANnel1:RANGe 8"),
        ("write", "CHANnel1:SCALe 1"),
        ("write", "CHANnel1:POSition 0.25"),
        ("write", "CHANnel1:OFFSet 0.1"),
        ("write", "CHANnel2:RANGe 4"),
        ("write", "CHANnel2:SCALe 0.5"),
        ("write", "CHANnel2:POSition -0.5"),
        ("write", "CHANnel2:OFFSet -0.2"),
        ("write", "CHANnel1:STATE ON"),
        ("write", "CHANnel2:STATE OFF"),
    ]
    assert backend.matches_initial()


def test_driver_focus_rejects_invalid_inputs_before_io() -> None:
    backend = FocusTransport()
    driver = RTM2032Scope(transport=backend)
    baseline = _baseline(backend)

    with pytest.raises(ValueError, match="CH1 and/or CH2"):
        driver.configure_focus_v2(ScopeFocusRequest(channels=(3,)), baseline=baseline)
    with pytest.raises(ValueError, match="restore_order"):
        driver.restore_focus_v2(replace(baseline, restore_order=("scope.channel_display",)))
    assert backend.events == []


def test_driver_focus_rejects_malformed_off_channel_state_before_write() -> None:
    backend = FocusTransport(
        response_overrides={"CHANnel2:SCALe?": "UNAVAILABLE"},
    )

    with pytest.raises(DataError, match="CHANnel2:SCALe"):
        RTM2032Scope(transport=backend).get_focus_state_v2()
    assert not [event for event in backend.events if event[0] == "write"]


def test_core_service_focus_verifies_change_and_noop() -> None:
    backend = FocusTransport()
    service, transport = _service(backend)
    request = ScopeFocusRequest(
        channels=(2,),
        time_range_s=0.02,
        vertical_scales=(ScopeFocusVerticalScale(2, 0.25),),
        hide_others=True,
    )

    result = service.configure_focus_v2(request)

    assert result.value.write_performed is True
    assert result.value.after.time_range_s == 0.02
    assert {item.channel for item in result.value.after.channels if item.enabled} == {2}
    audit = transport.audit_snapshot()
    assert audit["counters"]["write_requests"] == 4
    assert audit["counters"]["write_completed"] == 4
    assert transport.session_state.health.value == "healthy"

    backend = FocusTransport(
        time_range_s=0.02,
        channel_1=(False, 8.0, 1.0, 0.25, 0.1),
        channel_2=(True, 2.0, 0.25, -0.5, -0.2),
    )
    service, transport = _service(backend)
    result = service.configure_focus_v2(request)
    assert result.value.write_performed is False
    assert transport.audit_snapshot()["counters"]["write_requests"] == 0


def test_core_service_focus_restores_after_postcondition_mismatch() -> None:
    backend = FocusTransport(ignore_scale_write=True)
    service, transport = _service(backend)

    with pytest.raises(DataError, match="postcondition does not match") as raised:
        service.configure_focus_v2(
            ScopeFocusRequest(
                channels=(2,),
                time_range_s=0.02,
                vertical_scales=(ScopeFocusVerticalScale(2, 0.25),),
                hide_others=True,
            )
        )

    assert backend.matches_initial()
    assert raised.value.scope_operation_diagnostics["cleanup_error"] is None
    assert (
        raised.value.scope_operation_diagnostics["cleanup"]["verification"]["status"]
        == "verified"
    )
    assert transport.session_state.health.value == "healthy"


@pytest.mark.parametrize("fail_main_write_at", (1, 2, 3, 4))
def test_core_service_focus_restores_every_partial_main_failure(
    fail_main_write_at: int,
) -> None:
    backend = FocusTransport(fail_main_write_at=fail_main_write_at)
    service, transport = _service(backend)

    with pytest.raises(TransportIOError, match="synchronized write completion failure"):
        service.configure_focus_v2(
            ScopeFocusRequest(
                channels=(2,),
                time_range_s=0.02,
                vertical_scales=(ScopeFocusVerticalScale(2, 0.25),),
                hide_others=True,
            )
        )

    assert backend.failure_triggered
    assert backend.matches_initial()
    assert transport.session_state.health.value == "healthy"
    audit = transport.audit_snapshot()
    assert audit["counters"]["write_outcome_unknown"] == 1
    assert audit["counters"]["write_completed"] == 12 + fail_main_write_at - 1


def test_core_service_focus_poisons_when_protected_position_cannot_restore() -> None:
    backend = FocusTransport(
        scale_changes_position=True,
        ignore_position_restore=True,
    )
    service, transport = _service(backend)

    with pytest.raises(DataError, match="postcondition does not match") as raised:
        service.configure_focus_v2(
            ScopeFocusRequest(
                channels=(1,),
                vertical_scales=(ScopeFocusVerticalScale(1, 0.5),),
            )
        )

    assert raised.value.scope_operation_diagnostics["cleanup_error"] == "ValueError"
    assert (
        raised.value.scope_operation_diagnostics["cleanup"]["verification"]["status"]
        == "mismatch"
    )
    assert transport.session_state.health.value == "poisoned"
