# OCS 職能文件 JSON 結構

> **v3 註記**：代碼規則（T/P/O/K/S/A）仍對應 v3 `build_doc` 產出。差異：v3 OCU 分組改用 **catalog `unit_id`/`unit_title`**（非舊 `graph_state.responsibility_groups`）；K/S 巢狀在每個任務下、A 為全域（對齊 OCS 職能基準，見 `superpowers/specs/2026-06-18-ksa-flow-redesign-design.md`）。

## 代碼規則

| 代碼類型 | 格式 | 說明 |
|---------|------|------|
| 職能單元 (OCU) | `T1`, `T2` | 主要職責，每個職稱 2-4 個 |
| 工作任務 | `T1.1`, `T1.2`, `T2.1` | 隸屬於職能單元 |
| 行為指標 | `P1.1.1`, `P1.1.2` | P = Performance |
| 工作產出 | `O1.1.1`, `O1.1.2` | O = Output |
| 知識 | `K01`, `K02` | 文件層級去重，不重複 |
| 技能 | `S01`, `S02` | 文件層級去重，不重複 |
| 態度 | `A01`, `A02` | A = Attitude |

K/S 去重邏輯：以 `name` 為 key，同一份文件內相同名稱只保留一個代碼，所有任務引用同一個代碼物件。
OCU 主要職責優先使用使用者確認過的 `graph_state.responsibility_groups`；若沒有分組資料，才由 OCS builder 依任務內容 fallback 分組。

---

## 頂層結構

```json
{
  "version_info": { ... },
  "ocs_profile":  { ... },
  "ocs_content":  { ... },
  "ocs_attitude": { ... }
}
```

---

## `version_info`

```json
{
  "versions": [
    { "status": "最新版本", "ocs_code": "DAT-001" }
  ]
}
```

---

## `ocs_profile`

```json
{
  "ocs_code": "DAT-001",
  "ocs_name": { "occupation_name": "資料工程師" },
  "job_description": "負責 ETL pipeline 開發與維護...",
  "ocs_level": 3,
  "notes": "學歷要求：大學以上；工作年資：3年以上...",
  "category": {
    "occ_code":       "2522",
    "job_categories": [{ "name": "資訊服務業", "code": "J" }],
    "occupations":    [{ "name": "資料庫管理師", "code": "2522" }],
    "industries":     [{ "name": "電腦及電子產品製造業" }]
  }
}
```

- `ocs_code` 規則：`{職稱前3碼英文大寫}-{iCAP末3碼}`，例如 `DAT-001`；若無 iCAP 命中則 `DAT-001`
- `notes`：從 iCAP `notes_and_appendix.requirements[].content` 彙整
- `occ_code`：優先取 `occupations[0].code`，否則從 `ocs_code` 分割取第一段

---

## `ocs_content`

```json
{
  "ocu_units": [
    {
      "ocu_code": "T1",
      "ocu_name": "資料工程與整合",
      "tasks": [
        {
          "task_codes": [
            { "code": "T1.1", "name": "設計 ETL Pipeline" }
          ],
          "evidence_refs": [
            { "source_type": "interview_quote", "evidence_kind": "direct", "quote": "我每天要從 ERP 抓資料然後跑合併腳本" }
          ],
          "display_label": "[訪談確認]",
          "display_labels": ["[訪談確認]"],
          "competency_blocks": [
            {
              "competency_level": 3,
              "indicators": [
                {
                  "code": "P1.1.1",
                  "text": "在每月月底，為了提供管理決策依據，與 DS 協作...",
                  "evidence_refs": [
                    { "source_type": "star_slot", "evidence_kind": "direct", "field": "S", "value": "每月月底彙整業績時" },
                    { "source_type": "five_w2h_field", "evidence_kind": "structured", "field": "workflow_steps", "value": ["從 ERP 匯出", "清洗合併"] }
                  ],
                  "display_label": "[訪談確認]",
                  "display_labels": ["[訪談確認]"]
                }
              ],
              "outputs": [
                { "code": "O1.1.1", "name": "ETL 排程腳本", "display_label": "[AI整理]", "display_labels": ["[AI整理]"] },
                { "code": "O1.1.2", "name": "資料品質報告", "display_label": "[AI整理]", "display_labels": ["[AI整理]"] }
              ],
              "knowledge": [
                { "code": "K01", "name": "SQL 查詢語法", "source_type": "icap_official", "icap_ref": "K-INF-001", "display_label": "[iCAP參考]", "display_labels": ["[iCAP參考]"] },
                { "code": "K02", "name": "Airflow 排程原理", "source_type": "company_defined", "display_label": "[AI整理]", "display_labels": ["[AI整理]"] }
              ],
              "skills": [
                { "code": "S01", "name": "Python 資料處理", "source_type": "company_defined", "display_label": "[AI整理]", "display_labels": ["[AI整理]"] }
              ]
            }
          ]
        }
      ]
    }
  ]
}
```

### `source_type` 值

| 值 | 說明 |
|----|------|
| `icap_official` | iCAP 官方標準內容，含 `icap_ref` 代碼 |
| `company_defined` | 企業自定義，無 `icap_ref` |

### `tasks[].details` — 任務客製細項(2026-07-05 新增;訪談引擎 v1)

