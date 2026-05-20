"""
Full end-to-end interview test.

Drives the complete pipeline:
  basic_info → icap_rag → interview → task_extraction → star
  → five_w2h → indicator → ocs_builder → preview

Then verifies ocs_document is stored in DB with correct OCS structure.

Run: python scripts/test_full_interview.py
"""
import asyncio
import json
import re
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import httpx

BASE = "http://localhost:8000/api/v1"

# ── Job under test ────────────────────────────────────────────────────────────
JOB_TITLE   = "倉庫管理員"
DEPARTMENT  = "物流部"
JOB_SUMMARY = "負責倉庫物料收發管理、庫存盤點及物料分類擺放，確保帳物相符、倉儲有序。"

# ── Scripted replies by stage ──────────────────────────────────────────────────
# interview phase: 3 messages needed to trigger task_extraction
INTERVIEW_REPLIES = [
    "我主要負責每天的進出貨管理，廠商送貨來的時候要核對送貨單，逐件清點數量，然後掃碼入庫。",
    "每週五我會做庫存盤點，用 Excel 記錄每個料號的實際庫存，和系統數量比對，發現差異要查明原因。",
    "另外我還負責倉庫的整理，料架要按類別擺放，標示清楚，讓其他部門來領料的時候方便找到。",
]

# After task extraction shows tasks, confirm
TASK_CONFIRM = "確認，這樣沒問題。"

# STAR replies (4 per task, reused for all tasks with minor variation)
STAR_REPLIES = [
    "上個月有一批原物料提前到貨，廠商沒有事先通知，我接到門衛電話才知道，當時倉庫正在辦公會議。",
    "我的工作是立刻去收貨區接待廠商，確認這批貨是否在我們採購訂單上，如果是才可以收。",
    "我先用手機查採購系統確認有這張訂單，然後逐件掃描條碼核對規格與數量，最後填寫入庫單並讓廠商簽收。",
    "這批貨全部順利入庫，沒有短少或規格錯誤，而且比預期時間早一小時完成，採購部門很滿意。",
]

# 5W2H answers (for each of the 6 required fields)
FIVE_W2H_ANSWERS: dict[str, str] = {
    "situation":         "每天上午 8:00 到 10:00 的進貨時段，以及下午 14:00 到 16:00 的出貨時段，在倉庫收發區進行。",
    "purpose":           "確保每筆進出貨都有憑據，避免帳物不符，同時讓庫存數字即時反映實際情況，方便採購和業務決策。",
    "stakeholders":      "採購部、業務部、廠商司機、物流公司",
    "tools":             "進銷存系統（ERP）、條碼掃描器、Excel、入庫單紙本、出庫申請單",
    "outputs":           "入庫確認單、出庫簽收單、每週庫存盤點表",
    "quality_standards": "數量核對準確率 100%；當日進貨必須當日入庫；庫存差異超過 0.5% 需在 24 小時內查明原因。",
}


def _current_phase(stage: str, gs: dict) -> str:
    """Compute the correct phase string to send based on current stage."""
    if stage == "star":
        tasks = gs.get("extracted_tasks", [])
        idx   = gs.get("current_task_index", 0)
        if idx < len(tasks):
            return f"star_{tasks[idx]['task_name']}"
    if stage == "five_w2h":
        tasks = gs.get("extracted_tasks", [])
        idx   = gs.get("current_task_index", 0)
        if idx < len(tasks):
            return f"five_w2h_{tasks[idx]['task_name']}"
    return "general"


async def stream_chat(client: httpx.AsyncClient, profile_id: str, content: str, phase: str = "general") -> str:
    """Call /chat SSE endpoint and collect the full AI response."""
    full_text = ""
    async with client.stream(
        "POST",
        f"{BASE}/interviews/{profile_id}/chat",
        json={"content": content, "phase": phase},
        timeout=120,
    ) as resp:
        if resp.status_code != 200:
            body = await resp.aread()
            raise RuntimeError(f"Chat {resp.status_code}: {body.decode()[:200]}")
        async for line in resp.aiter_lines():
            if line.startswith("data: "):
                raw = line[6:]
                if raw in ('["[DONE]"]', '"[DONE]"', "[DONE]"):
                    break
                try:
                    chunk = json.loads(raw)
                    if isinstance(chunk, str) and chunk != "[DONE]":
                        full_text += chunk
                except json.JSONDecodeError:
                    if raw != "[DONE]":
                        full_text += raw
    return full_text


async def get_stage(client: httpx.AsyncClient, profile_id: str) -> tuple[str, dict]:
    """Return current stage and graph_state from DB."""
    r = await client.get(f"{BASE}/job-profiles/{profile_id}")
    data = r.json()
    return data.get("stage", "?"), data.get("graph_state") or {}


