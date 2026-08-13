from __future__ import annotations

from copy import deepcopy
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt


class ConsultantPurposeState(TypedDict, total=False):
    command: dict[str, Any]
    interview_units: dict[str, dict[str, Any]]
    active_unit_id: str | None
    issue_queue: dict[str, dict[str, Any]]
    evolving_understanding: dict[str, dict[str, Any]]
    review_queue: dict[str, dict[str, Any]]
    approved_artifact: dict[str, Any]
    required_inputs: dict[str, dict[str, Any]]
    employee_evidence: dict[str, dict[str, Any]]
    revision: int


def _ordered_candidates(
    units: dict[str, dict[str, Any]], statuses: set[str]
) -> list[str]:
    candidates = (
        unit for unit in units.values() if unit.get("status") in statuses
    )
    return [
        unit["id"]
        for unit in sorted(candidates, key=lambda item: (item.get("order", 0), item["id"]))
    ]


def _activate(
    units: dict[str, dict[str, Any]], unit_id: str, *, status: str = "active"
) -> None:
    for candidate_id, candidate in units.items():
        if candidate_id != unit_id and candidate.get("status") in {"active", "reopened"}:
            candidate["status"] = "pending"
    units[unit_id]["status"] = status


def _read_path(value: dict[str, Any], path: list[str]) -> Any:
    current: Any = value
    for segment in path:
        if not isinstance(current, dict):
            raise KeyError(path)
        current = current.get(segment)
    return current


def _write_path(value: dict[str, Any], path: list[str], replacement: Any) -> None:
    if not path:
        raise ValueError("operation path cannot be empty")
    current: dict[str, Any] = value
    for segment in path[:-1]:
        child = current.get(segment)
        if child is None:
            child = {}
            current[segment] = child
        if not isinstance(child, dict):
            raise KeyError(path)
        current = child
    current[path[-1]] = deepcopy(replacement)


def _operations_are_current(
    artifact: dict[str, Any], operations: list[dict[str, Any]]
) -> bool:
    return all(
        _read_path(artifact, operation["path"]) == operation.get("before")
        for operation in operations
    )


def _apply_operations(
    artifact: dict[str, Any], operations: list[dict[str, Any]]
) -> dict[str, Any]:
    updated = deepcopy(artifact)
    for operation in operations:
        _write_path(updated, operation["path"], operation.get("after"))
    return updated


