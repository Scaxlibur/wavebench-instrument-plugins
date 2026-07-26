from __future__ import annotations

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_rigol_dm3000 import descriptor
from wavebench_rigol_dm3000.driver import (
    DMM_FUNCTION_COMMANDS,
    DMM_FUNCTION_RANGE_QUERIES,
    DMM_FUNCTION_SET_COMMANDS,
    DM3000Dmm,
)


class FakeTransport:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.function = "DCV"
        self.readings = {command: "1.250000E+00" for command in DMM_FUNCTION_COMMANDS.values()}
        self.readings.update({query: "0" for query in DMM_FUNCTION_RANGE_QUERIES.values()})
        self.readings[":MEASure:VOLTage:DC:IMPedance?"] = "10M"
        self.closed = False

    def write(self, command: str) -> None:
        self.writes.append(command)
        reverse = {value: key for key, value in DMM_FUNCTION_SET_COMMANDS.items()}
        if command in reverse:
            self.function = reverse[command].upper()
        if command.startswith(":MEASure:VOLTage:DC "):
            self.readings[":MEASure:VOLTage:DC:RANGe?"] = command.rsplit(" ", 1)[1]
        if command.startswith(":MEASure:VOLTage:AC "):
            self.readings[":MEASure:VOLTage:AC:RANGe?"] = command.rsplit(" ", 1)[1]
        if command.startswith(":MEASure:VOLTage:DC:IMPedance "):
            self.readings[":MEASure:VOLTage:DC:IMPedance?"] = command.rsplit(" ", 1)[1]

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
        "dmm.measurement_profile",
        "dmm.set_voltage_range",
        "dmm.set_dcv_impedance",
    )
    assert item.wavebench_min_version == "0.8.9"
    assert item.version == "0.3.0"
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


def test_measurement_profile_is_query_only_and_typed() -> None:
    transport = FakeTransport()

    profile = DM3000Dmm(transport).measurement_profile()

    assert profile.function == "dcv"
    assert profile.range_code == 0
    assert profile.auto_range is None
    assert profile.impedance == "10M"
    assert transport.writes == []
    assert transport.queries == [
        ":FUNCtion?",
        ":MEASure:VOLTage:DC:RANGe?",
        ":MEASure:VOLTage:DC:IMPedance?",
    ]


def test_measurement_profile_omits_unaccepted_range_query() -> None:
    transport = FakeTransport()
    transport.function = "CONT"

    profile = DM3000Dmm(transport).measurement_profile()

    assert profile.function == "continuity"
    assert profile.range_code is None
    assert profile.auto_range is None
    assert profile.impedance is None
    assert transport.writes == []
    assert transport.queries == [":FUNCtion?"]


def test_set_voltage_range_is_function_gated_and_read_back() -> None:
    transport = FakeTransport()
    transport.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"

    result = DM3000Dmm(transport).set_voltage_range("dcv", 1)

    assert result.function == "dcv"
    assert result.previous_range_code == 2
    assert result.range_code == 1
    assert result.changed is True
    assert transport.writes == [":MEASure:VOLTage:DC 1"]
    assert transport.queries == [
        ":FUNCtion?",
        ":MEASure:VOLTage:DC:RANGe?",
        ":MEASure:VOLTage:DC:RANGe?",
    ]


def test_set_voltage_range_noop_does_not_write() -> None:
    transport = FakeTransport()
    transport.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"

    result = DM3000Dmm(transport).set_voltage_range("dcv", 2)

    assert result.changed is False
    assert transport.writes == []


def test_set_voltage_range_rejects_wrong_active_function_before_write() -> None:
    transport = FakeTransport()
    transport.function = "ACV"

    with pytest.raises(InstrumentError, match="requires active function dcv"):
        DM3000Dmm(transport).set_voltage_range("dcv", 1)

    assert transport.writes == []
    assert transport.queries == [":FUNCtion?"]


