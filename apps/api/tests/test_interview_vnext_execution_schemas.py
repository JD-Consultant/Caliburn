from __future__ import annotations

import json
from hashlib import sha256

import pytest

from app.interview_vnext.application.schema_exports import (
    SCHEMA_EXPORTS as APPLICATION_SCHEMA_EXPORTS,
    published_schema as published_application_schema,
)
from app.interview_vnext.application.write_schemas import (
    SCHEMA_DIR as APPLICATION_SCHEMA_DIR,
)
from app.interview_vnext.llm.schema_exports import (
    HISTORICAL_SCHEMAS as LLM_HISTORICAL_SCHEMAS,
    SCHEMA_EXPORTS as LLM_SCHEMA_EXPORTS,
    published_schema as published_llm_schema,
)
from app.interview_vnext.llm.context import (
    CONTEXT_POLICIES,
    context_policy_filename,
)
from app.interview_vnext.llm.operation_documents import (
    OPERATION_DIR,
    TURN_INTERPRET_PROMPT_PATH,
    operation_documents,
    raw_text_hash,
)
from app.interview_vnext.llm.portable_schema import (
    ProviderSchemaPortabilityError,
    assert_portable_strict_output_schema,
)
from app.interview_vnext.llm.turn_interpret import (
    TURN_INTERPRET_VERIFIER_POLICY_V2,
)
from app.interview_vnext.llm.write_context_policies import POLICY_DIR
from app.interview_vnext.llm.write_schemas import SCHEMA_DIR as LLM_SCHEMA_DIR
from app.interview_vnext.llm.write_verifier_policies import (
    POLICY_DIR as VERIFIER_POLICY_DIR,
)
from app.interview_vnext.observability.schema_exports import (
    HISTORICAL_SCHEMAS as CAPTURE_HISTORICAL_SCHEMAS,
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
            frozenset(),
        ),
        (LLM_SCHEMA_DIR, LLM_SCHEMA_EXPORTS, published_llm_schema, LLM_HISTORICAL_SCHEMAS),
        (
            CAPTURE_SCHEMA_DIR,
            CAPTURE_SCHEMA_EXPORTS,
            published_capture_schema,
            CAPTURE_HISTORICAL_SCHEMAS,
        ),
    )
    for directory, exports, publisher, historical in groups:
        # active exports are regenerated from models; historical files stay frozen
        assert {path.name for path in directory.glob("*.json")} == set(exports) | historical
        for filename in exports:
            committed = json.loads((directory / filename).read_text(encoding="utf-8"))
            assert committed == publisher(filename)
            assert committed["$id"] == f"https://caliburn.local/schemas/{filename}"
            if committed.get("type") == "object":
                assert committed["additionalProperties"] is False
            for definition in committed.get("$defs", {}).values():
                if definition.get("type") == "object":
                    assert definition["additionalProperties"] is False


def test_historical_llm_schemas_stay_present_and_frozen():
    """v1 request/result schemas are superseded but never deleted (plan §4.1)."""

    for filename in LLM_HISTORICAL_SCHEMAS:
        committed = json.loads((LLM_SCHEMA_DIR / filename).read_text(encoding="utf-8"))
        assert committed["$id"] == f"https://caliburn.local/schemas/{filename}"
        # the historical file is not regenerated: its schema_version stays v1
        assert filename not in LLM_SCHEMA_EXPORTS


def test_committed_context_policies_match_hash_addressed_registry():
    expected_names = {
        context_policy_filename(name, version)
        for name, version in CONTEXT_POLICIES
    }
    historical_name = "turn-interpret.1.0.0.json"
    assert {path.name for path in POLICY_DIR.glob("*.json")} == expected_names | {
        historical_name
    }
    for (name, version), policy in CONTEXT_POLICIES.items():
        path = POLICY_DIR / context_policy_filename(name, version)
        assert json.loads(path.read_text(encoding="utf-8")) == policy.model_dump(
            mode="json"
        )
        assert policy.policy_hash.startswith("sha256:")
    assert sha256((POLICY_DIR / historical_name).read_bytes()).hexdigest() == (
        "d6e34a228ab562fe41179daa3923fca6db9634b4b00fbac5a1b03593afce9619"
    )


def test_turn_output_schema_is_in_the_strict_provider_portable_subset():
    schema = published_llm_schema("turn-interpret-output.v2.schema.json")
    assert_portable_strict_output_schema(schema)
    encoded = json.dumps(schema, ensure_ascii=False)
    for forbidden in (
        '"default"',
        '"format"',
        '"maximum"',
        '"maxLength"',
        '"minimum"',
        '"minLength"',
        '"pattern"',
    ):
        assert forbidden not in encoded

    invalid = {
        "type": "object",
        "properties": {"value": {"type": "string"}},
        "required": [],
        "additionalProperties": False,
    }
    with pytest.raises(ProviderSchemaPortabilityError, match="every property"):
        assert_portable_strict_output_schema(invalid)


def test_committed_turn_verifier_policy_matches_hash_addressed_contract():
    paths = {path.name: path for path in VERIFIER_POLICY_DIR.glob("*.json")}
    assert set(paths) == {
        "turn-interpret-verifier.1.0.0.json",
        "turn-interpret-verifier.2.0.0.json",
    }

    # v1 is frozen history, not a second active runtime contract.
    historical_bytes = paths["turn-interpret-verifier.1.0.0.json"].read_bytes()
    assert sha256(historical_bytes).hexdigest() == (
        "71abe648c9c8bc9112c5c01cc0f1393af58da1e88ce57307370e2eead5b5eebb"
    )

    active = json.loads(
        paths["turn-interpret-verifier.2.0.0.json"].read_text(encoding="utf-8")
    )
    assert active == TURN_INTERPRET_VERIFIER_POLICY_V2.model_dump(mode="json")
    assert TURN_INTERPRET_VERIFIER_POLICY_V2.policy_hash.startswith("sha256:")


def test_committed_operation_document_and_prompt_match_current_contracts():
    expected = operation_documents()
    historical_operation = "turn-interpret.1.0.0.json"
    assert {path.name for path in OPERATION_DIR.glob("*.json")} == set(expected) | {
        historical_operation
    }
    for filename, operation in expected.items():
        committed = json.loads((OPERATION_DIR / filename).read_text(encoding="utf-8"))
        assert committed == operation.model_dump(mode="json")
        assert operation.definition_hash.startswith("sha256:")
    prompt = TURN_INTERPRET_PROMPT_PATH.read_text(encoding="utf-8")
    assert expected["turn-interpret.2.0.0.json"].prompt_template.content_hash == (
        raw_text_hash(prompt)
    )
    folded = prompt.casefold()
    for forbidden in ("o*net", "ocs", "職務說明書", "chain-of-thought"):
        assert forbidden not in folded
    assert sha256((OPERATION_DIR / historical_operation).read_bytes()).hexdigest() == (
        "0eed5920a97f746e7696ea07d3633e4c6f638166b884ee17bb80f4db162d17e2"
    )
    historical_prompt = TURN_INTERPRET_PROMPT_PATH.with_name("turn-interpret.1.0.0.md")
    assert sha256(historical_prompt.read_bytes()).hexdigest() == (
        "2f8214d02ec3d75a940922e4c1d4b929d7f7180f821bc9ac2f086ca0d79eb42f"
    )


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
