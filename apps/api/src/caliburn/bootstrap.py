"""Application composition root; dependency creation is explicit at startup."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from caliburn.adapters.database import Database
from caliburn.settings import Settings
from caliburn.transport.http.health import router as health_router
from caliburn.transport.http.interview_inputs import router as interview_input_router
from caliburn.transport.http.jd_areas import router as jd_areas_router
from caliburn.transport.http.jd_capabilities import router as jd_capabilities_router
from caliburn.transport.http.jd_profile import router as jd_profile_router
from caliburn.transport.http.jd_tasks import router as jd_tasks_router
from caliburn.transport.http.jd_work import router as jd_work_router
from caliburn.transport.http.job_files import router as job_file_router
from caliburn.workflows.interview_inputs import InterviewInputWorkflow
from caliburn.workflows.jd_editing import JdEditingWorkflow
from caliburn.workflows.job_files import JobFileWorkflow


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create the app without reading legacy configuration or requiring model credentials."""
    configured = settings if settings is not None else Settings.from_environment()

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        database = Database(configured.database) if configured.database else None
        app.state.database = database
        app.state.job_file_workflow = JobFileWorkflow(database.sessions) if database else None
        app.state.jd_editing_workflow = JdEditingWorkflow(database.sessions) if database else None
        app.state.interview_input_workflow = (
            InterviewInputWorkflow(database.sessions) if database else None
        )
        try:
            if database is not None:
                await database.verify_schema()
            yield
        finally:
            if database is not None:
                await database.close()

    app = FastAPI(title="Caliburn", version="0.1.0", lifespan=lifespan)
    app.include_router(health_router)
    app.include_router(job_file_router)
    app.include_router(interview_input_router)
    app.include_router(jd_profile_router)
    app.include_router(jd_areas_router)
    app.include_router(jd_capabilities_router)
    app.include_router(jd_tasks_router)
    app.include_router(jd_work_router)
    return app
