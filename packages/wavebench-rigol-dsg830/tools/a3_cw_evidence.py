"""Collect one local A3 CW loopback evidence record for a RIGOL DSG830.

This local-only harness gathers the controlled hardware evidence required
before the production descriptor may declare ``rf_source.cw_configure``.  It
never modifies the production descriptor.  A private read-only RF config, a
private read-only scope config, and a resource-free A3 setup file are
required; ``--execute`` is the explicit write boundary.

The sequence is deliberately small: verify RF OFF, set one low-power CW
frequency, set one low-power CW level, briefly enable the already-validated
RF output, inspect only the current CH2 buffer, then confirm RF OFF.  The RF
source's typed frequency and power readbacks are the primary evidence.  CH2
only proves that a signal is externally visible; no dBm-to-Vpp conversion or
scope frequency measurement is inferred.  Scope fetch changes display and
transfer setup and is deliberately recorded as not restored by this harness.
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

from wavebench.config import RfPortSafetyConfig, WaveBenchConfig, load_config
from wavebench.instruments import (
    RF_SOURCE_CONTRACT_VERSION,
    RfAvailability,
    RfCwProfile,
    RfCwRequest,
    RfFeature,
    RfFeatureCapability,
    RfFeatureDirection,
    RfOutputRequest,
    RfSourceDescriptorExtensions,
    RfSourceSnapshot,
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
from wavebench.services.scope_service import ScopeService
from wavebench.transport.session import SessionHealth


A3_EVIDENCE_SCHEMA = "wavebench.rigol_dsg830.a3_evidence.v1"
_DRIVER_ID = "rigol.dsg830"
_MODEL = "DSG830"
_PORT_ID = "rf_out"
_PRODUCTION_CAPABILITIES = (
    "rf_source.idn",
    "rf_source.snapshot",
    "rf_source.output",
)
_SNAPSHOT_QUERY_COUNT = 8
_EXPECTED_RF_SNAPSHOT_COUNT = 9
_EXPECTED_RF_QUERY_COUNT = _SNAPSHOT_QUERY_COUNT * _EXPECTED_RF_SNAPSHOT_COUNT
_EXPECTED_RF_WRITES = 4
_MAX_A3_POWER_DBM = -40.0
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
_SCOPE_UNRESTORED_FIELDS = (
    "channel_enable",
    "waveform_format",
    "waveform_byte_order",
    "waveform_point_count",
)


class A3PreflightError(RuntimeError):
    """A stable reason to refuse A3 before opening an RF transport."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ScopeObservationSetup:
    """Explicit, non-sensitive CH2 observation facts for the A3 setup."""

    ch2: int
    allow_ch2_50ohm: bool
    points: str
    minimum_observable_vpp_v: float


@dataclass(frozen=True, slots=True)
class A3EvidenceSetup:
    """Human-confirmed, non-sensitive A3 safety facts from the private setup."""

    port_id: str
    actual_termination_ohm: float
    installed_options: tuple[str, ...]
    frequency_hz: float
    power_dbm: float
    scope_observation: ScopeObservationSetup


@dataclass(frozen=True, slots=True)
class A3Preflight:
    """Static facts accepted before a controlled A3 session may open."""

    production_descriptor: InstrumentDescriptor
    evidence_descriptor: InstrumentDescriptor
    scope_descriptor: InstrumentDescriptor


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
        raise A3PreflightError(code)
    normalized = float(value)
    if minimum is not None and normalized < minimum:
        raise A3PreflightError(code)
    return normalized


def _safe_options(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or _SAFE_METADATA_TOKEN.fullmatch(item) is None for item in value
    ):
        raise A3PreflightError("a3_evidence_options_invalid")
    options = tuple(value)
    if len(set(options)) != len(options) or options != tuple(sorted(options)):
        raise A3PreflightError("a3_evidence_options_invalid")
    return options


