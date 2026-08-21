from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import SDG2000XSource

    return SDG2000XSource(transport=context.open_transport())


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="siglent.sdg2000x",
        kind="source",
        display_name="SIGLENT SDG2000X Function/Arbitrary Waveform Generator",
        manufacturer="SIGLENT Technologies",
        models=("SDG2042X", "SDG2082X", "SDG2122X"),
        aliases=(),
        capabilities=(
            "source.idn",
            "source.status",
            "source.set_frequency",
            "source.set_function",
            "source.set_amplitude_vpp",
            "source.output",
        ),
        idn_patterns=("Siglent Technologies,SDG2", "*IDN,SDG,SDG2"),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Strict identity and channel status for SIGLENT SDG2000X-series sources, "
            "with readback-verified output control and fail-safe OFF recovery."
        ),
        wavebench_min_version="0.8.0",
        wavebench_max_version="0.9.0",
        distribution="wavebench-siglent-sdg2000x",
        version="0.6.0",
        source="entry_point:siglent.sdg2000x",
        config_fields=(
            "source.resource",
            "source.driver",
            "safety_limits.max_source_vpp",
        ),
    )
