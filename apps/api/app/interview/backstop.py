"""backstop 撿漏(v3;ADR 0030 T5)= periodic deterministic reconciliation sweep。

**禁令(§6.4,寫死):backstop 永不 LLM 化。** 主流共識「確定性檢查對 100% 輸出跑、
成本近零、先攔最常見遺漏」;要語意判斷的活輪不到兜底層做。

行為:每 N 回合掃「上次掃描後的員工逐字稿」,規則比對——
- 官方檢查表 unasked 任務名被提及、doc 無對應 → 產 held 追問(下輪由顧問吐出)。
- 官方池 K/S/O 名被提及、doc/_pending 無對應 → 同上。
命中只進 held 待問清單(intelligence not actions:提案給人/顧問,不動文件)。
v2 的 LLM 收尾複查已整段退場。
"""
from app.interview.verify import normalize

SWEEP_EVERY = 5          # 每 N 個員工回合掃一次(常數;校準縫)
_MIN_NAME_LEN = 3        # 太短的名稱(如「測試」)不比對,防雜訊命中


def _doc_texts(doc: dict) -> str:
    """文件現值+待審值的正規化串(命中判重用:已在文件裡就不再追)。"""
    parts: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k in ("name", "text") and isinstance(v, str):
                    parts.append(v)
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    walk(doc or {})
    return normalize("\n".join(parts))


def backstop_sweep(*, doc: dict, texts_since: list[str],
                   unasked_tasks: list[dict],
                   pool_items: dict[str, str]) -> list[str]:
    """確定性撿漏。回 held 追問清單(可空)。
    texts_since=上次掃描後的員工原話;unasked_tasks=checklist()["unasked"];
    pool_items=官方池 code→name。"""
    hay = normalize("\n".join(texts_since))
    if not hay:
        return []
    in_doc = _doc_texts(doc)
    held: list[str] = []

    for pt in unasked_tasks:
        name = pt.get("name") or ""
        key = normalize(name)
        if len(key) >= _MIN_NAME_LEN and key in hay and key not in in_doc:
            held.append(f"你剛才提到跟「{name}」相關的事——這是不是你平常的任務之一?")

    for code, name in pool_items.items():
        key = normalize(name or "")
        if len(key) >= _MIN_NAME_LEN and key in hay and key not in in_doc:
            held.append(f"你提過「{name}」——這對你的工作重要嗎?想多聽一點。")

    return held