def test_set_voltage_range_rejects_high_dcv_range_with_10g_before_write() -> None:
    transport = FakeTransport()
    transport.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"
    transport.readings[":MEASure:VOLTage:DC:IMPedance?"] = "10G"

    with pytest.raises(InstrumentError, match="require 10M impedance"):
        DM3000Dmm(transport).set_voltage_range("dcv", 3)

    assert transport.writes == []
    assert transport.queries == [
        ":FUNCtion?",
        ":MEASure:VOLTage:DC:RANGe?",
        ":MEASure:VOLTage:DC:IMPedance?",
    ]


def test_set_voltage_range_restores_and_latches_on_readback_failure() -> None:
    class IgnoredFirstRangeWrite(FakeTransport):
        def __init__(self) -> None:
            super().__init__()
            self.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"
            self._range_writes = 0

        def write(self, command: str) -> None:
            if command.startswith(":MEASure:VOLTage:DC "):
                self.writes.append(command)
                self._range_writes += 1
                if self._range_writes == 1:
                    return
                self.readings[":MEASure:VOLTage:DC:RANGe?"] = command.rsplit(" ", 1)[1]
                return
            super().write(command)

    transport = IgnoredFirstRangeWrite()
    driver = DM3000Dmm(transport)

    with pytest.raises(InstrumentError, match="original range was restored"):
        driver.set_voltage_range("dcv", 1)

    assert driver.configuration_writes_blocked is True
    writes_before = list(transport.writes)
    queries_before = list(transport.queries)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_voltage_range("dcv", 1)
    assert transport.writes == writes_before
    assert transport.queries == queries_before


def test_ambiguous_range_write_restores_then_latches_all_configuration_writes() -> None:
    class AmbiguousFirstRangeWrite(FakeTransport):
        def __init__(self) -> None:
            super().__init__()
            self.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"
            self._range_writes = 0

        def write(self, command: str) -> None:
            if command.startswith(":MEASure:VOLTage:DC "):
                self.writes.append(command)
                self._range_writes += 1
                if self._range_writes == 1:
                    raise OSError("simulated timeout")
                self.readings[":MEASure:VOLTage:DC:RANGe?"] = command.rsplit(" ", 1)[1]
                return
            super().write(command)

    transport = AmbiguousFirstRangeWrite()
    driver = DM3000Dmm(transport)

    with pytest.raises(InstrumentError, match="write outcome is ambiguous"):
        driver.set_voltage_range("dcv", 1)

    assert driver.configuration_writes_blocked is True
    writes_before = list(transport.writes)
    queries_before = list(transport.queries)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_function("acv")
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_dcv_impedance("10G")
    assert transport.writes == writes_before
    assert transport.queries == queries_before


def test_range_restore_failure_latches_writes() -> None:
    class FailedRangeRestore(FakeTransport):
        def __init__(self) -> None:
            super().__init__()
            self.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"
            self._range_writes = 0

        def write(self, command: str) -> None:
            if command.startswith(":MEASure:VOLTage:DC "):
                self.writes.append(command)
                self._range_writes += 1
                if self._range_writes == 1:
                    return
                raise OSError("simulated restore timeout")
            super().write(command)

    driver = DM3000Dmm(FailedRangeRestore())

    with pytest.raises(InstrumentError, match="restoration is ambiguous"):
        driver.set_voltage_range("dcv", 1)

    assert driver.configuration_writes_blocked is True


def test_set_dcv_impedance_is_gated_by_function_and_range() -> None:
    transport = FakeTransport()
    transport.readings[":MEASure:VOLTage:DC:RANGe?"] = "3"

    with pytest.raises(InstrumentError, match="requires range code 0, 1, or 2"):
        DM3000Dmm(transport).set_dcv_impedance("10G")

    assert transport.writes == []
    assert transport.queries == [":FUNCtion?", ":MEASure:VOLTage:DC:RANGe?"]


def test_set_dcv_impedance_writes_and_reads_back() -> None:
    transport = FakeTransport()
    transport.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"

    result = DM3000Dmm(transport).set_dcv_impedance("10g")

    assert result.previous_impedance == "10M"
    assert result.impedance == "10G"
    assert result.range_code == 2
    assert result.changed is True
    assert transport.writes == [":MEASure:VOLTage:DC:IMPedance 10G"]


