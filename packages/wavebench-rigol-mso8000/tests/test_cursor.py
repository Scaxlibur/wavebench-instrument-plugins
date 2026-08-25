from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments.models import (
    ScopeCursorQuantity,
    ScopeCursorReadout,
    ScopeCursorReadoutV2,
)
from wavebench_rigol_mso8000.driver import MSO8104Scope


class CursorTransport:
    def __init__(self, responses: dict[str, str] | None = None) -> None:
        self.responses = {
            ":CURSor:MODE?": "MAN",
            ":CURSor:MANual:TYPE?": "TIME",
            ":CURSor:MANual:SOURce1?": "CHAN1",
            ":CURSor:MANual:SOURce2?": "CHAN1",
            ":CURSor:MANual:TUNit?": "SEC",
            ":CURSor:MANual:AXValue?": "-1.25e-6",
            ":CURSor:MANual:BXValue?": "1.25e-6",
            ":CURSor:MANual:XDELta?": "2.5e-6",
            ":CURSor:MANual:IXDelta?": "4e5",
            ":CURSor:MANual:AYValue?": "0.125",
            ":CURSor:MANual:BYValue?": "-0.125",
            ":CURSor:MANual:YDELta?": "-0.25",
            **(responses or {}),
        }
        self.queries: list[str] = []
        self.close_calls = 0

    def query(self, command: str) -> str:
        self.queries.append(command)
        return self.responses[command]

    def close(self) -> None:
        self.close_calls += 1


def test_time_cursor_readout_maps_seconds_and_inverse_frequency() -> None:
    transport = CursorTransport()

    readout = MSO8104Scope(transport=transport).get_cursor_readout(
        1,
        configured_cursor=True,
    )

    assert readout == ScopeCursorReadout(
        cursor_index=1,
        source="CHAN1",
        function="VERTICAL",
        x_delta_s=2.5e-6,
        inverse_x_delta_hz=4e5,
    )
    assert transport.queries == [
        ":CURSor:MODE?",
        ":CURSor:MANual:TYPE?",
        ":CURSor:MANual:SOURce1?",
        ":CURSor:MANual:SOURce2?",
        ":CURSor:MANual:TUNit?",
        ":CURSor:MANual:XDELta?",
        ":CURSor:MANual:IXDelta?",
    ]


def test_amplitude_cursor_readout_maps_source_units() -> None:
    transport = CursorTransport(
        {
            ":CURSor:MANual:TYPE?": "AMPL",
            ":CURSor:MANual:SOURce1?": "MATH2",
            ":CURSor:MANual:SOURce2?": "MATH2",
            ":CURSor:MANual:VUNit?": "SOUR",
            ":CURSor:MANual:YDELta?": "-0.25",
        }
    )

    readout = MSO8104Scope(transport=transport).get_cursor_readout(
        1,
        configured_cursor=True,
    )

    assert readout == ScopeCursorReadout(
        cursor_index=1,
        source="MATH2",
        function="HORIZONTAL",
        y_delta=-0.25,
    )
    assert transport.queries[-2:] == [
        ":CURSor:MANual:VUNit?",
        ":CURSor:MANual:YDELta?",
    ]


def test_cursor_readout_v2_reads_global_manual_time_values() -> None:
    transport = CursorTransport()

    readout = MSO8104Scope(transport=transport).get_cursor_readout_v2(
        None,
        configured_cursor=True,
    )

    assert readout == ScopeCursorReadoutV2(
        cursor_index=None,
        mode="MAN",
        function="TIME",
        source_a="CHAN1",
        source_b="CHAN1",
        x_a=ScopeCursorQuantity(-1.25e-6, "s"),
        x_b=ScopeCursorQuantity(1.25e-6, "s"),
        x_delta=ScopeCursorQuantity(2.5e-6, "s"),
        inverse_x_delta=ScopeCursorQuantity(4e5, "Hz"),
        not_applicable_fields=("cursor_index", "y_a", "y_b", "y_delta"),
    )
    assert transport.queries == [
        ":CURSor:MODE?",
        ":CURSor:MANual:TYPE?",
        ":CURSor:MANual:SOURce1?",
        ":CURSor:MANual:SOURce2?",
        ":CURSor:MANual:TUNit?",
        ":CURSor:MANual:AXValue?",
        ":CURSor:MANual:BXValue?",
        ":CURSor:MANual:XDELta?",
        ":CURSor:MANual:IXDelta?",
    ]


