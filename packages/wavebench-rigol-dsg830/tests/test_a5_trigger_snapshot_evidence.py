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
    RfExternalGatePolarity,
    RfExternalTriggerEdge,
    RfModulationState,
    RfObserved,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfPulseTriggerMode,
    RfSourceSnapshot,
    RfSweepMode,
    RfSweepState,
    RfSweepTriggerMode,
    RfTriggerSnapshot,
)
from wavebench.transport.session import InstrumentSessionState


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a5_trigger_snapshot_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a5_trigger_snapshot_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    from wavebench_rigol_dsg830.descriptor import descriptor

    return descriptor()


def _config(*, access: str = "read_only", retries: int = 0) -> WaveBenchConfig:
    return WaveBenchConfig(
        connection=ConnectionConfig(
            backend="lan",
            resource="TCPIP::rf::INSTR",
            timeout_ms=1_000,
            opc_timeout_ms=2_000,
            read_retry_attempts=retries,
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
            resource="TCPIP::rf::INSTR",
            access=access,  # type: ignore[arg-type]
        ),
    )


def _setup(module):
    return module.A5TriggerSnapshotEvidenceSetup(port_id="rf_out")


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


def _trigger_snapshot() -> RfTriggerSnapshot:
    return RfTriggerSnapshot(
        port_id="rf_out",
        pulse_trigger_mode=RfPulseTriggerMode.AUTOMATIC,
        pulse_external_trigger_edge=RfExternalTriggerEdge.POSITIVE,
        pulse_external_gate_polarity=RfExternalGatePolarity.NORMAL,
        sweep_mode=RfSweepMode.CONTINUOUS,
        sweep_period_trigger_mode=RfSweepTriggerMode.AUTOMATIC,
        sweep_point_trigger_mode=RfSweepTriggerMode.AUTOMATIC,
    )


class _FakeTransport:
    def __init__(self, module, state: InstrumentSessionState) -> None:
        self._state = state
        self._access = "read_only"
        self.counters = {key: 0 for key in module._AUDIT_COUNTER_KEYS}

    def add_queries(self, count: int) -> None:
        self.counters["query_calls"] += count

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
        trigger_snapshot: RfTriggerSnapshot,
        trigger_error: Exception | None = None,
    ) -> None:
        self.transport = transport
        self.session_state = session_state
        self.snapshots = list(snapshots)
        self.trigger_snapshot = trigger_snapshot
        self.trigger_error = trigger_error
        self.trigger_reads = 0
        self.write_requests: list[object] = []
        self.closed = False

    def idn(self) -> str:
        return "RIGOL TECHNOLOGIES,DSG830,PRIVATE,00.01.00"

    def get_rf_snapshot(self) -> RfSourceSnapshot:
        self.transport.add_queries(8)
        return self.snapshots.pop(0)

    def get_rf_trigger_snapshot(self, port_id: str) -> RfTriggerSnapshot:
        assert port_id == "rf_out"
        self.trigger_reads += 1
        self.transport.add_queries(6)
        if self.trigger_error is not None:
            raise self.trigger_error
        return self.trigger_snapshot

    def configure_cw(self, request: object) -> None:
        self.write_requests.append(request)

    def get_rf_modulation_state(self, port_id: str) -> object:
        assert port_id == "rf_out"
        return object()

    def get_rf_modulation_snapshot(self, port_id: str, kind: object) -> object:
        assert port_id == "rf_out"
        del kind
        return object()

    def configure_rf_modulation(self, request: object) -> None:
        self.write_requests.append(request)

    def get_rf_pulse_snapshot(self, port_id: str) -> object:
        assert port_id == "rf_out"
        return object()

    def configure_rf_pulse(self, request: object) -> None:
        self.write_requests.append(request)

    def get_rf_sweep_snapshot(self, port_id: str) -> object:
        assert port_id == "rf_out"
        return object()

    def configure_rf_sweep(self, request: object) -> None:
        self.write_requests.append(request)

    def set_rf_output(self, request: object) -> None:
        self.write_requests.append(request)

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
    return production, module.validate_a5_trigger_snapshot_preflight(config, setup)


def _opener(production, driver: _FakeDriver, transport: _FakeTransport, state):
    def open_driver(**kwargs):
        assert kwargs["access"] == "read_only"
        assert kwargs["read_retry_attempts"] == 0
        assert kwargs["read_retry_delay_ms"] == 0
        return SimpleNamespace(
            descriptor=production,
            driver=driver,
            transport=transport,
            session_state=state,
        )

    return open_driver


def test_a5_preflight_adds_trigger_snapshot_only_to_an_in_memory_descriptor(monkeypatch) -> None:
    module = _script_module()
    production, preflight = _preflight(module, monkeypatch, _config(), _setup(module))

    assert "rf_source.trigger_snapshot" not in production.capabilities
    assert all(
        feature.feature.value != "trigger" for feature in production.rf_source_extensions.features
    )
    assert preflight.evidence_descriptor.capabilities == (
        *production.capabilities,
        "rf_source.trigger_snapshot",
    )
    assert any(
        feature.feature.value == "trigger" for feature in preflight.evidence_descriptor.rf_source_extensions.features
    )
    assert "rf_source.trigger_snapshot" not in production.capabilities


