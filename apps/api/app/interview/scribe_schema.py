"""書記兩通道 schema(v2;ADR 0027、spec 2026-07-08 §3.1)。

書記(獨立抽取 pass)把員工發言轉結構化寫入,走既有 select_schema 受限解碼路。
**兩通道**(§9.1「官方=參考,寫入分兩條」):
- 池通道(record_*_pool):對上官方 → pool_id 從當回合合法池 enum 挑,**零幻覺**
  (宣稱官方的必真官方);官方碼結構上編不出來。
- 自訂通道(record_*_custom / draft_indicator / add_custom_task):對不上/更細/官方沒有 →
  自由 name/text,但 **quote 必填**(executor 驗逐字稿子串;§3.2)。

設計(T3):**分離變體、每個 enum 全鎖死、不賭 nullable-enum**——最強零幻覺保證。
池空/無 task → 不生該變體(fail-closed;§7.3);永遠保留 `none` 逃生口
(GPT-5.6/§2.8:強迫工具呼叫會虛構輸入,schema 給「無可記」出口、寧 null 不猜)。

kind↔pool_id 的語義一致(pool_id 確屬 pools[kind])= executor(T4)持 knowledge 驗;
本層只保證 pool_id ∈ 合法池聯集(生成期)+ 結構(pydantic)。LLM 不選通道、不繞 guard。
"""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field

from app.interview.schema_utils import _obj, _s, _variant

# 能力區塊 kind(task-scoped 三類;態度池通道 0028 D3 退場——收尾 attitudes_pass 整體編碼,
# 逐回合僅剩 record_attitude_custom 機會性提議)
TASK_KINDS = ("outputs", "knowledge", "skills")


# --- strict-subset schema 建構器 ---

def scribe_schema(*, slot_paths: list[str], pools: dict[str, list[str]],
                  task_keys: list[str], unit_keys: list[str]) -> dict:
    """回本回合合法的書記 schema。輸入(由程式注入,非 LLM 產):
    - slot_paths:本回合可寫的細項槽 path(枚舉;沿 v1 turn_output 的 slot enum)。
    - pools:kind → 官方 pool_id 清單(items:match/occupation_brief 得來)。
    - task_keys:文件現有任務 path(record 掛靠與跨任務歸位的 enum)。
    - unit_keys:文件現有職責 path(add_custom_task 掛靠)。
    """
    variants: list[dict] = []

    if slot_paths:
        variants.append(_variant(
            "set_slot", path={"enum": list(slot_paths)},
            value=_s(["string", "number"]), quote=_s("string")))

    task_pool_kinds = [k for k in TASK_KINDS if pools.get(k)]
    task_pool_ids = sorted({pid for k in task_pool_kinds for pid in pools[k]})
    if task_keys and task_pool_ids:
        variants.append(_variant(
            "record_task_pool", kind={"enum": task_pool_kinds},
            task={"enum": list(task_keys)}, pool_id={"enum": task_pool_ids},
            quote=_s("string")))

    if task_keys:
        variants.append(_variant(
            "record_task_custom", kind={"enum": list(TASK_KINDS)},
            task={"enum": list(task_keys)}, name=_s("string"), quote=_s("string")))
        variants.append(_variant(
            "draft_indicator", task={"enum": list(task_keys)},
            text=_s("string"), quote=_s("string")))
        # 態度由任務故事編碼而來(§15.3)→ 與 task 情境綁定,無 task 不記
        variants.append(_variant("record_attitude_custom", name=_s("string"), quote=_s("string")))

    if unit_keys:
        variants.append(_variant(
            "add_custom_task", unit_ref={"enum": list(unit_keys)},
            name=_s("string"), quote=_s("string")))

    variants.append(_variant("none"))     # 逃生口:本句無可記(永遠在)

    return _obj({"records": {"type": "array", "items": {"anyOf": variants}}})


# --- pydantic 結構驗證(語義 kind↔pool_id↔quote 在 executor/T4) ---

class _Rec(BaseModel):
    model_config = ConfigDict(extra="ignore")


class RecordTaskPool(_Rec):
    type: Literal["record_task_pool"]
    kind: Literal["outputs", "knowledge", "skills"]
    task: str
    pool_id: str
    quote: str


class RecordTaskCustom(_Rec):
    type: Literal["record_task_custom"]
    kind: Literal["outputs", "knowledge", "skills"]
    task: str
    name: str
    quote: str


class RecordAttitudeCustom(_Rec):
    type: Literal["record_attitude_custom"]
    name: str
    quote: str


class DraftIndicator(_Rec):
    type: Literal["draft_indicator"]
    task: str
    text: str
    quote: str


class SetSlot(_Rec):
    type: Literal["set_slot"]
    path: str
    value: str | float
    quote: str


class AddCustomTask(_Rec):
    type: Literal["add_custom_task"]
    unit_ref: str
    name: str
    quote: str


class NoRecord(_Rec):
    type: Literal["none"]


ScribeRecord = Annotated[
    Union[SetSlot, RecordTaskPool, RecordTaskCustom,
          RecordAttitudeCustom, DraftIndicator, AddCustomTask, NoRecord],
    Field(discriminator="type"),
]


class ScribeOutput(BaseModel):
    model_config = ConfigDict(extra="ignore")
    records: list[ScribeRecord]
