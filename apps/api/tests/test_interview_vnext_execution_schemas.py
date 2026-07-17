from __future__ import annotations

import json

from app.interview_vnext.application.schema_exports import (
    SCHEMA_EXPORTS as APPLICATION_SCHEMA_EXPORTS,
    published_schema as published_application_schema,
)
from app.interview_vnext.application.write_schemas import (
    SCHEMA_DIR as APPLICATION_SCHEMA_DIR,
)
from app.interview_vnext.llm.schema_exports import (
    SCHEMA_EXPORTS as LLM_SCHEMA_EXPORTS,
    published_schema as published_llm_schema,
)
from app.interview_vnext.llm.context import (
    CONTEXT_POLICIES,
    context_policy_filename,
)
from app.interview_vnext.llm.write_context_policies import POLICY_DIR
from app.interview_vnext.llm.write_schemas import SCHEMA_DIR as LLM_SCHEMA_DIR
from app.interview_vnext.observability.schema_exports import (
    SCHEMA_EXPORTS as CAPTURE_SCHEMA_EXPORTS,
    published_schema as published_capture_schema,
)
from app.interview_vnext.observability.write_schemas import SCHEMA_DIR as CAPTURE_SCHEMA_DIR
from app.interview_vnext.observability.taxonomy import EXECUTION_TAXONOMIES
from app.interview_vnext.observability.write_taxonomies import (
    TAXONOMY_DIR,
    taxonomy_filename,
)


def test_committed_application_llm_and_capture_schemas_match_contracts():
    groups = (
        (
            APPLICATION_SCHEMA_DIR,
            APPLICATION_SCHEMA_EXPORTS,
            published_application_schema,
        ),
        (LLM_SCHEMA_DIR, LLM_SCHEMA_EXPORTS, published_llm_schema),
        (CAPTURE_SCHEMA_DIR, CAPTURE_SCHEMA_EXPORTS, published_capture_schema),
    )
    for directory, exports, publisher in groups:
        assert {path.name for path in directory.glob("*.json")} == set(exports)
        for filename in exports:
            committed = json.loads((directory / filename).read_text(encoding="utf-8"))
            assert committed == publisher(filename)
            assert committed["$id"] == f"https://caliburn.local/schemas/{filename}"
            if committed.get("type") == "object":
                assert committed["additionalProperties"] is False
            for definition in committed.get("$defs", {}).values():
                if definition.get("type") == "object":
                    assert definition["additionalProperties"] is False


def test_committed_context_policies_match_hash_addressed_registry():
    expected_names = {
        context_policy_filename(name, version)
        for name, version in CONTEXT_POLICIES
    }
    assert {path.name for path in POLICY_DIR.glob("*.json")} == expected_names
    for (name, version), policy in CONTEXT_POLICIES.items():
        path = POLICY_DIR / context_policy_filename(name, version)
        assert json.loads(path.read_text(encoding="utf-8")) == policy.model_dump(
            mode="json"
        )
        assert policy.policy_hash.startswith("sha256:")


def test_committed_execution_taxonomies_match_versioned_registry():
    expected_names = {
        taxonomy_filename(taxonomy_id, version)
        for taxonomy_id, version in EXECUTION_TAXONOMIES
    }
    assert {path.name for path in TAXONOMY_DIR.glob("*.json")} == expected_names
    for (taxonomy_id, version), taxonomy in EXECUTION_TAXONOMIES.items():
        path = TAXONOMY_DIR / taxonomy_filename(taxonomy_id, version)
        assert json.loads(path.read_text(encoding="utf-8")) == taxonomy.model_dump(mode="json")
        assert taxonomy.content_hash.startswith("sha256:")
        assert "model.call.completed" in taxonomy.event_types
        assert "turn.interpret" in taxonomy.stages
