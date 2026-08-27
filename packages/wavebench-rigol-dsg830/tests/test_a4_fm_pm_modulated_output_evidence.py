from __future__ import annotations

import importlib
import importlib.util
from dataclasses import replace
import json
from pathlib import Path
import stat
import sys
from types import SimpleNamespace

import numpy as np
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
from wavebench.instruments.models import WaveformData, WaveformHeader
from wavebench.instruments.rf_source_extensions import (
    RfCwRequest,
    RfFeature,
    RfModulationDisableRequest,
    RfModulationKind,
    RfModulationRequest,
    RfModulationSnapshot,
    RfModulationSource,
    RfModulationState,
    RfModulationStateSnapshot,
    RfModulationWaveform,
    RfObserved,
    RfOutputRequest,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfSourceSnapshot,
    RfSweepState,
)
from wavebench.transport.session import InstrumentSessionState


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a4_fm_pm_modulated_output_evidence.py"


def _module():
    spec = importlib.util.spec_from_file_location("dsg830_a4_fm_pm_modulated_output_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _production_descriptor():
    return importlib.import_module("wavebench_rigol_dsg830.descriptor").descriptor()


def _historical_production_descriptor():
    """Return the pre-FM/PM A4-MO descriptor for historical harness regression."""

    production = _production_descriptor()
    extensions = production.rf_source_extensions
    assert extensions is not None
    features = tuple(
        replace(
            feature,
            profile=replace(feature.profile, mode_profiles=(feature.profile.mode_profiles[0],)),
        )
        if feature.feature is RfFeature.MODULATED_OUTPUT
        else feature
        for feature in extensions.features
    )
    return replace(production, rf_source_extensions=replace(extensions, features=features))


def _scope_descriptor():
    return SimpleNamespace(
        driver_id="rohde-schwarz.rtm2032",
        kind="scope",
        capabilities=("scope.idn", "scope.channel_coupling", "scope.fetch_waveform"),
    )


def _config(*, driver: str = "rigol.dsg830", access: str = "read_only") -> WaveBenchConfig:
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
            access=access,  # type: ignore[arg-type]
        ),
        autoscale=AutoscaleConfig(True, True),
        waveform=WaveformConfig("real", "lsbf", "def"),
        output=OutputConfig(Path("data/raw"), "timestamp_label", True, True, True, True, False),
        source_path=Path("test.toml"),
        rf_source=RfSourceConfig(
            driver=driver,
            resource="TCPIP::rf-test::INSTR",
            access=access,  # type: ignore[arg-type]
        ),
    )


def _setup_file(path: Path, *, kind: RfModulationKind, value: float | None = None) -> None:
    value_field = {
        RfModulationKind.FM: "frequency_deviation_hz",
        RfModulationKind.PM: "phase_deviation_rad",
    }[kind]
    target_value = {
        RfModulationKind.FM: 20_000.0,
        RfModulationKind.PM: 1.25,
    }[kind]
    path.write_text(
        "[a4_fm_pm_modulated_output]\n"
        'port_id = "rf_out"\n'
        "actual_termination_ohm = 50\n"
        "installed_options = []\n"
        "frequency_hz = 1000000\n"
        "power_dbm = -50\n"
        f'modulation_kind = "{kind.value}"\n'
        f"{value_field} = {target_value if value is None else value}\n"
        "internal_frequency_hz = 1000\n\n"
        "[scope_observation]\n"
        "ch2 = 2\n"
        "allow_ch2_50ohm = true\n"
        'points = "def"\n'
        "minimum_observable_vpp_v = 0.001\n",
        encoding="utf-8",
    )


