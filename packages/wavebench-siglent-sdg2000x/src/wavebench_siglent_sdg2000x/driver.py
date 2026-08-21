from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isclose, isfinite
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
_MIN_FREQUENCY_HZ = 1.0e-6
_MAX_USER_AMPLITUDE_VPP = 10.0
_MAX_ABSOLUTE_OUTPUT_V = 10.0
_MODEL_SINE_MAX_FREQUENCY_HZ = {
    "SDG2042X": 40.0e6,
    "SDG2082X": 80.0e6,
    "SDG2122X": 120.0e6,
}
_FUNCTION_MAX_FREQUENCY_HZ = {
    "SQU": 25.0e6,
    "RAMP": 1.0e6,
    "PULS": 25.0e6,
    "USER": 20.0e6,
}


@dataclass(frozen=True)
class _BasicWaveStatus:
    function: str
    frequency_hz: float | None
    amplitude: float | None
    amplitude_unit: str | None
    offset_v: float | None
    phase_deg: float | None
    square_duty_cycle_percent: float | None


@dataclass(frozen=True)
class _OutputStatus:
    state: str
    load_ohm: float | None
    polarity: str
    power_on_state: str | None


@dataclass(frozen=True)
class _OutputSafetyContext:
    modulation_enabled: bool
    burst_enabled: bool
    harmonic_enabled: bool
    combine_enabled: bool
    noise_add_enabled: bool
    coupling_trace_enabled: bool
    coupling_tracking_direction_enabled: bool
    coupling_frequency_enabled: bool
    coupling_phase_enabled: bool
    coupling_amplitude_enabled: bool


@dataclass(frozen=True)
class _ConfigurationSnapshot:
    status: SourceStatus
    output: _OutputStatus
    context: _OutputSafetyContext


def _validate_channel(channel: int) -> None:
    if isinstance(channel, bool) or channel not in (1, 2):
        raise DataError("SDG2000X channel must be 1 or 2")


def _validate_write_check_errors(check_errors: bool, *, capability: str) -> None:
    if type(check_errors) is not bool:
        raise DataError("SDG2000X check_errors must be a boolean")
    if check_errors:
        raise DataError(
            f"SDG2000X {capability} requires check_errors=false because the "
            "programming guide does not define an accepted error-queue query"
        )


