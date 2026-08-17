from __future__ import annotations

from collections import deque
import inspect
import struct
from types import SimpleNamespace

import numpy as np
import pytest

from wavebench.errors import ConfigError, DataError
from wavebench.instruments.models import WaveformData
from wavebench.services.scope_service import ScopeService

from wavebench_siglent_sds800x_hd import descriptor
from wavebench_siglent_sds800x_hd.driver import SDS800XHDScope


DEFAULT_IDN = "SIGLENT TECHNOLOGIES,SDS824X HD,SDS8FAKE000001,1.1.3.1"
_ORIGINAL_TRANSFER_STATE = {
    ":WAVeform:SOURce?": "F1",
    ":WAVeform:START?": "5",
    ":WAVeform:INTerval?": "3",
    ":WAVeform:POINt?": "17",
    ":WAVeform:WIDTH?": "BYTE",
    ":WAVeform:BYTeorder?": "MSB",
}
_RESTORE_WRITES = [
    ":WAVeform:START 0",
    ":WAVeform:POINt 0",
    ":WAVeform:SOURce F1",
    ":WAVeform:WIDTH BYTE",
    ":WAVeform:BYTeorder MSB",
    ":WAVeform:POINt 17",
    ":WAVeform:INTerval 3",
    ":WAVeform:START 5",
]


def _preamble(*, points: int = 5, channel: int = 2) -> bytes:
    payload = bytearray(346)
    payload[0:8] = b"WAVEDESC"
    payload[16:23] = b"WAVEACE"
    payload[76:87] = b"Siglent SDS"

    def int16(offset: int, value: int) -> None:
        struct.pack_into("<h", payload, offset, value)

    def int32(offset: int, value: int) -> None:
        struct.pack_into("<i", payload, offset, value)

    def float32(offset: int, value: float) -> None:
        struct.pack_into("<f", payload, offset, value)

    int16(32, 1)
    int16(34, 0)
    int32(36, 346)
    int32(60, points * 2)
    int32(116, points)
    int32(132, 0)
    int32(136, 1)
    int32(144, 1)
    int32(148, 1)
    float32(156, 0.2)
    float32(160, 0.1)
    float32(164, 25.0)
    int16(172, 12)
    int16(174, 1)
    float32(176, 1e-9)
    struct.pack_into("<d", payload, 180, 2e-9)
    int16(324, 9)
    int16(326, 0)
    float32(328, 10.0)
    int16(344, channel - 1)
    return bytes(payload)


class FakeTransport:
    def __init__(
        self,
        *,
        responses: dict[str, str] | None = None,
        preamble: bytes | BaseException | None = None,
        chunks: list[bytes | BaseException] | None = None,
        write_failures: dict[str, BaseException] | None = None,
    ) -> None:
        self.responses = {
            "*IDN?": DEFAULT_IDN,
            ":TRIGger:STATus?": "Stop",
            ":ACQuire:SEQuence?": "OFF",
            ":WAVeform:MAXPoint?": "2",
            **_ORIGINAL_TRANSFER_STATE,
        }
        if responses is not None:
            self.responses.update(responses)
        raw = np.asarray([-25, 0, 25, -1, 0x0A00], dtype="<i2").tobytes()
        self.preamble = _preamble() if preamble is None else preamble
        self.chunks = deque(
            [raw[0:4], raw[4:8], raw[8:10]] if chunks is None else chunks
        )
        self.write_failures = dict(write_failures or {})
        self.operations: list[tuple[str, str]] = []
        self.writes: list[str] = []
        self.queries: list[str] = []
        self.binary_queries: list[str] = []

    def write(self, command: str) -> None:
        self.operations.append(("write", command))
        self.writes.append(command)
        failure = self.write_failures.get(command)
        if failure is not None:
            raise failure

    def query(self, command: str) -> str:
        self.operations.append(("query", command))
        self.queries.append(command)
        return self.responses[command]

    def query_bin_block(self, command: str) -> bytes:
        self.operations.append(("binary", command))
        self.binary_queries.append(command)
        result = self.preamble if command == ":WAVeform:PREamble?" else self.chunks.popleft()
        if isinstance(result, BaseException):
            raise result
        return result

    def close(self) -> None:
        pass


