from __future__ import annotations

from dataclasses import dataclass
import math
import re

from wavebench.errors import DataError
from wavebench.instruments.models import ScopeChannelInputStateV2


@dataclass(frozen=True)
class RigolIdentity:
    manufacturer: str
    model: str
    serial_number: str
    firmware: str


@dataclass(frozen=True)
class RigolWaveformPreamble:
    format_code: int
    type_code: int
    points: int
    count: int
    x_increment: float
    x_origin: float
    x_reference: float
    y_increment: float
    y_origin: float
    y_reference: float


_STRICT_INTEGER = re.compile(r"[0-9]+")
_WAVEFORM_SOURCES = frozenset(
    (
        *(f"D{index}" for index in range(16)),
        *(f"CHAN{index}" for index in range(1, 5)),
        *(f"MATH{index}" for index in range(1, 5)),
    )
)
_MATH_OPERATORS = frozenset(
    {
        "ADD",
        "SUBT",
        "MULT",
        "DIV",
        "AND",
        "OR",
        "XOR",
        "NOT",
        "FFT",
        "INTG",
        "DIFF",
        "SQRT",
        "LOG",
        "LN",
        "EXP",
        "ABS",
        "LPAS",
        "HPAS",
        "BPAS",
        "BST",
        "AXB",
    }
)
_FFT_SOURCES = frozenset(f"CHAN{index}" for index in range(1, 5))
_FFT_WINDOWS = frozenset({"RECT", "BLAC", "HANN", "HAMM", "FLAT", "TRI"})
_FFT_VERTICAL_UNITS = frozenset({"VRMS", "DB"})
_ACQUISITION_TYPES = frozenset({"NORM", "PEAK", "AVER", "HRES"})
MSO8104_ACQUISITION_STATUS_V2_READABLE_FIELDS = (
    "acquisition_type",
    "sample_rate_hz",
    "memory_depth",
    "average",
    "average.configured_count",
)
MSO8104_ACQUISITION_STATUS_V2_CONDITIONALLY_APPLICABLE_FIELDS = ("average",)
MSO8104_MEASUREMENT_STATISTICS_ITEMS = (
    "VMAX",
    "VMIN",
    "VPP",
    "VTOP",
    "VBASV",
    "VAMP",
    "VAVG",
    "VRMS",
    "OVERSHOOT",
    "PRESHOOT",
    "MAREA",
    "MPAREA",
    "PERIOD",
    "FREQUENCY",
    "RTIME",
    "FTIME",
    "PWIDTH",
    "NWIDTH",
    "PDUTY",
    "NDUTY",
    "TVMAX",
    "TVMIN",
    "PSLEWRATE",
    "NSLEWRATE",
    "VUPPER",
    "VMID",
    "VLOWER",
    "VARIANCE",
    "PVRMS",
    "PPULSES",
    "NPULSES",
    "PEDGES",
    "NEDGES",
    "RRDELAY",
    "RFDELAY",
    "FRDELAY",
    "FFDELAY",
    "RRPHASE",
    "RFPHASE",
    "FRPHASE",
    "FFPHASE",
)
MSO8104_MEASUREMENT_STATISTICS_TWO_SOURCE_ITEMS = frozenset(
    {
        "RRDELAY",
        "RFDELAY",
        "FRDELAY",
        "FFDELAY",
        "RRPHASE",
        "RFPHASE",
        "FRPHASE",
        "FFPHASE",
    }
)
MSO8104_MEASUREMENT_STATISTICS_DIGITAL_SOURCE_ITEMS = frozenset(
    {
        "PERIOD",
        "FREQUENCY",
        "PWIDTH",
        "NWIDTH",
        "PDUTY",
        "NDUTY",
        *MSO8104_MEASUREMENT_STATISTICS_TWO_SOURCE_ITEMS,
    }
)
MSO8104_MEASUREMENT_STATISTICS_ANALOG_MATH_SOURCES = frozenset(
    {
        *(f"CHAN{index}" for index in range(1, 5)),
        *(f"MATH{index}" for index in range(1, 5)),
    }
)
MSO8104_MEASUREMENT_STATISTICS_DIGITAL_SOURCES = frozenset(
    f"D{index}" for index in range(16)
)


def parse_mso8104_identity(response: str) -> RigolIdentity:
    normalized = response.strip()
    parts = tuple(item.strip() for item in normalized.split(",", 3))
    if len(parts) != 4 or any(not item for item in parts):
        raise DataError(f"invalid MSO8104 *IDN? response: {response!r}")
    manufacturer, model, serial_number, firmware = parts
    if manufacturer.upper() != "RIGOL TECHNOLOGIES":
        raise DataError(
            f"unexpected MSO8104 manufacturer in *IDN? response: {manufacturer!r}"
        )
    if model.upper() != "MSO8104":
        raise DataError(f"unexpected MSO8104 model in *IDN? response: {model!r}")
    return RigolIdentity(
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        firmware=firmware,
    )


