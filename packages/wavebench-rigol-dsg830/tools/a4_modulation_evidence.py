"""Collect one local A4 RF-OFF modulation evidence record for a RIGOL DSG830.

This local-only harness gathers the controlled hardware evidence required before
the production descriptor may declare ``rf_source.modulation_configure``.  It
never modifies the production descriptor, never opens RF output, and never
uses the scope.  A private read-only RF config and a resource-free A4 setup
file are required; ``--execute`` is the explicit write boundary.

One invocation validates exactly one internal-sine AM, FM, or PM profile.  The
RF output must be confirmed OFF before the fixed configuration sequence.  A
successful configuration is immediately followed by a bounded, mode-specific
modulation-disable transaction and an independent final snapshot.  The final
state must keep RF output and modulation disabled; this is not evidence that
modulated RF output is safe or authorized.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from importlib.metadata import PackageNotFoundError, version
import json
from math import isfinite
import os
from pathlib import Path
import re
import tomllib
from typing import Any, Callable, Mapping, TextIO

from wavebench.config import WaveBenchConfig, load_config
from wavebench.instruments import (
    RF_SOURCE_CONTRACT_VERSION,
    RfAvailability,
    RfFeature,
    RfFeatureCapability,
    RfFeatureDirection,
    RfModulationDisableRequest,
    RfModulationKind,
    RfModulationModeProfile,
    RfModulationProfile,
    RfModulationRequest,
    RfModulationSource,
    RfModulationState,
    RfModulationValueUnit,
    RfModulationWaveform,
    RfProtectionStatus,
    RfPulseState,
    RfSourceDescriptorExtensions,
    RfSourceSnapshot,
    RfSweepState,
    open_instrument_driver,
    rf_source_snapshot_operation_artifact,
)
from wavebench.instruments.api import InstrumentDescriptor
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.registry import resolve_instrument_descriptor
from wavebench.instruments.rf_source_capabilities import validate_rf_source_descriptor
from wavebench.logging import CommandLogger
from wavebench.services.resource_lease import ResourceLease
from wavebench.services.rf_source_service import RfSourceService


A4_EVIDENCE_SCHEMA = "wavebench.rigol_dsg830.a4_evidence.v1"
_DRIVER_ID = "rigol.dsg830"
_MODEL = "DSG830"
_PORT_ID = "rf_out"
_PRODUCTION_CAPABILITIES = (
    "rf_source.idn",
    "rf_source.snapshot",
    "rf_source.cw_configure",
    "rf_source.output",
)
_SNAPSHOT_QUERY_COUNT = 8
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


class A4PreflightError(RuntimeError):
    """A stable reason to refuse A4 before opening an RF transport."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class A4EvidenceSetup:
    """Human-confirmed, non-sensitive A4 facts from the private setup."""

    port_id: str
    actual_termination_ohm: float
    installed_options: tuple[str, ...]
    request: RfModulationRequest


@dataclass(frozen=True, slots=True)
class A4Preflight:
    """Static facts accepted before a controlled A4 session may open."""

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


def _finite(value: object, code: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value):
        raise A4PreflightError(code)
    normalized = float(value)
    if minimum is not None and normalized < minimum:
        raise A4PreflightError(code)
    return normalized


def _safe_options(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or _SAFE_METADATA_TOKEN.fullmatch(item) is None for item in value
    ):
        raise A4PreflightError("a4_evidence_options_invalid")
    options = tuple(value)
    if len(set(options)) != len(options) or options != tuple(sorted(options)):
        raise A4PreflightError("a4_evidence_options_invalid")
    return options


def _mode_value_field(kind: RfModulationKind) -> str:
    return {
        RfModulationKind.AM: "depth_percent",
        RfModulationKind.FM: "frequency_deviation_hz",
        RfModulationKind.PM: "phase_deviation_rad",
    }[kind]