def _finite_number(value: object, *, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise DataError(f"SDG2000X {field_name} must be a finite number")
    parsed = float(value)
    if not isfinite(parsed):
        raise DataError(f"SDG2000X {field_name} must be a finite number")
    return parsed


def _numeric_matches(actual: float | None, expected: float) -> bool:
    return actual is not None and isclose(
        actual,
        expected,
        rel_tol=1.0e-6,
        abs_tol=1.0e-6,
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


def _parse_on_off(value: str, *, command: str, field_name: str) -> bool:
    normalized = value.strip().upper()
    if normalized not in {"ON", "OFF"}:
        raise DataError(
            f"unexpected SDG2000X {field_name} for {command}: {normalized!r}"
        )
    return normalized == "ON"


def _parse_output(response: str, *, channel: int) -> _OutputStatus:
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
    load_ohm = None
    if load not in {"HZ", "HIZ", "HIGHZ"}:
        if load.endswith("OHM"):
            load = load[:-3]
        load_ohm = _plain_number(load, command=command, field_name="load")
        if not 50 <= load_ohm <= 100_000:
            raise DataError(f"SDG2000X load response for {command} is out of range")

    polarity = parameters["PLRT"].upper()
    if polarity not in {"NOR", "INVT"}:
        raise DataError(f"unexpected SDG2000X output polarity for {command}: {polarity!r}")
    power_on_state = parameters.get("POWERON_STATE")
    if power_on_state is not None:
        power_on_state = power_on_state.upper()
        _parse_on_off(
            power_on_state,
            command=command,
            field_name="power-on output state",
        )
    return _OutputStatus(
        state=state,
        load_ohm=load_ohm,
        polarity="NORMAL" if polarity == "NOR" else "INVERTED",
        power_on_state=power_on_state,
    )


def _parse_named_state(
    response: str,
    *,
    channel: int,
    header: str,
    state_name: str,
) -> bool:
    command = f"C{channel}:{header}?"
    _, body = _response_body(response, channel=channel, header=header)
    values = _tokens(body, command=command)
    matches = [index for index, value in enumerate(values) if value.upper() == state_name]
    if len(matches) != 1 or matches[0] + 1 >= len(values):
        raise DataError(
            f"SDG2000X response for {command} must contain one complete {state_name} field"
        )
    return _parse_on_off(
        values[matches[0] + 1],
        command=command,
        field_name=state_name.lower(),
    )


def _parse_combine_state(response: str, *, channel: int) -> bool:
    command = f"C{channel}:CMBN?"
    _, body = _response_body(response, channel=channel, header="CMBN")
    values = _tokens(body, command=command)
    if len(values) != 1:
        raise DataError(f"unexpected SDG2000X combine response for {command}")
    return _parse_on_off(values[0], command=command, field_name="combine state")


def _parse_coupling_states(response: str) -> tuple[bool, bool, bool, bool, bool]:
    command = "COUP?"
    value = _response_text(response, command=command)
    match = re.fullmatch(r"COUP\s+(.+)", value, flags=re.IGNORECASE)
    if match is None:
        raise DataError(f"unexpected SDG2000X response header for {command}")
    parameters = _parameter_pairs(
        _tokens(match.group(1), command=command),
        command=command,
        known=frozenset(
            {
                "TRACE",
                "TRDUCH",
                "STATE",
                "BSCH",
                "FCOUP",
                "FDEV",
                "FRAT",
                "PCOUP",
                "PDEV",
                "PRAT",
                "ACOUP",
                "ADEV",
            }
        ),
    )
    required = ("TRACE", "FCOUP", "PCOUP", "ACOUP")
    if not set(required).issubset(parameters):
        raise DataError(
            "SDG2000X response for COUP? must include TRACE, FCOUP, PCOUP, and ACOUP"
        )
    parsed = tuple(
        _parse_on_off(
            parameters[name],
            command=command,
            field_name=name.lower(),
        )
        for name in required
    )
    tracking_direction_enabled = False
    if "TRDUCH" in parameters:
        tracking_direction_enabled = _parse_on_off(
            parameters["TRDUCH"],
            command=command,
            field_name="trduch",
        )
    return (
        parsed[0],
        tracking_direction_enabled,
        parsed[1],
        parsed[2],
        parsed[3],
    )


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
    _configuration_writes_blocked: bool = field(default=False, init=False, repr=False)

    def _ensure_identity(self) -> str:
        if self._identity_model is None:
            self._identity_model = parse_idn_model(self.transport.query("*IDN?"))
        return self._identity_model

    def idn(self) -> str:
        with self._io_lock:
            response = _response_text(self.transport.query("*IDN?"), command="*IDN?")
            self._identity_model = parse_idn_model(response)
            return response

    def _read_status(self, channel: int) -> tuple[SourceStatus, _OutputStatus]:
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
        return (
            SourceStatus(
                channel=channel,
                output=output.state,
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
            ),
            output,
        )

    def _read_output_safety_context(self, channel: int) -> _OutputSafetyContext:
        modulation_enabled = _parse_named_state(
            self.transport.query(f"C{channel}:MDWV?"),
            channel=channel,
            header="MDWV",
            state_name="STATE",
        )
        burst_enabled = _parse_named_state(
            self.transport.query(f"C{channel}:BTWV?"),
            channel=channel,
            header="BTWV",
            state_name="STATE",
        )
        harmonic_enabled = _parse_named_state(
            self.transport.query(f"C{channel}:HARM?"),
            channel=channel,
            header="HARM",
            state_name="HARMSTATE",
        )
        combine_enabled = _parse_combine_state(
            self.transport.query(f"C{channel}:CMBN?"),
            channel=channel,
        )
        noise_add_enabled = _parse_named_state(
            self.transport.query(f"C{channel}:NOISE_ADD?"),
            channel=channel,
            header="NOISE_ADD",
            state_name="STATE",
        )
        coupling = _parse_coupling_states(self.transport.query("COUP?"))
        return _OutputSafetyContext(
            modulation_enabled=modulation_enabled,
            burst_enabled=burst_enabled,
            harmonic_enabled=harmonic_enabled,
            combine_enabled=combine_enabled,
            noise_add_enabled=noise_add_enabled,
            coupling_trace_enabled=coupling[0],
            coupling_tracking_direction_enabled=coupling[1],
            coupling_frequency_enabled=coupling[2],
            coupling_phase_enabled=coupling[3],
            coupling_amplitude_enabled=coupling[4],
        )

    def _read_configuration_snapshot(self, channel: int) -> _ConfigurationSnapshot:
        status, output = self._read_status(channel)
        return _ConfigurationSnapshot(
            status=status,
            output=output,
            context=self._read_output_safety_context(channel),
        )

    def get_status(self, channel: int) -> SourceStatus:
        _validate_channel(channel)
        with self._io_lock:
            return self._read_status(channel)[0]

    @property
    def output_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._configuration_writes_blocked

    @property
    def configuration_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._configuration_writes_blocked

    def _ensure_configuration_writes_allowed(self) -> None:
        if self._configuration_writes_blocked:
            raise InstrumentError(
                "SDG2000X configuration writes are blocked after a failed transaction; "
                "reopen the instrument session and verify state"
            )

    @staticmethod
    def _active_advanced_modes(context: _OutputSafetyContext) -> tuple[str, ...]:
        return tuple(
            name
            for name, enabled in (
                ("modulation", context.modulation_enabled),
                ("burst", context.burst_enabled),
                ("harmonic", context.harmonic_enabled),
                ("combine", context.combine_enabled),
                ("noise-add", context.noise_add_enabled),
                ("coupling-trace", context.coupling_trace_enabled),
                (
                    "coupling-tracking-direction",
                    context.coupling_tracking_direction_enabled,
                ),
                ("frequency-coupling", context.coupling_frequency_enabled),
                ("phase-coupling", context.coupling_phase_enabled),
                ("amplitude-coupling", context.coupling_amplitude_enabled),
            )
            if enabled
        )

    @classmethod
    def _validate_advanced_modes_off(cls, context: _OutputSafetyContext) -> None:
        active = cls._active_advanced_modes(context)
        if active:
            raise DataError(
                "SDG2000X configuration writes require advanced signal modes OFF; "
                "active modes: " + ", ".join(active)
            )

    @staticmethod
    def _validate_output_enable_snapshot(
        status: SourceStatus,
        output: _OutputStatus,
        context: _OutputSafetyContext,
    ) -> None:
        if status.frequency_mode != "FIX" or status.sweep_enabled != "OFF":
            raise DataError("SDG2000X output enable requires fixed-frequency mode with sweep OFF")
        if status.amplitude is None or status.amplitude_unit != "VPP":
            raise DataError("SDG2000X output enable requires a verified Vpp amplitude")
        if status.offset_v is None:
            raise DataError("SDG2000X output enable requires a verified voltage offset")
        if status.amplitude > _MAX_USER_AMPLITUDE_VPP:
            raise DataError("SDG2000X output enable exceeds the 10 Vpp hard safety limit")
        if abs(status.offset_v) + status.amplitude / 2 > _MAX_ABSOLUTE_OUTPUT_V:
            raise DataError(
                "SDG2000X output enable exceeds the verified absolute voltage envelope"
            )
        if output.load_ohm is not None:
            raise DataError(
                "SDG2000X output enable requires a verified high-impedance load setting"
            )
        active = SDG2000XSource._active_advanced_modes(context)
        if active:
            raise DataError(
                "SDG2000X output enable requires advanced signal modes OFF; active modes: "
                + ", ".join(active)
            )

    @staticmethod
    def _validate_frequency_range(*, model: str, function: str, value_hz: float) -> None:
        if value_hz < _MIN_FREQUENCY_HZ:
            raise DataError("SDG2000X frequency must be at least 1 uHz")
        if function == "SIN":
            maximum = _MODEL_SINE_MAX_FREQUENCY_HZ[model]
        else:
            try:
                maximum = _FUNCTION_MAX_FREQUENCY_HZ[function]
            except KeyError as exc:
                raise DataError(
                    f"SDG2000X frequency is not applicable to function {function}"
                ) from exc
        if value_hz > maximum:
            raise DataError(
                f"SDG2000X frequency exceeds the {maximum:.12g} Hz limit for "
                f"{model} function {function}"
            )

    @classmethod
    def _validate_basic_configuration_snapshot(
        cls,
        snapshot: _ConfigurationSnapshot,
    ) -> None:
        cls._validate_advanced_modes_off(snapshot.context)
        if snapshot.status.output == "ON":
            cls._validate_output_enable_snapshot(
                snapshot.status,
                snapshot.output,
                snapshot.context,
            )

    @classmethod
    def _verify_configuration_closure(
        cls,
        *,
        before: _ConfigurationSnapshot,
        after: _ConfigurationSnapshot,
    ) -> None:
        cls._validate_basic_configuration_snapshot(after)
        if after.output != before.output:
            raise InstrumentError(
                "SDG2000X configuration transaction changed output, load, polarity, "
                "or power-on state"
            )
        if after.context != before.context:
            raise InstrumentError(
                "SDG2000X configuration transaction changed advanced signal state"
            )

    def _fail_configuration_transaction(self, channel: int, exc: Exception) -> None:
        self._configuration_writes_blocked = True
        try:
            self._force_output_off(channel)
        except Exception as recovery_exc:
            raise InstrumentError(
                "SDG2000X configuration transaction failed and OFF recovery could not be "
                "verified; output state is uncertain and configuration writes are blocked"
            ) from recovery_exc
        raise InstrumentError(
            "SDG2000X configuration transaction failed; output is confirmed OFF and "
            "configuration writes are blocked until the session is reopened"
        ) from exc

    def _force_output_off(self, channel: int) -> None:
        self.transport.write(f"C{channel}:OUTP OFF")
        output = _parse_output(
            self.transport.query(f"C{channel}:OUTP?"),
            channel=channel,
        )
        if output.state != "OFF":
            raise InstrumentError("SDG2000X output failed to converge to OFF")

    def set_frequency(
        self,
        channel: int,
        value_hz: float,
        *,
        ensure_fix_mode: bool = True,
        check_errors: bool = True,
    ) -> SourceStatus:
        _validate_channel(channel)
        value_hz = _finite_number(value_hz, field_name="frequency")
        if type(ensure_fix_mode) is not bool:
            raise DataError("SDG2000X ensure_fix_mode must be a boolean")
        _validate_write_check_errors(check_errors, capability="source.set_frequency")

        with self._io_lock:
            self._ensure_configuration_writes_allowed()
            model = self._ensure_identity()
            before = self._read_configuration_snapshot(channel)
            if before.status.frequency_mode != "FIX":
                self._validate_advanced_modes_off(before.context)
                if not ensure_fix_mode:
                    raise DataError(
                        "SDG2000X frequency writes require FIX mode when automatic mode "
                        "selection is disabled"
                    )
                if before.status.output != "OFF":
                    raise DataError(
                        "SDG2000X automatic FIX-mode selection requires output OFF"
                    )
            else:
                self._validate_basic_configuration_snapshot(before)

            self._validate_frequency_range(
                model=model,
                function=before.status.function,
                value_hz=value_hz,
            )
            if (
                before.status.frequency_mode == "FIX"
                and _numeric_matches(before.status.frequency_hz, value_hz)
            ):
                return before.status

            current = before
            try:
                if current.status.frequency_mode != "FIX":
                    self.transport.write(f"C{channel}:SWWV STATE,OFF")
                    fixed = self._read_configuration_snapshot(channel)
                    self._verify_configuration_closure(before=before, after=fixed)
                    expected_fixed = replace(
                        before.status,
                        frequency_mode="FIX",
                        sweep_enabled="OFF",
                        apply_raw=fixed.status.apply_raw,
                    )
                    if fixed.status != expected_fixed:
                        raise InstrumentError(
                            "SDG2000X FIX-mode selection changed non-mode channel state"
                        )
                    current = fixed
                    if _numeric_matches(current.status.frequency_hz, value_hz):
                        return current.status

                self.transport.write(f"C{channel}:BSWV FRQ,{value_hz:.12g}")
                after = self._read_configuration_snapshot(channel)
                self._verify_configuration_closure(before=current, after=after)
                if not _numeric_matches(after.status.frequency_hz, value_hz):
                    raise InstrumentError("SDG2000X frequency write readback mismatch")
                expected = replace(
                    current.status,
                    frequency_hz=after.status.frequency_hz,
                    apply_raw=after.status.apply_raw,
                )
                if after.status != expected:
                    raise InstrumentError(
                        "SDG2000X frequency transaction changed non-frequency channel state"
                    )
                return after.status
            except Exception as exc:
                self._fail_configuration_transaction(channel, exc)
                raise AssertionError("unreachable")

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
        _validate_write_check_errors(check_errors, capability="source.output")

        with self._io_lock:
            if self._configuration_writes_blocked:
                if enabled:
                    self._ensure_configuration_writes_allowed()
                self._force_output_off(channel)
                return self.get_status(channel)
            self._ensure_identity()

            previous, previous_output = self._read_status(channel)
            target = "ON" if enabled else "OFF"
            previous_context = None
            if enabled:
                previous_context = self._read_output_safety_context(channel)
                self._validate_output_enable_snapshot(
                    previous,
                    previous_output,
                    previous_context,
                )
            if previous.output == target:
                return previous

            try:
                self.transport.write(f"C{channel}:OUTP {target}")
                status, output = self._read_status(channel)
                if status.output != target:
                    raise InstrumentError("SDG2000X output write readback mismatch")
                if replace(status, output=previous.output) != previous:
                    raise InstrumentError(
                        "SDG2000X output transaction changed non-output channel state"
                    )
                if replace(output, state=previous_output.state) != previous_output:
                    raise InstrumentError(
                        "SDG2000X output transaction changed load, polarity, or power-on state"
                    )
                if enabled:
                    context = self._read_output_safety_context(channel)
                    self._validate_output_enable_snapshot(status, output, context)
                    if context != previous_context:
                        raise InstrumentError(
                            "SDG2000X output transaction changed advanced signal state"
                        )
                return status
            except Exception as exc:
                self._fail_configuration_transaction(channel, exc)
                raise AssertionError("unreachable")

    def close(self) -> None:
        with self._io_lock:
            self.transport.close()
