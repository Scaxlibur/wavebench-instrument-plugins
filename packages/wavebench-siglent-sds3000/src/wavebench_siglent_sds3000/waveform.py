from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
import struct

import numpy as np

from wavebench.errors import DataError
from wavebench.instruments.models import WaveformData, WaveformHeader


_LEGACY_DESCRIPTOR_LENGTHS = frozenset({344, 346})


@dataclass(frozen=True)
class SDS3000WaveformDescriptor:
    template_name: str
    byte_order: str
    sample_width_bytes: int
    wave_descriptor_length: int
    wave_array_1_bytes: int
    wave_array_count: int
    first_valid: int
    last_valid: int
    first_point: int
    sparsing_factor: int
    segment_number: int
    subarray_count: int
    vertical_gain: float
    vertical_offset: float
    horizontal_interval: float
    horizontal_offset: float
    vertical_unit: str
    horizontal_unit: str


def _ascii_field(data: bytes, offset: int, length: int, *, name: str) -> str:
    raw = data[offset : offset + length].split(b"\0", 1)[0].rstrip(b" ")
    try:
        return raw.decode("ascii")
    except UnicodeDecodeError as exc:
        raise DataError(f"SDS3000 WAVEDESC {name} is not ASCII") from exc


def _descriptor_byte_order(data: bytes) -> tuple[str, str]:
    raw = data[34:36]
    if raw == b"\x00\x00":
        return ">", "big"
    if raw == b"\x01\x00":
        return "<", "little"
    raise DataError("invalid SDS3000 WAVEDESC COMM_ORDER")


def parse_waveform_descriptor(data: bytes) -> SDS3000WaveformDescriptor:
    if not isinstance(data, bytes) or len(data) < 344:
        raise DataError("truncated SDS3000 WAVEDESC block")
    if _ascii_field(data, 0, 16, name="DESCRIPTOR_NAME") != "WAVEDESC":
        raise DataError("invalid SDS3000 WAVEDESC DESCRIPTOR_NAME")

    endian, byte_order = _descriptor_byte_order(data)

    def unpack(code: str, offset: int) -> int | float:
        return struct.unpack_from(endian + code, data, offset)[0]

    comm_type = int(unpack("h", 32))
    if comm_type not in {0, 1}:
        raise DataError("invalid SDS3000 WAVEDESC COMM_TYPE")
    wave_descriptor_length = int(unpack("i", 36))
    if wave_descriptor_length not in _LEGACY_DESCRIPTOR_LENGTHS:
        raise DataError("unsupported SDS3000 WAVEDESC block length")
    if len(data) < wave_descriptor_length:
        raise DataError("truncated SDS3000 WAVEDESC block")

    sample_width_bytes = 1 if comm_type == 0 else 2
    wave_array_1_bytes = int(unpack("i", 60))
    wave_array_count = int(unpack("i", 116))
    first_valid = int(unpack("i", 124))
    last_valid = int(unpack("i", 128))
    first_point = int(unpack("i", 132))
    sparsing_factor = int(unpack("i", 136))
    segment_number = int(unpack("i", 140))
    subarray_count = int(unpack("i", 144))
    vertical_gain = float(unpack("f", 156))
    vertical_offset = float(unpack("f", 160))
    horizontal_interval = float(unpack("f", 176))
    horizontal_offset = float(unpack("d", 180))

    if wave_array_count < 1:
        raise DataError("invalid SDS3000 WAVEDESC WAVE_ARRAY_COUNT")
    if wave_array_1_bytes != wave_array_count * sample_width_bytes:
        raise DataError("inconsistent SDS3000 WAVEDESC WAVE_ARRAY_1 length")
    if not 0 <= first_valid <= last_valid < wave_array_count:
        raise DataError("invalid SDS3000 WAVEDESC valid point range")
    if first_point < 0 or sparsing_factor < 0:
        raise DataError("invalid SDS3000 WAVEDESC transfer point selection")
    if segment_number < 0 or subarray_count < 0:
        raise DataError("invalid SDS3000 WAVEDESC segment metadata")
    if not isfinite(vertical_gain) or vertical_gain <= 0:
        raise DataError("invalid SDS3000 WAVEDESC VERTICAL_GAIN")
    if not isfinite(vertical_offset):
        raise DataError("invalid SDS3000 WAVEDESC VERTICAL_OFFSET")
    if not isfinite(horizontal_interval) or horizontal_interval <= 0:
        raise DataError("invalid SDS3000 WAVEDESC HORIZONTAL_INTERVAL")
    if not isfinite(horizontal_offset):
        raise DataError("invalid SDS3000 WAVEDESC HORIZONTAL_OFFSET")

    return SDS3000WaveformDescriptor(
        template_name=_ascii_field(data, 16, 16, name="TEMPLATE_NAME"),
        byte_order=byte_order,
        sample_width_bytes=sample_width_bytes,
        wave_descriptor_length=wave_descriptor_length,
        wave_array_1_bytes=wave_array_1_bytes,
        wave_array_count=wave_array_count,
        first_valid=first_valid,
        last_valid=last_valid,
        first_point=first_point,
        sparsing_factor=sparsing_factor,
        segment_number=segment_number,
        subarray_count=subarray_count,
        vertical_gain=vertical_gain,
        vertical_offset=vertical_offset,
        horizontal_interval=horizontal_interval,
        horizontal_offset=horizontal_offset,
        vertical_unit=_ascii_field(data, 196, 48, name="VERTUNIT"),
        horizontal_unit=_ascii_field(data, 244, 48, name="HORUNIT"),
    )


