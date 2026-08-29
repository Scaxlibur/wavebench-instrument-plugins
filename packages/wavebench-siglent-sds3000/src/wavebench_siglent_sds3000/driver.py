from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass, field
from math import isfinite
import re
from threading import RLock
from typing import Callable, Iterator

from wavebench.errors import (
    DataError,
    InstrumentError,
    OperationTimeout,
    SessionHealthError,
    StateDriftError,
    TransportIOError,
)
from wavebench.instruments import WaveformData
from wavebench.transport import InstrumentTransport, ReplayPolicy

from .waveform import decode_waveform_data, parse_waveform_descriptor


_SUPPORTED_REMOTE_MANUFACTURER = "LECROY"
_SUPPORTED_MODEL = "SDS3054"
_SUPPORTED_FIRMWARE = "8.4.1"
_SUPPORTED_CHANNELS = (1, 2, 3, 4)
_COUPLING_MAP = {
    "A1M": "ACL",
    "D1M": "DCL",
    "D50": "DC",
    "GND": "GND",
}
_QUANTITY_RE = re.compile(
    r"(?P<number>[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:E[+-]?\d+)?)\s*(?P<unit>[A-Z]*)"
)
_STRUCTURED_IO_ERRORS = (TransportIOError, SessionHealthError)


@dataclass(frozen=True)
class SDS3000Identity:
    remote_manufacturer: str
    model: str
    serial: str
    firmware: str


@dataclass(frozen=True)
class _WaveformTransferState:
    header: str
    data_format: str
    byte_order: str
    setup: str


def parse_sds3000_identity(response: str) -> SDS3000Identity:
    normalized = response.strip()
    if (
        not normalized
        or not normalized.isascii()
        or any(ord(character) < 0x20 for character in normalized)
    ):
        raise DataError("invalid SDS3000 *IDN? response")
    fields = tuple(field.strip() for field in normalized.split(","))
    if len(fields) != 4 or any(not field for field in fields):
        raise DataError("invalid SDS3000 *IDN? response")
    remote_manufacturer = fields[0]
    if remote_manufacturer.startswith("*IDN "):
        remote_manufacturer = remote_manufacturer.removeprefix("*IDN ").strip()
    identity = SDS3000Identity(remote_manufacturer, *fields[1:])
    if identity.remote_manufacturer != _SUPPORTED_REMOTE_MANUFACTURER:
        raise InstrumentError("configured instrument is not a supported SIGLENT SDS3000")
    if identity.model != _SUPPORTED_MODEL:
        raise InstrumentError(
            f"unsupported SIGLENT SDS3000 model {identity.model!r}; expected {_SUPPORTED_MODEL}"
        )
    if identity.firmware != _SUPPORTED_FIRMWARE:
        raise InstrumentError(
            f"unsupported SDS3054 firmware {identity.firmware!r}; expected {_SUPPORTED_FIRMWARE}"
        )
    return identity


