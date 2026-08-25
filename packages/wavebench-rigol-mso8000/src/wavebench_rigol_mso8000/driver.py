from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from hashlib import sha256
import math
from threading import RLock
import time

import numpy as np

from wavebench.errors import ConfigError, DataError, InstrumentError, OperationTimeout
from wavebench.instruments.models import (
    ScopeChannelInputStateV2,
    ScopeCursorReadout,
    ScopeCursorReadoutV2,
    ScopeCursorQuantity,
    ScopeDigitalChannelStatusV2,
    ScopeDigitalPodStatusV2,
    ScopeDigitalSharedStatusV2,
    ScopeDerivedWaveformMetadata,
    ScopeFftStatusV2,
    ScopeIdentitySnapshot,
    ScopeMeasurementStatisticsRequestV2,
    ScopeMeasurementStatisticsV2,
    ScopeSnapshotFieldV2,
    ScopeSnapshotV2,
    SCOPE_SNAPSHOT_V2_FIELD_ORDER,
    WaveformData,
    WaveformHeader,
)
from wavebench.instruments.scope_extensions import (
    ScopeAcquisitionCompletion,
    ScopeAcquisitionControlBaseline,
    ScopeAcquisitionControlSnapshot,
    ScopeAcquisitionRunState,
    ScopeAcquisitionStatusFieldV2,
    ScopeAcquisitionStatusV2,
    ScopeAverageStatusV2,
    ScopeBaselineRestoreResult,
    DriverErrorRecord,
    ErrorDrainResult,
    ScopeWaveformTransferBaseline,
    ScopeWaveformTransferField,
    ScopeWaveformTransferRestoreResult,
    ScopeWaveformTransferStateSnapshot,
)
from wavebench.transport.base import InstrumentTransport
from wavebench.transport.contracts import BinaryResponseFraming, ReplayPolicy

from .parsers import (
    MSO8104_ACQUISITION_STATUS_V2_READABLE_FIELDS,
    MSO8104_MEASUREMENT_STATISTICS_ANALOG_MATH_SOURCES,
    MSO8104_MEASUREMENT_STATISTICS_DIGITAL_SOURCE_ITEMS,
    MSO8104_MEASUREMENT_STATISTICS_DIGITAL_SOURCES,
    MSO8104_MEASUREMENT_STATISTICS_ITEMS,
    MSO8104_MEASUREMENT_STATISTICS_TWO_SOURCE_ITEMS,
    MSO8104_SNAPSHOT_V2_READABLE_FIELDS,
    MSO8104_SYSTEM_OPTION_TYPES,
    parse_channel_input_state_v2,
    parse_acquisition_type,
    parse_average_acquisition_count,
    normalize_channel_input,
    parse_boolean_state,
    parse_cursor_mode,
    parse_cursor_source,
    parse_cursor_time_unit,
    parse_cursor_vertical_unit,
    parse_digital_display_size,
    parse_digital_label,
    parse_digital_pod_threshold,
    parse_digital_timing_calibration,
    parse_display_state,
    parse_fft_source,
    parse_fft_vertical_unit,
    parse_fft_window,
    parse_finite_float,
    parse_manual_cursor_type,
    parse_math_operator,
    parse_mso8104_error_queue_record,
    parse_mso8104_identity,
    parse_nonnegative_statistic_count,
    parse_positive_finite_float,
    parse_positive_integer,
    parse_positive_scientific_integer,
    parse_rigol_waveform_preamble,
    parse_timebase_mode,
    parse_trigger_sweep,
    parse_trigger_status,
    parse_waveform_format,
    parse_waveform_mode,
    parse_waveform_source,
    parse_logic_analyzer_module_present,
)


_ANALOG_CHANNELS = frozenset({1, 2, 3, 4})
_DIGITAL_CHANNELS = frozenset(range(16))
_NORMAL_WAVEFORM_POINTS = 1000
_MAX_WAVEFORM_STATE_POINTS = 500_000_000
_HARD_MAX_TOTAL_WAVEFORM_POINTS = 4_000_000
_HARD_MAX_BYTE_POINTS_PER_READ = 250_000
_BOUNDED_FETCH_MAX_BINARY_QUERIES = 16
_POINT_MODE_TO_TRANSFER = {
    "DEF": ("NORM", 0),
    "MAX": ("MAX", 1),
    "DMAX": ("RAW", 2),
}
_WAVEFORM_BINARY_FETCH_RESTORE_ORDER: tuple[ScopeWaveformTransferField, ...] = (
    "scope.waveform_source",
    "scope.waveform_mode",
    "scope.waveform_format",
    "scope.waveform_points",
    "scope.waveform_transfer_window",
)
_WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER: tuple[ScopeWaveformTransferField, ...] = (
    "scope.acquisition",
    "scope.trigger",
    "scope.timebase",
    "scope.channel_display",
    "scope.channel_vertical",
    "scope.waveform_source",
    "scope.waveform_mode",
    "scope.query_response_header",
    "scope.waveform_format",
    "scope.waveform_byte_order",
    "scope.waveform_points",
    "scope.waveform_transfer_window",
    "scope.run_state",
)
_WAVEFORM_CAPTURE_RESPONSE_HEADER_TOKEN = "definite-block-lf"
_WAVEFORM_CAPTURE_BYTE_ORDER_TOKEN = "not-applicable-byte"
_CAPTURE_RECOVERY_OPC_MAX_QUERIES = 8
_CURSOR_TIME_UNITS = {
    "SEC": ("s", "Hz"),
    "HZ": ("Hz", "s"),
    "DEGR": ("degree", None),
    "PERC": ("percent", None),
}
_CURSOR_VERTICAL_UNITS = {
    "SOUR": "source",
    "PERC": "percent",
}
_FFT_STATUS_V2_UNAVAILABLE_FIELDS = (
    "average_complete",
    "resolution_bandwidth_hz",
    "sample_rate_hz",
)
_ACQUISITION_STATUS_V2_FIELDS: tuple[ScopeAcquisitionStatusFieldV2, ...] = (
    "acquisition_type",
    "sample_rate_hz",
    "memory_depth",
    "average",
    "average.configured_count",
)
_ACQUISITION_STATUS_V2_STATIC_UNAVAILABLE_FIELDS: tuple[
    ScopeAcquisitionStatusFieldV2, ...
] = ("run_state", "segmented")
_ACQUISITION_STATUS_V2_AVERAGE_UNAVAILABLE_FIELDS: tuple[
    ScopeAcquisitionStatusFieldV2, ...
] = ("run_state", "average.complete", "segmented")
_ACQUISITION_CONTROL_RESTORE_ORDER = (
    "scope.run_state",
    "scope.trigger",
    "scope.acquisition",
)
_ACQUISITION_CONTROL_FAILURE_RESTORE_ORDER = (
    "scope.trigger",
    "scope.acquisition",
)
_TRIGGER_SWEEP_TO_CORE_MODE = {
    "AUTO": "auto",
    "NORM": "normal",
    "SING": "single",
}
_TRIGGER_SWEEP_TO_COMMAND = {
    "AUTO": ":TRIGger:SWEep AUTO",
    "NORM": ":TRIGger:SWEep NORMal",
    "SING": ":TRIGger:SWEep SINGle",
}
_ACQUISITION_TYPE_TO_COMMAND = {
    "NORM": ":ACQuire:TYPE NORMal",
    "PEAK": ":ACQuire:TYPE PEAK",
    "AVER": ":ACQuire:TYPE AVERages",
    "HRES": ":ACQuire:TYPE HRESolution",
}
_ERROR_QUEUE_COMMAND = ":SYSTem:ERRor?"
_ERROR_QUEUE_TERMINATOR = (0, "No error")
_TRIGGER_STATUS_TO_PHASE = {
    "STOP": "stopped",
    "WAIT": "waiting",
    "RUN": "acquiring",
    "AUTO": "acquiring",
}
_DIGITAL_STATUS_V2_LA_UNAVAILABLE_FIELDS = (
    "position_div",
    "label_enabled",
    "activity",
    "technology",
    "hysteresis",
)
_DIGITAL_STATUS_V2_NO_LA_UNAVAILABLE_FIELDS = (
    "displayed",
    "position_div",
    "label",
    "label_enabled",
    "activity",
    "technology",
    "hysteresis",
    "pod",
    "shared.timing_calibration_s",
    "shared.size",
)
_SNAPSHOT_V2_FIELDS: tuple[ScopeSnapshotFieldV2, ...] = (
    "identity.manufacturer",
    "identity.model",
    "identity.serial_number",
    "identity.firmware",
    "identity.options",
)
_SNAPSHOT_V2_UNAVAILABLE_FIELDS: tuple[ScopeSnapshotFieldV2, ...] = tuple(
    field_name for field_name in SCOPE_SNAPSHOT_V2_FIELD_ORDER if field_name not in _SNAPSHOT_V2_FIELDS
)


@dataclass(frozen=True)
class WaveformTransferState:
    source: str
    mode: str
    data_format: str
    points: int
    start: int
    stop: int


@dataclass(frozen=True)
class CaptureRecoveryState:
    run_state: str
    acquisition_type: str
    trigger_sweep: str
    timebase_scale_s_per_div: float
    timebase_offset_s: float
    channel_display: tuple[bool, bool, bool, bool]
    channel_vertical: tuple[tuple[float, float], tuple[float, float], tuple[float, float], tuple[float, float]]
    waveform: WaveformTransferState


