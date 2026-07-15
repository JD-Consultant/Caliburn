from __future__ import annotations

import json
from pathlib import Path

from app.interview_vnext.domain.schema_exports import SCHEMA_EXPORTS, published_schema
from app.interview_vnext.domain.write_schemas import SCHEMA_DIR


def test_committed_vnext_schemas_match_pydantic_contracts():
    assert {path.name for path in SCHEMA_DIR.glob("*.json")} == set(SCHEMA_EXPORTS)
    for filename in SCHEMA_EXPORTS:
        committed = SCHEMA_DIR / filename
        assert json.loads(committed.read_text(encoding="utf-8")) == published_schema(filename)


def test_published_schemas_have_stable_ids_and_forbid_unknown_fields():
    for filename in SCHEMA_EXPORTS:
        schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        assert schema["$id"] == f"https://caliburn.local/schemas/{filename}"
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
