from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from math import isfinite
import time

from wavebench.errors import DataError, OperationTimeout
from wavebench.instruments.models import ScopeMeasurementStatistics, WaveformData
from wavebench.transport.base import InstrumentTransport

from .waveform import (
    build_analog_waveform,
    parse_waveform_preamble,
    waveform_header_from_preamble,
)


_MODEL_CHANNEL_COUNTS = {
    "SDS802X HD": 2,
    "SDS804X HD": 4,
    "SDS812X HD": 2,
    "SDS814X HD": 4,
    "SDS822X HD": 2,
    "SDS824X HD": 4,
}
_SUPPORTED_COUPLINGS = {"AC", "DC", "GND"}
_SUPPORTED_POINTS = {"DEF", "MAX", "DMAX"}
_TRIGGER_STATES = {"ARM", "READY", "AUTO", "TRIG'D", "STOP", "ROLL"}


@dataclass(frozen=True)
class _WaveformTransferState:
    source: str
    start: int
    interval: int
    points: int
    width: str
    byte_order: str


def _normalize_identity_field(value: str) -> str:
    return " ".join(value.strip().upper().split())


def _parse_optional_finite_float(value: str, *, field_name: str) -> float | None:
    normalized = value.strip()
    if normalized.upper() == "NAN":
        return None
    try:
        result = float(normalized)
    except ValueError as exc:
        raise DataError(f"SDS800X HD {field_name} must be a number or NAN") from exc
    if not isfinite(result):
        raise DataError(f"SDS800X HD {field_name} must be finite or NAN")
    return result


def _parse_nonnegative_integer(value: str, *, field_name: str) -> int:
    try:
        result = Decimal(value.strip())
    except InvalidOperation as exc:
        raise DataError(f"SDS800X HD {field_name} must be an integer") from exc
    if not result.is_finite() or result < 0 or result != result.to_integral_value():
        raise DataError(f"SDS800X HD {field_name} must be a non-negative integer")
    return int(result)


def _parse_statistics_history(value: str) -> tuple[float, ...]:
    fields = [item.strip() for item in value.strip().split(",")]
    if fields and fields[-1] == "":
        fields.pop()
    if not fields or "=" not in fields[0]:
        raise DataError("SDS800X HD measurement statistics history is missing Count")
    name, count_text = fields[0].split("=", 1)
    if name.strip().upper() != "COUNT":
        raise DataError("SDS800X HD measurement statistics history is missing Count")
    count = _parse_nonnegative_integer(
        count_text,
        field_name="measurement statistics history count",
    )
    if count > 1024:
        raise DataError("SDS800X HD measurement statistics history exceeds 1024 values")
    results = tuple(
        _parse_optional_finite_float(
            item,
            field_name="measurement statistics history value",
        )
        for item in fields[1:]
    )
    if any(item is None for item in results):
        raise DataError("SDS800X HD measurement statistics history values must be finite")
    if len(results) != count:
        raise DataError(
            "SDS800X HD measurement statistics history count does not match its values"
        )
    return tuple(float(item) for item in results)