def _parse_enum(response: str, *, field: str, allowed: frozenset[str]) -> str:
    normalized = response.strip().upper()
    if normalized not in allowed:
        raise DataError(f"invalid MSO8104 {field} response: {response!r}")
    return normalized


def parse_waveform_source(response: str) -> str:
    return _parse_enum(response, field="waveform source", allowed=_WAVEFORM_SOURCES)


def parse_math_operator(response: str) -> str:
    return _parse_enum(response, field="math operator", allowed=_MATH_OPERATORS)


def parse_fft_source(response: str) -> str:
    return _parse_enum(response, field="FFT source", allowed=_FFT_SOURCES)


def parse_fft_window(response: str) -> str:
    return _parse_enum(response, field="FFT window", allowed=_FFT_WINDOWS)


def parse_fft_vertical_unit(response: str) -> str:
    return _parse_enum(response, field="FFT vertical unit", allowed=_FFT_VERTICAL_UNITS)


def parse_acquisition_type(response: str) -> str:
    return _parse_enum(response, field="acquisition type", allowed=_ACQUISITION_TYPES)


def parse_waveform_mode(response: str) -> str:
    return _parse_enum(
        response,
        field="waveform mode",
        allowed=frozenset({"NORM", "MAX", "RAW", "TRAC"}),
    )


def parse_waveform_format(response: str) -> str:
    return _parse_enum(
        response,
        field="waveform format",
        allowed=frozenset({"BYTE", "WORD", "ASC"}),
    )


def parse_display_state(response: str) -> bool:
    return parse_boolean_state(response, field="channel display")


def parse_boolean_state(response: str, *, field: str) -> bool:
    normalized = response.strip()
    if normalized not in {"0", "1"}:
        raise DataError(f"invalid MSO8104 {field} response: {response!r}")
    return normalized == "1"


def parse_timebase_mode(response: str) -> str:
    return _parse_enum(
        response,
        field="timebase mode",
        allowed=frozenset({"MAIN", "XY", "ROLL"}),
    )


def parse_trigger_status(response: str) -> str:
    return _parse_enum(
        response,
        field="trigger status",
        allowed=frozenset({"TD", "WAIT", "RUN", "AUTO", "STOP"}),
    )


def parse_cursor_mode(response: str) -> str:
    return _parse_enum(
        response,
        field="cursor mode",
        allowed=frozenset({"MAN", "TRAC", "XY", "MEAS"}),
    )


def parse_manual_cursor_type(response: str) -> str:
    return _parse_enum(
        response,
        field="manual cursor type",
        allowed=frozenset({"HBA", "VBA", "TIME", "AMPL"}),
    )


def parse_cursor_source(response: str) -> str:
    return _parse_enum(
        response,
        field="cursor source",
        allowed=frozenset(
            {
                *(f"CHAN{index}" for index in range(1, 5)),
                *(f"MATH{index}" for index in range(1, 5)),
                "LA",
                "NONE",
            }
        ),
    )


def parse_cursor_time_unit(response: str) -> str:
    return _parse_enum(
        response,
        field="manual cursor horizontal unit",
        allowed=frozenset({"SEC", "HZ", "DEGR", "PERC"}),
    )


def parse_cursor_vertical_unit(response: str) -> str:
    return _parse_enum(
        response,
        field="manual cursor vertical unit",
        allowed=frozenset({"SOUR", "PERC"}),
    )


def parse_finite_float(response: str, *, field: str) -> float:
    try:
        value = float(response.strip())
    except ValueError as exc:
        raise DataError(f"invalid MSO8104 {field} response: {response!r}") from exc
    if not math.isfinite(value):
        raise DataError(f"non-finite MSO8104 {field} response: {response!r}")
    return value


def parse_positive_finite_float(response: str, *, field: str) -> float:
    value = parse_finite_float(response, field=field)
    if value <= 0:
        raise DataError(f"MSO8104 {field} must be positive, got {response!r}")
    return value


def parse_positive_scientific_integer(response: str, *, field: str) -> int:
    value = parse_positive_finite_float(response, field=field)
    if not value.is_integer():
        raise DataError(f"MSO8104 {field} must be an integer, got {response!r}")
    return int(value)


