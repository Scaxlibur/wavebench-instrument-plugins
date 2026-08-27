"""Collect private A5-0 read-only trigger-configuration evidence for a DSG830.

This diagnostic does not validate a physical trigger or synchronization path.
It only records the instrument's logical Pulse/Sweep trigger configuration
through a temporary in-memory descriptor.  The production descriptor remains
unchanged.  The diagnostic never enables RF output, changes a rear-panel
setting, arms or fires Pulse/Sweep, or sends a trigger command.

The input RF configuration must already be isolated, ``read_only``, and have
read retries disabled.  Running without ``--diagnose`` performs static
preflight only.  ``--diagnose`` performs one bounded zero-write session and
requires a new private output file.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import re
import tomllib
from typing import Any, Callable, Mapping, TextIO

from wavebench.config import WaveBenchConfig, load_config
from wavebench.instruments.api import InstrumentDescriptor
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.factory import open_instrument_driver
from wavebench.instruments.registry import resolve_instrument_descriptor
from wavebench.instruments.rf_source_capabilities import validate_rf_source_descriptor
from wavebench.instruments.rf_source_extensions import (
    RF_SOURCE_CONTRACT_VERSION,
    RfAvailability,
    RfExternalGatePolarity,
    RfExternalTriggerEdge,
    RfFeature,
    RfFeatureCapability,
    RfFeatureDirection,
    RfModulationState,
    RfProtectionStatus,
    RfPulseState,
    RfPulseTriggerMode,
    RfSourceDescriptorExtensions,
    RfSourceSnapshot,
    RfSweepMode,
    RfSweepState,
    RfSweepTriggerMode,
    RfTriggerProfile,
    RfTriggerSnapshot,
    rf_source_snapshot_operation_artifact,
)
from wavebench.logging import CommandLogger
from wavebench.services.resource_lease import ResourceLease
from wavebench.services.rf_source_service import RfSourceService


A5_TRIGGER_SNAPSHOT_EVIDENCE_SCHEMA = "wavebench.rigol_dsg830.a5_trigger_snapshot_evidence.v1"
_DRIVER_ID = "rigol.dsg830"
_MODEL = "DSG830"
_PORT_ID = "rf_out"
_PRODUCTION_CAPABILITIES = (
    "rf_source.idn",
    "rf_source.snapshot",
    "rf_source.cw_configure",
    "rf_source.output",
    "rf_source.modulation_configure",
    "rf_source.modulation_disable",
    "rf_source.modulated_output_enable",
    "rf_source.pulse_configure",
    "rf_source.sweep_configure",
)
_SNAPSHOT_QUERY_COUNT = 8
_TRIGGER_QUERY_COUNT = 6
_SAFE_METADATA_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_AUDIT_COUNTER_KEYS = (
    "query_calls",
    "binary_query_calls",
    "blocked_query_calls",
    "blocked_binary_query_calls",
    "write_requests",
    "write_attempts",
    "write_transmitted",
    "write_completed",
    "write_outcome_unknown",
    "binary_write_requests",
    "binary_write_attempts",
    "binary_write_transmitted",
    "binary_write_completed",
    "binary_write_outcome_unknown",
    "blocked_write_requests",
    "blocked_binary_write_requests",
    "instrument_mutation_writes",
    "instrument_mutation_writes_completed",
    "blocked_session_io",
    "session_health_transitions",
)
_WRITE_COUNTER_KEYS = (
    "write_requests",
    "write_attempts",
    "write_transmitted",
    "write_completed",
    "write_outcome_unknown",
    "binary_write_requests",
    "binary_write_attempts",
    "binary_write_transmitted",
    "binary_write_completed",
    "binary_write_outcome_unknown",
    "instrument_mutation_writes",
    "instrument_mutation_writes_completed",
)


class A5TriggerSnapshotPreflightError(RuntimeError):
    """A stable reason to reject the private A5-0 diagnostic before I/O."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class A5TriggerSnapshotEvidenceSetup:
    """Non-sensitive target selection for the logical A5-0 diagnostic."""

    port_id: str


