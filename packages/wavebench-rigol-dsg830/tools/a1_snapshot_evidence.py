"""Collect one local, read-only A1 snapshot evidence record for a DSG830.

This is deliberately not a WaveBench CLI command or a plugin capability.  It
exists only to gather the hardware evidence required before the production
descriptor may declare ``rf_source.snapshot``.
"""

import argparse
from dataclasses import dataclass
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
from math import isfinite
import os
from pathlib import Path
import re
import tomllib
from typing import Any, Callable, Mapping, TextIO

from wavebench.config import RfSourceConfig, WaveBenchConfig, load_config
from wavebench.instruments import (
    RfAvailability,
    RfSourceSnapshot,
    open_instrument_driver,
    rf_source_snapshot_operation_artifact,
)
from wavebench.instruments.api import InstrumentDescriptor
from wavebench.instruments.registry import resolve_instrument_descriptor
from wavebench.logging import CommandLogger
from wavebench.services.resource_lease import ResourceLease


A1_EVIDENCE_SCHEMA = "wavebench.rigol_dsg830.a1_evidence.v2"
_DRIVER_ID = "rigol.dsg830"
_MODEL = "DSG830"
_PORT_ID = "rf_out"
_PRODUCTION_CAPABILITIES = ("rf_source.idn",)
_EXPECTED_QUERY_COUNT = 8
_SAFE_METADATA_TOKEN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
_MUTATION_COUNTER_KEYS = (
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
)
_AUDIT_COUNTER_KEYS = (
    "query_calls",
    "binary_query_calls",
    "blocked_query_calls",
    "blocked_binary_query_calls",
    *_MUTATION_COUNTER_KEYS,
    "blocked_session_io",
    "session_health_transitions",
)


