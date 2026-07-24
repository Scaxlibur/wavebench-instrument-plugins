from __future__ import annotations

import pytest

from wavebench.errors import DataError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_rigol_dm3000 import descriptor
from wavebench_rigol_dm3000.driver import (
    DMM_FUNCTION_COMMANDS,
    DMM_FUNCTION_SET_COMMANDS,
    DM3000Dmm,
)


class FakeTransport:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.function = "DCV"
        self.readings = {command: "1.250000E+00" for command in DMM_FUNCTION_COMMANDS.values()}
        self.closed = False

    def write(self, command: str) -> None:
        self.writes.append(command)
        reverse = {value: key for key, value in DMM_FUNCTION_SET_COMMANDS.items()}
        if command in reverse:
            self.function = reverse[command].upper()

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command == "*IDN?":
            return "RIGOL TECHNOLOGIES,DM3058,<serial>,<firmware>"
        if command == ":FUNCtion?":
            return f'"{self.function}"'
        return self.readings[command]

    def close(self) -> None:
        self.closed = True


def test_descriptor_is_canonical_lan_only_and_alias_free() -> None:
    item = descriptor()

    assert item.driver_id == "rigol.dm3000"
    assert item.distribution == "wavebench-rigol-dm3000"
    assert item.aliases == ()
    assert item.kind == "dmm"
    assert item.backends == ("pyvisa",)
    assert item.resource_schemes == ("tcpip",)
    assert item.capabilities == (
        "dmm.idn",
        "dmm.read",
        "dmm.function_status",
        "dmm.set_function",
    )
    assert not any("baud" in field or "termination" in field for field in item.config_fields)


def test_factory_opens_one_core_transport_and_satisfies_capabilities() -> None:
    item = descriptor()
    transport = FakeTransport()
    opened = 0

    def open_transport() -> FakeTransport:
        nonlocal opened
        opened += 1
        return transport

    context = DriverContext(
        driver_id=item.driver_id,
        kind=item.kind,
        resource="TCPIP::192.0.2.40::INSTR",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=1000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, DM3000Dmm)
    assert driver.transport is transport
    assert opened == 1


def test_idn_is_single_query_and_close_delegates() -> None:
    transport = FakeTransport()
    driver = DM3000Dmm(transport)

    result = driver.idn()
    driver.close()

    assert result.startswith("RIGOL TECHNOLOGIES,DM3058")
    assert transport.queries == ["*IDN?"]
    assert transport.closed


@pytest.mark.parametrize(
    ("reported", "expected"),
    [
        ("DCV", "dcv"),
        ("2WR", "res"),
        ("4WR", "fres"),
        ("FREQ", "freq"),
        ("PERI", "period"),
        ("CONT", "continuity"),
        ("CAP", "cap"),
    ],
)
def test_function_status_accepts_dm3058_short_symbols(reported: str, expected: str) -> None:
    transport = FakeTransport()
    transport.function = reported

    assert DM3000Dmm(transport).function_status() == expected


def test_set_function_preserves_write_then_readback_semantics() -> None:
    transport = FakeTransport()

    result = DM3000Dmm(transport).set_function("vac")

    assert result == "acv"
    assert transport.writes == [":FUNCtion:VOLTage:AC"]
    assert transport.queries == [":FUNCtion?"]


@pytest.mark.parametrize(
    ("requested", "command", "function", "unit"),
    [
        ("vdc", ":MEASure:VOLTage:DC?", "dcv", "V"),
        ("vac", ":MEASure:VOLTage:AC?", "acv", "V"),
        ("idc", ":MEASure:CURRent:DC?", "dci", "A"),
        ("iac", ":MEASure:CURRent:AC?", "aci", "A"),
        ("2wr", ":MEASure:RESistance?", "res", "ohm"),
        ("4wr", ":MEASure:FRESistance?", "fres", "ohm"),
        ("freq", ":MEASure:FREQuency?", "freq", "Hz"),
        ("period", ":MEASure:PERiod?", "period", "s"),
        ("cont", ":MEASure:CONTinuity?", "continuity", "ohm"),
        ("diode", ":MEASure:DIODe?", "diode", "V"),
        ("cap", ":MEASure:CAPacitance?", "cap", "F"),
    ],
)
def test_read_uses_existing_scpi_and_public_reading_contract(
    requested: str,
    command: str,
    function: str,
    unit: str,
) -> None:
    transport = FakeTransport()

    reading = DM3000Dmm(transport).read(requested)

    assert transport.queries == [command]
    assert reading.function == function
    assert reading.value == 1.25
    assert reading.unit == unit
    assert reading.raw == "1.250000E+00"


def test_unknown_function_status_raises_without_writing() -> None:
    transport = FakeTransport()
    transport.function = "MYSTERY"

    with pytest.raises(DataError, match="unexpected DMM function status"):
        DM3000Dmm(transport).function_status()

    assert transport.writes == []


def test_unsupported_function_and_invalid_reading_preserve_data_errors() -> None:
    transport = FakeTransport()
    driver = DM3000Dmm(transport)

    with pytest.raises(DataError, match="unsupported DMM function"):
        driver.read("temperature")
    transport.readings[":MEASure:VOLTage:DC?"] = "not-a-number"
    with pytest.raises(DataError, match="unexpected DM3000 reading"):
        driver.read("dcv")

    assert transport.writes == []
