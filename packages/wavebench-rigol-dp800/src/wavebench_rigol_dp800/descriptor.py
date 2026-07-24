from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import DP800Power

    return DP800Power(
        transport=context.open_transport(),
        check_errors_after_ops=bool(context.settings["check_errors"]),
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.dp800",
        kind="power",
        display_name="RIGOL DP800 Power Supply",
        manufacturer="RIGOL Technologies",
        models=("DP800", "DP832", "DP832A"),
        aliases=(),
        capabilities=(
            "power.idn",
            "power.status",
            "power.measurement",
            "power.set_voltage_current_limit",
            "power.output",
            "power.protection",
        ),
        idn_patterns=("RIGOL TECHNOLOGIES,DP8",),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Installable RIGOL DP800-series power driver for status, measurement, "
            "setpoint, output, and protection operations."
        ),
        wavebench_min_version="0.8.0",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-dp800",
        version="0.1.0",
        source="entry_point:rigol.dp800",
        config_fields=(
            "power.resource",
            "power.driver",
            "power.check_errors",
            "power.settle_ms_after_set",
            "power.settle_ms_after_output",
            "safety_limits.max_power_voltage_v",
            "safety_limits.max_power_current_limit_a",
        ),
    )
