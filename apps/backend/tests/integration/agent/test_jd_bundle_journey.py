"""離線 OpenAI 串流、正式 JD Bundle 與真 PG；不推論模型或 UI 品質。"""

import asyncio
import json
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.bundles.job_description.cancellation import cancel_turn_jd
from caliburn.bundles.job_description.services import JD_UOW_FACTORY
from caliburn.bundles.job_description.state import JobDescriptionState
from caliburn.host.app import build_app
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import AgentContext
from caliburn.modules.agent.plugins.services import PluginServices
from caliburn.modules.job_description.application.job_description_results import (
    JobDescriptionResult,
)
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    update_job_description,
)
from caliburn.modules.job_description.application.tasks.inputs import UpdateTaskInput
from caliburn.modules.job_description.application.tasks.lifecycle import (
    delete_task,
    update_task,
)
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.model_references.contracts import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.integration.agent.jd_bundle_support import (
    open_jd_agent,
    prepare_jd,
    read_call,
    tool_outputs,
    wait_for_idle,
)
from tests.integration.agent.stream_support import consume
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_read_views_keep_refs_after_restart_and_reject_invalid_targets(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    baseline = prepare_jd(pg_engine, jd_workspace_id)
    target_task = next(task for task in baseline.tasks if task.name == "核對成果")
    sessions = create_session_factory(pg_engine)
    factory = partial(SqlAlchemyJobDescriptionUnitOfWork, sessions)
    references = SqlAlchemyModelReferences(sessions)
    foreign_workspace = (
        WorkspaceService(partial(SqlAlchemyWorkspaceUnitOfWork, sessions))
        .create(interviewee_name="另一工作區")
        .workspace_id
    )
    foreign_target = ReferenceTarget("task", uuid4())
    foreign_ref = references.get_or_create_refs(foreign_workspace, (foreign_target,))[
        foreign_target
    ]
    message_target = ReferenceTarget("message", uuid4())
    wrong_kind_ref = references.get_or_create_refs(jd_workspace_id, (message_target,))[
        message_target
    ]
    requests: list[dict[str, Any]] = []
    task_ref = ""

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal task_ref
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) == 1:
            output = [read_call("map", "map")]
        elif len(requests) == 2:
            navigation = tool_outputs(body)["map"]
            task_ref = next(
                task["read_ref"]
                for task in navigation["tasks"]
                if task["name"] == "核對成果"
            )
            output = [read_call("item", "item", task_ref), read_call("full", "full")]
        elif len(requests) == 4:
            output = [read_call("renamed", "item", task_ref)]
        elif len(requests) == 6:
            output = [
                read_call("deleted", "item", task_ref),
                read_call("foreign", "item", foreign_ref),
                read_call("wrong_kind", "item", wrong_kind_ref),
                read_call("uuid", "item", str(target_task.id)),
            ]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with open_jd_agent(pg_engine, checkpoint_conninfo, transport) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="讀取 JD"
                )
            )
        navigation = tool_outputs(requests[1])["map"]
        outputs = tool_outputs(requests[2])
        assert navigation["version"] == baseline.version
        mapped = {task["name"]: task for task in navigation["tasks"]}
        assert mapped["核對成果"]["outcome_count"] == 2
        assert mapped["待分類任務"]["duty_ref"] is None
        assert [task["name"] for task in outputs["full"]["tasks"]] == [
            task.name for task in baseline.tasks
        ]
        assert outputs["item"]["item"] == next(
            task for task in outputs["full"]["tasks"] if task["read_ref"] == task_ref
        )
        assert [item["text"] for item in outputs["item"]["item"]["outcomes"]] == [
            "交付核對清單",
            "異常紀錄",
        ]
        assert outputs["full"]["knowledge"][0]["description"] == "完整規格"
        assert outputs["full"]["skills"][0]["description"] == "完整判讀方法"
        assert outputs["full"]["duties"][0]["scope"] == "交付範圍保持原文 task_999"
        assert str(target_task.id) not in json.dumps(outputs)
        updated = update_task(
            workspace_id=jd_workspace_id,
            input=UpdateTaskInput(
                job_description_id=baseline.job_description_id,
                task_id=target_task.id,
                expected_version=baseline.version,
                name="重新核對成果",
            ),
            uow_factory=factory,
        )
        async with open_jd_agent(
            pg_engine, checkpoint_conninfo, transport, initialize=False
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="沿原短碼讀取"
                )
            )
        renamed = tool_outputs(requests[4])["renamed"]
        assert renamed["item"]["read_ref"] == task_ref
        assert renamed["item"]["name"] == "重新核對成果"
        assert renamed["version"] == updated.version
        manual_changes = [
            json.loads(item["content"])
            for item in requests[3]["input"]
            if item.get("role") == "user"
            and item.get("content", "").startswith('{"data_kind": "jd_manual_changes"')
        ]
        assert len(manual_changes) == 1
        assert manual_changes[0]["before_version"] == baseline.version
        assert manual_changes[0]["after_version"] == updated.version
        assert manual_changes[0]["items"][0]["read_ref"] == task_ref
        deleted = delete_task(
            workspace_id=jd_workspace_id,
            job_description_id=baseline.job_description_id,
            task_id=target_task.id,
            expected_version=updated.version,
            uow_factory=factory,
        )
        async with open_jd_agent(
            pg_engine, checkpoint_conninfo, transport, initialize=False
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="拒絕無效項目"
                )
            )
        rejections = tool_outputs(requests[6])
        for call_id in ("deleted", "foreign", "wrong_kind", "uuid"):
            assert rejections[call_id]["status"] == "rejected"
            assert rejections[call_id]["code"] == "target_not_found"
        assert references.resolve_refs(jd_workspace_id, (task_ref,))[task_ref] == (
            ReferenceTarget("task", target_task.id)
        )

        # 關閉 Agent 後沿正式 build_app 的模組 HTTP 查讀正文與原歷史。
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
            prefix = (
                f"/workspaces/{jd_workspace_id}/job-descriptions/"
                f"{baseline.job_description_id}"
            )
            current = await reader.get(prefix)
            assert current.status_code == 200, current.text
            assert current.json()["version"] == deleted.version
            history = await reader.get(prefix + f"/history/{baseline.version}")
            assert history.status_code == 200, history.text
            assert "核對成果" in history.text
            assert (await reader.get(prefix + "/history")).status_code == 200

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize("captured", ["absent", "previous_turn", "no_jd"])
def test_cancel_without_matching_capture_preserves_jd(
    pg_engine: Engine, jd_workspace_id: UUID, captured: str
) -> None:
    baseline = prepare_jd(pg_engine, jd_workspace_id)
    turn_id = uuid4()
    state: JobDescriptionState | None = None
    if captured != "absent":
        state = {
            "jd_turn_id": uuid4() if captured == "previous_turn" else turn_id,
            "jd_id": baseline.job_description_id
            if captured == "previous_turn"
            else None,
            "jd_turn_start_version": baseline.version
            if captured == "previous_turn"
            else None,
            "jd_version": baseline.version,
            "jd_manual_before_version": 1,
            "jd_completed_version": None,
        }
    context = AgentContext(PluginServices({}))
    asyncio.run(
        cancel_turn_jd(
            state, workspace_id=jd_workspace_id, turn_id=turn_id, context=context
        ),
        loop_factory=asyncio.SelectorEventLoop,
    )
    assert (
        SqlAlchemyJobDescriptionQueries(pg_engine).get_job_description(
            workspace_id=jd_workspace_id, job_description_id=baseline.job_description_id
        )
        == baseline
    )