每個 task 物件可帶 optional `details`(**權威 = `packages/ocs-contract/schema/ocs-document.schema.json`
的 `TaskDetails`**;ADR 0023、spec `2026-07-05-interview-engine-v1-spec.md` §1):11 欄全 optional——
`frequency`(頻率)、`time_share_pct`(工作比重 %,0–100)、`duration`(單次耗時)、`volume`(數量批次)、
`trigger`(觸發)、`inputs`(準備材料)、`tools`(工具系統)、`collaborators`(協作對象)、
`wait_points`(等待瓶頸)、`exceptions`(例外處理)、`standards`(完成標準)。
**OCS 官方來源沒有這些**——由訪談引擎產生(pdf-to-json 產出一律無/`null`);
溯源(員工原話 quote)不落文件,住訪談 session(稽核用)。

---

## `ocs_attitude`

```json
{
  "attitudes": [
    { "code": "A01", "name": "主動積極", "source_type": "icap_official", "icap_ref": "A-GEN-001" },
    { "code": "A02", "name": "跨部門協作", "source_type": "company_defined" }
  ]
}
```

---

## Pydantic 模型（`app/schemas/ocs.py`）

```
OcsDocument
  ├── version_info: OcsVersionInfo
  │     └── versions: list[OcsVersion]
  ├── ocs_profile: OcsProfile                              ← Stage 4 #16 補齊
  │     ├── ocs_code / ocs_name / job_description / ocs_level
  │     ├── notes: str | None                             ← Stage 4 #16 新增
  │     └── category: OcsCategory
  │           ├── occ_code: str                          ← Stage 4 #16 新增
  │           ├── job_categories / industries
  │           └── occupations: list[{name, code}]        ← Stage 4 #16 新增 code 欄
  ├── ocs_content: OcsContent
  │     └── ocu_units: list[OcsUnit]
  │           └── tasks: list[OcsTask]
  │                 ├── task_codes: list[OcsTaskCode]
  │                 ├── evidence_refs: list[EvidenceRef]  ← P0 新增；Stage 4 #16 強型別
  │                 ├── display_label: str | None
  │                 ├── display_labels: list[str]
  │                 └── competency_blocks: list[OcsCompetencyBlock]
  │                       ├── indicators: list[OcsIndicator]
  │                       │     ├── code / text
  │                       │     ├── evidence_refs: list[EvidenceRef]
  │                       │     ├── display_label / display_labels
  │                       │     ├── quality_score: float | None    ← Stage 4 #16 新增
  │                       │     └── quality_status: str | None     ← Stage 4 #16 新增
  │                       ├── outputs: list[OcsOutput]
  │                       │     ├── code / name
  │                       │     ├── display_label / display_labels
  │                       │     ├── quality_score: float | None    ← Stage 4 #16 新增
  │                       │     └── quality_status: str | None     ← Stage 4 #16 新增
  │                       ├── knowledge: list[OcsKnowledge]
  │                       │     ├── code / name / source_type / icap_ref
  │                       │     └── display_label / display_labels
  │                       └── skills: list[OcsSkill]               ← 同上
  └── ocs_attitude: OcsAttitudeSection
        └── attitudes: list[OcsAttitude]
              ├── code / name / source_type / icap_ref
              └── display_label / display_labels

# 匯出專用 Schema（Stage 4 #16 新增）
EnrichedExportJson
  ├── ocs_document: OcsDocument
  ├── evidence_refs: list[EvidenceRef]      # 展開所有 task / indicator 的 evidence
  ├── icap_reference_pack: IcapReferencePack
  │     ├── icap_mode / icap_hit / candidates
  └── quality_scores: dict[str, TaskQualityScore]  # { task_name: {quality_score, quality_status} }
```

---

## 已知問題與改善方向（Review 結論）

> **P0 問題已於 2026-05-20 全部解決。** 以下保留原始問題描述與解決方式供參考。

### ✅ evidence_refs — 來源可追溯（P0 已解決）

**已實作**：每個 task / indicator 加入結構化 `evidence_refs`，含 `source_type`（`interview_quote` / `star_slot` / `five_w2h_field` / `icap_reference` / `manual_edit`）與 `evidence_kind`（`direct` / `structured` / `inferred`）。

### ✅ display_label — 來源標籤（P0 已解決）

**已實作**：每個 task / indicator / output / K/S/A / attitude 加入 `display_label`（主標籤）與 `display_labels`（完整標籤列表）。

| 標籤 | 優先序 | 條件 |
|------|--------|------|
| `[待確認]` | 最高 | quality_status = force_accepted，或無任何 evidence |
| `[訪談確認]` | 2 | 有 interview_quote / star_slot 且 quality_score >= 0.70 |
| `[iCAP參考]` | 3 | 有 icap_reference 或 source_type = icap_official |
| `[AI整理]` | 最低 | 僅有 five_w2h_field 或無 evidence |

### ✅ indicator_quality_score（P0 已解決）

**已實作**：LLM 同 call 自評 7 維度（has_situation / has_purpose / has_collaborators / has_tools / has_action / has_output / has_standard），score = hits/7。threshold = 0.60，低於門檻退回補問（最多 1 次），第二次強制接受標為 `[待確認]`。

### ✅ document freeze / version（Bug #3 已解決）

**已實作**：`POST /documents/{profile_id}/freeze` 直接從 `graph_state["ocs_document"]` 建立 `DocumentVersion`，不依賴 export 先行；設 `stage = "preview"` 作為 terminal state。

### ✅ Pydantic schema 補齊（Stage 4 #16 已完成）

`app/schemas/ocs.py` 已補齊：`EvidenceRef`、`notes`、`occ_code`、`quality_score`、`quality_status`、`EnrichedExportJson`、`IcapReferencePack`、`TaskQualityScore`。
