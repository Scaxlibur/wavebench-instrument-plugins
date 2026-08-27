"""Collect one local A4-MO modulated-RF-output evidence record for a DSG830.

This private harness validates one deliberately narrow path: a fixed internal
Sine AM profile is configured while RF is OFF, then RF is enabled once at a
fixed low power, CH2 is inspected only for the presence of a signal, and the
source is returned to RF OFF with modulation disabled. It never changes the
production descriptor, never uses trigger/sync or rear-panel Pulse I/O, and
never interprets the DSG830 LF OUTPUT as a modulation measurement.
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
    RfCwRequest,
    RfFeature,
    RfFeatureCapability,
    RfFeatureDirection,
    RfModulatedOutputProfile,
    RfModulatedOutputRequest,
    RfModulationDisableRequest,
    RfModulationKind,
    RfModulationModeProfile,
    RfModulationProfile,
    RfModulationRequest,
    RfModulationSource,
    RfModulationState,
    RfModulationValueUnit,
    RfModulationWaveform,
    RfOutputRequest,
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
from wavebench.services.scope_service import ScopeService
from wavebench.transport.session import SessionHealth


A4_MODULATED_OUTPUT_EVIDENCE_SCHEMA = "wavebench.rigol_dsg830.a4_modulated_output_evidence.v1"
_DRIVER_ID = "rigol.dsg830"
_MODEL = "DSG830"
_PORT_ID = "rf_out"
_PRODUCTION_CAPABILITIES = (
    "rf_source.idn",
    "rf_source.snapshot",
    "rf_source.cw_configure",
    "rf_source.output",
    "rf_source.modulation_configure",
    "rf_source.pulse_configure",
    "rf_source.sweep_configure",
)
_TEST_FREQUENCY_HZ = 1_000_000.0
_TEST_POWER_DBM = -50.0
_TEST_AM_DEPTH_PERCENT = 50.0
_TEST_INTERNAL_FREQUENCY_HZ = 1_000.0
_SNAPSHOT_QUERY_COUNT = 8
_EXPECTED_RF_QUERY_COUNT = 154
_EXPECTED_RF_WRITES = 12
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


class A4ModulatedOutputPreflightError(RuntimeError):
    """Stable, redacted reason to refuse before opening a real transport."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class ScopeObservationSetup:
    ch2: int
    allow_ch2_50ohm: bool
    points: str
    minimum_observable_vpp_v: float


@dataclass(frozen=True, slots=True)
class A4ModulatedOutputSetup:
    port_id: str
    actual_termination_ohm: float
    installed_options: tuple[str, ...]
    frequency_hz: float
    power_dbm: float
    modulation: RfModulationRequest
    scope_observation: ScopeObservationSetup


@dataclass(frozen=True, slots=True)
class A4ModulatedOutputPreflight:
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
        raise A4ModulatedOutputPreflightError(code)
    normalized = float(value)
    if minimum is not None and normalized < minimum:
        raise A4ModulatedOutputPreflightError(code)
    return normalized


def _safe_options(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or _SAFE_METADATA_TOKEN.fullmatch(item) is None for item in value
    ):
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_options_invalid")
    options = tuple(value)
    if len(set(options)) != len(options) or options != tuple(sorted(options)):
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_options_invalid")
    return options


def _load_scope_setup(raw: Mapping[str, object]) -> ScopeObservationSetup:
    required = {"ch2", "allow_ch2_50ohm", "points", "minimum_observable_vpp_v"}
    if set(raw) != required:
        raise A4ModulatedOutputPreflightError("scope_observation_invalid")
    if raw["ch2"] != 2:
        raise A4ModulatedOutputPreflightError("scope_observation_channel_must_be_ch2")
    if raw["allow_ch2_50ohm"] is not True:
        raise A4ModulatedOutputPreflightError("scope_observation_ch2_50ohm_not_explicit")
    if raw["points"] != "def":
        raise A4ModulatedOutputPreflightError("scope_observation_points_must_be_def")
    return ScopeObservationSetup(
        ch2=2,
        allow_ch2_50ohm=True,
        points="def",
        minimum_observable_vpp_v=_finite(
            raw["minimum_observable_vpp_v"],
            "scope_observation_threshold_invalid",
            minimum=1e-12,
        ),
    )


