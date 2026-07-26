from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from functools import wraps
import math
from numbers import Real
import re
from threading import RLock
import time

import numpy as np

from wavebench.errors import DataError, InstrumentError, OperationTimeout
from wavebench.instruments.models import (
    ScopeAcquisitionStatus,
    ScopeAverageCaptureRequest,
    ScopeAverageCaptureResult,
    ScopeAverageConfiguration,
    ScopeAnalogChannelSnapshot,
    ScopeCursorReadout,
    ScopeDerivedWaveformMetadata,
    ScopeEdgeTriggerSnapshot,
    ScopeFftStatus,
    ScopeHealthSnapshot,
    ScopeHistoryTimestamp,
    ScopeHistoryTimestamps,
    ScopeMeasurementStatistics,
    ScopeIdentitySnapshot,
    ScopeProbeSnapshot,
    ScopeSnapshot,
    ScopeTimebaseSnapshot,
    ScopeWaveformMetadataSnapshot,
    WaveformData,
    WaveformHeader,
)
from wavebench.transport.base import InstrumentTransport


_DECIMAL_INTEGER = re.compile(r"[+-]?[0-9]+")
_UNAVAILABLE_FLOAT_MINIMUM = 9.0e37
_MAX_HISTORY_RESPONSE_CHARS = 8_000_000
_MAX_HISTORY_SEGMENTS = 100_000
_NEWEST_RELATIVE_TIME_TOLERANCE_S = 1.0e-6


def _parse_idn(response: str) -> tuple[str, str, str, str]:
    parts = tuple(item.strip() for item in response.split(","))
    if len(parts) != 4 or any(not item for item in parts):
        raise DataError(f"invalid *IDN? response: {response!r}")
    manufacturer, model, serial_number, firmware = parts
    if not model.upper().startswith("RTM"):
        raise DataError(f"unexpected RTM2000 model in *IDN? response: {model!r}")
    return manufacturer, model, serial_number, firmware


def _parse_options(response: str) -> tuple[str, ...]:
    value = response.strip().strip('"')
    if value in {"", "0"}:
        return ()
    options = tuple(item.strip() for item in value.split(","))
    if any(
        not item or any(ord(character) < 0x20 for character in item)
        for item in options
    ):
        raise DataError(f"invalid *OPT? response: {response!r}")
    return options


def _has_option(options: tuple[str, ...], option_code: str) -> bool:
    expected = option_code.strip().upper()
    return any(
        option.upper() == expected
        or option.upper().startswith(f"{expected} ")
        for option in options
    )


def _parse_decimal_integer(
    response: str,
    *,
    command: str,
    minimum: int,
    maximum: int | None = None,
) -> int:
    value = response.strip()
    if _DECIMAL_INTEGER.fullmatch(value) is None:
        raise DataError(f"invalid {command} response: {response!r}")
    parsed = int(value, 10)
    if parsed < minimum or (maximum is not None and parsed > maximum):
        raise DataError(f"out-of-range {command} response: {response!r}")
    return parsed


def _parse_positive_float(response: str, *, command: str) -> float:
    try:
        value = float(response.strip())
    except ValueError as exc:
        raise DataError(f"invalid {command} response: {response!r}") from exc
    if not math.isfinite(value) or value <= 0:
        raise DataError(f"out-of-range {command} response: {response!r}")
    return value


def _parse_finite_float(response: str, *, command: str) -> float:
    try:
        value = float(response.strip())
    except ValueError as exc:
        raise DataError(f"invalid {command} response: {response!r}") from exc
    if not math.isfinite(value):
        raise DataError(f"non-finite {command} response: {response!r}")
    return value


def _parse_bounded_float(
    response: str,
    *,
    command: str,
    minimum: float,
    maximum: float,
) -> float:
    value = _parse_finite_float(response, command=command)
    if value < minimum or value > maximum:
        raise DataError(f"out-of-range {command} response: {response!r}")
    return value


def _parse_optional_positive_float(response: str, *, command: str) -> float | None:
    value = _parse_positive_float(response, command=command)
    return None if value >= _UNAVAILABLE_FLOAT_MINIMUM else value


def _parse_bool(response: str, *, command: str) -> bool:
    value = response.strip().upper()
    if value in {"1", "ON"}:
        return True
    if value in {"0", "OFF"}:
        return False
    raise DataError(f"invalid {command} response: {response!r}")


def _parse_csv_fields(response: str, *, command: str) -> tuple[str, ...]:
    if len(response) > _MAX_HISTORY_RESPONSE_CHARS:
        raise DataError(f"oversized {command} response")
    value = response.strip()
    if not value:
        return ()
    fields = tuple(item.strip() for item in value.split(","))
    if any(not item for item in fields):
        raise DataError(f"invalid {command} response: {response!r}")
    return fields


def _parse_history_relative_times(response: str) -> tuple[float, ...]:
    command = "CHANnel:HISTORY:TSRelative:ALL?"
    fields = _parse_csv_fields(response, command=command)
    if len(fields) > _MAX_HISTORY_SEGMENTS:
        raise DataError(f"too many segments in {command} response")
    values = tuple(_parse_finite_float(item, command=command) for item in fields)
    if any(value > _NEWEST_RELATIVE_TIME_TOLERANCE_S for value in values):
        raise DataError(f"out-of-range {command} response: {response!r}")
    if any(current > following for current, following in zip(values, values[1:])):
        raise DataError(f"out-of-order {command} response: {response!r}")
    newest_is_not_zero = (
        bool(values)
        and abs(values[-1]) > _NEWEST_RELATIVE_TIME_TOLERANCE_S
    )
    if newest_is_not_zero:
        raise DataError(f"newest segment is not near zero in {command} response")
    return values


def _parse_history_dates(response: str) -> tuple[tuple[int, int, int], ...]:
    command = "CHANnel:HISTORY:TSDate:ALL?"
    fields = _parse_csv_fields(response, command=command)
    if len(fields) % 3:
        raise DataError(f"invalid {command} response: {response!r}")
    if len(fields) // 3 > _MAX_HISTORY_SEGMENTS:
        raise DataError(f"too many segments in {command} response")
    result = []
    for offset in range(0, len(fields), 3):
        year, month, day = (
            _parse_decimal_integer(field, command=command, minimum=1)
            for field in fields[offset : offset + 3]
        )
        try:
            date(year, month, day)
        except ValueError as exc:
            raise DataError(f"out-of-range {command} response: {response!r}") from exc
        result.append((year, month, day))
    return tuple(result)


def _parse_history_times(response: str) -> tuple[tuple[int, int, float], ...]:
    command = "CHANnel:HISTORY:TSABsolute:ALL?"
    fields = _parse_csv_fields(response, command=command)
    if len(fields) % 3:
        raise DataError(f"invalid {command} response: {response!r}")
    if len(fields) // 3 > _MAX_HISTORY_SEGMENTS:
        raise DataError(f"too many segments in {command} response")
    result = []
    for offset in range(0, len(fields), 3):
        hour = _parse_decimal_integer(
            fields[offset], command=command, minimum=0, maximum=23
        )
        minute = _parse_decimal_integer(
            fields[offset + 1], command=command, minimum=0, maximum=59
        )
        second = _parse_bounded_float(
            fields[offset + 2], command=command, minimum=0.0, maximum=60.0
        )
        if second >= 60.0:
            raise DataError(f"out-of-range {command} response: {response!r}")
        result.append((hour, minute, second))
    return tuple(result)


