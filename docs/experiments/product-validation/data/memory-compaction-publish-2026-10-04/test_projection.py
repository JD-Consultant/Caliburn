"""Public evidence must not expose private reasoning or mutate native context."""

from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID

from analyze import document
from experiment import public_document


def test_nested_native_items_remain_private_and_unchanged():
    original = {
        "output": [
            {
                "type": "reasoning",
                "encrypted_content": "private",
                "content": ["raw"],
                "summary": ["visible"],
            },
            {"type": "compaction", "encrypted_content": "private"},
        ]
    }
    before = deepcopy(original)
    projected = public_document(original)
    assert original == before
    assert "content" not in projected["output"][0]
    assert projected["output"][0]["summary"] == ["visible"]
    assert "encrypted_content" not in str(projected)
    assert "private" not in str(projected)
    assert "raw" not in str(projected)
    assert projected["output"][1]["encrypted_length"] == 7


def test_fixed_reference_sets_are_structured_without_string_repr():
    @dataclass(frozen=True)
    class Reference:
        object_id: UUID
        revision_id: UUID

    reference = Reference(UUID(int=1), UUID(int=2))
    assert document(frozenset([reference])) == [
        {"object_id": str(UUID(int=1)), "revision_id": str(UUID(int=2))}
    ]
