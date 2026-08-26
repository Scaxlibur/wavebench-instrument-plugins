from __future__ import annotations

from pathlib import Path
import tomllib


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def test_package_metadata_declares_single_dsg830_instrument_entry_point() -> None:
    pyproject_path = PACKAGE_ROOT / "pyproject.toml"
    assert pyproject_path.is_file()

    with pyproject_path.open("rb") as file:
        pyproject = tomllib.load(file)

    assert pyproject["project"]["name"] == "wavebench-rigol-dsg830"
    assert pyproject["project"]["version"] == "0.2.0"
    assert pyproject["project"]["requires-python"] == ">=3.11"
    assert pyproject["project"]["dependencies"] == ["wavebench>=0.8.25,<0.9"]
    assert pyproject["project"]["entry-points"]["wavebench.instruments"] == {
        "rigol.dsg830": "wavebench_rigol_dsg830:descriptor"
    }
    assert pyproject["tool"]["hatch"]["build"]["targets"]["sdist"]["exclude"] == [
        "/doc/vendor-local"
    ]