def test_cold_cancel_callback_reentry_preserves_later_manual_edit_and_reference(
    pg_engine: Engine, jd_workspace_id: UUID
) -> None:
    baseline = prepare_jd(pg_engine, jd_workspace_id)
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    turn_id = uuid4()
    state: JobDescriptionState = {
        "jd_turn_id": turn_id,
        "jd_id": baseline.job_description_id,
        "jd_turn_start_version": baseline.version,
        "jd_version": baseline.version,
        "jd_manual_before_version": 1,
        "jd_completed_version": None,
    }
    update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=baseline.job_description_id,
            expected_version=baseline.version,
            purpose="已提交但工具 checkpoint 尚未保存",
            correlation_id=str(turn_id),
        ),
        uow_factory=factory,
    )
    target = ReferenceTarget("task", baseline.tasks[0].id)
    reference = SqlAlchemyModelReferences(
        create_session_factory(pg_engine)
    ).get_or_create_refs(jd_workspace_id, (target,))[target]

    async def cancel() -> None:
        # 每次建立新的依賴實例，重入不能依賴前一個 callback 的記憶體。
        fresh_factory = partial(
            SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
        )
        await cancel_turn_jd(
            state,
            workspace_id=jd_workspace_id,
            turn_id=turn_id,
            context=AgentContext(PluginServices({JD_UOW_FACTORY: fresh_factory})),
        )

    asyncio.run(cancel(), loop_factory=asyncio.SelectorEventLoop)
    manual = update_job_description(
        workspace_id=jd_workspace_id,
        input=UpdateJobDescriptionInput(
            job_description_id=baseline.job_description_id,
            expected_version=baseline.version + 2,
            purpose="取消後人工保留內容",
        ),
        uow_factory=factory,
    )
    asyncio.run(cancel(), loop_factory=asyncio.SelectorEventLoop)
    assert (
        SqlAlchemyJobDescriptionQueries(pg_engine).get_job_description(
            workspace_id=jd_workspace_id, job_description_id=baseline.job_description_id
        )
        == manual
    )
    assert (
        SqlAlchemyModelReferences(create_session_factory(pg_engine)).get_or_create_refs(
            jd_workspace_id, (target,)
        )[target]
        == reference
    )


