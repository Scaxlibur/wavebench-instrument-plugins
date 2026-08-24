from __future__ import annotations

from collections import deque
import zlib

from wavebench.errors import DataError
from wavebench.instruments import (
    InstrumentDescriptor,
    ScopeAcquisitionCompletion,
    ScopeAcquisitionControlBaseline,
    ScopeAcquisitionControlProfile,
    ScopeAcquisitionControlSnapshot,
    ScopeAcquisitionRunState,
    ScopeBaselineRestoreResult,
    ScopeDescriptorExtensions,
    ScopeScreenshot,
    ScopeScreenshotBaseline,
    ScopeScreenshotProfile,
    ScopeScreenshotRequest,
    ScopeScreenshotRestoreResult,
    ScopeScreenshotStateSnapshot,
    ScopeScreenshotVariant,
)
from wavebench.services import ScopeExtensionService
from wavebench.transport import (
    BinaryQueryResult,
    BinaryResponseFraming,
    ReplayPolicy,
)
from wavebench.transport.guarded import GuardedAuditedTransport


SCREENSHOT_REQUEST = ScopeScreenshotRequest(menu_mode="device", color_mode="color")


def png(width: int = 2, height: int = 3) -> bytes:
    def chunk(kind: bytes, payload: bytes) -> bytes:
        crc = zlib.crc32(kind + payload) & 0xFFFFFFFF
        return len(payload).to_bytes(4, "big") + kind + payload + crc.to_bytes(4, "big")

    ihdr = width.to_bytes(4, "big") + height.to_bytes(4, "big") + b"\x08\x02\x00\x00\x00"
    rows = b"".join(b"\x00" + b"\x00" * (width * 3) for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", ihdr)
        + chunk(b"IDAT", zlib.compress(rows))
        + chunk(b"IEND", b"")
    )


class SDSR13ControlBackend:
    resource = "TCPIP::redacted::INSTR"

    def __init__(self) -> None:
        self.trigger_status = "Stop"
        self.trigger_mode = "NORMAL"
        self.acquisition_mode = "YT"
        self.acquisition_count = 0
        self.status_after_run: deque[str] = deque()
        self.status_sequence_on_run: tuple[str, ...] = ("Arm", "Stop")
        self.status_sequence_on_stop: tuple[str, ...] = ("Stop",)
        self.screenshot_payload = png() + b"\x0a"
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
        if command == "*IDN?":
            return "SIGLENT TECHNOLOGIES,SDS804X HD,SDS8FAKE000001,4.8.12.1.1.6.5"
        if command == ":TRIGger:STATus?":
            if self.status_after_run:
                self.trigger_status = self.status_after_run.popleft()
                if self.trigger_status == "Stop":
                    self.acquisition_count += 1
            return self.trigger_status
        if command == ":TRIGger:MODE?":
            return self.trigger_mode
        if command == ":ACQuire:MODE?":
            return self.acquisition_mode
        if command == ":ACQuire:NUMACq?":
            return str(self.acquisition_count)
        raise AssertionError(f"unexpected fake query: {command}")

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
        self.binary_queries.append(command)
        if command != ":PRINt? PNG,NORMal":
            raise AssertionError(f"unexpected binary query: {command}")
        if framing is not BinaryResponseFraming.MESSAGE:
            raise AssertionError("SDS screenshot fixture requires MESSAGE framing")
        if len(self.screenshot_payload) > max_bytes:
            raise AssertionError("fixture payload exceeds the core-provided limit")
        return BinaryQueryResult(
            data=self.screenshot_payload,
            framing=framing,
            declared_length=None,
            framing_header_bytes=0,
            consumed_bytes=len(self.screenshot_payload),
        )

    def query_opc(self, *, replay: ReplayPolicy = ReplayPolicy.NO_REPLAY) -> str:
        raise AssertionError("SDS acquisition completion must not use *OPC?")

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command == ":TRIGger:STOP":
            self.trigger_status = "Stop"
            self.status_after_run = deque(self.status_sequence_on_stop)
        elif command == ":TRIGger:RUN":
            self.trigger_status = "Arm"
            self.status_after_run = deque(self.status_sequence_on_run)
        elif command.startswith(":TRIGger:MODE "):
            self.trigger_mode = command.rsplit(" ", maxsplit=1)[1].upper()
        elif command.startswith(":ACQuire:MODE "):
            self.acquisition_mode = command.rsplit(" ", maxsplit=1)[1].upper()
        else:
            raise AssertionError(f"unexpected fake write: {command}")

    def write_bytes(self, command: bytes) -> None:
        raise AssertionError("binary writes are outside the SDS fixture")

    def close(self) -> None:
        self.closed += 1


