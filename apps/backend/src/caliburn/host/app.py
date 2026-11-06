"""組裝儲存資源與 HTTP 應用，集中管理 Engine 生命週期。"""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial
from uuid import UUID

from fastapi import APIRouter, FastAPI, HTTPException

from caliburn.bundles.interview.services import (
    INTERVIEW_UOW_FACTORY,
)
from caliburn.bundles.job_description.services import (
    JD_CITATION_SOURCES,
    JD_HISTORY_QUERIES,
    JD_MEMORY_QUERIES,
    JD_QUERIES,
    JD_REFERENCES,
    JD_UOW_FACTORY,
)
from caliburn.bundles.job_reference.services import (
    REFERENCE_IDS,
    REFERENCE_RUNNER,
    REFERENCE_SEARCH,
)
from caliburn.bundles.plan.services import PLAN_QUERIES, PLAN_UOW_FACTORY
from caliburn.host.agent_settings import AgentConfiguration
from caliburn.host.consultant import start_consultant
from caliburn.host.web import health
from caliburn.host.workspaces import (
    SqlAlchemyWorkspaceInitialization,
    WorkspaceDeletion,
)
from caliburn.modules.agent.application.agent_service import AgentService
from caliburn.modules.agent.infrastructure.persistence.postgres_checkpointer import (
    open_postgres_checkpointer,
)
from caliburn.modules.agent.presentation.api.event_schema import (
    install_agent_event_schema,
)
from caliburn.modules.agent.presentation.api.router import build_agent_router
from caliburn.modules.human_questions.api import (
    PUBLIC_VALIDATION_FIELDS as QUESTION_VALIDATION_FIELDS,
)
from caliburn.modules.human_questions.api import build_question_router
from caliburn.modules.human_questions.question_service import QuestionService
from caliburn.modules.interview.infrastructure.persistence.queries import (
    SqlAlchemyInterviewQueries,
)
from caliburn.modules.interview.infrastructure.persistence.unit_of_work import (
    SqlAlchemyInterviewUnitOfWork,
)
from caliburn.modules.interview.presentation.api.router import build_interview_router
from caliburn.modules.job_description.application.turn_history import (
    CompletedTurnReader,
    JobDescriptionTurnVersions,
)
from caliburn.modules.job_description.infrastructure.pdf_renderer import (
    PdfConfiguration,
    PdfRenderer,
)
from caliburn.modules.job_description.infrastructure.persistence import (
    citation_sources,
)
from caliburn.modules.job_description.infrastructure.persistence.queries import (
    SqlAlchemyJobDescriptionQueries,
)
from caliburn.modules.job_description.infrastructure.persistence.unit_of_work import (
    SqlAlchemyJobDescriptionUnitOfWork,
)
from caliburn.modules.job_description.presentation.api.router import (
    build_job_description_router,
)
from caliburn.modules.job_description.presentation.api.routes.export import (
    build_export_router,
)
from caliburn.modules.job_description.presentation.api.schemas import (
    PUBLIC_VALIDATION_FIELDS as JD_VALIDATION_FIELDS,
)
from caliburn.modules.memory.infrastructure.persistence.queries import (
    SqlAlchemyMemoryQueries,
)
from caliburn.modules.memory.infrastructure.persistence.unit_of_work import (
    SqlAlchemyMemoryUnitOfWork,
)
from caliburn.modules.memory.presentation.api.router import build_memory_router
from caliburn.modules.model_references.persistence import SqlAlchemyModelReferences
from caliburn.modules.occupation_reference.application.errors import (
    ReferenceUnavailableError,
)
from caliburn.modules.occupation_reference.application.execution import SearchRunner
from caliburn.modules.occupation_reference.application.search import ReferenceSearch
from caliburn.modules.occupation_reference.bootstrap import open_reference
from caliburn.modules.occupation_reference.configuration import ReferenceConfiguration
from caliburn.modules.occupation_reference.presentation.api.router import (
    build_reference_router,
)
from caliburn.modules.plan.infrastructure.persistence.queries import (
    SqlAlchemyPlanQueries,
)
from caliburn.modules.plan.infrastructure.persistence.unit_of_work import (
    SqlAlchemyPlanUnitOfWork,
)
from caliburn.modules.plan.presentation.api.router import build_plan_router
from caliburn.modules.workspace.application.lifecycle import create_workspace
from caliburn.modules.workspace.application.workspace_service import WorkspaceService
from caliburn.modules.workspace.infrastructure.persistence.unit_of_work import (
    SqlAlchemyWorkspaceUnitOfWork,
)
from caliburn.modules.workspace.presentation.api.router import build_workspace_router
from caliburn.modules.workspace.presentation.api.schemas import (
    PUBLIC_VALIDATION_FIELDS,
)
from caliburn.shared.infrastructure.persistence.database import (
    create_database_engine,
    create_session_factory,
)
from caliburn.shared.presentation.api.app import build_http_app


