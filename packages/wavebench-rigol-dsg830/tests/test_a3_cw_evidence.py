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
    RfFeature,
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
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a3_cw_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a3_cw_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    from wavebench_rigol_dsg830.descriptor import descriptor

    return descriptor()


def _pre_a3_descriptor():
    """Rebuild the immutable production contract that the historical A3 harness tests."""

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
                "rf_source.cw_configure",
                "rf_source.modulation_configure",
                "rf_source.pulse_configure",
                "rf_source.sweep_configure",
            }
        ),
        rf_source_extensions=replace(
            extensions,
            features=tuple(
                feature
                for feature in extensions.features
                if feature.feature
                not in {RfFeature.CW, RfFeature.MODULATION, RfFeature.PULSE, RfFeature.SWEEP}
            ),
        ),
    )


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
    return module.A3EvidenceSetup(
        port_id="rf_out",
        actual_termination_ohm=50.0,
        installed_options=(),
        frequency_hz=1_000_000.0,
        power_dbm=-50.0,
        scope_observation=module.ScopeObservationSetup(
            ch2=2,
            allow_ch2_50ohm=True,
            points="def",
            minimum_observable_vpp_v=0.001,
        ),
    )


def _snapshot(
    *,
    frequency_hz: float = 4_000_000.0,
    power_dbm: float = -50.0,
    output_enabled: bool = False,
) -> RfSourceSnapshot:
    return RfSourceSnapshot(
        ports=(
            RfPortSnapshot(
                port_id="rf_out",
                frequency_hz=RfObserved.value_of(frequency_hz),
                power_dbm=RfObserved.value_of(power_dbm),
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
        self.frequency_hz = 4_000_000.0
        self.power_dbm = -50.0
        self.output_enabled = output_enabled
        self.frequency_error: BaseException | None = None
        self.power_error: BaseException | None = None
        self.cw_requests: list[object] = []
        self.output_requests: list[bool] = []
        self.close_calls = 0

    def a1_snapshot_firmware(self) -> str:
        return "00.01.01"

    def close(self) -> None:
        self.close_calls += 1
        self.transport.closed = True


def _artifact(**field: object) -> dict[str, object]:
    return {
        "postcondition_snapshot": {
            "ports": [
                {
                    name: {"availability": "value", "value": value}
                    for name, value in field.items()
                }
            ]
        }
    }


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
        return _snapshot(
            frequency_hz=self.driver.frequency_hz,
            power_dbm=self.driver.power_dbm,
            output_enabled=self.driver.output_enabled,
        )

    def configure_cw_with_artifact(self, request):
        self.driver.cw_requests.append(request)
        self.transport.query_calls += 16
        self.transport.write_calls += 1
        if request.frequency_hz is not None:
            if self.driver.frequency_error is not None:
                raise self.driver.frequency_error
            self.driver.frequency_hz = request.frequency_hz
            return SimpleNamespace(port_id=request.port_id), _artifact(frequency_hz=request.frequency_hz)
        if self.driver.power_error is not None:
            raise self.driver.power_error
        self.driver.power_dbm = request.power_dbm
        return SimpleNamespace(port_id=request.port_id), _artifact(power_dbm=request.power_dbm)

    def set_output_with_artifact(self, request):
        self.driver.output_requests.append(request.enabled)
        self.transport.query_calls += 16
        self.transport.write_calls += 1
        self.driver.output_enabled = request.enabled
        return (
            SimpleNamespace(port_id=request.port_id, enabled=request.enabled, write_completed=True),
            _artifact(output_enabled=request.enabled),
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


def _collector(production, driver: _FakeDriver):
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


def test_preflight_keeps_production_cw_gate_and_rejects_shared_scope_resource(monkeypatch) -> None:
    module = _script_module()
    production = _pre_a3_descriptor()
    _install_common_patches(monkeypatch, module, production)
    scope_descriptor = SimpleNamespace(
        capabilities=("scope.idn", "scope.channel_coupling", "scope.fetch_waveform")
    )
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda driver, **_kwargs: production if driver == "rigol.dsg830" else scope_descriptor,
    )
    setup = _setup(module)

    preflight = module.validate_a3_preflight(_config(), setup, scope_config=_config())

    assert preflight.production_descriptor.capabilities == (
        "rf_source.idn",
        "rf_source.snapshot",
        "rf_source.output",
    )
    assert preflight.evidence_descriptor.capabilities[-1] == "rf_source.cw_configure"
    assert preflight.evidence_descriptor.rf_source_extensions is not None
    assert tuple(
        feature.feature for feature in preflight.evidence_descriptor.rf_source_extensions.features
    ) == (RfFeature.CW, RfFeature.OUTPUT)

    shared = _config(scope_resource="TCPIP::198.51.100.83::INSTR")
    with pytest.raises(module.A3PreflightError, match="scope_resource_must_differ_from_rf_source"):
        module.validate_a3_preflight(shared, setup, scope_config=shared)

    changed = preflight.evidence_descriptor
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: changed)
    with pytest.raises(module.A3PreflightError, match="production_cw_gate_changed"):
        module.validate_a3_preflight(_config(), setup, scope_config=_config())


def test_collects_exact_cw_loopback_evidence_without_promoting_descriptor(monkeypatch) -> None:
    module = _script_module()
    production = _pre_a3_descriptor()
    _install_common_patches(monkeypatch, module, production)
    scope_descriptor = SimpleNamespace(
        capabilities=("scope.idn", "scope.channel_coupling", "scope.fetch_waveform")
    )
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda driver, **_kwargs: production if driver == "rigol.dsg830" else scope_descriptor,
    )
    scope_calls: list[int] = []

    class FakeScopeService:
        def fetch_waveform(self, channel: int):
            scope_calls.append(channel)
            return SimpleNamespace(voltages_v=[-0.002, 0.002])

    scope_transport = _FakeTransport(module)
    scope_driver = _FakeDriver(scope_transport)
    monkeypatch.setattr(
        module,
        "_open_scope_observer",
        lambda *_args, **_kwargs: (FakeScopeService(), scope_driver, scope_transport, "DC"),
    )
    rf_transport = _FakeTransport(module)
    driver = _FakeDriver(rf_transport)
    calls, opener = _collector(production, driver)
    rf_config = _config()
    scope_config = _config(scope_resource="TCPIP::198.51.100.32::INSTR")
    setup = _setup(module)
    preflight = module.validate_a3_preflight(rf_config, setup, scope_config=scope_config)

    evidence = module.collect_a3_evidence(
        rf_config,
        scope_config,
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert [request.frequency_hz for request in driver.cw_requests] == [1_000_000.0, None]
    assert [request.power_dbm for request in driver.cw_requests] == [None, -50.0]
    assert driver.output_requests == [True, False]
    assert driver.output_enabled is False
    assert scope_calls == [2]
    assert evidence["scope_observation"]["signal_detected"] is True
    assert evidence["rf_audit"]["before_close"]["counters"]["query_calls"] == 72
    assert evidence["rf_audit"]["before_close"]["counters"]["write_completed"] == 4
    assert evidence["rf_audit"]["after_close"]["session_health"] == "closed"
    assert driver.close_calls == 1
    assert scope_driver.close_calls == 1
    assert calls[0]["access"] == "read_write"
    assert "198.51.100.83" not in str(evidence)


def test_initial_on_is_failed_but_forces_one_bounded_off(monkeypatch) -> None:
    module = _script_module()
    production = _pre_a3_descriptor()
    _install_common_patches(monkeypatch, module, production)
    scope_descriptor = SimpleNamespace(
        capabilities=("scope.idn", "scope.channel_coupling", "scope.fetch_waveform")
    )
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda driver, **_kwargs: production if driver == "rigol.dsg830" else scope_descriptor,
    )
    scope_transport = _FakeTransport(module)
    scope_driver = _FakeDriver(scope_transport)
    monkeypatch.setattr(
        module,
        "_open_scope_observer",
        lambda *_args, **_kwargs: (SimpleNamespace(), scope_driver, scope_transport, "DC"),
    )
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport, output_enabled=True)
    _, opener = _collector(production, driver)
    config = _config()
    preflight = module.validate_a3_preflight(config, _setup(module), scope_config=_config())

    evidence = module.collect_a3_evidence(
        config,
        _config(),
        preflight,
        _setup(module),
        opener=opener,
    )

    assert evidence["status"] == "failed"
    assert "initial_rf_output_not_off" in evidence["failure_codes"]
    assert "final_rf_off_not_confirmed" not in evidence["failure_codes"]
    assert driver.cw_requests == []
    assert driver.output_requests == [False]
    assert driver.output_enabled is False