def load_a3_evidence_setup(path: Path) -> A3EvidenceSetup:
    """Load only the explicit, non-sensitive facts required for A3."""

    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise A3PreflightError("a3_evidence_invalid") from exc

    evidence = raw.get("a3_evidence")
    if not isinstance(evidence, Mapping):
        raise A3PreflightError("a3_evidence_not_configured")
    required = {
        "port_id",
        "actual_termination_ohm",
        "installed_options",
        "frequency_hz",
        "power_dbm",
    }
    if set(evidence) != required:
        raise A3PreflightError("a3_evidence_invalid")
    if evidence["port_id"] != _PORT_ID:
        raise A3PreflightError("a3_evidence_port_must_be_rf_out")

    actual_termination_ohm = _finite(
        evidence["actual_termination_ohm"],
        "a3_evidence_termination_invalid",
        minimum=1e-12,
    )
    frequency_hz = _finite(
        evidence["frequency_hz"],
        "a3_evidence_frequency_invalid",
        minimum=1e-12,
    )
    power_dbm = _finite(evidence["power_dbm"], "a3_evidence_power_invalid")
    if power_dbm > _MAX_A3_POWER_DBM:
        raise A3PreflightError("a3_evidence_power_not_low_enough")

    scope = raw.get("scope_observation")
    if not isinstance(scope, Mapping):
        raise A3PreflightError("scope_observation_not_configured")
    required_scope = {
        "ch2",
        "allow_ch2_50ohm",
        "points",
        "minimum_observable_vpp_v",
    }
    if set(scope) != required_scope:
        raise A3PreflightError("scope_observation_invalid")
    if scope["ch2"] != 2:
        raise A3PreflightError("scope_observation_channel_must_be_ch2")
    if scope["allow_ch2_50ohm"] is not True:
        raise A3PreflightError("scope_observation_ch2_50ohm_not_explicit")
    if scope["points"] != "def":
        raise A3PreflightError("scope_observation_points_must_be_def")
    minimum_observable_vpp_v = _finite(
        scope["minimum_observable_vpp_v"],
        "scope_observation_threshold_invalid",
        minimum=1e-12,
    )

    return A3EvidenceSetup(
        port_id=_PORT_ID,
        actual_termination_ohm=actual_termination_ohm,
        installed_options=_safe_options(evidence["installed_options"]),
        frequency_hz=frequency_hz,
        power_dbm=power_dbm,
        scope_observation=ScopeObservationSetup(
            ch2=2,
            allow_ch2_50ohm=True,
            points="def",
            minimum_observable_vpp_v=minimum_observable_vpp_v,
        ),
    )


def _require_no_retries(config: WaveBenchConfig, *, code: str) -> None:
    if config.connection.read_retry_attempts != 0 or config.connection.read_retry_delay_ms != 0:
        raise A3PreflightError(code)


def _normalized_resource(value: object) -> str:
    """Compare configured resources without ever copying them into evidence."""

    return value.strip().casefold() if isinstance(value, str) else ""


def _build_evidence_descriptor(production: InstrumentDescriptor) -> InstrumentDescriptor:
    """Create an in-memory, A3-only CW descriptor; never register it."""

    extensions = production.rf_source_extensions
    if not isinstance(extensions, RfSourceDescriptorExtensions):
        raise A3PreflightError("rf_source_extensions_invalid")
    if extensions.contract_version != RF_SOURCE_CONTRACT_VERSION:
        raise A3PreflightError("rf_source_extensions_invalid")
    if tuple(port.port_id for port in extensions.topology.ports) != (_PORT_ID,):
        raise A3PreflightError("unexpected_rf_topology")
    features = extensions.features
    if any(feature.feature is RfFeature.CW for feature in features):
        raise A3PreflightError("production_cw_gate_changed")
    if sum(feature.feature is RfFeature.OUTPUT for feature in features) != 1:
        raise A3PreflightError("production_output_contract_invalid")
    cw_feature = RfFeatureCapability(
        feature=RfFeature.CW,
        directions=(RfFeatureDirection.CONFIGURE, RfFeatureDirection.READ),
        port_ids=(_PORT_ID,),
        profile=RfCwProfile(
            frequency_readable=True,
            power_readable=True,
            frequency_configurable=True,
            power_configurable=True,
        ),
    )
    evidence = replace(
        production,
        capabilities=(*production.capabilities, "rf_source.cw_configure"),
        rf_source_extensions=replace(
            extensions,
            features=tuple(sorted((*features, cw_feature), key=lambda item: item.feature.value)),
        ),
    )
    try:
        validate_rf_source_descriptor(evidence)
    except Exception as exc:
        raise A3PreflightError("a3_evidence_descriptor_invalid") from exc
    return evidence


