from __future__ import annotations

from threading import Event, Thread

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.logging import CommandLogger

from wavebench_shengpu_sp3000a import descriptor
from wavebench_shengpu_sp3000a.driver import (
    SP30120ControlError,
    SP30120ProtocolError,
    SP30120SweepAnalyzer,
)


class FakeTransport:
    def __init__(
        self,
        responses: dict[str, str] | None = None,
        *,
        ignored_writes: set[str] | None = None,
        failing_writes: set[str] | None = None,
        failing_queries_after_write: set[str] | None = None,
        rf_on_after_write: set[str] | None = None,
        mutate_after_write: dict[str, tuple[str, str]] | None = None,
    ) -> None:
        self.responses = {
            "*IDN?": "SHENGPU SP3000 Series Digital Sweeper",
            "RFSTAT?": "ON",
            "OUTOHMSEL?": "50",
            "CENS?": "6.050000e+07,1.190000e+08",
            "STAS?": "1.000000e+06,1.200000e+08",
            "CWFREQ?": "1.000000e+07",
            "FREQOFFSET?": "0.000000e+00",
            "SWET?": "2.000000e-01",
            "SWET:MODE?": "LIN",
            "TRIM?": "CONT",
            "EXTT?": "OFF",
            "INPZ?": "50",
            "SETREFP?": "4",
            "CLOCKSW?": "ON",
            "LANGSEL?": "CHINESE",
            **(responses or {}),
        }
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.events: list[tuple[str, str]] = []
        self.ignored_writes = ignored_writes or set()
        self.failing_writes = failing_writes or set()
        self.failing_queries_after_write = failing_queries_after_write or set()
        self.rf_on_after_write = rf_on_after_write or set()
        self.mutate_after_write = mutate_after_write or {}
        self.closed = False

    def query(self, command: str) -> str:
        self.queries.append(command)
        self.events.append(("query", command))
        if self.writes and command in self.failing_queries_after_write:
            raise OSError("simulated post-write query failure")
        return self.responses[command]

    def write(self, command: str) -> None:
        self.writes.append(command)
        self.events.append(("write", command))
        if command in self.failing_writes:
            raise OSError("simulated write failure")
        if command in self.ignored_writes:
            return
        prefix, value = command.split(" ", 1)
        query = {
            "TRIM": "TRIM?",
            "SETREFP": "SETREFP?",
            "CLOCKSW": "CLOCKSW?",
            "LANGSEL": "LANGSEL?",
            "EXTT": "EXTT?",
        }[prefix]
        self.responses[query] = value
        if command in self.rf_on_after_write:
            self.responses["RFSTAT?"] = "ON"
        if command in self.mutate_after_write:
            key, response = self.mutate_after_write[command]
            self.responses[key] = response

    def close(self) -> None:
        self.closed = True


class BlockingControlsTransport(FakeTransport):
    """Pause a controls snapshot after it owns the driver's transaction lock."""

    def __init__(self) -> None:
        super().__init__({"RFSTAT?": "OFF"})
        self.snapshot_entered = Event()
        self.release_snapshot = Event()

    def query(self, command: str) -> str:
        if command == "SETREFP?" and not self.snapshot_entered.is_set():
            self.snapshot_entered.set()
            assert self.release_snapshot.wait(timeout=2)
        return super().query(command)


def test_descriptor_is_query_only_executable_metadata_without_io() -> None:
    item = descriptor()

    assert item.driver_id == "shengpu.sp30120"
    assert item.api_version == "wavebench.instrument.v2"
    assert item.kind == "sweep_analyzer"
    assert item.models == ("SP30120",)
    assert item.aliases == ()
    assert item.backends == ("serial",)
    assert item.capabilities == ("sweep_analyzer.idn",)
    assert item.distribution == "wavebench-shengpu-sp3000a"


def test_factory_opens_exactly_one_core_transport() -> None:
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
        resource="serial-by-id:<configured>",
        backend="serial",
        timeout_ms=2000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, SP30120SweepAnalyzer)
    assert driver.transport is transport
    assert opened == 1
    assert transport.queries == []