class _AuditTransport:
    def __init__(self, *, access: str) -> None:
        self.access = access
        self.query_calls = 0
        self.write_calls = 0
        self.closed = False

    def audit_snapshot(self) -> dict[str, object]:
        counters = {
            "query_calls": self.query_calls,
            "binary_query_calls": 0,
            "blocked_query_calls": 0,
            "blocked_binary_query_calls": 0,
            "write_requests": self.write_calls,
            "write_attempts": self.write_calls,
            "write_transmitted": self.write_calls,
            "write_completed": self.write_calls,
            "write_outcome_unknown": 0,
            "binary_write_requests": 0,
            "binary_write_attempts": 0,
            "binary_write_transmitted": 0,
            "binary_write_completed": 0,
            "binary_write_outcome_unknown": 0,
            "blocked_write_requests": 0,
            "blocked_binary_write_requests": 0,
            "instrument_mutation_writes": self.write_calls,
            "instrument_mutation_writes_completed": self.write_calls,
            "blocked_session_io": 0,
            "session_health_transitions": 0,
        }
        return {
            "access": self.access,
            "counters": counters,
            "session": {"health": "closed" if self.closed else "healthy"},
        }

    def close(self) -> None:
        self.closed = True


class _FakeRfDriver:
    def __init__(self, transport: _AuditTransport) -> None:
        self.transport = transport
        self.frequency_hz = 1_000_000.0
        self.power_dbm = -50.0
        self.output_enabled = False
        self.modulation_enabled = False
        self.modulation_request: RfModulationRequest | None = None

    def close(self) -> None:
        self.transport.close()

    def idn(self) -> str:
        return "EXAMPLE,DSG830,redacted,1.0"

    def a1_snapshot_firmware(self) -> str:
        return "1.0"

    def get_rf_snapshot(self) -> RfSourceSnapshot:
        self.transport.query_calls += 8
        return RfSourceSnapshot(
            ports=(
                RfPortSnapshot(
                    port_id="rf_out",
                    frequency_hz=RfObserved.value_of(self.frequency_hz),
                    power_dbm=RfObserved.value_of(self.power_dbm),
                    output_enabled=RfObserved.value_of(self.output_enabled),
                    modulation=RfObserved.value_of(
                        RfModulationState.ENABLED
                        if self.modulation_enabled
                        else RfModulationState.DISABLED
                    ),
                    pulse=RfObserved.value_of(RfPulseState.DISABLED),
                    sweep=RfObserved.value_of(RfSweepState.DISABLED),
                ),
            ),
            protection=RfObserved.value_of(RfProtectionStatus(active_codes=())),
        )

    def configure_cw(self, request: RfCwRequest) -> None:
        self.transport.write_calls += 1
        if request.frequency_hz is not None:
            self.frequency_hz = request.frequency_hz
        else:
            assert request.power_dbm is not None
            self.power_dbm = request.power_dbm

    def get_rf_modulation_state(self, port_id: str) -> RfModulationStateSnapshot:
        assert port_id == "rf_out"
        self.transport.query_calls += 5
        kind = self.modulation_request.kind if self.modulation_request is not None else None
        return RfModulationStateSnapshot(
            port_id=port_id,
            enabled_modes=(kind,) if self.modulation_enabled and kind is not None else (),
            global_enabled=self.modulation_enabled,
        )

    def get_rf_modulation_snapshot(
        self,
        port_id: str,
        kind: RfModulationKind,
    ) -> RfModulationSnapshot:
        assert port_id == "rf_out"
        assert kind in {RfModulationKind.FM, RfModulationKind.PM}
        self.transport.query_calls += 10
        request = self.modulation_request
        if request is None:
            request = RfModulationRequest(
                port_id="rf_out",
                kind=kind,
                internal_frequency_hz=1_000.0,
                frequency_deviation_hz=20_000.0
                if kind is RfModulationKind.FM
                else None,
                phase_deviation_rad=1.25 if kind is RfModulationKind.PM else None,
            )
        assert request.kind is kind
        common = {
            "port_id": port_id,
            "kind": kind,
            "source": RfModulationSource.INTERNAL,
            "waveform": RfModulationWaveform.SINE,
            "internal_frequency_hz": request.internal_frequency_hz,
            "selected_fm_pm_kind": kind,
            "enabled_modes": (kind,) if self.modulation_enabled else (),
            "global_enabled": self.modulation_enabled,
        }
        if kind is RfModulationKind.FM:
            return RfModulationSnapshot(
                **common,
                frequency_deviation_hz=request.frequency_deviation_hz,
            )
        return RfModulationSnapshot(
            **common,
            phase_deviation_rad=request.phase_deviation_rad,
        )

    def configure_rf_modulation(self, request: RfModulationRequest) -> None:
        assert request.kind in {RfModulationKind.FM, RfModulationKind.PM}
        self.transport.write_calls += 7
        self.modulation_request = request
        self.modulation_enabled = True

    def disable_rf_modulation(self, request: RfModulationDisableRequest) -> None:
        assert self.modulation_request is not None
        assert request.kind is self.modulation_request.kind
        self.transport.write_calls += 2
        self.modulation_enabled = False

    def set_rf_output(self, request: RfOutputRequest) -> None:
        self.transport.write_calls += 1
        self.output_enabled = request.enabled

    def get_rf_pulse_snapshot(self, port_id: str):
        raise AssertionError(f"unexpected pulse snapshot for {port_id}")

    def configure_rf_pulse(self, request: object) -> None:
        raise AssertionError(f"unexpected pulse configuration {request!r}")

    def get_rf_pulse_output_snapshot(self, port_id: str, interface_id: str):
        raise AssertionError(f"unexpected pulse output snapshot for {port_id}/{interface_id}")

    def set_rf_pulse_output(self, request: object) -> None:
        raise AssertionError(f"unexpected pulse output write {request!r}")

    def get_rf_sweep_snapshot(self, port_id: str):
        raise AssertionError(f"unexpected sweep snapshot for {port_id}")

    def configure_rf_sweep(self, request: object) -> None:
        raise AssertionError(f"unexpected sweep configuration {request!r}")


