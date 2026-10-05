"""Reference tools keep excluded work separate from search across qualified Turns.

The shared fixture settles formal exchange and execution in one transaction. Exclusions
carry text only; this tests storage and transport, not employee interpretation or model behavior.
"""

import json
from uuid import uuid4

import httpx2
import pytest
from fastapi.testclient import TestClient

from caliburn.adapters.occupation_references import OccupationReferenceClient
from caliburn.features.executions.models import ExecutionStatus
from caliburn.transport.model_tools.occupation_references import OccupationReferenceTools
from caliburn.workflows.occupation_references import OccupationReferenceWorkflow
from tests.integration.test_occupation_reference_workflow import finish, new_writer
from tests.unit.test_occupation_reference_client import (
    REFERENCE_ID,
    reference_payload,
    search_payload,
    task_payload,
)

pytestmark = pytest.mark.postgres


@pytest.mark.parametrize("result_format", ["state", "status"])
def test_reference_tools_persist_excluded_work_replay_and_keep_search_input_separate(
    client: TestClient,
    result_format,
) -> None:
    writer = new_writer(client)
    sessions = client.app.state.database.sessions
    requests: list[tuple[str, str]] = []
    selected_state = {"selected_reference_ids": [REFERENCE_ID], "excluded_work": []}
    excluded_state = {
        "selected_reference_ids": [REFERENCE_ID],
        "excluded_work": ["不負責正式部署"],
    }

    def respond(request: httpx2.Request) -> httpx2.Response:
        requests.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/occupation-references:search":
            assert json.loads(request.content) == {"query": "本人負責功能開發", "limit": 5}
            return httpx2.Response(200, json=search_payload())
        if request.method == "GET":
            if request.url.path == f"/occupation-references/{REFERENCE_ID}":
                return httpx2.Response(200, json=reference_payload())
            if request.url.path == f"/occupation-references/{REFERENCE_ID}/tasks/u1-t1":
                return httpx2.Response(200, json=task_payload())
        raise AssertionError(f"Unexpected reference request: {request.method} {request.url.path}")

    async def use_catalog_and_exclude_work() -> tuple[
        dict[str, object], str, dict[str, object], str
    ]:
        async with httpx2.AsyncClient(
            base_url="http://references.invalid", transport=httpx2.MockTransport(respond)
        ) as http:
            provider = OccupationReferenceClient(http)
            workflow = OccupationReferenceWorkflow(sessions, provider)
            await workflow.start(writer)
            tools = OccupationReferenceTools(
                workflow,
                provider,
                writer,
                write_result_format=result_format,
            )
            assert json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == {
                "selected_reference_ids": None,
                "excluded_work": [],
            }

            found = json.loads(
                await tools.invoke(
                    "search_occupation_references", json.dumps({"query": "本人負責功能開發"})
                )
            )
            assert set(found) == {"references"}
            catalog = found["references"][0]
            assert catalog["reference_id"] == REFERENCE_ID
            assert catalog["overview"] == "完整概述\n第二行"
            assert [task["task_id"] for task in catalog["units"][0]["tasks"]] == [
                "u1-t1",
                "u1-t2",
            ]

            # An unselected reference remains readable when its title is insufficient.
            task = json.loads(
                await tools.invoke(
                    "read_occupation_reference",
                    json.dumps({"reference_id": REFERENCE_ID, "task_id": "u1-t1"}),
                )
            )
            assert task["reference_id"] == REFERENCE_ID
            assert task["competency_blocks"][0]["indicators"] == [
                {"code": "P1", "text": "完整指標\n第二行"}
            ]
            assert (
                json.loads(await tools.invoke("read_occupation_reference_state", "{}"))[
                    "selected_reference_ids"
                ]
                is None
            )

            prepared = await tools.prepare(
                "select_occupation_references",
                json.dumps({"reference_ids": [REFERENCE_ID]}),
                uuid4(),
            )
            assert isinstance(prepared, dict)
            selection = json.loads(json.dumps(prepared))
            selected_result = await tools.execute(selection)
            assert json.loads(selected_result) == (
                selected_state if result_format == "state" else {"status": "updated"}
            )
            assert json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == (
                selected_state
            )

            prepared_exclusion = await tools.prepare(
                "update_excluded_work",
                json.dumps(
                    {
                        "add": ["不負責正式部署"],
                        "remove": [],
                    }
                ),
                uuid4(),
            )
            assert isinstance(prepared_exclusion, dict)
            exclusion = json.loads(json.dumps(prepared_exclusion))
            excluded_result = await tools.execute(exclusion)
            assert json.loads(excluded_result) == (
                excluded_state if result_format == "state" else {"status": "updated"}
            )
            assert json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == (
                excluded_state
            )
            # The HTTP fixture checks the exact positive query again after exclusion exists.
            found_again = json.loads(
                await tools.invoke(
                    "search_occupation_references", json.dumps({"query": "本人負責功能開發"})
                )
            )
            assert found_again == found
            assert json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == (
                excluded_state
            )
            return selection, selected_result, exclusion, excluded_result

    selection, selected_result, exclusion, excluded_result = client.portal.call(
        use_catalog_and_exclude_work
    )
    assert requests == [
        ("POST", "/occupation-references:search"),
        ("GET", f"/occupation-references/{REFERENCE_ID}/tasks/u1-t1"),
        ("GET", f"/occupation-references/{REFERENCE_ID}"),
        ("POST", "/occupation-references:search"),
    ]
    offline_requests: list[str] = []

    def unavailable(request: httpx2.Request) -> httpx2.Response:
        offline_requests.append(request.url.path)
        assert request.method == "POST"
        assert request.url.path == "/occupation-references:search"
        assert json.loads(request.content) == {"query": "本人負責功能開發", "limit": 5}
        return httpx2.Response(503, json={"detail": "Reference service unavailable"})

    async def replay_with_rebuilt_tools() -> None:
        async with httpx2.AsyncClient(
            base_url="http://references.invalid", transport=httpx2.MockTransport(unavailable)
        ) as http:
            provider = OccupationReferenceClient(http)
            workflow = OccupationReferenceWorkflow(sessions, provider)
            await workflow.start(writer)
            tools = OccupationReferenceTools(
                workflow,
                provider,
                writer,
                write_result_format=result_format,
            )
            # Original selection replay cannot discard a later exclusion or requery RAG.
            assert await tools.execute(json.loads(json.dumps(selection))) == selected_result
            assert await tools.execute(json.loads(json.dumps(exclusion))) == excluded_result
            assert json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == (
                excluded_state
            )

    client.portal.call(replay_with_rebuilt_tools)
    assert offline_requests == []
    finish(client, writer, ExecutionStatus.COMPLETED)
    next_writer = new_writer(client, writer.scope.job_file_id)

    async def read_and_remove_excluded_work_after_recreation() -> None:
        async with httpx2.AsyncClient(
            base_url="http://references.invalid", transport=httpx2.MockTransport(unavailable)
        ) as http:
            provider = OccupationReferenceClient(http)
            workflow = OccupationReferenceWorkflow(sessions, provider)
            await workflow.start(next_writer)
            tools = OccupationReferenceTools(
                workflow,
                provider,
                next_writer,
                write_result_format=result_format,
            )
            expected = {
                "selected_reference_ids": [REFERENCE_ID],
                "excluded_work": ["不負責正式部署"],
            }
            assert (
                json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == expected
            )
            # A real service failure is neither empty search success nor an empty selection.
            rejected_search = json.loads(
                await tools.invoke(
                    "search_occupation_references", json.dumps({"query": "本人負責功能開發"})
                )
            )
            assert rejected_search["status"] == "rejected"
            assert rejected_search["code"] == "reference_service_unavailable"
            assert (
                json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == expected
            )
            # Removing an exclusion makes that scope available for asking again; no status
            # or employee-source record is generated, and the selected references remain.
            removal = await tools.prepare(
                "update_excluded_work",
                json.dumps(
                    {
                        "add": [],
                        "remove": ["不負責正式部署"],
                    }
                ),
                uuid4(),
            )
            assert isinstance(removal, dict)
            result = await tools.execute(json.loads(json.dumps(removal)))
            assert json.loads(result) == (
                selected_state if result_format == "state" else {"status": "updated"}
            )
            assert json.loads(await tools.invoke("read_occupation_reference_state", "{}")) == (
                selected_state
            )

    client.portal.call(read_and_remove_excluded_work_after_recreation)
    assert offline_requests == ["/occupation-references:search"]
