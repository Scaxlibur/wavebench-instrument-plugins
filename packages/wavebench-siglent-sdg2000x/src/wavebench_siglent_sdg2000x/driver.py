from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isfinite
import re
from threading import RLock

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.models import SourceStatus
from wavebench.transport.base import InstrumentTransport


_SUPPORTED_MODELS = frozenset({"SDG2042X", "SDG2082X", "SDG2122X"})
_WAVE_FUNCTIONS = {
    "SINE": "SIN",
    "SQUARE": "SQU",
    "RAMP": "RAMP",
    "PULSE": "PULS",
    "NOISE": "NOIS",
    "ARB": "USER",
    "DC": "DC",
}
_BSWV_PARAMETERS = frozenset(
    {
        "WVTP",
        "FRQ",
        "PERI",
        "AMP",
        "AMPVRMS",
        "AMPDBM",
        "MAX_OUTPUT_AMP",
        "OFST",
        "COM_OFST",
        "SYM",
        "DUTY",
        "PHSE",
        "STDEV",
        "MEAN",
        "WIDTH",
        "RISE",
        "FALL",
        "DLY",
        "HLEV",
        "LLEV",
        "BANDSTATE",
        "BANDWIDTH",
        "LENGTH",
        "EDGE",
        "FORMAT",
        "DIFFSTATE",
        "BITRATE",
        "LOGICLEVEL",
    }
)
_FREQUENCY_WAVES = frozenset({"SINE", "SQUARE", "RAMP", "PULSE", "ARB"})
_OFFSET_WAVES = frozenset({"SINE", "SQUARE", "RAMP", "PULSE", "ARB", "DC"})
_PHASE_WAVES = frozenset({"SINE", "SQUARE", "RAMP", "ARB"})
_QUANTITY_PATTERN = re.compile(
    r"^([+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[Ee][+-]?\d+)?)([A-Za-z%µμ°]*)$"
)
_MAX_RESPONSE_CHARACTERS = 16_384


@dataclass(frozen=True)
class _BasicWaveStatus:
    function: str
    frequency_hz: float | None
    amplitude: float | None
    amplitude_unit: str | None
    offset_v: float | None
    phase_deg: float | None
    square_duty_cycle_percent: float | None


def _validate_channel(channel: int) -> None:
    if isinstance(channel, bool) or channel not in (1, 2):
        raise DataError("SDG2000X channel must be 1 or 2")


def _validate_output_check_errors(check_errors: bool) -> None:
    if type(check_errors) is not bool:
        raise DataError("SDG2000X check_errors must be a boolean")
    if check_errors:
        raise DataError(
            "SDG2000X source.output requires check_errors=false because the "
            "programming guide does not define an accepted error-queue query"
        )


def _response_text(response: str, *, command: str) -> str:
    value = str(response).strip()
    if not value:
        raise DataError(f"SDG2000X returned an empty response for {command}")
    if len(value) > _MAX_RESPONSE_CHARACTERS:
        raise DataError(f"SDG2000X returned an oversized response for {command}")
    if "\n" in value or "\r" in value:
        raise DataError(f"SDG2000X returned multiple lines for {command}")
    return value


def _response_body(response: str, *, channel: int, header: str) -> tuple[str, str]:
    command = f"C{channel}:{header}?"
    value = _response_text(response, command=command)
    match = re.fullmatch(
        rf"C([12]):{re.escape(header)}\s*(.*)",
        value,
        flags=re.IGNORECASE,
    )
    if match is None or int(match.group(1)) != channel:
        raise DataError(f"unexpected SDG2000X response header for {command}")
    body = match.group(2).strip()
    if not body:
        raise DataError(f"SDG2000X returned no parameters for {command}")
    return value, body


def _tokens(body: str, *, command: str) -> tuple[str, ...]:
    values = tuple(item.strip() for item in body.split(","))
    if any(not item for item in values):
        raise DataError(f"SDG2000X returned an empty parameter for {command}")
    return values


