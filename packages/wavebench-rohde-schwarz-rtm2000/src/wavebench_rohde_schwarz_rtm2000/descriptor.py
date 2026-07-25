from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor, OptionSpec


def _open_driver(context):
    from .driver import RTM2032Scope

    return RTM2032Scope(
        transport=context.open_transport(),
        check_errors_after_ops=bool(context.settings["check_errors"]),
        long_waveform_timeout_ms=int(context.options["long_waveform_timeout_ms"]),
    )


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rohde-schwarz.rtm2032",
        kind="scope",
        display_name="Rohde & Schwarz RTM2032 Oscilloscope",
        manufacturer="Rohde & Schwarz",
        models=("RTM2032", "RTM2000"),
        aliases=(),
        capabilities=(
            "scope.idn",
            "scope.errors",
            "scope.autoscale",
            "scope.fetch_waveform",
            "scope.capture_waveform",
            "scope.capture_waveforms",
            "scope.screenshot",
            "scope.channel_coupling",
        ),
        idn_patterns=("Rohde&Schwarz,RTM", "Rohde & Schwarz,RTM"),
        backends=(
            "rsinstrument-socket",
            "rsinstrument",
            "rsinstrument-rsvisa",
            "rsinstrument-pyvisa-py",
        ),
        option_specs=(
            OptionSpec(
                "long_waveform_timeout_ms",
                int,
                default=300_000,
                minimum=1_000,
                maximum=3_600_000,
            ),
        ),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary="Installable R&S RTM2000-series scope capture driver.",
        wavebench_min_version="0.8.0",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rohde-schwarz-rtm2000",
        version="0.3.0",
        source="entry_point:rohde-schwarz.rtm2032",
        scope_coupling_policy="switchable-termination",
        config_fields=(
            "connection.backend",
            "connection.resource",
            "scope.driver",
            "scope.options.long_waveform_timeout_ms",
            "waveform.*",
        ),
        resource_schemes=("tcpip",),
    )
