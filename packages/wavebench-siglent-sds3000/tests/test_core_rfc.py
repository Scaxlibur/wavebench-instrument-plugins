from __future__ import annotations

import json
from pathlib import Path


PACKAGE_ROOT = Path(__file__).resolve().parents[1]
RFC_PATH = PACKAGE_ROOT / "doc" / "wavebench-core-rfc.json"


def test_each_core_proposal_is_additive_and_cross_vendor() -> None:
    assessment = json.loads(RFC_PATH.read_text(encoding="utf-8"))

    assert assessment["schema_version"] == 1
    assert assessment["wavebench_baseline"] == "0.8.22"
    assert assessment["core_changed_by_this_plugin"] is False
    assert assessment["decision"] == "assessment-only"

    proposals = assessment["proposals"]
    assert {proposal["id"] for proposal in proposals} == {
        "scope-configuration-state-and-patch",
        "scope-partial-status-v2",
    }
    forbidden_vendor_tokens = ("siglent", "lecroy", "rigol", "rohde", "sds", "rtm")
    for proposal in proposals:
        assert proposal["compatibility"] == "additive"
        manufacturers = {vendor["manufacturer"] for vendor in proposal["vendors"]}
        assert len(manufacturers) >= 2
        assert all(vendor["drivers"] and vendor["evidence"] for vendor in proposal["vendors"])
        assert proposal["capabilities"]
        for capability in proposal["capabilities"]:
            assert capability.startswith("scope.")
            assert not any(token in capability.lower() for token in forbidden_vendor_tokens)


def test_core_assessment_rejects_arbitrary_command_surfaces() -> None:
    assessment = json.loads(RFC_PATH.read_text(encoding="utf-8"))
    decisions = {
        item["id"]: item["decision"] for item in assessment["rejected_or_deferred"]
    }

    assert decisions["arbitrary-raw-scpi-or-vbs"] == "rejected"
    assert decisions["sds3000-vicp-core-backend"] == "not-needed"
    assert decisions["raw-screenshot-transport-for-sds3000"] == "not-justified"
    assert decisions["mutate-v1-status-models-in-place"] == "rejected"
    assert decisions["dynamic-descriptor-instrument-probing"] == "rejected"
