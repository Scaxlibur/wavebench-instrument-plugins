"""Collect local A4 RF-OFF Pulse evidence for a RIGOL DSG830.

This private, controlled harness gathers the hardware evidence required before
the production descriptor may declare ``rf_source.pulse_configure``. It never
modifies the production descriptor, enables RF output, drives the rear Pulse
I/O connector, triggers a pulse, or reads the oscilloscope. A private
read-only RF config and a resource-free setup file are required; ``--execute``
is the only write boundary.

The sole write sequence configures an internal single-pulse profile and ends
with Pulse disabled. A failed write or readback is not retried and has no
automatic recovery setter: the harness records the failed evidence and leaves
the instrument for explicit human recovery.
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
    RfProtectionStatus,
    RfPulseConfigureRequest,
    RfPulseMode,
    RfPulseModeProfile,
    RfPulsePolarity,
    RfPulseProfile,
    RfPulseSource,
    RfPulseState,
    RfPulseSnapshot,
    RfSourceDescriptorExtensions,
    RfSourceSnapshot,
    RfSweepState,
    open_instrument_driver,
    rf_pulse_snapshot_document,
    rf_source_snapshot_operation_artifact,
)
from wavebench.instruments.api import InstrumentDescriptor
from wavebench.instruments.capabilities import validate_declared_capabilities
from wavebench.instruments.registry import resolve_instrument_descriptor
from wavebench.instruments.rf_source_capabilities import validate_rf_source_descriptor
from wavebench.logging import CommandLogger
from wavebench.services.resource_lease import ResourceLease
from wavebench.services.rf_source_service import RfSourceService
from wavebench.transport.session import SessionHealth


A4_PULSE_EVIDENCE_SCHEMA = "wavebench.rigol_dsg830.a4_pulse_evidence.v1"
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
_PULSE_PROFILE_QUERY_COUNT = 6
_PULSE_WRITE_COUNT = 6
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


class A4PulsePreflightError(RuntimeError):
    """A stable reason to reject an A4 Pulse operation before I/O."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class A4PulseEvidenceSetup:
    """Human-confirmed, non-sensitive A4 Pulse facts from private setup."""

    port_id: str
    actual_termination_ohm: float
    installed_options: tuple[str, ...]
    request: RfPulseConfigureRequest


@dataclass(frozen=True, slots=True)
class A4PulsePreflight:
    """Static facts accepted before opening the controlled RF session."""

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
        raise A4PulsePreflightError(code)
    normalized = float(value)
    if minimum is not None and normalized < minimum:
        raise A4PulsePreflightError(code)
    return normalized


def _safe_options(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or _SAFE_METADATA_TOKEN.fullmatch(item) is None for item in value
    ):
        raise A4PulsePreflightError("a4_pulse_evidence_options_invalid")
    options = tuple(value)
    if len(set(options)) != len(options) or options != tuple(sorted(options)):
        raise A4PulsePreflightError("a4_pulse_evidence_options_invalid")
    return options


def _request_from_setup(evidence: Mapping[str, object]) -> RfPulseConfigureRequest:
    required = {
        "port_id",
        "actual_termination_ohm",
        "installed_options",
        "period_s",
        "width_s",
        "polarity",
    }
    if set(evidence) != required:
        raise A4PulsePreflightError("a4_pulse_evidence_invalid")
    raw_polarity = evidence.get("polarity")
    if not isinstance(raw_polarity, str):
        raise A4PulsePreflightError("a4_pulse_evidence_polarity_invalid")
    try:
        polarity = RfPulsePolarity(raw_polarity.lower())
    except ValueError as exc:
        raise A4PulsePreflightError("a4_pulse_evidence_polarity_invalid") from exc
    try:
        return RfPulseConfigureRequest(
            port_id=_PORT_ID,
            period_s=_finite(evidence.get("period_s"), "a4_pulse_evidence_period_invalid", minimum=1e-18),
            width_s=_finite(evidence.get("width_s"), "a4_pulse_evidence_width_invalid", minimum=1e-18),
            polarity=polarity,
        )
    except ValueError as exc:
        raise A4PulsePreflightError("a4_pulse_evidence_timing_invalid") from exc


