from __future__ import annotations

from wavebench.instruments.api import DriverContext, InstrumentDescriptor


def _open_driver(context: DriverContext):
    from .driver import SDS3000Scope

    return SDS3000Scope(transport=context.open_transport())


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="siglent.sds3000",
        kind="scope",
        display_name="SIGLENT SDS3054 Oscilloscope",
        manufacturer="SIGLENT / Teledyne LeCroy MAUI",
        models=("SDS3054",),
        aliases=(),
        capabilities=(
            "scope.idn",
            "scope.errors",
            "scope.channel_coupling",
            "scope.fetch_waveform",
        ),
        idn_patterns=("*IDN LECROY,SDS3054,", "LECROY,SDS3054,"),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Installable driver for the early SIGLENT SDS3054 running the "
            "Teledyne LeCroy MAUI platform."
        ),
        wavebench_min_version="0.8.22",
        wavebench_max_version="0.9.0",
        distribution="wavebench-siglent-sds3000",
        version="0.1.0",
        source="entry_point:siglent.sds3000",
        scope_coupling_policy="switchable-termination",
        config_fields=("connection.resource", "scope.driver", "waveform.*"),
        resource_schemes=("vicp", "tcpip"),
    )