def _parameter_pairs(
    values: tuple[str, ...],
    *,
    command: str,
    known: frozenset[str],
) -> dict[str, str]:
    if len(values) % 2:
        raise DataError(f"SDG2000X returned an incomplete parameter pair for {command}")
    parsed: dict[str, str] = {}
    for index in range(0, len(values), 2):
        name = values[index].upper()
        if name not in known:
            raise DataError(f"SDG2000X returned an unknown parameter {name!r} for {command}")
        if name in parsed:
            raise DataError(f"SDG2000X returned duplicate parameter {name!r} for {command}")
        parsed[name] = values[index + 1]
    return parsed


def _required_parameter(parameters: dict[str, str], name: str, *, command: str) -> str:
    try:
        return parameters[name]
    except KeyError as exc:
        raise DataError(f"SDG2000X response for {command} is missing {name}") from exc


def _quantity(
    value: str,
    *,
    command: str,
    field_name: str,
    unit_factors: dict[str, float],
) -> float:
    match = _QUANTITY_PATTERN.fullmatch(value.strip())
    if match is None:
        raise DataError(f"invalid SDG2000X {field_name} response for {command}")
    unit = match.group(2).replace("µ", "U").replace("μ", "U").upper()
    try:
        factor = unit_factors[unit]
    except KeyError as exc:
        raise DataError(f"unexpected SDG2000X {field_name} unit for {command}: {unit!r}") from exc
    parsed = float(match.group(1)) * factor
    if not isfinite(parsed):
        raise DataError(f"SDG2000X {field_name} response for {command} must be finite")
    return parsed


def _frequency(value: str, *, command: str) -> float:
    parsed = _quantity(
        value,
        command=command,
        field_name="frequency",
        unit_factors={"HZ": 1.0, "KHZ": 1e3, "MHZ": 1e6, "GHZ": 1e9},
    )
    if parsed <= 0:
        raise DataError(f"SDG2000X frequency response for {command} must be positive")
    return parsed


def _voltage(value: str, *, command: str, field_name: str, allow_vpp: bool = False) -> float:
    units = {"V": 1.0, "MV": 1e-3, "UV": 1e-6}
    if allow_vpp:
        units.update({"VPP": 1.0, "MVPP": 1e-3, "UVPP": 1e-6})
    return _quantity(
        value,
        command=command,
        field_name=field_name,
        unit_factors=units,
    )


def _plain_number(
    value: str,
    *,
    command: str,
    field_name: str,
    allow_percent: bool = False,
    allow_degrees: bool = False,
) -> float:
    units = {"": 1.0}
    if allow_percent:
        units["%"] = 1.0
    if allow_degrees:
        units.update({"DEG": 1.0, "°": 1.0})
    return _quantity(
        value,
        command=command,
        field_name=field_name,
        unit_factors=units,
    )


def _parse_output(response: str, *, channel: int) -> str:
    command = f"C{channel}:OUTP?"
    _, body = _response_body(response, channel=channel, header="OUTP")
    values = _tokens(body, command=command)
    state = values[0].upper()
    if state not in {"ON", "OFF"}:
        raise DataError(f"unexpected SDG2000X output state for {command}: {state!r}")
    parameters = _parameter_pairs(
        values[1:],
        command=command,
        known=frozenset({"LOAD", "PLRT", "POWERON_STATE"}),
    )
    if not {"LOAD", "PLRT"}.issubset(parameters):
        raise DataError(f"SDG2000X response for {command} must include LOAD and PLRT")

    load = parameters["LOAD"].strip().upper().replace(" ", "")
    if load not in {"HZ", "HIZ", "HIGHZ"}:
        if load.endswith("OHM"):
            load = load[:-3]
        numeric_load = _plain_number(load, command=command, field_name="load")
        if not 50 <= numeric_load <= 100_000:
            raise DataError(f"SDG2000X load response for {command} is out of range")

    polarity = parameters["PLRT"].upper()
    if polarity not in {"NOR", "INVT"}:
        raise DataError(f"unexpected SDG2000X output polarity for {command}: {polarity!r}")
    if "POWERON_STATE" in parameters:
        power_on_state = parameters["POWERON_STATE"].upper()
        if power_on_state not in {"ON", "OFF"}:
            raise DataError(
                f"unexpected SDG2000X power-on output state for {command}: "
                f"{power_on_state!r}"
            )
    return state


