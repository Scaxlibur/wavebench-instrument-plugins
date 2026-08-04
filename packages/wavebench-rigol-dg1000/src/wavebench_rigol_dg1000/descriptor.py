from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import DG1000Source

    return DG1000Source(
        transport=context.open_transport(),
        check_errors_after_ops=bool(context.settings["check_errors"]),
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.dg1000",
        kind="source",
        display_name="RIGOL DG1000/DG1000Z Function/Arbitrary Waveform Generator",
        manufacturer="RIGOL Technologies",
        models=("DG1022", "DG1022A", "DG1022Z", "DG1032Z", "DG1062Z", "DG1000", "DG1000Z"),
        aliases=(),
        capabilities=(
            "source.idn",
            "source.errors",
            "source.status",
            "source.set_frequency",
            "source.set_function",
            "source.set_amplitude_vpp",
            "source.set_square_duty_cycle",
            "source.output",
        ),
        idn_patterns=("RIGOL TECHNOLOGIES,DG10",),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Installable RIGOL DG1000-series source driver for basic frequency, "
            "waveform, amplitude, duty-cycle, and output control."
        ),
        wavebench_min_version="0.8.0",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-dg1000",
        version="0.1.0",
        source="entry_point:rigol.dg1000",
        config_fields=(
            "source.resource",
            "source.driver",
            "safety_limits.max_source_vpp",
        ),
    )
