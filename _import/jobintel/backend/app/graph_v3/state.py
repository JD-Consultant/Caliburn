from typing import Any, TypedDict


class ProfilePick(TypedDict):
    candidates: list[dict]
    selected_ocs_codes: list[str]   # 複選，順序=優先度
    selected_ocs_code: str | None   # primary = selected_ocs_codes[0]（相容既有欄位）


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


class KsaState(TypedDict):
    pool: KsaDraft                 # fetch_ksa_pool 填的職類池候選
    by_task: dict[str, dict]       # task_key -> {"knowledge": list[dict], "skills": list[dict]}
    attitudes: list[dict]          # 全域 A（curate_attitudes 填）
    ks_index: int                  # 觀測用進度


class InterviewState(TypedDict):
    job_profile_id: str
    job_title: str
    job_summary: str
    current_step: str            # pick_profile|task_pool|deep|fetch_ksa_pool|curate_ks|curate_attitudes|build_doc|done
    profile: ProfilePick
    tasks: list[dict]            # editable; each item carries provenance
    deep: DeepState
    ksa: KsaState
    document: dict | None


def new_state(*, job_profile_id: str, job_title: str, job_summary: str = "") -> InterviewState:
    return {
        "job_profile_id": job_profile_id,
        "job_title": job_title,
        "job_summary": job_summary,
        "current_step": "pick_profile",
        "profile": {"candidates": [], "selected_ocs_codes": [], "selected_ocs_code": None},
        "tasks": [],
        "deep": {"current_task_index": 0, "slots_by_task": {}, "missing_fields": [],
                 "completed_task_ids": [], "retry": {}},
        "ksa": {"pool": {"knowledge": [], "skills": [], "attitudes": []},
                "by_task": {}, "attitudes": [], "ks_index": 0},
        "document": None,
    }


def task_key(task: dict) -> str:
    """逐任務穩定鍵：優先 indexer task_id，否則 task_name。"""
    return (task.get("indexer_ref") or {}).get("task_id") or task["task_name"]
