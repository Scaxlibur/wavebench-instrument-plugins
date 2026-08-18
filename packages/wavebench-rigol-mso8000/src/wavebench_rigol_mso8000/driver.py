from __future__ import annotations

from dataclasses import dataclass, field
import math
from threading import RLock

import numpy as np

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments.models import WaveformData, WaveformHeader
from wavebench.transport.base import InstrumentTransport

from .parsers import (
    normalize_channel_input,
    parse_display_state,
    parse_mso8104_identity,
    parse_positive_integer,
    parse_rigol_waveform_preamble,
    parse_waveform_format,
    parse_waveform_mode,
    parse_waveform_source,
)


_ANALOG_CHANNELS = frozenset({1, 2, 3, 4})
_NORMAL_WAVEFORM_POINTS = 1000
_MAX_WAVEFORM_STATE_POINTS = 500_000_000


@dataclass(frozen=True)
class WaveformTransferState:
    source: str
    mode: str
    data_format: str
    points: int
    start: int
    stop: int


@dataclass
class MSO8104Scope:
    transport: InstrumentTransport
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _waveform_writes_blocked: bool = field(default=False, init=False, repr=False)

    def _require_open(self) -> None:
        if self._closed:
            raise InstrumentError("MSO8104 driver is closed")

    def idn(self) -> str:
        with self._io_lock:
            self._require_open()
            response = self.transport.query("*IDN?").strip()
            parse_mso8104_identity(response)
            return response

    @staticmethod
    def _validate_analog_channel(channel: int) -> None:
        if type(channel) is not int or channel not in _ANALOG_CHANNELS:
            raise DataError("MSO8104 analog channel must be an integer from 1 through 4")

    def channel_coupling(self, channel: int) -> str:
        self._validate_analog_channel(channel)
        with self._io_lock:
            self._require_open()
            coupling = self.transport.query(f":CHANnel{channel}:COUPling?")
            impedance = self.transport.query(f":CHANnel{channel}:IMPedance?")
            return normalize_channel_input(coupling=coupling, impedance=impedance)

    @property
    def waveform_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._waveform_writes_blocked

    def _require_waveform_writes_allowed(self) -> None:
        if self._waveform_writes_blocked:
            raise InstrumentError(
                "MSO8104 waveform transfer writes are blocked after an ambiguous transaction; "
                "close and reopen the instrument session before retrying"
            )

    def _snapshot_waveform_state(self) -> WaveformTransferState:
        source = parse_waveform_source(self.transport.query(":WAVeform:SOURce?"))
        mode = parse_waveform_mode(self.transport.query(":WAVeform:MODE?"))
        data_format = parse_waveform_format(self.transport.query(":WAVeform:FORMat?"))
        points = parse_positive_integer(
            self.transport.query(":WAVeform:POINts?"),
            field="waveform points",
            maximum=_MAX_WAVEFORM_STATE_POINTS,
        )
        start = parse_positive_integer(
            self.transport.query(":WAVeform:STARt?"),
            field="waveform start",
            maximum=_MAX_WAVEFORM_STATE_POINTS,
        )
        stop = parse_positive_integer(
            self.transport.query(":WAVeform:STOP?"),
            field="waveform stop",
            maximum=_MAX_WAVEFORM_STATE_POINTS,
        )
        if start > stop:
            raise DataError(
                f"invalid MSO8104 waveform range in state snapshot: start {start} > stop {stop}"
            )
        return WaveformTransferState(
            source=source,
            mode=mode,
            data_format=data_format,
            points=points,
            start=start,
            stop=stop,
        )

    def _write_and_verify(
        self,
        *,
        command: str,
        query: str,
        expected: str | int,
        parser,
        phase: str,
    ) -> None:
        try:
            self.transport.write(command)
            actual = parser(self.transport.query(query))
            if actual != expected:
                raise DataError(
                    f"MSO8104 waveform {phase} readback mismatch for {query}: "
                    f"expected {expected!r}, got {actual!r}"
                )
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                f"MSO8104 waveform {phase} could not verify {command!r}; "
                "waveform transfer writes are blocked"
            ) from exc

    def _apply_waveform_state(self, state: WaveformTransferState, *, phase: str) -> None:
        fields = [
            (
                f":WAVeform:SOURce {state.source}",
                ":WAVeform:SOURce?",
                state.source,
                parse_waveform_source,
            ),
            (
                f":WAVeform:MODE {state.mode}",
                ":WAVeform:MODE?",
                state.mode,
                parse_waveform_mode,
            ),
            (
                f":WAVeform:FORMat {state.data_format}",
                ":WAVeform:FORMat?",
                state.data_format,
                parse_waveform_format,
            ),
            (
                f":WAVeform:POINts {state.points}",
                ":WAVeform:POINts?",
                state.points,
                lambda value: parse_positive_integer(
                    value,
                    field="waveform points",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
            ),
        ]
        range_fields = [
            (
                f":WAVeform:STOP {state.stop}",
                ":WAVeform:STOP?",
                state.stop,
                lambda value: parse_positive_integer(
                    value,
                    field="waveform stop",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
            ),
            (
                f":WAVeform:STARt {state.start}",
                ":WAVeform:STARt?",
                state.start,
                lambda value: parse_positive_integer(
                    value,
                    field="waveform start",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
            ),
        ]
        if phase == "setup":
            range_fields.reverse()
        for command, query, expected, parser in (*fields, *range_fields):
            self._write_and_verify(
                command=command,
                query=query,
                expected=expected,
                parser=parser,
                phase=phase,
            )
        try:
            actual_state = self._snapshot_waveform_state()
            if actual_state != state:
                raise DataError(
                    f"MSO8104 waveform {phase} final state mismatch: "
                    f"expected {state!r}, got {actual_state!r}"
                )
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                f"MSO8104 waveform {phase} final verification failed; "
                "waveform transfer writes are blocked"
            ) from exc

    def _restore_waveform_state(self, state: WaveformTransferState) -> None:
        try:
            self._apply_waveform_state(state, phase="restore")
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                "MSO8104 waveform transfer state restoration failed; "
                "waveform transfer writes are blocked"
            ) from exc

    def _read_normal_waveform(self, channel: int) -> WaveformData:
        preamble = parse_rigol_waveform_preamble(
            self.transport.query(":WAVeform:PREamble?")
        )
        if preamble.points != _NORMAL_WAVEFORM_POINTS:
            raise DataError(
                "MSO8104 NORMal waveform preamble point count does not match "
                f"the requested {_NORMAL_WAVEFORM_POINTS} points: {preamble.points}"
            )
        payload = self.transport.query_bin_block(":WAVeform:DATA?")
        if len(payload) != preamble.points:
            raise DataError(
                "MSO8104 waveform payload length mismatch: "
                f"expected {preamble.points}, got {len(payload)}"
            )
        voltages = np.frombuffer(payload, dtype=np.uint8).astype(np.float64)
        with np.errstate(over="ignore", invalid="ignore"):
            voltages -= preamble.y_origin + preamble.y_reference
            voltages *= preamble.y_increment
        x_start = preamble.x_origin - preamble.x_reference * preamble.x_increment
        x_stop = x_start + (preamble.points - 1) * preamble.x_increment
        if not math.isfinite(x_start) or not math.isfinite(x_stop):
            raise DataError("MSO8104 waveform X axis is non-finite")
        if not np.all(np.isfinite(voltages)):
            raise DataError("MSO8104 waveform voltage conversion produced non-finite values")
        voltages.setflags(write=False)
        return WaveformData(
            channel=channel,
            header=WaveformHeader(
                x_start=x_start,
                x_stop=x_stop,
                points=preamble.points,
            ),
            voltages_v=voltages,
        )

    def fetch_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
    ) -> WaveformData:
        self._validate_analog_channel(channel)
        if not isinstance(points, str) or points.strip().upper() != "DEF":
            raise DataError("MSO8104 offline-validated fetch supports only points='DEF'")
        if type(check_errors) is not bool:
            raise DataError("MSO8104 check_errors must be a boolean")
        if check_errors:
            raise ConfigError(
                "MSO8104 scope.errors is unavailable until non-replayable text queries exist; "
                "set scope.check_errors=false"
            )
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            displayed = parse_display_state(
                self.transport.query(f":CHANnel{channel}:DISPlay?")
            )
            if not displayed:
                raise ConfigError(
                    f"MSO8104 CH{channel} is not displayed; refusing to change channel state"
                )
            previous = self._snapshot_waveform_state()
            transfer = WaveformTransferState(
                source=f"CHAN{channel}",
                mode="NORM",
                data_format="BYTE",
                points=_NORMAL_WAVEFORM_POINTS,
                start=1,
                stop=_NORMAL_WAVEFORM_POINTS,
            )
            try:
                self._apply_waveform_state(transfer, phase="setup")
                return self._read_normal_waveform(channel)
            finally:
                self._restore_waveform_state(previous)

    def close(self) -> None:
        with self._io_lock:
            if self._closed:
                return
            self._closed = True
            self.transport.close()
