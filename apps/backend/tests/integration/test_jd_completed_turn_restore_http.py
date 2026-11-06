"""正式 Host 的完成輪 JD 恢復；真保存、固定完成版與重送接縫。"""

import asyncio
import json
from typing import Any
from uuid import uuid4

import httpx2
import pytest
from sqlalchemy import Engine

from caliburn.modules.agent.bootstrap import BundleConfig
from tests.integration.agent.conftest import (
    checkpoint_conninfo as checkpoint_conninfo,
)
from tests.integration.agent.conftest import (
    isolate_external_configuration as isolate_external_configuration,
)
from tests.integration.agent.http_support import api_client
from tests.integration.agent.jd_bundle_support import (
    prepare_jd,
    read_call,
    tool_outputs,
    wait_for_idle,
)
from tests.integration.agent.jd_turn_history_support import (
    checkpoint_ids,
    create_workspace_jd,
)
from tests.integration.test_jd_citations import source_message
from tests.unit.modules.agent.offline_openai import (
    EventStream,
    call,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


def test_completed_restore_recovers_full_jd_and_is_idempotent_after_manual_edit(
    pg_engine: Engine, checkpoint_conninfo: str
) -> None:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) == 1:
            output = [read_call("map", "map")]
        elif len(requests) == 2:
            task_ref = next(
                item["read_ref"]
                for item in tool_outputs(body)["map"]["tasks"]
                if item["name"] == "核對成果"
            )
            output = [
                call("delete_jd_item", "delete", json.dumps({"read_ref": task_ref}))
            ]
        elif len(requests) == 3:
            assert tool_outputs(body)["delete"]["status"] == "deleted"
            output = [
                call(
                    "create_jd_task",
                    "create",
                    json.dumps(
                        {"name": "輪內新任務", "outcomes": [{"text": "新成果"}]}
                    ),
                )
            ]
        else:
            assert len(requests) == 4
            assert tool_outputs(body)["create"]["status"] == "created"
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            baseline = await asyncio.to_thread(
                prepare_jd, pg_engine, workspace_id, initialized=initial
            )
            _, source = await asyncio.to_thread(source_message, pg_engine, workspace_id)
            jd_id = initial.job_description_id
            prefix = f"/workspaces/{workspace_id}/job-descriptions/{jd_id}"
            task_id = next(
                task.id for task in baseline.tasks if task.name == "核對成果"
            )
            cited = await client.patch(
                prefix + f"/tasks/{task_id}",
                json={
                    "expected_version": baseline.version,
                    "citations": [
                        {"action": "add", "source": source.model_dump(mode="json")}
                    ],
                },
            )
            assert cited.status_code == 200, cited.text
            before = cited.json()
            assert len(before["citations"]) == 1
            turn_id = uuid4()
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": "替換核對成果任務"},
            )
            assert accepted.status_code == 202, accepted.text
            turn_location = accepted.headers["Location"]
            completed = await wait_for_idle(client, turn_location)
            assert completed["status"] == "completed"
            current = (await client.get(prefix)).json()
            assert current["version"] == before["version"] + 2
            assert current["citations"] == []
            assert any(task["name"] == "輪內新任務" for task in current["tasks"])
            changes_path = prefix + f"/turns/{turn_id}/changes"
            changes = await client.get(changes_path)
            assert changes.status_code == 200, changes.text
            fixed_changes = changes.json()
            assert fixed_changes["before_version"] == before["version"]
            assert fixed_changes["after_version"] == current["version"]
            assert fixed_changes["before"]["citations"] == before["citations"]
            checkpoints = await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)

            restore_path = prefix + f"/turns/{turn_id}:restore"
            restored = await client.post(restore_path)
            assert restored.status_code == 200, restored.text
            assert restored.json() == {
                **before,
                "version": current["version"] + 1,
            }
            history = (await client.get(prefix + "/history")).json()
            repeated = await client.post(restore_path)
            assert repeated.status_code == 200, repeated.text
            assert repeated.json() == restored.json()
            assert (await client.get(prefix + "/history")).json() == history

            edited = await client.patch(
                prefix,
                json={
                    "expected_version": restored.json()["version"],
                    "purpose": "撤回後人工保留",
                },
            )
            assert edited.status_code == 200, edited.text
            history_after_edit = (await client.get(prefix + "/history")).json()
            repeated_after_edit = await client.post(restore_path)
            assert repeated_after_edit.status_code == 200, repeated_after_edit.text
            assert repeated_after_edit.json() == edited.json()
            assert (await client.get(prefix + "/history")).json() == history_after_edit
            assert (await client.get(changes_path)).json() == fixed_changes
            assert (await client.get(turn_location)).json() == completed
            assert (
                await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
                == checkpoints
            )
            assert len(requests) == 4

            other_workspace, other_jd = await create_workspace_jd(client)
            missing_paths = (
                prefix + f"/turns/{uuid4()}:restore",
                f"/workspaces/{other_workspace}/job-descriptions/{jd_id}/turns/{turn_id}:restore",
                f"/workspaces/{workspace_id}/job-descriptions/{other_jd.job_description_id}/turns/{turn_id}:restore",
            )
            for path in missing_paths:
                rejected = await client.post(path)
                assert rejected.status_code == 404, rejected.text
                assert rejected.json()["detail"] == {
                    "code": "jd_turn_not_found",
                    "commit_status": "not_committed",
                }
            assert (await client.get(prefix)).json() == edited.json()

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)


