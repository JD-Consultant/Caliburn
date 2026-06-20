"""Live end-to-end smoke driver for graph_v3 (manual verification, not a test).

跑一條真流程：真 indexer 檢索 + 真 OpenRouter 深問 + 真 Postgres 落庫 / checkpointer。
繞過 CopilotKit/前端（那只是傳輸層），直接驅動 graph + build_live_deps()。

前置：
  1) 起 indexer：  (S:\\jd-ocs-indexer)  uv run jd-ocs-indexer serve --host 127.0.0.1 --port 8000
  2) Postgres 在跑；backend/.env 設好 DATABASE_URL / INDEXER_BASE_URL / OPENROUTER_API_KEY
  3) 跑：           (s:\\jobintel-ai\\backend)  uv run python scripts/live_smoke.py

每個 interrupt 會在終端機問你，輸入答案後 Enter 繼續；最後印出組裝好的 OCS 文件。
"""
from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid

# 讓 `import app.*` 可用（本檔在 backend/scripts/ 下，往上一層是 backend/）
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langgraph.types import Command  # noqa: E402

from app.config import settings  # noqa: E402
from app.database import AsyncSessionLocal  # noqa: E402
from app.models import JobProfile, User  # noqa: E402
from app.graph_v3.checkpointer import open_pg_checkpointer  # noqa: E402
from app.graph_v3.graph import build_graph_v3  # noqa: E402
from app.graph_v3.serving import build_live_deps  # noqa: E402
from app.graph_v3.state import new_state  # noqa: E402


def _ask(prompt: str) -> str:
    """阻塞讀一行（CLI 工具，單用戶，阻塞可接受）。"""
    return input(prompt).strip()


async def _ensure_profile(job_title: str, job_summary: str) -> uuid.UUID:
    """建一筆 User+JobProfile，回 profile id。"""
    uid = uuid.uuid4()
    pid = uuid.uuid4()
    async with AsyncSessionLocal() as s:
        s.add_all([
            User(id=uid, email=f"smoke-{uid}@example.com", name="live-smoke"),
            JobProfile(id=pid, user_id=uid, job_title=job_title, job_summary=job_summary),
        ])
        await s.commit()
    return pid


def _resume_for(payload: dict):
    """依 interrupt 種類，在終端機取得 resume 值。"""
    kind = payload.get("kind")

    if kind == "select_profile":
        cands = payload.get("candidates", [])
        if not cands:
            print("⚠ indexer 沒回任何候選 OCS — 檢查 indexer 是否有資料 / 查詢字串。")
        for i, c in enumerate(cands):
            print(f"  [{i}] {c.get('ocs_code','?')}  {c.get('job_title') or c.get('task_title') or ''}")
        idx = _ask("選一個 OCS 候選（輸入編號，預設 0）：") or "0"
        chosen = cands[int(idx)]["ocs_code"]
        print(f"→ 選定 {chosen}")
        return {"ocs_code": chosen}

    if kind == "edit_tasks":
        tasks = payload.get("tasks", [])
        print(f"catalog 取出 {len(tasks)} 個任務：")
        for i, t in enumerate(tasks):
            print(f"  [{i}] {t.get('task_name','?')}  (unit={t.get('unit_title','')})")
        drop = _ask("要刪哪些任務?（逗號分隔編號，直接 Enter = 全留）：")
        if drop:
            drop_set = {int(x) for x in drop.split(",") if x.strip().isdigit()}
            tasks = [t for i, t in enumerate(tasks) if i not in drop_set]
        print(f"→ 保留 {len(tasks)} 個任務")
        return {"tasks": tasks}

    if kind == "ask_human":
        label = payload.get("label", "")
        print(f"\n[{payload.get('stage')}] {label}")
        print(f"  Q: {payload.get('question','')}")
        return _ask("  你的回答：")

    if kind == "curate_ks":
        task_name = payload.get("task_name", "?")
        ks = payload.get("ks", {})
        for cat in ("knowledge", "skills"):
            names = [it.get("content") for it in ks.get(cat, [])]
            print(f"  [{task_name}] {cat}: {names}")
        _ask("（catalog K/S 如上；Enter 接受不改）")
        return {"ks": {"knowledge": [], "skills": []}}

    if kind == "curate_attitudes":
        attitudes = payload.get("attitudes", [])
        names = [it.get("content") for it in attitudes]
        print(f"  attitudes: {names}")
        _ask("（catalog A 如上；Enter 接受不改）")
        return {"attitudes": []}

    if kind == "preview":
        print("\n===== OCS 文件預覽 =====")
        print(json.dumps(payload.get("document", {}), ensure_ascii=False, indent=2))
        _ask("（Enter 確認並存檔）")
        return "confirm"

    # 未知 interrupt：原樣印出，讓人自行輸入
    print("⚠ 未知 interrupt payload：", json.dumps(payload, ensure_ascii=False))
    return _ask("  resume 值（字串）：")


async def main() -> None:
    if not settings.openrouter_api_key:
        print("✗ 未設 OPENROUTER_API_KEY（backend/.env 或環境變數）。深問會拿不到 LLM 輸出。")
    print(f"indexer = {settings.indexer_base_url}")
    print(f"db      = {settings.database_url}")

    job_title = _ask("職稱（例：設備維護工程師）：") or "設備維護工程師"
    job_summary = _ask("職務簡述（可空）：")

    pid = await _ensure_profile(job_title, job_summary)
    thread_id = str(pid)
    print(f"job_profile_id / thread_id = {thread_id}")

    deps = build_live_deps()
    # 先確認 indexer 連得到
    try:
        ok = await deps.knowledge.healthz()
        print(f"indexer healthz = {ok}")
    except Exception as exc:  # noqa: BLE001
        print(f"✗ indexer 連線失敗：{exc}（確認 indexer serve 有起、INDEXER_BASE_URL 正確）")
        await deps.knowledge.aclose()
        return

    async with open_pg_checkpointer(settings.database_url) as saver:
        graph = build_graph_v3(checkpointer=saver)
        cfg = {"configurable": {"thread_id": thread_id, "deps": deps}}

        out = await graph.ainvoke(new_state(job_profile_id=thread_id,
                                            job_title=job_title,
                                            job_summary=job_summary), cfg)
        guard = 0
        while "__interrupt__" in out:
            guard += 1
            if guard > 200:
                print("✗ interrupt 迴圈超過 200 次，中止。")
                break
            payload = out["__interrupt__"][0].value
            resume = _resume_for(payload)
            out = await graph.ainvoke(Command(resume=resume), cfg)

        print("\n===== 完成 =====")
        print("current_step =", out.get("current_step"))
        if out.get("document"):
            print(json.dumps(out["document"], ensure_ascii=False, indent=2))
        print(f"（文件已落 document_versions；profile={thread_id}）")

    await deps.knowledge.aclose()


if __name__ == "__main__":
    asyncio.run(main())
