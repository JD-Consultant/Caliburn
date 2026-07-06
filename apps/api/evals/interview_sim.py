"""模擬受訪者回歸(T14;plan 2026-07-05;手動閘門,家規同 run_eval.py)。

    cd apps/api && PYTHONUTF8=1 uv run python evals/interview_sim.py [--max-turns 16]

形狀:**純智力迴圈,不碰 DB**(記憶體 doc/counters/focus + 真顧問 LLM(select_schema)
+ 真 executor)——DB/route 已由 tests/ 蓋;這裡量的是「問得好不好」。
模擬員工 = cheap LLM 綁**事實表**(黃金範本樣張王OO;Sim2Real 坑對策:只准照表答,
表上沒有就說不知道)。指標:覆蓋達標回合數 / 槽值關鍵字正確率 / quote 驗證率。
結果留 docs/specs/ 校準紀錄;門檻改 = 重跑本腳本,不改碼。
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.adapters.llm_openrouter import OpenRouterLlm  # noqa: E402
from app.interview import executor as ex  # noqa: E402
from app.interview.commands import TurnOutput, turn_output_schema  # noqa: E402
from app.interview.context import build_prompt  # noqa: E402
from app.interview.slots import gate_missing  # noqa: E402

TASK_PATH = "ocs_content.ocu_units.u1.tasks.t1"

# 事實表 = 黃金範本樣張 §4.2(王OO,任務 2.2 手動測試+版本回歸)
FACTS = {
    "frequency": ("每天會零星測,每兩週上線前會密集跑兩天回歸", ["兩週", "雙週"]),
    "time_share_pct": ("大概占我四分之一的時間", ["25"]),
    "duration": ("密集的那次大概兩天", ["兩天", "2 天", "2天"]),
    "volume": ("回歸套件大概三百多條,自動化跑兩百、手動一百", ["300", "三百"]),
    "trigger": ("每天 build 好 Slack bot 會通知,我就開始測", ["build", "通知", "Slack"]),
    "inputs": ("要有回歸清單、測試環境的帳號,還有這版改了什麼的說明", ["回歸清單", "帳號"]),
    "tools": ("staging 環境、Postman,自動化那塊是我們自己寫的 pytest 腳本", ["staging", "Postman", "pytest"]),
    "collaborators": ("有缺陷就跟開發來回,環境掛了找 DevOps", ["開發", "DevOps"]),
    "wait_points": ("環境只有一套,被開發佔住就要排隊,平均等一兩個小時", ["等", "排隊", "小時"]),
    "exceptions": ("遇到擋版的 blocker 就立刻通報組長跟開發 Lead,當天修完重測", ["blocker", "通報", "擋版"]),
    "standards": ("回歸要百分之百跑完、沒有未解的 blocker,我簽核了才放行", ["100", "百分之百", "簽核"]),
}

EMPLOYEE_SYSTEM = """你在扮演一位軟體測試工程師「王OO」接受職務說明書訪談。
你【只能】根據下面的事實表回答;事實表沒有的就說「這我不確定」。
口語化、像聊天,一次回答一到三句,不要主動把整張表倒出來。

