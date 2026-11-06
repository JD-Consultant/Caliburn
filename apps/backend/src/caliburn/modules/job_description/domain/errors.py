"""JD 領域規則拒絕的具名例外，不含傳輸或儲存細節。"""

from caliburn.shared.domain.domain_error import DomainError


class InvalidNameError(DomainError):
    """具名條目名稱清洗後不可空白或超過 255 個 code points。"""


class DuplicateNameError(DomainError):
    """同一名稱範圍內不可重名。"""


class DuplicateIdentityError(DomainError):
    """同種類的條目身分已存在。"""


class InvalidJobDescriptionOwnershipError(DomainError):
    """JD 內部成員的歸屬必須與所屬聚合根一致。"""


class InvalidCompetencyLevelError(DomainError):
    """職能級別不在 1–6 的有效範圍。"""


class InvalidTextError(DomainError):
    """成果、工作要求或條件不可使用空白正文。"""


class TaskOutcomeNotFoundError(DomainError):
    """指定成果不存在於此任務。"""


class TaskRequirementNotFoundError(DomainError):
    """指定工作要求不存在於此任務。"""


class InvalidTaskOrderError(DomainError):
    """排序目標或錨點不在同一集合，或錨點指向自己。"""


class DutyNotFoundError(DomainError):
    """指定職責不存在於此 JD。"""


class TaskNotFoundError(DomainError):
    """指定任務不存在於此 JD。"""


class KnowledgeNotFoundError(DomainError):
    """指定知識不存在於此 JD。"""


class SkillNotFoundError(DomainError):
    """指定技能不存在於此 JD。"""


class InvalidTaskReferenceError(DomainError):
    """任務分類或引用目標不存在於此 JD 的對應種類。"""


class CollaborationNotFoundError(DomainError):
    """指定協作不存在於此 JD。"""


class JobConditionNotFoundError(DomainError):
    """指定條件不存在於此 JD。"""


class InvalidJobDescriptionRecordOrderError(DomainError):
    """排序錨點須是同一 JD、同一集合／類別的其他條目。"""


class InvalidCollaborationNameError(DomainError):
    """協作對象不可為空白。"""


class InvalidDefinitionOrderError(DomainError):
    """總覽排序目標與錨點須是同組的不同條目。"""


class CitationTargetNotFoundError(DomainError):
    """引用目標不存在於指定 JD 的指定種類。"""


class CitationNotFoundError(DomainError):
    """引用不存在於目前 JD。"""


class InvalidCitationError(DomainError):
    """引用歸屬、來源身分或唯一性不符。"""
