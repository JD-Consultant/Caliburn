"""Eval 閘門（D20）：換 OpenRouter 模型前手動跑。deterministic-first。
  uv run python evals/run_eval.py     # 需 OPENROUTER_API_KEY（json_zhtw 類打真模型）
checks 邏輯見 evals/checks.py（已單測）。"""
from __future__ import annotations

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evals import checks  # noqa: E402


_DATA = os.path.join(os.path.dirname(__file__), "datasets", "json_zhtw.json")

# doc_structure 類已隨 app/authoring 退場(T12;ADR 0030)——結構驗證改由
# 契約 schema + verify 六查 + promptfoo 確定性斷言承擔。


async def _eval_json_zhtw(llm) -> dict:
    cases = json.load(open(_DATA, encoding="utf-8"))
    results = []
    for c in cases:
        text = await llm.complete_text(c["prompt"], role="cheap")
        ok_json = checks.is_valid_json(text)
        obj = json.loads(text) if ok_json else {}
        ok = ok_json and checks.has_keys(obj, c["keys"]) and checks.is_zh_tw(text)
        results.append({"name": c["name"], "ok": ok})
    return {"passed": all(r["ok"] for r in results), "cases": results}


async def run_all(llm=None) -> tuple[bool, dict]:
    if llm is None:
        from app.adapters.llm_openrouter import OpenRouterLlm
        llm = OpenRouterLlm()
    report = {
        "json_zhtw": await _eval_json_zhtw(llm),
    }
    passed = all(section["passed"] for section in report.values())
    return passed, report


def main() -> int:
    if not os.getenv("OPENROUTER_API_KEY"):
        print("✗ 需 OPENROUTER_API_KEY 才能跑 json_zhtw（真模型）類。")
    passed, report = asyncio.run(run_all())
    print(json.dumps(report, ensure_ascii=False, indent=2))
    print("GATE:", "PASS ✅" if passed else "FAIL ❌")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
