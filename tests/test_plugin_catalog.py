from __future__ import annotations

import importlib.util
import re
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "generate_plugin_catalog.py"
SPEC = importlib.util.spec_from_file_location("wavebench_plugin_catalog", SCRIPT)
assert SPEC and SPEC.loader
CATALOG = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = CATALOG
SPEC.loader.exec_module(CATALOG)


def test_catalog_tracks_all_packages_and_entry_points():
    records = CATALOG.discover_records(ROOT)

    assert len({record.distribution for record in records}) == 11
    assert len(records) == 13
    assert [record.driver_id for record in records if record.distribution == "wavebench-rigol-dg4000"] == [
        "rigol.dg4202",
        "rigol.dg4202-v2",
        "rigol.dg4202-v2-workspace",
    ]


def test_catalog_uses_current_dsg830_and_sdg2000x_capabilities():
    records = {record.driver_id: record for record in CATALOG.discover_records(ROOT)}

    assert len(records["rigol.dsg830"].capabilities) == 10
    assert "rf_source.modulated_output_enable" in records["rigol.dsg830"].capabilities
    assert "rf_source.pulse_output" in records["rigol.dsg830"].capabilities
    assert len(records["siglent.sdg2000x"].capabilities) == 12
    assert "source.harmonics_disable_v2" in records["siglent.sdg2000x"].capabilities


def test_check_mode_detects_missing_or_changed_output(tmp_path):
    rendered = {"zh": "中文\n", "en": "English\n"}

    with pytest.raises(CATALOG.CatalogError, match="stale"):
        CATALOG.write_outputs(tmp_path, rendered, check=True)

    CATALOG.write_outputs(tmp_path, rendered, check=False)
    CATALOG.write_outputs(tmp_path, rendered, check=True)
    (tmp_path / CATALOG.OUTPUTS["en"]).write_text("changed\n", encoding="utf-8")

    with pytest.raises(CATALOG.CatalogError, match="plugin-catalog-en.md"):
        CATALOG.write_outputs(tmp_path, rendered, check=True)


@pytest.mark.parametrize(
    ("driver_id", "relative_paths"),
    (
        (
            "rigol.dsg830",
            (
                "packages/wavebench-rigol-dsg830/doc/reference.md",
                "packages/wavebench-rigol-dsg830/doc/reference-en.md",
            ),
        ),
        (
            "siglent.sdg2000x",
            (
                "packages/wavebench-siglent-sdg2000x/doc/SDG2000X_COVERAGE_MATRIX.md",
                "packages/wavebench-siglent-sdg2000x/doc/SDG2000X_COVERAGE_MATRIX_EN.md",
            ),
        ),
    ),
)
def test_pilot_references_match_descriptor_capabilities(driver_id, relative_paths):
    record = next(item for item in CATALOG.discover_records(ROOT) if item.driver_id == driver_id)

    for relative_path in relative_paths:
        body = (ROOT / relative_path).read_text(encoding="utf-8")
        documented = tuple(
            re.findall(r"^\| `((?:rf_source|source)\.[^`]+)` \|", body, re.MULTILINE)
        )
        assert documented == record.capabilities
        assert f"`{record.version}`" in body