def _validate_setup_target(
    evidence_descriptor: InstrumentDescriptor,
    setup: A3EvidenceSetup,
) -> None:
    extensions = evidence_descriptor.rf_source_extensions
    assert isinstance(extensions, RfSourceDescriptorExtensions)
    port = extensions.topology.ports[0]
    if not port.frequency_min_hz <= setup.frequency_hz <= port.frequency_max_hz:
        raise A3PreflightError("a3_evidence_frequency_outside_descriptor_range")
    if not port.power_min_dbm <= setup.power_dbm <= port.power_max_dbm:
        raise A3PreflightError("a3_evidence_power_outside_descriptor_range")
    if setup.actual_termination_ohm != port.power_reference_impedance_ohm:
        raise A3PreflightError("a3_evidence_termination_mismatch")


def validate_a3_preflight(
    rf_config: WaveBenchConfig,
    setup: A3EvidenceSetup,
    *,
    scope_config: WaveBenchConfig,
) -> A3Preflight:
    """Fail closed before creating an RF or scope transport."""

    rf_source = rf_config.rf_source
    if rf_source is None:
        raise A3PreflightError("rf_source_not_configured")
    if rf_source.driver != _DRIVER_ID:
        raise A3PreflightError("unexpected_rf_source_driver")
    rf_resource = _normalized_resource(rf_source.resource)
    if not rf_resource:
        raise A3PreflightError("rf_source_resource_missing")
    if rf_source.access != "read_only":
        raise A3PreflightError("rf_source_base_access_must_be_read_only")
    _require_no_retries(rf_config, code="rf_source_retries_must_be_disabled")

    production = resolve_instrument_descriptor(_DRIVER_ID, expected_kind="rf_source")
    if production.driver_id != _DRIVER_ID or production.kind != "rf_source":
        raise A3PreflightError("unexpected_descriptor_identity")
    if _MODEL not in production.models:
        raise A3PreflightError("unexpected_descriptor_model")
    if tuple(production.capabilities) != _PRODUCTION_CAPABILITIES:
        raise A3PreflightError("production_cw_gate_changed")
    if not _runtime_versions_available(_runtime_versions()):
        raise A3PreflightError("runtime_version_unavailable")
    evidence_descriptor = _build_evidence_descriptor(production)
    _validate_setup_target(evidence_descriptor, setup)

    scope_resource = _normalized_resource(scope_config.connection.resource)
    if not scope_resource:
        raise A3PreflightError("scope_resource_missing")
    if scope_resource == rf_resource:
        raise A3PreflightError("scope_resource_must_differ_from_rf_source")
    if scope_config.scope.access != "read_only":
        raise A3PreflightError("scope_base_access_must_be_read_only")
    if scope_config.scope.check_errors:
        raise A3PreflightError("scope_error_drain_must_be_disabled")
    _require_no_retries(scope_config, code="scope_retries_must_be_disabled")
    scope_descriptor = resolve_instrument_descriptor(
        scope_config.scope.driver,
        expected_kind="scope",
    )
    required_scope_capabilities = {"scope.idn", "scope.channel_coupling", "scope.fetch_waveform"}
    if not required_scope_capabilities <= set(scope_descriptor.capabilities):
        raise A3PreflightError("scope_observation_capability_missing")
    return A3Preflight(
        production_descriptor=production,
        evidence_descriptor=evidence_descriptor,
        scope_descriptor=scope_descriptor,
    )


def _a3_rf_config(config: WaveBenchConfig, setup: A3EvidenceSetup) -> WaveBenchConfig:
    rf_source = config.rf_source
    assert rf_source is not None  # validated before this internal helper
    safety = RfPortSafetyConfig(
        port_id=setup.port_id,
        minimum_frequency_hz=setup.frequency_hz,
        maximum_frequency_hz=setup.frequency_hz,
        maximum_power_dbm=setup.power_dbm,
        actual_termination_ohm=setup.actual_termination_ohm,
    )
    return replace(
        config,
        rf_source=replace(rf_source, access="read_write", safety_ports=(safety,)),
    )


def _a3_scope_config(config: WaveBenchConfig) -> WaveBenchConfig:
    return replace(
        config,
        scope=replace(config.scope, access="read_write", check_errors=False),
        waveform=replace(config.waveform, format="real", byte_order="lsbf", points="DEF"),
    )


