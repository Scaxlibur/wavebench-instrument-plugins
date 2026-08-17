from __future__ import annotations

from dataclasses import replace
import struct

import numpy as np
import pytest

from wavebench.errors import DataError
from wavebench.instruments.models import WaveformData, WaveformHeader

from wavebench_siglent_sds800x_hd.waveform import (
    build_analog_waveform,
    decode_analog_samples,
    parse_waveform_preamble,
    waveform_header_from_preamble,
)


def _descriptor(
    *,
    prefix: str = "<",
    comm_type: int = 0,
    comm_order: int = 0,
    points: int = 3,
    adc_bits: int = 8,
    source_channel: int = 2,
    appended: bytes = b"",
) -> bytes:
    payload = bytearray(346)
    payload[0:8] = b"WAVEDESC"
    payload[16:23] = b"WAVEACE"
    payload[76:87] = b"Siglent SDS"

    def int16(offset: int, value: int) -> None:
        struct.pack_into(f"{prefix}h", payload, offset, value)

    def int32(offset: int, value: int) -> None:
        struct.pack_into(f"{prefix}i", payload, offset, value)

    def float32(offset: int, value: float) -> None:
        struct.pack_into(f"{prefix}f", payload, offset, value)

    def float64(offset: int, value: float) -> None:
        struct.pack_into(f"{prefix}d", payload, offset, value)

    width = 1 if comm_type == 0 else 2
    int16(32, comm_type)
    int16(34, comm_order)
    int32(36, 346)
    int32(60, points * width)
    int32(116, points)
    int32(132, 0)
    int32(136, 1)
    int32(144, 1)
    int32(148, 1)
    float32(156, 0.2)
    float32(160, 0.1)
    float32(164, 25.0)
    int16(172, adc_bits)
    int16(174, 1)
    float32(176, 1e-9)
    float64(180, 2e-9)
    int16(324, 9)
    int16(326, 0)
    float32(328, 10.0)
    int16(344, source_channel - 1)
    return bytes(payload) + appended


def test_parse_little_endian_byte_descriptor_and_timebase_typo_correction() -> None:
    preamble = parse_waveform_preamble(_descriptor())

    assert preamble.descriptor_byte_order == "little"
    assert preamble.comm_type == 0
    assert preamble.comm_order == 0
    assert preamble.descriptor_length == 346
    assert preamble.data_bytes == 3
    assert preamble.points == 3
    assert preamble.start == 0
    assert preamble.interval == 1
    assert preamble.adc_bits == 8
    assert preamble.sample_width_bytes == 1
    assert preamble.sample_byte_order == "little"
    assert preamble.timebase_s_per_div == pytest.approx(200e-9)
    assert preamble.coupling == "DC"
    assert preamble.source_channel == 2


def test_parse_big_endian_word_descriptor() -> None:
    preamble = parse_waveform_preamble(
        _descriptor(prefix=">", comm_type=1, comm_order=1, adc_bits=12)
    )

    assert preamble.descriptor_byte_order == "big"
    assert preamble.comm_type == 1
    assert preamble.comm_order == 1
    assert preamble.sample_width_bytes == 2
    assert preamble.sample_byte_order == "big"


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda data: data[:345], "exactly one 346-byte"),
        (lambda data: data + b"\x00" * 16, "without sequence timestamps"),
        (lambda data: b"NOTADESC" + data[8:], "WAVEDESC"),
        (lambda data: data[:16] + b"NOTWAVE" + data[23:], "WAVEACE"),
        (lambda data: data[:76] + b"Other Scope" + data[87:], "instrument signature"),
    ],
)
def test_parse_rejects_invalid_descriptor_envelope(mutator, message: str) -> None:
    with pytest.raises(DataError, match=message):
        parse_waveform_preamble(mutator(_descriptor()))


def test_parse_rejects_unknown_descriptor_byte_order() -> None:
    payload = bytearray(_descriptor())
    struct.pack_into("<i", payload, 36, 345)

    with pytest.raises(DataError, match="unambiguous 346-byte descriptor order"):
        parse_waveform_preamble(payload)


