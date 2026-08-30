from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace

import pytest

from wavebench.errors import DataError, InstrumentError
from wavebench.instruments import (
    Availability,
    DG4000ByteOrder,
    DG4000DacBlock,
    Observed,
    PatchAction,
    SourceArbitraryPlaybackMode,
    SourceAmplitudeUnit,
    SourceBasicConfigureRequest,
    SourceCounterMeasurementKind,
    SourceCouplingDimension,
    SourceCouplingParameterKind,
    SourceFieldId,
    SourceFeature,
    SourceFeatureDirection,
    SourceFrequencyMode,
    SourceInputCoupling,
    SourceModulationKind,
    SourceNoiseOverlayScaleKind,
    SourceOutputRequest,
    SourceSemanticQueryPlan,
    SourceSyncPolarity,
    SourceWaveformKind,
)
from wavebench.instruments.api import DriverContext
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.source_extension_capabilities import validate_source_descriptor
from wavebench.logging import CommandLogger
from wavebench.services.source_snapshot_v2 import (
    build_source_snapshot,
    build_source_snapshot_plan,
    new_source_snapshot_context,
)

from wavebench_rigol_dg4000 import descriptor
from wavebench_rigol_dg4000.driver import DG4202Source


class FakeTransport:
    def __init__(self, channel: int = 1, *, model: str = "DG4202") -> None:
        self.channel = channel
        self.model = model
        self.writes: list[str] = []
        self.byte_writes: list[bytes] = []
        self.queries: list[str] = []
        self.query_overrides: dict[str, str] = {}
        self.fail_queries: set[str] = set()
        self.fail_write_commands: set[str] = set()
        self.ignored_write_commands: set[str] = set()
        self.fail_byte_write = False
        self.error_queue = ['0,"No error"']
        self.closed = False
        self.state = {
            "out": "OFF",
            "func": "SIN",
            "freq": 5000.0,
            "volt": 1.0,
            "unit": "VPP",
            "offs": 0.0,
            "phas": 0.0,
            "mode": "SWE",
            "swe": "ON",
            "apply": '"SIN,5.000000E+03,1.000000E+00,0.000000E+00,0.000000E+00"',
            "duty": 50.0,
            "load": "INFINITY",
            "polarity": "NORMAL",
            "noise": "OFF",
            "noise_scale": 10.0,
            "sync": "ON",
            "sync_polarity": "POS",
            "burst": "OFF",
            "burst_mode": "TRIG",
            "burst_cycles": 4,
            "burst_phase": 10.0,
            "burst_internal_period": 0.01,
            "burst_delay": 0.0,
            "burst_gate_polarity": "NORM",
            "burst_trigger_source": "INT",
            "burst_trigger_slope": "POS",
            "burst_trigger_out": "OFF",
            "harmonic_order": 8,
            "harmonic_maximum_order": 16,
            "harmonic_type": "ODD",
            "modulation": "OFF",
            "modulation_type": "AM",
            "marker": "OFF",
            "marker_frequency": 550.0,
            "pulse_hold": "DUTY",
            "pulse_width": 0.0005,
            "pulse_duty": 50.0,
            "pulse_delay": 0.0,
            "pulse_leading": 1.0e-6,
            "pulse_trailing": 2.0e-6,
            "sweep_start": 100.0,
            "sweep_stop": 1000.0,
            "sweep_center": 550.0,
            "sweep_span": 900.0,
            "sweep_spacing": "LIN",
            "sweep_steps": 101.0,
            "sweep_time": 1.0,
            "sweep_start_hold": 0.0,
            "sweep_stop_hold": 0.0,
            "sweep_return_time": 0.0,
            "sweep_trigger_source": "INT",
            "sweep_trigger_slope": "POS",
            "sweep_trigger_out": "OFF",
            "counter": "OFF",
            "counter_measurement": "1.000000E+03,1.000000E-03,4.000000E+01,4.000000E-04,6.000000E-04",
            "counter_coupling": "AC",
            "counter_impedance": "1M",
            "counter_attenuation": "1X",
            "counter_gate_time": "USER1",
            "counter_hf": "OFF",
            "counter_level": 0.0,
            "counter_sensitivity": 50.0,
            "counter_statistics": "OFF",
            "counter_statistics_display": "DIGITAL",
            "coupling": "FREQ:OFF,PHASE:OFF,AMPL:OFF",
            "coupling_base": "CH1",
            "coupling_amplitude_deviation": 0.5,
            "coupling_frequency_deviation": 100.0,
            "coupling_phase_deviation": 10.0,
        }

    def write(self, command: str) -> None:
        self.writes.append(command)
        if command in self.ignored_write_commands:
            return
        self._apply_write(command)
        if command in self.fail_write_commands:
            self.fail_write_commands.remove(command)
            raise InstrumentError(f"injected ambiguous write failure: {command}")

    def _apply_write(self, command: str) -> None:
        prefix = f":SOUR{self.channel}"
        if command.startswith(f"{prefix}:FREQ:MODE "):
            self.state["mode"] = command.split()[-1]
            self.state["swe"] = "OFF" if self.state["mode"] == "FIX" else "ON"
        elif command.startswith(f"{prefix}:FREQ "):
            self.state["freq"] = float(command.split()[-1])
        elif command.startswith(f":OUTP{self.channel} "):
            self.state["out"] = command.split()[-1]
        elif command.startswith(f"{prefix}:FUNC:SHAP "):
            self.state["func"] = command.split()[-1]
        elif command.startswith(f"{prefix}:FUNC:SQU:DCYC "):
            self.state["duty"] = float(command.split()[-1])
        elif command.startswith(f"{prefix}:FUNC "):
            self.state["func"] = command.split()[-1]
        elif command.startswith(f"{prefix}:VOLT:OFFS "):
            self.state["offs"] = float(command.split()[-1])
        elif command.startswith(f"{prefix}:VOLT:UNIT "):
            self.state["unit"] = command.split()[-1]
        elif command.startswith(f"{prefix}:VOLT "):
            self.state["volt"] = float(command.split()[-1])

    def write_bytes(self, command: bytes) -> None:
        self.byte_writes.append(command)
        if self.fail_byte_write:
            self.fail_byte_write = False
            raise InstrumentError("injected ambiguous binary write failure")

    def query(self, command: str) -> str:
        self.queries.append(command)
        if command in self.fail_queries:
            raise InstrumentError(f"injected query failure: {command}")
        if command in self.query_overrides:
            return self.query_overrides[command]
        if command == "SYST:ERR?":
            if self.error_queue:
                return self.error_queue.pop(0)
            return '0,"No error"'
        channel = self.channel
        mapping = {
            "*IDN?": f"RIGOL TECHNOLOGIES,{self.model},<serial>,<firmware>",
            f":OUTP{channel}?": self.state["out"],
            f":SOUR{channel}:FUNC?": self.state["func"],
            f":SOUR{channel}:FREQ?": str(self.state["freq"]),
            f":SOUR{channel}:VOLT?": str(self.state["volt"]),
            f":SOUR{channel}:VOLT:UNIT?": self.state["unit"],
            f":SOUR{channel}:VOLT:OFFS?": str(self.state["offs"]),
            f":SOUR{channel}:PHAS?": str(self.state["phas"]),
            f":SOUR{channel}:FREQ:MODE?": self.state["mode"],
            f":SOUR{channel}:SWE:STAT?": self.state["swe"],
            f":SOUR{channel}:APPL?": self.state["apply"],
            f":SOUR{channel}:FUNC:SQU:DCYC?": str(self.state["duty"]),
            f":OUTP{channel}:LOAD?": self.state["load"],
            f":OUTP{channel}:POL?": self.state["polarity"],
            f":OUTP{channel}:NOIS?": self.state["noise"],
            f":OUTP{channel}:NOIS:SCAL?": str(self.state["noise_scale"]),
            f":OUTP{channel}:SYNC?": self.state["sync"],
            f":OUTP{channel}:SYNC:POL?": self.state["sync_polarity"],
            f":SOUR{channel}:BURS:STAT?": self.state["burst"],
            f":SOUR{channel}:BURS:MODE?": self.state["burst_mode"],
            f":SOUR{channel}:BURS:NCYC?": str(self.state["burst_cycles"]),
            f":SOUR{channel}:BURS:PHAS?": str(self.state["burst_phase"]),
            f":SOUR{channel}:BURS:INT:PER?": str(
                self.state["burst_internal_period"]
            ),
            f":SOUR{channel}:BURS:TDEL?": str(self.state["burst_delay"]),
            f":SOUR{channel}:BURS:GATE:POL?": self.state["burst_gate_polarity"],
            f":SOUR{channel}:BURS:TRIG:SOUR?": self.state["burst_trigger_source"],
            f":SOUR{channel}:BURS:TRIG:SLOP?": self.state["burst_trigger_slope"],
            f":SOUR{channel}:BURS:TRIG:TRIGOUT?": self.state["burst_trigger_out"],
            f":SOUR{channel}:HARM:ORDER?": str(self.state["harmonic_order"]),
            f":SOUR{channel}:HARM:ORDER? MAX": str(
                self.state["harmonic_maximum_order"]
            ),
            f":SOUR{channel}:HARM:TYPE?": self.state["harmonic_type"],
            f":SOUR{channel}:MOD:STAT?": self.state["modulation"],
            f":SOUR{channel}:MOD:TYPE?": self.state["modulation_type"],
            f":SOUR{channel}:MARK:STAT?": self.state["marker"],
            f":SOUR{channel}:MARK:FREQ?": str(self.state["marker_frequency"]),
            f":SOUR{channel}:PULS:HOLD?": self.state["pulse_hold"],
            f":SOUR{channel}:PULS:WIDT?": str(self.state["pulse_width"]),
            f":SOUR{channel}:PULS:DCYC?": str(self.state["pulse_duty"]),
            f":SOUR{channel}:PULS:DEL?": str(self.state["pulse_delay"]),
            f":SOUR{channel}:PULS:TRAN?": str(self.state["pulse_leading"]),
            f":SOUR{channel}:PULS:TRAN:TRA?": str(self.state["pulse_trailing"]),
            f":SOUR{channel}:FREQ:STAR?": str(self.state["sweep_start"]),
            f":SOUR{channel}:FREQ:STOP?": str(self.state["sweep_stop"]),
            f":SOUR{channel}:FREQ:CENT?": str(self.state["sweep_center"]),
            f":SOUR{channel}:FREQ:SPAN?": str(self.state["sweep_span"]),
            f":SOUR{channel}:SWE:SPAC?": self.state["sweep_spacing"],
            f":SOUR{channel}:SWE:STEP?": str(self.state["sweep_steps"]),
            f":SOUR{channel}:SWE:TIME?": str(self.state["sweep_time"]),
            f":SOUR{channel}:SWE:HTIM:STAR?": str(self.state["sweep_start_hold"]),
            f":SOUR{channel}:SWE:HTIM:STOP?": str(self.state["sweep_stop_hold"]),
            f":SOUR{channel}:SWE:RTIM?": str(self.state["sweep_return_time"]),
            f":SOUR{channel}:SWE:TRIG:SOUR?": self.state["sweep_trigger_source"],
            f":SOUR{channel}:SWE:TRIG:SLOP?": self.state["sweep_trigger_slope"],
            f":SOUR{channel}:SWE:TRIG:TRIGOUT?": self.state["sweep_trigger_out"],
            ":COUN?": self.state["counter"],
            ":COUN:MEAS?": self.state["counter_measurement"],
            ":COUN:COUP?": self.state["counter_coupling"],
            ":COUN:IMP?": self.state["counter_impedance"],
            ":COUN:ATT?": self.state["counter_attenuation"],
            ":COUN:GATE?": self.state["counter_gate_time"],
            ":COUN:HF?": self.state["counter_hf"],
            ":COUN:LEVE?": str(self.state["counter_level"]),
            ":COUN:SENS?": str(self.state["counter_sensitivity"]),
            ":COUN:STATI:STAT?": self.state["counter_statistics"],
            ":COUN:STATI:DISP?": self.state["counter_statistics_display"],
            ":COUP?": self.state["coupling"],
            ":COUP:CHANNEL:BASE?": self.state["coupling_base"],
            ":COUP:AMPL:DEV?": str(self.state["coupling_amplitude_deviation"]),
            ":COUP:FREQ:DEV?": str(self.state["coupling_frequency_deviation"]),
            ":COUP:PHAS:DEV?": str(self.state["coupling_phase_deviation"]),
            f":SOUR{channel}:FUNC:USER?": '"USER1"',
            f":SOUR{channel}:ARB:SRAT?": "1000000",
        }
        if command not in mapping:
            self.error_queue.append('-113,"Undefined header"')
            return ""
        return str(mapping[command])

    def close(self) -> None:
        self.closed = True


