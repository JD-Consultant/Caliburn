"""HTTP dependency for the single JD editing workflow, shared by its resource routes."""

from typing import Annotated

from fastapi import Depends, HTTPException, Request

from caliburn.workflows.jd_editing import JdEditingWorkflow


def get_jd_workflow(request: Request) -> JdEditingWorkflow:
    workflow = request.app.state.jd_editing_workflow
    if not isinstance(workflow, JdEditingWorkflow):
        raise HTTPException(status_code=503, detail={"code": "database_not_configured"})
    return workflow


JdEditing = Annotated[JdEditingWorkflow, Depends(get_jd_workflow)]
