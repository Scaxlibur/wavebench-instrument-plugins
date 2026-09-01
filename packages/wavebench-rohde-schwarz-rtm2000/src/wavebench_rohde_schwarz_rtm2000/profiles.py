from __future__ import annotations

from wavebench.instruments import (
    SCOPE_FFT_STATUS_V2_FIELD_ORDER,
    SCOPE_SNAPSHOT_V2_FIELD_ORDER,
    ScopeChannelDisplayProfileV2,
    ScopeDescriptorExtensions,
    ScopeFftStatusProfileV2,
    ScopeFocusProfileV2,
    ScopeMeasurementStatisticsProfileV2,
    ScopeSnapshotProfileV2,
)


RTM2000_SNAPSHOT_V2_READABLE_FIELDS = (
    "identity.manufacturer",
    "identity.model",
    "identity.serial_number",
    "identity.firmware",
    "identity.options",
)
RTM2000_SNAPSHOT_V2_UNAVAILABLE_FIELDS = tuple(
    field
    for field in SCOPE_SNAPSHOT_V2_FIELD_ORDER
    if field not in RTM2000_SNAPSHOT_V2_READABLE_FIELDS
)

RTM2000_FFT_STATUS_V2_READABLE_FIELDS = (
    "average_complete",
    "resolution_bandwidth_hz",
    "sample_rate_hz",
)
RTM2000_FFT_STATUS_V2_UNAVAILABLE_FIELDS = tuple(
    field
    for field in SCOPE_FFT_STATUS_V2_FIELD_ORDER
    if field not in RTM2000_FFT_STATUS_V2_READABLE_FIELDS
)

RTM2000_FOCUS_PROFILE_V2 = ScopeFocusProfileV2(
    analog_channels=(1, 2),
    time_range_min_s=1e-9,
    time_range_max_s=100.0,
    time_range_abs_tolerance_s=1e-12,
    vertical_scale_min_v_per_div=1e-3,
    vertical_scale_max_v_per_div=10.0,
    vertical_scale_abs_tolerance_v_per_div=1e-9,
    vertical_range_abs_tolerance_v=1e-9,
    time_position_abs_tolerance_s=1e-12,
    position_abs_tolerance=1e-9,
    offset_abs_tolerance_v=1e-9,
    snapshot_max_steps=12,
    configure_max_steps=17,
    restore_max_steps=12,
    verify_max_steps=12,
)

RTM2000_SCOPE_EXTENSIONS = ScopeDescriptorExtensions(
    channel_display_profile_v2=ScopeChannelDisplayProfileV2(
        analog_channels=(1, 2),
        snapshot_max_steps=1,
        configure_max_steps=2,
        restore_max_steps=1,
        verify_max_steps=1,
    ),
    focus_profile_v2=RTM2000_FOCUS_PROFILE_V2,
    snapshot_profile_v2=ScopeSnapshotProfileV2(
        readable_fields=RTM2000_SNAPSHOT_V2_READABLE_FIELDS,
        max_queries=2,
    ),
    measurement_statistics_profile_v2=ScopeMeasurementStatisticsProfileV2(
        selector_modes=("slot",),
        max_queries=7,
        slot_range=(1, 4),
    ),
    fft_status_profile_v2=ScopeFftStatusProfileV2(
        readable_fields=RTM2000_FFT_STATUS_V2_READABLE_FIELDS,
        max_queries=3,
    ),
)
