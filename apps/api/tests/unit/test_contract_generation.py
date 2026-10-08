"""Generation resolves one canonical contract root without enabling remote references."""

import importlib.util
import json
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[2] / "scripts/generate_contracts.py"
SPEC = importlib.util.spec_from_file_location("caliburn_contract_generator", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
GENERATOR = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(GENERATOR)


def test_generation_stages_shared_body_ref_and_preserves_canonical_source(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    (root / "http").mkdir(parents=True)
    (root / "tools").mkdir()
    body = root / "tools/body.schema.json"
    view = root / "http/view.schema.json"
    body.write_text('{"properties":{"plan":{"type":["string","null"]}}}', encoding="utf-8")
    original = '{"$ref":"../tools/body.schema.json#/properties/plan"}'
    view.write_text(original, encoding="utf-8")
    staged = GENERATOR.stage_contract_schemas(
        [body, view], tmp_path / "staged", contracts_root=root
    )
    assert json.loads(staged[view].read_text(encoding="utf-8")) == {
        "$ref": "body.schema.json#/properties/plan"
    }
    assert view.read_text(encoding="utf-8") == original


@pytest.mark.parametrize("reference", ["https://example.com/body.json", "../../private.json"])
def test_generation_rejects_remote_and_outside_contract_references(
    tmp_path: Path, reference: str
) -> None:
    root = tmp_path / "contracts"
    root.mkdir()
    schema = root / "view.schema.json"
    schema.write_text(json.dumps({"$ref": reference}), encoding="utf-8")
    with pytest.raises(ValueError):
        GENERATOR.stage_contract_schemas([schema], tmp_path / "staged", contracts_root=root)


def test_generation_rejects_same_filename_collision_between_families(tmp_path: Path) -> None:
    root = tmp_path / "contracts"
    http = root / "http/body.schema.json"
    tool = root / "tools/body.schema.json"
    for path in (http, tool):
        path.parent.mkdir(parents=True)
        path.write_text('{"type":"string"}', encoding="utf-8")
    with pytest.raises(ValueError, match="unique filenames"):
        GENERATOR.stage_contract_schemas([http, tool], tmp_path / "staged", contracts_root=root)
