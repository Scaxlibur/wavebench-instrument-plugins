from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments import DG4000ByteOrder, DG4000DacBlock
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_rigol_dg4000 import descriptor
from wavebench_rigol_dg4000.driver import DG4202Source


class FakeTransport:
    def __init__(self, channel: int = 1, *, model: str = "DG4202") -> None:
        self.channel = channel
        self.model = model
        self.writes: list[str] = []
        self.byte_writes: list[bytes] = []
        self.queries: list[str] = []
        self.query_overrides: dict[str, str] = {}
        self.fail_queries: set[str] = set()
        self.fail_write_commands: set[str] = set()
        self.ignored_write_commands: set[str] = set()
        self.fail_byte_write = False
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
        if command in self.ignored_write_commands:
            return
        self._apply_write(command)
        if command in self.fail_write_commands:
            self.fail_write_commands.remove(command)
            raise InstrumentError(f"injected ambiguous write failure: {command}")

    def _apply_write(self, command: str) -> None:
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
        if self.fail_byte_write:
            self.fail_byte_write = False
            raise InstrumentError("injected ambiguous binary write failure")

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command in self.fail_queries:
            raise InstrumentError(f"injected query failure: {command}")
        if command in self.query_overrides:
            return self.query_overrides[command]
        if command == "SYST:ERR?":
            if self.error_queue:
                return self.error_queue.pop(0)
            return '0,"No error"'
        channel = self.channel
        mapping = {
            "*IDN?": f"RIGOL TECHNOLOGIES,{self.model},<serial>,<firmware>",
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


def test_write_readback_accepts_instrument_display_precision() -> None:
    transport = FakeTransport()
    transport.query_overrides[":SOUR1:FREQ?"] = "1.000000E+03"
    driver = DG4202Source(transport)

    status = driver.set_frequency(1, 1000.0004)

    assert status.frequency_hz == 1000.0


def test_write_readback_rejects_material_mismatch() -> None:
    transport = FakeTransport()
    transport.query_overrides[":SOUR1:FREQ?"] = "1.001000E+03"
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="readback mismatch"):
        driver.set_frequency(1, 1000.0)


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
    transport = FakeTransport()
    driver = DG4202Source(transport)

    with pytest.raises(DataError, match="function must be"):
        driver.set_function(1, "invalid")
    with pytest.raises(DataError, match="frequency must be"):
        driver.set_frequency(1, 0.0)
    with pytest.raises(DataError, match="amplitude must be"):
        driver.set_amplitude_vpp(1, 0.0)
    with pytest.raises(DataError, match="duty cycle"):
        driver.set_square_duty_cycle(1, 100.0)
    for invalid in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(DataError, match="finite"):
            driver.set_frequency(1, invalid)
        with pytest.raises(DataError, match="finite"):
            driver.set_amplitude_vpp(1, invalid)
        with pytest.raises(DataError, match="finite"):
            driver.set_square_duty_cycle(1, invalid)

    assert transport.writes == []
    assert transport.queries == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        ("*IDN?", "OTHER,DG4202,SN,FW", "manufacturer"),
        ("*IDN?", "RIGOL TECHNOLOGIES,DG9999,SN,FW", "unsupported"),
        (":OUTP1?", "MAYBE", "output state"),
        (":SOUR1:FUNC?", "MYSTERY", "function"),
        (":SOUR1:FREQ?", "nan", "finite"),
        (":SOUR1:VOLT?", "inf", "finite"),
        (":SOUR1:VOLT:UNIT?", "WATTS", "amplitude unit"),
        (":SOUR1:VOLT:OFFS?", "nan", "finite"),
        (":SOUR1:PHAS?", "inf", "finite"),
        (":SOUR1:FREQ:MODE?", "LIST", "frequency mode"),
        (":SOUR1:SWE:STAT?", "UNKNOWN", "sweep state"),
        (":SOUR1:APPL?", '"SIN,1000,1,0"', "APPLy"),
        (":SOUR1:FUNC:SQU:DCYC?", "100", "duty cycle"),
    ],
)
def test_status_rejects_untrusted_responses_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.query_overrides[command] = response

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).get_status(1)

    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    "command",
    [
        "*IDN?",
        ":OUTP1?",
        ":SOUR1:FUNC?",
        ":SOUR1:FREQ?",
        ":SOUR1:VOLT?",
        ":SOUR1:VOLT:UNIT?",
        ":SOUR1:VOLT:OFFS?",
        ":SOUR1:PHAS?",
        ":SOUR1:FREQ:MODE?",
        ":SOUR1:SWE:STAT?",
        ":SOUR1:APPL?",
        ":SOUR1:FUNC:SQU:DCYC?",
    ],
)
def test_status_query_failure_returns_no_partial_snapshot_and_never_writes(
    command: str,
) -> None:
    transport = FakeTransport()
    transport.fail_queries.add(command)

    with pytest.raises(InstrumentError, match="injected query failure"):
        DG4202Source(transport).get_status(1)

    assert transport.writes == []
    assert transport.byte_writes == []