def test_fetch_waveform_signature_matches_core_contract() -> None:
    signature = inspect.signature(SDS800XHDScope.fetch_waveform)

    assert list(signature.parameters) == ["self", "channel", "points", "check_errors"]
    assert signature.parameters["points"].default == "dmax"
    assert signature.parameters["check_errors"].default is True
    assert signature.return_annotation == "WaveformData"


def _scope_service(
    transport: FakeTransport,
    *,
    check_errors: bool,
) -> ScopeService:
    item = descriptor()
    config = SimpleNamespace(
        scope=SimpleNamespace(
            driver=item.driver_id,
            check_errors=check_errors,
            access="read_write",
        ),
        waveform=SimpleNamespace(
            format="real",
            byte_order="lsbf",
            points="DMAX",
        ),
    )
    return ScopeService(
        config=config,
        logger=SimpleNamespace(),
        session=SDS800XHDScope(transport),
        descriptor=item,
    )


def test_core_scope_service_fetches_with_error_checking_explicitly_disabled() -> None:
    transport = FakeTransport()

    waveform = _scope_service(transport, check_errors=False).fetch_waveform(channel=2)

    assert isinstance(waveform, WaveformData)
    assert waveform.channel == 2
    assert transport.binary_queries.count(":WAVeform:DATA?") == 3


def test_core_scope_service_requires_missing_error_capability_before_io() -> None:
    transport = FakeTransport()

    with pytest.raises(ConfigError, match=r"missing capabilities: scope\.errors"):
        _scope_service(transport, check_errors=True).fetch_waveform(channel=2)

    assert transport.operations == []


def test_fetch_waveform_reads_stopped_record_in_chunks_and_restores_state() -> None:
    transport = FakeTransport()

    waveform = SDS800XHDScope(transport).fetch_waveform(
        channel=2,
        points="DMAX",
        check_errors=False,
    )

    assert isinstance(waveform, WaveformData)
    assert waveform.channel == 2
    assert waveform.sample_count == 5
    np.testing.assert_allclose(
        waveform.voltages_v,
        [-3.0, -1.0, 1.0, -1.08, 203.8],
        rtol=0,
        atol=2e-5,
    )
    assert waveform.header.x_start == pytest.approx(-998e-9)
    assert waveform.header.x_increment == pytest.approx(1e-9)
    assert transport.operations == [
        ("query", "*IDN?"),
        ("query", ":TRIGger:STATus?"),
        ("query", ":ACQuire:SEQuence?"),
        ("query", ":WAVeform:SOURce?"),
        ("query", ":WAVeform:START?"),
        ("query", ":WAVeform:INTerval?"),
        ("query", ":WAVeform:POINt?"),
        ("query", ":WAVeform:WIDTH?"),
        ("query", ":WAVeform:BYTeorder?"),
        ("write", ":WAVeform:SOURce C2"),
        ("write", ":WAVeform:WIDTH WORD"),
        ("write", ":WAVeform:BYTeorder LSB"),
        ("write", ":WAVeform:START 0"),
        ("write", ":WAVeform:INTerval 1"),
        ("write", ":WAVeform:POINt 0"),
        ("binary", ":WAVeform:PREamble?"),
        ("query", ":WAVeform:MAXPoint?"),
        ("write", ":WAVeform:POINt 2"),
        ("write", ":WAVeform:START 0"),
        ("binary", ":WAVeform:DATA?"),
        ("write", ":WAVeform:POINt 2"),
        ("write", ":WAVeform:START 2"),
        ("binary", ":WAVeform:DATA?"),
        ("write", ":WAVeform:POINt 1"),
        ("write", ":WAVeform:START 4"),
        ("binary", ":WAVeform:DATA?"),
        *(("write", command) for command in _RESTORE_WRITES),
    ]


