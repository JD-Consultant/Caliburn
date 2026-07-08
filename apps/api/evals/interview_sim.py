"""模擬受訪者回歸 v2(T14;ADR 0027;pre-testing 制度化 §10 收編3)。

    cd apps/api && PYTHONUTF8=1 uv run python evals/interview_sim.py [--max-turns 20] [--dump]

形狀:**純智力迴圈,不碰 DB**(記憶體 doc + 真 v2 管線:書記 scribe_pass + 帳本 ledger +
顧問 chat_with_tools)——DB/route 由 tests/ 蓋;這裡量「問得好不好 + 抽得全不全」。
模擬員工 = cheap LLM 綁**事實表**(黃金範本樣張王OO;只准照表答,表外說不知道)。
量兩軸(spec §8):coverage(帳本缺口清空率、細項命中率)+ depth(引文驗證率、每回合進帳、
hedging 追問)。結果留 docs/specs 校準紀錄;門檻改=重跑,不改碼。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.llm_openrouter import OpenRouterLlm  # noqa: E402
from app.core.knowledge_dto import CitableItem, CompetencyPool  # noqa: E402
from app.interview import consultant as C  # noqa: E402
from app.interview import ledger as L  # noqa: E402
from app.interview.scribe import scribe_pass  # noqa: E402
from app.interview.tools import CONSULTANT_TOOLS, dispatch_tool  # noqa: E402
from functools import partial  # noqa: E402

TASK_PATH = "ocs_content.ocu_units.u1.tasks.t1"

# 事實表 = 黃金範本樣張 §4.2(王OO,任務 2.2 手動測試+版本回歸)
FACTS = {
    "frequency": ("每天會零星測,每兩週上線前會密集跑兩天回歸", ["兩週", "雙週", "每天"]),
    "time_share_pct": ("大概占我四分之一的時間,25%", ["25", "四分之一"]),
    "duration": ("密集的那次大概兩天", ["兩天", "2 天", "2天"]),
    "volume": ("回歸套件大概三百多條,自動化跑兩百、手動一百", ["300", "三百", "兩百"]),
    "trigger": ("每天 build 好 Slack bot 會通知,我就開始測", ["build", "通知", "Slack"]),
    "inputs": ("要有回歸清單、測試環境的帳號,還有這版改了什麼的說明", ["回歸清單", "帳號"]),
    "tools": ("staging 環境、Postman,自動化那塊是自己寫的 pytest 腳本", ["staging", "Postman", "pytest"]),
    "collaborators": ("有缺陷就跟開發來回,環境掛了找 DevOps", ["開發", "DevOps"]),
    "wait_points": ("環境只有一套,被開發佔住就要排隊,平均等一兩個小時", ["等", "排隊", "小時"]),
    "exceptions": ("遇到擋版的 blocker 就立刻通報組長跟開發 Lead,當天修完重測", ["blocker", "通報", "擋版"]),
    "standards": ("回歸要百分之百跑完、沒有未解的 blocker,我簽核了才放行", ["100", "百分之百", "簽核"]),
}

EMPLOYEE_SYSTEM = """你在扮演軟體測試工程師「王OO」接受職務說明書訪談。
你【只能】根據下面事實表回答;表上沒有的就說「這我不確定」。口語化、像聊天,一次一到三句,
不要主動把整張表倒出來,顧問問到才講對應的那點。

