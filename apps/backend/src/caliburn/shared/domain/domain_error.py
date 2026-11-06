"""具名領域失敗的共同例外類別。"""


class DomainError(Exception):
    """具體子類表達業務規則遭拒，不攜帶 HTTP 或儲存錯誤政策。"""