def load_a4_modulated_output_setup(path: Path) -> A4ModulatedOutputSetup:
    """Load only the fixed, non-sensitive A4-MO target and scope facts."""

    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_invalid") from exc
    evidence = raw.get("a4_modulated_output")
    scope = raw.get("scope_observation")
    if not isinstance(evidence, Mapping):
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_not_configured")
    if not isinstance(scope, Mapping):
        raise A4ModulatedOutputPreflightError("scope_observation_not_configured")
    required = {
        "port_id",
        "actual_termination_ohm",
        "installed_options",
        "frequency_hz",
        "power_dbm",
        "modulation_kind",
        "depth_percent",
        "internal_frequency_hz",
    }
    if set(evidence) != required:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_invalid")
    if evidence["port_id"] != _PORT_ID:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_port_must_be_rf_out")
    if evidence["modulation_kind"] != RfModulationKind.AM.value:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_mode_must_be_am")
    frequency_hz = _finite(
        evidence["frequency_hz"],
        "a4_mo_evidence_frequency_invalid",
        minimum=1e-12,
    )
    power_dbm = _finite(evidence["power_dbm"], "a4_mo_evidence_power_invalid")
    depth_percent = _finite(
        evidence["depth_percent"],
        "a4_mo_evidence_depth_invalid",
        minimum=0.0,
    )
    internal_frequency_hz = _finite(
        evidence["internal_frequency_hz"],
        "a4_mo_evidence_internal_frequency_invalid",
        minimum=1e-12,
    )
    if (
        frequency_hz != _TEST_FREQUENCY_HZ
        or power_dbm != _TEST_POWER_DBM
        or depth_percent != _TEST_AM_DEPTH_PERCENT
        or internal_frequency_hz != _TEST_INTERNAL_FREQUENCY_HZ
    ):
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_target_must_match_fixed_profile")
    try:
        modulation = RfModulationRequest(
            port_id=_PORT_ID,
            kind=RfModulationKind.AM,
            internal_frequency_hz=internal_frequency_hz,
            depth_percent=depth_percent,
        )
    except ValueError as exc:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_depth_invalid") from exc
    return A4ModulatedOutputSetup(
        port_id=_PORT_ID,
        actual_termination_ohm=_finite(
            evidence["actual_termination_ohm"],
            "a4_mo_evidence_termination_invalid",
            minimum=1e-12,
        ),
        installed_options=_safe_options(evidence["installed_options"]),
        frequency_hz=frequency_hz,
        power_dbm=power_dbm,
        modulation=modulation,
        scope_observation=_load_scope_setup(scope),
    )


def _normalized_resource(value: object) -> str:
    return value.strip().casefold() if isinstance(value, str) else ""


def _modulated_output_profile() -> RfModulatedOutputProfile:
    return RfModulatedOutputProfile(
        maximum_power_dbm=_TEST_POWER_DBM,
        mode_profiles=(
            RfModulationModeProfile(
                kind=RfModulationKind.AM,
                value_unit=RfModulationValueUnit.PERCENT,
                value_min=_TEST_AM_DEPTH_PERCENT,
                value_max=_TEST_AM_DEPTH_PERCENT,
                internal_frequency_min_hz=_TEST_INTERNAL_FREQUENCY_HZ,
                internal_frequency_max_hz=_TEST_INTERNAL_FREQUENCY_HZ,
            ),
        ),
    )


def _build_evidence_descriptor(production: InstrumentDescriptor) -> InstrumentDescriptor:
    """Build an in-memory, fixed-profile descriptor; never register it."""

    extensions = production.rf_source_extensions
    if not isinstance(extensions, RfSourceDescriptorExtensions):
        raise A4ModulatedOutputPreflightError("rf_source_extensions_invalid")
    if extensions.contract_version != RF_SOURCE_CONTRACT_VERSION:
        raise A4ModulatedOutputPreflightError("rf_source_extensions_invalid")
    if tuple(port.port_id for port in extensions.topology.ports) != (_PORT_ID,):
        raise A4ModulatedOutputPreflightError("unexpected_rf_topology")
    features = extensions.features
    if any(feature.feature is RfFeature.MODULATED_OUTPUT for feature in features):
        raise A4ModulatedOutputPreflightError("production_modulated_output_gate_changed")
    modulation_feature = next(
        (feature for feature in features if feature.feature is RfFeature.MODULATION),
        None,
    )
    output_feature = next(
        (feature for feature in features if feature.feature is RfFeature.OUTPUT),
        None,
    )
    if not isinstance(getattr(modulation_feature, "profile", None), RfModulationProfile):
        raise A4ModulatedOutputPreflightError("production_modulation_contract_invalid")
    if output_feature is None:
        raise A4ModulatedOutputPreflightError("production_output_contract_invalid")
    evidence_modulation_feature = replace(
        modulation_feature,
        directions=(
            RfFeatureDirection.CONFIGURE,
            RfFeatureDirection.DISABLE,
            RfFeatureDirection.READ,
        ),
    )
    modulated_output_feature = RfFeatureCapability(
        feature=RfFeature.MODULATED_OUTPUT,
        directions=(RfFeatureDirection.ENABLE,),
        port_ids=(_PORT_ID,),
        profile=_modulated_output_profile(),
    )
    evidence = replace(
        production,
        capabilities=(
            *production.capabilities,
            "rf_source.modulation_disable",
            "rf_source.modulated_output_enable",
        ),
        rf_source_extensions=replace(
            extensions,
            features=tuple(
                sorted(
                    (
                        *(
                            evidence_modulation_feature
                            if feature is modulation_feature
                            else feature
                            for feature in features
                        ),
                        modulated_output_feature,
                    ),
                    key=lambda item: item.feature.value,
                )
            ),
        ),
    )
    try:
        validate_rf_source_descriptor(evidence)
    except Exception as exc:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_descriptor_invalid") from exc
    return evidence


