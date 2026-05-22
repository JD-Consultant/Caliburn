"""
OCS document builder node.

Replaces the old ksa_alignment_node.  Produces a full OCS-compliant JSON
document stored in state["ocs_document"], while also populating the legacy
state["ksa_items"] list for backward compatibility with the preview page.
"""
import logging
import re

from app.graph.llm_gateway import LLMGateway
from app.graph.state import InterviewState
from app.services.icap_retriever import search_knowledge, search_skills, search_attitudes

logger = logging.getLogger("jobintel")

_OCS_BUILD_PROMPT = """\
你是 iCAP 職能標準撰寫專家。根據下列訪談資料，生成符合 iCAP OCS 架構的職能文件。

職稱：{job_title}
部門：{department}
職務描述：{job_summary}
iCAP 參考基準：{icap_ref}
iCAP 使用模式：{icap_mode_instruction}

已萃取任務（含 5W2H）：
{tasks_detail}

已生成行為指標：
{indicators_detail}

輸出 JSON（只輸出 JSON）：
{{
  "competency_level": 3,
  "ocu_units": [
    {{
      "ocu_name": "職能單元名稱（動詞片語，3-10字）",
      "tasks": [
        {{
          "task_name": "（必須與已萃取任務名稱完全一致）",
          "indicators": ["（系統自動注入，此欄位會被忽略，填空陣列即可）"],
          "outputs": ["（系統自動注入，此欄位會被忽略，填空陣列即可）"],
          "knowledge": [
            {{"name": "知識名稱", "source_type": "icap_official 或 company_defined"}}
          ],
          "skills": [
            {{"name": "技能名稱", "source_type": "icap_official 或 company_defined"}}
          ]
        }}
      ]
    }}
  ],
  "attitudes": [
    {{"name": "態度名稱", "source_type": "icap_official 或 company_defined"}}
  ]
}}

規則：
1. 將相關任務歸入同一職能單元，每單元 2-4 個任務
2. indicators 和 outputs 由系統從「已生成行為指標」自動注入，你只需確保 task_name 正確對應
3. source_type 分配依照上方「iCAP 使用模式」指示執行
4. 每任務 knowledge 2-4 項、skills 2-4 項（根據行為指標內容推斷所需知識技能）
5. attitudes：4-6 項，涵蓋通用職業態度及企業特有要求
6. competency_level 參考 iCAP 命中結果（預設 3）
"""

_MODE_INSTRUCTIONS: dict[str, str] = {
    "reference": (
        "高信心命中（reference）：知識與技能以 icap_official 為主（每任務至少 2 項），"
        "企業特有內容標 company_defined 補充。"
    ),
    "hybrid": (
        "中信心命中（hybrid）：通用知識技能各 1-2 項標 icap_official，"
        "企業特有部分各 1-2 項標 company_defined，均衡混合。"
    ),
    "company_defined": (
        "低信心／未命中（company_defined）：所有 knowledge、skills、attitudes "
        "均標記為 company_defined，不引用 iCAP 官方代碼。"
    ),
}


def _build_task_evidence(task: dict) -> list[dict]:
    """task 層 evidence：來自訪談原始 evidence_from_user。"""
    refs = []
    if task.get("evidence_from_user"):
        refs.append({
            "source_type": "interview_quote",
            "evidence_kind": "direct",
            "quote": task["evidence_from_user"],
        })
    return refs


