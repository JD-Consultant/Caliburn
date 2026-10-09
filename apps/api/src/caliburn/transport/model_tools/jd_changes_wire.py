"""The canonical two-query wire contains model choices, never revision coordinates."""

from caliburn.contracts.generated.tools import read_jd_changes_arguments as wire
from caliburn.contracts.validation import parse_contract
from caliburn.features.job_description.models import ProfileField
from caliburn.workflows.jd_changes import (
    AllManualChanges,
    AreaManualChanges,
    ItemManualChanges,
    JdChangeQuery,
    ManualChangeQuery,
    ManualChangeScope,
    ManualJdArea,
    ProfileManualChanges,
    SourceChangeQuery,
)


def parse_jd_changes(arguments: str) -> JdChangeQuery:
    query = parse_contract(wire.ReadJdChangesArguments, arguments).query
    if isinstance(query, wire.SourceQuery):
        if not query.citation_ref.strip():
            raise ValueError("Choose a citation_ref")
        return SourceChangeQuery(query.citation_ref)
    scope: ManualChangeScope
    if isinstance(query.scope, wire.AllScope):
        scope = AllManualChanges()
    elif isinstance(query.scope, wire.AreaScope):
        scope = AreaManualChanges(ManualJdArea(query.scope.view.value))
    elif isinstance(query.scope, wire.ItemScope):
        if not query.scope.read_ref.strip():
            raise ValueError("Choose a read_ref")
        scope = ItemManualChanges(query.scope.read_ref)
    else:
        scope = ProfileManualChanges(ProfileField(query.scope.field.value))
    return ManualChangeQuery(scope)
