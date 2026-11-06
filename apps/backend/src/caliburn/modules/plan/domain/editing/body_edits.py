"""Plan 的單正文編修政策；共用演算法由 shared 提供。"""

from caliburn.modules.plan.domain.errors import (
    BodyEditError,
    BodyMatch,
    InvalidPlanTextError,
)
from caliburn.modules.plan.domain.text import MAX_BODY_CHARACTERS
from caliburn.shared.domain.text_editing.body_edits import EditLimits
from caliburn.shared.domain.text_editing.body_edits import (
    apply_body_diff as apply_text_diff,
)
from caliburn.shared.domain.text_editing.errors import InvalidTextError, TextEditError

_PLAN_EDIT_LIMITS = EditLimits(
    max_body_characters=MAX_BODY_CHARACTERS,
    max_patch_characters=16_000,
    max_hunks=32,
    max_scan_characters=20_000_000,
)


def apply_body_diff(body: str, diff: str) -> str:
    """保留 Plan 容量與領域錯誤，不改寫原有文字。"""
    try:
        return apply_text_diff(body, diff, limits=_PLAN_EDIT_LIMITS)
    except InvalidTextError as error:
        raise InvalidPlanTextError(
            "Plan text contains an unsupported character"
        ) from error
    except TextEditError as error:
        raise BodyEditError(
            error.code,
            str(error),
            hunk_number=error.hunk_number,
            candidates=tuple(
                BodyMatch(match.start_line, match.end_line)
                for match in error.candidates
            ),
        ) from error
