from __future__ import annotations

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments.models import (
    ScopeDigitalChannelStatusV2,
    ScopeDigitalPodStatusV2,
    ScopeDigitalSharedStatusV2,
)
from wavebench_rigol_mso8000.driver import MSO8104Scope


def _commands(channel: int = 0) -> list[str]:
    pod = 1 if channel <= 7 else 2
    return [
        ":SYSTem:MODules?",
        f":LA:DIGital:DISPlay? D{channel}",
        f":LA:DIGital:LABel? D{channel}",
        f":LA:POD{pod}:THReshold?",
        ":LA:TCALibrate?",
        ":LA:SIZE?",
    ]


class DigitalStatusTransport:
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
    channel: int = 0,
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    return {
        command: response
        for command, response in zip(
            _commands(channel),
            ("1,0,0,0,0", "1", "DATA", "1.400000E0", "2.000000E-8", "MED"),
            strict=True,
        )
    } | (overrides or {})


def test_digital_status_v2_reads_manual_backed_pod_and_shared_fields_without_writes() -> None:
    transport = DigitalStatusTransport(_responses())

    result = MSO8104Scope(transport=transport).get_digital_status_v2(0)

    assert result == ScopeDigitalChannelStatusV2(
        channel=0,
        displayed=True,
        label="DATA",
        pod=ScopeDigitalPodStatusV2(
            start_channel=0,
            stop_channel=7,
            threshold_v=1.4,
            threshold_scope="pod",
        ),
        shared=ScopeDigitalSharedStatusV2(
            module_present=True,
            timing_calibration_s=20e-9,
            size="MEDIUM",
        ),
        unavailable_fields=(
            "position_div",
            "label_enabled",
            "activity",
            "technology",
            "hysteresis",
        ),
    )
    assert transport.queries == _commands()
    assert transport.writes == []


def test_digital_status_v2_maps_the_second_pod_and_preserves_an_empty_label() -> None:
    transport = DigitalStatusTransport(
        _responses(
            12,
            overrides={
                ":LA:DIGital:DISPlay? D12": "0",
                ":LA:DIGital:LABel? D12": "\n",
                ":LA:POD2:THReshold?": "-2.000000E0",
                ":LA:TCALibrate?": "0",
                ":LA:SIZE?": "LARG",
            },
        )
    )

    result = MSO8104Scope(transport=transport).get_digital_status_v2(12)

    assert result.channel == 12
    assert result.displayed is False
    assert result.label == ""
    assert result.pod == ScopeDigitalPodStatusV2(
        start_channel=8,
        stop_channel=15,
        threshold_v=-2.0,
        threshold_scope="pod",
    )
    assert result.shared == ScopeDigitalSharedStatusV2(
        module_present=True,
        timing_calibration_s=0.0,
        size="LARGE",
    )
    assert transport.queries == _commands(12)
    assert transport.writes == []


def test_digital_status_v2_reports_an_absent_la_module_without_la_queries() -> None:
    transport = DigitalStatusTransport({":SYSTem:MODules?": "0,0,0,0,0"})

    result = MSO8104Scope(transport=transport).get_digital_status_v2(3)

    assert result == ScopeDigitalChannelStatusV2(
        channel=3,
        shared=ScopeDigitalSharedStatusV2(module_present=False),
        unavailable_fields=(
            "displayed",
            "position_div",
            "label",
            "label_enabled",
            "activity",
            "technology",
            "hysteresis",
            "pod",
            "shared.timing_calibration_s",
            "shared.size",
        ),
    )
    assert transport.queries == [":SYSTem:MODules?"]
    assert transport.writes == []


@pytest.mark.parametrize("channel", [-1, 16, True, 1.0])
def test_digital_status_v2_rejects_non_mso_channel_without_io(channel: object) -> None:
    transport = DigitalStatusTransport({})

    with pytest.raises(DataError, match="0 through 15"):
        MSO8104Scope(transport=transport).get_digital_status_v2(channel)  # type: ignore[arg-type]

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response"),
    [
        (":SYSTem:MODules?", "1"),
        (":SYSTem:MODules?", "2,0,0,0,0"),
        (":LA:DIGital:DISPlay? D0", "ON"),
        (":LA:POD1:THReshold?", "nan"),
        (":LA:POD1:THReshold?", "20.1"),
        (":LA:TCALibrate?", "101E-9"),
        (":LA:SIZE?", "GIANT"),
    ],
)
def test_digital_status_v2_stops_on_invalid_manual_response(command: str, response: str) -> None:
    transport = DigitalStatusTransport(_responses(overrides={command: response}))
    commands = _commands()

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_digital_status_v2(0)

    assert transport.queries == commands[: commands.index(command) + 1]
    assert transport.writes == []


def test_digital_status_v2_rejects_closed_driver_without_io() -> None:
    transport = DigitalStatusTransport(_responses())
    scope = MSO8104Scope(transport=transport)
    scope.close()

    with pytest.raises(InstrumentError, match="closed"):
        scope.get_digital_status_v2(0)

    assert transport.queries == []
    assert transport.writes == []
    assert transport.close_calls == 1
