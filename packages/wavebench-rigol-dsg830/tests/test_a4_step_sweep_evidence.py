from __future__ import annotations

import importlib.util
from dataclasses import replace
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import pytest

from wavebench.config import (
    AutoscaleConfig,
    ConnectionConfig,
    OutputConfig,
    RfSourceConfig,
    ScopeConfig,
    WaveBenchConfig,
    WaveformConfig,
)
from wavebench.instruments.rf_source_extensions import (
    RfFeature,
    RfModulationState,
    RfObserved,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfSourceSnapshot,
    RfSweepConfigureRequest,
    RfSweepDirection,
    RfSweepShape,
    RfSweepSnapshot,
    RfSweepSpacing,
    RfSweepState,
    RfSweepType,
)
from wavebench.transport.session import InstrumentSessionState


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a4_step_sweep_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a4_step_sweep_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    from wavebench_rigol_dsg830.descriptor import descriptor

    return descriptor()


def _historical_pre_promotion_descriptor():
    production = _production_descriptor()
    extensions = production.rf_source_extensions
    assert extensions is not None
    return replace(
        production,
        capabilities=tuple(
            capability
            for capability in production.capabilities
            if capability
            not in {
                "rf_source.modulation_configure",
                "rf_source.modulation_disable",
                "rf_source.modulated_output_enable",
                "rf_source.pulse_output",
                "rf_source.sweep_configure",
            }
        ),
        rf_source_extensions=replace(
            extensions,
            features=tuple(
                feature
                for feature in extensions.features
                if feature.feature
                not in {
                    RfFeature.MODULATED_OUTPUT,
                    RfFeature.MODULATION,
                    RfFeature.PULSE_OUTPUT,
                    RfFeature.SWEEP,
                }
            ),
        ),
    )


def _config(*, access: str = "read_only") -> WaveBenchConfig:
    return WaveBenchConfig(
        connection=ConnectionConfig(
            backend="lan",
            resource="TCPIP::198.51.100.32::INSTR",
            timeout_ms=1_000,
            opc_timeout_ms=2_000,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
        ),
        scope=ScopeConfig(
            driver="rohde-schwarz.rtm2032",
            model_hint=None,
            default_channel=1,
            reset_before_run=False,
            check_errors=False,
            access="read_only",
        ),
        autoscale=AutoscaleConfig(wait_opc=False, check_errors=False),
        waveform=WaveformConfig(format="real", byte_order="lsbf", points="DEF"),
        output=OutputConfig(
            directory=Path("unused"),
            package_naming="timestamp_label",
            save_csv=False,
            save_npy=False,
            save_json=False,
            save_commands_log=False,
            save_screenshot=False,
        ),
        source_path=Path("unused.toml"),
        rf_source=RfSourceConfig(
            driver="rigol.dsg830",
            resource="TCPIP::198.51.100.83::INSTR",
            access=access,  # type: ignore[arg-type]
        ),
    )


def _request() -> RfSweepConfigureRequest:
    return RfSweepConfigureRequest(
        port_id="rf_out",
        start_frequency_hz=1_000_000.0,
        stop_frequency_hz=2_000_000.0,
        points=11,
        dwell_s=20e-3,
    )


def _setup(module):
    return module.A4StepSweepEvidenceSetup(
        port_id="rf_out",
        actual_termination_ohm=50.0,
        installed_options=(),
        request=_request(),
    )


def _rf_snapshot(
    *,
    output_enabled: bool = False,
    modulation: RfModulationState = RfModulationState.DISABLED,
    pulse: RfPulseState = RfPulseState.DISABLED,
    sweep: RfSweepState = RfSweepState.DISABLED,
) -> RfSourceSnapshot:
    return RfSourceSnapshot(
        ports=(
            RfPortSnapshot(
                port_id="rf_out",
                frequency_hz=RfObserved.value_of(1_000_000.0),
                power_dbm=RfObserved.value_of(-50.0),
                output_enabled=RfObserved.value_of(output_enabled),
                modulation=RfObserved.value_of(modulation),
                pulse=RfObserved.value_of(pulse),
                sweep=RfObserved.value_of(sweep),
            ),
        ),
        protection=RfObserved.value_of(RfProtectionStatus(active_codes=())),
    )


def _sweep_snapshot(
    request: RfSweepConfigureRequest,
    *,
    state: RfSweepState = RfSweepState.DISABLED,
) -> RfSweepSnapshot:
    return RfSweepSnapshot(
        port_id=request.port_id,
        sweep_type=RfSweepType.STEP,
        direction=RfSweepDirection.FORWARD,
        shape=RfSweepShape.RAMP,
        spacing=RfSweepSpacing.LINEAR,
        start_frequency_hz=request.start_frequency_hz,
        stop_frequency_hz=request.stop_frequency_hz,
        points=request.points,
        dwell_s=request.dwell_s,
        state=state,
    )


