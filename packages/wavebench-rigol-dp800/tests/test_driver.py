from __future__ import annotations

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_rigol_dp800 import descriptor
from wavebench_rigol_dp800.driver import (
    DP800Power,
    parse_apply_response,
    parse_idn_model,
    parse_measure_all_response,
    parse_protection_value_response,
)


class FakeTransport:
    def __init__(self) -> None:
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.closed = False
        self.errors = ['0,"No error"']
        self.fail_command: str | None = None
        self.responses = {
            "*IDN?": "RIGOL TECHNOLOGIES,DP832A,<serial>,<firmware>",
            ":APPL? CH1": "CH1:30V/3A,5.000,0.100",
            ":MEAS:ALL? CH1": "5.0114,0.0000,0.000",
            ":OUTP? CH1": "OFF",
            ":OUTP:MODE? CH1": "CV",
            ":OUTP:OVP? CH1": "ON",
            ":OUTP:OVP:VAL? CH1": "6.000",
            ":OUTP:OVP:QUES? CH1": "NO",
            ":OUTP:OCP? CH1": "ON",
            ":OUTP:OCP:VAL? CH1": "0.5000",
            ":OUTP:OCP:QUES? CH1": "NO",
        }

    def write(self, command: str) -> None:
        self.writes.append(command)

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command == self.fail_command:
            raise InstrumentError(f"injected failure for {command}")
        if command == "SYST:ERR?":
            return self.errors.pop(0)
        return self.responses[command]

    def close(self) -> None:
        self.closed = True


def test_descriptor_matches_current_head_contract() -> None:
    item = descriptor()

    assert item.driver_id == "rigol.dp800"
    assert item.distribution == "wavebench-rigol-dp800"
    assert item.aliases == ()
    assert item.kind == "power"
    assert item.backends == ("pyvisa",)
    assert item.capabilities == (
        "power.idn",
        "power.status",
        "power.measurement",
        "power.set_voltage_current_limit",
        "power.output",
        "power.protection",
    )


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
        resource="TCPIP::192.0.2.50::INSTR",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=1000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
        settings={"check_errors": True},
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, DP800Power)
    assert driver.transport is transport
    assert driver.check_errors_after_ops is True
    assert opened == 1


def test_parsers_preserve_current_head_behavior() -> None:
    assert parse_idn_model("RIGOL TECHNOLOGIES,DP811A,<serial>,<firmware>") == (
        "DP811A",
        1,
    )
    assert parse_idn_model("RIGOL TECHNOLOGIES,DP821,<serial>,<firmware>") == ("DP821", 2)
    with pytest.raises(DataError, match="unsupported DP800 model"):
        parse_idn_model("RIGOL TECHNOLOGIES,DP999,<serial>,<firmware>")
    assert parse_apply_response("CH1:30V/3A,5.000,0.100") == ("30V/3A", 5.0, 0.1)
    assert parse_apply_response(
        "5.000,0.100", expected_channel=1, allow_targetless=True
    ) == (None, 5.0, 0.1)
    assert parse_measure_all_response("5.0114,0.0000,0.000") == (5.0114, 0.0, 0.0)
    assert parse_protection_value_response("8.800") == 8.8
    with pytest.raises(DataError, match="unexpected DP800 APPL"):
        parse_apply_response("CH1:30V/3A,5.000")
    with pytest.raises(DataError, match="unexpected DP800 APPL"):
        parse_apply_response("CH1:30V/3A,5.000,0.100,extra")
    with pytest.raises(DataError, match="unexpected DP800 MEAS:ALL"):
        parse_measure_all_response("5.0,0.1")
    with pytest.raises(DataError, match="unexpected DP800 MEAS:ALL"):
        parse_measure_all_response("5.0,0.1,0.5,extra")
    with pytest.raises(DataError, match="unexpected DP800 APPL.*channel"):
        parse_apply_response("CH2:30V/3A,5.000,0.100", expected_channel=1)
    with pytest.raises(DataError, match="confirmed single-channel target"):
        parse_apply_response("5.000,0.100", expected_channel=2)
    with pytest.raises(DataError, match="confirmed single-channel target"):
        parse_apply_response("5.000,0.100", expected_channel=1)
    with pytest.raises(DataError, match="unexpected DP800 APPL.*target"):
        parse_apply_response("CH1:bogus,5.000,0.100")
    with pytest.raises(DataError, match="must be finite"):
        parse_apply_response("CH1:30V/3A,nan,0.100")
    with pytest.raises(DataError, match="must be finite"):
        parse_measure_all_response("5.0,inf,0.1")


