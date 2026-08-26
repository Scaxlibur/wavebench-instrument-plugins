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
    RfModulationDisableRequest,
    RfModulationKind,
    RfModulationRequest,
    RfModulationSnapshot,
    RfModulationSource,
    RfModulationState,
    RfModulationWaveform,
    RfObserved,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfSourceSnapshot,
    RfSweepState,
)
from wavebench.transport.session import SessionHealth


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a4_modulation_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a4_modulation_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    from wavebench_rigol_dsg830.descriptor import descriptor

    production = descriptor()
    extensions = production.rf_source_extensions
    assert extensions is not None
    return replace(
        production,
        capabilities=tuple(
            capability
            for capability in production.capabilities
            if capability != "rf_source.pulse_configure"
        ),
        rf_source_extensions=replace(
            extensions,
            features=tuple(
                feature
                for feature in extensions.features
                if feature.feature is not RfFeature.PULSE
            ),
        ),
    )


def _config(*, resource: str = "TCPIP::198.51.100.83::INSTR") -> WaveBenchConfig:
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
            resource=resource,
            access="read_only",
        ),
    )


def _request(kind: RfModulationKind) -> RfModulationRequest:
    fields: dict[str, object] = {
        "port_id": "rf_out",
        "kind": kind,
        "internal_frequency_hz": 1_000.0,
    }
    if kind is RfModulationKind.AM:
        fields["depth_percent"] = 25.0
    elif kind is RfModulationKind.FM:
        fields["frequency_deviation_hz"] = 20_000.0
    else:
        fields["phase_deviation_rad"] = 2.0
    return RfModulationRequest(**fields)  # type: ignore[arg-type]


def _setup(module, kind: RfModulationKind = RfModulationKind.AM):
    return module.A4EvidenceSetup(
        port_id="rf_out",
        actual_termination_ohm=50.0,
        installed_options=(),
        request=_request(kind),
    )


def _rf_snapshot(
    *,
    output_enabled: bool = False,
    modulation: RfModulationState = RfModulationState.DISABLED,
) -> RfSourceSnapshot:
    return RfSourceSnapshot(
        ports=(
            RfPortSnapshot(
                port_id="rf_out",
                frequency_hz=RfObserved.value_of(1_000_000.0),
                power_dbm=RfObserved.value_of(-50.0),
                output_enabled=RfObserved.value_of(output_enabled),
                modulation=RfObserved.value_of(modulation),
                pulse=RfObserved.value_of(RfPulseState.DISABLED),
                sweep=RfObserved.value_of(RfSweepState.DISABLED),
            ),
        ),
        protection=RfObserved.value_of(RfProtectionStatus(active_codes=())),
    )


def _modulation_snapshot(
    request: RfModulationRequest,
    *,
    enabled: bool,
    selected_fm_pm_kind: RfModulationKind | None = None,
) -> RfModulationSnapshot:
    fields: dict[str, object] = {
        "port_id": request.port_id,
        "kind": request.kind,
        "source": RfModulationSource.INTERNAL,
        "waveform": RfModulationWaveform.SINE,
        "internal_frequency_hz": request.internal_frequency_hz,
        "selected_fm_pm_kind": (
            selected_fm_pm_kind
            if selected_fm_pm_kind is not None
            else (
                request.kind
                if request.kind in {RfModulationKind.FM, RfModulationKind.PM}
                else None
            )
        ),
        "enabled_modes": (request.kind,) if enabled else (),
        "global_enabled": enabled,
        "fault_codes": (),
    }
    if request.kind is RfModulationKind.AM:
        fields["depth_percent"] = request.value
    elif request.kind is RfModulationKind.FM:
        fields["frequency_deviation_hz"] = request.value
    else:
        fields["phase_deviation_rad"] = request.value
    return RfModulationSnapshot(**fields)  # type: ignore[arg-type]


class _FakeTransport:
    def __init__(self, module) -> None:
        self.module = module
        self.closed = False
        self.access = "read_write"
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
            "access": self.access,
            "counters": counters,
            "session": {"health": "closed" if self.closed else "healthy"},
        }