def _base_evidence(
    preflight: A3Preflight,
    setup: A3EvidenceSetup,
    *,
    timestamp_utc: str,
) -> dict[str, object]:
    return {
        "schema": A3_EVIDENCE_SCHEMA,
        "evidence": "A3",
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
            "frequency_hz": setup.frequency_hz,
            "power_dbm": setup.power_dbm,
        },
        "scope_observation": {
            "status": "not_started",
            "channel": setup.scope_observation.ch2,
            "coupling": None,
            "signal_detected": None,
            "unrestored_fields": [],
        },
        "status": "failed",
        "failure_codes": [],
        "initial_snapshot": None,
        "frequency_configure": None,
        "power_configure": None,
        "output_enable": None,
        "output_disable": None,
        "rf_audit": {"before_close": None, "after_close": None},
        "scope_audit": {"before_close": None, "after_close": None},
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


def _initial_snapshot_failure_codes(snapshot: RfSourceSnapshot) -> list[str]:
    port = _snapshot_port(snapshot)
    if port is None:
        return ["unexpected_snapshot_topology"]
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
        codes.append("initial_snapshot_contains_unknown_state")
    if port.output_enabled.availability is RfAvailability.VALUE and port.output_enabled.value is not False:
        codes.append("initial_rf_output_not_off")
    if snapshot.protection.availability is RfAvailability.VALUE:
        protection = snapshot.protection.value
        if protection is not None and protection.active_codes:
            codes.append("initial_active_protection_condition")
    return codes


def _snapshot_may_have_rf_output_enabled(snapshot: RfSourceSnapshot) -> bool:
    """Return a conservative cleanup decision without interpreting other RF state."""

    port = _snapshot_port(snapshot)
    if port is None or port.output_enabled.availability is not RfAvailability.VALUE:
        return True
    return port.output_enabled.value is not False


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


def _artifact_port_value(artifact: object, field: str, expected: object) -> bool:
    if not isinstance(artifact, Mapping):
        return False
    postcondition = artifact.get("postcondition_snapshot")
    if not isinstance(postcondition, Mapping):
        return False
    ports = postcondition.get("ports")
    if not isinstance(ports, list) or len(ports) != 1 or not isinstance(ports[0], Mapping):
        return False
    observed = ports[0].get(field)
    return (
        isinstance(observed, Mapping)
        and observed.get("availability") == "value"
        and observed.get("value") == expected
    )


def _sanitize_recovery(exc: BaseException) -> dict[str, str] | None:
    recovery = getattr(exc, "rf_source_recovery", None)
    if not isinstance(recovery, Mapping):
        return None
    result: dict[str, str] = {}
    for key in ("status", "session_health", "reason"):
        value = recovery.get(key)
        if isinstance(value, str) and _SAFE_METADATA_TOKEN.fullmatch(value) is not None:
            result[key] = value
    return result or None


def _scope_channel_summary(
    waveform: object,
    *,
    channel: int,
    coupling: str,
    minimum_vpp_v: float,
) -> dict[str, object]:
    values = getattr(waveform, "voltages_v", None)
    if values is None:
        return {"status": "invalid_waveform", "coupling": coupling, "channel": channel}
    try:
        finite_values = [float(value) for value in values if isfinite(float(value))]
    except Exception:
        return {"status": "invalid_waveform", "coupling": coupling, "channel": channel}
    if len(finite_values) < 2:
        return {"status": "insufficient_samples", "coupling": coupling, "channel": channel}
    vpp_v = max(finite_values) - min(finite_values)
    return {
        "status": "observed",
        "coupling": coupling,
        "sample_count": len(finite_values),
        "vpp_v": vpp_v,
        "signal_detected": vpp_v >= minimum_vpp_v,
        "channel": channel,
    }


def _open_scope_observer(
    config: WaveBenchConfig,
    preflight: A3Preflight,
    setup: A3EvidenceSetup,
    *,
    opener: Callable[..., Any],
) -> tuple[ScopeService, object, object, str]:
    opened = opener(
        driver_reference=config.scope.driver,
        expected_kind="scope",
        resource=config.connection.resource,
        configured_backend=config.connection.backend,
        timeout_ms=config.connection.timeout_ms,
        opc_timeout_ms=config.connection.opc_timeout_ms,
        read_retry_attempts=0,
        read_retry_delay_ms=0,
        logger=CommandLogger(),
        settings={"check_errors": False},
        options=config.scope.options,
        access="read_write",
        lease=ResourceLease(
            resource=config.connection.resource,
            mode="exclusive",
            operation="dsg830.a3_cw_observation",
        ),
    )
    if getattr(opened, "descriptor", None) != preflight.scope_descriptor:
        raise A3PreflightError("scope_descriptor_changed_after_preflight")
    service = ScopeService(
        config=config,
        logger=CommandLogger(),
        session=opened.driver,
        descriptor=preflight.scope_descriptor,
        transport=opened.transport,
        session_state=opened.session_state,
    )
    coupling = service.require_high_impedance(
        setup.scope_observation.ch2,
        allow_50ohm=setup.scope_observation.allow_ch2_50ohm,
    )
    return service, opened.driver, opened.transport, coupling


