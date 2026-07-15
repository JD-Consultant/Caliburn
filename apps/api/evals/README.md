# 訪談引擎 evals(T11;ADR 0030)

> **2026-07-15 邊界說明**：本目錄目前是 v3 的 regression／smoke 資產，不能單獨證明
> C1 Evidence-first 或任何新架構較好。現有單一 golden、simulated user、Source Score 0.8、
> 空輸出計分與「每回合恰好一問」的適用限制及修正計畫，見
> [`../../../docs/specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md`](../../../docs/specs/2026-07-15-c0-c1-interview-eval-experiment-plan.md)。

新架構實驗的 vendor-neutral foundation 位於 [`interview_v4/`](interview_v4/)：case/gold/run
contracts、只讀 session inventory/export、隱私預篩、content-free candidate metrics、deterministic
graders 與 isolated C0 runner。第一個 database session（資料擁有者已確認為測試資料）稽核見
[`interview_v4/reports/real-candidate-audit-2026-07-15.md`](interview_v4/reports/real-candidate-audit-2026-07-15.md)；
已提交的 `TEST-SYNTHETIC-SESSION-001` 可做靜態 claim eval；historical replay 仍缺 initial
fixtures，不能假造 C0 baseline。新 session 的 opt-in immutable capture 操作與限制見
[`interview_v4/README.md`](interview_v4/README.md)。

雙指標(Harvey 式):**Source Score(程式算)** + **Answer Score(rubric 裁判,Phase 2)**。

## 佈局
- `promptfooconfig.yaml` — 考卷:單回合 deterministic 斷言 + Simulated User 端到端
  (四種不合作 persona:話少/跑題/自誇灌水/矛盾)。
- `provider_turn.py` — promptfoo Python provider:包引擎一回合(打 http://127.0.0.1:8001)。
- `assertions/deterministic.py` — 確定性斷言:一問收尾/位置碼不可寫/結構不變量/Source Score≥0.8。
- `source_score.py` — 可溯源比率:分母=AI 寫入(`_pending`∪accepted 事件),
  分子=出處過 verify ②③ 者。單測:`tests/test_source_score.py`。
- `golden/<case_id>/` — 黃金題:`transcript.txt` + `reference.md`(顧問級成品)+
  `rubric.yaml`(二元 item+負分;Phase 2 llm-rubric 用)。
  **歷史 reference 是維護者／agent 依權威來源整理的 provisional 樣本，不是 domain-SME
  ground truth；只可做 migration、grader smoke 與待審 capability case。新的 semantic
  release gate 必須使用 claim-level gold，並依上列實驗計畫標示 domain review 狀態。**
- CI:`.github/workflows/evals.yml`(promptfoo-action;引擎/評測檔變更觸發,紅燈擋 merge)。

## 跑法
    npm run up                     # api:8001 起
    # 建測試 profile 後:
    EVAL_PROFILE_ID=<uuid> npx promptfoo eval -c apps/api/evals/promptfooconfig.yaml

## 舊件(v1;換模型手動閘門,保留)
- `run_eval.py` + `checks.py` + `datasets/`:json_zhtw / doc_structure(打真模型/確定性,
  換 OpenRouter 模型前手動跑:`OPENROUTER_API_KEY=… uv run python evals/run_eval.py`)。
- `interview_sim.py`:模擬受訪者回歸(裁剪/深聊/態度三段;純智力迴圈不碰 DB)。
