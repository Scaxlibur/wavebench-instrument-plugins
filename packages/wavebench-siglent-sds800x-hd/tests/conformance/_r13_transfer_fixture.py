from __future__ import annotations

from collections import deque
from typing import Any

import numpy as np

from wavebench.errors import DataError
from wavebench.instruments.api import InstrumentDescriptor
from wavebench.instruments.scope_extensions import (
    ScopeAxisMetadata,
    ScopeDescriptorExtensions,
    ScopeTraceData,
    ScopeTraceMetadata,
    ScopeTraceProfile,
    ScopeTraceRef,
    ScopeTraceTransferBaseline,
    ScopeTraceTransferRestoreResult,
    ScopeTraceTransferStateSnapshot,
)
from wavebench.services.scope_extension_service import ExperimentalScopeExtensionService
from wavebench.transport.binary import parse_definite_block_response
from wavebench.transport.contracts import (
    BinaryQueryResult,
    BinaryResponseFraming,
    ReplayPolicy,
)
from wavebench.transport.guarded import GuardedAuditedTransport


TRACE_FIELDS = (
    "scope.run_state",
    "scope.waveform_source",
    "scope.waveform_mode",
    "scope.query_response_header",
    "scope.waveform_format",
    "scope.waveform_byte_order",
    "scope.waveform_points",
    "scope.waveform_transfer_window",
)

INITIAL_TRACE_STATE = {
    "scope.run_state": "STOP",
    "scope.waveform_source": "F1",
    "scope.waveform_mode": "SEQUENCE_OFF",
    "scope.query_response_header": "RAW_MESSAGE",
    "scope.waveform_format": "BYTE",
    "scope.waveform_byte_order": "MSB",
    "scope.waveform_points": "17",
    "scope.waveform_transfer_window": "5:3",
}


def ieee_block(payload: bytes) -> bytes:
    length = str(len(payload)).encode("ascii")
    return b"#" + str(len(length)).encode("ascii") + length + payload