@pytest.mark.parametrize(
    ("unit", "quantity_unit", "inverse_unit", "expects_inverse"),
    [
        ("HZ", "Hz", "s", True),
        ("DEGR", "degree", None, False),
        ("PERC", "percent", None, False),
    ],
)
def test_cursor_readout_v2_preserves_time_units(
    unit: str,
    quantity_unit: str,
    inverse_unit: str | None,
    expects_inverse: bool,
) -> None:
    transport = CursorTransport(
        {
            ":CURSor:MANual:TUNit?": unit,
            ":CURSor:MANual:SOURce1?": "CHAN1",
            ":CURSor:MANual:SOURce2?": "CHAN2",
        }
    )

    readout = MSO8104Scope(transport=transport).get_cursor_readout_v2(
        None,
        configured_cursor=True,
    )

    assert readout.source_a == "CHAN1"
    assert readout.source_b == "CHAN2"
    assert readout.x_a == ScopeCursorQuantity(-1.25e-6, quantity_unit)  # type: ignore[arg-type]
    assert readout.x_b == ScopeCursorQuantity(1.25e-6, quantity_unit)  # type: ignore[arg-type]
    assert readout.x_delta == ScopeCursorQuantity(2.5e-6, quantity_unit)  # type: ignore[arg-type]
    if expects_inverse:
        assert readout.inverse_x_delta == ScopeCursorQuantity(4e5, inverse_unit)  # type: ignore[arg-type]
        assert ":CURSor:MANual:IXDelta?" in transport.queries
    else:
        assert readout.inverse_x_delta is None
        assert ":CURSor:MANual:IXDelta?" not in transport.queries
        assert readout.not_applicable_fields == (
            "cursor_index",
            "inverse_x_delta",
            "y_a",
            "y_b",
            "y_delta",
        )


@pytest.mark.parametrize(
    ("unit", "quantity_unit"),
    [("SOUR", "source"), ("PERC", "percent")],
)
def test_cursor_readout_v2_preserves_vertical_units(
    unit: str,
    quantity_unit: str,
) -> None:
    transport = CursorTransport(
        {
            ":CURSor:MANual:TYPE?": "AMPL",
            ":CURSor:MANual:SOURce1?": "MATH2",
            ":CURSor:MANual:SOURce2?": "CHAN2",
            ":CURSor:MANual:VUNit?": unit,
        }
    )

    readout = MSO8104Scope(transport=transport).get_cursor_readout_v2(
        None,
        configured_cursor=True,
    )

    assert readout == ScopeCursorReadoutV2(
        cursor_index=None,
        mode="MAN",
        function="AMPL",
        source_a="MATH2",
        source_b="CHAN2",
        y_a=ScopeCursorQuantity(0.125, quantity_unit),  # type: ignore[arg-type]
        y_b=ScopeCursorQuantity(-0.125, quantity_unit),  # type: ignore[arg-type]
        y_delta=ScopeCursorQuantity(-0.25, quantity_unit),  # type: ignore[arg-type]
        not_applicable_fields=(
            "cursor_index",
            "x_a",
            "x_b",
            "x_delta",
            "inverse_x_delta",
        ),
    )
    assert transport.queries == [
        ":CURSor:MODE?",
        ":CURSor:MANual:TYPE?",
        ":CURSor:MANual:SOURce1?",
        ":CURSor:MANual:SOURce2?",
        ":CURSor:MANual:VUNit?",
        ":CURSor:MANual:AYValue?",
        ":CURSor:MANual:BYValue?",
        ":CURSor:MANual:YDELta?",
    ]


@pytest.mark.parametrize(
    ("cursor_index", "configured_cursor"),
    [(1, True), (0, True), (None, False), (None, 1)],
)
def test_cursor_readout_v2_rejects_invalid_preconditions_without_io(
    cursor_index: object,
    configured_cursor: object,
) -> None:
    transport = CursorTransport()

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout_v2(
            cursor_index,  # type: ignore[arg-type]
            configured_cursor=configured_cursor,  # type: ignore[arg-type]
        )

    assert transport.queries == []


@pytest.mark.parametrize(
    ("cursor_type", "source_a", "source_b", "query"),
    [
        ("HBA", "CHAN1", "CHAN1", ":CURSor:MANual:SOURce1?"),
        ("TIME", "NONE", "CHAN1", ":CURSor:MANual:TUNit?"),
        ("AMPL", "LA", "CHAN1", ":CURSor:MANual:VUNit?"),
    ],
)
def test_cursor_readout_v2_rejects_unsupported_manual_states_before_values(
    cursor_type: str,
    source_a: str,
    source_b: str,
    query: str,
) -> None:
    transport = CursorTransport(
        {
            ":CURSor:MANual:TYPE?": cursor_type,
            ":CURSor:MANual:SOURce1?": source_a,
            ":CURSor:MANual:SOURce2?": source_b,
        }
    )

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout_v2(
            None,
            configured_cursor=True,
        )

    assert query not in transport.queries
    assert not any("Value?" in command or "DELta?" in command for command in transport.queries)