@dataclass
class SDS800XHDScope:
    transport: InstrumentTransport
    capture_timeout_s: float = 10.0
    capture_poll_interval_s: float = 0.02
    _identity_response: str | None = field(default=None, init=False, repr=False)
    _model: str | None = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def _ensure_identity(self) -> tuple[str, str]:
        if self._identity_response is not None and self._model is not None:
            return self._identity_response, self._model

        response = self.transport.query("*IDN?").strip()
        if not response:
            raise DataError("SDS800X HD returned an empty response for *IDN?")

        fields = tuple(item.strip() for item in response.split(","))
        if len(fields) != 4 or any(not item for item in fields):
            raise DataError("SDS800X HD *IDN? must contain four non-empty comma-separated fields")
        manufacturer, model_text, serial, firmware = fields
        if _normalize_identity_field(manufacturer) != "SIGLENT TECHNOLOGIES":
            raise DataError("SDS800X HD *IDN? returned an unsupported manufacturer")

        model = _normalize_identity_field(model_text)
        if model not in _MODEL_CHANNEL_COUNTS:
            raise DataError("SDS800X HD *IDN? returned an unsupported model")
        if len(serial) != 14 or not serial.isascii():
            raise DataError("SDS800X HD *IDN? serial must contain 14 ASCII characters")
        if not firmware.isascii():
            raise DataError("SDS800X HD *IDN? firmware must contain ASCII characters")

        self._identity_response = response
        self._model = model
        return response, model

    def idn(self) -> str:
        response, _ = self._ensure_identity()
        return response

    def _validate_channel(self, channel: int) -> None:
        if type(channel) is not int:
            raise DataError("SDS800X HD channel must be an integer")
        if channel < 1:
            raise DataError("SDS800X HD channel must be >= 1")
        if channel > 4:
            raise DataError("SDS800X HD channel must be between 1 and 4")

        _, model = self._ensure_identity()
        channel_count = _MODEL_CHANNEL_COUNTS[model]
        if channel > channel_count:
            raise DataError(f"{model} channel must be between 1 and {channel_count}")

    def channel_coupling(self, channel: int) -> str:
        self._validate_channel(channel)

        response = self.transport.query(f":CHANnel{channel}:COUPling?").strip().upper()
        if response not in _SUPPORTED_COUPLINGS:
            raise DataError(
                "SDS800X HD channel coupling must be one of AC, DC, or GND"
            )
        return response

    def get_measurement_statistics(
        self,
        slot: int,
        *,
        configured_slot: bool,
        include_buffer: bool = False,
        acquisition_stopped: bool = False,
    ) -> ScopeMeasurementStatistics:
        if type(slot) is not int or slot not in range(1, 13):
            raise ValueError("SDS800X HD measurement slot must be an integer from 1 through 12")
        if configured_slot is not True:
            raise ValueError(
                "reading an SDS800X HD measurement requires explicit confirmation "
                "that the slot is already configured"
            )
        if type(include_buffer) is not bool or type(acquisition_stopped) is not bool:
            raise ValueError(
                "SDS800X HD measurement buffer flags must be boolean values"
            )
        if include_buffer and not acquisition_stopped:
            raise ValueError(
                "reading the SDS800X HD statistics history requires explicit "
                "confirmation that acquisition is stopped"
            )

        prefix = f":MEASure:ADVanced:P{slot}"
        measurement_mode = self._query_text(
            ":MEASure:MODE?",
            field_name="measurement mode",
        )
        if measurement_mode not in {"SIMPLC", "ADVANCED"}:
            raise DataError("SDS800X HD measurement mode must be SIMPlc or ADVanced")
        if measurement_mode != "ADVANCED":
            raise DataError("SDS800X HD advanced measurement mode is not enabled")
        slot_state = self._query_text(f"{prefix}?", field_name="measurement slot state")
        if slot_state not in {"ON", "OFF"}:
            raise DataError("SDS800X HD measurement slot state must be ON or OFF")
        if slot_state != "ON":
            raise DataError("SDS800X HD measurement slot is not enabled")
        statistics_state = self._query_text(
            ":MEASure:ADVanced:STATistics?",
            field_name="measurement statistics state",
        )
        if statistics_state not in {"ON", "OFF"}:
            raise DataError("SDS800X HD measurement statistics state must be ON or OFF")
        if statistics_state != "ON":
            raise DataError("SDS800X HD measurement statistics are not enabled")

        category = self._query_text(
            f"{prefix}:TYPE?",
            field_name="measurement category",
        )
        fields = {
            "actual": "CURRENT",
            "average": "MEAN",
            "minimum": "MINimum",
            "maximum": "MAXimum",
            "standard_deviation": "STDev",
        }
        values = {
            name: _parse_optional_finite_float(
                self.transport.query(f"{prefix}:STATistics? {selector}"),
                field_name=f"measurement {name}",
            )
            for name, selector in fields.items()
        }
        waveform_count = _parse_nonnegative_integer(
            self.transport.query(f"{prefix}:STATistics? COUNT"),
            field_name="measurement waveform count",
        )
        buffered_values = None
        if include_buffer:
            buffered_values = _parse_statistics_history(
                self.transport.query(f"{prefix}:SHIStory?")
            )
        return ScopeMeasurementStatistics(
            slot=slot,
            category=category,
            actual=values["actual"],
            average=values["average"],
            standard_deviation=values["standard_deviation"],
            minimum=values["minimum"],
            maximum=values["maximum"],
            waveform_count=waveform_count,
            buffered_values=buffered_values,
        )

    def _query_text(self, command: str, *, field_name: str) -> str:
        response = self.transport.query(command)
        if not isinstance(response, str):
            raise DataError(f"SDS800X HD {field_name} response must be text")
        normalized = response.strip().upper()
        if not normalized:
            raise DataError(f"SDS800X HD {field_name} response must not be empty")
        return normalized

    def _query_integer(
        self,
        command: str,
        *,
        field_name: str,
        minimum: int,
    ) -> int:
        response = self._query_text(command, field_name=field_name)
        if not response.isascii() or not response.isdigit():
            raise DataError(f"SDS800X HD {field_name} response must be an integer")
        value = int(response)
        if value < minimum:
            raise DataError(f"SDS800X HD {field_name} must be >= {minimum}")
        return value

    def _read_waveform_transfer_state(self) -> _WaveformTransferState:
        source = self._query_text(":WAVeform:SOURce?", field_name="waveform source")
        if (
            len(source) < 2
            or source[0] not in {"C", "F", "D"}
            or not source[1:].isascii()
            or not source[1:].isdigit()
        ):
            raise DataError("SDS800X HD waveform source must be Cn, Fn, or Dn")

        start = self._query_integer(
            ":WAVeform:START?",
            field_name="waveform start",
            minimum=0,
        )
        interval = self._query_integer(
            ":WAVeform:INTerval?",
            field_name="waveform interval",
            minimum=1,
        )
        points = self._query_integer(
            ":WAVeform:POINt?",
            field_name="waveform point count",
            minimum=0,
        )
        width = self._query_text(":WAVeform:WIDTH?", field_name="waveform width")
        if width not in {"BYTE", "WORD"}:
            raise DataError("SDS800X HD waveform width must be BYTE or WORD")
        byte_order = self._query_text(
            ":WAVeform:BYTeorder?",
            field_name="waveform byte order",
        )
        if byte_order not in {"LSB", "MSB"}:
            raise DataError("SDS800X HD waveform byte order must be LSB or MSB")
        return _WaveformTransferState(
            source=source,
            start=start,
            interval=interval,
            points=points,
            width=width,
            byte_order=byte_order,
        )

    def _configure_waveform_transfer(self, *, channel: int) -> None:
        self.transport.write(f":WAVeform:SOURce C{channel}")
        self.transport.write(":WAVeform:WIDTH WORD")
        self.transport.write(":WAVeform:BYTeorder LSB")
        self.transport.write(":WAVeform:START 0")
        self.transport.write(":WAVeform:INTerval 1")
        self.transport.write(":WAVeform:POINt 0")

    def _restore_waveform_transfer_state(self, state: _WaveformTransferState) -> None:
        commands = (
            ":WAVeform:START 0",
            ":WAVeform:POINt 0",
            f":WAVeform:SOURce {state.source}",
            f":WAVeform:WIDTH {state.width}",
            f":WAVeform:BYTeorder {state.byte_order}",
            f":WAVeform:POINt {state.points}",
            f":WAVeform:INTerval {state.interval}",
            f":WAVeform:START {state.start}",
        )
        failures: list[tuple[str, Exception]] = []
        for command in commands:
            try:
                self.transport.write(command)
            except Exception as exc:
                failures.append((command, exc))
        if failures:
            first_command, first_error = failures[0]
            first_error.add_note(
                f"SDS800X HD waveform transfer restore failed at {first_command!r}"
            )
            for command, error in failures[1:]:
                first_error.add_note(
                    "additional SDS800X HD waveform transfer restore failure at "
                    f"{command!r}: {error}"
                )
            raise first_error

    def _read_waveform_chunks(self, *, points: int, max_points: int) -> bytes:
        chunks: list[bytes] = []
        for start in range(0, points, max_points):
            chunk_points = min(max_points, points - start)
            self.transport.write(f":WAVeform:POINt {chunk_points}")
            self.transport.write(f":WAVeform:START {start}")
            chunk = self.transport.query_bin_block(":WAVeform:DATA?")
            expected_bytes = chunk_points * 2
            if len(chunk) != expected_bytes:
                raise DataError(
                    "SDS800X HD waveform chunk length mismatch at start "
                    f"{start}: expected {expected_bytes}, got {len(chunk)}"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    @staticmethod
    def _validate_waveform_options(points: str, check_errors: bool) -> str:
        if not isinstance(points, str):
            raise DataError("SDS800X HD waveform points must be DEF, MAX, or DMAX")
        normalized_points = points.strip().upper()
        if normalized_points not in _SUPPORTED_POINTS:
            raise DataError("SDS800X HD waveform points must be DEF, MAX, or DMAX")
        if normalized_points != "DMAX":
            raise DataError("SDS800X HD waveform reads currently support only DMAX points")
        if type(check_errors) is not bool:
            raise DataError("SDS800X HD check_errors must be a boolean")
        if check_errors:
            raise DataError(
                "SDS800X HD waveform reads require check_errors=False because CN11G "
                "documents no error-queue query"
            )
        return normalized_points

    def _require_non_sequence_acquisition(self) -> None:
        sequence_state = self._query_text(
            ":ACQuire:SEQuence?",
            field_name="sequence acquisition state",
        )
        if sequence_state not in {"ON", "OFF"}:
            raise DataError("SDS800X HD sequence acquisition state must be ON or OFF")
        if sequence_state != "OFF":
            raise DataError("SDS800X HD waveform reads do not support sequence acquisition")

    @staticmethod
    def _validate_capture_adjustments(
        *,
        time_range_s: float | None,
        vertical_scale_v_per_div: float | None,
    ) -> None:
        for value, name in (
            (time_range_s, "time range"),
            (vertical_scale_v_per_div, "vertical scale"),
        ):
            if value is None:
                continue
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise DataError(f"SDS800X HD {name} must be a finite number")
            if not isfinite(float(value)) or float(value) <= 0:
                raise DataError(f"SDS800X HD {name} must be finite and > 0")

    def _configure_capture_channels(
        self,
        *,
        channels: list[int],
        time_range_s: float | None,
        vertical_scale_v_per_div: float | None,
    ) -> None:
        if time_range_s is not None:
            self.transport.write(f":TIMebase:SCALe {float(time_range_s) / 10.0:.12g}")
        for channel in channels:
            self.transport.write(f":CHANnel{channel}:SWITch ON")
            if vertical_scale_v_per_div is not None:
                self.transport.write(
                    f":CHANnel{channel}:SCALe {float(vertical_scale_v_per_div):.12g}"
                )

    def _stop_after_capture_failure(self, error: BaseException) -> None:
        try:
            self.transport.write(":TRIGger:STOP")
        except Exception as stop_error:
            error.add_note(
                "SDS800X HD failed to stop acquisition after capture failure: "
                f"{stop_error}"
            )

    def _run_single_acquisition(self) -> None:
        if not isfinite(self.capture_timeout_s) or self.capture_timeout_s <= 0:
            raise DataError("SDS800X HD capture timeout must be finite and > 0")
        if not isfinite(self.capture_poll_interval_s) or self.capture_poll_interval_s < 0:
            raise DataError("SDS800X HD capture poll interval must be finite and >= 0")

        self.transport.write(":TRIGger:MODE SINGLE")
        mode = self._query_text(":TRIGger:MODE?", field_name="trigger mode")
        if mode != "SINGLE":
            error = DataError("SDS800X HD did not enter SINGLE trigger mode")
            self._stop_after_capture_failure(error)
            raise error
        self.transport.write(":TRIGger:RUN")
        deadline = time.monotonic() + self.capture_timeout_s
        while True:
            state = self._query_text(":TRIGger:STATus?", field_name="trigger status")
            if state not in _TRIGGER_STATES:
                error = DataError("SDS800X HD returned an unsupported trigger status")
                self._stop_after_capture_failure(error)
                raise error
            if state == "STOP":
                break
            if time.monotonic() >= deadline:
                error = OperationTimeout(
                    "SDS800X HD single acquisition timed out while waiting for Stop. "
                    "Check the trigger source and level, or use scope fetch to read the "
                    "current stopped record."
                )
                self._stop_after_capture_failure(error)
                raise error
            if self.capture_poll_interval_s > 0:
                time.sleep(self.capture_poll_interval_s)
        self._query_integer(
            ":ACQuire:NUMACq?",
            field_name="single acquisition count",
            minimum=1,
        )

    def fetch_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
    ) -> WaveformData:
        self._validate_waveform_options(points, check_errors)
        self._validate_channel(channel)

        trigger_state = self._query_text(
            ":TRIGger:STATus?",
            field_name="trigger status",
        )
        if trigger_state not in _TRIGGER_STATES:
            raise DataError("SDS800X HD returned an unsupported trigger status")
        if trigger_state != "STOP":
            raise DataError("SDS800X HD waveform reads require acquisition state Stop")

        self._require_non_sequence_acquisition()

        state = self._read_waveform_transfer_state()
        primary_error: BaseException | None = None
        try:
            self._configure_waveform_transfer(channel=channel)
            preamble = parse_waveform_preamble(
                self.transport.query_bin_block(":WAVeform:PREamble?")
            )
            if preamble.comm_type != 1 or preamble.sample_byte_order != "little":
                raise DataError("SDS800X HD waveform transfer did not apply WORD and LSB")
            if preamble.source_channel != channel:
                raise DataError(
                    "SDS800X HD waveform preamble source does not match the requested channel"
                )
            waveform_header_from_preamble(preamble)
            expected_bytes = preamble.points * preamble.sample_width_bytes
            if preamble.data_bytes != expected_bytes:
                raise DataError(
                    "SDS800X HD waveform preamble data length does not match the full record"
                )

            max_points = self._query_integer(
                ":WAVeform:MAXPoint?",
                field_name="waveform maximum chunk points",
                minimum=1,
            )
            payload = self._read_waveform_chunks(
                points=preamble.points,
                max_points=max_points,
            )
            return build_analog_waveform(
                channel=channel,
                preamble=preamble,
                payload=payload,
            )
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                self._restore_waveform_transfer_state(state)
            except Exception as restore_error:
                if primary_error is None:
                    raise
                primary_error.add_note(
                    "SDS800X HD waveform transfer state restoration also failed: "
                    f"{restore_error}"
                )

    def capture_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
    ) -> WaveformData:
        self._validate_waveform_options(points, check_errors)
        self._validate_capture_adjustments(
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        self._validate_channel(channel)
        self._require_non_sequence_acquisition()
        self._configure_capture_channels(
            channels=[channel],
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        self._run_single_acquisition()
        return self.fetch_waveform(
            channel=channel,
            points=points,
            check_errors=check_errors,
        )

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
        self._validate_waveform_options(points, check_errors)
        self._validate_capture_adjustments(
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        if not isinstance(channels, list) or not channels:
            raise DataError("SDS800X HD capture channels must be a non-empty list")
        if any(type(channel) is not int for channel in channels):
            raise DataError("SDS800X HD capture channels must contain only integers")
        if len(set(channels)) != len(channels):
            raise DataError("SDS800X HD capture channels must be unique")
        if on_channel_start is not None and not callable(on_channel_start):
            raise DataError("SDS800X HD on_channel_start must be callable")
        if on_waveform is not None and not callable(on_waveform):
            raise DataError("SDS800X HD on_waveform must be callable")
        for channel in channels:
            self._validate_channel(channel)
        self._require_non_sequence_acquisition()
        self._configure_capture_channels(
            channels=channels,
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        self._run_single_acquisition()

        waveforms: dict[int, WaveformData] = {}
        for channel in channels:
            if on_channel_start is not None:
                on_channel_start(channel)
            waveform = self.fetch_waveform(
                channel=channel,
                points=points,
                check_errors=check_errors,
            )
            waveforms[channel] = waveform
            if on_waveform is not None:
                on_waveform(channel, waveform)
        return waveforms

    def close(self) -> None:
        if self._closed:
            return
        self.transport.close()
        self._closed = True
