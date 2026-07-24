from __future__ import annotations

from wavebench.instruments.api import InstrumentDescriptor


def _open_driver(context):
    from .driver import RTM2032Scope

    return RTM2032Scope(
        transport=context.open_transport(),
        check_errors_after_ops=bool(context.settings["check_errors"]),
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
        backends=("rsinstrument",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary="Installable R&S RTM2000-series scope capture driver.",
        wavebench_min_version="0.7.0",
        wavebench_max_version="1.0.0",
        distribution="wavebench-rohde-schwarz-rtm2000",
        version="0.1.0",
        source="entry_point:rohde-schwarz.rtm2032",
        scope_coupling_policy="switchable-termination",
        config_fields=("connection.resource", "scope.driver", "waveform.*"),
    )