class _FakeDriver:
    def __init__(self, transport: _FakeTransport) -> None:
        self.transport = transport
        self.close_calls = 0
        self.modulation_requests: list[RfModulationRequest] = []
        self.modulation_disable_requests: list[RfModulationDisableRequest] = []
        self.modulation_profile_requests: list[tuple[str, RfModulationKind]] = []
        self.output_requests: list[object] = []

    def a1_snapshot_firmware(self) -> str:
        return "00.01.01"

    def get_rf_modulation_snapshot(self, port_id: str, kind: RfModulationKind) -> RfModulationSnapshot:
        self.modulation_profile_requests.append((port_id, kind))
        self.transport.query_calls += 9 if kind is RfModulationKind.AM else 10
        if getattr(self, "profile_error", None) is not None:
            raise self.profile_error
        profile = getattr(self, "diagnostic_profile", None)
        return profile if profile is not None else _modulation_snapshot(_request(kind), enabled=False)

    def close(self) -> None:
        self.close_calls += 1
        self.transport.closed = True


def _artifact(
    request: RfModulationRequest,
    *,
    matching: bool = True,
) -> dict[str, object]:
    value = request.value if matching else request.value + 1.0
    value_field = {
        RfModulationKind.AM: "depth_percent",
        RfModulationKind.FM: "frequency_deviation_hz",
        RfModulationKind.PM: "phase_deviation_rad",
    }[request.kind]
    return {
        "operation": "rf_source.modulation_configure",
        "postcondition_snapshot": {
            "ports": [
                {
                    "output_enabled": {"availability": "value", "value": False},
                    "modulation": {"availability": "value", "value": "enabled"},
                    "pulse": {"availability": "value", "value": "disabled"},
                    "sweep": {"availability": "value", "value": "disabled"},
                }
            ]
        },
        "postcondition_modulation_snapshot": {
            "port_id": request.port_id,
            "kind": request.kind.value,
            "source": "internal",
            "waveform": "sine",
            "selected_fm_pm_kind": (
                request.kind.value if request.kind in {RfModulationKind.FM, RfModulationKind.PM} else None
            ),
            value_field: value,
            "internal_frequency_hz": request.internal_frequency_hz,
            "enabled_modes": [request.kind.value],
            "global_enabled": True,
            "fault_codes": [],
        },
    }