def load_a4_pulse_evidence_setup(path: Path) -> A4PulseEvidenceSetup:
    """Load only the explicit, non-sensitive A4 Pulse setup facts."""

    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise A4PulsePreflightError("a4_pulse_evidence_invalid") from exc
    evidence = raw.get("a4_pulse_evidence")
    if not isinstance(evidence, Mapping):
        raise A4PulsePreflightError("a4_pulse_evidence_not_configured")
    if evidence.get("port_id") != _PORT_ID:
        raise A4PulsePreflightError("a4_pulse_evidence_port_must_be_rf_out")
    actual_termination_ohm = _finite(
        evidence.get("actual_termination_ohm"),
        "a4_pulse_evidence_termination_invalid",
        minimum=1e-12,
    )
    return A4PulseEvidenceSetup(
        port_id=_PORT_ID,
        actual_termination_ohm=actual_termination_ohm,
        installed_options=_safe_options(evidence.get("installed_options")),
        request=_request_from_setup(evidence),
    )


def _require_no_retries(config: WaveBenchConfig) -> None:
    if config.connection.read_retry_attempts != 0 or config.connection.read_retry_delay_ms != 0:
        raise A4PulsePreflightError("rf_source_retries_must_be_disabled")


def _pulse_mode_profile() -> RfPulseModeProfile:
    return RfPulseModeProfile(
        source=RfPulseSource.INTERNAL,
        mode=RfPulseMode.SINGLE,
        polarities=(RfPulsePolarity.INVERTED, RfPulsePolarity.NORMAL),
        period_min_s=40e-9,
        period_max_s=170.0,
        width_min_s=10e-9,
        width_max_s=170.0 - 10e-9,
        minimum_off_time_s=10e-9,
    )


def _build_evidence_descriptor(production: InstrumentDescriptor) -> InstrumentDescriptor:
    """Create one in-memory A4 Pulse descriptor; never register it."""

    extensions = production.rf_source_extensions
    if not isinstance(extensions, RfSourceDescriptorExtensions):
        raise A4PulsePreflightError("rf_source_extensions_invalid")
    if extensions.contract_version != RF_SOURCE_CONTRACT_VERSION:
        raise A4PulsePreflightError("rf_source_extensions_invalid")
    if tuple(port.port_id for port in extensions.topology.ports) != (_PORT_ID,):
        raise A4PulsePreflightError("unexpected_rf_topology")
    features = extensions.features
    if any(feature.feature is RfFeature.PULSE for feature in features):
        raise A4PulsePreflightError("production_pulse_gate_changed")
    if sum(feature.feature is RfFeature.CW for feature in features) != 1:
        raise A4PulsePreflightError("production_cw_contract_invalid")
    if sum(feature.feature is RfFeature.OUTPUT for feature in features) != 1:
        raise A4PulsePreflightError("production_output_contract_invalid")
    pulse_feature = RfFeatureCapability(
        feature=RfFeature.PULSE,
        directions=(RfFeatureDirection.CONFIGURE, RfFeatureDirection.READ),
        port_ids=(_PORT_ID,),
        profile=RfPulseProfile(
            state_readable=True,
            configuration_readable=True,
            mode_profiles=(_pulse_mode_profile(),),
        ),
    )
    evidence = replace(
        production,
        capabilities=(*production.capabilities, "rf_source.pulse_configure"),
        rf_source_extensions=replace(
            extensions,
            features=tuple(sorted((*features, pulse_feature), key=lambda item: item.feature.value)),
        ),
    )
    try:
        validate_rf_source_descriptor(evidence)
    except Exception as exc:
        raise A4PulsePreflightError("a4_pulse_evidence_descriptor_invalid") from exc
    return evidence


