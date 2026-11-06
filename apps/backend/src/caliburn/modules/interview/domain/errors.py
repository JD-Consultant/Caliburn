"""訪談規則拒絕；訊息不包含員工原文。"""


class InvalidAnswerError(ValueError):
    def __init__(self, message: str, *, field: str = "selected") -> None:
        super().__init__(message)
        self.field = field


class InterviewTurnWithdrawnError(ValueError):
    """已撤回輪次不得追加。"""


class InterviewTurnKindError(ValueError):
    """一般訪談用例不能操作固定開場。"""


class InterviewInputConflictError(ValueError):
    """同一輪次或開場的原始文字不一致。"""


class InterviewQuestionNotFoundError(ValueError):
    """原題不在指定的訪談輪次。"""


class InterviewAnswerConflictError(ValueError):
    """原題已有不同的正式答案。"""