class DualChannelFakeTransport(FakeTransport):
    def query(self, command: str) -> str:
        translated = command.replace(":SOUR2", ":SOUR1").replace(":OUTP2", ":OUTP1")
        response = super().query(translated)
        self.queries[-1] = command
        return response


def _source_v2_plan(
    *,
    max_queries: int | None = None,
    deadline_monotonic: float | None = None,
) -> tuple[object, SourceSemanticQueryPlan]:
    extensions = descriptor().source_extensions
    assert extensions is not None
    context = new_source_snapshot_context(
        session_epoch="dg4000-source-v2-a0",
        session_health_before="healthy",
        descriptor_extensions=extensions,
        timeout_ms=5_000,
    )
    plan = build_source_snapshot_plan(context)
    if max_queries is not None:
        plan = replace(plan, max_queries=max_queries)
    if deadline_monotonic is not None:
        plan = replace(plan, deadline_monotonic=deadline_monotonic)
    return context, plan


def _prime_v2_write_cache(
    driver: DG4202Source,
    *,
    transport: FakeTransport | None = None,
    channel: int = 1,
) -> None:
    if transport is not None:
        transport.state["mode"] = "FIX"
        transport.state["swe"] = "OFF"
        transport.state["unit"] = "VPP"
    _context, plan = _source_v2_plan()
    driver.execute_source_query_plan_v2(plan)
    assert channel in driver._v2_preflight_snapshots


def _basic_v2_request(channel: int, **values: object) -> SourceBasicConfigureRequest:
    from wavebench.instruments import PatchValue, SourceBasicPatch

    fields = {
        name: PatchValue(PatchAction.SET, value)
        for name, value in values.items()
    }
    return SourceBasicConfigureRequest(channel=channel, patch=SourceBasicPatch(**fields))


def _write_candidate_descriptor():
    item = descriptor()
    assert item.source_extensions is not None
    extensions = replace(
        item.source_extensions,
        features=tuple(
            replace(
                feature,
                directions=(
                    (SourceFeatureDirection.CONFIGURE, SourceFeatureDirection.READ)
                    if feature.feature is SourceFeature.BASIC
                    else (
                        SourceFeatureDirection.DISABLE,
                        SourceFeatureDirection.ENABLE,
                        SourceFeatureDirection.READ,
                    )
                ),
                profile=(
                    replace(
                        feature.profile,
                        live_frequency_configurable=True,
                        live_amplitude_vpp_configurable=True,
                    )
                    if feature.feature is SourceFeature.BASIC
                    else feature.profile
                ),
            )
            if feature.feature in {SourceFeature.BASIC, SourceFeature.OUTPUT}
            else feature
            for feature in item.source_extensions.features
        ),
    )
    return replace(
        item,
        capabilities=(
            *item.capabilities,
            "source.basic_configure_v2",
            "source.basic_live_configure_v2",
            "source.output_v2",
        ),
        source_extensions=extensions,
    )


def test_source_v2_write_candidate_satisfies_core_descriptor_gate() -> None:
    candidate = _write_candidate_descriptor()
    driver = DG4202Source(DualChannelFakeTransport())

    validate_source_descriptor(candidate, driver)
    validate_declared_capabilities(candidate, driver)

    assert "source.basic_configure_v2" in candidate.capabilities
    assert "source.output_v2" in candidate.capabilities
    assert "source.basic_configure_v2" not in descriptor().capabilities


def test_source_v2_basic_and_output_writes_use_only_preflight_cache() -> None:
    transport = DualChannelFakeTransport()
    driver = DG4202Source(transport)
    _prime_v2_write_cache(driver, transport=transport)
    queries_before = list(transport.queries)

    basic = driver.configure_source_basic_v2(
        _basic_v2_request(1, frequency_hz=1_000.0)
    )
    assert basic.output_enabled is False
    assert basic.basic.frequency_hz.value == 1_000.0
    assert transport.writes == [":SOUR1:FREQ 1000"]
    assert transport.queries == queries_before

    enabled = driver.set_source_output_v2(SourceOutputRequest(channel=1, enabled=True))
    assert enabled.enabled is True
    assert enabled.final_amplitude is not None
    assert enabled.final_amplitude.unit is SourceAmplitudeUnit.VPP
    assert enabled.final_offset_v == 0.0
    assert transport.writes[-1] == ":OUTP1 ON"
    assert transport.queries == queries_before


def test_source_v2_basic_write_requires_fresh_preflight_and_safe_fixed_state() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)
    request = _basic_v2_request(1, frequency_hz=1_000.0)

    with pytest.raises(DataError, match="fresh source.snapshot_v2 preflight"):
        driver.configure_source_basic_v2(request)
    assert transport.writes == []

    transport = DualChannelFakeTransport()
    driver = DG4202Source(transport)
    _prime_v2_write_cache(driver, transport=transport)
    basic, output = driver._v2_preflight_snapshots[1]
    driver._v2_preflight_snapshots[1] = (
        basic,
        replace(output, enabled=Observed.value_of(True)),
    )
    with pytest.raises(DataError, match="requires output OFF"):
        driver.configure_source_basic_v2(request)
    assert transport.writes == []

    driver._v2_preflight_snapshots[1] = (
        replace(basic, frequency_mode=Observed.value_of(SourceFrequencyMode.SWEEP)),
        output,
    )
    with pytest.raises(DataError, match="requires fixed-frequency mode"):
        driver.configure_source_basic_v2(request)
    assert transport.writes == []


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("amplitude_vpp", 2.0, ":SOUR1:VOLT 2"),
        ("offset_v", 0.25, ":SOUR1:VOLT:OFFS 0.25"),
        ("square_duty_cycle_percent", 25.0, ":SOUR1:FUNC:SQU:DCYC 25"),
        ("waveform_kind", SourceWaveformKind.RAMP, ":SOUR1:FUNC RAMP"),
    ],
)
def test_source_v2_basic_write_maps_one_supported_field(
    field: str,
    value: object,
    expected: str,
) -> None:
    transport = DualChannelFakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
    if field == "square_duty_cycle_percent":
        transport.state["func"] = "SQU"
    driver = DG4202Source(transport)
    _prime_v2_write_cache(driver, transport=transport)

    result = driver.configure_source_basic_v2(_basic_v2_request(1, **{field: value}))

    assert result.output_enabled is False
    assert transport.writes == [expected]


