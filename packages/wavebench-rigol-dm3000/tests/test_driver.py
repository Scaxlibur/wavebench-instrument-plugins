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
        self.readings.update(
            {
                ":TRIGger:SOURce?": "AUTO",
                ":TRIGger:AUTO:INTerval?": "400ms",
                ":TRIGger:AUTO:HOLD?": "OFF",
                ":TRIGger:AUTO:HOLD:SENSitivity?": "1",
                ":TRIGger:SINGle?": "1",
                ":TRIGger:EXT?": "RISE",
                ":TRIGger:VMComplete:POLar?": "POS",
                ":TRIGger:VMComplete:PULSewidth?": "7ms",
                ":CALCulate:FUNCtion?": "NONE",
                ":CALCulate:STATistic:COUNt?": "0.00000000E+00",
                ":CALCulate:DB:REFerence?": "0.00000000E+00",
                ":CALCulate:DBM:REFerence?": "6.00000000E+02",
                ":CALCulate:STATistic:AVERage?": "1.25000000E+00",
                ":CALCulate:STATistic:MIN?": "1.00000000E+00",
                ":CALCulate:STATistic:MAX?": "1.50000000E+00",
                ":SYSTem:BEEPer:STATe?": "1",
                ":SYSTem:LANGuage?": "english",
                ":SYSTem:FORMat:DECimal?": "dot",
                ":SYSTem:FORMat:SEParate?": "none",
                ":SYSTem:DISPlay:BRIGht?": "128",
                ":SYSTem:SCANserial?": "None",
                ":SYSTem:LANserial?": "Installed",
                ":UTILity:INTerface:LAN:DHCP?": "ON",
                ":UTILity:INTerface:GPIB:ADDRess?": "22",
                ":UTILity:INTerface:RS232:BAUD?": "9600",
                ":UTILity:INTerface:RS232:PARity?": "none8bits",
            }
        )
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
        "dmm.trigger_status",
        "dmm.calculation_status",
        "dmm.calculation_statistics",
        "dmm.system_interface_status",
        "dmm.set_voltage_range",
        "dmm.set_dcv_impedance",
    )
    assert item.wavebench_min_version == "0.8.11"
    assert item.version == "0.5.0"
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


def test_trigger_status_is_query_only_and_parses_units() -> None:
    transport = FakeTransport()

    status = DM3000Dmm(transport).trigger_status()

    assert status.source == "AUTO"
    assert status.auto_interval_s == 0.4
    assert status.auto_hold is False
    assert status.auto_hold_sensitivity == 1
    assert status.single_count == 1
    assert status.external_slope == "RISE"
    assert status.vmc_polarity == "POS"
    assert status.vmc_pulse_width_s == 0.007
    assert transport.writes == []


def test_trigger_status_rejects_unknown_time_units() -> None:
    transport = FakeTransport()
    transport.readings[":TRIGger:AUTO:INTerval?"] = "400ticks"

    with pytest.raises(DataError, match="trigger auto interval"):
        DM3000Dmm(transport).trigger_status()


def test_trigger_status_rejects_out_of_contract_discrete_response() -> None:
    transport = FakeTransport()
    transport.readings[":TRIGger:SOURce?"] = "UNKNOWN"

    with pytest.raises(DataError, match="unsupported DMM trigger source"):
        DM3000Dmm(transport).trigger_status()


def test_calculation_status_is_query_only_and_typed() -> None:
    transport = FakeTransport()

    status = DM3000Dmm(transport).calculation_status()

    assert status.function == "none"
    assert status.statistic_count == 0
    assert status.db_reference == 0.0
    assert status.dbm_reference_ohm == 600.0
    assert transport.writes == []


def test_calculation_status_rejects_nonfinite_response() -> None:
    transport = FakeTransport()
    transport.readings[":CALCulate:DB:REFerence?"] = "nan"

    with pytest.raises(DataError, match="non-finite.*dB reference"):
        DM3000Dmm(transport).calculation_status()