事實表(任務「手動測試+版本回歸」):
""" + "\n".join(f"- {k}:{v[0]}" for k, v in FACTS.items())


def _knowledge():
    """golden-sample 對齊的知識庫 stub(官方碼池,供書記 record_task_pool)。"""
    code = "ISD2519-002v2"

    class _K:
        async def competencies(self, ocs_code):
            return CompetencyPool(
                ocs_code=code,
                knowledge=[CitableItem(id="k1", type="K", code="K2.2a", name="測試層級與技術")],
                skills=[CitableItem(id="s1", type="S", code="S2.2a", name="測試工具與技術使用能力"),
                        CitableItem(id="s2", type="S", code="S2.2b", name="資料備份和還原能力")],
                outputs=[CitableItem(id="o1", type="O", code="O2.2", name="測試事件報告")],
                attitudes=[CitableItem(id="a1", type="A", code="A03", name="謹慎細心"),
                           CitableItem(id="a2", type="A", code="A04", name="壓力容忍")])

        async def search_occupations(self, query, *, top_k=10):
            return type("R", (), {"hits": []})()

        async def occupation_tasks(self, ocs_code):
            return type("R", (), {"ocs_name": "軟體測試工程人員", "units": []})()

    return _K()


def _doc() -> dict:
    return {
        "ocs_profile": {"ocs_code": "ISD2519-002v2", "job_description": ""},
        "ocs_content": {"ocu_units": [{
            "_uid": "u1", "ocu_name": "軟體測試實作與執行",
            "tasks": [{"_tid": "t1",
                       "task_codes": [{"code": "T2.2", "name": "測試執行(手動+版本回歸)"}],
                       "competency_blocks": [{"outputs": []}],
                       "details": {}}]}]},
        "ocs_attitude": {"attitudes": []},
    }


def _score_slots(details: dict) -> tuple[int, list[str]]:
    hit, miss = 0, []
    for key, (_, keywords) in FACTS.items():
        v = str(details.get(key) or "")
        if v and any(kw in v for kw in keywords):
            hit += 1
        elif v:
            miss.append(f"{key}={v!r}(未含關鍵字)")
    return hit, miss


async def simulate(max_turns: int, dump: bool = False) -> dict:
    llm = OpenRouterLlm()
    knowledge = _knowledge()
    dispatch = partial(dispatch_tool, knowledge=knowledge)
    doc = _doc()
    state: dict = {}
    transcript: list[tuple[str, str]] = []
    employee_texts: list[str] = []
    ev_total = ev_verified = 0
    quote_lens: list[int] = []
    progressed_turns = 0
    question = C.opening_disclosure()
    turns_used = 0

    for i in range(max_turns):
        turns_used = i + 1
        conv = "\n".join(f"{'顧問' if r == 'consultant' else '我'}:{t}" for r, t in transcript[-8:])
        answer = (await llm.complete_text(
            EMPLOYEE_SYSTEM + f"\n\n最近對話:\n{conv}\n顧問剛問:{question}\n你的回答:",
            role="cheap") or "嗯…這我不確定").strip()
        transcript.append(("consultant", question))
        employee_texts.append(answer)

        # ① 書記 pass(v2)
        scribe_res = await scribe_pass(llm, knowledge, doc=doc,
                                       employee_texts=employee_texts, human_touched=[])
        if scribe_res.new_doc is not None:
            doc = scribe_res.new_doc
        for e in scribe_res.evidence:
            ev_total += 1
            ev_verified += 1 if e["verified"] else 0
            if e["verified"]:
                quote_lens.append(len(e.get("quote", "")))
        if scribe_res.progressed:
            progressed_turns += 1

        # ② 帳本
        state = L.note_attempt(state, state.get("last_gap"), scribe_res.progressed)
        state["last_gap"] = L.next_gap(doc, state, {})

        # ③ 顧問 chat_with_tools
        msgs = C.build_consultant_messages(doc=doc, ledger_state=state, recent_turns=transcript,
                                           pending=[], employee_text=answer)
        chat = await llm.chat_with_tools(role="interview", messages=msgs,
                                         tools=CONSULTANT_TOOLS, dispatch=dispatch)
        question = (chat.text or "還有想補充的嗎?").strip()
        transcript.append(("employee", answer))

        if dump:
            print(f"--- turn {turns_used} ---\n  員工:{answer}\n  書記:{scribe_res.guard_log}\n"
                  f"  下一縫:{state.get('last_gap')}\n  顧問:{question[:80]}", file=sys.stderr)
        if L.can_finish(doc, state, {})[0]:
            break

    task = next((t for _, t, tp in L.iter_tasks(doc) if tp.endswith("tasks.t1")), {})
    details = task.get("details") or {}
    hit, mismatches = _score_slots(details)
    ok, blockers = L.can_finish(doc, state, {})
    cov = L.coverage(doc, state)
    return {
        "turns_used": turns_used,
        "coverage": cov,
        "coverage_cleared": ok,
        "blockers_remaining": len(blockers),
        "slot_keyword_accuracy": round(hit / len(FACTS), 2),
        "slot_mismatches": mismatches,
        "evidence_verified_rate": round(ev_verified / ev_total, 2) if ev_total else None,
        "avg_quote_len": round(sum(quote_lens) / len(quote_lens), 1) if quote_lens else 0,
        "progressed_turn_rate": round(progressed_turns / turns_used, 2) if turns_used else 0,
        "details_filled": {k: details.get(k) for k in FACTS if details.get(k)},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args()
    report = asyncio.run(simulate(args.max_turns, dump=args.dump))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # v2 出廠閘門(校準 #3 後修數字):細項命中率 ≥0.6 + 引文驗證率 ≥0.8
    passed = (report["slot_keyword_accuracy"] >= 0.6
              and (report["evidence_verified_rate"] or 0) >= 0.8)
    print("GATE:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
