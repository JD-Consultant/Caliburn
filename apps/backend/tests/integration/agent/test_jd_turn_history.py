"""完成輪差異沿正式 Host、JD Bundle 與 PostgreSQL 固定歷史查讀。"""

import asyncio
import json
from functools import partial
from typing import Any
from uuid import UUID, uuid4

import httpx2
import pytest
from sqlalchemy import Engine, delete

from caliburn.host.app import build_app
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.job_description.application.job_descriptions import (
    UpdateJobDescriptionInput,
    update_job_description,
)
from caliburn.modules.job_description.infrastructure.persistence.orm_models import (
    JobDescriptionSnapshotRow,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.integration.agent.http_support import api_client
from tests.integration.agent.jd_bundle_support import (
    prepare_jd,
    read_call,
    tool_outputs,
    wait_for_idle,
)
from tests.integration.agent.jd_turn_history_support import (
    append_checkpoint_fault,
    checkpoint_ids,
    create_workspace_jd,
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


def test_completed_turn_without_write_returns_identical_fixed_contents(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests: list[httpx2.Request] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request)
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            jd_id = initial.job_description_id
            turn_id = uuid4()
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": "這輪只回覆"},
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"

            changes = await client.get(
                f"/workspaces/{workspace_id}/job-descriptions/{jd_id}"
                f"/turns/{turn_id}/changes"
            )
            assert changes.status_code == 200, changes.text
            body = changes.json()
            assert body["before_version"] == body["after_version"] == 1
            assert body["before"] == body["after"]
            assert body["difference"]["items"] == []
            assert len(requests) == 1

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_completed_tool_turn_keeps_model_seen_versions_after_manual_edits_and_reopen(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests: list[dict[str, Any]] = []
    workspace_id: UUID
    jd_id: UUID
    before_version: int
    factory = partial(
        SqlAlchemyJobDescriptionUnitOfWork, create_session_factory(pg_engine)
    )

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) == 1:
            output = [
                call(
                    "create_jd_task",
                    "new_task",
                    json.dumps(
                        {"name": "輪內新增任務", "outcomes": [{"text": "輪內正式成果"}]}
                    ),
                )
            ]
        else:
            assert tool_outputs(body)["new_task"]["status"] == "created"
            # 在最後模型請求返回之前改稿：完成版仍須採模型已見 jd_version。
            update_job_description(
                workspace_id=workspace_id,
                input=UpdateJobDescriptionInput(
                    job_description_id=jd_id,
                    expected_version=before_version + 1,
                    purpose="模型尚未看見的人工修改",
                ),
                uow_factory=factory,
            )
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        nonlocal workspace_id, jd_id, before_version
        transport = httpx2.MockTransport(respond)
        bundles = (BundleConfig("caliburn.bundles.job_description"),)
        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            baseline = await asyncio.to_thread(
                prepare_jd, pg_engine, workspace_id, initialized=initial
            )
            jd_id, before_version = baseline.job_description_id, baseline.version
            prefix = f"/workspaces/{workspace_id}/job-descriptions/{jd_id}"
            turn_id = uuid4()
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": "建立一項新任務"},
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            assert (await client.get(prefix)).json()["version"] == before_version + 2
            url = prefix + f"/turns/{turn_id}/changes"
            history_before = await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
            response = await client.get(url)
            assert response.status_code == 200, response.text
            changes = response.json()
            assert changes["before_version"] == before_version
            assert changes["after_version"] == before_version + 1
            for side, version in (
                ("before", before_version),
                ("after", before_version + 1),
            ):
                history = await client.get(prefix + f"/history/{version}")
                assert history.status_code == 200, history.text
                assert changes[side] == history.json()["content"]
            assert changes["after"]["purpose"] is None
            assert len(changes["after"]["tasks"]) == len(baseline.tasks) + 1
            assert changes["difference"]["items"]

            edited = await client.patch(
                prefix,
                json={
                    "expected_version": before_version + 2,
                    "purpose": "完成後再人工改稿",
                },
            )
            assert edited.status_code == 200, edited.text
            assert (await client.get(url)).json() == changes
            assert (
                await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
                == history_before
            )
            assert len(requests) == 2

            other_workspace, other_jd = await create_workspace_jd(client)
            rejected_urls = (
                prefix + f"/turns/{uuid4()}/changes",
                f"/workspaces/{workspace_id}/job-descriptions/{other_jd.job_description_id}"
                f"/turns/{turn_id}/changes",
                f"/workspaces/{other_workspace}/job-descriptions/{jd_id}/turns/{turn_id}/changes",
            )
            for rejected_url in rejected_urls:
                denied = await client.get(rejected_url)
                assert denied.status_code == 404, denied.text
                assert denied.json()["detail"]["code"] == "jd_turn_not_found"

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=bundles
        ) as client:
            reopened = await client.get(url)
            assert reopened.status_code == 200, reopened.text
            assert reopened.json() == changes
            assert len(requests) == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_continued_window_keeps_older_seen_version_when_manual_edits_have_no_net_change(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append(request_body(request))
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig("caliburn.bundles.job_description"),
                BundleConfig(
                    "caliburn.bundles.context",
                    plugins=("window",),
                ),
            ),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            jd_id = initial.job_description_id
            prefix = f"/workspaces/{workspace_id}/job-descriptions/{jd_id}"
            turns = f"/workspaces/{workspace_id}/agent/turns"
            first = await client.post(
                turns, json={"turn_id": str(uuid4()), "input": "讀取第一版導覽"}
            )
            assert first.status_code == 202, first.text
            assert (await wait_for_idle(client, first.headers["Location"]))[
                "status"
            ] == "completed"
            for version, purpose in ((1, "暫時人工修改"), (2, None)):
                edited = await client.patch(
                    prefix, json={"expected_version": version, "purpose": purpose}
                )
                assert edited.status_code == 200, edited.text
                assert edited.json()["version"] == version + 1
            second_turn = uuid4()
            second = await client.post(
                turns, json={"turn_id": str(second_turn), "input": "沿用原窗口只回覆"}
            )
            assert second.status_code == 202, second.text
            assert (await wait_for_idle(client, second.headers["Location"]))[
                "status"
            ] == "completed"
            response = await client.get(prefix + f"/turns/{second_turn}/changes")
            assert response.status_code == 200, response.text
            changes = response.json()
            assert changes["before_version"] == 3
            assert changes["after_version"] == 1
            assert changes["before"] == changes["after"]
            assert changes["difference"]["items"] == []
            assert changes["difference"]["collections"] == []
            assert len(requests) == 2
            assert not any(
                item.get("role") == "user"
                and item.get("content", "").startswith(
                    '{"data_kind": "jd_manual_changes"'
                )
                for item in requests[-1]["input"]
            )
            edited = await client.patch(
                prefix, json={"expected_version": 3, "purpose": "下一次人工修改"}
            )
            assert edited.status_code == 200, edited.text
            assert (
                await client.get(prefix + f"/turns/{second_turn}/changes")
            ).json() == changes

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_restore_completed_turn_only_restores_jd_and_repeated_request_keeps_version(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) == 1:
            output = [
                call("create_jd_task", "new_task", '{"name":"本輪新增任務"}'),
                call("read_interview_plan", "read_plan", "{}"),
                call(
                    "edit_interview_plan",
                    "edit_plan",
                    json.dumps({"diff": "@@\n+後續釐清交付範圍\n*** End of File"}),
                ),
            ]
        else:
            replies = tool_outputs(body)
            assert replies["new_task"]["status"] == "created"
            assert replies["edit_plan"]["status"] == "updated"
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(
                BundleConfig("caliburn.bundles.job_description"),
                BundleConfig("caliburn.bundles.interview"),
                BundleConfig("caliburn.bundles.plan"),
            ),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            baseline = await asyncio.to_thread(
                prepare_jd, pg_engine, workspace_id, initialized=initial
            )
            jd_id = baseline.job_description_id
            prefix = f"/workspaces/{workspace_id}/job-descriptions/{jd_id}"
            turn_id = uuid4()
            input_text = "整理 JD 並保留後續訪談計畫"
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": input_text},
            )
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            completed = await wait_for_idle(client, location)
            assert completed["status"] == "completed"
            turn_url = prefix + f"/turns/{turn_id}"
            response = await client.get(turn_url + "/changes")
            assert response.status_code == 200, response.text
            changes = response.json()
            assert changes["before_version"] == baseline.version
            assert changes["after_version"] == baseline.version + 1
            assert any(
                task["name"] == "本輪新增任務" for task in changes["after"]["tasks"]
            )
            checkpoints = await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
            transcript_url = f"/workspaces/{workspace_id}/interview/messages"
            transcript = await client.get(
                transcript_url, params={"turn_id": str(turn_id)}
            )
            assert transcript.status_code == 200, transcript.text
            messages = transcript.json()
            assert {item["speaker"] for item in messages} == {"employee", "consultant"}
            assert any(item["text"] == input_text for item in messages)
            plan_url = f"/workspaces/{workspace_id}/plan"
            plan = await client.get(plan_url)
            assert plan.status_code == 200, plan.text
            assert plan.json()["body"] == "後續釐清交付範圍"

            restored = await client.post(turn_url + ":restore")
            assert restored.status_code == 200, restored.text
            assert restored.json() == {
                **baseline.model_dump(mode="json"),
                "version": baseline.version + 2,
            }
            assert (await client.get(prefix)).json() == restored.json()
            saved_history = await client.get(prefix + "/history")
            assert saved_history.status_code == 200, saved_history.text
            restored_entry = saved_history.json()["items"][0]
            assert restored_entry["kind"] == "restored"
            assert restored_entry["restored_from_version"] == baseline.version
            assert restored_entry["reverts_correlation_id"] == str(turn_id)

            repeated = await client.post(turn_url + ":restore")
            assert repeated.status_code == 200, repeated.text
            assert repeated.json() == restored.json()
            assert (
                await client.get(prefix + "/history")
            ).json() == saved_history.json()
            assert (await client.get(turn_url + "/changes")).json() == changes
            assert (await client.get(location)).json() == completed
            assert (
                await client.get(transcript_url, params={"turn_id": str(turn_id)})
            ).json() == messages
            assert (await client.get(plan_url)).json() == plan.json()
            assert (
                await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
                == checkpoints
            )
            assert len(requests) == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_disabled_jd_bundle_after_reopen_does_not_reuse_previous_turn_jd_fields(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        return sse_response(EventStream(response_events(response_payload())))

    async def run() -> None:
        transport = httpx2.MockTransport(respond)
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            transport,
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            turns = f"/workspaces/{workspace_id}/agent/turns"
            previous_turn, new_turn = uuid4(), uuid4()
            accepted = await client.post(
                turns, json={"turn_id": str(previous_turn), "input": "JD 參與的完成輪"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            prefix = (
                f"/workspaces/{workspace_id}/job-descriptions/"
                f"{initial.job_description_id}/turns"
            )
            previous = await client.get(prefix + f"/{previous_turn}/changes")
            assert previous.status_code == 200, previous.text

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=()
        ) as client:
            accepted = await client.post(
                turns, json={"turn_id": str(new_turn), "input": "停用 JD 後正常完成"}
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            for response in (
                await client.get(prefix + f"/{new_turn}/changes"),
                await client.post(prefix + f"/{new_turn}:restore"),
            ):
                assert response.status_code == 404, response.text
                assert response.json()["detail"]["code"] == "jd_turn_not_found"
            assert (
                await client.get(prefix + f"/{previous_turn}/changes")
            ).json() == previous.json()
            assert requests == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_interrupted_and_cancelled_turn_never_exposes_completed_changes(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests = 0

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal requests
        requests += 1
        output = (
            [read_call("map", "map")]
            if requests == 1
            else [call("create_jd_task", "new", '{"name":"待取消任務"}')]
        )
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
            workspace_id, initial = await create_workspace_jd(client)
            turn_id = uuid4()
            jd_id = initial.job_description_id
            prefix = f"/workspaces/{workspace_id}/job-descriptions/{jd_id}"
            url = prefix + f"/turns/{turn_id}/changes"
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": "提交後故障"},
            )
            assert accepted.status_code == 202, accepted.text
            location = accepted.headers["Location"]
            assert (await wait_for_idle(client, location))["status"] == "interrupted"
            assert (await client.get(prefix)).json()["version"] == 2
            assert (await client.get(url)).status_code == 404
            assert (
                await client.post(prefix + f"/turns/{turn_id}:restore")
            ).status_code == 404
            cancelled = await client.post(location + "/cancel")
            assert cancelled.status_code == 204, cancelled.text
            assert (await client.get(url)).status_code == 404
            assert (
                await client.post(prefix + f"/turns/{turn_id}:restore")
            ).status_code == 404
            assert (await client.get(prefix)).json()["tasks"] == []

        async with api_client(
            pg_engine, checkpoint_conninfo, transport, bundles=()
        ) as client:
            assert (await client.get(url)).status_code == 404
        assert requests == 2

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize(
    ("fault", "expected_status", "code"),
    [
        ({"turn_completed": False}, 404, "jd_turn_not_found"),
        ({"cancel_status": "completed"}, 404, "jd_turn_not_found"),
        ({"jd_completed_version": None}, 500, "jd_turn_data_error"),
    ],
)
def test_latest_saved_turn_state_cannot_fall_back_to_older_completed_checkpoint(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    fault: dict[str, object],
    expected_status: int,
    code: str,
) -> None:
    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            ),
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            turn_id = uuid4()
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": "先完成一輪"},
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            url = (
                f"/workspaces/{workspace_id}/job-descriptions/{initial.job_description_id}"
                f"/turns/{turn_id}/changes"
            )
            assert (await client.get(url)).status_code == 200
            await append_checkpoint_fault(
                checkpoint_conninfo, turn_id=turn_id, values=fault
            )
            history = await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
            rejected = await client.get(url)
            assert rejected.status_code == expected_status, rejected.text
            assert rejected.json()["detail"]["code"] == code
            assert "model_request" not in rejected.text
            assert "jd_completed_version" not in rejected.text
            assert await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id) == history

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_new_input_snapshot_with_previous_completed_values_is_not_a_completed_turn(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            ),
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            old_turn, new_turn = uuid4(), uuid4()
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(old_turn), "input": "前輪正常完成"},
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            jd_id = initial.job_description_id
            prefix = f"/workspaces/{workspace_id}/job-descriptions/{jd_id}"
            previous = await client.get(prefix + f"/turns/{old_turn}/changes")
            assert previous.status_code == 200, previous.text
            await append_checkpoint_fault(
                checkpoint_conninfo, turn_id=old_turn, values={}, input_turn_id=new_turn
            )
            denied = await client.get(prefix + f"/turns/{new_turn}/changes")
            assert denied.status_code == 404, denied.text
            assert denied.json()["detail"]["code"] == "jd_turn_not_found"
            assert (
                await client.get(prefix + f"/turns/{old_turn}/changes")
            ).json() == previous.json()

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


