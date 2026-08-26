from __future__ import annotations

from dataclasses import replace
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
    RfModulationState,
    RfObserved,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfSourceSnapshot,
    RfSweepState,
)
from wavebench.transport.session import SessionHealth


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a2_output_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a2_output_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    from wavebench_rigol_dsg830.descriptor import descriptor

    return descriptor()


def _config(
    *,
    rf_resource: str = "TCPIP::198.51.100.83::INSTR",
    scope_resource: str = "TCPIP::198.51.100.32::INSTR",
) -> WaveBenchConfig:
    return WaveBenchConfig(
        connection=ConnectionConfig(
            backend="lan",
            resource=scope_resource,
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
            resource=rf_resource,
            access="read_only",
        ),
    )


def _setup(module):
    return module.A2EvidenceSetup(
        port_id="rf_out",
        actual_termination_ohm=50.0,
        installed_options=(),
        minimum_frequency_hz=9_000.0,
        maximum_frequency_hz=3_000_000_000.0,
        maximum_power_dbm=-50.0,
        scope_observation=module.ScopeObservationSetup(
            ch1=1,
            ch2=2,
            allow_ch2_50ohm=True,
            points="def",
            minimum_observable_vpp_v=0.001,
        ),
    )


def _snapshot(*, output_enabled: bool = False) -> RfSourceSnapshot:
    return RfSourceSnapshot(
        ports=(
            RfPortSnapshot(
                port_id="rf_out",
                frequency_hz=RfObserved.value_of(4_000_000.0),
                power_dbm=RfObserved.value_of(-50.0),
                output_enabled=RfObserved.value_of(output_enabled),
                modulation=RfObserved.value_of(RfModulationState.DISABLED),
                pulse=RfObserved.value_of(RfPulseState.DISABLED),
                sweep=RfObserved.value_of(RfSweepState.DISABLED),
            ),
        ),
        protection=RfObserved.value_of(RfProtectionStatus(active_codes=())),
    )


class _FakeTransport:
    def __init__(self, module) -> None:
        self.module = module
        self.closed = False
        self.query_calls = 0
        self.write_calls = 0

    def audit_snapshot(self) -> dict[str, object]:
        counters = {key: 0 for key in self.module._AUDIT_COUNTER_KEYS}
        counters["query_calls"] = self.query_calls
        for key in (
            "write_requests",
            "write_attempts",
            "write_transmitted",
            "write_completed",
            "instrument_mutation_writes",
            "instrument_mutation_writes_completed",
        ):
            counters[key] = self.write_calls
        return {
            "access": "read_write",
            "counters": counters,
            "session": {"health": "closed" if self.closed else "healthy"},
        }


class _FakeDriver:
    def __init__(self, transport: _FakeTransport, *, output_enabled: bool = False) -> None:
        self.transport = transport
        self.output_enabled = output_enabled
        self.enable_error: BaseException | None = None
        self.calls: list[bool] = []
        self.close_calls = 0

    def a1_snapshot_firmware(self) -> str:
        return "00.01.01"

    def close(self) -> None:
        self.close_calls += 1
        self.transport.closed = True


class _FakeRfSourceService:
    def __init__(
        self,
        *,
        session: _FakeDriver,
        transport: _FakeTransport,
        session_state: SimpleNamespace,
        **_kwargs,
    ) -> None:
        self.driver = session
        self.transport = transport
        self.session_state = session_state

    def snapshot(self) -> RfSourceSnapshot:
        self.transport.query_calls += 8
        return _snapshot(output_enabled=self.driver.output_enabled)

    def set_output_with_artifact(self, request):
        self.driver.calls.append(request.enabled)
        self.transport.query_calls += 16
        self.transport.write_calls += 1
        if request.enabled and self.driver.enable_error is not None:
            raise self.driver.enable_error
        self.driver.output_enabled = request.enabled
        return (
            SimpleNamespace(port_id=request.port_id, enabled=request.enabled, write_completed=True),
            {
                "postcondition_snapshot": {
                    "ports": [
                        {
                            "output_enabled": {
                                "availability": "value",
                                "value": request.enabled,
                            }
                        }
                    ]
                }
            },
        )


def _install_common_patches(monkeypatch, module, production) -> None:
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda driver, **_kwargs: production,
    )
    monkeypatch.setattr(
        module,
        "_runtime_versions",
        lambda: {"wavebench_version": "test", "plugin_version": "test"},
    )
    monkeypatch.setattr(module, "validate_declared_capabilities", lambda *_args: None)
    monkeypatch.setattr(module, "RfSourceService", _FakeRfSourceService)


def _collector(module, production, driver: _FakeDriver):
    calls: list[dict[str, object]] = []
    state = SimpleNamespace(health=SessionHealth.HEALTHY)

    def opener(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            descriptor=production,
            driver=driver,
            transport=driver.transport,
            session_state=state,
        )

    return calls, opener


def test_preflight_keeps_production_output_gate_and_rejects_shared_scope_resource(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    setup = _setup(module)

    preflight = module.validate_a2_preflight(_config(), setup)

    assert preflight.production_descriptor.capabilities == ("rf_source.idn", "rf_source.snapshot")
    assert preflight.evidence_descriptor.capabilities[-1] == "rf_source.output"

    shared = _config(scope_resource="TCPIP::198.51.100.83::INSTR")
    with pytest.raises(module.A2PreflightError, match="scope_resource_must_differ_from_rf_source"):
        module.validate_a2_preflight(shared, setup, scope_config=shared, observe_scope=True)

    changed = replace(production, capabilities=(*production.capabilities, "rf_source.output"))
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: changed)
    with pytest.raises(module.A2PreflightError, match="production_output_gate_changed"):
        module.validate_a2_preflight(_config(), setup)