@dataclass(frozen=True, slots=True)
class A5TriggerSnapshotPreflight:
    """Static descriptor facts accepted before the read-only session opens."""

    production_descriptor: InstrumentDescriptor
    evidence_descriptor: InstrumentDescriptor


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _distribution_version(name: str) -> str:
    try:
        return version(name)
    except PackageNotFoundError:
        return "unavailable"


def _runtime_versions() -> dict[str, str]:
    return {
        "wavebench_version": _distribution_version("wavebench"),
        "plugin_version": _distribution_version("wavebench-rigol-dsg830"),
    }


def _runtime_versions_available(runtime: Mapping[str, object]) -> bool:
    return all(isinstance(value, str) and value != "unavailable" for value in runtime.values())


def load_a5_trigger_snapshot_evidence_setup(path: Path) -> A5TriggerSnapshotEvidenceSetup:
    """Load only the explicit logical RF output target from a private setup file."""

    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise A5TriggerSnapshotPreflightError("a5_trigger_snapshot_evidence_invalid") from exc
    evidence = raw.get("a5_trigger_snapshot_evidence")
    if not isinstance(evidence, Mapping):
        raise A5TriggerSnapshotPreflightError("a5_trigger_snapshot_evidence_not_configured")
    if set(evidence) != {"port_id"}:
        raise A5TriggerSnapshotPreflightError("a5_trigger_snapshot_evidence_invalid")
    if evidence.get("port_id") != _PORT_ID:
        raise A5TriggerSnapshotPreflightError("a5_trigger_snapshot_evidence_port_must_be_rf_out")
    return A5TriggerSnapshotEvidenceSetup(port_id=_PORT_ID)


def _require_no_retries(config: WaveBenchConfig) -> None:
    if config.connection.read_retry_attempts != 0 or config.connection.read_retry_delay_ms != 0:
        raise A5TriggerSnapshotPreflightError("rf_source_retries_must_be_disabled")


def _trigger_profile() -> RfTriggerProfile:
    return RfTriggerProfile(
        state_readable=True,
        pulse_trigger_modes=(
            RfPulseTriggerMode.AUTOMATIC,
            RfPulseTriggerMode.BUS,
            RfPulseTriggerMode.EXTERNAL,
            RfPulseTriggerMode.EXTERNAL_GATE,
            RfPulseTriggerMode.KEY,
        ),
        pulse_external_trigger_edges=(
            RfExternalTriggerEdge.NEGATIVE,
            RfExternalTriggerEdge.POSITIVE,
        ),
        pulse_external_gate_polarities=(
            RfExternalGatePolarity.INVERTED,
            RfExternalGatePolarity.NORMAL,
        ),
        sweep_modes=(RfSweepMode.CONTINUOUS, RfSweepMode.SINGLE),
        sweep_period_trigger_modes=(
            RfSweepTriggerMode.AUTOMATIC,
            RfSweepTriggerMode.BUS,
            RfSweepTriggerMode.EXTERNAL,
            RfSweepTriggerMode.KEY,
        ),
        sweep_point_trigger_modes=(
            RfSweepTriggerMode.AUTOMATIC,
            RfSweepTriggerMode.BUS,
            RfSweepTriggerMode.EXTERNAL,
            RfSweepTriggerMode.KEY,
        ),
    )


def _build_evidence_descriptor(production: InstrumentDescriptor) -> InstrumentDescriptor:
    """Create one private read-only descriptor without registering or mutating production."""

    extensions = production.rf_source_extensions
    if not isinstance(extensions, RfSourceDescriptorExtensions):
        raise A5TriggerSnapshotPreflightError("rf_source_extensions_invalid")
    if extensions.contract_version != RF_SOURCE_CONTRACT_VERSION:
        raise A5TriggerSnapshotPreflightError("rf_source_extensions_invalid")
    if tuple(port.port_id for port in extensions.topology.ports) != (_PORT_ID,):
        raise A5TriggerSnapshotPreflightError("unexpected_rf_topology")
    if "rf_source.trigger_snapshot" in production.capabilities:
        raise A5TriggerSnapshotPreflightError("production_trigger_snapshot_gate_changed")
    if any(feature.feature is RfFeature.TRIGGER for feature in extensions.features):
        raise A5TriggerSnapshotPreflightError("production_trigger_feature_gate_changed")
    trigger_feature = RfFeatureCapability(
        feature=RfFeature.TRIGGER,
        directions=(RfFeatureDirection.READ,),
        port_ids=(_PORT_ID,),
        profile=_trigger_profile(),
    )
    evidence = replace(
        production,
        capabilities=(*production.capabilities, "rf_source.trigger_snapshot"),
        rf_source_extensions=replace(
            extensions,
            features=tuple(
                sorted(
                    (*extensions.features, trigger_feature),
                    key=lambda item: item.feature.value,
                )
            ),
        ),
    )
    try:
        validate_rf_source_descriptor(evidence)
    except Exception as exc:
        raise A5TriggerSnapshotPreflightError(
            "a5_trigger_snapshot_evidence_descriptor_invalid"
        ) from exc
    return evidence