def test_missing_fixed_history_is_data_error_and_unconfigured_agent_is_unavailable(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(
                lambda _: sse_response(EventStream(response_events(response_payload())))
            ),
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            turn_id = uuid4()
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": "完成後缺少歷史"},
            )
            assert accepted.status_code == 202, accepted.text
            assert (await wait_for_idle(client, accepted.headers["Location"]))[
                "status"
            ] == "completed"
            url = (
                f"/workspaces/{workspace_id}/job-descriptions/{initial.job_description_id}"
                f"/turns/{turn_id}/changes"
            )
            assert (await client.get(url)).status_code == 200
            # 只破壞本測例的合成歷史，驗不能回退至仍存在的目前正式 JD。
            with pg_engine.begin() as connection:
                connection.execute(
                    delete(JobDescriptionSnapshotRow).where(
                        JobDescriptionSnapshotRow.job_description_id
                        == initial.job_description_id,
                        JobDescriptionSnapshotRow.version == 1,
                    )
                )
            missing = await client.get(url)
            assert missing.status_code == 500, missing.text
            assert missing.json()["detail"]["code"] == "jd_turn_data_error"
            assert "model_request" not in missing.text

        app = build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url=pg_engine.url.render_as_string(hide_password=False),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url="http://testserver"
            ) as client,
        ):
            unavailable = await client.get(url)
            assert unavailable.status_code == 503, unavailable.text
            assert unavailable.json()["detail"]["code"] == "agent_unavailable"

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
