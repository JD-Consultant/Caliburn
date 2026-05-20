from dataclasses import dataclass


@dataclass(frozen=True)
class Phase:
    """Strongly-typed phase key, replaces manual f"star_{task_id}" string building."""

    stage: str
    task_id: str | None = None

    def to_str(self) -> str:
        if self.task_id:
            return f"{self.stage}_{self.task_id}"
        return self.stage

    @classmethod
    def from_str(cls, s: str) -> "Phase":
        for prefix in ("star", "five_w2h"):
            if s.startswith(f"{prefix}_"):
                return cls(stage=prefix, task_id=s[len(prefix) + 1:])
        return cls(stage=s)

    @classmethod
    def general(cls) -> "Phase":
        return cls(stage="general")

    @classmethod
    def star(cls, task_id: str) -> "Phase":
        return cls(stage="star", task_id=task_id)

    @classmethod
    def five_w2h(cls, task_id: str) -> "Phase":
        return cls(stage="five_w2h", task_id=task_id)