def print_stage(label: str, stage: str, ai_preview: str = ""):
    preview = ai_preview.replace("\n", " ")[:100]
    print(f"  [{stage:>15s}]  {label}")
    if preview:
        print(f"               AI: {preview}…")


async def main():
    async with httpx.AsyncClient(timeout=180) as client:

        # ── 1. Create user & profile ──────────────────────────────────────────
        email = f"interview-test-{uuid.uuid4().hex[:6]}@example.com"
        r = await client.post(f"{BASE}/users/", json={"email": email, "name": "InterviewBot"})
        assert r.status_code == 201, r.text
        user_id = r.json()["id"]

        r = await client.post(
            f"{BASE}/job-profiles/?user_id={user_id}",
            json={"job_title": JOB_TITLE, "department": DEPARTMENT, "job_summary": JOB_SUMMARY},
        )
        assert r.status_code == 201, r.text
        profile_id = r.json()["id"]
        print(f"\nProfile: {profile_id}  ({JOB_TITLE} / {DEPARTMENT})\n")

        # ── 2. Trigger interview start (silent send) ──────────────────────────
        print("Phase: interview")
        ai = await stream_chat(client, profile_id, "開始訪談")
        stage, gs = await get_stage(client, profile_id)
        print_stage("start interview", stage, ai)

        # ── 3. Interview phase — 3 messages ───────────────────────────────────
        for i, reply in enumerate(INTERVIEW_REPLIES, 1):
            ai = await stream_chat(client, profile_id, reply, _current_phase(stage, gs))
            stage, gs = await get_stage(client, profile_id)
            print_stage(f"interview msg {i}", stage, ai)
            if stage == "task_extraction":
                break

        # ── 4. Confirm tasks ──────────────────────────────────────────────────
        if stage == "task_extraction":
            tasks = gs.get("extracted_tasks", [])
            print(f"\n  Extracted {len(tasks)} tasks: {[t['task_name'] for t in tasks]}")
            ai = await stream_chat(client, profile_id, TASK_CONFIRM)
            stage, gs = await get_stage(client, profile_id)
            print_stage("confirm tasks", stage, ai)

        # ── 5. STAR phase — 4 replies per task ────────────────────────────────
        print("\nPhase: star")
        star_rounds = 0
        while stage == "star":
            tasks = gs.get("extracted_tasks", [])
            idx   = gs.get("current_task_index", 0)
            task_name = tasks[idx]["task_name"] if idx < len(tasks) else "?"
            reply = STAR_REPLIES[star_rounds % len(STAR_REPLIES)]
            phase = _current_phase(stage, gs)
            ai = await stream_chat(client, profile_id, reply, phase)
            stage, gs = await get_stage(client, profile_id)
            star_rounds += 1
            print_stage(f"star [{task_name}] round {star_rounds}", stage, ai)
            if star_rounds > 40:
                print("  [WARN] star safety cap hit")
                break

        # ── 6. 5W2H phase — answer each missing field ────────────────────────
        print("\nPhase: five_w2h")
        w2h_rounds = 0
        while stage == "five_w2h":
            tasks = gs.get("extracted_tasks", [])
            idx   = gs.get("current_task_index", 0)
            task_name = tasks[idx]["task_name"] if idx < len(tasks) else "done"

            # Pick missing field from graph state, then provide its scripted answer
            missing = gs.get("missing_fields", [])
            field = missing[0] if missing else "situation"
            answer = FIVE_W2H_ANSWERS.get(field, "每天都在倉庫進行這些工作，流程穩定。")

            phase = _current_phase(stage, gs)
            ai = await stream_chat(client, profile_id, answer, phase)
            stage, gs = await get_stage(client, profile_id)
            w2h_rounds += 1
            print_stage(f"5W2H [{task_name}] field={field}", stage, ai)
            if w2h_rounds > 60:
                print("  [WARN] 5W2H safety cap hit")
                break

        # ── 7. Indicator + OCS builder run automatically ──────────────────────
        print("\nPhase: indicator / ocs_builder")
        if stage in ("indicator", "ksa"):
            ai = await stream_chat(client, profile_id, "繼續")
            stage, gs = await get_stage(client, profile_id)
            print_stage("auto-complete", stage, ai)

        # Wait for preview
        wait = 0
        while stage not in ("preview", "ksa") and wait < 10:
            await asyncio.sleep(3)
            stage, gs = await get_stage(client, profile_id)
            wait += 1

        print(f"\nFinal stage: {stage}")

        # ── 8. Verify ocs_document in DB ─────────────────────────────────────
        print("\n── OCS Document Validation ──────────────────────────────────")
        ocs = gs.get("ocs_document", {})

        if not ocs:
            print("FAIL: ocs_document not found in graph_state")
            sys.exit(1)

        profile_sec  = ocs.get("ocs_profile", {})
        units        = ocs.get("ocs_content", {}).get("ocu_units", [])
        attitudes    = ocs.get("ocs_attitude", {}).get("attitudes", [])

        all_tasks   = [t for u in units for t in u.get("tasks", [])]
        all_blocks  = [b for t in all_tasks for b in t.get("competency_blocks", [])]
        all_inds    = [i for b in all_blocks for i in b.get("indicators", [])]
        all_outputs = [o for b in all_blocks for o in b.get("outputs", [])]
        all_k       = [k for b in all_blocks for k in b.get("knowledge", [])]
        all_s       = [s for b in all_blocks for s in b.get("skills", [])]
        icap_k      = [k for k in all_k if k.get("icap_ref")]
        icap_s      = [s for s in all_s if s.get("icap_ref")]

        # Verify hierarchical code format: T1.1 / P1.1.1 / O1.1.1 / K01 / S01 / A01
        ind_codes_hierarchical = all(
            re.match(r"^P\d+\.\d+\.\d+$", i.get("code", "")) for i in all_inds
        ) if all_inds else False
        out_codes_hierarchical = all(
            re.match(r"^O\d+\.\d+\.\d+$", o.get("code", "")) for o in all_outputs
        ) if all_outputs else False
        task_codes_hierarchical = all(
            re.match(r"^T\d+\.\d+$", t.get("task_codes", [{}])[0].get("code", "")) for t in all_tasks
        ) if all_tasks else False
        k_codes_doc_level = all(
            re.match(r"^K\d{2}$", k.get("code", "")) for k in all_k
        ) if all_k else False
        a_codes_doc_level = all(
            re.match(r"^A\d{2}$", a.get("code", "")) for a in attitudes
        ) if attitudes else False

        checks = [
            ("ocs_code set",           bool(profile_sec.get("ocs_code"))),
            ("occupation_name set",    bool(profile_sec.get("ocs_name", {}).get("occupation_name"))),
            (">=1 OCU unit",           len(units) >= 1),
            (">=1 task",               len(all_tasks) >= 1),
            ("task_codes present",     all(t.get("task_codes") for t in all_tasks)),
            ("competency_blocks",      all(t.get("competency_blocks") for t in all_tasks)),
            (">=1 P indicator",        len(all_inds) >= 1),
            (">=1 O output",           len(all_outputs) >= 1),
            (">=1 K item",             len(all_k) >= 1),
            (">=1 S item",             len(all_s) >= 1),
            (">=1 attitude",           len(attitudes) >= 1),
            ("P codes P1.1.1 format",  ind_codes_hierarchical),
            ("O codes O1.1.1 format",  out_codes_hierarchical),
            ("T codes T1.1 format",    task_codes_hierarchical),
            ("K codes K01 format",     k_codes_doc_level),
            ("A codes A01 format",     a_codes_doc_level),
            ("K source_type set",      all(k.get("source_type") for k in all_k)),
            ("A source_type set",      all(a.get("source_type") for a in attitudes)),
        ]

        passed = 0
        for label, ok in checks:
            status = "OK" if ok else "FAIL"
            print(f"  {status}  {label}")
            if ok:
                passed += 1

        print(f"\n  OCU units : {len(units)}")
        print(f"  Tasks     : {len(all_tasks)}")
        print(f"  P inds    : {len(all_inds)}")
        print(f"  O outputs : {len(all_outputs)}")
        print(f"  K items   : {len(all_k)}  (iCAP-matched: {len(icap_k)})")
        print(f"  S items   : {len(all_s)}  (iCAP-matched: {len(icap_s)})")
        print(f"  Attitudes : {len(attitudes)}")

        if icap_k or icap_s:
            print("\n  iCAP references found:")
            for k in icap_k[:3]:
                print(f"    K [{k['code']}] {k['name']}  ← {k['icap_ref']}")
            for s in icap_s[:3]:
                print(f"    S [{s['code']}] {s['name']}  ← {s['icap_ref']}")

        print(f"\n  OCS code  : {profile_sec.get('ocs_code')}")
        print(f"  Occ name  : {profile_sec.get('ocs_name', {}).get('occupation_name')}")

        print(f"\n{passed}/{len(checks)} checks passed", end="")
        if passed == len(checks):
            print("  — ALL PASS")
        else:
            print("  — SOME FAILED")
            sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