class SDSR13ControlDriver:
    """Test-only SDS adapter for the public R1.3 screenshot/acquisition contracts."""

    def __init__(self, transport: GuardedAuditedTransport) -> None:
        self.transport = transport
        self.screenshot_recovery_calls = 0
        self.acquisition_restore_calls = 0
        self.single_proof = "state_transition"
        self.screenshot_profile = ScopeScreenshotProfile(
            variants=(
                ScopeScreenshotVariant(
                    request=SCREENSHOT_REQUEST,
                    media_type="image/png",
                    framing=BinaryResponseFraming.MESSAGE,
                    response_max_bytes=262_144,
                    operation_max_bytes=262_144,
                    resynchronization_max_bytes=0,
                    changed_fields=(),
                    restore_order=(),
                    snapshot_max_steps=0,
                    restore_max_steps=0,
                    verify_max_steps=0,
                    content_trailing_hex="0a",
                    width_px=(2, 2),
                    height_px=(3, 3),
                ),
            ),
            source="descriptor",
        )
        self.acquisition_profile = ScopeAcquisitionControlProfile(
            supported_continuous_modes=("auto", "normal"),
            single_arm_semantics="configure_then_arm",
            arm_resets_acquisition_count=False,
            failure_restore_order=("scope.trigger", "scope.acquisition"),
            snapshot_max_steps=3,
            restore_max_steps=3,
            verify_max_steps=3,
            identity_semantics="unknown",
        )

    @property
    def backend(self) -> SDSR13ControlBackend:
        return self.transport.inner  # type: ignore[return-value]

    def close(self) -> None:
        self.transport.close()

    def idn(self) -> str:
        return self.transport.query("*IDN?")

    def get_screenshot_profile(self) -> ScopeScreenshotProfile:
        return self.screenshot_profile

    def snapshot_screenshot_state(
        self,
        fields: tuple[str, ...],
    ) -> ScopeScreenshotStateSnapshot:
        self.screenshot_recovery_calls += 1
        return ScopeScreenshotStateSnapshot(captured_fields=fields)

    def capture_screenshot(
        self,
        request: ScopeScreenshotRequest,
        *,
        baseline: ScopeScreenshotBaseline | None,
    ) -> ScopeScreenshot:
        if request != SCREENSHOT_REQUEST or baseline is not None:
            raise DataError("SDS screenshot fixture accepts one stateless request")
        result = self.transport.query_binary(
            ":PRINt? PNG,NORMal",
            framing=BinaryResponseFraming.MESSAGE,
            max_bytes=262_144,
        )
        if not result.data.endswith(b"\x0a"):
            raise DataError("SDS screenshot content trailing differs from profile")
        canonical = result.data[:-1]
        return ScopeScreenshot(
            data=canonical,
            media_type="image/png",
            width_px=2,
            height_px=3,
            requested=request,
            effective=request,
            framing=result.framing,
        )

    def restore_screenshot_state(
        self,
        baseline: ScopeScreenshotBaseline,
    ) -> ScopeScreenshotRestoreResult:
        self.screenshot_recovery_calls += 1
        return ScopeScreenshotRestoreResult("not_attempted", (), ())

    def verify_screenshot_state_restored(
        self,
        fields: tuple[str, ...],
        baseline: ScopeScreenshotBaseline,
    ) -> ScopeScreenshotStateSnapshot:
        self.screenshot_recovery_calls += 1
        return ScopeScreenshotStateSnapshot(captured_fields=fields)

    def get_acquisition_run_state(self) -> ScopeAcquisitionRunState:
        raw = self.transport.query(":TRIGger:STATus?")
        return self._run_state(raw)

    def snapshot_acquisition_control(self) -> ScopeAcquisitionControlSnapshot:
        run_state = self.get_acquisition_run_state()
        trigger = self.transport.query(":TRIGger:MODE?").upper()
        acquisition = self.transport.query(":ACQuire:MODE?").upper()
        return ScopeAcquisitionControlSnapshot(run_state, trigger, acquisition)

    def start_continuous(
        self,
        *,
        trigger_mode: str,
        baseline: ScopeAcquisitionControlBaseline,
    ) -> ScopeAcquisitionRunState:
        self.transport.write(f":TRIGger:MODE {trigger_mode.upper()}")
        self.transport.write(":TRIGger:RUN")
        return self.get_acquisition_run_state()

    def stop_acquisition(self) -> ScopeAcquisitionRunState:
        self.transport.write(":TRIGger:STOP")
        return self.get_acquisition_run_state()

    def acquire_single(
        self,
        *,
        baseline: ScopeAcquisitionControlBaseline,
        deadline: float,
    ) -> ScopeAcquisitionCompletion:
        self.transport.write(":TRIGger:MODE SINGLE")
        if self.transport.query(":TRIGger:MODE?").upper() != "SINGLE":
            raise DataError("SDS trigger mode query-back did not enter SINGLE")
        proof_baseline = ScopeAcquisitionRunState(
            "ready",
            "single",
            "READY",
            acquisition_count=self.backend.acquisition_count,
        )
        self.transport.write(":TRIGger:RUN")
        armed = self.get_acquisition_run_state()
        completed = self.get_acquisition_run_state()
        if completed.phase != "stopped":
            raise DataError("SDS SINGLE did not reach Stop")

        if self.single_proof == "count_without_epoch":
            proof = "count_delta_with_epoch"
            baseline_count = proof_baseline.acquisition_count
            completed_count = completed.acquisition_count
            baseline_identity = None
            completed_identity = None
            observed = (armed, completed)
        elif self.single_proof == "identity_without_semantics":
            proof = "identity_delta"
            proof_baseline = ScopeAcquisitionRunState(
                "ready",
                "single",
                "READY",
                acquisition_identity="old",
            )
            completed = ScopeAcquisitionRunState(
                "stopped",
                "single",
                "Stop",
                acquisition_identity="new",
            )
            baseline_count = None
            completed_count = None
            baseline_identity = "old"
            completed_identity = "new"
            observed = (armed, completed)
        else:
            proof = "state_transition"
            baseline_count = None
            completed_count = None
            baseline_identity = None
            completed_identity = None
            observed = (completed,) if self.single_proof == "no_transition" else (armed, completed)
        return ScopeAcquisitionCompletion(
            state=completed,
            original_state=baseline.snapshot.run_state,
            proof_baseline_state=proof_baseline,
            proof_baseline_stage="configured_pre_arm",
            proof=proof,
            baseline_count=baseline_count,
            completed_count=completed_count,
            baseline_identity=baseline_identity,
            completed_identity=completed_identity,
            observed_states=observed,
        )

    def restore_acquisition_control(
        self,
        baseline: ScopeAcquisitionControlBaseline,
    ) -> ScopeBaselineRestoreResult:
        self.acquisition_restore_calls += 1
        for field_name in baseline.restore_order:
            if field_name == "scope.run_state":
                self.transport.write(":TRIGger:STOP")
            elif field_name == "scope.trigger":
                self.transport.write(
                    f":TRIGger:MODE {baseline.snapshot.trigger_state_token}"
                )
            elif field_name == "scope.acquisition":
                self.transport.write(
                    f":ACQuire:MODE {baseline.snapshot.acquisition_state_token}"
                )
        return ScopeBaselineRestoreResult(
            "completed",
            baseline.restore_order,
            baseline.restore_order,
        )

    def verify_acquisition_control_restored(
        self,
        baseline: ScopeAcquisitionControlBaseline,
    ) -> ScopeAcquisitionControlSnapshot:
        return self.snapshot_acquisition_control()

    def _run_state(self, raw: str) -> ScopeAcquisitionRunState:
        phase = {
            "STOP": "stopped",
            "ARM": "arming",
            "READY": "ready",
        }.get(raw.upper(), "unknown")
        trigger_mode = self.backend.trigger_mode.lower()
        if trigger_mode not in {"auto", "normal", "single", "roll"}:
            trigger_mode = "unknown"
        return ScopeAcquisitionRunState(
            phase=phase,
            trigger_mode=trigger_mode,
            raw_state=raw,
            acquisition_count=self.backend.acquisition_count,
        )