def _parse_basic_wave(response: str, *, channel: int) -> tuple[str, _BasicWaveStatus]:
    command = f"C{channel}:BSWV?"
    raw, body = _response_body(response, channel=channel, header="BSWV")
    parameters = _parameter_pairs(
        _tokens(body, command=command),
        command=command,
        known=_BSWV_PARAMETERS,
    )
    wave_type = _required_parameter(parameters, "WVTP", command=command).upper()
    try:
        function = _WAVE_FUNCTIONS[wave_type]
    except KeyError as exc:
        raise DataError(f"unsupported SDG2000X basic wave type for {command}: {wave_type!r}") from exc

    frequency_hz = None
    amplitude = None
    amplitude_unit = None
    offset_v = None
    phase_deg = None
    duty_percent = None

    if wave_type in _FREQUENCY_WAVES:
        frequency_hz = _frequency(
            _required_parameter(parameters, "FRQ", command=command),
            command=command,
        )
        amplitude = _voltage(
            _required_parameter(parameters, "AMP", command=command),
            command=command,
            field_name="amplitude",
            allow_vpp=True,
        )
        if amplitude <= 0:
            raise DataError(f"SDG2000X amplitude response for {command} must be positive")
        amplitude_unit = "VPP"

    if wave_type in _OFFSET_WAVES:
        offset_v = _voltage(
            _required_parameter(parameters, "OFST", command=command),
            command=command,
            field_name="offset",
        )

    if wave_type in _PHASE_WAVES:
        phase_deg = _plain_number(
            _required_parameter(parameters, "PHSE", command=command),
            command=command,
            field_name="phase",
            allow_degrees=True,
        )
        if not 0 <= phase_deg <= 360:
            raise DataError(f"SDG2000X phase response for {command} is out of range")

    if wave_type == "SQUARE":
        duty_percent = _plain_number(
            _required_parameter(parameters, "DUTY", command=command),
            command=command,
            field_name="square duty cycle",
            allow_percent=True,
        )
        if not 0 <= duty_percent <= 100:
            raise DataError(f"SDG2000X square duty-cycle response for {command} is out of range")

    return raw, _BasicWaveStatus(
        function=function,
        frequency_hz=frequency_hz,
        amplitude=amplitude,
        amplitude_unit=amplitude_unit,
        offset_v=offset_v,
        phase_deg=phase_deg,
        square_duty_cycle_percent=duty_percent,
    )


def _parse_sweep_state(response: str, *, channel: int) -> str:
    command = f"C{channel}:SWWV?"
    _, body = _response_body(response, channel=channel, header="SWWV")
    values = _tokens(body, command=command)
    if len(values) < 2 or values[0].upper() != "STATE":
        raise DataError(f"unexpected SDG2000X sweep response for {command}")
    state = values[1].upper()
    if state not in {"ON", "OFF"}:
        raise DataError(f"unexpected SDG2000X sweep state for {command}: {state!r}")
    if state == "OFF" and len(values) != 2:
        raise DataError(f"unexpected SDG2000X disabled sweep parameters for {command}")
    if state == "ON" and len(values) < 4:
        raise DataError(f"incomplete SDG2000X enabled sweep response for {command}")
    return state


def parse_idn_model(response: str) -> str:
    """Return a verified SDG2000X model from either documented IDN format."""

    value = _response_text(response, command="*IDN?")
    fields = tuple(item.strip() for item in value.split(","))

    if len(fields) == 4 and fields[0].casefold() == "siglent technologies":
        model = fields[1].upper()
    elif (
        len(fields) == 6
        and fields[0].upper() == "*IDN"
        and fields[1].upper() == "SDG"
    ):
        model = fields[2].upper()
    else:
        raise DataError("unsupported SDG2000X identity response format")

    if any(not field for field in fields):
        raise DataError("unsupported SDG2000X identity response format")
    if model not in _SUPPORTED_MODELS:
        raise DataError(f"unsupported SDG2000X model: {model or '<empty>'}")
    return model


