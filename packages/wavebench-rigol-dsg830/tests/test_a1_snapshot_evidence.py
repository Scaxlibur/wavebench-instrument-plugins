from __future__ import annotations

from dataclasses import replace
import importlib.util
from pathlib import Path
from types import SimpleNamespace

import pytest

from wavebench.config import load_config
import wavebench.instruments.factory as instrument_factory
import wavebench.instruments.registry as instrument_registry
from wavebench.instruments.rf_source_extensions import (
    RfAvailability,
    RfModulationState,
    RfObserved,
    RfPortSnapshot,
    RfProtectionStatus,
    RfPulseState,
    RfReasonCode,
    RfSourceSnapshot,
    RfSweepState,
)
from wavebench.services.resource_lease import ResourceLease


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = PACKAGE_ROOT / "tools" / "a1_snapshot_evidence.py"


def _script_module():
    spec = importlib.util.spec_from_file_location("dsg830_a1_snapshot_evidence", SCRIPT_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(
    *,
    output_enabled: bool = False,
    protection_codes: tuple[str, ...] = (),
    unknown_frequency: bool = False,
) -> RfSourceSnapshot:
    return RfSourceSnapshot(
        ports=(
            RfPortSnapshot(
                port_id="rf_out",
                frequency_hz=(
                    RfObserved.missing(RfAvailability.UNKNOWN, RfReasonCode.UNKNOWN_STATE)
                    if unknown_frequency
                    else RfObserved.value_of(4_000_000.0)
                ),
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
    def __init__(
        self,
        *,
        writes: int = 0,
        after_writes: int | None = None,
        after_access: str | None = None,
        audit_failures: tuple[int, ...] = (),
    ) -> None:
        self.closed = False
        self.writes = writes
        self.after_writes = after_writes
        self.after_access = after_access
        self.audit_failures = set(audit_failures)
        self.audit_calls = 0

    def audit_snapshot(self) -> dict[str, object]:
        self.audit_calls += 1
        if self.audit_calls in self.audit_failures:
            raise RuntimeError("audit failure must not escape")
        writes = self.after_writes if self.closed and self.after_writes is not None else self.writes
        access = self.after_access if self.closed and self.after_access is not None else "read_only"
        return {
            "access": access,
            "counters": {
                "query_calls": 8,
                "binary_query_calls": 0,
                "blocked_query_calls": 0,
                "blocked_binary_query_calls": 0,
                "write_requests": writes,
                "write_attempts": writes,
                "write_transmitted": writes,
                "write_completed": writes,
                "write_outcome_unknown": 0,
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
            },
            "session": {"health": "closed" if self.closed else "healthy"},
        }


class _FakeDriver:
    def __init__(
        self,
        transport: _FakeTransport,
        snapshot: RfSourceSnapshot | Exception,
        *,
        close_error: Exception | None = None,
        firmware: str | None | Exception = "00.01.01",
    ) -> None:
        self.transport = transport
        self.snapshot = snapshot
        self.close_error = close_error
        self.firmware = firmware
        self.close_calls = 0

    def get_rf_snapshot(self) -> RfSourceSnapshot:
        if isinstance(self.snapshot, Exception):
            raise self.snapshot
        return self.snapshot

    def a1_snapshot_firmware(self) -> str | None:
        if isinstance(self.firmware, Exception):
            raise self.firmware
        return self.firmware

    def close(self) -> None:
        self.close_calls += 1
        self.transport.closed = True
        if self.close_error is not None:
            raise self.close_error


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


def _setup(module, *, options: tuple[str, ...] = ("OPT01",)):
    return module.A1EvidenceSetup(
        port_id="rf_out",
        actual_termination_ohm=1_000_000.0,
        installed_options=options,
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
            _setup(module),
            opener=opener,
            timestamp_utc="2026-08-26T00:00:00Z",
        )
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "passed"
    assert evidence["failure_codes"] == []
    assert evidence["snapshot"]["operation"] == "rf_source.snapshot"
    assert evidence["hardware"] == {
        "model": "DSG830",
        "firmware": "00.01.01",
        "installed_options": ["OPT01"],
    }
    assert evidence["setup"] == {"port_id": "rf_out", "actual_termination_ohm": 1_000_000.0}
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
        (_snapshot(unknown_frequency=True), "snapshot_contains_unknown_state"),
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
        evidence = module.collect_a1_evidence(_config(), descriptor, _setup(module), opener=opener)
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
        evidence = module.collect_a1_evidence(_config(), descriptor, _setup(module), opener=opener)
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "failed"
    assert "snapshot_failed" in evidence["failure_codes"]
    assert "unexpected_write_activity" in evidence["failure_codes"]
    assert "raw response" not in str(evidence)
    assert driver.close_calls == 1


@pytest.mark.parametrize(
    ("audit_failures", "failure_code"),
    (
        ((1,), "audit_before_close_unavailable"),
        ((2,), "audit_after_close_unavailable"),
    ),
)
def test_a1_evidence_closes_session_when_audit_fails(
    audit_failures: tuple[int, ...],
    failure_code: str,
) -> None:
    module = _script_module()
    descriptor = _descriptor()
    transport = _FakeTransport(audit_failures=audit_failures)
    driver = _FakeDriver(transport, _snapshot())
    _, opener = _collector(module, transport, driver, descriptor)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        evidence = module.collect_a1_evidence(_config(), descriptor, _setup(module), opener=opener)
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "failed"
    assert failure_code in evidence["failure_codes"]
    assert driver.close_calls == 1


def test_a1_evidence_rejects_audit_changes_during_close() -> None:
    module = _script_module()
    descriptor = _descriptor()
    transport = _FakeTransport(after_writes=1, after_access="read_write")
    driver = _FakeDriver(transport, _snapshot())
    _, opener = _collector(module, transport, driver, descriptor)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        evidence = module.collect_a1_evidence(_config(), descriptor, _setup(module), opener=opener)
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "failed"
    assert "unexpected_write_activity_after_close" in evidence["failure_codes"]
    assert "audit_after_close_access_not_read_only" in evidence["failure_codes"]
    assert "audit_counters_changed_after_close" in evidence["failure_codes"]
    assert driver.close_calls == 1


def test_a1_evidence_reports_driver_close_failure() -> None:
    module = _script_module()
    descriptor = _descriptor()
    transport = _FakeTransport()
    driver = _FakeDriver(transport, _snapshot(), close_error=RuntimeError("close failure"))
    _, opener = _collector(module, transport, driver, descriptor)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        evidence = module.collect_a1_evidence(_config(), descriptor, _setup(module), opener=opener)
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "failed"
    assert "driver_close_failed" in evidence["failure_codes"]
    assert driver.close_calls == 1


def test_a1_evidence_rejects_missing_firmware_without_retaining_identity_text() -> None:
    module = _script_module()
    descriptor = _descriptor()
    transport = _FakeTransport()
    driver = _FakeDriver(transport, _snapshot(), firmware=None)
    _, opener = _collector(module, transport, driver, descriptor)

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    try:
        evidence = module.collect_a1_evidence(_config(), descriptor, _setup(module), opener=opener)
    finally:
        monkeypatch.undo()

    assert evidence["status"] == "failed"
    assert "snapshot_firmware_unavailable" in evidence["failure_codes"]
    assert evidence["hardware"]["firmware"] is None
    assert "resource" not in str(evidence)


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


def test_a1_preflight_requires_installed_runtime_versions(monkeypatch) -> None:
    module = _script_module()
    descriptor = _descriptor()
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    monkeypatch.setattr(module, "_distribution_version", lambda name: "unavailable")

    with pytest.raises(module.A1PreflightError, match="runtime_version_unavailable"):
        module.validate_a1_preflight(_config())


def test_a1_evidence_setup_requires_explicit_safe_setup_facts(tmp_path: Path) -> None:
    module = _script_module()
    config_path = tmp_path / "a1.toml"
    config_path.write_text(
        """
[a1_evidence]
port_id = "rf_out"
actual_termination_ohm = 1000000
installed_options = ["OPT01", "OPT02"]
""".lstrip(),
        encoding="utf-8",
    )

    assert module.load_a1_evidence_setup(config_path) == module.A1EvidenceSetup(
        port_id="rf_out",
        actual_termination_ohm=1_000_000.0,
        installed_options=("OPT01", "OPT02"),
    )
    config_path.write_text("[a1_evidence]\ninstalled_options = []\n", encoding="utf-8")
    with pytest.raises(module.A1PreflightError, match="a1_evidence_invalid"):
        module.load_a1_evidence_setup(config_path)


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


def test_a1_dry_run_does_not_collect_live_evidence(monkeypatch, capsys) -> None:
    module = _script_module()
    config = _config()
    descriptor = _descriptor()
    monkeypatch.setattr(module, "load_config", lambda path: config)
    monkeypatch.setattr(module, "load_a1_evidence_setup", lambda path: _setup(module))
    monkeypatch.setattr(module, "validate_a1_preflight", lambda value: (config.rf_source, descriptor))
    monkeypatch.setattr(
        module,
        "collect_a1_evidence",
        lambda *args, **kwargs: pytest.fail("dry-run must not open a transport"),
    )

    assert module.main(["--config", "private-a1.toml"]) == 0
    assert '"status": "dry_run_ok"' in capsys.readouterr().out


def test_a1_execute_existing_output_does_not_collect_live_evidence(tmp_path: Path, monkeypatch) -> None:
    module = _script_module()
    output_path = tmp_path / "existing.json"
    output_path.write_text("already exists\n", encoding="utf-8")
    config = _config()
    descriptor = _descriptor()
    monkeypatch.setattr(module, "load_config", lambda path: config)
    monkeypatch.setattr(module, "load_a1_evidence_setup", lambda path: _setup(module))
    monkeypatch.setattr(module, "validate_a1_preflight", lambda value: (config.rf_source, descriptor))
    monkeypatch.setattr(
        module,
        "collect_a1_evidence",
        lambda *args, **kwargs: pytest.fail("existing output must stop before connection"),
    )

    assert module.main(["--config", "private-a1.toml", "--output", str(output_path), "--execute"]) == 2


def test_a1_execute_does_not_report_passed_when_evidence_file_cannot_close(
    tmp_path: Path,
    monkeypatch,
    capsys,
) -> None:
    module = _script_module()
    config = _config()
    descriptor = _descriptor()

    class CloseFailureOutput:
        def close(self) -> None:
            raise OSError("close failure")

    monkeypatch.setattr(module, "load_config", lambda path: config)
    monkeypatch.setattr(module, "load_a1_evidence_setup", lambda path: _setup(module))
    monkeypatch.setattr(module, "validate_a1_preflight", lambda value: (config.rf_source, descriptor))
    monkeypatch.setattr(module, "_open_evidence_output", lambda path: CloseFailureOutput())
    monkeypatch.setattr(module, "_replace_evidence", lambda output, evidence: None)
    monkeypatch.setattr(
        module,
        "collect_a1_evidence",
        lambda *args, **kwargs: {"status": "passed", "failure_codes": []},
    )

    assert module.main(["--config", "private-a1.toml", "--output", str(tmp_path / "a1.json"), "--execute"]) == 2
    output = capsys.readouterr().out
    assert '"failure_code": "local_output_failed"' in output
    assert '"status": "passed"' not in output


class _FactoryTransport:
    def __init__(self) -> None:
        self.resource = "TCPIP::192.0.2.83::INSTR"
        self.query_calls: list[str] = []
        self.writes: list[str] = []
        self.closed = False
        self.responses = {
            "*IDN?": "RIGOL TECHNOLOGIES,DSG830,redacted,00.01.01",
            ":FREQ?": "4MHz",
            ":LEV?": "-20.00",
            ":OUTP?": "0",
            ":MOD:STAT?": "0",
            ":PULM:STAT?": "0",
            ":SWE:STAT?": "OFF",
            ":STAT:QUES:POW:COND?": "0",
        }

    def record_event(self, direction: str, text: str) -> None:
        return None

    def query(self, command: str, **kwargs) -> str:
        self.query_calls.append(command)
        return self.responses[command]

    def write(self, command: str) -> None:
        self.writes.append(command)

    def write_bytes(self, command: bytes) -> None:
        raise AssertionError("A1 must not write bytes")

    def close(self) -> None:
        self.closed = True


def test_a1_evidence_uses_real_core_factory_and_guard_with_fake_transport(
    tmp_path: Path,
    monkeypatch,
) -> None:
    module = _script_module()
    config_path = tmp_path / "a1.toml"
    config_path.write_text(
        """
[connection]
backend = "lan"
resource = "TCPIP::192.0.2.1::INSTR"
timeout_ms = 1000
opc_timeout_ms = 2000

[scope]
driver = "rtm2032"
access = "disabled"

[rf_source]
driver = "rigol.dsg830"
resource = "TCPIP::192.0.2.83::INSTR"
access = "read_only"

[a1_evidence]
port_id = "rf_out"
actual_termination_ohm = 1000000
installed_options = ["OPT01"]
""".lstrip(),
        encoding="utf-8",
    )
    setup = module.load_a1_evidence_setup(config_path)
    monkeypatch.syspath_prepend(str(PACKAGE_ROOT / "src"))
    from wavebench_rigol_dsg830 import descriptor as source_descriptor

    # A1 is a historical, pre-promotion harness. Exercise its real Core factory
    # path with the descriptor shape that existed while evidence was collected.
    descriptor = replace(source_descriptor(), capabilities=("rf_source.idn",))

    def validate_reference(reference: str, *, expected_kind: str) -> None:
        if expected_kind == "rf_source":
            assert reference == "rigol.dsg830"

    monkeypatch.setattr(instrument_registry, "validate_instrument_reference", validate_reference)
    config = load_config(config_path)
    monkeypatch.setattr(module, "resolve_instrument_descriptor", lambda *args, **kwargs: descriptor)
    monkeypatch.setattr(
        instrument_factory,
        "resolve_instrument_descriptor",
        lambda *args, **kwargs: descriptor,
    )
    _, resolved_descriptor = module.validate_a1_preflight(config)
    assert resolved_descriptor == descriptor
    transports: list[_FactoryTransport] = []
    factory_arguments: dict[str, object] = {}

    def fake_open_transport(**kwargs):
        factory_arguments.update(kwargs)
        transport = _FactoryTransport()
        transports.append(transport)
        return transport

    def lease_factory(**kwargs):
        return ResourceLease(directory=tmp_path / "leases", **kwargs)

    monkeypatch.setattr(instrument_factory, "_open_transport", fake_open_transport)
    monkeypatch.setattr(module, "ResourceLease", lease_factory)
    evidence = module.collect_a1_evidence(
        config,
        descriptor,
        setup,
        timestamp_utc="2026-08-26T00:00:00Z",
    )

    assert evidence["status"] == "passed"
    assert factory_arguments["read_retry_attempts"] == 0
    assert factory_arguments["read_retry_delay_ms"] == 0
    assert len(transports) == 1
    assert transports[0].query_calls == [
        "*IDN?",
        ":FREQ?",
        ":LEV?",
        ":OUTP?",
        ":MOD:STAT?",
        ":PULM:STAT?",
        ":SWE:STAT?",
        ":STAT:QUES:POW:COND?",
    ]
    assert transports[0].writes == []
    assert transports[0].closed is True
    assert evidence["hardware"]["firmware"] == "00.01.01"
