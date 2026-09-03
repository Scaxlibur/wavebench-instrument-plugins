from __future__ import annotations

from dataclasses import replace

import pytest

from wavebench.errors import ConfigError, DataError
from wavebench.instruments import (
    ScopeChannelDisplayBaseline,
    ScopeChannelDisplayProfileV2,
    ScopeChannelDisplayRequest,
    ScopeChannelDisplayRestoreResult,
    ScopeChannelDisplayState,
    ScopeDescriptorExtensions,
)
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.services.scope_extension_service import ScopeExtensionService
from wavebench.transport import ReplayPolicy
from wavebench.transport.guarded import GuardedAuditedTransport
from wavebench_siglent_sds3000 import descriptor as plugin_descriptor
from wavebench_siglent_sds3000.driver import SDS3000Scope


_CAPABILITY = "scope.channel_display_configure_v2"
_PROFILE = ScopeChannelDisplayProfileV2(
    analog_channels=(1, 2, 3, 4),
    snapshot_max_steps=1,
    configure_max_steps=2,
    restore_max_steps=1,
    verify_max_steps=1,
)


class DisplayTransport:
    resource = "test"

    def __init__(
        self,
        *,
        enabled: bool = False,
        display_responses: list[str] | None = None,
    ) -> None:
        self.displayed = {channel: enabled for channel in range(1, 5)}
        self.display_responses = list(display_responses or [])
        self.states_after_writes: list[bool] = []
        self.events: list[tuple[str, str]] = []
        self.close_calls = 0

    def record_event(self, direction: str, text: str) -> None:
        del direction, text

    def query(self, command: str, *, replay: ReplayPolicy) -> str:
        del replay
        self.events.append(("query", command))
        if command == "*IDN?":
            return "LECROY,SDS3054,redacted,8.4.1"
        for channel in range(1, 5):
            if command == f"C{channel}:TRA?":
                if self.display_responses:
                    return self.display_responses.pop(0)
                state = "ON" if self.displayed[channel] else "OFF"
                return f"C{channel}:TRA {state}"
        raise AssertionError(f"unexpected query: {command}")

    def write(self, command: str) -> None:
        self.events.append(("write", command))
        for channel in range(1, 5):
            prefix = f"C{channel}:TRA "
            if command.startswith(prefix):
                self.displayed[channel] = command.removeprefix(prefix) == "ON"
                self.states_after_writes.append(self.displayed[channel])
                return
        raise AssertionError(f"unexpected write: {command}")

    def close(self) -> None:
        self.close_calls += 1


def _baseline(channel: int, *, enabled: bool) -> ScopeChannelDisplayBaseline:
    return ScopeChannelDisplayBaseline(
        context_id="context",
        session_epoch="epoch",
        baseline_nonce="nonce",
        snapshot=ScopeChannelDisplayState(channel=channel, enabled=enabled),
        restore_order=("scope.channel_display",),
    )


def _candidate_descriptor():
    production = plugin_descriptor()
    return replace(
        production,
        capabilities=(*production.capabilities, _CAPABILITY),
        scope_extensions=ScopeDescriptorExtensions(
            channel_display_profile_v2=_PROFILE,
        ),
    )


def _service(
    backend: DisplayTransport,
) -> tuple[ScopeExtensionService, GuardedAuditedTransport]:
    transport = GuardedAuditedTransport(backend)
    driver = SDS3000Scope(transport=transport)
    descriptor = _candidate_descriptor()
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


def test_production_descriptor_keeps_channel_display_candidate_disabled() -> None:
    descriptor = plugin_descriptor()
    assert _CAPABILITY not in descriptor.capabilities
    assert descriptor.scope_extensions is None

    backend = DisplayTransport()
    transport = GuardedAuditedTransport(backend)
    driver = SDS3000Scope(transport=transport)
    service = ScopeExtensionService(
        driver=driver,
        descriptor=descriptor,
        session_state=transport.session_state,
        connection_timeout_ms=1_000,
    )

    with pytest.raises(ConfigError, match="missing capabilities"):
        service.configure_channel_display_v2(
            ScopeChannelDisplayRequest(channel=1, enabled=True)
        )
    assert backend.events == []