def _validate_setup_target(
    evidence_descriptor: InstrumentDescriptor,
    setup: A4PulseEvidenceSetup,
) -> None:
    extensions = evidence_descriptor.rf_source_extensions
    assert isinstance(extensions, RfSourceDescriptorExtensions)
    port = extensions.topology.ports[0]
    if setup.actual_termination_ohm != port.power_reference_impedance_ohm:
        raise A4PulsePreflightError("a4_pulse_evidence_termination_mismatch")
    pulse_feature = next(
        (feature for feature in extensions.features if feature.feature is RfFeature.PULSE),
        None,
    )
    if pulse_feature is None or not isinstance(pulse_feature.profile, RfPulseProfile):
        raise A4PulsePreflightError("a4_pulse_evidence_descriptor_invalid")
    mode_profile = next(
        (
            profile
            for profile in pulse_feature.profile.mode_profiles
            if profile.source is RfPulseSource.INTERNAL and profile.mode is RfPulseMode.SINGLE
        ),
        None,
    )
    if mode_profile is None:
        raise A4PulsePreflightError("a4_pulse_evidence_mode_not_declared")
    request = setup.request
    if request.polarity not in mode_profile.polarities:
        raise A4PulsePreflightError("a4_pulse_evidence_polarity_outside_descriptor_range")
    if not mode_profile.period_min_s <= request.period_s <= mode_profile.period_max_s:
        raise A4PulsePreflightError("a4_pulse_evidence_period_outside_descriptor_range")
    if not mode_profile.width_min_s <= request.width_s <= mode_profile.width_max_s:
        raise A4PulsePreflightError("a4_pulse_evidence_width_outside_descriptor_range")
    if request.width_s > request.period_s - mode_profile.minimum_off_time_s:
        raise A4PulsePreflightError("a4_pulse_evidence_minimum_off_time_violated")


def validate_a4_pulse_preflight(
    rf_config: WaveBenchConfig,
    setup: A4PulseEvidenceSetup,
) -> A4PulsePreflight:
    """Fail closed before creating an RF transport."""

    rf_source = rf_config.rf_source
    if rf_source is None:
        raise A4PulsePreflightError("rf_source_not_configured")
    if rf_source.driver != _DRIVER_ID:
        raise A4PulsePreflightError("unexpected_rf_source_driver")
    if not isinstance(rf_source.resource, str) or not rf_source.resource.strip():
        raise A4PulsePreflightError("rf_source_resource_missing")
    if rf_source.access != "read_only":
        raise A4PulsePreflightError("rf_source_base_access_must_be_read_only")
    _require_no_retries(rf_config)
    production = resolve_instrument_descriptor(_DRIVER_ID, expected_kind="rf_source")
    if production.driver_id != _DRIVER_ID or production.kind != "rf_source":
        raise A4PulsePreflightError("unexpected_descriptor_identity")
    if _MODEL not in production.models:
        raise A4PulsePreflightError("unexpected_descriptor_model")
    if tuple(production.capabilities) != _PRODUCTION_CAPABILITIES:
        raise A4PulsePreflightError("production_pulse_gate_changed")
    if not _runtime_versions_available(_runtime_versions()):
        raise A4PulsePreflightError("runtime_version_unavailable")
    evidence_descriptor = _build_evidence_descriptor(production)
    _validate_setup_target(evidence_descriptor, setup)
    return A4PulsePreflight(
        production_descriptor=production,
        evidence_descriptor=evidence_descriptor,
    )


def _a4_pulse_rf_config(config: WaveBenchConfig) -> WaveBenchConfig:
    rf_source = config.rf_source
    assert rf_source is not None
    return replace(config, rf_source=replace(rf_source, access="read_write"))


def _base_evidence(
    preflight: A4PulsePreflight,
    setup: A4PulseEvidenceSetup,
    *,
    timestamp_utc: str,
    operation_mode: str = "configuration",
) -> dict[str, object]:
    request = setup.request
    return {
        "schema": A4_PULSE_EVIDENCE_SCHEMA,
        "evidence": "A4_PULSE",
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
            "period_s": request.period_s,
            "width_s": request.width_s,
            "polarity": request.polarity.value,
        },
        "status": "failed",
        "failure_codes": [],
        "initial_snapshot": None,
        "pulse_profile": None,
        "pulse_configure": None,
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


def _snapshot_failure_codes(snapshot: RfSourceSnapshot, *, phase: str) -> list[str]:
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
    if any(value.availability is not RfAvailability.VALUE for value in values):
        return [f"{phase}_snapshot_contains_unknown_state"]
    codes: list[str] = []
    if port.output_enabled.value is not False:
        codes.append(f"{phase}_rf_output_not_off")
    if port.modulation.value.value != "disabled":
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


def _observed_artifact_value(port: Mapping[str, object], field: str, expected: object) -> bool:
    observed = port.get(field)
    return (
        isinstance(observed, Mapping)
        and observed.get("availability") == "value"
        and observed.get("value") == expected
    )


