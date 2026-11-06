"""原生中斷定位及本程序正常執行所確認的等待證據。"""

from collections.abc import Sequence
from copy import deepcopy
from dataclasses import dataclass
from uuid import UUID

from langgraph.types import Interrupt, StateSnapshot
from pydantic import JsonValue


@dataclass(frozen=True)
class ResumePoint:
    checkpoint_id: str
    interrupt: Interrupt

    def matches(self, snapshot: StateSnapshot) -> bool:
        return snapshot.config["configurable"].get(
            "checkpoint_id"
        ) == self.checkpoint_id and any(
            pending.id == self.interrupt.id and pending.value == self.interrupt.value
            for pending in snapshot.interrupts
        )


@dataclass(frozen=True)
class InterruptResume:
    point: ResumePoint
    value: JsonValue


@dataclass(frozen=True)
class ConfirmedInterrupts:
    """錯誤可能殘留；只接受此次正常執行重新發出的特定中斷。"""

    turn_id: UUID
    points: tuple[ResumePoint, ...]

    def matches(self, snapshot: StateSnapshot, target: Interrupt | None = None) -> bool:
        return snapshot.values.get("turn_id") == self.turn_id and any(
            point.matches(snapshot)
            and (
                target is None
                or (
                    point.interrupt.id == target.id
                    and point.interrupt.value == target.value
                )
            )
            for point in self.points
        )


def confirmed_interrupts(
    snapshot: StateSnapshot, emitted: Sequence[Interrupt]
) -> ConfirmedInterrupts | None:
    points = tuple(
        ResumePoint(snapshot.config["configurable"]["checkpoint_id"], deepcopy(pending))
        for pending in snapshot.interrupts
        if any(
            item.id == pending.id and item.value == pending.value for item in emitted
        )
    )
    return ConfirmedInterrupts(snapshot.values["turn_id"], points) if points else None


def can_resume_interrupt(
    snapshot: StateSnapshot,
    target: Interrupt,
    confirmed: ConfirmedInterrupts | None,
) -> bool:
    return any(
        pending.id == target.id and pending.value == target.value
        for pending in snapshot.interrupts
    ) and (
        not any(task.error is not None for task in snapshot.tasks)
        or (confirmed is not None and confirmed.matches(snapshot, target))
    )