class SDSR13TraceBackend:
    """Stateful fake backend; it is not a claim about a production backend."""

    resource = "TCPIP::redacted::INSTR"

    def __init__(self) -> None:
        first = np.asarray([-2, -1], dtype="<i2").tobytes()
        second = np.asarray([1, 2], dtype="<i2").tobytes()
        self.trace_state = dict(INITIAL_TRACE_STATE)
        self.binary_wires: deque[bytes] = deque((ieee_block(first), ieee_block(second)))
        self.queries: list[str] = []
        self.writes: list[str] = []
        self.binary_queries: list[str] = []
        self.closed = 0

    def record_event(self, direction: str, text: str) -> None:
        pass

    def query(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> str:
        self.queries.append(command)
        responses = {
            "*IDN?": "SIGLENT TECHNOLOGIES,SDS804X HD,REDACTED,4.8.12.1.1.6.5",
            ":TRIGger:STATus?": self.trace_state["scope.run_state"],
            ":WAVeform:SOURce?": self.trace_state["scope.waveform_source"],
            ":ACQuire:SEQuence?": self.trace_state["scope.waveform_mode"].removeprefix(
                "SEQUENCE_"
            ),
            ":WAVeform:WIDTH?": self.trace_state["scope.waveform_format"],
            ":WAVeform:BYTeorder?": self.trace_state["scope.waveform_byte_order"],
            ":WAVeform:POINt?": self.trace_state["scope.waveform_points"],
            ":WAVeform:START?": self.trace_state[
                "scope.waveform_transfer_window"
            ].split(":", maxsplit=1)[0],
            ":WAVeform:INTerval?": self.trace_state[
                "scope.waveform_transfer_window"
            ].split(":", maxsplit=1)[1],
        }
        try:
            return responses[command]
        except KeyError as exc:
            raise AssertionError(f"unexpected fake query: {command}") from exc

    def query_float_list(
        self,
        command: str,
        *,
        timeout_ms: int | None = None,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> list[float]:
        raise AssertionError(f"unexpected float-list query: {command}")

    def query_bin_block(
        self,
        command: str,
        *,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> bytes:
        raise AssertionError(f"legacy binary entry must not be used: {command}")

    def query_binary(
        self,
        command: str,
        *,
        framing: BinaryResponseFraming,
        max_bytes: int,
        timeout_ms: int | None = None,
        replay: ReplayPolicy = ReplayPolicy.NO_REPLAY,
    ) -> BinaryQueryResult:
        if framing is not BinaryResponseFraming.DEFINITE_BLOCK:
            raise AssertionError("SDS waveform fixture requires definite-block framing")
        self.binary_queries.append(command)
        if command != ":WAVeform:DATA?":
            raise AssertionError(f"unexpected binary query: {command}")
        try:
            wire = self.binary_wires.popleft()
        except IndexError as exc:
            raise AssertionError("waveform fixture exhausted its binary blocks") from exc
        return parse_definite_block_response(wire, max_bytes=max_bytes)

    def query_opc(self, *, replay: ReplayPolicy = ReplayPolicy.NO_REPLAY) -> str:
        raise AssertionError("SDS acquisition completion must not use *OPC?")

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command == ":TRIGger:STOP":
            self.trace_state["scope.run_state"] = "STOP"
        elif command == ":TRIGger:RUN":
            self.trace_state["scope.run_state"] = "RUN"
        elif command.startswith(":WAVeform:SOURce "):
            self.trace_state["scope.waveform_source"] = command.rsplit(" ", maxsplit=1)[1]
        elif command.startswith(":ACQuire:SEQuence "):
            value = command.rsplit(" ", maxsplit=1)[1]
            self.trace_state["scope.waveform_mode"] = f"SEQUENCE_{value}"
        elif command.startswith(":WAVeform:WIDTH "):
            self.trace_state["scope.waveform_format"] = command.rsplit(" ", maxsplit=1)[1]
        elif command.startswith(":WAVeform:BYTeorder "):
            self.trace_state["scope.waveform_byte_order"] = command.rsplit(
                " ", maxsplit=1
            )[1]
        elif command.startswith(":WAVeform:POINt "):
            self.trace_state["scope.waveform_points"] = command.rsplit(" ", maxsplit=1)[1]
        elif command.startswith(":WAVeform:START "):
            _, interval = self.trace_state["scope.waveform_transfer_window"].split(":")
            start = command.rsplit(" ", maxsplit=1)[1]
            self.trace_state["scope.waveform_transfer_window"] = f"{start}:{interval}"
        elif command.startswith(":WAVeform:INTerval "):
            start, _ = self.trace_state["scope.waveform_transfer_window"].split(":")
            interval = command.rsplit(" ", maxsplit=1)[1]
            self.trace_state["scope.waveform_transfer_window"] = f"{start}:{interval}"
        else:
            raise AssertionError(f"unexpected fake write: {command}")

    def write_bytes(self, command: bytes) -> None:
        raise AssertionError("binary writes are outside the SDS fixture")

    def close(self) -> None:
        self.closed += 1


class SDSR13TraceDriver:
    """Test-only adapter from documented SDS state to R1.3 typed contracts."""

    def __init__(self, transport: GuardedAuditedTransport) -> None:
        self.transport = transport
        self.fail_after_binary = False
        self.restore_skip_field: str | None = None
        self.verify_mismatch_field: str | None = None
        self.restore_calls = 0
        self.trace_profile = ScopeTraceProfile(
            fetchable_kinds=("analog",),
            max_points=8_388_608,
            restore_order=TRACE_FIELDS,
            snapshot_max_steps=12,
            restore_max_steps=12,
            verify_max_steps=12,
            source_index_max=4,
        )

    @property
    def backend(self) -> SDSR13TraceBackend:
        return self.transport.inner  # type: ignore[return-value]

    def close(self) -> None:
        self.transport.close()

    def idn(self) -> str:
        return self.transport.query("*IDN?")

    def get_trace_metadata(self, source: ScopeTraceRef) -> ScopeTraceMetadata:
        if source != ScopeTraceRef("analog", index=1):
            raise DataError("SDS R1.3 fixture exposes only analog channel 1")
        return ScopeTraceMetadata(
            source=source,
            x_axis=ScopeAxisMetadata("time", "s", 0.0, 1e-9, 4),
            y_unit="v",
            y_semantics="linear",
            value_encoding="real",
            operation="identity",
            fetchable=True,
        )

    def snapshot_trace_transfer_state(
        self,
        fields: tuple[str, ...],
    ) -> ScopeTraceTransferStateSnapshot:
        if tuple(fields) != TRACE_FIELDS:
            raise DataError("SDS transfer fixture requires the complete R1.3 field set")
        return self._fresh_trace_snapshot(fields)

    def fetch_trace(
        self,
        source: ScopeTraceRef,
        *,
        points: str | int = "dmax",
        baseline: ScopeTraceTransferBaseline | None,
    ) -> ScopeTraceData:
        if baseline is None:
            raise DataError("SDS trace transfer requires a core-owned baseline")
        if points != 4:
            raise DataError("SDS R1.3 fixture uses an explicit four-point vector")

        self.transport.write(":WAVeform:SOURce C1")
        self.transport.write(":WAVeform:WIDTH WORD")
        self.transport.write(":WAVeform:BYTeorder LSB")
        self.transport.write(":WAVeform:INTerval 1")

        payloads: list[bytes] = []
        for start in (0, 2):
            self.transport.write(f":WAVeform:START {start}")
            self.transport.write(":WAVeform:POINt 2")
            result = self.transport.query_binary(
                ":WAVeform:DATA?",
                framing=BinaryResponseFraming.DEFINITE_BLOCK,
                max_bytes=8_388_608,
            )
            payloads.append(result.data)

        if self.fail_after_binary:
            raise DataError("injected SDS post-transfer decode failure")
        codes = np.frombuffer(b"".join(payloads), dtype="<i2")
        values = codes.astype(np.float64) * 1e-3
        return ScopeTraceData(self.get_trace_metadata(source), values)

    def restore_trace_transfer_state(
        self,
        baseline: ScopeTraceTransferBaseline,
    ) -> ScopeTraceTransferRestoreResult:
        self.restore_calls += 1
        attempted: list[str] = []
        restored: list[str] = []
        for field_name in baseline.restore_order:
            attempted.append(field_name)
            if field_name == self.restore_skip_field:
                continue
            self._restore_trace_field(field_name, baseline.snapshot)
            restored.append(field_name)
        status = "completed" if len(restored) == len(attempted) else "failed"
        return ScopeTraceTransferRestoreResult(
            status=status,
            attempted_fields=tuple(attempted),
            restored_fields=tuple(restored),
            error_code=None if status == "completed" else "fixture_restore_failed",
        )

    def verify_trace_transfer_state_restored(
        self,
        baseline: ScopeTraceTransferBaseline,
    ) -> ScopeTraceTransferStateSnapshot:
        if self.verify_mismatch_field is not None:
            self.backend.trace_state[self.verify_mismatch_field] = "EXTERNAL_CHANGE"
        return self._fresh_trace_snapshot(tuple(baseline.restore_order))

    def _fresh_trace_snapshot(
        self,
        fields: tuple[str, ...],
    ) -> ScopeTraceTransferStateSnapshot:
        state: dict[str, str] = {}
        state["scope.run_state"] = self.transport.query(":TRIGger:STATus?").upper()
        state["scope.waveform_source"] = self.transport.query(":WAVeform:SOURce?").upper()
        sequence = self.transport.query(":ACQuire:SEQuence?").upper()
        state["scope.waveform_mode"] = f"SEQUENCE_{sequence}"
        # SDS raw responses have no configurable CHDR-equivalent in CN11G.
        state["scope.query_response_header"] = self.backend.trace_state[
            "scope.query_response_header"
        ]
        state["scope.waveform_format"] = self.transport.query(":WAVeform:WIDTH?").upper()
        state["scope.waveform_byte_order"] = self.transport.query(
            ":WAVeform:BYTeorder?"
        ).upper()
        state["scope.waveform_points"] = self.transport.query(":WAVeform:POINt?")
        start = self.transport.query(":WAVeform:START?")
        interval = self.transport.query(":WAVeform:INTerval?")
        state["scope.waveform_transfer_window"] = f"{start}:{interval}"
        selected = {field_name: state[field_name] for field_name in fields}
        return ScopeTraceTransferStateSnapshot(
            captured_fields=fields,
            run_state_token=selected.get("scope.run_state"),
            waveform_source_token=selected.get("scope.waveform_source"),
            waveform_mode_token=selected.get("scope.waveform_mode"),
            query_response_header_token=selected.get("scope.query_response_header"),
            waveform_format_token=selected.get("scope.waveform_format"),
            waveform_byte_order_token=selected.get("scope.waveform_byte_order"),
            waveform_points_token=selected.get("scope.waveform_points"),
            waveform_transfer_window_token=selected.get("scope.waveform_transfer_window"),
        )

    def _restore_trace_field(
        self,
        field_name: str,
        snapshot: ScopeTraceTransferStateSnapshot,
    ) -> None:
        values: dict[str, Any] = {
            "scope.run_state": snapshot.run_state_token,
            "scope.waveform_source": snapshot.waveform_source_token,
            "scope.waveform_mode": snapshot.waveform_mode_token,
            "scope.query_response_header": snapshot.query_response_header_token,
            "scope.waveform_format": snapshot.waveform_format_token,
            "scope.waveform_byte_order": snapshot.waveform_byte_order_token,
            "scope.waveform_points": snapshot.waveform_points_token,
            "scope.waveform_transfer_window": snapshot.waveform_transfer_window_token,
        }
        value = values[field_name]
        if not isinstance(value, str):
            raise DataError(f"missing SDS transfer baseline token for {field_name}")
        if field_name == "scope.run_state":
            command = ":TRIGger:STOP" if value == "STOP" else ":TRIGger:RUN"
            self.transport.write(command)
        elif field_name == "scope.waveform_source":
            self.transport.write(f":WAVeform:SOURce {value}")
        elif field_name == "scope.waveform_mode":
            self.transport.write(f":ACQuire:SEQuence {value.removeprefix('SEQUENCE_')}")
        elif field_name == "scope.query_response_header":
            if value != "RAW_MESSAGE":
                raise DataError("SDS CN11G exposes no mutable query-header setting")
        elif field_name == "scope.waveform_format":
            self.transport.write(f":WAVeform:WIDTH {value}")
        elif field_name == "scope.waveform_byte_order":
            self.transport.write(f":WAVeform:BYTeorder {value}")
        elif field_name == "scope.waveform_points":
            self.transport.write(f":WAVeform:POINt {value}")
        elif field_name == "scope.waveform_transfer_window":
            start, interval = value.split(":", maxsplit=1)
            self.transport.write(f":WAVeform:INTerval {interval}")
            self.transport.write(f":WAVeform:START {start}")
        else:
            raise DataError(f"unsupported SDS transfer field: {field_name}")


def make_trace_service() -> tuple[
    ExperimentalScopeExtensionService,
    SDSR13TraceDriver,
    GuardedAuditedTransport,
    SDSR13TraceBackend,
]:
    backend = SDSR13TraceBackend()
    transport = GuardedAuditedTransport(backend)  # type: ignore[arg-type]
    driver = SDSR13TraceDriver(transport)
    descriptor = InstrumentDescriptor(
        driver_id="siglent.sds800x-hd.r13-fixture",
        kind="scope",
        display_name="SIGLENT SDS800X HD R1.3 fixture",
        manufacturer="SIGLENT",
        models=("SDS804X HD",),
        aliases=(),
        capabilities=("scope.idn", "scope.trace_metadata", "scope.fetch_trace"),
        idn_patterns=("SIGLENT TECHNOLOGIES,SDS804X HD",),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io",),
        factory=lambda context: driver,
        scope_extensions=ScopeDescriptorExtensions(trace_profile=driver.trace_profile),
    )
    service = ExperimentalScopeExtensionService(
        driver=driver,
        descriptor=descriptor,
        session_state=transport.session_state,
        connection_timeout_ms=1_000,
        enabled=True,
    )
    return service, driver, transport, backend
