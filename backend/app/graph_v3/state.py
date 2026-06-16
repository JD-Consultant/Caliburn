from typing import Any, TypedDict


class ProfilePick(TypedDict):
    candidates: list[dict]
    selected_ocs_code: str | None


class DeepState(TypedDict):
    current_task_index: int
    slots_by_task: dict[str, dict]
    missing_fields: list[str]
    completed_task_ids: list[str]
    retry: dict[str, int]


class KsaDraft(TypedDict):
    knowledge: list[dict]
    skills: list[dict]
    attitudes: list[dict]


class InterviewState(TypedDict):
    job_profile_id: str
    job_title: str
    job_summary: str
    current_step: str            # pick_profile|task_pool|deep|assemble_ksa|build_doc|done
    profile: ProfilePick
    tasks: list[dict]            # editable; each item carries provenance
    deep: DeepState
    ksa: KsaDraft
    document: dict | None


def new_state(*, job_profile_id: str, job_title: str, job_summary: str = "") -> InterviewState:
    return {
        "job_profile_id": job_profile_id,
        "job_title": job_title,
        "job_summary": job_summary,
        "current_step": "pick_profile",
        "profile": {"candidates": [], "selected_ocs_code": None},
        "tasks": [],
        "deep": {"current_task_index": 0, "slots_by_task": {}, "missing_fields": [],
                 "completed_task_ids": [], "retry": {}},
        "ksa": {"knowledge": [], "skills": [], "attitudes": []},
        "document": None,
    }