def _parse_optional_measurement_float(response: str, *, command: str) -> float | None:
    value = response.strip().upper()
    if value == "NAN":
        return None
    return _parse_finite_float(response, command=command)


_CURSOR_RESULT_FUNCTIONS = frozenset(
    {
        "PPCOUNT",
        "NPCOUNT",
        "RECOUNT",
        "FECOUNT",
        "MEAN",
        "RMS",
        "RTIME",
        "FTIME",
        "PEAK",
        "UPEAKVALUE",
        "LPEAKVALUE",
        "BWIDTH",
    }
)

_CURSOR_FUNCTION_ALIASES = {
    "VERT": "VERTICAL",
    "VERTICAL": "VERTICAL",
    "HOR": "HORIZONTAL",
    "HORIZ": "HORIZONTAL",
    "HORIZONTAL": "HORIZONTAL",
    "PAIR": "PAIRED",
    "PAIRED": "PAIRED",
    "VRAT": "VRATIO",
    "VRATIO": "VRATIO",
    "HRAT": "HRATIO",
    "HRATIO": "HRATIO",
}


def _normalize_cursor_function(response: str, *, command: str) -> str:
    function = _parse_token(response, command=command)
    return _CURSOR_FUNCTION_ALIASES.get(function, function)


def _metadata_from_prefix(
    transport: InstrumentTransport,
    *,
    prefix: str,
    source_kind: str,
    index: int,
    source_catalog: str | None,
) -> ScopeDerivedWaveformMetadata:
    header, values_per_sample = _parse_waveform_header_response(
        transport.query(f"{prefix}:HEADer?")
    )
    points = _parse_decimal_integer(
        transport.query(f"{prefix}:POINts?"),
        command=f"{prefix}:POINts?",
        minimum=1,
    )
    if points != header.points:
        raise DataError(
            f"{source_kind} waveform metadata point count mismatch: "
            f"header says {header.points}, POINTs? returned {points}"
        )
    x_increment = _parse_positive_float(
        transport.query(f"{prefix}:XINCrement?"),
        command=f"{prefix}:XINCrement?",
    )
    x_origin = _parse_finite_float(
        transport.query(f"{prefix}:XORigin?"),
        command=f"{prefix}:XORigin?",
    )
    tolerance = max(x_increment * 1e-6, 1e-15)
    if not math.isclose(x_origin, header.x_start, abs_tol=tolerance) or not math.isclose(
        x_origin + (points - 1) * x_increment,
        header.x_stop,
        abs_tol=tolerance,
    ):
        raise DataError(f"{source_kind} waveform metadata x-axis mismatch")
    return ScopeDerivedWaveformMetadata(
        source_kind=source_kind,
        index=index,
        source_catalog=source_catalog,
        x_start=header.x_start,
        x_stop=header.x_stop,
        points=points,
        values_per_sample=values_per_sample,
        x_increment=x_increment,
        x_origin=x_origin,
        y_increment=_parse_positive_float(
            transport.query(f"{prefix}:YINCrement?"),
            command=f"{prefix}:YINCrement?",
        ),
        y_origin=_parse_finite_float(
            transport.query(f"{prefix}:YORigin?"),
            command=f"{prefix}:YORigin?",
        ),
        y_resolution_bits=_parse_decimal_integer(
            transport.query(f"{prefix}:YRESolution?"),
            command=f"{prefix}:YRESolution?",
            minimum=1,
            maximum=64,
        ),
    )


def _parse_token(
    response: str,
    *,
    command: str,
    allowed: frozenset[str] | None = None,
) -> str:
    value = response.strip().upper()
    valid_characters = value.replace("_", "")
    if (
        not value
        or not value.isascii()
        or not value[0].isalpha()
        or not valid_characters.isalnum()
        or (allowed is not None and value not in allowed)
    ):
        raise DataError(f"invalid {command} response: {response!r}")
    return value


def _parse_quoted_text(response: str, *, command: str) -> str:
    value = response.strip()
    if len(value) < 2 or not value.startswith('"') or not value.endswith('"'):
        raise DataError(f"invalid {command} response: {response!r}")
    text = value[1:-1]
    if '"' in text or any(ord(character) < 0x20 for character in text):
        raise DataError(f"invalid {command} response: {response!r}")
    return text


def _validate_rtm2032_channel(channel: int) -> None:
    if isinstance(channel, bool) or channel not in {1, 2}:
        raise DataError("RTM2032 channel must be 1 or 2")


RTM2000IdentitySnapshot = ScopeIdentitySnapshot
RTM2000HealthSnapshot = ScopeHealthSnapshot
RTM2000AnalogChannelSnapshot = ScopeAnalogChannelSnapshot
RTM2000TimebaseSnapshot = ScopeTimebaseSnapshot
RTM2000ProbeSnapshot = ScopeProbeSnapshot
RTM2000WaveformMetadataSnapshot = ScopeWaveformMetadataSnapshot
RTM2000EdgeTriggerSnapshot = ScopeEdgeTriggerSnapshot


class RTM2000TriggerControlError(InstrumentError):
    def __init__(self, message: str, *, phase: str):
        super().__init__(message)
        self.phase = phase


class RTM2000AverageCaptureError(InstrumentError):
    def __init__(self, message: str, *, phase: str):
        super().__init__(message)
        self.phase = phase


def _parse_waveform_header_response(
    response: str,
) -> tuple[WaveformHeader, int | None]:
    parts = [item.strip() for item in response.split(",")]
    if len(parts) not in {3, 4}:
        raise DataError(f"invalid CHAN:DATA:HEAD? response: {response!r}")
    try:
        x_start = float(parts[0])
        x_stop = float(parts[1])
        points = _parse_decimal_integer(
            parts[2],
            command="CHAN:DATA:HEAD? point count",
            minimum=1,
        )
        values_per_sample = (
            _parse_decimal_integer(
                parts[3],
                command="CHAN:DATA:HEAD? values per sample interval",
                minimum=1,
            )
            if len(parts) == 4
            else None
        )
    except ValueError as exc:
        raise DataError(f"invalid CHAN:DATA:HEAD? response: {response!r}") from exc
    if (
        not math.isfinite(x_start)
        or not math.isfinite(x_stop)
        or x_stop < x_start
        or (points > 1 and x_stop == x_start)
    ):
        raise DataError(f"invalid waveform time range: {response!r}")
    return (
        WaveformHeader(
            x_start=x_start,
            x_stop=x_stop,
            points=points,
            # RTM2000 DATA:HEADER field 4 is values per sample interval,
            # not a history-segment identity. Do not leak it into core
            # capture metadata under the misleading ``segment`` field.
            segment=None,
        ),
        values_per_sample,
    )