class A1PreflightError(RuntimeError):
    """A safe, stable reason why the harness must not open a transport."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class A1EvidenceSetup:
    """Human-confirmed, non-sensitive A1 setup facts from the private TOML."""

    port_id: str
    actual_termination_ohm: float
    installed_options: tuple[str, ...]


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
    return all(
        isinstance(value, str) and value != "unavailable"
        for value in runtime.values()
    )


def load_a1_evidence_setup(path: Path) -> A1EvidenceSetup:
    """Load only the explicit, non-sensitive setup facts required by A1."""

    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise A1PreflightError("a1_evidence_invalid") from exc
    setup = raw.get("a1_evidence")
    if not isinstance(setup, Mapping):
        raise A1PreflightError("a1_evidence_not_configured")
    if set(setup) != {"port_id", "actual_termination_ohm", "installed_options"}:
        raise A1PreflightError("a1_evidence_invalid")

    port_id = setup["port_id"]
    if port_id != _PORT_ID:
        raise A1PreflightError("a1_evidence_port_must_be_rf_out")
    actual_termination_ohm = setup["actual_termination_ohm"]
    if (
        isinstance(actual_termination_ohm, bool)
        or not isinstance(actual_termination_ohm, (int, float))
        or not isfinite(actual_termination_ohm)
        or actual_termination_ohm <= 0
    ):
        raise A1PreflightError("a1_evidence_termination_invalid")
    installed_options = setup["installed_options"]
    if not isinstance(installed_options, list) or any(
        not isinstance(option, str) or _SAFE_METADATA_TOKEN.fullmatch(option) is None
        for option in installed_options
    ):
        raise A1PreflightError("a1_evidence_options_invalid")
    option_tokens = tuple(installed_options)
    if len(set(option_tokens)) != len(option_tokens) or option_tokens != tuple(sorted(option_tokens)):
        raise A1PreflightError("a1_evidence_options_invalid")
    return A1EvidenceSetup(
        port_id=port_id,
        actual_termination_ohm=float(actual_termination_ohm),
        installed_options=option_tokens,
    )


def validate_a1_preflight(config: WaveBenchConfig) -> tuple[RfSourceConfig, InstrumentDescriptor]:
    """Validate the local A1 boundary without creating a transport."""

    rf_source = config.rf_source
    if rf_source is None:
        raise A1PreflightError("rf_source_not_configured")
    if rf_source.driver != _DRIVER_ID:
        raise A1PreflightError("unexpected_rf_source_driver")
    if not rf_source.resource:
        raise A1PreflightError("rf_source_resource_missing")
    if rf_source.access != "read_only":
        raise A1PreflightError("rf_source_access_must_be_read_only")

    descriptor = resolve_instrument_descriptor(_DRIVER_ID, expected_kind="rf_source")
    if descriptor.driver_id != _DRIVER_ID or descriptor.kind != "rf_source":
        raise A1PreflightError("unexpected_descriptor_identity")
    if _MODEL not in descriptor.models:
        raise A1PreflightError("unexpected_descriptor_model")
    if tuple(descriptor.capabilities) != _PRODUCTION_CAPABILITIES:
        raise A1PreflightError("production_snapshot_gate_changed")
    if not _runtime_versions_available(_runtime_versions()):
        raise A1PreflightError("runtime_version_unavailable")
    return rf_source, descriptor


def _base_evidence(
    descriptor: InstrumentDescriptor,
    setup: A1EvidenceSetup,
    *,
    timestamp_utc: str,
) -> dict[str, object]:
    return {
        "schema": A1_EVIDENCE_SCHEMA,
        "evidence": "A1",
        "timestamp_utc": timestamp_utc,
        "driver_id": descriptor.driver_id,
        "model": _MODEL,
        "production_capabilities": list(descriptor.capabilities),
        "runtime": _runtime_versions(),
        "hardware": {
            "model": _MODEL,
            "firmware": None,
            "installed_options": list(setup.installed_options),
        },
        "setup": {
            "port_id": setup.port_id,
            "actual_termination_ohm": setup.actual_termination_ohm,
        },
        "status": "failed",
        "failure_codes": [],
        "snapshot": None,
        "audit": {"before_close": None, "after_close": None},
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


def _audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
) -> list[str]:
    failure_codes: list[str] = []
    if before_close is None:
        return ["audit_before_close_unavailable"]
    if after_close is None:
        failure_codes.append("audit_after_close_unavailable")

    if before_close["access"] != "read_only":
        failure_codes.append("audit_access_not_read_only")
    before_counters = before_close["counters"]
    assert isinstance(before_counters, dict)
    if before_counters["query_calls"] != _EXPECTED_QUERY_COUNT:
        failure_codes.append("unexpected_query_count")
    if before_counters["binary_query_calls"] != 0:
        failure_codes.append("unexpected_binary_query")
    if before_counters["blocked_session_io"] != 0:
        failure_codes.append("blocked_session_io")
    if any(before_counters[key] != 0 for key in _MUTATION_COUNTER_KEYS):
        failure_codes.append("unexpected_write_activity")
    if before_close["session_health"] != "healthy":
        failure_codes.append("session_not_healthy_before_close")

    if after_close is not None:
        if after_close["access"] != "read_only":
            failure_codes.append("audit_after_close_access_not_read_only")
        after_counters = after_close["counters"]
        assert isinstance(after_counters, dict)
        if any(after_counters[key] != 0 for key in _MUTATION_COUNTER_KEYS):
            failure_codes.append("unexpected_write_activity_after_close")
        if after_counters != before_counters:
            failure_codes.append("audit_counters_changed_after_close")
        if after_close["session_health"] != "closed":
            failure_codes.append("session_not_closed")
    return failure_codes


def _snapshot_failure_codes(snapshot: RfSourceSnapshot) -> list[str]:
    if tuple(port.port_id for port in snapshot.ports) != (_PORT_ID,):
        return ["unexpected_snapshot_topology"]

    port = snapshot.ports[0]
    observations = (
        port.frequency_hz,
        port.power_dbm,
        port.output_enabled,
        port.modulation,
        port.pulse,
        port.sweep,
        snapshot.protection,
    )
    failure_codes: list[str] = []
    if any(item.availability is not RfAvailability.VALUE for item in observations):
        failure_codes.append("snapshot_contains_unknown_state")
    if port.output_enabled.availability is RfAvailability.VALUE and port.output_enabled.value is not False:
        failure_codes.append("rf_output_not_off")
    if snapshot.protection.availability is RfAvailability.VALUE:
        protection = snapshot.protection.value
        if protection is not None and protection.active_codes:
            failure_codes.append("active_protection_condition")
    return failure_codes


def _a1_firmware(driver: object) -> str | None:
    read_firmware = getattr(driver, "a1_snapshot_firmware", None)
    if not callable(read_firmware):
        return None
    try:
        firmware = read_firmware()
    except Exception:
        return None
    if not isinstance(firmware, str) or _SAFE_METADATA_TOKEN.fullmatch(firmware) is None:
        return None
    return firmware


def collect_a1_evidence(
    config: WaveBenchConfig,
    descriptor: InstrumentDescriptor,
    setup: A1EvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Perform exactly one guarded snapshot attempt and return safe evidence.

    The caller must call :func:`validate_a1_preflight` before this function.
    No exception text, resource, raw response, or command log is retained in
    the returned record.
    """

    rf_source, checked_descriptor = validate_a1_preflight(config)
    if (
        checked_descriptor.driver_id,
        checked_descriptor.kind,
        tuple(checked_descriptor.models),
        tuple(checked_descriptor.capabilities),
    ) != (
        descriptor.driver_id,
        descriptor.kind,
        tuple(descriptor.models),
        tuple(descriptor.capabilities),
    ):
        raise A1PreflightError("descriptor_changed_after_preflight")

    evidence = _base_evidence(descriptor, setup, timestamp_utc=timestamp_utc or _utc_now())
    failure_codes: list[str] = []
    opened: Any | None = None
    before_close: dict[str, object] | None = None
    after_close: dict[str, object] | None = None
    snapshot: RfSourceSnapshot | None = None
    firmware: str | None = None

    try:
        opened = opener(
            driver_reference=rf_source.driver,
            expected_kind="rf_source",
            resource=rf_source.resource,
            configured_backend=config.connection.backend,
            timeout_ms=config.connection.timeout_ms,
            opc_timeout_ms=config.connection.opc_timeout_ms,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
            logger=CommandLogger(),
            options=rf_source.options,
            access="read_only",
            lease=ResourceLease(
                resource=rf_source.resource,
                mode="exclusive",
                operation="dsg830.a1_snapshot_evidence",
            ),
        )
    except Exception:
        failure_codes.append("session_open_failed")
    else:
        transport = getattr(opened, "transport", None)
        driver = getattr(opened, "driver", None)
        audit_snapshot = getattr(transport, "audit_snapshot", None)
        try:
            get_snapshot = getattr(driver, "get_rf_snapshot", None)
            if not callable(get_snapshot):
                failure_codes.append("snapshot_method_missing")
            else:
                candidate = get_snapshot()
                if not isinstance(candidate, RfSourceSnapshot):
                    failure_codes.append("invalid_snapshot_type")
                else:
                    snapshot = candidate
                    firmware = _a1_firmware(driver)
                    if firmware is None:
                        failure_codes.append("snapshot_firmware_unavailable")
        except Exception:
            failure_codes.append("snapshot_failed")
        finally:
            if callable(audit_snapshot):
                try:
                    before_close = _sanitize_audit(audit_snapshot())
                except Exception:
                    failure_codes.append("audit_before_close_unavailable")
            else:
                failure_codes.append("audit_before_close_unavailable")

            close = getattr(driver, "close", None)
            if not callable(close):
                failure_codes.append("driver_close_missing")
            else:
                try:
                    close()
                except Exception:
                    failure_codes.append("driver_close_failed")

            if callable(audit_snapshot):
                try:
                    after_close = _sanitize_audit(audit_snapshot())
                except Exception:
                    failure_codes.append("audit_after_close_unavailable")

    if snapshot is not None:
        evidence["snapshot"] = rf_source_snapshot_operation_artifact(snapshot)
        failure_codes.extend(_snapshot_failure_codes(snapshot))
    hardware = evidence["hardware"]
    assert isinstance(hardware, dict)
    hardware["firmware"] = firmware
    evidence["audit"] = {"before_close": before_close, "after_close": after_close}
    runtime = evidence["runtime"]
    assert isinstance(runtime, Mapping)
    if not _runtime_versions_available(runtime):
        failure_codes.append("runtime_version_unavailable")
    failure_codes.extend(_audit_failure_codes(before_close, after_close))
    evidence["failure_codes"] = sorted(set(failure_codes))
    evidence["status"] = "passed" if not evidence["failure_codes"] else "failed"
    return evidence


