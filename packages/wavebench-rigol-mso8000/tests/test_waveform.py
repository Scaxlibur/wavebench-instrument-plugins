from __future__ import annotations

from dataclasses import asdict, replace
from threading import Event, Thread
from typing import Any

import numpy as np
import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError, OperationTimeout
from wavebench.instruments.models import ScopeDerivedWaveformMetadata
from wavebench.services.scope_waveform_executor import BoundedWaveformExecutor
from wavebench.transport.contracts import (
    BinaryQueryResult,
    BinaryResponseFraming,
    ReplayPolicy,
)
from wavebench.transport.guarded import GuardedAuditedTransport
from wavebench.transport.session import InstrumentSessionState, SessionHealth
from wavebench_rigol_mso8000 import descriptor as plugin_descriptor
from wavebench_rigol_mso8000.driver import MSO8104Scope, WaveformTransferState
from wavebench_rigol_mso8000.parsers import parse_rigol_waveform_preamble


def _initial_state() -> WaveformTransferState:
    return WaveformTransferState(
        source="CHAN3",
        mode="RAW",
        data_format="WORD",
        points=4096,
        start=101,
        stop=4096,
    )


def _capture_initial_state() -> WaveformTransferState:
    return replace(_initial_state(), data_format="BYTE")


def _normal_preamble(*, points: int = 1000) -> str:
    return f"0,0,{points},1,0.5,-1,1,0.25,10,128"


def _normal_payload(*, points: int = 1000) -> bytes:
    return bytes(128 + index % 4 for index in range(points))


def _long_preamble(*, type_code: int, points: int, x_increment: float = 0.5) -> str:
    return f"0,{type_code},{points},1,{x_increment},-1,1,0.25,10,128"


