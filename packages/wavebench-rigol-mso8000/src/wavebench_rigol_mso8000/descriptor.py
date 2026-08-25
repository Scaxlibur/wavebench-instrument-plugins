from __future__ import annotations

from wavebench.errors import DataError
from wavebench.instruments import InstrumentDescriptor, OptionSpec
from wavebench.instruments.scope_extensions import (
    ScopeCursorReadoutProfileV2,
    ScopeDescriptorExtensions,
    ScopeMeasurementStatisticsProfileV2,
    ScopeWaveformBinaryOperationProfile,
    ScopeWaveformBinaryProfile,
)

from .parsers import MSO8104_MEASUREMENT_STATISTICS_ITEMS


_WAVEFORM_FETCH_RESTORE_ORDER = (
    "scope.waveform_source",
    "scope.waveform_mode",
    "scope.waveform_format",
    "scope.waveform_points",
    "scope.waveform_transfer_window",
)
_WAVEFORM_BINARY_PROFILE = ScopeWaveformBinaryProfile(
    operations=(
        ScopeWaveformBinaryOperationProfile(
            operation_kind="fetch",
            response_max_bytes=1_000,
            operation_max_bytes=1_000,
            query_max_count=1,
            resynchronization_max_bytes=65_536,
            restore_order=_WAVEFORM_FETCH_RESTORE_ORDER,
            snapshot_max_steps=6,
            restore_max_steps=6,
            verify_max_steps=6,
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
            "scope.fetch_waveform",
            "scope.channel_coupling",
            "scope.channel_input_state_v2",
            "scope.autoscale",
            "scope.math_metadata",
            "scope.measurement_statistics_v2",
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
            "Hardware-identified RIGOL MSO8104 identity, safety, bounded DEF waveform fetch, "
            "autoscale, math, and cursor driver."
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
            cursor_readout_profile_v2=_CURSOR_READOUT_PROFILE_V2,
        ),
    )