def _pulse_artifact_matches(artifact: object, request: RfPulseConfigureRequest) -> bool:
    if not isinstance(artifact, Mapping) or artifact.get("operation") != "rf_source.pulse_configure":
        return False
    postcondition = artifact.get("postcondition_snapshot")
    if not isinstance(postcondition, Mapping):
        return False
    ports = postcondition.get("ports")
    if not isinstance(ports, list) or len(ports) != 1 or not isinstance(ports[0], Mapping):
        return False
    if not (
        _observed_artifact_value(ports[0], "output_enabled", False)
        and _observed_artifact_value(ports[0], "modulation", "disabled")
        and _observed_artifact_value(ports[0], "pulse", "disabled")
        and _observed_artifact_value(ports[0], "sweep", "disabled")
    ):
        return False
    profile = artifact.get("postcondition_pulse_snapshot")
    return (
        isinstance(profile, Mapping)
        and profile.get("port_id") == request.port_id
        and profile.get("source") == RfPulseSource.INTERNAL.value
        and profile.get("mode") == RfPulseMode.SINGLE.value
        and profile.get("period_s") == request.period_s
        and profile.get("width_s") == request.width_s
        and profile.get("polarity") == request.polarity.value
        and profile.get("state") == RfPulseState.DISABLED.value
    )


def _diagnostic_profile_failure_codes(profile: object) -> list[str]:
    if not isinstance(profile, RfPulseSnapshot):
        return ["diagnostic_pulse_profile_invalid"]
    codes: list[str] = []
    if profile.port_id != _PORT_ID:
        codes.append("diagnostic_pulse_profile_port_invalid")
    if profile.source is not RfPulseSource.INTERNAL or profile.mode is not RfPulseMode.SINGLE:
        codes.append("diagnostic_pulse_profile_mode_invalid")
    if profile.state is not RfPulseState.DISABLED:
        codes.append("diagnostic_pulse_profile_not_disabled")
    return codes


def _diagnostic_pulse_read_failure_code(error: Exception) -> str:
    """Classify a fixed driver parser error without retaining its raw response."""

    message = str(error)
    labels = (
        ("pulse source", "source"),
        ("pulse mode", "mode"),
        ("pulse period", "period"),
        ("pulse width", "width"),
        ("pulse polarity", "polarity"),
        ("pulse state", "state"),
    )
    field = next((field for label, field in labels if label in message), None)
    if field is None:
        return "diagnostic_pulse_read_failed"
    if "invalid format" in message or "must be INT or EXT" in message or "must be SINGLE or TRAIN" in message or "must be NORMAL or INVERSE" in message or "must be 0 or 1" in message:
        return f"diagnostic_pulse_{field}_format_invalid"
    if "outside the documented range" in message:
        return f"diagnostic_pulse_{field}_outside_documented_range"
    if "must be finite" in message:
        return f"diagnostic_pulse_{field}_not_finite"
    return f"diagnostic_pulse_{field}_read_invalid"


def _expected_a4_pulse_queries() -> int:
    return 4 * _SNAPSHOT_QUERY_COUNT + _PULSE_PROFILE_QUERY_COUNT


def _expected_a4_pulse_diagnostic_queries() -> int:
    return 2 * _SNAPSHOT_QUERY_COUNT + _PULSE_PROFILE_QUERY_COUNT


