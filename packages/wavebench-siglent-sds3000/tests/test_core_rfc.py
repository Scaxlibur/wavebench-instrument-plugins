from __future__ import annotations

import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RFC_PATH = PACKAGE_ROOT / "doc" / "wavebench-core-rfc.json"


def _assessment() -> dict[str, object]:
    return json.loads(RFC_PATH.read_text(encoding="utf-8"))


def test_rfc_is_explicitly_a_draft_and_milestones_are_aligned() -> None:
    assessment = _assessment()

    assert assessment["schema_version"] == 2
    assert assessment["document_kind"] == "wavebench-core-rfc"
    assert assessment["status"] == "draft-needs-revision"
    assert assessment["revision"] == "R1"
    assert assessment["wavebench_baseline"] == "0.8.22"
    assert assessment["core_changed_by_this_plugin"] is False
    assert assessment["decision"] == "assessment-only"
    assert assessment["core_contract_reference"] == {
        "document": "WaveBench_transport重放与session健康RFC.md",
        "revision": "R1",
        "status": "accepted",
        "implementation": "M1-M7-implemented-unreleased",
        "release_required_for_plugin_adoption": True,
    }
    assert assessment["milestones"] == {
        "plugin": "M8-functional-complete",
        "p0_safety_hardening": "pending",
        "rfc": "R1-draft-needs-revision",
        "core_implementation": "M1-M7-implemented-unreleased",
        "plugin_adoption": "blocked-until-core-release",
    }
    assert assessment["scope"]["p0_safety_hardening_pending"] is True


def test_p0_foundations_define_replay_and_shared_session_contracts() -> None:
    assessment = _assessment()
    foundations = {item["id"]: item for item in assessment["p0_foundations"]}

    assert set(foundations) == {
        "transport-replay-contract",
        "shared-session-health-and-poison",
    }
    replay = foundations["transport-replay-contract"]
    assert replay["priority"] == "P0"
    assert replay["status"] == "implemented-unreleased"
    assert set(replay["replay_policies"]) == {
        "safe_to_replay",
        "no_replay",
        "read_continuation_only",
    }
    assert "PyVISA" in replay["minimum_behavior"]["backends"]
    assert "GuardedAuditedTransport" in replay["minimum_behavior"]["backends"]
    assert "no_replay" in replay["minimum_behavior"]["legacy_query_default"]
    assert "fail closed" in replay["minimum_behavior"]["unsupported_continuation"]
    assert any("at most one" in item for item in replay["acceptance"])

    session = foundations["shared-session-health-and-poison"]
    assert session["status"] == "implemented-unreleased"
    assert set(session["states"]) == {"healthy", "uncertain", "poisoned", "closed"}
    assert set(session["configuration_states"]) == {"verified", "unverified"}
    assert "unverified" in session["transitions"]["new_or_reconnected_session"]
    unknown_write = session["transitions"]["write_result_unknown"]
    assert unknown_write["communication_synchronized"] == {
        "next_state": "uncertain",
        "allowed_instrument_io": [
            "authorized_bounded_recovery",
            "state_validation",
        ],
    }
    assert unknown_write["communication_desynchronized_or_unproven"] == {
        "next_state": "poisoned",
        "allowed_instrument_io": [],
    }
    assert "unrecoverable" in session["transitions"]["restore_failure"]
    assert "all later instrument operations" in " ".join(session["acceptance"])
    assert "restored" in " ".join(session["acceptance"])
    assert "on_failure=continue" in " ".join(session["acceptance"])
    assert session["responsibility"]["core"]
    assert session["responsibility"]["plugin"]
    assert session["responsibility"]["transport"]