def test_cancelled_turn_does_not_advance_manual_changes_baseline(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    baseline = prepare_jd(pg_engine, jd_workspace_id)
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    requests: list[dict[str, Any]] = []
    cancelled_turn = uuid4()

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        # 空 response 使第二輪保持可取消；不冒充模型自然失敗的品質證據。
        output: list[dict[str, object]] | None = [] if len(requests) == 2 else None
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with open_jd_agent(pg_engine, checkpoint_conninfo, transport) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="第一輪完成"
                )
            )
            manual = update_job_description(
                workspace_id=jd_workspace_id,
                input=UpdateJobDescriptionInput(
                    job_description_id=baseline.job_description_id,
                    expected_version=baseline.version,
                    purpose="人工新增目的",
                ),
                uow_factory=factory,
            )
            with pytest.raises(ValueError, match="complete assistant message"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id,
                        turn_id=cancelled_turn,
                        input="稍後取消",
                    )
                )
            update_job_description(
                workspace_id=jd_workspace_id,
                input=UpdateJobDescriptionInput(
                    job_description_id=baseline.job_description_id,
                    expected_version=manual.version,
                    purpose="取消輪已提交修改",
                    correlation_id=str(cancelled_turn),
                ),
                uow_factory=factory,
            )
            await agent.acancel_turn(
                workspace_id=jd_workspace_id, turn_id=cancelled_turn
            )
        async with open_jd_agent(
            pg_engine, checkpoint_conninfo, transport, initialize=False
        ) as agent:
            await consume(
                agent.astream(
                    workspace_id=jd_workspace_id, turn_id=uuid4(), input="取消後新輪"
                )
            )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    changes = [
        json.loads(item["content"])
        for item in requests[2]["input"]
        if item.get("role") == "user"
        and item.get("content", "").startswith('{"data_kind": "jd_manual_changes"')
    ]
    assert len(changes) == 1
    assert changes[0]["before_version"] == baseline.version
    assert changes[0]["after_version"] == baseline.version + 3
    assert changes[0]["items"][0]["before"]["purpose"] is None
    assert changes[0]["items"][0]["after"]["purpose"] == "人工新增目的"


def test_manual_edit_during_final_response_remains_visible_next_turn(
    pg_engine: Engine, checkpoint_conninfo: str, jd_workspace_id: UUID
) -> None:
    baseline = prepare_jd(pg_engine, jd_workspace_id)
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        if len(requests) == 1:
            # 模型請求已送出後才有人改稿，這份內容不在該輪模型已見版本。
            update_job_description(
                workspace_id=jd_workspace_id,
                input=UpdateJobDescriptionInput(
                    job_description_id=baseline.job_description_id,
                    expected_version=baseline.version,
                    purpose="模型尚未看見的人工修改",
                ),
                uow_factory=factory,
            )
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with open_jd_agent(
            pg_engine, checkpoint_conninfo, httpx2.MockTransport(respond)
        ) as agent:
            for user_input in ("顧問完成時人工同時改稿", "下一輪查核改稿"):
                await consume(
                    agent.astream(
                        workspace_id=jd_workspace_id, turn_id=uuid4(), input=user_input
                    )
                )

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    changes = [
        json.loads(item["content"])
        for item in requests[1]["input"]
        if item.get("role") == "user"
        and item.get("content", "").startswith('{"data_kind": "jd_manual_changes"')
    ]
    assert len(changes) == 1
    assert changes[0]["before_version"] == baseline.version
    assert changes[0]["after_version"] == baseline.version + 1
    assert changes[0]["items"][0]["after"]["purpose"] == "模型尚未看見的人工修改"


