"""正式 Host 串接訪談短碼、JD 引用、人工待核對與撤回後查讀。"""

import asyncio
import json
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
from sqlalchemy import Engine

from caliburn.host.app import build_app
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.interview.application.recording import record_turn_input
from caliburn.modules.interview.application.withdrawal import withdraw_turn
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.job_description.application.citation_inputs import (
    AddCitationInput,
)
from caliburn.modules.job_description.application.citations import (
    ChangeCitationsInput,
    change_citations,
)
from caliburn.modules.job_description.domain.models.citation import MemoryReference
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.memory.application.inputs import MemoryWriteContext
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.content import MemoryContent
from caliburn.modules.memory.infrastructure.persistence.unit_of_work import (
    SqlAlchemyMemoryUnitOfWork,
)
from caliburn.modules.model_references import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.integration.agent.jd_bundle_support import (
    prepare_jd,
    read_call,
    tool_outputs,
    wait_for_idle,
)
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_host_citation_read_confirm_and_withdrawal_keep_original_source(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    baseline = prepare_jd(pg_engine, jd_workspace_id)
    target_task = next(task for task in baseline.tasks if task.name == "核對成果")
    requests: list[dict[str, Any]] = []
    message_ref = task_ref = citation_ref = ""
    source_turn_id = uuid4()
    employee_text = "我逐項核對交付清單，保留異常紀錄。"

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal message_ref, task_ref, citation_ref
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) == 1:
            navigation = next(
                json.loads(item["content"])
                for item in body["input"]
                if item.get("role") == "user"
                and item.get("content", "").startswith(
                    '{"data_kind": "interview_navigation"'
                )
            )
            message_ref = navigation["last_ref"]
            output = [
                call(
                    "read_interview",
                    "source",
                    json.dumps({"query": {"kind": "messages", "refs": [message_ref]}}),
                ),
                read_call("map", "map"),
            ]
        elif len(requests) == 2:
            task_ref = next(
                task["read_ref"]
                for task in tool_outputs(body)["map"]["tasks"]
                if task["name"] == "核對成果"
            )
            output = [
                call(
                    "revise_jd_item",
                    "cite",
                    json.dumps(
                        {
                            "read_ref": task_ref,
                            "changes": [
                                {
                                    "action": "add_source",
                                    "source": {
                                        "kind": "interview",
                                        "message_ref": message_ref,
                                    },
                                }
                            ],
                        }
                    ),
                )
            ]
        elif len(requests) == 3:
            citation_ref = tool_outputs(body)["cite"]["created_refs"][0]
            output = [
                read_call("citation", "item", citation_ref),
                read_call("task", "item", task_ref),
                read_call("message_is_not_jd_item", "item", message_ref),
            ]
        elif len(requests) == 5:
            output = [read_call("changed_citation", "item", citation_ref)]
        elif len(requests) == 6:
            output = [
                call(
                    "revise_jd_item",
                    "confirm",
                    json.dumps(
                        {
                            "read_ref": task_ref,
                            "changes": [
                                {
                                    "action": "confirm_reference_alignment",
                                    "citation_ref": citation_ref,
                                }
                            ],
                        }
                    ),
                ),
                read_call("confirmed", "item", citation_ref),
            ]
        elif len(requests) == 8:
            output = [read_call("withdrawn", "item", citation_ref)]
        elif len(requests) == 9:
            output = [
                call(
                    "revise_jd_item",
                    "reject_withdrawn",
                    json.dumps(
                        {
                            "read_ref": task_ref,
                            "changes": [
                                {
                                    "action": "set_field",
                                    "field": "description",
                                    "value": "不能因失效來源保存",
                                },
                                {
                                    "action": "add_source",
                                    "source": {
                                        "kind": "interview",
                                        "message_ref": message_ref,
                                    },
                                },
                            ],
                        }
                    ),
                )
            ]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        prefix = (
            f"/workspaces/{jd_workspace_id}/job-descriptions/"
            f"{baseline.job_description_id}"
        )
        turns = f"/workspaces/{jd_workspace_id}/agent/turns"
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig("caliburn.bundles.job_description"),
                BundleConfig(
                    "caliburn.bundles.interview",
                    plugins=(
                        "interview",
                        "interview_source_prompt",
                        "interview_read",
                        "interview_navigation",
                    ),
                ),
            ),
        ) as client:

            async def run_turn(turn_id: UUID, user_input: str) -> None:
                accepted = await client.post(
                    turns, json={"turn_id": str(turn_id), "input": user_input}
                )
                assert accepted.status_code == 202, accepted.text
                assert (await wait_for_idle(client, accepted.headers["Location"]))[
                    "status"
                ] == "completed"

            await run_turn(source_turn_id, employee_text)
            first = tool_outputs(requests[3])
            citation = first["citation"]["item"]
            assert citation["source_text"] == employee_text
            assert citation["availability"] == "available"
            assert citation["needs_recheck"] is False
            assert citation["message_ref"] == message_ref
            assert (
                first["task"]["item"]["supporting_sources"][0]["citation_ref"]
                == citation_ref
            )
            assert first["message_is_not_jd_item"]["code"] == "target_not_found"
            saved = (await client.get(prefix)).json()
            assert len(saved["citations"]) == 1
            citation_id = saved["citations"][0]["id"]
            source_id = saved["citations"][0]["source"]["message_id"]
            assert str(baseline.job_description_id) not in json.dumps(first)
            edited = await client.patch(
                prefix + f"/tasks/{target_task.id}",
                json={
                    "expected_version": saved["version"],
                    "description": "人工補充核對步驟",
                },
            )
            assert edited.status_code == 200, edited.text
            assert edited.json()["citations"][0]["jd_changed"] is True

            await run_turn(uuid4(), "確認這筆引用仍支持人工改稿")
            pending = tool_outputs(requests[5])["changed_citation"]["item"]
            assert pending["jd_changed"] is pending["needs_recheck"] is True
            confirmed = tool_outputs(requests[6])
            assert confirmed["confirm"]["status"] == "updated"
            assert confirmed["confirmed"]["item"]["needs_recheck"] is False
            confirmed_jd = (await client.get(prefix)).json()
            assert confirmed_jd["citations"][0]["id"] == citation_id
            assert confirmed_jd["citations"][0]["source"]["message_id"] == source_id

            await asyncio.to_thread(
                withdraw_turn,
                workspace_id=jd_workspace_id,
                turn_id=source_turn_id,
                uow_factory=partial(
                    SqlAlchemyInterviewUnitOfWork, create_session_factory(pg_engine)
                ),
            )
            await run_turn(uuid4(), "已撤回來源不得再用來保存新修改")
            withdrawn = tool_outputs(requests[8])["withdrawn"]["item"]
            assert withdrawn["availability"] == "unavailable"
            assert withdrawn["source_text"] is None
            assert withdrawn["message_ref"] == message_ref
            assert (
                tool_outputs(requests[9])["reject_withdrawn"]["code"]
                == "source_not_available"
            )
            assert (await client.get(prefix)).json() == confirmed_jd

        app = build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url=pg_engine.url.render_as_string(hide_password=False),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url="http://testserver"
            ) as reader,
        ):
            assert (await reader.get(prefix)).json() == confirmed_jd
            detail = await reader.get(prefix + f"/citations/{citation_id}")
            assert detail.status_code == 200, detail.text
            assert detail.json()["source"]["availability"] == "unavailable"
            assert detail.json()["citation"]["source"]["message_id"] == source_id
            assert (
                await reader.get(prefix + f"/history/{saved['version']}")
            ).status_code == 200

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_host_fixed_memory_changes_include_both_source_chains_and_confirm(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    """以公開 Memory 用例備料；完成輪資格為測試邊界，不驗分析模型品質。"""
    baseline = prepare_jd(pg_engine, jd_workspace_id)
    sessions = create_session_factory(pg_engine)
    source_turns: set[UUID] = set()

    class CompletedSourceTurns:
        def completed_turn_ids(self, *, workspace_id: UUID) -> frozenset[UUID]:
            assert workspace_id == jd_workspace_id
            return frozenset(source_turns)

    memory = MemoryService(
        partial(SqlAlchemyMemoryUnitOfWork, sessions),
        completed_turns=CompletedSourceTurns(),
    )
    analysis_id = uuid4()

    def context(version: int) -> MemoryWriteContext:
        return MemoryWriteContext(jd_workspace_id, version, analysis_id)

    def source(text: str) -> UUID:
        turn_id = uuid4()
        result = record_turn_input(
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            text=text,
            uow_factory=partial(SqlAlchemyInterviewUnitOfWork, sessions),
        )
        source_turns.add(turn_id)
        return result.message_id

    old_message = source("先核對數量，再交接。")
    memory.start(context(0), through_message_id=old_message)
    situation = memory.create_situation(
        context(1),
        content=MemoryContent(
            title="交接情境", description="原情境", body="舊情境正文"
        ),
        interview_message_ids=(old_message,),
    )
    assert situation.item_id is not None
    memory.handoff(context(2))
    understanding = memory.create_understanding(
        context(3),
        content=MemoryContent(
            title="核對責任", description="原理解", body="舊理解正文"
        ),
        situation_ids=(situation.item_id,),
    )
    assert understanding.item_id is not None
    old_published = memory.publish(context(4)).version

    new_message = source("補充逐筆核對差異，留存紀錄。")
    analysis_id = uuid4()
    memory.start(context(5), through_message_id=new_message)
    memory.revise_situation(
        context(6),
        item_id=situation.item_id,
        content=MemoryContent(
            title="交接情境新版", description="新情境", body="新情境正文"
        ),
        interview_message_ids=(new_message,),
    )
    memory.handoff(context(7))
    memory.revise_understanding(
        context(8),
        item_id=understanding.item_id,
        content=MemoryContent(
            title="核對責任新版", description="新理解", body="新理解正文"
        ),
        situation_ids=(situation.item_id,),
    )
    new_published = memory.publish(context(9)).version
    attached = change_citations(
        workspace_id=jd_workspace_id,
        input=ChangeCitationsInput(
            job_description_id=baseline.job_description_id,
            expected_version=baseline.version,
            target_kind="job_description",
            target_id=baseline.job_description_id,
            changes=(
                AddCitationInput(
                    source=MemoryReference(
                        workspace_id=jd_workspace_id,
                        published_version=old_published,
                        item_id=understanding.item_id,
                    )
                ),
            ),
        ),
        uow_factory=partial(SqlAlchemyJobDescriptionUnitOfWork, sessions),
    )
    requests: list[dict[str, Any]] = []
    citation_ref = ""

    def changes(call_id: str) -> dict[str, Any]:
        return call(
            "read_jd_changes",
            call_id,
            json.dumps({"query": {"kind": "source", "citation_ref": citation_ref}}),
        )

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal citation_ref
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) == 1:
            jd_map = next(
                json.loads(item["content"])["jd"]
                for item in body["input"]
                if item.get("role") == "user"
                and item.get("content", "").startswith(
                    '{"data_kind": "job_description_map"'
                )
            )
            summary = jd_map["supporting_sources"][0]
            citation_ref = summary["citation_ref"]
            assert summary["source_changed"] is summary["needs_recheck"] is True
            assert summary["published_version"] == old_published
            assert summary["target_title"] == "核對責任"
            assert summary["memory_kind"] == "work_understanding"
            output = [changes("changed")]
        elif len(requests) == 2:
            output = [
                call(
                    "revise_jd_profile",
                    "confirm",
                    json.dumps(
                        {
                            "changes": [
                                {
                                    "action": "confirm_reference_alignment",
                                    "citation_ref": citation_ref,
                                }
                            ]
                        }
                    ),
                )
            ]
        elif len(requests) == 3:
            output = [read_call("confirmed", "item", citation_ref)]
        elif len(requests) == 5:
            output = [
                read_call("next_turn", "item", citation_ref),
                changes("unchanged"),
            ]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        prefix = (
            f"/workspaces/{jd_workspace_id}/job-descriptions/"
            f"{baseline.job_description_id}"
        )
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig("caliburn.bundles.job_description"),
                BundleConfig("caliburn.bundles.memory"),
                BundleConfig(
                    "caliburn.bundles.context",
                    plugins=("window",),
                ),
            ),
        ) as client:
            for text in ("比較來源兩端再確認引用", "下一輪確認引用已對齊"):
                accepted = await client.post(
                    f"/workspaces/{jd_workspace_id}/agent/turns",
                    json={"turn_id": str(uuid4()), "input": text},
                )
                assert accepted.status_code == 202, accepted.text
                state = await wait_for_idle(client, accepted.headers["Location"])
                assert state["status"] == "completed", state
            comparison = tool_outputs(requests[1])["changed"]
            assert comparison["source_changed"] is True
            assert comparison["before"]["body"] == "舊理解正文"
            assert comparison["after"]["body"] == "新理解正文"
            before_chain = comparison["before"]["situations"][0]
            after_chain = comparison["after"]["situations"][0]
            assert before_chain["body"] == "舊情境正文"
            assert after_chain["body"] == "新情境正文"
            assert before_chain["target_title"] == "交接情境"
            assert after_chain["target_title"] == "交接情境新版"
            references = SqlAlchemyModelReferences(sessions)
            resolved = await asyncio.to_thread(
                references.resolve_refs,
                jd_workspace_id,
                (*before_chain["interview_refs"], *after_chain["interview_refs"]),
            )
            assert resolved[before_chain["interview_refs"][0]] == ReferenceTarget(
                "message", old_message
            )
            assert resolved[after_chain["interview_refs"][0]] == ReferenceTarget(
                "message", new_message
            )
            assert str(understanding.item_id) not in json.dumps(comparison)
            assert tool_outputs(requests[2])["confirm"]["status"] == "updated"
            confirmed = tool_outputs(requests[3])["confirmed"]["item"]
            next_turn = tool_outputs(requests[5])
            assert confirmed["source_changed"] is confirmed["needs_recheck"] is False
            assert next_turn["next_turn"]["item"]["needs_recheck"] is False
            assert next_turn["unchanged"]["source_changed"] is False
            assert next_turn["unchanged"]["before"] == next_turn["unchanged"]["after"]
            saved = (await client.get(prefix)).json()
            assert saved["version"] == attached.version + 1
            assert saved["citations"][0]["id"] == str(attached.citations[0].id)
            assert saved["citations"][0]["source"]["item_id"] == str(
                understanding.item_id
            )
            assert saved["citations"][0]["source"]["published_version"] == new_published
            detail = await client.get(
                prefix + f"/citations/{attached.citations[0].id}",
                params={"published_version": new_published},
            )
            assert detail.status_code == 200, detail.text
            assert detail.json()["source"]["item_kind"] == "understanding"
            assert detail.json()["needs_recheck"] is False
            removed = await client.patch(
                prefix + "/citations",
                json={
                    "expected_version": saved["version"],
                    "target_kind": "job_description",
                    "target_id": str(baseline.job_description_id),
                    "changes": [
                        {
                            "action": "remove",
                            "citation_id": str(attached.citations[0].id),
                        }
                    ],
                },
            )
            assert removed.status_code == 200, removed.text
            assert removed.json()["citations"] == []
            accepted = await client.post(
                f"/workspaces/{jd_workspace_id}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "核對人工移除的引用"},
            )
            assert accepted.status_code == 202, accepted.text
            state = await wait_for_idle(client, accepted.headers["Location"])
            assert state["status"] == "completed", state
            manual = [
                json.loads(item["content"])
                for item in requests[6]["input"]
                if item.get("role") == "user"
                and item.get("content", "").startswith(
                    '{"data_kind": "jd_manual_changes"'
                )
            ][-1]
            removal = next(
                item for item in manual["items"] if item["kind"] == "citation"
            )
            assert removal["change"] == "removed"
            assert removal["after"] is None
            assert removal["before"]["citation_ref"] == citation_ref
            assert removal["before"]["memory_kind"] == "work_understanding"
            assert removal["before"]["target_title"] == "核對責任新版"
            assert removal["before"]["source_text"] == "新理解正文"
            assert removal["before"]["published_version"] == new_published
            assert removal["before"]["source_changed"] is None

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
