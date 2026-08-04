from __future__ import annotations

from dataclasses import dataclass, field
from math import isclose, isfinite
from threading import RLock

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.models import SourceStatus


_LEGACY_MODELS = frozenset({"DG1022", "DG1022A"})
_SOURCE_LAYOUT_MODELS = frozenset({"DG1022Z", "DG1032Z", "DG1062Z"})
_KNOWN_MODELS = _LEGACY_MODELS | _SOURCE_LAYOUT_MODELS
_FUNCTION_ALIASES = {
    "SIN": "SIN",
    "SINE": "SIN",
    "SINUSOID": "SIN",
    "SQU": "SQU",
    "SQUARE": "SQU",
    "RAMP": "RAMP",
    "TRI": "RAMP",
    "TRIANGLE": "RAMP",
    "PULS": "PULS",
    "PULSE": "PULS",
    "NOIS": "NOIS",
    "NOISE": "NOIS",
    "DC": "DC",
    "USER": "USER",
    "ARB": "USER",
}
_RESTORABLE_FUNCTIONS = frozenset({"SIN", "SQU", "RAMP", "PULS", "NOIS", "DC", "USER"})


def _validate_channel(channel: int) -> None:
    if channel not in (1, 2):
        raise DataError("DG1000 channel must be 1 or 2")


def _finite_float(value: object, *, field_name: str) -> float:
    text = str(value).strip().strip('"')
    if ":" in text:
        text = text.split(":", 1)[1]
    try:
        parsed = float(text)
    except (TypeError, ValueError) as exc:
        raise DataError(f"{field_name} must be a finite number") from exc
    if not isfinite(parsed):
        raise DataError(f"{field_name} must be a finite number")
    return parsed


def _normalize_enum(value: object, *, field_name: str, aliases: dict[str, str]) -> str:
    text = str(value).strip().strip('"')
    if ":" in text:
        text = text.split(":", 1)[1]
    normalized = text.upper()
    try:
        return aliases[normalized]
    except KeyError as exc:
        raise DataError(f"unexpected {field_name} response: {value!r}") from exc


def _parse_identity(response: str) -> tuple[str, str, str, str]:
    parts = tuple(item.strip() for item in response.split(","))
    if len(parts) != 4 or any(not item for item in parts):
        raise DataError("unexpected DG1000 *IDN? response")
    manufacturer, model, serial_number, firmware = parts
    if manufacturer.upper() != "RIGOL TECHNOLOGIES":
        raise DataError(f"unexpected DG1000 manufacturer: {manufacturer!r}")
    normalized_model = model.upper()
    if normalized_model not in _KNOWN_MODELS:
        raise DataError(f"unsupported DG1000 model: {model!r}")
    return manufacturer, normalized_model, serial_number, firmware


def _channel_suffix(channel: int) -> str:
    _validate_channel(channel)
    return "" if channel == 1 else ":CH2"


def _parse_apply_function(response: str) -> str | None:
    text = response.strip().strip('"')
    if ":" in text:
        text = text.split(":", 1)[1].strip().strip('"')
    first = text.split(",", 1)[0].strip().strip('"').upper()
    if not first:
        return None
    return _FUNCTION_ALIASES.get(first)


class _AmbiguousWriteError(InstrumentError):
    pass