@pytest.mark.parametrize(
    ("offset", "fmt", "value", "message"),
    [
        (60, "i", 0, "data length"),
        (116, "i", 0, "point count"),
        (132, "i", -1, "start"),
        (136, "i", 0, "interval"),
        (156, "f", float("nan"), "vertical scale"),
        (164, "f", 0.0, "code-per-division"),
        (172, "h", 17, "ADC width"),
        (176, "f", 0.0, "sample interval"),
        (324, "h", 39, "timebase index"),
        (326, "h", 3, "coupling code"),
        (328, "f", 0.0, "probe factor"),
        (344, "h", 8, "analog source"),
    ],
)
def test_parse_rejects_invalid_descriptor_fields(
    offset: int,
    fmt: str,
    value: int | float,
    message: str,
) -> None:
    payload = bytearray(_descriptor())
    struct.pack_into(f"<{fmt}", payload, offset, value)

    with pytest.raises(DataError, match=message):
        parse_waveform_preamble(payload)


def test_parse_rejects_high_resolution_byte_transfer() -> None:
    with pytest.raises(DataError, match="above 8 bits require WORD"):
        parse_waveform_preamble(_descriptor(adc_bits=12))


def test_decode_signed_byte_samples_without_stripping_binary_tail() -> None:
    preamble = parse_waveform_preamble(_descriptor(points=3))

    voltages = decode_analog_samples(preamble, bytes([0xE7, 0x00, 0x0A]))

    np.testing.assert_allclose(voltages, [-3.0, -1.0, -0.2], rtol=0, atol=1e-7)


@pytest.mark.parametrize(
    ("comm_order", "dtype"),
    [(0, "<i2"), (1, ">i2")],
)
def test_decode_signed_word_samples_uses_declared_sample_order(
    comm_order: int,
    dtype: str,
) -> None:
    preamble = parse_waveform_preamble(
        _descriptor(comm_type=1, comm_order=comm_order, adc_bits=12)
    )
    raw = np.asarray([-32768, 0, 16384], dtype=np.dtype(dtype)).tobytes()

    voltages = decode_analog_samples(preamble, raw)

    np.testing.assert_allclose(voltages, [-2622.44, -1.0, 1309.72], rtol=0, atol=2e-4)


def test_decode_rejects_preamble_and_payload_length_mismatches() -> None:
    preamble = parse_waveform_preamble(_descriptor())

    with pytest.raises(DataError, match="payload length mismatch"):
        decode_analog_samples(preamble, b"\x00\x01")
    with pytest.raises(DataError, match="preamble data length"):
        decode_analog_samples(replace(preamble, data_bytes=4), b"\x00\x01\x02")


def test_waveform_header_uses_documented_ten_division_time_axis() -> None:
    preamble = parse_waveform_preamble(_descriptor())

    header = waveform_header_from_preamble(preamble)

    assert isinstance(header, WaveformHeader)
    assert header.points == 3
    assert header.x_start == pytest.approx(-998e-9)
    assert header.x_stop == pytest.approx(-996e-9)
    assert header.x_increment == pytest.approx(1e-9)


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"start": 1}, "START 0"),
        ({"interval": 2}, "INTERVAL 1"),
        ({"read_frames": 0, "sum_frames": 1}, "sequence"),
        ({"read_frames": 1, "sum_frames": 0}, "sequence"),
        ({"read_frames": 1, "sum_frames": 2}, "sequence"),
    ],
)
def test_waveform_header_rejects_unsupported_transfer_modes(changes, message: str) -> None:
    preamble = replace(parse_waveform_preamble(_descriptor()), **changes)

    with pytest.raises(DataError, match=message):
        waveform_header_from_preamble(preamble)


def test_build_analog_waveform_returns_core_models() -> None:
    preamble = parse_waveform_preamble(_descriptor())

    waveform = build_analog_waveform(
        channel=2,
        preamble=preamble,
        payload=bytes([0xE7, 0x00, 0x19]),
    )

    assert isinstance(waveform, WaveformData)
    assert isinstance(waveform.header, WaveformHeader)
    assert waveform.channel == 2
    assert waveform.sample_count == 3
    np.testing.assert_allclose(waveform.voltages_v, [-3.0, -1.0, 1.0], rtol=0, atol=1e-7)


def test_build_analog_waveform_rejects_source_mismatch() -> None:
    preamble = parse_waveform_preamble(_descriptor(source_channel=2))

    with pytest.raises(DataError, match="source does not match"):
        build_analog_waveform(channel=1, preamble=preamble, payload=b"\x00\x00\x00")
