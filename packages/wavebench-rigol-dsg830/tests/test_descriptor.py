from __future__ import annotations

import importlib
import importlib.util

from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.rf_source_extensions import RF_SOURCE_CONTRACT_VERSION


def _descriptor_module():
    spec = importlib.util.find_spec("wavebench_rigol_dsg830.descriptor")
    assert spec is not None
    return importlib.import_module("wavebench_rigol_dsg830.descriptor")


def test_descriptor_declares_production_read_only_contract() -> None:
    descriptor = _descriptor_module().descriptor()

    assert descriptor.driver_id == "rigol.dsg830"
    assert descriptor.kind == "rf_source"
    assert descriptor.display_name == "RIGOL DSG830 RF Signal Generator"
    assert descriptor.manufacturer == "RIGOL Technologies"
    assert descriptor.models == ("DSG830",)
    assert descriptor.aliases == ()
    assert descriptor.capabilities == ("rf_source.idn", "rf_source.snapshot")
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