def _request_from_setup(evidence: Mapping[str, object]) -> RfModulationRequest:
    raw_kind = evidence.get("modulation_kind")
    if not isinstance(raw_kind, str):
        raise A4PreflightError("a4_evidence_modulation_kind_invalid")
    try:
        kind = RfModulationKind(raw_kind.lower())
    except ValueError as exc:
        raise A4PreflightError("a4_evidence_modulation_kind_invalid") from exc
    value_field = _mode_value_field(kind)
    base_fields = {
        "port_id",
        "actual_termination_ohm",
        "installed_options",
        "modulation_kind",
        "internal_frequency_hz",
        value_field,
    }
    if set(evidence) != base_fields:
        raise A4PreflightError("a4_evidence_invalid")
    value = _finite(evidence[value_field], "a4_evidence_modulation_value_invalid", minimum=0.0)
    internal_frequency_hz = _finite(
        evidence["internal_frequency_hz"],
        "a4_evidence_internal_frequency_invalid",
        minimum=1e-12,
    )
    request_fields: dict[str, object] = {
        "port_id": _PORT_ID,
        "kind": kind,
        "internal_frequency_hz": internal_frequency_hz,
        value_field: value,
    }
    try:
        return RfModulationRequest(**request_fields)  # type: ignore[arg-type]
    except ValueError as exc:
        raise A4PreflightError("a4_evidence_modulation_value_invalid") from exc


def load_a4_evidence_setup(path: Path) -> A4EvidenceSetup:
    """Load only the explicit, non-sensitive facts required for A4."""

    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise A4PreflightError("a4_evidence_invalid") from exc
    evidence = raw.get("a4_evidence")
    if not isinstance(evidence, Mapping):
        raise A4PreflightError("a4_evidence_not_configured")
    if evidence.get("port_id") != _PORT_ID:
        raise A4PreflightError("a4_evidence_port_must_be_rf_out")
    actual_termination_ohm = _finite(
        evidence.get("actual_termination_ohm"),
        "a4_evidence_termination_invalid",
        minimum=1e-12,
    )
    return A4EvidenceSetup(
        port_id=_PORT_ID,
        actual_termination_ohm=actual_termination_ohm,
        installed_options=_safe_options(evidence.get("installed_options")),
        request=_request_from_setup(evidence),
    )


def _require_no_retries(config: WaveBenchConfig) -> None:
    if config.connection.read_retry_attempts != 0 or config.connection.read_retry_delay_ms != 0:
        raise A4PreflightError("rf_source_retries_must_be_disabled")


def _mode_profiles() -> tuple[RfModulationModeProfile, ...]:
    return (
        RfModulationModeProfile(
            kind=RfModulationKind.AM,
            value_unit=RfModulationValueUnit.PERCENT,
            value_min=0.0,
            value_max=100.0,
            internal_frequency_min_hz=10.0,
            internal_frequency_max_hz=100_000.0,
        ),
        RfModulationModeProfile(
            kind=RfModulationKind.FM,
            value_unit=RfModulationValueUnit.HZ,
            value_min=0.1,
            value_max=1_000_000.0,
            internal_frequency_min_hz=10.0,
            internal_frequency_max_hz=100_000.0,
        ),
        RfModulationModeProfile(
            kind=RfModulationKind.PM,
            value_unit=RfModulationValueUnit.RAD,
            value_min=0.0,
            value_max=5.0,
            internal_frequency_min_hz=10.0,
            internal_frequency_max_hz=100_000.0,
        ),
    )