def test_known_unaccepted_model_is_read_only_and_unknown_model_is_rejected() -> None:
    read_transport = FakeTransport(model="DG4102")
    driver = DG4202Source(read_transport)

    assert driver.get_status(1).frequency_hz == 5000.0
    with pytest.raises(DataError, match="writes are not accepted"):
        driver.set_output(1, False)

    assert read_transport.writes == []

    unknown_transport = FakeTransport(model="DG9999")
    with pytest.raises(DataError, match="unsupported"):
        DG4202Source(unknown_transport).get_status(1)
    assert unknown_transport.writes == []


def test_instance_error_check_default_is_respected() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport, check_errors_after_ops=False)

    driver.set_output(1, False)

    assert "SYST:ERR?" not in transport.queries


def test_frequency_readback_mismatch_restores_without_latching() -> None:
    transport = FakeTransport()
    transport.ignored_write_commands.add(":SOUR1:FREQ 1000")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="readback mismatch"):
        driver.set_frequency(1, 1000.0)

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    assert transport.state["mode"] == "SWE"
    transport.ignored_write_commands.clear()
    assert driver.set_frequency(1, 2000.0).frequency_hz == 2000.0


def test_frequency_ambiguous_write_restores_and_latches() -> None:
    transport = FakeTransport()
    transport.fail_write_commands.add(":SOUR1:FREQ 1000")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="ambiguous write"):
        driver.set_frequency(1, 1000.0)

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    assert transport.state["mode"] == "SWE"
    writes_before = list(transport.writes)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_function(1, "square")
    assert transport.writes == writes_before


def test_configuration_recovery_failure_latches() -> None:
    transport = FakeTransport()
    transport.ignored_write_commands.add(":SOUR1:FREQ 1000")
    transport.fail_write_commands.add(":OUTP1 OFF")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="recovery could not be verified"):
        driver.set_frequency(1, 1000.0)

    writes_before = list(transport.writes)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_amplitude_vpp(1, 0.5)
    assert transport.writes == writes_before


def test_amplitude_second_write_ambiguity_restores_and_latches() -> None:
    transport = FakeTransport()
    transport.fail_write_commands.add(":SOUR1:VOLT 0.5")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="ambiguous write"):
        driver.set_amplitude_vpp(1, 0.5)

    assert transport.state["out"] == "OFF"
    assert transport.state["volt"] == 1.0
    assert transport.state["unit"] == "VPP"
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_function(1, "square")


def test_error_queue_failure_restores_without_latching() -> None:
    transport = FakeTransport()
    transport.error_queue = ['-222,"Data out of range"', '0,"No error"']
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="error queue"):
        driver.set_function(1, "square")

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert driver.set_function(1, "ramp").function == "RAMP"


def test_unrestorable_function_snapshot_rejects_before_write() -> None:
    transport = FakeTransport()
    transport.state["func"] = "USER"
    driver = DG4202Source(transport)

    with pytest.raises(DataError, match="restorable basic function"):
        driver.set_frequency(1, 1000.0)

    assert transport.writes == []


def test_fix_mode_disabled_rejects_sweep_snapshot_before_write() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    with pytest.raises(DataError, match="require FIX mode"):
        driver.set_frequency(1, 1000.0, ensure_fix_mode=False)

    assert transport.writes == []


def test_output_ambiguous_write_converges_off_and_latches() -> None:
    transport = FakeTransport()
    transport.fail_write_commands.add(":OUTP1 ON")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(1, True)

    assert transport.state["out"] == "OFF"
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_output(1, True)
    assert driver.set_output(1, False).output == "OFF"


def test_output_readback_mismatch_converges_off_without_latching() -> None:
    transport = FakeTransport()
    transport.ignored_write_commands.add(":OUTP1 ON")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="readback mismatch"):
        driver.set_output(1, True)

    assert transport.state["out"] == "OFF"
    transport.ignored_write_commands.clear()
    assert driver.set_output(1, True).output == "ON"


def test_output_on_rejects_preexisting_error_before_any_write() -> None:
    transport = FakeTransport()
    transport.error_queue = ['-222,"Data out of range"', '0,"No error"']
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="Data out of range"):
        driver.set_output(1, True)

    assert transport.state["out"] == "OFF"
    assert transport.writes == []


def test_latched_emergency_output_off_does_not_require_full_status_snapshot() -> None:
    transport = FakeTransport()
    transport.state["out"] = "ON"
    driver = DG4202Source(transport)
    driver._configuration_writes_blocked = True
    transport.fail_queries.add(":SOUR1:FUNC?")

    with pytest.raises(InstrumentError, match="injected query failure"):
        driver.set_output(1, False)

    assert transport.state["out"] == "OFF"
    assert ":OUTP1 OFF" in transport.writes