def _open_evidence_output(path: Path) -> TextIO:
    if not path.parent.is_dir():
        raise A1PreflightError("invalid_evidence_output_path")
    try:
        file_descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise A1PreflightError("invalid_evidence_output_path") from exc
    return os.fdopen(file_descriptor, "w", encoding="utf-8")


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
            "schema": A1_EVIDENCE_SCHEMA,
            "status": evidence["status"],
            "failure_codes": evidence["failure_codes"],
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True, type=Path, help="Private A1 TOML configuration")
    parser.add_argument("--output", type=Path, help="New local JSON evidence file")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly permit one live, read-only snapshot attempt",
    )
    args = parser.parse_args(argv)

    try:
        config = load_config(args.config)
        setup = load_a1_evidence_setup(args.config)
        _, descriptor = validate_a1_preflight(config)
    except A1PreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "config_or_descriptor_invalid"}))
        return 2

    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": A1_EVIDENCE_SCHEMA,
                    "status": "dry_run_ok",
                    "driver_id": descriptor.driver_id,
                    "production_capabilities": list(descriptor.capabilities),
                    "a1_setup": {
                        "port_id": setup.port_id,
                        "actual_termination_ohm": setup.actual_termination_ohm,
                        "installed_options": list(setup.installed_options),
                    },
                    "will_connect": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required with --execute")

    output: TextIO | None = None
    try:
        output = _open_evidence_output(args.output)
        _replace_evidence(
            output,
            {
                "schema": A1_EVIDENCE_SCHEMA,
                "evidence": "A1",
                "status": "started",
            },
        )
    except A1PreflightError as exc:
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
            evidence = collect_a1_evidence(config, descriptor, setup)
        except A1PreflightError as exc:
            evidence = _base_evidence(descriptor, setup, timestamp_utc=_utc_now())
            evidence["failure_codes"] = [exc.code]
        except Exception:
            evidence = _base_evidence(descriptor, setup, timestamp_utc=_utc_now())
            evidence["failure_codes"] = ["local_harness_failed"]
        _replace_evidence(output, evidence)
    except Exception:
        try:
            output.close()
        except Exception:
            pass
        print(json.dumps({"status": "evidence_write_failed", "failure_code": "local_output_failed"}))
        return 2
    try:
        output.close()
    except Exception:
        print(json.dumps({"status": "evidence_write_failed", "failure_code": "local_output_failed"}))
        return 2

    print(_summary(evidence))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":  # pragma: no cover - exercised through the local harness entry point.
    raise SystemExit(main())
