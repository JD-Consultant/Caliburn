"""Shared helpers for locating a task inside an OCS document dict.

Pure dict helpers (no pydantic / DB). Used by the ``/ai/*`` route adapters to
resolve a ``task_key`` (the human task code, e.g. ``"T1.1"``) to the task object
so its ``provenance.id`` (catalog UUID) and current name can be read.
"""
from __future__ import annotations


def find_task(content: dict, task_key: str) -> dict | None:
    """Return the task dict whose ``task_codes[*].code`` == ``task_key``, else None."""
    if not task_key:
        return None
    for unit in (content.get("ocs_content") or {}).get("ocu_units") or []:
        for task in unit.get("tasks") or []:
            for tc in task.get("task_codes") or []:
                if isinstance(tc, dict) and tc.get("code") == task_key:
                    return task
    return None


def task_name(task: dict) -> str:
    """First task_code name, or ''."""
    tcs = task.get("task_codes") or []
    return (tcs[0].get("name") if tcs and isinstance(tcs[0], dict) else "") or ""


def catalog_id(task: dict) -> str:
    """provenance.id (catalog UUID), or '' for custom/cherry-picked tasks."""
    return (task.get("provenance") or {}).get("id") or ""


def catalog_ref(task: dict) -> dict:
    """provenance (ocs_code, task_code) for catalog tasks; empty strings for custom."""
    p = task.get("provenance") or {}
    return {"ocs_code": p.get("ocs_code") or "", "task_code": p.get("task_code") or ""}