@dataclass
class MSO8104Scope:
    transport: InstrumentTransport
    acquisition_timeout_s: float = 30.0
    trigger_poll_interval_s: float = 0.25
    capture_recovery_settle_s: float = 0.5
    max_total_waveform_points: int = _HARD_MAX_TOTAL_WAVEFORM_POINTS
    max_byte_points_per_read: int = _HARD_MAX_BYTE_POINTS_PER_READ
    _clock: Callable[[], float] = field(default=time.monotonic, repr=False)
    _sleep: Callable[[float], None] = field(default=time.sleep, repr=False)
    _io_lock: RLock = field(default_factory=RLock, init=False, repr=False)
    _closed: bool = field(default=False, init=False, repr=False)
    _waveform_writes_blocked: bool = field(default=False, init=False, repr=False)
    _acquisition_writes_blocked: bool = field(default=False, init=False, repr=False)
    _autoscale_writes_blocked: bool = field(default=False, init=False, repr=False)
    _capture_recovery_states: dict[str, CaptureRecoveryState] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if not math.isfinite(self.acquisition_timeout_s) or self.acquisition_timeout_s <= 0:
            raise DataError("MSO8104 acquisition timeout must be a finite positive number")
        if (
            not math.isfinite(self.trigger_poll_interval_s)
            or self.trigger_poll_interval_s < 0
        ):
            raise DataError("MSO8104 trigger poll interval must be finite and non-negative")
        if (
            not math.isfinite(self.capture_recovery_settle_s)
            or self.capture_recovery_settle_s < 0
        ):
            raise DataError(
                "MSO8104 capture recovery settle interval must be finite and non-negative"
            )
        if (
            type(self.max_total_waveform_points) is not int
            or not 1
            <= self.max_total_waveform_points
            <= _HARD_MAX_TOTAL_WAVEFORM_POINTS
        ):
            raise DataError(
                "MSO8104 max_total_waveform_points must be an integer from 1 through 4000000"
            )
        if (
            type(self.max_byte_points_per_read) is not int
            or not 1
            <= self.max_byte_points_per_read
            <= _HARD_MAX_BYTE_POINTS_PER_READ
        ):
            raise DataError(
                "MSO8104 max_byte_points_per_read must be an integer from 1 through 250000"
            )

    def _require_open(self) -> None:
        if self._closed:
            raise InstrumentError("MSO8104 driver is closed")

    def idn(self) -> str:
        with self._io_lock:
            self._require_open()
            response = self.transport.query("*IDN?").strip()
            parse_mso8104_identity(response)
            return response

    def drain_errors(self, *, max_records: int) -> ErrorDrainResult:
        if type(max_records) is not int or not 1 <= max_records <= 256:
            raise DataError("MSO8104 error drain max_records must be an integer from 1 through 256")
        with self._io_lock:
            self._require_open()
            records: list[DriverErrorRecord] = []
            for query_count in range(1, max_records + 2):
                code, message = parse_mso8104_error_queue_record(
                    self.transport.query(_ERROR_QUEUE_COMMAND, replay=ReplayPolicy.NO_REPLAY)
                )
                if (code, message) == _ERROR_QUEUE_TERMINATOR:
                    return ErrorDrainResult(
                        records=tuple(records),
                        terminated=True,
                        query_count=query_count,
                    )
                record = DriverErrorRecord(
                    code=code,
                    message=message,
                    severity="error",
                    source="mso8104",
                )
                if len(records) == max_records:
                    return ErrorDrainResult(
                        records=tuple(records),
                        terminated=False,
                        query_count=query_count,
                        overflow_record=record,
                    )
                records.append(record)
        raise AssertionError("MSO8104 error drain exhausted without an overflow record")

    @staticmethod
    def _validate_analog_channel(channel: int) -> None:
        if type(channel) is not int or channel not in _ANALOG_CHANNELS:
            raise DataError("MSO8104 analog channel must be an integer from 1 through 4")

    @staticmethod
    def _validate_digital_channel(channel: int) -> None:
        if type(channel) is not int or channel not in _DIGITAL_CHANNELS:
            raise DataError("MSO8104 digital channel must be an integer from 0 through 15")

    @staticmethod
    def _digital_pod(channel: int) -> tuple[int, int, int]:
        if channel <= 7:
            return 1, 0, 7
        return 2, 8, 15

    @staticmethod
    def _validate_math_index(math_index: int) -> None:
        if type(math_index) is not int or math_index not in {1, 2, 3, 4}:
            raise DataError("MSO8104 math waveform index must be an integer from 1 through 4")

    def channel_coupling(self, channel: int) -> str:
        self._validate_analog_channel(channel)
        with self._io_lock:
            self._require_open()
            coupling = self.transport.query(f":CHANnel{channel}:COUPling?")
            impedance = self.transport.query(f":CHANnel{channel}:IMPedance?")
            return normalize_channel_input(coupling=coupling, impedance=impedance)

    def get_channel_input_state_v2(self, channel: int) -> ScopeChannelInputStateV2:
        self._validate_analog_channel(channel)
        with self._io_lock:
            self._require_open()
            coupling = self.transport.query(f":CHANnel{channel}:COUPling?")
            impedance = self.transport.query(f":CHANnel{channel}:IMPedance?")
            return parse_channel_input_state_v2(
                channel=channel,
                coupling=coupling,
                impedance=impedance,
            )

    def get_digital_status_v2(self, channel: int) -> ScopeDigitalChannelStatusV2:
        self._validate_digital_channel(channel)
        with self._io_lock:
            self._require_open()
            logic_analyzer_present = parse_logic_analyzer_module_present(
                self.transport.query(":SYSTem:MODules?")
            )
            if not logic_analyzer_present:
                return ScopeDigitalChannelStatusV2(
                    channel=channel,
                    shared=ScopeDigitalSharedStatusV2(module_present=False),
                    unavailable_fields=_DIGITAL_STATUS_V2_NO_LA_UNAVAILABLE_FIELDS,
                )
            pod_number, pod_start, pod_stop = self._digital_pod(channel)
            displayed = parse_display_state(
                self.transport.query(f":LA:DIGital:DISPlay? D{channel}")
            )
            label = parse_digital_label(
                self.transport.query(f":LA:DIGital:LABel? D{channel}")
            )
            threshold_v = parse_digital_pod_threshold(
                self.transport.query(f":LA:POD{pod_number}:THReshold?")
            )
            timing_calibration_s = parse_digital_timing_calibration(
                self.transport.query(":LA:TCALibrate?")
            )
            size = parse_digital_display_size(self.transport.query(":LA:SIZE?"))
            return ScopeDigitalChannelStatusV2(
                channel=channel,
                displayed=displayed,
                label=label,
                pod=ScopeDigitalPodStatusV2(
                    start_channel=pod_start,
                    stop_channel=pod_stop,
                    threshold_v=threshold_v,
                    threshold_scope="pod",
                ),
                shared=ScopeDigitalSharedStatusV2(
                    module_present=True,
                    timing_calibration_s=timing_calibration_s,
                    size=size,
                ),
                unavailable_fields=_DIGITAL_STATUS_V2_LA_UNAVAILABLE_FIELDS,
            )

    def get_snapshot_v2(
        self,
        channel: int,
        *,
        fields: tuple[ScopeSnapshotFieldV2, ...],
    ) -> ScopeSnapshotV2:
        self._validate_analog_channel(channel)
        if fields != MSO8104_SNAPSHOT_V2_READABLE_FIELDS:
            raise ConfigError(
                "MSO8104 snapshot V2 supports only its descriptor's exact readable field profile"
            )
        with self._io_lock:
            self._require_open()
            identity = parse_mso8104_identity(self.transport.query("*IDN?"))
            options = tuple(
                option
                for option in MSO8104_SYSTEM_OPTION_TYPES
                if parse_boolean_state(
                    self.transport.query(f":SYSTem:OPTion:STATus? {option}"),
                    field=f"system option {option} status",
                )
            )
            return ScopeSnapshotV2(
                identity=ScopeIdentitySnapshot(
                    manufacturer=identity.manufacturer,
                    model=identity.model,
                    serial_number=identity.serial_number,
                    firmware=identity.firmware,
                    options=options,
                ),
                unavailable_fields=_SNAPSHOT_V2_UNAVAILABLE_FIELDS,
            )

    def autoscale(self, wait_opc: bool = True, check_errors: bool = True) -> None:
        if type(wait_opc) is not bool:
            raise DataError("MSO8104 wait_opc must be a boolean")
        self._validate_check_errors(check_errors)
        with self._io_lock:
            self._require_open()
            self._require_autoscale_writes_allowed()
            enabled = parse_boolean_state(
                self.transport.query(":SYSTem:AUToscale?"),
                field="system autoscale enable",
            )
            if not enabled:
                raise ConfigError(
                    "MSO8104 system autoscale is disabled; refusing an ineffective "
                    ":AUToscale write"
                )
            try:
                self.transport.write(":AUToscale")
            except Exception as exc:
                self._autoscale_writes_blocked = True
                raise InstrumentError(
                    "MSO8104 autoscale write outcome is uncertain; autoscale writes are blocked"
                ) from exc
            if not wait_opc:
                return
            try:
                response = self.transport.query_opc().strip()
                if response != "1":
                    raise DataError(
                        f"invalid MSO8104 *OPC? response after autoscale: {response!r}"
                    )
            except Exception as exc:
                self._autoscale_writes_blocked = True
                raise InstrumentError(
                    "MSO8104 autoscale completion is uncertain; autoscale writes are blocked"
                ) from exc

    @property
    def waveform_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._waveform_writes_blocked

    @property
    def acquisition_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._acquisition_writes_blocked

    @property
    def autoscale_writes_blocked(self) -> bool:
        with self._io_lock:
            return self._autoscale_writes_blocked

    def _require_waveform_writes_allowed(self) -> None:
        if self._waveform_writes_blocked:
            raise InstrumentError(
                "MSO8104 waveform transfer writes are blocked after an ambiguous transaction; "
                "close and reopen the instrument session before retrying"
            )

    def _require_acquisition_writes_allowed(self) -> None:
        if self._acquisition_writes_blocked:
            raise InstrumentError(
                "MSO8104 acquisition writes are blocked after an uncertain acquisition "
                "transaction; "
                "close and reopen the instrument session before retrying"
            )

    def _require_autoscale_writes_allowed(self) -> None:
        if self._autoscale_writes_blocked:
            raise InstrumentError(
                "MSO8104 autoscale writes are blocked after an ambiguous operation; "
                "close and reopen the instrument session before retrying"
            )

    @staticmethod
    def _run_state_from_trigger_status(
        status: str,
        *,
        trigger_mode: str,
    ) -> ScopeAcquisitionRunState:
        phase = _TRIGGER_STATUS_TO_PHASE.get(status, "unknown")
        if status == "AUTO" and trigger_mode == "single":
            phase = "unknown"
        return ScopeAcquisitionRunState(
            phase=phase,
            trigger_mode=trigger_mode,
            raw_state=status,
        )

    @staticmethod
    def _trigger_sweep_command(token: str) -> str:
        try:
            return _TRIGGER_SWEEP_TO_COMMAND[token]
        except KeyError as exc:
            raise DataError(
                "MSO8104 acquisition baseline has an unsupported trigger sweep token"
            ) from exc

    @staticmethod
    def _acquisition_type_command(token: str) -> str:
        try:
            return _ACQUISITION_TYPE_TO_COMMAND[token]
        except KeyError as exc:
            raise DataError(
                "MSO8104 acquisition baseline has an unsupported acquisition type token"
            ) from exc

    @staticmethod
    def _validate_acquisition_control_baseline(
        baseline: ScopeAcquisitionControlBaseline,
    ) -> None:
        if not isinstance(baseline, ScopeAcquisitionControlBaseline):
            raise DataError("MSO8104 acquisition control baseline has an invalid type")
        if baseline.restore_order != _ACQUISITION_CONTROL_RESTORE_ORDER:
            raise DataError(
                "MSO8104 acquisition control baseline does not match the descriptor profile"
            )
        MSO8104Scope._trigger_sweep_command(baseline.snapshot.trigger_state_token)
        MSO8104Scope._acquisition_type_command(baseline.snapshot.acquisition_state_token)

    def _snapshot_acquisition_control_state(self) -> ScopeAcquisitionControlSnapshot:
        status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
        trigger_sweep = parse_trigger_sweep(self.transport.query(":TRIGger:SWEep?"))
        acquisition_type = parse_acquisition_type(self.transport.query(":ACQuire:TYPE?"))
        return ScopeAcquisitionControlSnapshot(
            run_state=self._run_state_from_trigger_status(
                status,
                trigger_mode=_TRIGGER_SWEEP_TO_CORE_MODE[trigger_sweep],
            ),
            trigger_state_token=trigger_sweep,
            acquisition_state_token=acquisition_type,
        )

    def get_acquisition_run_state(self) -> ScopeAcquisitionRunState:
        with self._io_lock:
            self._require_open()
            status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
            return self._run_state_from_trigger_status(status, trigger_mode="unknown")

    def snapshot_acquisition_control(self) -> ScopeAcquisitionControlSnapshot:
        with self._io_lock:
            self._require_open()
            return self._snapshot_acquisition_control_state()

    def restore_acquisition_control(
        self,
        baseline: ScopeAcquisitionControlBaseline,
    ) -> ScopeBaselineRestoreResult:
        self._validate_acquisition_control_baseline(baseline)
        commands = (
            ("scope.run_state", ":STOP"),
            (
                "scope.trigger",
                self._trigger_sweep_command(baseline.snapshot.trigger_state_token),
            ),
            (
                "scope.acquisition",
                self._acquisition_type_command(baseline.snapshot.acquisition_state_token),
            ),
        )
        with self._io_lock:
            self._require_open()
            attempted: list[str] = []
            restored: list[str] = []
            for field_name, command in commands:
                attempted.append(field_name)
                try:
                    self.transport.write(command)
                except Exception:
                    self._acquisition_writes_blocked = True
                    return ScopeBaselineRestoreResult(
                        status="failed",
                        attempted_fields=tuple(attempted),
                        restored_fields=tuple(restored),
                        error_code="restore_write_failed",
                    )
                restored.append(field_name)
            return ScopeBaselineRestoreResult(
                status="completed",
                attempted_fields=tuple(attempted),
                restored_fields=tuple(restored),
            )

    def verify_acquisition_control_restored(
        self,
        baseline: ScopeAcquisitionControlBaseline,
    ) -> ScopeAcquisitionControlSnapshot:
        self._validate_acquisition_control_baseline(baseline)
        with self._io_lock:
            self._require_open()
            return self._snapshot_acquisition_control_state()

    def start_continuous(
        self,
        *,
        trigger_mode: str,
        baseline: ScopeAcquisitionControlBaseline,
    ) -> ScopeAcquisitionRunState:
        if trigger_mode != "normal":
            raise ConfigError("MSO8104 acquisition control supports only normal trigger mode")
        self._validate_acquisition_control_baseline(baseline)
        with self._io_lock:
            self._require_open()
            self._require_acquisition_writes_allowed()
            try:
                self.transport.write(_TRIGGER_SWEEP_TO_COMMAND["NORM"])
                actual_sweep = parse_trigger_sweep(
                    self.transport.query(":TRIGger:SWEep?")
                )
                if actual_sweep != "NORM":
                    raise DataError(
                        "MSO8104 normal acquisition trigger sweep readback did not match"
                    )
                self.transport.write(":RUN")
                status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
                state = self._run_state_from_trigger_status(
                    status,
                    trigger_mode="normal",
                )
                if state.phase not in {"ready", "arming", "waiting", "acquiring"}:
                    raise DataError(
                        "MSO8104 normal acquisition postcondition is not proven by trigger "
                        f"status {status!r}"
                    )
                return state
            except Exception as exc:
                self._acquisition_writes_blocked = True
                raise InstrumentError(
                    "MSO8104 normal acquisition outcome is uncertain; acquisition writes are "
                    "blocked"
                ) from exc

    def stop_acquisition(self) -> ScopeAcquisitionRunState:
        with self._io_lock:
            self._require_open()
            status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
            state = self._run_state_from_trigger_status(status, trigger_mode="unknown")
            if state.phase == "stopped":
                return state
            if state.phase == "unknown":
                raise ConfigError(
                    "MSO8104 acquisition stop requires a directly mappable trigger status, "
                    f"got {status!r}"
                )
            try:
                self.transport.write(":STOP")
                stopped_status = parse_trigger_status(
                    self.transport.query(":TRIGger:STATus?")
                )
                stopped = self._run_state_from_trigger_status(
                    stopped_status,
                    trigger_mode="unknown",
                )
                if stopped.phase != "stopped":
                    raise DataError(
                        "MSO8104 acquisition stop postcondition is not proven by trigger "
                        f"status {stopped_status!r}"
                    )
                return stopped
            except Exception as exc:
                self._acquisition_writes_blocked = True
                raise InstrumentError(
                    "MSO8104 acquisition stop outcome is uncertain; acquisition writes are "
                    "blocked"
                ) from exc

    def acquire_single(
        self,
        *,
        baseline: ScopeAcquisitionControlBaseline,
        deadline: float,
    ) -> ScopeAcquisitionCompletion:
        self._validate_acquisition_control_baseline(baseline)
        if not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
            raise DataError("MSO8104 single-acquisition deadline must be finite")
        with self._io_lock:
            self._require_open()
            self._require_acquisition_writes_allowed()
            if deadline <= self._clock():
                raise OperationTimeout("MSO8104 single-acquisition deadline expired before arming")
            try:
                proof, observed_states, post_arm_trigger_mode = (
                    self._arm_single_and_wait_for_completion(deadline)
                )
                return ScopeAcquisitionCompletion(
                    state=observed_states[-1],
                    original_state=baseline.snapshot.run_state,
                    proof_baseline_state=baseline.snapshot.run_state,
                    proof_baseline_stage="original_atomic_arm",
                    proof=proof,
                    observed_states=observed_states,
                    post_arm_trigger_mode=post_arm_trigger_mode,
                )
            except (DataError, OperationTimeout):
                self._acquisition_writes_blocked = True
                raise
            except Exception as exc:
                self._acquisition_writes_blocked = True
                raise InstrumentError(
                    "MSO8104 single-acquisition outcome is uncertain; acquisition writes are "
                    "blocked"
                ) from exc

    def _arm_single_and_wait_for_completion(
        self,
        deadline: float,
    ) -> tuple[str, tuple[ScopeAcquisitionRunState, ...], str | None]:
        self.transport.write(":SINGle")
        if deadline <= self._clock():
            raise OperationTimeout(
                "MSO8104 single-acquisition deadline expired before mode readback"
            )
        trigger_sweep = parse_trigger_sweep(self.transport.query(":TRIGger:SWEep?"))
        if trigger_sweep != "SING":
            raise DataError(
                "MSO8104 single-acquisition mode readback did not confirm SINGLE"
            )
        if deadline <= self._clock():
            raise OperationTimeout(
                "MSO8104 single-acquisition deadline expired before initial status"
            )
        initial_status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
        initial_state = self._single_completion_state(initial_status)
        if initial_state.phase == "stopped":
            return (
                "single_mode_readback_then_stopped",
                (initial_state,),
                "single",
            )
        if initial_status not in {"TD", "WAIT"}:
            raise DataError(
                "MSO8104 single acquisition completion is unproven for unexpected trigger "
                f"status {initial_status!r} after SINGLE mode readback"
            )
        observed_states = [initial_state]
        while True:
            remaining_s = deadline - self._clock()
            if remaining_s <= 0:
                raise OperationTimeout(
                    "MSO8104 single acquisition did not reach STOP before the operation deadline"
                )
            self._sleep(min(self.trigger_poll_interval_s, remaining_s))
            if deadline <= self._clock():
                raise OperationTimeout(
                    "MSO8104 single acquisition did not reach STOP before the operation deadline"
                )
            status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
            state = self._single_completion_state(status)
            if status not in {"TD", "WAIT", "STOP"}:
                raise DataError(
                    "MSO8104 single acquisition completion is unproven for unexpected trigger "
                    f"status {status!r} after SINGLE mode readback"
                )
            observed_states.append(state)
            if state.phase == "stopped":
                return "state_transition", tuple(observed_states), None

    @staticmethod
    def _single_completion_state(status: str) -> ScopeAcquisitionRunState:
        if status == "TD":
            # The manual lists TD but does not define its subphase.  Only under a
            # just-read-back SINGLE mode may it serve as a raw, nonterminal
            # transition observation; it never proves completion by itself.
            return ScopeAcquisitionRunState("arming", "single", status)
        return MSO8104Scope._run_state_from_trigger_status(status, trigger_mode="single")

    def _arm_single_and_wait_for_transition(
        self,
        deadline: float,
    ) -> tuple[ScopeAcquisitionRunState, ...]:
        self.transport.write(":SINGle")
        remaining_s = deadline - self._clock()
        if remaining_s <= 0:
            raise OperationTimeout(
                "MSO8104 single-acquisition deadline expired before initial status"
            )
        self._sleep(min(self.trigger_poll_interval_s, remaining_s))
        if deadline <= self._clock():
            raise OperationTimeout(
                "MSO8104 single-acquisition deadline expired before initial status"
            )
        observed_states: list[ScopeAcquisitionRunState] = []
        while True:
            if deadline <= self._clock():
                raise OperationTimeout(
                    "MSO8104 single acquisition did not reach STOP before the operation deadline"
                )
            status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
            state = self._run_state_from_trigger_status(status, trigger_mode="single")
            observed_states.append(state)
            if state.phase == "stopped":
                if not any(
                    item.phase in {"arming", "waiting", "acquiring"}
                    for item in observed_states[:-1]
                ):
                    raise DataError(
                        "MSO8104 single acquisition completion is unproven: no "
                        "post-arm transition was observed before STOP"
                    )
                return tuple(observed_states)
            if state.phase == "unknown":
                raise DataError(
                    "MSO8104 single acquisition completion is unproven for trigger "
                    f"status {status!r}"
                )
            remaining_s = deadline - self._clock()
            if remaining_s <= 0:
                raise OperationTimeout(
                    "MSO8104 single acquisition did not reach STOP before the operation deadline"
                )
            self._sleep(min(self.trigger_poll_interval_s, remaining_s))

    def _require_main_timebase(self) -> None:
        mode = parse_timebase_mode(self.transport.query(":TIMebase:MODE?"))
        if mode != "MAIN":
            raise ConfigError(
                f"MSO8104 waveform operations require MAIN timebase mode, got {mode}"
            )

    def _snapshot_waveform_state(self) -> WaveformTransferState:
        source = parse_waveform_source(self.transport.query(":WAVeform:SOURce?"))
        mode = parse_waveform_mode(self.transport.query(":WAVeform:MODE?"))
        data_format = parse_waveform_format(self.transport.query(":WAVeform:FORMat?"))
        points = parse_positive_integer(
            self.transport.query(":WAVeform:POINts?"),
            field="waveform points",
            maximum=_MAX_WAVEFORM_STATE_POINTS,
        )
        start = parse_positive_integer(
            self.transport.query(":WAVeform:STARt?"),
            field="waveform start",
            maximum=_MAX_WAVEFORM_STATE_POINTS,
        )
        stop = parse_positive_integer(
            self.transport.query(":WAVeform:STOP?"),
            field="waveform stop",
            maximum=_MAX_WAVEFORM_STATE_POINTS,
        )
        if start > stop:
            raise DataError(
                f"invalid MSO8104 waveform range in state snapshot: start {start} > stop {stop}"
            )
        return WaveformTransferState(
            source=source,
            mode=mode,
            data_format=data_format,
            points=points,
            start=start,
            stop=stop,
        )

    @staticmethod
    def _waveform_transfer_snapshot(
        state: WaveformTransferState,
    ) -> ScopeWaveformTransferStateSnapshot:
        return ScopeWaveformTransferStateSnapshot(
            captured_fields=_WAVEFORM_BINARY_FETCH_RESTORE_ORDER,
            waveform_source_token=state.source,
            waveform_mode_token=state.mode,
            waveform_format_token=state.data_format,
            waveform_points_token=str(state.points),
            waveform_transfer_window_token=f"{state.start}:{state.stop}",
        )

    @staticmethod
    def _capture_recovery_field_tokens(
        state: CaptureRecoveryState,
    ) -> dict[ScopeWaveformTransferField, str]:
        def float_token(value: float) -> str:
            return value.hex().replace("+", "")

        def token(label: str, *pieces: str) -> str:
            return sha256("|".join((label, *pieces)).encode("ascii")).hexdigest()

        return {
            "scope.run_state": token("run_state", state.run_state),
            "scope.acquisition": token("acquisition", state.acquisition_type),
            "scope.trigger": token("trigger", state.trigger_sweep),
            "scope.timebase": token(
                "timebase",
                float_token(state.timebase_scale_s_per_div),
                float_token(state.timebase_offset_s),
            ),
            "scope.channel_display": token(
                "channel_display",
                *("1" if displayed else "0" for displayed in state.channel_display),
            ),
            "scope.channel_vertical": token(
                "channel_vertical",
                *(
                    float_token(value)
                    for scale, offset in state.channel_vertical
                    for value in (scale, offset)
                ),
            ),
            "scope.waveform_source": token("waveform_source", state.waveform.source),
            "scope.waveform_mode": token("waveform_mode", state.waveform.mode),
            "scope.query_response_header": token(
                "query_response_header",
                _WAVEFORM_CAPTURE_RESPONSE_HEADER_TOKEN,
            ),
            "scope.waveform_format": token(
                "waveform_format",
                state.waveform.data_format,
            ),
            "scope.waveform_byte_order": token(
                "waveform_byte_order",
                _WAVEFORM_CAPTURE_BYTE_ORDER_TOKEN,
            ),
            "scope.waveform_points": token(
                "waveform_points",
                str(state.waveform.points),
            ),
            "scope.waveform_transfer_window": token(
                "waveform_transfer_window",
                str(state.waveform.start),
                str(state.waveform.stop),
            ),
        }

    @staticmethod
    def _capture_recovery_state_key(
        tokens: dict[ScopeWaveformTransferField, str],
    ) -> str:
        return sha256(
            "|".join(
                f"{field_name}={tokens[field_name]}"
                for field_name in _WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER
            ).encode("ascii")
        ).hexdigest()

    def _capture_recovery_snapshot(
        self,
        state: CaptureRecoveryState,
    ) -> ScopeWaveformTransferStateSnapshot:
        tokens = self._capture_recovery_field_tokens(state)
        self._capture_recovery_states[self._capture_recovery_state_key(tokens)] = state
        return ScopeWaveformTransferStateSnapshot(
            captured_fields=_WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER,
            run_state_token=tokens["scope.run_state"],
            acquisition_token=tokens["scope.acquisition"],
            trigger_token=tokens["scope.trigger"],
            timebase_token=tokens["scope.timebase"],
            channel_display_token=tokens["scope.channel_display"],
            channel_vertical_token=tokens["scope.channel_vertical"],
            waveform_source_token=tokens["scope.waveform_source"],
            waveform_mode_token=tokens["scope.waveform_mode"],
            query_response_header_token=tokens["scope.query_response_header"],
            waveform_format_token=tokens["scope.waveform_format"],
            waveform_byte_order_token=tokens["scope.waveform_byte_order"],
            waveform_points_token=tokens["scope.waveform_points"],
            waveform_transfer_window_token=tokens["scope.waveform_transfer_window"],
        )

    def _snapshot_capture_recovery_state(self) -> CaptureRecoveryState:
        status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
        if status != "STOP":
            raise ConfigError(
                "MSO8104 bounded capture requires an already stopped baseline; "
                f"got trigger status {status!r}"
            )
        acquisition_type = parse_acquisition_type(self.transport.query(":ACQuire:TYPE?"))
        trigger_sweep = parse_trigger_sweep(self.transport.query(":TRIGger:SWEep?"))
        timebase_mode = parse_timebase_mode(self.transport.query(":TIMebase:MODE?"))
        if timebase_mode != "MAIN":
            raise ConfigError(
                "MSO8104 bounded capture requires MAIN timebase for a restorable baseline"
            )
        timebase_scale_s_per_div = parse_positive_finite_float(
            self.transport.query(":TIMebase:MAIN:SCALe?"),
            field="main timebase scale",
        )
        timebase_offset_s = parse_finite_float(
            self.transport.query(":TIMebase:MAIN:OFFSet?"),
            field="main timebase offset",
        )
        displayed = tuple(
            parse_display_state(self.transport.query(f":CHANnel{channel}:DISPlay?"))
            for channel in range(1, 5)
        )
        vertical = tuple(
            (
                parse_positive_finite_float(
                    self.transport.query(f":CHANnel{channel}:SCALe?"),
                    field=f"CH{channel} vertical scale",
                ),
                parse_finite_float(
                    self.transport.query(f":CHANnel{channel}:OFFSet?"),
                    field=f"CH{channel} vertical offset",
                ),
            )
            for channel in range(1, 5)
        )
        waveform = self._snapshot_waveform_state()
        if waveform.data_format != "BYTE":
            raise ConfigError(
                "MSO8104 bounded capture requires a BYTE waveform-transfer baseline; "
                "the programming guide does not define a queryable waveform byte-order state"
            )
        return CaptureRecoveryState(
            run_state=status,
            acquisition_type=acquisition_type,
            trigger_sweep=trigger_sweep,
            timebase_scale_s_per_div=timebase_scale_s_per_div,
            timebase_offset_s=timebase_offset_s,
            channel_display=(displayed[0], displayed[1], displayed[2], displayed[3]),
            channel_vertical=(vertical[0], vertical[1], vertical[2], vertical[3]),
            waveform=waveform,
        )

    @staticmethod
    def _validate_waveform_transfer_baseline(
        baseline: ScopeWaveformTransferBaseline,
    ) -> None:
        if not isinstance(baseline, ScopeWaveformTransferBaseline):
            raise DataError("MSO8104 bounded waveform baseline has an invalid type")
        if (
            baseline.restore_order != _WAVEFORM_BINARY_FETCH_RESTORE_ORDER
            or baseline.snapshot.captured_fields != _WAVEFORM_BINARY_FETCH_RESTORE_ORDER
        ):
            raise DataError(
                "MSO8104 bounded waveform baseline does not match the fetch transfer profile"
            )

    @staticmethod
    def _validate_capture_waveform_transfer_baseline(
        baseline: ScopeWaveformTransferBaseline,
    ) -> None:
        if not isinstance(baseline, ScopeWaveformTransferBaseline):
            raise DataError("MSO8104 bounded capture baseline has an invalid type")
        if (
            baseline.restore_order != _WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER
            or baseline.snapshot.captured_fields != _WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER
        ):
            raise DataError(
                "MSO8104 bounded capture baseline does not match the capture transfer profile"
            )

    def _capture_recovery_state_from_baseline(
        self,
        baseline: ScopeWaveformTransferBaseline,
    ) -> CaptureRecoveryState:
        self._validate_capture_waveform_transfer_baseline(baseline)
        tokens = {
            "scope.run_state": baseline.snapshot.run_state_token,
            "scope.acquisition": baseline.snapshot.acquisition_token,
            "scope.trigger": baseline.snapshot.trigger_token,
            "scope.timebase": baseline.snapshot.timebase_token,
            "scope.channel_display": baseline.snapshot.channel_display_token,
            "scope.channel_vertical": baseline.snapshot.channel_vertical_token,
            "scope.waveform_source": baseline.snapshot.waveform_source_token,
            "scope.waveform_mode": baseline.snapshot.waveform_mode_token,
            "scope.query_response_header": baseline.snapshot.query_response_header_token,
            "scope.waveform_format": baseline.snapshot.waveform_format_token,
            "scope.waveform_byte_order": baseline.snapshot.waveform_byte_order_token,
            "scope.waveform_points": baseline.snapshot.waveform_points_token,
            "scope.waveform_transfer_window": baseline.snapshot.waveform_transfer_window_token,
        }
        if any(value is None for value in tokens.values()):
            raise DataError("MSO8104 bounded capture baseline is missing state tokens")
        expected_tokens = {field_name: value for field_name, value in tokens.items() if value is not None}
        key = self._capture_recovery_state_key(expected_tokens)
        try:
            state = self._capture_recovery_states[key]
        except KeyError as exc:
            raise DataError(
                "MSO8104 bounded capture baseline state is unavailable in this session"
            ) from exc
        if self._capture_recovery_field_tokens(state) != expected_tokens:
            raise DataError("MSO8104 bounded capture baseline state token is invalid")
        return state

    @classmethod
    def _waveform_state_from_baseline(
        cls,
        baseline: ScopeWaveformTransferBaseline,
    ) -> WaveformTransferState:
        cls._validate_waveform_transfer_baseline(baseline)
        snapshot = baseline.snapshot
        try:
            source = parse_waveform_source(snapshot.waveform_source_token or "")
            mode = parse_waveform_mode(snapshot.waveform_mode_token or "")
            data_format = parse_waveform_format(snapshot.waveform_format_token or "")
            points = parse_positive_integer(
                snapshot.waveform_points_token or "",
                field="waveform points",
                maximum=_MAX_WAVEFORM_STATE_POINTS,
            )
            window = snapshot.waveform_transfer_window_token or ""
            start_text, separator, stop_text = window.partition(":")
            if not separator:
                raise DataError("MSO8104 bounded waveform baseline has an invalid window")
            start = parse_positive_integer(
                start_text,
                field="waveform start",
                maximum=_MAX_WAVEFORM_STATE_POINTS,
            )
            stop = parse_positive_integer(
                stop_text,
                field="waveform stop",
                maximum=_MAX_WAVEFORM_STATE_POINTS,
            )
        except (DataError, ValueError) as exc:
            raise DataError("MSO8104 bounded waveform baseline contains invalid state") from exc
        if start > stop:
            raise DataError(
                "MSO8104 bounded waveform baseline has a start point after its stop point"
            )
        return WaveformTransferState(
            source=source,
            mode=mode,
            data_format=data_format,
            points=points,
            start=start,
            stop=stop,
        )

    def snapshot_waveform_transfer_state(
        self,
        fields: tuple[ScopeWaveformTransferField, ...],
    ) -> ScopeWaveformTransferStateSnapshot:
        with self._io_lock:
            self._require_open()
            if fields == _WAVEFORM_BINARY_FETCH_RESTORE_ORDER:
                self._require_waveform_writes_allowed()
                return self._waveform_transfer_snapshot(self._snapshot_waveform_state())
            if fields == _WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER:
                self._require_waveform_writes_allowed()
                self._require_acquisition_writes_allowed()
                return self._capture_recovery_snapshot(
                    self._snapshot_capture_recovery_state()
                )
            raise DataError(
                "MSO8104 bounded waveform snapshot fields do not match a supported profile"
            )

    def _write_waveform_state_without_readback(self, state: WaveformTransferState) -> None:
        for command in (
            f":WAVeform:SOURce {state.source}",
            f":WAVeform:MODE {state.mode}",
            f":WAVeform:FORMat {state.data_format}",
            f":WAVeform:POINts {state.points}",
            f":WAVeform:STOP {state.stop}",
            f":WAVeform:STARt {state.start}",
        ):
            self.transport.write(command)

    @staticmethod
    def _scpi_float(value: float) -> str:
        return format(value, ".17g")

    def _restore_capture_recovery_state(
        self,
        baseline: ScopeWaveformTransferBaseline,
    ) -> ScopeWaveformTransferRestoreResult:
        state = self._capture_recovery_state_from_baseline(baseline)
        attempted: list[ScopeWaveformTransferField] = []
        restored: list[ScopeWaveformTransferField] = []

        def restore_field(
            field_name: ScopeWaveformTransferField,
            commands: tuple[str, ...],
        ) -> None:
            attempted.append(field_name)
            for command in commands:
                self.transport.write(command)
            restored.append(field_name)

        try:
            # A failed capture can still be armed or acquiring.  Force a quiet state before
            # replaying any configuration, then restore the requested run state last.
            self.transport.write(":STOP")
            restore_field(
                "scope.acquisition",
                (self._acquisition_type_command(state.acquisition_type),),
            )
            restore_field(
                "scope.trigger",
                (self._trigger_sweep_command(state.trigger_sweep),),
            )
            restore_field(
                "scope.timebase",
                (
                    ":TIMebase:MODE MAIN",
                    ":TIMebase:MAIN:SCALe "
                    + self._scpi_float(state.timebase_scale_s_per_div),
                    ":TIMebase:MAIN:OFFSet " + self._scpi_float(state.timebase_offset_s),
                ),
            )
            restore_field(
                "scope.channel_display",
                tuple(
                    f":CHANnel{channel}:DISPlay {'ON' if displayed else 'OFF'}"
                    for channel, displayed in enumerate(state.channel_display, start=1)
                ),
            )
            restore_field(
                "scope.channel_vertical",
                tuple(
                    command
                    for channel, (scale, offset) in enumerate(
                        state.channel_vertical,
                        start=1,
                    )
                    for command in (
                        f":CHANnel{channel}:SCALe {self._scpi_float(scale)}",
                        f":CHANnel{channel}:OFFSet {self._scpi_float(offset)}",
                    )
                ),
            )
            restore_field(
                "scope.waveform_source",
                (f":WAVeform:SOURce {state.waveform.source}",),
            )
            restore_field(
                "scope.waveform_mode",
                (f":WAVeform:MODE {state.waveform.mode}",),
            )
            restore_field("scope.query_response_header", ())
            restore_field(
                "scope.waveform_format",
                (f":WAVeform:FORMat {state.waveform.data_format}",),
            )
            restore_field("scope.waveform_byte_order", ())
            restore_field(
                "scope.waveform_points",
                (f":WAVeform:POINts {state.waveform.points}",),
            )
            restore_field(
                "scope.waveform_transfer_window",
                (
                    f":WAVeform:STOP {state.waveform.stop}",
                    f":WAVeform:STARt {state.waveform.start}",
                ),
            )
            restore_field(
                "scope.run_state",
                (":STOP",),
            )
        except Exception:
            self._waveform_writes_blocked = True
            self._acquisition_writes_blocked = True
            return ScopeWaveformTransferRestoreResult(
                status="failed",
                attempted_fields=tuple(attempted),
                restored_fields=tuple(restored),
                error_code="capture_restore_write_failed",
            )
        return ScopeWaveformTransferRestoreResult(
            status="completed",
            attempted_fields=tuple(attempted),
            restored_fields=tuple(restored),
        )

    def restore_waveform_transfer_state(
        self,
        baseline: ScopeWaveformTransferBaseline,
    ) -> ScopeWaveformTransferRestoreResult:
        with self._io_lock:
            self._require_open()
            if baseline.restore_order == _WAVEFORM_BINARY_FETCH_RESTORE_ORDER:
                state = self._waveform_state_from_baseline(baseline)
                try:
                    self._write_waveform_state_without_readback(state)
                except Exception:
                    self._waveform_writes_blocked = True
                    raise
                return ScopeWaveformTransferRestoreResult(
                    status="completed",
                    attempted_fields=baseline.restore_order,
                    restored_fields=baseline.restore_order,
                )
            if baseline.restore_order == _WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER:
                return self._restore_capture_recovery_state(baseline)
            raise DataError("MSO8104 bounded waveform restore baseline is unsupported")

    def verify_waveform_transfer_state_restored(
        self,
        baseline: ScopeWaveformTransferBaseline,
    ) -> ScopeWaveformTransferStateSnapshot:
        with self._io_lock:
            self._require_open()
            if baseline.restore_order == _WAVEFORM_BINARY_FETCH_RESTORE_ORDER:
                self._validate_waveform_transfer_baseline(baseline)
                return self._waveform_transfer_snapshot(self._snapshot_waveform_state())
            if baseline.restore_order == _WAVEFORM_BINARY_CAPTURE_RESTORE_ORDER:
                self._validate_capture_waveform_transfer_baseline(baseline)
                # The MSO8104 accepts the recovery write batch before its trigger
                # status query is ready on the LAN session.  Keep verification
                # mandatory, but let the instrument settle and synchronize the
                # recovery writes before issuing it.  This is transport recovery
                # only; it is not an acquisition-completion proof.
                self._sleep(self.capture_recovery_settle_s)
                for attempt in range(_CAPTURE_RECOVERY_OPC_MAX_QUERIES):
                    recovery_opc = self.transport.query("*OPC?").strip()
                    if recovery_opc == "1":
                        break
                    if recovery_opc != "0":
                        raise DataError(
                            "MSO8104 capture recovery synchronization returned an invalid "
                            f"OPC response {recovery_opc!r}"
                        )
                    if attempt + 1 != _CAPTURE_RECOVERY_OPC_MAX_QUERIES:
                        self._sleep(self.capture_recovery_settle_s)
                else:
                    raise DataError(
                        "MSO8104 capture recovery synchronization did not reach OPC=1"
                    )
                return self._capture_recovery_snapshot(
                    self._snapshot_capture_recovery_state()
                )
            raise DataError("MSO8104 bounded waveform verification baseline is unsupported")

    def _write_and_verify(
        self,
        *,
        command: str,
        query: str,
        expected: str | int,
        parser,
        phase: str,
    ) -> None:
        try:
            self.transport.write(command)
            actual = parser(self.transport.query(query))
            if actual != expected:
                raise DataError(
                    f"MSO8104 waveform {phase} readback mismatch for {query}: "
                    f"expected {expected!r}, got {actual!r}"
                )
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                f"MSO8104 waveform {phase} could not verify {command!r}; "
                "waveform transfer writes are blocked"
            ) from exc

    def _apply_waveform_state(self, state: WaveformTransferState, *, phase: str) -> None:
        source_field = (
            f":WAVeform:SOURce {state.source}",
            ":WAVeform:SOURce?",
            state.source,
            parse_waveform_source,
        )
        mode_field = (
            f":WAVeform:MODE {state.mode}",
            ":WAVeform:MODE?",
            state.mode,
            parse_waveform_mode,
        )
        prefix_fields = [source_field, mode_field]
        if phase == "setup" and state.source.startswith("MATH"):
            prefix_fields.reverse()
        fields = [
            *prefix_fields,
            (
                f":WAVeform:FORMat {state.data_format}",
                ":WAVeform:FORMat?",
                state.data_format,
                parse_waveform_format,
            ),
            (
                f":WAVeform:POINts {state.points}",
                ":WAVeform:POINts?",
                state.points,
                lambda value: parse_positive_integer(
                    value,
                    field="waveform points",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
            ),
        ]
        range_fields = [
            (
                f":WAVeform:STOP {state.stop}",
                ":WAVeform:STOP?",
                state.stop,
                lambda value: parse_positive_integer(
                    value,
                    field="waveform stop",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
            ),
            (
                f":WAVeform:STARt {state.start}",
                ":WAVeform:STARt?",
                state.start,
                lambda value: parse_positive_integer(
                    value,
                    field="waveform start",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
            ),
        ]
        if phase == "setup":
            range_fields.reverse()
        for command, query, expected, parser in (*fields, *range_fields):
            self._write_and_verify(
                command=command,
                query=query,
                expected=expected,
                parser=parser,
                phase=phase,
            )
        try:
            actual_state = self._snapshot_waveform_state()
            if actual_state != state:
                raise DataError(
                    f"MSO8104 waveform {phase} final state mismatch: "
                    f"expected {state!r}, got {actual_state!r}"
                )
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                f"MSO8104 waveform {phase} final verification failed; "
                "waveform transfer writes are blocked"
            ) from exc

    def _restore_waveform_state(self, state: WaveformTransferState) -> None:
        try:
            self._apply_waveform_state(state, phase="restore")
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                "MSO8104 waveform transfer state restoration failed: "
                f"{exc}; "
                "waveform transfer writes are blocked"
            ) from exc

    def _apply_waveform_prefix(self, *, channel: int, mode: str) -> None:
        fields = (
            (
                f":WAVeform:SOURce CHAN{channel}",
                ":WAVeform:SOURce?",
                f"CHAN{channel}",
                parse_waveform_source,
            ),
            (
                f":WAVeform:MODE {mode}",
                ":WAVeform:MODE?",
                mode,
                parse_waveform_mode,
            ),
            (
                ":WAVeform:FORMat BYTE",
                ":WAVeform:FORMat?",
                "BYTE",
                parse_waveform_format,
            ),
        )
        for command, query, expected, parser in fields:
            self._write_and_verify(
                command=command,
                query=query,
                expected=expected,
                parser=parser,
                phase="setup",
            )
        try:
            source = parse_waveform_source(self.transport.query(":WAVeform:SOURce?"))
            actual_mode = parse_waveform_mode(self.transport.query(":WAVeform:MODE?"))
            data_format = parse_waveform_format(self.transport.query(":WAVeform:FORMat?"))
            if (source, actual_mode, data_format) != (f"CHAN{channel}", mode, "BYTE"):
                raise DataError("MSO8104 waveform setup prefix drifted after readback")
        except Exception as exc:
            self._waveform_writes_blocked = True
            raise InstrumentError(
                "MSO8104 waveform setup prefix verification failed; "
                "waveform transfer writes are blocked"
            ) from exc

    @staticmethod
    def _convert_byte_chunk(
        payload: bytes,
        *,
        y_origin: float,
        y_reference: float,
        y_increment: float,
    ) -> np.ndarray:
        voltages = np.frombuffer(payload, dtype=np.uint8).astype(np.float64)
        with np.errstate(over="ignore", invalid="ignore"):
            voltages -= y_origin + y_reference
            voltages *= y_increment
        if not np.all(np.isfinite(voltages)):
            raise DataError("MSO8104 waveform voltage conversion produced non-finite values")
        return voltages

    def _read_waveform_binary_payload(
        self,
        *,
        expected_length: int,
        bounded: bool,
    ) -> bytes:
        if bounded:
            result = self.transport.query_binary(
                ":WAVeform:DATA?",
                framing=BinaryResponseFraming.DEFINITE_BLOCK,
                max_bytes=expected_length,
                replay=ReplayPolicy.NO_REPLAY,
            )
            return result.data
        return self.transport.query_bin_block(":WAVeform:DATA?")

    def _read_byte_waveform(
        self,
        channel: int,
        *,
        point_mode: str,
        remaining_points: int,
        bounded: bool = False,
    ) -> WaveformData:
        _, expected_type_code = _POINT_MODE_TO_TRANSFER[point_mode]
        maximum_points = min(remaining_points, self.max_total_waveform_points)
        preamble = parse_rigol_waveform_preamble(
            self.transport.query(":WAVeform:PREamble?"),
            expected_type_code=expected_type_code,
            maximum_points=maximum_points,
        )
        if point_mode == "DEF" and preamble.points != _NORMAL_WAVEFORM_POINTS:
            raise DataError(
                "MSO8104 NORMal waveform preamble point count does not match "
                f"the requested {_NORMAL_WAVEFORM_POINTS} points: {preamble.points}"
            )
        if point_mode == "DEF":
            payload = self._read_waveform_binary_payload(
                expected_length=preamble.points,
                bounded=bounded,
            )
            if len(payload) != preamble.points:
                raise DataError(
                    "MSO8104 waveform payload length mismatch: "
                    f"expected {preamble.points}, got {len(payload)}"
                )
            voltages = self._convert_byte_chunk(
                payload,
                y_origin=preamble.y_origin,
                y_reference=preamble.y_reference,
                y_increment=preamble.y_increment,
            )
        else:
            voltages = np.empty(preamble.points, dtype=np.float64)
            self._write_and_verify(
                command=":WAVeform:STARt 1",
                query=":WAVeform:STARt?",
                expected=1,
                parser=lambda value: parse_positive_integer(
                    value,
                    field="waveform start",
                    maximum=_MAX_WAVEFORM_STATE_POINTS,
                ),
                phase="setup",
            )
            for start in range(1, preamble.points + 1, self.max_byte_points_per_read):
                stop = min(
                    preamble.points,
                    start + self.max_byte_points_per_read - 1,
                )
                self._write_and_verify(
                    command=f":WAVeform:STOP {stop}",
                    query=":WAVeform:STOP?",
                    expected=stop,
                    parser=lambda value: parse_positive_integer(
                        value,
                        field="waveform stop",
                        maximum=_MAX_WAVEFORM_STATE_POINTS,
                    ),
                    phase="setup",
                )
                if start != 1:
                    self._write_and_verify(
                        command=f":WAVeform:STARt {start}",
                        query=":WAVeform:STARt?",
                        expected=start,
                        parser=lambda value: parse_positive_integer(
                            value,
                            field="waveform start",
                            maximum=_MAX_WAVEFORM_STATE_POINTS,
                        ),
                        phase="setup",
                    )
                expected_length = stop - start + 1
                payload = self._read_waveform_binary_payload(
                    expected_length=expected_length,
                    bounded=bounded,
                )
                if len(payload) != expected_length:
                    raise DataError(
                        "MSO8104 waveform chunk length mismatch for "
                        f"points {start}-{stop}: expected {expected_length}, got {len(payload)}"
                    )
                voltages[start - 1 : stop] = self._convert_byte_chunk(
                    payload,
                    y_origin=preamble.y_origin,
                    y_reference=preamble.y_reference,
                    y_increment=preamble.y_increment,
                )
        x_start = preamble.x_origin - preamble.x_reference * preamble.x_increment
        x_stop = x_start + (preamble.points - 1) * preamble.x_increment
        if not math.isfinite(x_start) or not math.isfinite(x_stop):
            raise DataError("MSO8104 waveform X axis is non-finite")
        voltages.setflags(write=False)
        return WaveformData(
            channel=channel,
            header=WaveformHeader(
                x_start=x_start,
                x_stop=x_stop,
                points=preamble.points,
            ),
            voltages_v=voltages,
        )

    def _read_waveform_transaction(
        self,
        channel: int,
        *,
        point_mode: str,
        remaining_points: int,
    ) -> WaveformData:
        if remaining_points < 1:
            raise DataError("MSO8104 waveform total point budget is exhausted")
        if point_mode == "DEF" and remaining_points < _NORMAL_WAVEFORM_POINTS:
            raise DataError(
                "MSO8104 waveform total point budget is below the 1000-point DEF transfer"
            )
        previous = self._snapshot_waveform_state()
        try:
            self._configure_waveform_transfer(channel=channel, point_mode=point_mode)
            return self._read_byte_waveform(
                channel,
                point_mode=point_mode,
                remaining_points=remaining_points,
            )
        finally:
            self._restore_waveform_state(previous)

    def _configure_waveform_transfer(self, *, channel: int, point_mode: str) -> None:
        mode, _ = _POINT_MODE_TO_TRANSFER[point_mode]
        if point_mode == "DEF":
            transfer = WaveformTransferState(
                source=f"CHAN{channel}",
                mode=mode,
                data_format="BYTE",
                points=_NORMAL_WAVEFORM_POINTS,
                start=1,
                stop=_NORMAL_WAVEFORM_POINTS,
            )
            self._apply_waveform_state(transfer, phase="setup")
            return
        self._apply_waveform_prefix(channel=channel, mode=mode)

    def _bounded_long_waveform_point_budget(self) -> int:
        memory_depth = parse_positive_scientific_integer(
            self.transport.query(":ACQuire:MDEPth?"),
            field="acquisition memory depth",
        )
        if memory_depth > _MAX_WAVEFORM_STATE_POINTS:
            raise DataError(
                "MSO8104 acquisition memory depth exceeds the documented 500000000 "
                f"points: {memory_depth}"
            )
        return min(
            memory_depth,
            self.max_total_waveform_points,
            _BOUNDED_FETCH_MAX_BINARY_QUERIES * self.max_byte_points_per_read,
        )

    def _require_long_fetch_stopped(self, point_mode: str) -> None:
        status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
        if status != "STOP":
            raise ConfigError(
                f"MSO8104 {point_mode} fetch requires an already stopped acquisition; "
                f"current trigger status is {status}"
            )

    def _configure_bounded_long_waveform_transfer(
        self,
        *,
        channel: int,
        point_mode: str,
        point_budget: int,
    ) -> None:
        self._configure_waveform_transfer(channel=channel, point_mode=point_mode)
        self._write_and_verify(
            command=f":WAVeform:POINts {point_budget}",
            query=":WAVeform:POINts?",
            expected=point_budget,
            parser=lambda value: parse_positive_integer(
                value,
                field="waveform points",
                maximum=_MAX_WAVEFORM_STATE_POINTS,
            ),
            phase="setup",
        )

    def fetch_waveform_bounded(
        self,
        channel: int,
        points: str = "dmax",
        *,
        baseline: ScopeWaveformTransferBaseline,
    ) -> WaveformData:
        self._validate_analog_channel(channel)
        point_mode = self._normalize_point_mode(points)
        self._validate_waveform_transfer_baseline(baseline)
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            self._require_displayed_channels([channel])
            self._require_main_timebase()
            if point_mode == "DEF":
                self._configure_waveform_transfer(channel=channel, point_mode=point_mode)
                point_budget = self.max_total_waveform_points
            else:
                self._require_long_fetch_stopped(point_mode)
                point_budget = self._bounded_long_waveform_point_budget()
                self._configure_bounded_long_waveform_transfer(
                    channel=channel,
                    point_mode=point_mode,
                    point_budget=point_budget,
                )
            return self._read_byte_waveform(
                channel,
                point_mode=point_mode,
                remaining_points=point_budget,
                bounded=True,
            )

    def get_math_waveform_metadata(
        self,
        math_index: int,
    ) -> ScopeDerivedWaveformMetadata:
        self._validate_math_index(math_index)
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            displayed = parse_boolean_state(
                self.transport.query(f":MATH{math_index}:DISPlay?"),
                field=f"MATH{math_index} display",
            )
            if not displayed:
                raise ConfigError(
                    f"MSO8104 MATH{math_index} is not displayed; refusing to change "
                    "waveform transfer state"
                )
            self._require_main_timebase()
            previous = self._snapshot_waveform_state()
            try:
                transfer = WaveformTransferState(
                    source=f"MATH{math_index}",
                    mode="NORM",
                    data_format="BYTE",
                    points=_NORMAL_WAVEFORM_POINTS,
                    start=1,
                    stop=_NORMAL_WAVEFORM_POINTS,
                )
                self._apply_waveform_state(transfer, phase="setup")
                preamble = parse_rigol_waveform_preamble(
                    self.transport.query(":WAVeform:PREamble?"),
                    expected_type_code=0,
                    maximum_points=_NORMAL_WAVEFORM_POINTS,
                )
                if preamble.points != _NORMAL_WAVEFORM_POINTS:
                    raise DataError(
                        "MSO8104 math waveform preamble point count does not match the "
                        f"configured {_NORMAL_WAVEFORM_POINTS} points: {preamble.points}"
                    )
                x_start = (
                    preamble.x_origin
                    - preamble.x_reference * preamble.x_increment
                )
                x_stop = x_start + (preamble.points - 1) * preamble.x_increment
                if not math.isfinite(x_start) or not math.isfinite(x_stop):
                    raise DataError("MSO8104 math waveform X axis is non-finite")
                return ScopeDerivedWaveformMetadata(
                    source_kind="math",
                    index=math_index,
                    source_catalog=None,
                    x_start=x_start,
                    x_stop=x_stop,
                    points=preamble.points,
                    values_per_sample=None,
                    x_increment=preamble.x_increment,
                    x_origin=preamble.x_origin,
                    y_increment=preamble.y_increment,
                    y_origin=preamble.y_origin,
                    y_resolution_bits=8,
                )
            finally:
                self._restore_waveform_state(previous)

    def get_cursor_readout(
        self,
        cursor_index: int,
        *,
        configured_cursor: bool,
    ) -> ScopeCursorReadout:
        if type(cursor_index) is not int or cursor_index != 1:
            raise DataError("MSO8104 cursor index must be the integer 1")
        if type(configured_cursor) is not bool:
            raise DataError("MSO8104 configured_cursor must be a boolean")
        if not configured_cursor:
            raise ConfigError(
                "reading an MSO8104 cursor requires explicit confirmation that it is "
                "already configured"
            )
        with self._io_lock:
            self._require_open()
            mode = parse_cursor_mode(self.transport.query(":CURSor:MODE?"))
            if mode != "MAN":
                raise ConfigError(
                    "MSO8104 cursor readout supports only the preconfigured manual mode; "
                    f"current mode is {mode}"
                )
            cursor_type = parse_manual_cursor_type(
                self.transport.query(":CURSor:MANual:TYPE?")
            )
            source_a = parse_cursor_source(
                self.transport.query(":CURSor:MANual:SOURce1?")
            )
            source_b = parse_cursor_source(
                self.transport.query(":CURSor:MANual:SOURce2?")
            )
            if source_a == "NONE" or source_a != source_b:
                raise ConfigError(
                    "MSO8104 cursor readout requires the manual A and B cursors to use "
                    f"the same non-NONE source, got {source_a} and {source_b}"
                )
            if cursor_type == "TIME":
                unit = parse_cursor_time_unit(
                    self.transport.query(":CURSor:MANual:TUNit?")
                )
                if unit != "SEC":
                    raise ConfigError(
                        "MSO8104 TIME cursor readout requires the preconfigured SEC unit, "
                        f"got {unit}"
                    )
                return ScopeCursorReadout(
                    cursor_index=cursor_index,
                    source=source_a,
                    function="VERTICAL",
                    x_delta_s=parse_finite_float(
                        self.transport.query(":CURSor:MANual:XDELta?"),
                        field="manual cursor X delta",
                    ),
                    inverse_x_delta_hz=parse_finite_float(
                        self.transport.query(":CURSor:MANual:IXDelta?"),
                        field="manual cursor inverse X delta",
                    ),
                )
            if cursor_type == "AMPL":
                if source_a == "LA":
                    raise ConfigError(
                        "MSO8104 AMPL cursor readout does not support the LA source"
                    )
                unit = parse_cursor_vertical_unit(
                    self.transport.query(":CURSor:MANual:VUNit?")
                )
                if unit != "SOUR":
                    raise ConfigError(
                        "MSO8104 AMPL cursor readout requires the preconfigured SOUR unit, "
                        f"got {unit}"
                    )
                return ScopeCursorReadout(
                    cursor_index=cursor_index,
                    source=source_a,
                    function="HORIZONTAL",
                    y_delta=parse_finite_float(
                        self.transport.query(":CURSor:MANual:YDELta?"),
                        field="manual cursor Y delta",
                    ),
                )
            raise ConfigError(
                "MSO8104 cursor readout supports only preconfigured TIME or AMPL manual "
                f"cursor types, got {cursor_type}"
            )

    def get_cursor_readout_v2(
        self,
        cursor_index: int | None,
        *,
        configured_cursor: bool,
    ) -> ScopeCursorReadoutV2:
        if cursor_index is not None:
            raise DataError("MSO8104 cursor readout V2 uses global addressing and requires None")
        if type(configured_cursor) is not bool:
            raise DataError("MSO8104 configured_cursor must be a boolean")
        if not configured_cursor:
            raise ConfigError(
                "reading an MSO8104 cursor requires explicit confirmation that it is "
                "already configured"
            )
        with self._io_lock:
            self._require_open()
            mode = parse_cursor_mode(self.transport.query(":CURSor:MODE?"))
            if mode != "MAN":
                raise ConfigError(
                    "MSO8104 cursor readout V2 supports only the preconfigured manual mode; "
                    f"current mode is {mode}"
                )
            cursor_type = parse_manual_cursor_type(
                self.transport.query(":CURSor:MANual:TYPE?")
            )
            if cursor_type not in {"TIME", "AMPL"}:
                raise ConfigError(
                    "MSO8104 cursor readout V2 supports only preconfigured TIME or AMPL "
                    f"manual cursor types, got {cursor_type}"
                )
            source_a = parse_cursor_source(
                self.transport.query(":CURSor:MANual:SOURce1?")
            )
            source_b = parse_cursor_source(
                self.transport.query(":CURSor:MANual:SOURce2?")
            )
            if source_a == "NONE" or source_b == "NONE":
                raise ConfigError(
                    "MSO8104 cursor readout V2 requires non-NONE manual cursor sources, "
                    f"got {source_a} and {source_b}"
                )
            if cursor_type == "TIME":
                unit_token = parse_cursor_time_unit(
                    self.transport.query(":CURSor:MANual:TUNit?")
                )
                value_unit, inverse_unit = _CURSOR_TIME_UNITS[unit_token]
                x_a = ScopeCursorQuantity(
                    parse_finite_float(
                        self.transport.query(":CURSor:MANual:AXValue?"),
                        field="manual cursor A X value",
                    ),
                    value_unit,
                )
                x_b = ScopeCursorQuantity(
                    parse_finite_float(
                        self.transport.query(":CURSor:MANual:BXValue?"),
                        field="manual cursor B X value",
                    ),
                    value_unit,
                )
                x_delta = ScopeCursorQuantity(
                    parse_finite_float(
                        self.transport.query(":CURSor:MANual:XDELta?"),
                        field="manual cursor X delta",
                    ),
                    value_unit,
                )
                inverse_x_delta = (
                    None
                    if inverse_unit is None
                    else ScopeCursorQuantity(
                        parse_finite_float(
                            self.transport.query(":CURSor:MANual:IXDelta?"),
                            field="manual cursor inverse X delta",
                        ),
                        inverse_unit,
                    )
                )
                not_applicable = (
                    ("cursor_index", "y_a", "y_b", "y_delta")
                    if inverse_x_delta is not None
                    else ("cursor_index", "inverse_x_delta", "y_a", "y_b", "y_delta")
                )
                return ScopeCursorReadoutV2(
                    cursor_index=None,
                    mode=mode,
                    function=cursor_type,
                    source_a=source_a,
                    source_b=source_b,
                    x_a=x_a,
                    x_b=x_b,
                    x_delta=x_delta,
                    inverse_x_delta=inverse_x_delta,
                    not_applicable_fields=not_applicable,
                )
            if source_a == "LA" or source_b == "LA":
                raise ConfigError(
                    "MSO8104 AMPL cursor readout V2 does not support the LA source"
                )
            unit_token = parse_cursor_vertical_unit(
                self.transport.query(":CURSor:MANual:VUNit?")
            )
            value_unit = _CURSOR_VERTICAL_UNITS[unit_token]
            return ScopeCursorReadoutV2(
                cursor_index=None,
                mode=mode,
                function=cursor_type,
                source_a=source_a,
                source_b=source_b,
                y_a=ScopeCursorQuantity(
                    parse_finite_float(
                        self.transport.query(":CURSor:MANual:AYValue?"),
                        field="manual cursor A Y value",
                    ),
                    value_unit,
                ),
                y_b=ScopeCursorQuantity(
                    parse_finite_float(
                        self.transport.query(":CURSor:MANual:BYValue?"),
                        field="manual cursor B Y value",
                    ),
                    value_unit,
                ),
                y_delta=ScopeCursorQuantity(
                    parse_finite_float(
                        self.transport.query(":CURSor:MANual:YDELta?"),
                        field="manual cursor Y delta",
                    ),
                    value_unit,
                ),
                not_applicable_fields=(
                    "cursor_index",
                    "x_a",
                    "x_b",
                    "x_delta",
                    "inverse_x_delta",
                ),
            )

    @staticmethod
    def _validate_measurement_statistics_request(
        request: ScopeMeasurementStatisticsRequestV2,
    ) -> tuple[str, tuple[str, ...]]:
        if not isinstance(request, ScopeMeasurementStatisticsRequestV2):
            raise DataError("MSO8104 measurement statistics V2 request has an invalid type")
        if request.selector.mode != "item_sources":
            raise ConfigError(
                "MSO8104 measurement statistics V2 supports only explicit item_sources "
                "selectors"
            )
        if request.include_buffer:
            raise ConfigError(
                "MSO8104 measurement statistics V2 does not support statistics buffers"
            )

        item = request.selector.item
        sources = request.selector.sources
        if item not in MSO8104_MEASUREMENT_STATISTICS_ITEMS:
            raise ConfigError(
                f"MSO8104 measurement statistics V2 does not support item {item!r}"
            )
        expected_source_count = (
            2 if item in MSO8104_MEASUREMENT_STATISTICS_TWO_SOURCE_ITEMS else 1
        )
        if len(sources) != expected_source_count:
            raise ConfigError(
                f"MSO8104 measurement statistics V2 item {item} requires exactly "
                f"{expected_source_count} source(s)"
            )
        for source in sources:
            if source in MSO8104_MEASUREMENT_STATISTICS_ANALOG_MATH_SOURCES:
                continue
            if (
                source in MSO8104_MEASUREMENT_STATISTICS_DIGITAL_SOURCES
                and item in MSO8104_MEASUREMENT_STATISTICS_DIGITAL_SOURCE_ITEMS
            ):
                continue
            raise ConfigError(
                f"MSO8104 measurement statistics V2 item {item} does not support "
                f"source {source!r}"
            )
        return item, sources

    def get_measurement_statistics_v2(
        self,
        request: ScopeMeasurementStatisticsRequestV2,
    ) -> ScopeMeasurementStatisticsV2:
        item, sources = self._validate_measurement_statistics_request(request)
        selector_args = f"{item},{','.join(sources)}"
        with self._io_lock:
            self._require_open()
            actual = parse_finite_float(
                self.transport.query(
                    f":MEASure:STATistic:ITEM? CURRENT,{selector_args}"
                ),
                field="measurement statistics current",
            )
            average = parse_finite_float(
                self.transport.query(
                    f":MEASure:STATistic:ITEM? AVERages,{selector_args}"
                ),
                field="measurement statistics average",
            )
            standard_deviation = parse_finite_float(
                self.transport.query(
                    f":MEASure:STATistic:ITEM? DEViation,{selector_args}"
                ),
                field="measurement statistics deviation",
            )
            minimum = parse_finite_float(
                self.transport.query(
                    f":MEASure:STATistic:ITEM? MINimum,{selector_args}"
                ),
                field="measurement statistics minimum",
            )
            maximum = parse_finite_float(
                self.transport.query(
                    f":MEASure:STATistic:ITEM? MAXimum,{selector_args}"
                ),
                field="measurement statistics maximum",
            )
            waveform_count = parse_nonnegative_statistic_count(
                self.transport.query(
                    f":MEASure:STATistic:ITEM? CNT,{selector_args}"
                ),
                field="measurement statistics count",
            )
            return ScopeMeasurementStatisticsV2(
                selector=request.selector,
                category=item,
                actual=actual,
                average=average,
                standard_deviation=standard_deviation,
                minimum=minimum,
                maximum=maximum,
                waveform_count=waveform_count,
            )

    def get_fft_status_v2(
        self,
        math_index: int,
        *,
        configured_fft: bool,
    ) -> ScopeFftStatusV2:
        self._validate_math_index(math_index)
        if type(configured_fft) is not bool:
            raise DataError("MSO8104 configured_fft must be a boolean")
        if not configured_fft:
            raise ConfigError(
                "reading MSO8104 FFT status requires explicit confirmation that the "
                "target math slot is already configured"
            )
        with self._io_lock:
            self._require_open()
            operator = parse_math_operator(
                self.transport.query(f":MATH{math_index}:OPERator?")
            )
            if operator != "FFT":
                raise ConfigError(
                    f"MSO8104 MATH{math_index} is not configured for FFT, got {operator}"
                )
            source = parse_fft_source(
                self.transport.query(f":MATH{math_index}:FFT:SOURce?")
            )
            window = parse_fft_window(
                self.transport.query(f":MATH{math_index}:FFT:WINDow?")
            )
            vertical_unit = parse_fft_vertical_unit(
                self.transport.query(f":MATH{math_index}:FFT:UNIT?")
            )
            frequency_start_hz = parse_finite_float(
                self.transport.query(f":MATH{math_index}:FFT:FREQuency:STARt?"),
                field="FFT frequency start",
            )
            frequency_stop_hz = parse_finite_float(
                self.transport.query(f":MATH{math_index}:FFT:FREQuency:END?"),
                field="FFT frequency stop",
            )
            if frequency_start_hz >= frequency_stop_hz:
                raise DataError(
                    "MSO8104 FFT frequency start must be below frequency stop, got "
                    f"{frequency_start_hz} and {frequency_stop_hz}"
                )
            return ScopeFftStatusV2(
                math_index=math_index,
                source=source,
                window=window,
                vertical_unit=vertical_unit,
                frequency_start_hz=frequency_start_hz,
                frequency_stop_hz=frequency_stop_hz,
                unavailable_fields=_FFT_STATUS_V2_UNAVAILABLE_FIELDS,
            )

    def get_acquisition_status_v2(
        self,
        *,
        fields: tuple[ScopeAcquisitionStatusFieldV2, ...],
    ) -> ScopeAcquisitionStatusV2:
        if fields != MSO8104_ACQUISITION_STATUS_V2_READABLE_FIELDS:
            raise ConfigError(
                "MSO8104 acquisition status V2 supports only its descriptor's exact "
                "readable field profile"
            )
        with self._io_lock:
            self._require_open()
            acquisition_type = parse_acquisition_type(
                self.transport.query(":ACQuire:TYPE?")
            )
            sample_rate_hz = parse_positive_finite_float(
                self.transport.query(":ACQuire:SRATe?"),
                field="acquisition sample rate",
            )
            memory_depth = parse_positive_scientific_integer(
                self.transport.query(":ACQuire:MDEPth?"),
                field="acquisition memory depth",
            )
            if memory_depth > _MAX_WAVEFORM_STATE_POINTS:
                raise DataError(
                    "MSO8104 acquisition memory depth exceeds the documented 500000000 "
                    f"points: {memory_depth}"
                )
            if acquisition_type != "AVER":
                return ScopeAcquisitionStatusV2(
                    acquisition_type=acquisition_type,
                    sample_rate_hz=sample_rate_hz,
                    memory_depth=memory_depth,
                    unavailable_fields=_ACQUISITION_STATUS_V2_STATIC_UNAVAILABLE_FIELDS,
                    not_applicable_fields=("average",),
                )
            return ScopeAcquisitionStatusV2(
                acquisition_type=acquisition_type,
                sample_rate_hz=sample_rate_hz,
                memory_depth=memory_depth,
                average=ScopeAverageStatusV2(
                    configured_count=parse_average_acquisition_count(
                        self.transport.query(":ACQuire:AVERages?")
                    )
                ),
                unavailable_fields=_ACQUISITION_STATUS_V2_AVERAGE_UNAVAILABLE_FIELDS,
            )

    @staticmethod
    def _validate_check_errors(check_errors: bool) -> None:
        if type(check_errors) is not bool:
            raise DataError("MSO8104 check_errors must be a boolean")
        if check_errors:
            raise ConfigError(
                "MSO8104 legacy check_errors bypasses Core error-drain policy; "
                "use the Core bounded operation or set scope.check_errors=false"
            )

    @staticmethod
    def _normalize_point_mode(points: str) -> str:
        if not isinstance(points, str):
            raise DataError("MSO8104 waveform points must be DEF, MAX, or DMAX")
        normalized = points.strip().upper()
        if normalized not in _POINT_MODE_TO_TRANSFER:
            raise DataError("MSO8104 waveform points must be DEF, MAX, or DMAX")
        return normalized

    @staticmethod
    def _validate_capture_adjustments(
        *,
        time_range_s: float | None,
        vertical_scale_v_per_div: float | None,
    ) -> None:
        if time_range_s is not None:
            raise ConfigError(
                "MSO8104 capture does not yet support time_range_s; preconfigure the timebase"
            )
        if vertical_scale_v_per_div is not None:
            raise ConfigError(
                "MSO8104 capture does not yet support vertical_scale_v_per_div; "
                "preconfigure channel scale"
            )

    def _require_displayed_channels(self, channels: list[int]) -> None:
        for channel in channels:
            displayed = parse_display_state(
                self.transport.query(f":CHANnel{channel}:DISPlay?")
            )
            if not displayed:
                raise ConfigError(
                    f"MSO8104 CH{channel} is not displayed; refusing to change channel state"
                )

    def _single_and_wait_for_stop(self) -> None:
        try:
            self.transport.write(":SINGle")
        except Exception as exc:
            self._acquisition_writes_blocked = True
            raise InstrumentError(
                "MSO8104 single-acquisition write outcome is uncertain; "
                "acquisition writes are blocked"
            ) from exc
        deadline = self._clock() + self.acquisition_timeout_s
        while True:
            try:
                status = parse_trigger_status(self.transport.query(":TRIGger:STATus?"))
            except Exception as exc:
                self._acquisition_writes_blocked = True
                raise InstrumentError(
                    "MSO8104 trigger status became uncertain after SINGLE; "
                    "acquisition writes are blocked"
                ) from exc
            if status == "STOP":
                return
            remaining_s = deadline - self._clock()
            if remaining_s <= 0:
                self._acquisition_writes_blocked = True
                raise OperationTimeout(
                    "MSO8104 single acquisition did not reach STOP before the configured "
                    "opc timeout; the instrument was not forced or retriggered, and acquisition "
                    "writes are blocked until the session is reopened"
                )
            self._sleep(min(self.trigger_poll_interval_s, remaining_s))

    def _capture_single_and_wait_for_transition(self) -> None:
        deadline = self._clock() + self.acquisition_timeout_s
        try:
            proof, _, _ = self._arm_single_and_wait_for_completion(deadline)
            if proof != "state_transition":
                raise DataError(
                    "MSO8104 bounded capture freshness is unproven: terminal STOP "
                    "after SINGLE mode readback does not prove a post-arm waveform"
                )
        except (DataError, OperationTimeout):
            self._acquisition_writes_blocked = True
            raise
        except Exception as exc:
            self._acquisition_writes_blocked = True
            raise InstrumentError(
                "MSO8104 bounded capture SINGLE outcome is uncertain; acquisition writes are "
                "blocked"
            ) from exc

    @staticmethod
    def _assert_matching_x_axis(
        reference: WaveformData,
        candidate: WaveformData,
    ) -> None:
        tolerance = max(
            abs(reference.header.x_increment) * 1.0e-6,
            abs(reference.header.x_stop) * 1.0e-12,
            1.0e-18,
        )
        if (
            reference.header.points != candidate.header.points
            or not math.isclose(
                reference.header.x_start,
                candidate.header.x_start,
                rel_tol=0.0,
                abs_tol=tolerance,
            )
            or not math.isclose(
                reference.header.x_stop,
                candidate.header.x_stop,
                rel_tol=0.0,
                abs_tol=tolerance,
            )
        ):
            raise DataError(
                "MSO8104 multi-channel waveforms do not share a consistent X axis"
            )

    def fetch_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
    ) -> WaveformData:
        self._validate_analog_channel(channel)
        point_mode = self._normalize_point_mode(points)
        self._validate_check_errors(check_errors)
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            self._require_displayed_channels([channel])
            self._require_main_timebase()
            if point_mode == "DMAX":
                self._require_long_fetch_stopped(point_mode)
            return self._read_waveform_transaction(
                channel,
                point_mode=point_mode,
                remaining_points=self.max_total_waveform_points,
            )

    def capture_waveform(
        self,
        channel: int,
        points: str = "dmax",
        check_errors: bool = True,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
    ) -> WaveformData:
        waveforms = self.capture_waveforms(
            channels=[channel],
            points=points,
            check_errors=check_errors,
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        return waveforms[channel]

    def capture_waveforms(
        self,
        channels: list[int],
        points: str = "dmax",
        check_errors: bool = True,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
        on_channel_start: Callable[[int | None], None] | None = None,
        on_waveform: Callable[[int, WaveformData], None] | None = None,
    ) -> dict[int, WaveformData]:
        if not isinstance(channels, list) or not channels:
            raise DataError("MSO8104 capture channels must be a non-empty list")
        for channel in channels:
            self._validate_analog_channel(channel)
        if len(set(channels)) != len(channels):
            raise DataError("MSO8104 capture channels must be unique")
        point_mode = self._normalize_point_mode(points)
        self._validate_check_errors(check_errors)
        self._validate_capture_adjustments(
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        if on_channel_start is not None and not callable(on_channel_start):
            raise DataError("MSO8104 on_channel_start must be callable or None")
        if on_waveform is not None and not callable(on_waveform):
            raise DataError("MSO8104 on_waveform must be callable or None")
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            self._require_acquisition_writes_allowed()
            self._require_displayed_channels(channels)
            self._require_main_timebase()
            self._single_and_wait_for_stop()
            waveforms: dict[int, WaveformData] = {}
            reference: WaveformData | None = None
            remaining_points = self.max_total_waveform_points
            for channel in channels:
                if on_channel_start is not None:
                    on_channel_start(channel)
                waveform = self._read_waveform_transaction(
                    channel,
                    point_mode=point_mode,
                    remaining_points=remaining_points,
                )
                if reference is None:
                    reference = waveform
                else:
                    self._assert_matching_x_axis(reference, waveform)
                waveforms[channel] = waveform
                remaining_points -= waveform.sample_count
                if on_waveform is not None:
                    on_waveform(channel, waveform)
            return waveforms

    def capture_waveform_bounded(
        self,
        channel: int,
        points: str = "dmax",
        *,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
        baseline: ScopeWaveformTransferBaseline,
    ) -> WaveformData:
        waveforms = self.capture_waveforms_bounded(
            channels=[channel],
            points=points,
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
            baseline=baseline,
        )
        return waveforms[channel]

    def capture_waveforms_bounded(
        self,
        channels: list[int],
        points: str = "dmax",
        *,
        time_range_s: float | None = None,
        vertical_scale_v_per_div: float | None = None,
        on_channel_start: Callable[[int | None], None] | None = None,
        on_waveform: Callable[[int, WaveformData], None] | None = None,
        baseline: ScopeWaveformTransferBaseline,
    ) -> dict[int, WaveformData]:
        if not isinstance(channels, list) or not channels:
            raise DataError("MSO8104 bounded capture channels must be a non-empty list")
        for channel in channels:
            self._validate_analog_channel(channel)
        if len(set(channels)) != len(channels):
            raise DataError("MSO8104 bounded capture channels must be unique")
        point_mode = self._normalize_point_mode(points)
        if point_mode != "DEF":
            raise ConfigError(
                "MSO8104 bounded capture candidate supports only DEF pending independent "
                "MAX and DMAX capture acceptance"
            )
        self._validate_capture_adjustments(
            time_range_s=time_range_s,
            vertical_scale_v_per_div=vertical_scale_v_per_div,
        )
        if on_channel_start is not None and not callable(on_channel_start):
            raise DataError("MSO8104 on_channel_start must be callable or None")
        if on_waveform is not None and not callable(on_waveform):
            raise DataError("MSO8104 on_waveform must be callable or None")
        self._validate_capture_waveform_transfer_baseline(baseline)
        with self._io_lock:
            self._require_open()
            self._require_waveform_writes_allowed()
            self._require_acquisition_writes_allowed()
            self._require_displayed_channels(channels)
            self._require_main_timebase()
            self._capture_single_and_wait_for_transition()
            waveforms: dict[int, WaveformData] = {}
            reference: WaveformData | None = None
            remaining_points = self.max_total_waveform_points
            for channel in channels:
                if on_channel_start is not None:
                    on_channel_start(channel)
                self._configure_waveform_transfer(channel=channel, point_mode=point_mode)
                waveform = self._read_byte_waveform(
                    channel,
                    point_mode=point_mode,
                    remaining_points=remaining_points,
                    bounded=True,
                )
                if reference is None:
                    reference = waveform
                else:
                    self._assert_matching_x_axis(reference, waveform)
                waveforms[channel] = waveform
                remaining_points -= waveform.sample_count
                if on_waveform is not None:
                    on_waveform(channel, waveform)
            return waveforms

    def close(self) -> None:
        with self._io_lock:
            if self._closed:
                return
            self._closed = True
            self._capture_recovery_states.clear()
            self.transport.close()
