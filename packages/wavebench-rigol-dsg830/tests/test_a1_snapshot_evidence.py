from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from wavebench.instruments.rf_source_extensions import (
    RfModulationState,
    RfObserved,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfSourceSnapshot,
    RfSweepState,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a1_snapshot_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a1_snapshot_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(*, output_enabled: bool = False, protection_codes: tuple[str, ...] = ()) -> RfSourceSnapshot:
    return RfSourceSnapshot(
        ports=(
            RfPortSnapshot(
                port_id="rf_out",
                frequency_hz=RfObserved.value_of(4_000_000.0),
                power_dbm=RfObserved.value_of(-20.0),
                output_enabled=RfObserved.value_of(output_enabled),
                modulation=RfObserved.value_of(RfModulationState.DISABLED),
                pulse=RfObserved.value_of(RfPulseState.DISABLED),
                sweep=RfObserved.value_of(RfSweepState.DISABLED),
            ),
        ),
        protection=RfObserved.value_of(RfProtectionStatus(active_codes=protection_codes)),
    )


class _FakeTransport:
    def __init__(self, *, writes: int = 0) -> None:
        self.closed = False
        self.writes = writes

    def audit_snapshot(self) -> dict[str, object]:
        return {
            "access": "read_only",
            "counters": {
                "query_calls": 8,
                "binary_query_calls": 0,
                "blocked_query_calls": 0,
                "blocked_binary_query_calls": 0,
                "write_requests": self.writes,
                "write_attempts": self.writes,
                "write_transmitted": self.writes,
                "write_completed": self.writes,
                "write_outcome_unknown": 0,
                "binary_write_requests": 0,
                "binary_write_attempts": 0,
                "binary_write_transmitted": 0,
                "binary_write_completed": 0,
                "binary_write_outcome_unknown": 0,
                "blocked_write_requests": 0,
                "blocked_binary_write_requests": 0,
                "instrument_mutation_writes": self.writes,
                "instrument_mutation_writes_completed": self.writes,
                "blocked_session_io": 0,
                "session_health_transitions": 0,
            },
            "session": {"health": "closed" if self.closed else "healthy"},
        }


class _FakeDriver:
    def __init__(self, transport: _FakeTransport, snapshot: RfSourceSnapshot | Exception) -> None:
        self.transport = transport
        self.snapshot = snapshot
        self.close_calls = 0

    def get_rf_snapshot(self) -> RfSourceSnapshot:
        if isinstance(self.snapshot, Exception):
            raise self.snapshot
        return self.snapshot

    def close(self) -> None:
        self.close_calls += 1
        self.transport.closed = True


def _descriptor(*, capabilities: tuple[str, ...] = ("rf_source.idn",)) -> SimpleNamespace:
    return SimpleNamespace(
        driver_id="rigol.dsg830",
        kind="rf_source",
        models=("DSG830",),
        capabilities=capabilities,
    )


def _config(*, access: str = "read_only") -> SimpleNamespace:
    return SimpleNamespace(
        rf_source=SimpleNamespace(
            driver="rigol.dsg830",
            resource="TCPIP::192.0.2.83::INSTR",
            access=access,
            options={},
        ),
        connection=SimpleNamespace(backend="lan", timeout_ms=1_000, opc_timeout_ms=2_000),
    )


def _collector(module, transport: _FakeTransport, driver: _FakeDriver, descriptor: SimpleNamespace):
    calls: dict[str, object] = {}

    def opener(**kwargs):
        calls.update(kwargs)
        return SimpleNamespace(descriptor=descriptor, driver=driver, transport=transport)

    return calls, opener


def test_a1_evidence_passes_only_for_zero_write_off_snapshot() -> None:
    module = _script_module()
    descriptor = _descriptor()
    config = _config()
    transport = _FakeTransport()
    driver = _FakeDriver(transport, _snapshot())
    calls, opener = _collector(module, transport, driver, descriptor)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        evidence = module.collect_a1_evidence(
            config,
            descriptor,
            opener=opener,
            timestamp_utc="2026-08-26T00:00:00Z",
        )
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert evidence["snapshot"]["operation"] == "rf_source.snapshot"
    assert evidence["audit"]["before_close"]["counters"]["query_calls"] == 8
    assert evidence["audit"]["after_close"]["session_health"] == "closed"
    assert driver.close_calls == 1
    assert calls["access"] == "read_only"
    assert calls["read_retry_attempts"] == 0
    assert calls["read_retry_delay_ms"] == 0
    assert calls["lease"].mode == "exclusive"
    assert "resource" not in str(evidence)


@pytest.mark.parametrize(
    ("snapshot", "failure_code"),
    (
        (_snapshot(output_enabled=True), "rf_output_not_off"),
        (_snapshot(protection_codes=("alc_unlocked",)), "active_protection_condition"),
    ),
)
def test_a1_evidence_rejects_unsafe_snapshot_state(
    snapshot: RfSourceSnapshot,
    failure_code: str,
) -> None:
    module = _script_module()
    descriptor = _descriptor()
    transport = _FakeTransport()
    driver = _FakeDriver(transport, snapshot)
    _, opener = _collector(module, transport, driver, descriptor)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        evidence = module.collect_a1_evidence(_config(), descriptor, opener=opener)
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "failed"
    assert failure_code in evidence["failure_codes"]
    assert driver.close_calls == 1


def test_a1_evidence_rejects_audit_write_activity_and_snapshot_failure() -> None:
    module = _script_module()
    descriptor = _descriptor()
    transport = _FakeTransport(writes=1)
    driver = _FakeDriver(transport, ValueError("raw response must not escape"))
    _, opener = _collector(module, transport, driver, descriptor)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        evidence = module.collect_a1_evidence(_config(), descriptor, opener=opener)
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "failed"
    assert "snapshot_failed" in evidence["failure_codes"]
    assert "unexpected_write_activity" in evidence["failure_codes"]
    assert "raw response" not in str(evidence)
    assert driver.close_calls == 1


def test_a1_preflight_refuses_nonproduction_descriptor_before_opening() -> None:
    module = _script_module()
    descriptor = _descriptor(capabilities=("rf_source.idn", "rf_source.snapshot"))

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        with pytest.raises(module.A1PreflightError, match="production_snapshot_gate_changed"):
            module.validate_a1_preflight(_config())
    finally:
        monkeypatch.undo()


def test_a1_preflight_requires_read_only_config() -> None:
    module = _script_module()

    with pytest.raises(module.A1PreflightError, match="rf_source_access_must_be_read_only"):
        module.validate_a1_preflight(_config(access="read_write"))


def test_a1_evidence_output_is_new_private_file(tmp_path: Path) -> None:
    module = _script_module()
    output_path = tmp_path / "a1-evidence.json"
    output = module._open_evidence_output(output_path)
    try:
        module._replace_evidence(output, {"status": "started"})
    finally:
        output.close()

    assert output_path.read_text(encoding="utf-8") == '{\n  "status": "started"\n}\n'
    assert output_path.stat().st_mode & 0o777 == 0o600
    with pytest.raises(module.A1PreflightError, match="invalid_evidence_output_path"):
        module._open_evidence_output(output_path)