def test_fetch_waveform_accepts_case_insensitive_dmax() -> None:
    transport = FakeTransport(
        responses={":WAVeform:MAXPoint?": "5"},
        chunks=[np.asarray([0, 1, 2, 3, 4], dtype="<i2").tobytes()],
    )

    waveform = SDS800XHDScope(transport).fetch_waveform(
        channel=2,
        points=" dmax ",
        check_errors=False,
    )

    assert waveform.sample_count == 5
    assert transport.binary_queries.count(":WAVeform:DATA?") == 1
    assert ":WAVeform:POINt 0" in transport.writes


@pytest.mark.parametrize("points", ["DEF", "MAX"])
def test_fetch_waveform_rejects_unproven_core_point_modes_without_io(
    points: str,
) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="currently support only DMAX"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            points=points,
            check_errors=False,
        )

    assert transport.operations == []


@pytest.mark.parametrize("channel", [True, 0, -1, 5])
def test_fetch_waveform_rejects_invalid_channel_without_io(channel: object) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="channel"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=channel,  # type: ignore[arg-type]
            check_errors=False,
        )

    assert transport.operations == []


@pytest.mark.parametrize("points", [None, 1, "", "RAW"])
def test_fetch_waveform_rejects_invalid_points_without_io(points: object) -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="points must be DEF, MAX, or DMAX"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=1,
            points=points,  # type: ignore[arg-type]
            check_errors=False,
        )

    assert transport.operations == []


def test_fetch_waveform_rejects_error_checking_without_io() -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="require check_errors=False"):
        SDS800XHDScope(transport).fetch_waveform(channel=1)

    assert transport.operations == []


def test_fetch_waveform_rejects_non_boolean_error_checking_without_io() -> None:
    transport = FakeTransport()

    with pytest.raises(DataError, match="check_errors must be a boolean"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=1,
            check_errors=0,  # type: ignore[arg-type]
        )

    assert transport.operations == []


@pytest.mark.parametrize(
    ("responses", "message", "expected_queries"),
    [
        (
            {":TRIGger:STATus?": "Ready"},
            "require acquisition state Stop",
            ["*IDN?", ":TRIGger:STATus?"],
        ),
        (
            {":TRIGger:STATus?": "UNKNOWN"},
            "unsupported trigger status",
            ["*IDN?", ":TRIGger:STATus?"],
        ),
        (
            {":ACQuire:SEQuence?": "ON"},
            "do not support sequence",
            ["*IDN?", ":TRIGger:STATus?", ":ACQuire:SEQuence?"],
        ),
    ],
)
def test_fetch_waveform_fails_closed_before_transfer_writes(
    responses: dict[str, str],
    message: str,
    expected_queries: list[str],
) -> None:
    transport = FakeTransport(responses=responses)

    with pytest.raises(DataError, match=message):
        SDS800XHDScope(transport).fetch_waveform(
            channel=1,
            check_errors=False,
        )

    assert transport.queries == expected_queries
    assert transport.writes == []
    assert transport.binary_queries == []


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ({":WAVeform:SOURce?": "C1;:RUN"}, "source must be Cn"),
        ({":WAVeform:START?": "1.0"}, "start response must be an integer"),
        ({":WAVeform:INTerval?": "0"}, "interval must be >= 1"),
        ({":WAVeform:POINt?": "RAW"}, "point count response must be an integer"),
        ({":WAVeform:WIDTH?": "REAL"}, "width must be BYTE or WORD"),
        ({":WAVeform:BYTeorder?": "NATIVE"}, "byte order must be LSB or MSB"),
    ],
)
def test_fetch_waveform_rejects_unsafe_saved_state_before_writing(
    response: dict[str, str],
    message: str,
) -> None:
    transport = FakeTransport(responses=response)

    with pytest.raises(DataError, match=message):
        SDS800XHDScope(transport).fetch_waveform(
            channel=1,
            check_errors=False,
        )

    assert transport.writes == []
    assert transport.binary_queries == []


