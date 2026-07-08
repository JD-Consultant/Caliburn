"""書記施作器 + 服務(v2;ADR 0027 §3、spec 2026-07-08 §3.2、§16.3)。

- apply_scribe(T4a,純函式):把驗證過的 ScribeRecord 確定性落文件。
  重用 executor 守衛(quote_verified/resolve/set_at);新增能力區塊/態度 append。
  兩通道:池項(pool_id∈pools[kind] 語義守衛 → 直寫官方碼+名)/ 自訂(→建議層,附 quote)。
- scribe_pass(T4b):LLM 編排(建 schema 輸入→select_schema→apply_scribe→重試/backstop)。

信任機制:LLM 選通道靠 schema(T3),值落地靠這裡的確定性守衛——一件繞不過。
風險分層(pending 標記/tier)= T5;本層預設池項直寫、自訂/draft/add_task 建議。
"""
import copy
from dataclasses import dataclass, field

from app.interview.executor import get_at, quote_verified, set_at, writable_path

# 能力區塊 kind → 條目形狀(CodeName{code,name} / CodeText{code,text})
_BLOCK_FIELDS = {"outputs": "name", "knowledge": "name", "skills": "name",
                 "indicators": "text"}


@dataclass
class ScribeResult:
    new_doc: dict | None = None            # None = 無直改
    evidence: list[dict] = field(default_factory=list)
    suggestions: list[dict] = field(default_factory=list)
    guard_log: list[str] = field(default_factory=list)


def _first_block(task: dict) -> dict:
    """回任務第一個能力區塊(缺則建一塊)。呼叫端須已在 work(deep copy)上操作。"""
    blocks = task.setdefault("competency_blocks", [])
    if not blocks:
        blocks.append({})
    return blocks[0]


def _append_item(block: dict, kind: str, item: dict) -> None:
    block.setdefault(kind, []).append(item)


def apply_scribe(records: list[dict], *, doc: dict, pool_items: dict[str, str],
                 pools: dict[str, list[str]], employee_texts: list[str],
                 human_touched: list[str]) -> ScribeResult:
    """records=已過 pydantic 的 ScribeRecord dict 列表。輸入 doc 不變;有直改才回 new_doc。"""
    res = ScribeResult()
    work: dict | None = None
    touched = set(human_touched or [])

    def _doc() -> dict:
        nonlocal work
        if work is None:
            work = copy.deepcopy(doc)
        return work

    def _task_node(task_path: str) -> dict | None:
        node = get_at(_doc(), task_path)
        return node if isinstance(node, dict) else None

    for rec in records:
        t = rec.get("type")

        if t == "none":
            continue

        # 引文守衛(所有寫入類都要;none 除外)
        quote = rec.get("quote", "")
        verified = quote_verified(quote, employee_texts)

        if t in ("record_task_pool", "record_attitude_pool"):
            kind = "attitudes" if t == "record_attitude_pool" else rec["kind"]
            pid = rec["pool_id"]
            if pid not in (pools.get(kind) or []):        # 語義守衛:kind↔pool_id 一致
                res.guard_log.append(f"drop:pool_id {pid} 不屬 {kind} 池")
                continue
            item = {"code": pid, "name": pool_items.get(pid)}
            path = ("ocs_attitude.attitudes" if kind == "attitudes"
                    else f"{rec['task']}.competency_blocks.0.{kind}")
            res.evidence.append({"doc_path": path, "quote": quote, "verified": verified})
            if not verified:
                res.guard_log.append(f"drop:{path}(quote 未驗證)")
                continue
            if kind == "attitudes":
                (_doc().setdefault("ocs_attitude", {}).setdefault("attitudes", [])).append(item)
            else:
                task = _task_node(rec["task"])
                if task is None:
                    res.guard_log.append(f"drop:{path}(task 解析不到)")
                    continue
                _append_item(_first_block(task), kind, item)
            res.guard_log.append(f"write:{path}={pid}")

        elif t in ("record_task_custom", "record_attitude_custom"):
            kind = "attitudes" if t == "record_attitude_custom" else rec["kind"]
            name = rec["name"]
            path = ("ocs_attitude.attitudes" if kind == "attitudes"
                    else f"{rec.get('task', '')}.competency_blocks.0.{kind}")
            res.evidence.append({"doc_path": path, "quote": quote, "verified": verified})
            res.suggestions.append({                       # 自訂一律建議層(人核准)
                "doc_path": path, "old_value": None,
                "new_value": {"code": None, "name": name},
                "reason": f"自訂{kind}(公版外;quote:{quote[:30]})",
            })
            res.guard_log.append(f"suggest:{path}(custom:{name})")

        elif t == "draft_indicator":
            path = f"{rec['task']}.competency_blocks.0.indicators"
            res.evidence.append({"doc_path": path, "quote": quote, "verified": verified})
            res.suggestions.append({                       # 指標=AI 草擬→人確認(§15.3)
                "doc_path": path, "old_value": None,
                "new_value": {"code": None, "text": rec["text"]},
                "reason": f"AI 草擬指標(待確認;quote:{quote[:30]})",
            })
            res.guard_log.append(f"suggest:{path}(draft_indicator)")

        elif t == "add_custom_task":
            name = rec["name"]
            res.evidence.append({"doc_path": f"add_task:{name}", "quote": quote,
                                 "verified": verified})
            res.suggestions.append({
                "doc_path": f"add_task:{name}", "old_value": None,
                "new_value": {"unit_ref": rec["unit_ref"], "name": name},
                "reason": "抓漏(公版外任務,一律人核准)",
            })
            res.guard_log.append(f"suggest:add_task:{name}")

        elif t == "set_slot":
            path = rec["path"]
            res.evidence.append({"doc_path": path, "quote": quote, "verified": verified})
            if not writable_path(path):
                res.guard_log.append(f"drop:{path}(未知槽)")
                continue
            if path in touched:                            # 通道分流(ADR 0025)
                res.suggestions.append({
                    "doc_path": path, "old_value": get_at(doc, path),
                    "new_value": rec["value"], "reason": f"訪談(quote:{quote[:30]})"})
                res.guard_log.append(f"suggest:{path}(human_touched)")
            elif not verified:
                res.guard_log.append(f"drop:{path}(quote 未驗證)")
            elif set_at(_doc(), path, rec["value"]):
                res.guard_log.append(f"write:{path}")
            else:
                res.guard_log.append(f"drop:{path}(path 不存在)")

    res.new_doc = work
    return res