def validate_a5_trigger_snapshot_preflight(
    rf_config: WaveBenchConfig,
    setup: A5TriggerSnapshotEvidenceSetup,
) -> A5TriggerSnapshotPreflight:
    """Fail closed before opening the isolated read-only RF transport."""

    rf_source = rf_config.rf_source
    if rf_source is None:
        raise A5TriggerSnapshotPreflightError("rf_source_not_configured")
    if rf_source.driver != _DRIVER_ID:
        raise A5TriggerSnapshotPreflightError("unexpected_rf_source_driver")
    if not isinstance(rf_source.resource, str) or not rf_source.resource.strip():
        raise A5TriggerSnapshotPreflightError("rf_source_resource_missing")
    if rf_source.access != "read_only":
        raise A5TriggerSnapshotPreflightError("rf_source_base_access_must_be_read_only")
    if setup.port_id != _PORT_ID:
        raise A5TriggerSnapshotPreflightError("a5_trigger_snapshot_evidence_port_must_be_rf_out")
    _require_no_retries(rf_config)
    production = resolve_instrument_descriptor(_DRIVER_ID, expected_kind="rf_source")
    if production.driver_id != _DRIVER_ID or production.kind != "rf_source":
        raise A5TriggerSnapshotPreflightError("unexpected_descriptor_identity")
    if _MODEL not in production.models:
        raise A5TriggerSnapshotPreflightError("unexpected_descriptor_model")
    if tuple(production.capabilities) != _PRODUCTION_CAPABILITIES:
        raise A5TriggerSnapshotPreflightError("production_capabilities_changed")
    if "rf_source.trigger_snapshot" in production.capabilities:
        raise A5TriggerSnapshotPreflightError("production_trigger_snapshot_gate_changed")
    if not _runtime_versions_available(_runtime_versions()):
        raise A5TriggerSnapshotPreflightError("runtime_version_unavailable")
    return A5TriggerSnapshotPreflight(
        production_descriptor=production,
        evidence_descriptor=_build_evidence_descriptor(production),
    )


def _base_evidence(
    preflight: A5TriggerSnapshotPreflight,
    setup: A5TriggerSnapshotEvidenceSetup,
    *,
    timestamp_utc: str,
) -> dict[str, object]:
    return {
        "schema": A5_TRIGGER_SNAPSHOT_EVIDENCE_SCHEMA,
        "evidence": "A5_TRIGGER_SNAPSHOT",
        "operation_mode": "diagnostic",
        "timestamp_utc": timestamp_utc,
        "driver_id": preflight.production_descriptor.driver_id,
        "model": _MODEL,
        "production_capabilities": list(preflight.production_descriptor.capabilities),
        "runtime": _runtime_versions(),
        "hardware": {"model": _MODEL, "firmware": None},
        "setup": {"port_id": setup.port_id},
        "status": "failed",
        "failure_codes": [],
        "initial_snapshot": None,
        "trigger_snapshot": None,
        "final_snapshot": None,
        "rf_audit": {"before_close": None, "after_close": None},
    }


def _sanitize_audit(raw: object) -> dict[str, object] | None:
    if not isinstance(raw, Mapping):
        return None
    access = raw.get("access")
    counters = raw.get("counters")
    session = raw.get("session")
    if not isinstance(access, str) or not isinstance(counters, Mapping) or not isinstance(session, Mapping):
        return None
    sanitized_counters: dict[str, int] = {}
    for key in _AUDIT_COUNTER_KEYS:
        value = counters.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            return None
        sanitized_counters[key] = value
    health = session.get("health")
    if not isinstance(health, str):
        return None
    return {"access": access, "counters": sanitized_counters, "session_health": health}