class WaveformTransport:
    resource = "TCPIP::192.0.2.10::INSTR"
    _wavebench_binary_budget_parameters = True

    def __init__(
        self,
        *,
        state: WaveformTransferState | None = None,
        preamble: str | None = None,
        payload: bytes | None = None,
    ) -> None:
        self.state = asdict(state or _initial_state())
        self.preamble = preamble or _normal_preamble()
        self.payload = payload if payload is not None else _normal_payload()
        self.preambles: dict[str, str] = {}
        self.payloads: dict[str, bytes] = {}
        self.displayed = {channel: True for channel in range(1, 5)}
        self.math_display_responses = {index: "1" for index in range(1, 5)}
        self.timebase_mode = "MAIN"
        self.timebase_scale_s_per_div = 1e-3
        self.timebase_offset_s = 0.0
        self.channel_scales = {channel: 0.5 for channel in range(1, 5)}
        self.channel_offsets = {channel: 0.0 for channel in range(1, 5)}
        self.acquisition_type = "NORM"
        self.trigger_sweep = "NORM"
        self.memory_depth = 10_000
        self.trigger_statuses = ["STOP"]
        self.opc_responses = ["1"]
        self.error_records = ['0,"No error"']
        self.error_query_replays: list[ReplayPolicy] = []
        self.events: list[tuple[str, str]] = []
        self.fail_writes: set[str] = set()
        self.binary_error: Exception | None = None
        self.binary_payload_overrides: dict[int, bytes] = {}
        self.binary_entered: Event | None = None
        self.binary_release: Event | None = None
        self.binary_calls = 0
        self.binary_requests: list[
            tuple[str, BinaryResponseFraming, int, ReplayPolicy, bytes, int]
        ] = []
        self.close_calls = 0

    def record_event(self, direction: str, text: str) -> None:
        return None

    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        self.events.append(("query", command))
        if command == "*IDN?":
            return "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000,00.02.02"
        for channel in range(1, 5):
            if command == f":CHANnel{channel}:DISPlay?":
                return "1" if self.displayed[channel] else "0"
            if command == f":CHANnel{channel}:SCALe?":
                return str(self.channel_scales[channel])
            if command == f":CHANnel{channel}:OFFSet?":
                return str(self.channel_offsets[channel])
        for math_index in range(1, 5):
            if command == f":MATH{math_index}:DISPlay?":
                return self.math_display_responses[math_index]
        queries = {
            ":WAVeform:SOURce?": "source",
            ":WAVeform:MODE?": "mode",
            ":WAVeform:FORMat?": "data_format",
            ":WAVeform:POINts?": "points",
            ":WAVeform:STARt?": "start",
            ":WAVeform:STOP?": "stop",
        }
        if command in queries:
            return str(self.state[queries[command]])
        if command == ":TIMebase:MODE?":
            return self.timebase_mode
        if command == ":TIMebase:MAIN:SCALe?":
            return str(self.timebase_scale_s_per_div)
        if command == ":TIMebase:MAIN:OFFSet?":
            return str(self.timebase_offset_s)
        if command == ":ACQuire:TYPE?":
            return self.acquisition_type
        if command == ":TRIGger:SWEep?":
            return self.trigger_sweep
        if command == ":ACQuire:MDEPth?":
            return str(self.memory_depth)
        if command == ":SYSTem:ERRor?":
            self.error_query_replays.append(replay)
            if len(self.error_records) > 1:
                return self.error_records.pop(0)
            return self.error_records[0]
        if command == "*OPC?":
            if len(self.opc_responses) > 1:
                return self.opc_responses.pop(0)
            return self.opc_responses[0]
        if command == ":TRIGger:STATus?":
            if len(self.trigger_statuses) > 1:
                return self.trigger_statuses.pop(0)
            return self.trigger_statuses[0]
        if command == ":WAVeform:PREamble?":
            return self.preambles.get(str(self.state["source"]), self.preamble)
        raise AssertionError(f"unexpected text query: {command}")

    def write(self, command: str) -> None:
        self.events.append(("write", command))
        if command == ":SINGle":
            self.trigger_sweep = "SING"
            if command in self.fail_writes:
                self.fail_writes.remove(command)
                raise InstrumentError(f"injected ambiguous write: {command}")
            return
        if command == ":STOP":
            self.trigger_statuses = ["STOP"]
        elif command == ":RUN":
            self.trigger_statuses = ["RUN"]
        elif command.startswith(":TRIGger:SWEep "):
            self.trigger_sweep = {
                "AUTO": "AUTO",
                "NORMal": "NORM",
                "SINGle": "SING",
            }[command.removeprefix(":TRIGger:SWEep ")]
        elif command.startswith(":ACQuire:TYPE "):
            self.acquisition_type = {
                "NORMal": "NORM",
                "PEAK": "PEAK",
                "AVERages": "AVER",
                "HRESolution": "HRES",
            }[command.removeprefix(":ACQuire:TYPE ")]
        elif command == ":TIMebase:MODE MAIN":
            self.timebase_mode = "MAIN"
        elif command.startswith(":TIMebase:MAIN:SCALe "):
            self.timebase_scale_s_per_div = float(
                command.removeprefix(":TIMebase:MAIN:SCALe ")
            )
        elif command.startswith(":TIMebase:MAIN:OFFSet "):
            self.timebase_offset_s = float(
                command.removeprefix(":TIMebase:MAIN:OFFSet ")
            )
        else:
            for channel in range(1, 5):
                display_prefix = f":CHANnel{channel}:DISPlay "
                scale_prefix = f":CHANnel{channel}:SCALe "
                offset_prefix = f":CHANnel{channel}:OFFSet "
                if command.startswith(display_prefix):
                    self.displayed[channel] = command.removeprefix(display_prefix) == "ON"
                    break
                if command.startswith(scale_prefix):
                    self.channel_scales[channel] = float(command.removeprefix(scale_prefix))
                    break
                if command.startswith(offset_prefix):
                    self.channel_offsets[channel] = float(command.removeprefix(offset_prefix))
                    break
            else:
                prefixes = {
                    ":WAVeform:SOURce ": "source",
                    ":WAVeform:MODE ": "mode",
                    ":WAVeform:FORMat ": "data_format",
                    ":WAVeform:POINts ": "points",
                    ":WAVeform:STARt ": "start",
                    ":WAVeform:STOP ": "stop",
                }
                for prefix, field_name in prefixes.items():
                    if command.startswith(prefix):
                        value: str | int = command.removeprefix(prefix)
                        if field_name in {"points", "start", "stop"}:
                            value = int(value)
                        self.state[field_name] = value
                        break
                else:
                    raise AssertionError(f"unexpected write: {command}")
        if command in self.fail_writes:
            self.fail_writes.remove(command)
            raise InstrumentError(f"injected ambiguous write: {command}")

    def _next_binary_payload(self, command: str, *, event_name: str) -> bytes:
        self.events.append((event_name, command))
        self.binary_calls += 1
        if self.binary_calls == 1 and self.binary_entered is not None:
            self.binary_entered.set()
            assert self.binary_release is not None
            if not self.binary_release.wait(timeout=5):
                raise AssertionError("binary release was not signaled")
        if self.binary_error is not None:
            raise self.binary_error
        if self.binary_calls in self.binary_payload_overrides:
            return self.binary_payload_overrides[self.binary_calls]
        payload = self.payloads.get(str(self.state["source"]), self.payload)
        start = int(self.state["start"])
        stop = int(self.state["stop"])
        return payload[start - 1 : stop]

    def query_bin_block(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> bytes:
        return self._next_binary_payload(command, event_name="query_bin_block")

    def query_binary(
        self,
        command: str,
        *,
        framing: BinaryResponseFraming,
        max_bytes: int,
        timeout_ms: int | None = None,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
        _transport_trailing: bytes = b"",
        _resynchronization_max_bytes: int = 0,
    ) -> BinaryQueryResult:
        self.binary_requests.append(
            (
                command,
                framing,
                max_bytes,
                replay,
                _transport_trailing,
                _resynchronization_max_bytes,
            )
        )
        assert framing is BinaryResponseFraming.DEFINITE_BLOCK
        assert replay is ReplayPolicy.NO_REPLAY
        payload = self._next_binary_payload(command, event_name="query_binary")
        assert len(payload) <= max_bytes
        header_bytes = len(f"#{len(str(len(payload)))}{len(payload)}")
        return BinaryQueryResult(
            data=payload,
            framing=framing,
            declared_length=len(payload),
            framing_header_bytes=header_bytes,
            consumed_bytes=header_bytes + len(payload) + len(_transport_trailing),
            transport_trailing_bytes=_transport_trailing,
        )

    def query_float_list(
        self,
        command: str,
        *,
        timeout_ms: int | None = None,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> list[float]:
        raise AssertionError(f"unexpected float query: {command}")

    def query_opc(
        self,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        raise AssertionError("unexpected OPC query")

    def write_bytes(self, command: bytes) -> None:
        raise AssertionError("unexpected binary write")

    def close(self) -> None:
        self.close_calls += 1


def test_fetch_normal_byte_waveform_restores_complete_transfer_state() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    scope = MSO8104Scope(transport=transport)

    waveform = scope.fetch_waveform(channel=2, points=" def\n", check_errors=False)

    assert waveform.channel == 2
    assert waveform.header.points == 1000
    assert waveform.header.x_start == pytest.approx(-1.5)
    assert waveform.header.x_stop == pytest.approx(498.0)
    np.testing.assert_allclose(waveform.voltages_v[:4], [-2.5, -2.25, -2.0, -1.75])
    assert waveform.voltages_v.flags.writeable is False
    assert transport.state == asdict(previous)
    assert transport.events[0] == ("query", ":CHANnel2:DISPlay?")
    assert transport.events.count(("query_bin_block", ":WAVeform:DATA?")) == 1
    writes = [command for direction, command in transport.events if direction == "write"]
    assert writes[:6] == [
        ":WAVeform:SOURce CHAN2",
        ":WAVeform:MODE NORM",
        ":WAVeform:FORMat BYTE",
        ":WAVeform:POINts 1000",
        ":WAVeform:STARt 1",
        ":WAVeform:STOP 1000",
    ]
    assert not any(
        command.upper() in {":STOP", ":SINGLE", ":AUTOSCALE"} for command in writes
    )
    assert scope.waveform_writes_blocked is False


def test_math_metadata_uses_normal_byte_preamble_and_restores_state() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.preambles["MATH2"] = _normal_preamble()

    metadata = MSO8104Scope(transport=transport).get_math_waveform_metadata(2)

    assert metadata == ScopeDerivedWaveformMetadata(
        source_kind="math",
        index=2,
        source_catalog=None,
        x_start=-1.5,
        x_stop=498.0,
        points=1000,
        values_per_sample=None,
        x_increment=0.5,
        x_origin=-1.0,
        y_increment=0.25,
        y_origin=10.0,
        y_resolution_bits=8,
    )
    assert transport.state == asdict(previous)
    assert transport.binary_calls == 0
    writes = [command for direction, command in transport.events if direction == "write"]
    assert writes[:6] == [
        ":WAVeform:MODE NORM",
        ":WAVeform:SOURce MATH2",
        ":WAVeform:FORMat BYTE",
        ":WAVeform:POINts 1000",
        ":WAVeform:STARt 1",
        ":WAVeform:STOP 1000",
    ]


def test_math_metadata_has_exact_transfer_transaction_without_data_or_acquisition_io() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.preambles["MATH1"] = _normal_preamble()

    MSO8104Scope(transport=transport).get_math_waveform_metadata(1)

    snapshot_queries = [
        ("query", ":WAVeform:SOURce?"),
        ("query", ":WAVeform:MODE?"),
        ("query", ":WAVeform:FORMat?"),
        ("query", ":WAVeform:POINts?"),
        ("query", ":WAVeform:STARt?"),
        ("query", ":WAVeform:STOP?"),
    ]
    assert transport.events == [
        ("query", ":MATH1:DISPlay?"),
        ("query", ":TIMebase:MODE?"),
        *snapshot_queries,
        ("write", ":WAVeform:MODE NORM"),
        ("query", ":WAVeform:MODE?"),
        ("write", ":WAVeform:SOURce MATH1"),
        ("query", ":WAVeform:SOURce?"),
        ("write", ":WAVeform:FORMat BYTE"),
        ("query", ":WAVeform:FORMat?"),
        ("write", ":WAVeform:POINts 1000"),
        ("query", ":WAVeform:POINts?"),
        ("write", ":WAVeform:STARt 1"),
        ("query", ":WAVeform:STARt?"),
        ("write", ":WAVeform:STOP 1000"),
        ("query", ":WAVeform:STOP?"),
        *snapshot_queries,
        ("query", ":WAVeform:PREamble?"),
        ("write", f":WAVeform:SOURce {previous.source}"),
        ("query", ":WAVeform:SOURce?"),
        ("write", f":WAVeform:MODE {previous.mode}"),
        ("query", ":WAVeform:MODE?"),
        ("write", f":WAVeform:FORMat {previous.data_format}"),
        ("query", ":WAVeform:FORMat?"),
        ("write", f":WAVeform:POINts {previous.points}"),
        ("query", ":WAVeform:POINts?"),
        ("write", f":WAVeform:STOP {previous.stop}"),
        ("query", ":WAVeform:STOP?"),
        ("write", f":WAVeform:STARt {previous.start}"),
        ("query", ":WAVeform:STARt?"),
        *snapshot_queries,
    ]
    assert transport.binary_calls == 0
    assert all(
        command not in {":RUN", ":STOP", ":SINGle", ":AUToscale"}
        for direction, command in transport.events
        if direction == "write"
    )


@pytest.mark.parametrize("math_index", [0, 5, True, 1.0, "1"])
def test_math_metadata_rejects_invalid_index_without_io(math_index: object) -> None:
    transport = WaveformTransport()

    with pytest.raises(DataError, match="math waveform index"):
        MSO8104Scope(transport=transport).get_math_waveform_metadata(
            math_index,  # type: ignore[arg-type]
        )

    assert transport.events == []


@pytest.mark.parametrize("display_response", ["0", "OFF", "", "2"])
def test_math_metadata_refuses_hidden_or_invalid_math_without_writes(
    display_response: str,
) -> None:
    transport = WaveformTransport()
    transport.math_display_responses[3] = display_response

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_math_waveform_metadata(3)

    assert transport.events == [("query", ":MATH3:DISPlay?")]
    assert transport.state == asdict(_initial_state())


@pytest.mark.parametrize("mode", ["XY", "ROLL", "BROKEN"])
def test_math_metadata_refuses_non_main_timebase_without_writes(mode: str) -> None:
    transport = WaveformTransport()
    transport.timebase_mode = mode

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_math_waveform_metadata(2)

    assert transport.events == [
        ("query", ":MATH2:DISPlay?"),
        ("query", ":TIMebase:MODE?"),
    ]
    assert transport.state == asdict(_initial_state())


@pytest.mark.parametrize(
    ("preamble", "message"),
    [
        ("1,0,1000,1,0.5,-1,1,0.25,10,128", "BYTE"),
        ("0,1,1000,1,0.5,-1,1,0.25,10,128", "type code 0"),
        ("0,0,999,1,0.5,-1,1,0.25,10,128", "point count"),
        ("0,0,1000,1,1e308,1e308,0,0.25,10,128", "X axis"),
    ],
)
def test_math_metadata_invalid_preamble_restores_without_latching(
    preamble: str,
    message: str,
) -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.preambles["MATH1"] = preamble
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(DataError, match=message):
        scope.get_math_waveform_metadata(1)

    assert transport.state == asdict(previous)
    assert transport.binary_calls == 0
    assert scope.waveform_writes_blocked is False


def test_math_metadata_ambiguous_setup_latches_waveform_domain() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.fail_writes.add(":WAVeform:SOURce MATH4")
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="writes are blocked"):
        scope.get_math_waveform_metadata(4)

    assert transport.state == asdict(previous)
    assert scope.waveform_writes_blocked is True
    event_count = len(transport.events)
    with pytest.raises(InstrumentError, match="close and reopen"):
        scope.get_math_waveform_metadata(4)
    assert len(transport.events) == event_count


@pytest.mark.parametrize(
    "kwargs",
    [
        {"channel": 0, "points": "DEF", "check_errors": False},
        {"channel": 1, "points": "ALL", "check_errors": False},
        {"channel": 1, "points": 1000, "check_errors": False},
        {"channel": 1, "points": "DEF", "check_errors": 0},
        {"channel": 1, "points": "DEF", "check_errors": True},
    ],
)
def test_fetch_rejects_unsupported_arguments_without_io(kwargs: dict[str, Any]) -> None:
    transport = WaveformTransport()
    scope = MSO8104Scope(transport=transport)

    with pytest.raises((ConfigError, DataError)):
        scope.fetch_waveform(**kwargs)

    assert transport.events == []


def test_fetch_refuses_hidden_channel_without_mutation() -> None:
    transport = WaveformTransport()
    transport.displayed[4] = False

    with pytest.raises(ConfigError, match="CH4 is not displayed"):
        MSO8104Scope(transport=transport).fetch_waveform(
            channel=4,
            points="DEF",
            check_errors=False,
        )

    assert transport.events == [("query", ":CHANnel4:DISPlay?")]
    assert transport.state == asdict(_initial_state())


@pytest.mark.parametrize(
    ("preamble", "message"),
    [
        ("0,0,1000,1,1,2,3,4,5", "preamble"),
        ("0.0,0,1000,1,1,2,3,4,5,6", "format code"),
        ("1,0,1000,1,1,2,3,4,5,6", "BYTE"),
        ("0,1,1000,1,1,2,3,4,5,6", "type code 0"),
        ("0,0,1e3,1,1,2,3,4,5,6", "points"),
        ("0,0,1001,1,1,2,3,4,5,6", "points"),
        ("0,0,1000,0,1,2,3,4,5,6", "count"),
        ("0,0,1000,1,nan,2,3,4,5,6", "non-finite"),
        ("0,0,1000,1,0,2,3,4,5,6", "X increment"),
        ("0,0,1000,1,1,2,3,inf,5,6", "non-finite"),
        ("0,0,1000,1,1,2,3,0,5,6", "Y increment"),
    ],
)
def test_preamble_parser_fails_closed(preamble: str, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_rigol_waveform_preamble(preamble)


def test_payload_mismatch_restores_state_without_latching() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous, payload=b"short")
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(DataError, match="payload length mismatch"):
        scope.fetch_waveform(channel=1, points="DEF", check_errors=False)

    assert transport.state == asdict(previous)
    assert transport.binary_calls == 1
    assert scope.waveform_writes_blocked is False


@pytest.mark.parametrize(
    ("preamble", "message"),
    [
        ("0,0,1000,1,1e308,1e308,0,1,0,0", "X axis"),
        ("0,0,1000,1,1,0,0,1e308,-1e308,0", "voltage conversion"),
    ],
)
def test_derived_non_finite_waveform_values_fail_and_restore(
    preamble: str,
    message: str,
) -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous, preamble=preamble)
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(DataError, match=message):
        scope.fetch_waveform(channel=1, points="DEF", check_errors=False)

    assert transport.state == asdict(previous)
    assert scope.waveform_writes_blocked is False


@pytest.mark.parametrize(
    ("field_name", "invalid"),
    [
        ("source", "CHAN5"),
        ("mode", "NORMAL"),
        ("data_format", "ASCII"),
        ("points", "1e3"),
        ("start", "0"),
        ("stop", "500000001"),
    ],
)
def test_invalid_transfer_snapshot_fails_before_first_write(
    field_name: str,
    invalid: str,
) -> None:
    transport = WaveformTransport()
    transport.state[field_name] = invalid

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).fetch_waveform(
            channel=1,
            points="DEF",
            check_errors=False,
        )

    assert all(direction != "write" for direction, _ in transport.events)


