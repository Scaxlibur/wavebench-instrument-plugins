from __future__ import annotations

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments import DG4000ByteOrder, DG4000DacBlock
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_rigol_dg4000 import descriptor
from wavebench_rigol_dg4000.driver import DG4202Source


class FakeTransport:
    def __init__(self, channel: int = 1) -> None:
        self.channel = channel
        self.writes: list[str] = []
        self.byte_writes: list[bytes] = []
        self.error_queue = ['0,"No error"']
        self.closed = False
        self.state = {
            "out": "OFF",
            "func": "SIN",
            "freq": 5000.0,
            "volt": 1.0,
            "unit": "VPP",
            "offs": 0.0,
            "phas": 0.0,
            "mode": "SWE",
            "swe": "ON",
            "apply": '"SIN,5.000000E+03,1.000000E+00,0.000000E+00,0.000000E+00"',
            "duty": 50.0,
        }

    def write(self, command: str) -> None:
        self.writes.append(command)
        prefix = f":SOUR{self.channel}"
        if command.startswith(f"{prefix}:FREQ:MODE "):
            self.state["mode"] = command.split()[-1]
            self.state["swe"] = "OFF" if self.state["mode"] == "FIX" else "ON"
        elif command.startswith(f"{prefix}:FREQ "):
            self.state["freq"] = float(command.split()[-1])
        elif command.startswith(f":OUTP{self.channel} "):
            self.state["out"] = command.split()[-1]
        elif command.startswith(f"{prefix}:FUNC:SHAP "):
            self.state["func"] = command.split()[-1]
        elif command.startswith(f"{prefix}:FUNC:SQU:DCYC "):
            self.state["duty"] = float(command.split()[-1])
        elif command.startswith(f"{prefix}:FUNC "):
            self.state["func"] = command.split()[-1]
        elif command.startswith(f"{prefix}:VOLT:OFFS "):
            self.state["offs"] = float(command.split()[-1])
        elif command.startswith(f"{prefix}:VOLT:UNIT "):
            self.state["unit"] = command.split()[-1]
        elif command.startswith(f"{prefix}:VOLT "):
            self.state["volt"] = float(command.split()[-1])

    def write_bytes(self, command: bytes) -> None:
        self.byte_writes.append(command)

    def query(self, command: str) -> str:
        if command == "SYST:ERR?":
            if self.error_queue:
                return self.error_queue.pop(0)
            return '0,"No error"'
        channel = self.channel
        mapping = {
            "*IDN?": "RIGOL TECHNOLOGIES,DG4202,<serial>,<firmware>",
            f":OUTP{channel}?": self.state["out"],
            f":SOUR{channel}:FUNC?": self.state["func"],
            f":SOUR{channel}:FREQ?": str(self.state["freq"]),
            f":SOUR{channel}:VOLT?": str(self.state["volt"]),
            f":SOUR{channel}:VOLT:UNIT?": self.state["unit"],
            f":SOUR{channel}:VOLT:OFFS?": str(self.state["offs"]),
            f":SOUR{channel}:PHAS?": str(self.state["phas"]),
            f":SOUR{channel}:FREQ:MODE?": self.state["mode"],
            f":SOUR{channel}:SWE:STAT?": self.state["swe"],
            f":SOUR{channel}:APPL?": self.state["apply"],
            f":SOUR{channel}:FUNC:SQU:DCYC?": str(self.state["duty"]),
            f":SOUR{channel}:FUNC:USER?": '"USER1"',
            f":SOUR{channel}:ARB:SRAT?": "1000000",
        }
        if command not in mapping:
            self.error_queue.append('-113,"Undefined header"')
            return ""
        return str(mapping[command])

    def close(self) -> None:
        self.closed = True


def test_descriptor_declares_canonical_source_contract_without_io() -> None:
    item = descriptor()

    assert item.driver_id == "rigol.dg4202"
    assert item.distribution == "wavebench-rigol-dg4000"
    assert item.aliases == ()
    assert item.kind == "source"
    assert "source.arbitrary_upload" in item.capabilities


def test_factory_opens_exactly_one_core_transport_and_satisfies_capabilities() -> None:
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
        resource="TCPIP::192.0.2.30::INSTR",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
        settings={"check_errors": True},
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, DG4202Source)
    assert driver.transport is transport
    assert opened == 1


