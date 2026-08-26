"""Instrument descriptor for the RIGOL DSG830 plugin."""

from wavebench.instruments.api import InstrumentDescriptor
from wavebench.instruments.rf_source_extensions import (
    RF_SOURCE_CONTRACT_VERSION,
    RfOutputPortProfile,
    RfProtectionConditionPolicy,
    RfSourceDescriptorExtensions,
    RfSourceTopology,
)


def _open_driver(context):
    from .driver import DSG830RfSource

    return DSG830RfSource(transport=context.open_transport())


def descriptor() -> InstrumentDescriptor:
    return InstrumentDescriptor(
        driver_id="rigol.dsg830",
        kind="rf_source",
        display_name="RIGOL DSG830 RF Signal Generator",
        manufacturer="RIGOL Technologies",
        models=("DSG830",),
        aliases=(),
        # A1 hardware evidence is required before production may declare snapshot.
        capabilities=("rf_source.idn",),
        idn_patterns=("RIGOL TECHNOLOGIES,DSG830",),
        backends=("pyvisa",),
        option_specs=(),
        permissions=("instrument.io", "configured-resource-only"),
        factory=_open_driver,
        summary=(
            "RIGOL DSG830 RF signal-source driver; production descriptor exposes identity "
            "only until A1 snapshot evidence is recorded."
        ),
        wavebench_min_version="0.8.25",
        wavebench_max_version="0.9.0",
        distribution="wavebench-rigol-dsg830",
        version="0.2.0",
        source="entry_point:rigol.dsg830",
        config_fields=("rf_source.resource", "rf_source.driver"),
        resource_schemes=("tcpip", "usb"),
        rf_source_extensions=RfSourceDescriptorExtensions(
            contract_version=RF_SOURCE_CONTRACT_VERSION,
            topology=RfSourceTopology(
                (
                    RfOutputPortProfile(
                        port_id="rf_out",
                        frequency_min_hz=9_000.0,
                        frequency_max_hz=3_000_000_000.0,
                        power_min_dbm=-110.0,
                        power_max_dbm=20.0,
                        power_reference_impedance_ohm=50.0,
                    ),
                )
            ),
            protection_conditions=(
                RfProtectionConditionPolicy("alc_heater_detector_30min", True),
                RfProtectionConditionPolicy("alc_unlocked", True),
                RfProtectionConditionPolicy("output_power_protection", True),
            ),
        ),
    )
