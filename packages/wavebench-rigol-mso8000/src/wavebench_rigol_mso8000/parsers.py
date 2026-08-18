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