def _disable_artifact(
    request: RfModulationDisableRequest,
    *,
    matching: bool = True,
    write_completed: bool = True,
) -> dict[str, object]:
    enabled_modes = [] if matching else [request.kind.value]
    return {
        "operation": "rf_source.modulation_disable",
        "result": {"write_completed": write_completed},
        "postcondition_snapshot": {
            "ports": [
                {
                    "output_enabled": {"availability": "value", "value": False},
                    "modulation": {
                        "availability": "value",
                        "value": "disabled" if matching else "enabled",
                    },
                    "pulse": {"availability": "value", "value": "disabled"},
                    "sweep": {"availability": "value", "value": "disabled"},
                }
            ]
        },
        "postcondition_modulation_state": {
            "port_id": request.port_id,
            "enabled_modes": enabled_modes,
            "global_enabled": not matching,
            "fault_codes": [],
        },
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
        self.snapshots: list[RfSourceSnapshot] = list(getattr(session, "snapshots"))

    def snapshot(self) -> RfSourceSnapshot:
        self.transport.query_calls += 8
        if not self.snapshots:
            raise AssertionError("unexpected snapshot")
        return self.snapshots.pop(0)

    def configure_modulation_with_artifact(self, request: RfModulationRequest):
        self.driver.modulation_requests.append(request)
        postcondition_modulation_queries = 9 if request.kind is RfModulationKind.AM else 10
        self.transport.query_calls += 8 + 5 + 8 + postcondition_modulation_queries
        self.transport.write_calls += 6 if request.kind is RfModulationKind.AM else 7
        if getattr(self.driver, "configure_error", None) is not None:
            raise self.driver.configure_error
        return SimpleNamespace(port_id=request.port_id), _artifact(
            request,
            matching=getattr(self.driver, "artifact_matches", True),
        )

    def disable_modulation_with_artifact(self, request: RfModulationDisableRequest):
        self.driver.modulation_disable_requests.append(request)
        write_completed = getattr(self.driver, "disable_write_completed", True)
        self.transport.query_calls += 8 + 5 + (8 + 5 if write_completed else 0)
        self.transport.write_calls += 2 if write_completed else 0
        if getattr(self.driver, "disable_error", None) is not None:
            raise self.driver.disable_error
        return SimpleNamespace(
            port_id=request.port_id,
            write_completed=write_completed,
        ), _disable_artifact(
            request,
            matching=getattr(self.driver, "disable_artifact_matches", True),
            write_completed=write_completed,
        )

    def set_output_with_artifact(self, request):
        self.driver.output_requests.append(request)
        raise AssertionError("A4 must not invoke RF output control")


def _install_common_patches(monkeypatch, module, production) -> None:
    monkeypatch.setattr(
        module,
        "resolve_instrument_descriptor",
        lambda *_args, **_kwargs: production,
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
        driver.transport.access = kwargs["access"]
        return SimpleNamespace(
            descriptor=production,
            driver=driver,
            transport=driver.transport,
            session_state=state,
        )

    return calls, opener


def test_preflight_builds_in_memory_m3_descriptor_without_production_promotion(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)

    preflight = module.validate_a4_preflight(_config(), _setup(module))

    assert preflight.production_descriptor.capabilities == (
        "rf_source.idn",
        "rf_source.snapshot",
        "rf_source.cw_configure",
        "rf_source.output",
    )
    assert preflight.evidence_descriptor.capabilities[-2:] == (
        "rf_source.modulation_configure",
        "rf_source.modulation_disable",
    )
    assert preflight.evidence_descriptor.rf_source_extensions is not None
    assert tuple(
        feature.feature for feature in preflight.evidence_descriptor.rf_source_extensions.features
    ) == (RfFeature.CW, RfFeature.MODULATION, RfFeature.OUTPUT)

    changed = preflight.evidence_descriptor
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *_args, **_kwargs: changed)
    with pytest.raises(module.A4PreflightError, match="production_modulation_gate_changed"):
        module.validate_a4_preflight(_config(), _setup(module))


@pytest.mark.parametrize(
    ("kind", "expected_queries", "expected_writes"),
    (
        (RfModulationKind.AM, 72, 8),
        (RfModulationKind.FM, 73, 9),
        (RfModulationKind.PM, 73, 9),
    ),
)
def test_collects_one_rf_off_internal_sine_mode_without_output_control(
    monkeypatch,
    kind: RfModulationKind,
    expected_queries: int,
    expected_writes: int,
) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    setup = _setup(module, kind)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [
        _rf_snapshot(),
        _rf_snapshot(),
    ]
    calls, opener = _collector(production, driver)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_evidence(
        _config(),
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert driver.modulation_requests == [setup.request]
    assert driver.modulation_disable_requests == [
        RfModulationDisableRequest(port_id="rf_out", kind=kind)
    ]
    assert driver.output_requests == []
    assert evidence["rf_audit"]["before_close"]["counters"]["query_calls"] == expected_queries
    assert evidence["rf_audit"]["before_close"]["counters"]["write_completed"] == expected_writes
    assert evidence["rf_audit"]["after_close"]["session_health"] == "closed"
    assert driver.close_calls == 1
    assert calls[0]["access"] == "read_write"
    assert calls[0]["lease"].operation == "dsg830.a4_modulation_evidence"
    assert "198.51.100.83" not in str(evidence)


@pytest.mark.parametrize(
    ("kind", "expected_queries"),
    (
        (RfModulationKind.AM, 25),
        (RfModulationKind.FM, 26),
        (RfModulationKind.PM, 26),
    ),
)
def test_collects_readonly_a4_profile_diagnostic_without_output_control(
    monkeypatch,
    kind: RfModulationKind,
    expected_queries: int,
) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    setup = _setup(module, kind)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [_rf_snapshot(), _rf_snapshot()]
    calls, opener = _collector(production, driver)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_diagnostic_evidence(
        _config(),
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["operation_mode"] == "diagnostic"
    assert evidence["modulation_profile"]["kind"] == kind.value
    assert driver.modulation_profile_requests == [("rf_out", kind)]
    assert driver.modulation_requests == []
    assert driver.modulation_disable_requests == []
    assert driver.output_requests == []
    assert transport.write_calls == 0
    assert evidence["rf_audit"]["before_close"]["access"] == "read_only"
    assert evidence["rf_audit"]["before_close"]["counters"]["query_calls"] == expected_queries
    assert evidence["rf_audit"]["after_close"]["session_health"] == "closed"
    assert calls[0]["access"] == "read_only"
    assert calls[0]["lease"].operation == "dsg830.a4_modulation_diagnostic"
    assert "198.51.100.83" not in str(evidence)


def test_readonly_diagnostic_refuses_an_unsafe_initial_snapshot_without_profile_or_write(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [_rf_snapshot(output_enabled=True)]
    _, opener = _collector(production, driver)
    setup = _setup(module, RfModulationKind.PM)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_diagnostic_evidence(_config(), preflight, setup, opener=opener)

    assert evidence["status"] == "failed"
    assert "initial_rf_output_not_off" in evidence["failure_codes"]
    assert evidence["modulation_profile"] is None
    assert driver.modulation_profile_requests == []
    assert driver.modulation_requests == []
    assert driver.modulation_disable_requests == []
    assert driver.output_requests == []
    assert transport.write_calls == 0


def test_readonly_diagnostic_does_not_retry_a_profile_read_failure(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [_rf_snapshot()]
    driver.profile_error = RuntimeError("redacted")
    _, opener = _collector(production, driver)
    setup = _setup(module, RfModulationKind.PM)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_diagnostic_evidence(_config(), preflight, setup, opener=opener)

    assert evidence["status"] == "failed"
    assert "diagnostic_profile_read_failed" in evidence["failure_codes"]
    assert evidence["final_snapshot"] is None
    assert driver.modulation_profile_requests == [("rf_out", RfModulationKind.PM)]
    assert driver.modulation_requests == []
    assert driver.modulation_disable_requests == []
    assert driver.output_requests == []
    assert transport.write_calls == 0


def test_initial_output_on_fails_without_modulation_or_output_write(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [_rf_snapshot(output_enabled=True)]
    _, opener = _collector(production, driver)
    setup = _setup(module)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_evidence(_config(), preflight, setup, opener=opener)

    assert evidence["status"] == "failed"
    assert "initial_rf_output_not_off" in evidence["failure_codes"]
    assert "final_rf_off_not_confirmed" in evidence["failure_codes"]
    assert driver.modulation_requests == []
    assert driver.modulation_disable_requests == []
    assert driver.output_requests == []
    assert transport.write_calls == 0


def test_modulation_failure_does_not_attempt_output_or_final_snapshot(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [_rf_snapshot()]
    driver.configure_error = RuntimeError("redacted")
    _, opener = _collector(production, driver)
    setup = _setup(module, RfModulationKind.FM)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_evidence(_config(), preflight, setup, opener=opener)

    assert evidence["status"] == "failed"
    assert "rf_modulation_configure_failed" in evidence["failure_codes"]
    assert evidence["final_snapshot"] is None
    assert driver.modulation_requests == [setup.request]
    assert driver.modulation_disable_requests == []
    assert driver.output_requests == []


def test_invalid_postcondition_or_final_output_state_never_invokes_output_control(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    setup = _setup(module)

    bad_artifact_transport = _FakeTransport(module)
    bad_artifact_driver = _FakeDriver(bad_artifact_transport)
    bad_artifact_driver.snapshots = [_rf_snapshot(), _rf_snapshot()]
    bad_artifact_driver.artifact_matches = False
    _, bad_artifact_opener = _collector(production, bad_artifact_driver)
    preflight = module.validate_a4_preflight(_config(), setup)
    bad_artifact = module.collect_a4_evidence(
        _config(),
        preflight,
        setup,
        opener=bad_artifact_opener,
    )
    assert "rf_modulation_readback_invalid" in bad_artifact["failure_codes"]
    assert len(bad_artifact_driver.modulation_disable_requests) == 1
    assert bad_artifact_driver.output_requests == []

    final_output_transport = _FakeTransport(module)
    final_output_driver = _FakeDriver(final_output_transport)
    final_output_driver.snapshots = [
        _rf_snapshot(),
        _rf_snapshot(output_enabled=True),
    ]
    _, final_output_opener = _collector(production, final_output_driver)
    final_output = module.collect_a4_evidence(
        _config(),
        preflight,
        setup,
        opener=final_output_opener,
    )
    assert "final_rf_output_not_off" in final_output["failure_codes"]
    assert "final_rf_off_not_confirmed" in final_output["failure_codes"]
    assert final_output_driver.output_requests == []


def test_modulation_disable_failure_does_not_retry_or_attempt_output_or_final_snapshot(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [_rf_snapshot()]
    driver.disable_error = RuntimeError("redacted")
    _, opener = _collector(production, driver)
    setup = _setup(module)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_evidence(_config(), preflight, setup, opener=opener)

    assert evidence["status"] == "failed"
    assert "rf_modulation_disable_failed" in evidence["failure_codes"]
    assert evidence["final_snapshot"] is None
    assert len(driver.modulation_disable_requests) == 1
    assert driver.output_requests == []


def test_collects_a_private_mode_specific_recovery_without_configuration_or_output_control(
    monkeypatch,
) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.snapshots = [
        _rf_snapshot(modulation=RfModulationState.ENABLED),
        _rf_snapshot(),
    ]
    calls, opener = _collector(production, driver)
    setup = _setup(module)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_recovery_evidence(
        _config(),
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["operation_mode"] == "recovery"
    assert evidence["modulation_configure"] is None
    assert driver.modulation_requests == []
    assert driver.modulation_disable_requests == [
        RfModulationDisableRequest(port_id="rf_out", kind=RfModulationKind.AM)
    ]
    assert driver.output_requests == []
    assert evidence["rf_audit"]["before_close"]["counters"]["query_calls"] == 42
    assert evidence["rf_audit"]["before_close"]["counters"]["write_completed"] == 2
    assert calls[0]["lease"].operation == "dsg830.a4_modulation_recovery"


def test_recovery_records_an_already_disabled_consistent_state_without_write(monkeypatch) -> None:
    module = _script_module()
    production = _production_descriptor()
    _install_common_patches(monkeypatch, module, production)
    transport = _FakeTransport(module)
    driver = _FakeDriver(transport)
    driver.disable_write_completed = False
    driver.snapshots = [_rf_snapshot(), _rf_snapshot()]
    _, opener = _collector(production, driver)
    setup = _setup(module)
    preflight = module.validate_a4_preflight(_config(), setup)

    evidence = module.collect_a4_recovery_evidence(
        _config(),
        preflight,
        setup,
        opener=opener,
    )

    assert evidence["status"] == "passed"
    assert evidence["modulation_disable"]["result"]["write_completed"] is False
    assert transport.write_calls == 0
    assert evidence["rf_audit"]["before_close"]["counters"]["query_calls"] == 29


def test_setup_parser_and_evidence_file_are_strict_and_private(tmp_path: Path) -> None:
    module = _script_module()
    setup_path = tmp_path / "a4.toml"
    setup_path.write_text(
        """
[a4_evidence]
port_id = "rf_out"
actual_termination_ohm = 50
installed_options = []
modulation_kind = "pm"
phase_deviation_rad = 2
internal_frequency_hz = 1000
""".strip(),
        encoding="utf-8",
    )

    setup = module.load_a4_evidence_setup(setup_path)
    assert setup.request.kind is RfModulationKind.PM
    assert setup.request.phase_deviation_rad == 2.0
    output = module._open_evidence_output(tmp_path / "evidence.json")
    output.close()
    assert stat.S_IMODE((tmp_path / "evidence.json").stat().st_mode) == 0o600

    setup_path.write_text(
        setup_path.read_text(encoding="utf-8") + "\ndepth_percent = 20\n",
        encoding="utf-8",
    )
    with pytest.raises(module.A4PreflightError, match="a4_evidence_invalid"):
        module.load_a4_evidence_setup(setup_path)