def test_status_and_fixed_frequency_flow() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    before = driver.get_status(1)
    after = driver.set_frequency(1, 1000.0)
    assert before.frequency_mode == "SWE"
    assert transport.writes[:2] == [":SOUR1:FREQ:MODE FIX", ":SOUR1:FREQ 1000"]
    assert after.frequency_mode == "FIX"
    assert after.frequency_hz == 1000.0


def test_second_channel_uses_channel_two_scpi_prefixes() -> None:
    transport = FakeTransport(channel=2)
    driver = DG4202Source(transport)

    status = driver.set_frequency(2, 2500.0)

    assert transport.writes[:2] == [":SOUR2:FREQ:MODE FIX", ":SOUR2:FREQ 2500"]
    assert status.channel == 2
    assert status.frequency_hz == 2500.0


def test_function_amplitude_duty_and_output_commands() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    assert driver.set_function(1, "triangle").function == "RAMP"
    assert driver.set_amplitude_vpp(1, 1.25).amplitude == 1.25
    assert driver.set_square_duty_cycle(1, 25.0).square_duty_cycle_percent == 25.0
    assert driver.set_output(1, True).output == "ON"


@pytest.mark.parametrize("channel", [0, 3])
def test_rejects_channels_outside_dg4202_range(channel: int) -> None:
    with pytest.raises(DataError, match="must be 1 or 2"):
        DG4202Source(FakeTransport()).get_status(channel)


def test_rejects_invalid_function_frequency_amplitude_and_duty() -> None:
    driver = DG4202Source(FakeTransport())

    with pytest.raises(DataError, match="function must be"):
        driver.set_function(1, "invalid")
    with pytest.raises(DataError, match="frequency must be"):
        driver.set_frequency(1, 0.0)
    with pytest.raises(DataError, match="amplitude must be"):
        driver.set_amplitude_vpp(1, 0.0)
    with pytest.raises(DataError, match="duty cycle"):
        driver.set_square_duty_cycle(1, 100.0)


def test_arbitrary_upload_uses_validated_public_block_and_exact_command_order() -> None:
    payload = b"\x00\x00\xff\x3f"
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14" + payload,
        points=2,
        data_bytes=len(payload),
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    driver = DG4202Source(transport)

    status = driver.upload_dg4000_dac14_block(
        channel=1,
        block=block,
        playback_frequency_hz=2000.0,
        amplitude_vpp=1.2,
        offset_v=0.1,
        output_on=True,
    )

    assert transport.byte_writes == [block.command]
    assert transport.writes[:6] == [
        "*CLS",
        ":SOUR1:FREQ 2000",
        ":SOUR1:VOLT:UNIT VPP",
        ":SOUR1:VOLT 1.2",
        ":SOUR1:VOLT:OFFS 0.1",
        ":SOUR1:FUNC:SHAP USER",
    ]
    assert ":OUTP1 ON" in transport.writes
    assert status.function == "USER"


def test_arbitrary_upload_requires_binary_transport() -> None:
    transport = FakeTransport()
    transport.write_bytes = None  # type: ignore[method-assign,assignment]

    with pytest.raises(InstrumentError, match="does not support binary"):
        DG4202Source(transport).upload_dg4000_dac14_block(
            channel=1,
            block=DG4000DacBlock(b":DATA:DAC VOLATILE,#10", 0, 0, DG4000ByteOrder.LITTLE),
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )


def test_probe_is_query_only_and_continues_across_unsupported_commands() -> None:
    driver = DG4202Source(FakeTransport())

    results = driver.probe_arbitrary_queries(1)

    assert all(item.command.endswith("?") for item in results)
    accepted = {item.label: item.accepted for item in results}
    assert accepted["user_function"]
    assert accepted["arb_sample_rate"]
    assert not accepted["source_data_catalog"]
    with pytest.raises(DataError, match="query-only"):
        driver.probe_arbitrary_queries(1, candidates=(("bad", ":SOUR1:FUNC ARB"),))


def test_error_queue_failure_is_reported_and_close_is_forwarded() -> None:
    transport = FakeTransport()
    transport.error_queue = ['-222,"Data out of range"', '0,"No error"']
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="Data out of range"):
        driver.assert_no_errors()
    driver.close()

    assert transport.closed