@pytest.mark.parametrize("max_points", ["0", "-1", "2.5"])
def test_fetch_waveform_rejects_invalid_maximum_chunk_size_and_restores(
    max_points: str,
) -> None:
    transport = FakeTransport(responses={":WAVeform:MAXPoint?": max_points})

    with pytest.raises(DataError, match="maximum chunk points"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert transport.writes[-len(_RESTORE_WRITES) :] == _RESTORE_WRITES


def test_fetch_waveform_short_second_chunk_restores_state() -> None:
    raw = np.asarray([-1, 0, 1, 2, 3], dtype="<i2").tobytes()
    transport = FakeTransport(chunks=[raw[0:4], raw[4:6]])

    with pytest.raises(DataError, match="chunk length mismatch at start 2"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert transport.binary_queries.count(":WAVeform:DATA?") == 2
    assert transport.writes[-len(_RESTORE_WRITES) :] == _RESTORE_WRITES


def test_fetch_waveform_binary_failure_is_not_retried_and_restores_state() -> None:
    transport = FakeTransport(chunks=[TimeoutError("binary timeout")])

    with pytest.raises(TimeoutError, match="binary timeout"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert transport.binary_queries.count(":WAVeform:DATA?") == 1
    assert transport.writes[-len(_RESTORE_WRITES) :] == _RESTORE_WRITES


def test_fetch_waveform_configuration_failure_restores_state() -> None:
    transport = FakeTransport(
        write_failures={":WAVeform:SOURce C2": RuntimeError("configuration failed")}
    )

    with pytest.raises(RuntimeError, match="configuration failed"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert transport.binary_queries == []
    assert transport.writes[-len(_RESTORE_WRITES) :] == _RESTORE_WRITES


def test_fetch_waveform_invalid_preamble_restores_state() -> None:
    transport = FakeTransport(preamble=b"not a descriptor")

    with pytest.raises(DataError, match="346-byte descriptor"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert transport.binary_queries == [":WAVeform:PREamble?"]
    assert transport.writes[-len(_RESTORE_WRITES) :] == _RESTORE_WRITES


def test_fetch_waveform_preamble_total_length_mismatch_restores_before_data() -> None:
    preamble = bytearray(_preamble())
    struct.pack_into("<i", preamble, 60, 12)
    transport = FakeTransport(preamble=bytes(preamble))

    with pytest.raises(DataError, match="does not match the full record"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert transport.binary_queries == [":WAVeform:PREamble?"]
    assert transport.writes[-len(_RESTORE_WRITES) :] == _RESTORE_WRITES


def test_fetch_waveform_success_surfaces_restore_failure_and_attempts_remaining_writes() -> None:
    transport = FakeTransport(
        write_failures={":WAVeform:WIDTH BYTE": RuntimeError("restore failed")}
    )

    with pytest.raises(RuntimeError, match="restore failed"):
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert transport.writes[-1] == ":WAVeform:START 5"


def test_fetch_waveform_restore_failure_does_not_hide_primary_failure() -> None:
    transport = FakeTransport(
        chunks=[TimeoutError("primary binary failure")],
        write_failures={":WAVeform:WIDTH BYTE": RuntimeError("secondary restore failure")},
    )

    with pytest.raises(TimeoutError, match="primary binary failure") as caught:
        SDS800XHDScope(transport).fetch_waveform(
            channel=2,
            check_errors=False,
        )

    assert any("restoration also failed" in note for note in caught.value.__notes__)
    assert transport.writes[-1] == ":WAVeform:START 5"
