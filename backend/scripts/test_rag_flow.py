"""
End-to-end RAG flow evaluator.

Simulates all 7 RAG checkpoints for a given job profile WITHOUT running
a full interview — lets you evaluate RAG quality quickly.

Usage:
    python -m scripts.test_rag_flow --title "資料庫管理師" --dept "IT部" \
        --summary "負責資料庫維護、效能監控與備份還原作業"

    python -m scripts.test_rag_flow --title "電腦維修技術員" --dept "資訊部" \
        --summary "負責公司電腦設備維修、故障排除與定期保養"
"""
import argparse
import asyncio
import io
import sys
from pathlib import Path

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import text
from app.database import AsyncSessionLocal
from app.graph.llm import get_embeddings
from app.config import settings
from app.services.icap_retriever import (
    search_tasks, search_outputs, search_indicators,
    search_knowledge, search_skills, search_attitudes,
)

SEP  = "=" * 62
SEP2 = "-" * 62


def _bar(sim: float, w: int = 16) -> str:
    f = round(sim * w)
    return "#" * f + "-" * (w - f)


def _print_hits(hits: list[dict], indent: str = "    "):
    if not hits:
        print(f"{indent}（無命中 — similarity < 0.58）")
        return
    for i, h in enumerate(hits, 1):
        print(f"{indent}#{i}  [{_bar(h['similarity'])}] {h['similarity']:.4f}")
        print(f"{indent}    code : {h['code']}")
        print(f"{indent}    name : {h['name']}")
        if h.get("breadcrumb"):
            print(f"{indent}    path : {h['breadcrumb']}")


def _rating(score: float) -> str:
    if score >= 0.80: return "EXCELLENT"
    if score >= 0.65: return "GOOD     "
    if score >= 0.50: return "FAIR     "
    return "POOR     "


def _print_summary(
    job_title: str,
    icap_mode: str,
    top_ocs: str | None,
    candidates: list[dict],
    task_hits: list[tuple[str, list, list, list]],   # (task_name, task_h, out_h, ind_h)
    ksa_hits: tuple[list, list, list],
):
    k_hits, s_hits, a_hits = ksa_hits
    print(f"\n{'#' * 62}")
    print(f"  SUMMARY — RAG Quality Assessment")
    print(f"{'#' * 62}")

    # ── RAG #1 ────────────────────────────────────────────────────────────────
    top = candidates[0] if candidates else None
    top_sim = top["similarity"] if top else 0.0
    mode_label = {"reference": "iCAP 官方為主", "hybrid": "官方 + 自訂混合", "company_defined": "純自訂（無 iCAP 注入）"}.get(icap_mode, icap_mode)
    print(f"\n  RAG #1  competency 命中")
    print(f"    top match : {top['icap_title']} ({top['ocs_code']})  {top_sim:.4f}" if top else "    top match : （無結果）")
    print(f"    icap_mode : {icap_mode.upper()} — {mode_label}")
    if candidates and len(candidates) > 1:
        # warn if top-2 are very close
        gap = candidates[0]["similarity"] - candidates[1]["similarity"]
        if gap < 0.02:
            print(f"    [!] WARNING: top-2 差距僅 {gap:.4f}，職稱命中可能不穩定")

    # ── RAG #2～#4：任務命中率 ─────────────────────────────────────────────────
    print(f"\n  RAG #2-4  任務 / 產出 / 指標  (共 {len(task_hits)} 任務)")
    rag2_hits = sum(1 for _, th, _, _ in task_hits if th)
    rag3_hits = sum(1 for _, _, oh, _ in task_hits if oh)
    rag4_hits = sum(1 for _, _, _, ih in task_hits if ih)
    total = len(task_hits) or 1

    def _pct(n): return f"{n}/{total} ({n/total*100:.0f}%)"

    print(f"    RAG #2 task      : {_pct(rag2_hits)}")
    print(f"    RAG #3 output    : {_pct(rag3_hits)}")
    print(f"    RAG #4 indicator : {_pct(rag4_hits)}")
    for task_name, th, oh, ih in task_hits:
        tag2 = "HIT " if th else "MISS"
        tag3 = "HIT " if oh else "MISS"
        tag4 = "HIT " if ih else "MISS"
        t2s = f"{th[0]['similarity']:.4f}" if th else "  N/A "
        t3s = f"{oh[0]['similarity']:.4f}" if oh else "  N/A "
        t4s = f"{ih[0]['similarity']:.4f}" if ih else "  N/A "
        print(f"      [{tag2} {t2s}][{tag3} {t3s}][{tag4} {t4s}]  {task_name}")

    # ── RAG #5～#7：KSA 命中 ──────────────────────────────────────────────────
    print(f"\n  RAG #5-7  K/S/A 代碼對照")
    for label, hits in [("knowledge", k_hits), ("skill", s_hits), ("attitude", a_hits)]:
        if hits:
            best = hits[0]
            print(f"    {label:<10}: HIT  {best['similarity']:.4f}  {best['code']}  {best['name']}")
        else:
            print(f"    {label:<10}: MISS （similarity < 0.58）")

    # ── 整體品質評分 ───────────────────────────────────────────────────────────
    scores = []
    if top_sim > 0:
        scores.append(top_sim)
    for _, th, oh, ih in task_hits:
        if th: scores.append(th[0]["similarity"])
        if oh: scores.append(oh[0]["similarity"])
        if ih: scores.append(ih[0]["similarity"])
    for hits in [k_hits, s_hits, a_hits]:
        if hits: scores.append(hits[0]["similarity"])

    avg = sum(scores) / len(scores) if scores else 0.0
    hit_count = (rag2_hits + rag3_hits + rag4_hits) + sum(1 for h in [k_hits, s_hits, a_hits] if h)
    total_checkpoints = total * 3 + 3  # task×3 + KSA×3

    print(f"\n  Overall")
    print(f"    avg similarity  : {avg:.4f}  [{_rating(avg)}]")
    print(f"    checkpoint hits : {hit_count}/{total_checkpoints} ({hit_count/total_checkpoints*100:.0f}%)")
    if icap_mode == "company_defined":
        print(f"    [!] icap_mode=company_defined — RAG #2-7 全部未執行，iCAP 注入品質無法評估")
    elif icap_mode == "hybrid":
        print(f"    [~] icap_mode=hybrid — 建議確認職稱是否有更精確的 iCAP 對照職種")
    else:
        print(f"    [v] icap_mode=reference — iCAP 注入品質良好")
    print(f"{'#' * 62}\n")


