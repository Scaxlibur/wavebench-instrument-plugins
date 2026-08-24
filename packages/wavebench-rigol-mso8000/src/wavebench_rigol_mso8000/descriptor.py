from __future__ import annotations

from wavebench.errors import DataError
from wavebench.instruments import InstrumentDescriptor, OptionSpec


def _strict_bounded_option(
    context,
    name: str,
    *,
    default: int,
    maximum: int,
) -> int:
    value = context.options.get(name, default)
    if type(value) is not int or not 1 <= value <= maximum:
        raise DataError(f"MSO8104 option {name} must be an integer from 1 through {maximum}")
    return value


def _open_driver(context):
    from .driver import MSO8104Scope

    max_total_points = _strict_bounded_option(
        context,
        "max_total_points",
        default=4_000_000,
        maximum=4_000_000,
    )
    max_chunk_points = _strict_bounded_option(
        context,
        "max_chunk_points",
        default=250_000,
        maximum=250_000,
    )
    return MSO8104Scope(
        transport=context.open_transport(),
        acquisition_timeout_s=context.opc_timeout_ms / 1000.0,
        max_total_waveform_points=max_total_points,
        max_byte_points_per_read=max_chunk_points,
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.mso8104",
        kind="scope",
        display_name="RIGOL MSO8104 Oscilloscope",
        manufacturer="RIGOL Technologies",
        models=("MSO8104",),
        aliases=(),
        capabilities=(
            "scope.idn",
            "scope.channel_coupling",
            "scope.autoscale",
            "scope.math_metadata",
            "scope.cursor_readout",
        ),
        idn_patterns=("RIGOL TECHNOLOGIES,MSO8104",),
        backends=("pyvisa",),
        resource_schemes=("tcpip", "usb", "gpib"),
        option_specs=(
            OptionSpec(
                "max_total_points",
                int,
                default=4_000_000,
                minimum=1,
                maximum=4_000_000,
            ),
            OptionSpec(
                "max_chunk_points",
                int,
                default=250_000,
                minimum=1,
                maximum=250_000,
            ),
        ),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Hardware-identified RIGOL MSO8104 identity, safety, autoscale, math, and cursor driver."
        ),
        wavebench_min_version="0.8.22",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-mso8000",
        version="0.8.0",
        source="entry_point:rigol.mso8104",
        scope_coupling_policy="switchable-termination",
        config_fields=(
            "connection.backend",
            "connection.resource",
            "scope.driver",
            "scope.options.max_total_points",
            "scope.options.max_chunk_points",
            "waveform.*",
        ),
    )
