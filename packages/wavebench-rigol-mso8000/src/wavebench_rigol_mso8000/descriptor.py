from __future__ import annotations

from wavebench.instruments import InstrumentDescriptor


def _open_driver(context):
    from .driver import MSO8104Scope

    return MSO8104Scope(
        transport=context.open_transport(),
        acquisition_timeout_s=context.opc_timeout_ms / 1000.0,
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
            "scope.fetch_waveform",
            "scope.capture_waveform",
            "scope.capture_waveforms",
        ),
        idn_patterns=("RIGOL TECHNOLOGIES,MSO8104",),
        backends=("pyvisa",),
        resource_schemes=("tcpip", "usb", "gpib"),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "Offline-validated RIGOL MSO8104 identity, input safety, and screen waveform driver."
        ),
        wavebench_min_version="0.8.22",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-mso8000",
        version="0.3.1",
        source="entry_point:rigol.mso8104",
        scope_coupling_policy="switchable-termination",
        config_fields=(
            "connection.backend",
            "connection.resource",
            "scope.driver",
        ),
    )