def _validate_setup_target(
    descriptor: InstrumentDescriptor,
    setup: A4ModulatedOutputSetup,
) -> None:
    extensions = descriptor.rf_source_extensions
    assert isinstance(extensions, RfSourceDescriptorExtensions)
    port = extensions.topology.ports[0]
    if setup.actual_termination_ohm != port.power_reference_impedance_ohm:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_termination_mismatch")
    if not port.frequency_min_hz <= setup.frequency_hz <= port.frequency_max_hz:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_frequency_outside_descriptor_range")
    if not port.power_min_dbm <= setup.power_dbm <= port.power_max_dbm:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_power_outside_descriptor_range")
    feature = next(
        (item for item in extensions.features if item.feature is RfFeature.MODULATED_OUTPUT),
        None,
    )
    if feature is None or not isinstance(feature.profile, RfModulatedOutputProfile):
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_descriptor_invalid")
    profile = feature.profile.mode_profiles[0]
    if (
        profile.kind is not setup.modulation.kind
        or not profile.value_min <= setup.modulation.value <= profile.value_max
        or not (
            profile.internal_frequency_min_hz
            <= setup.modulation.internal_frequency_hz
            <= profile.internal_frequency_max_hz
        )
    ):
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_target_outside_descriptor_range")


def validate_a4_modulated_output_preflight(
    rf_config: WaveBenchConfig,
    setup: A4ModulatedOutputSetup,
    *,
    scope_config: WaveBenchConfig,
) -> A4ModulatedOutputPreflight:
    """Validate every static safety fact without opening either instrument."""

    rf_source = rf_config.rf_source
    if rf_source is None:
        raise A4ModulatedOutputPreflightError("rf_source_not_configured")
    if rf_source.driver != _DRIVER_ID:
        raise A4ModulatedOutputPreflightError("unexpected_rf_source_driver")
    rf_resource = _normalized_resource(rf_source.resource)
    if not rf_resource:
        raise A4ModulatedOutputPreflightError("rf_source_resource_missing")
    if rf_source.access != "read_only":
        raise A4ModulatedOutputPreflightError("rf_source_base_access_must_be_read_only")
    if rf_config.connection.read_retry_attempts or rf_config.connection.read_retry_delay_ms:
        raise A4ModulatedOutputPreflightError("rf_source_retries_must_be_disabled")
    production = resolve_instrument_descriptor(_DRIVER_ID, expected_kind="rf_source")
    if production.driver_id != _DRIVER_ID or production.kind != "rf_source":
        raise A4ModulatedOutputPreflightError("unexpected_descriptor_identity")
    if _MODEL not in production.models:
        raise A4ModulatedOutputPreflightError("unexpected_descriptor_model")
    if tuple(production.capabilities) != _PRODUCTION_CAPABILITIES:
        raise A4ModulatedOutputPreflightError("production_modulated_output_gate_changed")
    if not _runtime_versions_available(_runtime_versions()):
        raise A4ModulatedOutputPreflightError("runtime_version_unavailable")
    evidence_descriptor = _build_evidence_descriptor(production)
    _validate_setup_target(evidence_descriptor, setup)

    scope_resource = _normalized_resource(scope_config.connection.resource)
    if not scope_resource:
        raise A4ModulatedOutputPreflightError("scope_resource_missing")
    if scope_resource == rf_resource:
        raise A4ModulatedOutputPreflightError("scope_resource_must_differ_from_rf_source")
    if scope_config.scope.access != "read_only":
        raise A4ModulatedOutputPreflightError("scope_base_access_must_be_read_only")
    if scope_config.scope.check_errors:
        raise A4ModulatedOutputPreflightError("scope_error_drain_must_be_disabled")
    if scope_config.connection.read_retry_attempts or scope_config.connection.read_retry_delay_ms:
        raise A4ModulatedOutputPreflightError("scope_retries_must_be_disabled")
    scope_descriptor = resolve_instrument_descriptor(
        scope_config.scope.driver,
        expected_kind="scope",
    )
    required_scope_capabilities = {"scope.idn", "scope.channel_coupling", "scope.fetch_waveform"}
    if not required_scope_capabilities <= set(scope_descriptor.capabilities):
        raise A4ModulatedOutputPreflightError("scope_observation_capability_missing")
    return A4ModulatedOutputPreflight(
        production_descriptor=production,
        evidence_descriptor=evidence_descriptor,
        scope_descriptor=scope_descriptor,
    )


def _rf_write_config(config: WaveBenchConfig, setup: A4ModulatedOutputSetup) -> WaveBenchConfig:
    rf_source = config.rf_source
    assert rf_source is not None
    return replace(
        config,
        rf_source=replace(
            rf_source,
            access="read_write",
            safety_ports=(
                RfPortSafetyConfig(
                    port_id=setup.port_id,
                    minimum_frequency_hz=setup.frequency_hz,
                    maximum_frequency_hz=setup.frequency_hz,
                    maximum_power_dbm=setup.power_dbm,
                    actual_termination_ohm=setup.actual_termination_ohm,
                ),
            ),
        ),
    )


