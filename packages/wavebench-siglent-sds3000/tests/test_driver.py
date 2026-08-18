from __future__ import annotations

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger
from wavebench_siglent_sds3000 import descriptor as plugin_descriptor
from wavebench_siglent_sds3000.driver import (
    SDS3000Scope,
    SDS3000Identity,
    parse_sds3000_identity,
)


class FakeTransport:
    def __init__(
        self,
        response: str = "LECROY,SDS3054,redacted,8.4.1",
        *,
        responses: dict[str, str] | None = None,
    ) -> None:
        self.response = response
        self.responses = responses or {}
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.close_count = 0

    def write(self, command: str) -> None:
        self.writes.append(command)

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses.get(command, self.response)

    def close(self) -> None:
        self.close_count += 1


def test_descriptor_is_executable_v2_metadata_without_io() -> None:
    descriptor = plugin_descriptor()

    assert descriptor.driver_id == "siglent.sds3000"
    assert descriptor.api_version == "wavebench.instrument.v2"
    assert descriptor.kind == "scope"
    assert descriptor.models == ("SDS3054",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == (
        "scope.idn",
        "scope.errors",
        "scope.channel_coupling",
    )
    assert descriptor.idn_patterns == ("LECROY,SDS3054,",)
    assert descriptor.backends == ("pyvisa",)
    assert descriptor.resource_schemes == ("tcpip",)
    assert descriptor.scope_coupling_policy == "switchable-termination"
    assert descriptor.validate_options({}) == {}


def test_factory_opens_only_the_context_transport_and_performs_no_io() -> None:
    transport = FakeTransport()
    descriptor = plugin_descriptor()
    context = DriverContext(
        driver_id=descriptor.driver_id,
        kind="scope",
        resource="configured-resource",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=lambda: transport,
        settings={},
        options=descriptor.validate_options({}),
    )

    driver = descriptor.factory(context)

    assert driver.transport is transport
    assert transport.queries == []
    assert transport.writes == []
    validate_declared_capabilities(descriptor, driver)


def test_identity_parser_accepts_only_the_verified_device_baseline() -> None:
    assert parse_sds3000_identity(" LECROY,SDS3054,redacted,8.4.1\n") == SDS3000Identity(
        remote_manufacturer="LECROY",
        model="SDS3054",
        serial="redacted",
        firmware="8.4.1",
    )


@pytest.mark.parametrize(
    ("response", "error", "message"),
    [
        ("bad", DataError, "invalid"),
        ("SIGLENT,SDS3054,redacted,8.4.1", InstrumentError, "not a supported"),
        ("LECROY,SDS3024,redacted,8.4.1", InstrumentError, "unsupported.*model"),
        ("LECROY,SDS3054,redacted,8.5.0", InstrumentError, "unsupported.*firmware"),
    ],
)
def test_identity_gate_rejects_unsupported_targets_without_writes(
    response: str,
    error: type[Exception],
    message: str,
) -> None:
    transport = FakeTransport(response)
    scope = SDS3000Scope(transport)

    with pytest.raises(error, match=message):
        scope.idn()

    assert transport.queries == ["*IDN?"]
    assert transport.writes == []


def test_idn_queries_once_and_close_is_idempotent() -> None:
    transport = FakeTransport()
    scope = SDS3000Scope(transport)

    assert scope.idn() == "LECROY,SDS3054,redacted,8.4.1"
    assert transport.queries == ["*IDN?"]
    assert transport.writes == []

    scope.close()
    scope.close()
    assert transport.close_count == 1


@pytest.mark.parametrize(
    ("response", "coupling"),
    [
        ("A1M", "ACL"),
        ("C2:CPL D1M", "DCL"),
        ("C2:COUPLING D50", "DC"),
        ("GND", "GND"),
    ],
)
def test_channel_coupling_maps_maui_tokens_to_wavebench_values(
    response: str,
    coupling: str,
) -> None:
    transport = FakeTransport(responses={"C2:CPL?": response})

    assert SDS3000Scope(transport).channel_coupling(2) == coupling
    assert transport.queries == ["*IDN?", "C2:CPL?"]
    assert transport.writes == []


@pytest.mark.parametrize("channel", [False, 0, 5])
def test_channel_coupling_rejects_invalid_channels_before_io(channel: int) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="CH1, CH2, CH3, or CH4"):
        SDS3000Scope(transport).channel_coupling(channel)

    assert transport.queries == []
    assert transport.writes == []


def test_channel_coupling_rejects_overload_and_unknown_responses() -> None:
    overload = FakeTransport(responses={"C1:CPL?": "C1:CPL OVL"})
    with pytest.raises(InstrumentError, match="overload"):
        SDS3000Scope(overload).channel_coupling(1)

    unknown = FakeTransport(responses={"C1:CPL?": "C1:CPL MAGIC"})
    with pytest.raises(DataError, match=r"C1:CPL\?"):
        SDS3000Scope(unknown).channel_coupling(1)


def test_error_registers_are_read_once_and_only_nonzero_values_are_returned() -> None:
    transport = FakeTransport(
        responses={
            "CMR?": "CMR 0",
            "EXR?": "EXR? 21",
            "DDR?": "2",
        }
    )
    scope = SDS3000Scope(transport)

    assert scope.errors() == ["EXR 21", "DDR 2"]
    assert transport.queries == ["*IDN?", "CMR?", "EXR?", "DDR?"]
    assert transport.writes == []


def test_error_register_parser_rejects_bad_values_and_limit_before_writes() -> None:
    bad = FakeTransport(responses={"CMR?": "CMR 14"})
    with pytest.raises(DataError, match="out-of-range CMR"):
        SDS3000Scope(bad).errors()
    assert bad.writes == []

    invalid_limit = FakeTransport()
    with pytest.raises(DataError, match="positive integer"):
        SDS3000Scope(invalid_limit).errors(limit=0)
    assert invalid_limit.queries == []


def test_assert_no_errors_uses_the_stateful_register_snapshot() -> None:
    clear = FakeTransport(responses={"CMR?": "0", "EXR?": "0", "DDR?": "0"})
    SDS3000Scope(clear).assert_no_errors()

    active = FakeTransport(responses={"CMR?": "1", "EXR?": "0", "DDR?": "0"})
    with pytest.raises(InstrumentError, match="CMR 1"):
        SDS3000Scope(active).assert_no_errors()
