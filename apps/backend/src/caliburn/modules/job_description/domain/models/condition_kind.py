"""共通條件的五種分類；實際適用範圍由正文說明。"""

from enum import StrEnum


class ConditionKind(StrEnum):
    WORK_ENVIRONMENT = "work_environment"
    SCHEDULE_TRAVEL = "schedule_travel"
    SHARED_AUTHORITY = "shared_authority"
    SHARED_COLLABORATION = "shared_collaboration"
    QUALIFICATION = "qualification"