@dataclass
class DG1000Source:
    transport: object
    check_errors_after_ops: bool = True
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _identity: tuple[str, str, str, str] | None = field(default=None, init=False, repr=False)
    _configuration_writes_blocked: bool = field(default=False, init=False, repr=False)

    def _ensure_identity(self) -> tuple[str, str, str, str]:
        if self._identity is None:
            self._identity = _parse_identity(self.transport.query("*IDN?"))
        return self._identity

    def _uses_source_layout(self) -> bool:
        return self._ensure_identity()[1] in _SOURCE_LAYOUT_MODELS

    def _channel_prefix(self, channel: int) -> str:
        _validate_channel(channel)
        if self._uses_source_layout():
            return f":SOUR{channel}:"
        return ""

    def _output_command(self, channel: int) -> str:
        _validate_channel(channel)
        return f":OUTP{channel}" if self._uses_source_layout() else f"OUTP{_channel_suffix(channel)}"

    def _function_command(self, channel: int) -> str:
        return f"{self._channel_prefix(channel)}FUNC{_channel_suffix(channel) if not self._uses_source_layout() else ''}"

    def _frequency_command(self, channel: int) -> str:
        return f"{self._channel_prefix(channel)}FREQ{_channel_suffix(channel) if not self._uses_source_layout() else ''}"

    def _voltage_command(self, channel: int) -> str:
        return f"{self._channel_prefix(channel)}VOLT{_channel_suffix(channel) if not self._uses_source_layout() else ''}"

    def _voltage_unit_command(self, channel: int) -> str:
        return f"{self._channel_prefix(channel)}VOLT:UNIT{_channel_suffix(channel) if not self._uses_source_layout() else ''}"

    def _voltage_offset_command(self, channel: int) -> str:
        return f"{self._channel_prefix(channel)}VOLT:OFFS{_channel_suffix(channel) if not self._uses_source_layout() else ''}"

    def _phase_command(self, channel: int) -> str:
        return f"{self._channel_prefix(channel)}PHAS{_channel_suffix(channel) if not self._uses_source_layout() else ''}"

    def _square_duty_command(self, channel: int) -> str:
        return f"{self._channel_prefix(channel)}FUNC:SQU:DCYC{_channel_suffix(channel) if not self._uses_source_layout() else ''}"

    def _apply_query(self, channel: int) -> str:
        if self._uses_source_layout():
            return f":SOUR{channel}:APPL?"
        return "APPL?" if channel == 1 else "APPL:CH2?"

    def _sweep_state_command(self, channel: int) -> str:
        if self._uses_source_layout():
            return f":SOUR{channel}:SWE:STAT"
        return "SWE:STAT"

    def _check_errors_enabled(self, requested: bool | None) -> bool:
        return self.check_errors_after_ops if requested is None else requested

    def _ensure_configuration_write_allowed(self) -> None:
        if self._configuration_writes_blocked:
            raise InstrumentError(
                "DG1000 configuration writes are blocked after an ambiguous write; "
                "reopen the instrument session and verify state"
            )

    def _write(self, command: str) -> None:
        try:
            self.transport.write(command)
        except Exception as exc:
            raise _AmbiguousWriteError(
                f"DG1000 write result is unknown for {command!r}: {exc}"
            ) from exc

    @staticmethod
    def _numeric_matches(actual: float | None, expected: float) -> bool:
        return actual is not None and isclose(
            actual,
            expected,
            rel_tol=1.0e-6,
            abs_tol=1.0e-6,
        )

    def _query_output(self, channel: int) -> str:
        return _normalize_enum(
            self.transport.query(f"{self._output_command(channel)}?"),
            field_name="output state",
            aliases={"0": "OFF", "OFF": "OFF", "1": "ON", "ON": "ON"},
        )

    def _query_function(self, channel: int) -> str:
        raw = self.transport.query(f"{self._function_command(channel)}?")
        function = _normalize_enum(
            raw,
            field_name="function",
            aliases=_FUNCTION_ALIASES,
        )
        if function != "USER":
            return function
        apply_function = _parse_apply_function(self.transport.query(self._apply_query(channel)))
        return apply_function or function

    def _query_amplitude_unit(self, channel: int) -> str:
        return _normalize_enum(
            self.transport.query(f"{self._voltage_unit_command(channel)}?"),
            field_name="amplitude unit",
            aliases={"VPP": "VPP", "VRMS": "VRMS", "DBM": "DBM"},
        )

    def _query_sweep_enabled(self, channel: int) -> str:
        return _normalize_enum(
            self.transport.query(f"{self._sweep_state_command(channel)}?"),
            field_name="sweep state",
            aliases={"0": "OFF", "OFF": "OFF", "1": "ON", "ON": "ON"},
        )

    def _finish_transaction(self, *, channel: int, check_errors: bool | None) -> SourceStatus:
        status = self.get_status(channel)
        if self._check_errors_enabled(check_errors):
            self.assert_no_errors()
        return status

    def idn(self) -> str:
        with self._io_lock:
            response = self.transport.query("*IDN?")
            self._identity = _parse_identity(response)
            return response

    def errors(self, limit: int = 8) -> list[str]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise DataError("error query limit must be a positive integer")
        with self._io_lock:
            errors: list[str] = []
            for _ in range(limit):
                response = self.transport.query("SYST:ERR?").strip()
                if not response:
                    raise DataError("empty DG1000 error-queue response")
                errors.append(response)
                if response.startswith("0") or "No error" in response:
                    break
            return errors

    def assert_no_errors(self) -> None:
        with self._io_lock:
            active = [
                item
                for item in self.errors()
                if not (item.startswith("0") or "No error" in item)
            ]
            if active:
                raise InstrumentError("instrument error queue is not empty: " + "; ".join(active))

    def get_status(self, channel: int) -> SourceStatus:
        _validate_channel(channel)
        with self._io_lock:
            self._ensure_identity()
            output = self._query_output(channel)
            function = self._query_function(channel)
            frequency_hz = _finite_float(
                self.transport.query(f"{self._frequency_command(channel)}?"),
                field_name="frequency",
            )
            amplitude = _finite_float(
                self.transport.query(f"{self._voltage_command(channel)}?"),
                field_name="amplitude",
            )
            amplitude_unit = self._query_amplitude_unit(channel)
            offset_v = _finite_float(
                self.transport.query(f"{self._voltage_offset_command(channel)}?"),
                field_name="offset",
            )
            phase_deg = _finite_float(
                self.transport.query(f"{self._phase_command(channel)}?"),
                field_name="phase",
            )
            sweep_enabled = self._query_sweep_enabled(channel)
            duty = _finite_float(
                self.transport.query(f"{self._square_duty_command(channel)}?"),
                field_name="square duty cycle",
            )
            if duty <= 0 or duty >= 100:
                raise DataError("square duty cycle response must be > 0 and < 100")
            return SourceStatus(
                channel=channel,
                output=output,
                function=function,
                frequency_hz=frequency_hz,
                amplitude=amplitude,
                amplitude_unit=amplitude_unit,
                offset_v=offset_v,
                phase_deg=phase_deg,
                frequency_mode="SWE" if sweep_enabled == "ON" else "FIX",
                sweep_enabled=sweep_enabled,
                apply_raw=self.transport.query(self._apply_query(channel)).strip(),
                square_duty_cycle_percent=duty,
            )

    def set_frequency(
        self,
        channel: int,
        value_hz: float,
        *,
        ensure_fix_mode: bool = True,
        check_errors: bool | None = None,
    ) -> SourceStatus:
        _validate_channel(channel)
        value_hz = _finite_float(value_hz, field_name="frequency")
        if value_hz <= 0:
            raise DataError("frequency must be > 0")
        with self._io_lock:
            self._ensure_identity()
            self._ensure_configuration_write_allowed()
            if ensure_fix_mode and self._query_sweep_enabled(channel) != "OFF":
                self._write(f"{self._sweep_state_command(channel)} OFF")
                if self._query_sweep_enabled(channel) != "OFF":
                    raise InstrumentError("DG1000 sweep state did not converge to OFF")
            self._write(f"{self._frequency_command(channel)} {value_hz:.12g}")
            actual = _finite_float(
                self.transport.query(f"{self._frequency_command(channel)}?"),
                field_name="frequency",
            )
            if not self._numeric_matches(actual, value_hz):
                raise InstrumentError("DG1000 frequency write readback mismatch")
            return self._finish_transaction(channel=channel, check_errors=check_errors)

    def set_output(
        self,
        channel: int,
        enabled: bool,
        *,
        check_errors: bool | None = None,
    ) -> SourceStatus:
        _validate_channel(channel)
        if not isinstance(enabled, bool):
            raise DataError("output enabled must be a boolean")
        with self._io_lock:
            self._ensure_identity()
            if enabled:
                self._ensure_configuration_write_allowed()
            target = "ON" if enabled else "OFF"
            self._write(f"{self._output_command(channel)} {target}")
            if self._query_output(channel) != target:
                raise InstrumentError("DG1000 output write readback mismatch")
            return self._finish_transaction(channel=channel, check_errors=check_errors)

    def set_function(
        self,
        channel: int,
        function: str,
        *,
        check_errors: bool | None = None,
    ) -> SourceStatus:
        _validate_channel(channel)
        normalized = str(function).strip().upper()
        if normalized not in _FUNCTION_ALIASES:
            raise DataError("function must be one of: sin, squ, ramp/triangle, puls, nois, dc, user")
        expected = _FUNCTION_ALIASES[normalized]
        if expected not in _RESTORABLE_FUNCTIONS:
            raise DataError("unsupported DG1000 function")
        with self._io_lock:
            self._ensure_identity()
            self._ensure_configuration_write_allowed()
            self._write(f"{self._function_command(channel)} {expected}")
            actual = self._query_function(channel)
            if actual != expected and not (expected in {"DC", "USER"} and actual == "USER"):
                raise InstrumentError("DG1000 function write readback mismatch")
            return self._finish_transaction(channel=channel, check_errors=check_errors)

    def set_amplitude_vpp(
        self,
        channel: int,
        value_vpp: float,
        *,
        check_errors: bool | None = None,
    ) -> SourceStatus:
        _validate_channel(channel)
        value_vpp = _finite_float(value_vpp, field_name="amplitude")
        if value_vpp <= 0:
            raise DataError("amplitude must be > 0")
        with self._io_lock:
            self._ensure_identity()
            self._ensure_configuration_write_allowed()
            self._write(f"{self._voltage_unit_command(channel)} VPP")
            if self._query_amplitude_unit(channel) != "VPP":
                raise InstrumentError("DG1000 amplitude-unit write readback mismatch")
            self._write(f"{self._voltage_command(channel)} {value_vpp:.12g}")
            actual = _finite_float(
                self.transport.query(f"{self._voltage_command(channel)}?"),
                field_name="amplitude",
            )
            if not self._numeric_matches(actual, value_vpp):
                raise InstrumentError("DG1000 amplitude write readback mismatch")
            return self._finish_transaction(channel=channel, check_errors=check_errors)

    def set_square_duty_cycle(
        self,
        channel: int,
        duty_percent: float,
        *,
        check_errors: bool | None = None,
    ) -> SourceStatus:
        _validate_channel(channel)
        duty_percent = _finite_float(duty_percent, field_name="duty cycle percent")
        if duty_percent <= 0 or duty_percent >= 100:
            raise DataError("duty cycle percent must be > 0 and < 100")
        with self._io_lock:
            self._ensure_identity()
            self._ensure_configuration_write_allowed()
            self._write(f"{self._square_duty_command(channel)} {duty_percent:.12g}")
            actual = _finite_float(
                self.transport.query(f"{self._square_duty_command(channel)}?"),
                field_name="square duty cycle",
            )
            if not self._numeric_matches(actual, duty_percent):
                raise InstrumentError("DG1000 duty-cycle write readback mismatch")
            return self._finish_transaction(channel=channel, check_errors=check_errors)

    def close(self) -> None:
        with self._io_lock:
            self.transport.close()