def parse_waveform_header(response: str) -> WaveformHeader:
    return _parse_waveform_header_response(response)[0]


def _serialized_io(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self._io_lock:
            return method(self, *args, **kwargs)

    return wrapped


@dataclass
class RTM2032Scope:
    transport: InstrumentTransport
    check_errors_after_ops: bool = True
    long_waveform_timeout_ms: int = 300_000
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _trigger_writes_blocked: bool = field(default=False, init=False, repr=False)
    _average_writes_blocked: bool = field(default=False, init=False, repr=False)

    @_serialized_io
    def idn(self) -> str:
        return self.transport.query("*IDN?")

    @_serialized_io
    def identity_snapshot(self) -> RTM2000IdentitySnapshot:
        with self._io_lock:
            manufacturer, model, serial_number, firmware = _parse_idn(self.idn())
            return RTM2000IdentitySnapshot(
                manufacturer=manufacturer,
                model=model,
                serial_number=serial_number,
                firmware=firmware,
                options=_parse_options(self.transport.query("*OPT?")),
            )

    @_serialized_io
    def get_acquisition_status(self) -> ScopeAcquisitionStatus:
        with self._io_lock:
            options = _parse_options(self.transport.query("*OPT?"))
            has_k15 = _has_option(options, "K15")
            average_count = _parse_decimal_integer(
                self.transport.query("ACQuire:AVERage:COUNt?"),
                command="ACQuire:AVERage:COUNt?",
                minimum=2,
                maximum=1024,
            )
            average_complete = _parse_bool(
                self.transport.query("ACQuire:AVERage:COMPlete?"),
                command="ACQuire:AVERage:COMPlete?",
            )
            if not has_k15:
                return ScopeAcquisitionStatus(
                    average_count=average_count,
                    average_complete=average_complete,
                    segmented_option_installed=False,
                    segmented_enabled=None,
                    segmented_maximum_enabled=None,
                    segment_capacity=None,
                    segments_available=None,
                )
            return ScopeAcquisitionStatus(
                average_count=average_count,
                average_complete=average_complete,
                segmented_option_installed=True,
                segmented_enabled=_parse_bool(
                    self.transport.query("ACQuire:SEGMented:STATe?"),
                    command="ACQuire:SEGMented:STATe?",
                ),
                segmented_maximum_enabled=_parse_bool(
                    self.transport.query("ACQuire:SEGMented:MAXimum?"),
                    command="ACQuire:SEGMented:MAXimum?",
                ),
                segment_capacity=_parse_decimal_integer(
                    self.transport.query("ACQuire:COUNt?"),
                    command="ACQuire:COUNt?",
                    minimum=0,
                ),
                segments_available=_parse_decimal_integer(
                    self.transport.query("ACQuire:AVAilable?"),
                    command="ACQuire:AVAilable?",
                    minimum=0,
                ),
            )

    def _average_configuration_unlocked(
        self,
    ) -> ScopeAverageConfiguration:
        average_count = _parse_decimal_integer(
            self.transport.query("ACQuire:AVERage:COUNt?"),
            command="ACQuire:AVERage:COUNt?",
            minimum=2,
            maximum=1024,
        )
        single_count = _parse_decimal_integer(
            self.transport.query("ACQuire:NSINgle:COUNt?"),
            command="ACQuire:NSINgle:COUNt?",
            minimum=1,
        )
        arithmetic = tuple(
            (
                channel,
                _parse_token(
                    self.transport.query(f"CHANnel{channel}:ARITHmetics?"),
                    command=f"CHANnel{channel}:ARITHmetics?",
                    allowed=frozenset(
                        {"OFF", "ENVELOPE", "AVERAGE", "SMOOTH", "FILTER"}
                    ),
                ),
            )
            for channel in (1, 2)
        )
        if arithmetic[0][1] != arithmetic[1][1]:
            raise DataError(
                "RTM2032 channel arithmetic readback is inconsistent even though the "
                "documented setting affects all channels"
            )
        return ScopeAverageConfiguration(
            average_count=average_count,
            single_count=single_count,
            channel_arithmetic=arithmetic,
        )

    def _restore_average_configuration_unlocked(
        self,
        configuration: ScopeAverageConfiguration,
    ) -> None:
        self.transport.write(
            f"ACQuire:AVERage:COUNt {configuration.average_count}"
        )
        self.transport.write(
            f"ACQuire:NSINgle:COUNt {configuration.single_count}"
        )
        self.transport.write(
            f"CHANnel1:ARITHmetics {configuration.channel_arithmetic[0][1]}"
        )

    def _require_real_waveform_transfer_unlocked(self) -> None:
        data_format = self.transport.query("FORMat?").strip().upper().replace(" ", "")
        byte_order = self.transport.query("FORMat:BORDer?").strip().upper()
        if data_format != "REAL,32" or byte_order != "LSBF":
            raise DataError(
                "controlled average capture requires the existing waveform transfer "
                "format to be REAL,32 with LSBF byte order"
            )

    @property
    def average_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._average_writes_blocked

    def capture_average(
        self,
        request: ScopeAverageCaptureRequest,
    ) -> ScopeAverageCaptureResult:
        for channel in request.channels:
            _validate_rtm2032_channel(channel)
        with self._io_lock:
            if self._average_writes_blocked:
                raise RTM2000AverageCaptureError(
                    "average writes are blocked after an earlier ambiguous transaction",
                    phase="blocked",
                )
            phase = "preflight"
            self._require_real_waveform_transfer_unlocked()
            configuration_before = self._average_configuration_unlocked()
            wrote = False
            acquisition_started = False
            acquisition_completed = False
            try:
                phase = "configure"
                wrote = True
                self.transport.write(
                    f"ACQuire:AVERage:COUNt {request.average_count}"
                )
                self.transport.write(
                    f"ACQuire:NSINgle:COUNt {request.average_count}"
                )
                self.transport.write("CHANnel1:ARITHmetics AVERage")

                phase = "configure-readback"
                configured = self._average_configuration_unlocked()
                expected = ScopeAverageConfiguration(
                    average_count=request.average_count,
                    single_count=request.average_count,
                    channel_arithmetic=((1, "AVERAGE"), (2, "AVERAGE")),
                )
                if configured != expected:
                    raise DataError("average configuration readback mismatch")

                phase = "acquire"
                acquisition_started = True
                self.transport.write("SINGle")
                self.transport.query_opc()

                phase = "average-complete"
                average_complete = _parse_bool(
                    self.transport.query("ACQuire:AVERage:COMPlete?"),
                    command="ACQuire:AVERage:COMPlete?",
                )
                if not average_complete:
                    raise DataError("average acquisition did not complete")
                acquisition_completed = True

                phase = "read-waveforms"
                waveforms = tuple(
                    self._read_waveform(channel=channel, points="current")
                    for channel in request.channels
                )
            except Exception as exc:
                if wrote:
                    try:
                        self._restore_average_configuration_unlocked(
                            configuration_before
                        )
                        restored = self._average_configuration_unlocked()
                        if restored != configuration_before:
                            raise DataError("average configuration restore mismatch")
                    except Exception as restore_exc:
                        self._average_writes_blocked = True
                        raise RTM2000AverageCaptureError(
                            f"ambiguous RTM2032 average transaction during {phase}; "
                            "configuration restoration failed",
                            phase="restore",
                        ) from restore_exc
                if phase == "configure":
                    self._average_writes_blocked = True
                    raise RTM2000AverageCaptureError(
                        "RTM2032 average configuration write outcome is ambiguous; "
                        "configuration was restored but further average writes are blocked",
                        phase="write-uncertain",
                    ) from exc
                if acquisition_started and not acquisition_completed:
                    self._average_writes_blocked = True
                    raise RTM2000AverageCaptureError(
                        f"RTM2032 average capture failed during {phase}; "
                        "configuration was restored but acquisition state is unknown",
                        phase="acquisition-unknown",
                    ) from exc
                raise RTM2000AverageCaptureError(
                    f"RTM2032 average capture failed during {phase}; "
                    "configuration was restored",
                    phase=phase,
                ) from exc

            phase = "restore"
            try:
                self._restore_average_configuration_unlocked(configuration_before)
                configuration_after = self._average_configuration_unlocked()
                if configuration_after != configuration_before:
                    raise DataError("average configuration restore mismatch")
            except Exception as exc:
                self._average_writes_blocked = True
                raise RTM2000AverageCaptureError(
                    "average capture completed but configuration restoration is ambiguous",
                    phase=phase,
                ) from exc

            restored_fields = (
                "ACQuire:AVERage:COUNt",
                "ACQuire:NSINgle:COUNt",
                "CHANnel:ARITHmetics",
            )
            return ScopeAverageCaptureResult(
                request=request,
                waveforms=waveforms,
                average_complete=average_complete,
                configuration_before=configuration_before,
                configuration_after=configuration_after,
                restored_fields=restored_fields,
            )

    @_serialized_io
    def get_history_timestamps(self, channel: int) -> ScopeHistoryTimestamps:
        _validate_rtm2032_channel(channel)
        with self._io_lock:
            options = _parse_options(self.transport.query("*OPT?"))
            if not _has_option(options, "K15"):
                raise InstrumentError(
                    "RTM2000 history timestamps require installed option K15; "
                    "*OPT? did not report K15"
                )
            prefix = f"CHANnel{channel}:HISTORY"
            relatives = _parse_history_relative_times(
                self.transport.query(f"{prefix}:TSRelative:ALL?")
            )
            times = _parse_history_times(
                self.transport.query(f"{prefix}:TSABsolute:ALL?")
            )
            dates = _parse_history_dates(
                self.transport.query(f"{prefix}:TSDate:ALL?")
            )
            if not (len(relatives) == len(times) == len(dates)):
                raise DataError(
                    "RTM2000 history timestamp tables have inconsistent segment counts"
                )
            calendar_values = tuple(
                (*date_value, *time_value)
                for date_value, time_value in zip(dates, times)
            )
            if any(
                current > following
                for current, following in zip(calendar_values, calendar_values[1:])
            ):
                raise DataError("RTM2000 history timestamp tables are not oldest-to-newest")
            return ScopeHistoryTimestamps(
                channel=channel,
                entries=tuple(
                    ScopeHistoryTimestamp(
                        position=position,
                        relative_s=relative_s,
                        year=date_value[0],
                        month=date_value[1],
                        day=date_value[2],
                        hour=time_value[0],
                        minute=time_value[1],
                        second=time_value[2],
                    )
                    for position, (relative_s, date_value, time_value) in enumerate(
                        zip(relatives, dates, times),
                        start=1,
                    )
                ),
            )

    @_serialized_io
    def get_measurement_statistics(
        self,
        slot: int,
        *,
        configured_slot: bool,
        include_buffer: bool = False,
        acquisition_stopped: bool = False,
    ) -> ScopeMeasurementStatistics:
        if slot not in {1, 2, 3, 4}:
            raise ValueError("RTM2000 automatic measurement slot must be 1, 2, 3, or 4")
        if not configured_slot:
            raise ValueError(
                "reading an RTM2000 automatic measurement requires explicit confirmation "
                "that the slot is already configured"
            )
        if include_buffer and not acquisition_stopped:
            raise ValueError(
                "reading the RTM2000 statistics buffer requires explicit confirmation "
                "that acquisition is stopped"
            )
        prefix = f"MEASurement{slot}"
        with self._io_lock:
            category = _parse_token(
                self.transport.query(f"{prefix}:CATegory?"),
                command=f"{prefix}:CATegory?",
                allowed=frozenset({"AMPT", "AMPTIME"}),
            )
            fields = {
                "actual": f"{prefix}:RESult:ACTual?",
                "average": f"{prefix}:RESult:AVG?",
                "standard_deviation": f"{prefix}:RESult:STDDev?",
                "minimum": f"{prefix}:RESult:NPEak?",
                "maximum": f"{prefix}:RESult:PPEak?",
            }
            values = {
                name: _parse_optional_measurement_float(
                    self.transport.query(command),
                    command=command,
                )
                for name, command in fields.items()
            }
            waveform_count_command = f"{prefix}:RESult:WFMCount?"
            waveform_count = _parse_decimal_integer(
                self.transport.query(waveform_count_command),
                command=waveform_count_command,
                minimum=0,
            )
            buffered_values = None
            if include_buffer:
                buffer_command = f"{prefix}:STATistics:VALue:ALL?"
                fields_response = _parse_csv_fields(
                    self.transport.query(buffer_command),
                    command=buffer_command,
                )
                if len(fields_response) > 1000:
                    raise DataError(f"too many values in {buffer_command} response")
                buffered_values = tuple(
                    _parse_finite_float(value, command=buffer_command)
                    for value in fields_response
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

    @_serialized_io
    def get_math_waveform_metadata(self, math_index: int) -> ScopeDerivedWaveformMetadata:
        if math_index not in {1, 2, 3, 4}:
            raise ValueError("RTM2000 math waveform index must be 1, 2, 3, or 4")
        with self._io_lock:
            return _metadata_from_prefix(
                self.transport,
                prefix=f"CALCulate:MATH{math_index}:DATA",
                source_kind="math",
                index=math_index,
                source_catalog=None,
            )

    @_serialized_io
    def get_fft_status(
        self,
        math_index: int,
        *,
        configured_fft: bool,
    ) -> ScopeFftStatus:
        if math_index not in {1, 2, 3, 4}:
            raise ValueError("RTM2000 FFT math waveform index must be 1, 2, 3, or 4")
        if not configured_fft:
            raise ValueError(
                "reading RTM2000 FFT status requires explicit confirmation that the math "
                "waveform is already configured as FFT"
            )
        prefix = f"CALCulate:MATH{math_index}:FFT"
        with self._io_lock:
            return ScopeFftStatus(
                math_index=math_index,
                average_complete=_parse_bool(
                    self.transport.query(f"{prefix}:AVERAGE:COMPLETE?"),
                    command=f"{prefix}:AVERAGE:COMPLETE?",
                ),
                resolution_bandwidth_hz=_parse_positive_float(
                    self.transport.query(f"{prefix}:BANDwidth:RESolution:ADJusted?"),
                    command=f"{prefix}:BANDwidth:RESolution:ADJusted?",
                ),
                sample_rate_hz=_parse_positive_float(
                    self.transport.query(f"{prefix}:SRATe?"),
                    command=f"{prefix}:SRATe?",
                ),
            )

    @_serialized_io
    def get_reference_waveform_metadata(
        self,
        reference_index: int,
    ) -> ScopeDerivedWaveformMetadata:
        if reference_index not in {1, 2, 3, 4}:
            raise ValueError("RTM2000 reference waveform index must be 1, 2, 3, or 4")
        prefix = f"REFCurve{reference_index}"
        with self._io_lock:
            source_catalog = _parse_token(
                self.transport.query(f"{prefix}:SOURce:CATalog?"),
                command=f"{prefix}:SOURce:CATalog?",
            )
            return _metadata_from_prefix(
                self.transport,
                prefix=f"{prefix}:DATA",
                source_kind="reference",
                index=reference_index,
                source_catalog=source_catalog,
            )

    @_serialized_io
    def get_cursor_readout(
        self,
        cursor_index: int,
        *,
        configured_cursor: bool,
    ) -> ScopeCursorReadout:
        if cursor_index != 1:
            raise ValueError("RTM2000 cursor index must be 1")
        if not configured_cursor:
            raise ValueError(
                "reading an RTM2000 cursor requires explicit confirmation that it is "
                "already configured"
            )
        prefix = f"CURSor{cursor_index}"
        with self._io_lock:
            source = _parse_token(
                self.transport.query(f"{prefix}:SOURce?"),
                command=f"{prefix}:SOURce?",
            )
            function = _normalize_cursor_function(
                self.transport.query(f"{prefix}:FUNCTION?"),
                command=f"{prefix}:FUNCTION?",
            )
            fields: dict[str, float | None] = {
                "result": None,
                "x_delta_s": None,
                "inverse_x_delta_hz": None,
                "y_delta": None,
                "inverse_y_delta": None,
                "x_ratio": None,
                "y_ratio": None,
            }
            if function in _CURSOR_RESULT_FUNCTIONS:
                command = f"{prefix}:RESult?"
                fields["result"] = _parse_optional_measurement_float(
                    self.transport.query(command), command=command
                )
            elif function == "VERTICAL":
                x_command = f"{prefix}:XDELta:VALue?"
                inverse_command = f"{prefix}:XDELta:INVerse?"
                fields["x_delta_s"] = _parse_finite_float(
                    self.transport.query(x_command), command=x_command
                )
                fields["inverse_x_delta_hz"] = _parse_finite_float(
                    self.transport.query(inverse_command), command=inverse_command
                )
            elif function == "HORIZONTAL":
                y_command = f"{prefix}:YDELta:VALue?"
                inverse_command = f"{prefix}:YDELta:SLOPe?"
                fields["y_delta"] = _parse_finite_float(
                    self.transport.query(y_command), command=y_command
                )
                fields["inverse_y_delta"] = _parse_finite_float(
                    self.transport.query(inverse_command), command=inverse_command
                )
            elif function == "PAIRED":
                x_command = f"{prefix}:XDELta:VALue?"
                y_command = f"{prefix}:YDELta:VALue?"
                fields["x_delta_s"] = _parse_finite_float(
                    self.transport.query(x_command), command=x_command
                )
                fields["y_delta"] = _parse_finite_float(
                    self.transport.query(y_command), command=y_command
                )
            elif function == "VRATIO":
                command = f"{prefix}:XRATio:VALue?"
                fields["x_ratio"] = _parse_finite_float(
                    self.transport.query(command), command=command
                )
            elif function == "HRATIO":
                command = f"{prefix}:YRATio:VALue?"
                fields["y_ratio"] = _parse_finite_float(
                    self.transport.query(command), command=command
                )
            else:
                raise DataError(f"unsupported RTM2000 cursor function {function!r}")
            return ScopeCursorReadout(
                cursor_index=cursor_index,
                source=source,
                function=function,
                **fields,
            )

    @_serialized_io
    def get_snapshot(self, channel: int) -> ScopeSnapshot:
        _validate_rtm2032_channel(channel)
        with self._io_lock:
            return ScopeSnapshot(
                identity=self.identity_snapshot(),
                health=self.health_snapshot(),
                channel=self.analog_channel_snapshot(channel),
                timebase=self.timebase_snapshot(),
                probe=self.probe_snapshot(channel),
                waveform=self.waveform_metadata_snapshot(channel),
                trigger=self.edge_trigger_snapshot(),
            )

    @_serialized_io
    def health_snapshot(self) -> RTM2000HealthSnapshot:
        with self._io_lock:
            status_byte = _parse_decimal_integer(
                self.transport.query("*STB?"),
                command="*STB?",
                minimum=0,
                maximum=0xFF,
            )
            operation_condition = _parse_decimal_integer(
                self.transport.query("STATUS:OPERation:CONDITION?"),
                command="STATUS:OPERation:CONDITION?",
                minimum=0,
                maximum=0xFFFF,
            )
            questionable_condition = _parse_decimal_integer(
                self.transport.query("STATUS:QUESTIONable:CONDITION?"),
                command="STATUS:QUESTIONable:CONDITION?",
                minimum=0,
                maximum=0xFFFF,
            )
            acquisition_available = _parse_decimal_integer(
                self.transport.query("ACQuire:AVAilable?"),
                command="ACQuire:AVAilable?",
                minimum=0,
            )
            acquisition_count = _parse_decimal_integer(
                self.transport.query("ACQuire:COUNT?"),
                command="ACQuire:COUNT?",
                minimum=0,
            )
            sample_rate_hz = _parse_positive_float(
                self.transport.query("ACQuire:SRATe?"),
                command="ACQuire:SRATe?",
            )
            return RTM2000HealthSnapshot(
                status_byte=status_byte,
                operation_condition=operation_condition,
                questionable_condition=questionable_condition,
                acquisition_available=acquisition_available,
                acquisition_count=acquisition_count,
                sample_rate_hz=sample_rate_hz,
                error_queue_nonempty=bool(status_byte & (1 << 2)),
                waiting_for_trigger=bool(operation_condition & (1 << 3)),
            )

    @_serialized_io
    def analog_channel_snapshot(self, channel: int) -> RTM2000AnalogChannelSnapshot:
        _validate_rtm2032_channel(channel)
        prefix = f"CHANnel{channel}"
        enabled = _parse_bool(
            self.transport.query(f"{prefix}:STATE?"),
            command=f"{prefix}:STATE?",
        )
        coupling = _parse_token(
            self.transport.query(f"{prefix}:COUPling?"),
            command=f"{prefix}:COUPling?",
            allowed=frozenset({"AC", "ACL", "DC", "DCL", "GND"}),
        )
        range_v = _parse_positive_float(
            self.transport.query(f"{prefix}:RANGE?"),
            command=f"{prefix}:RANGE?",
        )
        scale_v_per_div = _parse_positive_float(
            self.transport.query(f"{prefix}:SCALe?"),
            command=f"{prefix}:SCALe?",
        )
        offset_v = _parse_finite_float(
            self.transport.query(f"{prefix}:OFFSET?"),
            command=f"{prefix}:OFFSET?",
        )
        position_div = _parse_finite_float(
            self.transport.query(f"{prefix}:POSITION?"),
            command=f"{prefix}:POSITION?",
        )
        bandwidth_response = self.transport.query(f"{prefix}:BANDwidth?")
        bandwidth_hz = (
            None
            if bandwidth_response.strip().upper() == "FULL"
            else _parse_positive_float(
                bandwidth_response,
                command=f"{prefix}:BANDwidth?",
            )
        )
        polarity = _parse_token(
            self.transport.query(f"{prefix}:POLarity?"),
            command=f"{prefix}:POLarity?",
            allowed=frozenset({"NORM", "INV"}),
        )
        skew_s = _parse_finite_float(
            self.transport.query(f"{prefix}:SKEW?"),
            command=f"{prefix}:SKEW?",
        )
        label = _parse_quoted_text(
            self.transport.query(f"{prefix}:LABel?"),
            command=f"{prefix}:LABel?",
        )
        label_enabled = _parse_bool(
            self.transport.query(f"{prefix}:LABel:STATE?"),
            command=f"{prefix}:LABel:STATE?",
        )
        overloaded = _parse_bool(
            self.transport.query(f"{prefix}:OVERload?"),
            command=f"{prefix}:OVERload?",
        )
        acquisition_type = _parse_token(
            self.transport.query(f"{prefix}:TYPE?"),
            command=f"{prefix}:TYPE?",
        )
        return RTM2000AnalogChannelSnapshot(
            channel=channel,
            enabled=enabled,
            coupling=coupling,
            range_v=range_v,
            scale_v_per_div=scale_v_per_div,
            offset_v=offset_v,
            position_div=position_div,
            bandwidth_hz=bandwidth_hz,
            polarity=polarity,
            skew_s=skew_s,
            label=label,
            label_enabled=label_enabled,
            overloaded=overloaded,
            acquisition_type=acquisition_type,
        )

    @_serialized_io
    def timebase_snapshot(self) -> RTM2000TimebaseSnapshot:
        return RTM2000TimebaseSnapshot(
            acquisition_time_s=_parse_positive_float(
                self.transport.query("TIMebase:ACQTime?"),
                command="TIMebase:ACQTime?",
            ),
            divisions=_parse_decimal_integer(
                self.transport.query("TIMebase:DIVisions?"),
                command="TIMebase:DIVisions?",
                minimum=1,
                maximum=100,
            ),
            position_s=_parse_finite_float(
                self.transport.query("TIMebase:POSition?"),
                command="TIMebase:POSition?",
            ),
            range_s=_parse_positive_float(
                self.transport.query("TIMebase:RANGE?"),
                command="TIMebase:RANGE?",
            ),
            reference_percent=_parse_bounded_float(
                self.transport.query("TIMebase:REFerence?"),
                command="TIMebase:REFerence?",
                minimum=0.0,
                maximum=100.0,
            ),
            scale_s_per_div=_parse_positive_float(
                self.transport.query("TIMebase:SCALe?"),
                command="TIMebase:SCALe?",
            ),
            roll_enabled=_parse_bool(
                self.transport.query("TIMebase:ROLL:ENABLE?"),
                command="TIMebase:ROLL:ENABLE?",
            ),
        )

    @_serialized_io
    def probe_snapshot(self, channel: int) -> RTM2000ProbeSnapshot:
        _validate_rtm2032_channel(channel)
        prefix = f"PROBe{channel}:SETup"
        attenuation_factor = _parse_positive_float(
            self.transport.query(f"{prefix}:ATTenuation:AUTO?"),
            command=f"{prefix}:ATTenuation:AUTO?",
        )
        bandwidth_hz = _parse_optional_positive_float(
            self.transport.query(f"{prefix}:BANDwidth?"),
            command=f"{prefix}:BANDwidth?",
        )
        capacitance_f = _parse_optional_positive_float(
            self.transport.query(f"{prefix}:CAPacitance?"),
            command=f"{prefix}:CAPacitance?",
        )
        impedance_response = self.transport.query(f"{prefix}:IMPedance?").strip()
        impedance_ohm = (
            None
            if impedance_response.upper() == "UNKN"
            else _parse_optional_positive_float(
                impedance_response,
                command=f"{prefix}:IMPedance?",
            )
        )
        name = _parse_quoted_text(
            self.transport.query(f"{prefix}:NAME?"),
            command=f"{prefix}:NAME?",
        )
        probe_type = _parse_token(
            self.transport.query(f"{prefix}:TYPE?"),
            command=f"{prefix}:TYPE?",
        )
        return RTM2000ProbeSnapshot(
            channel=channel,
            attenuation_factor=attenuation_factor,
            bandwidth_hz=bandwidth_hz,
            capacitance_f=capacitance_f,
            impedance_ohm=impedance_ohm,
            name=name,
            probe_type=probe_type,
        )

    @_serialized_io
    def waveform_metadata_snapshot(
        self,
        channel: int,
    ) -> RTM2000WaveformMetadataSnapshot:
        _validate_rtm2032_channel(channel)
        prefix = f"CHANnel{channel}:DATA"
        header, values_per_sample = _parse_waveform_header_response(
            self.transport.query(f"{prefix}:HEADer?")
        )
        points = _parse_decimal_integer(
            self.transport.query(f"{prefix}:POINTs?"),
            command=f"{prefix}:POINTs?",
            minimum=1,
        )
        if points != header.points:
            raise DataError(
                "waveform metadata point count mismatch: "
                f"header says {header.points}, POINTs? returned {points}"
            )
        x_increment_s = _parse_positive_float(
            self.transport.query(f"{prefix}:XINCrement?"),
            command=f"{prefix}:XINCrement?",
        )
        x_origin_s = _parse_finite_float(
            self.transport.query(f"{prefix}:XORigin?"),
            command=f"{prefix}:XORigin?",
        )
        x_tolerance_s = max(x_increment_s * 1e-6, 1e-15)
        expected_x_stop_s = x_origin_s + (points - 1) * x_increment_s
        if not math.isclose(
            x_origin_s,
            header.x_start,
            rel_tol=0.0,
            abs_tol=x_tolerance_s,
        ) or not math.isclose(
            expected_x_stop_s,
            header.x_stop,
            rel_tol=0.0,
            abs_tol=x_tolerance_s,
        ):
            raise DataError(
                "waveform metadata x-axis mismatch between DATA:HEADER, "
                "XINCrement, and XORigin"
            )
        return RTM2000WaveformMetadataSnapshot(
            channel=channel,
            x_start_s=header.x_start,
            x_stop_s=header.x_stop,
            points=header.points,
            values_per_sample=values_per_sample,
            x_increment_s=x_increment_s,
            x_origin_s=x_origin_s,
            y_increment_v=_parse_positive_float(
                self.transport.query(f"{prefix}:YINCrement?"),
                command=f"{prefix}:YINCrement?",
            ),
            y_origin_v=_parse_finite_float(
                self.transport.query(f"{prefix}:YORigin?"),
                command=f"{prefix}:YORigin?",
            ),
            y_resolution_bits=_parse_decimal_integer(
                self.transport.query(f"{prefix}:YRESolution?"),
                command=f"{prefix}:YRESolution?",
                minimum=1,
                maximum=64,
            ),
        )

    @_serialized_io
    def edge_trigger_snapshot(self) -> RTM2000EdgeTriggerSnapshot:
        with self._io_lock:
            return self._edge_trigger_snapshot_unlocked()

    def _edge_trigger_snapshot_unlocked(self) -> RTM2000EdgeTriggerSnapshot:
        trigger_type = _parse_token(
            self.transport.query("TRIGger:A:TYPE?"),
            command="TRIGger:A:TYPE?",
            allowed=frozenset({"EDGE"}),
        )
        source = _parse_token(
            self.transport.query("TRIGger:A:SOURce?"),
            command="TRIGger:A:SOURce?",
            allowed=frozenset({"CH1", "CH2"}),
        )
        source_channel = int(source.removeprefix("CH"))
        mode = _parse_token(
            self.transport.query("TRIGger:A:MODE?"),
            command="TRIGger:A:MODE?",
            allowed=frozenset({"AUTO"}),
        )
        slope = _parse_token(
            self.transport.query("TRIGger:A:EDGE:SLOPe?"),
            command="TRIGger:A:EDGE:SLOPe?",
            allowed=frozenset({"POS"}),
        )
        coupling = _parse_token(
            self.transport.query("TRIGger:A:EDGE:COUpling?"),
            command="TRIGger:A:EDGE:COUpling?",
            allowed=frozenset({"DC"}),
        )
        level_command = f"TRIGger:A:LEVel{source_channel}?"
        level_v = _parse_finite_float(
            self.transport.query(level_command),
            command=level_command,
        )
        hysteresis_mode = _parse_token(
            self.transport.query("TRIGger:A:HYSTEResis?"),
            command="TRIGger:A:HYSTEResis?",
            allowed=frozenset({"AUTO"}),
        )
        holdoff_mode = _parse_token(
            self.transport.query("TRIGger:A:HOLDoff:MODE?"),
            command="TRIGger:A:HOLDoff:MODE?",
            allowed=frozenset({"OFF"}),
        )
        holdoff_time_s = _parse_positive_float(
            self.transport.query("TRIGger:A:HOLDoff:TIME?"),
            command="TRIGger:A:HOLDoff:TIME?",
        )
        return RTM2000EdgeTriggerSnapshot(
            trigger_type=trigger_type,
            source_channel=source_channel,
            mode=mode,
            slope=slope,
            coupling=coupling,
            level_v=level_v,
            hysteresis_mode=hysteresis_mode,
            holdoff_mode=holdoff_mode,
            holdoff_time_s=holdoff_time_s,
        )

    @property
    def trigger_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._trigger_writes_blocked

    def configure_ch2_edge_trigger(
        self,
        *,
        level_v: float,
    ) -> RTM2000EdgeTriggerSnapshot:
        if (
            isinstance(level_v, bool)
            or not isinstance(level_v, Real)
            or not math.isfinite(float(level_v))
        ):
            raise DataError("CH2 edge-trigger level must be finite")
        level_v = float(level_v)
        with self._io_lock:
            if self._trigger_writes_blocked:
                raise RTM2000TriggerControlError(
                    "trigger writes are blocked after an earlier ambiguous write",
                    phase="blocked",
                )
            identity_before = self.identity_snapshot()
            health_before = self.health_snapshot()
            trigger_before = self._edge_trigger_snapshot_unlocked()
            channel_before = self.analog_channel_snapshot(2)
            if identity_before.model.upper() != "RTM2032":
                raise RTM2000TriggerControlError(
                    "controlled trigger writes require an RTM2032 identity",
                    phase="preflight",
                )
            if health_before.error_queue_nonempty or health_before.questionable_condition:
                raise RTM2000TriggerControlError(
                    "instrument health is not clean before trigger write",
                    phase="preflight",
                )
            if trigger_before.source_channel != 2:
                raise RTM2000TriggerControlError(
                    "controlled trigger writes require the existing CH2 baseline",
                    phase="preflight",
                )
            if (
                not channel_before.enabled
                or channel_before.coupling not in {"DCL", "ACL"}
                or channel_before.overloaded
            ):
                raise RTM2000TriggerControlError(
                    "controlled trigger writes require enabled, high-impedance, non-overloaded CH2",
                    phase="preflight",
                )
            visible_min_v = channel_before.offset_v - channel_before.range_v / 2.0
            visible_max_v = channel_before.offset_v + channel_before.range_v / 2.0
            if level_v < visible_min_v or level_v > visible_max_v:
                raise RTM2000TriggerControlError(
                    "requested trigger level is outside the current CH2 range",
                    phase="preflight",
                )

            commands = (
                "TRIGger:A:TYPE EDGE",
                "TRIGger:A:SOURce CH2",
                "TRIGger:A:MODE AUTO",
                "TRIGger:A:EDGE:SLOPe POS",
                "TRIGger:A:EDGE:COUpling DC",
                f"TRIGger:A:LEVel2 {level_v:.12g}",
            )
            phase = "write"
            try:
                for command in commands:
                    self.transport.write(command)
                phase = "readback"
                trigger_after = self._edge_trigger_snapshot_unlocked()
                if (
                    trigger_after.trigger_type != "EDGE"
                    or trigger_after.source_channel != 2
                    or trigger_after.mode != "AUTO"
                    or trigger_after.slope != "POS"
                    or trigger_after.coupling != "DC"
                    or not math.isclose(
                        trigger_after.level_v,
                        level_v,
                        rel_tol=1e-9,
                        abs_tol=1e-12,
                    )
                    or trigger_after.hysteresis_mode != trigger_before.hysteresis_mode
                    or trigger_after.holdoff_mode != trigger_before.holdoff_mode
                    or trigger_after.holdoff_time_s != trigger_before.holdoff_time_s
                ):
                    raise DataError("trigger readback does not match requested CH2 edge state")
                phase = "health-postcheck"
                health_after = self.health_snapshot()
                if health_after.error_queue_nonempty or health_after.questionable_condition:
                    raise DataError("instrument health changed after trigger write")
                phase = "identity-postcheck"
                if self.identity_snapshot() != identity_before:
                    raise DataError("instrument identity changed after trigger write")
                return trigger_after
            except Exception as exc:
                self._trigger_writes_blocked = True
                raise RTM2000TriggerControlError(
                    f"ambiguous RTM2032 trigger write during {phase}",
                    phase=phase,
                ) from exc

    @_serialized_io
    def clear_status(self) -> None:
        self.transport.write("*CLS")

    @_serialized_io
    def channel_coupling(self, channel: int) -> str:
        if channel < 1:
            raise DataError("channel must be >= 1")
        return self.transport.query(f"CHAN{channel}:COUP?").strip().upper()

    @_serialized_io
    def errors(self, limit: int = 16) -> list[str]:
        errors: list[str] = []
        for _ in range(limit):
            response = self.transport.query("SYST:ERR?")
            errors.append(response)
            if response.startswith("0") or "No error" in response:
                break
        return errors

    @_serialized_io
    def assert_no_errors(self) -> None:
        errors = self.errors()
        active = [
            item
            for item in errors
            if not (item.startswith("0") or "No error" in item)
        ]
        if active:
            raise InstrumentError("instrument error queue is not empty: " + "; ".join(active))

    @_serialized_io
    def autoscale(self, wait_opc: bool = True, check_errors: bool = True) -> None:
        self.transport.write("AUToscale")
        if wait_opc:
            self.transport.query_opc()
        if check_errors:
            self.assert_no_errors()

    @_serialized_io
    def set_time_range(self, time_range_s: float) -> None:
        if time_range_s <= 0:
            raise DataError("time range must be > 0")
        self.transport.write(f"TIMebase:RANGe {time_range_s:.12g}")

    @_serialized_io
    def set_vertical_scale(self, channel: int, scale_v_per_div: float) -> None:
        if channel < 1:
            raise DataError("channel must be >= 1")
        if scale_v_per_div <= 0:
            raise DataError("vertical scale must be > 0")
        self.transport.write(f"CHAN{channel}:STAT ON")
        self.transport.write(f"CHAN{channel}:SCAL {scale_v_per_div:.12g}")
        self.transport.write(f"CHAN{channel}:POS 0")

    def _setup_real_waveform_transfer(self, channel: int, points: str) -> None:
        if channel < 1:
            raise DataError("channel must be >= 1")
        self.transport.write(f"CHAN{channel}:STAT ON")
        self.transport.write("FORM REAL")
        self.transport.write("FORM:BORD LSBF")
        self.transport.write(f"CHAN:DATA:POIN {points.upper()}")

    def _read_waveform(self, channel: int, points: str) -> WaveformData:
        header = parse_waveform_header(
            self.transport.query(f"CHAN{channel}:DATA:HEAD?")
        )
        point_mode = points.strip().upper()
        transfer_timeout_ms = (
            self.long_waveform_timeout_ms
            if point_mode in {"MAX", "DMAX"}
            else None
        )
        started = time.perf_counter()
        voltages = np.asarray(
            self.transport.query_float_list(
                f"CHAN{channel}:DATA?",
                timeout_ms=transfer_timeout_ms,
            ),
            dtype=np.float64,
        )
        elapsed_s = max(time.perf_counter() - started, 0.0)
        self.transport.record_event(
            "telemetry",
            " ".join(
                (
                    "operation=rtm2000_waveform",
                    f"point_mode={point_mode}",
                    f"points={voltages.size}",
                    f"elapsed_ms={elapsed_s * 1000.0:.3f}",
                )
            ),
        )
        if voltages.size != header.points:
            raise DataError(
                f"waveform length mismatch: header says {header.points}, "
                f"got {voltages.size}"
            )
        return WaveformData(channel=channel, header=header, voltages_v=voltages)

    @_serialized_io
    def fetch_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
    ) -> WaveformData:
        self._setup_real_waveform_transfer(channel=channel, points=points)
        waveform = self._read_waveform(channel=channel, points=points)
        if check_errors:
            self.assert_no_errors()
        return waveform

    @_serialized_io
    def capture_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
    ) -> WaveformData:
        self.transport.write("*CLS")
        if time_range_s is not None:
            self.set_time_range(time_range_s)
        if vertical_scale_v_per_div is not None:
            self.set_vertical_scale(channel, vertical_scale_v_per_div)
        self._setup_real_waveform_transfer(channel=channel, points=points)
        self.transport.write("SINGle")
        try:
            self.transport.query_opc()
        except Exception as exc:
            raise OperationTimeout(
                "single acquisition timed out while waiting for *OPC?. "
                "Check trigger source/level, or use `scope fetch` to read the current waveform."
            ) from exc
        waveform = self._read_waveform(channel=channel, points=points)
        if check_errors:
            self.assert_no_errors()
        return waveform

    @_serialized_io
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
        self.transport.write("*CLS")
        if time_range_s is not None:
            self.set_time_range(time_range_s)
        for channel in channels:
            if channel < 1:
                raise DataError("channel must be >= 1")
            if vertical_scale_v_per_div is not None:
                self.set_vertical_scale(channel, vertical_scale_v_per_div)
            else:
                self.transport.write(f"CHAN{channel}:STAT ON")
            state = self.transport.query(f"CHAN{channel}:STAT?").strip().upper()
            if state not in {"1", "ON"}:
                raise DataError(
                    f"channel {channel} did not become active before single acquisition: "
                    f"CHAN{channel}:STAT? returned {state!r}"
                )
        self.transport.write("SINGle")
        try:
            self.transport.query_opc()
        except Exception as exc:
            raise OperationTimeout(
                "single acquisition timed out while waiting for *OPC?. "
                "Check trigger source/level, or use `scope fetch` to read the current waveform."
            ) from exc
        waveforms: dict[int, WaveformData] = {}
        for channel in channels:
            if on_channel_start is not None:
                on_channel_start(channel)
            self._setup_real_waveform_transfer(channel=channel, points=points)
            waveform = self._read_waveform(channel=channel, points=points)
            waveforms[channel] = waveform
            if on_waveform is not None:
                on_waveform(channel, waveform)
        if check_errors:
            if on_channel_start is not None:
                on_channel_start(None)
            self.assert_no_errors()
        return waveforms

    @_serialized_io
    def screenshot_png(
        self,
        *,
        include_menu: bool = False,
        color_scheme: str = "COL",
    ) -> bytes:
        self.transport.write("HCOP:LANG PNG")
        self.transport.write(f"HCOP:COL:SCH {color_scheme}")
        self.transport.write(f"HCOP:MENU {'ON' if include_menu else 'OFF'}")
        data = self.transport.query_bin_block("HCOP:DATA?")
        if not data.startswith(b"\x89PNG\r\n\x1a\n"):
            raise DataError("screenshot response is not a PNG image")
        return data

    @_serialized_io
    def close(self) -> None:
        with self._io_lock:
            self.transport.close()
