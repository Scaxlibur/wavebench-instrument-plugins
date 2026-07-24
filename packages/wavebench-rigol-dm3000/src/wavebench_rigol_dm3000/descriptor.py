from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import DM3000Dmm

    return DM3000Dmm(transport=context.open_transport())


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.dm3000",
        kind="dmm",
        display_name="RIGOL DM3000/DM3058 Digital Multimeter",
        manufacturer="RIGOL Technologies",
        models=("DM3000", "DM3058"),
        aliases=(),
        capabilities=("dmm.idn", "dmm.read", "dmm.function_status", "dmm.set_function"),
        idn_patterns=("RIGOL TECHNOLOGIES,DM3", "RIGOL TECHNOLOGIES,DM3058"),
        backends=("pyvisa",),
        resource_schemes=("tcpip",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary="LAN-only RIGOL DM3000-family DMM driver for configured PyVISA resources.",
        wavebench_min_version="0.7.0",
        wavebench_max_version="1.0.0",
        distribution="wavebench-rigol-dm3000",
        version="0.1.0",
        source="entry_point:rigol.dm3000",
        config_fields=(
            "dmm.resource",
            "dmm.driver",
            "dmm.backend",
            "dmm.timeout_ms",
            "dmm.settle_ms_before_read",
            "dmm.settle_ms_after_function_change",
        ),
    )
