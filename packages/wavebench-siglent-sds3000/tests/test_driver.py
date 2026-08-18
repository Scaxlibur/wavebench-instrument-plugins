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
    def __init__(self, response: str = "LECROY,SDS3054,redacted,8.4.1") -> None:
        self.response = response
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.close_count = 0

    def write(self, command: str) -> None:
        self.writes.append(command)

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.response

    def close(self) -> None:
        self.close_count += 1


def test_descriptor_is_executable_v2_metadata_without_io() -> None:
    descriptor = plugin_descriptor()

    assert descriptor.driver_id == "siglent.sds3000"
    assert descriptor.api_version == "wavebench.instrument.v2"
    assert descriptor.kind == "scope"
    assert descriptor.models == ("SDS3054",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == ("scope.idn",)
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