class _FakeTransport:
    def __init__(self, state: InstrumentSessionState, *, access: str) -> None:
        self._state = state
        self._access = access
        self.counters = {
            "query_calls": 0,
            "binary_query_calls": 0,
            "blocked_query_calls": 0,
            "blocked_binary_query_calls": 0,
            "write_requests": 0,
            "write_attempts": 0,
            "write_transmitted": 0,
            "write_completed": 0,
            "write_outcome_unknown": 0,
            "binary_write_requests": 0,
            "binary_write_attempts": 0,
            "binary_write_transmitted": 0,
            "binary_write_completed": 0,
            "binary_write_outcome_unknown": 0,
            "blocked_write_requests": 0,
            "blocked_binary_write_requests": 0,
            "instrument_mutation_writes": 0,
            "instrument_mutation_writes_completed": 0,
            "blocked_session_io": 0,
            "session_health_transitions": 0,
        }

    def add_queries(self, count: int) -> None:
        self.counters["query_calls"] += count

    def add_writes(self, count: int) -> None:
        for key in (
            "write_requests",
            "write_attempts",
            "write_transmitted",
            "write_completed",
            "instrument_mutation_writes",
            "instrument_mutation_writes_completed",
        ):
            self.counters[key] += count

    def audit_snapshot(self) -> dict[str, object]:
        return {
            "access": self._access,
            "counters": dict(self.counters),
            "session": {"health": self._state.health.value},
        }


class _FakeDriver:
    def __init__(
        self,
        *,
        transport: _FakeTransport,
        session_state: InstrumentSessionState,
        snapshots: list[RfSourceSnapshot],
        sweep_snapshot: RfSweepSnapshot,
    ) -> None:
        self.transport = transport
        self.session_state = session_state
        self.snapshots = list(snapshots)
        self.sweep_snapshot = sweep_snapshot
        self.sweep_requests: list[RfSweepConfigureRequest] = []
        self.output_requests: list[object] = []
        self.pulse_requests: list[object] = []
        self.closed = False

    def idn(self) -> str:
        return "RIGOL TECHNOLOGIES,DSG830,PRIVATE,00.01.00"

    def get_rf_snapshot(self) -> RfSourceSnapshot:
        self.transport.add_queries(8)
        return self.snapshots.pop(0)

    def configure_cw(self, request: object) -> None:
        del request

    def set_rf_output(self, request: object) -> None:
        self.output_requests.append(request)

    def get_rf_pulse_snapshot(self, port_id: str) -> object:
        assert port_id == "rf_out"
        return object()

    def configure_rf_pulse(self, request: object) -> None:
        self.pulse_requests.append(request)

    def get_rf_sweep_snapshot(self, port_id: str) -> RfSweepSnapshot:
        assert port_id == "rf_out"
        self.transport.add_queries(9)
        return self.sweep_snapshot

    def configure_rf_sweep(self, request: RfSweepConfigureRequest) -> None:
        self.sweep_requests.append(request)
        self.transport.add_writes(9)

    def a1_snapshot_firmware(self) -> str:
        return "00.01.00"

    def close(self) -> None:
        self.closed = True
        self.session_state.close()


def _preflight(module, monkeypatch, config: WaveBenchConfig, setup):
    production = _historical_pre_promotion_descriptor()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: production)
    monkeypatch.setattr(
        module,
        "_runtime_versions",
        lambda: {"wavebench_version": "0.8.25", "plugin_version": "0.2.0"},
    )
    return production, module.validate_a4_step_sweep_preflight(config, setup)


def _opener(production, driver: _FakeDriver, transport: _FakeTransport, session_state):
    def open_driver(**kwargs):
        assert kwargs["access"] == transport._access
        assert kwargs["read_retry_attempts"] == 0
        assert kwargs["read_retry_delay_ms"] == 0
        return SimpleNamespace(
            descriptor=production,
            driver=driver,
            transport=transport,
            session_state=session_state,
        )

    return open_driver


def test_a4_step_sweep_preflight_creates_only_an_in_memory_sweep_capability(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)

    assert "rf_source.sweep_configure" not in production.capabilities
    assert all(
        feature.feature is not RfFeature.SWEEP
        for feature in production.rf_source_extensions.features
    )
    assert preflight.evidence_descriptor.capabilities == (
        *production.capabilities,
        "rf_source.sweep_configure",
    )
    assert any(
        feature.feature is RfFeature.SWEEP
        for feature in preflight.evidence_descriptor.rf_source_extensions.features
    )
    assert "rf_source.sweep_configure" not in production.capabilities


def test_a4_step_sweep_harness_rejects_a_promoted_production_descriptor(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    promoted = _production_descriptor()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: promoted)
    monkeypatch.setattr(
        module,
        "_runtime_versions",
        lambda: {"wavebench_version": "0.8.25", "plugin_version": "0.2.0"},
    )

    with pytest.raises(module.A4StepSweepPreflightError, match="production_sweep_gate_changed"):
        module.validate_a4_step_sweep_preflight(config, setup)


