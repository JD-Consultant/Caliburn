"""官方 SDK 壓縮原件經 Core serializer 往返，保留未知欄位及 unset 語意。"""

import warnings
from typing import Any, cast
from uuid import UUID

from langgraph.types import StateSnapshot
from openai.types.responses import CompactedResponse

from caliburn.modules.agent.agent import _prepare_new_turn_input
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    openai_checkpoint_serializer,
)
from tests.unit.bundles.context.support import compacted_payload


def test_new_turn_clears_previous_compaction_response() -> None:
    response = CompactedResponse.model_construct(
        **cast(dict[str, Any], compacted_payload())
    )
    previous = StateSnapshot(
        values={"turn_completed": True, "compaction_response": response},
        next=(),
        config={},
        metadata=None,
        created_at=None,
        parent_config=None,
        tasks=(),
        interrupts=(),
    )

    prepared = _prepare_new_turn_input(
        previous, workspace_id=UUID(int=1), turn_id=UUID(int=102), input="next"
    )

    assert "compaction_response" in prepared
    assert prepared["compaction_response"] is None


def test_compacted_response_roundtrip_preserves_envelope_and_sdk_fields() -> None:
    payload = compacted_payload()
    payload["output"] = [cast(list[dict[str, object]], payload["output"])[1]]
    response = CompactedResponse.model_construct(**cast(dict[str, Any], payload))
    serializer = openai_checkpoint_serializer()

    restored = serializer.loads_typed(serializer.dumps_typed(response))

    assert isinstance(restored, CompactedResponse)
    assert restored.id == "cmp_offline"
    assert restored.created_at == 1793491200
    assert restored.usage.total_tokens == 128020
    assert restored.model_extra == {"future_response_field": {"retained": True}}
    assert restored.model_fields_set == {
        "id",
        "created_at",
        "object",
        "output",
        "usage",
    }
    assert restored.output[0].model_fields_set == {
        "id",
        "type",
        "encrypted_content",
        "future_compaction_field",
    }
    assert restored.model_dump(exclude_unset=True) == payload


def test_compacted_user_item_roundtrip_does_not_log_original_text() -> None:
    payload = compacted_payload()
    response = CompactedResponse.model_construct(**cast(dict[str, Any], payload))
    serializer = openai_checkpoint_serializer()

    with warnings.catch_warnings(record=True) as observed:
        warnings.simplefilter("always")
        restored = serializer.loads_typed(
            serializer.dumps_typed({"prepared": response})
        )

    assert observed == []
    compacted = restored["prepared"]
    assert isinstance(compacted, CompactedResponse)
    assert compacted.model_dump(exclude_unset=True, warnings=False) == payload
    user = compacted.output[0]
    assert user.type == "message"
    assert user.model_fields_set == {"id", "type", "role", "status", "content"}
    assert user.content[0].model_fields_set == {"type", "text"}


def test_compaction_explicit_null_and_unset_survive_as_distinct_values() -> None:
    payload = compacted_payload()
    user = cast(list[dict[str, object]], payload["output"])[0]
    user["phase"] = None
    response = CompactedResponse.model_construct(**cast(dict[str, Any], payload))
    serializer = openai_checkpoint_serializer()

    restored = serializer.loads_typed(serializer.dumps_typed([response]))[0]

    assert isinstance(restored, CompactedResponse)
    assert restored.output[0].type == "message"
    assert "phase" in restored.output[0].model_fields_set
    assert "annotations" not in restored.output[0].content[0].model_fields_set
    assert restored.model_dump(exclude_unset=True, warnings=False) == payload
