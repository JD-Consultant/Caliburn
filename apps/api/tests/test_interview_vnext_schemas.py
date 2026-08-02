from __future__ import annotations

import json
import hashlib
from pathlib import Path

from app.interview_vnext.domain.schema_exports import (
    HISTORICAL_SCHEMAS,
    SCHEMA_EXPORTS,
    published_schema,
)
from app.interview_vnext.domain.write_schemas import SCHEMA_DIR


def test_committed_vnext_schemas_match_pydantic_contracts():
    assert {path.name for path in SCHEMA_DIR.glob("*.json")} == (
        set(SCHEMA_EXPORTS) | HISTORICAL_SCHEMAS
    )
    for filename in SCHEMA_EXPORTS:
        committed = SCHEMA_DIR / filename
        assert json.loads(committed.read_text(encoding="utf-8")) == published_schema(filename)


def test_historical_vnext_schemas_are_frozen_bytes():
    expected = {
        "append-transcript-turn-command.v1.schema.json": "ce01319377cd49f3a38e7ef7d2c06e4883b86c8dd245283c421e0b40dff287aa",
        "apply-evidence-command.v2.schema.json": "c69b21d7efc7610800576c0303a3062d9a6f196942b8b23f71ccc882717d0512",
        "domain-event.v1.schema.json": "699fc206eb96f42259d106229765054533622eb025ca67e6660853a44db8fa5f",
        "evidence.v2.schema.json": "888c80f0fb4c7f3dcbede00560bc7744d50d843115c8b13d6b91f48f43e76c83",
        "interview-state.v2.schema.json": "15fedcf6421528ef7116eeec7b5caad0bac458c497e8c51be01453ab371a735c",
        "reduction-result.v1.schema.json": "1e9115e95271e7a601b288731328e7c092efc95bf41ee7262b872fa117e246ef",
    }
    assert set(expected) == HISTORICAL_SCHEMAS
    for filename, digest in expected.items():
        assert hashlib.sha256((SCHEMA_DIR / filename).read_bytes()).hexdigest() == digest


def test_published_schemas_have_stable_ids_and_forbid_unknown_fields():
    for filename in SCHEMA_EXPORTS:
        schema = json.loads((SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        assert schema["$id"] == f"https://caliburn.local/schemas/{filename}"
        if schema.get("type") == "object":
            assert schema["additionalProperties"] is False