def test_verified_scalar_status_is_query_only_and_typed() -> None:
    transport = FakeTransport()
    driver = SP30120SweepAnalyzer(transport)

    assert driver.idn() == "SHENGPU SP3000 Series Digital Sweeper"
    status = driver.read_scalar_status()

    assert status.rf_output_enabled is True
    assert status.source_impedance_ohm == 50
    assert status.center_frequency_hz == 60_500_000.0
    assert status.span_frequency_hz == 119_000_000.0
    assert status.start_frequency_hz == 1_000_000.0
    assert status.stop_frequency_hz == 120_000_000.0
    assert status.cw_frequency_hz == 10_000_000.0
    assert status.frequency_offset_hz == 0.0
    assert status.sweep_time_s == 0.2
    assert status.sweep_axis == "linear"
    assert status.acquisition == "continuous"
    assert status.external_trigger_enabled is False
    assert status.input_impedance == 50
    assert transport.writes == []
    assert all(command.endswith("?") for command in transport.queries)


def test_certified_controls_readback_is_typed_and_query_only() -> None:
    transport = FakeTransport()
    controls = SP30120SweepAnalyzer(transport).read_certified_controls()

    assert controls.trim == "continuous"
    assert controls.reference_position == 4
    assert controls.clock_display == "on"
    assert controls.ui_language == "chinese"
    assert controls.external_trigger == "off"
    assert transport.writes == []
    assert transport.queries == ["TRIM?", "SETREFP?", "CLOCKSW?", "LANGSEL?", "EXTT?"]


@pytest.mark.parametrize(
    ("method", "value", "command", "query", "wire_value"),
    [
        ("set_trim", "single", "TRIM SING", "TRIM?", "SING"),
        ("set_reference_position", 5, "SETREFP 5", "SETREFP?", "5"),
        ("set_clock_display", "off", "CLOCKSW OFF", "CLOCKSW?", "OFF"),
        ("set_ui_language", "english", "LANGSEL ENGLISH", "LANGSEL?", "ENGLISH"),
        ("set_external_trigger", "on_sweep", "EXTT ONSWEE", "EXTT?", "ONSWEE"),
    ],
)
def test_certified_control_uses_one_write_with_independent_readback_and_fingerprints(
    method: str,
    value: object,
    command: str,
    query: str,
    wire_value: str,
) -> None:
    transport = FakeTransport({"RFSTAT?": "OFF"})
    driver = SP30120SweepAnalyzer(transport)

    assert getattr(driver, method)(value) == value

    assert transport.writes == [command]
    assert transport.responses[query] == wire_value
    write_index = transport.events.index(("write", command))
    assert ("query", "*IDN?") in transport.events[:write_index]
    assert ("query", "RFSTAT?") in transport.events[:write_index]
    assert ("query", query) in transport.events[:write_index]
    assert ("query", query) in transport.events[write_index + 1 :]
    assert ("query", "RFSTAT?") in transport.events[write_index + 1 :]
    assert transport.events[-1] == ("query", "*IDN?")
    assert driver.control_writes_blocked is False


@pytest.mark.parametrize(
    ("method", "value"),
    [
        ("set_trim", "invalid"),
        ("set_trim", []),
        ("set_reference_position", 3),
        ("set_reference_position", True),
        ("set_reference_position", 4.0),
        ("set_clock_display", "enabled"),
        ("set_ui_language", "french"),
        ("set_external_trigger", "on"),
    ],
)
def test_invalid_certified_control_value_performs_zero_io(method: str, value: object) -> None:
    transport = FakeTransport({"RFSTAT?": "OFF"})

    with pytest.raises(DataError):
        getattr(SP30120SweepAnalyzer(transport), method)(value)

    assert transport.events == []


def test_certified_control_reasserts_an_existing_target_with_full_postchecks() -> None:
    transport = FakeTransport({"RFSTAT?": "OFF"})

    assert SP30120SweepAnalyzer(transport).set_clock_display("on") == "on"

    assert transport.writes == ["CLOCKSW ON"]
    assert transport.queries.count("CLOCKSW?") == 2
    write_index = transport.events.index(("write", "CLOCKSW ON"))
    assert transport.events[-1] == ("query", "*IDN?")
    assert ("query", "RFSTAT?") in transport.events[write_index + 1 :]


def test_rf_on_interlock_blocks_before_any_write_and_does_not_latch() -> None:
    transport = FakeTransport({"RFSTAT?": "ON"})
    driver = SP30120SweepAnalyzer(transport)

    with pytest.raises(SP30120ControlError, match="RF output must.*OFF") as caught:
        driver.set_clock_display("off")

    assert caught.value.phase == "preflight"
    assert caught.value.state_uncertain is False
    assert caught.value.retryable is False
    assert transport.writes == []
    assert driver.control_writes_blocked is False


