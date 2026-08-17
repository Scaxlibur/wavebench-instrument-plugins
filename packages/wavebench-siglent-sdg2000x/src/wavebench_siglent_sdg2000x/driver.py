from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from wavebench.errors import DataError
from wavebench.transport.base import InstrumentTransport


_SUPPORTED_MODELS = frozenset({"SDG2042X", "SDG2082X", "SDG2122X"})


def parse_idn_model(response: str) -> str:
    """Return a verified SDG2000X model from either documented IDN format."""

    value = response.strip()
    if not value:
        raise DataError("SDG2000X returned an empty *IDN? response")
    fields = tuple(item.strip() for item in value.split(","))

    if len(fields) >= 4 and fields[0].casefold() == "siglent technologies":
        model = fields[1].upper()
    elif (
        len(fields) >= 5
        and fields[0].upper() == "*IDN"
        and fields[1].upper() == "SDG"
    ):
        model = fields[2].upper()
    else:
        raise DataError("unsupported SDG2000X identity response format")

    if model not in _SUPPORTED_MODELS:
        raise DataError(f"unsupported SDG2000X model: {model or '<empty>'}")
    return model


@dataclass
class SDG2000XSource:
    transport: InstrumentTransport
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)

    def idn(self) -> str:
        with self._io_lock:
            response = self.transport.query("*IDN?").strip()
            parse_idn_model(response)
            return response

    def close(self) -> None:
        with self._io_lock:
            self.transport.close()
