"""真 Host／PG／SDK 往返；模型離線，Qdrant 使用記憶體模式。"""

import asyncio
import json
import re
from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager, closing
from uuid import UUID, uuid4

import httpx2
import pytest
from langgraph.checkpoint.memory import InMemorySaver
from qdrant_client import QdrantClient
from sqlalchemy import Engine

import caliburn.host.app as host
from caliburn.host.agent_settings import AgentConfiguration
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
    openai_checkpoint_serializer,
)
from caliburn.modules.model_references.contracts import ReferenceTarget
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.configuration import ReferenceConfiguration
from caliburn.modules.occupation_reference.infrastructure.execution import (
    RetrievalWorker,
)
from caliburn.modules.occupation_reference.infrastructure.qdrant.store import (
    QdrantReferenceStore,
    index_references,
)
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.reference_configuration import HOST_REFERENCE_CONFIGURATION
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    call,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)
from tests.unit.modules.occupation_reference.source_support import (
    FixedEmbedder,
    FixedReranker,
    source_document,
)

pytestmark = pytest.mark.filterwarnings("ignore:Payload indexes have no effect")


def agent_configuration(
    respond: Callable[[httpx2.Request], httpx2.Response],
    *,
    checkpoint_conninfo: str = "offline",
) -> AgentConfiguration:
    return AgentConfiguration(
        agent_id="reference-test",
        resume_version="reference-read-v2",
        checkpoint_conninfo=checkpoint_conninfo,
        model_settings=MODEL_REQUEST,
        bundles=(BundleConfig("caliburn.bundles.job_reference"),),
        client_factory=lambda: offline_client(httpx2.MockTransport(respond)),
    )