def _build_indicator_evidence(task: dict) -> list[dict]:
    """indicator 層 evidence：STAR 四槽 + 關鍵 5W2H 欄位。"""
    refs = []
    task_name = task.get("task_name", "")
    star = task.get("star_case") or {}

    for star_field, label in [("situation", "S"), ("task", "T"), ("action", "A"), ("result", "R")]:
        val = star.get(star_field)
        if not val:
            continue
        v: str | list[str] = val if isinstance(val, list) else val.strip()
        if not v:
            continue
        refs.append({
            "source_type": "star_slot",
            "evidence_kind": "direct",
            "source_phase": f"star_{task_name}",
            "field": label,
            "value": v,
        })

    for w2h_field in ["situation", "purpose", "workflow_steps", "outputs", "quality_standards", "time_standards"]:
        val = task.get(w2h_field)
        if not val:
            continue
        refs.append({
            "source_type": "five_w2h_field",
            "evidence_kind": "structured",
            "source_phase": f"five_w2h_{task_name}",
            "field": w2h_field,
            "value": val if isinstance(val, list) else str(val),
        })

    return refs


def _attach_evidence_to_ocs_task(ocs_task: dict, orig_task: dict) -> None:
    """Attach task-level and indicator-level evidence_refs in-place."""
    ocs_task["evidence_refs"] = _build_task_evidence(orig_task)
    indicator_evidence = _build_indicator_evidence(orig_task)
    for block in ocs_task.get("competency_blocks", []):
        for indicator in block.get("indicators", []):
            indicator["evidence_refs"] = indicator_evidence


# ── Display label helpers ───────────────────────────────────────────────────

_LOW_QUALITY_SCORE = 0.60  # mirrors _QUALITY_THRESHOLD in indicator.py


def _compute_display_labels(
    item_type: str,
    evidence_refs: list[dict] | None = None,
    icap_ref: str | None = None,
    source_type: str = "company_defined",
    quality_score: float | None = None,
    quality_status: str = "ok",
) -> list[str]:
    """Return list of applicable display labels for an OCS item.

    item_type: "task" | "indicator" | "ksa" | "output"
    Priority (for primary selection): [待確認] > [訪談確認] > [iCAP參考] > [AI整理]
    """
    evidence_refs = evidence_refs or []
    source_types = {
        e.get("source_type") for e in evidence_refs
        if isinstance(e, dict) and e.get("source_type")
    }

    has_direct    = bool({"interview_quote", "star_slot"} & source_types)
    has_structured = "five_w2h_field" in source_types
    has_icap_ref  = bool(
        icap_ref
        or source_type == "icap_official"
        or "icap_reference" in source_types
    )
    has_evidence  = bool(evidence_refs) or has_icap_ref

    # KSA / output: source_type-based only
    if item_type == "ksa":
        return ["[iCAP參考]"] if has_icap_ref else ["[AI整理]"]

    if item_type == "output":
        return ["[iCAP參考]"] if has_icap_ref else ["[AI整理]"]

    # Indicator: quality-gated first
    if item_type == "indicator":
        if quality_status == "force_accepted" or (
            quality_score is not None and quality_score < _LOW_QUALITY_SCORE
        ):
            return ["[待確認]"]
        if not has_evidence:
            return ["[待確認]"]
        labels: list[str] = []
        if has_direct and (quality_score is None or quality_score >= 0.70):
            labels.append("[訪談確認]")
        if has_icap_ref:
            labels.append("[iCAP參考]")
        return labels or (["[AI整理]"] if has_structured else ["[AI整理]"])

    # Task
    if not has_evidence:
        return ["[待確認]"]
    labels = []
    if has_direct:
        labels.append("[訪談確認]")
    if has_icap_ref:
        labels.append("[iCAP參考]")
    return labels or ["[AI整理]"]


def _primary_display_label(labels: list[str]) -> str:
    for candidate in ["[待確認]", "[訪談確認]", "[iCAP參考]", "[AI整理]"]:
        if candidate in labels:
            return candidate
    return labels[0] if labels else "[AI整理]"


def _make_prefix(job_title: str) -> str:
    """Extract 3-letter uppercase code from job title."""
    ascii_only = re.sub(r"[^a-zA-Z]", "", job_title).upper()
    if len(ascii_only) >= 3:
        return ascii_only[:3]
    return "ENT"


