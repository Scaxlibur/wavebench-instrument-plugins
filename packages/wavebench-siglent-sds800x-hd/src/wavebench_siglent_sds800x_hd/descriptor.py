from __future__ import annotations

from wavebench.instruments import InstrumentDescriptor, ScopeDescriptorExtensions

from .profiles import (
    SDS800X_HD_ACQUISITION_CONTROL_PROFILE,
    SDS800X_HD_SCREENSHOT_PROFILE,
)


def _open_driver(context):
    from .driver import SDS800XHDScope

    return SDS800XHDScope(
        transport=context.open_transport(),
        capture_timeout_s=context.opc_timeout_ms / 1000.0,
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="siglent.sds800x-hd",
        kind="scope",
        display_name="SIGLENT SDS800X HD Oscilloscope",
        manufacturer="SIGLENT Technologies",
        models=(
            "SDS802X HD",
            "SDS804X HD",
            "SDS812X HD",
            "SDS814X HD",
            "SDS822X HD",
            "SDS824X HD",
        ),
        aliases=(),
        capabilities=(
            "scope.idn",
            "scope.channel_coupling",
            "scope.fetch_waveform",
            "scope.capture_waveform",
            "scope.capture_waveforms",
            "scope.measurement_statistics",
            "scope.screenshot_profile",
            "scope.screenshot_v2",
            "scope.acquisition_run_state",
            "scope.acquisition_control",
        ),
        idn_patterns=(
            "SDS802X HD",
            "SDS804X HD",
            "SDS812X HD",
            "SDS814X HD",
            "SDS822X HD",
            "SDS824X HD",
        ),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "SDS800X HD family driver with strict identity, analog-channel coupling, "
            "stopped-record and single-acquisition DMAX waveform reads, and read-only "
            "statistics, message-framed PNG screenshots, and standalone acquisition control."
        ),
        wavebench_min_version="0.8.23",
        wavebench_max_version="0.9.0",
        distribution="wavebench-siglent-sds800x-hd",
        version="0.6.0",
        source="entry_point:siglent.sds800x-hd",
        scope_coupling_policy="fixed-high-impedance",
        config_fields=("connection.resource", "scope.driver", "waveform.*"),
        resource_schemes=("tcpip", "usb"),
        scope_extensions=ScopeDescriptorExtensions(
            screenshot_profile=SDS800X_HD_SCREENSHOT_PROFILE,
            acquisition_control_profile=SDS800X_HD_ACQUISITION_CONTROL_PROFILE,
        ),
    )
