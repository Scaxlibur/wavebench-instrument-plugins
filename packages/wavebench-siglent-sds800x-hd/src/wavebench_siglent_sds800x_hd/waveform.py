from __future__ import annotations

from dataclasses import dataclass
import struct
from typing import Literal

import numpy as np

from wavebench.errors import DataError
from wavebench.instruments.models import WaveformData, WaveformHeader


_DESCRIPTOR_LENGTH = 346
_HORIZONTAL_DIVISIONS = 10.0
_TIMEBASE_SECONDS_PER_DIVISION = (
    200e-12,
    500e-12,
    1e-9,
    2e-9,
    5e-9,
    10e-9,
    20e-9,
    50e-9,
    100e-9,
    200e-9,
    500e-9,
    1e-6,
    2e-6,
    5e-6,
    10e-6,
    20e-6,
    50e-6,
    100e-6,
    200e-6,
    500e-6,
    1e-3,
    2e-3,
    5e-3,
    10e-3,
    20e-3,
    50e-3,
    100e-3,
    200e-3,
    500e-3,
    1.0,
    2.0,
    5.0,
    10.0,
    20.0,
    50.0,
    100.0,
    200.0,
    500.0,
    1000.0,
)
_COUPLINGS = {0: "DC", 1: "AC", 2: "GND"}


@dataclass(frozen=True)
class SDSWaveformPreamble:
    descriptor_byte_order: Literal["little", "big"]
    comm_type: int
    comm_order: int
    descriptor_length: int
    data_bytes: int
    points: int
    start: int
    interval: int
    read_frames: int
    sum_frames: int
    vertical_scale_raw: float
    vertical_offset_raw: float
    code_per_div: float
    adc_bits: int
    segment: int
    sample_interval_s: float
    horizontal_delay_s: float
    timebase_s_per_div: float
    coupling: str
    probe_factor: float
    source_channel: int

    @property
    def sample_width_bytes(self) -> int:
        return 1 if self.comm_type == 0 else 2

    @property
    def sample_byte_order(self) -> Literal["little", "big"]:
        return "little" if self.comm_order == 0 else "big"


def _binary_view(payload: bytes | bytearray | memoryview, *, field: str) -> memoryview:
    if not isinstance(payload, (bytes, bytearray, memoryview)):
        raise DataError(f"{field} must be bytes-like")
    return memoryview(payload).cast("B")


def _descriptor_prefix(payload: memoryview) -> tuple[str, Literal["little", "big"]]:
    candidates: list[tuple[str, Literal["little", "big"]]] = []
    for prefix, name in (("<", "little"), (">", "big")):
        comm_type = struct.unpack_from(f"{prefix}h", payload, 32)[0]
        comm_order = struct.unpack_from(f"{prefix}h", payload, 34)[0]
        descriptor_length = struct.unpack_from(f"{prefix}i", payload, 36)[0]
        if (
            comm_type in {0, 1}
            and comm_order in {0, 1}
            and descriptor_length == _DESCRIPTOR_LENGTH
        ):
            candidates.append((prefix, name))
    if len(candidates) != 1:
        raise DataError("SDS waveform preamble has no unambiguous 346-byte descriptor order")
    return candidates[0]