def make_control_service() -> tuple[
    ScopeExtensionService,
    SDSR13ControlDriver,
    GuardedAuditedTransport,
    SDSR13ControlBackend,
]:
    backend = SDSR13ControlBackend()
    transport = GuardedAuditedTransport(backend)  # type: ignore[arg-type]
    driver = SDSR13ControlDriver(transport)
    descriptor = InstrumentDescriptor(
        driver_id="siglent.sds800x-hd.r13-control-fixture",
        kind="scope",
        display_name="SIGLENT SDS800X HD R1.3 control fixture",
        manufacturer="SIGLENT",
        models=("SDS804X HD",),
        aliases=(),
        capabilities=(
            "scope.idn",
            "scope.screenshot_profile",
            "scope.screenshot_v2",
            "scope.acquisition_run_state",
            "scope.acquisition_control",
        ),
        idn_patterns=("SIGLENT TECHNOLOGIES,SDS804X HD",),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io",),
        factory=lambda context: driver,
        wavebench_min_version="0.8.23",
        scope_extensions=ScopeDescriptorExtensions(
            screenshot_profile=driver.screenshot_profile,
            acquisition_control_profile=driver.acquisition_profile,
        ),
    )
    service = ScopeExtensionService(
        driver=driver,
        descriptor=descriptor,
        session_state=transport.session_state,
        connection_timeout_ms=1_000,
    )
    return service, driver, transport, backend