def test_source_v2_live_frequency_is_one_write_and_never_cycles_output() -> None:
    transport = DualChannelFakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
    transport.state["out"] = "ON"
    driver = DG4202Source(transport)
    _prime_v2_write_cache(driver, transport=transport)

    result = driver.configure_source_basic_live_v2(
        _basic_v2_request(1, frequency_hz=1_000.0)
    )

    assert result.output_enabled is True
    assert transport.writes == [":SOUR1:FREQ 1000"]


def test_source_v2_ambiguous_write_latches_and_invalidates_cache() -> None:
    transport = DualChannelFakeTransport()
    driver = DG4202Source(transport)
    _prime_v2_write_cache(driver, transport=transport)
    transport.fail_write_commands.add(":SOUR1:FREQ 1000")

    with pytest.raises(InstrumentError, match="write result is unknown"):
        driver.configure_source_basic_v2(_basic_v2_request(1, frequency_hz=1_000.0))

    assert driver._v2_preflight_snapshots == {}
    assert driver.set_source_output_v2(
        SourceOutputRequest(channel=1, enabled=False)
    ).enabled is False
    assert transport.writes[-1] == ":OUTP1 OFF"
    _prime_v2_write_cache(driver, transport=transport)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.configure_source_basic_v2(_basic_v2_request(1, frequency_hz=2_000.0))


def test_source_v2_output_off_stays_available_after_write_latch() -> None:
    transport = DualChannelFakeTransport()
    driver = DG4202Source(transport)
    _prime_v2_write_cache(driver, transport=transport)
    driver._configuration_writes_blocked = True

    result = driver.set_source_output_v2(SourceOutputRequest(channel=1, enabled=False))

    assert result.enabled is False
    assert transport.writes == [":OUTP1 OFF"]


def test_source_v2_snapshot_reads_active_sweep_and_never_writes() -> None:
    transport = DualChannelFakeTransport()
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 99
    assert len(execution.items) == 28
    assert len(transport.queries) == 99
    assert transport.queries.count("*IDN?") == 2
    assert ":SOUR1:FREQ:MODE?" not in transport.queries
    assert ":SOUR2:FREQ:MODE?" not in transport.queries
    assert all(command.endswith("?") for command in transport.queries)
    assert transport.writes == []
    assert transport.byte_writes == []
    assert tuple(channel.channel for channel in snapshot.channels) == (1, 2)
    assert snapshot.channels[0].sweep.availability is Availability.VALUE
    assert snapshot.channels[0].sweep.value.start_hz.value == 100.0
    assert snapshot.channels[0].modulation.value.enabled.value is False
    assert snapshot.channels[0].modulation.value.kind.value is SourceModulationKind.AM
    assert snapshot.channels[0].arbitrary.availability is Availability.NOT_APPLICABLE

    observations = tuple(
        observation
        for record in execution.items
        for observation in record.observations
    )
    basic = next(
        item.value
        for item in observations
        if item.field.field is SourceFieldId.BASIC
        and item.field.target.channel == 1
    )
    assert basic.waveform_kind.value is SourceWaveformKind.SINE
    assert basic.frequency_mode.value is SourceFrequencyMode.SWEEP
    assert basic.amplitude.value.unit is SourceAmplitudeUnit.VPP
    output = next(
        item.value
        for item in observations
        if item.field.field is SourceFieldId.OUTPUT
        and item.field.target.channel == 2
    )
    assert output.enabled.value is False
    assert output.display_load.availability is Availability.NOT_QUERIED
    assert output.polarity.availability is Availability.NOT_QUERIED


