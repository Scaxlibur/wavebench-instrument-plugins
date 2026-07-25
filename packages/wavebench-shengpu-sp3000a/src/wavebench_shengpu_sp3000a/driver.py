from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isfinite
import re
from threading import RLock
from typing import Callable, Literal, TypeVar

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


class SP30120ControlError(InstrumentError):
    """Non-retryable failure from a certified RF-off control transaction."""

    retryable = False

    def __init__(
        self,
        *,
        phase: str,
        command: str,
        detail: str,
        state_uncertain: bool,
    ) -> None:
        self.phase = phase
        self.command = command
        self.state_uncertain = state_uncertain
        super().__init__(
            f"SP30120 certified control failed during {phase} for {command}: {detail}"
        )


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


SweepExecution = Literal["continuous", "single"]
ReferencePosition = Literal[4, 5]
ClockDisplay = Literal["on", "off"]
UiLanguage = Literal["chinese", "english"]
ExternalTrigger = Literal["off", "on_sweep"]
CertifiedStatusUpdate = Literal["none", "trim", "external-trigger"]


@dataclass(frozen=True)
class SP30120CertifiedControls:
    trim: SweepExecution
    reference_position: ReferencePosition
    clock_display: ClockDisplay
    ui_language: UiLanguage
    external_trigger: ExternalTrigger


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


def _parse_reference_position(response: str) -> ReferencePosition:
    value = _response_text(response, "SETREFP?")
    if value == "4":
        return 4
    if value == "5":
        return 5
    raise DataError(
        "unsupported SP30120 certified reference position; expected 4 or 5"
    )


_ControlValue = TypeVar("_ControlValue")


