"""事件收割 pass(ADR 0033 T7)——BEI 事後編碼的即時版;**P(行為指標)的結構性的家**。

顧問 close_episode(或 guardrail auto-close)時,對**該事件期間的逐字稿**跑一次
受限抽取:起草行為指標(STAR 句式)、補 K/S、掛回被觸及的任務——走既有
op→verify→`_pending` 綠字。與書記分工(spec §3.5):書記=逐回合機會性(員工明說
標準時逐字掛);收割=事件級系統性(從敘事提煉)。重複由 verify 的 dup 檢查擋。

家規:
- 教材**全文注入**(behavior-indicator+ks-distinction)——Agent Skills 的
  progressive disclosure「按需全文」層:只在收割(事件結束一呼)載入,書記逐回合
  不背這 500 行(BUG-2 的正解:P 教材真的送到寫 P 的角色手上)。
- quote **跨多輪定位**(episode 逐字稿範圍;書記是單輪,故不能共用 records_to_ops
  的固定 turn_id)——每筆 record 的 quote 定位到範圍內正確那一輪再建 op。
- 執行腦(小模型 role=select);fail-open(LLM 掛不擋回合,漏的下事件/收尾再收)。
"""
import logging

from app.interview.scribe import (
    ScribeResult, build_pool_inputs, land_ops, records_to_ops,
)
from app.interview.scribe_schema import ScribeOutput, scribe_schema
from app.interview.skill_loader import load_skill
from app.interview.slots import SLOT_DEFS
from app.interview.trace_utils import canonical_hash
from app.interview.verify import normalize

logger = logging.getLogger(__name__)

# 收割 system prompt(BEI 編碼員;GPT-5.6 outcome-first——給成功判準不給步驟)。
# 教材全文在 build 時附(behavior-indicator/ks-distinction),此處只定人格與判準。
HARVEST_SYS = (
    "你是行為事件編碼員(BEI)。剛結束一段員工親述的**具體事件**,你的工作是把這段"
    "故事編碼成職務說明書的結構化欄位。成功=這個事件裡**可觀察的能力證據**都被萃取:\n"
    "- 行為指標(draft_indicator):他講到『怎樣算做好/怎麼驗收/出錯怎麼發現』時,"
    "用 STAR 句式起草——情境+可觀察行為+標準;動詞必須可觀察(見下方教材)。\n"
    "- 知識/技能(record_task_*):故事裡顯露的 K/S,對得上官方池就走池、否則自訂。\n"
    "- 細項槽(set_slot):頻率/工具/協作/例外等他講到的事實。\n"
    "規則:quote 逐字照抄他原句(可截段不可改字);只編他真的說過的,聽不出就不編;"
    "掛到對的任務(一個事件常橫跨多任務,各掛各的)。無可編就回 records=[{\"type\":\"none\"}]。"
)

_MATERIALS = ("behavior-indicator", "ks-distinction")


def _episode_turns(turns: dict[int, str], opened_seq: int) -> dict[int, str]:
    """事件期間的員工逐字稿(seq ≥ 開場輪)。"""
    return {s: t for s, t in turns.items() if s >= opened_seq}


def _locate(quote: str, turns: dict[int, str]) -> int:
    """quote → 所在員工回合 seq(範圍內逐字子串;找不到回 0,verify 會擋)。"""
    q = normalize(quote)
    for seq, text in sorted(turns.items()):
        if q and q in normalize(text):
            return seq
    return 0


async def harvest_pass(llm, knowledge, *, doc: dict, turns: dict[int, str],
                       episode: dict, header_codes: set[str],
                       ref_ocs_codes: tuple[str, ...] = (),
                       max_retry: int = 1) -> ScribeResult:
    """收割一個事件。episode={target, opened_seq, ...};turns=全逐字稿。
    回 ScribeResult(new_doc 有落地才非 None;progressed=有 op 落地)。"""
    from app.interview import coverage as C

    ep_turns = _episode_turns(turns, int(episode.get("opened_seq") or 0))
    res = ScribeResult()
    if not ep_turns:
        return res

    task_keys = [tp for _, _, tp in C.iter_tasks(doc)]
    unit_keys = [f"ocs_content.ocu_units.{C._seg(u, i)}"
                 for i, u in enumerate((doc.get("ocs_content") or {}).get("ocu_units") or [])]
    slot_paths = [f"{tp}.details.{k}" for tp in task_keys for k in SLOT_DEFS]
    pools, pool_items = await build_pool_inputs(knowledge, doc, ref_ocs_codes)
    res.pools, res.pool_items = pools, pool_items
    schema = scribe_schema(slot_paths=slot_paths, pools=pools,
                           task_keys=task_keys, unit_keys=unit_keys)
    ref_codes = set(pool_items)

    materials = "\n\n".join(f"<判準教材:{m}>\n{load_skill(m)}\n</判準教材>" for m in _MATERIALS)
    story = "\n".join(f"[第{s}輪] {t}" for s, t in sorted(ep_turns.items()))
    prompt = (f"{HARVEST_SYS}\n\n{materials}\n\n任務清單:{task_keys}\n合法官方池:{pools}\n"
              f"<事件逐字稿>\n{story}\n</事件逐字稿>")
    res.llm_called = True
    res.prompt_hash = canonical_hash(prompt)
    res.tool_schema_hash = canonical_hash(schema)

    records = None
    for attempt in range(max_retry + 1):
        res.attempt_count = attempt + 1
        try:
            data = await llm.select_schema(prompt, schema, role="select",
                                           schema_name="harvest_output")
            records = [r.model_dump() for r in ScribeOutput.model_validate(data).records]
            break
        except Exception as exc:  # noqa: BLE001  (fail-open:收割掛不擋回合)
            logger.warning("harvest 抽取不合法(attempt %d):%s", attempt, str(exc)[:160])
    if records is None:
        res.records_failed = True
        res.outcome = "parse_failure"
        return res

    # 每筆 record 的 quote 跨多輪定位 → 用該輪 turn_id 建 op(書記單輪故不共用其 turn_id)
    ops: list[dict] = []
    for rec in records:
        if rec.get("type") == "none":
            continue
        tid = _locate(rec.get("quote") or "", ep_turns)
        rec_ops, g = records_to_ops([rec], turn_id=tid, pools=pools, pool_items=pool_items)
        ops += rec_ops
        res.guard_log.extend(g)
    if not ops:
        return res

    new_doc, guard, landed = land_ops(ops, doc=doc, turns=turns, ref_codes=ref_codes,
                                      header_codes=header_codes, pool_items=pool_items)
    res.new_doc = new_doc
    res.guard_log.extend(guard)
    res.ops = landed
    res.progressed = bool(landed)
    return res