def _scope_write_config(config: WaveBenchConfig) -> WaveBenchConfig:
    return replace(
        config,
        scope=replace(config.scope, access="read_write", check_errors=False),
        waveform=replace(config.waveform, format="real", byte_order="lsbf", points="DEF"),
    )


def _base_evidence(
    preflight: A4ModulatedOutputPreflight,
    setup: A4ModulatedOutputSetup,
    *,
    mode: str,
    timestamp_utc: str,
) -> dict[str, object]:
    return {
        "schema": A4_MODULATED_OUTPUT_EVIDENCE_SCHEMA,
        "evidence": "A4-MO",
        "mode": mode,
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
            "modulation_kind": setup.modulation.kind.value,
            "depth_percent": setup.modulation.value,
            "internal_frequency_hz": setup.modulation.internal_frequency_hz,
        },
        "scope_observation": {
            "status": "not_started" if mode == "execute" else "not_used",
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
        "modulation_configure": None,
        "modulated_output_enable": None,
        "output_disable": None,
        "modulation_disable": None,
        "final_snapshot": None,
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


def _audit_snapshot(transport: object | None) -> dict[str, object] | None:
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


def _baseline_failure_codes(snapshot: RfSourceSnapshot, *, phase: str) -> list[str]:
    port = _snapshot_port(snapshot)
    if port is None:
        return [f"{phase}_snapshot_topology_invalid"]
    observed = (
        port.frequency_hz,
        port.power_dbm,
        port.output_enabled,
        port.modulation,
        port.pulse,
        port.sweep,
        snapshot.protection,
    )
    if any(item.availability is not RfAvailability.VALUE for item in observed):
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


def _active_modulation_artifact_matches(
    artifact: object,
    setup: A4ModulatedOutputSetup,
    *,
    operation: str,
    output_enabled: bool,
) -> bool:
    if not isinstance(artifact, Mapping) or artifact.get("operation") != operation:
        return False
    if not _artifact_port_value(artifact, "output_enabled", output_enabled):
        return False
    if not _artifact_port_value(artifact, "modulation", RfModulationState.ENABLED.value):
        return False
    if not _artifact_port_value(artifact, "pulse", RfPulseState.DISABLED.value):
        return False
    if not _artifact_port_value(artifact, "sweep", RfSweepState.DISABLED.value):
        return False
    profile = artifact.get("postcondition_modulation_snapshot")
    if not isinstance(profile, Mapping):
        return False
    return (
        profile.get("port_id") == setup.port_id
        and profile.get("kind") == RfModulationKind.AM.value
        and profile.get("source") == RfModulationSource.INTERNAL.value
        and profile.get("waveform") == RfModulationWaveform.SINE.value
        and profile.get("depth_percent") == setup.modulation.value
        and profile.get("internal_frequency_hz") == setup.modulation.internal_frequency_hz
        and profile.get("enabled_modes") == [RfModulationKind.AM.value]
        and profile.get("global_enabled") is True
        and profile.get("fault_codes") == []
    )


def _modulation_disable_artifact_matches(
    artifact: object,
    setup: A4ModulatedOutputSetup,
) -> bool:
    if not isinstance(artifact, Mapping) or artifact.get("operation") != "rf_source.modulation_disable":
        return False
    result = artifact.get("result")
    if not isinstance(result, Mapping) or result.get("write_completed") is not True:
        return False
    if not _artifact_port_value(artifact, "output_enabled", False):
        return False
    if not _artifact_port_value(artifact, "modulation", RfModulationState.DISABLED.value):
        return False
    profile = artifact.get("postcondition_modulation_state")
    return (
        isinstance(profile, Mapping)
        and profile.get("port_id") == setup.port_id
        and profile.get("enabled_modes") == []
        and profile.get("global_enabled") is False
        and profile.get("fault_codes") == []
    )


def _scope_channel_summary(
    waveform: object,
    *,
    setup: ScopeObservationSetup,
    coupling: str,
) -> dict[str, object]:
    values = getattr(waveform, "voltages_v", None)
    if values is None:
        return {"status": "invalid_waveform", "channel": setup.ch2, "coupling": coupling}
    try:
        finite_values = [float(value) for value in values if isfinite(float(value))]
    except Exception:
        return {"status": "invalid_waveform", "channel": setup.ch2, "coupling": coupling}
    if len(finite_values) < 2:
        return {"status": "insufficient_samples", "channel": setup.ch2, "coupling": coupling}
    vpp_v = max(finite_values) - min(finite_values)
    return {
        "status": "observed",
        "channel": setup.ch2,
        "coupling": coupling,
        "sample_count": len(finite_values),
        "vpp_v": vpp_v,
        "signal_detected": vpp_v >= setup.minimum_observable_vpp_v,
        "unrestored_fields": list(_SCOPE_UNRESTORED_FIELDS),
    }


def _open_scope_observer(
    config: WaveBenchConfig,
    preflight: A4ModulatedOutputPreflight,
    setup: A4ModulatedOutputSetup,
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
            operation="dsg830.a4_modulated_output_observation",
        ),
    )
    if getattr(opened, "descriptor", None) != preflight.scope_descriptor:
        raise A4ModulatedOutputPreflightError("scope_descriptor_changed_after_preflight")
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
    setup: A4ModulatedOutputSetup,
) -> tuple[dict[str, object], list[str]]:
    try:
        waveform = service.fetch_waveform(setup.scope_observation.ch2)
    except Exception:
        return (
            {
                "status": "fetch_failed",
                "channel": setup.scope_observation.ch2,
                "coupling": coupling,
                "signal_detected": None,
                "unrestored_fields": list(_SCOPE_UNRESTORED_FIELDS),
            },
            ["scope_ch2_fetch_failed"],
        )
    summary = _scope_channel_summary(
        waveform,
        setup=setup.scope_observation,
        coupling=coupling,
    )
    if summary.get("signal_detected") is not True:
        return summary, ["scope_ch2_signal_not_observed"]
    return summary, []


