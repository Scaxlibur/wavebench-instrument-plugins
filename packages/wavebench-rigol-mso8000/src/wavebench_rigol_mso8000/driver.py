from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock

from wavebench.errors import DataError, InstrumentError
from wavebench.transport.base import InstrumentTransport

from .parsers import normalize_channel_input, parse_mso8104_identity


_ANALOG_CHANNELS = frozenset({1, 2, 3, 4})


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

    @staticmethod
    def _validate_analog_channel(channel: int) -> None:
        if type(channel) is not int or channel not in _ANALOG_CHANNELS:
            raise DataError("MSO8104 analog channel must be an integer from 1 through 4")

    def channel_coupling(self, channel: int) -> str:
        self._validate_analog_channel(channel)
        with self._io_lock:
            self._require_open()
            coupling = self.transport.query(f":CHANnel{channel}:COUPling?")
            impedance = self.transport.query(f":CHANnel{channel}:IMPedance?")
            return normalize_channel_input(coupling=coupling, impedance=impedance)

    def close(self) -> None:
        with self._io_lock:
            if self._closed:
                return
            self._closed = True
            self.transport.close()