def parse_waveform_preamble(
    payload: bytes | bytearray | memoryview,
) -> SDSWaveformPreamble:
    """Parse the payload returned after the core removes its IEEE binary-block envelope."""

    data = _binary_view(payload, field="SDS waveform preamble")
    if len(data) != _DESCRIPTOR_LENGTH:
        raise DataError(
            "SDS waveform first version requires exactly one 346-byte descriptor "
            "without sequence timestamps"
        )
    if bytes(data[0:8]) != b"WAVEDESC":
        raise DataError("SDS waveform preamble is missing the WAVEDESC signature")
    if bytes(data[16:23]) != b"WAVEACE":
        raise DataError("SDS waveform preamble is missing the WAVEACE template signature")
    if bytes(data[76:87]) != b"Siglent SDS":
        raise DataError("SDS waveform preamble has an unsupported instrument signature")

    prefix, descriptor_byte_order = _descriptor_prefix(data)

    def int16(offset: int) -> int:
        return int(struct.unpack_from(f"{prefix}h", data, offset)[0])

    def int32(offset: int) -> int:
        return int(struct.unpack_from(f"{prefix}i", data, offset)[0])

    def float32(offset: int) -> float:
        return float(struct.unpack_from(f"{prefix}f", data, offset)[0])

    def float64(offset: int) -> float:
        return float(struct.unpack_from(f"{prefix}d", data, offset)[0])

    comm_type = int16(32)
    comm_order = int16(34)
    descriptor_length = int32(36)
    data_bytes = int32(60)
    points = int32(116)
    start = int32(132)
    interval = int32(136)
    read_frames = int32(144)
    sum_frames = int32(148)
    vertical_scale_raw = float32(156)
    vertical_offset_raw = float32(160)
    code_per_div = float32(164)
    adc_bits = int16(172)
    segment = int16(174)
    sample_interval_s = float32(176)
    horizontal_delay_s = float64(180)
    timebase_index = int16(324)
    coupling_code = int16(326)
    probe_factor = float32(328)
    source_code = int16(344)

    if data_bytes <= 0:
        raise DataError("SDS waveform preamble data length must be > 0")
    if points <= 0:
        raise DataError("SDS waveform preamble point count must be > 0")
    if start < 0:
        raise DataError("SDS waveform preamble start must be >= 0")
    if interval <= 0:
        raise DataError("SDS waveform preamble interval must be > 0")
    if read_frames < 0 or sum_frames < 0:
        raise DataError("SDS waveform preamble frame counts must be >= 0")
    if not np.isfinite(vertical_scale_raw) or vertical_scale_raw <= 0:
        raise DataError("SDS waveform preamble vertical scale must be finite and > 0")
    if not np.isfinite(vertical_offset_raw):
        raise DataError("SDS waveform preamble vertical offset must be finite")
    if not np.isfinite(code_per_div) or code_per_div <= 0:
        raise DataError("SDS waveform preamble code-per-division must be finite and > 0")
    if not 1 <= adc_bits <= 16:
        raise DataError("SDS waveform preamble ADC width must be between 1 and 16 bits")
    if adc_bits > 8 and comm_type != 1:
        raise DataError("SDS waveform ADC widths above 8 bits require WORD transfer")
    if segment < -1:
        raise DataError("SDS waveform preamble segment must be >= -1")
    if not np.isfinite(sample_interval_s) or sample_interval_s <= 0:
        raise DataError("SDS waveform preamble sample interval must be finite and > 0")
    if not np.isfinite(horizontal_delay_s):
        raise DataError("SDS waveform preamble horizontal delay must be finite")
    if not 0 <= timebase_index < len(_TIMEBASE_SECONDS_PER_DIVISION):
        raise DataError("SDS waveform preamble has an unsupported timebase index")
    if coupling_code not in _COUPLINGS:
        raise DataError("SDS waveform preamble has an unsupported coupling code")
    if not np.isfinite(probe_factor) or probe_factor <= 0:
        raise DataError("SDS waveform preamble probe factor must be finite and > 0")
    if not 0 <= source_code <= 7:
        raise DataError("SDS waveform preamble has an unsupported analog source")

    return SDSWaveformPreamble(
        descriptor_byte_order=descriptor_byte_order,
        comm_type=comm_type,
        comm_order=comm_order,
        descriptor_length=descriptor_length,
        data_bytes=data_bytes,
        points=points,
        start=start,
        interval=interval,
        read_frames=read_frames,
        sum_frames=sum_frames,
        vertical_scale_raw=vertical_scale_raw,
        vertical_offset_raw=vertical_offset_raw,
        code_per_div=code_per_div,
        adc_bits=adc_bits,
        segment=segment,
        sample_interval_s=sample_interval_s,
        horizontal_delay_s=horizontal_delay_s,
        timebase_s_per_div=_TIMEBASE_SECONDS_PER_DIVISION[timebase_index],
        coupling=_COUPLINGS[coupling_code],
        probe_factor=probe_factor,
        source_channel=source_code + 1,
    )


def decode_analog_samples(
    preamble: SDSWaveformPreamble,
    payload: bytes | bytearray | memoryview,
) -> np.ndarray:
    data = _binary_view(payload, field="SDS analog waveform payload")
    expected_bytes = preamble.points * preamble.sample_width_bytes
    if preamble.data_bytes != expected_bytes:
        raise DataError(
            "SDS waveform preamble data length does not match point count and width"
        )
    if len(data) != expected_bytes:
        raise DataError(
            f"SDS waveform payload length mismatch: expected {expected_bytes}, got {len(data)}"
        )

    if preamble.sample_width_bytes == 1:
        dtype = np.dtype("i1")
    else:
        dtype = np.dtype("<i2" if preamble.sample_byte_order == "little" else ">i2")
    raw = np.frombuffer(data, dtype=dtype, count=preamble.points).astype(np.float64)
    vertical_scale = preamble.vertical_scale_raw * preamble.probe_factor
    vertical_offset = preamble.vertical_offset_raw * preamble.probe_factor
    voltages = raw * (vertical_scale / preamble.code_per_div) - vertical_offset
    if voltages.ndim != 1 or voltages.size != preamble.points:
        raise DataError("SDS waveform conversion produced an invalid sample shape")
    if not np.all(np.isfinite(voltages)):
        raise DataError("SDS waveform conversion produced non-finite voltages")
    return voltages


def waveform_header_from_preamble(preamble: SDSWaveformPreamble) -> WaveformHeader:
    if preamble.start != 0:
        raise DataError("SDS waveform first version requires START 0")
    if preamble.interval != 1:
        raise DataError("SDS waveform first version requires INTERVAL 1")
    if (
        preamble.read_frames != 0
        or preamble.sum_frames != 1
        or preamble.segment not in {-1, 1}
    ):
        raise DataError(
            "SDS waveform first version requires the non-sequence frame signature "
            "read_frames=0, sum_frames=1, segment=-1 or 1"
        )

    x_start = (
        preamble.horizontal_delay_s
        - preamble.timebase_s_per_div * _HORIZONTAL_DIVISIONS / 2.0
    )
    x_stop = x_start + (preamble.points - 1) * preamble.sample_interval_s
    if not np.isfinite(x_start) or not np.isfinite(x_stop) or x_stop < x_start:
        raise DataError("SDS waveform preamble produced an invalid time axis")
    return WaveformHeader(x_start=x_start, x_stop=x_stop, points=preamble.points)


def build_analog_waveform(
    *,
    channel: int,
    preamble: SDSWaveformPreamble,
    payload: bytes | bytearray | memoryview,
) -> WaveformData:
    if type(channel) is not int or channel < 1:
        raise DataError("SDS waveform channel must be a positive integer")
    if preamble.source_channel != channel:
        raise DataError("SDS waveform preamble source does not match the requested channel")
    header = waveform_header_from_preamble(preamble)
    voltages = decode_analog_samples(preamble, payload)
    return WaveformData(channel=channel, header=header, voltages_v=voltages)
