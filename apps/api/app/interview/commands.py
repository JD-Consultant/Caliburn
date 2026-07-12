"""指令詞彙表 v1(T5;ADR 0023 §決定2、spec §5)。

兩層防線:
1. **受限解碼層**——`turn_output_schema()` 手工建構 strict-subset JSON schema
   (只用確定安全的關鍵字:type/properties/required/additionalProperties/enum/anyOf/items;
   全欄位列 required、可空用 ["T","null"];tagged union 用 anyOf + type enum 單值)。
   `ask_choice` 變體只在呼叫端給了池 id 時才進 schema——LLM 結構上發不出沒有選項的選單。
2. **pydantic 層**——`TurnOutput.model_validate()` 解碼後的語義驗證(discriminated union)。

LLM 不選寫入通道、不能繞 guard——那些在 executor(T6)。純函式、零 I/O。
"""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field


class _Cmd(BaseModel):
    model_config = ConfigDict(extra="ignore")


class Reply(_Cmd):
    type: Literal["reply"]
    text: str


class Ask(_Cmd):
    type: Literal["ask"]
    question: str
    target_path: str | None = None   # 指向槽位 → 記追問預算;None = 開放問


class AskChoice(_Cmd):
    type: Literal["ask_choice"]
    question: str
    options: list[str]               # 池內 id(schema 層以 enum 鎖死)
    target_path: str | None = None


class SetSlot(_Cmd):
    type: Literal["set_slot"]
    path: str
    value: str | float
    quote: str                       # 員工原話(executor 驗逐字稿子串)


class CorrectSlot(_Cmd):
    type: Literal["correct_slot"]
    path: str
    value: str | float
    quote: str


class AddTask(_Cmd):
    type: Literal["add_task"]
    unit_ref: str                    # 掛哪個職責(_uid 或顯示碼)
    name: str
    quote: str


class AddDuty(_Cmd):
    type: Literal["add_duty"]
    name: str
    quote: str


class Skip(_Cmd):
    type: Literal["skip"]
    path: str
    reason: str                      # justified skip(落 trace 供稽核)


class Advance(_Cmd):
    type: Literal["advance"]
    next_focus: str                  # 下一任務 ref 或 "review"


Command = Annotated[
    Union[Reply, Ask, AskChoice, SetSlot, CorrectSlot, AddTask, AddDuty, Skip, Advance],
    Field(discriminator="type"),
]


class TurnOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    commands: list[Command]
    saturation: bool = False         # 對當前焦點「再問也無新資訊」信號(三重保險之一)


# --- strict-subset schema 建構器:已搬 schema_utils(ADR 0030 T3)——
# 轉口供本檔與 v1 測試沿用;本檔其餘為 v1 死碼,T12 隨檔退場。
from app.interview.schema_utils import _obj, _s, _variant  # noqa: E402,F401


def turn_output_schema(choice_ids: list[str] | None = None,
                       slot_paths: list[str] | None = None) -> dict:
    """slot_paths 給了就把寫入類 path(set/correct/skip)鎖成 enum——槽位是目錄類值,
    LLM 結構上發不出幽靈槽(實戰教訓:曾發明 details.process/tool/exception)。"""
    nullable_str = _s(["string", "null"])
    str_or_num = _s(["string", "number"])
    path_s = {"enum": list(slot_paths)} if slot_paths else _s("string")
    variants = [
        _variant("reply", text=_s("string")),
        _variant("ask", question=_s("string"), target_path=nullable_str),
        _variant("set_slot", path=path_s, value=str_or_num, quote=_s("string")),
        _variant("correct_slot", path=path_s, value=str_or_num, quote=_s("string")),
        _variant("add_task", unit_ref=_s("string"), name=_s("string"), quote=_s("string")),
        _variant("add_duty", name=_s("string"), quote=_s("string")),
        _variant("skip", path=path_s, reason=_s("string")),
        _variant("advance", next_focus=_s("string")),
    ]
    if choice_ids:
        variants.insert(2, _variant(
            "ask_choice",
            question=_s("string"),
            options={"type": "array", "items": {"type": "string", "enum": list(choice_ids)}},
            target_path=nullable_str,
        ))
    return _obj({
        "commands": {"type": "array", "items": {"anyOf": variants}},
        "saturation": _s("boolean"),
    })