class _FakeScopeDriver:
    def __init__(self, transport: _AuditTransport) -> None:
        self.transport = transport

    def close(self) -> None:
        self.transport.close()


def _waveform(*, amplitude_v: float) -> WaveformData:
    points = 4_001
    header = WaveformHeader(x_start=0.0, x_stop=10e-6, points=points)
    times_s = np.linspace(header.x_start, header.x_stop, points, dtype=np.float64)
    return WaveformData(
        channel=2,
        header=header,
        voltages_v=amplitude_v * np.sin(2.0 * np.pi * 1_000_000.0 * times_s),
    )


class _FakeScopeService:
    def fetch_waveform(self, channel: int) -> WaveformData:
        assert channel == 2
        return _waveform(amplitude_v=0.001)


class _NoSignalScopeService:
    def fetch_waveform(self, channel: int) -> WaveformData:
        assert channel == 2
        return _waveform(amplitude_v=0.0)


def _patch_static_preflight(monkeypatch, module, production) -> None:
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
        return _scope_descriptor()

    monkeypatch.setattr(module, "resolve_instrument_descriptor", resolve)


@pytest.mark.parametrize(
    ("kind", "expected_field", "expected_value"),
    (
        (RfModulationKind.FM, "frequency_deviation_hz", 20_000.0),
        (RfModulationKind.PM, "phase_deviation_rad", 1.25),
    ),
)
def test_a4_fm_pm_setup_is_fixed_and_resource_free(
    tmp_path: Path,
    kind: RfModulationKind,
    expected_field: str,
    expected_value: float,
) -> None:
    module = _module()
    setup_path = tmp_path / "setup.toml"
    _setup_file(setup_path, kind=kind)

    setup = module.load_a4_fm_pm_modulated_output_setup(setup_path)

    assert setup.modulation.kind is kind
    assert setup.modulation.value == expected_value
    assert getattr(setup.modulation, expected_field) == expected_value
    _setup_file(setup_path, kind=kind, value=expected_value + 1.0)
    with pytest.raises(module.A4FmPmModulatedOutputPreflightError, match="fixed_profile"):
        module.load_a4_fm_pm_modulated_output_setup(setup_path)


