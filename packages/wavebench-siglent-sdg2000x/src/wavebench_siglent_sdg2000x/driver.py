from __future__ import annotations

from dataclasses import dataclass, field, replace
from math import isclose, isfinite
import re
from threading import RLock
import time
from collections.abc import Callable

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.models import ArbitraryQueryProbeResult, SourceStatus
from wavebench.instruments.source_extensions import (
    SOURCE_CONTRACT_VERSION,
    Availability,
    BasicWaveFacet,
    Observed,
    OutputFacet,
    PatchAction,
    SourceAmplitude,
    SourceAmplitudeUnit,
    SourceBasicConfigureRequest,
    SourceBasicConfigureResult,
    SourceDisplayLoad,
    SourceFieldId,
    SourceFrequencyMode,
    SourceLoadKind,
    SourceOutputPolarity,
    SourceOutputRequest,
    SourceOutputResult,
    SourceProtocolQueryRecord,
    SourceQueryEffect,
    SourceQueryExecutionRecord,
    SourceQueryItemOutcome,
    SourceQueryPhase,
    SourceReasonCode,
    SourceRuntimeIdentity,
    SourceSemanticQueryPlan,
    SourceTypedObservation,
    SourceWaveformKind,
)
from wavebench.transport.base import InstrumentTransport


