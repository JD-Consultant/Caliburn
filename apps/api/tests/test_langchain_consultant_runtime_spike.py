from __future__ import annotations

from uuid import uuid4

import pytest
from deepagents.backends import StateBackend
from deepagents.backends.utils import create_file_data
from langchain.messages import AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.store.memory import InMemoryStore

import langchain_consultant_runtime_spike as spike


def _skill_files() -> dict[str, object]:
    descriptions = {
        "task-analysis": "辨識、修訂與檢查工作任務。",
        "duty-analysis": "依共同目的動態整理職責。",
        "opks-o": "釐清任務產出與成果標準。",
        "opks-p": "釐清工作流程與關鍵步驟。",
        "opks-k": "釐清完成任務需要的知識。",
        "opks-s": "釐清完成任務需要的技能。",
    }
    return {
        f"/skills/{name}/SKILL.md": create_file_data(
            "---\n"
            f"name: {name}\n"
            f"description: {description}\n"
            "---\n"
            f"FULL_BODY::{name}::只在真正載入此 Skill 後才可看見。\n"
        )
        for name, description in descriptions.items()
    }


def test_model_profile_builds_replaceable_chatopenrouter_configuration() -> None:
    profile = spike.ConsultantModelProfile(
        profile_id="consultant-primary-v1",
        model_id="anthropic/claude-sonnet-4.6",
        temperature=0.2,
        max_completion_tokens=4096,
        reasoning={"effort": "high"},
        provider_order=("anthropic",),
        allow_fallbacks=False,
        require_parameters=True,
    )

    model = profile.build(api_key="test-key")

    assert model.model_name == "anthropic/claude-sonnet-4.6"
    assert model._default_params == {
        "model": "anthropic/claude-sonnet-4.6",
        "stream": False,
        "temperature": 0.2,
        "max_completion_tokens": 4096,
        "reasoning": {"effort": "high"},
        "provider": {
            "order": ["anthropic"],
            "allow_fallbacks": False,
            "require_parameters": True,
        },
    }


@pytest.mark.asyncio
async def test_bounded_consultant_loads_only_eligible_skill_and_selected_context() -> None:
    document_id = f"jd-context-{uuid4()}"
    store = InMemoryStore()
    namespace = ("job-analysis", document_id, "sources")
    store.put(
        namespace,
        "answer-old",
        {"text": "舊說法：我不處理缺料。", "processing_status": "complete"},
    )
    store.put(
        namespace,
        "answer-correction",
        {
            "text": "更正：我每天都會確認缺料並安排採購。",
            "processing_status": "complete",
            "supersedes": "answer-old",
        },
    )
    store.put(
        namespace,
        "answer-side",
        {"text": "旁支：偶爾也會協助盤點。", "processing_status": "complete"},
    )

    model = spike.ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "read_file",
                        "args": {
                            "file_path": "/skills/opks-o/SKILL.md",
                            "offset": 0,
                            "limit": 1000,
                        },
                        "id": "read-o",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "lookup_source",
                        "args": {"source_id": "answer-side"},
                        "id": "lookup-side",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ConsultantTurn",
                        "args": {
                            "visible_message": "目前先確認這項工作的成果，再回頭處理盤點旁支。",
                            "used_skill_names": ["opks-o"],
                            "used_source_ids": ["answer-correction", "answer-side"],
                            "next_focus": "task-1:outcome",
                        },
                        "id": "submit-turn",
                        "type": "tool_call",
                    }
                ],
                usage_metadata={"input_tokens": 80, "output_tokens": 20, "total_tokens": 100},
            ),
        ]
    )
    context = spike.ConsultantRunContext(
        operation_id="operation-1",
        document_id=document_id,
        focus={"task_id": "task-1", "target": "outcome"},
        progress={"covered": ["task-1:statement"], "gaps": ["task-1:outcome"]},
        current_jd={"tasks": []},
        effective_source_ids=("answer-correction",),
        available_source_ids=("answer-correction", "answer-side"),
        eligible_skill_names=("task-analysis", "opks-o"),
        source_token_budget=120,
    )
    agent = spike.build_consultant_agent(
        model=model,
        backend=StateBackend(),
        checkpointer=InMemorySaver(),
        store=store,
    )

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "繼續訪談。"}], "files": _skill_files()},
        {"configurable": {"thread_id": f"consultant-{uuid4()}"}},
        context=context,
    )

    assert result["structured_response"] == spike.ConsultantTurn(
        visible_message="目前先確認這項工作的成果，再回頭處理盤點旁支。",
        used_skill_names=["opks-o"],
        used_source_ids=["answer-correction", "answer-side"],
        next_focus="task-1:outcome",
    )
    assert model.call_count == 3
    tool_call_names = [
        call["name"]
        for message in result["messages"]
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]
    assert tool_call_names == ["read_file", "lookup_source", "ConsultantTurn"]
    assert result["context_manifest"]["included_source_ids"] == ["answer-correction"]
    assert result["context_manifest"]["eligible_skill_names"] == [
        "task-analysis",
        "opks-o",
    ]

    first_prompt = model.system_prompts[0]
    assert "更正：我每天都會確認缺料並安排採購。" in first_prompt
    assert "舊說法：我不處理缺料。" not in first_prompt
    assert "旁支：偶爾也會協助盤點。" not in first_prompt
    assert "task-analysis" in first_prompt
    assert "opks-o" in first_prompt
    assert "duty-analysis" not in first_prompt
    assert "opks-k" not in first_prompt
    assert "FULL_BODY::opks-o" not in first_prompt
    assert any("FULL_BODY::opks-o" in message for message in model.captured_text[1])
    spike.verify_consultant_turn(result["structured_response"], context)


