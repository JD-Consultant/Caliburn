"""以明示角色組裝建立 Memory 背景協調器。"""

from collections.abc import Callable, Sequence
from contextlib import AbstractAsyncContextManager
from copy import deepcopy
from dataclasses import replace
from typing import Any
from uuid import UUID

from langgraph.checkpoint.base import BaseCheckpointSaver
from openai import AsyncOpenAI
from openai.types.responses.response_create_params import ResponseCreateParamsBase

from caliburn.bundles.memory.coordinator import (
    MemoryAnalysisCoordinator,
    open_memory_role_agent,
)
from caliburn.bundles.memory.services import MemoryCoordinatorFactory
from caliburn.modules.agent.agent import Agent
from caliburn.modules.agent.bootstrap import BundleConfig
from caliburn.modules.agent.plugins.contracts import AgentBundle
from caliburn.modules.interview.application.persistence import InterviewQueries
from caliburn.modules.memory.application.persistence import (
    MemoryQueries,
    MemoryUnitOfWork,
)
from caliburn.modules.memory.application.service import MemoryService
from caliburn.modules.memory.domain.items import MemoryKind
from caliburn.modules.model_references import ModelReferences


def create_coordinator_factory(
    *,
    situation_bundles: Sequence[BundleConfig | AgentBundle] | None = None,
    understanding_bundles: Sequence[BundleConfig | AgentBundle] | None = None,
    max_tool_result_characters: int = 1_000_000,
    max_context_characters: int = 1_000_000,
) -> MemoryCoordinatorFactory:
    """固定角色設定；預設採內建 Memory 與 160K 原生壓縮，明示組裝完整替換。"""
    role_bundles: dict[MemoryKind, Sequence[BundleConfig | AgentBundle] | None] = {
        "situation": situation_bundles,
        "understanding": understanding_bundles,
    }
    for role, bundles in role_bundles.items():
        if bundles is None:
            bundles = (
                BundleConfig(
                    "caliburn.bundles.memory",
                    {
                        "role": role,
                        "max_tool_result_characters": max_tool_result_characters,
                        "max_context_characters": max_context_characters,
                    },
                ),
                BundleConfig(
                    "caliburn.bundles.context", plugins=("native_compaction",)
                ),
            )
        role_bundles[role] = tuple(
            replace(bundle, config=deepcopy(bundle.config))
            if isinstance(bundle, BundleConfig)
            else bundle
            for bundle in bundles
        )

    def create(
        *,
        consultant: Agent,
        client: AsyncOpenAI,
        model_settings: ResponseCreateParamsBase,
        checkpointer: BaseCheckpointSaver[Any],
        agent_id: str,
        resume_version: str,
        queries: MemoryQueries,
        interview_queries: InterviewQueries,
        uow_factory: Callable[[], MemoryUnitOfWork],
        references: ModelReferences,
    ) -> MemoryAnalysisCoordinator:
        def open_role(
            *, role: MemoryKind, analysis_id: UUID, memory_service: MemoryService
        ) -> AbstractAsyncContextManager[Agent]:
            return open_memory_role_agent(
                agent_id=agent_id,
                resume_version=resume_version,
                client=client,
                model_settings=model_settings,
                checkpointer=checkpointer,
                queries=queries,
                references=references,
                role=role,
                analysis_id=analysis_id,
                memory_service=memory_service,
                bundles=role_bundles[role],
            )

        return MemoryAnalysisCoordinator(
            consultant=consultant,
            interview_queries=interview_queries,
            queries=queries,
            uow_factory=uow_factory,
            open_role_agent=open_role,
        )

    return create