@pytest.mark.parametrize("kind", (RfModulationKind.FM, RfModulationKind.PM))
def test_a4_fm_pm_preflight_adds_exactly_one_private_profile(
    monkeypatch,
    tmp_path: Path,
    kind: RfModulationKind,
) -> None:
    module = _module()
    production = _historical_production_descriptor()
    _patch_static_preflight(monkeypatch, module, production)
    setup_path = tmp_path / "setup.toml"
    _setup_file(setup_path, kind=kind)
    setup = module.load_a4_fm_pm_modulated_output_setup(setup_path)

    preflight = module.validate_a4_fm_pm_modulated_output_preflight(
        _config(),
        setup,
        scope_config=_config(),
    )

    assert module._has_expected_am_only_production_profile(production)
    production_feature = module._production_modulated_output_feature(production)
    evidence_feature = module._production_modulated_output_feature(preflight.evidence_descriptor)
    assert production_feature is not None and evidence_feature is not None
    assert [item.kind for item in production_feature.profile.mode_profiles] == [RfModulationKind.AM]
    assert [item.kind for item in evidence_feature.profile.mode_profiles] == [RfModulationKind.AM, kind]


@pytest.mark.parametrize("kind", (RfModulationKind.FM, RfModulationKind.PM))
def test_a4_fm_pm_diagnostic_is_zero_write_and_closes(
    monkeypatch,
    tmp_path: Path,
    kind: RfModulationKind,
) -> None:
    module = _module()
    production = _historical_production_descriptor()
    _patch_static_preflight(monkeypatch, module, production)
    setup_path = tmp_path / "setup.toml"
    _setup_file(setup_path, kind=kind)
    setup = module.load_a4_fm_pm_modulated_output_setup(setup_path)
    preflight = module.validate_a4_fm_pm_modulated_output_preflight(
        _config(),
        setup,
        scope_config=_config(),
    )
    transport = _AuditTransport(access="read_only")
    driver = _FakeRfDriver(transport)

    def opener(**kwargs):
        assert kwargs["expected_kind"] == "rf_source"
        return SimpleNamespace(
            driver=driver,
            transport=transport,
            descriptor=production,
            session_state=InstrumentSessionState(),
        )

    evidence = module.collect_a4_fm_pm_modulated_output_diagnostic(
        _config(),
        _config(),
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert evidence["rf_audit"]["before_close"]["counters"]["query_calls"] == 26
    assert evidence["rf_audit"]["before_close"]["counters"]["write_completed"] == 0
    assert evidence["rf_audit"]["after_close"]["session_health"] == "closed"


@pytest.mark.parametrize(
    ("kind", "value_field", "value"),
    (
        (RfModulationKind.FM, "frequency_deviation_hz", 20_000.0),
        (RfModulationKind.PM, "phase_deviation_rad", 1.25),
    ),
)
def test_a4_fm_pm_collects_one_fixed_cycle_with_wavebench_quality_analysis(
    monkeypatch,
    tmp_path: Path,
    kind: RfModulationKind,
    value_field: str,
    value: float,
) -> None:
    module = _module()
    production = _historical_production_descriptor()
    _patch_static_preflight(monkeypatch, module, production)
    setup_path = tmp_path / "setup.toml"
    _setup_file(setup_path, kind=kind)
    setup = module.load_a4_fm_pm_modulated_output_setup(setup_path)
    preflight = module.validate_a4_fm_pm_modulated_output_preflight(
        _config(),
        setup,
        scope_config=_config(),
    )
    rf_transport = _AuditTransport(access="read_write")
    rf_driver = _FakeRfDriver(rf_transport)
    scope_transport = _AuditTransport(access="read_write")
    scope_driver = _FakeScopeDriver(scope_transport)

    def opener(**kwargs):
        assert kwargs["expected_kind"] == "rf_source"
        return SimpleNamespace(
            driver=rf_driver,
            transport=rf_transport,
            descriptor=production,
            session_state=InstrumentSessionState(),
        )

    monkeypatch.setattr(
        module,
        "_open_scope_observer",
        lambda *args, **kwargs: (_FakeScopeService(), scope_driver, scope_transport, "50OHM"),
    )
    evidence = module.collect_a4_fm_pm_modulated_output_evidence(
        _config(),
        _config(),
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert evidence["setup"][value_field] == value
    assert evidence["modulated_output_enable"]["operation"] == "rf_source.modulated_output_enable"
    assert evidence["output_disable"]["operation"] == "rf_source.output_disable"
    assert evidence["modulation_disable"]["operation"] == "rf_source.modulation_disable"
    scope = evidence["scope_observation"]
    assert scope["signal_detected"] is True
    assert scope["carrier_frequency_accepted"] is True
    assert scope["waveform_summary"]["frequency_in_tolerance"] is True
    assert scope["fft_analysis"]["peak_frequency_hz"] > 0
    assert len(scope["analysis_limitations"]) == 2
    assert rf_transport.query_calls == module._EXPECTED_RF_QUERY_COUNT
    assert rf_transport.write_calls == module._EXPECTED_RF_WRITES
    assert rf_driver.output_enabled is False
    assert rf_driver.modulation_enabled is False
    assert evidence["rf_audit"]["after_close"]["session_health"] == "closed"
    assert evidence["scope_audit"]["after_close"]["session_health"] == "closed"
    serialized = json.dumps(evidence, ensure_ascii=False)
    assert "TCPIP" not in serialized
    assert "response" not in serialized.casefold()
    assert "command" not in serialized.casefold()


def test_a4_fm_pm_scope_analysis_failure_still_runs_explicit_cleanup(monkeypatch, tmp_path: Path) -> None:
    module = _module()
    production = _historical_production_descriptor()
    _patch_static_preflight(monkeypatch, module, production)
    setup_path = tmp_path / "setup.toml"
    _setup_file(setup_path, kind=RfModulationKind.FM)
    setup = module.load_a4_fm_pm_modulated_output_setup(setup_path)
    preflight = module.validate_a4_fm_pm_modulated_output_preflight(
        _config(),
        setup,
        scope_config=_config(),
    )
    rf_transport = _AuditTransport(access="read_write")
    rf_driver = _FakeRfDriver(rf_transport)
    scope_transport = _AuditTransport(access="read_write")
    scope_driver = _FakeScopeDriver(scope_transport)

    def opener(**kwargs):
        assert kwargs["expected_kind"] == "rf_source"
        return SimpleNamespace(
            driver=rf_driver,
            transport=rf_transport,
            descriptor=production,
            session_state=InstrumentSessionState(),
        )

    monkeypatch.setattr(
        module,
        "_open_scope_observer",
        lambda *args, **kwargs: (_NoSignalScopeService(), scope_driver, scope_transport, "50OHM"),
    )
    evidence = module.collect_a4_fm_pm_modulated_output_evidence(
        _config(),
        _config(),
        preflight,
        setup,
        opener=opener,
        timestamp_utc="2026-08-27T00:00:00Z",
    )

    assert evidence["status"] == "failed"
    assert "scope_ch2_signal_not_observed" in evidence["failure_codes"]
    assert evidence["scope_observation"]["carrier_frequency_accepted"] is False
    assert evidence["output_disable"]["operation"] == "rf_source.output_disable"
    assert evidence["modulation_disable"]["operation"] == "rf_source.modulation_disable"
    assert rf_driver.output_enabled is False
    assert rf_driver.modulation_enabled is False


@pytest.mark.parametrize("kind", (RfModulationKind.FM, RfModulationKind.PM))
def test_a4_fm_pm_historical_harness_refuses_promoted_profile(
    monkeypatch,
    tmp_path: Path,
    kind: RfModulationKind,
) -> None:
    module = _module()
    production = _production_descriptor()
    _patch_static_preflight(monkeypatch, module, production)
    setup_path = tmp_path / "setup.toml"
    _setup_file(setup_path, kind=kind)
    setup = module.load_a4_fm_pm_modulated_output_setup(setup_path)

    with pytest.raises(
        module.A4FmPmModulatedOutputPreflightError,
        match="production_modulated_output_profile_gate_changed",
    ):
        module.validate_a4_fm_pm_modulated_output_preflight(
            _config(),
            setup,
            scope_config=_config(),
        )


def test_a4_fm_pm_evidence_output_is_private_and_new(tmp_path: Path) -> None:
    module = _module()
    output_path = tmp_path / "evidence.json"

    with module._open_evidence_output(output_path) as output:
        output.write("{}")
    assert stat.S_IMODE(output_path.stat().st_mode) == 0o600
    with pytest.raises(module.A4FmPmModulatedOutputPreflightError, match="invalid_evidence_output_path"):
        module._open_evidence_output(output_path)