def build_consultant_purpose_graph(checkpointer: Any) -> Any:
    def apply_command(state: ConsultantPurposeState) -> ConsultantPurposeState:
        command = state["command"]
        kind = command["kind"]
        revision = state.get("revision", 0)

        if kind == "seed":
            raw_units = command.get("interview_units", [])
            if isinstance(raw_units, dict):
                units = deepcopy(raw_units)
            else:
                units = {unit["id"]: deepcopy(unit) for unit in raw_units}
            active = next(
                (
                    unit_id
                    for unit_id, unit in units.items()
                    if unit.get("status") in {"active", "reopened"}
                ),
                None,
            )
            if active is None:
                pending = _ordered_candidates(units, {"pending"})
                if pending:
                    active = pending[0]
                    _activate(units, active)
            return {
                "interview_units": units,
                "active_unit_id": active,
                "issue_queue": deepcopy(command.get("issue_queue", {})),
                "evolving_understanding": deepcopy(
                    command.get("evolving_understanding", {})
                ),
                "review_queue": deepcopy(command.get("review_queue", {})),
                "approved_artifact": deepcopy(command.get("approved_artifact", {})),
                "required_inputs": deepcopy(command.get("required_inputs", {})),
                "employee_evidence": deepcopy(command.get("employee_evidence", {})),
                "revision": revision + 1,
            }

        if kind == "discover_issue":
            issues = deepcopy(state.get("issue_queue", {}))
            issue = deepcopy(command["issue"])
            issues[issue["id"]] = issue
            return {"issue_queue": issues, "revision": revision + 1}

        if kind == "defer_unit":
            units = deepcopy(state["interview_units"])
            unit_id = command["unit_id"]
            units[unit_id]["status"] = "deferred"
            units[unit_id]["defer_reason"] = command["reason"]
            pending = _ordered_candidates(units, {"pending"})
            active = pending[0] if pending else None
            if active is not None:
                _activate(units, active)
            return {
                "interview_units": units,
                "active_unit_id": active,
                "revision": revision + 1,
            }

        if kind == "complete_unit":
            units = deepcopy(state["interview_units"])
            units[command["unit_id"]]["status"] = "completed"
            deferred = _ordered_candidates(units, {"deferred"})
            pending = _ordered_candidates(units, {"pending"})
            active = (deferred or pending or [None])[0]
            if active is not None:
                _activate(units, active)
            return {
                "interview_units": units,
                "active_unit_id": active,
                "revision": revision + 1,
            }

        if kind == "correct_source":
            evidence = deepcopy(state.get("employee_evidence", {}))
            source_id = command["source_id"]
            correction_id = command["correction_id"]
            evidence[correction_id] = {
                "text": command["text"],
                "speaker": "employee",
                "supersedes": source_id,
            }

            understanding = deepcopy(state.get("evolving_understanding", {}))
            affected = set(command.get("affected_unit_ids", []))
            for claim in understanding.values():
                if source_id in claim.get("depends_on_source_ids", []):
                    claim["status"] = "challenged"
                    claim["challenged_by"] = correction_id
                    if unit_id := claim.get("unit_id"):
                        affected.add(unit_id)

            units = deepcopy(state.get("interview_units", {}))
            active = state.get("active_unit_id")
            if affected:
                active = sorted(
                    affected,
                    key=lambda unit_id: (
                        units.get(unit_id, {}).get("order", 0),
                        unit_id,
                    ),
                )[0]
                _activate(units, active, status="reopened")
                units[active]["reopened_reason"] = "source_correction"
            return {
                "employee_evidence": evidence,
                "evolving_understanding": understanding,
                "interview_units": units,
                "active_unit_id": active,
                "revision": revision + 1,
            }

        if kind == "add_review":
            queue = deepcopy(state.get("review_queue", {}))
            review = deepcopy(command["review"])
            queue[review["id"]] = review
            return {"review_queue": queue, "revision": revision + 1}

        if kind == "decide_review":
            queue = deepcopy(state["review_queue"])
            review_id = command["review_id"]
            review = queue[review_id]
            decision = command["decision"]
            if decision == "defer":
                review["status"] = "deferred"
                return {"review_queue": queue, "revision": revision + 1}
            if decision == "reject":
                review["status"] = "rejected"
                return {"review_queue": queue, "revision": revision + 1}
            if decision not in {"accept", "edit_accept"}:
                raise ValueError(f"unknown review decision: {decision}")

            operations = deepcopy(
                command.get("edited_operations", review.get("operations", []))
            )
            artifact = state.get("approved_artifact", {})
            if not _operations_are_current(artifact, operations):
                review["status"] = "stale"
                return {"review_queue": queue, "revision": revision + 1}
            review["status"] = "accepted"
            review["applied_operations"] = operations
            return {
                "review_queue": queue,
                "approved_artifact": _apply_operations(artifact, operations),
                "revision": revision + 1,
            }

        if kind == "direct_edit":
            artifact = state.get("approved_artifact", {})
            operations = deepcopy(command["operations"])
            if not _operations_are_current(artifact, operations):
                raise ValueError("direct edit read-set is stale")
            return {
                "approved_artifact": _apply_operations(artifact, operations),
                "revision": revision + 1,
            }

        if kind == "require_clarification":
            request = deepcopy(command["request"])
            request["status"] = "pending"
            required = deepcopy(state.get("required_inputs", {}))
            required[request["id"]] = request

            units = deepcopy(state.get("interview_units", {}))
            affected_unit = request["affected_unit_id"]
            units[affected_unit]["status"] = "blocked"
            safe = _ordered_candidates(units, {"pending", "deferred"})
            active = safe[0] if safe else None
            if active is not None:
                _activate(units, active)
            return {
                "required_inputs": required,
                "interview_units": units,
                "active_unit_id": active,
                "revision": revision + 1,
            }

        raise ValueError(f"unknown command kind: {kind}")

    def route_after_command(state: ConsultantPurposeState) -> str:
        if state["command"]["kind"] == "require_clarification":
            return "await_clarification"
        return "done"

    def await_clarification(
        state: ConsultantPurposeState,
    ) -> ConsultantPurposeState:
        request = state["command"]["request"]
        answer = interrupt(
            {
                "kind": "required_clarification",
                "request_id": request["id"],
                "reason": request["reason"],
                "question": request["question"],
                "choices": request["choices"],
                "affected_unit_id": request["affected_unit_id"],
                "affected_branch": request["affected_branch"],
            }
        )
        required = deepcopy(state["required_inputs"])
        required[request["id"]]["status"] = "resolved"
        required[request["id"]]["answer"] = deepcopy(answer)

        evidence = deepcopy(state.get("employee_evidence", {}))
        evidence[request["id"]] = {
            "speaker": "employee",
            "choice": answer["choice"],
            "text": answer["text"],
            "reason": "required_clarification",
        }
        units = deepcopy(state["interview_units"])
        affected_unit = request["affected_unit_id"]
        _activate(units, affected_unit, status="reopened")
        units[affected_unit]["reopened_reason"] = "clarification_resolved"
        return {
            "required_inputs": required,
            "employee_evidence": evidence,
            "interview_units": units,
            "active_unit_id": affected_unit,
            "revision": state.get("revision", 0) + 1,
        }

    builder = StateGraph(ConsultantPurposeState)
    builder.add_node("apply_command", apply_command)
    builder.add_node("await_clarification", await_clarification)
    builder.add_edge(START, "apply_command")
    builder.add_conditional_edges(
        "apply_command",
        route_after_command,
        {"await_clarification": "await_clarification", "done": END},
    )
    builder.add_edge("await_clarification", END)
    return builder.compile(checkpointer=checkpointer)
