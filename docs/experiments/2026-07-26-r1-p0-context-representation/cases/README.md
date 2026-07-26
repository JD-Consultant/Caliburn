# Case records

本目錄在執行前放置六個固定 JSON case。每個 case 同時包含 raw、structured、hybrid 三種 paired
Context；三者必須來自同一 transcript，不得額外替某個 arm 補答案。

## Case JSON 格式

```json
{
  "case_id": "CR-01-tools-not-tasks",
  "case_family_id": "CR-01",
  "source_type": "constructed_edge",
  "title": "工具不得升格為工作",
  "primary_risk": "員工提到 Java、Python 與 HTML，但它們只是完成工作的手段",
  "applicable_critical_checks": [
    "C1_TOOL_BOUNDARY",
    "C6_SOURCE_FIDELITY"
  ],
  "transcript": [
    {
      "source_id": "turn-001",
      "role": "consultant",
      "text": "請描述最近一次完成這項工作的過程。"
    },
    {
      "source_id": "turn-002",
      "role": "employee",
      "text": "案例正式內容會在執行前寫入。"
    }
  ],
  "structured_context": {
    "claims": [
      {
        "claim_id": "claim-001",
        "statement": "案例正式結構化內容會在執行前寫入。",
        "actor": "employee",
        "time_scope": "current",
        "responsibility": "unknown",
        "candidate_kind": "unmapped",
        "source_ids": ["turn-002"],
        "qualifiers": []
      }
    ],
    "corrections": [],
    "unresolved": []
  },
  "hybrid_source_ids": ["turn-002"],
  "adjudication": {
    "must_retain_tasks": [],
    "must_not_create_tasks_from": ["Java", "Python", "HTML"],
    "allowed_task_variants": [],
    "required_uncertainties": [],
    "notes": "正式裁決在 trial 前固定，不傳給受測 subagent。"
  }
}
```

上例只定義格式，`turn-002`、claim 與 adjudication 的示意文字不得直接拿去跑 trial。正式案例建立後，
不得保留「正式內容會在執行前寫入」等模板文字。

## Context 組裝

- `raw_only`：只傳 `transcript`。
- `structured_only`：只傳 `structured_context`。
- `hybrid`：傳 `structured_context`、`hybrid_source_ids` 指向的逐字 turns，以及 transcript 最後一個
  employee turn；不得附 `adjudication`。

三種 payload 都要保留原始 `source_id`，讓 `source_ids` 可驗證。

## 凍結規則

- 六個案例一次完成後才開始 trial。
- `adjudication` 不會傳給受測 subagent。
- 若 transcript、structured context 或 adjudication 有任何實質修改，既有 trial 不得混入新版結果。
- P0 不沿用舊 Evidence schema、gold、loader、grader 名稱或 suite hash；舊案例只能提供語意陷阱靈感。