def test_source_v2_skips_inactive_sweep_without_extra_queries() -> None:
    transport = DualChannelFakeTransport()
    transport.state["swe"] = "OFF"
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 67
    assert len(transport.queries) == 67
    assert all(
        channel.sweep.availability is Availability.NOT_APPLICABLE
        for channel in snapshot.channels
    )
    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_documented_pulse_facet_only_for_pulse_waveforms() -> None:
    transport = DualChannelFakeTransport()
    transport.state.update({"func": "PULSE", "swe": "OFF"})
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 79
    assert len(transport.queries) == 79
    assert all(channel.pulse.availability is Availability.VALUE for channel in snapshot.channels)
    assert snapshot.channels[0].pulse.value.width_s.value == 0.0005
    assert snapshot.channels[0].sweep.availability is Availability.NOT_APPLICABLE
    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_full_burst_facet_only_when_burst_is_enabled() -> None:
    transport = DualChannelFakeTransport()
    transport.state.update({"burst": "ON", "swe": "OFF"})
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 85
    assert len(transport.queries) == 85
    assert all(channel.burst.availability is Availability.VALUE for channel in snapshot.channels)
    assert snapshot.channels[0].burst.value.enabled.value is True
    assert snapshot.channels[0].burst.value.cycles.value == 4
    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_partial_harmonic_facet_for_harmonic_waveforms() -> None:
    transport = DualChannelFakeTransport()
    transport.state.update({"func": "HARMONIC", "swe": "OFF"})
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 73
    assert len(transport.queries) == 73
    assert all(
        channel.harmonics.availability is Availability.VALUE
        for channel in snapshot.channels
    )
    harmonics = snapshot.channels[0].harmonics.value
    assert harmonics.enabled.value is True
    assert harmonics.configured_order.value == 8
    assert harmonics.maximum_supported_order.value == 16
    assert harmonics.components.availability is Availability.NOT_QUERIED
    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_counter_off_without_fabricating_gate_time() -> None:
    transport = DualChannelFakeTransport()
    transport.state["swe"] = "OFF"
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 67
    counter = snapshot.system.value.counters[0]
    assert counter.input_id == "counter"
    assert counter.enabled.value is False
    assert counter.measurements.availability is Availability.NOT_APPLICABLE
    assert counter.coupling.value is SourceInputCoupling.AC
    assert counter.impedance_ohm.value == 1_000_000.0
    assert counter.attenuation.value == 1
    assert counter.gate_time_s.availability is Availability.UNSUPPORTED
    assert counter.trigger_level_v.value == 0.0
    assert counter.statistics_enabled.value is False
    assert transport.queries.count(":COUN?") == 1
    assert ":COUN:MEAS?" not in transport.queries
    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_counter_on_measurement_tuple() -> None:
    transport = DualChannelFakeTransport()
    transport.state.update({"swe": "OFF", "counter": "ON"})
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 68
    counter = snapshot.system.value.counters[0]
    assert counter.enabled.value is True
    assert tuple(item.kind for item in counter.measurements.value) == (
        SourceCounterMeasurementKind.DUTY_PERCENT,
        SourceCounterMeasurementKind.FREQUENCY_HZ,
        SourceCounterMeasurementKind.NEGATIVE_WIDTH_S,
        SourceCounterMeasurementKind.PERIOD_S,
        SourceCounterMeasurementKind.POSITIVE_WIDTH_S,
    )
    assert tuple(item.value for item in counter.measurements.value) == (
        40.0,
        1000.0,
        0.0006,
        0.001,
        0.0004,
    )
    assert transport.queries.count(":COUN:MEAS?") == 1
    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_parameterized_coupling_as_one_channel_set() -> None:
    transport = DualChannelFakeTransport()
    transport.state.update(
        {
            "swe": "OFF",
            "coupling": "FREQ:ON,PHASE:OFF,AMPL:ON",
            "coupling_base": "CH2",
            "coupling_amplitude_deviation": 0.75,
            "coupling_frequency_deviation": 250.0,
            "coupling_phase_deviation": 15.0,
        }
    )
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 67
    coupling = snapshot.cross_channel.value.relations[0]
    assert coupling.channels == (1, 2)
    assert coupling.enabled.value is True
    assert coupling.reference_channel.value == 2
    assert tuple(item.dimension for item in coupling.dimensions) == (
        SourceCouplingDimension.AMPLITUDE,
        SourceCouplingDimension.FREQUENCY,
        SourceCouplingDimension.PHASE,
    )
    assert tuple(item.enabled.value for item in coupling.dimensions) == (True, True, False)
    assert tuple(item.parameter.value.kind for item in coupling.dimensions) == (
        SourceCouplingParameterKind.AMPLITUDE_DEVIATION_VPP,
        SourceCouplingParameterKind.FREQUENCY_DEVIATION_HZ,
        SourceCouplingParameterKind.PHASE_DEVIATION_DEG,
    )
    assert tuple(item.parameter.value.value for item in coupling.dimensions) == (
        0.75,
        250.0,
        15.0,
    )
    assert tuple(
        command
        for command in transport.queries
        if command.startswith(":COUP")
    ) == (
        ":COUP?",
        ":COUP:CHANNEL:BASE?",
        ":COUP:AMPL:DEV?",
        ":COUP:FREQ:DEV?",
        ":COUP:PHAS:DEV?",
    )
    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    (
        (":COUP?", "FREQ:OFF,PHASE:OFF", "must contain"),
        (":COUP?", "FREQ:OFF,PHASE:OFF,FREQ:ON", "unique"),
        (":COUP?", "FREQ:MAYBE,PHASE:OFF,AMPL:OFF", "frequency coupling state"),
        (":COUP:CHANNEL:BASE?", "CH3", "coupling base channel"),
        (":COUP:AMPL:DEV?", "nan", "amplitude coupling deviation"),
        (":COUP:AMPL:DEV?", "21", "amplitude coupling deviation response"),
        (":COUP:FREQ:DEV?", "-1", "frequency coupling deviation response"),
        (":COUP:PHAS:DEV?", "361", "phase coupling deviation response"),
    ),
)
def test_source_v2_rejects_invalid_coupling_readback_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = DualChannelFakeTransport()
    transport.state["swe"] = "OFF"
    transport.query_overrides[command] = response
    _context, plan = _source_v2_plan()

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).execute_source_query_plan_v2(plan)

    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_channel_sync_state_and_polarity_only() -> None:
    transport = DualChannelFakeTransport()
    transport.state.update(
        {
            "swe": "OFF",
            "sync": "0",
            "sync_polarity": "NEGATIVE",
        }
    )
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 67
    assert all(channel.sync.value.enabled.value is False for channel in snapshot.channels)
    assert all(
        channel.sync.value.polarity.value is SourceSyncPolarity.NEGATIVE
        for channel in snapshot.channels
    )
    assert all(
        channel.sync.value.source_channel.availability is Availability.NOT_QUERIED
        for channel in snapshot.channels
    )
    assert transport.queries.count(":OUTP1:SYNC?") == 1
    assert transport.queries.count(":OUTP1:SYNC:POL?") == 1
    assert transport.queries.count(":OUTP2:SYNC?") == 1
    assert transport.queries.count(":OUTP2:SYNC:POL?") == 1
    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    (
        (":OUTP1:SYNC?", "MAYBE", "sync state"),
        (":OUTP1:SYNC:POL?", "BOTH", "sync polarity"),
    ),
)
def test_source_v2_rejects_invalid_sync_readback_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = DualChannelFakeTransport()
    transport.state["swe"] = "OFF"
    transport.query_overrides[command] = response
    _context, plan = _source_v2_plan()

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).execute_source_query_plan_v2(plan)

    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_reads_noise_overlay_without_changing_basic_waveform() -> None:
    transport = DualChannelFakeTransport()
    transport.state.update(
        {
            "swe": "OFF",
            "noise": "ON",
            "noise_scale": 25.0,
        }
    )
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 67
    assert all(
        channel.basic.value.waveform_kind.value is SourceWaveformKind.SINE
        for channel in snapshot.channels
    )
    assert all(
        channel.noise_overlay.value.enabled.value is True
        for channel in snapshot.channels
    )
    scales = snapshot.channels[0].noise_overlay.value.scales.value
    assert len(scales) == 1
    assert scales[0].kind is SourceNoiseOverlayScaleKind.PERCENT
    assert scales[0].value == 25.0
    assert transport.queries.count(":OUTP1:NOIS?") == 1
    assert transport.queries.count(":OUTP1:NOIS:SCAL?") == 1
    assert transport.queries.count(":OUTP2:NOIS?") == 1
    assert transport.queries.count(":OUTP2:NOIS:SCAL?") == 1
    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    (
        (":OUTP1:NOIS?", "MAYBE", "noise overlay state"),
        (":OUTP1:NOIS:SCAL?", "nan", "noise overlay scale"),
        (":OUTP1:NOIS:SCAL?", "51", "noise overlay scale response"),
    ),
)
def test_source_v2_rejects_invalid_noise_overlay_readback_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = DualChannelFakeTransport()
    transport.state["swe"] = "OFF"
    transport.query_overrides[command] = response
    _context, plan = _source_v2_plan()

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).execute_source_query_plan_v2(plan)

    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("response", "expected"),
    (
        ("AM", SourceModulationKind.AM),
        ("ASK", SourceModulationKind.ASK),
        ("FM", SourceModulationKind.FM),
        ("FSK", SourceModulationKind.FSK),
        ("PM", SourceModulationKind.PM),
        ("PSK", SourceModulationKind.PSK),
        ("PWM", SourceModulationKind.PWM),
        ("BPSK", SourceModulationKind.OTHER),
        ("QPSK", SourceModulationKind.OTHER),
        ("3FSK", SourceModulationKind.OTHER),
        ("4FSK", SourceModulationKind.OTHER),
        ("OSK", SourceModulationKind.OTHER),
    ),
)
def test_source_v2_reads_modulation_state_and_type_only(
    response: str,
    expected: SourceModulationKind,
) -> None:
    transport = DualChannelFakeTransport()
    transport.state.update(
        {"swe": "OFF", "modulation": "ON", "modulation_type": response}
    )
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 67
    assert all(channel.modulation.value.enabled.value is True for channel in snapshot.channels)
    assert all(channel.modulation.value.kind.value is expected for channel in snapshot.channels)
    modulation = snapshot.channels[0].modulation.value
    assert modulation.source.availability is Availability.NOT_QUERIED
    assert modulation.parameters.availability is Availability.NOT_QUERIED
    assert modulation.internal_frequency_hz.availability is Availability.NOT_QUERIED
    assert modulation.internal_waveform_kind.availability is Availability.NOT_QUERIED
    assert transport.queries.count(":SOUR1:MOD:STAT?") == 1
    assert transport.queries.count(":SOUR2:MOD:TYPE?") == 1
    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize("waveform", ("USER", "ABSSINE"))
def test_source_v2_reuses_basic_anchor_for_partial_arbitrary_read(
    waveform: str,
) -> None:
    transport = DualChannelFakeTransport()
    transport.state.update({"func": waveform, "swe": "OFF"})
    context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)
    snapshot = build_source_snapshot(
        context=context,
        plan=plan,
        execution=execution,
        session_health_after="healthy",
    )

    assert execution.query_count == 67
    assert all(channel.arbitrary.availability is Availability.VALUE for channel in snapshot.channels)
    arbitrary = snapshot.channels[0].arbitrary.value
    assert arbitrary.selected_waveform_id.value == waveform.lower()
    assert arbitrary.playback_frequency_hz.value == 5000.0
    assert arbitrary.playback_mode.availability is Availability.NOT_QUERIED
    assert arbitrary.sample_rate_hz.availability is Availability.NOT_QUERIED
    assert arbitrary.point_count.availability is Availability.NOT_QUERIED
    assert arbitrary.storage_digest.availability is Availability.NOT_QUERIED
    assert ":SOUR1:FUNC:USER?" not in transport.queries
    assert ":SOUR1:ARB:SRAT?" not in transport.queries
    assert transport.writes == []
    assert transport.byte_writes == []


def test_source_v2_accepts_documented_long_waveform_tokens_without_changing_v1() -> None:
    transport = DualChannelFakeTransport()
    transport.query_overrides[":SOUR1:FUNC?"] = "PULSE"
    _context, plan = _source_v2_plan()

    execution = DG4202Source(transport).execute_source_query_plan_v2(plan)

    basics = tuple(
        observation.value
        for record in execution.items
        for observation in record.observations
        if observation.field.field is SourceFieldId.BASIC
    )
    assert all(item.waveform_kind.value is SourceWaveformKind.PULSE for item in basics)
    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("plan", "message"),
    (
        (_source_v2_plan(max_queries=137)[1], "total query budget"),
        (_source_v2_plan(deadline_monotonic=0.0)[1], "deadline has expired"),
    ),
)
def test_source_v2_rejects_invalid_plan_before_io(
    plan: SourceSemanticQueryPlan,
    message: str,
) -> None:
    transport = DualChannelFakeTransport()

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).execute_source_query_plan_v2(plan)

    assert transport.queries == []
    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("sweep_state", "last_query", "blocked_query"),
    (
        ("OFF", ":COUN:COUP?", ":COUN:IMP?"),
        ("ON", ":SOUR1:FREQ:STAR?", ":SOUR1:FREQ:STOP?"),
    ),
)
def test_source_v2_deadline_stops_aggregate_reads_between_queries(
    monkeypatch: pytest.MonkeyPatch,
    sweep_state: str,
    last_query: str,
    blocked_query: str,
) -> None:
    transport = DualChannelFakeTransport()
    transport.state["swe"] = sweep_state
    _context, plan = _source_v2_plan(deadline_monotonic=100.0)

    def monotonic() -> float:
        return 101.0 if last_query in transport.queries else 99.0

    monkeypatch.setattr("wavebench_rigol_dg4000.driver.time.monotonic", monotonic)

    with pytest.raises(DataError, match="deadline has expired"):
        DG4202Source(transport).execute_source_query_plan_v2(plan)

    assert last_query in transport.queries
    assert blocked_query not in transport.queries
    assert transport.writes == []
    assert transport.byte_writes == []