def test_transport_spec_is_complete_and_typed_scope_spec_remains_required() -> None:
    assessment = _assessment()
    gates = {item["id"]: item for item in assessment["specification_freeze_gates"]}

    assert set(gates) == {
        "transport-replay-session-rfc",
        "typed-scope-state-rfc",
    }
    assert (
        gates["transport-replay-session-rfc"]["status"]
        == "completed-in-core-development-release-gated-for-plugin"
    )
    transport = " ".join(gates["transport-replay-session-rfc"]["must_define"])
    assert "default replay policy" in transport
    assert "legacy call-site migration" in transport
    assert "read_continuation_only" in transport
    session_contract = gates["transport-replay-session-rfc"]["session_contract_freeze"]
    assert set(session_contract) == {
        "health_owner",
        "recovery_authorization",
        "state_validation_scope",
    }
    assert "authoritative shared owner" in session_contract["health_owner"]
    assert "transaction coordinator" in session_contract["recovery_authorization"]
    assert "affected-field closure" in session_contract["state_validation_scope"]

    typed_scope = " ".join(gates["typed-scope-state-rfc"]["must_define"])
    assert "Protocol signatures" in typed_scope
    assert "Service/CLI/run-plan" in typed_scope
    assert "SDS3000, DS1000Z, and RTM2000" in typed_scope

    findings = {item["interface"]: item for item in assessment["existing_interface_findings"]}
    operation_spec = findings["OperationSpec.effect=acquire"]
    assert operation_spec["decision"] == "core-audit-complete-plugin-verification-pending"
    assert "core M7" in operation_spec["evidence"]


def test_active_proposals_are_typed_read_only_first_and_cross_vendor() -> None:
    assessment = _assessment()
    proposals = {item["id"]: item for item in assessment["proposals"]}

    assert set(proposals) == {
        "scope-read-only-state",
        "scope-acquisition-run-state",
        "scope-configuration-patch",
        "scope-partial-status-v2",
    }
    assert proposals["scope-read-only-state"]["priority"] == "P1"
    assert proposals["scope-read-only-state"]["status"] == "blocked-on-p0"
    state_contract = proposals["scope-read-only-state"]["public_contract"]
    assert state_contract["field_metadata"]
    assert state_contract["termination"] == "read-only in the first version"
    assert set(state_contract["availability"]) == {
        "unsupported",
        "supported_but_not_readable",
        "stale_or_unknown",
        "valid_value",
    }
    assert "query_failed" not in state_contract["availability"]
    assert "operation-error envelope" in state_contract["query_failure"]

    run_state = proposals["scope-acquisition-run-state"]
    assert run_state["status"] == "design-required"
    assert run_state["compatibility"] == "not-frozen"
    assert run_state["capabilities"] == []
    assert run_state["candidate_capability"] == "scope.acquisition_run_state"
    assert set(run_state["public_contract"]["candidate_axes"]) == {
        "execution_state",
        "trigger_phase",
        "trigger_mode",
    }
    assert len(run_state["vendors"]) == 3
    vendor_text = json.dumps(run_state["vendors"])
    assert "SEQ is firmware-unverified" in vendor_text
    assert "no read-only acquisition or trigger-status query" in vendor_text
    assert "STATUS:OPERation:CONDITION? bit 3" in vendor_text
    assert "all three vendors" in run_state["freeze_gate"]

    patch = proposals["scope-configuration-patch"]
    assert patch["priority"] == "P2"
    assert patch["status"] == "deferred-until-safety-contract"
    assert "termination" in patch["excluded_from_first_version"]
    assert "edge_trigger_configure" in patch["excluded_from_first_version"]

    snapshot = proposals["scope-partial-status-v2"]
    assert snapshot["status"] == "deferred"
    assert "ScopeStatusSummary" in snapshot["reason"]

    forbidden_vendor_tokens = ("siglent", "lecroy", "rigol", "rohde", "sds", "rtm")
    for proposal in proposals.values():
        capabilities = proposal["capabilities"]
        assert all(capability.startswith("scope.") for capability in capabilities)
        assert all(
            not any(token in capability.lower() for token in forbidden_vendor_tokens)
            for capability in capabilities
        )