@pytest.mark.parametrize(
    ("transport", "phase"),
    [
        (
            FakeTransport({"RFSTAT?": "OFF"}, failing_writes={"CLOCKSW OFF"}),
            "write",
        ),
        (
            FakeTransport({"RFSTAT?": "OFF"}, ignored_writes={"CLOCKSW OFF"}),
            "readback",
        ),
        (
            FakeTransport({"RFSTAT?": "OFF"}, rf_on_after_write={"CLOCKSW OFF"}),
            "rf-postcheck",
        ),
        (
            FakeTransport(
                {"RFSTAT?": "OFF"},
                mutate_after_write={"CLOCKSW OFF": ("CENS?", "6.000000e+07,1.190000e+08")},
            ),
            "fingerprint-postcheck",
        ),
        (
            FakeTransport(
                {"RFSTAT?": "OFF"},
                mutate_after_write={
                    "CLOCKSW OFF": ("*IDN?", "unrecognized instrument family")
                },
            ),
            "identity-postcheck",
        ),
    ],
)
def test_uncertain_write_failure_latches_instance_and_prevents_second_write(
    transport: FakeTransport,
    phase: str,
) -> None:
    driver = SP30120SweepAnalyzer(transport)

    with pytest.raises(SP30120ControlError) as caught:
        driver.set_clock_display("off")

    assert caught.value.phase == phase
    assert caught.value.state_uncertain is True
    assert caught.value.retryable is False
    assert driver.control_writes_blocked is True
    events_after_failure = list(transport.events)

    with pytest.raises(SP30120ControlError, match="uncertain write outcome") as blocked:
        driver.set_ui_language("english")

    assert blocked.value.phase == "latched"
    assert transport.events == events_after_failure
    assert len(transport.writes) == 1


@pytest.mark.parametrize(
    ("query", "phase", "query_count"),
    [
        ("CLOCKSW?", "readback", 2),
        ("RFSTAT?", "rf-postcheck", 3),
        ("OUTOHMSEL?", "fingerprint-postcheck", 2),
        ("*IDN?", "identity-postcheck", 2),
    ],
)
def test_post_write_query_exception_latches_without_retry(
    query: str,
    phase: str,
    query_count: int,
) -> None:
    transport = FakeTransport(
        {"RFSTAT?": "OFF"},
        failing_queries_after_write={query},
    )
    driver = SP30120SweepAnalyzer(transport)

    with pytest.raises(SP30120ControlError) as caught:
        driver.set_clock_display("off")

    assert caught.value.phase == phase
    assert caught.value.state_uncertain is True
    assert caught.value.retryable is False
    assert transport.writes == ["CLOCKSW OFF"]
    assert transport.queries.count(query) == query_count
    events_after_failure = list(transport.events)

    with pytest.raises(SP30120ControlError) as blocked:
        driver.set_trim("single")

    assert blocked.value.phase == "latched"
    assert transport.events == events_after_failure


@pytest.mark.parametrize(
    ("method", "value", "command"),
    [
        ("set_trim", "single", "TRIM SING"),
        ("set_reference_position", 5, "SETREFP 5"),
        ("set_clock_display", "off", "CLOCKSW OFF"),
        ("set_ui_language", "english", "LANGSEL ENGLISH"),
        ("set_external_trigger", "on_sweep", "EXTT ONSWEE"),
    ],
)
def test_each_certified_setter_latches_on_write_failure_and_then_performs_zero_io(
    method: str,
    value: object,
    command: str,
) -> None:
    transport = FakeTransport({"RFSTAT?": "OFF"}, failing_writes={command})
    driver = SP30120SweepAnalyzer(transport)

    with pytest.raises(SP30120ControlError) as caught:
        getattr(driver, method)(value)

    assert caught.value.phase == "write"
    assert caught.value.state_uncertain is True
    assert transport.writes == [command]
    events_after_failure = list(transport.events)

    with pytest.raises(SP30120ControlError, match="uncertain write outcome") as blocked:
        driver.set_clock_display("on")

    assert blocked.value.phase == "latched"
    assert transport.events == events_after_failure


def test_controls_snapshot_and_setter_cannot_interleave() -> None:
    transport = BlockingControlsTransport()
    driver = SP30120SweepAnalyzer(transport)
    controls: list[object] = []
    writer_finished = Event()

    reader = Thread(target=lambda: controls.append(driver.read_certified_controls()))
    reader.start()
    assert transport.snapshot_entered.wait(timeout=1)

    def set_clock() -> None:
        driver.set_clock_display("off")
        writer_finished.set()

    writer = Thread(target=set_clock)
    writer.start()
    assert not writer_finished.wait(timeout=0.1)
    assert transport.writes == []

    transport.release_snapshot.set()
    reader.join(timeout=2)
    writer.join(timeout=2)

    assert not reader.is_alive()
    assert not writer.is_alive()
    assert len(controls) == 1
    assert writer_finished.is_set()
    assert transport.writes == ["CLOCKSW OFF"]


