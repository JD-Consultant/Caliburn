"""
Custom iCAP JSON parser that produces semantic TextNode chunks at 8 granularity levels.
LlamaIndex is used only for embedding + storage, NOT for parsing.
"""

import json
import uuid
from pathlib import Path
from typing import Optional

from llama_index.core.schema import TextNode


def _latest_version(version_info: dict) -> Optional[str]:
    for v in version_info.get("versions", []):
        if v.get("status") == "最新版本":
            return v.get("ocs_code")
    return None


def chunk_icap(data: dict, source_path: str = "") -> list[TextNode]:
    """
    Parse one iCAP JSON dict into TextNodes across 8 granularity levels:
      1. competency  – whole OCS profile (job description)
      2. unit        – ocu_unit (responsibility cluster)
      3. task        – individual task
      4. indicator   – behavior indicator (P-code)
      5. output      – work output (O-code)
      6. knowledge   – knowledge item (K-code)
      7. skill       – skill item (S-code)
      8. attitude    – attitude item (A-code)
    """
    nodes: list[TextNode] = []

    version_info = data.get("version_info", {})
    latest_code = _latest_version(version_info)
    if not latest_code:
        return nodes  # skip files with no latest version

    profile = data.get("ocs_profile", {})
    ocs_code = profile.get("ocs_code", "")

    # Guard: only process if ocs_code matches latest version code
    if ocs_code != latest_code:
        return nodes

    ocs_name_obj = profile.get("ocs_name", {})
    occupation_name = ocs_name_obj.get("occupation_name", "") or ocs_name_obj.get("job_category_name", "")
    job_description = profile.get("job_description", "")
    ocs_level = profile.get("ocs_level", 0)

    category_obj = profile.get("category", {})
    # Keep full dicts {name, code} instead of name-only strings
    job_categories = category_obj.get("job_categories", [])
    occupations    = category_obj.get("occupations", [])
    industries     = category_obj.get("industries", [])

    # Flatten notes_and_appendix into a single text block
    notes_obj  = data.get("notes_and_appendix", {})
    notes_text = "\n".join(
        r.get("content", "") for r in notes_obj.get("requirements", []) if r.get("content")
    ).strip()

    base_meta = {
        "ocs_code":      ocs_code,
        "occupation_name": occupation_name,
        "ocs_level":     ocs_level,
        "job_categories": job_categories,  # [{name, code}, ...]
        "occupations":   occupations,       # [{name, code}, ...]
        "industries":    industries,         # [{name, code}, ...]
        "notes":         notes_text,
        "source_path":   source_path,
    }

    # ── Level 1: competency (whole profile) ──────────────────────────────────
    nodes.append(TextNode(
        id_=str(uuid.uuid4()),
        text=f"職能標準：{occupation_name}\n職務描述：{job_description}",
        metadata={**base_meta, "chunk_type": "competency",
                  "breadcrumb": f"{occupation_name} ({ocs_code})"},
    ))

    # ── Level 1b: notes chunk (說明與補充事項) ─────────────────────────────────
    if notes_text:
        nodes.append(TextNode(
            id_=str(uuid.uuid4()),
            text=f"說明與補充事項：{occupation_name}\n{notes_text}",
            metadata={**base_meta, "chunk_type": "notes",
                      "breadcrumb": f"{occupation_name} ({ocs_code}) > 說明補充"},
        ))

    ocu_units = data.get("ocs_content", {}).get("ocu_units", [])

    for unit in ocu_units:
        ocu_code = unit.get("ocu_code", "")
        ocu_name = unit.get("ocu_name", "")

        # ── Level 2: unit ────────────────────────────────────────────────────
        nodes.append(TextNode(
            id_=str(uuid.uuid4()),
            text=f"職能單元 {ocu_code}：{ocu_name}（職業：{occupation_name}）",
            metadata={
                **base_meta,
                "chunk_type": "unit",
                "ocu_code": ocu_code,
                "ocu_name": ocu_name,
                "breadcrumb": f"{occupation_name} ({ocs_code}) > {ocu_name} ({ocu_code})",
            },
        ))

        for task_obj in unit.get("tasks", []):
            task_codes_raw = task_obj.get("task_codes", [])
            # Support multi-value task_codes; primary = first entry
            task_code = task_codes_raw[0].get("code", "") if task_codes_raw else ""
            task_name = task_codes_raw[0].get("name", "") if task_codes_raw else ""
            # Combined label for multi-code tasks (e.g. "T1.1 / T1.2")
            all_codes_str = " / ".join(
                f"{tc.get('code','')} {tc.get('name','')}" for tc in task_codes_raw
            )

            # ── Level 3: task ─────────────────────────────────────────────────
            nodes.append(TextNode(
                id_=str(uuid.uuid4()),
                text=(
                    f"工作任務 {all_codes_str}\n"
                    f"所屬單元：{ocu_name}\n"
                    f"職業：{occupation_name}"
                ),
                metadata={
                    **base_meta,
                    "chunk_type":  "task",
                    "ocu_code":    ocu_code,
                    "ocu_name":    ocu_name,
                    "task_code":   task_code,
                    "task_name":   task_name,
                    "task_codes":  task_codes_raw,
                    "breadcrumb":  f"{occupation_name} ({ocs_code}) > {ocu_name} ({ocu_code}) > {task_name} ({task_code})",
                },
            ))

            for block in task_obj.get("competency_blocks", []):
                competency_level = block.get("competency_level", 0)
                block_meta = {
                    **base_meta,
                    "ocu_code": ocu_code,
                    "ocu_name": ocu_name,
                    "task_code": task_code,
                    "task_name": task_name,
                    "competency_level": competency_level,
                }

                # ── Level 4: indicator ────────────────────────────────────────
                for ind in block.get("indicators", []):
                    ind_code = ind.get("code", "")
                    ind_text = ind.get("text", "")
                    nodes.append(TextNode(
                        id_=str(uuid.uuid4()),
                        text=(
                            f"行為指標 {ind_code}：{ind_text}\n"
                            f"任務：{task_name} | 單元：{ocu_name} | 職業：{occupation_name}"
                        ),
                        metadata={
                            **block_meta,
                            "chunk_type": "indicator",
                            "indicator_code": ind_code,
                            "breadcrumb": f"{occupation_name} ({ocs_code}) > {ocu_name} ({ocu_code}) > {task_name} ({task_code}) > {ind_code}",
                        },
                    ))

                # ── Level 5: output ───────────────────────────────────────────
                for out in block.get("outputs", []):
                    out_code = out.get("code", "")
                    out_name = out.get("name", "")
                    nodes.append(TextNode(
                        id_=str(uuid.uuid4()),
                        text=(
                            f"工作產出 {out_code}：{out_name}\n"
                            f"任務：{task_name} | 單元：{ocu_name} | 職業：{occupation_name}"
                        ),
                        metadata={
                            **block_meta,
                            "chunk_type": "output",
                            "output_code": out_code,
                            "breadcrumb": f"{occupation_name} ({ocs_code}) > {ocu_name} ({ocu_code}) > {task_name} ({task_code}) > {out_code}",
                        },
                    ))

                # ── Level 6: knowledge ────────────────────────────────────────
                for k in block.get("knowledge", []):
                    k_code = k.get("code", "")
                    k_name = k.get("name", "").replace(" ", " ").strip()
                    nodes.append(TextNode(
                        id_=str(uuid.uuid4()),
                        text=(
                            f"職能知識 {k_code}：{k_name}\n"
                            f"任務：{task_name} | 職業：{occupation_name}"
                        ),
                        metadata={
                            **block_meta,
                            "chunk_type": "knowledge",
                            "knowledge_code": k_code,
                            "breadcrumb": f"{occupation_name} ({ocs_code}) > {ocu_name} ({ocu_code}) > {task_name} ({task_code}) > {k_code}",
                        },
                    ))

                # ── Level 7: skill ────────────────────────────────────────────
                for s in block.get("skills", []):
                    s_code = s.get("code", "")
                    s_name = s.get("name", "")
                    nodes.append(TextNode(
                        id_=str(uuid.uuid4()),
                        text=(
                            f"職能技能 {s_code}：{s_name}\n"
                            f"任務：{task_name} | 職業：{occupation_name}"
                        ),
                        metadata={
                            **block_meta,
                            "chunk_type": "skill",
                            "skill_code": s_code,
                            "breadcrumb": f"{occupation_name} ({ocs_code}) > {ocu_name} ({ocu_code}) > {task_name} ({task_code}) > {s_code}",
                        },
                    ))

    # ── Level 8: attitude ─────────────────────────────────────────────────────
    for att in data.get("ocs_attitude", {}).get("attitudes", []):
        att_code = att.get("code", "")
        att_name = att.get("name", "")
        nodes.append(TextNode(
            id_=str(uuid.uuid4()),
            text=(
                f"職能態度 {att_code}：{att_name}\n"
                f"職業：{occupation_name}"
            ),
            metadata={
                **base_meta,
                "chunk_type": "attitude",
                "attitude_code": att_code,
                "breadcrumb": f"{occupation_name} ({ocs_code}) > {att_code}",
            },
        ))

    return nodes


def parse_icap_file(filepath: str | Path) -> list[TextNode]:
    filepath = Path(filepath)
    try:
        with open(filepath, encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        print(f"[WARN] Skipping {filepath}: {e}")
        return []
    return chunk_icap(data, source_path=str(filepath))


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python icap_parser.py <path-to-json>")
        sys.exit(1)

    nodes = parse_icap_file(sys.argv[1])
    print(f"Generated {len(nodes)} nodes:")
    for n in nodes[:5]:
        print(f"  [{n.metadata.get('chunk_type')}] {n.text[:80]!r}")
    if len(nodes) > 5:
        print(f"  ... and {len(nodes) - 5} more")
