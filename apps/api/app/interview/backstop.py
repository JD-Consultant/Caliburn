"""backstop 收尾複查(v2;ADR 0027 第4組件、spec §6)。

收尾一呼、便宜模型、**只答兩題、只產建議**(§8.4「intelligence not actions」——提案給
單一 writer,不並行直寫):
- misses(完整性):員工說過、但對應必填縫隙仍空的原句。
- misattributed(歸屬):已寫值中,quote 不支持其值/答非該欄的項目。

schema 用自由字串 + **確定性後驗**(gap∈空縫、path∈已寫、quote 逐字驗)——backstop 只提案
人審,故不必生成期 enum 鎖死;後驗擋幻覺 gap/path/quote 即可(便宜且穩)。
"""
import logging
from dataclasses import dataclass, field

from app.interview.schema_utils import _obj, _s
from app.interview.verify import quote_verified

logger = logging.getLogger(__name__)

BACKSTOP_SYS = (
    "你是訪談品質複查員。給你:員工逐字稿、仍空的必填欄(gap)清單、已記錄的(path, quote)。"
    "只回答兩題,別的都不做:1) misses——員工說過、但對應某個『仍空必填欄』的原句(gap 用清單裡的、"
    "quote 逐字照抄員工的話)。2) misattributed——已記錄中,quote 不支持其欄位/答非該欄的項目"
    "(path 用清單裡的、reason 一句話)。找不到就回空陣列。嚴禁建議新內容、嚴禁改寫。"
)


def backstop_schema() -> dict:
    miss = _obj({"gap": _s("string"), "quote": _s("string")})
    misattr = _obj({"path": _s("string"), "reason": _s("string")})
    return _obj({
        "misses": {"type": "array", "items": miss},
        "misattributed": {"type": "array", "items": misattr},
    })


@dataclass
class BackstopResult:
    misses: list[dict] = field(default_factory=list)          # [{gap, quote}]
    misattributed: list[dict] = field(default_factory=list)   # [{path, reason}]

    def to_suggestions(self) -> list[dict]:
        """轉建議層(單一 writer 提案;人審)。miss→補漏建議(填該 gap);
        misattributed→出處疑慮旗標(不自動改,人裁)。"""
        out = []
        for m in self.misses:
            out.append({"doc_path": m["gap"], "old_value": None,
                        "new_value": m["quote"],
                        "reason": f"收尾補漏(員工說過卻沒記;quote:{m['quote'][:30]})"})
        for m in self.misattributed:
            out.append({"doc_path": m["path"], "old_value": None, "new_value": None,
                        "reason": f"出處疑慮:{m['reason'][:60]}"})
        return out


async def backstop_pass(llm, *, employee_texts: list[str], empty_gaps: list[dict],
                        recorded: list[dict]) -> BackstopResult:
    """收尾複查。empty_gaps=[{gap,label}]、recorded=[{path,quote}]。輸入不變;
    確定性後驗過的 misses/misattributed。無縫無寫 → 不呼 LLM(省成本)。"""
    if not empty_gaps and not recorded:
        return BackstopResult()

    gap_ids = {g["gap"] for g in empty_gaps}
    rec_paths = {r["path"] for r in recorded}
    prompt = (f"{BACKSTOP_SYS}\n\n<逐字稿>\n" + "\n".join(employee_texts) + "\n</逐字稿>\n"
              f"<仍空必填欄>\n" + "\n".join(f"{g['gap']} = {g['label']}" for g in empty_gaps) +
              f"\n</仍空必填欄>\n<已記錄>\n" +
              "\n".join(f"{r['path']} ← 「{r['quote']}」" for r in recorded) + "\n</已記錄>")
    try:
        data = await llm.select_schema(prompt, backstop_schema(), role="select",
                                       schema_name="backstop")
    except Exception as exc:  # noqa: BLE001  (backstop 是加分項,失敗不擋收尾)
        logger.warning("backstop 複查失敗(略過):%s", str(exc)[:120])
        return BackstopResult()

    # 確定性後驗:gap∈空縫 + quote 逐字;path∈已寫
    misses = [m for m in (data.get("misses") or [])
              if m.get("gap") in gap_ids and quote_verified(m.get("quote", ""), employee_texts)]
    misattr = [m for m in (data.get("misattributed") or []) if m.get("path") in rec_paths]
    return BackstopResult(misses=misses, misattributed=misattr)