@pytest.mark.parametrize(
    "same_turn_correlation", [False, True], ids=["human", "late-same-turn"]
)
def test_first_completed_restore_rejects_newer_saved_work_without_changing_history(
    pg_engine: Engine, checkpoint_conninfo: str, same_turn_correlation: bool
) -> None:
    requests: list[dict[str, Any]] = []

    def respond(request: httpx2.Request) -> httpx2.Response:
        body = request_body(request)
        requests.append(body)
        output = None
        if len(requests) == 1:
            output = [read_call("map", "map")]
        elif len(requests) == 2:
            output = [call("create_jd_task", "create", '{"name":"已完成輪的新任務"}')]
        else:
            assert len(requests) == 3
            assert tool_outputs(body)["create"]["status"] == "created"
        return sse_response(EventStream(response_events(response_payload(output))))

    async def run() -> None:
        async with api_client(
            pg_engine,
            checkpoint_conninfo,
            httpx2.MockTransport(respond),
            bundles=(BundleConfig("caliburn.bundles.job_description"),),
        ) as client:
            workspace_id, initial = await create_workspace_jd(client)
            prefix = (
                f"/workspaces/{workspace_id}/job-descriptions/"
                f"{initial.job_description_id}"
            )
            turn_id = uuid4()
            accepted = await client.post(
                f"/workspaces/{workspace_id}/agent/turns",
                json={"turn_id": str(turn_id), "input": "建立任務後完成"},
            )
            assert accepted.status_code == 202, accepted.text
            turn_location = accepted.headers["Location"]
            completed = await wait_for_idle(client, turn_location)
            assert completed["status"] == "completed"
            changes_path = prefix + f"/turns/{turn_id}/changes"
            changes = (await client.get(changes_path)).json()
            assert changes["after_version"] == initial.version + 1
            later_input = {
                "expected_version": changes["after_version"],
                "purpose": "完成後保存的內容",
                **({"correlation_id": str(turn_id)} if same_turn_correlation else {}),
            }
            edited = await client.patch(prefix, json=later_input)
            assert edited.status_code == 200, edited.text
            history = (await client.get(prefix + "/history")).json()
            checkpoints = await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
            rejected = await client.post(prefix + f"/turns/{turn_id}:restore")
            assert rejected.status_code == 409, rejected.text
            assert rejected.json()["detail"]["code"] == "jd_concurrency_conflict"
            assert rejected.json()["detail"]["commit_status"] == "not_committed"
            assert (await client.get(prefix)).json() == edited.json()
            assert (await client.get(prefix + "/history")).json() == history
            assert (await client.get(changes_path)).json() == changes
            assert (await client.get(turn_location)).json() == completed
            assert (
                await checkpoint_ids(checkpoint_conninfo, turn_id=turn_id)
                == checkpoints
            )
            assert len(requests) == 3

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
