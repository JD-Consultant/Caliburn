"""JD domain results retain facts until the model transport renders them."""

from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from caliburn.agents.job_consultant.configuration import (
    ConsultantConfiguration,
    ToolDescriptionOverride,
)
from caliburn.features.executions.models import ExecutionKind, ExecutionScope, ExecutionWriter
from caliburn.features.job_description.areas import CreateArea, ResponsibilityArea
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.compound_edits import JdCompoundEditResult
from caliburn.features.job_description.navigation import JdReadTargetNotFoundError
from caliburn.transport.model_tools.occupation_references import occupation_reference_definitions
from caliburn.workflows import jd_item_creation
from caliburn.workflows.jd_model_references import JdModelReferences


def test_reference_description_is_only_wording():
    description = "記錄員工確認的排除範圍。"
    config = ConsultantConfiguration(
        tool_descriptions=(ToolDescriptionOverride("update_excluded_work", description),)
    )
    changed = config.describe_tools(occupation_reference_definitions())
    assert (
        next(tool for tool in changed if tool["name"] == "update_excluded_work")["description"]
        == description
    )


async def test_model_reference_rejects_canonical_identity_without_database_access():
    references = JdModelReferences(None, uuid4())
    with pytest.raises(JdReadTargetNotFoundError):
        await references.resolve((f"task_{uuid4().hex}",))


async def test_creation_workflow_returns_committed_domain_result(monkeypatch):
    committed = False

    class Sessions:
        @asynccontextmanager
        async def begin(self):
            nonlocal committed
            yield object()
            committed = True

    async def allowed(*args):
        pass

    result = JdCompoundEditResult(
        uuid4(), "created", ResponsibilityArea(uuid4(), uuid4(), "盤點", None)
    )

    async def apply(*args, **kwargs):
        return result

    monkeypatch.setattr(jd_item_creation.job_files, "lock_job_file", allowed)
    monkeypatch.setattr(jd_item_creation.executions, "lock_active_writer", allowed)
    monkeypatch.setattr(jd_item_creation.revision_editing, "require_open_candidate", allowed)
    monkeypatch.setattr(jd_item_creation.compound_service, "apply_compound_edit", apply)
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
    writer = ExecutionWriter(scope, uuid4())
    prepared = jd_item_creation.PreparedItemCreation(
        uuid4(),
        JdCandidateScope(scope.execution_id, uuid4()),
        uuid4(),
        CreateArea("盤點", None),
        (),
    )
    actual = await jd_item_creation.JdItemCreationWorkflow(Sessions()).execute(writer, prepared)
    assert committed
    assert actual == result


def test_work_value_and_transformations_have_pure_owners():
    from caliburn.features.job_description.compound_changes import (
        apply_area_change,
        apply_collaborator_change,
    )
    from caliburn.features.job_description.navigation import JdWorkRevision

    assert JdWorkRevision.__module__ == "caliburn.features.job_description.work_models"
    assert apply_area_change.__module__ == "caliburn.features.job_description.area_changes"
    assert (
        apply_collaborator_change.__module__
        == "caliburn.features.job_description.collaborator_changes"
    )