def _build_evidence_descriptor(production: InstrumentDescriptor) -> InstrumentDescriptor:
    """Create an in-memory, A4-only modulation descriptor; never register it."""

    extensions = production.rf_source_extensions
    if not isinstance(extensions, RfSourceDescriptorExtensions):
        raise A4PreflightError("rf_source_extensions_invalid")
    if extensions.contract_version != RF_SOURCE_CONTRACT_VERSION:
        raise A4PreflightError("rf_source_extensions_invalid")
    if tuple(port.port_id for port in extensions.topology.ports) != (_PORT_ID,):
        raise A4PreflightError("unexpected_rf_topology")
    features = extensions.features
    if any(feature.feature is RfFeature.MODULATION for feature in features):
        raise A4PreflightError("production_modulation_gate_changed")
    if sum(feature.feature is RfFeature.CW for feature in features) != 1:
        raise A4PreflightError("production_cw_contract_invalid")
    if sum(feature.feature is RfFeature.OUTPUT for feature in features) != 1:
        raise A4PreflightError("production_output_contract_invalid")
    modulation_feature = RfFeatureCapability(
        feature=RfFeature.MODULATION,
        directions=(
            RfFeatureDirection.CONFIGURE,
            RfFeatureDirection.DISABLE,
            RfFeatureDirection.READ,
        ),
        port_ids=(_PORT_ID,),
        profile=RfModulationProfile(
            state_readable=True,
            configuration_readable=True,
            mode_profiles=_mode_profiles(),
        ),
    )
    evidence = replace(
        production,
        capabilities=(
            *production.capabilities,
            "rf_source.modulation_configure",
            "rf_source.modulation_disable",
        ),
        rf_source_extensions=replace(
            extensions,
            features=tuple(sorted((*features, modulation_feature), key=lambda item: item.feature.value)),
        ),
    )
    try:
        validate_rf_source_descriptor(evidence)
    except Exception as exc:
        raise A4PreflightError("a4_evidence_descriptor_invalid") from exc
    return evidence


def _validate_setup_target(
    evidence_descriptor: InstrumentDescriptor,
    setup: A4EvidenceSetup,
) -> None:
    extensions = evidence_descriptor.rf_source_extensions
    assert isinstance(extensions, RfSourceDescriptorExtensions)
    port = extensions.topology.ports[0]
    if setup.actual_termination_ohm != port.power_reference_impedance_ohm:
        raise A4PreflightError("a4_evidence_termination_mismatch")
    feature = next(
        (item for item in extensions.features if item.feature is RfFeature.MODULATION),
        None,
    )
    if feature is None or not isinstance(feature.profile, RfModulationProfile):
        raise A4PreflightError("a4_evidence_descriptor_invalid")
    mode = next((item for item in feature.profile.mode_profiles if item.kind is setup.request.kind), None)
    if mode is None:
        raise A4PreflightError("a4_evidence_mode_not_declared")
    if not mode.value_min <= setup.request.value <= mode.value_max:
        raise A4PreflightError("a4_evidence_modulation_value_outside_descriptor_range")
    if not mode.internal_frequency_min_hz <= setup.request.internal_frequency_hz <= mode.internal_frequency_max_hz:
        raise A4PreflightError("a4_evidence_internal_frequency_outside_descriptor_range")


def validate_a4_preflight(
    rf_config: WaveBenchConfig,
    setup: A4EvidenceSetup,
) -> A4Preflight:
    """Fail closed before creating an RF transport."""

    rf_source = rf_config.rf_source
    if rf_source is None:
        raise A4PreflightError("rf_source_not_configured")
    if rf_source.driver != _DRIVER_ID:
        raise A4PreflightError("unexpected_rf_source_driver")
    if not isinstance(rf_source.resource, str) or not rf_source.resource.strip():
        raise A4PreflightError("rf_source_resource_missing")
    if rf_source.access != "read_only":
        raise A4PreflightError("rf_source_base_access_must_be_read_only")
    _require_no_retries(rf_config)
    production = resolve_instrument_descriptor(_DRIVER_ID, expected_kind="rf_source")
    if production.driver_id != _DRIVER_ID or production.kind != "rf_source":
        raise A4PreflightError("unexpected_descriptor_identity")
    if _MODEL not in production.models:
        raise A4PreflightError("unexpected_descriptor_model")
    if tuple(production.capabilities) != _PRODUCTION_CAPABILITIES:
        raise A4PreflightError("production_modulation_gate_changed")
    if not _runtime_versions_available(_runtime_versions()):
        raise A4PreflightError("runtime_version_unavailable")
    evidence_descriptor = _build_evidence_descriptor(production)
    _validate_setup_target(evidence_descriptor, setup)
    return A4Preflight(
        production_descriptor=production,
        evidence_descriptor=evidence_descriptor,
    )


def _a4_rf_config(config: WaveBenchConfig) -> WaveBenchConfig:
    rf_source = config.rf_source
    assert rf_source is not None
    return replace(config, rf_source=replace(rf_source, access="read_write"))


