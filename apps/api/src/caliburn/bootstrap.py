"""Application composition root; dependency creation is explicit at startup."""

from collections.abc import AsyncIterator
from contextlib import AsyncExitStack, asynccontextmanager
from functools import partial

from fastapi import FastAPI
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg.conninfo import make_conninfo

from caliburn.adapters.database import Database
from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.adapters.openai_responses import create_responses_client
from caliburn.adapters.pdf_renderer import PdfRenderer
from caliburn.adapters.process_lock import PostgresProcessLock
from caliburn.adapters.reasoning_summaries import PublicReasoningSummary
from caliburn.adapters.response_streaming import PublicCommentaryUpdate
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions.models import ExecutionScope, ExecutionStatus
from caliburn.settings import ModelSettings, Settings
from caliburn.transport.http.consultant_activity import router as consultant_activity_router
from caliburn.transport.http.consultant_turns import router as consultant_turn_router
from caliburn.transport.http.health import router as health_router
from caliburn.transport.http.interview_inputs import router as interview_input_router
from caliburn.transport.http.jd_areas import router as jd_areas_router
from caliburn.transport.http.jd_capabilities import router as jd_capabilities_router
from caliburn.transport.http.jd_collaborators import router as jd_collaborators_router
from caliburn.transport.http.jd_conditions import router as jd_conditions_router
from caliburn.transport.http.jd_evidence import router as jd_evidence_router
from caliburn.transport.http.jd_export import router as jd_export_router
from caliburn.transport.http.jd_profile import router as jd_profile_router
from caliburn.transport.http.jd_tasks import router as jd_tasks_router
from caliburn.transport.http.jd_undo import router as jd_undo_router
from caliburn.transport.http.jd_work import router as jd_work_router
from caliburn.transport.http.job_files import router as job_file_router
from caliburn.transport.http.security import LocalHttpSecurityMiddleware
from caliburn.transport.http.turn_jd_changes import router as turn_jd_changes_router
from caliburn.transport.model_tools.memory_analysis import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.consultant_activity import ConsultantActivityHub
from caliburn.workflows.consultant_commentary import ConsultantCommentaryHub
from caliburn.workflows.consultant_commentary import (
    PublicCommentaryUpdate as ScopedCommentaryUpdate,
)
from caliburn.workflows.consultant_completion import ConsultantCompletionWorkflow
from caliburn.workflows.consultant_controls import (
    ConsultantControlWorkflow,
    run_consultant_with_controls,
)
from caliburn.workflows.consultant_status import ConsultantStatusWorkflow
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.execution_failures import run_with_failure_boundary
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from caliburn.workflows.jd_editing import JdEditingWorkflow
from caliburn.workflows.jd_evidence import JdEvidenceWorkflow
from caliburn.workflows.jd_export import JdExportWorkflow
from caliburn.workflows.jd_undo import JdUndoWorkflow
from caliburn.workflows.job_files import JobFileWorkflow
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_supervisor import MemorySupervisor
from caliburn.workflows.turn_jd_changes import TurnJdChangesWorkflow

