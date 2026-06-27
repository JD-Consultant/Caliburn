"""OCS source-doc models — now sourced from the shared `ocs-contract` package.

The canonical structure lives in `packages/ocs-contract` (JSON-Schema → Pydantic).
The contract model is tolerant enough (additionalProperties + optional fields) to
load the full 908-file corpus — verified before wiring. The indexer's reader /
normalizer only need `OCSDocument`; the rest are re-exported for convenience.
"""

from ocs_contract.models import (  # noqa: F401
    OCSDocument,
    OcsProfile,
    OcsContent,
    OcsAttitude,
    Notes,
    OcuUnit,
    TaskGroup,
    CompetencyBlock,
    Category,
    OcsName,
    CodeName,
    CodeText,
    VersionInfo,
    VersionEntry,
)
