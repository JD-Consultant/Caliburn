"""JD 同組資源的相對位置意圖；省略 placement 由個別修改輸入表達。"""

from uuid import UUID

from caliburn.shared.application.base_dto import BaseDTO


class PlacementInput(BaseDTO):
    """移至錨點前；沒有錨點時移至目前所屬集合末尾。"""

    before_id: UUID | None = None
