from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import SDS800XHDScope

    return SDS800XHDScope(transport=context.open_transport())


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
        capabilities=("scope.idn", "scope.channel_coupling"),
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
            "Query-only SDS800X HD family driver with strict identity and analog-channel "
            "coupling reads; waveform and write capabilities remain disabled."
        ),
        wavebench_min_version="0.8.0",
        wavebench_max_version="0.9.0",
        distribution="wavebench-siglent-sds800x-hd",
        version="0.2.0",
        source="entry_point:siglent.sds800x-hd",
        scope_coupling_policy="fixed-high-impedance",
        config_fields=("connection.resource", "scope.driver"),
        resource_schemes=("tcpip", "usb"),
    )