def _collect_scope_observation(
    service: ScopeService,
    coupling: str,
    setup: A3EvidenceSetup,
) -> tuple[dict[str, object], list[str]]:
    channel = setup.scope_observation.ch2
    observation: dict[str, object] = {
        "status": "observed",
        "channel": channel,
        "coupling": coupling,
        "signal_detected": None,
        "unrestored_fields": list(_SCOPE_UNRESTORED_FIELDS),
    }
    try:
        waveform = service.fetch_waveform(channel)
    except Exception:
        observation["status"] = "fetch_failed"
        return observation, ["scope_ch2_fetch_failed"]
    summary = _scope_channel_summary(
        waveform,
        channel=channel,
        coupling=coupling,
        minimum_vpp_v=setup.scope_observation.minimum_observable_vpp_v,
    )
    observation.update(summary)
    if summary.get("signal_detected") is not True:
        return observation, ["scope_ch2_signal_not_observed"]
    return observation, []


def _rf_audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
    *,
    completed: bool,
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
    if completed:
        if counters["query_calls"] != _EXPECTED_RF_QUERY_COUNT:
            codes.append("unexpected_rf_query_count")
        for key in (
            "write_requests",
            "write_attempts",
            "write_transmitted",
            "write_completed",
            "instrument_mutation_writes",
            "instrument_mutation_writes_completed",
        ):
            if counters[key] != _EXPECTED_RF_WRITES:
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


def _base_descriptor_matches(preflight: A3Preflight, current: InstrumentDescriptor) -> bool:
    return (
        current.driver_id == preflight.production_descriptor.driver_id
        and current.kind == preflight.production_descriptor.kind
        and tuple(current.models) == tuple(preflight.production_descriptor.models)
        and tuple(current.capabilities) == tuple(preflight.production_descriptor.capabilities)
    )


