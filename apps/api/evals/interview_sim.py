"""模擬受訪者回歸 v4(T10;ADR 0028/0030/**0033**;承 v2/T14 校準 #3 教訓 §16.14)。

    cd apps/api && PYTHONUTF8=1 uv run python evals/interview_sim.py [--max-turns 20] [--dump]
    換模 A/B:MODEL_INTERVIEW=<slug> uv run python evals/interview_sim.py

形狀:**純智力迴圈,不碰 DB**。三段:
① 裁剪段(0028 D1/D6):**劇本化員工述職**(消掉 §16.14 的模擬員工漂移混淆因子)
   → curation_pass → 量預勾 precision/recall(vs 事實表 DOES)+ declined 正確率(⊆DOESNT)。
② 深聊段(v4;ADR 0033):模擬員工(cheap LLM 綁事實表)× 真管線(書記 op→verify→
   `_pending` + **議程事件工具 open/close_episode** + **收割 harvest→P** + 顧問)→
   grounding(verify 通過率)+ **P 產出量**(indicators_total;收割是行為指標的家)。
   鏡射 service.run_turn 的 episode→harvest 接線(in-memory,無 DB/持久化)。
③ 態度收尾段(0028 D3):深聊全逐字稿 → attitudes_pass → 條數 ≤MAX_A、守衛丟棄數。
閘門=**確定性指標**(§16.14:verify 通過率+進帳率+裁剪 precision + **P≥1**);
recall/態度=資訊訊號。結果留 docs/specs 校準紀錄;門檻改=重跑,不改碼。
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
from app.interview import agenda as AG  # noqa: E402
from app.interview import consultant as C  # noqa: E402
from app.interview import coverage as CO  # noqa: E402
from app.interview.attitudes import attitudes_pass  # noqa: E402
from app.interview.curation import curation_pass  # noqa: E402
from app.interview.harvest import harvest_pass  # noqa: E402
from app.interview.scribe import scribe_pass  # noqa: E402
from app.interview.tools import CONSULTANT_TOOLS, dispatch_tool  # noqa: E402

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


# ── ① 裁剪段 ground truth(0028 D6;黃金範本職類的官方任務盤)──────────────
# 劇本化述職(非 LLM 員工):消掉 §16.14 的 Sim2Real 漂移,單測抽取器。
OFFICIAL_POOL = [
    {"key": "ISD:T2.1", "name": "測試案例設計", "unit": "測試設計",
     "ocs_code": "ISD", "task_code": "T2.1"},
    {"key": "ISD:T2.2", "name": "測試執行與版本回歸", "unit": "測試實作",
     "ocs_code": "ISD", "task_code": "T2.2"},
    {"key": "ISD:T3.1", "name": "缺陷通報與追蹤", "unit": "測試實作",
     "ocs_code": "ISD", "task_code": "T3.1"},
    {"key": "ISD:T4.1", "name": "自動化測試框架開發", "unit": "測試工程",
     "ocs_code": "ISD", "task_code": "T4.1"},
    {"key": "ISD:T5.1", "name": "性能與壓力測試", "unit": "測試工程",
     "ocs_code": "ISD", "task_code": "T5.1"},
    {"key": "ISD:T1.1", "name": "測試環境建置", "unit": "測試規劃",
     "ocs_code": "ISD", "task_code": "T1.1"},          # 未提及=ambiguous,兩邊都不該標
]
DOES = {"ISD:T2.1", "ISD:T2.2", "ISD:T3.1"}
DOESNT = {"ISD:T4.1", "ISD:T5.1"}
CURATION_SAID = [
    "我平常主要在寫測試案例,然後每版上線前跑測試執行跟版本回歸",
    "有 bug 我就開單做缺陷通報,追蹤到開發修完我再驗一次",
    "自動化測試框架開發不是我,那是 SDET 團隊在做;性能與壓力測試我們公司沒有做",
]

# ── ③ 態度收尾段官方 A 池(含干擾項;正解=A03 謹慎細心 / A04 壓力容忍 有故事佐證)──
A_POOL = ["A01", "A03", "A04", "A06"]
A_ITEMS = {"A01": "親和關係", "A03": "謹慎細心", "A04": "壓力容忍", "A06": "自我提升"}


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


def _count_indicators(doc: dict) -> int:
    """全文件行為指標(P)條數——收割是 P 的家,這是 v4「真的產 P」的主量尺。"""
    return sum(len(b.get("indicators") or [])
               for _, t, _ in CO.iter_tasks(doc)
               for b in (t.get("competency_blocks") or []))


def _score_slots(details: dict) -> tuple[int, list[str]]:
    hit, miss = 0, []
    for key, (_, keywords) in FACTS.items():
        v = str(details.get(key) or "")
        if v and any(kw in v for kw in keywords):
            hit += 1
        elif v:
            miss.append(f"{key}={v!r}(未含關鍵字)")
    return hit, miss


async def curation_segment(llm) -> dict:
    """① 裁剪段:劇本述職 → curation_pass → precision/recall/declined 正確率。"""
    res = await curation_pass(llm, pool_tasks=OFFICIAL_POOL, employee_texts=CURATION_SAID)
    pre = {p["key"] for p in res.precheck}
    dec = {d["key"] for d in res.declined}
    tp = len(pre & DOES)
    return {
        "precheck": sorted(pre), "declined": sorted(dec),
        "precision": round(tp / len(pre), 2) if pre else 0.0,
        "recall": round(tp / len(DOES), 2),
        "declined_all_correct": dec <= DOESNT and not (dec & DOES),
        "ambiguous_untouched": "ISD:T1.1" not in (pre | dec),
        "guard_drops": len(res.guard_log),
    }


async def attitudes_segment(llm, employee_texts: list[str]) -> dict:
    """③ 態度收尾段:全逐字稿 → attitudes_pass。條數/守衛丟棄=資訊訊號(非閘門)。"""
    res = await attitudes_pass(llm, pool=A_POOL, pool_items=A_ITEMS,
                               employee_texts=employee_texts, existing=[])
    return {"proposals": [{"code": p["pool_id"], "quote": p["quote"][:30]}
                          for p in res.proposals],
            "count": len(res.proposals), "cap_ok": len(res.proposals) <= CO.MAX_A,
            "guard_drops": len(res.guard_log), "failed": res.failed}


async def simulate(max_turns: int, dump: bool = False) -> dict:
    llm = OpenRouterLlm()
    knowledge = _knowledge()
    doc = _doc()
    state: dict = {}
    ref_ocs = frozenset()      # has_occupation 由 doc.ocs_profile 撐;pool 由 build_pool_inputs 抓 doc 碼
    transcript: list[tuple[str, str]] = []
    employee_texts: list[str] = []
    turns_map: dict[int, str] = {}
    ev_total = ev_verified = 0
    quote_lens: list[int] = []
    progressed_turns = 0
    ep_opened = ep_closed = harvest_runs = harvest_landed = 0
    question = C.opening_disclosure()
    turns_used = 0

    async def run_harvest() -> None:
        """收割最近歸檔事件一次(鏡射 service ③⅝:episode→BEI 編碼→P)。"""
        nonlocal doc, harvest_runs, harvest_landed
        ep = (state.get("episodes") or [None])[-1]
        if not ep:
            return
        h_res = await harvest_pass(llm, knowledge, doc=doc, turns=turns_map,
                                   episode=ep, header_codes=set())
        harvest_runs += 1
        if h_res.new_doc is not None:
            doc = h_res.new_doc
        if h_res.progressed:
            harvest_landed += 1

    for i in range(max_turns):
        turns_used = i + 1
        conv = "\n".join(f"{'顧問' if r == 'consultant' else '我'}:{t}" for r, t in transcript[-8:])
        answer = (await llm.complete_text(
            EMPLOYEE_SYSTEM + f"\n\n最近對話:\n{conv}\n顧問剛問:{question}\n你的回答:",
            role="cheap") or "嗯…這我不確定").strip()
        transcript.append(("consultant", question))
        employee_texts.append(answer)
        turns_map[turns_used] = answer

        # ① 書記 pass(v3:op→verify→`_pending`;grounding=verify 通過率)
        scribe_res = await scribe_pass(llm, knowledge, doc=doc, turns=turns_map,
                                       turn_id=turns_used, header_codes=set())
        if scribe_res.new_doc is not None:
            doc = scribe_res.new_doc
        rejects = sum(1 for g in scribe_res.guard_log if g.startswith("verify-reject"))
        landed = len(scribe_res.ops)
        ev_total += landed + rejects
        ev_verified += landed
        for op in scribe_res.ops:
            q = ((op.get("src") or {}).get("quote") or {}).get("text") or ""
            if q:
                quote_lens.append(len(q))
        if scribe_res.progressed:
            progressed_turns += 1

        # ② 顧問 chat_with_tools(含議程工具+artifact;鏡射 service.run_turn ③/③⅛)
        candidates = AG.blank_candidates(doc, state, ref_ocs)
        agenda_view = AG.agenda_view(doc, state, pool_tasks=[], ref_codes=ref_ocs,
                                     turns_n=turns_used)
        msgs = C.build_consultant_messages(doc=doc, ledger_state=state, recent_turns=transcript,
                                           employee_text=answer, agenda_view=agenda_view)
        agenda_actions: list[tuple[str, dict]] = []

        async def _dispatch(name: str, arguments: dict):
            if name == "open_episode":
                agenda_actions.append(("open", arguments or {}))
                return {"ok": True, "note": "已開始這個事件——請往細節、完成標準、驗收方式追問。"}
            if name == "close_episode":
                agenda_actions.append(("close", arguments or {}))
                return {"ok": True, "note": "已記錄,事件內容會編碼進文件。"}
            return await dispatch_tool(name, arguments, knowledge=knowledge)

        chat = await llm.chat_with_tools(
            role="interview", messages=msgs,
            tools=CONSULTANT_TOOLS + AG.agenda_tools(candidates), dispatch=_dispatch)
        question = (chat.text or "還有想補充的嗎?").strip()
        transcript.append(("employee", answer))

        # ②⅛ 議程動作確定性 apply(鏡射 service 269-278)
        for kind, args in agenda_actions:
            if kind == "open":
                real = AG.resolve_target(candidates, str(args.get("target") or ""))
                if real:
                    state = AG.open_episode(state, target=real, seq=turns_used,
                                            note=str(args.get("note") or ""))
                    ep_opened += 1
            elif kind == "close" and AG.episode_state(state) is not None:
                state = AG.close_episode(state, reason=str(args.get("reason") or "covered"),
                                         seq=turns_used)
                state["pending_harvest"] = True

        # ②⅜ 收割(鏡射 service 296-321:auto-close 後衛 + pending_harvest → harvest→P)
        if AG.signals(state, turns_used)["auto_close"] and AG.episode_state(state) is not None:
            state = AG.close_episode(state, reason="auto", seq=turns_used)
            state["pending_harvest"] = True
        if state.get("pending_harvest"):
            await run_harvest()
            ep_closed += 1
            state = {k: v for k, v in state.items() if k != "pending_harvest"}

        # ②½ 帳本收帳(鏡射 service 340-342;dry_streak 累計供 auto-close)
        state = AG.bump_streaks(state, has_episode=AG.episode_state(state) is not None,
                                progressed=scribe_res.progressed)

        if dump:
            ep = AG.episode_state(state)
            print(f"--- turn {turns_used} ---\n  員工:{answer}\n  書記:{scribe_res.guard_log}\n"
                  f"  事件:{('開→' + str(ep.get('target'))) if ep else '無'}"
                  f" P={_count_indicators(doc)}\n  顧問:{question[:80]}", file=sys.stderr)
        if CO.can_finish(doc, state, {})[0]:
            break

    # 收尾:仍有開著的事件 → 強制收割一次(sim 量 P;真管線靠 close/auto-close/後續回合接)
    if AG.episode_state(state) is not None:
        state = AG.close_episode(state, reason="covered", seq=turns_used)
        await run_harvest()
        ep_closed += 1

    task = next((t for _, t, tp in CO.iter_tasks(doc) if tp.endswith("tasks.t1")), {})
    details = task.get("details") or {}
    hit, mismatches = _score_slots(details)
    ok, blockers = CO.can_finish(doc, state, {})
    cov = CO.coverage(doc, state)

    # ①/③ v3 段(0028):裁剪(劇本述職)+ 態度收尾(深聊全逐字稿)
    curation = await curation_segment(llm)
    attitudes = await attitudes_segment(llm, employee_texts)

    return {
        "turns_used": turns_used,
        "coverage": cov,
        "coverage_cleared": ok,
        "blockers_remaining": len(blockers),
        "indicators_total": _count_indicators(doc),        # v4:收割產出的 P 總數
        "episodes_opened": ep_opened,
        "episodes_closed": ep_closed,
        "harvest_runs": harvest_runs,
        "harvest_landed": harvest_landed,
        "slot_keyword_accuracy": round(hit / len(FACTS), 2),
        "slot_mismatches": mismatches,
        "verify_pass_rate": round(ev_verified / ev_total, 2) if ev_total else None,
        "avg_quote_len": round(sum(quote_lens) / len(quote_lens), 1) if quote_lens else 0,
        "progressed_turn_rate": round(progressed_turns / turns_used, 2) if turns_used else 0,
        "details_filled": {k: details.get(k) for k in FACTS if details.get(k)},
        "curation": curation,
        "attitudes": attitudes,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-turns", type=int, default=20)
    ap.add_argument("--dump", action="store_true")
    args = ap.parse_args()
    report = asyncio.run(simulate(args.max_turns, dump=args.dump))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # 閘門=**有效的確定性指標**(校準 #3/§16.14):grounding(引文逐字驗)+ 每回合進帳
    # + 裁剪 precision(0028 T10;保守預勾的品質底線)。recall/態度條數=資訊訊號
    # (保守預勾天然犧牲 recall——漏勾由顧問成組反問接住;不用脆弱指標假 PASS/FAIL)。
    cur = report["curation"]
    passed = ((report["verify_pass_rate"] or 0) >= 0.8
              and report["progressed_turn_rate"] >= 0.8
              and report["indicators_total"] >= 1        # v4:收割是 P 的家,產不出 P=架構失效
              and cur["precision"] >= 0.8 and cur["declined_all_correct"])
    print(f"(informational) slot_keyword_accuracy={report['slot_keyword_accuracy']}"
          f" — keyword 量尺,語意評分待補")
    print(f"(v4 harvest) indicators_total={report['indicators_total']}"
          f" episodes={report['episodes_opened']}→{report['episodes_closed']}"
          f" harvest_landed={report['harvest_landed']}/{report['harvest_runs']}")
    print(f"(informational) curation_recall={cur['recall']}"
          f" ambiguous_untouched={cur['ambiguous_untouched']}"
          f" attitudes_count={report['attitudes']['count']}")
    print("GATE:", "PASS" if passed else "FAIL")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