def _rf_audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
    *,
    completed: bool,
    diagnostic: bool,
) -> list[str]:
    if before_close is None:
        return ["rf_audit_before_close_unavailable"]
    codes: list[str] = []
    if after_close is None:
        codes.append("rf_audit_after_close_unavailable")
    expected_access = "read_only" if diagnostic else "read_write"
    if before_close["access"] != expected_access:
        codes.append("rf_audit_access_invalid")
    counters = before_close["counters"]
    assert isinstance(counters, Mapping)
    if counters["write_outcome_unknown"] or counters["binary_write_outcome_unknown"]:
        codes.append("rf_write_outcome_unknown")
    if counters["blocked_session_io"]:
        codes.append("rf_blocked_session_io")
    if diagnostic:
        if any(
            counters[key] != 0
            for key in (
                "write_requests",
                "write_attempts",
                "write_transmitted",
                "write_completed",
                "instrument_mutation_writes",
                "instrument_mutation_writes_completed",
            )
        ):
            codes.append("rf_diagnostic_unexpected_write_activity")
        if completed and counters["query_calls"] != 25:
            codes.append("unexpected_rf_diagnostic_query_count")
    elif completed:
        if counters["query_calls"] != _EXPECTED_RF_QUERY_COUNT:
            codes.append("unexpected_rf_query_count")
        if any(
            counters[key] != _EXPECTED_RF_WRITES
            for key in (
                "write_requests",
                "write_attempts",
                "write_transmitted",
                "write_completed",
                "instrument_mutation_writes",
                "instrument_mutation_writes_completed",
            )
        ):
            codes.append("unexpected_rf_write_count")
    if completed and before_close["session_health"] != "healthy":
        codes.append("rf_session_not_healthy_before_close")
    if after_close is not None:
        after_counters = after_close["counters"]
        assert isinstance(after_counters, Mapping)
        if after_close["access"] != expected_access:
            codes.append("rf_audit_after_close_access_invalid")
        if after_counters != counters:
            codes.append("rf_audit_counters_changed_after_close")
        if after_close["session_health"] != "closed":
            codes.append("rf_session_not_closed")
    return codes


def _scope_audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
) -> list[str]:
    if before_close is None:
        return ["scope_audit_before_close_unavailable"]
    codes: list[str] = []
    if after_close is None:
        codes.append("scope_audit_after_close_unavailable")
    if before_close["access"] != "read_write":
        codes.append("scope_audit_access_invalid")
    counters = before_close["counters"]
    assert isinstance(counters, Mapping)
    if counters["write_outcome_unknown"] or counters["binary_write_outcome_unknown"]:
        codes.append("scope_write_outcome_unknown")
    if counters["blocked_session_io"]:
        codes.append("scope_blocked_session_io")
    if before_close["session_health"] != "healthy":
        codes.append("scope_session_not_healthy_before_close")
    if after_close is not None:
        after_counters = after_close["counters"]
        assert isinstance(after_counters, Mapping)
        if after_close["access"] != "read_write":
            codes.append("scope_audit_after_close_access_invalid")
        if after_counters != counters:
            codes.append("scope_audit_counters_changed_after_close")
        if after_close["session_health"] != "closed":
            codes.append("scope_session_not_closed")
    return codes


def _base_descriptor_matches(
    preflight: A4ModulatedOutputPreflight,
    current: InstrumentDescriptor,
) -> bool:
    return (
        current.driver_id == preflight.production_descriptor.driver_id
        and current.kind == preflight.production_descriptor.kind
        and tuple(current.models) == tuple(preflight.production_descriptor.models)
        and tuple(current.capabilities) == tuple(preflight.production_descriptor.capabilities)
    )