def test_descriptor_declares_canonical_source_contract_without_io() -> None:
    item = descriptor()

    assert item.driver_id == "rigol.dg4202"
    assert item.distribution == "wavebench-rigol-dg4000"
    assert item.aliases == ()
    assert item.kind == "source"
    assert item.version == "0.7.0"
    assert item.wavebench_min_version == "0.8.25"
    assert "source.snapshot_v2" in item.capabilities
    assert item.source_extensions is not None
    assert item.source_extensions.topology.input_ids == ("counter",)
    assert item.source_extensions.query_contract.max_queries == 138
    _context, plan = _source_v2_plan()
    assert len(plan.items) == 28
    assert sum(query.max_queries for query in plan.items) == 138
    assert next(
        query for query in plan.items if query.fields[0].field is SourceFieldId.COUNTER
    ).target.input_id == "counter"
    assert next(
        query for query in plan.items if query.fields[0].field is SourceFieldId.COUPLING
    ).target.channels == (1, 2)
    arbitrary = next(
        feature
        for feature in item.source_extensions.features
        if feature.feature.value == "arbitrary"
        and feature.channels == (1,)
    )
    assert arbitrary.profile.playback_modes == (SourceArbitraryPlaybackMode.UNKNOWN,)
    assert arbitrary.profile.selection_readable is True
    assert arbitrary.profile.storage_metadata_readable is False
    assert arbitrary.profile.sample_rate_readable is False
    coupling = next(
        feature
        for feature in item.source_extensions.features
        if feature.feature.value == "coupling"
    )
    assert coupling.channels == (1, 2)
    assert coupling.profile.dimensions == tuple(SourceCouplingDimension)
    assert coupling.profile.parameter_kinds == (
        SourceCouplingParameterKind.AMPLITUDE_DEVIATION_VPP,
        SourceCouplingParameterKind.FREQUENCY_DEVIATION_HZ,
        SourceCouplingParameterKind.PHASE_DEVIATION_DEG,
    )
    assert coupling.profile.supported_channel_sets == ((1, 2),)
    assert coupling.profile.global_state_readable is True
    assert coupling.profile.reference_channel_readable is True
    assert coupling.profile.relation_graph_readable is False
    coupling_query = next(
        facet
        for facet in item.source_extensions.query_contract.facets
        if facet.feature.value == "coupling"
    )
    assert coupling_query.fields == (SourceFieldId.COUPLING,)
    assert coupling_query.max_queries == 5
    sync = tuple(
        feature
        for feature in item.source_extensions.features
        if feature.feature.value == "sync"
    )
    assert tuple(feature.channels for feature in sync) == ((1,), (2,))
    assert all(feature.profile.enabled_readable is True for feature in sync)
    assert all(feature.profile.polarity_readable is True for feature in sync)
    assert all(feature.profile.source_channel_readable is False for feature in sync)
    sync_query = next(
        facet
        for facet in item.source_extensions.query_contract.facets
        if facet.feature.value == "sync"
    )
    assert sync_query.fields == (SourceFieldId.SYNC,)
    assert sync_query.max_queries == 2
    noise_overlay = tuple(
        feature
        for feature in item.source_extensions.features
        if feature.feature.value == "noise_overlay"
    )
    assert tuple(feature.channels for feature in noise_overlay) == ((1,), (2,))
    assert all(feature.profile.enabled_readable is True for feature in noise_overlay)
    assert all(
        feature.profile.scale_kinds == (SourceNoiseOverlayScaleKind.PERCENT,)
        for feature in noise_overlay
    )
    noise_overlay_query = next(
        facet
        for facet in item.source_extensions.query_contract.facets
        if facet.feature.value == "noise_overlay"
    )
    assert noise_overlay_query.fields == (SourceFieldId.NOISE_OVERLAY,)
    assert noise_overlay_query.max_queries == 2
    assert "source.channel_profile" in item.capabilities
    assert "source.sweep_profile" in item.capabilities
    assert "source.counter_profile" in item.capabilities
    assert "source.arbitrary_upload" in item.capabilities


def test_channel_profile_is_strict_all_or_nothing_and_query_only() -> None:
    transport = FakeTransport()

    profile = DG4202Source(transport).get_channel_profile(1)

    assert profile.status.channel == 1
    assert profile.load_ohm is None
    assert profile.polarity == "NORMAL"
    assert profile.noise_enabled is False
    assert profile.noise_scale_percent == 10.0
    assert profile.sync_enabled is True
    assert profile.sync_polarity == "POSITIVE"
    assert profile.burst_enabled is False
    assert profile.modulation_enabled is False
    assert profile.modulation_type == "AM"
    assert profile.marker_enabled is False
    assert profile.pulse_hold == "DUTY"
    assert transport.writes == []
    assert transport.byte_writes == []


def test_channel_profile_normalizes_finite_load_and_documented_short_enums() -> None:
    transport = FakeTransport(channel=2)
    transport.state.update(
        {
            "load": "5.000000E+01",
            "polarity": "INV",
            "noise": "1",
            "noise_scale": 25.0,
            "sync": "0",
            "sync_polarity": "NEG",
            "burst": "1",
            "modulation": "1",
            "modulation_type": "4FSK",
            "marker": "1",
            "pulse_hold": "WIDT",
        }
    )

    profile = DG4202Source(transport).get_channel_profile(2)

    assert profile.load_ohm == 50.0
    assert profile.polarity == "INVERTED"
    assert profile.noise_enabled is True
    assert profile.noise_scale_percent == 25.0
    assert profile.sync_enabled is False
    assert profile.sync_polarity == "NEGATIVE"
    assert profile.burst_enabled is True
    assert profile.modulation_enabled is True
    assert profile.modulation_type == "4FSK"
    assert profile.marker_enabled is True
    assert profile.pulse_hold == "WIDTH"
    assert all("1" not in command for command in transport.queries if command != "*IDN?")
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        (":OUTP1:LOAD?", "nan", "output load"),
        (":OUTP1:LOAD?", "10001", "output load"),
        (":OUTP1:POL?", "SIDEWAYS", "output polarity"),
        (":OUTP1:NOIS?", "MAYBE", "noise state"),
        (":OUTP1:NOIS:SCAL?", "nan", "noise scale"),
        (":OUTP1:NOIS:SCAL?", "51", "noise scale"),
        (":OUTP1:SYNC?", "MAYBE", "sync state"),
        (":OUTP1:SYNC:POL?", "BOTH", "sync polarity"),
        (":SOUR1:BURS:STAT?", "MAYBE", "burst state"),
        (":SOUR1:MOD:STAT?", "MAYBE", "modulation state"),
        (":SOUR1:MOD:TYPE?", "UNKNOWN", "modulation type"),
        (":SOUR1:MARK:STAT?", "MAYBE", "marker state"),
        (":SOUR1:PULS:HOLD?", "BOTH", "pulse hold"),
    ],
)
def test_channel_profile_rejects_untrusted_context_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.query_overrides[command] = response

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).get_channel_profile(1)

    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    "command",
    [
        ":OUTP1:LOAD?",
        ":OUTP1:POL?",
        ":OUTP1:NOIS?",
        ":OUTP1:NOIS:SCAL?",
        ":OUTP1:SYNC?",
        ":OUTP1:SYNC:POL?",
        ":SOUR1:BURS:STAT?",
        ":SOUR1:MOD:STAT?",
        ":SOUR1:MOD:TYPE?",
        ":SOUR1:MARK:STAT?",
        ":SOUR1:PULS:HOLD?",
    ],
)
def test_channel_profile_query_failure_returns_no_partial_profile_and_never_writes(
    command: str,
) -> None:
    transport = FakeTransport()
    transport.fail_queries.add(command)

    with pytest.raises(InstrumentError, match="injected query failure"):
        DG4202Source(transport).get_channel_profile(1)

    assert transport.writes == []
    assert transport.byte_writes == []


SWEEP_PROFILE_QUERIES = [
    "*IDN?",
    ":SOUR1:SWE:STAT?",
    ":SOUR1:FREQ:STAR?",
    ":SOUR1:FREQ:STOP?",
    ":SOUR1:FREQ:CENT?",
    ":SOUR1:FREQ:SPAN?",
    ":SOUR1:SWE:SPAC?",
    ":SOUR1:SWE:STEP?",
    ":SOUR1:SWE:TIME?",
    ":SOUR1:SWE:HTIM:STAR?",
    ":SOUR1:SWE:HTIM:STOP?",
    ":SOUR1:SWE:RTIM?",
    ":SOUR1:SWE:TRIG:SOUR?",
    ":SOUR1:SWE:TRIG:SLOP?",
    ":SOUR1:SWE:TRIG:TRIGOUT?",
    ":SOUR1:MARK:STAT?",
    ":SOUR1:MARK:FREQ?",
]


def test_sweep_profile_is_complete_strict_and_query_only() -> None:
    transport = FakeTransport()

    profile = DG4202Source(transport).get_sweep_profile(1)

    assert profile.as_dict() == {
        "channel": 1,
        "enabled": True,
        "start_hz": 100.0,
        "stop_hz": 1000.0,
        "center_hz": 550.0,
        "span_hz": 900.0,
        "spacing": "LINEAR",
        "steps": 101,
        "sweep_time_s": 1.0,
        "start_hold_s": 0.0,
        "stop_hold_s": 0.0,
        "return_time_s": 0.0,
        "trigger_source": "INTERNAL",
        "trigger_slope": "POSITIVE",
        "trigger_out": "OFF",
        "marker_enabled": False,
        "marker_frequency_hz": 550.0,
    }
    assert transport.queries == SWEEP_PROFILE_QUERIES
    assert all(command.endswith("?") for command in transport.queries)
    assert transport.writes == []
    assert transport.byte_writes == []