def test_ambiguous_impedance_write_restores_then_latches() -> None:
    class AmbiguousFirstImpedanceWrite(FakeTransport):
        def __init__(self) -> None:
            super().__init__()
            self.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"
            self._impedance_writes = 0

        def write(self, command: str) -> None:
            if command.startswith(":MEASure:VOLTage:DC:IMPedance "):
                self.writes.append(command)
                self._impedance_writes += 1
                if self._impedance_writes == 1:
                    raise OSError("simulated timeout")
                self.readings[":MEASure:VOLTage:DC:IMPedance?"] = command.rsplit(" ", 1)[1]
                return
            super().write(command)

    transport = AmbiguousFirstImpedanceWrite()
    driver = DM3000Dmm(transport)

    with pytest.raises(InstrumentError, match="write outcome is ambiguous"):
        driver.set_dcv_impedance("10G")

    assert transport.readings[":MEASure:VOLTage:DC:IMPedance?"] == "10M"
    assert driver.configuration_writes_blocked is True


def test_impedance_restore_failure_latches_writes() -> None:
    class FailedImpedanceRestore(FakeTransport):
        def __init__(self) -> None:
            super().__init__()
            self.readings[":MEASure:VOLTage:DC:RANGe?"] = "2"
            self._impedance_writes = 0

        def write(self, command: str) -> None:
            if command.startswith(":MEASure:VOLTage:DC:IMPedance "):
                self.writes.append(command)
                self._impedance_writes += 1
                if self._impedance_writes == 1:
                    return
                raise OSError("simulated restore timeout")
            super().write(command)

    driver = DM3000Dmm(FailedImpedanceRestore())

    with pytest.raises(InstrumentError, match="restoration is ambiguous"):
        driver.set_dcv_impedance("10G")

    assert driver.configuration_writes_blocked is True


@pytest.mark.parametrize("raw", ["bad", "-1"])
def test_measurement_profile_rejects_invalid_range_code(raw: str) -> None:
    transport = FakeTransport()
    transport.readings[":MEASure:VOLTage:DC:RANGe?"] = raw

    with pytest.raises(DataError, match="unexpected DM3000 range code"):
        DM3000Dmm(transport).measurement_profile()

    assert transport.writes == []


@pytest.mark.parametrize(
    ("requested", "command", "reported"),
    [
        ("dcv", ":FUNCtion:VOLTage:DC", "DCV"),
        ("acv", ":FUNCtion:VOLTage:AC", "ACV"),
        ("dci", ":FUNCtion:CURRent:DC", "DCI"),
        ("aci", ":FUNCtion:CURRent:AC", "ACI"),
        ("res", ":FUNCtion:RESistance", "RES"),
        ("fres", ":FUNCtion:FRESistance", "FRES"),
        ("freq", ":FUNCtion:FREQuency", "FREQ"),
        ("period", ":FUNCtion:PERiod", "PERI"),
        ("continuity", ":FUNCtion:CONTinuity", "CONT"),
        ("diode", ":FUNCtion:DIODe", "DIODE"),
        ("cap", ":FUNCtion:CAPacitance", "CAP"),
    ],
)
def test_all_function_selectors_send_exact_scpi_and_read_back(
    requested: str,
    command: str,
    reported: str,
) -> None:
    transport = FakeTransport()
    transport.function = reported

    assert DM3000Dmm(transport).set_function(requested) == requested
    assert transport.writes == [command]
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


@pytest.mark.parametrize("raw", ["nan", "+inf", "-inf", "1e9999"])
def test_read_rejects_nonfinite_values(raw: str) -> None:
    transport = FakeTransport()
    transport.readings[":MEASure:VOLTage:DC?"] = raw

    with pytest.raises(DataError, match="non-finite DM3000 reading"):
        DM3000Dmm(transport).read("dcv")