@dataclass
class SP30120SweepAnalyzer:
    transport: InstrumentTransport
    _control_lock: RLock = field(
        default_factory=RLock,
        init=False,
        repr=False,
        compare=False,
    )
    _control_writes_blocked: bool = field(default=False, init=False, repr=False)

    def idn(self) -> str:
        with self._control_lock:
            response = _response_text(self.transport.query("*IDN?"), "*IDN?")
            if _normalized_idn(response) != _normalized_idn(_EXPECTED_IDN):
                raise DataError(
                    "SP30120 family identity mismatch: the response did not match the "
                    "verified SP3000-family identity (response details redacted)"
                )
            return response

    def read_scalar_status(self) -> SP30120ScalarStatus:
        with self._control_lock:
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
            trigger_raw = _parse_enum(
                self.transport.query("EXTT?"), "EXTT?", {"OFF", "ONSWEE"}
            )
            input_impedance = _parse_input_impedance(
                self.transport.query("INPZ?"), "INPZ?"
            )
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

    @property
    def control_writes_blocked(self) -> bool:
        """Whether a write-side ambiguity has locked this driver instance."""

        with self._control_lock:
            return self._control_writes_blocked

    def read_trim(self) -> SweepExecution:
        with self._control_lock:
            value = _parse_enum(self.transport.query("TRIM?"), "TRIM?", {"CONT", "SING"})
            return "continuous" if value == "CONT" else "single"

    def read_reference_position(self) -> ReferencePosition:
        with self._control_lock:
            return _parse_reference_position(self.transport.query("SETREFP?"))

    def read_clock_display(self) -> ClockDisplay:
        with self._control_lock:
            value = _parse_enum(
                self.transport.query("CLOCKSW?"), "CLOCKSW?", {"ON", "OFF"}
            )
            return "on" if value == "ON" else "off"

    def read_ui_language(self) -> UiLanguage:
        with self._control_lock:
            value = _parse_enum(
                self.transport.query("LANGSEL?"),
                "LANGSEL?",
                {"CHINESE", "ENGLISH"},
            )
            return "chinese" if value == "CHINESE" else "english"

    def read_external_trigger(self) -> ExternalTrigger:
        with self._control_lock:
            value = _parse_enum(
                self.transport.query("EXTT?"),
                "EXTT?",
                {"OFF", "ONSWEE"},
            )
            return "off" if value == "OFF" else "on_sweep"

    def read_certified_controls(self) -> SP30120CertifiedControls:
        with self._control_lock:
            return SP30120CertifiedControls(
                trim=self.read_trim(),
                reference_position=self.read_reference_position(),
                clock_display=self.read_clock_display(),
                ui_language=self.read_ui_language(),
                external_trigger=self.read_external_trigger(),
            )

    def _read_rf_output_enabled(self) -> bool:
        value = _parse_enum(self.transport.query("RFSTAT?"), "RFSTAT?", {"ON", "OFF"})
        return value == "ON"

    def _set_certified_control(
        self,
        *,
        command: str,
        target: _ControlValue,
        readback: Callable[[], _ControlValue],
        status_update: CertifiedStatusUpdate = "none",
    ) -> _ControlValue:
        with self._control_lock:
            if self._control_writes_blocked:
                raise SP30120ControlError(
                    phase="latched",
                    command=command,
                    detail=(
                        "this driver instance observed an uncertain write outcome; "
                        "close it and independently verify the instrument before reopening"
                    ),
                    state_uncertain=True,
                )

            self.idn()
            if self._read_rf_output_enabled():
                raise SP30120ControlError(
                    phase="preflight",
                    command=command,
                    detail="RF output must be independently observed OFF before any write",
                    state_uncertain=False,
                )

            before_status = self.read_scalar_status()
            if before_status.rf_output_enabled:
                raise SP30120ControlError(
                    phase="preflight",
                    command=command,
                    detail="RF output changed from OFF during the preflight fingerprint",
                    state_uncertain=False,
                )
            readback()
            phase = "write"
            try:
                self.transport.write(command)
                phase = "readback"
                observed = readback()
                if observed != target:
                    raise DataError(
                        "SP30120 certified control readback did not match the requested value"
                    )

                phase = "rf-postcheck"
                if self._read_rf_output_enabled():
                    raise DataError("SP30120 RF output was not OFF after the control write")

                phase = "fingerprint-postcheck"
                after_status = self.read_scalar_status()
                if status_update == "none":
                    expected_status = before_status
                elif status_update == "trim":
                    if target not in {"continuous", "single"}:
                        raise AssertionError("invalid internal TRIM status update")
                    expected_status = replace(before_status, acquisition=target)
                elif status_update == "external-trigger":
                    if target not in {"off", "on_sweep"}:
                        raise AssertionError("invalid internal EXTT status update")
                    expected_status = replace(
                        before_status,
                        external_trigger_enabled=target == "on_sweep",
                    )
                else:
                    raise AssertionError("invalid internal certified status update")
                if after_status != expected_status:
                    raise DataError(
                        "SP30120 core status fingerprint changed outside the certified field"
                    )

                phase = "identity-postcheck"
                self.idn()
            except Exception as exc:
                self._control_writes_blocked = True
                if isinstance(exc, SP30120ControlError):
                    raise
                raise SP30120ControlError(
                    phase=phase,
                    command=command,
                    detail=(
                        "instrument state is uncertain; the write is not retried and this "
                        "driver instance now refuses further writes"
                    ),
                    state_uncertain=True,
                ) from exc
            return observed

    def set_trim(self, value: SweepExecution) -> SweepExecution:
        commands = {"continuous": "TRIM CONT", "single": "TRIM SING"}
        if not isinstance(value, str) or value not in commands:
            raise DataError("sweep execution must be 'continuous' or 'single'")
        return self._set_certified_control(
            command=commands[value],
            target=value,
            readback=self.read_trim,
            status_update="trim",
        )

    def set_reference_position(self, value: ReferencePosition) -> ReferencePosition:
        if type(value) is not int or value not in {4, 5}:
            raise DataError("certified reference position must be 4 or 5")
        return self._set_certified_control(
            command=f"SETREFP {value}",
            target=value,
            readback=self.read_reference_position,
        )

    def set_clock_display(self, value: ClockDisplay) -> ClockDisplay:
        commands = {"on": "CLOCKSW ON", "off": "CLOCKSW OFF"}
        if not isinstance(value, str) or value not in commands:
            raise DataError("clock display must be 'on' or 'off'")
        return self._set_certified_control(
            command=commands[value],
            target=value,
            readback=self.read_clock_display,
        )

    def set_ui_language(self, value: UiLanguage) -> UiLanguage:
        commands = {"chinese": "LANGSEL CHINESE", "english": "LANGSEL ENGLISH"}
        if not isinstance(value, str) or value not in commands:
            raise DataError("UI language must be 'chinese' or 'english'")
        return self._set_certified_control(
            command=commands[value],
            target=value,
            readback=self.read_ui_language,
        )

    def set_external_trigger(self, value: ExternalTrigger) -> ExternalTrigger:
        commands = {"off": "EXTT OFF", "on_sweep": "EXTT ONSWEE"}
        if not isinstance(value, str) or value not in commands:
            raise DataError("external trigger must be 'off' or 'on_sweep'")
        return self._set_certified_control(
            command=commands[value],
            target=value,
            readback=self.read_external_trigger,
            status_update="external-trigger",
        )

    def close(self) -> None:
        with self._control_lock:
            self.transport.close()