def test_binary_failure_is_not_replayed_and_state_is_restored() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.binary_error = InstrumentError("injected binary failure")
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="injected binary failure"):
        scope.fetch_waveform(channel=1, points="DEF", check_errors=False)

    assert transport.binary_calls == 1
    assert transport.state == asdict(previous)
    assert scope.waveform_writes_blocked is False


def test_ambiguous_setup_write_restores_state_and_latches_future_writes() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.fail_writes.add(":WAVeform:MODE NORM")
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="writes are blocked"):
        scope.fetch_waveform(channel=1, points="DEF", check_errors=False)

    assert transport.state == asdict(previous)
    assert scope.waveform_writes_blocked is True
    event_count = len(transport.events)
    with pytest.raises(InstrumentError, match="close and reopen"):
        scope.fetch_waveform(channel=1, points="DEF", check_errors=False)
    assert len(transport.events) == event_count


def test_restore_failure_latches_and_refuses_to_return_waveform() -> None:
    transport = WaveformTransport()
    transport.fail_writes.add(":WAVeform:SOURce CHAN3")
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="state restoration failed") as error:
        scope.fetch_waveform(channel=2, points="DEF", check_errors=False)

    assert ":WAVeform:SOURce CHAN3" in str(error.value)
    assert transport.binary_calls == 1
    assert scope.waveform_writes_blocked is True
    event_count = len(transport.events)
    with pytest.raises(InstrumentError, match="close and reopen"):
        scope.fetch_waveform(channel=2, points="DEF", check_errors=False)
    assert len(transport.events) == event_count


