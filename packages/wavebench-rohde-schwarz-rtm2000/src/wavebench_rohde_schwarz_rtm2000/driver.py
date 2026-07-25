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


def parse_waveform_header(response: str) -> WaveformHeader:
    parts = [item.strip() for item in response.split(",")]
    if len(parts) < 3:
        raise DataError(f"invalid CHAN:DATA:HEAD? response: {response!r}")
    try:
        x_start = float(parts[0])
        x_stop = float(parts[1])
        points = int(float(parts[2]))
        segment = int(float(parts[3])) if len(parts) >= 4 else None
    except ValueError as exc:
        raise DataError(f"invalid CHAN:DATA:HEAD? response: {response!r}") from exc
    if points <= 0:
        raise DataError(f"invalid waveform point count: {points}")
    return WaveformHeader(
        x_start=x_start,
        x_stop=x_stop,
        points=points,
        segment=segment,
    )


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