@dataclass
class SDG2000XSource:
    transport: InstrumentTransport
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _identity_model: str | None = field(default=None, init=False, repr=False)
    _output_writes_blocked: bool = field(default=False, init=False, repr=False)

    def _ensure_identity(self) -> str:
        if self._identity_model is None:
            self._identity_model = parse_idn_model(self.transport.query("*IDN?"))
        return self._identity_model

    def idn(self) -> str:
        with self._io_lock:
            response = _response_text(self.transport.query("*IDN?"), command="*IDN?")
            self._identity_model = parse_idn_model(response)
            return response

    def get_status(self, channel: int) -> SourceStatus:
        _validate_channel(channel)
        with self._io_lock:
            self._ensure_identity()
            output = _parse_output(
                self.transport.query(f"C{channel}:OUTP?"),
                channel=channel,
            )
            apply_raw, basic = _parse_basic_wave(
                self.transport.query(f"C{channel}:BSWV?"),
                channel=channel,
            )
            sweep_enabled = _parse_sweep_state(
                self.transport.query(f"C{channel}:SWWV?"),
                channel=channel,
            )
            return SourceStatus(
                channel=channel,
                output=output,
                function=basic.function,
                frequency_hz=basic.frequency_hz,
                amplitude=basic.amplitude,
                amplitude_unit=basic.amplitude_unit,
                offset_v=basic.offset_v,
                phase_deg=basic.phase_deg,
                frequency_mode="SWE" if sweep_enabled == "ON" else "FIX",
                sweep_enabled=sweep_enabled,
                apply_raw=apply_raw,
                square_duty_cycle_percent=basic.square_duty_cycle_percent,
            )

    @property
    def output_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._output_writes_blocked

    @staticmethod
    def _validate_output_enable_snapshot(status: SourceStatus) -> None:
        if status.frequency_mode != "FIX" or status.sweep_enabled != "OFF":
            raise DataError("SDG2000X output enable requires fixed-frequency mode with sweep OFF")
        if status.amplitude is None or status.amplitude_unit != "VPP":
            raise DataError("SDG2000X output enable requires a verified Vpp amplitude")
        if status.offset_v is None:
            raise DataError("SDG2000X output enable requires a verified voltage offset")

    def _force_output_off(self, channel: int) -> None:
        self.transport.write(f"C{channel}:OUTP OFF")
        output = _parse_output(
            self.transport.query(f"C{channel}:OUTP?"),
            channel=channel,
        )
        if output != "OFF":
            raise InstrumentError("SDG2000X output failed to converge to OFF")

    def set_output(
        self,
        channel: int,
        enabled: bool,
        *,
        check_errors: bool = True,
    ) -> SourceStatus:
        _validate_channel(channel)
        if type(enabled) is not bool:
            raise DataError("SDG2000X output enabled must be a boolean")
        _validate_output_check_errors(check_errors)

        with self._io_lock:
            self._ensure_identity()
            if self._output_writes_blocked:
                if enabled:
                    raise InstrumentError(
                        "SDG2000X output writes are blocked after a failed transaction; "
                        "reopen the instrument session and verify state"
                    )
                self._force_output_off(channel)
                return self.get_status(channel)

            previous = self.get_status(channel)
            target = "ON" if enabled else "OFF"
            if previous.output == target:
                return previous
            if enabled:
                self._validate_output_enable_snapshot(previous)

            try:
                self.transport.write(f"C{channel}:OUTP {target}")
                status = self.get_status(channel)
                if status.output != target:
                    raise InstrumentError("SDG2000X output write readback mismatch")
                if replace(status, output=previous.output) != previous:
                    raise InstrumentError(
                        "SDG2000X output transaction changed non-output channel state"
                    )
                return status
            except Exception as exc:
                self._output_writes_blocked = True
                try:
                    self._force_output_off(channel)
                except Exception as recovery_exc:
                    raise InstrumentError(
                        "SDG2000X output transaction failed and OFF recovery could not be "
                        "verified; output state is uncertain and output writes are blocked"
                    ) from recovery_exc
                raise InstrumentError(
                    "SDG2000X output transaction failed; output is confirmed OFF and output "
                    "writes are blocked until the session is reopened"
                ) from exc

    def close(self) -> None:
        with self._io_lock:
            self.transport.close()