@dataclass
class SDS3000Scope:
    transport: InstrumentTransport
    io_timeout_ms: int = 30_000
    opc_timeout_ms: int = 30_000
    _closed: bool = field(default=False, init=False, repr=False)
    _identity: SDS3000Identity | None = field(default=None, init=False, repr=False)
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)

    @staticmethod
    def _validate_channel(channel: int) -> None:
        if isinstance(channel, bool) or channel not in _SUPPORTED_CHANNELS:
            raise DataError("SDS3054 channel must be one of CH1, CH2, CH3, or CH4")

    def _query_identity(self) -> tuple[str, SDS3000Identity]:
        response = self.transport.query(
            "*IDN?",
            replay=ReplayPolicy.NO_REPLAY,
        ).strip()
        identity = parse_sds3000_identity(response)
        self._identity = identity
        return response, identity

    def _require_identity(self) -> SDS3000Identity:
        if self._identity is None:
            _, identity = self._query_identity()
            return identity
        return self._identity

    def idn(self) -> str:
        response, _ = self._query_identity()
        return response

    def channel_coupling(self, channel: int) -> str:
        self._validate_channel(channel)
        self._require_identity()
        response = self.transport.query(
            f"C{channel}:CPL?",
            replay=ReplayPolicy.NO_REPLAY,
        )
        normalized = response.strip().upper().split()
        if len(normalized) == 1:
            value = normalized[0]
        elif len(normalized) == 2 and normalized[0] in {
            f"C{channel}:CPL",
            f"C{channel}:COUPLING",
        }:
            value = normalized[1]
        else:
            raise DataError(f"invalid C{channel}:CPL? response")
        if value == "OVL":
            raise InstrumentError(
                f"SDS3054 CH{channel} reports a 50 ohm input overload and disconnected the input"
            )
        try:
            return _COUPLING_MAP[value]
        except KeyError as exc:
            raise DataError(f"invalid C{channel}:CPL? response") from exc

    @staticmethod
    def _parse_register(response: str, *, register: str, maximum: int) -> int:
        fields = response.strip().upper().split()
        if len(fields) == 1:
            raw_value = fields[0]
        elif len(fields) == 2 and fields[0].removesuffix("?") == register:
            raw_value = fields[1]
        else:
            raise DataError(f"invalid {register}? response")
        if not raw_value.isascii() or not raw_value.isdecimal():
            raise DataError(f"invalid {register}? response")
        value = int(raw_value)
        if value > maximum:
            raise DataError(f"out-of-range {register}? response")
        return value

    def errors(self, limit: int = 16) -> list[str]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise DataError("SDS3054 error limit must be a positive integer")
        self._require_identity()
        registers = (
            (
                "CMR",
                self._parse_register(
                    self.transport.query("CMR?", replay=ReplayPolicy.NO_REPLAY),
                    register="CMR",
                    maximum=13,
                ),
            ),
            (
                "EXR",
                self._parse_register(
                    self.transport.query("EXR?", replay=ReplayPolicy.NO_REPLAY),
                    register="EXR",
                    maximum=64,
                ),
            ),
            (
                "DDR",
                self._parse_register(
                    self.transport.query("DDR?", replay=ReplayPolicy.NO_REPLAY),
                    register="DDR",
                    maximum=65_535,
                ),
            ),
        )
        return [f"{register} {value}" for register, value in registers if value][:limit]

    def assert_no_errors(self) -> None:
        active = self.errors()
        if active:
            raise InstrumentError("SDS3054 error registers are not clear: " + "; ".join(active))

    @staticmethod
    def _response_value(response: str, *headers: str) -> str:
        normalized = response.strip().upper()
        if (
            not normalized
            or not normalized.isascii()
            or any(ord(character) < 0x20 for character in normalized)
        ):
            raise DataError("invalid SDS3000 communication state response")
        fields = normalized.split(maxsplit=1)
        if fields[0].removesuffix("?") in headers:
            if len(fields) != 2:
                raise DataError("invalid SDS3000 communication state response")
            return fields[1].strip()
        return normalized

    @classmethod
    def _parse_header_state(cls, response: str) -> str:
        value = cls._response_value(response, "CHDR", "COMM_HEADER")
        if value not in {"SHORT", "LONG", "OFF"}:
            raise DataError("invalid SDS3000 CHDR? response")
        return value

    @classmethod
    def _parse_format_state(cls, response: str) -> str:
        value = cls._response_value(response, "CFMT", "COMM_FORMAT")
        fields = tuple(field.strip() for field in value.split(","))
        if (
            len(fields) != 3
            or fields[0] != "DEF9"
            or fields[1] not in {"BYTE", "WORD"}
            or fields[2] != "BIN"
        ):
            raise DataError("invalid SDS3000 CFMT? response")
        return ",".join(fields)

    @classmethod
    def _parse_order_state(cls, response: str) -> str:
        value = cls._response_value(response, "CORD", "COMM_ORDER")
        if value not in {"HI", "LO"}:
            raise DataError("invalid SDS3000 CORD? response")
        return value

    @classmethod
    def _parse_setup_state(cls, response: str) -> str:
        value = cls._response_value(response, "WFSU", "WAVEFORM_SETUP")
        fields = tuple(field.strip() for field in value.split(","))
        if len(fields) != 8:
            raise DataError("invalid SDS3000 WFSU? response")
        values: dict[str, int] = {}
        for key, raw_value in zip(fields[0::2], fields[1::2]):
            if key not in {"SP", "NP", "FP", "SN"} or key in values:
                raise DataError("invalid SDS3000 WFSU? response")
            try:
                parsed = int(raw_value, 10)
            except ValueError as exc:
                raise DataError("invalid SDS3000 WFSU? response") from exc
            if parsed < 0:
                raise DataError("invalid SDS3000 WFSU? response")
            values[key] = parsed
        if values.keys() != {"SP", "NP", "FP", "SN"}:
            raise DataError("invalid SDS3000 WFSU? response")
        return ",".join(f"{key},{values[key]}" for key in ("SP", "NP", "FP", "SN"))

    def _query_waveform_transfer_state(self) -> _WaveformTransferState:
        return _WaveformTransferState(
            header=self._parse_header_state(
                self.transport.query("CHDR?", replay=ReplayPolicy.NO_REPLAY)
            ),
            data_format=self._parse_format_state(
                self.transport.query("CFMT?", replay=ReplayPolicy.NO_REPLAY)
            ),
            byte_order=self._parse_order_state(
                self.transport.query("CORD?", replay=ReplayPolicy.NO_REPLAY)
            ),
            setup=self._parse_setup_state(
                self.transport.query("WFSU?", replay=ReplayPolicy.NO_REPLAY)
            ),
        )

    @contextmanager
    def _temporary_waveform_transfer_state(
        self,
        state: _WaveformTransferState,
    ) -> Iterator[None]:
        settings = (
            ("CHDR", state.header, "OFF"),
            ("CFMT", state.data_format, "DEF9,WORD,BIN"),
            ("CORD", state.byte_order, "LO"),
            ("WFSU", state.setup, "SP,0,NP,0,FP,0,SN,1"),
        )
        restore: list[tuple[str, str]] = []
        operation_failure: BaseException | None = None
        try:
            for command, previous, desired in settings:
                if previous == desired:
                    continue
                restore.append((command, previous))
                self.transport.write(f"{command} {desired}")
            yield
        except BaseException as exc:
            operation_failure = exc
            raise
        finally:
            if not isinstance(operation_failure, _STRUCTURED_IO_ERRORS):
                failures: list[tuple[str, str, Exception]] = []
                for command, previous in reversed(restore):
                    try:
                        self.transport.write(f"{command} {previous}")
                    except _STRUCTURED_IO_ERRORS:
                        raise
                    except Exception as exc:  # pragma: no branch - all failures are retained
                        failures.append((command, previous, exc))
                if failures:
                    expected = {command: previous for command, previous, _ in failures}
                    diff = {
                        command: {"expected": previous, "actual": "unknown"}
                        for command, previous, _ in failures
                    }
                    names = ", ".join(command for command, _, _ in failures)
                    raise StateDriftError(
                        f"failed to restore SDS3000 waveform transfer state: {names}",
                        expected=expected,
                        actual={command: "unknown" for command in expected},
                        diff=diff,
                    ) from failures[0][2]

    @staticmethod
    def _validate_waveform_points(points: str) -> str:
        if not isinstance(points, str):
            raise DataError("SDS3054 waveform points must be DEF, MAX, or DMAX")
        normalized = points.strip().upper()
        if normalized not in {"DEF", "MAX", "DMAX"}:
            raise DataError("SDS3054 waveform points must be DEF, MAX, or DMAX")
        return normalized

    @classmethod
    def _parse_trigger_mode(cls, response: str) -> str:
        value = cls._response_value(response, "TRMD", "TRIG_MODE")
        if value not in {"AUTO", "NORM", "SINGLE", "STOP"}:
            raise DataError("invalid SDS3000 TRMD? response")
        return value

    @classmethod
    def _parse_trace_state(cls, response: str, *, channel: int) -> str:
        value = cls._response_value(response, f"C{channel}:TRA", f"C{channel}:TRACE")
        if value not in {"ON", "OFF"}:
            raise DataError(f"invalid C{channel}:TRA? response")
        return value

    @classmethod
    def _parse_positive_quantity(
        cls,
        response: str,
        *,
        headers: tuple[str, ...],
        units: frozenset[str],
        name: str,
    ) -> str:
        value = cls._response_value(response, *headers)
        match = _QUANTITY_RE.fullmatch(value)
        if match is None or match.group("unit") not in units:
            raise DataError(f"invalid SDS3000 {name}? response")
        number = float(match.group("number"))
        if not isfinite(number) or number <= 0:
            raise DataError(f"invalid SDS3000 {name}? response")
        return value

    @classmethod
    def _parse_opc(cls, response: str) -> None:
        if cls._response_value(response, "*OPC") != "1":
            raise DataError("invalid SDS3000 *OPC? response")

    @staticmethod
    def _validate_optional_positive(value: float | None, *, name: str) -> None:
        if value is None:
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise DataError(f"SDS3054 {name} must be a positive finite number")
        if not isfinite(float(value)) or value <= 0:
            raise DataError(f"SDS3054 {name} must be a positive finite number")

    def _read_waveform_in_transfer_state(self, channel: int) -> WaveformData:
        descriptor = parse_waveform_descriptor(
            self.transport.query_bin_block(
                f"C{channel}:WF? DESC",
                replay=ReplayPolicy.NO_REPLAY,
            )
        )
        if descriptor.byte_order != "little" or descriptor.sample_width_bytes != 2:
            raise DataError("SDS3000 waveform transfer settings did not take effect")
        return decode_waveform_data(
            descriptor,
            self.transport.query_bin_block(
                f"C{channel}:WF? DAT1",
                replay=ReplayPolicy.NO_REPLAY,
            ),
            channel=channel,
        )

    def _read_waveforms(self, channels: list[int]) -> dict[int, WaveformData]:
        state = self._query_waveform_transfer_state()
        with self._temporary_waveform_transfer_state(state):
            return {channel: self._read_waveform_in_transfer_state(channel) for channel in channels}

    def fetch_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
    ) -> WaveformData:
        self._validate_channel(channel)
        self._validate_waveform_points(points)
        with self._io_lock:
            self._require_identity()
            waveform = self._read_waveforms([channel])[channel]
            if check_errors:
                self.assert_no_errors()
            return waveform

    @contextmanager
    def _temporary_capture_state(
        self,
        channels: list[int],
        *,
        time_range_s: float | None,
        vertical_scale_v_per_div: float | None,
    ) -> Iterator[None]:
        trigger_mode = self._parse_trigger_mode(
            self.transport.query("TRMD?", replay=ReplayPolicy.NO_REPLAY)
        )
        time_division = (
            self._parse_positive_quantity(
                self.transport.query("TDIV?", replay=ReplayPolicy.NO_REPLAY),
                headers=("TDIV", "TIME_DIV"),
                units=frozenset({"", "S", "MS", "US", "NS", "KS"}),
                name="TDIV",
            )
            if time_range_s is not None
            else None
        )
        vertical_divisions = {
            channel: self._parse_positive_quantity(
                self.transport.query(
                    f"C{channel}:VDIV?",
                    replay=ReplayPolicy.NO_REPLAY,
                ),
                headers=(f"C{channel}:VDIV", f"C{channel}:VOLT_DIV"),
                units=frozenset({"", "V", "MV", "UV", "NV", "KV"}),
                name=f"C{channel}:VDIV",
            )
            for channel in channels
            if vertical_scale_v_per_div is not None
        }
        traces = {
            channel: self._parse_trace_state(
                self.transport.query(
                    f"C{channel}:TRA?",
                    replay=ReplayPolicy.NO_REPLAY,
                ),
                channel=channel,
            )
            for channel in channels
        }

        restore: list[tuple[str, str, str]] = []
        operation_failure: BaseException | None = None
        try:
            restore.append(("TRMD", f"TRMD {trigger_mode}", trigger_mode))
            self.transport.write("STOP")
            if time_division is not None:
                restore.append(("TDIV", f"TDIV {time_division}", time_division))
                self.transport.write(f"TDIV {float(time_range_s) / 10.0:.12g}")
            for channel, previous in vertical_divisions.items():
                name = f"C{channel}:VDIV"
                restore.append((name, f"{name} {previous}", previous))
                self.transport.write(f"{name} {float(vertical_scale_v_per_div):.12g}")
            for channel, previous in traces.items():
                if previous == "ON":
                    continue
                name = f"C{channel}:TRA"
                restore.append((name, f"{name} {previous}", previous))
                self.transport.write(f"{name} ON")
            yield
        except BaseException as exc:
            operation_failure = exc
            raise
        finally:
            if not isinstance(operation_failure, _STRUCTURED_IO_ERRORS):
                failures: list[tuple[str, str, Exception]] = []
                for name, command, expected in reversed(restore):
                    try:
                        self.transport.write(command)
                    except _STRUCTURED_IO_ERRORS:
                        raise
                    except Exception as exc:  # pragma: no branch - all failures are retained
                        failures.append((name, expected, exc))
                if failures:
                    expected = {name: value for name, value, _ in failures}
                    diff = {
                        name: {"expected": value, "actual": "unknown"}
                        for name, value, _ in failures
                    }
                    names = ", ".join(name for name, _, _ in failures)
                    raise StateDriftError(
                        f"failed to restore SDS3000 capture state: {names}",
                        expected=expected,
                        actual={name: "unknown" for name in expected},
                        diff=diff,
                    ) from failures[0][2]

    def _acquire_once(self) -> None:
        budget_ms = max(min(self.io_timeout_ms, self.opc_timeout_ms), 1_000)
        wait_seconds = max((budget_ms - 2_000) / 1_000.0, 1.0)
        self.transport.write("ARM")
        self.transport.write(f"WAIT {wait_seconds:.12g}")
        try:
            self._parse_opc(
                self.transport.query_opc(replay=ReplayPolicy.NO_REPLAY)
            )
        except _STRUCTURED_IO_ERRORS:
            raise
        except Exception as exc:
            raise OperationTimeout(
                "SDS3054 single acquisition timed out while waiting for WAIT/*OPC?"
            ) from exc
        if (
            self._parse_trigger_mode(
                self.transport.query("TRMD?", replay=ReplayPolicy.NO_REPLAY)
            )
            != "STOP"
        ):
            raise OperationTimeout(
                "SDS3054 did not complete a triggered acquisition before the WAIT timeout"
            )

    def capture_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
    ) -> WaveformData:
        return self.capture_waveforms(
            [channel],
            points=points,
            check_errors=check_errors,
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )[channel]

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
            raise DataError("SDS3054 capture channels must be a non-empty list")
        for channel in channels:
            self._validate_channel(channel)
        if len(set(channels)) != len(channels):
            raise DataError("SDS3054 capture channels must be unique")
        self._validate_waveform_points(points)
        self._validate_optional_positive(time_range_s, name="time range")
        self._validate_optional_positive(
            vertical_scale_v_per_div,
            name="vertical scale",
        )

        with self._io_lock:
            self._require_identity()
            with self._temporary_capture_state(
                channels,
                time_range_s=time_range_s,
                vertical_scale_v_per_div=vertical_scale_v_per_div,
            ):
                self._acquire_once()
                transfer_state = self._query_waveform_transfer_state()
                waveforms: dict[int, WaveformData] = {}
                with self._temporary_waveform_transfer_state(transfer_state):
                    for channel in channels:
                        if on_channel_start is not None:
                            on_channel_start(channel)
                        waveform = self._read_waveform_in_transfer_state(channel)
                        waveforms[channel] = waveform
                        if on_waveform is not None:
                            on_waveform(channel, waveform)
            if check_errors:
                if on_channel_start is not None:
                    on_channel_start(None)
                self.assert_no_errors()
            return waveforms

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.transport.close()