@pytest.mark.parametrize(
    ("config", "code"),
    (
        (_config(access="read_write"), "rf_source_base_access_must_be_read_only"),
        (_config(retries=1), "rf_source_retries_must_be_disabled"),
    ),
)
def test_a5_preflight_rejects_writable_or_retrying_config(monkeypatch, config, code: str) -> None:
    module = _script_module()
    setup = _setup(module)
    production = _production_descriptor()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: production)
    monkeypatch.setattr(
        module,
        "_runtime_versions",
        lambda: {"wavebench_version": "0.8.25", "plugin_version": "0.2.0"},
    )

    with pytest.raises(module.A5TriggerSnapshotPreflightError, match=code):
        module.validate_a5_trigger_snapshot_preflight(config, setup)


def test_a5_preflight_rejects_a_production_trigger_capability(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    promoted = replace(
        production,
        capabilities=(*production.capabilities, "rf_source.trigger_snapshot"),
    )
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: promoted)
    monkeypatch.setattr(
        module,
        "_runtime_versions",
        lambda: {"wavebench_version": "0.8.25", "plugin_version": "0.2.0"},
    )

    with pytest.raises(module.A5TriggerSnapshotPreflightError, match="production_capabilities_changed"):
        module.validate_a5_trigger_snapshot_preflight(_config(), _setup(module))


def test_a5_diagnostic_reads_once_and_keeps_the_baseline_zero_write(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)
    state = InstrumentSessionState()
    transport = _FakeTransport(module, state)
    driver = _FakeDriver(
        transport=transport,
        session_state=state,
        snapshots=[_rf_snapshot(), _rf_snapshot()],
        trigger_snapshot=_trigger_snapshot(),
    )

    evidence = module.collect_a5_trigger_snapshot_diagnostic_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, state),
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert driver.trigger_reads == 1
    assert driver.write_requests == []
    assert transport.counters["query_calls"] == 22
    assert all(transport.counters[key] == 0 for key in module._WRITE_COUNTER_KEYS)
    assert evidence["trigger_snapshot"]["operation"] == "rf_source.trigger_snapshot"
    assert evidence["rf_audit"]["after_close"]["session_health"] == "closed"
    assert "TCPIP" not in str(evidence)


def test_a5_diagnostic_rejects_an_unsafe_initial_baseline_without_trigger_read(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)
    state = InstrumentSessionState()
    transport = _FakeTransport(module, state)
    driver = _FakeDriver(
        transport=transport,
        session_state=state,
        snapshots=[_rf_snapshot(output_enabled=True)],
        trigger_snapshot=_trigger_snapshot(),
    )

    evidence = module.collect_a5_trigger_snapshot_diagnostic_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, state),
    )

    assert evidence["status"] == "failed"
    assert "initial_rf_output_not_off" in evidence["failure_codes"]
    assert driver.trigger_reads == 0
    assert driver.write_requests == []
    assert transport.counters["query_calls"] == 8
    assert all(transport.counters[key] == 0 for key in module._WRITE_COUNTER_KEYS)


def test_a5_diagnostic_does_not_retry_a_trigger_read_failure(monkeypatch) -> None:
    module = _script_module()
    config = _config()
    setup = _setup(module)
    production, preflight = _preflight(module, monkeypatch, config, setup)
    state = InstrumentSessionState()
    transport = _FakeTransport(module, state)
    driver = _FakeDriver(
        transport=transport,
        session_state=state,
        snapshots=[_rf_snapshot()],
        trigger_snapshot=_trigger_snapshot(),
        trigger_error=ValueError("malformed trigger response"),
    )

    evidence = module.collect_a5_trigger_snapshot_diagnostic_evidence(
        config,
        preflight,
        setup,
        opener=_opener(production, driver, transport, state),
    )

    assert evidence["status"] == "failed"
    assert "trigger_snapshot_read_failed" in evidence["failure_codes"]
    assert driver.trigger_reads == 1
    assert driver.write_requests == []
    assert transport.counters["query_calls"] == 14
    assert all(transport.counters[key] == 0 for key in module._WRITE_COUNTER_KEYS)


def test_a5_setup_is_minimal_and_output_is_private(tmp_path: Path) -> None:
    module = _script_module()
    setup_path = tmp_path / "setup.toml"
    setup_path.write_text(
        "[a5_trigger_snapshot_evidence]\nport_id = \"rf_out\"\nunexpected = true\n",
        encoding="utf-8",
    )
    with pytest.raises(module.A5TriggerSnapshotPreflightError, match="a5_trigger_snapshot_evidence_invalid"):
        module.load_a5_trigger_snapshot_evidence_setup(setup_path)

    output_path = tmp_path / "evidence.json"
    with module._open_evidence_output(output_path) as output:
        output.write("{}")
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    with pytest.raises(module.A5TriggerSnapshotPreflightError, match="invalid_evidence_output_path"):
        module._open_evidence_output(output_path)
