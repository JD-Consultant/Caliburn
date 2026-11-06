"""輪次不存在、准入衝突與受理結果未知的明確錯誤。"""


class TurnNotFound(LookupError):
    pass


class TurnConflict(RuntimeError):
    pass


class AgentUnavailable(RuntimeError):
    pass