def _audit_snapshot(transport: object) -> dict[str, object] | None:
    reader = getattr(transport, "audit_snapshot", None)
    if not callable(reader):
        return None
    try:
        return _sanitize_audit(reader())
    except Exception:
        return None


def _close_driver(driver: object) -> str | None:
    close = getattr(driver, "close", None)
    if not callable(close):
        return "driver_close_missing"
    try:
        close()
    except Exception:
        return "driver_close_failed"
    return None


def _snapshot_failure_codes(snapshot: RfSourceSnapshot, *, phase: str) -> list[str]:
    if tuple(port.port_id for port in snapshot.ports) != (_PORT_ID,):
        return [f"{phase}_snapshot_topology_invalid"]
    port = snapshot.ports[0]
    values = (
        port.frequency_hz,
        port.power_dbm,
        port.output_enabled,
        port.modulation,
        port.pulse,
        port.sweep,
        snapshot.protection,
    )
    if any(value.availability is not RfAvailability.VALUE for value in values):
        return [f"{phase}_snapshot_contains_unknown_state"]
    codes: list[str] = []
    if port.output_enabled.value is not False:
        codes.append(f"{phase}_rf_output_not_off")
    if port.modulation.value is not RfModulationState.DISABLED:
        codes.append(f"{phase}_modulation_not_disabled")
    if port.pulse.value is not RfPulseState.DISABLED:
        codes.append(f"{phase}_pulse_not_disabled")
    if port.sweep.value is not RfSweepState.DISABLED:
        codes.append(f"{phase}_sweep_not_disabled")
    protection = snapshot.protection.value
    if not isinstance(protection, RfProtectionStatus) or protection.active_codes:
        codes.append(f"{phase}_active_protection_condition")
    return codes


def _firmware(driver: object) -> str | None:
    reader = getattr(driver, "a1_snapshot_firmware", None)
    if not callable(reader):
        return None
    try:
        firmware = reader()
    except Exception:
        return None
    if not isinstance(firmware, str) or _SAFE_METADATA_TOKEN.fullmatch(firmware) is None:
        return None
    return firmware


def _trigger_snapshot_failure_codes(snapshot: object) -> list[str]:
    if not isinstance(snapshot, RfTriggerSnapshot):
        return ["trigger_snapshot_invalid"]
    return [] if snapshot.port_id == _PORT_ID else ["trigger_snapshot_port_invalid"]


def _expected_diagnostic_queries() -> int:
    return 2 * _SNAPSHOT_QUERY_COUNT + _TRIGGER_QUERY_COUNT


def _rf_audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
    *,
    expected_queries: int | None,
) -> list[str]:
    if before_close is None:
        return ["rf_audit_before_close_unavailable"]
    codes: list[str] = []
    if before_close["access"] != "read_only":
        codes.append("rf_audit_access_invalid")
    counters = before_close["counters"]
    assert isinstance(counters, Mapping)
    if any(counters[key] != 0 for key in _WRITE_COUNTER_KEYS):
        codes.append("rf_readonly_unexpected_write_activity")
    if counters["blocked_session_io"] != 0:
        codes.append("rf_blocked_session_io")
    if expected_queries is not None:
        if counters["query_calls"] != expected_queries:
            codes.append("unexpected_rf_query_count")
        if before_close["session_health"] != "healthy":
            codes.append("rf_session_not_healthy_before_close")
    if after_close is None:
        return [*codes, "rf_audit_after_close_unavailable"]
    if after_close["access"] != "read_only":
        codes.append("rf_audit_after_close_access_invalid")
    after_counters = after_close["counters"]
    assert isinstance(after_counters, Mapping)
    if after_counters != counters:
        codes.append("rf_audit_counters_changed_after_close")
    if after_close["session_health"] != "closed":
        codes.append("rf_session_not_closed")
    return codes