def test_driver_candidate_queries_configures_and_restores_one_channel() -> None:
    backend = DisplayTransport(enabled=False)
    driver = SDS3000Scope(transport=backend)
    baseline = _baseline(3, enabled=False)

    assert driver.get_channel_display_state_v2(3) == ScopeChannelDisplayState(3, False)
    driver.configure_channel_display_v2(
        ScopeChannelDisplayRequest(channel=3, enabled=True),
        baseline=baseline,
    )
    result = driver.restore_channel_display_v2(baseline)

    assert result == ScopeChannelDisplayRestoreResult(
        status="completed",
        attempted_fields=("scope.channel_display",),
        restored_fields=("scope.channel_display",),
    )
    result.validate_for(baseline)
    assert backend.events == [
        ("query", "*IDN?"),
        ("query", "C3:TRA?"),
        ("write", "C3:TRA ON"),
        ("write", "C3:TRA OFF"),
    ]


def test_driver_candidate_rejects_invalid_inputs_before_io() -> None:
    backend = DisplayTransport()
    driver = SDS3000Scope(transport=backend)

    with pytest.raises(DataError, match="CH1, CH2, CH3, or CH4"):
        driver.get_channel_display_state_v2(5)
    with pytest.raises(ValueError, match="different channel"):
        driver.configure_channel_display_v2(
            ScopeChannelDisplayRequest(channel=2, enabled=True),
            baseline=_baseline(1, enabled=False),
        )
    with pytest.raises(DataError, match="CH1, CH2, CH3, or CH4"):
        driver.restore_channel_display_v2(_baseline(5, enabled=False))
    assert backend.events == []


def test_driver_candidate_rejects_malformed_display_response_without_writes() -> None:
    backend = DisplayTransport(display_responses=["C1:TRA MAYBE"])

    with pytest.raises(DataError, match="invalid C1:TRA\\? response"):
        SDS3000Scope(transport=backend).get_channel_display_state_v2(1)
    assert backend.events == [
        ("query", "*IDN?"),
        ("query", "C1:TRA?"),
    ]


@pytest.mark.parametrize(
    ("initial", "requested", "expected_writes"),
    [(False, True, 1), (True, True, 0)],
)
def test_core_service_candidate_verifies_change_and_noop(
    initial: bool,
    requested: bool,
    expected_writes: int,
) -> None:
    backend = DisplayTransport(enabled=initial)
    service, transport = _service(backend)

    result = service.configure_channel_display_v2(
        ScopeChannelDisplayRequest(channel=2, enabled=requested)
    )

    assert result.value.before == ScopeChannelDisplayState(2, initial)
    assert result.value.after == ScopeChannelDisplayState(2, requested)
    assert result.value.write_performed is bool(expected_writes)
    assert backend.displayed[2] is requested
    audit = transport.audit_snapshot()
    assert audit["counters"]["write_requests"] == expected_writes
    assert audit["counters"]["write_completed"] == expected_writes
    assert transport.session_state.health.value == "healthy"


def test_core_service_candidate_restores_after_postcondition_mismatch() -> None:
    backend = DisplayTransport(
        enabled=False,
        display_responses=["C4:TRA OFF", "C4:TRA OFF", "C4:TRA OFF"],
    )
    service, transport = _service(backend)

    with pytest.raises(DataError, match="postcondition does not match"):
        service.configure_channel_display_v2(
            ScopeChannelDisplayRequest(channel=4, enabled=True)
        )

    assert backend.events == [
        ("query", "*IDN?"),
        ("query", "C4:TRA?"),
        ("write", "C4:TRA ON"),
        ("query", "C4:TRA?"),
        ("write", "C4:TRA OFF"),
        ("query", "C4:TRA?"),
    ]
    assert backend.states_after_writes == [True, False]
    assert backend.displayed[4] is False
    audit = transport.audit_snapshot()
    assert audit["counters"]["write_completed"] == 2
    assert transport.session_state.health.value == "healthy"