def test_two_fetch_transactions_do_not_interleave() -> None:
    transport = WaveformTransport()
    transport.binary_entered = Event()
    transport.binary_release = Event()
    scope = MSO8104Scope(transport=transport)
    second_attempted = Event()
    results: list[int] = []
    errors: list[BaseException] = []

    def fetch(channel: int, *, attempted: Event | None = None) -> None:
        if attempted is not None:
            attempted.set()
        try:
            results.append(
                scope.fetch_waveform(
                    channel=channel,
                    points="DEF",
                    check_errors=False,
                ).channel
            )
        except BaseException as exc:
            errors.append(exc)

    first = Thread(target=fetch, args=(1,))
    first.start()
    assert transport.binary_entered.wait(timeout=5)
    second = Thread(target=fetch, args=(2,), kwargs={"attempted": second_attempted})
    second.start()
    assert second_attempted.wait(timeout=5)
    assert ("query", ":CHANnel2:DISPlay?") not in transport.events

    transport.binary_release.set()
    first.join(timeout=5)
    second.join(timeout=5)

    assert not first.is_alive()
    assert not second.is_alive()
    assert errors == []
    assert sorted(results) == [1, 2]
    assert transport.binary_calls == 2
    assert transport.state == asdict(_initial_state())


def test_multi_channel_capture_uses_one_single_and_stop_poll() -> None:
    transport = WaveformTransport()
    transport.trigger_statuses = ["WAIT", "RUN", "TD", "STOP"]
    scope = MSO8104Scope(
        transport=transport,
        trigger_poll_interval_s=0.0,
        _sleep=lambda _: None,
    )
    callbacks: list[tuple[str, int]] = []

    waveforms = scope.capture_waveforms(
        channels=[1, 2],
        points="DEF",
        check_errors=False,
        on_channel_start=lambda channel: callbacks.append(("start", int(channel))),
        on_waveform=lambda channel, _: callbacks.append(("waveform", channel)),
    )

    assert list(waveforms) == [1, 2]
    assert callbacks == [
        ("start", 1),
        ("waveform", 1),
        ("start", 2),
        ("waveform", 2),
    ]
    assert transport.events.count(("write", ":SINGle")) == 1
    assert transport.events.count(("query", ":TRIGger:STATus?")) == 4
    assert transport.binary_calls == 2
    assert transport.state == asdict(_initial_state())
    acquisition_writes = [
        command
        for direction, command in transport.events
        if direction == "write" and command in {":SINGle", ":RUN", ":STOP"}
    ]
    assert acquisition_writes == [":SINGle"]
    assert scope.acquisition_writes_blocked is False


def test_single_channel_capture_delegates_to_one_multi_capture() -> None:
    transport = WaveformTransport()
    scope = MSO8104Scope(transport=transport)

    waveform = scope.capture_waveform(
        channel=3,
        points="DEF",
        check_errors=False,
    )

    assert waveform.channel == 3
    assert transport.events.count(("write", ":SINGle")) == 1
    assert transport.binary_calls == 1