def _open_rf_service(
    config: WaveBenchConfig,
    preflight: A4ModulatedOutputPreflight,
    *,
    descriptor: InstrumentDescriptor,
    access: str,
    operation: str,
    opener: Callable[..., Any],
) -> tuple[RfSourceService, object, object]:
    rf_source = config.rf_source
    assert rf_source is not None
    opened = opener(
        driver_reference=rf_source.driver,
        expected_kind="rf_source",
        resource=rf_source.resource or "",
        configured_backend=config.connection.backend,
        timeout_ms=config.connection.timeout_ms,
        opc_timeout_ms=config.connection.opc_timeout_ms,
        read_retry_attempts=0,
        read_retry_delay_ms=0,
        logger=CommandLogger(),
        options=rf_source.options,
        access=access,
        lease=ResourceLease(
            resource=rf_source.resource or "",
            mode="exclusive",
            operation=operation,
        ),
    )
    if getattr(opened, "descriptor", None) != preflight.production_descriptor:
        raise A4ModulatedOutputPreflightError("descriptor_changed_after_preflight")
    try:
        validate_declared_capabilities(descriptor, opened.driver)
    except Exception as exc:
        raise A4ModulatedOutputPreflightError("a4_mo_evidence_driver_invalid") from exc
    service = RfSourceService(
        config=config,
        logger=CommandLogger(),
        session=opened.driver,
        descriptor=descriptor,
        transport=opened.transport,
        session_state=opened.session_state,
    )
    return service, opened.driver, opened.transport


