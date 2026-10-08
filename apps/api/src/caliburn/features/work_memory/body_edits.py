"""Memory body editing retains its nonblank source/result policy."""

from caliburn.adapters.body_edits import (
    DEFAULT_BODY_MATCH_POLICY as DEFAULT_BODY_MATCH_POLICY,
)
from caliburn.adapters.body_edits import (
    apply_body_diff as _apply_body_diff,
)
from caliburn.adapters.body_edits import (
    split_body_lines as split_body_lines,
)
from caliburn.adapters.body_matching import BodyMatchPolicy


def apply_body_diff(
    body: str, diff: str, *, policy: BodyMatchPolicy = DEFAULT_BODY_MATCH_POLICY
) -> str:
    """Apply the shared editor under Memory's existing nonblank body policy."""
    return _apply_body_diff(body, diff, policy=policy)
