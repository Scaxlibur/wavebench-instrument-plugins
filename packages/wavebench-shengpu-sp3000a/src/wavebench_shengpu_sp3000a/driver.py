from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import re
from typing import Literal

from wavebench.errors import DataError, InstrumentError
from wavebench.transport.base import InstrumentTransport


_EXPECTED_IDN = "SHENGPU SP3000 Series Digital Sweeper"
_PRIVATE_ERRORS = {
    "ERRORNO00": ("ERRORNo00", "command format error"),
    "ERRORNO01": ("ERRORNo01", "command invalid in the current state"),
    "ERRORNO02": ("ERRORNo02", "input value out of range"),
    "ERRORNO03": ("ERRORNo03", "zero value is not allowed"),
    "ERRORNO04": ("ERRORNo04", "negative value is not allowed"),
    "ERRORNO05": ("ERRORNo05", "invalid floating-point format"),
    "ERRORNO06": ("ERRORNo06", "digits are not allowed after leading zero"),
    "ERRORNO07": ("ERRORNo07", "no valid input data"),
    "ERRORNO08": ("ERRORNo08", "input value has too many digits"),
}


class SP30120ProtocolError(InstrumentError):
    """Deterministic, non-retryable error reported by the SP30120 firmware."""

    retryable = False

    def __init__(self, *, code: str, command: str, detail: str) -> None:
        self.code = code
        self.command = command
        super().__init__(f"SP30120 protocol error {code} for {command}: {detail}")


@dataclass(frozen=True)
class SP30120ScalarStatus:
    rf_output_enabled: bool
    source_impedance_ohm: int
    center_frequency_hz: float
    span_frequency_hz: float
    start_frequency_hz: float
    stop_frequency_hz: float
    cw_frequency_hz: float
    frequency_offset_hz: float
    sweep_time_s: float
    sweep_axis: Literal["linear", "logarithmic"]
    acquisition: Literal["single", "continuous"]
    external_trigger_enabled: bool
    input_impedance: Literal[50, 75, "highz"]

    def __post_init__(self) -> None:
        positive = (
            self.center_frequency_hz,
            self.span_frequency_hz,
            self.start_frequency_hz,
            self.stop_frequency_hz,
            self.cw_frequency_hz,
            self.sweep_time_s,
        )
        if any(not isfinite(value) or value <= 0 for value in positive):
            raise ValueError("SP30120 positive scalar status values must be finite and > 0")
        if not isfinite(self.frequency_offset_hz):
            raise ValueError("SP30120 frequency offset must be finite")
        if self.start_frequency_hz >= self.stop_frequency_hz:
            raise ValueError("SP30120 start frequency must be below stop frequency")
        if self.source_impedance_ohm not in {50, 75}:
            raise ValueError("SP30120 source impedance must be 50 or 75 ohms")
        if self.input_impedance not in {50, 75, "highz"}:
            raise ValueError("SP30120 input impedance must be 50, 75, or highz")


def _response_text(response: str, command: str) -> str:
    value = response.strip()
    if not value:
        raise DataError(f"SP30120 returned an empty response for {command}")
    normalized = value.upper()
    if normalized in _PRIVATE_ERRORS:
        code, detail = _PRIVATE_ERRORS[normalized]
        raise SP30120ProtocolError(
            code=code,
            command=command,
            detail=detail,
        )
    if normalized == "ERROR":
        raise SP30120ProtocolError(
            code="undocumented_error",
            command=command,
            detail="device returned undocumented Error",
        )
    return value


def _parse_float(response: str, command: str, *, positive: bool = False) -> float:
    value = _response_text(response, command)
    try:
        parsed = float(value)
    except ValueError as exc:
        raise DataError(f"invalid SP30120 numeric response for {command}: {value!r}") from exc
    if not isfinite(parsed) or (positive and parsed <= 0):
        qualifier = "finite and > 0" if positive else "finite"
        raise DataError(f"SP30120 response for {command} must be {qualifier}: {value!r}")
    return parsed


def _parse_pair(response: str, command: str) -> tuple[float, float]:
    parts = [item.strip() for item in _response_text(response, command).split(",")]
    if len(parts) != 2:
        raise DataError(f"invalid SP30120 pair response for {command}: {response!r}")
    return (
        _parse_float(parts[0], command, positive=True),
        _parse_float(parts[1], command, positive=True),
    )


def _parse_enum(response: str, command: str, values: set[str]) -> str:
    value = _response_text(response, command).upper()
    if value not in values:
        expected = ", ".join(sorted(values))
        raise DataError(
            f"invalid SP30120 response for {command}: {value!r}; expected {expected}"
        )
    return value


def _parse_impedance(response: str, command: str) -> int:
    value = _parse_float(response, command, positive=True)
    if value not in {50.0, 75.0}:
        raise DataError(f"unsupported SP30120 verified impedance for {command}: {value:g}")
    return int(value)


def _parse_input_impedance(response: str, command: str) -> Literal[50, 75, "highz"]:
    value = _response_text(response, command).upper()
    if value == "HIGHZ":
        return "highz"
    return _parse_impedance(value, command)


def _normalized_idn(response: str) -> str:
    return re.sub(r"\s+", " ", response.strip().rstrip(".")).casefold()


@dataclass
class SP30120SweepAnalyzer:
    transport: InstrumentTransport

    def idn(self) -> str:
        response = _response_text(self.transport.query("*IDN?"), "*IDN?")
        if _normalized_idn(response) != _normalized_idn(_EXPECTED_IDN):
            raise DataError(
                "SP30120 family identity mismatch: the response did not match the "
                "verified SP3000-family identity (response details redacted)"
            )
        return response

    def read_scalar_status(self) -> SP30120ScalarStatus:
        rf = _parse_enum(self.transport.query("RFSTAT?"), "RFSTAT?", {"ON", "OFF"})
        source_impedance = _parse_impedance(
            self.transport.query("OUTOHMSEL?"), "OUTOHMSEL?"
        )
        center, span = _parse_pair(self.transport.query("CENS?"), "CENS?")
        start, stop = _parse_pair(self.transport.query("STAS?"), "STAS?")
        cw = _parse_float(self.transport.query("CWFREQ?"), "CWFREQ?", positive=True)
        offset = _parse_float(self.transport.query("FREQOFFSET?"), "FREQOFFSET?")
        sweep_time = _parse_float(self.transport.query("SWET?"), "SWET?", positive=True)
        axis_raw = _parse_enum(
            self.transport.query("SWET:MODE?"), "SWET:MODE?", {"LIN", "LOG"}
        )
        acquisition_raw = _parse_enum(
            self.transport.query("TRIM?"), "TRIM?", {"CONT", "SING"}
        )
        trigger_raw = _parse_enum(self.transport.query("EXTT?"), "EXTT?", {"OFF", "ONSWEE"})
        input_impedance = _parse_input_impedance(self.transport.query("INPZ?"), "INPZ?")
        return SP30120ScalarStatus(
            rf_output_enabled=rf == "ON",
            source_impedance_ohm=source_impedance,
            center_frequency_hz=center,
            span_frequency_hz=span,
            start_frequency_hz=start,
            stop_frequency_hz=stop,
            cw_frequency_hz=cw,
            frequency_offset_hz=offset,
            sweep_time_s=sweep_time,
            sweep_axis="linear" if axis_raw == "LIN" else "logarithmic",
            acquisition="continuous" if acquisition_raw == "CONT" else "single",
            external_trigger_enabled=trigger_raw == "ONSWEE",
            input_impedance=input_impedance,
        )

    def close(self) -> None:
        self.transport.close()
