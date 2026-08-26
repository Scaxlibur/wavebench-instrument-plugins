from __future__ import annotations

import importlib.util
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
    RfPulseConfigureRequest,
    RfPulseMode,
    RfPulsePolarity,
    RfPulseSnapshot,
    RfPulseSource,
    RfPulseState,
    RfSourceSnapshot,
    RfSweepState,
)
from wavebench.transport.session import InstrumentSessionState


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a4_pulse_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a4_pulse_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    from wavebench_rigol_dsg830.descriptor import descriptor

    return descriptor()


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


def _request(*, polarity: RfPulsePolarity = RfPulsePolarity.INVERTED) -> RfPulseConfigureRequest:
    return RfPulseConfigureRequest(
        port_id="rf_out",
        period_s=0.001,
        width_s=0.0001,
        polarity=polarity,
    )


def _setup(module, *, polarity: RfPulsePolarity = RfPulsePolarity.INVERTED):
    return module.A4PulseEvidenceSetup(
        port_id="rf_out",
        actual_termination_ohm=50.0,
        installed_options=(),
        request=_request(polarity=polarity),
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


def _pulse_snapshot(
    request: RfPulseConfigureRequest,
    *,
    polarity: RfPulsePolarity | None = None,
    state: RfPulseState = RfPulseState.DISABLED,
) -> RfPulseSnapshot:
    return RfPulseSnapshot(
        port_id=request.port_id,
        source=RfPulseSource.INTERNAL,
        mode=RfPulseMode.SINGLE,
        period_s=request.period_s,
        width_s=request.width_s,
        polarity=polarity or request.polarity,
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
        pulse_snapshot: RfPulseSnapshot,
    ) -> None:
        self.transport = transport
        self.session_state = session_state
        self.snapshots = list(snapshots)
        self.pulse_snapshot = pulse_snapshot
        self.pulse_requests: list[RfPulseConfigureRequest] = []
        self.output_requests: list[object] = []
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

    def get_rf_pulse_snapshot(self, port_id: str) -> RfPulseSnapshot:
        assert port_id == "rf_out"
        self.transport.add_queries(6)
        return self.pulse_snapshot

    def configure_rf_pulse(self, request: RfPulseConfigureRequest) -> None:
        self.pulse_requests.append(request)
        self.transport.add_writes(6)

    def a1_snapshot_firmware(self) -> str:
        return "00.01.00"

    def close(self) -> None:
        self.closed = True
        self.session_state.close()


def _preflight(module, monkeypatch, config: WaveBenchConfig, setup):
    production = _production_descriptor()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: production)
    monkeypatch.setattr(
        module,
        "_runtime_versions",
        lambda: {"wavebench_version": "0.8.25", "plugin_version": "0.2.0"},
    )
    return production, module.validate_a4_pulse_preflight(config, setup)


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


def test_a4_pulse_preflight_creates_only_an_in_memory_pulse_capability(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)

    assert "rf_source.pulse_configure" not in production.capabilities
    assert all(
        feature.feature is not RfFeature.PULSE
        for feature in production.rf_source_extensions.features
    )
    assert preflight.evidence_descriptor.capabilities == (
        *production.capabilities,
        "rf_source.pulse_configure",
    )
    assert any(
        feature.feature is RfFeature.PULSE
        for feature in preflight.evidence_descriptor.rf_source_extensions.features
    )
    assert "rf_source.pulse_configure" not in production.capabilities


def test_a4_pulse_evidence_configures_once_and_keeps_rf_and_pulse_off(monkeypatch) -> None:
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
        pulse_snapshot=_pulse_snapshot(setup.request),
    )

    evidence = module.collect_a4_pulse_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert driver.pulse_requests == [setup.request]
    assert driver.output_requests == []
    assert driver.closed is True
    assert transport.counters["query_calls"] == 38
    assert transport.counters["write_completed"] == 6
    assert evidence["pulse_configure"]["operation"] == "rf_source.pulse_configure"
    assert evidence["pulse_configure"]["postcondition_pulse_snapshot"]["state"] == "disabled"


def test_a4_pulse_evidence_refuses_an_initially_enabled_rf_output(monkeypatch) -> None:
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
        pulse_snapshot=_pulse_snapshot(setup.request),
    )

    evidence = module.collect_a4_pulse_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
    )

    assert evidence["status"] == "failed"
    assert "initial_rf_output_not_off" in evidence["failure_codes"]
    assert driver.pulse_requests == []
    assert driver.output_requests == []
    assert transport.counters["write_requests"] == 0


def test_a4_pulse_evidence_does_not_retry_a_failed_pulse_readback(monkeypatch) -> None:
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
        pulse_snapshot=_pulse_snapshot(setup.request, polarity=RfPulsePolarity.NORMAL),
    )

    evidence = module.collect_a4_pulse_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
    )

    assert evidence["status"] == "failed"
    assert "rf_pulse_configure_failed" in evidence["failure_codes"]
    assert driver.pulse_requests == [setup.request]
    assert driver.output_requests == []
    assert transport.counters["write_completed"] == 6


def test_a4_pulse_diagnostic_is_read_only_and_keeps_the_baseline(monkeypatch) -> None:
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
        pulse_snapshot=_pulse_snapshot(setup.request),
    )

    evidence = module.collect_a4_pulse_diagnostic_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, session_state),
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert driver.pulse_requests == []
    assert driver.output_requests == []
    assert transport.counters["query_calls"] == 22
    assert transport.counters["write_requests"] == 0
    assert evidence["pulse_profile"]["state"] == "disabled"


def test_a4_pulse_setup_rejects_extra_fields_and_output_is_private(tmp_path: Path) -> None:
    module = _script_module()
    setup_path = tmp_path / "setup.toml"
    setup_path.write_text(
        "[a4_pulse_evidence]\n"
        'port_id = "rf_out"\n'
        "actual_termination_ohm = 50\n"
        "installed_options = []\n"
        "period_s = 0.001\n"
        "width_s = 0.0001\n"
        'polarity = "normal"\n'
        "unexpected = true\n",
        encoding="utf-8",
    )
    with pytest.raises(module.A4PulsePreflightError, match="a4_pulse_evidence_invalid"):
        module.load_a4_pulse_evidence_setup(setup_path)

    output_path = tmp_path / "evidence.json"
    with module._open_evidence_output(output_path) as output:
        output.write("{}")
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    with pytest.raises(module.A4PulsePreflightError, match="invalid_evidence_output_path"):
        module._open_evidence_output(output_path)


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("DSG830 pulse source response must be INT or EXT", "diagnostic_pulse_source_read_invalid"),
        ("DSG830 pulse mode response must be SINGLE or TRAIN", "diagnostic_pulse_mode_read_invalid"),
        ("DSG830 pulse period response has an invalid format", "diagnostic_pulse_period_read_invalid"),
        ("DSG830 pulse width response has an invalid format", "diagnostic_pulse_width_read_invalid"),
        ("DSG830 pulse polarity response must be NORMAL or INVERSE", "diagnostic_pulse_polarity_read_invalid"),
        ("DSG830 pulse state response must be 0 or 1", "diagnostic_pulse_state_read_invalid"),
        ("unclassified error", "diagnostic_pulse_read_failed"),
    ),
)
def test_a4_pulse_diagnostic_redacts_parser_failure_details(message: str, expected: str) -> None:
    module = _script_module()

    assert module._diagnostic_pulse_read_failure_code(ValueError(message)) == expected