@pytest.mark.filterwarnings("error:Pydantic serializer warnings:UserWarning")
def test_host_shares_reference_resources_for_sdk_tools_and_http(
    monkeypatch: pytest.MonkeyPatch,
    pg_engine: Engine,
    jd_workspace_id: UUID,
    checkpoint_conninfo: str,
) -> None:
    document = source_document()
    sent = []
    model_calls = []
    lifetime = []
    query = "  維護網頁與資料串接  "
    model_reference_id = ""

    def respond(request: httpx2.Request) -> httpx2.Response:
        nonlocal model_reference_id
        sent.append(request_body(request))
        if len(sent) == 2:
            search_reply = next(
                json.loads(item["output"])
                for item in sent[-1]["input"]
                if item.get("type") == "function_call_output"
                and item["call_id"] == "search"
            )
            model_reference_id = search_reply["references"][0]["reference_id"]
            assert re.fullmatch(r"occupation_[1-9][0-9]*", model_reference_id)
            assert document.reference_id not in json.dumps(search_reply)
        outputs = [
            [
                call(
                    "search_occupation_references",
                    "search",
                    json.dumps({"query": query}),
                )
            ],
            [
                call(
                    "read_occupation_reference",
                    "catalog",
                    json.dumps({"reference_id": model_reference_id, "task_id": None}),
                )
            ],
            [
                call(
                    "read_occupation_reference",
                    "task",
                    json.dumps(
                        {"reference_id": model_reference_id, "task_id": "u1-t1"}
                    ),
                )
            ],
            None,
        ]
        output = outputs[len(sent) - 1]
        if output is not None:
            model_calls.extend(output)
        return sse_response(EventStream(response_events(response_payload(output))))

    @asynccontextmanager
    async def references(
        config: ReferenceConfiguration,
    ) -> AsyncIterator[tuple[ReferenceSearch, RetrievalWorker]]:
        assert config.collection == "reference_test"
        embedder = FixedEmbedder()
        with closing(QdrantClient(":memory:")) as database:
            index_references(database, config.collection, [document], embedder)
            service = ReferenceSearch(
                QdrantReferenceStore(database, config.collection, embedder.signature),
                embedder,
                FixedReranker(),
            )
            worker = RetrievalWorker()
            try:
                yield service, worker
            finally:
                await worker.aclose()
                lifetime.append("reference_closed")

    monkeypatch.setattr(host, "open_reference", references)

    async def run() -> None:
        async with open_postgres_checkpointer(checkpoint_conninfo, initialize=True):
            pass
        app = host.build_app(
            database_url=pg_engine.url.render_as_string(hide_password=False),
            agent_configuration=agent_configuration(
                respond, checkpoint_conninfo=checkpoint_conninfo
            ),
            reference_configuration=ReferenceConfiguration(collection="reference_test"),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url="http://testserver"
            ) as client,
        ):
            created = await client.post(
                f"/workspaces/{jd_workspace_id}/agent/turns",
                json={"turn_id": str(uuid4()), "input": "查閱已確認的工作參考"},
            )
            assert created.status_code == 202, created.text
            async with asyncio.timeout(15):
                while True:
                    turn = (await client.get(created.headers["Location"])).json()
                    if turn["status"] != "running":
                        break
                    await asyncio.sleep(0.01)
            assert turn["status"] == "completed", turn
            catalog = (
                await client.get(f"/occupation-references/{document.reference_id}")
            ).json()
            detail = (
                await client.get(
                    f"/occupation-references/{document.reference_id}/tasks/u1-t1"
                )
            ).json()

        declarations = {tool["name"]: tool for tool in sent[0]["tools"]}
        assert set(declarations) == {
            "search_occupation_references",
            "read_occupation_reference",
        }
        for tool in declarations.values():
            assert tool["strict"] is True
            assert tool["parameters"]["additionalProperties"] is False
        assert set(
            declarations["search_occupation_references"]["parameters"]["properties"]
        ) == {"query"}
        assert declarations["read_occupation_reference"]["parameters"]["required"] == [
            "reference_id",
            "task_id",
        ]
        assert [
            item for item in sent[-1]["input"] if item.get("type") == "function_call"
        ] == model_calls
        replies = {
            item["call_id"]: json.loads(item["output"])
            for item in sent[-1]["input"]
            if item.get("type") == "function_call_output"
        }
        assert catalog["reference_id"] == document.reference_id
        assert detail["reference_id"] == document.reference_id
        model_catalog: dict[str, object] = {
            "reference_id": model_reference_id,
            "source_sha256": document.source_sha256,
            "source_file": "selected.json",
            "ocs_code": "OC1",
            "title": "職位標題",
            "overview": "工作內容## 網頁服務",
            "category": {"job_categories": [], "occupations": [], "industries": []},
            "ocs_level": None,
            "attitudes": [],
            "notes": {"prerequisites": [], "supplements": []},
            "catalog_scope": "all_parsed_task_groups",
            "units": [
                {
                    "unit_id": "u1",
                    "name": "開發",
                    "tasks": [
                        {
                            "task_id": "u1-t1",
                            "names": [
                                {"name": "介面製作"},
                                {"name": "流程整合"},
                                {"name": "資料串接"},
                            ],
                            "competency_block_count": 2,
                        },
                        {
                            "task_id": "u1-t2",
                            "names": [{"name": "測試"}],
                            "competency_block_count": 0,
                        },
                        {
                            "task_id": "u1-t3",
                            "names": [],
                            "competency_block_count": 0,
                        },
                    ],
                }
            ],
        }
        assert replies["search"] == {"references": [model_catalog]}
        assert replies["catalog"] == model_catalog
        assert replies["task"] == {
            "reference_id": model_reference_id,
            "source_sha256": document.source_sha256,
            "task_id": "u1-t1",
            "unit_id": "u1",
            "names": [
                {"name": "介面製作"},
                {"name": "流程整合"},
                {"name": "資料串接"},
            ],
            "competency_blocks": [
                {
                    "competency_level": None,
                    "outputs": [{"name": "網頁"}],
                    "indicators": [{"text": "顯示資料"}],
                    "knowledge": [{"name": "工程識圖"}],
                    "skills": [{"name": "資料閱讀"}],
                },
                {
                    "competency_level": None,
                    "outputs": [{"name": "無碼產出"}],
                    "indicators": [],
                    "knowledge": [],
                    "skills": [],
                },
            ],
            "notes": {"prerequisites": [], "supplements": []},
        }
        assert document.reference_id not in json.dumps(replies)
        assert catalog["overview"] == "工作內容\n## 網頁服務"
        assert catalog["units"][0]["code"] == "U1"
        assert (
            catalog["units"][0]["tasks"][0]["names"]
            == detail["names"]
            == [
                {"code": "T1", "name": "介面製作"},
                {"code": "T2", "name": "流程整合"},
                {"code": None, "name": "資料串接"},
            ]
        )
        assert detail["competency_blocks"][0]["outputs"] == [
            {"code": "O1", "name": "O1 網頁"}
        ]
        assert detail["competency_blocks"][0]["indicators"] == [
            {"code": "P1", "text": "P1 顯示資料"}
        ]
        assert len(catalog["units"][0]["tasks"]) == 3
        assert len(detail["names"]) == 3
        assert len(detail["competency_blocks"]) == 2
        assert "retrieval_policy" not in replies["search"]
        persisted = SqlAlchemyModelReferences(create_session_factory(pg_engine))
        assert persisted.resolve_refs(jd_workspace_id, [model_reference_id]) == {
            model_reference_id: ReferenceTarget(
                "occupation", UUID(document.reference_id)
            )
        }

        # 關閉 Agent 後，模組仍可由同一 Host 獨立開啟及查讀。
        reader_app = host.build_app(
            database_url=pg_engine.url.render_as_string(hide_password=False),
            reference_configuration=ReferenceConfiguration(collection="reference_test"),
        )
        async with (
            reader_app.router.lifespan_context(reader_app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(reader_app), base_url="http://testserver"
            ) as reader,
        ):
            assert (
                await reader.get(f"/occupation-references/{document.reference_id}")
            ).json() == catalog

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
    assert lifetime == ["reference_closed", "reference_closed"]


def test_enabled_reference_bundle_starts_with_lazy_reference_resources(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    @asynccontextmanager
    async def checkpoints(conninfo: str) -> AsyncIterator[InMemorySaver]:
        yield InMemorySaver(serde=openai_checkpoint_serializer())

    def unexpected(request: httpx2.Request) -> httpx2.Response:
        raise AssertionError("startup must not call the model")

    monkeypatch.setattr(host, "open_postgres_checkpointer", checkpoints)

    async def run() -> None:
        app = host.build_app(
            reference_configuration=HOST_REFERENCE_CONFIGURATION,
            database_url="postgresql+psycopg://localhost:1/offline",
            agent_configuration=agent_configuration(unexpected),
        )
        async with (
            app.router.lifespan_context(app),
            httpx2.AsyncClient(
                transport=httpx2.ASGITransport(app), base_url="http://testserver"
            ) as client,
        ):
            response = await client.get("/openapi.json")
            assert response.status_code == 200
            assert "/occupation-references:search" in response.json()["paths"]

    asyncio.run(run(), loop_factory=asyncio.SelectorEventLoop)