@pytest.mark.parametrize(
    "kwargs",
    [
        {"channels": [], "points": "DEF", "check_errors": False},
        {"channels": (1,), "points": "DEF", "check_errors": False},
        {"channels": [1, 1], "points": "DEF", "check_errors": False},
        {"channels": [5], "points": "DEF", "check_errors": False},
        {"channels": [1], "points": "ALL", "check_errors": False},
        {"channels": [1], "points": "DEF", "check_errors": True},
        {
            "channels": [1],
            "points": "DEF",
            "check_errors": False,
            "time_range_s": 1.0,
        },
        {
            "channels": [1],
            "points": "DEF",
            "check_errors": False,
            "vertical_scale_v_per_div": 1.0,
        },
        {
            "channels": [1],
            "points": "DEF",
            "check_errors": False,
            "on_channel_start": "not-callable",
        },
        {
            "channels": [1],
            "points": "DEF",
            "check_errors": False,
            "on_waveform": "not-callable",
        },
    ],
)
def test_capture_rejects_unsupported_arguments_without_io(kwargs: dict[str, Any]) -> None:
    transport = WaveformTransport()

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).capture_waveforms(**kwargs)

    assert transport.events == []


def test_capture_preflights_every_display_before_single() -> None:
    transport = WaveformTransport()
    transport.displayed[2] = False

    with pytest.raises(ConfigError, match="CH2 is not displayed"):
        MSO8104Scope(transport=transport).capture_waveforms(
            channels=[1, 2, 3],
            points="DEF",
            check_errors=False,
        )

    assert transport.events == [
        ("query", ":CHANnel1:DISPlay?"),
        ("query", ":CHANnel2:DISPlay?"),
    ]


@pytest.mark.parametrize("mode", ["XY", "ROLL", "BROKEN"])
def test_capture_refuses_non_main_or_unknown_timebase_without_single(mode: str) -> None:
    transport = WaveformTransport()
    transport.timebase_mode = mode

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).capture_waveforms(
            channels=[1, 2],
            points="DEF",
            check_errors=False,
        )

    assert all(event != ("write", ":SINGle") for event in transport.events)


def test_single_timeout_does_not_force_or_retry_and_latches_acquisition() -> None:
    transport = WaveformTransport()
    transport.trigger_statuses = ["WAIT"]
    clock_values = iter((0.0, 1.0))
    scope = MSO8104Scope(
        transport=transport,
        acquisition_timeout_s=0.1,
        trigger_poll_interval_s=0.0,
        _clock=lambda: next(clock_values),
        _sleep=lambda _: None,
    )

    with pytest.raises(OperationTimeout, match="did not reach STOP"):
        scope.capture_waveforms(
            channels=[1],
            points="DEF",
            check_errors=False,
        )

    assert transport.events.count(("write", ":SINGle")) == 1
    assert transport.events.count(("query", ":TRIGger:STATus?")) == 1
    assert transport.binary_calls == 0
    assert scope.acquisition_writes_blocked is True
    event_count = len(transport.events)
    with pytest.raises(InstrumentError, match="close and reopen"):
        scope.capture_waveforms(
            channels=[1],
            points="DEF",
            check_errors=False,
        )
    assert len(transport.events) == event_count


@pytest.mark.parametrize("failure", ["write", "status"])
def test_uncertain_single_or_status_latches_acquisition(failure: str) -> None:
    transport = WaveformTransport()
    if failure == "write":
        transport.fail_writes.add(":SINGle")
    else:
        transport.trigger_statuses = ["UNKNOWN"]
    scope = MSO8104Scope(transport=transport)

    with pytest.raises(InstrumentError, match="acquisition writes are blocked"):
        scope.capture_waveforms(
            channels=[1],
            points="DEF",
            check_errors=False,
        )

    assert scope.acquisition_writes_blocked is True
    assert transport.binary_calls == 0


def test_multi_channel_axis_mismatch_preserves_first_callback_result() -> None:
    transport = WaveformTransport()
    transport.preambles["CHAN2"] = "0,0,1000,1,0.6,-1,1,0.25,10,128"
    completed: list[int] = []

    with pytest.raises(DataError, match="consistent X axis"):
        MSO8104Scope(transport=transport).capture_waveforms(
            channels=[1, 2, 3],
            points="DEF",
            check_errors=False,
            on_waveform=lambda channel, _: completed.append(channel),
        )

    assert completed == [1]
    assert transport.binary_calls == 2
    assert transport.state == asdict(_initial_state())


def test_callback_failure_stops_later_channels_after_restoration() -> None:
    transport = WaveformTransport()

    def fail_after_first(channel: int, _: object) -> None:
        raise RuntimeError(f"injected callback failure on CH{channel}")

    with pytest.raises(RuntimeError, match="CH1"):
        MSO8104Scope(transport=transport).capture_waveforms(
            channels=[1, 2],
            points="DEF",
            check_errors=False,
            on_waveform=fail_after_first,
        )

    assert transport.binary_calls == 1
    assert transport.state == asdict(_initial_state())


def test_dmax_fetch_requires_stop_and_reads_bounded_chunks() -> None:
    previous = _initial_state()
    transport = WaveformTransport(
        state=previous,
        preamble=_long_preamble(type_code=2, points=5),
        payload=bytes([128, 129, 130, 131, 132]),
    )
    transport.memory_depth = 5
    transport.trigger_statuses = ["STOP"]
    scope = MSO8104Scope(
        transport=transport,
        max_total_waveform_points=10,
        max_byte_points_per_read=2,
    )

    waveform = scope.fetch_waveform(
        channel=1,
        points="dmax",
        check_errors=False,
    )

    assert waveform.header.points == 5
    np.testing.assert_allclose(
        waveform.voltages_v,
        [-2.5, -2.25, -2.0, -1.75, -1.5],
    )
    assert transport.binary_calls == 3
    assert transport.events.count(("query", ":TRIGger:STATus?")) == 1
    assert ("write", ":WAVeform:MODE RAW") in transport.events
    assert transport.state == asdict(previous)


@pytest.mark.parametrize("status", ["WAIT", "RUN", "AUTO", "TD"])
def test_dmax_fetch_refuses_non_stopped_acquisition_without_waveform_writes(
    status: str,
) -> None:
    transport = WaveformTransport(
        preamble=_long_preamble(type_code=2, points=5),
        payload=bytes(range(5)),
    )
    transport.trigger_statuses = [status]

    with pytest.raises(ConfigError, match="already stopped"):
        MSO8104Scope(transport=transport).fetch_waveform(
            channel=1,
            points="DMAX",
            check_errors=False,
        )

    assert all(direction != "write" for direction, _ in transport.events)
    assert transport.binary_calls == 0


def test_max_fetch_keeps_state_dependent_mode_without_forcing_stop() -> None:
    transport = WaveformTransport(
        preamble=_long_preamble(type_code=1, points=3),
        payload=bytes([128, 129, 130]),
    )
    transport.trigger_statuses = ["RUN"]
    scope = MSO8104Scope(
        transport=transport,
        max_total_waveform_points=3,
        max_byte_points_per_read=2,
    )

    waveform = scope.fetch_waveform(channel=2, points="MAX", check_errors=False)

    assert waveform.sample_count == 3
    assert ("write", ":WAVeform:MODE MAX") in transport.events
    assert ("query", ":TRIGger:STATus?") not in transport.events
    assert all(event != ("write", ":STOP") for event in transport.events)
    assert transport.binary_calls == 2