def collect_a3_evidence(
    rf_config: WaveBenchConfig,
    scope_config: WaveBenchConfig,
    preflight: A3Preflight,
    setup: A3EvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Perform one A3 sequence and return redacted, typed evidence."""

    current = validate_a3_preflight(rf_config, setup, scope_config=scope_config)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A3PreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(
        preflight,
        setup,
        timestamp_utc=timestamp_utc or _utc_now(),
    )
    failure_codes: list[str] = []
    rf_driver: object | None = None
    rf_transport: object | None = None
    rf_service: RfSourceService | None = None
    scope_driver: object | None = None
    scope_transport: object | None = None
    scope_service: ScopeService | None = None
    scope_coupling: str | None = None
    frequency_confirmed = False
    power_confirmed = False
    rf_enable_confirmed = False
    rf_output_may_be_on = False
    rf_off_confirmed = False
    rf_disable_transaction_started = False

    try:
        scope_service, scope_driver, scope_transport, scope_coupling = _open_scope_observer(
            _a3_scope_config(scope_config),
            preflight,
            setup,
            opener=opener,
        )
        scope_observation = evidence["scope_observation"]
        assert isinstance(scope_observation, dict)
        scope_observation["coupling"] = scope_coupling
        scope_observation["status"] = "ready"

        a3_rf_config = _a3_rf_config(rf_config, setup)
        rf_source = a3_rf_config.rf_source
        assert rf_source is not None
        opened = opener(
            driver_reference=rf_source.driver,
            expected_kind="rf_source",
            resource=rf_source.resource or "",
            configured_backend=a3_rf_config.connection.backend,
            timeout_ms=a3_rf_config.connection.timeout_ms,
            opc_timeout_ms=a3_rf_config.connection.opc_timeout_ms,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
            logger=CommandLogger(),
            options=rf_source.options,
            access="read_write",
            lease=ResourceLease(
                resource=rf_source.resource or "",
                mode="exclusive",
                operation="dsg830.a3_cw_evidence",
            ),
        )
        rf_driver = opened.driver
        rf_transport = opened.transport
        if getattr(opened, "descriptor", None) != preflight.production_descriptor:
            raise A3PreflightError("descriptor_changed_after_preflight")
        try:
            validate_declared_capabilities(preflight.evidence_descriptor, rf_driver)
        except Exception as exc:
            raise A3PreflightError("a3_evidence_driver_invalid") from exc
        rf_service = RfSourceService(
            config=a3_rf_config,
            logger=CommandLogger(),
            session=rf_driver,
            descriptor=preflight.evidence_descriptor,
            transport=rf_transport,
            session_state=opened.session_state,
        )
        initial = rf_service.snapshot()
        evidence["initial_snapshot"] = rf_source_snapshot_operation_artifact(initial)
        firmware = _firmware(rf_driver)
        hardware = evidence["hardware"]
        assert isinstance(hardware, dict)
        hardware["firmware"] = firmware
        if firmware is None:
            failure_codes.append("snapshot_firmware_unavailable")
        failure_codes.extend(_initial_snapshot_failure_codes(initial))
        rf_output_may_be_on = _snapshot_may_have_rf_output_enabled(initial)

        if not failure_codes:
            try:
                _, frequency = rf_service.configure_cw_with_artifact(
                    RfCwRequest(port_id=setup.port_id, frequency_hz=setup.frequency_hz)
                )
                evidence["frequency_configure"] = frequency
                if _artifact_port_value(frequency, "frequency_hz", setup.frequency_hz):
                    frequency_confirmed = True
                else:
                    failure_codes.append("rf_frequency_readback_invalid")
            except Exception:
                failure_codes.append("rf_frequency_configure_failed")

        if frequency_confirmed:
            try:
                _, power = rf_service.configure_cw_with_artifact(
                    RfCwRequest(port_id=setup.port_id, power_dbm=setup.power_dbm)
                )
                evidence["power_configure"] = power
                if _artifact_port_value(power, "power_dbm", setup.power_dbm):
                    power_confirmed = True
                else:
                    failure_codes.append("rf_power_readback_invalid")
            except Exception:
                failure_codes.append("rf_power_configure_failed")

        if frequency_confirmed and power_confirmed:
            # A failed ON transaction may have sent its write before postcondition
            # readback fails.  Core then owns exactly one authorised OFF recovery.
            rf_output_may_be_on = True
            try:
                _, enable = rf_service.set_output_with_artifact(
                    RfOutputRequest(port_id=setup.port_id, enabled=True)
                )
                evidence["output_enable"] = enable
                if _artifact_port_value(enable, "output_enabled", True):
                    rf_enable_confirmed = True
                else:
                    failure_codes.append("rf_output_enable_readback_invalid")
            except Exception as exc:
                failure_codes.append("rf_output_enable_failed")
                recovery = _sanitize_recovery(exc)
                if recovery is not None:
                    evidence["output_enable_recovery"] = recovery
                    if recovery.get("status") == "off_verified":
                        rf_off_confirmed = True
                        rf_output_may_be_on = False

        if rf_enable_confirmed and scope_service is not None and scope_coupling is not None:
            observation, observation_failures = _collect_scope_observation(
                scope_service,
                scope_coupling,
                setup,
            )
            evidence["scope_observation"] = observation
            failure_codes.extend(observation_failures)

        if rf_output_may_be_on and not rf_off_confirmed:
            rf_disable_transaction_started = True
            try:
                _, disable = rf_service.set_output_with_artifact(
                    RfOutputRequest(port_id=setup.port_id, enabled=False)
                )
                evidence["output_disable"] = disable
                if _artifact_port_value(disable, "output_enabled", False):
                    rf_off_confirmed = True
                    rf_output_may_be_on = False
                else:
                    failure_codes.append("rf_output_disable_readback_invalid")
            except Exception:
                failure_codes.append("rf_output_disable_failed")
    except A3PreflightError as exc:
        failure_codes.append(exc.code)
    except Exception:
        failure_codes.append("local_harness_failed")
    finally:
        if (
            rf_output_may_be_on
            and not rf_off_confirmed
            and not rf_disable_transaction_started
            and rf_service is not None
            and rf_service.session_state is not None
            and rf_service.session_state.health is SessionHealth.HEALTHY
        ):
            rf_disable_transaction_started = True
            try:
                _, disable = rf_service.set_output_with_artifact(
                    RfOutputRequest(port_id=setup.port_id, enabled=False)
                )
                evidence["output_disable"] = disable
                if _artifact_port_value(disable, "output_enabled", False):
                    rf_off_confirmed = True
                    rf_output_may_be_on = False
                else:
                    failure_codes.append("rf_output_disable_readback_invalid")
            except Exception:
                failure_codes.append("rf_output_disable_failed")

        if rf_driver is not None:
            before_close = _audit_snapshot(rf_transport)
            rf_close_error = _close_driver(rf_driver)
            after_close = _audit_snapshot(rf_transport)
            evidence["rf_audit"] = {"before_close": before_close, "after_close": after_close}
            if rf_close_error is not None:
                failure_codes.append(rf_close_error)
            completed = (
                frequency_confirmed
                and power_confirmed
                and rf_enable_confirmed
                and rf_off_confirmed
            )
            failure_codes.extend(_rf_audit_failure_codes(before_close, after_close, completed=completed))

        if scope_driver is not None:
            before_close = _audit_snapshot(scope_transport)
            scope_close_error = _close_driver(scope_driver)
            after_close = _audit_snapshot(scope_transport)
            evidence["scope_audit"] = {"before_close": before_close, "after_close": after_close}
            if scope_close_error is not None:
                failure_codes.append("scope_driver_close_failed")

    if not rf_off_confirmed:
        failure_codes.append("final_rf_off_not_confirmed")
    if not _runtime_versions_available(evidence["runtime"]):
        failure_codes.append("runtime_version_unavailable")
    evidence["failure_codes"] = sorted(set(failure_codes))
    evidence["status"] = "passed" if not evidence["failure_codes"] else "failed"
    return evidence


def _open_evidence_output(path: Path) -> TextIO:
    if not path.parent.is_dir():
        raise A3PreflightError("invalid_evidence_output_path")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise A3PreflightError("invalid_evidence_output_path") from exc
    return os.fdopen(descriptor, "w", encoding="utf-8")


def _replace_evidence(output: TextIO, evidence: Mapping[str, object]) -> None:
    text = json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    output.seek(0)
    output.truncate()
    output.write(text)
    output.flush()
    os.fsync(output.fileno())


def _summary(evidence: Mapping[str, object]) -> str:
    scope = evidence.get("scope_observation")
    return json.dumps(
        {
            "schema": A3_EVIDENCE_SCHEMA,
            "status": evidence["status"],
            "failure_codes": evidence["failure_codes"],
            "scope_ch2_signal_detected": (
                scope.get("signal_detected") if isinstance(scope, Mapping) else None
            ),
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rf-config", required=True, type=Path, help="Private read-only RF TOML")
    parser.add_argument("--setup", required=True, type=Path, help="Private A3 setup TOML without resources")
    parser.add_argument("--scope-config", required=True, type=Path, help="Private read-only scope TOML")
    parser.add_argument("--output", type=Path, help="New local JSON evidence file")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly permit two CW writes and one controlled RF ON/OFF sequence",
    )
    args = parser.parse_args(argv)

    try:
        rf_config = load_config(args.rf_config)
        scope_config = load_config(args.scope_config)
        setup = load_a3_evidence_setup(args.setup)
        preflight = validate_a3_preflight(rf_config, setup, scope_config=scope_config)
    except A3PreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "config_or_descriptor_invalid"}))
        return 2

    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": A3_EVIDENCE_SCHEMA,
                    "status": "dry_run_ok",
                    "driver_id": preflight.production_descriptor.driver_id,
                    "production_capabilities": list(preflight.production_descriptor.capabilities),
                    "a3_setup": {
                        "port_id": setup.port_id,
                        "actual_termination_ohm": setup.actual_termination_ohm,
                        "frequency_hz": setup.frequency_hz,
                        "power_dbm": setup.power_dbm,
                    },
                    "scope_channel": setup.scope_observation.ch2,
                    "will_connect": False,
                    "will_write": False,
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
        _replace_evidence(output, {"schema": A3_EVIDENCE_SCHEMA, "evidence": "A3", "status": "started"})
    except A3PreflightError as exc:
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
            evidence = collect_a3_evidence(rf_config, scope_config, preflight, setup)
        except A3PreflightError as exc:
            evidence = _base_evidence(preflight, setup, timestamp_utc=_utc_now())
            evidence["failure_codes"] = [exc.code]
        except Exception:
            evidence = _base_evidence(preflight, setup, timestamp_utc=_utc_now())
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