def _format_tasks_detail(tasks: list[dict]) -> str:
    lines = []
    for t in tasks:
        lines.append(f"### {t['task_name']}")
        if t.get("description"):
            lines.append(f"說明：{t['description']}")
        lines.append(f"頻率：{t.get('frequency', '?')}　責任：{t.get('responsibility_type', '?')}")
        if t.get("purpose"):
            lines.append(f"目的：{t['purpose']}")
        if t.get("outputs"):
            lines.append(f"產出：{', '.join(t['outputs'])}")
        if t.get("tools"):
            lines.append(f"工具：{', '.join(t['tools'])}")
        lines.append("")
    return "\n".join(lines)


async def _enrich_and_assign_codes(
    raw: dict,
    job_title: str,
    job_summary: str,
    icap_candidates: list[dict],
    extracted_tasks: list[dict] | None = None,
    behavior_indicators: list[dict] | None = None,
    icap_mode: str = "company_defined",
) -> dict:
    """Assign hierarchical codes, RAG-match K/S/A, inject evidence_refs and display_labels.

    Code format matches official iCAP OCS:
      ocu_code  T1, T2 …
      task_code T1.1, T1.2, T2.1 …
      indicator P1.1.1, P1.1.2 …
      output    O1.1.1, O1.1.2 …
      knowledge K01, K02 … (document-level, deduped)
      skill     S01, S02 … (document-level, deduped)
      attitude  A01, A02 …
    """
    prefix = _make_prefix(job_title)
    competency_level = raw.get("competency_level", 3)
    task_lookup: dict[str, dict] = {t["task_name"]: t for t in (extracted_tasks or [])}
    # Per-output: one task_name → multiple indicator entries
    indicator_meta_lookup: dict[str, list[dict]] = {}
    for ind in (behavior_indicators or []):
        indicator_meta_lookup.setdefault(ind["task_name"], []).append(ind)

    # Build OCS code from prefix + first iCAP OCS code suffix if available
    base_code = icap_candidates[0].get("ocs_code", "") if icap_candidates else ""
    ocs_code = f"{prefix}-001" if not base_code else f"{prefix}-{base_code[-3:]}"

    # Document-level K/S registries keyed by name for deduplication
    k_registry: dict[str, dict] = {}
    s_registry: dict[str, dict] = {}

    ocu_units = []
    for u_idx, unit_raw in enumerate(raw.get("ocu_units", []), 1):
        ocu_code = f"T{u_idx}"
        tasks_out = []

        for t_idx, task_raw in enumerate(unit_raw.get("tasks", []), 1):
            task_name = task_raw.get("task_name", "")
            task_code = f"T{u_idx}.{t_idx}"
            task_query = task_name

            # P indicators + O outputs — from behavior_indicators (per-output), not LLM
            task_ind_data: list[dict] = indicator_meta_lookup.get(task_name, [])
            if task_ind_data:
                # Per-output: each ind entry → one P code + one O code (1-to-1)
                indicators = [
                    {"code": f"P{u_idx}.{t_idx}.{p_idx}", "text": ind["indicator_5w2h"]}
                    for p_idx, ind in enumerate(task_ind_data, 1)
                    if ind.get("indicator_5w2h")
                ]
                outputs = [
                    {"code": f"O{u_idx}.{t_idx}.{o_idx}", "name": ind["output_name"]}
                    for o_idx, ind in enumerate(task_ind_data, 1)
                    if ind.get("output_name")
                ]
                # Fallback: if all output_names empty (single-indicator mode), use LLM outputs
                if not outputs:
                    outputs = [
                        {"code": f"O{u_idx}.{t_idx}.{o_idx}", "name": out_name}
                        for o_idx, out_name in enumerate(task_raw.get("outputs", []), 1)
                        if out_name
                    ]
            else:
                # No behavior_indicators for this task — fallback to LLM-generated
                indicators = [
                    {"code": f"P{u_idx}.{t_idx}.{p_idx}", "text": text}
                    for p_idx, text in enumerate(task_raw.get("indicators", []), 1)
                    if text
                ]
                outputs = [
                    {"code": f"O{u_idx}.{t_idx}.{o_idx}", "name": out_name}
                    for o_idx, out_name in enumerate(task_raw.get("outputs", []), 1)
                    if out_name
                ]

            # K knowledge — document-level dedup + RAG enrich
            knowledge = []
            for k_raw in task_raw.get("knowledge", []):
                name = k_raw["name"]
                if name not in k_registry:
                    code = f"K{len(k_registry) + 1:02d}"
                    item: dict = {
                        "code": code,
                        "name": name,
                        "source_type": k_raw.get("source_type", "company_defined"),
                    }
                    if k_raw.get("source_type") == "icap_official":
                        hits = await search_knowledge(f"{name} {task_query}", top_k=1)
                        if hits:
                            item["icap_ref"] = hits[0]["code"]
                    k_labels = _compute_display_labels(
                        "ksa", icap_ref=item.get("icap_ref"), source_type=item["source_type"]
                    )
                    item["display_label"]  = _primary_display_label(k_labels)
                    item["display_labels"] = k_labels
                    k_registry[name] = item
                knowledge.append(k_registry[name])

            # S skills — document-level dedup + RAG enrich
            skills = []
            for s_raw in task_raw.get("skills", []):
                name = s_raw["name"]
                if name not in s_registry:
                    code = f"S{len(s_registry) + 1:02d}"
                    item = {
                        "code": code,
                        "name": name,
                        "source_type": s_raw.get("source_type", "company_defined"),
                    }
                    if s_raw.get("source_type") == "icap_official":
                        hits = await search_skills(f"{name} {task_query}", top_k=1)
                        if hits:
                            item["icap_ref"] = hits[0]["code"]
                    s_labels = _compute_display_labels(
                        "ksa", icap_ref=item.get("icap_ref"), source_type=item["source_type"]
                    )
                    item["display_label"]  = _primary_display_label(s_labels)
                    item["display_labels"] = s_labels
                    s_registry[name] = item
                skills.append(s_registry[name])

            tasks_out.append({
                "task_codes": [{"code": task_code, "name": task_name}],
                "competency_blocks": [{
                    "competency_level": competency_level,
                    "indicators": indicators,
                    "outputs": outputs,
                    "knowledge": knowledge,
                    "skills": skills,
                }],
            })
            orig_task = task_lookup.get(task_name, {})
            if not orig_task:
                logger.warning("ocs_builder evidence: no extracted task found for task_name='%s'", task_name)
            _attach_evidence_to_ocs_task(tasks_out[-1], orig_task)

            # ── Display labels — injected after evidence is attached ─────────
            # Per-output: each indicator maps to task_ind_data[p_idx-1]
            for block in tasks_out[-1]["competency_blocks"]:
                for p_idx, ind in enumerate(block["indicators"]):
                    ind_data = (task_ind_data[p_idx] if p_idx < len(task_ind_data)
                                else (task_ind_data[0] if task_ind_data else {}))
                    ind_labels = _compute_display_labels(
                        "indicator",
                        evidence_refs=ind.get("evidence_refs", []),
                        quality_score=ind_data.get("quality_score"),
                        quality_status=ind_data.get("quality_status", "ok"),
                    )
                    ind["display_label"]  = _primary_display_label(ind_labels)
                    ind["display_labels"] = ind_labels
                for o_idx, out in enumerate(block["outputs"]):
                    # Output label mirrors its paired indicator's label
                    paired_ind = block["indicators"][o_idx] if o_idx < len(block["indicators"]) else None
                    if paired_ind:
                        out["display_label"]  = paired_ind.get("display_label", "[AI整理]")
                        out["display_labels"] = paired_ind.get("display_labels", ["[AI整理]"])
                    else:
                        out["display_label"]  = "[AI整理]"
                        out["display_labels"] = ["[AI整理]"]

            task_icap_ref = (orig_task.get("icap_task_ref") or {}).get("code")
            task_labels = _compute_display_labels(
                "task",
                evidence_refs=tasks_out[-1].get("evidence_refs", []),
                icap_ref=task_icap_ref,
            )
            tasks_out[-1]["display_label"]  = _primary_display_label(task_labels)
            tasks_out[-1]["display_labels"] = task_labels

        ocu_units.append({"ocu_code": ocu_code, "ocu_name": unit_raw.get("ocu_name", ""), "tasks": tasks_out})

    # A attitudes — A01, A02 …
    attitudes = []
    for a_idx, a_raw in enumerate(raw.get("attitudes", []), 1):
        item = {
            "code": f"A{a_idx:02d}",
            "name": a_raw["name"],
            "source_type": a_raw.get("source_type", "company_defined"),
        }
        if a_raw.get("source_type") == "icap_official":
            hits = await search_attitudes(a_raw["name"], top_k=1)
            if hits:
                item["icap_ref"] = hits[0]["code"]
        a_labels = _compute_display_labels(
            "ksa", icap_ref=item.get("icap_ref"), source_type=item["source_type"]
        )
        item["display_label"]  = _primary_display_label(a_labels)
        item["display_labels"] = a_labels
        attitudes.append(item)

    # Build category from iCAP candidates
    industries     = []
    job_categories = []
    occupations    = []
    occ_code       = ""
    notes          = ""
    if icap_candidates:
        c0 = icap_candidates[0]

        # Accept both legacy str items and new {name, code} dicts
        def _norm(items: list) -> list[dict]:
            return [i if isinstance(i, dict) else {"name": i} for i in items]

        job_categories = _norm(c0.get("job_categories", []))
        occupations    = _norm(c0.get("occupations", []))
        industries     = _norm(c0.get("industries", []))
        notes          = c0.get("notes", "")

        # occ_code: prefer occupations[0].code, else split from full ocs_code string
        if occupations and occupations[0].get("code"):
            occ_code = occupations[0]["code"]
        else:
            raw_ocs  = c0.get("ocs_code", "")
            occ_code = raw_ocs.split("-")[0] if raw_ocs else ""

    return {
        "version_info": {"versions": [{"status": "最新版本", "ocs_code": ocs_code}]},
        "ocs_profile": {
            "ocs_code": ocs_code,
            "ocs_name": {"occupation_name": job_title},
            "job_description": job_summary,
            "ocs_level": competency_level,
            "notes": notes,
            "category": {
                "occ_code":       occ_code,
                "job_categories": job_categories,
                "occupations":    occupations,
                "industries":     industries,
            },
        },
        "ocs_content": {"ocu_units": ocu_units},
        "ocs_attitude": {"attitudes": attitudes},
    }


