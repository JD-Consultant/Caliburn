"""契約 PendingMark(ADR 0030 T1):修訂標記選填欄位的 pydantic 端驗證。

驗證重點:
- PendingMark 型別存在且可解析(op/by/turn_id 必填;prev/src 選填;src.ref_urn 與
  src.quote 可並存或僅其一——「至少一」是 verify 層語意,不在 schema 強制)。
- 物件節點(CodeName/CodeText/TaskGroup/OcuUnit)有 `_pending` 選填欄位。
- scalar 容器(TaskDetails/OcsProfile)有集合式 `_pending`(槽名→PendingMark)。
- 不帶 `_pending` 的既有文件照常合法(非破壞性)。
"""

import pytest
from pydantic import ValidationError

from ocs_contract.models import (
    CodeName,
    CodeText,
    OcsProfile,
    OCSDocument,
    PendingMark,
    TaskDetails,
    TaskGroup,
)


def _alias_map(model_cls) -> dict[str, str]:
    """回 {alias或欄名: 欄名},讓測試不猜 codegen 對底線欄的命名策略。"""
    return {(f.alias or name): name for name, f in model_cls.model_fields.items()}


PENDING_ADD = {
    "op": "add",
    "by": "ai",
    "turn_id": 3,
    "src": {"quote": {"turn_id": 3, "text": "每週要跟三個部門開需求會議"}},
}

PENDING_MOD_BOTH_SRC = {
    "op": "mod",
    "by": "ai",
    "turn_id": 5,
    "prev": "舊值",
    "src": {
        "ref_urn": "ocs:unit:ABC1234:t2",
        "quote": {"turn_id": 5, "text": "其實現在改成雙週一次"},
    },
}


def test_pending_mark_parses_minimal_and_full():
    minimal = PendingMark.model_validate({"op": "del", "by": "ai", "turn_id": 1})
    assert minimal.model_dump(mode="json")["op"] == "del"
    full = PendingMark.model_validate(PENDING_MOD_BOTH_SRC)
    assert full.src.ref_urn == "ocs:unit:ABC1234:t2"
    assert full.src.quote.text == "其實現在改成雙週一次"
    assert full.prev == "舊值"


def test_pending_mark_rejects_bad_op_and_by():
    with pytest.raises(ValidationError):
        PendingMark.model_validate({"op": "replace", "by": "ai", "turn_id": 1})
    with pytest.raises(ValidationError):
        PendingMark.model_validate({"op": "add", "by": "human", "turn_id": 1})


@pytest.mark.parametrize("model_cls", [CodeName, CodeText, TaskGroup])
def test_object_nodes_have_pending_field(model_cls):
    assert "_pending" in _alias_map(model_cls)


def test_code_name_roundtrip_with_pending():
    node = CodeName.model_validate(
        {"code": None, "name": "跨部門需求協調", "_pending": PENDING_ADD}
    )
    dumped = node.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["_pending"]["op"] == "add"
    assert dumped["_pending"]["src"]["quote"]["turn_id"] == 3


def test_task_details_pending_is_per_slot_map():
    details = TaskDetails.model_validate(
        {"frequency": "每週", "_pending": {"frequency": PENDING_MOD_BOTH_SRC}}
    )
    dumped = details.model_dump(by_alias=True, exclude_none=True)
    assert dumped["_pending"]["frequency"]["prev"] == "舊值"


def test_profile_pending_covers_header_fields():
    profile = OcsProfile.model_validate(
        {
            "ocs_code": "ABC1234",
            "_pending": {
                "ocs_code": {
                    "op": "mod",
                    "by": "ai",
                    "turn_id": 9,
                    "prev": "ABC1234",
                    "src": {"ref_urn": "ocs:doc:XYZ9999"},
                }
            },
        }
    )
    dumped = profile.model_dump(mode="json", by_alias=True, exclude_none=True)
    assert dumped["_pending"]["ocs_code"]["op"] == "mod"


def test_document_without_pending_still_valid():
    doc = OCSDocument.model_validate({"ocs_profile": {"ocs_code": "ABC1234"}})
    dumped = doc.model_dump(by_alias=True, exclude_none=True)
    assert "_pending" not in dumped["ocs_profile"]