def test_close_cannot_interrupt_a_controls_snapshot() -> None:
    transport = BlockingControlsTransport()
    driver = SP30120SweepAnalyzer(transport)

    reader = Thread(target=driver.read_certified_controls)
    reader.start()
    assert transport.snapshot_entered.wait(timeout=1)

    closer = Thread(target=driver.close)
    closer.start()
    closer.join(timeout=0.1)
    assert closer.is_alive()
    assert transport.closed is False

    transport.release_snapshot.set()
    reader.join(timeout=2)
    closer.join(timeout=2)

    assert not reader.is_alive()
    assert not closer.is_alive()
    assert transport.closed is True


@pytest.mark.parametrize(
    ("response", "code", "message"),
    [
        ("ERRORNo00", "ERRORNo00", "command format error"),
        ("ERRORNo01", "ERRORNo01", "current state"),
        ("ERRORNo02", "ERRORNo02", "out of range"),
        ("ERRORNo03", "ERRORNo03", "zero value"),
        ("ERRORNo04", "ERRORNo04", "negative value"),
        ("ERRORNo05", "ERRORNo05", "floating-point format"),
        ("ERRORNo06", "ERRORNo06", "leading zero"),
        ("ERRORNo07", "ERRORNo07", "no valid input data"),
        ("errorno08", "ERRORNo08", "too many digits"),
        ("Error", "undocumented_error", "undocumented Error"),
    ],
)
def test_private_errors_are_structured_deterministic_and_never_retried(
    response: str, code: str, message: str
) -> None:
    command = "RFSTAT?"
    transport = FakeTransport({command: response})

    with pytest.raises(SP30120ProtocolError, match=message) as caught:
        SP30120SweepAnalyzer(transport).read_scalar_status()

    assert isinstance(caught.value, InstrumentError)
    assert caught.value.code == code
    assert caught.value.command == command
    assert caught.value.retryable is False
    assert transport.queries.count(command) == 1
    assert transport.writes == []


@pytest.mark.parametrize(
    ("responses", "message"),
    [
        ({"RFSTAT?": "MAYBE"}, "RFSTAT"),
        ({"CENS?": "1,2,3"}, "pair response"),
        ({"STAS?": "2.0e6,1.0e6"}, "start frequency"),
        ({"SWET?": "nan"}, "finite and > 0"),
        ({"INPZ?": "100"}, "unsupported.*impedance"),
    ],
)
def test_invalid_or_unverified_status_shapes_fail_closed(
    responses: dict[str, str], message: str
) -> None:
    with pytest.raises((DataError, ValueError), match=message):
        SP30120SweepAnalyzer(FakeTransport(responses)).read_scalar_status()


def test_family_identity_does_not_claim_model_from_incompatible_response() -> None:
    private_token = "SERIAL-DO-NOT-LOG"
    driver = SP30120SweepAnalyzer(
        FakeTransport({"*IDN?": f"SHENGPU,SP30120A,{private_token},FW"})
    )

    with pytest.raises(DataError, match="identity mismatch") as caught:
        driver.idn()

    assert private_token not in str(caught.value)
    assert "SP30120A" not in str(caught.value)


def test_family_identity_tolerates_only_formatting_variations() -> None:
    driver = SP30120SweepAnalyzer(
        FakeTransport({"*IDN?": "  shengpu   sp3000 series digital sweeper.  "})
    )

    assert driver.idn() == "shengpu   sp3000 series digital sweeper."


def test_documented_high_impedance_status_is_preserved_without_guessing_ohms() -> None:
    status = SP30120SweepAnalyzer(FakeTransport({"INPZ?": "HIGHZ"})).read_scalar_status()

    assert status.input_impedance == "highz"


def test_unverified_and_write_paths_are_not_exposed() -> None:
    driver = SP30120SweepAnalyzer(FakeTransport())

    assert not hasattr(driver, "get_snapshot")
    assert not hasattr(driver, "fetch_frequency_response")
    assert not hasattr(driver, "apply_sweep_plan")
    assert not hasattr(driver, "trigger_single")
    assert not hasattr(driver, "set_source_output")
    assert not hasattr(driver, "read_markers")
    assert not hasattr(driver, "read_measurements")
    assert not hasattr(driver, "write_scpi")


def test_close_is_forwarded() -> None:
    transport = FakeTransport()
    SP30120SweepAnalyzer(transport).close()
    assert transport.closed
