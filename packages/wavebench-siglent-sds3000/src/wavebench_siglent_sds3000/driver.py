from __future__ import annotations

from dataclasses import dataclass, field

from wavebench.errors import DataError, InstrumentError
from wavebench.transport.base import InstrumentTransport


_SUPPORTED_REMOTE_MANUFACTURER = "LECROY"
_SUPPORTED_MODEL = "SDS3054"
_SUPPORTED_FIRMWARE = "8.4.1"


@dataclass(frozen=True)
class SDS3000Identity:
    remote_manufacturer: str
    model: str
    serial: str
    firmware: str


def parse_sds3000_identity(response: str) -> SDS3000Identity:
    normalized = response.strip()
    if (
        not normalized
        or not normalized.isascii()
        or any(ord(character) < 0x20 for character in normalized)
    ):
        raise DataError("invalid SDS3000 *IDN? response")
    fields = tuple(field.strip() for field in normalized.split(","))
    if len(fields) != 4 or any(not field for field in fields):
        raise DataError("invalid SDS3000 *IDN? response")
    identity = SDS3000Identity(*fields)
    if identity.remote_manufacturer != _SUPPORTED_REMOTE_MANUFACTURER:
        raise InstrumentError("configured instrument is not a supported SIGLENT SDS3000")
    if identity.model != _SUPPORTED_MODEL:
        raise InstrumentError(
            f"unsupported SIGLENT SDS3000 model {identity.model!r}; expected {_SUPPORTED_MODEL}"
        )
    if identity.firmware != _SUPPORTED_FIRMWARE:
        raise InstrumentError(
            f"unsupported SDS3054 firmware {identity.firmware!r}; expected {_SUPPORTED_FIRMWARE}"
        )
    return identity


@dataclass
class SDS3000Scope:
    transport: InstrumentTransport
    _closed: bool = field(default=False, init=False, repr=False)

    def idn(self) -> str:
        response = self.transport.query("*IDN?").strip()
        parse_sds3000_identity(response)
        return response

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.transport.close()