def test_a4_step_sweep_evidence_configures_once_and_keeps_rf_and_sweep_off(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)
    session_state = InstrumentSessionState()
    transport = _FakeTransport(session_state, access="read_write")
    driver = _FakeDriver(
        transport=transport,
        session_state=session_state,
        snapshots=[_rf_snapshot(), _rf_snapshot(), _rf_snapshot(), _rf_snapshot()],
        sweep_snapshot=_sweep_snapshot(setup.request),
    )

    evidence = module.collect_a4_step_sweep_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert driver.sweep_requests == [setup.request]
    assert driver.output_requests == []
    assert driver.pulse_requests == []
    assert transport.counters["query_calls"] == 41
    assert transport.counters["write_completed"] == 9
    assert evidence["step_sweep_configure"]["operation"] == "rf_source.sweep_configure"
    assert evidence["step_sweep_configure"]["postcondition_sweep_snapshot"]["state"] == "disabled"


def test_a4_step_sweep_evidence_refuses_an_initially_enabled_rf_output(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)
    session_state = InstrumentSessionState()
    transport = _FakeTransport(session_state, access="read_write")
    driver = _FakeDriver(
        transport=transport,
        session_state=session_state,
        snapshots=[_rf_snapshot(output_enabled=True)],
        sweep_snapshot=_sweep_snapshot(setup.request),
    )

    evidence = module.collect_a4_step_sweep_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
    )

    assert evidence["status"] == "failed"
    assert "initial_rf_output_not_off" in evidence["failure_codes"]
    assert driver.sweep_requests == []
    assert driver.output_requests == []
    assert transport.counters["write_requests"] == 0


def test_a4_step_sweep_evidence_does_not_retry_a_failed_sweep_readback(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)
    session_state = InstrumentSessionState()
    transport = _FakeTransport(session_state, access="read_write")
    driver = _FakeDriver(
        transport=transport,
        session_state=session_state,
        snapshots=[_rf_snapshot(), _rf_snapshot(), _rf_snapshot()],
        sweep_snapshot=_sweep_snapshot(setup.request, state=RfSweepState.ENABLED),
    )

    evidence = module.collect_a4_step_sweep_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
    )

    assert evidence["status"] == "failed"
    assert "rf_step_sweep_configure_failed" in evidence["failure_codes"]
    assert driver.sweep_requests == [setup.request]
    assert driver.output_requests == []
    assert transport.counters["write_completed"] == 9


def test_a4_step_sweep_diagnostic_is_read_only_and_keeps_the_baseline(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)
    session_state = InstrumentSessionState()
    transport = _FakeTransport(session_state, access="read_only")
    driver = _FakeDriver(
        transport=transport,
        session_state=session_state,
        snapshots=[_rf_snapshot(), _rf_snapshot()],
        sweep_snapshot=_sweep_snapshot(setup.request),
    )

    evidence = module.collect_a4_step_sweep_diagnostic_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert driver.sweep_requests == []
    assert driver.output_requests == []
    assert transport.counters["query_calls"] == 25
    assert transport.counters["write_requests"] == 0
    assert evidence["step_sweep_profile"]["state"] == "disabled"


def test_a4_step_sweep_setup_rejects_extra_fields_and_output_is_private(tmp_path: Path) -> None:
    module = _script_module()
    setup_path = tmp_path / "setup.toml"
    setup_path.write_text(
        "[a4_step_sweep_evidence]\n"
        'port_id = "rf_out"\n'
        "actual_termination_ohm = 50\n"
        "installed_options = []\n"
        "start_frequency_hz = 1000000\n"
        "stop_frequency_hz = 2000000\n"
        "points = 11\n"
        "dwell_s = 0.02\n"
        "unexpected = true\n",
        encoding="utf-8",
    )
    with pytest.raises(module.A4StepSweepPreflightError, match="a4_step_sweep_evidence_invalid"):
        module.load_a4_step_sweep_evidence_setup(setup_path)

    output_path = tmp_path / "evidence.json"
    with module._open_evidence_output(output_path) as output:
        output.write("{}")
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    with pytest.raises(module.A4StepSweepPreflightError, match="invalid_evidence_output_path"):
        module._open_evidence_output(output_path)


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("DSG830 Sweep type response must be STEP", "diagnostic_step_sweep_type_format_invalid"),
        ("DSG830 Sweep direction response must be FWD", "diagnostic_step_sweep_direction_format_invalid"),
        ("DSG830 Sweep start frequency response has an invalid format", "diagnostic_step_sweep_start_frequency_format_invalid"),
        ("DSG830 Sweep dwell response has an invalid format", "diagnostic_step_sweep_dwell_format_invalid"),
        ("DSG830 Sweep points response is outside the documented range", "diagnostic_step_sweep_points_outside_documented_range"),
        ("unclassified error", "diagnostic_step_sweep_read_failed"),
    ),
)
def test_a4_step_sweep_diagnostic_redacts_parser_failure_details(
    message: str,
    expected: str,
) -> None:
    module = _script_module()

    assert module._diagnostic_sweep_read_failure_code(ValueError(message)) == expected