def test_sweep_profile_normalizes_documented_long_and_short_enums_on_channel_two() -> None:
    transport = FakeTransport(channel=2)
    transport.state.update(
        {
            "swe": "0",
            "sweep_spacing": "LOGARITHMIC",
            "sweep_steps": 2048.0,
            "sweep_time": 300.0,
            "sweep_start_hold": 1.25,
            "sweep_stop_hold": 2.5,
            "sweep_return_time": 3.75,
            "sweep_trigger_source": "MAN",
            "sweep_trigger_slope": "NEGATIVE",
            "sweep_trigger_out": "POS",
            "marker": "1",
            "marker_frequency": 800.0,
        }
    )

    profile = DG4202Source(transport).get_sweep_profile(2)

    assert profile.channel == 2
    assert profile.enabled is False
    assert profile.spacing == "LOGARITHMIC"
    assert profile.steps == 2048
    assert profile.trigger_source == "MANUAL"
    assert profile.trigger_slope == "NEGATIVE"
    assert profile.trigger_out == "POSITIVE"
    assert profile.marker_enabled is True
    assert profile.marker_frequency_hz == 800.0
    assert all(":SOUR1:" not in command for command in transport.queries)
    assert transport.writes == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        (":SOUR1:SWE:STAT?", "MAYBE", "sweep state"),
        (":SOUR1:FREQ:STAR?", "nan", "sweep start frequency"),
        (":SOUR1:FREQ:STOP?", "inf", "sweep stop frequency"),
        (":SOUR1:FREQ:CENT?", "nan", "sweep center frequency"),
        (":SOUR1:FREQ:SPAN?", "nan", "sweep span"),
        (":SOUR1:SWE:SPAC?", "RANDOM", "sweep spacing"),
        (":SOUR1:SWE:STEP?", "2.5", "integer"),
        (":SOUR1:SWE:TIME?", "", "sweep time"),
        (":SOUR1:SWE:TIME?", "nan", "sweep time"),
        (":SOUR1:SWE:HTIM:STAR?", "nan", "sweep start hold"),
        (":SOUR1:SWE:HTIM:STOP?", "nan", "sweep stop hold"),
        (":SOUR1:SWE:RTIM?", "nan", "sweep return time"),
        (":SOUR1:SWE:TRIG:SOUR?", "BUS", "sweep trigger source"),
        (":SOUR1:SWE:TRIG:SLOP?", "BOTH", "sweep trigger slope"),
        (":SOUR1:SWE:TRIG:TRIGOUT?", "HIGH", "sweep trigger output"),
        (":SOUR1:MARK:STAT?", "MAYBE", "marker state"),
        (":SOUR1:MARK:FREQ?", "nan", "marker frequency"),
    ],
)
def test_sweep_profile_rejects_untrusted_responses_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.query_overrides[command] = response

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).get_sweep_profile(1)

    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        (":SOUR1:FREQ:STOP?", "50", "start frequency must not exceed"),
        (":SOUR1:FREQ:CENT?", "600", "center frequency is inconsistent"),
        (":SOUR1:FREQ:SPAN?", "901", "span is inconsistent"),
        (":SOUR1:SWE:STEP?", "1", "steps"),
        (":SOUR1:SWE:TIME?", "0", "sweep time"),
        (":SOUR1:SWE:HTIM:STAR?", "301", "start hold"),
        (":SOUR1:MARK:FREQ?", "1001", "marker frequency"),
    ],
)
def test_sweep_profile_rejects_inconsistent_field_relationships(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.query_overrides[command] = response

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).get_sweep_profile(1)

    assert transport.writes == []
    assert transport.byte_writes == []


def test_sweep_profile_rejects_enabled_marker_with_step_spacing() -> None:
    transport = FakeTransport()
    transport.state["sweep_spacing"] = "STE"
    transport.state["marker"] = "ON"

    with pytest.raises(DataError, match="step spacing"):
        DG4202Source(transport).get_sweep_profile(1)

    assert transport.writes == []


@pytest.mark.parametrize("command", SWEEP_PROFILE_QUERIES)
def test_sweep_profile_query_failure_returns_no_partial_profile_and_never_writes(
    command: str,
) -> None:
    transport = FakeTransport()
    transport.fail_queries.add(command)

    with pytest.raises(InstrumentError, match="injected query failure"):
        DG4202Source(transport).get_sweep_profile(1)

    assert transport.writes == []
    assert transport.byte_writes == []


COUNTER_PROFILE_OFF_QUERIES = [
    "*IDN?",
    ":COUN?",
    ":COUN:COUP?",
    ":COUN:IMP?",
    ":COUN:ATT?",
    ":COUN:GATE?",
    ":COUN:HF?",
    ":COUN:LEVE?",
    ":COUN:SENS?",
    ":COUN:STATI:STAT?",
    ":COUN:STATI:DISP?",
]
COUNTER_PROFILE_ON_QUERIES = [
    "*IDN?",
    ":COUN?",
    ":COUN:MEAS?",
    *COUNTER_PROFILE_OFF_QUERIES[2:],
]


def test_counter_profile_off_is_complete_query_only_and_skips_measurement() -> None:
    transport = FakeTransport()

    profile = DG4202Source(transport).get_counter_profile()

    assert profile.as_dict() == {
        "enabled": False,
        "measurement": None,
        "coupling": "AC",
        "impedance_ohm": 1_000_000.0,
        "attenuation": 1,
        "gate_time": "USER1",
        "high_frequency_rejection_enabled": False,
        "trigger_level_v": 0.0,
        "sensitivity_percent": 50.0,
        "statistics_enabled": False,
        "statistics_display": "DIGITAL",
    }
    assert transport.queries == COUNTER_PROFILE_OFF_QUERIES
    assert all(command.endswith("?") for command in transport.queries)
    assert ":COUN:MEAS?" not in transport.queries
    assert transport.writes == []
    assert transport.byte_writes == []


def test_counter_profile_on_returns_complete_measurement_and_normalizes_responses() -> None:
    transport = FakeTransport()
    transport.state.update(
        {
            "counter": "1",
            "counter_measurement": (
                "1.000099993E+03,9.999000134E-04,1.422600068E+01,"
                "1.422537019E-04,8.576463115E-04"
            ),
            "counter_coupling": "DC",
            "counter_impedance": "5.000000E+01",
            "counter_attenuation": "10",
            "counter_gate_time": "USER6",
            "counter_hf": "ON",
            "counter_level": -2.5,
            "counter_sensitivity": 100.0,
            "counter_statistics": "1",
            "counter_statistics_display": "CURV",
        }
    )

    profile = DG4202Source(transport).get_counter_profile()

    assert profile.enabled is True
    assert profile.measurement is not None
    assert profile.measurement.frequency_hz == pytest.approx(1000.099993)
    assert profile.measurement.period_s == pytest.approx(0.0009999000134)
    assert profile.measurement.duty_cycle_percent == pytest.approx(14.22600068)
    assert profile.measurement.positive_width_s == pytest.approx(0.0001422537019)
    assert profile.measurement.negative_width_s == pytest.approx(0.0008576463115)
    assert profile.coupling == "DC"
    assert profile.impedance_ohm == 50.0
    assert profile.attenuation == 10
    assert profile.gate_time == "USER6"
    assert profile.high_frequency_rejection_enabled is True
    assert profile.trigger_level_v == -2.5
    assert profile.sensitivity_percent == 100.0
    assert profile.statistics_enabled is True
    assert profile.statistics_display == "CURVE"
    assert transport.queries == COUNTER_PROFILE_ON_QUERIES
    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        (":COUN?", "MAYBE", "counter state"),
        (":COUN:COUP?", "GND", "counter coupling"),
        (":COUN:IMP?", "75", "counter impedance"),
        (":COUN:ATT?", "2X", "counter attenuation"),
        (":COUN:GATE?", "USER7", "counter gate time"),
        (":COUN:HF?", "MAYBE", "high-frequency rejection"),
        (":COUN:LEVE?", "nan", "counter trigger level"),
        (":COUN:LEVE?", "2.51", "counter trigger level"),
        (":COUN:SENS?", "inf", "counter sensitivity"),
        (":COUN:SENS?", "101", "counter sensitivity"),
        (":COUN:STATI:STAT?", "MAYBE", "counter statistics state"),
        (":COUN:STATI:DISP?", "GRAPH", "counter statistics display"),
    ],
)
def test_counter_profile_rejects_untrusted_configuration_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.query_overrides[command] = response

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).get_counter_profile()

    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    ("response", "message"),
    [
        ("", "must contain"),
        ("1,2,3,4", "must contain"),
        ("1,2,3,4,5,6", "must contain"),
        ("1,2,,4,5", "must contain"),
        ("nan,0.001,40,0.0004,0.0006", "frequency"),
        ("1000,0.002,40,0.0004,0.0016", "frequency and period"),
        ("1000,0.001,40,0.0005,0.0006", "pulse widths"),
        ("1000,0.001,50,0.0004,0.0006", "duty cycle"),
    ],
)
def test_counter_profile_rejects_invalid_measurement_without_writes(
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.state["counter"] = "ON"
    transport.query_overrides[":COUN:MEAS?"] = response

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).get_counter_profile()

    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize("command", COUNTER_PROFILE_OFF_QUERIES)
