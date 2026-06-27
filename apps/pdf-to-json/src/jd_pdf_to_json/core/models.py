"""OCS document models — now sourced from the shared `ocs-contract` package.

The canonical structure lives in `packages/ocs-contract` (JSON-Schema → Pydantic).
Old jd-pdf-to-json class names are kept as aliases so the transformer / cli /
writers / validators import points keep working unchanged (Phase 2, no logic change).
"""

from ocs_contract.models import (  # noqa: F401
    OCSDocument,
    VersionInfo,
    VersionEntry,
    OcsName,
    Category,
    OcsProfile,
    CompetencyBlock,
    CodeName,
    CodeText,
    TaskGroup,
    OcuUnit,
    OcsContent,
    OcsAttitude,
    Notes,
)

# ── backward-compat aliases (old name → contract name) ───────────────────────
OCSName = OcsName
OCSCategory = Category
CategoryItem = CodeName
OCSProfile = OcsProfile
OCSContent = OcsContent
OCSUnit = OcuUnit
Task = TaskGroup
TaskCodeEntry = CodeName
OutputItem = CodeName
BehavioralIndicator = CodeText
CompetencyItem = CodeName
Attitude = CodeName
OCSAttitude = OcsAttitude
