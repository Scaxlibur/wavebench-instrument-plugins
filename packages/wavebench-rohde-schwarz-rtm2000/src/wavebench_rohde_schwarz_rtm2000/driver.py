from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
import math
import re
import time

import numpy as np

from wavebench.errors import DataError, InstrumentError, OperationTimeout
from wavebench.instruments.models import WaveformData, WaveformHeader
from wavebench.transport.base import InstrumentTransport


_DECIMAL_INTEGER = re.compile(r"[+-]?[0-9]+")
_UNAVAILABLE_FLOAT_MINIMUM = 9.0e37


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


@dataclass(frozen=True)
class RTM2000IdentitySnapshot:
    manufacturer: str
    model: str
    serial_number: str
    firmware: str
    options: tuple[str, ...]


@dataclass(frozen=True)
class RTM2000HealthSnapshot:
    status_byte: int
    operation_condition: int
    questionable_condition: int
    acquisition_available: int
    acquisition_count: int
    sample_rate_hz: float
    error_queue_nonempty: bool
    waiting_for_trigger: bool


@dataclass(frozen=True)
class RTM2000AnalogChannelSnapshot:
    channel: int
    enabled: bool
    coupling: str
    range_v: float
    scale_v_per_div: float
    offset_v: float
    position_div: float
    bandwidth_hz: float | None
    polarity: str
    skew_s: float
    label: str
    label_enabled: bool
    overloaded: bool
    acquisition_type: str


@dataclass(frozen=True)
class RTM2000TimebaseSnapshot:
    acquisition_time_s: float
    divisions: int
    position_s: float
    range_s: float
    reference_percent: float
    scale_s_per_div: float
    roll_enabled: bool


@dataclass(frozen=True)
class RTM2000ProbeSnapshot:
    channel: int
    attenuation_factor: float
    bandwidth_hz: float | None
    capacitance_f: float | None
    impedance_ohm: float | None
    name: str
    probe_type: str


@dataclass(frozen=True)
class RTM2000WaveformMetadataSnapshot:
    channel: int
    x_start_s: float
    x_stop_s: float
    points: int
    values_per_sample: int | None
    x_increment_s: float
    x_origin_s: float
    y_increment_v: float
    y_origin_v: float
    y_resolution_bits: int


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


@dataclass
class RTM2032Scope:
    transport: InstrumentTransport
    check_errors_after_ops: bool = True
    long_waveform_timeout_ms: int = 300_000

    def idn(self) -> str:
        return self.transport.query("*IDN?")

    def identity_snapshot(self) -> RTM2000IdentitySnapshot:
        manufacturer, model, serial_number, firmware = _parse_idn(self.idn())
        return RTM2000IdentitySnapshot(
            manufacturer=manufacturer,
            model=model,
            serial_number=serial_number,
            firmware=firmware,
            options=_parse_options(self.transport.query("*OPT?")),
        )

    def health_snapshot(self) -> RTM2000HealthSnapshot:
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

    def clear_status(self) -> None:
        self.transport.write("*CLS")

    def channel_coupling(self, channel: int) -> str:
        if channel < 1:
            raise DataError("channel must be >= 1")
        return self.transport.query(f"CHAN{channel}:COUP?").strip().upper()

    def errors(self, limit: int = 16) -> list[str]:
        errors: list[str] = []
        for _ in range(limit):
            response = self.transport.query("SYST:ERR?")
            errors.append(response)
            if response.startswith("0") or "No error" in response:
                break
        return errors

    def assert_no_errors(self) -> None:
        errors = self.errors()
        active = [
            item
            for item in errors
            if not (item.startswith("0") or "No error" in item)
        ]
        if active:
            raise InstrumentError("instrument error queue is not empty: " + "; ".join(active))

    def autoscale(self, wait_opc: bool = True, check_errors: bool = True) -> None:
        self.transport.write("AUToscale")
        if wait_opc:
            self.transport.query_opc()
        if check_errors:
            self.assert_no_errors()

    def set_time_range(self, time_range_s: float) -> None:
        if time_range_s <= 0:
            raise DataError("time range must be > 0")
        self.transport.write(f"TIMebase:RANGe {time_range_s:.12g}")

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

    def close(self) -> None:
        self.transport.close()
