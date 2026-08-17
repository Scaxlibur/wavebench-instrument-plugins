from __future__ import annotations

from dataclasses import dataclass, field

from wavebench.errors import DataError
from wavebench.instruments.models import WaveformData
from wavebench.transport.base import InstrumentTransport

from .waveform import (
    build_analog_waveform,
    parse_waveform_preamble,
    waveform_header_from_preamble,
)


_MODEL_CHANNEL_COUNTS = {
    "SDS802X HD": 2,
    "SDS804X HD": 4,
    "SDS812X HD": 2,
    "SDS814X HD": 4,
    "SDS822X HD": 2,
    "SDS824X HD": 4,
}
_SUPPORTED_COUPLINGS = {"AC", "DC", "GND"}
_SUPPORTED_POINTS = {"DEF", "MAX", "DMAX"}
_TRIGGER_STATES = {"ARM", "READY", "AUTO", "TRIG'D", "STOP", "ROLL"}


@dataclass(frozen=True)
class _WaveformTransferState:
    source: str
    start: int
    interval: int
    points: int
    width: str
    byte_order: str


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

    def _validate_channel(self, channel: int) -> None:
        if type(channel) is not int:
            raise DataError("SDS800X HD channel must be an integer")
        if channel < 1:
            raise DataError("SDS800X HD channel must be >= 1")
        if channel > 4:
            raise DataError("SDS800X HD channel must be between 1 and 4")

        _, model = self._ensure_identity()
        channel_count = _MODEL_CHANNEL_COUNTS[model]
        if channel > channel_count:
            raise DataError(f"{model} channel must be between 1 and {channel_count}")

    def channel_coupling(self, channel: int) -> str:
        self._validate_channel(channel)

        response = self.transport.query(f":CHANnel{channel}:COUPling?").strip().upper()
        if response not in _SUPPORTED_COUPLINGS:
            raise DataError(
                "SDS800X HD channel coupling must be one of AC, DC, or GND"
            )
        return response

    def _query_text(self, command: str, *, field_name: str) -> str:
        response = self.transport.query(command)
        if not isinstance(response, str):
            raise DataError(f"SDS800X HD {field_name} response must be text")
        normalized = response.strip().upper()
        if not normalized:
            raise DataError(f"SDS800X HD {field_name} response must not be empty")
        return normalized

    def _query_integer(
        self,
        command: str,
        *,
        field_name: str,
        minimum: int,
    ) -> int:
        response = self._query_text(command, field_name=field_name)
        if not response.isascii() or not response.isdigit():
            raise DataError(f"SDS800X HD {field_name} response must be an integer")
        value = int(response)
        if value < minimum:
            raise DataError(f"SDS800X HD {field_name} must be >= {minimum}")
        return value

    def _read_waveform_transfer_state(self) -> _WaveformTransferState:
        source = self._query_text(":WAVeform:SOURce?", field_name="waveform source")
        if (
            len(source) < 2
            or source[0] not in {"C", "F", "D"}
            or not source[1:].isascii()
            or not source[1:].isdigit()
        ):
            raise DataError("SDS800X HD waveform source must be Cn, Fn, or Dn")

        start = self._query_integer(
            ":WAVeform:START?",
            field_name="waveform start",
            minimum=0,
        )
        interval = self._query_integer(
            ":WAVeform:INTerval?",
            field_name="waveform interval",
            minimum=1,
        )
        points = self._query_integer(
            ":WAVeform:POINt?",
            field_name="waveform point count",
            minimum=0,
        )
        width = self._query_text(":WAVeform:WIDTH?", field_name="waveform width")
        if width not in {"BYTE", "WORD"}:
            raise DataError("SDS800X HD waveform width must be BYTE or WORD")
        byte_order = self._query_text(
            ":WAVeform:BYTeorder?",
            field_name="waveform byte order",
        )
        if byte_order not in {"LSB", "MSB"}:
            raise DataError("SDS800X HD waveform byte order must be LSB or MSB")
        return _WaveformTransferState(
            source=source,
            start=start,
            interval=interval,
            points=points,
            width=width,
            byte_order=byte_order,
        )

    def _configure_waveform_transfer(self, *, channel: int) -> None:
        self.transport.write(f":WAVeform:SOURce C{channel}")
        self.transport.write(":WAVeform:WIDTH WORD")
        self.transport.write(":WAVeform:BYTeorder LSB")
        self.transport.write(":WAVeform:START 0")
        self.transport.write(":WAVeform:INTerval 1")
        self.transport.write(":WAVeform:POINt 0")

    def _restore_waveform_transfer_state(self, state: _WaveformTransferState) -> None:
        commands = (
            ":WAVeform:START 0",
            ":WAVeform:POINt 0",
            f":WAVeform:SOURce {state.source}",
            f":WAVeform:WIDTH {state.width}",
            f":WAVeform:BYTeorder {state.byte_order}",
            f":WAVeform:POINt {state.points}",
            f":WAVeform:INTerval {state.interval}",
            f":WAVeform:START {state.start}",
        )
        failures: list[tuple[str, Exception]] = []
        for command in commands:
            try:
                self.transport.write(command)
            except Exception as exc:
                failures.append((command, exc))
        if failures:
            first_command, first_error = failures[0]
            first_error.add_note(
                f"SDS800X HD waveform transfer restore failed at {first_command!r}"
            )
            for command, error in failures[1:]:
                first_error.add_note(
                    "additional SDS800X HD waveform transfer restore failure at "
                    f"{command!r}: {error}"
                )
            raise first_error

    def _read_waveform_chunks(self, *, points: int, max_points: int) -> bytes:
        chunks: list[bytes] = []
        for start in range(0, points, max_points):
            chunk_points = min(max_points, points - start)
            self.transport.write(f":WAVeform:POINt {chunk_points}")
            self.transport.write(f":WAVeform:START {start}")
            chunk = self.transport.query_bin_block(":WAVeform:DATA?")
            expected_bytes = chunk_points * 2
            if len(chunk) != expected_bytes:
                raise DataError(
                    "SDS800X HD waveform chunk length mismatch at start "
                    f"{start}: expected {expected_bytes}, got {len(chunk)}"
                )
            chunks.append(chunk)
        return b"".join(chunks)

    def fetch_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
    ) -> WaveformData:
        if not isinstance(points, str):
            raise DataError("SDS800X HD waveform points must be DEF, MAX, or DMAX")
        normalized_points = points.strip().upper()
        if normalized_points not in _SUPPORTED_POINTS:
            raise DataError("SDS800X HD waveform points must be DEF, MAX, or DMAX")
        if normalized_points != "DMAX":
            raise DataError("SDS800X HD waveform reads currently support only DMAX points")
        if type(check_errors) is not bool:
            raise DataError("SDS800X HD check_errors must be a boolean")
        if check_errors:
            raise DataError(
                "SDS800X HD waveform reads require check_errors=False because CN11G "
                "documents no error-queue query"
            )
        self._validate_channel(channel)

        trigger_state = self._query_text(
            ":TRIGger:STATus?",
            field_name="trigger status",
        )
        if trigger_state not in _TRIGGER_STATES:
            raise DataError("SDS800X HD returned an unsupported trigger status")
        if trigger_state != "STOP":
            raise DataError("SDS800X HD waveform reads require acquisition state Stop")

        sequence_state = self._query_text(
            ":ACQuire:SEQuence?",
            field_name="sequence acquisition state",
        )
        if sequence_state not in {"ON", "OFF"}:
            raise DataError("SDS800X HD sequence acquisition state must be ON or OFF")
        if sequence_state != "OFF":
            raise DataError("SDS800X HD waveform reads do not support sequence acquisition")

        state = self._read_waveform_transfer_state()
        primary_error: BaseException | None = None
        try:
            self._configure_waveform_transfer(channel=channel)
            preamble = parse_waveform_preamble(
                self.transport.query_bin_block(":WAVeform:PREamble?")
            )
            if preamble.comm_type != 1 or preamble.sample_byte_order != "little":
                raise DataError("SDS800X HD waveform transfer did not apply WORD and LSB")
            if preamble.source_channel != channel:
                raise DataError(
                    "SDS800X HD waveform preamble source does not match the requested channel"
                )
            waveform_header_from_preamble(preamble)
            expected_bytes = preamble.points * preamble.sample_width_bytes
            if preamble.data_bytes != expected_bytes:
                raise DataError(
                    "SDS800X HD waveform preamble data length does not match the full record"
                )

            max_points = self._query_integer(
                ":WAVeform:MAXPoint?",
                field_name="waveform maximum chunk points",
                minimum=1,
            )
            payload = self._read_waveform_chunks(
                points=preamble.points,
                max_points=max_points,
            )
            return build_analog_waveform(
                channel=channel,
                preamble=preamble,
                payload=payload,
            )
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            try:
                self._restore_waveform_transfer_state(state)
            except Exception as restore_error:
                if primary_error is None:
                    raise
                primary_error.add_note(
                    "SDS800X HD waveform transfer state restoration also failed: "
                    f"{restore_error}"
                )

    def close(self) -> None:
        if self._closed:
            return
        self.transport.close()
        self._closed = True
