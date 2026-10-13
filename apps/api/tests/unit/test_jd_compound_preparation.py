"""固定 compound command 的具體型別、順序與來源跨 checkpoint 不變。"""

import json
from uuid import uuid4

import pytest
from pydantic import TypeAdapter, ValidationError

from caliburn.adapters.graph_checkpointer import create_graph_serializer
from caliburn.features.executions.models import (
    ExecutionKind,
    ExecutionScope,
    ExecutionStateError,
    ExecutionWriter,
)
from caliburn.features.job_description.areas import (
    AreaField,
    AreaFieldChange,
    CreateArea,
    ReviseArea,
)
from caliburn.features.job_description.candidates import JdCandidateScope
from caliburn.features.job_description.capabilities import (
    CapabilityField,
    CapabilityFieldChange,
    CapabilityKind,
    CreateCapability,
    ReorderTaskCapability,
    ReviseCapability,
    SetTaskCapability,
)
from caliburn.features.job_description.collaborators import (
    CollaboratorField,
    CollaboratorFieldChange,
    CreateCollaborator,
    ReviseCollaborator,
)
from caliburn.features.job_description.compound_edits import (
    BoundProfileSources,
    CreateItemWithSources,
    CreateTaskWithSources,
    ReviseItemWithSources,
    ReviseProfileWithSources,
)
from caliburn.features.job_description.conditions import (
    ConditionKind,
    ConditionKindChange,
    ConditionTextChange,
    CreateCondition,
    ReviseCondition,
)
from caliburn.features.job_description.models import (
    ClearProfileField,
    ProfileField,
    SetProfileField,
)
from caliburn.features.job_description.sources import (
    AddJdSource,
    AlignJdSource,
    InterviewSource,
    MemorySource,
    MemorySourceLayer,
    RemoveJdSource,
)
from caliburn.features.job_description.tasks import (
    AddTaskDetail,
    CreateTask,
    DetailKind,
    RemoveTaskDetail,
    ReviseTask,
    ReviseTaskDetail,
    SetTaskField,
    TaskField,
)
from caliburn.transport.model_tools.jd_write_checkpoint import restore_jd_write, snapshot_jd_write
from caliburn.workflows.job_description.compound_writes import (
    PreparedJdEdit,
    execute_prepared_jd_edit,
)

_ID, _REVISION = uuid4(), uuid4()
_SOURCE = InterviewSource(uuid4())
_MEMORY = MemorySource(MemorySourceLayer.WORK_SITUATION, uuid4(), uuid4(), uuid4())
_CREATIONS = (
    CreateArea("職責", "範圍"),
    CreateCapability(CapabilityKind.KNOWLEDGE, "知識", "說明"),
    CreateCollaborator("協作者", "範圍"),
    CreateCondition(ConditionKind.WORK_ENVIRONMENT, "環境"),
)
_REVISIONS = (
    ReviseArea(uuid4(), (AreaFieldChange(AreaField.TITLE, "新職責"),)),
    ReviseTask(
        uuid4(),
        (
            SetTaskField(TaskField.TITLE, "新任務"),
            AddTaskDetail(DetailKind.REQUIREMENT, "要求"),
            ReviseTaskDetail(uuid4(), "成果"),
            RemoveTaskDetail(uuid4()),
        ),
    ),
    ReviseCapability(uuid4(), (CapabilityFieldChange(CapabilityField.NAME, "新知識"),)),
    ReviseCollaborator(uuid4(), (CollaboratorFieldChange(CollaboratorField.NAME, "新協作者"),)),
    ReviseCondition(
        uuid4(), (ConditionTextChange("新環境"), ConditionKindChange(ConditionKind.QUALIFICATION))
    ),
)
_COMMANDS = (
    ReviseProfileWithSources(
        _ID,
        _REVISION,
        (
            SetProfileField(ProfileField.JOB_TITLE, "工程師"),
            ClearProfileField(ProfileField.PURPOSE),
        ),
        (
            BoundProfileSources(
                ProfileField.JOB_TITLE,
                (AddJdSource(_SOURCE), RemoveJdSource(uuid4()), AlignJdSource(uuid4(), _MEMORY)),
            ),
        ),
    ),
    CreateTaskWithSources(
        _ID,
        _REVISION,
        CreateTask(None, "任務", None, ("成果",), ("要求",)),
        (_SOURCE,),
        (),
    ),
    *(CreateItemWithSources(_ID, _REVISION, item, (_SOURCE,)) for item in _CREATIONS),
    *(
        ReviseItemWithSources(
            _ID,
            _REVISION,
            item,
            (
                SetTaskCapability(uuid4(), uuid4(), True),
                ReorderTaskCapability(uuid4(), uuid4(), None),
            ),
            (),
        )
        for item in _REVISIONS
    ),
)


def _prepare(command):
    return PreparedJdEdit(JdCandidateScope(uuid4()), command)


@pytest.mark.parametrize("command", _COMMANDS)
def test_checkpoint_keeps_one_complete_command_with_exact_nested_types(command):
    prepared = _prepare(command)
    checkpoint = snapshot_jd_write(prepared)
    payload = json.loads(checkpoint["payload"])
    assert payload["command"] == TypeAdapter(type(command)).dump_python(command, mode="json")
    serializer = create_graph_serializer()
    restored = restore_jd_write(serializer.loads_typed(serializer.dumps_typed(checkpoint)))
    assert restored == prepared
    assert type(restored.command) is type(command)
    if isinstance(command, ReviseProfileWithSources):
        assert tuple(map(type, restored.command.changes)) == tuple(map(type, command.changes))
        assert tuple(map(type, restored.command.sources[0].changes)) == tuple(
            map(type, command.sources[0].changes)
        )
        assert type(restored.command.sources[0].changes[0].source) is InterviewSource
        assert type(restored.command.sources[0].changes[2].source) is MemorySource
    if isinstance(command, CreateItemWithSources):
        assert type(restored.command.item) is type(command.item)
    if isinstance(command, ReviseItemWithSources):
        assert type(restored.command.content) is type(command.content)
        assert tuple(map(type, restored.command.content.changes)) == tuple(
            map(type, command.content.changes)
        )
        assert tuple(map(type, restored.command.capabilities)) == tuple(
            map(type, command.capabilities)
        )


def test_wrong_outer_kind_cannot_reinterpret_a_fixed_command():
    checkpoint = snapshot_jd_write(_prepare(_COMMANDS[0]))
    checkpoint["kind"] = "task"
    with pytest.raises(ValidationError):
        restore_jd_write(checkpoint)


@pytest.mark.parametrize("kind", [ExecutionKind.MEMORY_BATCH, ExecutionKind.CONSULTANT_TURN])
async def test_wrong_turn_is_rejected_before_opening_transaction(kind):
    prepared = _prepare(_COMMANDS[0])
    execution_id = (
        prepared.candidate.execution_id if kind == ExecutionKind.MEMORY_BATCH else uuid4()
    )
    writer = ExecutionWriter(ExecutionScope(uuid4(), execution_id, kind), uuid4())
    with pytest.raises(ExecutionStateError, match="different Turn"):
        await execute_prepared_jd_edit(None, writer, prepared)
