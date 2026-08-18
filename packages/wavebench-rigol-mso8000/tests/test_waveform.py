from __future__ import annotations

from dataclasses import asdict
from threading import Event, Thread
from typing import Any

import numpy as np
import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
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


def _normal_preamble(*, points: int = 1000) -> str:
    return f"0,0,{points},1,0.5,-1,1,0.25,10,128"


def _normal_payload(*, points: int = 1000) -> bytes:
    return bytes(128 + index % 4 for index in range(points))


class WaveformTransport:
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
        self.displayed = {channel: True for channel in range(1, 5)}
        self.events: list[tuple[str, str]] = []
        self.fail_writes: set[str] = set()
        self.binary_error: Exception | None = None
        self.binary_entered: Event | None = None
        self.binary_release: Event | None = None
        self.binary_calls = 0
        self.close_calls = 0

    def query(self, command: str) -> str:
        self.events.append(("query", command))
        for channel in range(1, 5):
            if command == f":CHANnel{channel}:DISPlay?":
                return "1" if self.displayed[channel] else "0"
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
        if command == ":WAVeform:PREamble?":
            return self.preamble
        raise AssertionError(f"unexpected text query: {command}")

    def write(self, command: str) -> None:
        self.events.append(("write", command))
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

    def query_bin_block(self, command: str) -> bytes:
        self.events.append(("query_bin_block", command))
        self.binary_calls += 1
        if self.binary_calls == 1 and self.binary_entered is not None:
            self.binary_entered.set()
            assert self.binary_release is not None
            if not self.binary_release.wait(timeout=5):
                raise AssertionError("binary release was not signaled")
        if self.binary_error is not None:
            raise self.binary_error
        return self.payload

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


@pytest.mark.parametrize(
    "kwargs",
    [
        {"channel": 0, "points": "DEF", "check_errors": False},
        {"channel": 1, "points": "DMAX", "check_errors": False},
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
        ("0,1,1000,1,1,2,3,4,5,6", "NORMal"),
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

    with pytest.raises(InstrumentError, match="state restoration failed"):
        scope.fetch_waveform(channel=2, points="DEF", check_errors=False)

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