def test_counter_profile_off_query_failure_returns_no_partial_profile_and_never_writes(
    command: str,
) -> None:
    transport = FakeTransport()
    transport.fail_queries.add(command)

    with pytest.raises(InstrumentError, match="injected query failure"):
        DG4202Source(transport).get_counter_profile()

    assert transport.writes == []
    assert transport.byte_writes == []


def test_counter_profile_measurement_query_failure_never_writes() -> None:
    transport = FakeTransport()
    transport.state["counter"] = "ON"
    transport.fail_queries.add(":COUN:MEAS?")

    with pytest.raises(InstrumentError, match="injected query failure"):
        DG4202Source(transport).get_counter_profile()

    assert transport.writes == []
    assert transport.byte_writes == []


def test_factory_opens_exactly_one_core_transport_and_satisfies_capabilities() -> None:
    item = descriptor()
    transport = FakeTransport()
    opened = 0

    def open_transport() -> FakeTransport:
        nonlocal opened
        opened += 1
        return transport

    context = DriverContext(
        driver_id=item.driver_id,
        kind=item.kind,
        resource="TCPIP::192.0.2.30::INSTR",
        backend="pyvisa",
        timeout_ms=1000,
        opc_timeout_ms=2000,
        logger=CommandLogger(),
        _transport_factory=open_transport,
        settings={"check_errors": True},
    )

    driver = item.factory(context)
    validate_declared_capabilities(item, driver)

    assert isinstance(driver, DG4202Source)
    assert driver.transport is transport
    assert opened == 1


def test_status_and_fixed_frequency_flow() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    before = driver.get_status(1)
    after = driver.set_frequency(1, 1000.0)
    assert before.frequency_mode == "SWE"
    assert transport.writes[:2] == [":SOUR1:FREQ:MODE FIX", ":SOUR1:FREQ 1000"]
    assert after.frequency_mode == "FIX"
    assert after.frequency_hz == 1000.0


def test_write_readback_accepts_instrument_display_precision() -> None:
    transport = FakeTransport()
    transport.query_overrides[":SOUR1:FREQ?"] = "1.000000E+03"
    driver = DG4202Source(transport)

    status = driver.set_frequency(1, 1000.0004)

    assert status.frequency_hz == 1000.0


def test_write_readback_rejects_material_mismatch() -> None:
    transport = FakeTransport()
    transport.query_overrides[":SOUR1:FREQ?"] = "1.001000E+03"
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="readback mismatch"):
        driver.set_frequency(1, 1000.0)


def test_second_channel_uses_channel_two_scpi_prefixes() -> None:
    transport = FakeTransport(channel=2)
    driver = DG4202Source(transport)

    status = driver.set_frequency(2, 2500.0)

    assert transport.writes[:2] == [":SOUR2:FREQ:MODE FIX", ":SOUR2:FREQ 2500"]
    assert status.channel == 2
    assert status.frequency_hz == 2500.0


def test_function_amplitude_duty_and_output_commands() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    assert driver.set_function(1, "triangle").function == "RAMP"
    assert driver.set_amplitude_vpp(1, 1.25).amplitude == 1.25
    assert driver.set_square_duty_cycle(1, 25.0).square_duty_cycle_percent == 25.0
    assert driver.set_output(1, True).output == "ON"


@pytest.mark.parametrize("channel", [0, 3])
def test_rejects_channels_outside_dg4202_range(channel: int) -> None:
    with pytest.raises(DataError, match="must be 1 or 2"):
        DG4202Source(FakeTransport()).get_status(channel)


def test_rejects_invalid_function_frequency_amplitude_and_duty() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    with pytest.raises(DataError, match="function must be"):
        driver.set_function(1, "invalid")
    with pytest.raises(DataError, match="frequency must be"):
        driver.set_frequency(1, 0.0)
    with pytest.raises(DataError, match="amplitude must be"):
        driver.set_amplitude_vpp(1, 0.0)
    with pytest.raises(DataError, match="duty cycle"):
        driver.set_square_duty_cycle(1, 100.0)
    for invalid in (float("nan"), float("inf"), float("-inf")):
        with pytest.raises(DataError, match="finite"):
            driver.set_frequency(1, invalid)
        with pytest.raises(DataError, match="finite"):
            driver.set_amplitude_vpp(1, invalid)
        with pytest.raises(DataError, match="finite"):
            driver.set_square_duty_cycle(1, invalid)

    assert transport.writes == []
    assert transport.queries == []


@pytest.mark.parametrize(
    ("command", "response", "message"),
    [
        ("*IDN?", "OTHER,DG4202,SN,FW", "manufacturer"),
        ("*IDN?", "RIGOL TECHNOLOGIES,DG9999,SN,FW", "unsupported"),
        (":OUTP1?", "MAYBE", "output state"),
        (":SOUR1:FUNC?", "MYSTERY", "function"),
        (":SOUR1:FREQ?", "nan", "finite"),
        (":SOUR1:VOLT?", "inf", "finite"),
        (":SOUR1:VOLT:UNIT?", "WATTS", "amplitude unit"),
        (":SOUR1:VOLT:OFFS?", "nan", "finite"),
        (":SOUR1:PHAS?", "inf", "finite"),
        (":SOUR1:FREQ:MODE?", "LIST", "frequency mode"),
        (":SOUR1:SWE:STAT?", "UNKNOWN", "sweep state"),
        (":SOUR1:APPL?", '"SIN,1000,1,0"', "APPLy"),
        (":SOUR1:FUNC:SQU:DCYC?", "100", "duty cycle"),
    ],
)
def test_status_rejects_untrusted_responses_without_writes(
    command: str,
    response: str,
    message: str,
) -> None:
    transport = FakeTransport()
    transport.query_overrides[command] = response

    with pytest.raises(DataError, match=message):
        DG4202Source(transport).get_status(1)

    assert transport.writes == []
    assert transport.byte_writes == []


@pytest.mark.parametrize(
    "command",
    [
        "*IDN?",
        ":OUTP1?",
        ":SOUR1:FUNC?",
        ":SOUR1:FREQ?",
        ":SOUR1:VOLT?",
        ":SOUR1:VOLT:UNIT?",
        ":SOUR1:VOLT:OFFS?",
        ":SOUR1:PHAS?",
        ":SOUR1:FREQ:MODE?",
        ":SOUR1:SWE:STAT?",
        ":SOUR1:APPL?",
        ":SOUR1:FUNC:SQU:DCYC?",
    ],
)
def test_status_query_failure_returns_no_partial_snapshot_and_never_writes(
    command: str,
) -> None:
    transport = FakeTransport()
    transport.fail_queries.add(command)

    with pytest.raises(InstrumentError, match="injected query failure"):
        DG4202Source(transport).get_status(1)

    assert transport.writes == []
    assert transport.byte_writes == []


def test_known_unaccepted_model_is_read_only_and_unknown_model_is_rejected() -> None:
    read_transport = FakeTransport(model="DG4102")
    driver = DG4202Source(read_transport)

    assert driver.get_status(1).frequency_hz == 5000.0
    with pytest.raises(DataError, match="writes are not accepted"):
        driver.set_output(1, False)

    assert read_transport.writes == []

    unknown_transport = FakeTransport(model="DG9999")
    with pytest.raises(DataError, match="unsupported"):
        DG4202Source(unknown_transport).get_status(1)
    assert unknown_transport.writes == []


def test_instance_error_check_default_is_respected() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport, check_errors_after_ops=False)

    driver.set_output(1, False)

    assert "SYST:ERR?" not in transport.queries


def test_frequency_readback_mismatch_restores_without_latching() -> None:
    transport = FakeTransport()
    transport.ignored_write_commands.add(":SOUR1:FREQ 1000")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="readback mismatch"):
        driver.set_frequency(1, 1000.0)

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    assert transport.state["mode"] == "SWE"
    transport.ignored_write_commands.clear()
    assert driver.set_frequency(1, 2000.0).frequency_hz == 2000.0


def test_frequency_ambiguous_write_restores_and_latches() -> None:
    transport = FakeTransport()
    transport.fail_write_commands.add(":SOUR1:FREQ 1000")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="ambiguous write"):
        driver.set_frequency(1, 1000.0)

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    assert transport.state["mode"] == "SWE"
    writes_before = list(transport.writes)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_function(1, "square")
    assert transport.writes == writes_before


def test_configuration_recovery_failure_latches() -> None:
    transport = FakeTransport()
    transport.ignored_write_commands.add(":SOUR1:FREQ 1000")
    transport.fail_write_commands.add(":OUTP1 OFF")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="recovery could not be verified"):
        driver.set_frequency(1, 1000.0)

    writes_before = list(transport.writes)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_amplitude_vpp(1, 0.5)
    assert transport.writes == writes_before


def test_amplitude_second_write_ambiguity_restores_and_latches() -> None:
    transport = FakeTransport()
    transport.fail_write_commands.add(":SOUR1:VOLT 0.5")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="ambiguous write"):
        driver.set_amplitude_vpp(1, 0.5)

    assert transport.state["out"] == "OFF"
    assert transport.state["volt"] == 1.0
    assert transport.state["unit"] == "VPP"
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_function(1, "square")


