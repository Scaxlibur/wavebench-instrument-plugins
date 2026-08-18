from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from wavebench.errors import InstrumentError
from wavebench.transport.base import InstrumentTransport

from .parsers import parse_mso8104_identity


@dataclass
class MSO8104Scope:
    transport: InstrumentTransport
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def _require_open(self) -> None:
        if self._closed:
            raise InstrumentError("MSO8104 driver is closed")

    def idn(self) -> str:
        with self._io_lock:
            self._require_open()
            response = self.transport.query("*IDN?").strip()
            parse_mso8104_identity(response)
            return response

    def close(self) -> None:
        with self._io_lock:
            if self._closed:
                return
            self._closed = True
            self.transport.close()
