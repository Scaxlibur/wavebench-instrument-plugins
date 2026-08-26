from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments.models import (
    ScopeMeasurementSelector,
    ScopeMeasurementStatisticsRequestV2,
    ScopeMeasurementStatisticsV2,
)
from wavebench_rigol_mso8000.driver import MSO8104Scope


_STATISTIC_QUERY_TYPES = (
    "CURRENT",
    "AVERages",
    "DEViation",
    "MINimum",
    "MAXimum",
    "CNT",
)


class StatisticsTransport:
    def __init__(self, responses: dict[str, str]) -> None:
        self.responses = responses
        self.queries: list[str] = []
        self.close_calls = 0

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses[command]

    def close(self) -> None:
        self.close_calls += 1


def _commands(item: str, sources: tuple[str, ...]) -> list[str]:
    selector_args = f"{item},{','.join(sources)}"
    return [
        f":MEASure:STATistic:ITEM? {query_type},{selector_args}"
        for query_type in _STATISTIC_QUERY_TYPES
    ]


def _responses(
    item: str = "VPP",
    sources: tuple[str, ...] = ("CHAN1",),
    *,
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    commands = _commands(item, sources)
    return {
        command: value
        for command, value in zip(
            commands,
            ("1.100000E+00", "1.000000E+00", "1.000000E-02", "9.0E-01", "1.2E+00", "5.0E+00"),
            strict=True,
        )
    } | (overrides or {})


def _request(
    item: str = "VPP",
    sources: tuple[str, ...] = ("CHAN1",),
    **kwargs: object,
) -> ScopeMeasurementStatisticsRequestV2:
    return ScopeMeasurementStatisticsRequestV2(
        selector=ScopeMeasurementSelector(item=item, sources=sources),
        configured=True,
        **kwargs,
    )


def test_measurement_statistics_v2_reads_six_explicit_item_source_queries() -> None:
    transport = StatisticsTransport(_responses())
    request = _request()

    result = MSO8104Scope(transport=transport).get_measurement_statistics_v2(request)

    assert result == ScopeMeasurementStatisticsV2(
        selector=request.selector,
        category="VPP",
        actual=1.1,
        average=1.0,
        standard_deviation=0.01,
        minimum=0.9,
        maximum=1.2,
        waveform_count=5,
    )
    assert transport.queries == _commands("VPP", ("CHAN1",))


def test_measurement_statistics_v2_supports_documented_dual_source_items() -> None:
    sources = ("CHAN1", "CHAN2")
    transport = StatisticsTransport(_responses("RRDELAY", sources))

    result = MSO8104Scope(transport=transport).get_measurement_statistics_v2(
        _request("RRDELAY", sources)
    )

    assert result.selector.sources == sources
    assert result.category == "RRDELAY"
    assert transport.queries == _commands("RRDELAY", sources)


def test_measurement_statistics_v2_supports_documented_digital_period_source() -> None:
    transport = StatisticsTransport(_responses("PERIOD", ("D0",)))

    result = MSO8104Scope(transport=transport).get_measurement_statistics_v2(
        _request("PERIOD", ("D0",))
    )

    assert result.category == "PERIOD"
    assert transport.queries == _commands("PERIOD", ("D0",))


@pytest.mark.parametrize(
    "statistics_request",
    [
        ScopeMeasurementStatisticsRequestV2(
            selector=ScopeMeasurementSelector(slot=1),
            configured=True,
        ),
        _request("UNSUPPORTED", ("CHAN1",)),
        _request("VPP", ("CHAN1", "CHAN2")),
        _request("RRDELAY", ("CHAN1",)),
        _request("VPP", ("D0",)),
        _request("VPP", ("CHAN5",)),
        _request("VPP", ("CHAN1", "CHAN2", "CHAN3")),
        _request("VPP", ("CHAN1",), include_buffer=True),
    ],
)
def test_measurement_statistics_v2_rejects_unsupported_requests_without_io(
    statistics_request: ScopeMeasurementStatisticsRequestV2,
) -> None:
    transport = StatisticsTransport({})

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_measurement_statistics_v2(statistics_request)

    assert transport.queries == []


@pytest.mark.parametrize(
    ("query_type", "response"),
    [
        ("CURRENT", "not-a-number"),
        ("AVERages", "nan"),
        ("DEViation", "inf"),
        ("MINimum", "-inf"),
        ("MAXimum", ""),
    ],
)
def test_measurement_statistics_v2_stops_on_invalid_continuous_value(
    query_type: str,
    response: str,
) -> None:
    commands = _commands("VPP", ("CHAN1",))
    target = next(command for command in commands if f" {query_type}," in command)
    transport = StatisticsTransport(_responses(overrides={target: response}))

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_measurement_statistics_v2(_request())

    assert transport.queries == commands[: commands.index(target) + 1]


@pytest.mark.parametrize("response", ["-1", "1.5", "nan", "inf", "not-a-number"])
def test_measurement_statistics_v2_rejects_invalid_waveform_count(response: str) -> None:
    commands = _commands("VPP", ("CHAN1",))
    transport = StatisticsTransport(_responses(overrides={commands[-1]: response}))

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_measurement_statistics_v2(_request())

    assert transport.queries == commands


def test_measurement_statistics_v2_rejects_closed_driver_without_io() -> None:
    transport = StatisticsTransport(_responses())
    scope = MSO8104Scope(transport=transport)
    scope.close()

    with pytest.raises(InstrumentError, match="closed"):
        scope.get_measurement_statistics_v2(_request())

    assert transport.queries == []
    assert transport.close_calls == 1
