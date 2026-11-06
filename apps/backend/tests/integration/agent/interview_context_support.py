"""訪談 Context 驗收的真 PG 接線與離線模型觀察邊界。"""

import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from functools import partial
from typing import Any

import httpx2
from sqlalchemy import Engine

from caliburn.bundles.interview.services import (
    INTERVIEW_QUERIES,
    INTERVIEW_UOW_FACTORY,
    MODEL_REFERENCES,
)
from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig, open_agent
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.model_references import ModelReferences
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.shared.infrastructure.persistence.database import create_session_factory
from tests.unit.modules.agent.offline_openai import (
    MODEL_REQUEST,
    EventStream,
    offline_client,
    request_body,
    response_events,
    response_payload,
    sse_response,
)


@dataclass
class ScriptedInterviewModel:
    batches: list[list[dict[str, object]] | None]
    requests: list[dict[str, Any]] = field(default_factory=list)

    def __call__(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(request_body(request))
        output = self.batches[len(self.requests) - 1]
        return sse_response(EventStream(response_events(response_payload(output))))


def context_messages(request: dict[str, Any]) -> list[dict[str, Any]]:
    """只在實際 SDK JSON 邊界解開具來源標識的訪談材料。"""
    result = []
    for item in request["input"]:
        content = item.get("content")
        if item.get("role") != "user" or not isinstance(content, str):
            continue
        try:
            material = json.loads(content)
        except json.JSONDecodeError:
            continue
        if isinstance(material, dict) and material.get("source") == "interview":
            result.extend(material["messages"])
    return result


@asynccontextmanager
async def open_interview_agent(
    pg_engine: Engine,
    checkpoint_conninfo: str,
    transport: httpx2.MockTransport,
    *,
    agent_id: str = "interview-context",
    initialize: bool = True,
    context: bool = True,
    recording: bool = True,
    queries: InterviewQueries | None = None,
    references: ModelReferences | None = None,
    extra_bundles: tuple[BundleConfig, ...] = (),
) -> AsyncIterator[Agent]:
    sessions = create_session_factory(pg_engine)
    async with (
        open_postgres_checkpointer(checkpoint_conninfo, initialize=initialize) as saver,
        offline_client(transport) as client,
        open_agent(
            agent_id=agent_id,
            resume_version="context-v1",
            client=client,
            model_settings=MODEL_REQUEST,
            bundles=(
                BundleConfig(
                    "caliburn.bundles.interview",
                    plugins=(
                        *(("interview",) if recording else ()),
                        *(("interview_context",) if context else ()),
                        "interview_source_prompt",
                        "interview_read",
                        "interview_navigation",
                    ),
                ),
                *extra_bundles,
            ),
            external_services=(
                MODEL_REFERENCES.bind(
                    references
                    if references is not None
                    else SqlAlchemyModelReferences(sessions)
                ),
                INTERVIEW_UOW_FACTORY.bind(
                    partial(SqlAlchemyInterviewUnitOfWork, sessions)
                ),
                INTERVIEW_QUERIES.bind(
                    queries
                    if queries is not None
                    else SqlAlchemyInterviewQueries(pg_engine)
                ),
            ),
            checkpointer=saver,
        ) as agent,
    ):
        yield agent