def test_error_queue_failure_restores_without_latching() -> None:
    transport = FakeTransport()
    transport.error_queue = ['-222,"Data out of range"', '0,"No error"']
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="error queue"):
        driver.set_function(1, "square")

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert driver.set_function(1, "ramp").function == "RAMP"


def test_unrestorable_function_snapshot_rejects_before_write() -> None:
    transport = FakeTransport()
    transport.state["func"] = "USER"
    driver = DG4202Source(transport)

    with pytest.raises(DataError, match="restorable basic function"):
        driver.set_frequency(1, 1000.0)

    assert transport.writes == []


def test_fix_mode_disabled_rejects_sweep_snapshot_before_write() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    with pytest.raises(DataError, match="require FIX mode"):
        driver.set_frequency(1, 1000.0, ensure_fix_mode=False)

    assert transport.writes == []


def test_output_ambiguous_write_converges_off_and_latches() -> None:
    transport = FakeTransport()
    transport.fail_write_commands.add(":OUTP1 ON")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="confirmed OFF"):
        driver.set_output(1, True)

    assert transport.state["out"] == "OFF"
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_output(1, True)
    assert driver.set_output(1, False).output == "OFF"


def test_output_readback_mismatch_converges_off_without_latching() -> None:
    transport = FakeTransport()
    transport.ignored_write_commands.add(":OUTP1 ON")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="readback mismatch"):
        driver.set_output(1, True)

    assert transport.state["out"] == "OFF"
    transport.ignored_write_commands.clear()
    assert driver.set_output(1, True).output == "ON"


def test_output_on_rejects_preexisting_error_before_any_write() -> None:
    transport = FakeTransport()
    transport.error_queue = ['-222,"Data out of range"', '0,"No error"']
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="Data out of range"):
        driver.set_output(1, True)

    assert transport.state["out"] == "OFF"
    assert transport.writes == []


def test_latched_emergency_output_off_does_not_require_full_status_snapshot() -> None:
    transport = FakeTransport()
    transport.state["out"] = "ON"
    driver = DG4202Source(transport)
    driver._configuration_writes_blocked = True
    transport.fail_queries.add(":SOUR1:FUNC?")

    with pytest.raises(InstrumentError, match="injected query failure"):
        driver.set_output(1, False)

    assert transport.state["out"] == "OFF"
    assert ":OUTP1 OFF" in transport.writes


def test_public_io_operations_do_not_interleave_between_threads() -> None:
    transport = FakeTransport()
    driver = DG4202Source(transport)

    with ThreadPoolExecutor(max_workers=2) as executor:
        futures = [
            executor.submit(driver.set_frequency, 1, 1000.0),
            executor.submit(driver.set_function, 1, "square"),
        ]
        for future in futures:
            future.result()

    transaction_writes = [
        command
        for command in transport.writes
        if command in {
            ":SOUR1:FREQ:MODE FIX",
            ":SOUR1:FREQ 1000",
            ":SOUR1:FUNC SQU",
        }
    ]
    assert transaction_writes in (
        [":SOUR1:FREQ:MODE FIX", ":SOUR1:FREQ 1000", ":SOUR1:FUNC SQU"],
        [":SOUR1:FUNC SQU", ":SOUR1:FREQ:MODE FIX", ":SOUR1:FREQ 1000"],
    )


def test_arbitrary_upload_uses_validated_public_block_and_exact_command_order() -> None:
    payload = b"\x00\x00\xff\x3f"
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14" + payload,
        points=2,
        data_bytes=len(payload),
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
    driver = DG4202Source(transport)

    status = driver.upload_dg4000_dac14_block(
        channel=1,
        block=block,
        playback_frequency_hz=2000.0,
        amplitude_vpp=1.2,
        offset_v=0.1,
        output_on=True,
    )

    assert transport.byte_writes == [block.command]
    assert transport.writes[:6] == [
        "*CLS",
        ":SOUR1:FREQ 2000",
        ":SOUR1:VOLT:UNIT VPP",
        ":SOUR1:VOLT 1.2",
        ":SOUR1:VOLT:OFFS 0.1",
        ":SOUR1:FUNC:SHAP USER",
    ]
    assert ":OUTP1 ON" in transport.writes
    assert status.function == "USER"


def test_arbitrary_upload_requires_output_off_and_fix_mode_before_any_write() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )

    active = FakeTransport()
    active.state["out"] = "ON"
    active.state["mode"] = "FIX"
    active.state["swe"] = "OFF"
    with pytest.raises(DataError, match="output to be OFF"):
        DG4202Source(active).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )
    assert active.writes == []
    assert active.byte_writes == []

    sweep = FakeTransport()
    with pytest.raises(DataError, match="FIX mode"):
        DG4202Source(sweep).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )
    assert sweep.writes == []
    assert sweep.byte_writes == []


@pytest.mark.parametrize("invalid", [float("nan"), float("inf"), float("-inf")])
def test_arbitrary_upload_rejects_nonfinite_parameters_without_io(invalid: float) -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    driver = DG4202Source(transport)

    for kwargs in (
        {"playback_frequency_hz": invalid, "amplitude_vpp": 1.0},
        {"playback_frequency_hz": 1000.0, "amplitude_vpp": invalid},
        {
            "playback_frequency_hz": 1000.0,
            "amplitude_vpp": 1.0,
            "offset_v": invalid,
        },
    ):
        with pytest.raises(DataError, match="finite"):
            driver.upload_dg4000_dac14_block(channel=1, block=block, **kwargs)

    assert transport.queries == []
    assert transport.writes == []
    assert transport.byte_writes == []


def test_arbitrary_binary_ambiguity_restores_basic_state_and_latches() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
    transport.fail_byte_write = True
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="previous volatile waveform cannot be restored"):
        driver.upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    writes_before = list(transport.writes)
    with pytest.raises(InstrumentError, match="writes are blocked"):
        driver.set_frequency(1, 2000.0)
    assert transport.writes == writes_before


def test_arbitrary_post_binary_failure_restores_offset_and_reports_side_effect() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"
    transport.state["offs"] = 0.25
    transport.ignored_write_commands.add(":SOUR1:VOLT:OFFS 0.1")
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="previous volatile waveform cannot be restored"):
        driver.upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=2000.0,
            amplitude_vpp=1.2,
            offset_v=0.1,
        )

    assert transport.state["out"] == "OFF"
    assert transport.state["func"] == "SIN"
    assert transport.state["freq"] == 5000.0
    assert transport.state["offs"] == 0.25


def test_arbitrary_upload_without_output_request_remains_off() -> None:
    block = DG4000DacBlock(
        command=b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        points=2,
        data_bytes=4,
        byte_order=DG4000ByteOrder.LITTLE,
    )
    transport = FakeTransport()
    transport.state["mode"] = "FIX"
    transport.state["swe"] = "OFF"

    status = DG4202Source(transport).upload_dg4000_dac14_block(
        channel=1,
        block=block,
        playback_frequency_hz=1000.0,
        amplitude_vpp=1.0,
    )

    assert status.output == "OFF"
    assert not any(command == ":OUTP1 ON" for command in transport.writes)


def test_arbitrary_upload_requires_binary_transport() -> None:
    transport = FakeTransport()
    transport.write_bytes = None  # type: ignore[method-assign,assignment]
    block = DG4000DacBlock(
        b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
        2,
        4,
        DG4000ByteOrder.LITTLE,
    )

    with pytest.raises(InstrumentError, match="does not support binary"):
        DG4202Source(transport).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )


@pytest.mark.parametrize(
    "block",
    [
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
            2,
            4,
            DG4000ByteOrder.BIG,
        ),
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00\xff\x3f",
            3,
            4,
            DG4000ByteOrder.LITTLE,
        ),
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00",
            2,
            4,
            DG4000ByteOrder.LITTLE,
        ),
        DG4000DacBlock(
            b":DATA:DAC VOLATILE,#14\x00\x00\x00\x40",
            2,
            4,
            DG4000ByteOrder.LITTLE,
        ),
    ],
)
def test_arbitrary_upload_rejects_unvalidated_block_before_io(
    block: DG4000DacBlock,
) -> None:
    transport = FakeTransport()

    with pytest.raises(
        DataError,
        match="little-endian|byte count|payload length|within 0..16383",
    ):
        DG4202Source(transport).upload_dg4000_dac14_block(
            channel=1,
            block=block,
            playback_frequency_hz=1000.0,
            amplitude_vpp=1.0,
        )

    assert transport.queries == []
    assert transport.writes == []
    assert transport.byte_writes == []


def test_probe_is_query_only_and_continues_across_unsupported_commands() -> None:
    driver = DG4202Source(FakeTransport())

    results = driver.probe_arbitrary_queries(1)

    assert all(item.command.endswith("?") for item in results)
    accepted = {item.label: item.accepted for item in results}
    assert accepted["user_function"]
    assert accepted["arb_sample_rate"]
    assert not accepted["source_data_catalog"]
    with pytest.raises(DataError, match="query-only"):
        driver.probe_arbitrary_queries(1, candidates=(("bad", ":SOUR1:FUNC ARB"),))


def test_error_queue_failure_is_reported_and_close_is_forwarded() -> None:
    transport = FakeTransport()
    transport.error_queue = ['-222,"Data out of range"', '0,"No error"']
    driver = DG4202Source(transport)

    with pytest.raises(InstrumentError, match="Data out of range"):
        driver.assert_no_errors()
    driver.close()

    assert transport.closed
