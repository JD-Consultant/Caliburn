# 訪談引擎 evals(T11;ADR 0030)

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
  **SME gate(2026-07-13 改制:維護者非 JD 領域專家):由 agent 以權威來源
  自審定案,審查紀錄留 docs/specs/;reference 過 rubric 必須滿分(驗 grader)。**
- CI:`.github/workflows/evals.yml`(promptfoo-action;引擎/評測檔變更觸發,紅燈擋 merge)。

## 跑法
    npm run up                     # api:8001 起
    # 建測試 profile 後:
    EVAL_PROFILE_ID=<uuid> npx promptfoo eval -c apps/api/evals/promptfooconfig.yaml

## 舊件(v1;換模型手動閘門,保留)
- `run_eval.py` + `checks.py` + `datasets/`:json_zhtw / doc_structure(打真模型/確定性,
  換 OpenRouter 模型前手動跑:`OPENROUTER_API_KEY=… uv run python evals/run_eval.py`)。
- `interview_sim.py`:模擬受訪者回歸(裁剪/深聊/態度三段;純智力迴圈不碰 DB)。
