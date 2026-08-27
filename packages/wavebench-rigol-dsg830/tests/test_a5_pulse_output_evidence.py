from __future__ import annotations

import importlib
import importlib.util
from dataclasses import dataclass
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
from wavebench.errors import ConfigError
from wavebench.instruments.rf_source_extensions import (
    RfCwRequest,
    RfModulationState,
    RfObserved,
    RfOutputRequest,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseConfigureRequest,
    RfPulseMode,
    RfPulseOutputDirection,
    RfPulseOutputRequest,
    RfPulseOutputSnapshot,
    RfPulsePolarity,
    RfPulseSnapshot,
    RfPulseSource,
    RfPulseState,
    RfSourceSnapshot,
    RfSweepState,
)
from wavebench.transport.session import InstrumentSessionState


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a5_pulse_output_evidence.py"


def _module():
    spec = importlib.util.spec_from_file_location("dsg830_a5_pulse_output_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    return importlib.import_module("wavebench_rigol_dsg830.descriptor").descriptor()


def _scope_descriptor():
    return SimpleNamespace(driver_id="rohde-schwarz.rtm2032", kind="scope", capabilities=())


def _config(*, rf_access: str = "read_only", scope_access: str = "read_only") -> WaveBenchConfig:
    return WaveBenchConfig(
        connection=ConnectionConfig(
            "lan",
            "TCPIP::scope-test::INSTR",
            1_000,
            1_000,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
        ),
        scope=ScopeConfig(
            "rohde-schwarz.rtm2032",
            None,
            1,
            False,
            False,
            access=scope_access,  # type: ignore[arg-type]
        ),
        autoscale=AutoscaleConfig(True, True),
        waveform=WaveformConfig("real", "lsbf", "def"),
        output=OutputConfig(Path("data/raw"), "timestamp_label", True, True, True, True, False),
        source_path=Path("test.toml"),
        rf_source=RfSourceConfig(
            driver="rigol.dsg830",
            resource="TCPIP::rf-test::INSTR",
            access=rf_access,  # type: ignore[arg-type]
        ),
    )


def _audit_counters(*, queries: int, writes: int, write_outcome_unknown: int = 0) -> dict[str, int]:
    return {
        "query_calls": queries,
        "binary_query_calls": 0,
        "blocked_query_calls": 0,
        "blocked_binary_query_calls": 0,
        "write_requests": writes,
        "write_attempts": writes,
        "write_transmitted": writes,
        "write_completed": writes,
        "write_outcome_unknown": write_outcome_unknown,
        "binary_write_requests": 0,
        "binary_write_attempts": 0,
        "binary_write_transmitted": 0,
        "binary_write_completed": 0,
        "binary_write_outcome_unknown": 0,
        "blocked_write_requests": 0,
        "blocked_binary_write_requests": 0,
        "instrument_mutation_writes": writes,
        "instrument_mutation_writes_completed": writes,
        "blocked_session_io": 0,
        "session_health_transitions": 0,
    }


class _AuditTransport:
    def __init__(self, session_state: InstrumentSessionState, *, access: str = "read_write") -> None:
        self._session_state = session_state
        self._access = access
        self.query_calls = 0
        self.write_calls = 0
        self.write_outcome_unknown = 0
        self.closed = False

    def add_queries(self, count: int) -> None:
        self.query_calls += count

    def add_writes(self, count: int) -> None:
        self.write_calls += count

    def close(self) -> None:
        self.closed = True
        self._session_state.close()

    def audit_snapshot(self) -> dict[str, object]:
        return {
            "access": self._access,
            "counters": _audit_counters(
                queries=self.query_calls,
                writes=self.write_calls,
                write_outcome_unknown=self.write_outcome_unknown,
            ),
            "session": {"health": self._session_state.health.value},
        }


@dataclass
class _RfDevice:
    pulse_output_enabled: bool = False
    pulse_period_s: float = 1e-3
    pulse_width_s: float = 100e-6
    pulse_polarity: RfPulsePolarity = RfPulsePolarity.NORMAL
    fail_next_post_enable_snapshot: bool = False


class _FakeRfDriver:
    def __init__(
        self,
        device: _RfDevice,
        transport: _AuditTransport,
        *,
        fail_enable_postcondition: bool = False,
    ) -> None:
        self.device = device
        self.transport = transport
        self.session_state = transport._session_state
        self.fail_enable_postcondition = fail_enable_postcondition

    def close(self) -> None:
        self.transport.close()

    def idn(self) -> str:
        return "RIGOL TECHNOLOGIES,DSG830,PRIVATE,1.0"

    def a1_snapshot_firmware(self) -> str:
        return "1.0"

    def get_rf_snapshot(self) -> RfSourceSnapshot:
        self.transport.add_queries(8)
        if self.device.fail_next_post_enable_snapshot:
            self.device.fail_next_post_enable_snapshot = False
            raise ConfigError("simulated post-enable readback failure")
        return RfSourceSnapshot(
            ports=(
                RfPortSnapshot(
                    port_id="rf_out",
                    frequency_hz=RfObserved.value_of(1_000_000.0),
                    power_dbm=RfObserved.value_of(-50.0),
                    output_enabled=RfObserved.value_of(False),
                    modulation=RfObserved.value_of(RfModulationState.DISABLED),
                    pulse=RfObserved.value_of(RfPulseState.DISABLED),
                    sweep=RfObserved.value_of(RfSweepState.DISABLED),
                ),
            ),
            protection=RfObserved.value_of(RfProtectionStatus(active_codes=())),
        )

    def get_rf_pulse_snapshot(self, port_id: str) -> RfPulseSnapshot:
        assert port_id == "rf_out"
        self.transport.add_queries(6)
        return RfPulseSnapshot(
            port_id=port_id,
            source=RfPulseSource.INTERNAL,
            mode=RfPulseMode.SINGLE,
            period_s=self.device.pulse_period_s,
            width_s=self.device.pulse_width_s,
            polarity=self.device.pulse_polarity,
            state=RfPulseState.DISABLED,
        )

    def configure_rf_pulse(self, request: RfPulseConfigureRequest) -> None:
        assert request.port_id == "rf_out"
        self.transport.add_writes(6)
        self.device.pulse_period_s = request.period_s
        self.device.pulse_width_s = request.width_s
        self.device.pulse_polarity = request.polarity

    def get_rf_pulse_output_snapshot(
        self,
        port_id: str,
        interface_id: str,
    ) -> RfPulseOutputSnapshot:
        assert (port_id, interface_id) == ("rf_out", "pulse_in_out")
        self.transport.add_queries(7)
        return RfPulseOutputSnapshot(
            port_id=port_id,
            interface_id=interface_id,
            direction=RfPulseOutputDirection.OUTPUT,
            enabled=self.device.pulse_output_enabled,
            low_level_v=0.0,
            high_level_v=3.3,
            output_impedance_ohm=600.0,
            source=RfPulseSource.INTERNAL,
            mode=RfPulseMode.SINGLE,
            period_s=self.device.pulse_period_s,
            width_s=self.device.pulse_width_s,
            polarity=self.device.pulse_polarity,
            pulse_state=RfPulseState.DISABLED,
        )

    def set_rf_pulse_output(self, request: RfPulseOutputRequest) -> None:
        assert (request.port_id, request.interface_id) == ("rf_out", "pulse_in_out")
        self.transport.add_writes(1)
        self.device.pulse_output_enabled = request.enabled
        if request.enabled and self.fail_enable_postcondition:
            self.device.fail_next_post_enable_snapshot = True

    def configure_cw(self, request: RfCwRequest) -> None:
        del request

    def set_rf_output(self, request: RfOutputRequest) -> None:
        del request

    def get_rf_modulation_state(self, port_id: str):
        del port_id
        return None

    def get_rf_modulation_snapshot(self, port_id: str, kind: object):
        del port_id, kind
        return None

    def configure_rf_modulation(self, request: object) -> None:
        del request

    def disable_rf_modulation(self, request: object) -> None:
        del request

    def get_rf_sweep_snapshot(self, port_id: str):
        del port_id
        return None

    def configure_rf_sweep(self, request: object) -> None:
        del request


@dataclass
class _ScopeDevice:
    trigger_mode: str = "AUTO"
    fail_primary_auto_restore: bool = False


class _FakeScopeTransport(_AuditTransport):
    def __init__(
        self,
        device: _ScopeDevice,
        session_state: InstrumentSessionState,
        *,
        primary: bool,
    ) -> None:
        super().__init__(session_state)
        self.device = device
        self.primary = primary

    def query(self, command: str) -> str:
        self.add_queries(1)
        if command == "TRIGger:A:SOURce?":
            return "EXT\n"
        if command == "TRIGger:A:MODE?":
            return self.device.trigger_mode + "\n"
        if command == "*OPC?":
            return "1\n"
        raise AssertionError(f"unexpected scope query: {command}")

    def write(self, command: str) -> None:
        self.add_writes(1)
        if command == "TRIGger:A:MODE NORM":
            self.device.trigger_mode = "NORM"
            return
        if command == "SINGle":
            return
        if command == "TRIGger:A:MODE AUTO":
            if self.primary and self.device.fail_primary_auto_restore:
                self.write_outcome_unknown += 1
                raise ConfigError("simulated scope auto restore failure")
            self.device.trigger_mode = "AUTO"
            return
        raise AssertionError(f"unexpected scope write: {command}")


class _FakeScopeDriver:
    def __init__(self, transport: _FakeScopeTransport) -> None:
        self.transport = transport

    def close(self) -> None:
        self.transport.close()


class _Opener:
    def __init__(
        self,
        production,
        scope_descriptor,
        *,
        fail_enable_postcondition: bool = False,
        fail_primary_auto_restore: bool = False,
    ) -> None:
        self.production = production
        self.scope_descriptor = scope_descriptor
        self.rf_device = _RfDevice()
        self.scope_device = _ScopeDevice(fail_primary_auto_restore=fail_primary_auto_restore)
        self.fail_enable_postcondition = fail_enable_postcondition
        self.rf_transports: list[_AuditTransport] = []
        self.scope_transports: list[_FakeScopeTransport] = []

    def __call__(self, *, expected_kind: str, access: str, **kwargs):
        assert access == "read_write"
        assert kwargs["read_retry_attempts"] == 0
        assert kwargs["read_retry_delay_ms"] == 0
        if expected_kind == "rf_source":
            session_state = InstrumentSessionState()
            transport = _AuditTransport(session_state)
            driver = _FakeRfDriver(
                self.rf_device,
                transport,
                fail_enable_postcondition=(
                    self.fail_enable_postcondition and not self.rf_transports
                ),
            )
            self.rf_transports.append(transport)
            return SimpleNamespace(
                descriptor=self.production,
                driver=driver,
                transport=transport,
                session_state=session_state,
            )
        if expected_kind == "scope":
            session_state = InstrumentSessionState()
            transport = _FakeScopeTransport(
                self.scope_device,
                session_state,
                primary=not self.scope_transports,
            )
            driver = _FakeScopeDriver(transport)
            self.scope_transports.append(transport)
            return SimpleNamespace(
                descriptor=self.scope_descriptor,
                driver=driver,
                transport=transport,
                session_state=session_state,
            )
        raise AssertionError(f"unexpected instrument kind: {expected_kind}")


def _patch_preflight(monkeypatch, module, production, scope_descriptor) -> None:
    monkeypatch.setattr(
        module,
        "_runtime_versions",
        lambda: {"wavebench_version": "0.8.25", "plugin_version": "0.2.0"},
    )

    def resolve(driver_id: str, *, expected_kind: str):
        if expected_kind == "rf_source":
            assert driver_id == "rigol.dsg830"
            return production
        assert expected_kind == "scope"
        assert driver_id == "rohde-schwarz.rtm2032"
        return scope_descriptor

    monkeypatch.setattr(module, "resolve_instrument_descriptor", resolve)


def _preflight(module, monkeypatch):
    production = _production_descriptor()
    scope_descriptor = _scope_descriptor()
    _patch_preflight(monkeypatch, module, production, scope_descriptor)
    rf_config = _config()
    scope_config = _config()
    setup = module.A5PulseOutputEvidenceSetup(
        "rf_out",
        "pulse_in_out",
        "dsg830_pulse_in_out_to_rtm2032_ext_trigger_input",
    )
    return (
        rf_config,
        scope_config,
        setup,
        production,
        scope_descriptor,
        module.validate_a5_pulse_output_preflight(rf_config, scope_config, setup),
    )


def test_a5_pulse_output_preflight_creates_only_an_in_memory_capability(monkeypatch) -> None:
    module = _module()
    _, _, _, production, _, preflight = _preflight(module, monkeypatch)

    assert "rf_source.pulse_output" not in production.capabilities
    assert all(
        feature.feature is not module.RfFeature.PULSE_OUTPUT
        for feature in production.rf_source_extensions.features
    )
    assert preflight.evidence_descriptor.capabilities == (*production.capabilities, "rf_source.pulse_output")
    feature = next(
        item
        for item in preflight.evidence_descriptor.rf_source_extensions.features
        if item.feature is module.RfFeature.PULSE_OUTPUT
    )
    assert feature.profile.high_level_v == 3.3
    assert feature.profile.output_impedance_ohm == 600.0


def test_a5_pulse_output_happy_path_has_exact_audits_and_safe_final_state(monkeypatch) -> None:
    module = _module()
    rf_config, scope_config, setup, production, scope_descriptor, preflight = _preflight(
        module,
        monkeypatch,
    )
    opener = _Opener(production, scope_descriptor)

    evidence = module.collect_a5_pulse_output_evidence(
        rf_config,
        scope_config,
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert opener.rf_device.pulse_output_enabled is False
    assert opener.scope_device.trigger_mode == "AUTO"
    assert len(opener.rf_transports) == 2
    assert (opener.rf_transports[0].query_calls, opener.rf_transports[0].write_calls) == (97, 8)
    assert (opener.rf_transports[1].query_calls, opener.rf_transports[1].write_calls) == (15, 0)
    assert len(opener.scope_transports) == 1
    assert (opener.scope_transports[0].query_calls, opener.scope_transports[0].write_calls) == (5, 3)
    assert evidence["pulse_output_enable"]["operation"] == "rf_source.pulse_output_enable"
    assert evidence["pulse_output_disable"]["operation"] == "rf_source.pulse_output_disable"
    assert evidence["final_pulse_output_snapshot"]["enabled"] is False
    assert "TCPIP" not in str(evidence)


def test_a5_pulse_output_recovers_with_a_fresh_session_after_enable_readback_failure(monkeypatch) -> None:
    module = _module()
    rf_config, scope_config, setup, production, scope_descriptor, preflight = _preflight(
        module,
        monkeypatch,
    )
    opener = _Opener(production, scope_descriptor, fail_enable_postcondition=True)

    evidence = module.collect_a5_pulse_output_evidence(
        rf_config,
        scope_config,
        preflight,
        setup,
        opener=opener,
    )

    assert evidence["status"] == "failed"
    assert "pulse_output_enable_failed" in evidence["failure_codes"]
    assert "pulse_output_disable_failed" in evidence["failure_codes"]
    assert "final_pulse_output_off_not_confirmed" not in evidence["failure_codes"]
    assert opener.rf_device.pulse_output_enabled is False
    assert opener.scope_device.trigger_mode == "AUTO"
    assert len(opener.rf_transports) == 2
    assert (opener.rf_transports[1].query_calls, opener.rf_transports[1].write_calls) == (45, 1)
    assert evidence["recovery_pulse_output_disable"]["result"]["write_completed"] is True


def test_a5_pulse_output_scope_auto_recovery_uses_a_fresh_scope_session(monkeypatch) -> None:
    module = _module()
    rf_config, scope_config, setup, production, scope_descriptor, preflight = _preflight(
        module,
        monkeypatch,
    )
    opener = _Opener(production, scope_descriptor, fail_primary_auto_restore=True)

    evidence = module.collect_a5_pulse_output_evidence(
        rf_config,
        scope_config,
        preflight,
        setup,
        opener=opener,
    )

    assert evidence["status"] == "failed"
    assert "scope_trigger_mode_auto_restore_failed" in evidence["failure_codes"]
    assert opener.rf_device.pulse_output_enabled is False
    assert opener.scope_device.trigger_mode == "AUTO"
    assert len(opener.scope_transports) == 2
    assert (opener.scope_transports[1].query_calls, opener.scope_transports[1].write_calls) == (1, 1)
    scope = evidence["scope_observation"]
    assert scope["trigger_mode_restore_session"] == "recovery"


def test_a5_pulse_output_setup_is_strict_and_evidence_output_is_private(tmp_path: Path) -> None:
    module = _module()
    setup_path = tmp_path / "setup.toml"
    setup_path.write_text(
        "[a5_pulse_output_evidence]\n"
        'port_id = "rf_out"\n'
        'interface_id = "pulse_in_out"\n'
        'wiring = "dsg830_pulse_in_out_to_rtm2032_ext_trigger_input"\n'
        "unexpected = true\n",
        encoding="utf-8",
    )
    with pytest.raises(module.A5PulseOutputPreflightError, match="a5_pulse_output_evidence_invalid"):
        module.load_a5_pulse_output_evidence_setup(setup_path)

    output_path = tmp_path / "evidence.json"
    with module._open_evidence_output(output_path) as output:
        output.write("{}")
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    with pytest.raises(module.A5PulseOutputPreflightError, match="invalid_evidence_output_path"):
        module._open_evidence_output(output_path)