def collect_a4_modulated_output_diagnostic(
    rf_config: WaveBenchConfig,
    scope_config: WaveBenchConfig,
    preflight: A4ModulatedOutputPreflight,
    setup: A4ModulatedOutputSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Read the RF-OFF baseline and inactive AM profile without writes."""

    current = validate_a4_modulated_output_preflight(rf_config, setup, scope_config=scope_config)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A4ModulatedOutputPreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(preflight, setup, mode="diagnostic", timestamp_utc=timestamp_utc or _utc_now())
    failures: list[str] = []
    driver: object | None = None
    transport: object | None = None
    try:
        service, driver, transport = _open_rf_service(
            rf_config,
            preflight,
            descriptor=preflight.production_descriptor,
            access="read_only",
            operation="dsg830.a4_modulated_output_diagnostic",
            opener=opener,
        )
        initial = service.snapshot()
        evidence["initial_snapshot"] = rf_source_snapshot_operation_artifact(initial)
        hardware = evidence["hardware"]
        assert isinstance(hardware, dict)
        hardware["firmware"] = _firmware(driver)
        if hardware["firmware"] is None:
            failures.append("snapshot_firmware_unavailable")
        failures.extend(_baseline_failure_codes(initial, phase="initial"))
        profile = driver.get_rf_modulation_snapshot(setup.port_id, setup.modulation.kind)
        if (
            profile.port_id != setup.port_id
            or profile.kind is not setup.modulation.kind
            or profile.enabled_modes != ()
            or profile.global_enabled is not False
            or profile.fault_codes
        ):
            failures.append("diagnostic_modulation_profile_not_inactive")
        final = service.snapshot()
        evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final)
        failures.extend(_baseline_failure_codes(final, phase="final"))
    except A4ModulatedOutputPreflightError as exc:
        failures.append(exc.code)
    except Exception:
        failures.append("diagnostic_harness_failed")
    finally:
        if driver is not None:
            before_close = _audit_snapshot(transport)
            close_error = _close_driver(driver)
            after_close = _audit_snapshot(transport)
            evidence["rf_audit"] = {"before_close": before_close, "after_close": after_close}
            if close_error is not None:
                failures.append(close_error)
            completed = not failures
            failures.extend(
                _rf_audit_failure_codes(
                    before_close,
                    after_close,
                    completed=completed,
                    diagnostic=True,
                )
            )
    evidence["failure_codes"] = sorted(set(failures))
    evidence["status"] = "passed" if not evidence["failure_codes"] else "failed"
    return evidence


def collect_a4_modulated_output_evidence(
    rf_config: WaveBenchConfig,
    scope_config: WaveBenchConfig,
    preflight: A4ModulatedOutputPreflight,
    setup: A4ModulatedOutputSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Run one fixed AM RF-output cycle and retain only redacted evidence."""

    current = validate_a4_modulated_output_preflight(rf_config, setup, scope_config=scope_config)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A4ModulatedOutputPreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(preflight, setup, mode="execute", timestamp_utc=timestamp_utc or _utc_now())
    failures: list[str] = []
    rf_service: RfSourceService | None = None
    rf_driver: object | None = None
    rf_transport: object | None = None
    scope_service: ScopeService | None = None
    scope_driver: object | None = None
    scope_transport: object | None = None
    scope_coupling: str | None = None
    frequency_ok = False
    power_ok = False
    modulation_ok = False
    output_on_ok = False
    output_may_be_on = False
    output_off_ok = False
    modulation_off_ok = False
    final_baseline_ok = False
    output_disable_started = False

    try:
        scope_service, scope_driver, scope_transport, scope_coupling = _open_scope_observer(
            _scope_write_config(scope_config),
            preflight,
            setup,
            opener=opener,
        )
        scope = evidence["scope_observation"]
        assert isinstance(scope, dict)
        scope["status"] = "ready"
        scope["coupling"] = scope_coupling

        write_config = _rf_write_config(rf_config, setup)
        rf_service, rf_driver, rf_transport = _open_rf_service(
            write_config,
            preflight,
            descriptor=preflight.evidence_descriptor,
            access="read_write",
            operation="dsg830.a4_modulated_output_evidence",
            opener=opener,
        )
        initial = rf_service.snapshot()
        evidence["initial_snapshot"] = rf_source_snapshot_operation_artifact(initial)
        hardware = evidence["hardware"]
        assert isinstance(hardware, dict)
        hardware["firmware"] = _firmware(rf_driver)
        if hardware["firmware"] is None:
            failures.append("snapshot_firmware_unavailable")
        failures.extend(_baseline_failure_codes(initial, phase="initial"))
        output_off_ok = not any(code.startswith("initial_rf_output") for code in failures)

        if not failures:
            try:
                _, artifact = rf_service.configure_cw_with_artifact(
                    RfCwRequest(port_id=setup.port_id, frequency_hz=setup.frequency_hz)
                )
                evidence["frequency_configure"] = artifact
                frequency_ok = _artifact_port_value(artifact, "frequency_hz", setup.frequency_hz)
                if not frequency_ok:
                    failures.append("rf_frequency_readback_invalid")
            except Exception:
                failures.append("rf_frequency_configure_failed")

        if frequency_ok:
            try:
                _, artifact = rf_service.configure_cw_with_artifact(
                    RfCwRequest(port_id=setup.port_id, power_dbm=setup.power_dbm)
                )
                evidence["power_configure"] = artifact
                power_ok = _artifact_port_value(artifact, "power_dbm", setup.power_dbm)
                if not power_ok:
                    failures.append("rf_power_readback_invalid")
            except Exception:
                failures.append("rf_power_configure_failed")

        if frequency_ok and power_ok:
            try:
                _, artifact = rf_service.configure_modulation_with_artifact(setup.modulation)
                evidence["modulation_configure"] = artifact
                modulation_ok = _active_modulation_artifact_matches(
                    artifact,
                    setup,
                    operation="rf_source.modulation_configure",
                    output_enabled=False,
                )
                if not modulation_ok:
                    failures.append("rf_modulation_readback_invalid")
            except Exception:
                failures.append("rf_modulation_configure_failed")

        if modulation_ok:
            output_may_be_on = True
            output_off_ok = False
            try:
                _, artifact = rf_service.enable_modulated_output_with_artifact(
                    RfModulatedOutputRequest(modulation=setup.modulation)
                )
                evidence["modulated_output_enable"] = artifact
                output_on_ok = _active_modulation_artifact_matches(
                    artifact,
                    setup,
                    operation="rf_source.modulated_output_enable",
                    output_enabled=True,
                )
                if not output_on_ok:
                    failures.append("rf_modulated_output_readback_invalid")
            except Exception as exc:
                failures.append("rf_modulated_output_enable_failed")
                recovery = getattr(exc, "rf_source_recovery", None)
                if isinstance(recovery, Mapping) and recovery.get("status") == "off_verified":
                    output_off_ok = True
                    output_may_be_on = False

        if output_on_ok and scope_service is not None and scope_coupling is not None:
            observation, observation_failures = _collect_scope_observation(
                scope_service,
                scope_coupling,
                setup,
            )
            evidence["scope_observation"] = observation
            failures.extend(observation_failures)

        if output_may_be_on and not output_off_ok:
            output_disable_started = True
            try:
                _, artifact = rf_service.set_output_with_artifact(
                    RfOutputRequest(port_id=setup.port_id, enabled=False)
                )
                evidence["output_disable"] = artifact
                output_off_ok = _artifact_port_value(artifact, "output_enabled", False)
                output_may_be_on = not output_off_ok
                if not output_off_ok:
                    failures.append("rf_output_disable_readback_invalid")
            except Exception:
                failures.append("rf_output_disable_failed")

        if modulation_ok and output_off_ok and rf_service is not None:
            try:
                _, artifact = rf_service.disable_modulation_with_artifact(
                    RfModulationDisableRequest(port_id=setup.port_id, kind=setup.modulation.kind)
                )
                evidence["modulation_disable"] = artifact
                modulation_off_ok = _modulation_disable_artifact_matches(artifact, setup)
                if not modulation_off_ok:
                    failures.append("rf_modulation_disable_readback_invalid")
            except Exception:
                failures.append("rf_modulation_disable_failed")

        if modulation_off_ok and rf_service is not None:
            try:
                final = rf_service.snapshot()
                evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final)
                final_failures = _baseline_failure_codes(final, phase="final")
                failures.extend(final_failures)
                final_baseline_ok = not final_failures
            except Exception:
                failures.append("final_snapshot_failed")
    except A4ModulatedOutputPreflightError as exc:
        failures.append(exc.code)
    except Exception:
        failures.append("local_harness_failed")
    finally:
        if (
            output_may_be_on
            and not output_off_ok
            and not output_disable_started
            and rf_service is not None
            and rf_service.session_state is not None
            and rf_service.session_state.health is SessionHealth.HEALTHY
        ):
            output_disable_started = True
            try:
                _, artifact = rf_service.set_output_with_artifact(
                    RfOutputRequest(port_id=setup.port_id, enabled=False)
                )
                evidence["output_disable"] = artifact
                output_off_ok = _artifact_port_value(artifact, "output_enabled", False)
                output_may_be_on = not output_off_ok
                if not output_off_ok:
                    failures.append("rf_output_disable_readback_invalid")
            except Exception:
                failures.append("rf_output_disable_failed")
        if rf_driver is not None:
            before_close = _audit_snapshot(rf_transport)
            close_error = _close_driver(rf_driver)
            after_close = _audit_snapshot(rf_transport)
            evidence["rf_audit"] = {"before_close": before_close, "after_close": after_close}
            if close_error is not None:
                failures.append(close_error)
            completed = (
                frequency_ok
                and power_ok
                and modulation_ok
                and output_on_ok
                and output_off_ok
                and modulation_off_ok
                and final_baseline_ok
                and evidence["scope_observation"].get("signal_detected") is True
            )
            failures.extend(
                _rf_audit_failure_codes(
                    before_close,
                    after_close,
                    completed=completed,
                    diagnostic=False,
                )
            )
        if scope_driver is not None:
            before_close = _audit_snapshot(scope_transport)
            close_error = _close_driver(scope_driver)
            after_close = _audit_snapshot(scope_transport)
            evidence["scope_audit"] = {"before_close": before_close, "after_close": after_close}
            if close_error is not None:
                failures.append("scope_driver_close_failed")
            failures.extend(_scope_audit_failure_codes(before_close, after_close))

    if not output_off_ok:
        failures.append("final_rf_off_not_confirmed")
    if not modulation_off_ok:
        failures.append("final_modulation_off_not_confirmed")
    if not _runtime_versions_available(evidence["runtime"]):
        failures.append("runtime_version_unavailable")
    evidence["failure_codes"] = sorted(set(failures))
    evidence["status"] = "passed" if not evidence["failure_codes"] else "failed"
    return evidence