def _extract_legacy_ksa(ocs_doc: dict) -> list[dict]:
    """Flatten OCS K/S/A into the legacy ksa_items list."""
    ksa: list[dict] = []
    seen: set[str] = set()

    for unit in ocs_doc.get("ocs_content", {}).get("ocu_units", []):
        for task in unit.get("tasks", []):
            for block in task.get("competency_blocks", []):
                for k in block.get("knowledge", []):
                    key = k["name"]
                    if key not in seen:
                        seen.add(key)
                        ksa.append({"ksa_type": "K", "content": k["name"],
                                    "source_type": k.get("source_type", "company_defined"),
                                    "icap_ref": k.get("icap_ref")})
                for s in block.get("skills", []):
                    key = s["name"]
                    if key not in seen:
                        seen.add(key)
                        ksa.append({"ksa_type": "S", "content": s["name"],
                                    "source_type": s.get("source_type", "company_defined"),
                                    "icap_ref": s.get("icap_ref")})

    for a in ocs_doc.get("ocs_attitude", {}).get("attitudes", []):
        ksa.append({"ksa_type": "A", "content": a["name"],
                    "source_type": a.get("source_type", "company_defined"),
                    "icap_ref": a.get("icap_ref")})
    return ksa


def _format_ocs_summary(ocs_doc: dict) -> str:
    profile = ocs_doc.get("ocs_profile", {})
    units = ocs_doc.get("ocs_content", {}).get("ocu_units", [])
    attitudes = ocs_doc.get("ocs_attitude", {}).get("attitudes", [])

    lines = [f"**OCS 職能文件已生成**（代碼：{profile.get('ocs_code', '')}）\n"]
    for unit in units:
        lines.append(f"**{unit.get('ocu_code', '')} {unit['ocu_name']}**")
        for task in unit.get("tasks", []):
            tc = task.get("task_codes", [{}])[0]
            lines.append(f"  ├ {tc.get('code', '')} {tc.get('name', '')}")

    icap_k = sum(1 for u in units for t in u.get("tasks", [])
                 for b in t.get("competency_blocks", [])
                 for k in b.get("knowledge", []) if k.get("icap_ref"))
    icap_s = sum(1 for u in units for t in u.get("tasks", [])
                 for b in t.get("competency_blocks", [])
                 for s in b.get("skills", []) if s.get("icap_ref"))

    lines.append(f"\niCAP 知識對應：{icap_k} 項　iCAP 技能對應：{icap_s} 項　態度：{len(attitudes)} 項")
    lines.append("職務說明書已就緒，請前往預覽頁確認並匯出。")
    return "\n".join(lines)


