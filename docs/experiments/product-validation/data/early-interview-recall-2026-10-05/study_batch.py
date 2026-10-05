"""Sequential case blocks rotate arm order; native state never crosses job files."""

from collections.abc import Awaitable, Callable, Sequence
from typing import TypedDict

from caliburn.agent_execution.request_capacity import (
    CompactionRequiredError,
    RequestCapacityError,
    RequestOverCapacityError,
)
from study_context import StudyArm
from study_window import StudyCapacityError

ARMS: tuple[StudyArm, ...] = ("raw", "summary", "memory")


class ContinuationCase(TypedDict):
    case_id: str
    employee_input: str


def schedule(cases: Sequence[ContinuationCase]) -> list[tuple[StudyArm, ContinuationCase]]:
    planned: list[tuple[StudyArm, ContinuationCase]] = []
    for index, case in enumerate(cases):
        offset = index % len(ARMS)
        planned.extend((arm, case) for arm in (*ARMS[offset:], *ARMS[:offset]))
    return planned


async def run_schedule(
    cases: Sequence[ContinuationCase],
    run: Callable[[StudyArm, ContinuationCase], Awaitable[None]],
    record: Callable[[dict[str, object]], None],
) -> dict[str, object]:
    completed: dict[str, list[str]] = {arm: [] for arm in ARMS}
    stopped: dict[str, str] = {}
    for arm, case in schedule(cases):
        if arm in stopped:
            continue
        try:
            await run(arm, case)
        except (StudyCapacityError, RequestCapacityError) as error:
            if not (
                isinstance(error, (StudyCapacityError, RequestOverCapacityError))
                or isinstance(error.__cause__, CompactionRequiredError)
            ):
                raise  # Invalid counts/policy are not evidence of a method's capacity.
            stopped[arm] = str(error)
            record(
                {
                    "event": "capacity_stop",
                    "arm": arm,
                    "case_id": case["case_id"],
                    "reason": str(error),
                }
            )
        else:
            completed[arm].append(case["case_id"])
            record({"event": "case_completed", "arm": arm, "case_id": case["case_id"]})
    return {"completed": completed, "capacity_stops": stopped}