def test_failed_cw_never_attempts_rf_output_enable(monkeypatch) -> None:
    module = _script_module()
    production = _pre_a3_descriptor()
    _install_common_patches(monkeypatch, module, production)
    scope_descriptor = SimpleNamespace(
        capabilities=("scope.idn", "scope.channel_coupling", "scope.fetch_waveform")
    )
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda driver, **_kwargs: production if driver == "rigol.dsg830" else scope_descriptor,
    )
    scope_transport = _FakeTransport(module)
    scope_driver = _FakeDriver(scope_transport)
    monkeypatch.setattr(
        module,
        "_open_scope_observer",
        lambda *_args, **_kwargs: (SimpleNamespace(), scope_driver, scope_transport, "DC"),
    )
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.frequency_error = RuntimeError("redacted")
    _, opener = _collector(production, driver)
    config = _config()
    preflight = module.validate_a3_preflight(config, _setup(module), scope_config=_config())

    evidence = module.collect_a3_evidence(
        config,
        _config(),
        preflight,
        _setup(module),
        opener=opener,
    )

    assert evidence["status"] == "failed"
    assert "rf_frequency_configure_failed" in evidence["failure_codes"]
    assert driver.output_requests == []
    assert driver.output_enabled is False


def test_ch2_signal_is_a_required_a3_evidence_condition(monkeypatch) -> None:
    module = _script_module()
    production = _pre_a3_descriptor()
    _install_common_patches(monkeypatch, module, production)
    scope_descriptor = SimpleNamespace(
        capabilities=("scope.idn", "scope.channel_coupling", "scope.fetch_waveform")
    )
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda driver, **_kwargs: production if driver == "rigol.dsg830" else scope_descriptor,
    )

    class SilentScopeService:
        def fetch_waveform(self, channel: int):
            assert channel == 2
            return SimpleNamespace(voltages_v=[0.0, 0.0])

    scope_transport = _FakeTransport(module)
    scope_driver = _FakeDriver(scope_transport)
    monkeypatch.setattr(
        module,
        "_open_scope_observer",
        lambda *_args, **_kwargs: (SilentScopeService(), scope_driver, scope_transport, "DC"),
    )
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    _, opener = _collector(production, driver)
    config = _config()
    preflight = module.validate_a3_preflight(config, _setup(module), scope_config=_config())

    evidence = module.collect_a3_evidence(
        config,
        _config(),
        preflight,
        _setup(module),
        opener=opener,
    )

    assert evidence["status"] == "failed"
    assert "scope_ch2_signal_not_observed" in evidence["failure_codes"]
    assert "final_rf_off_not_confirmed" not in evidence["failure_codes"]
    assert driver.output_requests == [True, False]
    assert driver.output_enabled is False


def test_setup_parser_and_evidence_file_are_strict_and_private(tmp_path: Path) -> None:
    module = _script_module()
    setup_path = tmp_path / "a3.toml"
    setup_path.write_text(
        """
[a3_evidence]
port_id = "rf_out"
actual_termination_ohm = 50
installed_options = []
frequency_hz = 1000000
power_dbm = -50

[scope_observation]
ch2 = 2
allow_ch2_50ohm = true
points = "def"
minimum_observable_vpp_v = 0.001
""".strip(),
        encoding="utf-8",
    )

    setup = module.load_a3_evidence_setup(setup_path)
    assert setup.frequency_hz == 1_000_000.0
    output = module._open_evidence_output(tmp_path / "evidence.json")
    output.close()
    assert stat.S_IMODE((tmp_path / "evidence.json").stat().st_mode) == 0o600

    setup_path.write_text(setup_path.read_text(encoding="utf-8").replace("-50", "-39"), encoding="utf-8")
    with pytest.raises(module.A3PreflightError, match="a3_evidence_power_not_low_enough"):
        module.load_a3_evidence_setup(setup_path)
