from __future__ import annotations

from dataclasses import dataclass, field

from wavebench.errors import DataError
from wavebench.transport.base import InstrumentTransport


_MODEL_CHANNEL_COUNTS = {
    "SDS802X HD": 2,
    "SDS804X HD": 4,
    "SDS812X HD": 2,
    "SDS814X HD": 4,
    "SDS822X HD": 2,
    "SDS824X HD": 4,
}
_SUPPORTED_COUPLINGS = {"AC", "DC", "GND"}


def _normalize_identity_field(value: str) -> str:
    return " ".join(value.strip().upper().split())


@dataclass
class SDS800XHDScope:
    transport: InstrumentTransport
    _identity_response: str | None = field(default=None, init=False, repr=False)
    _model: str | None = field(default=None, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)

    def _ensure_identity(self) -> tuple[str, str]:
        if self._identity_response is not None and self._model is not None:
            return self._identity_response, self._model

        response = self.transport.query("*IDN?").strip()
        if not response:
            raise DataError("SDS800X HD returned an empty response for *IDN?")

        fields = tuple(item.strip() for item in response.split(","))
        if len(fields) != 4 or any(not item for item in fields):
            raise DataError("SDS800X HD *IDN? must contain four non-empty comma-separated fields")
        manufacturer, model_text, serial, firmware = fields
        if _normalize_identity_field(manufacturer) != "SIGLENT TECHNOLOGIES":
            raise DataError("SDS800X HD *IDN? returned an unsupported manufacturer")

        model = _normalize_identity_field(model_text)
        if model not in _MODEL_CHANNEL_COUNTS:
            raise DataError("SDS800X HD *IDN? returned an unsupported model")
        if len(serial) != 14 or not serial.isascii():
            raise DataError("SDS800X HD *IDN? serial must contain 14 ASCII characters")
        if not firmware.isascii():
            raise DataError("SDS800X HD *IDN? firmware must contain ASCII characters")

        self._identity_response = response
        self._model = model
        return response, model

    def idn(self) -> str:
        response, _ = self._ensure_identity()
        return response

    def channel_coupling(self, channel: int) -> str:
        if type(channel) is not int:
            raise DataError("SDS800X HD channel must be an integer")
        if channel < 1:
            raise DataError("SDS800X HD channel must be >= 1")

        _, model = self._ensure_identity()
        channel_count = _MODEL_CHANNEL_COUNTS[model]
        if channel > channel_count:
            raise DataError(f"{model} channel must be between 1 and {channel_count}")

        response = self.transport.query(f":CHANnel{channel}:COUPling?").strip().upper()
        if response not in _SUPPORTED_COUPLINGS:
            raise DataError(
                "SDS800X HD channel coupling must be one of AC, DC, or GND"
            )
        return response

    def close(self) -> None:
        if self._closed:
            return
        self.transport.close()
        self._closed = True
