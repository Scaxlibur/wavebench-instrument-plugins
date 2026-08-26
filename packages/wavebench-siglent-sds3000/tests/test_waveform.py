from __future__ import annotations

import struct

import numpy as np
import pytest

from wavebench.errors import DataError
from wavebench_siglent_sds3000.waveform import (
    decode_waveform_data,
    parse_waveform_descriptor,
)


def descriptor_block(
    *,
    byte_order: str = "little",
    sample_width_bytes: int = 2,
    length: int = 346,
    points: int = 4,
    first_valid: int = 0,
    last_valid: int | None = None,
    first_point: int = 0,
    sparsing_factor: int = 0,
    segment_number: int = 0,
    subarray_count: int = 1,
    vertical_gain: float = 0.5,
    vertical_offset: float = 1.0,
    horizontal_interval: float = 0.25,
    horizontal_offset: float = -1.0,
    vertical_unit: bytes = b"V",
    horizontal_unit: bytes = b"S",
) -> bytes:
    endian = "<" if byte_order == "little" else ">"
    comm_order = 1 if byte_order == "little" else 0
    comm_type = 1 if sample_width_bytes == 2 else 0
    last_valid = points - 1 if last_valid is None else last_valid
    block = bytearray(length)
    block[0:8] = b"WAVEDESC"
    block[16:26] = b"LECROY_2_4"
    struct.pack_into(endian + "h", block, 32, comm_type)
    struct.pack_into(endian + "h", block, 34, comm_order)
    struct.pack_into(endian + "i", block, 36, length)
    struct.pack_into(endian + "i", block, 60, points * sample_width_bytes)
    struct.pack_into(endian + "i", block, 116, points)
    struct.pack_into(endian + "i", block, 124, first_valid)
    struct.pack_into(endian + "i", block, 128, last_valid)
    struct.pack_into(endian + "i", block, 132, first_point)
    struct.pack_into(endian + "i", block, 136, sparsing_factor)
    struct.pack_into(endian + "i", block, 140, segment_number)
    struct.pack_into(endian + "i", block, 144, subarray_count)
    struct.pack_into(endian + "f", block, 156, vertical_gain)
    struct.pack_into(endian + "f", block, 160, vertical_offset)
    struct.pack_into(endian + "f", block, 176, horizontal_interval)
    struct.pack_into(endian + "d", block, 180, horizontal_offset)
    block[196 : 196 + len(vertical_unit)] = vertical_unit
    block[244 : 244 + len(horizontal_unit)] = horizontal_unit
    return bytes(block)


@pytest.mark.parametrize("length", [344, 346])
def test_parser_accepts_both_lengths_described_by_the_manual(length: int) -> None:
    descriptor = parse_waveform_descriptor(descriptor_block(length=length))

    assert descriptor.template_name == "LECROY_2_4"
    assert descriptor.wave_descriptor_length == length
    assert descriptor.byte_order == "little"
    assert descriptor.sample_width_bytes == 2


def test_little_endian_word_data_is_scaled_to_volts_and_time() -> None:
    descriptor = parse_waveform_descriptor(descriptor_block())
    waveform = decode_waveform_data(
        descriptor,
        struct.pack("<4h", -2, 0, 2, 4),
        channel=2,
    )

    np.testing.assert_allclose(waveform.voltages_v, [-2.0, -1.0, 0.0, 1.0])
    np.testing.assert_allclose(waveform.times_s, [-1.0, -0.75, -0.5, -0.25])
    assert waveform.channel == 2
    assert waveform.header.segment is None


def test_big_endian_signed_byte_data_and_valid_range_are_respected() -> None:
    descriptor = parse_waveform_descriptor(
        descriptor_block(
            byte_order="big",
            sample_width_bytes=1,
            first_valid=1,
            last_valid=2,
            first_point=10,
            sparsing_factor=4,
            segment_number=3,
            vertical_gain=0.25,
            vertical_offset=0.0,
            horizontal_interval=0.5,
            horizontal_offset=-10.0,
        )
    )
    waveform = decode_waveform_data(
        descriptor,
        struct.pack("4b", -128, -4, 4, 127),
        channel=1,
    )

    np.testing.assert_allclose(waveform.voltages_v, [-1.0, 1.0])
    np.testing.assert_allclose(waveform.times_s, [-3.0, -1.0])
    assert waveform.header.segment == 3


@pytest.mark.parametrize(
    ("mutation", "message"),
    [
        (lambda block: block.__setitem__(slice(0, 8), b"NOTADESC"), "DESCRIPTOR_NAME"),
        (lambda block: block.__setitem__(slice(34, 36), b"\x02\x00"), "COMM_ORDER"),
        (lambda block: struct.pack_into("<i", block, 36, 343), "block length"),
        (lambda block: struct.pack_into("<i", block, 60, 3), "WAVE_ARRAY_1"),
        (lambda block: struct.pack_into("<f", block, 156, 0.0), "VERTICAL_GAIN"),
    ],
)
def test_parser_rejects_malformed_descriptor_fields(mutation, message: str) -> None:
    block = bytearray(descriptor_block())
    mutation(block)

    with pytest.raises(DataError, match=message):
        parse_waveform_descriptor(bytes(block))


def test_parser_rejects_truncation_and_invalid_valid_point_range() -> None:
    with pytest.raises(DataError, match="truncated"):
        parse_waveform_descriptor(descriptor_block()[:200])

    with pytest.raises(DataError, match="valid point range"):
        parse_waveform_descriptor(descriptor_block(first_valid=3, last_valid=2))


def test_decoder_rejects_unsupported_units_segments_and_data_lengths() -> None:
    units = parse_waveform_descriptor(descriptor_block(vertical_unit=b"A"))
    with pytest.raises(DataError, match="not volts"):
        decode_waveform_data(units, bytes(8), channel=1)

    segments = parse_waveform_descriptor(descriptor_block(subarray_count=2))
    with pytest.raises(DataError, match="one selected segment"):
        decode_waveform_data(segments, bytes(8), channel=1)

    descriptor = parse_waveform_descriptor(descriptor_block())
    with pytest.raises(DataError, match="length mismatch"):
        decode_waveform_data(descriptor, bytes(7), channel=1)
    with pytest.raises(DataError, match="CH1, CH2, CH3, or CH4"):
        decode_waveform_data(descriptor, bytes(8), channel=0)
