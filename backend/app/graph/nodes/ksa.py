"""K/S/A 對齊節點：整理知識、技能、態度，區分 iCAP 來源 vs 企業專屬。"""
import logging

from app.graph.llm_gateway import LLMGateway
from app.graph.state import InterviewState

logger = logging.getLogger("jobintel")

_KSA_PROMPT = """根據以下企業崗位資訊，整理知識(K)、技能(S)、態度(A)。

職稱：{job_title}
任務列表：{tasks_summary}
iCAP 參考基準：{icap_candidates}
真實工具：{tools_mentioned}

輸出 JSON（只輸出 JSON）：
{{
  "knowledge": [
    {{"content": "...", "source_type": "icap_official|company_defined"}}
  ],
  "skills": [
    {{"content": "...", "source_type": "icap_official|company_defined"}}
  ],
  "attitudes": [
    {{"content": "...", "source_type": "icap_official|company_defined"}}
  ]
}}

規則：
- icap_official：iCAP 職能基準中有對應的通用能力
- company_defined：企業特有工具、流程、情境才有的能力
- 每類至少 3 項，最多 6 項
"""


async def ksa_alignment_node(state: InterviewState) -> dict:
    tasks = state.get("extracted_tasks", [])
    icap  = state.get("icap_candidates", [])

    tools_all = []
    for t in tasks:
        tools_all.extend(t.get("tools") or [])

    tasks_summary = "\n".join(
        f"- {t['task_name']}（{t.get('responsibility_type', '?')}）" for t in tasks
    )
    icap_summary = "\n".join(
        f"- {c['icap_title']}（相似度 {int(c['similarity'] * 100)}%）" for c in icap
    ) or "無 iCAP 命中（企業自建模式）"

    prompt = _KSA_PROMPT.format(
        job_title=state["job_title"],
        tasks_summary=tasks_summary,
        icap_candidates=icap_summary,
        tools_mentioned=", ".join(set(tools_all)) or "未提及",
    )

    logger.info("ksa_node: generating KSA for %d tasks", len(tasks))
    result = await LLMGateway(temperature=0.2).invoke_json(prompt, default={})

    ksa_items = []
    for k in result.get("knowledge", []):
        ksa_items.append({"ksa_type": "K", **k})
    for s in result.get("skills", []):
        ksa_items.append({"ksa_type": "S", **s})
    for a in result.get("attitudes", []):
        ksa_items.append({"ksa_type": "A", **a})

    return {
        "ksa_items":      ksa_items,
        "current_stage":  "preview",
        "document_ready": True,
        "ai_response":    _format_ksa_summary(result),
    }


def _format_ksa_summary(result: dict) -> str:
    lines = ["**K/S/A 整理完成**\n"]
    for label, key in [("K 知識", "knowledge"), ("S 技能", "skills"), ("A 態度", "attitudes")]:
        lines.append(f"**{label}**")
        for item in result.get(key, []):
            tag = "🔵 iCAP" if item.get("source_type") == "icap_official" else "🟠 企業專屬"
            lines.append(f"  {tag} {item['content']}")
        lines.append("")
    lines.append("職務說明書草稿已就緒，請前往預覽頁確認內容。")
    return "\n".join(lines)