def _rf_audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
    *,
    access: str,
    expected_queries: int | None,
    expected_writes: int | None,
) -> list[str]:
    codes: list[str] = []
    if before_close is None:
        return ["rf_audit_before_close_unavailable"]
    if after_close is None:
        codes.append("rf_audit_after_close_unavailable")
    if before_close["access"] != access:
        codes.append("rf_audit_access_invalid")
    counters = before_close["counters"]
    assert isinstance(counters, Mapping)
    if counters["write_outcome_unknown"] != 0 or counters["binary_write_outcome_unknown"] != 0:
        codes.append("rf_write_outcome_unknown")
    if counters["blocked_session_io"] != 0:
        codes.append("rf_blocked_session_io")
    if expected_writes == 0:
        if any(
            counters[key] != 0
            for key in (
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
        ):
            codes.append("rf_readonly_unexpected_write_activity")
    elif expected_writes is not None:
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
    if expected_queries is not None:
        if counters["query_calls"] != expected_queries:
            codes.append("unexpected_rf_query_count")
        if before_close["session_health"] != "healthy":
            codes.append("rf_session_not_healthy_before_close")
    if after_close is not None:
        if after_close["access"] != access:
            codes.append("rf_audit_after_close_access_invalid")
        after_counters = after_close["counters"]
        assert isinstance(after_counters, Mapping)
        if after_counters != counters:
            codes.append("rf_audit_counters_changed_after_close")
        if after_close["session_health"] != "closed":
            codes.append("rf_session_not_closed")
    return codes


def _base_descriptor_matches(preflight: A4PulsePreflight, current: InstrumentDescriptor) -> bool:
    return (
        current.driver_id == preflight.production_descriptor.driver_id
        and current.kind == preflight.production_descriptor.kind
        and tuple(current.models) == tuple(preflight.production_descriptor.models)
        and tuple(current.capabilities) == tuple(preflight.production_descriptor.capabilities)
    )


def collect_a4_pulse_evidence(
    rf_config: WaveBenchConfig,
    preflight: A4PulsePreflight,
    setup: A4PulseEvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Execute one no-trigger Pulse configuration and collect typed evidence."""

    current = validate_a4_pulse_preflight(rf_config, setup)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A4PulsePreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(preflight, setup, timestamp_utc=timestamp_utc or _utc_now())
    failure_codes: list[str] = []
    rf_driver: object | None = None
    rf_transport: object | None = None
    configure_completed = False
    configure_confirmed = False
    final_rf_off_confirmed = False

    try:
        controlled_config = _a4_pulse_rf_config(rf_config)
        rf_source = controlled_config.rf_source
        assert rf_source is not None
        opened = opener(
            driver_reference=rf_source.driver,
            expected_kind="rf_source",
            resource=rf_source.resource or "",
            configured_backend=controlled_config.connection.backend,
            timeout_ms=controlled_config.connection.timeout_ms,
            opc_timeout_ms=controlled_config.connection.opc_timeout_ms,
            read_retry_attempts=0,
            read_retry_delay_ms=0,
            logger=CommandLogger(),
            options=rf_source.options,
            access="read_write",
            lease=ResourceLease(
                resource=rf_source.resource or "",
                mode="exclusive",
                operation="dsg830.a4_pulse_evidence",
            ),
        )
        rf_driver = opened.driver
        rf_transport = opened.transport
        if getattr(opened, "descriptor", None) != preflight.production_descriptor:
            raise A4PulsePreflightError("descriptor_changed_after_preflight")
        try:
            validate_declared_capabilities(preflight.evidence_descriptor, rf_driver)
        except Exception as exc:
            raise A4PulsePreflightError("a4_pulse_evidence_driver_invalid") from exc
        rf_service = RfSourceService(
            config=controlled_config,
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
                _, artifact = rf_service.configure_pulse_with_artifact(setup.request)
                evidence["pulse_configure"] = artifact
                configure_completed = True
                if _pulse_artifact_matches(artifact, setup.request):
                    configure_confirmed = True
                else:
                    failure_codes.append("rf_pulse_readback_invalid")
            except Exception:
                failure_codes.append("rf_pulse_configure_failed")
        if configure_completed:
            try:
                final = rf_service.snapshot()
                evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final)
                final_failures = _snapshot_failure_codes(final, phase="final")
                failure_codes.extend(final_failures)
                final_rf_off_confirmed = not final_failures
            except Exception:
                failure_codes.append("final_rf_snapshot_failed")
    except A4PulsePreflightError as exc:
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
                    access="read_write",
                    expected_queries=(
                        _expected_a4_pulse_queries()
                        if configure_confirmed and final_rf_off_confirmed
                        else None
                    ),
                    expected_writes=(
                        _PULSE_WRITE_COUNT
                        if configure_confirmed and final_rf_off_confirmed
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


def collect_a4_pulse_diagnostic_evidence(
    rf_config: WaveBenchConfig,
    preflight: A4PulsePreflight,
    setup: A4PulseEvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Read one disabled Pulse profile without changing instrument state."""

    current = validate_a4_pulse_preflight(rf_config, setup)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A4PulsePreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(
        preflight,
        setup,
        timestamp_utc=timestamp_utc or _utc_now(),
        operation_mode="diagnostic",
    )
    failure_codes: list[str] = []
    rf_driver: object | None = None
    rf_transport: object | None = None
    profile_read = False
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
                operation="dsg830.a4_pulse_diagnostic",
            ),
        )
        rf_driver = opened.driver
        rf_transport = opened.transport
        if getattr(opened, "descriptor", None) != preflight.production_descriptor:
            raise A4PulsePreflightError("descriptor_changed_after_preflight")
        rf_service = RfSourceService(
            config=rf_config,
            logger=CommandLogger(),
            session=rf_driver,
            descriptor=preflight.production_descriptor,
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
            reader = getattr(rf_driver, "get_rf_pulse_snapshot", None)
            if not callable(reader):
                failure_codes.append("diagnostic_pulse_reader_missing")
            elif getattr(opened.session_state, "health", None) is not SessionHealth.HEALTHY:
                failure_codes.append("diagnostic_pulse_session_not_healthy")
            else:
                try:
                    profile = reader(setup.port_id)
                    evidence["pulse_profile"] = rf_pulse_snapshot_document(profile)
                    profile_read = True
                    failure_codes.extend(_diagnostic_profile_failure_codes(profile))
                except Exception as exc:
                    failure_codes.append(_diagnostic_pulse_read_failure_code(exc))
        if profile_read:
            final = rf_service.snapshot()
            evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final)
            final_failures = _snapshot_failure_codes(final, phase="final")
            failure_codes.extend(final_failures)
            final_rf_off_confirmed = not final_failures
    except A4PulsePreflightError as exc:
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
                    access="read_only",
                    expected_queries=(
                        _expected_a4_pulse_diagnostic_queries()
                        if profile_read and final_rf_off_confirmed
                        else None
                    ),
                    expected_writes=0,
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
        raise A4PulsePreflightError("invalid_evidence_output_path")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise A4PulsePreflightError("invalid_evidence_output_path") from exc
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
            "schema": A4_PULSE_EVIDENCE_SCHEMA,
            "status": evidence["status"],
            "failure_codes": evidence["failure_codes"],
            "operation_mode": evidence.get("operation_mode"),
            "pulse": setup if isinstance(setup, Mapping) else None,
            "rf_output_confirmed_off": evidence["status"] == "passed",
            "pulse_remained_disabled": evidence["status"] == "passed",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rf-config", required=True, type=Path, help="Private read-only RF TOML")
    parser.add_argument("--setup", required=True, type=Path, help="Private A4 Pulse setup TOML")
    parser.add_argument("--output", type=Path, help="New local JSON evidence file")
    execution_mode = parser.add_mutually_exclusive_group()
    execution_mode.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly permit one RF-OFF, Pulse-OFF configuration and readback",
    )
    execution_mode.add_argument(
        "--diagnose",
        action="store_true",
        help="Explicitly collect one read-only disabled Pulse profile diagnostic",
    )
    args = parser.parse_args(argv)

    try:
        rf_config = load_config(args.rf_config)
        setup = load_a4_pulse_evidence_setup(args.setup)
        preflight = validate_a4_pulse_preflight(rf_config, setup)
    except A4PulsePreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "config_or_descriptor_invalid"}))
        return 2

    if not args.execute and not args.diagnose:
        print(
            json.dumps(
                {
                    "schema": A4_PULSE_EVIDENCE_SCHEMA,
                    "status": "dry_run_ok",
                    "driver_id": preflight.production_descriptor.driver_id,
                    "production_capabilities": list(preflight.production_descriptor.capabilities),
                    "a4_pulse_setup": _base_evidence(
                        preflight,
                        setup,
                        timestamp_utc="dry_run",
                    )["setup"],
                    "will_connect": False,
                    "will_write": False,
                    "will_enable_rf_output": False,
                    "will_trigger": False,
                    "will_use_pulse_io": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required with --execute or --diagnose")

    output: TextIO | None = None
    try:
        output = _open_evidence_output(args.output)
        _replace_evidence(
            output,
            {"schema": A4_PULSE_EVIDENCE_SCHEMA, "evidence": "A4_PULSE", "status": "started"},
        )
    except A4PulsePreflightError as exc:
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
                collect_a4_pulse_evidence(rf_config, preflight, setup)
                if args.execute
                else collect_a4_pulse_diagnostic_evidence(rf_config, preflight, setup)
            )
        except A4PulsePreflightError as exc:
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