def _base_evidence(
    preflight: A4Preflight,
    setup: A4EvidenceSetup,
    *,
    timestamp_utc: str,
    operation_mode: str = "configuration",
) -> dict[str, object]:
    request = setup.request
    return {
        "schema": A4_EVIDENCE_SCHEMA,
        "evidence": "A4",
        "operation_mode": operation_mode,
        "timestamp_utc": timestamp_utc,
        "driver_id": preflight.production_descriptor.driver_id,
        "model": _MODEL,
        "production_capabilities": list(preflight.production_descriptor.capabilities),
        "runtime": _runtime_versions(),
        "hardware": {
            "model": _MODEL,
            "firmware": None,
            "installed_options": list(setup.installed_options),
        },
        "setup": {
            "port_id": setup.port_id,
            "actual_termination_ohm": setup.actual_termination_ohm,
            "modulation_kind": request.kind.value,
            _mode_value_field(request.kind): request.value,
            "internal_frequency_hz": request.internal_frequency_hz,
        },
        "status": "failed",
        "failure_codes": [],
        "initial_snapshot": None,
        "modulation_configure": None,
        "modulation_disable": None,
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


def _snapshot_port(snapshot: RfSourceSnapshot):
    if tuple(port.port_id for port in snapshot.ports) != (_PORT_ID,):
        return None
    return snapshot.ports[0]


def _snapshot_failure_codes(
    snapshot: RfSourceSnapshot,
    *,
    phase: str,
    expected_modulation: RfModulationState | None,
) -> list[str]:
    port = _snapshot_port(snapshot)
    if port is None:
        return [f"{phase}_snapshot_topology_invalid"]
    values = (
        port.frequency_hz,
        port.power_dbm,
        port.output_enabled,
        port.modulation,
        port.pulse,
        port.sweep,
        snapshot.protection,
    )
    codes: list[str] = []
    if any(value.availability is not RfAvailability.VALUE for value in values):
        codes.append(f"{phase}_snapshot_contains_unknown_state")
        return codes
    if port.output_enabled.value is not False:
        codes.append(f"{phase}_rf_output_not_off")
    if expected_modulation is not None and port.modulation.value is not expected_modulation:
        codes.append(f"{phase}_modulation_state_invalid")
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


def _observed_artifact_value(port: Mapping[str, object], field: str, expected: object) -> bool:
    observed = port.get(field)
    return (
        isinstance(observed, Mapping)
        and observed.get("availability") == "value"
        and observed.get("value") == expected
    )


def _modulation_artifact_matches(artifact: object, request: RfModulationRequest) -> bool:
    if not isinstance(artifact, Mapping) or artifact.get("operation") != "rf_source.modulation_configure":
        return False
    postcondition = artifact.get("postcondition_snapshot")
    if not isinstance(postcondition, Mapping):
        return False
    ports = postcondition.get("ports")
    if not isinstance(ports, list) or len(ports) != 1 or not isinstance(ports[0], Mapping):
        return False
    if not (
        _observed_artifact_value(ports[0], "output_enabled", False)
        and _observed_artifact_value(ports[0], "modulation", RfModulationState.ENABLED.value)
        and _observed_artifact_value(ports[0], "pulse", RfPulseState.DISABLED.value)
        and _observed_artifact_value(ports[0], "sweep", RfSweepState.DISABLED.value)
    ):
        return False
    modulation = artifact.get("postcondition_modulation_snapshot")
    if not isinstance(modulation, Mapping):
        return False
    selected_fm_pm_kind = (
        request.kind.value if request.kind in {RfModulationKind.FM, RfModulationKind.PM} else None
    )
    return (
        modulation.get("port_id") == request.port_id
        and modulation.get("kind") == request.kind.value
        and modulation.get("source") == RfModulationSource.INTERNAL.value
        and modulation.get("waveform") == RfModulationWaveform.SINE.value
        and modulation.get("selected_fm_pm_kind") == selected_fm_pm_kind
        and modulation.get(_mode_value_field(request.kind)) == request.value
        and modulation.get("internal_frequency_hz") == request.internal_frequency_hz
        and modulation.get("enabled_modes") == [request.kind.value]
        and modulation.get("global_enabled") is True
        and modulation.get("fault_codes") == []
    )


def _modulation_disable_artifact_matches(
    artifact: object,
    request: RfModulationRequest,
    *,
    require_write: bool = True,
) -> bool:
    if not isinstance(artifact, Mapping) or artifact.get("operation") != "rf_source.modulation_disable":
        return False
    result = artifact.get("result")
    if not isinstance(result, Mapping) or not isinstance(result.get("write_completed"), bool):
        return False
    if require_write and result.get("write_completed") is not True:
        return False
    postcondition = artifact.get("postcondition_snapshot")
    if not isinstance(postcondition, Mapping):
        return False
    ports = postcondition.get("ports")
    if not isinstance(ports, list) or len(ports) != 1 or not isinstance(ports[0], Mapping):
        return False
    if not (
        _observed_artifact_value(ports[0], "output_enabled", False)
        and _observed_artifact_value(ports[0], "modulation", RfModulationState.DISABLED.value)
        and _observed_artifact_value(ports[0], "pulse", RfPulseState.DISABLED.value)
        and _observed_artifact_value(ports[0], "sweep", RfSweepState.DISABLED.value)
    ):
        return False
    modulation = artifact.get("postcondition_modulation_state")
    return (
        isinstance(modulation, Mapping)
        and modulation.get("port_id") == request.port_id
        and modulation.get("enabled_modes") == []
        and modulation.get("global_enabled") is False
        and modulation.get("fault_codes") == []
    )


def _expected_a4_io(request: RfModulationRequest) -> tuple[int, int]:
    postcondition_modulation_query_count = 9 if request.kind is RfModulationKind.AM else 10
    driver_write_count = 6 if request.kind is RfModulationKind.AM else 7
    query_count = (
        _SNAPSHOT_QUERY_COUNT
        + _SNAPSHOT_QUERY_COUNT
        + 5
        + _SNAPSHOT_QUERY_COUNT
        + postcondition_modulation_query_count
        + _SNAPSHOT_QUERY_COUNT
        + 5
        + _SNAPSHOT_QUERY_COUNT
        + 5
        + _SNAPSHOT_QUERY_COUNT
    )
    return query_count, driver_write_count + 2


def _rf_audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
    *,
    expected_io: tuple[int, int] | None,
) -> list[str]:
    codes: list[str] = []
    if before_close is None:
        return ["rf_audit_before_close_unavailable"]
    if after_close is None:
        codes.append("rf_audit_after_close_unavailable")
    if before_close["access"] != "read_write":
        codes.append("rf_audit_access_not_read_write")
    counters = before_close["counters"]
    assert isinstance(counters, Mapping)
    if counters["write_outcome_unknown"] != 0 or counters["binary_write_outcome_unknown"] != 0:
        codes.append("rf_write_outcome_unknown")
    if counters["blocked_session_io"] != 0:
        codes.append("rf_blocked_session_io")
    if expected_io is not None:
        expected_queries, expected_writes = expected_io
        if counters["query_calls"] != expected_queries:
            codes.append("unexpected_rf_query_count")
        for key in (
            "write_requests",
            "write_attempts",
            "write_transmitted",
            "write_completed",
            "instrument_mutation_writes",
            "instrument_mutation_writes_completed",
        ):
            if counters[key] != expected_writes:
                codes.append("unexpected_rf_write_count")
                break
        if before_close["session_health"] != "healthy":
            codes.append("rf_session_not_healthy_before_close")
    if after_close is not None:
        if after_close["access"] != "read_write":
            codes.append("rf_audit_after_close_access_not_read_write")
        after_counters = after_close["counters"]
        assert isinstance(after_counters, Mapping)
        if after_counters != counters:
            codes.append("rf_audit_counters_changed_after_close")
        if after_close["session_health"] != "closed":
            codes.append("rf_session_not_closed")
    return codes