def _base_descriptor_matches(
    preflight: A5TriggerSnapshotPreflight,
    current: InstrumentDescriptor,
) -> bool:
    return (
        current.driver_id == preflight.production_descriptor.driver_id
        and current.kind == preflight.production_descriptor.kind
        and tuple(current.models) == tuple(preflight.production_descriptor.models)
        and tuple(current.capabilities) == tuple(preflight.production_descriptor.capabilities)
    )


def collect_a5_trigger_snapshot_diagnostic_evidence(
    rf_config: WaveBenchConfig,
    preflight: A5TriggerSnapshotPreflight,
    setup: A5TriggerSnapshotEvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Run exactly one bounded logical trigger-configuration read-only diagnostic."""

    current = validate_a5_trigger_snapshot_preflight(rf_config, setup)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A5TriggerSnapshotPreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(preflight, setup, timestamp_utc=timestamp_utc or _utc_now())
    failure_codes: list[str] = []
    rf_driver: object | None = None
    rf_transport: object | None = None
    trigger_read = False
    final_rf_off_confirmed = False

    try:
        rf_source = rf_config.rf_source
        assert rf_source is not None
        opened = opener(
            driver_reference=rf_source.driver,
            expected_kind="rf_source",
            resource=rf_source.resource or "",
            configured_backend=rf_config.connection.backend,
            timeout_ms=rf_config.connection.timeout_ms,
            opc_timeout_ms=rf_config.connection.opc_timeout_ms,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
            logger=CommandLogger(),
            options=rf_source.options,
            access="read_only",
            lease=ResourceLease(
                resource=rf_source.resource or "",
                mode="exclusive",
                operation="dsg830.a5_trigger_snapshot_diagnostic",
            ),
        )
        rf_driver = opened.driver
        rf_transport = opened.transport
        if getattr(opened, "descriptor", None) != preflight.production_descriptor:
            raise A5TriggerSnapshotPreflightError("descriptor_changed_after_preflight")
        try:
            validate_declared_capabilities(preflight.evidence_descriptor, rf_driver)
        except Exception as exc:
            raise A5TriggerSnapshotPreflightError(
                "a5_trigger_snapshot_evidence_driver_invalid"
            ) from exc
        rf_service = RfSourceService(
            config=rf_config,
            logger=CommandLogger(),
            session=rf_driver,
            descriptor=preflight.evidence_descriptor,
            transport=rf_transport,
            session_state=opened.session_state,
        )
        initial = rf_service.snapshot()
        evidence["initial_snapshot"] = rf_source_snapshot_operation_artifact(initial)
        hardware = evidence["hardware"]
        assert isinstance(hardware, dict)
        hardware["firmware"] = _firmware(rf_driver)
        if hardware["firmware"] is None:
            failure_codes.append("snapshot_firmware_unavailable")
        failure_codes.extend(_snapshot_failure_codes(initial, phase="initial"))
        if not failure_codes:
            try:
                trigger_snapshot, artifact = rf_service.trigger_snapshot_with_artifact(setup.port_id)
                evidence["trigger_snapshot"] = artifact
                trigger_read = True
                failure_codes.extend(_trigger_snapshot_failure_codes(trigger_snapshot))
            except Exception:
                failure_codes.append("trigger_snapshot_read_failed")
        if trigger_read:
            try:
                final = rf_service.snapshot()
                evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final)
                final_failures = _snapshot_failure_codes(final, phase="final")
                failure_codes.extend(final_failures)
                final_rf_off_confirmed = not final_failures
            except Exception:
                failure_codes.append("final_rf_snapshot_failed")
    except A5TriggerSnapshotPreflightError as exc:
        failure_codes.append(exc.code)
    except Exception:
        failure_codes.append("local_harness_failed")
    finally:
        if rf_driver is not None:
            before_close = _audit_snapshot(rf_transport)
            close_error = _close_driver(rf_driver)
            after_close = _audit_snapshot(rf_transport)
            evidence["rf_audit"] = {"before_close": before_close, "after_close": after_close}
            if close_error is not None:
                failure_codes.append(close_error)
            failure_codes.extend(
                _rf_audit_failure_codes(
                    before_close,
                    after_close,
                    expected_queries=(
                        _expected_diagnostic_queries()
                        if trigger_read and final_rf_off_confirmed
                        else None
                    ),
                )
            )

    if not final_rf_off_confirmed:
        failure_codes.append("final_rf_off_not_confirmed")
    if not _runtime_versions_available(evidence["runtime"]):
        failure_codes.append("runtime_version_unavailable")
    evidence["failure_codes"] = sorted(set(failure_codes))
    evidence["status"] = "passed" if not evidence["failure_codes"] else "failed"
    return evidence


def _open_evidence_output(path: Path) -> TextIO:
    if not path.parent.is_dir():
        raise A5TriggerSnapshotPreflightError("invalid_evidence_output_path")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise A5TriggerSnapshotPreflightError("invalid_evidence_output_path") from exc
    return os.fdopen(descriptor, "w", encoding="utf-8")


def _replace_evidence(output: TextIO, evidence: Mapping[str, object]) -> None:
    text = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.seek(0)
    output.truncate()
    output.write(text)
    output.flush()
    os.fsync(output.fileno())


def _summary(evidence: Mapping[str, object]) -> str:
    return json.dumps(
        {
            "schema": A5_TRIGGER_SNAPSHOT_EVIDENCE_SCHEMA,
            "status": evidence["status"],
            "failure_codes": evidence["failure_codes"],
            "trigger_snapshot_read": evidence.get("trigger_snapshot") is not None,
            "rf_output_confirmed_off": evidence["status"] == "passed",
            "will_write": False,
            "will_trigger": False,
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rf-config", required=True, type=Path, help="Private read-only RF TOML")
    parser.add_argument("--setup", required=True, type=Path, help="Private A5-0 setup TOML")
    parser.add_argument("--output", type=Path, help="New local JSON evidence file")
    parser.add_argument(
        "--diagnose",
        action="store_true",
        help="Explicitly run the bounded read-only logical trigger-configuration diagnostic",
    )
    args = parser.parse_args(argv)

    try:
        rf_config = load_config(args.rf_config)
        setup = load_a5_trigger_snapshot_evidence_setup(args.setup)
        preflight = validate_a5_trigger_snapshot_preflight(rf_config, setup)
    except A5TriggerSnapshotPreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "config_or_descriptor_invalid"}))
        return 2

    if not args.diagnose:
        print(
            json.dumps(
                {
                    "schema": A5_TRIGGER_SNAPSHOT_EVIDENCE_SCHEMA,
                    "status": "dry_run_ok",
                    "driver_id": preflight.production_descriptor.driver_id,
                    "production_capabilities": list(preflight.production_descriptor.capabilities),
                    "a5_trigger_snapshot_setup": _base_evidence(
                        preflight,
                        setup,
                        timestamp_utc="dry_run",
                    )["setup"],
                    "will_connect": False,
                    "will_write": False,
                    "will_enable_rf_output": False,
                    "will_arm_sweep": False,
                    "will_fire_sweep": False,
                    "will_trigger": False,
                    "will_use_scope": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required with --diagnose")

    output: TextIO | None = None
    try:
        output = _open_evidence_output(args.output)
        _replace_evidence(
            output,
            {
                "schema": A5_TRIGGER_SNAPSHOT_EVIDENCE_SCHEMA,
                "evidence": "A5_TRIGGER_SNAPSHOT",
                "status": "started",
            },
        )
    except A5TriggerSnapshotPreflightError as exc:
        if output is not None:
            try:
                output.close()
            except Exception:
                pass
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        if output is not None:
            try:
                output.close()
            except Exception:
                pass
        print(json.dumps({"status": "preflight_failed", "failure_code": "local_output_invalid"}))
        return 2

    try:
        try:
            evidence = collect_a5_trigger_snapshot_diagnostic_evidence(rf_config, preflight, setup)
        except A5TriggerSnapshotPreflightError as exc:
            evidence = _base_evidence(preflight, setup, timestamp_utc=_utc_now())
            evidence["failure_codes"] = [exc.code]
            evidence["status"] = "failed"
        except Exception:
            evidence = _base_evidence(preflight, setup, timestamp_utc=_utc_now())
            evidence["failure_codes"] = ["local_harness_failed"]
            evidence["status"] = "failed"
        _replace_evidence(output, evidence)
    finally:
        output.close()

    print(_summary(evidence))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
