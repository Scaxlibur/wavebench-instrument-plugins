from __future__ import annotations

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments import DriverContext
from wavebench.logging import CommandLogger
from wavebench_rigol_mso8000 import descriptor as plugin_descriptor
from wavebench_rigol_mso8000.driver import MSO8104Scope
from wavebench_rigol_mso8000.parsers import RigolIdentity, parse_mso8104_identity


class FakeTransport:
    def __init__(self, responses: dict[str, str] | None = None):
        self.responses = responses or {}
        self.queries: list[str] = []
        self.close_calls = 0

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses[command]

    def close(self) -> None:
        self.close_calls += 1


def test_descriptor_is_executable_v2_metadata_without_io() -> None:
    descriptor = plugin_descriptor()

    assert descriptor.driver_id == "rigol.mso8104"
    assert descriptor.api_version == "wavebench.instrument.v2"
    assert descriptor.models == ("MSO8104",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == ("scope.idn",)
    assert descriptor.backends == ("pyvisa",)
    assert descriptor.resource_schemes == ("tcpip", "usb", "gpib")
    assert descriptor.scope_coupling_policy == "switchable-termination"
    assert descriptor.wavebench_min_version == "0.8.22"
    assert descriptor.wavebench_max_version == "0.9.0"
    assert descriptor.validate_options({}) == {}


def test_factory_opens_exactly_one_core_transport_without_instrument_io() -> None:
    descriptor = plugin_descriptor()
    transport = FakeTransport()
    open_calls = 0

    def open_transport() -> FakeTransport:
        nonlocal open_calls
        open_calls += 1
        return transport

    context = DriverContext(
        driver_id=descriptor.driver_id,
        kind="scope",
        resource="TCPIP0::192.0.2.10::INSTR",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
    )

    driver = descriptor.factory(context)

    assert open_calls == 1
    assert driver.transport is transport
    assert transport.queries == []


def test_idn_validates_target_and_preserves_trimmed_response() -> None:
    response = "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000,00.01.02.03\n"
    transport = FakeTransport({"*IDN?": response})
    scope = MSO8104Scope(transport=transport)

    assert scope.idn() == response.strip()
    assert transport.queries == ["*IDN?"]


def test_identity_parser_splits_only_the_first_three_commas() -> None:
    identity = parse_mso8104_identity(
        "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000,00.01,build"
    )

    assert identity == RigolIdentity(
        manufacturer="RIGOL TECHNOLOGIES",
        model="MSO8104",
        serial_number="MSO8A000000000",
        firmware="00.01,build",
    )


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "invalid"),
        ("RIGOL TECHNOLOGIES,MSO8104,SERIAL", "invalid"),
        ("RIGOL TECHNOLOGIES,MSO8104,,00.01", "invalid"),
        ("OTHER,MSO8104,SERIAL,00.01", "manufacturer"),
        ("RIGOL TECHNOLOGIES,MSO8204,SERIAL,00.01", "model"),
    ],
)
def test_identity_parser_rejects_malformed_or_wrong_instruments(
    response: str,
    message: str,
) -> None:
    with pytest.raises(DataError, match=message):
        parse_mso8104_identity(response)


def test_close_is_idempotent_and_blocks_later_queries() -> None:
    transport = FakeTransport(
        {"*IDN?": "RIGOL TECHNOLOGIES,MSO8104,SERIAL,00.01"}
    )
    scope = MSO8104Scope(transport=transport)

    scope.close()
    scope.close()

    assert transport.close_calls == 1
    with pytest.raises(InstrumentError, match="closed"):
        scope.idn()
    assert transport.queries == []
