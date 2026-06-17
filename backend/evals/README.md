# Eval 閘門（Phase ⑤ / D20）

換 OpenRouter 模型前手動跑，確認便宜模型仍可靠：
    cd backend
    OPENROUTER_API_KEY=sk-or-... uv run python evals/run_eval.py

- **json_zhtw**：打真模型，驗嚴格 JSON + 必填 key + zh-TW（驗便宜模型）。
- **doc_structure**：deterministic，驗 build_doc 編碼/分組/K-S-A + 深問 quality_score。
- 深問語義品質的 LLM-judge：延後（見 decision-log D20）。
checks 純函式於 `evals/checks.py`，已被 `tests/test_eval_checks.py` 單測。
