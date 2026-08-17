from __future__ import annotations

from dataclasses import dataclass

from wavebench.errors import DataError
from wavebench.transport.base import InstrumentTransport


@dataclass
class SDS800XHDScope:
    transport: InstrumentTransport

    def idn(self) -> str:
        response = self.transport.query("*IDN?").strip()
        if not response:
            raise DataError("SDS800X HD returned an empty response for *IDN?")
        return response

    def close(self) -> None:
        self.transport.close()
