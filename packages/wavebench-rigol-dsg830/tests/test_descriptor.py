from __future__ import annotations

import importlib
import importlib.util

from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.rf_source_extensions import (
    RF_SOURCE_CONTRACT_VERSION,
    RfFeature,
    RfFeatureDirection,
    RfCwProfile,
    RfModulationKind,
    RfModulationProfile,
    RfModulationValueUnit,
    RfOutputProfile,
    RfPulseMode,
    RfPulsePolarity,
    RfPulseProfile,
    RfPulseSource,
    RfSweepDirection,
    RfSweepProfile,
    RfSweepShape,
    RfSweepSpacing,
    RfSweepType,
)


def _descriptor_module():
    spec = importlib.util.find_spec("wavebench_rigol_dsg830.descriptor")
    assert spec is not None
    return importlib.import_module("wavebench_rigol_dsg830.descriptor")


def test_descriptor_declares_production_output_contract() -> None:
    descriptor = _descriptor_module().descriptor()

    assert descriptor.driver_id == "rigol.dsg830"
    assert descriptor.kind == "rf_source"
    assert descriptor.display_name == "RIGOL DSG830 RF Signal Generator"
    assert descriptor.manufacturer == "RIGOL Technologies"
    assert descriptor.models == ("DSG830",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == (
        "rf_source.idn",
        "rf_source.snapshot",
        "rf_source.cw_configure",
        "rf_source.output",
        "rf_source.modulation_configure",
        "rf_source.pulse_configure",
        "rf_source.sweep_configure",
    )
    assert descriptor.idn_patterns == ("RIGOL TECHNOLOGIES,DSG830",)
    assert descriptor.backends == ("pyvisa",)
    assert descriptor.resource_schemes == ("tcpip", "usb")
    assert descriptor.option_specs == ()
    assert descriptor.permissions == ("instrument.io", "configured-resource-only")
    assert descriptor.wavebench_min_version == "0.8.25"
    assert descriptor.wavebench_max_version == "0.9.0"
    assert descriptor.distribution == "wavebench-rigol-dsg830"
    assert descriptor.version == "0.2.0"
    assert descriptor.source == "entry_point:rigol.dsg830"
    assert descriptor.config_fields == ("rf_source.resource", "rf_source.driver")
    assert descriptor.rf_source_extensions is not None
    assert descriptor.rf_source_extensions.contract_version == RF_SOURCE_CONTRACT_VERSION
    assert descriptor.rf_source_extensions.topology.ports[0].port_id == "rf_out"
    assert descriptor.rf_source_extensions.topology.ports[0].frequency_min_hz == 9_000.0
    assert descriptor.rf_source_extensions.topology.ports[0].frequency_max_hz == 3_000_000_000.0
    assert descriptor.rf_source_extensions.topology.ports[0].power_min_dbm == -110.0
    assert descriptor.rf_source_extensions.topology.ports[0].power_max_dbm == 20.0
    assert descriptor.rf_source_extensions.topology.ports[0].power_reference_impedance_ohm == 50.0
    assert tuple(item.code for item in descriptor.rf_source_extensions.protection_conditions) == (
        "alc_heater_detector_30min",
        "alc_unlocked",
        "output_power_protection",
    )
    assert len(descriptor.rf_source_extensions.features) == 5
    cw, modulation, output, pulse, sweep = descriptor.rf_source_extensions.features
    assert cw.feature is RfFeature.CW
    assert cw.directions == (RfFeatureDirection.CONFIGURE, RfFeatureDirection.READ)
    assert cw.port_ids == ("rf_out",)
    assert isinstance(cw.profile, RfCwProfile)
    assert cw.profile.frequency_readable is True
    assert cw.profile.power_readable is True
    assert cw.profile.frequency_configurable is True
    assert cw.profile.power_configurable is True
    assert modulation.feature is RfFeature.MODULATION
    assert modulation.directions == (RfFeatureDirection.CONFIGURE, RfFeatureDirection.READ)
    assert modulation.port_ids == ("rf_out",)
    assert isinstance(modulation.profile, RfModulationProfile)
    assert modulation.profile.state_readable is True
    assert modulation.profile.configuration_readable is True
    assert tuple(item.kind for item in modulation.profile.mode_profiles) == (
        RfModulationKind.AM,
        RfModulationKind.FM,
        RfModulationKind.PM,
    )
    am, fm, pm = modulation.profile.mode_profiles
    assert (am.value_unit, am.value_min, am.value_max) == (
        RfModulationValueUnit.PERCENT,
        0.0,
        100.0,
    )
    assert (fm.value_unit, fm.value_min, fm.value_max) == (
        RfModulationValueUnit.HZ,
        0.1,
        1_000_000.0,
    )
    assert (pm.value_unit, pm.value_min, pm.value_max) == (
        RfModulationValueUnit.RAD,
        1.25,
        1.25,
    )
    assert all(
        item.internal_frequency_min_hz == 10.0
        and item.internal_frequency_max_hz == 100_000.0
        for item in modulation.profile.mode_profiles
    )
    assert output.feature is RfFeature.OUTPUT
    assert output.directions == (
        RfFeatureDirection.DISABLE,
        RfFeatureDirection.ENABLE,
        RfFeatureDirection.READ,
    )
    assert output.port_ids == ("rf_out",)
    assert isinstance(output.profile, RfOutputProfile)
    assert output.profile.output_readable is True
    assert pulse.feature is RfFeature.PULSE
    assert pulse.directions == (RfFeatureDirection.CONFIGURE, RfFeatureDirection.READ)
    assert pulse.port_ids == ("rf_out",)
    assert isinstance(pulse.profile, RfPulseProfile)
    assert pulse.profile.state_readable is True
    assert pulse.profile.configuration_readable is True
    assert len(pulse.profile.mode_profiles) == 1
    mode = pulse.profile.mode_profiles[0]
    assert mode.source is RfPulseSource.INTERNAL
    assert mode.mode is RfPulseMode.SINGLE
    assert mode.polarities == (RfPulsePolarity.INVERTED, RfPulsePolarity.NORMAL)
    assert mode.period_min_s == 40e-9
    assert mode.period_max_s == 170.0
    assert mode.width_min_s == 10e-9
    assert mode.width_max_s == 170.0 - 10e-9
    assert mode.minimum_off_time_s == 10e-9
    assert sweep.feature is RfFeature.SWEEP
    assert sweep.directions == (RfFeatureDirection.CONFIGURE, RfFeatureDirection.READ)
    assert sweep.port_ids == ("rf_out",)
    assert isinstance(sweep.profile, RfSweepProfile)
    assert sweep.profile.state_readable is True
    assert sweep.profile.configuration_readable is True
    assert len(sweep.profile.mode_profiles) == 1
    sweep_mode = sweep.profile.mode_profiles[0]
    assert sweep_mode.sweep_type is RfSweepType.STEP
    assert sweep_mode.direction is RfSweepDirection.FORWARD
    assert sweep_mode.shape is RfSweepShape.RAMP
    assert sweep_mode.spacing is RfSweepSpacing.LINEAR
    assert sweep_mode.frequency_min_hz == 9_000.0
    assert sweep_mode.frequency_max_hz == 3_000_000_000.0
    assert sweep_mode.points_min == 2
    assert sweep_mode.points_max == 65_535
    assert sweep_mode.dwell_min_s == 20e-3
    assert sweep_mode.dwell_max_s == 100.0


def test_factory_opens_one_configured_transport_without_instrument_io() -> None:
    descriptor = _descriptor_module().descriptor()
    transport = object()

    class FakeContext:
        def __init__(self) -> None:
            self.open_calls = 0

        def open_transport(self) -> object:
            self.open_calls += 1
            return transport

    context = FakeContext()
    driver = descriptor.factory(context)

    assert context.open_calls == 1
    assert driver.transport is transport
    validate_declared_capabilities(descriptor, driver)