def test_long_preamble_over_total_budget_fails_before_binary_and_restores() -> None:
    previous = _initial_state()
    transport = WaveformTransport(
        state=previous,
        preamble=_long_preamble(type_code=2, points=5),
        payload=bytes(range(5)),
    )
    scope = MSO8104Scope(
        transport=transport,
        max_total_waveform_points=4,
        max_byte_points_per_read=2,
    )

    with pytest.raises(DataError, match="preamble points"):
        scope.fetch_waveform(channel=1, points="DMAX", check_errors=False)

    assert transport.binary_calls == 0
    assert transport.state == asdict(previous)


def test_multi_dmax_total_budget_preserves_completed_callback() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.preambles = {
        "CHAN1": _long_preamble(type_code=2, points=3),
        "CHAN2": _long_preamble(type_code=2, points=3),
    }
    transport.payloads = {
        "CHAN1": bytes([128, 129, 130]),
        "CHAN2": bytes([128, 129, 130]),
    }
    completed: list[int] = []
    scope = MSO8104Scope(
        transport=transport,
        max_total_waveform_points=5,
        max_byte_points_per_read=2,
    )

    with pytest.raises(DataError, match="preamble points"):
        scope.capture_waveforms(
            channels=[1, 2],
            points="DMAX",
            check_errors=False,
            on_waveform=lambda channel, _: completed.append(channel),
        )

    assert completed == [1]
    assert transport.events.count(("write", ":SINGle")) == 1
    assert transport.binary_calls == 2
    assert transport.state == asdict(previous)


def test_long_chunk_mismatch_is_not_replayed_and_restores_state() -> None:
    previous = _initial_state()
    transport = WaveformTransport(
        state=previous,
        preamble=_long_preamble(type_code=2, points=5),
        payload=bytes([128, 129, 130, 131, 132]),
    )
    transport.binary_payload_overrides[2] = b"x"
    scope = MSO8104Scope(
        transport=transport,
        max_total_waveform_points=5,
        max_byte_points_per_read=2,
    )

    with pytest.raises(DataError, match="chunk length mismatch"):
        scope.fetch_waveform(channel=1, points="DMAX", check_errors=False)

    assert transport.binary_calls == 2
    assert transport.state == asdict(previous)
    assert scope.waveform_writes_blocked is False


@pytest.mark.parametrize(
    "kwargs",
    [
        {"max_total_waveform_points": 0},
        {"max_total_waveform_points": 4_000_001},
        {"max_total_waveform_points": True},
        {"max_byte_points_per_read": 0},
        {"max_byte_points_per_read": 250_001},
        {"max_byte_points_per_read": 1.0},
    ],
)
def test_waveform_memory_limits_are_hard_bounded(kwargs: dict[str, Any]) -> None:
    with pytest.raises(DataError):
        MSO8104Scope(transport=WaveformTransport(), **kwargs)


def _bounded_executor(
    transport: WaveformTransport,
    *,
    max_total_waveform_points: int = 4_000_000,
    max_byte_points_per_read: int = 250_000,
) -> tuple[BoundedWaveformExecutor, MSO8104Scope, InstrumentSessionState]:
    session_state = InstrumentSessionState(epoch_id="mso8104-bounded-test")
    guarded = GuardedAuditedTransport(transport, session_state=session_state)
    guarded._mark_bounded_binary_backend_verified()
    scope = MSO8104Scope(
        transport=guarded,
        max_total_waveform_points=max_total_waveform_points,
        max_byte_points_per_read=max_byte_points_per_read,
    )
    return (
        BoundedWaveformExecutor(
            driver=scope,
            descriptor=plugin_descriptor(),
            session_state=session_state,
            connection_timeout_ms=5_000,
            transport=guarded,
        ),
        scope,
        session_state,
    )


def _capture_bounded_executor(
    transport: WaveformTransport,
) -> tuple[BoundedWaveformExecutor, MSO8104Scope, InstrumentSessionState]:
    session_state = InstrumentSessionState(epoch_id="mso8104-capture-candidate-test")
    guarded = GuardedAuditedTransport(transport, session_state=session_state)
    guarded._mark_bounded_binary_backend_verified()
    scope = MSO8104Scope(
        transport=guarded,
        trigger_poll_interval_s=0.0,
        capture_recovery_settle_s=0.0,
    )
    return (
        BoundedWaveformExecutor(
            driver=scope,
            descriptor=plugin_descriptor(),
            session_state=session_state,
            connection_timeout_ms=5_000,
            transport=guarded,
        ),
        scope,
        session_state,
    )


def _capture_state(transport: WaveformTransport) -> tuple[object, ...]:
    return (
        dict(transport.state),
        transport.trigger_sweep,
        transport.acquisition_type,
        transport.timebase_mode,
        transport.timebase_scale_s_per_div,
        transport.timebase_offset_s,
        dict(transport.displayed),
        dict(transport.channel_scales),
        dict(transport.channel_offsets),
    )


def test_bounded_fetch_uses_core_ledger_and_core_owned_recovery() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    executor, scope, session_state = _bounded_executor(transport)

    result = executor.fetch(channel=2, points="DEF", check_errors=False)

    assert result.value.channel == 2
    assert transport.state == asdict(previous)
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 1
    assert transport.events.count(("query_bin_block", ":WAVeform:DATA?")) == 0
    assert transport.binary_requests == [
        (
            ":WAVeform:DATA?",
            BinaryResponseFraming.DEFINITE_BLOCK,
            1000,
            ReplayPolicy.NO_REPLAY,
            b"\n",
            65_536,
        )
    ]
    assert scope.waveform_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY
    assert result.diagnostics["scope_operation"]["binary_budget"]["remaining_query_count"] == 15