# ── RAG #1：competency 搜尋 ───────────────────────────────────────────────────

async def _rag1_competency(job_title: str, department: str, job_summary: str) -> tuple[list[dict], str, str]:
    query = f"{job_title} {department} {job_summary}"
    embeddings = get_embeddings()
    vec = await embeddings.aembed_query(query)
    vec_str = "[" + ",".join(str(v) for v in vec) + "]"

    sql = text("""
        WITH deduped AS (
            SELECT DISTINCT ON (ocs_code)
                ocs_code,
                chunk_text,
                metadata,
                1 - (embedding <=> CAST(:vec AS vector)) AS similarity
            FROM icap_embeddings
            WHERE chunk_type = 'competency'
            ORDER BY ocs_code, embedding <=> CAST(:vec AS vector)
        )
        SELECT * FROM deduped
        ORDER BY similarity DESC
        LIMIT :k
    """)

    async with AsyncSessionLocal() as session:
        rows = (await session.execute(sql, {"vec": vec_str, "k": settings.icap_top_k})).fetchall()

    candidates = []
    for row in rows:
        import json as _json
        meta = row.metadata if isinstance(row.metadata, dict) else _json.loads(row.metadata or "{}")
        sim = round(float(row.similarity), 4)
        candidates.append({
            "ocs_code":   row.ocs_code,
            "icap_title": meta.get("occupation_name", row.ocs_code),
            "similarity": sim,
            "confidence": "high" if sim >= settings.icap_high_threshold
                          else "medium" if sim >= settings.icap_medium_threshold
                          else "low",
        })

    top_sim = candidates[0]["similarity"] if candidates else 0.0
    if top_sim >= settings.icap_high_threshold:
        icap_mode = "reference"
    elif top_sim >= settings.icap_medium_threshold:
        icap_mode = "hybrid"
    else:
        icap_mode = "company_defined"

    top_ocs = candidates[0]["ocs_code"] if candidates else None
    return candidates, icap_mode, top_ocs


# ── 主流程 ─────────────────────────────────────────────────────────────────────

