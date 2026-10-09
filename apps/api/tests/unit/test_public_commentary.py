"""Only durable, complete assistant commentary may cross the public boundary."""

from dataclasses import asdict

from langgraph.checkpoint.memory import InMemorySaver

from caliburn.adapters.response_serialization import snapshot_response
from caliburn.agent_execution.public_messages import project_commentary, read_public_commentary
from tests.fixtures.response_loop import response_at


def test_projection_discards_reasoning_tools_annotations_final_and_incomplete_messages() -> None:
    response = response_at(1, tools=1)
    response.output[1].content[0].text = " 公開說明\n保留原樣 "
    response.output[1].content[0] = (
        response.output[1].content[0].model_copy(update={"private_metadata": "do-not-leak"})
    )
    assert [asdict(item) for item in project_commentary(response)] == [
        {"response_id": "response_1", "message_id": "message_1", "text": " 公開說明\n保留原樣 "}
    ]
    assert project_commentary(response_at(2, final=True)) == ()
    response.output[1].status = "in_progress"
    assert project_commentary(response) == ()


async def test_checkpoint_reader_recovers_order_deduplicates_and_ignores_compacted_input() -> None:
    from langgraph.checkpoint.base import empty_checkpoint

    saver = InMemorySaver()
    config = {"configurable": {"thread_id": "one-turn", "checkpoint_ns": ""}}
    for index, snapshot in enumerate(
        (snapshot_response(response_at(1)), {}, snapshot_response(response_at(2)))
    ):
        checkpoint = empty_checkpoint()
        checkpoint["channel_values"] = {
            "response_snapshot": snapshot,
            "input_items": snapshot_response(response_at(99))["output"],
        }
        checkpoint["channel_versions"] = {"response_snapshot": index + 1, "input_items": index + 1}
        config = await saver.aput(
            config,
            checkpoint,
            {"source": "loop", "step": index, "parents": {}},
            checkpoint["channel_versions"],
        )
    await saver.aput_writes(
        config, [("response_snapshot", snapshot_response(response_at(2)))], "saved-model"
    )
    messages = await read_public_commentary(saver, thread_id="one-turn")
    assert [(item.response_id, item.message_id) for item in messages] == [
        ("response_1", "message_1"),
        ("response_2", "message_2"),
    ]
    assert await read_public_commentary(saver, thread_id="another-turn") == ()
