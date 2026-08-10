"""Public API: document/header/Duty/Task direct-edit use cases and readiness.

`documents` owns the employee/HR-editor-driven direct-edit path for a Current
JD's header, Duties, and Tasks, plus the pure readiness assessment consumed by
transport. LLM-driven Task Proposal analysis and OPKS stay in other feature
modules (ADR 0058).

Only what `app/api` routes and `app/api/job_analysis_mapper.py` actually
consume is re-exported here. Helpers such as `create_document`,
`DocumentMetadataWriteResult`, and `stale_task_proposals_for_direct_edit`
remain reachable via `app.documents.authoring` for tests and scripts, but are
not part of this curated surface (ADR 0058 rule 4).
"""

from __future__ import annotations

from .authoring import (
    add_jd_task,
    delete_jd_task,
    edit_jd_task,
    list_documents,
    load_document,
    put_document_metadata,
    put_jd_header,
    reorder_jd_tasks,
)
from .duty_authoring import (
    add_duty,
    delete_duty,
    edit_duty,
    reorder_duties,
)
from .errors import (
    DutyNotFound,
    InvalidDutyOrder,
    InvalidJdTaskOrder,
    JdHeaderNotChanged,
)
from .readiness import (
    DocumentReadiness,
    assess_readiness,
)

__all__ = [
    "DocumentReadiness",
    "DutyNotFound",
    "InvalidDutyOrder",
    "InvalidJdTaskOrder",
    "JdHeaderNotChanged",
    "add_duty",
    "add_jd_task",
    "assess_readiness",
    "delete_duty",
    "delete_jd_task",
    "edit_duty",
    "edit_jd_task",
    "list_documents",
    "load_document",
    "put_document_metadata",
    "put_jd_header",
    "reorder_duties",
    "reorder_jd_tasks",
]
