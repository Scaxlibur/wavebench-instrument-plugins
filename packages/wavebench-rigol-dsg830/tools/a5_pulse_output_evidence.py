"""Collect private A5 evidence for one bounded DSG830 Pulse-output path.

This tool covers only the verified physical route from DSG830 ``PULSE IN/OUT``
in its output direction to an RTM2032 ``EXT TRIGGER INPUT``.  It never uses
``TRIGGER IN``, reference-clock connectors, sweep arm/fire, or RF output.

The source starts and ends with RF output and Pulse Output off.  It configures
one internal/single ``1 ms`` / ``100 us`` / normal-polarity Pulse profile,
temporarily switches the scope trigger mode from external/auto to normal,
runs one ``SINGle`` acquisition, then turns Pulse Output off and restores the
scope trigger mode to auto.  The scope acquisition state and the original
DSG830 internal Pulse profile are deliberately not restored; both are recorded
as remaining manual state.

Private input configurations must be isolated, ``read_only``, and retry-free.
``--execute`` creates two temporary write-authorized sessions solely for this
fixed transaction.  The setup and output evidence files must not contain
instrument resources, serials, raw replies, or waveforms.
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
    RfFeature,
    RfFeatureCapability,
    RfFeatureDirection,
    RfModulationState,
    RfProtectionStatus,
    RfPulseConfigureRequest,
    RfPulseMode,
    RfPulseOutputDirection,
    RfPulseOutputProfile,
    RfPulseOutputRequest,
    RfPulseOutputSnapshot,
    RfPulsePolarity,
    RfPulseSource,
    RfPulseState,
    RfSourceDescriptorExtensions,
    RfSourceSnapshot,
    RfSweepState,
    rf_pulse_output_snapshot_document,
    rf_source_snapshot_operation_artifact,
)
from wavebench.logging import CommandLogger
from wavebench.services.resource_lease import ResourceLease
from wavebench.services.rf_source_service import RfSourceService


A5_PULSE_OUTPUT_EVIDENCE_SCHEMA = "wavebench.rigol_dsg830.a5_pulse_output_evidence.v1"
_RF_DRIVER_ID = "rigol.dsg830"
_SCOPE_DRIVER_ID = "rohde-schwarz.rtm2032"
_MODEL = "DSG830"
_PORT_ID = "rf_out"
_INTERFACE_ID = "pulse_in_out"
_WIRING = "dsg830_pulse_in_out_to_rtm2032_ext_trigger_input"
_SCOPE_TRIGGER_SOURCE = "external"
_SCOPE_INITIAL_TRIGGER_MODE = "auto"
_SCOPE_TRIAL_TRIGGER_MODE = "normal"
_PULSE_PERIOD_S = 1e-3
_PULSE_WIDTH_S = 100e-6
_PULSE_POLARITY = RfPulsePolarity.NORMAL
_PULSE_OUTPUT_LOW_LEVEL_V = 0.0
_PULSE_OUTPUT_HIGH_LEVEL_V = 3.3
_PULSE_OUTPUT_IMPEDANCE_OHM = 600.0
_SCOPE_EXT_TRIGGER_INPUT_IMPEDANCE_OHM = 1_000_000.0
_SCOPE_EXT_TRIGGER_INPUT_CAPACITANCE_PF = 12.0
_SCOPE_EXT_TRIGGER_INPUT_MAX_PEAK_V = 150.0
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
_PULSE_OUTPUT_SNAPSHOT_QUERY_COUNT = 7
_PULSE_CONFIGURE_QUERY_COUNT = 22
_PULSE_OUTPUT_TRANSACTION_QUERY_COUNT = 30
_PULSE_CONFIGURE_WRITE_COUNT = 6
_PULSE_OUTPUT_TRANSACTION_WRITE_COUNT = 1
_RF_PRIMARY_SUCCESS_QUERY_COUNT = (
    _SNAPSHOT_QUERY_COUNT
    + _PULSE_OUTPUT_SNAPSHOT_QUERY_COUNT
    + _PULSE_CONFIGURE_QUERY_COUNT
    + (2 * _PULSE_OUTPUT_TRANSACTION_QUERY_COUNT)
)
_RF_PRIMARY_SUCCESS_WRITE_COUNT = (
    _PULSE_CONFIGURE_WRITE_COUNT + (2 * _PULSE_OUTPUT_TRANSACTION_WRITE_COUNT)
)
_RF_FINAL_VERIFICATION_QUERY_COUNT = _SNAPSHOT_QUERY_COUNT + _PULSE_OUTPUT_SNAPSHOT_QUERY_COUNT
_RF_RECOVERY_DISABLE_AND_VERIFY_QUERY_COUNT = (
    _PULSE_OUTPUT_TRANSACTION_QUERY_COUNT + _RF_FINAL_VERIFICATION_QUERY_COUNT
)
_RF_RECOVERY_DISABLE_AND_VERIFY_WRITE_COUNT = _PULSE_OUTPUT_TRANSACTION_WRITE_COUNT
_SCOPE_EXPECTED_QUERY_COUNT = 5
_SCOPE_EXPECTED_WRITE_COUNT = 3
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
_COMPLETED_WRITE_COUNTER_KEYS = (
    "write_requests",
    "write_attempts",
    "write_transmitted",
    "write_completed",
    "instrument_mutation_writes",
    "instrument_mutation_writes_completed",
)
_BINARY_WRITE_COUNTER_KEYS = (
    "binary_write_requests",
    "binary_write_attempts",
    "binary_write_transmitted",
    "binary_write_completed",
    "binary_write_outcome_unknown",
)


class A5PulseOutputPreflightError(RuntimeError):
    """Stable redacted reason to refuse the physical path before I/O."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


