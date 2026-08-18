from __future__ import annotations

from dataclasses import dataclass

from wavebench.errors import DataError


@dataclass(frozen=True)
class RigolIdentity:
    manufacturer: str
    model: str
    serial_number: str
    firmware: str


def parse_mso8104_identity(response: str) -> RigolIdentity:
    normalized = response.strip()
    parts = tuple(item.strip() for item in normalized.split(",", 3))
    if len(parts) != 4 or any(not item for item in parts):
        raise DataError(f"invalid MSO8104 *IDN? response: {response!r}")
    manufacturer, model, serial_number, firmware = parts
    if manufacturer.upper() != "RIGOL TECHNOLOGIES":
        raise DataError(
            f"unexpected MSO8104 manufacturer in *IDN? response: {manufacturer!r}"
        )
    if model.upper() != "MSO8104":
        raise DataError(f"unexpected MSO8104 model in *IDN? response: {model!r}")
    return RigolIdentity(
        manufacturer=manufacturer,
        model=model,
        serial_number=serial_number,
        firmware=firmware,
    )


def _parse_enum(response: str, *, field: str, allowed: frozenset[str]) -> str:
    normalized = response.strip().upper()
    if normalized not in allowed:
        raise DataError(f"invalid MSO8104 {field} response: {response!r}")
    return normalized


def normalize_channel_input(*, coupling: str, impedance: str) -> str:
    normalized_coupling = _parse_enum(
        coupling,
        field="channel coupling",
        allowed=frozenset({"AC", "DC", "GND"}),
    )
    normalized_impedance = _parse_enum(
        impedance,
        field="channel impedance",
        allowed=frozenset({"OMEG", "FIFT"}),
    )
    if normalized_coupling == "GND":
        return "GND"
    if normalized_impedance == "OMEG":
        return f"{normalized_coupling}L"
    return normalized_coupling
