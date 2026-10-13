"""Source-only wire; the App fixes the comparison endpoints."""

from caliburn.contracts.generated.tools import read_jd_changes_arguments as wire
from caliburn.contracts.validation import parse_contract
from caliburn.workflows.job_description.source_changes import SourceChangeQuery


def parse_jd_changes(arguments: str) -> SourceChangeQuery:
    query = parse_contract(wire.ReadJdChangesArguments, arguments).query
    if not query.citation_ref.strip():
        raise ValueError("Choose a citation_ref")
    return SourceChangeQuery(query.citation_ref)
