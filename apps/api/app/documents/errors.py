"""Document/header/Duty/Task direct-edit failures owned by `documents`.

The six failures consumed by more than one feature module live in
`app.core.errors` (ADR 0058 rule 7), including `JdTaskNotFound`, which this
module deliberately does not duplicate. Only the failures specific to this
feature's direct-edit use cases live here.
"""

from __future__ import annotations

from app.core.errors import JobAnalysisApplicationError


class DutyNotFound(JobAnalysisApplicationError):
    pass


class InvalidDutyOrder(JobAnalysisApplicationError):
    pass


class InvalidJdTaskOrder(JobAnalysisApplicationError):
    pass


class JdHeaderNotChanged(JobAnalysisApplicationError):
    pass