def test_read_only_operations_return_public_models() -> None:
    transport = FakeTransport()
    driver = DP800Power(transport)

    assert driver.idn().startswith("RIGOL TECHNOLOGIES,DP832A")
    status = driver.get_status(1)
    measurement = driver.get_measurement(1)
    protection = driver.get_protection_status(1)

    assert status.output == "OFF"
    assert status.mode == "CV"
    assert status.rating == "30V/3A"
    assert status.set_voltage_v == 5.0
    assert status.set_current_a == 0.1
    assert measurement.measured_voltage_v == 5.0114
    assert protection.ovp_threshold_v == 6.0
    assert protection.ocp_threshold_a == 0.5


def test_setpoint_writes_once_then_reads_back_and_checks_errors() -> None:
    transport = FakeTransport()

    status = DP800Power(transport).set_voltage_current_limit(
        1,
        3.3,
        0.2,
        check_errors=True,
        settle_ms_after_set=0,
    )

    assert transport.writes == [":APPL CH1,3.3,0.2"]
    assert status.channel == 1
    assert transport.queries[-1] == "SYST:ERR?"


def test_output_writes_only_output_command() -> None:
    transport = FakeTransport()

    DP800Power(transport).set_output(1, True, check_errors=True)

    assert transport.writes == [":OUTP CH1,ON"]
    assert not any(command.startswith(":APPL ") for command in transport.writes)


def test_protection_write_order_and_error_check_are_stable() -> None:
    transport = FakeTransport()

    DP800Power(transport).set_protection(
        1,
        ovp_threshold_v=4.0,
        ovp_enabled=True,
        ocp_threshold_a=0.3,
        ocp_enabled=True,
        check_errors=True,
    )

    assert transport.writes == [
        ":OUTP:OVP:VAL CH1,4",
        ":OUTP:OVP CH1,ON",
        ":OUTP:OCP:VAL CH1,0.3",
        ":OUTP:OCP CH1,ON",
    ]
    assert transport.queries[-1] == "SYST:ERR?"


def test_error_queue_and_validation_fail_closed() -> None:
    transport = FakeTransport()
    transport.errors = ['-100,"Command error"', '0,"No error"']
    driver = DP800Power(transport)

    with pytest.raises(InstrumentError, match="Command error"):
        driver.assert_no_errors()
    with pytest.raises(DataError, match="channel must be an integer >= 1"):
        driver.get_status(0)
    with pytest.raises(DataError, match="voltage must be >= 0"):
        driver.set_voltage_current_limit(1, -1.0, 0.1)
    with pytest.raises(DataError, match="current limit must be > 0"):
        driver.set_voltage_current_limit(1, 1.0, 0.0)
    with pytest.raises(DataError, match="OVP threshold must be >= 0"):
        driver.set_protection(1, ovp_threshold_v=-1.0)
    with pytest.raises(DataError, match="OCP threshold must be > 0"):
        driver.set_protection(1, ocp_threshold_a=0.0)
    with pytest.raises(DataError, match="must be finite"):
        driver.set_voltage_current_limit(1, float("nan"), 0.1)
    with pytest.raises(DataError, match="must be finite"):
        driver.set_voltage_current_limit(1, 1.0, float("inf"))
    with pytest.raises(DataError, match="must be finite"):
        driver.set_protection(1, ovp_threshold_v=float("nan"))
    with pytest.raises(DataError, match="must be finite"):
        driver.set_protection(1, ocp_threshold_a=float("inf"))


