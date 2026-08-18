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
    assert assessment["milestones"] == {
        "plugin": "M8-complete",
        "rfc": "R1-draft-needs-revision",
        "core_implementation": "not-started",
    }


def test_p0_foundations_define_replay_and_shared_session_contracts() -> None:
    assessment = _assessment()
    foundations = {item["id"]: item for item in assessment["p0_foundations"]}

    assert set(foundations) == {
        "transport-replay-contract",
        "shared-session-health-and-poison",
    }
    replay = foundations["transport-replay-contract"]
    assert replay["priority"] == "P0"
    assert set(replay["replay_policies"]) == {
        "safe_to_replay",
        "no_replay",
        "read_continuation_only",
    }
    assert "PyVISA" in replay["minimum_behavior"]["backends"]
    assert "GuardedAuditedTransport" in replay["minimum_behavior"]["backends"]
    assert any("at most one" in item for item in replay["acceptance"])

    session = foundations["shared-session-health-and-poison"]
    assert set(session["states"]) == {"healthy", "uncertain", "poisoned", "closed"}
    assert "on_failure=continue" in " ".join(session["acceptance"])
    assert session["responsibility"]["core"]
    assert session["responsibility"]["plugin"]
    assert session["responsibility"]["transport"]


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
    assert proposals["scope-read-only-state"]["public_contract"]["field_metadata"]
    assert proposals["scope-read-only-state"]["public_contract"]["termination"] == "read-only in the first version"

    run_state = proposals["scope-acquisition-run-state"]
    assert run_state["capabilities"] == ["scope.acquisition_run_state"]
    assert len(run_state["vendors"]) >= 2

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
        "typed-state-and-patch",
        "service-cli-run-plan",
        "hardware-acceptance",
    } <= set(layers)
    assert layers["hardware-acceptance"]["hardware_required"] is True
    assert layers["transport-contract"]["hardware_required"] is False
