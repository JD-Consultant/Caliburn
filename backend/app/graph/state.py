from typing_extensions import TypedDict


class InterviewState(TypedDict):
    # job profile basics
    job_profile_id: str
    job_title: str
    department: str
    job_summary: str

    # flow control
    current_stage: str
    phase: str          # general | star_<task_id> | five_w2h_<task_id>

    # conversation (read-only per API call, loaded from DB)
    messages: list[dict]  # [{ role, content, phase }]
    user_input: str
    ai_response: str

    # iCAP RAG results
    icap_candidates: list[dict]
    icap_hit: bool
    icap_mode: str   # "reference" | "hybrid" | "company_defined"

    # task extraction
    extracted_tasks: list[dict]
    responsibility_groups: list[dict]
    responsibility_grouping_round: int  # 0=not yet, 1=shown awaiting confirm, 2+=confirmed into STAR
    current_task_index: int
    task_extraction_round: int   # 0=not yet, 1=shown awaiting confirm, 2+=confirmed into responsibility grouping

    # STAR slot filling
    star_slots_by_task: dict      # { task_id: { "S": str|None, "T": str|None, "A": str|None, "R": str|None } }
    star_completed_task_ids: list[str]  # task_ids that have all 4 slots filled

    # 5W2H completeness
    missing_fields: list[str]

    # interview readiness（每 call 重算；detail 持久化供前端顯示）
    interview_readiness_score: float
    interview_readiness_detail: dict   # ReadinessResult dict
    interview_ready: bool
    interview_ready_confirmed: bool    # True = 用戶已回應過「接下來整理清單」的訊息，可進 task_extraction

    # final outputs
    behavior_indicators: list[dict]
    indicator_retry_counts: dict  # { task_id: int } — prevents infinite quality-retry loops
    ksa_items: list[dict]         # flat K/S/A list (legacy compat)
    ocs_document: dict            # full OCS-compliant JSON structure
    document_ready: bool
