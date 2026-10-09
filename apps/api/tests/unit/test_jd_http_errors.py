"""Public JD error responses remain stable across resources and adjacent workflows."""

from unittest.mock import create_autospec
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from caliburn.features.executions.models import ExecutionBusyError
from caliburn.features.job_description import areas, capabilities, collaborators, conditions, tasks
from caliburn.features.job_description.models import (
    InvalidProfileChangeError,
    JdCommandConflictError,
    StaleJdRevisionError,
)
from caliburn.features.job_files.models import JobFileNotFoundError
from caliburn.transport.http import (
    jd_areas,
    jd_capabilities,
    jd_collaborators,
    jd_conditions,
    jd_profile,
    jd_tasks,
    jd_undo,
    job_files,
)
from caliburn.workflows.jd_editing import JdEditingWorkflow
from caliburn.workflows.jd_undo import JdUndoWorkflow
from caliburn.workflows.job_files import JobFileWorkflow

RESOURCES = (
    (
        jd_profile,
        "profile",
        "revise_profile",
        {"changes": [{"action": "set_field", "field": "job_title", "value": "合成職務"}]},
        InvalidProfileChangeError,
        "invalid_profile_changes",
        None,
        None,
    ),
    (
        jd_areas,
        "areas",
        "edit_areas",
        {"change": {"action": "create_area", "title": "合成職責", "scope_text": None}},
        areas.InvalidAreaChangeError,
        "invalid_area_change",
        areas.AreaNotFoundError,
        "jd_area_not_found",
    ),
    (
        jd_tasks,
        "tasks",
        "edit_tasks",
        {
            "change": {
                "action": "create_task",
                "area_id": None,
                "title": "合成任務",
                "description": None,
                "outcomes": [],
                "requirements": [],
            }
        },
        tasks.InvalidTaskChangeError,
        "invalid_task_change",
        tasks.TaskTargetNotFoundError,
        "jd_task_target_not_found",
    ),
    (
        jd_capabilities,
        "capabilities",
        "edit_capabilities",
        {
            "change": {
                "action": "create_capability",
                "kind": "knowledge",
                "name": "合成知識",
                "description": None,
            }
        },
        capabilities.InvalidCapabilityChangeError,
        "invalid_capability_change",
        capabilities.CapabilityTargetNotFoundError,
        "jd_capability_target_not_found",
    ),
    (
        jd_collaborators,
        "collaborators",
        "edit_collaborators",
        {"change": {"action": "create_collaborator", "name": "合成協作者", "scope_text": None}},
        collaborators.InvalidCollaboratorChangeError,
        "invalid_collaborator_change",
        collaborators.CollaboratorNotFoundError,
        "jd_collaborator_not_found",
    ),
    (
        jd_conditions,
        "conditions",
        "edit_conditions",
        {"change": {"action": "create_condition", "kind": "work_environment", "text": "合成條件"}},
        conditions.InvalidConditionChangeError,
        "invalid_condition_change",
        conditions.ConditionNotFoundError,
        "jd_condition_not_found",
    ),
)


@pytest.mark.parametrize("resource", RESOURCES, ids=[item[1] for item in RESOURCES])
@pytest.mark.parametrize(
    ("error_type", "status", "code"),
    [
        (JdCommandConflictError, 409, "jd_command_conflict"),
        (StaleJdRevisionError, 409, "jd_revision_stale"),
        (ExecutionBusyError, 409, "consultant_turn_active"),
        (JobFileNotFoundError, 404, "job_file_not_found"),
        (None, 422, None),
    ],
)
def test_manual_edit_errors_keep_their_public_response(resource, error_type, status, code):
    module, path, method, payload, invalid_type, invalid_code, _, _ = resource
    workflow = create_autospec(JdEditingWorkflow, instance=True)
    getattr(workflow, method).side_effect = (error_type or invalid_type)("private details")
    app = FastAPI()
    app.state.jd_editing_workflow = workflow
    app.include_router(module.router)
    with TestClient(app) as client:
        response = client.post(
            f"/api/job-files/{uuid4()}/jd/{path}",
            json={"command_id": str(uuid4()), "expected_revision_id": str(uuid4()), **payload},
        )
    assert response.status_code == status, response.text
    assert response.json() == {"detail": {"code": code or invalid_code}}
    getattr(workflow, method).assert_awaited_once()


@pytest.mark.parametrize("resource", RESOURCES[1:], ids=[item[1] for item in RESOURCES[1:]])
def test_missing_resource_keeps_its_specific_error(resource):
    module, path, method, payload, _, _, error_type, code = resource
    workflow = create_autospec(JdEditingWorkflow, instance=True)
    getattr(workflow, method).side_effect = error_type("private details")
    app = FastAPI()
    app.state.jd_editing_workflow = workflow
    app.include_router(module.router)
    with TestClient(app) as client:
        response = client.post(
            f"/api/job-files/{uuid4()}/jd/{path}",
            json={"command_id": str(uuid4()), "expected_revision_id": str(uuid4()), **payload},
        )
    assert response.status_code == 404
    assert response.json() == {"detail": {"code": code}}


def test_undo_and_delete_keep_their_distinct_conflict_meaning():
    app = FastAPI()
    undo = create_autospec(JdUndoWorkflow, instance=True)
    undo.undo.side_effect = StaleJdRevisionError("private details")
    deletion = create_autospec(JobFileWorkflow, instance=True)
    deletion.delete.side_effect = ExecutionBusyError("private details")
    app.state.jd_undo_workflow = undo
    app.state.job_file_workflow = deletion
    app.include_router(jd_undo.router)
    app.include_router(job_files.router)
    with TestClient(app) as client:
        response = client.post(f"/api/job-files/{uuid4()}/consultant-turns/{uuid4()}/undo-jd")
        assert response.status_code == 409
        assert response.json() == {"detail": {"code": "jd_undo_conflict"}}
        response = client.delete(f"/api/job-files/{uuid4()}")
        assert response.status_code == 409
        assert response.json() == {"detail": {"code": "job_file_busy"}}
