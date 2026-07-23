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
            "Query-only SP30120 driver with verified RS-232 identity and scalar-status "
            "queries; generic snapshots, traces, markers, and control are not exposed."
        ),
        wavebench_min_version="0.7.0",
        wavebench_max_version="1.0.0",
        distribution="wavebench-shengpu-sp3000a",
        version="0.1.0",
        source="entry_point:shengpu.sp30120",
        config_fields=("connection.resource",),
    )