def test_channel_count_fails_closed() -> None:
    transport = FakeTransport()
    transport.responses["*IDN?"] = "RIGOL TECHNOLOGIES,DP821A,<serial>,<firmware>"
    driver = DP800Power(transport)
    with pytest.raises(DataError, match="CH3 is unavailable"):
        driver.get_status(3)
    assert transport.queries == ["*IDN?"]


def test_unaccepted_models_are_read_only() -> None:
    transport = FakeTransport()
    transport.responses["*IDN?"] = "RIGOL TECHNOLOGIES,DP811A,<serial>,<firmware>"
    transport.responses[":APPL?"] = "5.000,0.100"
    driver = DP800Power(transport)
    assert driver.get_status(1).set_voltage_v == 5.0
    with pytest.raises(DataError, match="writes are supported only"):
        driver.set_voltage_current_limit(1, 3.3, 0.2)
    with pytest.raises(DataError, match="writes are supported only"):
        driver.set_output(1, False)
    with pytest.raises(DataError, match="writes are supported only"):
        driver.set_protection(1, ovp_enabled=False)
    assert transport.writes == []


def test_instance_error_check_default_is_honored() -> None:
    transport = FakeTransport()
    DP800Power(transport, check_errors_after_ops=False).set_output(1, False)
    assert "SYST:ERR?" not in transport.queries

    transport = FakeTransport()
    DP800Power(transport, check_errors_after_ops=False).set_output(
        1, False, check_errors=True
    )
    assert "SYST:ERR?" in transport.queries


def test_single_channel_status_uses_targetless_apply_query() -> None:
    transport = FakeTransport()
    transport.responses["*IDN?"] = "RIGOL TECHNOLOGIES,DP811A,<serial>,<firmware>"
    transport.responses[":APPL?"] = "5.000,0.100"
    status = DP800Power(transport).get_status(1)
    assert status.rating is None
    assert status.set_voltage_v == 5.0
    assert status.set_current_a == 0.1
    assert transport.queries[:2] == ["*IDN?", ":APPL?"]



@pytest.mark.parametrize(
    ("command", "response", "operation", "message"),
    (
        (":OUTP? CH1", "MAYBE", "status", "output state"),
        (":OUTP:MODE? CH1", "UNKNOWN", "status", "output mode"),
        (":OUTP:OVP? CH1", "MAYBE", "protection", "OVP state"),
        (":OUTP:OVP:QUES? CH1", "UNKNOWN", "protection", "OVP trip state"),
        (":OUTP:OCP? CH1", "MAYBE", "protection", "OCP state"),
        (":OUTP:OCP:QUES? CH1", "UNKNOWN", "protection", "OCP trip state"),
    ),
)
def test_all_enums_fail_closed(
    command: str,
    response: str,
    operation: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.responses[command] = response
    driver = DP800Power(transport)
    with pytest.raises(DataError, match=f"unexpected DP800 {message}"):
        if operation == "status":
            driver.get_status(1)
        else:
            driver.get_protection_status(1)
    assert transport.writes == []


@pytest.mark.parametrize(
    "command",
    (":APPL? CH1", ":MEAS:ALL? CH1", ":OUTP? CH1", ":OUTP:MODE? CH1"),
)
def test_status_snapshot_fails_at_every_query_without_writes(command: str) -> None:
    transport = FakeTransport()
    transport.fail_command = command
    with pytest.raises(InstrumentError, match="injected failure"):
        DP800Power(transport).get_status(1)
    assert transport.writes == []


@pytest.mark.parametrize(
    "command",
    (
        ":OUTP:OVP? CH1",
        ":OUTP:OVP:VAL? CH1",
        ":OUTP:OVP:QUES? CH1",
        ":OUTP:OCP? CH1",
        ":OUTP:OCP:VAL? CH1",
        ":OUTP:OCP:QUES? CH1",
    ),
)
def test_protection_snapshot_fails_at_every_query_without_writes(command: str) -> None:
    transport = FakeTransport()
    transport.fail_command = command
    with pytest.raises(InstrumentError, match="injected failure"):
        DP800Power(transport).get_protection_status(1)
    assert transport.writes == []


def test_close_delegates_to_transport() -> None:
    transport = FakeTransport()

    DP800Power(transport).close()

    assert transport.closed
