"""Manual JD workflow dependency and its shared HTTP conflict boundary."""

from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, HTTPException, Request

from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.job_description.models import JdCommandConflictError, StaleJdRevisionError
from caliburn.workflows.jd_editing import JdEditingWorkflow


async def get_jd_workflow(request: Request) -> AsyncIterator[JdEditingWorkflow]:
    """Translate shared edit conflicts; each route retains its resource-specific errors."""
    workflow = request.app.state.jd_editing_workflow
    if not isinstance(workflow, JdEditingWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    try:
        yield workflow
    except JdCommandConflictError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_command_conflict"}) from error
    except StaleJdRevisionError as error:
        raise HTTPException(status_code=409, detail={"code": "jd_revision_stale"}) from error
    except ExecutionBusyError as error:
        raise HTTPException(status_code=409, detail={"code": "consultant_turn_active"}) from error


JdEditing = Annotated[JdEditingWorkflow, Depends(get_jd_workflow, scope="function")]
