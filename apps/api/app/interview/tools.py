"""顧問 READ 工具層(v2;ADR 0027、spec §4.1、§16.6)。

顧問 agent 的唯讀工具(查官方職能基準)——**無寫入權**(寫入是書記+executor 的事)。
2 工具(§16.6:match_items 延後,match 是 ADR 0022 去重非片語映射器):
- knowledge_search_occupations:白話搜職類(onboarding 選職位)。
- knowledge_occupation_brief:一呼帶齊某職類的任務+職能(提議「你也做這個嗎?」)。

依 Anthropic《Writing effective tools for agents》(2025-09):search>list、回**語意名**
(code+name 非裸碼)、**合併工作流**(brief 併 tasks+competencies 省迴圈)、可操作錯誤、
top_k/截斷預設。dispatcher 純粹:呼 KnowledgePort → 壓縮 dict(顧問 context 省 token)。
"""
import logging

logger = logging.getLogger(__name__)

_SEARCH_DEFAULT_TOP_K = 5
_BRIEF_LIST_CAP = 40          # 每類職能截斷(Anthropic:sensible default,防 context 爆)

CONSULTANT_TOOLS = [
    {"type": "function", "function": {
        "name": "knowledge_search_occupations",
        "description": "用白話描述搜尋官方職類(選職位時用)。回最相近的前幾筆,"
                       "含官方碼、職類名、分數。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "職務的白話描述,如「幫客戶測軟體找 bug」"},
                "top_k": {"type": "integer", "description": f"回幾筆(預設 {_SEARCH_DEFAULT_TOP_K})"},
            },
            "required": ["query"],
        },
    }},
    {"type": "function", "function": {
        "name": "read_document",
        "description": "讀職務說明書現況(四態視圖):每個任務/條目標明 confirmed(已確認)/"
                       "pending_add(AI 新增待審)/pending_mod(AI 修改待審)/pending_del"
                       "(AI 建議刪待審)。想確認「已經記了什麼、哪些還沒被使用者核可」時用。",
        "parameters": {"type": "object", "properties": {}, "required": []},
    }},
    {"type": "function", "function": {
        "name": "knowledge_occupation_brief",
        "description": "取某官方職類的簡報:工作任務清單 + 各類職能(知識/技能/產出/行為指標/"
                       "態度,含代碼與名稱)。提議『你也做這個嗎?』或對照官方標準時用。",
        "parameters": {
            "type": "object",
            "properties": {"ocs_code": {"type": "string", "description": "職類官方碼(先用搜尋取得)"}},
            "required": ["ocs_code"],
        },
    }},
]


def _code_name(items) -> list[dict]:
    return [{"code": getattr(i, "code", None), "name": getattr(i, "name", None)}
            for i in (items or [])][:_BRIEF_LIST_CAP]


def _code_text(items) -> list[dict]:
    return [{"code": getattr(i, "code", None), "text": getattr(i, "text", None)}
            for i in (items or [])][:_BRIEF_LIST_CAP]


async def _search_occupations(knowledge, args: dict) -> dict:
    top_k = int(args.get("top_k") or _SEARCH_DEFAULT_TOP_K)
    resp = await knowledge.search_occupations(args["query"], top_k=top_k)
    hits = list(getattr(resp, "hits", []) or [])[:top_k]
    return {"occupations": [{"ocs_code": h.ocs_code, "name": h.ocs_name,
                             "score": round(h.score, 3) if h.score is not None else None}
                            for h in hits]}


async def _occupation_brief(knowledge, args: dict) -> dict:
    code = args["ocs_code"]
    tasks_resp = await knowledge.occupation_tasks(code)     # 合併呼(省迴圈)
    comp = await knowledge.competencies(code)
    tasks = [{"unit": u.ocu_name, "code": t.task_code, "name": t.task_name}
             for u in (getattr(tasks_resp, "units", []) or [])
             for t in (getattr(u, "tasks", []) or [])]
    return {
        "ocs_name": getattr(tasks_resp, "ocs_name", None),
        "tasks": tasks[:_BRIEF_LIST_CAP],
        "competencies": {
            "knowledge": _code_name(getattr(comp, "knowledge", None)),
            "skills": _code_name(getattr(comp, "skills", None)),
            "outputs": _code_name(getattr(comp, "outputs", None)),
            "indicators": _code_text(getattr(comp, "indicators", None)),
            "attitudes": _code_name(getattr(comp, "attitudes", None)),
        },
    }


_DISPATCH = {
    "knowledge_search_occupations": _search_occupations,
    "knowledge_occupation_brief": _occupation_brief,
}


async def dispatch_tool(name: str, arguments: dict, knowledge) -> dict:
    """呼一個 READ 工具;回壓縮 dict。錯誤=可操作字串(Anthropic:別回裸 traceback)。"""
    fn = _DISPATCH.get(name)
    if fn is None:
        return {"error": f"未知工具 {name}。可用:{list(_DISPATCH)}"}
    try:
        return await fn(knowledge, arguments or {})
    except KeyError as exc:
        return {"error": f"{name} 缺必填參數 {exc}"}
    except Exception as exc:  # noqa: BLE001  (知識庫故障 → 可操作訊息,不外洩 traceback)
        logger.warning("READ 工具 %s 失敗:%s", name, str(exc)[:160])
        return {"error": f"{name} 查詢失敗:{str(exc)[:120]}"}


def _entry_status(entry: dict) -> str:
    mark = entry.get("_pending")
    if isinstance(mark, dict) and mark.get("op"):
        return f"pending_{mark['op']}"
    return "confirmed"


def document_view(doc: dict) -> dict:
    """四態視圖(ADR 0030 T5):給顧問的文件現況——精簡、含待審狀態,不整卷重播。
    純函式;由 service 的 dispatch 供給(doc 不在 knowledge 內)。"""
    from app.interview import ledger as L  # 局部匯入避免循環

    units_out = []
    for u, t, tp in L.iter_tasks(doc):
        codes = t.get("task_codes") or []
        name = codes[0].get("name") if codes else "(未命名)"
        row = {"path": tp, "task": name, "status": _entry_status(t)}
        pend = []
        for b in (t.get("competency_blocks") or []):
            for kind in ("outputs", "indicators", "knowledge", "skills"):
                for it in (b.get(kind) or []):
                    st = _entry_status(it)
                    if st != "confirmed":
                        pend.append({"kind": kind,
                                     "value": it.get("name") or it.get("text"),
                                     "status": st})
        d = t.get("details") or {}
        for slot, mark in (d.get("_pending") or {}).items():
            if isinstance(mark, dict) and mark.get("op"):
                pend.append({"kind": f"details.{slot}", "value": d.get(slot),
                             "status": f"pending_{mark['op']}"})
        if pend:
            row["pending_items"] = pend
        units_out.append(row)
    atts = [{"value": a.get("name"), "status": _entry_status(a)}
            for a in ((doc.get("ocs_attitude") or {}).get("attitudes") or [])]
    prof_pend = ((doc.get("ocs_profile") or {}).get("_pending") or {})
    return {"tasks": units_out, "attitudes": atts,
            "header_pending": {k: {"status": f"pending_{v['op']}",
                                   "proposed": v.get("value")}
                               for k, v in prof_pend.items()
                               if isinstance(v, dict) and v.get("op")}}
