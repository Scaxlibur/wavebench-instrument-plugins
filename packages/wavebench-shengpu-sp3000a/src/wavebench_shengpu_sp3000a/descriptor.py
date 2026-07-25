from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import SP30120SweepAnalyzer

    return SP30120SweepAnalyzer(transport=context.open_transport())


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="shengpu.sp30120",
        kind="sweep_analyzer",
        display_name="Shengpu SP30120 Digital Sweep Analyzer",
        manufacturer="Shengpu",
        models=("SP30120",),
        aliases=(),
        capabilities=("sweep_analyzer.idn",),
        idn_patterns=("SHENGPU SP3000 Series Digital Sweeper",),
        backends=("serial",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "SP30120 driver with verified RS-232 identity, scalar-status queries, and "
            "vendor-specific RF-off controls; generic sweep capabilities are not exposed."
        ),
        wavebench_min_version="0.8.0",
        wavebench_max_version="0.9.0",
        distribution="wavebench-shengpu-sp3000a",
        version="0.2.0",
        source="entry_point:shengpu.sp30120",
        config_fields=("connection.resource",),
    )
