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
from caliburn.adapters.response_streaming import PublicCommentaryUpdate
from caliburn.agents.job_consultant.runner import ConsultantRunner
from caliburn.agents.memory_analysis.dispatch import MemoryRoleDispatch
from caliburn.agents.work_situation_analyst.runner import WorkSituationAnalystRunner
from caliburn.agents.work_understanding_analyst.runner import WorkUnderstandingAnalystRunner
from caliburn.features.executions.models import ExecutionScope
from caliburn.settings import Settings
from caliburn.transport.http.consultant_turns import router as consultant_turn_router
from caliburn.transport.http.health import router as health_router
from caliburn.transport.http.interview_inputs import router as interview_input_router
from caliburn.transport.http.jd_areas import router as jd_areas_router
from caliburn.transport.http.jd_capabilities import router as jd_capabilities_router
from caliburn.transport.http.jd_collaborators import router as jd_collaborators_router
from caliburn.transport.http.jd_conditions import router as jd_conditions_router
from caliburn.transport.http.jd_export import router as jd_export_router
from caliburn.transport.http.jd_profile import router as jd_profile_router
from caliburn.transport.http.jd_tasks import router as jd_tasks_router
from caliburn.transport.http.jd_undo import router as jd_undo_router
from caliburn.transport.http.jd_work import router as jd_work_router
from caliburn.transport.http.job_files import router as job_file_router
from caliburn.transport.http.security import LocalHttpSecurityMiddleware
from caliburn.workflows.consultant_commentary import ConsultantCommentaryHub
from caliburn.workflows.consultant_controls import (
    ConsultantControlWorkflow,
    run_consultant_with_controls,
)
from caliburn.workflows.consultant_status import ConsultantStatusWorkflow
from caliburn.workflows.consultant_supervisor import ConsultantSupervisor
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from caliburn.workflows.jd_editing import JdEditingWorkflow
from caliburn.workflows.jd_export import JdExportWorkflow
from caliburn.workflows.jd_undo import JdUndoWorkflow
from caliburn.workflows.job_files import JobFileWorkflow
from caliburn.workflows.memory_analysis.tools import MEMORY_CHECKPOINT_TYPES
from caliburn.workflows.memory_batch import MemoryBatchWorkflow
from caliburn.workflows.memory_supervisor import MemorySupervisor


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the app without reading legacy configuration or requiring model credentials."""
    configured = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(configured.database) if configured.database else None
        app.state.database = database
        app.state.job_file_workflow = JobFileWorkflow(database.sessions) if database else None
        app.state.jd_editing_workflow = JdEditingWorkflow(database.sessions) if database else None
        app.state.jd_undo_workflow = JdUndoWorkflow(database.sessions) if database else None
        app.state.interview_input_workflow = (
            InterviewInputWorkflow(database.sessions) if database else None
        )
        app.state.consultant_status_workflow = (
            ConsultantStatusWorkflow(database.sessions) if database else None
        )
        app.state.consultant_supervisor = None
        commentary_hub = ConsultantCommentaryHub()
        app.state.consultant_commentary_hub = commentary_hub
        app.state.memory_supervisor = None
        app.state.consultant_control_workflow = None
        app.state.jd_export_workflow = None
        try:
            async with AsyncExitStack() as resources:
                if database is not None:
                    await database.verify_schema()
                    if configured.pdf is not None:
                        renderer = PdfRenderer(
                            font_path=configured.pdf.font_path,
                            executable_path=configured.pdf.executable_path,
                        )
                        resources.push_async_callback(renderer.aclose)
                        app.state.jd_export_workflow = JdExportWorkflow(database.sessions, renderer)
                    if configured.model is not None:
                        dsn = make_conninfo(
                            database.settings.sqlalchemy_url.set(
                                drivername="postgresql"
                            ).render_as_string(hide_password=False),
                            options=f"-c search_path={database.settings.schema}",
                        )
                        saver = await resources.enter_async_context(
                            AsyncPostgresSaver.from_conn_string(
                                dsn,
                                serde=create_graph_serializer(
                                    allowed_types=MEMORY_CHECKPOINT_TYPES
                                ),
                            )
                        )
                        await saver.setup()
                        app.state.consultant_status_workflow = ConsultantStatusWorkflow(
                            database.sessions, saver
                        )
                        sdk = create_responses_client(
                            api_key=configured.model.api_key,
                            timeout_seconds=configured.model.request_timeout_seconds,
                        )
                        resources.push_async_callback(sdk.close)

                        def publish_commentary(
                            scope: ExecutionScope, update: PublicCommentaryUpdate
                        ) -> None:
                            commentary_hub.publish(
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
                            configured.model,
                            on_commentary=publish_commentary,
                        )
                        leader_lock = PostgresProcessLock(database.settings)
                        memory_batch = MemoryBatchWorkflow(
                            database.sessions,
                            run_role=MemoryRoleDispatch(
                                WorkSituationAnalystRunner(
                                    database.sessions, saver, sdk, configured.model
                                ),
                                WorkUnderstandingAnalystRunner(
                                    database.sessions, saver, sdk, configured.model
                                ),
                            ),
                        )
                        memory_supervisor = MemorySupervisor(
                            database.sessions,
                            run=memory_batch.run_supervised,
                            check_leadership=leader_lock.check,
                        )
                        supervisor = ConsultantSupervisor(
                            sessions=database.sessions,
                            run=partial(
                                run_consultant_with_controls,
                                sessions=database.sessions,
                                checkpointer=saver,
                                run=runner.run_supervised,
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
                        # LIFO cleanup stops Memory before releasing the shared leader fence,
                        # then SDK/saver, then database. No second leader or queue is created.
                        resources.push_async_callback(memory_supervisor.close)
                        await memory_supervisor.start()
                        app.state.memory_supervisor = memory_supervisor
                yield
        finally:
            app.state.consultant_supervisor = None
            app.state.memory_supervisor = None
            if database is not None:
                await database.close()

    app = FastAPI(title="Caliburn", version="0.1.0", lifespan=lifespan)
    app.add_middleware(LocalHttpSecurityMiddleware)
    app.include_router(health_router)
    app.include_router(job_file_router)
    app.include_router(interview_input_router)
    app.include_router(consultant_turn_router)
    app.include_router(jd_profile_router)
    app.include_router(jd_areas_router)
    app.include_router(jd_capabilities_router)
    app.include_router(jd_collaborators_router)
    app.include_router(jd_conditions_router)
    app.include_router(jd_tasks_router)
    app.include_router(jd_work_router)
    app.include_router(jd_export_router)
    app.include_router(jd_undo_router)
    return app
