from __future__ import annotations

from wavebench.instruments import (
    ScopeAcquisitionControlProfile,
    ScopeScreenshotProfile,
    ScopeScreenshotRequest,
    ScopeScreenshotVariant,
)
from wavebench.transport import BinaryResponseFraming


def _screenshot_variant(color_mode: str) -> ScopeScreenshotVariant:
    return ScopeScreenshotVariant(
        request=ScopeScreenshotRequest(menu_mode="device", color_mode=color_mode),
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
    )


SDS800X_HD_SCREENSHOT_PROFILE = ScopeScreenshotProfile(
    variants=(
        _screenshot_variant("color"),
        _screenshot_variant("inverted"),
    ),
    source="descriptor",
)

SDS800X_HD_ACQUISITION_CONTROL_PROFILE = ScopeAcquisitionControlProfile(
    supported_continuous_modes=("auto", "normal"),
    single_arm_semantics="configure_then_arm",
    arm_resets_acquisition_count=True,
    failure_restore_order=("scope.acquisition", "scope.trigger"),
    snapshot_max_steps=4,
    restore_max_steps=4,
    verify_max_steps=16,
    identity_semantics="unknown",
)


__all__ = [
    "SDS800X_HD_ACQUISITION_CONTROL_PROFILE",
    "SDS800X_HD_SCREENSHOT_PROFILE",
]
