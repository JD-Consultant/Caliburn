from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import JobProfile

PERSISTENT_KEYS: list[str] = [
    "extracted_tasks",
    "current_task_index",
    "task_extraction_round",
    "missing_fields",
    "star_slots_by_task",
    "star_completed_task_ids",
    "behavior_indicators",
    "indicator_retry_counts",
    "ksa_items",
    "ocs_document",
    "icap_candidates",
    "icap_hit",
    "icap_mode",
    "interview_readiness_detail",
    "interview_ready",
    "interview_ready_confirmed",
]

_DEFAULTS: dict = {
    "extracted_tasks":            [],
    "current_task_index":         0,
    "task_extraction_round":      0,
    "missing_fields":             [],
    "star_slots_by_task":         {},
    "star_completed_task_ids":    [],
    "behavior_indicators":        [],
    "indicator_retry_counts":     {},
    "ksa_items":                  [],
    "ocs_document":               {},
    "icap_candidates":            [],
    "icap_hit":                   False,
    "icap_mode":                  "company_defined",
    "interview_readiness_detail": {},
    "interview_ready":            False,
    "interview_ready_confirmed":  False,
}


class StateService:
    @staticmethod
    def build_initial_state(
        profile: JobProfile,
        phase: str,
        user_input: str,
        history: list[dict],
    ) -> dict:
        saved = profile.graph_state or {}
        return {
            "job_profile_id":            str(profile.id),
            "job_title":                 profile.job_title,
            "department":                profile.department or "",
            "job_summary":               profile.job_summary or "",
            "current_stage":             profile.stage or "basic_info",
            "phase":                     phase,
            "messages":                  history,
            "user_input":                user_input,
            "ai_response":               "",
            "document_ready":            False,
            "interview_readiness_score": 0.0,
            **{k: saved.get(k, _DEFAULTS[k]) for k in PERSISTENT_KEYS},
        }

    @staticmethod
    def extract_persistent(accumulated: dict) -> dict:
        return {k: accumulated.get(k, _DEFAULTS[k]) for k in PERSISTENT_KEYS}

    @staticmethod
    async def persist(
        db: AsyncSession,
        profile_id: UUID,
        final_stage: str,
        graph_state: dict,
    ) -> None:
        profile = await db.get(JobProfile, profile_id)
        if profile:
            profile.stage = final_stage
            profile.graph_state = graph_state
        await db.commit()