def test_public_io_operations_do_not_interleave_between_threads() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(driver.set_frequency, 1, 1000.0),
            executor.submit(driver.set_function, 1, "square"),
        ]
        for future in futures:
            future.result()

    transaction_writes = [
        command
        for command in transport.writes
        if command in {
            ":SOUR1:FREQ:MODE FIX",
            ":SOUR1:FREQ 1000",
            ":SOUR1:FUNC SQU",
        }
    ]
    assert transaction_writes in (
        [":SOUR1:FREQ:MODE FIX", ":SOUR1:FREQ 1000", ":SOUR1:FUNC SQU"],
        [":SOUR1:FUNC SQU", ":SOUR1:FREQ:MODE FIX", ":SOUR1:FREQ 1000"],
    )


def test_arbitrary_upload_uses_validated_public_block_and_exact_command_order() -> None:
    payload = b"\x00\x00\xff\x3f"
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14" + payload,
        points=2,
        data_bytes=len(payload),
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
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


def test_arbitrary_upload_requires_output_off_and_fix_mode_before_any_write() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )

    active = FakeTransport()
    active.state["out"] = "ON"
    active.state["mode"] = "FIX"
    active.state["swe"] = "OFF"
    with pytest.raises(DataError, match="output to be OFF"):
        DG4202Source(active).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )
    assert active.writes == []
    assert active.byte_writes == []

    sweep = FakeTransport()
    with pytest.raises(DataError, match="FIX mode"):
        DG4202Source(sweep).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )
    assert sweep.writes == []
    assert sweep.byte_writes == []


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_arbitrary_upload_rejects_nonfinite_parameters_without_io(invalid: float) -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    driver = DG4202Source(transport)

    for kwargs in (
        {"playback_frequency_hz": invalid, "amplitude_vpp": 1.0},
        {"playback_frequency_hz": 1000.0, "amplitude_vpp": invalid},
        {
            "playback_frequency_hz": 1000.0,
            "amplitude_vpp": 1.0,
            "offset_v": invalid,
        },
    ):
        with pytest.raises(DataError, match="finite"):
            driver.upload_dg4000_dac14_block(channel=1, block=block, **kwargs)

    assert transport.queries == []
    assert transport.writes == []
    assert transport.byte_writes == []


def test_arbitrary_binary_ambiguity_restores_basic_state_and_latches() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
    transport.fail_byte_write = True
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="previous volatile waveform cannot be restored"):
        driver.upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    writes_before = list(transport.writes)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_frequency(1, 2000.0)
    assert transport.writes == writes_before


def test_arbitrary_post_binary_failure_restores_offset_and_reports_side_effect() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
    transport.state["offs"] = 0.25
    transport.ignored_write_commands.add(":SOUR1:VOLT:OFFS 0.1")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="previous volatile waveform cannot be restored"):
        driver.upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=2000.0,
            amplitude_vpp=1.2,
            offset_v=0.1,
        )

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    assert transport.state["offs"] == 0.25


def test_arbitrary_upload_without_output_request_remains_off() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"

    status = DG4202Source(transport).upload_dg4000_dac14_block(
        channel=1,
        block=block,
        playback_frequency_hz=1000.0,
        amplitude_vpp=1.0,
    )

    assert status.output == "OFF"
    assert not any(command == ":OUTP1 ON" for command in transport.writes)


def test_arbitrary_upload_requires_binary_transport() -> None:
    transport = FakeTransport()
    transport.write_bytes = None  # type: ignore[method-assign,assignment]
    block = DG4000DacBlock(
        b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        2,
        4,
        DG4000ByteOrder.LITTLE,
    )

    with pytest.raises(InstrumentError, match="does not support binary"):
        DG4202Source(transport).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )


@pytest.mark.parametrize(
    "block",
    [
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
            2,
            4,
            DG4000ByteOrder.BIG,
        ),
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
            3,
            4,
            DG4000ByteOrder.LITTLE,
        ),
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00",
            2,
            4,
            DG4000ByteOrder.LITTLE,
        ),
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00\x00\x40",
            2,
            4,
            DG4000ByteOrder.LITTLE,
        ),
    ],
)
def test_arbitrary_upload_rejects_unvalidated_block_before_io(
    block: DG4000DacBlock,
) -> None:
    transport = FakeTransport()

    with pytest.raises(
        DataError,
        match="little-endian|byte count|payload length|within 0..16383",
    ):
        DG4202Source(transport).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )

    assert transport.queries == []
    assert transport.writes == []
    assert transport.byte_writes == []


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
