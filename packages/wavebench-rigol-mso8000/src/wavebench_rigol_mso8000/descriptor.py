from __future__ import annotations

from wavebench.errors import DataError
from wavebench.instruments import InstrumentDescriptor, OptionSpec
from wavebench.instruments.scope_extensions import (
    ScopeAcquisitionControlProfile,
    ScopeAcquisitionStatusProfileV2,
    ScopeCursorReadoutProfileV2,
    ScopeDescriptorExtensions,
    ScopeFftStatusProfileV2,
    ScopeMeasurementStatisticsProfileV2,
    ScopeSnapshotProfileV2,
    ScopeWaveformBinaryOperationProfile,
    ScopeWaveformBinaryProfile,
)

from .parsers import (
    MSO8104_ACQUISITION_STATUS_V2_CONDITIONALLY_APPLICABLE_FIELDS,
    MSO8104_ACQUISITION_STATUS_V2_READABLE_FIELDS,
    MSO8104_MEASUREMENT_STATISTICS_ITEMS,
    MSO8104_SNAPSHOT_V2_READABLE_FIELDS,
    MSO8104_SYSTEM_OPTION_TYPES,
)


_WAVEFORM_FETCH_RESTORE_ORDER = (
    "scope.waveform_source",
    "scope.waveform_mode",
    "scope.waveform_format",
    "scope.waveform_points",
    "scope.waveform_transfer_window",
)
_WAVEFORM_FETCH_RESPONSE_MAX_BYTES = 250_000
_WAVEFORM_FETCH_OPERATION_MAX_BYTES = 4_000_000
_WAVEFORM_FETCH_QUERY_MAX_COUNT = 16
_WAVEFORM_CAPTURE_RESTORE_ORDER = (
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
_WAVEFORM_BINARY_PROFILE = ScopeWaveformBinaryProfile(
    operations=(
        ScopeWaveformBinaryOperationProfile(
            operation_kind="fetch",
            response_max_bytes=_WAVEFORM_FETCH_RESPONSE_MAX_BYTES,
            operation_max_bytes=_WAVEFORM_FETCH_OPERATION_MAX_BYTES,
            query_max_count=_WAVEFORM_FETCH_QUERY_MAX_COUNT,
            resynchronization_max_bytes=65_536,
            restore_order=_WAVEFORM_FETCH_RESTORE_ORDER,
            snapshot_max_steps=6,
            restore_max_steps=6,
            verify_max_steps=6,
        ),
        ScopeWaveformBinaryOperationProfile(
            operation_kind="capture_single",
            response_max_bytes=1_000,
            operation_max_bytes=1_000,
            query_max_count=1,
            resynchronization_max_bytes=65_536,
            restore_order=_WAVEFORM_CAPTURE_RESTORE_ORDER,
            snapshot_max_steps=32,
            restore_max_steps=32,
            verify_max_steps=32,
        ),
        ScopeWaveformBinaryOperationProfile(
            operation_kind="capture_multiple",
            response_max_bytes=1_000,
            operation_max_bytes=4_000,
            query_max_count=4,
            resynchronization_max_bytes=65_536,
            restore_order=_WAVEFORM_CAPTURE_RESTORE_ORDER,
            snapshot_max_steps=32,
            restore_max_steps=32,
            verify_max_steps=32,
        ),
    ),
    transport_trailing_hex="0a",
)
_CURSOR_READOUT_PROFILE_V2 = ScopeCursorReadoutProfileV2(
    readable_fields=(
        "source_a",
        "source_b",
        "x_a",
        "x_b",
        "x_delta",
        "inverse_x_delta",
        "y_a",
        "y_b",
        "y_delta",
    ),
    conditionally_applicable_fields=(
        "x_a",
        "x_b",
        "x_delta",
        "inverse_x_delta",
        "y_a",
        "y_b",
        "y_delta",
    ),
    addressing="global",
    max_queries=9,
)
_MEASUREMENT_STATISTICS_PROFILE_V2 = ScopeMeasurementStatisticsProfileV2(
    selector_modes=("item_sources",),
    max_queries=6,
    supports_buffer=False,
    supported_items=MSO8104_MEASUREMENT_STATISTICS_ITEMS,
    item_source_count_range=(1, 2),
)
_FFT_STATUS_PROFILE_V2 = ScopeFftStatusProfileV2(
    readable_fields=(
        "source",
        "window",
        "vertical_unit",
        "frequency_start_hz",
        "frequency_stop_hz",
    ),
    max_queries=6,
)
_ACQUISITION_STATUS_PROFILE_V2 = ScopeAcquisitionStatusProfileV2(
    readable_fields=MSO8104_ACQUISITION_STATUS_V2_READABLE_FIELDS,
    max_queries=4,
    conditionally_applicable_fields=MSO8104_ACQUISITION_STATUS_V2_CONDITIONALLY_APPLICABLE_FIELDS,
)
_ACQUISITION_CONTROL_PROFILE = ScopeAcquisitionControlProfile(
    supported_continuous_modes=("normal",),
    single_arm_semantics="atomic_configure_and_arm",
    arm_resets_acquisition_count=True,
    failure_restore_order=("scope.trigger", "scope.acquisition"),
    snapshot_max_steps=3,
    restore_max_steps=3,
    verify_max_steps=3,
    identity_semantics="unknown",
    single_mode_readback_allows_terminal_stop=True,
)
_SNAPSHOT_PROFILE_V2 = ScopeSnapshotProfileV2(
    readable_fields=MSO8104_SNAPSHOT_V2_READABLE_FIELDS,
    max_queries=1 + len(MSO8104_SYSTEM_OPTION_TYPES),
)


def _strict_bounded_option(
    context,
    name: str,
    *,
    default: int,
    maximum: int,
) -> int:
    value = context.options.get(name, default)
    if type(value) is not int or not 1 <= value <= maximum:
        raise DataError(f"MSO8104 option {name} must be an integer from 1 through {maximum}")
    return value


def _open_driver(context):
    from .driver import MSO8104Scope

    max_total_points = _strict_bounded_option(
        context,
        "max_total_points",
        default=4_000_000,
        maximum=4_000_000,
    )
    max_chunk_points = _strict_bounded_option(
        context,
        "max_chunk_points",
        default=250_000,
        maximum=250_000,
    )
    return MSO8104Scope(
        transport=context.open_transport(),
        acquisition_timeout_s=context.opc_timeout_ms / 1000.0,
        max_total_waveform_points=max_total_points,
        max_byte_points_per_read=max_chunk_points,
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.mso8104",
        kind="scope",
        display_name="RIGOL MSO8104 Oscilloscope",
        manufacturer="RIGOL Technologies",
        models=("MSO8104",),
        aliases=(),
        capabilities=(
            "scope.idn",
            "scope.error_drain_v1",
            "scope.fetch_waveform",
            "scope.capture_waveform",
            "scope.capture_waveforms",
            "scope.channel_coupling",
            "scope.channel_input_state_v2",
            "scope.autoscale",
            "scope.math_metadata",
            "scope.measurement_statistics_v2",
            "scope.fft_status_v2",
            "scope.acquisition_status_v2",
            "scope.acquisition_run_state",
            "scope.acquisition_control",
            "scope.digital_status_v2",
            "scope.snapshot_v2",
            "scope.cursor_readout",
            "scope.cursor_readout_v2",
        ),
        idn_patterns=("RIGOL TECHNOLOGIES,MSO8104",),
        backends=("pyvisa",),
        resource_schemes=("tcpip", "usb", "gpib"),
        option_specs=(
            OptionSpec(
                "max_total_points",
                int,
                default=4_000_000,
                minimum=1,
                maximum=4_000_000,
            ),
            OptionSpec(
                "max_chunk_points",
                int,
                default=250_000,
                minimum=1,
                maximum=250_000,
            ),
        ),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Hardware-identified RIGOL MSO8104 identity, safety, bounded waveform "
            "fetch/capture with non-replayed error drain, autoscale, math, acquisition "
            "control, digital state, snapshot, and cursor driver."
        ),
        wavebench_min_version="0.8.24",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-mso8000",
        version="0.9.0",
        source="entry_point:rigol.mso8104",
        scope_coupling_policy="switchable-termination",
        config_fields=(
            "connection.backend",
            "connection.resource",
            "scope.driver",
        ),
        scope_extensions=ScopeDescriptorExtensions(
            waveform_binary_profile=_WAVEFORM_BINARY_PROFILE,
            measurement_statistics_profile_v2=_MEASUREMENT_STATISTICS_PROFILE_V2,
            fft_status_profile_v2=_FFT_STATUS_PROFILE_V2,
            acquisition_status_profile_v2=_ACQUISITION_STATUS_PROFILE_V2,
            acquisition_control_profile=_ACQUISITION_CONTROL_PROFILE,
            snapshot_profile_v2=_SNAPSHOT_PROFILE_V2,
            cursor_readout_profile_v2=_CURSOR_READOUT_PROFILE_V2,
        ),
    )
