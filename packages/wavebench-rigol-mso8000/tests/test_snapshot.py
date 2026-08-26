from __future__ import annotations

import pytest

from wavebench.errors import ConfigError, DataError, InstrumentError
from wavebench.instruments.models import (
    SCOPE_SNAPSHOT_V2_FIELD_ORDER,
    ScopeIdentitySnapshot,
    ScopeSnapshotV2,
)
from wavebench_rigol_mso8000.driver import MSO8104Scope


_FIELDS = (
    "identity.manufacturer",
    "identity.model",
    "identity.serial_number",
    "identity.firmware",
    "identity.options",
)
_OPTION_TYPES = (
    "BW610",
    "BW620",
    "BW1020",
    "BND",
    "COMP",
    "EMBD",
    "AUTO",
    "FLEX",
    "AUDIO",
    "AERO",
    "AWG",
    "PWR",
    "JITTER",
)
_COMMANDS = (
    "*IDN?",
    *(f":SYSTem:OPTion:STATus? {option}" for option in _OPTION_TYPES),
)
_UNAVAILABLE_FIELDS = tuple(
    field_name for field_name in SCOPE_SNAPSHOT_V2_FIELD_ORDER if field_name not in _FIELDS
)


class SnapshotTransport:
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


def _responses(*, overrides: dict[str, str] | None = None) -> dict[str, str]:
    return {
        "*IDN?": "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000,00.01.02.03",
        **{f":SYSTem:OPTion:STATus? {option}": "0" for option in _OPTION_TYPES},
    } | (overrides or {})


def _expected(options: tuple[str, ...]) -> ScopeSnapshotV2:
    return ScopeSnapshotV2(
        identity=ScopeIdentitySnapshot(
            manufacturer="RIGOL TECHNOLOGIES",
            model="MSO8104",
            serial_number="MSO8A000000000",
            firmware="00.01.02.03",
            options=options,
        ),
        unavailable_fields=_UNAVAILABLE_FIELDS,
    )


def test_snapshot_v2_reads_current_identity_and_all_manual_option_statuses_without_writes() -> None:
    transport = SnapshotTransport(
        _responses(
            overrides={
                ":SYSTem:OPTion:STATus? BND": "1",
                ":SYSTem:OPTion:STATus? AWG": "1",
            }
        )
    )

    result = MSO8104Scope(transport=transport).get_snapshot_v2(1, fields=_FIELDS)

    assert result == _expected(("BND", "AWG"))
    assert transport.queries == list(_COMMANDS)
    assert transport.writes == []


def test_snapshot_v2_uses_an_empty_option_tuple_only_after_all_manual_option_queries() -> None:
    transport = SnapshotTransport(_responses())

    result = MSO8104Scope(transport=transport).get_snapshot_v2(4, fields=_FIELDS)

    assert result == _expected(())
    assert transport.queries == list(_COMMANDS)
    assert transport.writes == []


@pytest.mark.parametrize(
    "fields",
    [
        (),
        ("identity.manufacturer",),
        (*_FIELDS, "health.sample_rate_hz"),
        ["identity.manufacturer", "identity.model"],
    ],
)
def test_snapshot_v2_rejects_non_profile_fields_without_io(fields: object) -> None:
    transport = SnapshotTransport({})

    with pytest.raises(ConfigError, match="exact"):
        MSO8104Scope(transport=transport).get_snapshot_v2(
            1,
            fields=fields,  # type: ignore[arg-type]
        )

    assert transport.queries == []
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response"),
    [
        ("*IDN?", "RIGOL TECHNOLOGIES,MSO8104,MSO8A000000000"),
        (":SYSTem:OPTion:STATus? BW620", "ON"),
        (":SYSTem:OPTion:STATus? JITTER", "2"),
    ],
)
def test_snapshot_v2_stops_on_invalid_identity_or_option_response(
    command: str,
    response: str,
) -> None:
    transport = SnapshotTransport(_responses(overrides={command: response}))

    with pytest.raises(DataError):
        MSO8104Scope(transport=transport).get_snapshot_v2(1, fields=_FIELDS)

    assert transport.queries == list(_COMMANDS[: _COMMANDS.index(command) + 1])
    assert transport.writes == []


@pytest.mark.parametrize("channel", [0, 5, True, 1.0])
def test_snapshot_v2_rejects_non_mso_analog_channel_without_io(channel: object) -> None:
    transport = SnapshotTransport({})

    with pytest.raises(DataError, match="1 through 4"):
        MSO8104Scope(transport=transport).get_snapshot_v2(
            channel,  # type: ignore[arg-type]
            fields=_FIELDS,
        )

    assert transport.queries == []
    assert transport.writes == []


def test_snapshot_v2_rejects_closed_driver_without_io() -> None:
    transport = SnapshotTransport(_responses())
    scope = MSO8104Scope(transport=transport)
    scope.close()

    with pytest.raises(InstrumentError, match="closed"):
        scope.get_snapshot_v2(1, fields=_FIELDS)

    assert transport.queries == []
    assert transport.writes == []
    assert transport.close_calls == 1
