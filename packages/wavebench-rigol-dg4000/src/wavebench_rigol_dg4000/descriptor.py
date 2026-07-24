from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import DG4202Source

    return DG4202Source(
        transport=context.open_transport(),
        check_errors_after_ops=bool(context.settings["check_errors"]),
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.dg4202",
        kind="source",
        display_name="RIGOL DG4000 Function/Arbitrary Waveform Generator",
        manufacturer="RIGOL Technologies",
        models=("DG4202", "DG4000"),
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
            "source.arbitrary_probe",
            "source.arbitrary_upload",
        ),
        idn_patterns=("RIGOL TECHNOLOGIES,DG4",),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Installable RIGOL DG4000-series source driver for fixed waveforms, "
            "output control, and validated DAC14 arbitrary-wave uploads."
        ),
        wavebench_min_version="0.8.0",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-dg4000",
        version="0.1.0",
        source="entry_point:rigol.dg4202",
        config_fields=(
            "source.resource",
            "source.driver",
            "safety_limits.max_source_vpp",
        ),
    )