@pytest.mark.parametrize(
    "reported",
    ["NONE", "NULL", "DB", "DBM", "AVERAGE", "MIN", "MAX", "TOTAL", "LIMIT"],
)
def test_calculation_status_accepts_all_documented_modes(reported: str) -> None:
    transport = FakeTransport()
    transport.readings[":CALCulate:FUNCtion?"] = reported

    status = DM3000Dmm(transport).calculation_status()

    assert status.function == reported.lower()
    assert status.statistic_count == 0
    assert status.db_reference == 0.0
    assert status.dbm_reference_ohm == 600.0
    assert transport.writes == []
    assert transport.queries == [
        ":CALCulate:FUNCtion?",
        ":CALCulate:STATistic:COUNt?",
        ":CALCulate:DB:REFerence?",
        ":CALCulate:DBM:REFerence?",
    ]


def test_calculation_statistics_requires_matching_active_mode() -> None:
    transport = FakeTransport()

    with pytest.raises(InstrumentError, match="current function is none"):
        DM3000Dmm(transport).calculation_statistics("average")

    assert transport.writes == []
    assert transport.queries == [":CALCulate:FUNCtion?"]


def test_calculation_statistics_reads_existing_mode_without_writes() -> None:
    transport = FakeTransport()
    transport.readings[":CALCulate:FUNCtion?"] = "AVERAGE"

    result = DM3000Dmm(transport).calculation_statistics("average")

    assert result.function == "average"
    assert result.value == 1.25
    assert result.count == 0
    assert transport.writes == []
    assert transport.queries == [
        ":CALCulate:FUNCtion?",
        ":CALCulate:STATistic:AVERage?",
        ":CALCulate:STATistic:COUNt?",
    ]


def test_system_interface_status_is_query_only_typed_and_redacted() -> None:
    transport = FakeTransport()

    status = DM3000Dmm(transport).system_interface_status()

    assert status.beeper_enabled is True
    assert status.language == "ENGLISH"
    assert status.decimal_format == "DOT"
    assert status.separator_format == "NONE"
    assert status.display_brightness == 128
    assert status.scan_board_installed is False
    assert status.lan_interface_installed is True
    assert status.dhcp_enabled is True
    assert status.gpib_address == 22
    assert status.rs232_baud == 9600
    assert status.rs232_parity == "NONE8BITS"
    assert transport.writes == []
    assert transport.queries == [
        ":SYSTem:BEEPer:STATe?",
        ":SYSTem:LANGuage?",
        ":SYSTem:FORMat:DECimal?",
        ":SYSTem:FORMat:SEParate?",
        ":SYSTem:DISPlay:BRIGht?",
        ":SYSTem:SCANserial?",
        ":SYSTem:LANserial?",
        ":UTILity:INTerface:LAN:DHCP?",
        ":UTILity:INTerface:GPIB:ADDRess?",
        ":UTILity:INTerface:RS232:BAUD?",
        ":UTILity:INTerface:RS232:PARity?",
    ]
    forbidden = ("IDN", "MAC", ":IP?", "MASK", "GATE", "DNS", "HOST", "DOMAIN", "OPEN")
    assert not any(token in query.upper() for query in transport.queries for token in forbidden)


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        (":SYSTem:BEEPer:STATe?", "ON", "beeper state"),
        (":SYSTem:LANGuage?", "GERMAN", "language"),
        (":SYSTem:FORMat:DECimal?", "AUTO", "decimal format"),
        (":SYSTem:FORMat:SEParate?", "COMMA", "separator format"),
        (":SYSTem:DISPlay:BRIGht?", "256", "display brightness"),
        (":SYSTem:SCANserial?", "UNKNOWN", "scan board status"),
        (":SYSTem:LANserial?", "SERIAL123", "LAN interface status"),
        (":UTILity:INTerface:LAN:DHCP?", "1", "LAN DHCP state"),
        (":UTILity:INTerface:GPIB:ADDRess?", "31", "GPIB address"),
        (":UTILity:INTerface:RS232:BAUD?", "14400", "baud rate"),
        (":UTILity:INTerface:RS232:PARity?", "MARK", "parity"),
    ],
)
def test_system_interface_status_rejects_out_of_contract_responses(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.readings[command] = response

    with pytest.raises(DataError, match=message):
        DM3000Dmm(transport).system_interface_status()

    assert transport.writes == []


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