def test_rfc_keeps_safety_rejections_and_test_layers_explicit() -> None:
    assessment = _assessment()
    decisions = {
        item["id"]: item["decision"] for item in assessment["deferred_or_rejected"]
    }

    assert decisions["termination-write"] == "deferred"
    assert decisions["scope-acquisition-status-v2"] == "deferred-and-split"
    assert decisions["arbitrary-raw-scpi-or-vbs"] == "rejected"
    assert decisions["sds3000-vicp-core-backend"] == "not-needed"
    assert decisions["raw-screenshot-transport-for-sds3000"] == "not-justified"
    assert decisions["mutate-v1-status-models-in-place"] == "rejected"
    assert decisions["dynamic-descriptor-instrument-probing"] == "rejected"

    layers = {item["layer"]: item for item in assessment["test_matrix"]}
    assert {
        "transport-contract",
        "session-transaction",
        "typed-read-only-state",
        "service-cli-run-plan",
        "plugin-version-gate",
        "hardware-acceptance",
    } <= set(layers)
    assert layers["hardware-acceptance"]["hardware_required"] is True
    assert layers["transport-contract"]["hardware_required"] is False

    typed_cases = layers["typed-read-only-state"]["required_cases"]
    assert "termination patch is rejected before I/O" in typed_cases
    assert "existing v1 behavior remains unchanged" in typed_cases
    assert all("v1 and v2" not in item for item in typed_cases)

    hardware_cases = layers["hardware-acceptance"]["required_cases"]
    assert "read-only state mappings on approved instruments" in hardware_cases
    assert all("termination" not in item for item in hardware_cases)

    future_scopes = {item["id"] for item in assessment["future_rfc_test_scopes"]}
    assert future_scopes == {
        "termination-write",
        "scope-partial-status-v2",
        "scope-configuration-patch",
    }

    session_cases = layers["session-transaction"]["required_cases"]
    assert any("proven communication synchronization enters uncertain" in item for item in session_cases)
    assert any("unproven communication enters poisoned" in item for item in session_cases)

    service_cases = layers["service-cli-run-plan"]["required_cases"]
    operation_audit = next(item for item in service_cases if "actual side effects" in item)
    for operation in (
        "scope.capture",
        "scope.capture_waveforms",
        "scope.capture_multiple",
        "scope.fetch_waveform",
    ):
        assert operation in operation_audit


def test_compatibility_contract_records_observable_behavior_changes() -> None:
    assessment = _assessment()
    compatibility = assessment["compatibility_contract"]

    assert "source-additive" in compatibility["source_api"]
    changes = " ".join(compatibility["observable_changes"])
    assert "no_replay" in changes
    assert "structured transport errors" in changes
    assert "on_failure=continue" in changes
    assert "legacy call-site migration inventory" in compatibility["required_controls"]


def test_release_gates_cover_wheel_descriptor_api_and_implementation_order() -> None:
    assessment = _assessment()
    gates = assessment["release_version_gates"]

    assert gates["current_plugin"] == {
        "wheel_requires_dist": "wavebench>=0.8.22,<0.9",
        "descriptor_wavebench_min_version": "0.8.22",
        "descriptor_wavebench_max_version": "0.9.0",
        "descriptor_api_version": "wavebench.instrument.v2",
    }
    assert gates["changed_by_r1"] is False
    adoption = " ".join(gates["p0_adoption"])
    assert "wheel and descriptor lower bounds move together" in adoption
    assert "new api_version" in adoption
    assert "before driver factory and transport I/O" in adoption
    adoption_checklist = gates["plugin_adoption_checklist"]
    assert any("TransportIOError" in item for item in adoption_checklist)
    assert any("zero secondary" in item for item in adoption_checklist)

    implementation_order = assessment["implementation_order"]
    operation_audit = next(item for item in implementation_order if "OperationSpec" in item)
    assert "core M7" in operation_audit
    for operation in (
        "scope.capture",
        "scope.capture_waveforms",
        "scope.capture_multiple",
        "scope.fetch_waveform",
    ):
        assert operation in operation_audit
    assert any("released P0 core" in item for item in implementation_order)
