from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments.scope_extensions import (
    ScopeAcquisitionStatusV2,
    ScopeAverageStatusV2,
)
from wavebench_rigol_mso8000.driver import MSO8104Scope


_FIELDS = (
    "acquisition_type",
    "sample_rate_hz",
    "memory_depth",
    "average",
    "average.configured_count",
)
_BASE_COMMANDS = (
    ":ACQuire:TYPE?",
    ":ACQuire:SRATe?",
    ":ACQuire:MDEPth?",
)


class AcquisitionStatusTransport:
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
    *,
    acquisition_type: str = "NORM",
    overrides: dict[str, str] | None = None,
) -> dict[str, str]:
    return {
        ":ACQuire:TYPE?": acquisition_type,
        ":ACQuire:SRATe?": "1.00000E+09",
        ":ACQuire:MDEPth?": "1.000E+06",
        ":ACQuire:AVERages?": "128",
    } | (overrides or {})


def test_acquisition_status_v2_reads_static_non_average_fields_without_writes() -> None:
    transport = AcquisitionStatusTransport(_responses())

    result = MSO8104Scope(transport=transport).get_acquisition_status_v2(fields=_FIELDS)

    assert result == ScopeAcquisitionStatusV2(
        acquisition_type="NORM",
        sample_rate_hz=1_000_000_000.0,
        memory_depth=1_000_000,
        unavailable_fields=("run_state", "segmented"),
        not_applicable_fields=("average",),
    )
    assert transport.queries == list(_BASE_COMMANDS)
    assert transport.writes == []


def test_acquisition_status_v2_reads_average_count_only_in_average_mode() -> None:
    transport = AcquisitionStatusTransport(_responses(acquisition_type="AVER"))

    result = MSO8104Scope(transport=transport).get_acquisition_status_v2(fields=_FIELDS)

    assert result == ScopeAcquisitionStatusV2(
        acquisition_type="AVER",
        sample_rate_hz=1_000_000_000.0,
        memory_depth=1_000_000,
        average=ScopeAverageStatusV2(configured_count=128),
        unavailable_fields=("run_state", "average.complete", "segmented"),
    )
    assert transport.queries == [*_BASE_COMMANDS, ":ACQuire:AVERages?"]
    assert transport.writes == []


@pytest.mark.parametrize(
    "fields",
    [
        (),
        ("acquisition_type",),
        ("acquisition_type", "run_state"),
        ["acquisition_type", "sample_rate_hz"],
    ],
)
def test_acquisition_status_v2_rejects_non_profile_fields_without_io(fields: object) -> None:
    transport = AcquisitionStatusTransport({})

    with pytest.raises(ConfigError, match="exact"):
        MSO8104Scope(transport=transport).get_acquisition_status_v2(
            fields=fields,  # type: ignore[arg-type]
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response"),
    [
        (":ACQuire:TYPE?", "ROLL"),
        (":ACQuire:SRATe?", "0"),
        (":ACQuire:MDEPth?", "1.5"),
        (":ACQuire:MDEPth?", "1.000E+09"),
    ],
)
def test_acquisition_status_v2_stops_on_invalid_static_response(
    command: str,
    response: str,
) -> None:
    transport = AcquisitionStatusTransport(_responses(overrides={command: response}))
    commands = list(_BASE_COMMANDS)

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_acquisition_status_v2(fields=_FIELDS)

    assert transport.queries == commands[: commands.index(command) + 1]
    assert transport.writes == []


@pytest.mark.parametrize("response", ["1", "3", "65537", "nan"])
def test_acquisition_status_v2_rejects_invalid_average_count(response: str) -> None:
    transport = AcquisitionStatusTransport(
        _responses(acquisition_type="AVER", overrides={":ACQuire:AVERages?": response})
    )

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_acquisition_status_v2(fields=_FIELDS)

    assert transport.queries == [*_BASE_COMMANDS, ":ACQuire:AVERages?"]
    assert transport.writes == []


def test_acquisition_status_v2_rejects_closed_driver_without_io() -> None:
    transport = AcquisitionStatusTransport(_responses())
    scope = MSO8104Scope(transport=transport)
    scope.close()

    with pytest.raises(InstrumentError, match="closed"):
        scope.get_acquisition_status_v2(fields=_FIELDS)

    assert transport.queries == []
    assert transport.writes == []
    assert transport.close_calls == 1