def parse_nonnegative_statistic_count(response: str, *, field: str) -> int:
    value = parse_finite_float(response, field=field)
    if value < 0 or not value.is_integer():
        raise DataError(
            f"MSO8104 {field} must be a non-negative integer, got {response!r}"
        )
    return int(value)


def _parse_bounded_integer(
    response: str,
    *,
    field: str,
    minimum: int,
    maximum: int,
) -> int:
    normalized = response.strip()
    if _STRICT_INTEGER.fullmatch(normalized) is None:
        raise DataError(f"invalid MSO8104 {field} response: {response!r}")
    value = int(normalized)
    if not minimum <= value <= maximum:
        raise DataError(
            f"MSO8104 {field} must be between {minimum} and {maximum}, got {value}"
        )
    return value


def parse_positive_integer(response: str, *, field: str, maximum: int) -> int:
    return _parse_bounded_integer(
        response,
        field=field,
        minimum=1,
        maximum=maximum,
    )


def parse_average_acquisition_count(response: str) -> int:
    value = _parse_bounded_integer(
        response,
        field="acquisition average count",
        minimum=2,
        maximum=65_536,
    )
    if value & (value - 1):
        raise DataError(
            "MSO8104 acquisition average count must be a power of two, "
            f"got {response!r}"
        )
    return value


def parse_rigol_waveform_preamble(
    response: str,
    *,
    expected_type_code: int = 0,
    maximum_points: int = 1000,
) -> RigolWaveformPreamble:
    parts = tuple(item.strip() for item in response.split(","))
    if len(parts) != 10:
        raise DataError(f"invalid MSO8104 waveform preamble: {response!r}")
    format_code = _parse_bounded_integer(
        parts[0],
        field="preamble format code",
        minimum=0,
        maximum=2,
    )
    type_code = _parse_bounded_integer(
        parts[1],
        field="preamble type code",
        minimum=0,
        maximum=2,
    )
    points = parse_positive_integer(
        parts[2],
        field="preamble points",
        maximum=maximum_points,
    )
    count = parse_positive_integer(parts[3], field="preamble count", maximum=1_000_000_000)
    try:
        numeric = tuple(float(item) for item in parts[4:])
    except ValueError as exc:
        raise DataError(f"invalid MSO8104 waveform preamble: {response!r}") from exc
    if not all(math.isfinite(value) for value in numeric):
        raise DataError(f"non-finite MSO8104 waveform preamble: {response!r}")
    x_increment, x_origin, x_reference, y_increment, y_origin, y_reference = numeric
    if format_code != 0:
        raise DataError(f"expected BYTE waveform format code 0, got {format_code}")
    if type_code != expected_type_code:
        raise DataError(
            f"expected waveform type code {expected_type_code}, got {type_code}"
        )
    if x_increment <= 0:
        raise DataError(f"MSO8104 waveform X increment must be positive, got {x_increment}")
    if y_increment <= 0:
        raise DataError(f"MSO8104 waveform Y increment must be positive, got {y_increment}")
    return RigolWaveformPreamble(
        format_code=format_code,
        type_code=type_code,
        points=points,
        count=count,
        x_increment=x_increment,
        x_origin=x_origin,
        x_reference=x_reference,
        y_increment=y_increment,
        y_origin=y_origin,
        y_reference=y_reference,
    )


def normalize_channel_input(*, coupling: str, impedance: str) -> str:
    normalized_coupling = _parse_enum(
        coupling,
        field="channel coupling",
        allowed=frozenset({"AC", "DC", "GND"}),
    )
    normalized_impedance = _parse_enum(
        impedance,
        field="channel impedance",
        allowed=frozenset({"OMEG", "FIFT"}),
    )
    if normalized_coupling == "GND":
        return "GND"
    if normalized_impedance == "OMEG":
        return f"{normalized_coupling}L"
    return normalized_coupling


def parse_channel_input_state_v2(
    *,
    channel: int,
    coupling: str,
    impedance: str,
) -> ScopeChannelInputStateV2:
    normalized_coupling = _parse_enum(
        coupling,
        field="channel coupling",
        allowed=frozenset({"AC", "DC", "GND"}),
    )
    normalized_impedance = _parse_enum(
        impedance,
        field="channel impedance",
        allowed=frozenset({"OMEG", "FIFT"}),
    )
    return ScopeChannelInputStateV2(
        channel=channel,
        coupling={"AC": "ac", "DC": "dc", "GND": "gnd"}[normalized_coupling],
        termination={"OMEG": "high_z", "FIFT": "50_ohm"}[normalized_impedance],
        impedance_ohm={"OMEG": 1_000_000.0, "FIFT": 50.0}[normalized_impedance],
    )
