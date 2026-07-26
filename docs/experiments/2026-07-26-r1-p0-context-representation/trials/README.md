# Trial records

每個受測 subagent 產生一個 JSON record。這是可追溯實驗資料，不是 production Capture 契約。

## 檔名

```text
<case-family-id>__<arm-id>__sol__t0N.json
```

`t0N` 是同一 case × arm 的重複序號。第 1 輪全部為 `t01`；
第 2 輪只有 CR-01／CR-04／CR-05 的三個產品 arm 增加 `t02`、`t03`。

## JSON 格式

```json
{
  "trial_id": "CR-01__raw-only__sol__t01",
  "experiment_id": "2026-07-26-r1-p0-context-representation",
  "experiment_revision": 1,
  "round": 1,
  "repeat_index": 1,
  "case_id": "CR-01-tools-not-tasks",
  "case_family_id": "CR-01",
  "arm_id": "raw_only",
  "requested_subagent_model": "gpt-5.6-sol",
  "reasoning_effort": "high",
  "fork_context": false,
  "agent_id": "實際 spawn 後填入的 opaque ID",
  "started_at": "實際 ISO 8601 時間",
  "completed_at": "實際 ISO 8601 時間",
  "subject_request": "實際傳給 subagent 的完整單一 request，包含共同指令與 INPUT_CONTEXT",
  "visible_input_char_count": 0,
  "span_duplicated_char_count": 0,
  "raw_final_output": "subagent 最終回覆原文，不修補 fenced JSON 或其他格式錯誤",
  "output_char_count": 0,
  "parse_result": {
    "status": "valid_json_object",
    "error": null,
    "parsed_output": {
      "tasks": [],
      "excluded_mentions": [],
      "uncertainties": [],
      "next_question": null
    }
  },
  "evaluation": {
    "review_blind_label": "實際評審前產生的匿名標籤",
    "reviewer": "codex-auto-review",
    "reviewer_calibrated": true,
    "critical_checks": {
      "C1_TOOL_BOUNDARY": "pass",
      "C6_SOURCE_FIDELITY": "unknown"
    },
    "critical_pass": null,
    "owner_resolution": {
      "C6_SOURCE_FIDELITY": "實際人工裁決結果與一句理由"
    },
    "secondary_scores": {
      "S1_TASK_STATEMENT": 0,
      "S2_NEXT_QUESTION": 0,
      "S3_UNSUPPORTED_CLAIMS": 0,
      "S4_CONTEXT_EFFICIENCY": 0
    },
    "reviewer_notes": []
  },
  "platform_limitations": [
    "hidden_system_instructions_not_captured",
    "project_instructions_possibly_injected_not_observable",
    "private_reasoning_not_captured",
    "tool_execution_trace_not_available",
    "requested_model_not_openrouter_shipping_model"
  ]
}
```

上例是欄位格式，不是有效實驗結果。正式 trial 必須：

- 將所有「實際……」示意值換成真值；
- `visible_input_char_count` 與 `output_char_count` 由實際字串計算；
  `span_duplicated_char_count` 記錄重貼相關片段所增加的字元（`raw_only`、`structured_only` 為 0），
  讓 `S4` 不會把重複計入的字元讀成效率差異；
- 原始輸出永遠保留；解析失敗不得靜默修復；
- 只寫適用的 critical checks；
- 三值判定：`pass` / `fail` / `unknown`。出現任何 `unknown` 時 `critical_pass` 先填 `null`，
  由 owner 在 `owner_resolution` 裁決後才定案；
- reviewer 在不知道 arm 名稱、且同時看同一 case 四份匿名輸出的狀態下完成 `C*` 與 `S1`–`S3`，
  解盲後才評 `S4`；
- `reviewer_calibrated` 記錄該裁決是否在 rubric §4.2 的人工校準之後產生；
- 不保存或推測 chain-of-thought。

## Parse status

允許值：

- `valid_json_object`
- `invalid_json`
- `non_object_root`
- `missing_required_field`
- `invalid_field_type`
- `cited_claim_id`（輸出引用了 `claim-*` 而非 `turn-*`，違反共同指令；保留原樣並在報告標示，
  因為它同時是解盲風險）

格式失敗要保存完整 `raw_final_output`，並在報告中與 Task 語意品質分開呈現。