def test_host_atomic_write_and_disabled_bundle_cold_cancel_keep_jd_readable(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests: list[dict[str, Any]] = []
    task_ref = ""

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal task_ref
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) in (1, 4):
            output = [read_call("map", "map")]
        elif len(requests) == 2:
            task_ref = next(
                item["read_ref"]
                for item in tool_outputs(body)["map"]["tasks"]
                if item["name"] == "核對成果"
            )
            output = [
                call(
                    "revise_jd_item",
                    "atomic_reject",
                    json.dumps(
                        {
                            "read_ref": task_ref,
                            "changes": [
                                {
                                    "action": "set_field",
                                    "field": "description",
                                    "value": "不得留下",
                                },
                                {
                                    "action": "create_capability",
                                    "kind": "knowledge",
                                    "name": "交付規格",
                                },
                            ],
                        }
                    ),
                ),
                call(
                    "revise_jd_item",
                    "atomic_write",
                    json.dumps(
                        {
                            "read_ref": task_ref,
                            "changes": [
                                {
                                    "action": "set_field",
                                    "field": "description",
                                    "value": "保存的局部改寫",
                                },
                                {
                                    "action": "add_detail",
                                    "kind": "outcome",
                                    "text": "新增正式成果",
                                },
                                {
                                    "action": "create_capability",
                                    "kind": "skill",
                                    "name": "交付審查",
                                },
                            ],
                        }
                    ),
                ),
            ]
        elif len(requests) == 5:
            output = [
                call(
                    "create_jd_task",
                    "cancelled_create",
                    json.dumps(
                        {
                            "name": "取消輪新增任務",
                            "outcomes": [{"text": "取消輪成果"}],
                        }
                    ),
                )
            ]
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(
                BundleConfig("caliburn.bundles.job_description"),
                BundleConfig(
                    "tests.integration.agent.jd_bundle_support",
                    {"fail_after": "create_jd_task"},
                ),
            ),
        ) as client:
            created_workspace = await client.post(
                "/workspaces", json={"interviewee_name": "JD HTTP 旅程"}
            )
            assert created_workspace.status_code == 201, created_workspace.text
            workspace_id = UUID(created_workspace.json()["workspace_id"])
            initial = await client.get(f"/workspaces/{workspace_id}/job-description")
            assert initial.status_code == 200, initial.text
            initialized = JobDescriptionResult.model_validate_json(initial.content)
            assert initialized.version == 1
            assert initialized.tasks == ()
            baseline = await asyncio.to_thread(
                prepare_jd, pg_engine, workspace_id, initialized=initialized
            )
            prefix = (
                f"/workspaces/{workspace_id}/job-descriptions/"
                f"{baseline.job_description_id}"
            )
            turns = f"/workspaces/{workspace_id}/agent/turns"
            accepted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "原子局部修改"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            replies = tool_outputs(requests[2])
            assert replies["atomic_reject"]["status"] == "rejected"
            assert replies["atomic_write"]["status"] == "updated"
            saved = (await client.get(prefix)).json()
            assert saved["version"] == baseline.version + 1
            changed = next(
                task for task in saved["tasks"] if task["name"] == "核對成果"
            )
            assert changed["description"] == "保存的局部改寫"
            assert len(changed["outcomes"]) == 3
            assert len(changed["skill_ids"]) == 2
            assert len(saved["knowledge"]) == 1
            assert saved["duties"][0]["scope"] == "交付範圍保持原文 task_999"

            interrupted = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "提交後故障"}
            )
            assert interrupted.status_code == 202, interrupted.text
            location = interrupted.headers["Location"]
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
            committed = (await client.get(prefix)).json()
            assert committed["version"] == saved["version"] + 1
            cancelled_task = next(
                task for task in committed["tasks"] if task["name"] == "取消輪新增任務"
            )
            target = ReferenceTarget("task", UUID(cancelled_task["id"]))
            refs = SqlAlchemyModelReferences(create_session_factory(pg_engine))
            cancelled_ref = refs.get_or_create_refs(workspace_id, (target,))[target]

        # 完整重開 Host，模型工具停用且 resume_version 改變，取消責任仍常設。
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=(), resume_version="v2"
        ) as client:
            assert (await client.post(location + "/resume")).status_code == 409
            for _ in range(2):
                cancelled = await client.post(location + "/cancel")
                assert cancelled.status_code == 204, cancelled.text
                restored = (await client.get(prefix)).json()
                assert restored == {**saved, "version": saved["version"] + 2}
            assert len(requests) == 5
            assert (
                refs.resolve_refs(workspace_id, (cancelled_ref,))[cancelled_ref]
                == target
            )

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
            assert (await reader.get(prefix)).json() == restored
            history = await reader.get(prefix + "/history")
            assert history.status_code == 200, history.text
            assert len(history.json()["items"]) == baseline.version + 3
            assert (
                await reader.get(prefix + f"/history/{baseline.version}")
            ).status_code == 200

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