# Registration order is route-matching order.
ROUTERS = (
    health_router,
    job_file_router,
    interview_input_router,
    consultant_turn_router,
    consultant_activity_router,
    jd_profile_router,
    jd_areas_router,
    jd_capabilities_router,
    jd_collaborators_router,
    jd_conditions_router,
    jd_tasks_router,
    jd_work_router,
    jd_evidence_router,
    jd_export_router,
    jd_undo_router,
    turn_jd_changes_router,
)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the app without reading legacy configuration or requiring model credentials."""
    configured = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(configured.database) if configured.database else None
        _reset_runtime_state(app, database)
        try:
            async with AsyncExitStack() as resources:
                if database is not None:
                    await database.verify_schema()
                    await _start_database_runtime(app, configured, database, resources)
                yield
        finally:
            app.state.consultant_supervisor = None
            app.state.memory_supervisor = None
            if database is not None:
                await database.close()

    app = FastAPI(title="Caliburn", version="0.1.0", lifespan=lifespan)
    app.add_middleware(LocalHttpSecurityMiddleware, dev_origin=configured.dev_origin)
    for router in ROUTERS:
        app.include_router(router)
    if configured.web_build_directory is not None:
        app.frontend("/", directory=configured.web_build_directory, fallback=None, check_dir=True)
        # Only UI navigation gets the SPA fallback; missing APIs/assets stay 404.
        app.frontend(
            "/job-files",
            directory=configured.web_build_directory,
            fallback="index.html",
            check_dir=True,
        )
    return app


def _reset_runtime_state(app: FastAPI, database: Database | None) -> None:
    """Workflows that need only the database exist at once; runtime services start later."""
    app.state.database = database
    sessions = database.sessions if database else None
    app.state.job_file_workflow = JobFileWorkflow(sessions) if sessions else None
    app.state.jd_editing_workflow = JdEditingWorkflow(sessions) if sessions else None
    app.state.jd_evidence_workflow = JdEvidenceWorkflow(sessions) if sessions else None
    app.state.jd_undo_workflow = JdUndoWorkflow(sessions) if sessions else None
    app.state.turn_jd_changes_workflow = TurnJdChangesWorkflow(sessions) if sessions else None
    app.state.interview_input_workflow = InterviewInputWorkflow(sessions) if sessions else None
    app.state.consultant_status_workflow = None
    app.state.consultant_supervisor = None
    app.state.consultant_commentary_hub = ConsultantCommentaryHub()
    app.state.consultant_activity_hub = ConsultantActivityHub()
    app.state.memory_supervisor = None
    app.state.consultant_control_workflow = None
    app.state.jd_export_workflow = None


async def _start_database_runtime(
    app: FastAPI, configured: Settings, database: Database, resources: AsyncExitStack
) -> None:
    if configured.pdf is not None:
        renderer = PdfRenderer(
            font_path=configured.pdf.font_path, executable_path=configured.pdf.executable_path
        )
        resources.push_async_callback(renderer.aclose)
        app.state.jd_export_workflow = JdExportWorkflow(database.sessions, renderer)
    # Saved public history remains readable without model credentials.
    dsn = make_conninfo(
        database.settings.sqlalchemy_url.set(drivername="postgresql").render_as_string(
            hide_password=False
        ),
        options=f"-c search_path={database.settings.schema}",
    )
    saver = await resources.enter_async_context(
        AsyncPostgresSaver.from_conn_string(
            dsn, serde=create_graph_serializer(allowed_types=MEMORY_CHECKPOINT_TYPES)
        )
    )
    await saver.setup()
    app.state.consultant_status_workflow = ConsultantStatusWorkflow(database.sessions, saver)
    if configured.model is not None:
        await _start_model_runtime(app, configured.model, database, saver, resources)


async def _start_model_runtime(
    app: FastAPI,
    model: ModelSettings,
    database: Database,
    saver: AsyncPostgresSaver,
    resources: AsyncExitStack,
) -> None:
    """Start the consultant and Memory supervisors that share one local leader fence."""
    sdk = create_responses_client(
        api_key=model.api_key, timeout_seconds=model.request_timeout_seconds
    )
    resources.push_async_callback(sdk.close)
    hub: ConsultantCommentaryHub = app.state.consultant_commentary_hub
    activity_hub: ConsultantActivityHub = app.state.consultant_activity_hub

    def publish_reasoning_summary(scope: ExecutionScope, summary: PublicReasoningSummary) -> None:
        activity_hub.publish(scope.job_file_id, scope.execution_id, summary)

    def publish_commentary(scope: ExecutionScope, update: PublicCommentaryUpdate) -> None:
        activity_hub.publish(
            scope.job_file_id,
            scope.execution_id,
            ScopedCommentaryUpdate(
                scope.job_file_id,
                scope.execution_id,
                update.response_id,
                update.message_id,
                update.text,
            ),
        )
        hub.publish(
            scope.job_file_id,
            scope.execution_id,
            update.response_id,
            update.message_id,
            update.text,
        )

    runner = ConsultantRunner(
        database.sessions,
        saver,
        sdk,
        model,
        on_commentary=publish_commentary,
        on_reasoning_summary=publish_reasoning_summary,
    )
    leader_lock = PostgresProcessLock(database.settings)
    memory_batch = MemoryBatchWorkflow(
        database.sessions,
        run_role=MemoryRoleDispatch(
            WorkSituationAnalystRunner(database.sessions, saver, sdk, model),
            WorkUnderstandingAnalystRunner(database.sessions, saver, sdk, model),
        ),
    )
    memory_supervisor = MemorySupervisor(
        database.sessions,
        run=partial(
            run_with_failure_boundary,
            run=memory_batch.run,
            settle_failure=memory_batch.settle_failure,
        ),
        check_leadership=leader_lock.check,
    )
    completion = ConsultantCompletionWorkflow(database.sessions)
    supervisor = ConsultantSupervisor(
        sessions=database.sessions,
        run=partial(
            run_with_failure_boundary,
            run=partial(
                run_consultant_with_controls,
                sessions=database.sessions,
                checkpointer=saver,
                run=runner.run,
            ),
            settle_failure=lambda writer, _error: completion.stop(writer, ExecutionStatus.FAILED),
        ),
        process_lock=leader_lock,
        before_leader_release=memory_supervisor.close,
    )
    resources.push_async_callback(supervisor.close)
    await supervisor.start()
    app.state.consultant_supervisor = supervisor
    app.state.consultant_control_workflow = ConsultantControlWorkflow(
        database.sessions, saver, supervisor
    )
    # LIFO cleanup stops Memory before releasing the shared leader fence, then SDK/saver,
    # then database. No second leader or queue is created.
    resources.push_async_callback(memory_supervisor.close)
    await memory_supervisor.start()
    app.state.memory_supervisor = memory_supervisor