def test_collects_exact_on_off_evidence_without_promoting_the_descriptor(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    calls, opener = _collector(module, production, driver)
    config = _config()
    setup = _setup(module)
    preflight = module.validate_a2_preflight(config, setup)

    evidence = module.collect_a2_evidence(
        config,
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-26T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert driver.calls == [True, False]
    assert driver.output_enabled is False
    assert evidence["rf_audit"]["before_close"]["counters"]["query_calls"] == 40
    assert evidence["rf_audit"]["before_close"]["counters"]["write_completed"] == 2
    assert evidence["rf_audit"]["after_close"]["session_health"] == "closed"
    assert driver.close_calls == 1
    assert calls[0]["access"] == "read_write"
    assert production.capabilities == ("rf_source.idn", "rf_source.snapshot")
    assert "198.51.100.83" not in str(evidence)


def test_unexpected_initial_on_state_is_failed_but_forces_one_bounded_off(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport, output_enabled=True)
    _, opener = _collector(module, production, driver)
    config = _config()
    preflight = module.validate_a2_preflight(config, _setup(module))

    evidence = module.collect_a2_evidence(config, preflight, _setup(module), opener=opener)

    assert evidence["status"] == "failed"
    assert "initial_rf_output_not_off" in evidence["failure_codes"]
    assert "final_rf_off_not_confirmed" not in evidence["failure_codes"]
    assert driver.calls == [False]
    assert driver.output_enabled is False


def test_enable_failure_accepts_only_core_verified_off_recovery(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    recovery_error = RuntimeError("redacted")
    recovery_error.rf_source_recovery = {
        "status": "off_verified",
        "session_health": "uncertain",
    }
    driver.enable_error = recovery_error
    _, opener = _collector(module, production, driver)
    config = _config()
    preflight = module.validate_a2_preflight(config, _setup(module))

    evidence = module.collect_a2_evidence(config, preflight, _setup(module), opener=opener)

    assert evidence["status"] == "failed"
    assert "rf_output_enable_failed" in evidence["failure_codes"]
    assert "final_rf_off_not_confirmed" not in evidence["failure_codes"]
    assert evidence["output_enable_recovery"]["status"] == "off_verified"
    assert driver.calls == [True]


def test_scope_observation_fetches_each_explicit_channel_once() -> None:
    module = _script_module()
    calls: list[int] = []

    class FakeScopeService:
        def fetch_waveform(self, channel: int):
            calls.append(channel)
            return SimpleNamespace(voltages_v=[-0.01, 0.01])

    observation, warnings = module._collect_scope_observation(
        FakeScopeService(),
        {"1": "DCL", "2": "DC"},
        _setup(module),
    )

    assert calls == [1, 2]
    assert warnings == []
    assert observation["channels"]["2"]["coupling"] == "DC"
    assert observation["channels"]["2"]["signal_detected"] is True


def test_collect_with_scope_observation_fetches_each_channel_once(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    scope_descriptor = SimpleNamespace(
        capabilities=("scope.idn", "scope.channel_coupling", "scope.fetch_waveform")
    )
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda driver, **_kwargs: (
            production if driver == "rigol.dsg830" else scope_descriptor
        ),
    )
    scope_calls: list[int] = []

    class FakeScopeService:
        def fetch_waveform(self, channel: int):
            scope_calls.append(channel)
            return SimpleNamespace(voltages_v=[-0.01, 0.01])

    scope_transport = _FakeTransport(module)
    scope_driver = _FakeDriver(scope_transport)
    monkeypatch.setattr(
        module,
        "_open_scope_observer",
        lambda *_args, **_kwargs: (
            FakeScopeService(),
            scope_driver,
            scope_transport,
            {"1": "DCL", "2": "DC"},
        ),
    )
    rf_transport = _FakeTransport(module)
    rf_driver = _FakeDriver(rf_transport)
    _, opener = _collector(module, production, rf_driver)
    rf_config = _config()
    scope_config = _config(scope_resource="TCPIP::198.51.100.32::INSTR")
    setup = _setup(module)
    preflight = module.validate_a2_preflight(
        rf_config,
        setup,
        scope_config=scope_config,
        observe_scope=True,
    )

    evidence = module.collect_a2_evidence(
        rf_config,
        preflight,
        setup,
        scope_config=scope_config,
        observe_scope=True,
        opener=opener,
    )

    assert evidence["status"] == "passed"
    assert scope_calls == [1, 2]
    assert evidence["scope_observation"]["status"] == "observed"
    assert scope_driver.close_calls == 1


def test_setup_parser_and_evidence_file_are_strict_and_private(tmp_path: Path) -> None:
    module = _script_module()
    setup_path = tmp_path / "a2.toml"
    setup_path.write_text(
        """
[a2_evidence]
port_id = "rf_out"
actual_termination_ohm = 50
installed_options = []
minimum_frequency_hz = 9000
maximum_frequency_hz = 3000000000
maximum_power_dbm = -50

[scope_observation]
ch1 = 1
ch2 = 2
allow_ch2_50ohm = true
points = "def"
minimum_observable_vpp_v = 0.001
""".strip(),
        encoding="utf-8",
    )

    setup = module.load_a2_evidence_setup(setup_path)
    assert setup.maximum_power_dbm == -50.0
    output = module._open_evidence_output(tmp_path / "evidence.json")
    output.close()
    assert stat.S_IMODE((tmp_path / "evidence.json").stat().st_mode) == 0o600

    setup_path.write_text(setup_path.read_text(encoding="utf-8").replace("-50", "-39"), encoding="utf-8")
    with pytest.raises(module.A2PreflightError, match="a2_evidence_power_limit_not_low_enough"):
        module.load_a2_evidence_setup(setup_path)