async def run(job_title: str, department: str, job_summary: str, sample_tasks: list[str]):
    print(f"\n{SEP}")
    print(f"  職稱  : {job_title}")
    print(f"  部門  : {department}")
    print(f"  摘要  : {job_summary}")
    print(SEP)

    # ── RAG #1 ────────────────────────────────────────────────────────────────
    print("\n[ RAG #1 ]  icap_rag_node — competency 職稱命中")
    print(SEP2)
    candidates, icap_mode, top_ocs = await _rag1_competency(job_title, department, job_summary)

    for i, c in enumerate(candidates[:5], 1):
        tag = {"high": "▲ HIGH  ", "medium": "◆ MEDIUM", "low": "▽ LOW   "}.get(c["confidence"], "")
        print(f"  #{i}  [{_bar(c['similarity'])}] {c['similarity']:.4f}  {tag}  {c['icap_title']} ({c['ocs_code']})")

    print(f"\n  => icap_mode : {icap_mode.upper()}")
    print(f"  => top_ocs   : {top_ocs}")
    print(f"  => threshold : HIGH={settings.icap_high_threshold}  MED={settings.icap_medium_threshold}")

    if icap_mode == "company_defined":
        print("\n  [!] company_defined — RAG #2～#7 全部跳過，以下結果為假設 ocs_code_filter=None 的情況")
        top_ocs = None

    # ── RAG #2～#4：逐任務 ────────────────────────────────────────────────────
    if not sample_tasks:
        sample_tasks = [f"{job_title}相關任務"]

    task_hits: list[tuple[str, list, list, list]] = []

    for task_name in sample_tasks:
        print(f"\n{SEP}")
        print(f"  任務 : {task_name}")
        print(SEP)

        # RAG #2 — task
        print("\n  [ RAG #2 ]  task_extraction — 任務對應 iCAP 代碼  (top_k=1)")
        t_hits = await search_tasks(task_name, top_k=1, ocs_code_filter=top_ocs)
        _print_hits(t_hits)

        # RAG #3 — output
        print(f"\n  [ RAG #3 ]  five_w2h — 產出欄位建議  (top_k=3)")
        o_hits = await search_outputs(f"{task_name} 工作產出", top_k=3, ocs_code_filter=top_ocs)
        _print_hits(o_hits)

        # RAG #4 — indicator
        print(f"\n  [ RAG #4 ]  indicator — 行為指標措辭範本  (top_k=2)")
        i_hits = await search_indicators(f"{task_name} 行為指標", top_k=2, ocs_code_filter=top_ocs)
        _print_hits(i_hits)

        task_hits.append((task_name, t_hits, o_hits, i_hits))

    # ── RAG #5～#7：K/S/A 代碼對照 ───────────────────────────────────────────
    print(f"\n{SEP}")
    print(f"  K/S/A 代碼對照（以職稱為 query）")
    print(SEP)

    print(f"\n  [ RAG #5 ]  knowledge  (top_k=1)")
    k_hits = await search_knowledge(f"{job_title} 知識", top_k=3)
    _print_hits(k_hits)

    print(f"\n  [ RAG #6 ]  skill  (top_k=1)")
    s_hits = await search_skills(f"{job_title} 技能", top_k=3)
    _print_hits(s_hits)

    print(f"\n  [ RAG #7 ]  attitude  (top_k=1)")
    a_hits = await search_attitudes(f"{job_title} 工作態度", top_k=3)
    _print_hits(a_hits)

    print(f"\n{SEP}\n")

    # ── 總結評估 ──────────────────────────────────────────────────────────────
    _print_summary(
        job_title=job_title,
        icap_mode=icap_mode,
        top_ocs=top_ocs,
        candidates=candidates,
        task_hits=task_hits,
        ksa_hits=(k_hits, s_hits, a_hits),
    )


def main():
    parser = argparse.ArgumentParser(description="End-to-end RAG flow evaluator")
    parser.add_argument("--title",   required=True, help="職稱")
    parser.add_argument("--dept",    default="",    help="部門")
    parser.add_argument("--summary", default="",    help="工作摘要")
    parser.add_argument("--tasks",   nargs="*",     help="模擬任務清單（可多個）",
                        default=[])
    args = parser.parse_args()
    asyncio.run(run(args.title, args.dept, args.summary, args.tasks))


if __name__ == "__main__":
    main()