@pytest.mark.asyncio
async def test_lookup_and_model_limits_stop_an_unbounded_agent_loop() -> None:
    document_id = f"jd-limit-{uuid4()}"
    store = InMemoryStore()
    namespace = ("job-analysis", document_id, "sources")
    store.put(namespace, "answer-1", {"text": "來源一", "processing_status": "complete"})
    lookup_calls = [
        AIMessage(
            content="",
            tool_calls=[
                {
                    "name": "lookup_source",
                    "args": {"source_id": "answer-1"},
                    "id": f"lookup-{index}",
                    "type": "tool_call",
                }
            ],
        )
        for index in range(1, 5)
    ]
    model = spike.ScriptedChatModel(responses=lookup_calls)
    context = spike.ConsultantRunContext(
        operation_id="operation-limit",
        document_id=document_id,
        focus={"task_id": "task-1"},
        progress={"gaps": ["task-1:outcome"]},
        current_jd={},
        effective_source_ids=(),
        available_source_ids=("answer-1",),
        eligible_skill_names=(),
        source_token_budget=20,
    )
    agent = spike.build_consultant_agent(
        model=model,
        backend=StateBackend(),
        checkpointer=InMemorySaver(),
        store=store,
    )

    result = await agent.ainvoke(
        {"messages": [{"role": "user", "content": "繼續。"}], "files": _skill_files()},
        {"configurable": {"thread_id": f"limit-{uuid4()}"}},
        context=context,
    )

    assert model.call_count == 3
    attempted_tool_calls = [
        call["name"]
        for message in result["messages"]
        if isinstance(message, AIMessage)
        for call in message.tool_calls
    ]
    assert attempted_tool_calls == ["lookup_source"] * 3
    assert "limit" in result["messages"][-1].content.lower()


@pytest.mark.asyncio
async def test_eligible_skill_metadata_changes_per_run_without_stale_skill_leakage() -> None:
    document_id = f"jd-skills-{uuid4()}"
    store = InMemoryStore()
    model = spike.ScriptedChatModel(
        responses=[
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ConsultantTurn",
                        "args": {
                            "visible_message": "先確認任務敘述。",
                            "used_skill_names": [],
                            "used_source_ids": [],
                            "next_focus": "task-1:statement",
                        },
                        "id": "turn-task",
                        "type": "tool_call",
                    }
                ],
            ),
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "name": "ConsultantTurn",
                        "args": {
                            "visible_message": "接著確認所需知識。",
                            "used_skill_names": [],
                            "used_source_ids": [],
                            "next_focus": "task-1:knowledge",
                        },
                        "id": "turn-knowledge",
                        "type": "tool_call",
                    }
                ],
            ),
        ]
    )
    agent = spike.build_consultant_agent(
        model=model,
        backend=StateBackend(),
        checkpointer=InMemorySaver(),
        store=store,
    )
    thread_config = {"configurable": {"thread_id": f"skills-{uuid4()}"}}

    first_context = spike.ConsultantRunContext(
        operation_id="operation-skills-1",
        document_id=document_id,
        focus={"task_id": "task-1", "target": "statement"},
        progress={},
        current_jd={},
        effective_source_ids=(),
        available_source_ids=(),
        eligible_skill_names=("task-analysis",),
        source_token_budget=20,
    )
    second_context = spike.ConsultantRunContext(
        operation_id="operation-skills-2",
        document_id=document_id,
        focus={"task_id": "task-1", "target": "knowledge"},
        progress={},
        current_jd={},
        effective_source_ids=(),
        available_source_ids=(),
        eligible_skill_names=("opks-k",),
        source_token_budget=20,
    )

    await agent.ainvoke(
        {"messages": [{"role": "user", "content": "先談任務。"}], "files": _skill_files()},
        thread_config,
        context=first_context,
    )
    await agent.ainvoke(
        {"messages": [{"role": "user", "content": "現在談知識。"}]},
        thread_config,
        context=second_context,
    )

    assert "task-analysis" in model.system_prompts[0]
    assert "opks-k" not in model.system_prompts[0]
    assert "opks-k" in model.system_prompts[1]
    assert "task-analysis" not in model.system_prompts[1]


def test_verifier_rejects_unavailable_sources_and_ineligible_skills() -> None:
    context = spike.ConsultantRunContext(
        operation_id="operation-verify",
        document_id="jd-verify",
        focus={},
        progress={},
        current_jd={},
        effective_source_ids=(),
        available_source_ids=("answer-1",),
        eligible_skill_names=("task-analysis",),
        source_token_budget=20,
    )

    with pytest.raises(spike.ConsultantContractViolation, match="ineligible skills"):
        spike.verify_consultant_turn(
            spike.ConsultantTurn(
                visible_message="錯誤技能",
                used_skill_names=["opks-s"],
                used_source_ids=["answer-1"],
                next_focus="task-1",
            ),
            context,
        )

    with pytest.raises(spike.ConsultantContractViolation, match="unavailable sources"):
        spike.verify_consultant_turn(
            spike.ConsultantTurn(
                visible_message="錯誤來源",
                used_skill_names=["task-analysis"],
                used_source_ids=["answer-unknown"],
                next_focus="task-1",
            ),
            context,
        )
