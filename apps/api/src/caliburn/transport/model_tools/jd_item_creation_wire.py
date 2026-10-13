"""Generated create_jd_item variants translate to existing domain create values."""

from caliburn.contracts.generated.tools import create_jd_item_arguments as wire
from caliburn.contracts.validation import parse_contract
from caliburn.features.job_description.areas import CreateArea
from caliburn.features.job_description.capabilities import CapabilityKind, CreateCapability
from caliburn.features.job_description.collaborators import CreateCollaborator
from caliburn.features.job_description.conditions import ConditionKind, CreateCondition
from caliburn.features.job_description.source_intents import (
    InterviewSourceSelection,
    JdSourceSelection,
    MemorySourceSelection,
)
from caliburn.features.job_description.sources import MemorySourceLayer
from caliburn.workflows.job_description.item_creation import CreateItemInput, ItemCreation


def parse_item_creation(arguments: str) -> CreateItemInput:
    item = parse_contract(wire.CreateJdItemArguments, arguments).item
    creation: ItemCreation
    if isinstance(item, wire.ResponsibilityAreaItem):
        creation = CreateArea(item.title, item.scope_text)
    elif isinstance(item, wire.CapabilityItem):
        creation = CreateCapability(CapabilityKind(item.kind.value), item.name, item.description)
    elif isinstance(item, wire.CollaboratorItem):
        creation = CreateCollaborator(item.name, item.scope_text)
    else:
        creation = CreateCondition(ConditionKind(item.condition_kind.value), item.text)
    return CreateItemInput(
        creation, tuple(_source_selection(source.root) for source in item.supporting_sources)
    )


def _source_selection(
    source: wire.InterviewSource | wire.MemorySource,
) -> JdSourceSelection:
    if isinstance(source, wire.InterviewSource):
        return InterviewSourceSelection(source.interview_sequence)
    return MemorySourceSelection(MemorySourceLayer(source.kind.value), source.target_title)