_SUPPORTED_MODELS = frozenset({"SDG2042X", "SDG2082X", "SDG2122X"})
ARBITRARY_QUERY_CANDIDATES: tuple[tuple[str, str], ...] = (
    ("current_selection", "C{channel}:ARWV?"),
    ("sample_rate_mode", "C{channel}:SRATE?"),
    ("builtin_catalog", "STL? BUILDIN"),
)
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
_MIN_AMPLITUDE_VPP = 2.0e-3
_MAX_USER_AMPLITUDE_VPP = 10.0
_MAX_ABSOLUTE_OUTPUT_V = 10.0
_MIN_DUTY_PERCENT = 0.001
_MAX_DUTY_PERCENT = 99.999
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
_FUNCTION_ALIASES = {
    "SIN": "SIN",
    "SINE": "SIN",
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
}
_CORE_TO_VENDOR_FUNCTION = {
    "SIN": "SINE",
    "SQU": "SQUARE",
    "RAMP": "RAMP",
    "PULS": "PULSE",
    "NOIS": "NOISE",
    "DC": "DC",
}
_PERIODIC_FUNCTIONS = frozenset({"SIN", "SQU", "RAMP", "PULS"})
_V2_WAVEFORMS = {
    "SIN": SourceWaveformKind.SINE,
    "SQU": SourceWaveformKind.SQUARE,
    "RAMP": SourceWaveformKind.RAMP,
    "PULS": SourceWaveformKind.PULSE,
    "NOIS": SourceWaveformKind.NOISE,
    "USER": SourceWaveformKind.ARBITRARY,
    "DC": SourceWaveformKind.DC,
}
_V2_WRITABLE_FUNCTIONS = {
    SourceWaveformKind.SINE: "SINE",
    SourceWaveformKind.SQUARE: "SQUARE",
    SourceWaveformKind.RAMP: "RAMP",
    SourceWaveformKind.PULSE: "PULSE",
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
class _SelectedHarmonicStatus:
    enabled: bool
    preset: str | None
    order: int | None
    amplitude_vpp: float | None
    amplitude_dbc: float | None
    phase_deg: float | None


@dataclass(frozen=True)
class _ConfigurationSnapshot:
    status: SourceStatus
    output: _OutputStatus
    context: _OutputSafetyContext


def _validate_channel(channel: int) -> None:
    if type(channel) is not int or channel not in (1, 2):
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


def _parse_harmonic_status(response: str, *, channel: int) -> _SelectedHarmonicStatus:
    command = f"C{channel}:HARM?"
    _, body = _response_body(response, channel=channel, header="HARM")
    parameters = _parameter_pairs(
        _tokens(body, command=command),
        command=command,
        known=frozenset(
            {
                "HARMSTATE",
                "HARMTYPE",
                "HARMORDER",
                "HARMAMP",
                "HARMDBC",
                "HARMPHASE",
            }
        ),
    )
    enabled = _parse_on_off(
        _required_parameter(parameters, "HARMSTATE", command=command),
        command=command,
        field_name="harmonic state",
    )
    details = {"HARMTYPE", "HARMORDER", "HARMAMP", "HARMDBC", "HARMPHASE"}
    if not enabled and set(parameters) == {"HARMSTATE"}:
        return _SelectedHarmonicStatus(False, None, None, None, None, None)
    if set(parameters) != {"HARMSTATE", *details}:
        raise DataError(
            f"SDG2000X response for {command} must contain either disabled state only "
            "or one complete selected harmonic"
        )

    preset = parameters["HARMTYPE"].upper()
    if preset not in {"EVEN", "ODD", "ALL"}:
        raise DataError(f"unexpected SDG2000X harmonic type for {command}: {preset!r}")
    order_value = _plain_number(
        parameters["HARMORDER"],
        command=command,
        field_name="harmonic order",
    )
    if not order_value.is_integer() or not 1 <= order_value <= 16:
        raise DataError(f"SDG2000X harmonic order for {command} must be from 1 to 16")
    amplitude_vpp = _voltage(
        parameters["HARMAMP"],
        command=command,
        field_name="harmonic amplitude",
        allow_vpp=True,
    )
    if not 0 <= amplitude_vpp <= 20:
        raise DataError(f"SDG2000X harmonic amplitude for {command} is out of range")
    amplitude_dbc = _quantity(
        parameters["HARMDBC"],
        command=command,
        field_name="harmonic relative amplitude",
        unit_factors={"DBC": 1.0},
    )
    if not -200 <= amplitude_dbc <= 0:
        raise DataError(
            f"SDG2000X harmonic relative amplitude for {command} is out of range"
        )
    phase_deg = _plain_number(
        parameters["HARMPHASE"],
        command=command,
        field_name="harmonic phase",
        allow_degrees=True,
    )
    if not 0 <= phase_deg <= 360:
        raise DataError(f"SDG2000X harmonic phase for {command} is out of range")
    return _SelectedHarmonicStatus(
        enabled=enabled,
        preset=preset,
        order=int(order_value),
        amplitude_vpp=amplitude_vpp,
        amplitude_dbc=amplitude_dbc,
        phase_deg=phase_deg,
    )


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


def _runtime_identity_from_idn(response: str) -> SourceRuntimeIdentity:
    """Parse the documented IDN variants into the V2 identity contract."""

    value = _response_text(response, command="*IDN?")
    fields = tuple(item.strip() for item in value.split(","))
    model = parse_idn_model(value)
    if len(fields) == 4:
        manufacturer = fields[0]
        firmware_id = fields[3]
    else:
        manufacturer = "SIGLENT Technologies"
        firmware_id = fields[4]
    return SourceRuntimeIdentity(
        manufacturer=manufacturer,
        model=model,
        firmware_id=firmware_id,
    )


@dataclass
class SDG2000XSource:
    transport: InstrumentTransport
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _identity_model: str | None = field(default=None, init=False, repr=False)
    _configuration_writes_blocked: bool = field(default=False, init=False, repr=False)
    _v2_preflight_snapshots: dict[int, _ConfigurationSnapshot] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def _ensure_identity(self) -> str:
        if self._identity_model is None:
            self._identity_model = parse_idn_model(self.transport.query("*IDN?"))
        return self._identity_model

    def idn(self) -> str:
        with self._io_lock:
            response = _response_text(self.transport.query("*IDN?"), command="*IDN?")
            self._identity_model = parse_idn_model(response)
            return response

    @staticmethod
    def _v2_missing() -> Observed[object]:
        return Observed.missing(
            Availability.NOT_APPLICABLE,
            SourceReasonCode.INACTIVE_BY_ANCHOR,
        )

    @classmethod
    def _v2_basic_facet(cls, status: SourceStatus) -> BasicWaveFacet:
        try:
            waveform_kind = _V2_WAVEFORMS[status.function]
        except KeyError as exc:  # pragma: no cover - status parsing is closed above
            raise DataError(
                f"SDG2000X cannot map function {status.function!r} to Source V2"
            ) from exc
        frequency_mode = (
            SourceFrequencyMode.FIXED
            if status.frequency_mode == "FIX"
            else SourceFrequencyMode.SWEEP
        )
        amplitude = (
            Observed.value_of(
                SourceAmplitude(
                    value=status.amplitude,
                    unit=SourceAmplitudeUnit.VPP,
                )
            )
            if status.amplitude is not None and status.amplitude_unit == "VPP"
            else cls._v2_missing()
        )
        return BasicWaveFacet(
            waveform_kind=Observed.value_of(waveform_kind),
            waveform_id=Observed.value_of(waveform_kind.value),
            frequency_mode=Observed.value_of(frequency_mode),
            frequency_hz=(
                Observed.value_of(status.frequency_hz)
                if status.frequency_hz is not None
                else cls._v2_missing()
            ),
            amplitude=amplitude,
            offset_v=(
                Observed.value_of(status.offset_v)
                if status.offset_v is not None
                else cls._v2_missing()
            ),
            phase_deg=(
                Observed.value_of(status.phase_deg)
                if status.phase_deg is not None
                else cls._v2_missing()
            ),
            square_duty_cycle_percent=(
                Observed.value_of(status.square_duty_cycle_percent)
                if status.square_duty_cycle_percent is not None
                else cls._v2_missing()
            ),
        )

    @staticmethod
    def _v2_output_facet(output: _OutputStatus) -> OutputFacet:
        if output.state not in {"ON", "OFF"}:
            raise DataError(f"unexpected SDG2000X output state: {output.state!r}")
        if output.polarity == "NORMAL":
            polarity = SourceOutputPolarity.NORMAL
        elif output.polarity == "INVERTED":
            polarity = SourceOutputPolarity.INVERTED
        else:  # pragma: no cover - output parsing is closed above
            raise DataError(f"unexpected SDG2000X output polarity: {output.polarity!r}")
        display_load = (
            SourceDisplayLoad(SourceLoadKind.HIGH_IMPEDANCE)
            if output.load_ohm is None
            else SourceDisplayLoad(SourceLoadKind.RESISTIVE, output.load_ohm)
        )
        return OutputFacet(
            enabled=Observed.value_of(output.state == "ON"),
            display_load=Observed.value_of(display_load),
            polarity=Observed.value_of(polarity),
        )

    @staticmethod
    def _v2_snapshot_query_count(snapshot: _ConfigurationSnapshot) -> int:
        return 9 if snapshot.status.function == "SIN" else 8

    @staticmethod
    def _v2_validate_query_plan(plan: SourceSemanticQueryPlan) -> None:
        if not isinstance(plan, SourceSemanticQueryPlan):
            raise DataError("SDG2000X Source V2 query plan has an invalid type")
        if plan.contract_version != SOURCE_CONTRACT_VERSION:
            raise DataError("SDG2000X Source V2 query plan has an unsupported version")
        if SourceQueryEffect.PURE_READ not in plan.allowed_effects:
            raise DataError("SDG2000X Source V2 query plan does not permit pure reads")
        if time.monotonic() > plan.deadline_monotonic:
            raise DataError("SDG2000X Source V2 query plan deadline has expired")
        if sum(item.max_queries for item in plan.items) > plan.max_queries:
            raise DataError(
                "SDG2000X Source V2 query plan exceeds its declared total query budget"
            )

        phase_fields: dict[SourceQueryPhase, dict[SourceFieldId, set[int | None]]] = {}
        for item in plan.items:
            if item.effect is not SourceQueryEffect.PURE_READ:
                raise DataError("SDG2000X Source V2 snapshots only support pure reads")
            current = phase_fields.setdefault(item.phase, {})
            for field_ref in item.fields:
                if field_ref.field is SourceFieldId.IDENTITY:
                    if field_ref.target.scope.value != "instrument":
                        raise DataError("SDG2000X Source V2 identity must be instrument scoped")
                    channel = None
                elif field_ref.field in {SourceFieldId.BASIC, SourceFieldId.OUTPUT}:
                    if field_ref.target.scope.value != "channel":
                        raise DataError("SDG2000X Source V2 channel facets must be channel scoped")
                    channel = field_ref.target.channel
                    _validate_channel(channel)
                else:
                    raise DataError(
                        "SDG2000X Source V2 query plan requests an unsupported field"
                    )
                channels = current.setdefault(field_ref.field, set())
                if channel in channels:
                    raise DataError("SDG2000X Source V2 query plan repeats a field target")
                channels.add(channel)

        for fields in phase_fields.values():
            basic_channels = fields.get(SourceFieldId.BASIC, set())
            output_channels = fields.get(SourceFieldId.OUTPUT, set())
            identity_targets = fields.get(SourceFieldId.IDENTITY, set())
            if basic_channels or output_channels:
                if identity_targets != {None}:
                    raise DataError(
                        "SDG2000X Source V2 channel snapshots require one identity anchor"
                    )
                if not output_channels <= basic_channels:
                    raise DataError(
                        "SDG2000X Source V2 output snapshots require matching basic anchors"
                    )

    @staticmethod
    def _v2_query_with_deadline(
        plan: SourceSemanticQueryPlan,
        query: Callable[[str], str],
        command: str,
    ) -> str:
        if time.monotonic() > plan.deadline_monotonic:
            raise DataError("SDG2000X Source V2 query plan deadline has expired")
        return query(command)

    def _v2_query_identity(
        self,
        plan: SourceSemanticQueryPlan,
        query: Callable[[str], str],
    ) -> SourceRuntimeIdentity:
        identity = _runtime_identity_from_idn(
            self._v2_query_with_deadline(plan, query, "*IDN?")
        )
        self._identity_model = identity.model
        return identity

    def execute_source_query_plan_v2(
        self,
        plan: SourceSemanticQueryPlan,
    ) -> SourceQueryExecutionRecord:
        """Execute the core-owned pure-read Source V2 plan without selector writes."""

        self._v2_validate_query_plan(plan)
        with self._io_lock:
            records: dict[str, SourceProtocolQueryRecord] = {}
            after_snapshots: dict[int, _ConfigurationSnapshot] = {}

            def query(command: str) -> str:
                return self._v2_query_with_deadline(
                    plan,
                    self.transport.query,
                    command,
                )

            for phase in SourceQueryPhase:
                phase_items = tuple(item for item in plan.items if item.phase is phase)
                if not phase_items:
                    continue
                identity_item = next(
                    (
                        item
                        for item in phase_items
                        if any(
                            field_ref.field is SourceFieldId.IDENTITY
                            for field_ref in item.fields
                        )
                    ),
                    None,
                )
                identity = (
                    self._v2_query_identity(plan, self.transport.query)
                    if identity_item is not None
                    else None
                )
                snapshots: dict[int, _ConfigurationSnapshot] = {}
                for item in phase_items:
                    for field_ref in item.fields:
                        if field_ref.field is SourceFieldId.BASIC:
                            assert field_ref.target.channel is not None
                            snapshots[field_ref.target.channel] = self._read_configuration_snapshot(
                                field_ref.target.channel,
                                query=query,
                            )
                if phase is SourceQueryPhase.ANCHOR_AFTER:
                    after_snapshots = snapshots

                for item in phase_items:
                    observations: list[SourceTypedObservation] = []
                    query_count = 0
                    for field_ref in item.fields:
                        if field_ref.field is SourceFieldId.IDENTITY:
                            assert identity is not None
                            observations.append(SourceTypedObservation(field_ref, identity))
                            query_count += 1
                        elif field_ref.field is SourceFieldId.BASIC:
                            assert field_ref.target.channel is not None
                            snapshot = snapshots[field_ref.target.channel]
                            observations.append(
                                SourceTypedObservation(
                                    field_ref,
                                    self._v2_basic_facet(snapshot.status),
                                )
                            )
                            query_count += self._v2_snapshot_query_count(snapshot)
                        else:
                            assert field_ref.field is SourceFieldId.OUTPUT
                            assert field_ref.target.channel is not None
                            snapshot = snapshots[field_ref.target.channel]
                            observations.append(
                                SourceTypedObservation(
                                    field_ref,
                                    self._v2_output_facet(snapshot.output),
                                )
                            )
                    if query_count > item.max_queries:
                        raise DataError(
                            "SDG2000X Source V2 query plan under-declares a snapshot query"
                        )
                    records[item.item_id] = SourceProtocolQueryRecord(
                        item_id=item.item_id,
                        effect=item.effect,
                        outcome=SourceQueryItemOutcome.OBSERVED,
                        query_count=query_count,
                        observations=tuple(observations),
                    )

            if not after_snapshots:
                raise DataError("SDG2000X Source V2 query plan has no after anchors")
            self._v2_preflight_snapshots = dict(after_snapshots)
            ordered_records = tuple(records[item.item_id] for item in plan.items)
            return SourceQueryExecutionRecord(
                contract_version=SOURCE_CONTRACT_VERSION,
                plan_id=plan.plan_id,
                items=ordered_records,
                query_count=sum(item.query_count for item in ordered_records),
            )

    def _v2_preflight_snapshot(self, channel: int) -> _ConfigurationSnapshot:
        _validate_channel(channel)
        try:
            return self._v2_preflight_snapshots[channel]
        except KeyError as exc:
            raise DataError(
                "SDG2000X Source V2 write requires a fresh source.snapshot_v2 preflight"
            ) from exc

    @classmethod
    def _validate_v2_basic_preflight(cls, snapshot: _ConfigurationSnapshot) -> None:
        if snapshot.status.output != "OFF":
            raise DataError("SDG2000X Source V2 basic configuration requires output OFF")
        if snapshot.status.frequency_mode != "FIX" or snapshot.status.sweep_enabled != "OFF":
            raise DataError(
                "SDG2000X Source V2 basic configuration requires fixed-frequency mode"
            )
        cls._validate_advanced_modes_off(snapshot.context)
        if snapshot.status.amplitude is None or snapshot.status.amplitude_unit != "VPP":
            raise DataError(
                "SDG2000X Source V2 basic configuration requires a verified Vpp amplitude"
            )
        if snapshot.status.offset_v is None:
            raise DataError(
                "SDG2000X Source V2 basic configuration requires a verified voltage offset"
            )

    @staticmethod
    def _v2_result_amplitude_offset(status: SourceStatus) -> tuple[SourceAmplitude, float]:
        if status.amplitude is None or status.amplitude_unit != "VPP":
            raise DataError("SDG2000X Source V2 result requires a verified Vpp amplitude")
        if status.offset_v is None:
            raise DataError("SDG2000X Source V2 result requires a verified voltage offset")
        return SourceAmplitude(status.amplitude, SourceAmplitudeUnit.VPP), status.offset_v

    def configure_source_basic_v2(
        self,
        request: SourceBasicConfigureRequest,
    ) -> SourceBasicConfigureResult:
        """Perform one previously audited SDG basic write from a V2 preflight cache."""

        if not isinstance(request, SourceBasicConfigureRequest):
            raise DataError("SDG2000X Source V2 basic request has an invalid type")
        _validate_channel(request.channel)
        fields = tuple(
            (name, patch_value.value)
            for name, patch_value in (
                ("waveform_kind", request.patch.waveform_kind),
                ("frequency_hz", request.patch.frequency_hz),
                ("amplitude_vpp", request.patch.amplitude_vpp),
                ("offset_v", request.patch.offset_v),
                (
                    "square_duty_cycle_percent",
                    request.patch.square_duty_cycle_percent,
                ),
            )
            if patch_value.action is PatchAction.SET
        )
        if len(fields) != 1:
            raise DataError(
                "SDG2000X Source V2 basic configuration supports one SET field per write"
            )
        field_name, raw_value = fields[0]
        if field_name == "offset_v":
            raise DataError(
                "SDG2000X Source V2 offset writes are not yet supported by verified SCPI"
            )

        with self._io_lock:
            self._ensure_configuration_writes_allowed()
            before = self._v2_preflight_snapshot(request.channel)
            self._validate_v2_basic_preflight(before)
            status = before.status
            model = self._identity_model
            if model is None:  # pragma: no cover - cache is only filled after identity
                raise DataError("SDG2000X Source V2 preflight identity is unavailable")

            updated = status
            command: str | None = None
            if field_name == "frequency_hz":
                value_hz = _finite_number(raw_value, field_name="frequency")
                self._validate_frequency_range(
                    model=model,
                    function=status.function,
                    value_hz=value_hz,
                )
                if not _numeric_matches(status.frequency_hz, value_hz):
                    command = f"C{request.channel}:BSWV FRQ,{value_hz:.12g}"
                    updated = replace(status, frequency_hz=value_hz)
            elif field_name == "amplitude_vpp":
                value_vpp = _finite_number(raw_value, field_name="amplitude")
                if not _MIN_AMPLITUDE_VPP <= value_vpp <= _MAX_USER_AMPLITUDE_VPP:
                    raise DataError("SDG2000X amplitude must be from 0.002 Vpp to 10 Vpp")
                assert status.offset_v is not None
                if abs(status.offset_v) + value_vpp / 2 > _MAX_ABSOLUTE_OUTPUT_V:
                    raise DataError(
                        "SDG2000X amplitude and offset exceed the absolute voltage envelope"
                    )
                if not _numeric_matches(status.amplitude, value_vpp):
                    command = f"C{request.channel}:BSWV AMP,{value_vpp:.12g}"
                    updated = replace(status, amplitude=value_vpp, amplitude_unit="VPP")
            elif field_name == "waveform_kind":
                if not isinstance(raw_value, SourceWaveformKind):
                    raise DataError("SDG2000X Source V2 waveform kind has an invalid type")
                try:
                    vendor_function = _V2_WRITABLE_FUNCTIONS[raw_value]
                except KeyError as exc:
                    raise DataError(
                        "SDG2000X Source V2 only configures sine, square, ramp, and pulse"
                    ) from exc
                target_function = _WAVE_FUNCTIONS[vendor_function]
                if status.frequency_hz is None:
                    raise DataError(
                        "SDG2000X Source V2 waveform changes require a verified frequency"
                    )
                self._validate_frequency_range(
                    model=model,
                    function=target_function,
                    value_hz=status.frequency_hz,
                )
                if status.function != target_function:
                    command = f"C{request.channel}:BSWV WVTP,{vendor_function}"
                    updated = replace(
                        status,
                        function=target_function,
                        square_duty_cycle_percent=(
                            status.square_duty_cycle_percent
                            if target_function == "SQU"
                            else None
                        ),
                    )
            else:
                assert field_name == "square_duty_cycle_percent"
                duty_percent = _finite_number(raw_value, field_name="duty cycle percent")
                if not _MIN_DUTY_PERCENT <= duty_percent <= _MAX_DUTY_PERCENT:
                    raise DataError("SDG2000X duty cycle must be from 0.001% to 99.999%")
                if status.function != "SQU" or status.square_duty_cycle_percent is None:
                    raise DataError("SDG2000X duty-cycle writes require the SQUARE function")
                if not _numeric_matches(status.square_duty_cycle_percent, duty_percent):
                    command = f"C{request.channel}:BSWV DUTY,{duty_percent:.12g}"
                    updated = replace(status, square_duty_cycle_percent=duty_percent)

            if command is not None:
                self.transport.write(command)
            self._v2_preflight_snapshots[request.channel] = replace(
                before,
                status=updated,
            )
            return SourceBasicConfigureResult(
                channel=request.channel,
                basic=self._v2_basic_facet(updated),
                output_enabled=False,
            )

    def set_source_output_v2(
        self,
        request: SourceOutputRequest,
    ) -> SourceOutputResult:
        """Write exactly one SDG output transition from a V2 preflight cache."""

        if not isinstance(request, SourceOutputRequest):
            raise DataError("SDG2000X Source V2 output request has an invalid type")
        _validate_channel(request.channel)
        with self._io_lock:
            before = self._v2_preflight_snapshot(request.channel)
            target = "ON" if request.enabled else "OFF"
            if request.enabled:
                self._ensure_configuration_writes_allowed()
                self._validate_output_enable_snapshot(
                    before.status,
                    before.output,
                    before.context,
                )
                if before.status.output != target:
                    self.transport.write(f"C{request.channel}:OUTP {target}")
            else:
                # Core recovery may reach this path after a main-write result is unknown.
                self.transport.write(f"C{request.channel}:OUTP {target}")

            updated_status = replace(before.status, output=target)
            updated_output = replace(before.output, state=target)
            self._v2_preflight_snapshots[request.channel] = replace(
                before,
                status=updated_status,
                output=updated_output,
            )
            if not request.enabled:
                return SourceOutputResult(channel=request.channel, enabled=False)
            amplitude, offset_v = self._v2_result_amplitude_offset(updated_status)
            return SourceOutputResult(
                channel=request.channel,
                enabled=True,
                final_amplitude=amplitude,
                final_offset_v=offset_v,
            )

    def _read_status(
        self,
        channel: int,
        *,
        query: Callable[[str], str] | None = None,
    ) -> tuple[SourceStatus, _OutputStatus]:
        self._ensure_identity()
        query_response = self.transport.query if query is None else query
        output = _parse_output(
            query_response(f"C{channel}:OUTP?"),
            channel=channel,
        )
        apply_raw, basic = _parse_basic_wave(
            query_response(f"C{channel}:BSWV?"),
            channel=channel,
        )
        sweep_enabled = _parse_sweep_state(
            query_response(f"C{channel}:SWWV?"),
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

    def _read_output_safety_context(
        self,
        channel: int,
        *,
        function: str,
        query: Callable[[str], str] | None = None,
    ) -> _OutputSafetyContext:
        query_response = self.transport.query if query is None else query
        modulation_enabled = _parse_named_state(
            query_response(f"C{channel}:MDWV?"),
            channel=channel,
            header="MDWV",
            state_name="STATE",
        )
        burst_enabled = _parse_named_state(
            query_response(f"C{channel}:BTWV?"),
            channel=channel,
            header="BTWV",
            state_name="STATE",
        )
        harmonic_enabled = False
        if function == "SIN":
            harmonic_enabled = _parse_harmonic_status(
                query_response(f"C{channel}:HARM?"),
                channel=channel,
            ).enabled
        combine_enabled = _parse_combine_state(
            query_response(f"C{channel}:CMBN?"),
            channel=channel,
        )
        noise_add_enabled = _parse_named_state(
            query_response(f"C{channel}:NOISE_ADD?"),
            channel=channel,
            header="NOISE_ADD",
            state_name="STATE",
        )
        coupling = _parse_coupling_states(query_response("COUP?"))
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

    def _read_configuration_snapshot(
        self,
        channel: int,
        *,
        query: Callable[[str], str] | None = None,
    ) -> _ConfigurationSnapshot:
        status, output = self._read_status(channel, query=query)
        return _ConfigurationSnapshot(
            status=status,
            output=output,
            context=self._read_output_safety_context(
                channel,
                function=status.function,
                query=query,
            ),
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
                raise AssertionError("unreachable")  # pragma: no cover

    def set_amplitude_vpp(
        self,
        channel: int,
        value_vpp: float,
        *,
        check_errors: bool = True,
    ) -> SourceStatus:
        _validate_channel(channel)
        value_vpp = _finite_number(value_vpp, field_name="amplitude")
        if not _MIN_AMPLITUDE_VPP <= value_vpp <= _MAX_USER_AMPLITUDE_VPP:
            raise DataError("SDG2000X amplitude must be from 0.002 Vpp to 10 Vpp")
        _validate_write_check_errors(check_errors, capability="source.set_amplitude_vpp")

        with self._io_lock:
            self._ensure_configuration_writes_allowed()
            self._ensure_identity()
            before = self._read_configuration_snapshot(channel)
            self._validate_basic_configuration_snapshot(before)
            if before.status.frequency_mode != "FIX":
                raise DataError("SDG2000X amplitude writes require FIX mode")
            if before.status.amplitude is None or before.status.amplitude_unit != "VPP":
                raise DataError(
                    f"SDG2000X amplitude is not applicable to function {before.status.function}"
                )
            if before.status.offset_v is None:
                raise DataError("SDG2000X amplitude writes require a verified voltage offset")
            if abs(before.status.offset_v) + value_vpp / 2 > _MAX_ABSOLUTE_OUTPUT_V:
                raise DataError(
                    "SDG2000X amplitude and offset exceed the absolute voltage envelope"
                )
            if _numeric_matches(before.status.amplitude, value_vpp):
                return before.status

            try:
                self.transport.write(f"C{channel}:BSWV AMP,{value_vpp:.12g}")
                after = self._read_configuration_snapshot(channel)
                self._verify_configuration_closure(before=before, after=after)
                if after.status.amplitude_unit != "VPP" or not _numeric_matches(
                    after.status.amplitude,
                    value_vpp,
                ):
                    raise InstrumentError("SDG2000X amplitude write readback mismatch")
                expected = replace(
                    before.status,
                    amplitude=after.status.amplitude,
                    apply_raw=after.status.apply_raw,
                )
                if after.status != expected:
                    raise InstrumentError(
                        "SDG2000X amplitude transaction changed non-amplitude channel state"
                    )
                return after.status
            except Exception as exc:
                self._fail_configuration_transaction(channel, exc)
                raise AssertionError("unreachable")  # pragma: no cover

    def set_function(
        self,
        channel: int,
        function: str,
        *,
        check_errors: bool = True,
    ) -> SourceStatus:
        _validate_channel(channel)
        if not isinstance(function, str):
            raise DataError(
                "SDG2000X function must be one of: sin, squ, ramp/triangle, "
                "puls, nois, dc"
            )
        normalized = function.strip().upper()
        try:
            target = _FUNCTION_ALIASES[normalized]
        except KeyError as exc:
            raise DataError(
                "SDG2000X function must be one of: sin, squ, ramp/triangle, "
                "puls, nois, dc"
            ) from exc
        _validate_write_check_errors(check_errors, capability="source.set_function")

        with self._io_lock:
            self._ensure_configuration_writes_allowed()
            model = self._ensure_identity()
            before = self._read_configuration_snapshot(channel)
            self._validate_advanced_modes_off(before.context)
            if before.status.frequency_mode != "FIX":
                raise DataError("SDG2000X function writes require FIX mode")
            if target in {"NOIS", "DC"} and before.status.output != "OFF":
                raise DataError("SDG2000X NOISE and DC function writes require output OFF")
            if target in _PERIODIC_FUNCTIONS and before.status.frequency_hz is not None:
                self._validate_frequency_range(
                    model=model,
                    function=target,
                    value_hz=before.status.frequency_hz,
                )
            if before.status.output == "ON":
                self._validate_output_enable_snapshot(
                    before.status,
                    before.output,
                    before.context,
                )
            if before.status.function == target:
                return before.status

            try:
                vendor_target = _CORE_TO_VENDOR_FUNCTION[target]
                self.transport.write(f"C{channel}:BSWV WVTP,{vendor_target}")
                after = self._read_configuration_snapshot(channel)
                self._verify_configuration_closure(before=before, after=after)
                if after.status.function != target:
                    raise InstrumentError("SDG2000X function write readback mismatch")
                if target in _PERIODIC_FUNCTIONS:
                    self._validate_frequency_range(
                        model=model,
                        function=target,
                        value_hz=after.status.frequency_hz or 0.0,
                    )
                    if (
                        after.status.amplitude is None
                        or after.status.amplitude_unit != "VPP"
                        or after.status.amplitude > _MAX_USER_AMPLITUDE_VPP
                        or after.status.offset_v is None
                        or abs(after.status.offset_v) + after.status.amplitude / 2
                        > _MAX_ABSOLUTE_OUTPUT_V
                    ):
                        raise InstrumentError(
                            "SDG2000X function write produced an unsafe periodic-wave state"
                        )
                    if before.status.function in _PERIODIC_FUNCTIONS:
                        common_fields_match = (
                            _numeric_matches(
                                after.status.frequency_hz,
                                before.status.frequency_hz or 0.0,
                            )
                            and _numeric_matches(
                                after.status.amplitude,
                                before.status.amplitude or 0.0,
                            )
                            and _numeric_matches(
                                after.status.offset_v,
                                before.status.offset_v or 0.0,
                            )
                        )
                        if not common_fields_match:
                            raise InstrumentError(
                                "SDG2000X function transaction changed a common waveform field"
                            )
                        phase_should_match = (
                            before.status.phase_deg is not None
                            and after.status.phase_deg is not None
                        )
                        if phase_should_match and not _numeric_matches(
                            after.status.phase_deg,
                            before.status.phase_deg or 0.0,
                        ):
                            raise InstrumentError(
                                "SDG2000X function transaction changed common phase"
                            )
                return after.status
            except Exception as exc:
                self._fail_configuration_transaction(channel, exc)
                raise AssertionError("unreachable")  # pragma: no cover

    def set_square_duty_cycle(
        self,
        channel: int,
        duty_percent: float,
        *,
        check_errors: bool = True,
    ) -> SourceStatus:
        _validate_channel(channel)
        duty_percent = _finite_number(duty_percent, field_name="duty cycle percent")
        if not _MIN_DUTY_PERCENT <= duty_percent <= _MAX_DUTY_PERCENT:
            raise DataError("SDG2000X duty cycle must be from 0.001% to 99.999%")
        _validate_write_check_errors(
            check_errors,
            capability="source.set_square_duty_cycle",
        )

        with self._io_lock:
            self._ensure_configuration_writes_allowed()
            self._ensure_identity()
            before = self._read_configuration_snapshot(channel)
            self._validate_basic_configuration_snapshot(before)
            if before.status.frequency_mode != "FIX":
                raise DataError("SDG2000X duty-cycle writes require FIX mode")
            if before.status.function != "SQU":
                raise DataError("SDG2000X duty-cycle writes require the SQUARE function")
            if before.status.square_duty_cycle_percent is None:
                raise DataError("SDG2000X square duty-cycle readback is unavailable")
            if _numeric_matches(
                before.status.square_duty_cycle_percent,
                duty_percent,
            ):
                return before.status

            try:
                self.transport.write(f"C{channel}:BSWV DUTY,{duty_percent:.12g}")
                after = self._read_configuration_snapshot(channel)
                self._verify_configuration_closure(before=before, after=after)
                if not _numeric_matches(
                    after.status.square_duty_cycle_percent,
                    duty_percent,
                ):
                    raise InstrumentError("SDG2000X duty-cycle write readback mismatch")
                expected = replace(
                    before.status,
                    square_duty_cycle_percent=after.status.square_duty_cycle_percent,
                    apply_raw=after.status.apply_raw,
                )
                if after.status != expected:
                    raise InstrumentError(
                        "SDG2000X duty-cycle transaction changed non-duty channel state"
                    )
                return after.status
            except Exception as exc:
                self._fail_configuration_transaction(channel, exc)
                raise AssertionError("unreachable")  # pragma: no cover

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
                previous_context = self._read_output_safety_context(
                    channel,
                    function=previous.function,
                )
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
                    context = self._read_output_safety_context(
                        channel,
                        function=status.function,
                    )
                    self._validate_output_enable_snapshot(status, output, context)
                    if context != previous_context:
                        raise InstrumentError(
                            "SDG2000X output transaction changed advanced signal state"
                        )
                return status
            except Exception as exc:
                self._fail_configuration_transaction(channel, exc)
                raise AssertionError("unreachable")  # pragma: no cover

    def probe_arbitrary_queries(self, channel: int) -> list[ArbitraryQueryProbeResult]:
        _validate_channel(channel)
        with self._io_lock:
            self._ensure_identity()
            results: list[ArbitraryQueryProbeResult] = []
            for label, template in ARBITRARY_QUERY_CANDIDATES:
                command = template.format(channel=channel)
                response: str | None = None
                exception: str | None = None
                try:
                    response = _response_text(
                        self.transport.query(command),
                        command=command,
                    )
                except Exception as exc:
                    exception = f"{type(exc).__name__}: {exc}"
                results.append(
                    ArbitraryQueryProbeResult(
                        label=label,
                        command=command,
                        response=response,
                        errors=[],
                        exception=exception,
                    )
                )
            return results

    def close(self) -> None:
        with self._io_lock:
            self.transport.close()
