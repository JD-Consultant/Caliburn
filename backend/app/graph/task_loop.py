from dataclasses import dataclass


@dataclass
class TaskLoopManager:
    """Centralises task-index boundary checks, skip-completed logic, and advancement."""

    tasks: list[dict]
    index: int

    @property
    def current_task(self) -> dict | None:
        if 0 <= self.index < len(self.tasks):
            return self.tasks[self.index]
        return None

    @property
    def is_done(self) -> bool:
        return self.index >= len(self.tasks)

    def current_task_id(self) -> str | None:
        task = self.current_task
        if task is None:
            return None
        return task.get("task_id", f"task_{self.index + 1:03d}")

    def advance(self) -> "TaskLoopManager":
        return TaskLoopManager(self.tasks, self.index + 1)

    def skip_completed(self, completed_ids: list[str]) -> "TaskLoopManager":
        idx = self.index
        while idx < len(self.tasks):
            tid = self.tasks[idx].get("task_id", f"task_{idx + 1:03d}")
            if tid not in completed_ids:
                break
            idx += 1
        return TaskLoopManager(self.tasks, idx)