async def ocs_builder_node(state: InterviewState) -> dict:
    tasks = state.get("extracted_tasks", [])
    indicators_raw = state.get("behavior_indicators", [])
    icap_candidates = state.get("icap_candidates", [])
    icap_mode = state.get("icap_mode", "company_defined")

    # 按任務分組，展示每個產出的指標（per-output 格式）
    _ind_by_task: dict[str, list[dict]] = {}
    for ind in indicators_raw:
        _ind_by_task.setdefault(ind["task_name"], []).append(ind)

    ind_lines = []
    for tn, inds in _ind_by_task.items():
        ind_lines.append(f"- {tn}：")
        for i in inds:
            label = f"（{i['output_name']}）" if i.get("output_name") else ""
            ind_lines.append(f"    {label} {i.get('indicator_5w2h', '')}")
    indicators_detail = "\n".join(ind_lines) or "（未生成行為指標）"

    icap_ref = "\n".join(
        f"- {c['icap_title']} ({int(c['similarity'] * 100)}%) [{c.get('confidence', '?')}]"
        for c in icap_candidates
    ) or "無 iCAP 命中"

    prompt = _OCS_BUILD_PROMPT.format(
        job_title=state["job_title"],
        department=state.get("department", ""),
        job_summary=state.get("job_summary", ""),
        icap_ref=icap_ref,
        icap_mode_instruction=_MODE_INSTRUCTIONS.get(icap_mode, _MODE_INSTRUCTIONS["company_defined"]),
        tasks_detail=_format_tasks_detail(tasks),
        indicators_detail=indicators_detail,
    )

    logger.info("ocs_builder: building OCS document for %d tasks", len(tasks))
    raw = await LLMGateway(temperature=0.2).invoke_json(prompt, default={})

    ocs_doc = await _enrich_and_assign_codes(
        raw, state["job_title"], state.get("job_summary", ""), icap_candidates,
        extracted_tasks=tasks,
        behavior_indicators=indicators_raw,
        icap_mode=icap_mode,
    )

    return {
        "ocs_document": ocs_doc,
        "ksa_items": _extract_legacy_ksa(ocs_doc),
        "current_stage": "preview",
        "document_ready": True,
        "ai_response": _format_ocs_summary(ocs_doc),
    }