def _open_evidence_output(path: Path) -> TextIO:
    if not path.parent.is_dir():
        raise A4ModulatedOutputPreflightError("invalid_evidence_output_path")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise A4ModulatedOutputPreflightError("invalid_evidence_output_path") from exc
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
            "schema": A4_MODULATED_OUTPUT_EVIDENCE_SCHEMA,
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
    parser.add_argument("--scope-config", required=True, type=Path, help="Private read-only scope TOML")
    parser.add_argument("--setup", required=True, type=Path, help="Private A4-MO setup without resources")
    parser.add_argument("--output", type=Path, help="New local JSON evidence file")
    parser.add_argument("--diagnose", action="store_true", help="Run only the zero-write RF-OFF diagnostic")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly permit fixed CW/modulation writes, one RF ON/OFF, and CH2 observation",
    )
    args = parser.parse_args(argv)
    if args.diagnose and args.execute:
        parser.error("--diagnose and --execute are mutually exclusive")
    try:
        rf_config = load_config(args.rf_config)
        scope_config = load_config(args.scope_config)
        setup = load_a4_modulated_output_setup(args.setup)
        preflight = validate_a4_modulated_output_preflight(
            rf_config,
            setup,
            scope_config=scope_config,
        )
    except A4ModulatedOutputPreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "config_or_descriptor_invalid"}))
        return 2

    if not args.diagnose and not args.execute:
        print(
            json.dumps(
                {
                    "schema": A4_MODULATED_OUTPUT_EVIDENCE_SCHEMA,
                    "status": "dry_run_ok",
                    "driver_id": preflight.production_descriptor.driver_id,
                    "production_capabilities": list(preflight.production_descriptor.capabilities),
                    "will_connect": False,
                    "will_write": False,
                    "will_enable_rf_output": False,
                    "will_fetch_scope": False,
                },
                sort_keys=True,
            )
        )
        return 0
    if args.output is None:
        parser.error("--output is required with --diagnose or --execute")

    output: TextIO | None = None
    try:
        output = _open_evidence_output(args.output)
        _replace_evidence(
            output,
            {
                "schema": A4_MODULATED_OUTPUT_EVIDENCE_SCHEMA,
                "evidence": "A4-MO",
                "status": "started",
            },
        )
    except A4ModulatedOutputPreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "local_output_invalid"}))
        return 2

    try:
        if args.diagnose:
            evidence = collect_a4_modulated_output_diagnostic(
                rf_config,
                scope_config,
                preflight,
                setup,
            )
        else:
            evidence = collect_a4_modulated_output_evidence(
                rf_config,
                scope_config,
                preflight,
                setup,
            )
        _replace_evidence(output, evidence)
    except Exception:
        print(json.dumps({"status": "evidence_write_failed", "failure_code": "local_output_failed"}))
        return 2
    finally:
        if output is not None:
            try:
                output.close()
            except Exception:
                return 2
    print(_summary(evidence))
    return 0 if evidence["status"] == "passed" else 1


if __name__ == "__main__":  # pragma: no cover - local harness entry point.
    raise SystemExit(main())