@dataclass(frozen=True, slots=True)
class A5PulseOutputEvidenceSetup:
    """Non-sensitive acknowledgement of the single physical route under test."""

    port_id: str
    interface_id: str
    wiring: str


@dataclass(frozen=True, slots=True)
class A5PulseOutputPreflight:
    """Static descriptor facts accepted before RF or scope transport creation."""

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


def load_a5_pulse_output_evidence_setup(path: Path) -> A5PulseOutputEvidenceSetup:
    """Load the fixed physical-route acknowledgement without private resources."""

    try:
        raw = tomllib.loads(path.read_bytes().decode("utf-8-sig"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_invalid") from exc
    setup = raw.get("a5_pulse_output_evidence")
    if not isinstance(setup, Mapping):
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_not_configured")
    if set(setup) != {"port_id", "interface_id", "wiring"}:
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_invalid")
    if setup.get("port_id") != _PORT_ID:
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_port_must_be_rf_out")
    if setup.get("interface_id") != _INTERFACE_ID:
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_interface_invalid")
    if setup.get("wiring") != _WIRING:
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_wiring_invalid")
    return A5PulseOutputEvidenceSetup(
        port_id=_PORT_ID,
        interface_id=_INTERFACE_ID,
        wiring=_WIRING,
    )


def _require_no_retries(config: WaveBenchConfig, *, prefix: str) -> None:
    if config.connection.read_retry_attempts != 0 or config.connection.read_retry_delay_ms != 0:
        raise A5PulseOutputPreflightError(f"{prefix}_retries_must_be_disabled")


def _pulse_output_profile() -> RfPulseOutputProfile:
    return RfPulseOutputProfile(
        interface_id=_INTERFACE_ID,
        direction=RfPulseOutputDirection.OUTPUT,
        output_readable=True,
        low_level_v=_PULSE_OUTPUT_LOW_LEVEL_V,
        high_level_v=_PULSE_OUTPUT_HIGH_LEVEL_V,
        output_impedance_ohm=_PULSE_OUTPUT_IMPEDANCE_OHM,
        source=RfPulseSource.INTERNAL,
        mode=RfPulseMode.SINGLE,
        period_s=_PULSE_PERIOD_S,
        width_s=_PULSE_WIDTH_S,
        polarity=_PULSE_POLARITY,
        pulse_state=RfPulseState.DISABLED,
    )


def _build_evidence_descriptor(production: InstrumentDescriptor) -> InstrumentDescriptor:
    """Create the temporary A5 descriptor without registering a production capability."""

    extensions = production.rf_source_extensions
    if not isinstance(extensions, RfSourceDescriptorExtensions):
        raise A5PulseOutputPreflightError("rf_source_extensions_invalid")
    if extensions.contract_version != RF_SOURCE_CONTRACT_VERSION:
        raise A5PulseOutputPreflightError("rf_source_extensions_invalid")
    if tuple(port.port_id for port in extensions.topology.ports) != (_PORT_ID,):
        raise A5PulseOutputPreflightError("unexpected_rf_topology")
    if "rf_source.pulse_output" in production.capabilities:
        raise A5PulseOutputPreflightError("production_pulse_output_gate_changed")
    if any(feature.feature is RfFeature.PULSE_OUTPUT for feature in extensions.features):
        raise A5PulseOutputPreflightError("production_pulse_output_feature_gate_changed")
    if not any(feature.feature is RfFeature.PULSE for feature in extensions.features):
        raise A5PulseOutputPreflightError("production_pulse_contract_missing")
    pulse_output_feature = RfFeatureCapability(
        feature=RfFeature.PULSE_OUTPUT,
        directions=(
            RfFeatureDirection.DISABLE,
            RfFeatureDirection.ENABLE,
            RfFeatureDirection.READ,
        ),
        port_ids=(_PORT_ID,),
        profile=_pulse_output_profile(),
    )
    evidence = replace(
        production,
        capabilities=(*production.capabilities, "rf_source.pulse_output"),
        rf_source_extensions=replace(
            extensions,
            features=tuple(
                sorted(
                    (*extensions.features, pulse_output_feature),
                    key=lambda item: item.feature.value,
                )
            ),
        ),
    )
    try:
        validate_rf_source_descriptor(evidence)
    except Exception as exc:
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_descriptor_invalid") from exc
    return evidence


def validate_a5_pulse_output_preflight(
    rf_config: WaveBenchConfig,
    scope_config: WaveBenchConfig,
    setup: A5PulseOutputEvidenceSetup,
) -> A5PulseOutputPreflight:
    """Fail closed before opening temporary read-write RF or scope sessions."""

    rf_source = rf_config.rf_source
    if rf_source is None:
        raise A5PulseOutputPreflightError("rf_source_not_configured")
    if rf_source.driver != _RF_DRIVER_ID:
        raise A5PulseOutputPreflightError("unexpected_rf_source_driver")
    if not isinstance(rf_source.resource, str) or not rf_source.resource.strip():
        raise A5PulseOutputPreflightError("rf_source_resource_missing")
    if rf_source.access != "read_only":
        raise A5PulseOutputPreflightError("rf_source_base_access_must_be_read_only")
    if scope_config.scope.driver != _SCOPE_DRIVER_ID:
        raise A5PulseOutputPreflightError("unexpected_scope_driver")
    if not isinstance(scope_config.connection.resource, str) or not scope_config.connection.resource.strip():
        raise A5PulseOutputPreflightError("scope_resource_missing")
    if scope_config.scope.access != "read_only":
        raise A5PulseOutputPreflightError("scope_base_access_must_be_read_only")
    if scope_config.scope.check_errors:
        raise A5PulseOutputPreflightError("scope_error_drain_must_be_disabled")
    if rf_source.resource.strip().casefold() == scope_config.connection.resource.strip().casefold():
        raise A5PulseOutputPreflightError("scope_resource_must_differ_from_rf_source")
    if setup != A5PulseOutputEvidenceSetup(_PORT_ID, _INTERFACE_ID, _WIRING):
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_setup_invalid")
    if _PULSE_OUTPUT_HIGH_LEVEL_V > _SCOPE_EXT_TRIGGER_INPUT_MAX_PEAK_V:
        raise A5PulseOutputPreflightError("scope_input_electrical_bound_invalid")
    _require_no_retries(rf_config, prefix="rf_source")
    _require_no_retries(scope_config, prefix="scope")
    production = resolve_instrument_descriptor(_RF_DRIVER_ID, expected_kind="rf_source")
    if production.driver_id != _RF_DRIVER_ID or production.kind != "rf_source":
        raise A5PulseOutputPreflightError("unexpected_descriptor_identity")
    if _MODEL not in production.models:
        raise A5PulseOutputPreflightError("unexpected_descriptor_model")
    if tuple(production.capabilities) != _PRODUCTION_CAPABILITIES:
        raise A5PulseOutputPreflightError("production_capabilities_changed")
    scope_descriptor = resolve_instrument_descriptor(_SCOPE_DRIVER_ID, expected_kind="scope")
    if scope_descriptor.driver_id != _SCOPE_DRIVER_ID or scope_descriptor.kind != "scope":
        raise A5PulseOutputPreflightError("unexpected_scope_descriptor")
    if not _runtime_versions_available(_runtime_versions()):
        raise A5PulseOutputPreflightError("runtime_version_unavailable")
    return A5PulseOutputPreflight(
        production_descriptor=production,
        evidence_descriptor=_build_evidence_descriptor(production),
        scope_descriptor=scope_descriptor,
    )


def _rf_write_config(config: WaveBenchConfig) -> WaveBenchConfig:
    rf_source = config.rf_source
    assert rf_source is not None
    return replace(config, rf_source=replace(rf_source, access="read_write"))


def _base_evidence(
    preflight: A5PulseOutputPreflight,
    setup: A5PulseOutputEvidenceSetup,
    *,
    timestamp_utc: str,
) -> dict[str, object]:
    return {
        "schema": A5_PULSE_OUTPUT_EVIDENCE_SCHEMA,
        "evidence": "A5_PULSE_OUTPUT",
        "operation_mode": "execute",
        "timestamp_utc": timestamp_utc,
        "driver_id": preflight.production_descriptor.driver_id,
        "model": _MODEL,
        "production_capabilities": list(preflight.production_descriptor.capabilities),
        "runtime": _runtime_versions(),
        "hardware": {"model": _MODEL, "firmware": None},
        "setup": {
            "port_id": setup.port_id,
            "interface_id": setup.interface_id,
            "wiring": setup.wiring,
            "scope_trigger_source": _SCOPE_TRIGGER_SOURCE,
            "scope_initial_trigger_mode": _SCOPE_INITIAL_TRIGGER_MODE,
            "scope_trial_trigger_mode": _SCOPE_TRIAL_TRIGGER_MODE,
            "pulse_profile": {
                "source": RfPulseSource.INTERNAL.value,
                "mode": RfPulseMode.SINGLE.value,
                "period_s": _PULSE_PERIOD_S,
                "width_s": _PULSE_WIDTH_S,
                "polarity": _PULSE_POLARITY.value,
                "pulse_state": RfPulseState.DISABLED.value,
            },
            "pulse_output": {
                "direction": RfPulseOutputDirection.OUTPUT.value,
                "low_level_v": _PULSE_OUTPUT_LOW_LEVEL_V,
                "high_level_v": _PULSE_OUTPUT_HIGH_LEVEL_V,
                "output_impedance_ohm": _PULSE_OUTPUT_IMPEDANCE_OHM,
            },
            "receiver": {
                "interface": "rtm2032_ext_trigger_input",
                "input_impedance_ohm": _SCOPE_EXT_TRIGGER_INPUT_IMPEDANCE_OHM,
                "input_capacitance_pf": _SCOPE_EXT_TRIGGER_INPUT_CAPACITANCE_PF,
                "maximum_peak_v": _SCOPE_EXT_TRIGGER_INPUT_MAX_PEAK_V,
            },
        },
        "status": "failed",
        "failure_codes": [],
        "initial_snapshot": None,
        "initial_pulse_output_snapshot": None,
        "initial_scope_trigger": None,
        "pulse_configure": None,
        "pulse_output_enable": None,
        "scope_observation": {
            "status": "not_started",
            "single_completed": None,
            "unrestored_fields": ["scope_acquisition_state"],
        },
        "pulse_output_disable": None,
        "recovery_pulse_output_disable": None,
        "final_snapshot": None,
        "final_pulse_output_snapshot": None,
        "rf_unrestored_fields": ["dsg830_internal_pulse_profile"],
        "rf_audit": {"primary": None, "recovery": None},
        "scope_audit": {"primary": None, "recovery": None},
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


def _close_and_audit(driver: object, transport: object) -> tuple[
    dict[str, object] | None,
    dict[str, object] | None,
    str | None,
]:
    before_close = _audit_snapshot(transport)
    close_error = _close_driver(driver)
    after_close = _audit_snapshot(transport)
    return before_close, after_close, close_error


def _audit_failure_codes(
    before_close: dict[str, object] | None,
    after_close: dict[str, object] | None,
    *,
    prefix: str,
    expected_queries: int | None,
    expected_writes: int | None,
) -> list[str]:
    if before_close is None:
        return [f"{prefix}_audit_before_close_unavailable"]
    codes: list[str] = []
    if before_close["access"] != "read_write":
        codes.append(f"{prefix}_audit_access_invalid")
    counters = before_close["counters"]
    assert isinstance(counters, Mapping)
    if counters["blocked_session_io"] != 0:
        codes.append(f"{prefix}_blocked_session_io")
    if counters["write_outcome_unknown"] or counters["binary_write_outcome_unknown"]:
        codes.append(f"{prefix}_write_outcome_unknown")
    if expected_queries is not None:
        if counters["query_calls"] != expected_queries:
            codes.append(f"unexpected_{prefix}_query_count")
        if before_close["session_health"] != "healthy":
            codes.append(f"{prefix}_session_not_healthy_before_close")
    if expected_writes is not None:
        if any(counters[key] != expected_writes for key in _COMPLETED_WRITE_COUNTER_KEYS):
            codes.append(f"unexpected_{prefix}_write_count")
        if any(counters[key] != 0 for key in _BINARY_WRITE_COUNTER_KEYS):
            codes.append(f"unexpected_{prefix}_binary_write_count")
    if after_close is None:
        return [*codes, f"{prefix}_audit_after_close_unavailable"]
    if after_close["access"] != "read_write":
        codes.append(f"{prefix}_audit_after_close_access_invalid")
    after_counters = after_close["counters"]
    assert isinstance(after_counters, Mapping)
    if after_counters != counters:
        codes.append(f"{prefix}_audit_counters_changed_after_close")
    if after_close["session_health"] != "closed":
        codes.append(f"{prefix}_session_not_closed")
    return codes


def _clean_scope_response(response: object) -> str:
    if not isinstance(response, str):
        raise ValueError("scope response invalid")
    value = response.strip().upper()
    if not value:
        raise ValueError("scope response invalid")
    return value


def _scope_trigger_source(response: object) -> str:
    value = _clean_scope_response(response)
    if value in {"EXT", "EXTERNAL"}:
        return _SCOPE_TRIGGER_SOURCE
    raise ValueError("scope trigger source invalid")


def _scope_trigger_mode(response: object) -> str:
    value = _clean_scope_response(response)
    if value in {"AUTO", "AUTOMATIC"}:
        return _SCOPE_INITIAL_TRIGGER_MODE
    if value in {"NORM", "NORMAL"}:
        return _SCOPE_TRIAL_TRIGGER_MODE
    raise ValueError("scope trigger mode invalid")


def _scope_opc_completed(response: object) -> bool:
    return _clean_scope_response(response) == "1"


def _snapshot_failure_codes(snapshot: object, *, phase: str) -> list[str]:
    if not isinstance(snapshot, RfSourceSnapshot):
        return [f"{phase}_snapshot_invalid"]
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


def _pulse_output_failure_codes(
    snapshot: object,
    *,
    phase: str,
    require_profile: bool,
) -> list[str]:
    if not isinstance(snapshot, RfPulseOutputSnapshot):
        return [f"{phase}_pulse_output_snapshot_invalid"]
    if snapshot.port_id != _PORT_ID or snapshot.interface_id != _INTERFACE_ID:
        return [f"{phase}_pulse_output_target_invalid"]
    if snapshot.direction is not RfPulseOutputDirection.OUTPUT:
        return [f"{phase}_pulse_output_direction_invalid"]
    if snapshot.enabled is not False:
        return [f"{phase}_pulse_output_not_off"]
    if not require_profile:
        return []
    profile = _pulse_output_profile()
    if (
        snapshot.low_level_v != profile.low_level_v
        or snapshot.high_level_v != profile.high_level_v
        or snapshot.output_impedance_ohm != profile.output_impedance_ohm
        or snapshot.source is not profile.source
        or snapshot.mode is not profile.mode
        or snapshot.period_s != profile.period_s
        or snapshot.width_s != profile.width_s
        or snapshot.polarity is not profile.polarity
        or snapshot.pulse_state is not profile.pulse_state
    ):
        return [f"{phase}_pulse_output_profile_invalid"]
    return []


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


def _base_descriptor_matches(
    preflight: A5PulseOutputPreflight,
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
    preflight: A5PulseOutputPreflight,
    *,
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
        access="read_write",
        lease=ResourceLease(
            resource=rf_source.resource or "",
            mode="exclusive",
            operation=operation,
        ),
    )
    if getattr(opened, "descriptor", None) != preflight.production_descriptor:
        raise A5PulseOutputPreflightError("descriptor_changed_after_preflight")
    try:
        validate_declared_capabilities(preflight.evidence_descriptor, opened.driver)
    except Exception as exc:
        raise A5PulseOutputPreflightError("a5_pulse_output_evidence_driver_invalid") from exc
    service = RfSourceService(
        config=config,
        logger=CommandLogger(),
        session=opened.driver,
        descriptor=preflight.evidence_descriptor,
        transport=opened.transport,
        session_state=opened.session_state,
    )
    return service, opened.driver, opened.transport


def _open_scope_transport(
    config: WaveBenchConfig,
    preflight: A5PulseOutputPreflight,
    *,
    operation: str,
    opener: Callable[..., Any],
) -> tuple[object, object]:
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
            operation=operation,
        ),
    )
    if getattr(opened, "descriptor", None) != preflight.scope_descriptor:
        raise A5PulseOutputPreflightError("scope_descriptor_changed_after_preflight")
    return opened.driver, opened.transport


def collect_a5_pulse_output_evidence(
    rf_config: WaveBenchConfig,
    scope_config: WaveBenchConfig,
    preflight: A5PulseOutputPreflight,
    setup: A5PulseOutputEvidenceSetup,
    *,
    opener: Callable[..., Any] = open_instrument_driver,
    timestamp_utc: str | None = None,
) -> dict[str, object]:
    """Run one fixed A5 physical-output cycle and return only redacted evidence."""

    current = validate_a5_pulse_output_preflight(rf_config, scope_config, setup)
    if not _base_descriptor_matches(preflight, current.production_descriptor):
        raise A5PulseOutputPreflightError("descriptor_changed_after_preflight")
    evidence = _base_evidence(preflight, setup, timestamp_utc=timestamp_utc or _utc_now())
    failures: list[str] = []
    rf_service: RfSourceService | None = None
    rf_driver: object | None = None
    rf_transport: object | None = None
    scope_driver: object | None = None
    scope_transport: object | None = None
    scope_mode_normal_attempted = False
    scope_mode_normal_confirmed = False
    scope_mode_auto_restored = False
    pulse_configure_confirmed = False
    pulse_output_enable_attempted = False
    pulse_output_enable_confirmed = False
    primary_pulse_output_disable_confirmed = False
    final_rf_output_off_confirmed = False
    final_pulse_output_off_confirmed = False
    final_baseline_confirmed = False

    try:
        scope_driver, scope_transport = _open_scope_transport(
            scope_config,
            preflight,
            operation="dsg830.a5_pulse_output_observation",
            opener=opener,
        )
        # This is a deliberately isolated hardware-acceptance adapter.  It
        # uses the audited transport for the exact EXT/AUTO/NORM/SINGle route
        # and does not claim or extend an RTM production-driver capability.
        source = _scope_trigger_source(scope_transport.query("TRIGger:A:SOURce?"))
        initial_mode = _scope_trigger_mode(scope_transport.query("TRIGger:A:MODE?"))
        evidence["initial_scope_trigger"] = {"source": source, "mode": initial_mode}
        if source != _SCOPE_TRIGGER_SOURCE:
            failures.append("scope_trigger_source_not_external")
        if initial_mode != _SCOPE_INITIAL_TRIGGER_MODE:
            failures.append("scope_trigger_mode_not_auto")

        if not failures:
            rf_service, rf_driver, rf_transport = _open_rf_service(
                _rf_write_config(rf_config),
                preflight,
                operation="dsg830.a5_pulse_output_evidence",
                opener=opener,
            )
            initial_snapshot = rf_service.snapshot()
            evidence["initial_snapshot"] = rf_source_snapshot_operation_artifact(initial_snapshot)
            hardware = evidence["hardware"]
            assert isinstance(hardware, dict)
            hardware["firmware"] = _firmware(rf_driver)
            if hardware["firmware"] is None:
                failures.append("snapshot_firmware_unavailable")
            failures.extend(_snapshot_failure_codes(initial_snapshot, phase="initial"))

            initial_pulse_output = rf_driver.get_rf_pulse_output_snapshot(
                setup.port_id,
                setup.interface_id,
            )
            evidence["initial_pulse_output_snapshot"] = rf_pulse_output_snapshot_document(
                initial_pulse_output
            )
            failures.extend(
                _pulse_output_failure_codes(
                    initial_pulse_output,
                    phase="initial",
                    require_profile=False,
                )
            )

        if not failures and rf_service is not None:
            request = RfPulseConfigureRequest(
                port_id=setup.port_id,
                period_s=_PULSE_PERIOD_S,
                width_s=_PULSE_WIDTH_S,
                polarity=_PULSE_POLARITY,
            )
            try:
                _, artifact = rf_service.configure_pulse_with_artifact(request)
                evidence["pulse_configure"] = artifact
                pulse_configure_confirmed = True
            except Exception:
                failures.append("rf_pulse_configure_failed")

        if pulse_configure_confirmed and not failures and scope_transport is not None:
            try:
                scope_mode_normal_attempted = True
                scope_transport.write("TRIGger:A:MODE NORM")
                if (
                    _scope_trigger_mode(scope_transport.query("TRIGger:A:MODE?"))
                    != _SCOPE_TRIAL_TRIGGER_MODE
                ):
                    failures.append("scope_trigger_mode_normal_unverified")
                else:
                    scope_mode_normal_confirmed = True
            except Exception:
                failures.append("scope_trigger_mode_normal_failed")

        if scope_mode_normal_confirmed and not failures and rf_service is not None:
            try:
                pulse_output_enable_attempted = True
                result, artifact = rf_service.set_pulse_output_with_artifact(
                    RfPulseOutputRequest(
                        port_id=setup.port_id,
                        interface_id=setup.interface_id,
                        enabled=True,
                    )
                )
                evidence["pulse_output_enable"] = artifact
                if result.enabled is not True or result.write_completed is not True:
                    failures.append("pulse_output_enable_unverified")
                else:
                    pulse_output_enable_confirmed = True
            except Exception:
                failures.append("pulse_output_enable_failed")

        if pulse_output_enable_confirmed and scope_transport is not None:
            scope = evidence["scope_observation"]
            assert isinstance(scope, dict)
            try:
                scope_transport.write("SINGle")
                scope["status"] = "single_started"
                completed = _scope_opc_completed(scope_transport.query("*OPC?"))
                scope["single_completed"] = completed
                scope["status"] = "single_completed" if completed else "single_not_completed"
                if not completed:
                    failures.append("scope_single_not_completed")
            except Exception:
                scope["status"] = "single_observation_failed"
                failures.append("scope_single_observation_failed")
    except A5PulseOutputPreflightError as exc:
        failures.append(exc.code)
    except Exception:
        failures.append("local_harness_failed")
    finally:
        if pulse_output_enable_attempted and rf_service is not None:
            try:
                result, artifact = rf_service.set_pulse_output_with_artifact(
                    RfPulseOutputRequest(
                        port_id=setup.port_id,
                        interface_id=setup.interface_id,
                        enabled=False,
                    )
                )
                evidence["pulse_output_disable"] = artifact
                if result.enabled is not False:
                    failures.append("pulse_output_disable_unverified")
                else:
                    primary_pulse_output_disable_confirmed = True
            except Exception:
                failures.append("pulse_output_disable_failed")
        if scope_mode_normal_attempted and scope_transport is not None:
            try:
                scope_transport.write("TRIGger:A:MODE AUTO")
                if (
                    _scope_trigger_mode(scope_transport.query("TRIGger:A:MODE?"))
                    != _SCOPE_INITIAL_TRIGGER_MODE
                ):
                    failures.append("scope_trigger_mode_auto_unverified")
                else:
                    scope_mode_auto_restored = True
                    scope = evidence["scope_observation"]
                    assert isinstance(scope, dict)
                    scope["trigger_mode_restored"] = _SCOPE_INITIAL_TRIGGER_MODE
            except Exception:
                failures.append("scope_trigger_mode_auto_restore_failed")
        if rf_driver is not None:
            before_close, after_close, close_error = _close_and_audit(rf_driver, rf_transport)
            rf_audit = evidence["rf_audit"]
            assert isinstance(rf_audit, dict)
            rf_audit["primary"] = {"before_close": before_close, "after_close": after_close}
            if close_error is not None:
                failures.append(f"rf_primary_{close_error}")
            primary_cycle_complete = (
                pulse_configure_confirmed
                and pulse_output_enable_confirmed
                and primary_pulse_output_disable_confirmed
            )
            failures.extend(
                _audit_failure_codes(
                    before_close,
                    after_close,
                    prefix="rf_primary",
                    expected_queries=(
                        _RF_PRIMARY_SUCCESS_QUERY_COUNT if primary_cycle_complete else None
                    ),
                    expected_writes=(
                        _RF_PRIMARY_SUCCESS_WRITE_COUNT if primary_cycle_complete else None
                    ),
                )
            )
        if scope_driver is not None:
            before_close, after_close, close_error = _close_and_audit(scope_driver, scope_transport)
            scope_audit = evidence["scope_audit"]
            assert isinstance(scope_audit, dict)
            scope_audit["primary"] = {
                "before_close": before_close,
                "after_close": after_close,
            }
            if close_error is not None:
                failures.append(f"scope_primary_{close_error}")
            completed_scope_transaction = (
                scope_mode_normal_attempted
                and scope_mode_normal_confirmed
                and scope_mode_auto_restored
                and isinstance(evidence["scope_observation"], Mapping)
                and evidence["scope_observation"].get("status")
                in {"single_completed", "single_not_completed"}
            )
            failures.extend(
                _audit_failure_codes(
                    before_close,
                    after_close,
                    prefix="scope_primary",
                    expected_queries=(
                        _SCOPE_EXPECTED_QUERY_COUNT if completed_scope_transaction else None
                    ),
                    expected_writes=(
                        _SCOPE_EXPECTED_WRITE_COUNT if completed_scope_transaction else None
                    ),
                )
            )

        if scope_mode_normal_attempted and not scope_mode_auto_restored:
            recovery_driver: object | None = None
            recovery_transport: object | None = None
            recovery_confirmed = False
            try:
                recovery_driver, recovery_transport = _open_scope_transport(
                    scope_config,
                    preflight,
                    operation="dsg830.a5_pulse_output_scope_recovery",
                    opener=opener,
                )
                recovery_transport.write("TRIGger:A:MODE AUTO")
                recovery_confirmed = (
                    _scope_trigger_mode(recovery_transport.query("TRIGger:A:MODE?"))
                    == _SCOPE_INITIAL_TRIGGER_MODE
                )
                if recovery_confirmed:
                    scope_mode_auto_restored = True
                    scope = evidence["scope_observation"]
                    assert isinstance(scope, dict)
                    scope["trigger_mode_restored"] = _SCOPE_INITIAL_TRIGGER_MODE
                    scope["trigger_mode_restore_session"] = "recovery"
                else:
                    failures.append("scope_trigger_mode_auto_recovery_unverified")
            except Exception:
                failures.append("scope_trigger_mode_auto_recovery_failed")
            finally:
                if recovery_driver is not None:
                    before_close, after_close, close_error = _close_and_audit(
                        recovery_driver,
                        recovery_transport,
                    )
                    scope_audit = evidence["scope_audit"]
                    assert isinstance(scope_audit, dict)
                    scope_audit["recovery"] = {
                        "before_close": before_close,
                        "after_close": after_close,
                    }
                    if close_error is not None:
                        failures.append(f"scope_recovery_{close_error}")
                    failures.extend(
                        _audit_failure_codes(
                            before_close,
                            after_close,
                            prefix="scope_recovery",
                            expected_queries=1 if recovery_confirmed else None,
                            expected_writes=1 if recovery_confirmed else None,
                        )
                    )

        if rf_driver is not None:
            recovery_service: RfSourceService | None = None
            recovery_driver: object | None = None
            recovery_transport: object | None = None
            recovery_disable_completed: bool | None = None
            try:
                recovery_service, recovery_driver, recovery_transport = _open_rf_service(
                    _rf_write_config(rf_config),
                    preflight,
                    operation="dsg830.a5_pulse_output_recovery",
                    opener=opener,
                )
                if pulse_output_enable_attempted and not primary_pulse_output_disable_confirmed:
                    result, artifact = recovery_service.set_pulse_output_with_artifact(
                        RfPulseOutputRequest(
                            port_id=setup.port_id,
                            interface_id=setup.interface_id,
                            enabled=False,
                        )
                    )
                    evidence["recovery_pulse_output_disable"] = artifact
                    if result.enabled is not False:
                        failures.append("recovery_pulse_output_disable_unverified")
                    else:
                        recovery_disable_completed = result.write_completed

                final_snapshot = recovery_service.snapshot()
                evidence["final_snapshot"] = rf_source_snapshot_operation_artifact(final_snapshot)
                final_snapshot_failures = _snapshot_failure_codes(final_snapshot, phase="final")
                failures.extend(final_snapshot_failures)
                final_pulse_output = recovery_driver.get_rf_pulse_output_snapshot(
                    setup.port_id,
                    setup.interface_id,
                )
                evidence["final_pulse_output_snapshot"] = rf_pulse_output_snapshot_document(
                    final_pulse_output
                )
                final_pulse_output_failures = _pulse_output_failure_codes(
                    final_pulse_output,
                    phase="final",
                    require_profile=pulse_configure_confirmed,
                )
                failures.extend(final_pulse_output_failures)
                final_rf_output_off_confirmed = not final_snapshot_failures
                final_pulse_output_off_confirmed = not final_pulse_output_failures
                final_baseline_confirmed = (
                    final_rf_output_off_confirmed and final_pulse_output_off_confirmed
                )
            except Exception:
                failures.append("final_rf_or_pulse_output_readback_failed")
            finally:
                if recovery_driver is not None:
                    before_close, after_close, close_error = _close_and_audit(
                        recovery_driver,
                        recovery_transport,
                    )
                    rf_audit = evidence["rf_audit"]
                    assert isinstance(rf_audit, dict)
                    rf_audit["recovery"] = {
                        "before_close": before_close,
                        "after_close": after_close,
                    }
                    if close_error is not None:
                        failures.append(f"rf_recovery_{close_error}")
                    if final_baseline_confirmed:
                        if recovery_disable_completed is True:
                            expected_queries = _RF_RECOVERY_DISABLE_AND_VERIFY_QUERY_COUNT
                            expected_writes = _RF_RECOVERY_DISABLE_AND_VERIFY_WRITE_COUNT
                        elif recovery_disable_completed is False:
                            expected_queries = (
                                _PULSE_OUTPUT_SNAPSHOT_QUERY_COUNT
                                + _SNAPSHOT_QUERY_COUNT
                                + _PULSE_OUTPUT_SNAPSHOT_QUERY_COUNT
                            )
                            expected_writes = 0
                        else:
                            expected_queries = _RF_FINAL_VERIFICATION_QUERY_COUNT
                            expected_writes = 0
                    else:
                        expected_queries = None
                        expected_writes = None
                    failures.extend(
                        _audit_failure_codes(
                            before_close,
                            after_close,
                            prefix="rf_recovery",
                            expected_queries=expected_queries,
                            expected_writes=expected_writes,
                        )
                    )

    if not final_pulse_output_off_confirmed:
        failures.append("final_pulse_output_off_not_confirmed")
    if not final_rf_output_off_confirmed:
        failures.append("final_rf_off_not_confirmed")
    if not final_baseline_confirmed:
        failures.append("final_baseline_not_confirmed")
    if scope_mode_normal_attempted and not scope_mode_auto_restored:
        failures.append("final_scope_trigger_mode_auto_not_confirmed")
    if not _runtime_versions_available(evidence["runtime"]):
        failures.append("runtime_version_unavailable")
    evidence["failure_codes"] = sorted(set(failures))
    evidence["status"] = "passed" if not evidence["failure_codes"] else "failed"
    return evidence


def _open_evidence_output(path: Path) -> TextIO:
    if not path.parent.is_dir():
        raise A5PulseOutputPreflightError("invalid_evidence_output_path")
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise A5PulseOutputPreflightError("invalid_evidence_output_path") from exc
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
            "schema": A5_PULSE_OUTPUT_EVIDENCE_SCHEMA,
            "status": evidence["status"],
            "failure_codes": evidence["failure_codes"],
            "scope_single_completed": (
                scope.get("single_completed") if isinstance(scope, Mapping) else None
            ),
            "pulse_output_confirmed_off": evidence["status"] == "passed",
            "rf_output_confirmed_off": evidence["status"] == "passed",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rf-config", required=True, type=Path, help="Private read-only RF TOML")
    parser.add_argument("--scope-config", required=True, type=Path, help="Private read-only scope TOML")
    parser.add_argument("--setup", required=True, type=Path, help="Private A5 setup without resources")
    parser.add_argument("--output", type=Path, help="New local JSON evidence file")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Explicitly permit the fixed Pulse-output and scope single-acquisition transaction",
    )
    args = parser.parse_args(argv)
    try:
        rf_config = load_config(args.rf_config)
        scope_config = load_config(args.scope_config)
        setup = load_a5_pulse_output_evidence_setup(args.setup)
        preflight = validate_a5_pulse_output_preflight(rf_config, scope_config, setup)
    except A5PulseOutputPreflightError as exc:
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        print(json.dumps({"status": "preflight_failed", "failure_code": "config_or_descriptor_invalid"}))
        return 2

    if not args.execute:
        print(
            json.dumps(
                {
                    "schema": A5_PULSE_OUTPUT_EVIDENCE_SCHEMA,
                    "status": "dry_run_ok",
                    "driver_id": preflight.production_descriptor.driver_id,
                    "production_capabilities": list(preflight.production_descriptor.capabilities),
                    "will_connect": False,
                    "will_write": False,
                    "will_enable_rf_output": False,
                    "will_use_trigger_in": False,
                    "will_arm_or_fire_sweep": False,
                    "will_toggle_pulse_output": False,
                    "will_change_scope_trigger_mode": False,
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
            {"schema": A5_PULSE_OUTPUT_EVIDENCE_SCHEMA, "evidence": "A5_PULSE_OUTPUT", "status": "started"},
        )
    except A5PulseOutputPreflightError as exc:
        if output is not None:
            output.close()
        print(json.dumps({"status": "preflight_failed", "failure_code": exc.code}))
        return 2
    except Exception:
        if output is not None:
            output.close()
        print(json.dumps({"status": "preflight_failed", "failure_code": "local_output_invalid"}))
        return 2

    try:
        try:
            evidence = collect_a5_pulse_output_evidence(
                rf_config,
                scope_config,
                preflight,
                setup,
            )
        except A5PulseOutputPreflightError as exc:
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