def decode_waveform_data(
    descriptor: SDS3000WaveformDescriptor,
    data: bytes,
    *,
    channel: int,
) -> WaveformData:
    if isinstance(channel, bool) or channel not in {1, 2, 3, 4}:
        raise DataError("SDS3054 channel must be one of CH1, CH2, CH3, or CH4")
    if descriptor.subarray_count > 1:
        raise DataError("segmented SDS3000 waveforms require one selected segment")
    if descriptor.vertical_unit.strip().upper() != "V":
        raise DataError("SDS3000 waveform vertical unit is not volts")
    if descriptor.horizontal_unit.strip().upper() != "S":
        raise DataError("SDS3000 waveform horizontal unit is not seconds")
    if not isinstance(data, bytes) or len(data) != descriptor.wave_array_1_bytes:
        raise DataError(
            "SDS3000 waveform data length mismatch: "
            f"expected {descriptor.wave_array_1_bytes}, got "
            f"{len(data) if isinstance(data, bytes) else 'non-bytes'}"
        )

    if descriptor.sample_width_bytes == 1:
        dtype = np.dtype("i1")
    else:
        dtype = np.dtype("<i2" if descriptor.byte_order == "little" else ">i2")
    raw = np.frombuffer(data, dtype=dtype)
    if raw.size != descriptor.wave_array_count:
        raise DataError(
            "SDS3000 waveform point count mismatch: "
            f"expected {descriptor.wave_array_count}, got {raw.size}"
        )

    valid = raw[descriptor.first_valid : descriptor.last_valid + 1]
    voltages = valid.astype(np.float64)
    voltages *= descriptor.vertical_gain
    voltages -= descriptor.vertical_offset

    point_stride = max(descriptor.sparsing_factor, 1)
    first_index = descriptor.first_point + descriptor.first_valid * point_stride
    x_increment = descriptor.horizontal_interval * point_stride
    x_start = descriptor.horizontal_offset + first_index * descriptor.horizontal_interval
    x_stop = x_start + (voltages.size - 1) * x_increment
    return WaveformData(
        channel=channel,
        header=WaveformHeader(
            x_start=x_start,
            x_stop=x_stop,
            points=int(voltages.size),
            segment=descriptor.segment_number or None,
        ),
        voltages_v=voltages,
    )


__all__ = [
    "SDS3000WaveformDescriptor",
    "decode_waveform_data",
    "parse_waveform_descriptor",
]