def test_bounded_fetch_drains_nonreplayed_errors_before_and_after() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    executor, _, session_state = _bounded_executor(transport)

    result = executor.fetch(channel=2, points="DEF", check_errors=True)

    assert result.value.channel == 2
    assert transport.state == asdict(previous)
    assert transport.events.count(("query", ":SYSTem:ERRor?")) == 2
    assert transport.error_query_replays == [ReplayPolicy.NO_REPLAY, ReplayPolicy.NO_REPLAY]
    assert result.diagnostics["error_check"]["completed_phases"] == ["before", "after"]
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_fetch_rejects_preexisting_error_before_binary_io() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous)
    transport.error_records = ['-222,"Data, out of range"', '0,"No error"']
    executor, _, session_state = _bounded_executor(transport)

    with pytest.raises(InstrumentError, match="instrument error records"):
        executor.fetch(channel=2, points="DEF", check_errors=True)

    assert transport.state == asdict(previous)
    assert transport.binary_calls == 0
    assert transport.events.count(("query", ":SYSTem:ERRor?")) == 2
    assert transport.error_query_replays == [ReplayPolicy.NO_REPLAY, ReplayPolicy.NO_REPLAY]
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_uses_strict_single_and_restores_full_baseline() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    previous = _capture_state(transport)
    executor, scope, session_state = _capture_bounded_executor(transport)

    result = executor.capture_single(
        channel=1,
        points="DEF",
        time_range_s=None,
        vertical_scale_v_per_div=None,
        check_errors=False,
    )

    assert result.value.channel == 1
    assert _capture_state(transport) == previous
    assert transport.trigger_statuses == ["STOP"]
    assert transport.events.count(("write", ":SINGle")) == 1
    single_index = transport.events.index(("write", ":SINGle"))
    assert transport.events[single_index + 1 : single_index + 3] == [
        ("query", ":TRIGger:SWEep?"),
        ("query", ":TRIGger:STATus?"),
    ]
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 1
    assert transport.events.count(("query_bin_block", ":WAVeform:DATA?")) == 0
    assert scope.waveform_writes_blocked is False
    assert scope.acquisition_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_waits_before_recovery_verification() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    sleeps: list[float] = []
    session_state = InstrumentSessionState(epoch_id="mso8104-capture-settle-test")
    guarded = GuardedAuditedTransport(transport, session_state=session_state)
    guarded._mark_bounded_binary_backend_verified()
    scope = MSO8104Scope(
        transport=guarded,
        trigger_poll_interval_s=0.0,
        capture_recovery_settle_s=0.5,
        _sleep=sleeps.append,
    )
    executor = BoundedWaveformExecutor(
        driver=scope,
        descriptor=plugin_descriptor(),
        session_state=session_state,
        connection_timeout_ms=5_000,
        transport=guarded,
    )

    result = executor.capture_single(
        channel=1,
        points="DEF",
        time_range_s=None,
        vertical_scale_v_per_div=None,
        check_errors=False,
    )

    assert result.value.channel == 1
    assert sleeps.count(0.5) == 1
    assert transport.events.count(("query", "*OPC?")) == 1
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_polls_recovery_synchronization_to_opc_ready() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    transport.opc_responses = ["0", "0", "1"]
    sleeps: list[float] = []
    session_state = InstrumentSessionState(epoch_id="mso8104-capture-opc-poll-test")
    guarded = GuardedAuditedTransport(transport, session_state=session_state)
    guarded._mark_bounded_binary_backend_verified()
    scope = MSO8104Scope(
        transport=guarded,
        trigger_poll_interval_s=0.0,
        capture_recovery_settle_s=0.5,
        _sleep=sleeps.append,
    )
    executor = BoundedWaveformExecutor(
        driver=scope,
        descriptor=plugin_descriptor(),
        session_state=session_state,
        connection_timeout_ms=5_000,
        transport=guarded,
    )

    result = executor.capture_single(
        channel=1,
        points="DEF",
        time_range_s=None,
        vertical_scale_v_per_div=None,
        check_errors=False,
    )

    assert result.value.channel == 1
    assert transport.events.count(("query", "*OPC?")) == 3
    assert sleeps.count(0.5) == 3
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_rejects_failed_recovery_synchronization() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    transport.opc_responses = ["0"]
    executor, _, session_state = _capture_bounded_executor(transport)

    with pytest.raises(DataError, match="recovery synchronization"):
        executor.capture_single(
            channel=1,
            points="DEF",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
    )

    assert transport.events.count(("query", "*OPC?")) == 8
    assert session_state.health is SessionHealth.POISONED


def test_bounded_capture_rejects_terminal_stop_after_mode_readback() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "STOP"]
    previous = _capture_state(transport)
    executor, scope, session_state = _capture_bounded_executor(transport)

    with pytest.raises(DataError, match="capture freshness is unproven"):
        executor.capture_single(
            channel=1,
            points="DEF",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
        )

    assert _capture_state(transport) == previous
    assert transport.binary_calls == 0
    single_index = transport.events.index(("write", ":SINGle"))
    assert transport.events[single_index + 1 : single_index + 3] == [
        ("query", ":TRIGger:SWEep?"),
        ("query", ":TRIGger:STATus?"),
    ]
    assert scope.acquisition_writes_blocked is True
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_accepts_td_to_stop_after_single_readback() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "TD", "STOP"]
    previous = _capture_state(transport)
    executor, scope, session_state = _capture_bounded_executor(transport)

    result = executor.capture_single(
        channel=1,
        points="DEF",
        time_range_s=None,
        vertical_scale_v_per_div=None,
        check_errors=False,
    )

    assert result.value.channel == 1
    assert _capture_state(transport) == previous
    assert transport.trigger_statuses == ["STOP"]
    assert transport.events.count(("write", ":SINGle")) == 1
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 1
    assert scope.waveform_writes_blocked is False
    assert scope.acquisition_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_rejects_non_stopped_baseline_before_single() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["WAIT"]
    executor, _, session_state = _capture_bounded_executor(transport)

    with pytest.raises(ConfigError, match="already stopped baseline"):
        executor.capture_single(
            channel=1,
            points="DEF",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
        )

    assert transport.events.count(("write", ":SINGle")) == 0
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_multi_capture_uses_one_single_and_one_baseline() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    previous = _capture_state(transport)
    executor, scope, session_state = _capture_bounded_executor(transport)
    started: list[int | None] = []
    received: list[tuple[int, int]] = []

    result = executor.capture_multiple(
        channels=[1, 2],
        points="DEF",
        time_range_s=None,
        vertical_scale_v_per_div=None,
        check_errors=False,
        on_channel_start=started.append,
        on_waveform=lambda channel, waveform: received.append(
            (channel, waveform.sample_count)
        ),
    )

    assert tuple(result.value) == (1, 2)
    assert started == [1, 2]
    assert received == [(1, 1000), (2, 1000)]
    assert _capture_state(transport) == previous
    assert transport.events.count(("write", ":SINGle")) == 1
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 2
    assert scope.waveform_writes_blocked is False
    assert scope.acquisition_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_rejects_non_byte_transfer_baseline_before_single() -> None:
    transport = WaveformTransport(state=_initial_state())
    executor, _, session_state = _capture_bounded_executor(transport)

    with pytest.raises(ConfigError, match="BYTE waveform-transfer baseline"):
        executor.capture_single(
            channel=1,
            points="DEF",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
        )

    assert transport.events.count(("write", ":SINGle")) == 0
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_rejects_long_point_modes_before_single() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    executor, _, session_state = _capture_bounded_executor(transport)

    with pytest.raises(ConfigError, match="supports only DEF"):
        executor.capture_single(
            channel=1,
            points="DMAX",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
        )

    assert transport.events.count(("write", ":SINGle")) == 0
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_binary_failure_restores_full_baseline() -> None:
    transport = WaveformTransport(state=_capture_initial_state(), payload=b"short")
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    previous = _capture_state(transport)
    executor, scope, session_state = _capture_bounded_executor(transport)

    with pytest.raises(DataError, match="payload length mismatch"):
        executor.capture_single(
            channel=1,
            points="DEF",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
        )

    assert _capture_state(transport) == previous
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 1
    assert scope.waveform_writes_blocked is False
    assert scope.acquisition_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_multi_capture_callback_failure_restores_full_baseline() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    previous = _capture_state(transport)
    executor, scope, session_state = _capture_bounded_executor(transport)

    def fail_callback(channel: int, waveform) -> None:
        del channel, waveform
        raise RuntimeError("injected callback failure")

    with pytest.raises(RuntimeError, match="injected callback failure"):
        executor.capture_multiple(
            channels=[1, 2],
            points="DEF",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
            on_channel_start=None,
            on_waveform=fail_callback,
        )

    assert _capture_state(transport) == previous
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 1
    assert scope.waveform_writes_blocked is False
    assert scope.acquisition_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_capture_restore_failure_rejects_success_value() -> None:
    transport = WaveformTransport(state=_capture_initial_state())
    transport.trigger_statuses = ["STOP", "WAIT", "STOP"]
    transport.fail_writes.add(":ACQuire:TYPE NORMal")
    executor, scope, session_state = _capture_bounded_executor(transport)

    with pytest.raises(InstrumentError, match="restore did not complete"):
        executor.capture_single(
            channel=1,
            points="DEF",
            time_range_s=None,
            vertical_scale_v_per_div=None,
            check_errors=False,
        )

    assert scope.waveform_writes_blocked is True
    assert scope.acquisition_writes_blocked is True
    assert session_state.health is SessionHealth.POISONED


