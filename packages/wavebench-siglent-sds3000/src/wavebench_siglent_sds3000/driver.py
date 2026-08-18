from __future__ import annotations

from dataclasses import dataclass, field

from wavebench.errors import DataError, InstrumentError
from wavebench.transport.base import InstrumentTransport


_SUPPORTED_REMOTE_MANUFACTURER = "LECROY"
_SUPPORTED_MODEL = "SDS3054"
_SUPPORTED_FIRMWARE = "8.4.1"
_SUPPORTED_CHANNELS = (1, 2, 3, 4)
_COUPLING_MAP = {
    "A1M": "ACL",
    "D1M": "DCL",
    "D50": "DC",
    "GND": "GND",
}


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
    _identity: SDS3000Identity | None = field(default=None, init=False, repr=False)

    @staticmethod
    def _validate_channel(channel: int) -> None:
        if isinstance(channel, bool) or channel not in _SUPPORTED_CHANNELS:
            raise DataError("SDS3054 channel must be one of CH1, CH2, CH3, or CH4")

    def _query_identity(self) -> tuple[str, SDS3000Identity]:
        response = self.transport.query("*IDN?").strip()
        identity = parse_sds3000_identity(response)
        self._identity = identity
        return response, identity

    def _require_identity(self) -> SDS3000Identity:
        if self._identity is None:
            _, identity = self._query_identity()
            return identity
        return self._identity

    def idn(self) -> str:
        response, _ = self._query_identity()
        return response

    def channel_coupling(self, channel: int) -> str:
        self._validate_channel(channel)
        self._require_identity()
        response = self.transport.query(f"C{channel}:CPL?")
        normalized = response.strip().upper().split()
        if len(normalized) == 1:
            value = normalized[0]
        elif len(normalized) == 2 and normalized[0] in {
            f"C{channel}:CPL",
            f"C{channel}:COUPLING",
        }:
            value = normalized[1]
        else:
            raise DataError(f"invalid C{channel}:CPL? response")
        if value == "OVL":
            raise InstrumentError(
                f"SDS3054 CH{channel} reports a 50 ohm input overload and disconnected the input"
            )
        try:
            return _COUPLING_MAP[value]
        except KeyError as exc:
            raise DataError(f"invalid C{channel}:CPL? response") from exc

    @staticmethod
    def _parse_register(response: str, *, register: str, maximum: int) -> int:
        fields = response.strip().upper().split()
        if len(fields) == 1:
            raw_value = fields[0]
        elif len(fields) == 2 and fields[0].removesuffix("?") == register:
            raw_value = fields[1]
        else:
            raise DataError(f"invalid {register}? response")
        if not raw_value.isascii() or not raw_value.isdecimal():
            raise DataError(f"invalid {register}? response")
        value = int(raw_value)
        if value > maximum:
            raise DataError(f"out-of-range {register}? response")
        return value

    def errors(self, limit: int = 16) -> list[str]:
        if isinstance(limit, bool) or not isinstance(limit, int) or limit < 1:
            raise DataError("SDS3054 error limit must be a positive integer")
        self._require_identity()
        registers = (
            (
                "CMR",
                self._parse_register(self.transport.query("CMR?"), register="CMR", maximum=13),
            ),
            (
                "EXR",
                self._parse_register(self.transport.query("EXR?"), register="EXR", maximum=64),
            ),
            (
                "DDR",
                self._parse_register(self.transport.query("DDR?"), register="DDR", maximum=65_535),
            ),
        )
        return [f"{register} {value}" for register, value in registers if value][:limit]

    def assert_no_errors(self) -> None:
        active = self.errors()
        if active:
            raise InstrumentError("SDS3054 error registers are not clear: " + "; ".join(active))

    def close(self) -> None:
        if self._closed:
            return
        self._closed = True
        self.transport.close()
