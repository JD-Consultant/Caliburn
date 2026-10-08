"""Generated JD wire intentions to typed application choices, without database access."""

from caliburn.contracts.generated.tools import create_jd_task_arguments as task
from caliburn.contracts.generated.tools import revise_jd_profile_arguments as profile
from caliburn.features.job_description.models import (
    ClearProfileField,
    ProfileChange,
    ProfileField,
    SetProfileField,
)
from caliburn.features.job_description.sources import MemorySourceLayer
from caliburn.workflows.jd_profile_writes import (
    AddProfileSource,
    AlignProfileSource,
    ProfileSourceIntent,
    RemoveProfileSource,
)
from caliburn.workflows.jd_sources import (
    CurrentInputSourceSelection,
    InterviewSourceSelection,
    JdSourceSelection,
    MemorySourceSelection,
)
from caliburn.workflows.jd_task_writes import CreateTaskInput, TaskCapabilityInput, TaskDetailInput


def parse_profile_write(
    arguments: str,
) -> tuple[tuple[ProfileChange, ...], tuple[ProfileSourceIntent, ...]]:
    parsed = profile.ReviseJdProfileArguments.model_validate_json(arguments)
    changes: list[ProfileChange] = []
    sources: list[ProfileSourceIntent] = []
    for item in parsed.changes:
        field = ProfileField(item.field.value)
        if isinstance(item, profile.SetProfileText):
            changes.append(SetProfileField(field, item.value))
        elif isinstance(item, profile.ClearProfileText):
            changes.append(ClearProfileField(field))
        elif isinstance(item, profile.AddProfileSource):
            sources.append(AddProfileSource(field, source_selection(item.source)))
        elif isinstance(item, profile.RemoveProfileSource):
            sources.append(RemoveProfileSource(field, item.citation_ref))
        else:
            sources.append(AlignProfileSource(field, item.citation_ref))
    return tuple(changes), tuple(sources)


def parse_task_write(arguments: str) -> CreateTaskInput:
    parsed = task.CreateJdTaskArguments.model_validate_json(arguments)
    return CreateTaskInput(
        parsed.parent_read_ref,
        parsed.title,
        parsed.description,
        tuple(
            TaskDetailInput(detail.text, _task_sources(detail.supporting_sources))
            for detail in parsed.outcomes
        ),
        tuple(
            TaskDetailInput(detail.text, _task_sources(detail.supporting_sources))
            for detail in parsed.requirements
        ),
        tuple(
            TaskCapabilityInput(item.capability_read_ref, _task_sources(item.supporting_sources))
            for item in parsed.required_knowledge
        ),
        tuple(
            TaskCapabilityInput(item.capability_read_ref, _task_sources(item.supporting_sources))
            for item in parsed.required_skills
        ),
        _task_sources(parsed.supporting_sources),
    )


type SourceWire = (
    task.CurrentInputSource
    | task.InterviewSource
    | task.MemorySource
    | profile.CurrentInputSource
    | profile.InterviewSource
    | profile.MemorySource
)


def source_selection(source: SourceWire) -> JdSourceSelection:
    if isinstance(source, task.CurrentInputSource | profile.CurrentInputSource):
        return CurrentInputSourceSelection()
    if isinstance(source, task.InterviewSource | profile.InterviewSource):
        return InterviewSourceSelection(source.interview_sequence)
    return MemorySourceSelection(MemorySourceLayer(source.kind.value), source.target_title)


def _task_sources(sources: list[task.Source]) -> tuple[JdSourceSelection, ...]:
    return tuple(source_selection(source.root) for source in sources)