def _expected_a4_recovery_io(*, write_completed: bool) -> tuple[int, int]:
    if write_completed:
        return (_SNAPSHOT_QUERY_COUNT + 26 + _SNAPSHOT_QUERY_COUNT, 2)
    return (_SNAPSHOT_QUERY_COUNT + _SNAPSHOT_QUERY_COUNT + 5 + _SNAPSHOT_QUERY_COUNT, 0)


def _base_descriptor_matches(preflight: A4Preflight, current: InstrumentDescriptor) -> bool:
    return (
        current.driver_id == preflight.production_descriptor.driver_id
        and current.kind == preflight.production_descriptor.kind
        and tuple(current.models) == tuple(preflight.production_descriptor.models)
        and tuple(current.capabilities) == tuple(preflight.production_descriptor.capabilities)
    )


def collect_a4_evidence(
    rf_config: WaveBenchConfig,
    preflight: A4Preflight,
    setup: A4EvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Perform one RF-OFF M3 sequence and return redacted, typed evidence."""

    current = validate_a4_preflight(rf_config, setup)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A4PreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(preflight, setup, timestamp_utc=timestamp_utc or _utc_now())
    failure_codes: list[str] = []
    rf_driver: object | None = None
    rf_transport: object | None = None
    rf_service: RfSourceService | None = None
    configure_completed = False
    configure_confirmed = False
    disable_completed = False
    disable_confirmed = False
    final_rf_off_confirmed = False

    try:
        a4_rf_config = _a4_rf_config(rf_config)
        rf_source = a4_rf_config.rf_source
        assert rf_source is not None
        opened = opener(
            driver_reference=rf_source.driver,
            expected_kind="rf_source",
            resource=rf_source.resource or "",
            configured_backend=a4_rf_config.connection.backend,
            timeout_ms=a4_rf_config.connection.timeout_ms,
            opc_timeout_ms=a4_rf_config.connection.opc_timeout_ms,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
            logger=CommandLogger(),
            options=rf_source.options,
            access="read_write",
            lease=ResourceLease(
                resource=rf_source.resource or "",
                mode="exclusive",
                operation="dsg830.a4_modulation_evidence",
            ),
        )
        rf_driver = opened.driver
        rf_transport = opened.transport
        if getattr(opened, "descriptor", None) != preflight.production_descriptor:
            raise A4PreflightError("descriptor_changed_after_preflight")
        try:
            validate_declared_capabilities(preflight.evidence_descriptor, rf_driver)
        except Exception as exc:
            raise A4PreflightError("a4_evidence_driver_invalid") from exc
        rf_service = RfSourceService(
            config=a4_rf_config,
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
        failure_codes.extend(
            _snapshot_failure_codes(
                initial,
                phase="initial",
                expected_modulation=RfModulationState.DISABLED,
            )
        )
        if not failure_codes:
            try:
                _, artifact = rf_service.configure_modulation_with_artifact(setup.request)
                evidence["modulation_configure"] = artifact
                configure_completed = True
                if _modulation_artifact_matches(artifact, setup.request):
                    configure_confirmed = True
                else:
                    failure_codes.append("rf_modulation_readback_invalid")
            except Exception:
                failure_codes.append("rf_modulation_configure_failed")
        if configure_completed:
            try:
                _, artifact = rf_service.disable_modulation_with_artifact(
                    RfModulationDisableRequest(
                        port_id=setup.request.port_id,
                        kind=setup.request.kind,
                    )
                )
                evidence["modulation_disable"] = artifact
                disable_completed = True
                if _modulation_disable_artifact_matches(artifact, setup.request):
                    disable_confirmed = True
                else:
                    failure_codes.append("rf_modulation_disable_readback_invalid")
            except Exception:
                failure_codes.append("rf_modulation_disable_failed")
        if disable_completed:
            final = rf_service.snapshot()
            evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final)
            final_failures = _snapshot_failure_codes(
                final,
                phase="final",
                expected_modulation=RfModulationState.DISABLED,
            )
            failure_codes.extend(final_failures)
            final_rf_off_confirmed = not final_failures
    except A4PreflightError as exc:
        failure_codes.append(exc.code)
    except Exception:
        failure_codes.append("local_harness_failed")
    finally:
        if rf_driver is not None:
            before_close = _audit_snapshot(rf_transport)
            rf_close_error = _close_driver(rf_driver)
            after_close = _audit_snapshot(rf_transport)
            evidence["rf_audit"] = {"before_close": before_close, "after_close": after_close}
            if rf_close_error is not None:
                failure_codes.append(rf_close_error)
            failure_codes.extend(
                _rf_audit_failure_codes(
                    before_close,
                    after_close,
                    expected_io=(
                        _expected_a4_io(setup.request)
                        if configure_confirmed and disable_confirmed and final_rf_off_confirmed
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


def collect_a4_recovery_evidence(
    rf_config: WaveBenchConfig,
    preflight: A4Preflight,
    setup: A4EvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Restore one known M3 mode to the RF-OFF, modulation-disabled baseline.

    This is a local recovery record, not A4 acceptance evidence.  It never
    enables RF output and uses the same temporary descriptor as the normal A4
    harness.  The Service only writes when state proves that exactly the
    requested mode is active; an already-disabled consistent state is recorded
    as a verified no-write result.
    """

    current = validate_a4_preflight(rf_config, setup)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A4PreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(
        preflight,
        setup,
        timestamp_utc=timestamp_utc or _utc_now(),
        operation_mode="recovery",
    )
    failure_codes: list[str] = []
    rf_driver: object | None = None
    rf_transport: object | None = None
    disable_completed = False
    disable_confirmed = False
    disable_write_completed: bool | None = None
    final_rf_off_confirmed = False

    try:
        a4_rf_config = _a4_rf_config(rf_config)
        rf_source = a4_rf_config.rf_source
        assert rf_source is not None
        opened = opener(
            driver_reference=rf_source.driver,
            expected_kind="rf_source",
            resource=rf_source.resource or "",
            configured_backend=a4_rf_config.connection.backend,
            timeout_ms=a4_rf_config.connection.timeout_ms,
            opc_timeout_ms=a4_rf_config.connection.opc_timeout_ms,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
            logger=CommandLogger(),
            options=rf_source.options,
            access="read_write",
            lease=ResourceLease(
                resource=rf_source.resource or "",
                mode="exclusive",
                operation="dsg830.a4_modulation_recovery",
            ),
        )
        rf_driver = opened.driver
        rf_transport = opened.transport
        if getattr(opened, "descriptor", None) != preflight.production_descriptor:
            raise A4PreflightError("descriptor_changed_after_preflight")
        try:
            validate_declared_capabilities(preflight.evidence_descriptor, rf_driver)
        except Exception as exc:
            raise A4PreflightError("a4_evidence_driver_invalid") from exc
        rf_service = RfSourceService(
            config=a4_rf_config,
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
        failure_codes.extend(
            _snapshot_failure_codes(
                initial,
                phase="initial",
                expected_modulation=None,
            )
        )
        if not failure_codes:
            try:
                result, artifact = rf_service.disable_modulation_with_artifact(
                    RfModulationDisableRequest(
                        port_id=setup.request.port_id,
                        kind=setup.request.kind,
                    )
                )
                evidence["modulation_disable"] = artifact
                disable_completed = True
                write_completed = getattr(result, "write_completed", None)
                if not isinstance(write_completed, bool):
                    failure_codes.append("rf_modulation_disable_result_invalid")
                elif _modulation_disable_artifact_matches(
                    artifact,
                    setup.request,
                    require_write=False,
                ):
                    disable_write_completed = write_completed
                    disable_confirmed = True
                else:
                    failure_codes.append("rf_modulation_disable_readback_invalid")
            except Exception:
                failure_codes.append("rf_modulation_disable_failed")
        if disable_completed:
            final = rf_service.snapshot()
            evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final)
            final_failures = _snapshot_failure_codes(
                final,
                phase="final",
                expected_modulation=RfModulationState.DISABLED,
            )
            failure_codes.extend(final_failures)
            final_rf_off_confirmed = not final_failures
    except A4PreflightError as exc:
        failure_codes.append(exc.code)
    except Exception:
        failure_codes.append("local_harness_failed")
    finally:
        if rf_driver is not None:
            before_close = _audit_snapshot(rf_transport)
            rf_close_error = _close_driver(rf_driver)
            after_close = _audit_snapshot(rf_transport)
            evidence["rf_audit"] = {"before_close": before_close, "after_close": after_close}
            if rf_close_error is not None:
                failure_codes.append(rf_close_error)
            expected_io = None
            if disable_confirmed and final_rf_off_confirmed:
                assert disable_write_completed is not None
                expected_io = _expected_a4_recovery_io(
                    write_completed=disable_write_completed
                )
            failure_codes.extend(
                _rf_audit_failure_codes(
                    before_close,
                    after_close,
                    expected_io=expected_io,
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
        raise A4PreflightError("invalid_evidence_output_path")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise A4PreflightError("invalid_evidence_output_path") from exc
    return os.fdopen(descriptor, "w", encoding="utf-8")


def _replace_evidence(output: TextIO, evidence: Mapping[str, object]) -> None:
    text = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.seek(0)
    output.truncate()
    output.write(text)
    output.flush()
    os.fsync(output.fileno())


def _summary(evidence: Mapping[str, object]) -> str:
    setup = evidence.get("setup")
    return json.dumps(
        {
            "schema": A4_EVIDENCE_SCHEMA,
            "status": evidence["status"],
            "failure_codes": evidence["failure_codes"],
            "operation_mode": evidence.get("operation_mode"),
            "modulation_kind": setup.get("modulation_kind") if isinstance(setup, Mapping) else None,
            "rf_output_confirmed_off": evidence["status"] == "passed",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rf-config", required=True, type=Path, help="Private read-only RF TOML")
    parser.add_argument("--setup", required=True, type=Path, help="Private A4 setup TOML without resources")
    parser.add_argument("--output", type=Path, help="New local JSON evidence file")
    execution_mode = parser.add_mutually_exclusive_group()
    execution_mode.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly permit one RF-OFF configuration, readback, and modulation-disable sequence",
    )
    execution_mode.add_argument(
        "--recover",
        action="store_true",
        help="Explicitly restore one known modulation mode to the RF-OFF disabled baseline",
    )
    args = parser.parse_args(argv)

    try:
        rf_config = load_config(args.rf_config)
        setup = load_a4_evidence_setup(args.setup)
        preflight = validate_a4_preflight(rf_config, setup)
    except A4PreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "config_or_descriptor_invalid"}))
        return 2

    if not args.execute and not args.recover:
        print(
            json.dumps(
                {
                    "schema": A4_EVIDENCE_SCHEMA,
                    "status": "dry_run_ok",
                    "driver_id": preflight.production_descriptor.driver_id,
                    "production_capabilities": list(preflight.production_descriptor.capabilities),
                    "a4_setup": _base_evidence(
                        preflight,
                        setup,
                        timestamp_utc="dry_run",
                    )["setup"],
                    "will_connect": False,
                    "will_write": False,
                    "will_enable_rf_output": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required with --execute or --recover")

    output: TextIO | None = None
    try:
        output = _open_evidence_output(args.output)
        _replace_evidence(output, {"schema": A4_EVIDENCE_SCHEMA, "evidence": "A4", "status": "started"})
    except A4PreflightError as exc:
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
            evidence = (
                collect_a4_evidence(rf_config, preflight, setup)
                if args.execute
                else collect_a4_recovery_evidence(rf_config, preflight, setup)
            )
        except A4PreflightError as exc:
            evidence = _base_evidence(
                preflight,
                setup,
                timestamp_utc=_utc_now(),
                operation_mode="recovery" if args.recover else "configuration",
            )
            evidence["failure_codes"] = [exc.code]
        except Exception:
            evidence = _base_evidence(
                preflight,
                setup,
                timestamp_utc=_utc_now(),
                operation_mode="recovery" if args.recover else "configuration",
            )
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


if __name__ == "__main__":  # pragma: no cover - local harness entry point.
    raise SystemExit(main())
