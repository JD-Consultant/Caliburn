"""Opaque provider history and bound domain commands have separate serializing contracts."""

from uuid import uuid4

import pytest
from pydantic import ValidationError

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.executions.models import ExecutionKind, ExecutionScope
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.models import ProfileField, SetProfileField
from caliburn.features.job_description.sources import AddJdSource, InterviewSource
from caliburn.features.job_description.tasks import CreateTask
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.workflows.jd_profile_writes import BoundProfileSources, PreparedProfileWrite
from caliburn.workflows.jd_task_writes import PreparedTaskWrite


@pytest.mark.parametrize("kind", ["profile", "task"])
def test_bound_write_survives_official_serializer_without_custom_constructors(kind: str) -> None:
    scope = ExecutionScope(uuid4(), uuid4(), ExecutionKind.CONSULTANT_TURN)
    candidate = JdCandidateScope(scope.execution_id, uuid4())
    source = InterviewSource(uuid4())
    if kind == "profile":
        command = PreparedProfileWrite(
            uuid4(),
            candidate,
            uuid4(),
            (SetProfileField(ProfileField.JOB_TITLE, "前端工程師"),),
            (BoundProfileSources(ProfileField.JOB_TITLE, (AddJdSource(source),)),),
        )
    else:
        command = PreparedTaskWrite(
            uuid4(),
            candidate,
            uuid4(),
            CreateTask(None, "盤點", "核對庫存", ("差異表",), ()),
            (source,),
            ((source,),),
            (),
        )
    serializer = create_graph_serializer()
    saved = serializer.dumps_typed(snapshot_jd_write(command))
    restored = restore_jd_write(serializer.loads_typed(saved))
    assert restored == command
    assert type(restored) is type(command)


def test_malformed_saved_command_is_rejected_before_effects() -> None:
    with pytest.raises(ValidationError):
        restore_jd_write({"kind": "profile", "payload": '{"command_id":"not-a-uuid"}'})
    with pytest.raises(ValidationError):
        restore_jd_write({"kind": "task", "payload": "{}", "unrecognized": True})


@pytest.mark.parametrize("operation", ["delete", "move"])
def test_lifecycle_prepared_facts_survive_native_serializer(operation):
    from caliburn.features.job_description.areas import DeleteArea, EditJdAreas
    from caliburn.features.job_description.tasks import MoveTask
    from caliburn.workflows.jd_item_deletion import PreparedItemDeletion
    from caliburn.workflows.jd_item_movement import PreparedItemMovement

    candidate = JdCandidateScope(uuid4(), uuid4())
    command_id, revision_id, item_id = uuid4(), uuid4(), uuid4()
    command = (
        PreparedItemDeletion(
            candidate, EditJdAreas(command_id, revision_id, DeleteArea(item_id)), 2
        )
        if operation == "delete"
        else PreparedItemMovement(
            command_id, candidate, revision_id, MoveTask(item_id, None, None, ()), (), True
        )
    )
    serializer = create_graph_serializer()
    saved = serializer.dumps_typed(snapshot_jd_write(command))
    assert restore_jd_write(serializer.loads_typed(saved)) == command