@pytest.mark.parametrize(
    ("cursor_index", "configured_cursor"),
    [(0, True), (2, True), (True, True), (1.0, True), (1, False), (1, 0)],
)
def test_cursor_readout_rejects_invalid_preconditions_without_io(
    cursor_index: object,
    configured_cursor: object,
) -> None:
    transport = CursorTransport()

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout(
            cursor_index,  # type: ignore[arg-type]
            configured_cursor=configured_cursor,  # type: ignore[arg-type]
        )

    assert transport.queries == []


@pytest.mark.parametrize("mode", ["TRAC", "XY", "MEAS", "BROKEN"])
def test_cursor_readout_rejects_unsupported_or_invalid_mode(mode: str) -> None:
    transport = CursorTransport({":CURSor:MODE?": mode})

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout(
            1,
            configured_cursor=True,
        )

    assert transport.queries == [":CURSor:MODE?"]


@pytest.mark.parametrize(
    ("source_a", "source_b"),
    [("NONE", "NONE"), ("CHAN1", "CHAN2"), ("CHAN5", "CHAN5")],
)
def test_cursor_readout_rejects_unrepresentable_sources(
    source_a: str,
    source_b: str,
) -> None:
    transport = CursorTransport(
        {
            ":CURSor:MANual:SOURce1?": source_a,
            ":CURSor:MANual:SOURce2?": source_b,
        }
    )

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout(
            1,
            configured_cursor=True,
        )

    assert ":CURSor:MANual:TUNit?" not in transport.queries


@pytest.mark.parametrize("cursor_type", ["HBA", "VBA", "BROKEN"])
def test_cursor_readout_rejects_unsupported_or_invalid_manual_type(
    cursor_type: str,
) -> None:
    transport = CursorTransport({":CURSor:MANual:TYPE?": cursor_type})

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout(
            1,
            configured_cursor=True,
        )

    assert not any("DELta?" in query for query in transport.queries)


@pytest.mark.parametrize("unit", ["HZ", "DEGR", "PERC", "BROKEN"])
def test_time_cursor_requires_seconds_without_reading_results(unit: str) -> None:
    transport = CursorTransport({":CURSor:MANual:TUNit?": unit})

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout(
            1,
            configured_cursor=True,
        )

    assert ":CURSor:MANual:XDELta?" not in transport.queries


@pytest.mark.parametrize("unit", ["PERC", "BROKEN"])
def test_amplitude_cursor_requires_source_units_without_reading_result(
    unit: str,
) -> None:
    transport = CursorTransport(
        {
            ":CURSor:MANual:TYPE?": "AMPL",
            ":CURSor:MANual:VUNit?": unit,
        }
    )

    with pytest.raises((ConfigError, DataError)):
        MSO8104Scope(transport=transport).get_cursor_readout(
            1,
            configured_cursor=True,
        )

    assert ":CURSor:MANual:YDELta?" not in transport.queries


def test_amplitude_cursor_rejects_la_before_unit_or_result_queries() -> None:
    transport = CursorTransport(
        {
            ":CURSor:MANual:TYPE?": "AMPL",
            ":CURSor:MANual:SOURce1?": "LA",
            ":CURSor:MANual:SOURce2?": "LA",
        }
    )

    with pytest.raises(ConfigError, match="LA source"):
        MSO8104Scope(transport=transport).get_cursor_readout(
            1,
            configured_cursor=True,
        )

    assert ":CURSor:MANual:VUNit?" not in transport.queries


@pytest.mark.parametrize("response", ["", "nan", "inf", "value"])
def test_cursor_readout_rejects_invalid_numeric_results(response: str) -> None:
    transport = CursorTransport({":CURSor:MANual:XDELta?": response})

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_cursor_readout(
            1,
            configured_cursor=True,
        )


def test_closed_cursor_driver_performs_no_queries() -> None:
    transport = CursorTransport()
    scope = MSO8104Scope(transport=transport)
    scope.close()

    with pytest.raises(InstrumentError, match="closed"):
        scope.get_cursor_readout(1, configured_cursor=True)

    assert transport.queries == []
