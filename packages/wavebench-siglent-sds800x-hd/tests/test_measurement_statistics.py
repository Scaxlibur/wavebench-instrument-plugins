from __future__ import annotations

from types import SimpleNamespace

import pytest

from wavebench.errors import DataError
from wavebench.instruments.models import ScopeMeasurementStatistics
from wavebench.services.scope_service import ScopeService

from wavebench_siglent_sds800x_hd import descriptor
from wavebench_siglent_sds800x_hd.driver import SDS800XHDScope


class FakeTransport:
    resource = "TCPIP0::<configured>::INSTR"

    def __init__(self, responses: dict[str, str]):
        self.responses = responses
        self.queries: list[str] = []
        self.writes: list[str] = []

    def query(self, command: str, **_kwargs) -> str:
        self.queries.append(command)
        return self.responses[command]

    def write(self, command: str) -> None:
        self.writes.append(command)

    def close(self) -> None:
        pass


def responses_for_slot(slot: int = 3) -> dict[str, str]:
    prefix = f":MEASure:ADVanced:P{slot}"
    return {
        ":MEASure:MODE?": "ADVanced",
        f"{prefix}?": "ON",
        ":MEASure:ADVanced:STATistics?": "ON",
        f"{prefix}:TYPE?": "PKPK",
        f"{prefix}:STATistics? CURRENT": "5.02",
        f"{prefix}:STATistics? MEAN": "5.01",
        f"{prefix}:STATistics? MINimum": "4.98",
        f"{prefix}:STATistics? MAXimum": "5.04",
        f"{prefix}:STATistics? STDev": "0.01",
        f"{prefix}:STATistics? COUNT": "4.2E+01",
    }


def test_reads_existing_measurement_statistics_without_writes() -> None:
    transport = FakeTransport(responses_for_slot())

    result = SDS800XHDScope(transport).get_measurement_statistics(
        3,
        configured_slot=True,
    )

    assert result == ScopeMeasurementStatistics(
        slot=3,
        category="PKPK",
        actual=5.02,
        average=5.01,
        standard_deviation=0.01,
        minimum=4.98,
        maximum=5.04,
        waveform_count=42,
    )
    assert transport.writes == []
    assert transport.queries == [
        ":MEASure:MODE?",
        ":MEASure:ADVanced:P3?",
        ":MEASure:ADVanced:STATistics?",
        ":MEASure:ADVanced:P3:TYPE?",
        ":MEASure:ADVanced:P3:STATistics? CURRENT",
        ":MEASure:ADVanced:P3:STATistics? MEAN",
        ":MEASure:ADVanced:P3:STATistics? MINimum",
        ":MEASure:ADVanced:P3:STATistics? MAXimum",
        ":MEASure:ADVanced:P3:STATistics? STDev",
        ":MEASure:ADVanced:P3:STATistics? COUNT",
    ]


def test_core_scope_service_reads_measurement_statistics() -> None:
    transport = FakeTransport(responses_for_slot())
    driver = SDS800XHDScope(transport)
    item = descriptor()
    service = ScopeService(
        config=SimpleNamespace(
            scope=SimpleNamespace(driver=item.driver_id, access="read_only")
        ),
        logger=SimpleNamespace(),
        session=driver,
        descriptor=item,
    )

    result = service.measurement_statistics(3, configured_slot=True)

    assert result.category == "PKPK"
    assert result.waveform_count == 42
    assert transport.writes == []


def test_maps_nan_measurement_value_to_none() -> None:
    responses = responses_for_slot()
    responses[":MEASure:ADVanced:P3:STATistics? CURRENT"] = "NAN"

    result = SDS800XHDScope(FakeTransport(responses)).get_measurement_statistics(
        3,
        configured_slot=True,
    )

    assert result.actual is None


def test_reads_statistics_history_only_with_stopped_confirmation() -> None:
    responses = responses_for_slot()
    responses[":MEASure:ADVanced:P3:SHIStory?"] = "Count=3,4.98,5.01,5.02,"
    transport = FakeTransport(responses)

    result = SDS800XHDScope(transport).get_measurement_statistics(
        3,
        configured_slot=True,
        include_buffer=True,
        acquisition_stopped=True,
    )

    assert result.buffered_values == (4.98, 5.01, 5.02)
    assert transport.queries[-1] == ":MEASure:ADVanced:P3:SHIStory?"
    assert transport.writes == []


@pytest.mark.parametrize("slot", [True, 0, 13, 1.0, "1"])
def test_rejects_invalid_slot_before_io(slot: object) -> None:
    transport = FakeTransport({})

    with pytest.raises(ValueError, match="slot must be"):
        SDS800XHDScope(transport).get_measurement_statistics(  # type: ignore[arg-type]
            slot,
            configured_slot=True,
        )

    assert transport.queries == []


def test_requires_configured_slot_before_io() -> None:
    transport = FakeTransport({})

    with pytest.raises(ValueError, match="already configured"):
        SDS800XHDScope(transport).get_measurement_statistics(3, configured_slot=False)

    assert transport.queries == []


def test_requires_stopped_confirmation_for_history_before_io() -> None:
    transport = FakeTransport({})

    with pytest.raises(ValueError, match="acquisition is stopped"):
        SDS800XHDScope(transport).get_measurement_statistics(
            3,
            configured_slot=True,
            include_buffer=True,
        )

    assert transport.queries == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        (":MEASure:MODE?", "SIMPlc", "advanced measurement mode"),
        (":MEASure:ADVanced:P3?", "MAYBE", "slot state"),
        (":MEASure:ADVanced:P3?", "OFF", "slot is not enabled"),
        (":MEASure:ADVanced:STATistics?", "OFF", "statistics are not enabled"),
        (":MEASure:ADVanced:P3:STATistics? CURRENT", "INF", "finite or NAN"),
        (":MEASure:ADVanced:P3:STATistics? COUNT", "1.5", "non-negative integer"),
    ],
)
def test_rejects_invalid_or_disabled_instrument_responses(
    command: str,
    response: str,
    message: str,
) -> None:
    responses = responses_for_slot()
    responses[command] = response

    with pytest.raises(DataError, match=message):
        SDS800XHDScope(FakeTransport(responses)).get_measurement_statistics(
            3,
            configured_slot=True,
        )


@pytest.mark.parametrize(
    "response",
    [
        "3,1,2,3",
        "Count=2,1,2,3",
        "Count=1,NAN",
        "Count=1025," + ",".join("1" for _ in range(1025)),
    ],
)
def test_rejects_malformed_statistics_history(response: str) -> None:
    responses = responses_for_slot()
    responses[":MEASure:ADVanced:P3:SHIStory?"] = response

    with pytest.raises(DataError, match="statistics history"):
        SDS800XHDScope(FakeTransport(responses)).get_measurement_statistics(
            3,
            configured_slot=True,
            include_buffer=True,
            acquisition_stopped=True,
        )