def build_app(
    *,
    database_url: str,
    reference_configuration: ReferenceConfiguration,
    agent_configuration: AgentConfiguration | None = None,
    checkpoint_conninfo: str | None = None,
    pdf_configuration: PdfConfiguration | None = None,
) -> FastAPI:
    engine = create_database_engine(database_url)
    session_factory = create_session_factory(engine)

    workspace_uow_factory = partial(SqlAlchemyWorkspaceUnitOfWork, session_factory)
    jd_uow_factory = partial(SqlAlchemyJobDescriptionUnitOfWork, session_factory)
    interview_uow_factory = partial(SqlAlchemyInterviewUnitOfWork, session_factory)
    plan_uow_factory = partial(SqlAlchemyPlanUnitOfWork, session_factory)
    memory_uow_factory = partial(SqlAlchemyMemoryUnitOfWork, session_factory)

    agent_service: AgentService | None = None
    reference_service: ReferenceSearch | None = None
    reference_runner: SearchRunner | None = None
    workspace_deletion: WorkspaceDeletion | None = None
    completed_jd_turn_reader: CompletedTurnReader | None = None

    async def completed_jd_turn(
        *, workspace_id: UUID, turn_id: UUID
    ) -> JobDescriptionTurnVersions | None:
        if completed_jd_turn_reader is None:
            raise HTTPException(503, detail={"code": "agent_unavailable"})
        return await completed_jd_turn_reader(
            workspace_id=workspace_id, turn_id=turn_id
        )

    async def delete_workspace_contents(workspace_id: UUID) -> None:
        if workspace_deletion is None:
            raise HTTPException(503, detail={"code": "workspace_deletion_unavailable"})
        await workspace_deletion.delete(workspace_id)

    def get_reference_service() -> ReferenceSearch:
        if reference_service is None:
            raise ReferenceUnavailableError("reference resources are not started")
        return reference_service

    def get_reference_runner() -> SearchRunner:
        if reference_runner is None:
            raise ReferenceUnavailableError("reference resources are not started")
        return reference_runner

    def get_agent_service() -> AgentService:
        if agent_service is None:
            raise HTTPException(503, detail={"code": "agent_unavailable"})
        return agent_service

    def get_question_service() -> QuestionService:
        return QuestionService(get_agent_service())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        nonlocal agent_service, reference_service, reference_runner, workspace_deletion
        nonlocal completed_jd_turn_reader
        try:
            async with AsyncExitStack() as stack:
                if pdf_renderer is not None:
                    stack.push_async_callback(pdf_renderer.aclose)
                saver = None
                memory_host = None
                reference, runner = await stack.enter_async_context(
                    open_reference(reference_configuration)
                )
                reference_service, reference_runner = reference, runner
                checkpoint_connection = (
                    agent_configuration.checkpoint_conninfo
                    if agent_configuration is not None
                    else checkpoint_conninfo
                )
                if checkpoint_connection is not None:
                    saver = await stack.enter_async_context(
                        open_postgres_checkpointer(checkpoint_connection)
                    )
                if agent_configuration is not None:
                    assert saver is not None
                    (
                        agent_service,
                        memory_host,
                        completed_jd_turn_reader,
                    ) = await start_consultant(
                        stack,
                        config=agent_configuration,
                        checkpointer=saver,
                        workspaces=workspace_service,
                        interview_queries=interview_queries,
                        memory_queries=memory_queries,
                        memory_uow_factory=memory_uow_factory,
                        references=model_references,
                        services=(
                            INTERVIEW_UOW_FACTORY.bind(interview_uow_factory),
                            JD_QUERIES.bind(jd_queries),
                            JD_HISTORY_QUERIES.bind(jd_queries),
                            JD_UOW_FACTORY.bind(jd_uow_factory),
                            JD_REFERENCES.bind(model_references),
                            JD_MEMORY_QUERIES.bind(memory_queries),
                            JD_CITATION_SOURCES.bind(jd_citation_sources),
                            PLAN_QUERIES.bind(plan_queries),
                            PLAN_UOW_FACTORY.bind(plan_uow_factory),
                            REFERENCE_IDS.bind(model_references),
                            REFERENCE_SEARCH.bind(reference),
                            REFERENCE_RUNNER.bind(runner),
                        ),
                    )
                workspace_deletion = WorkspaceDeletion(
                    workspaces=workspace_service,
                    checkpointer=saver,
                    agent=agent_service,
                    memory=memory_host,
                )
                stack.push_async_callback(workspace_deletion.aclose)
                try:
                    yield
                finally:
                    agent_service = None
                    reference_service = None
                    reference_runner = None
                    workspace_deletion = None
                    completed_jd_turn_reader = None
        finally:
            engine.dispose()

    try:
        workspace_service = WorkspaceService(workspace_uow_factory)
        jd_queries = SqlAlchemyJobDescriptionQueries(engine)
        jd_citation_sources = citation_sources.SqlAlchemyCitationSourceQueries(engine)
        interview_queries = SqlAlchemyInterviewQueries(engine)
        plan_queries = SqlAlchemyPlanQueries(engine)
        memory_queries = SqlAlchemyMemoryQueries(engine)
        model_references = SqlAlchemyModelReferences(session_factory)
        pdf_renderer = (
            PdfRenderer(
                font_path=pdf_configuration.font_path,
                executable_path=pdf_configuration.executable_path,
            )
            if pdf_configuration is not None
            else None
        )
        router = APIRouter()

        router.add_api_route("/health", health, tags=["system"])
        router.include_router(
            build_reference_router(get_reference_service, get_reference_runner)
        )
        router.include_router(build_agent_router(get_agent_service))
        router.include_router(build_question_router(get_question_service))
        router.include_router(build_interview_router(interview_queries))
        router.include_router(
            build_workspace_router(
                workspace_service,
                create_workspace=partial(
                    create_workspace,
                    uow_factory=partial(
                        SqlAlchemyWorkspaceInitialization, session_factory
                    ),
                ),
                delete_workspace=delete_workspace_contents,
            )
        )
        router.include_router(build_plan_router(plan_queries))
        router.include_router(build_memory_router(memory_queries))
        router.include_router(
            build_export_router(queries=jd_queries, renderer=pdf_renderer)
        )
        router.include_router(
            build_job_description_router(
                uow_factory=jd_uow_factory,
                queries=jd_queries,
                history_queries=jd_queries,
                citation_sources=jd_citation_sources,
                memory_queries=memory_queries,
                completed_turn_reader=completed_jd_turn,
            )
        )
        app = build_http_app(
            router,
            title="Caliburn",
            public_validation_fields=PUBLIC_VALIDATION_FIELDS
            | JD_VALIDATION_FIELDS
            | QUESTION_VALIDATION_FIELDS
            | frozenset({"turn_id", "input", "message_id"}),
            lifespan=lifespan,
        )
        install_agent_event_schema(app)
        return app
    except BaseException:
        engine.dispose()
        raise