事實表(關於「手動測試+版本回歸」這個任務):
""" + "\n".join(f"- {k}:{v[0]}" for k, v in FACTS.items())


def _doc() -> dict:
    return {
        "ocs_profile": {"ocs_code": "ISD2519-002v2", "job_description": ""},
        "ocs_content": {"ocu_units": [{
            "_uid": "u1", "ocu_name": "軟體測試實作與執行",
            "tasks": [{"_tid": "t1",
                       "task_codes": [{"code": "T2.2", "name": "測試執行(手動+版本回歸)"}],
                       "competency_blocks": [{"outputs": [{"code": "O2.2", "name": "測試事件報告"}]}]}],
        }]},
    }


def _score_slots(details: dict) -> tuple[int, int, list[str]]:
    hit, miss = 0, []
    for key, (_, keywords) in FACTS.items():
        v = str(details.get(key) or "")
        if v and any(kw in v for kw in keywords):
            hit += 1
        elif v:
            miss.append(f"{key}={v!r}(未含關鍵字 {keywords})")
    return hit, len(FACTS), miss


async def simulate(max_turns: int) -> dict:
    llm = OpenRouterLlm()
    doc = _doc()
    focus = {"task_path": TASK_PATH}
    counters: dict = {}
    transcript: list[tuple[str, str]] = []
    employee_texts: list[str] = []
    evidence_total = evidence_verified = 0
    question = "先跟我聊聊:版本回歸這件事你多久做一次?大概佔你多少時間?"
    turns_used = 0

    for i in range(max_turns):
        turns_used = i + 1
        # 模擬員工照事實表回答
        conv = "\n".join(f"{'顧問' if r == 'consultant' else '我'}:{t}" for r, t in transcript[-8:])
        answer = await llm.complete_text(
            EMPLOYEE_SYSTEM + f"\n\n最近對話:\n{conv}\n顧問剛問:{question}\n你的回答:",
            role="cheap")
        answer = (answer or "嗯…這我不確定").strip()
        transcript.append(("consultant", question))
        transcript.append(("employee", answer))
        employee_texts.append(answer)

        # 真顧問回合(select_schema + executor)
        prompt, choice_ids = build_prompt(
            doc=doc, phase="deep", focus=focus, counters=counters,
            recent_turns=transcript, user_text=answer)
        data = await llm.select_schema(prompt, turn_output_schema(choice_ids),
                                       schema_name="turn_output")
        turn = TurnOutput.model_validate(data)
        res = ex.apply(turn, doc=doc, human_touched=[], counters=counters,
                       focus=focus, employee_texts=employee_texts)
        if res.new_doc is not None:
            doc = res.new_doc
        for ev in res.evidence:
            evidence_total += 1
            evidence_verified += 1 if ev["verified"] else 0
        for k, v in res.counters_delta.items():
            counters[k] = v
        if res.skipped_add:
            focus["skipped"] = list(dict.fromkeys(
                (focus.get("skipped") or []) + res.skipped_add))
        if res.advanced_to:
            break
        question = ((res.question or {}).get("text")
                    or (res.widget or {}).get("question")
                    or "還有想補充的嗎?")

    task = ex.get_at(doc, TASK_PATH) or {}
    details = task.get("details") or {}
    missing = gate_missing(task)
    skipped = set((focus.get("skipped") or []))
    missing_after_skip = [m for m in missing
                          if f"{TASK_PATH}.details.{m}" not in skipped and m != "outputs"]
    hit, total, mismatches = _score_slots(details)
    return {
        "turns_used": turns_used,
        "coverage_cleared": not missing_after_skip,
        "missing_after_skip": missing_after_skip,
        "skipped": sorted(skipped),
        "slot_keyword_accuracy": round(hit / total, 2),
        "slot_mismatches": mismatches,
        "evidence_verified_rate": round(evidence_verified / evidence_total, 2)
        if evidence_total else None,
        "details_filled": {k: details.get(k) for k in FACTS if details.get(k)},
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--max-turns", type=int, default=16)
    args = ap.parse_args()
    if not os.getenv("OPENROUTER_API_KEY"):
        # .env 由 app.config 讀;這裡只提示 shell 環境沒有時的情況
        pass
    report = asyncio.run(simulate(args.max_turns))
    print(json.dumps(report, ensure_ascii=False, indent=2))
    # v0 閘門(校準紀錄 #1 後修數字):覆蓋達標 + 關鍵字正確率 ≥0.6 + 驗證率 ≥0.7
    passed = (report["coverage_cleared"]
              and report["slot_keyword_accuracy"] >= 0.6
              and (report["evidence_verified_rate"] or 0) >= 0.7)
    print("GATE:", "PASS ✅" if passed else "FAIL ❌")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