def test_bounded_fetch_data_error_restores_and_verifies_before_raising() -> None:
    previous = _initial_state()
    transport = WaveformTransport(state=previous, payload=b"short")
    executor, scope, session_state = _bounded_executor(transport)

    with pytest.raises(DataError, match="payload length mismatch"):
        executor.fetch(channel=1, points="DEF", check_errors=False)

    assert transport.state == asdict(previous)
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 1
    assert transport.events.count(("query_bin_block", ":WAVeform:DATA?")) == 0
    assert scope.waveform_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_dmax_fetch_uses_core_ledger_and_core_owned_recovery() -> None:
    previous = _initial_state()
    transport = WaveformTransport(
        state=previous,
        preamble=_long_preamble(type_code=2, points=5),
        payload=bytes([128, 129, 130, 131, 132]),
    )
    transport.memory_depth = 5
    transport.trigger_statuses = ["STOP"]
    executor, scope, session_state = _bounded_executor(
        transport,
        max_total_waveform_points=10,
        max_byte_points_per_read=2,
    )

    result = executor.fetch(channel=1, points="DMAX", check_errors=False)

    assert result.value.sample_count == 5
    assert transport.events.count(("query", ":TRIGger:STATus?")) == 1
    assert transport.events.count(("query", ":ACQuire:MDEPth?")) == 1
    assert ("write", ":WAVeform:POINts 5") in transport.events
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 3
    assert transport.events.count(("query_bin_block", ":WAVeform:DATA?")) == 0
    assert [request[2] for request in transport.binary_requests] == [2, 2, 1]
    assert transport.state == asdict(previous)
    assert scope.waveform_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY
    assert result.diagnostics["scope_operation"]["binary_budget"]["remaining_query_count"] == 13


def test_bounded_max_fetch_uses_memory_depth_in_stopped_state() -> None:
    previous = _initial_state()
    transport = WaveformTransport(
        state=previous,
        preamble=_long_preamble(type_code=1, points=5),
        payload=bytes([128, 129, 130, 131, 132]),
    )
    transport.memory_depth = 5
    transport.trigger_statuses = ["STOP"]
    executor, scope, session_state = _bounded_executor(
        transport,
        max_total_waveform_points=10,
        max_byte_points_per_read=2,
    )

    result = executor.fetch(channel=2, points="MAX", check_errors=False)

    assert result.value.sample_count == 5
    assert transport.events.count(("query", ":TRIGger:STATus?")) == 1
    assert transport.events.count(("query", ":ACQuire:MDEPth?")) == 1
    assert ("write", ":WAVeform:POINts 5") in transport.events
    assert ("write", ":STOP") not in transport.events
    assert transport.events.count(("query_binary", ":WAVeform:DATA?")) == 3
    assert transport.events.count(("query_bin_block", ":WAVeform:DATA?")) == 0
    assert [request[2] for request in transport.binary_requests] == [2, 2, 1]
    assert transport.state == asdict(previous)
    assert scope.waveform_writes_blocked is False
    assert session_state.health is SessionHealth.HEALTHY


@pytest.mark.parametrize(
    ("points", "mode"),
    (("MAX", "MAX"), ("DMAX", "RAW")),
)
def test_bounded_long_fetch_refuses_non_stopped_acquisition_before_setup(
    points: str,
    mode: str,
) -> None:
    previous = WaveformTransferState(
        source="CHAN3",
        mode="NORM",
        data_format="WORD",
        points=4096,
        start=101,
        stop=4096,
    )
    transport = WaveformTransport(
        state=previous,
        preamble=_long_preamble(type_code=1 if points == "MAX" else 2, points=5),
        payload=bytes(range(5)),
    )
    transport.trigger_statuses = ["RUN"]
    executor, _, session_state = _bounded_executor(transport)

    with pytest.raises(ConfigError, match="already stopped"):
        executor.fetch(channel=1, points=points, check_errors=False)

    assert ("write", f":WAVeform:MODE {mode}") not in transport.events
    assert transport.binary_calls == 0
    assert transport.state == asdict(previous)
    assert session_state.health is SessionHealth.HEALTHY


def test_bounded_long_fetch_rejects_preamble_that_exceeds_query_capacity() -> None:
    previous = _initial_state()
    transport = WaveformTransport(
        state=previous,
        preamble=_long_preamble(type_code=2, points=17),
        payload=bytes(range(17)),
    )
    transport.trigger_statuses = ["STOP"]
    executor, _, session_state = _bounded_executor(
        transport,
        max_total_waveform_points=1_000,
        max_byte_points_per_read=1,
    )

    with pytest.raises(DataError, match="preamble points"):
        executor.fetch(channel=1, points="DMAX", check_errors=False)

    assert transport.binary_calls == 0
    assert transport.state == asdict(previous)
    assert session_state.health is SessionHealth.HEALTHY
