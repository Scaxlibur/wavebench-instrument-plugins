from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
import math
from threading import RLock
import time

import numpy as np

from wavebench.errors import ConfigError, DataError, InstrumentError, OperationTimeout
from wavebench.instruments.models import WaveformData, WaveformHeader
from wavebench.transport.base import InstrumentTransport

from .parsers import (
    normalize_channel_input,
    parse_display_state,
    parse_mso8104_identity,
    parse_positive_integer,
    parse_rigol_waveform_preamble,
    parse_timebase_mode,
    parse_trigger_status,
    parse_waveform_format,
    parse_waveform_mode,
    parse_waveform_source,
)


_ANALOG_CHANNELS = frozenset({1, 2, 3, 4})
_NORMAL_WAVEFORM_POINTS = 1000
_MAX_WAVEFORM_STATE_POINTS = 500_000_000
_HARD_MAX_TOTAL_WAVEFORM_POINTS = 4_000_000
_HARD_MAX_BYTE_POINTS_PER_READ = 250_000
_POINT_MODE_TO_TRANSFER = {
    "DEF": ("NORM", 0),
    "MAX": ("MAX", 1),
    "DMAX": ("RAW", 2),
}


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
    acquisition_timeout_s: float = 30.0
    trigger_poll_interval_s: float = 0.05
    max_total_waveform_points: int = _HARD_MAX_TOTAL_WAVEFORM_POINTS
    max_byte_points_per_read: int = _HARD_MAX_BYTE_POINTS_PER_READ
    _clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    _sleep: Callable[[float], None] = field(default=time.sleep, repr=False)
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _waveform_writes_blocked: bool = field(default=False, init=False, repr=False)
    _acquisition_writes_blocked: bool = field(default=False, init=False, repr=False)

    def __post_init__(self) -> None:
        if not math.isfinite(self.acquisition_timeout_s) or self.acquisition_timeout_s <= 0:
            raise DataError("MSO8104 acquisition timeout must be a finite positive number")
        if (
            not math.isfinite(self.trigger_poll_interval_s)
            or self.trigger_poll_interval_s < 0
        ):
            raise DataError("MSO8104 trigger poll interval must be finite and non-negative")
        if (
            type(self.max_total_waveform_points) is not int
            or not 1
            <= self.max_total_waveform_points
            <= _HARD_MAX_TOTAL_WAVEFORM_POINTS
        ):
            raise DataError(
                "MSO8104 max_total_waveform_points must be an integer from 1 through 4000000"
            )
        if (
            type(self.max_byte_points_per_read) is not int
            or not 1
            <= self.max_byte_points_per_read
            <= _HARD_MAX_BYTE_POINTS_PER_READ
        ):
            raise DataError(
                "MSO8104 max_byte_points_per_read must be an integer from 1 through 250000"
            )

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

    @property
    def acquisition_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._acquisition_writes_blocked

    def _require_waveform_writes_allowed(self) -> None:
        if self._waveform_writes_blocked:
            raise InstrumentError(
                "MSO8104 waveform transfer writes are blocked after an ambiguous transaction; "
                "close and reopen the instrument session before retrying"
            )

    def _require_acquisition_writes_allowed(self) -> None:
        if self._acquisition_writes_blocked:
            raise InstrumentError(
                "MSO8104 acquisition writes are blocked after an uncertain single acquisition; "
                "close and reopen the instrument session before retrying"
            )

    def _require_main_timebase(self) -> None:
        mode = parse_timebase_mode(self.transport.query(":TIMebase:MODE?"))
        if mode != "MAIN":
            raise ConfigError(
                f"MSO8104 waveform operations require MAIN timebase mode, got {mode}"
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

    def _apply_waveform_prefix(self, *, channel: int, mode: str) -> None:
        fields = (
            (
                f":WAVeform:SOURce CHAN{channel}",
                ":WAVeform:SOURce?",
                f"CHAN{channel}",
                parse_waveform_source,
            ),
            (
                f":WAVeform:MODE {mode}",
                ":WAVeform:MODE?",
                mode,
                parse_waveform_mode,
            ),
            (
                ":WAVeform:FORMat BYTE",
                ":WAVeform:FORMat?",
                "BYTE",
                parse_waveform_format,
            ),
        )
        for command, query, expected, parser in fields:
            self._write_and_verify(
                command=command,
                query=query,
                expected=expected,
                parser=parser,
                phase="setup",
            )
        try:
            source = parse_waveform_source(self.transport.query(":WAVeform:SOURce?"))
            actual_mode = parse_waveform_mode(self.transport.query(":WAVeform:MODE?"))
            data_format = parse_waveform_format(self.transport.query(":WAVeform:FORMat?"))
            if (source, actual_mode, data_format) != (f"CHAN{channel}", mode, "BYTE"):
                raise DataError("MSO8104 waveform setup prefix drifted after readback")
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                "MSO8104 waveform setup prefix verification failed; "
                "waveform transfer writes are blocked"
            ) from exc

    @staticmethod
    def _convert_byte_chunk(
        payload: bytes,
        *,
        y_origin: float,
        y_reference: float,
        y_increment: float,
    ) -> np.ndarray:
        voltages = np.frombuffer(payload, dtype=np.uint8).astype(np.float64)
        with np.errstate(over="ignore", invalid="ignore"):
            voltages -= y_origin + y_reference
            voltages *= y_increment
        if not np.all(np.isfinite(voltages)):
            raise DataError("MSO8104 waveform voltage conversion produced non-finite values")
        return voltages

    def _read_byte_waveform(
        self,
        channel: int,
        *,
        point_mode: str,
        remaining_points: int,
    ) -> WaveformData:
        _, expected_type_code = _POINT_MODE_TO_TRANSFER[point_mode]
        maximum_points = min(remaining_points, self.max_total_waveform_points)
        preamble = parse_rigol_waveform_preamble(
            self.transport.query(":WAVeform:PREamble?"),
            expected_type_code=expected_type_code,
            maximum_points=maximum_points,
        )
        if point_mode == "DEF" and preamble.points != _NORMAL_WAVEFORM_POINTS:
            raise DataError(
                "MSO8104 NORMal waveform preamble point count does not match "
                f"the requested {_NORMAL_WAVEFORM_POINTS} points: {preamble.points}"
            )
        if point_mode == "DEF":
            payload = self.transport.query_bin_block(":WAVeform:DATA?")
            if len(payload) != preamble.points:
                raise DataError(
                    "MSO8104 waveform payload length mismatch: "
                    f"expected {preamble.points}, got {len(payload)}"
                )
            voltages = self._convert_byte_chunk(
                payload,
                y_origin=preamble.y_origin,
                y_reference=preamble.y_reference,
                y_increment=preamble.y_increment,
            )
        else:
            voltages = np.empty(preamble.points, dtype=np.float64)
            self._write_and_verify(
                command=":WAVeform:STARt 1",
                query=":WAVeform:STARt?",
                expected=1,
                parser=lambda value: parse_positive_integer(
                    value,
                    field="waveform start",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
                phase="setup",
            )
            for start in range(1, preamble.points + 1, self.max_byte_points_per_read):
                stop = min(
                    preamble.points,
                    start + self.max_byte_points_per_read - 1,
                )
                self._write_and_verify(
                    command=f":WAVeform:STOP {stop}",
                    query=":WAVeform:STOP?",
                    expected=stop,
                    parser=lambda value: parse_positive_integer(
                        value,
                        field="waveform stop",
                        maximum=_MAX_WAVEFORM_STATE_POINTS,
                    ),
                    phase="setup",
                )
                if start != 1:
                    self._write_and_verify(
                        command=f":WAVeform:STARt {start}",
                        query=":WAVeform:STARt?",
                        expected=start,
                        parser=lambda value: parse_positive_integer(
                            value,
                            field="waveform start",
                            maximum=_MAX_WAVEFORM_STATE_POINTS,
                        ),
                        phase="setup",
                    )
                payload = self.transport.query_bin_block(":WAVeform:DATA?")
                expected_length = stop - start + 1
                if len(payload) != expected_length:
                    raise DataError(
                        "MSO8104 waveform chunk length mismatch for "
                        f"points {start}-{stop}: expected {expected_length}, got {len(payload)}"
                    )
                voltages[start - 1 : stop] = self._convert_byte_chunk(
                    payload,
                    y_origin=preamble.y_origin,
                    y_reference=preamble.y_reference,
                    y_increment=preamble.y_increment,
                )
        x_start = preamble.x_origin - preamble.x_reference * preamble.x_increment
        x_stop = x_start + (preamble.points - 1) * preamble.x_increment
        if not math.isfinite(x_start) or not math.isfinite(x_stop):
            raise DataError("MSO8104 waveform X axis is non-finite")
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

    def _read_waveform_transaction(
        self,
        channel: int,
        *,
        point_mode: str,
        remaining_points: int,
    ) -> WaveformData:
        if remaining_points < 1:
            raise DataError("MSO8104 waveform total point budget is exhausted")
        if point_mode == "DEF" and remaining_points < _NORMAL_WAVEFORM_POINTS:
            raise DataError(
                "MSO8104 waveform total point budget is below the 1000-point DEF transfer"
            )
        previous = self._snapshot_waveform_state()
        mode, _ = _POINT_MODE_TO_TRANSFER[point_mode]
        try:
            if point_mode == "DEF":
                transfer = WaveformTransferState(
                    source=f"CHAN{channel}",
                    mode=mode,
                    data_format="BYTE",
                    points=_NORMAL_WAVEFORM_POINTS,
                    start=1,
                    stop=_NORMAL_WAVEFORM_POINTS,
                )
                self._apply_waveform_state(transfer, phase="setup")
            else:
                self._apply_waveform_prefix(channel=channel, mode=mode)
            return self._read_byte_waveform(
                channel,
                point_mode=point_mode,
                remaining_points=remaining_points,
            )
        finally:
            self._restore_waveform_state(previous)

    @staticmethod
    def _validate_check_errors(check_errors: bool) -> None:
        if type(check_errors) is not bool:
            raise DataError("MSO8104 check_errors must be a boolean")
        if check_errors:
            raise ConfigError(
                "MSO8104 scope.errors is unavailable until non-replayable text queries exist; "
                "set scope.check_errors=false"
            )

    @staticmethod
    def _normalize_point_mode(points: str) -> str:
        if not isinstance(points, str):
            raise DataError("MSO8104 waveform points must be DEF, MAX, or DMAX")
        normalized = points.strip().upper()
        if normalized not in _POINT_MODE_TO_TRANSFER:
            raise DataError("MSO8104 waveform points must be DEF, MAX, or DMAX")
        return normalized

    @staticmethod
    def _validate_capture_adjustments(
        *,
        time_range_s: float | None,
        vertical_scale_v_per_div: float | None,
    ) -> None:
        if time_range_s is not None:
            raise ConfigError(
                "MSO8104 capture does not yet support time_range_s; preconfigure the timebase"
            )
        if vertical_scale_v_per_div is not None:
            raise ConfigError(
                "MSO8104 capture does not yet support vertical_scale_v_per_div; "
                "preconfigure channel scale"
            )

    def _require_displayed_channels(self, channels: list[int]) -> None:
        for channel in channels:
            displayed = parse_display_state(
                self.transport.query(f":CHANnel{channel}:DISPlay?")
            )
            if not displayed:
                raise ConfigError(
                    f"MSO8104 CH{channel} is not displayed; refusing to change channel state"
                )

    def _single_and_wait_for_stop(self) -> None:
        try:
            self.transport.write(":SINGle")
        except Exception as exc:
            self._acquisition_writes_blocked = True
            raise InstrumentError(
                "MSO8104 single-acquisition write outcome is uncertain; "
                "acquisition writes are blocked"
            ) from exc
        deadline = self._clock() + self.acquisition_timeout_s
        while True:
            try:
                status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
            except Exception as exc:
                self._acquisition_writes_blocked = True
                raise InstrumentError(
                    "MSO8104 trigger status became uncertain after SINGLE; "
                    "acquisition writes are blocked"
                ) from exc
            if status == "STOP":
                return
            remaining_s = deadline - self._clock()
            if remaining_s <= 0:
                self._acquisition_writes_blocked = True
                raise OperationTimeout(
                    "MSO8104 single acquisition did not reach STOP before the configured "
                    "opc timeout; the instrument was not forced or retriggered, and acquisition "
                    "writes are blocked until the session is reopened"
                )
            self._sleep(min(self.trigger_poll_interval_s, remaining_s))

    @staticmethod
    def _assert_matching_x_axis(
        reference: WaveformData,
        candidate: WaveformData,
    ) -> None:
        tolerance = max(
            abs(reference.header.x_increment) * 1.0e-6,
            abs(reference.header.x_stop) * 1.0e-12,
            1.0e-18,
        )
        if (
            reference.header.points != candidate.header.points
            or not math.isclose(
                reference.header.x_start,
                candidate.header.x_start,
                rel_tol=0.0,
                abs_tol=tolerance,
            )
            or not math.isclose(
                reference.header.x_stop,
                candidate.header.x_stop,
                rel_tol=0.0,
                abs_tol=tolerance,
            )
        ):
            raise DataError(
                "MSO8104 multi-channel waveforms do not share a consistent X axis"
            )

    def fetch_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
    ) -> WaveformData:
        self._validate_analog_channel(channel)
        point_mode = self._normalize_point_mode(points)
        self._validate_check_errors(check_errors)
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            self._require_displayed_channels([channel])
            self._require_main_timebase()
            if point_mode == "DMAX":
                status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
                if status != "STOP":
                    raise ConfigError(
                        "MSO8104 DMAX fetch requires an already stopped acquisition; "
                        f"current trigger status is {status}"
                    )
            return self._read_waveform_transaction(
                channel,
                point_mode=point_mode,
                remaining_points=self.max_total_waveform_points,
            )

    def capture_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
    ) -> WaveformData:
        waveforms = self.capture_waveforms(
            channels=[channel],
            points=points,
            check_errors=check_errors,
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        return waveforms[channel]

    def capture_waveforms(
        self,
        channels: list[int],
        points: str = "dmax",
        check_errors: bool = True,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
        on_channel_start: Callable[[int | None], None] | None = None,
        on_waveform: Callable[[int, WaveformData], None] | None = None,
    ) -> dict[int, WaveformData]:
        if not isinstance(channels, list) or not channels:
            raise DataError("MSO8104 capture channels must be a non-empty list")
        for channel in channels:
            self._validate_analog_channel(channel)
        if len(set(channels)) != len(channels):
            raise DataError("MSO8104 capture channels must be unique")
        point_mode = self._normalize_point_mode(points)
        self._validate_check_errors(check_errors)
        self._validate_capture_adjustments(
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        if on_channel_start is not None and not callable(on_channel_start):
            raise DataError("MSO8104 on_channel_start must be callable or None")
        if on_waveform is not None and not callable(on_waveform):
            raise DataError("MSO8104 on_waveform must be callable or None")
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            self._require_acquisition_writes_allowed()
            self._require_displayed_channels(channels)
            self._require_main_timebase()
            self._single_and_wait_for_stop()
            waveforms: dict[int, WaveformData] = {}
            reference: WaveformData | None = None
            remaining_points = self.max_total_waveform_points
            for channel in channels:
                if on_channel_start is not None:
                    on_channel_start(channel)
                waveform = self._read_waveform_transaction(
                    channel,
                    point_mode=point_mode,
                    remaining_points=remaining_points,
                )
                if reference is None:
                    reference = waveform
                else:
                    self._assert_matching_x_axis(reference, waveform)
                waveforms[channel] = waveform
                remaining_points -= waveform.sample_count
                if on_waveform is not None:
                    on_waveform(channel, waveform)
            return waveforms

    def close(self) -> None:
        with self._io_lock:
            if self._closed:
                return
            self._closed = True
            self.transport.close()
