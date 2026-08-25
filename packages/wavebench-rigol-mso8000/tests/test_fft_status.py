from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments.models import ScopeFftStatusV2
from wavebench_rigol_mso8000.driver import MSO8104Scope


def _commands(math_index: int = 1) -> list[str]:
    return [
        f":MATH{math_index}:OPERator?",
        f":MATH{math_index}:FFT:SOURce?",
        f":MATH{math_index}:FFT:WINDow?",
        f":MATH{math_index}:FFT:UNIT?",
        f":MATH{math_index}:FFT:FREQuency:STARt?",
        f":MATH{math_index}:FFT:FREQuency:END?",
    ]


class FftTransport:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.close_calls = 0

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses[command]

    def write(self, command: str) -> None:
        self.writes.append(command)

    def close(self) -> None:
        self.close_calls += 1


def _responses(
    math_index: int = 1,
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    return {
        command: value
        for command, value in zip(
            _commands(math_index),
            ("FFT", "CHAN1", "HANN", "DB", "0.0", "1.0E+06"),
            strict=True,
        )
    } | (overrides or {})


def test_fft_status_v2_reads_manual_backed_fields_without_writes() -> None:
    transport = FftTransport(_responses())

    result = MSO8104Scope(transport=transport).get_fft_status_v2(
        1,
        configured_fft=True,
    )

    assert result == ScopeFftStatusV2(
        math_index=1,
        source="CHAN1",
        window="HANN",
        vertical_unit="DB",
        frequency_start_hz=0.0,
        frequency_stop_hz=1_000_000.0,
        unavailable_fields=(
            "average_complete",
            "resolution_bandwidth_hz",
            "sample_rate_hz",
        ),
    )
    assert transport.queries == _commands()
    assert transport.writes == []


def test_fft_status_v2_uses_requested_math_index() -> None:
    transport = FftTransport(
        _responses(
            3,
            overrides={
                ":MATH3:FFT:SOURce?": "CHAN3",
                ":MATH3:FFT:WINDow?": "FLAT",
                ":MATH3:FFT:UNIT?": "VRMS",
                ":MATH3:FFT:FREQuency:STARt?": "-5.0",
                ":MATH3:FFT:FREQuency:END?": "25.0",
            },
        )
    )

    result = MSO8104Scope(transport=transport).get_fft_status_v2(
        3,
        configured_fft=True,
    )

    assert result.math_index == 3
    assert result.source == "CHAN3"
    assert result.window == "FLAT"
    assert result.vertical_unit == "VRMS"
    assert (result.frequency_start_hz, result.frequency_stop_hz) == (-5.0, 25.0)
    assert transport.queries == _commands(3)
    assert transport.writes == []


@pytest.mark.parametrize(
    ("math_index", "configured_fft"),
    [
        (0, True),
        (5, True),
        (True, True),
        (1.0, True),
        (1, False),
        (1, 1),
    ],
)
def test_fft_status_v2_rejects_invalid_preconditions_without_io(
    math_index: object,
    configured_fft: object,
) -> None:
    transport = FftTransport({})

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_fft_status_v2(
            math_index,  # type: ignore[arg-type]
            configured_fft=configured_fft,  # type: ignore[arg-type]
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    ("operator", "exception_type"),
    [("ADD", ConfigError), ("unknown", DataError)],
)
def test_fft_status_v2_requires_a_current_fft_operator_before_field_reads(
    operator: str,
    exception_type: type[Exception],
) -> None:
    transport = FftTransport(_responses(overrides={":MATH1:OPERator?": operator}))

    with pytest.raises(exception_type):
        MSO8104Scope(transport=transport).get_fft_status_v2(1, configured_fft=True)

    assert transport.queries == [":MATH1:OPERator?"]
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response"),
    [
        (":MATH1:FFT:SOURce?", "MATH1"),
        (":MATH1:FFT:WINDow?", "KAISER"),
        (":MATH1:FFT:UNIT?", "VPP"),
        (":MATH1:FFT:FREQuency:STARt?", "nan"),
        (":MATH1:FFT:FREQuency:END?", "inf"),
    ],
)
def test_fft_status_v2_stops_on_invalid_field_response(
    command: str,
    response: str,
) -> None:
    commands = _commands()
    transport = FftTransport(_responses(overrides={command: response}))

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_fft_status_v2(1, configured_fft=True)

    assert transport.queries == commands[: commands.index(command) + 1]
    assert transport.writes == []


def test_fft_status_v2_rejects_a_non_increasing_frequency_range() -> None:
    commands = _commands()
    transport = FftTransport(
        _responses(
            overrides={
                ":MATH1:FFT:FREQuency:STARt?": "1000",
                ":MATH1:FFT:FREQuency:END?": "1000",
            }
        )
    )

    with pytest.raises(DataError, match="start must be below"):
        MSO8104Scope(transport=transport).get_fft_status_v2(1, configured_fft=True)

    assert transport.queries == commands
    assert transport.writes == []


def test_fft_status_v2_rejects_closed_driver_without_io() -> None:
    transport = FftTransport(_responses())
    scope = MSO8104Scope(transport=transport)
    scope.close()

    with pytest.raises(InstrumentError, match="closed"):
        scope.get_fft_status_v2(1, configured_fft=True)

    assert transport.queries == []
    assert transport.writes == []
    assert transport.close_calls == 1
