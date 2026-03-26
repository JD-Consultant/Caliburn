# jd-pdf-to-json

OCS/iCAP PDF 轉換成結構化 JSON 的資料規範文件。

## Quick Start

### 1) 安裝

```bash
uv sync
```

### 2) 單檔轉換

```bash
uv run python -m jd_pdf_to_json.cli convert path\to\input.pdf -o path\to\output.json
```

### 3) 批次轉換

```bash
uv run python -m jd_pdf_to_json.cli batch path\to\pdf_folder -o path\to\json_folder
```

## CLI 使用方法

### convert

將單一 PDF 轉成 JSON。

```bash
uv run python -m jd_pdf_to_json.cli convert <pdf_path> -o <output_path>
```

參數：

- `pdf_path`：輸入 PDF 檔案路徑。
- `-o, --output`：輸出 JSON 路徑（不指定時，預設與 PDF 同名）。
- `--validate/--no-validate`：是否啟用 schema 驗證（預設啟用）。

### batch

將資料夾內所有 PDF 批次轉成 JSON。

```bash
uv run python -m jd_pdf_to_json.cli batch <input_dir> -o <output_dir>
```

參數：

- `input_dir`：PDF 來源資料夾。
- `-o, --output`：JSON 輸出資料夾。
- `--validate/--no-validate`：是否啟用 schema 驗證（預設啟用）。

### validate

驗證 JSON 檔案是否符合專案 schema。

```bash
uv run python -m jd_pdf_to_json.cli validate <json_path>
```

參數：

- `json_path`：待驗證的 JSON 檔案路徑。

## 1. Purpose
本專案定義可重複、可驗證、可擴充的 JSON 輸出格式，用於將職能基準（OCS）PDF 轉為結構化資料，支援：

- 資料交換（Data Exchange）
- 搜尋與檢索（Search/RAG）
- 後續分析（Analytics）
- 規則驗證（Validation）

## 2. Scope
本規範適用於 iCAP 類型職能基準文件，包含以下五大區塊：

1. `version_info`
2. `ocs_profile`
3. `ocs_content`
4. `ocs_attitude`
5. `notes_and_appendix`

## 3. Design Principles

- 固定鍵名：所有已定義欄位必須存在，不可省略。
- 可空值：無資料時使用 `null`（物件欄位）或空陣列 `[]`（集合欄位）。
- 結構優先：避免將多筆資料串成單一字串。
- 代碼與名稱並存：`K/S/A/O/P/T` 等代碼需保留，並附可讀名稱。
- 向後相容：新增欄位不得破壞既有欄位語意。

## 4. Terminology

- OCS: Occupational Competency Standard（職能基準）
- OCU: Occupational Competency Unit（職能單元）
- K: Knowledge（知識）
- S: Skills（技能）
- A: Attitude（態度）
- O: Output（工作產出）
- P: Behavioral Indicator（行為指標）
- T: Task / Unit Code（任務或職責代碼）

## 5. Top-level Schema

```json
{
  "version_info": { "versions": [] },
  "ocs_profile": {},
  "ocs_content": { "ocu_units": [] },
  "ocs_attitude": { "attitudes": [] },
  "notes_and_appendix": { "requirements": [] }
}
```

## 6. Field Contract

### 6.1 version_info

```json
"version_info": {
  "versions": [
    {
      "version": "V3",
      "ocs_code": "FSI3311-001v3",
      "ocs_name": "證券業-受託買賣業務人員",
      "status": "最新版本",
      "update_note": "略",
      "update_date": "2025/11/24"
    }
  ]
}
```

規則：

- `versions` 依版本新到舊排序（建議）。
- 日期格式使用 `YYYY/MM/DD`。
- 無更新說明時可用 `"略"` 或 `null`，但鍵名需存在。

### 6.2 ocs_profile

```json
"ocs_profile": {
  "ocs_code": "FSI3311-001v3",
  "ocs_name": {
    "job_category_name": null,
    "occupation_name": "證券業-受託買賣業務人員"
  },
  "category": {
    "job_categories": [{ "name": "金融財務／證券及投資", "code": "FSI" }],
    "occupations": [{ "name": "證券金融交易員及經紀人", "code": "3311" }],
    "industries": [{ "name": "金融及保險業／證券期貨及金融輔助業（證券業）", "code": "K6611" }]
  },
  "job_description": "...",
  "ocs_level": 3
}
```

規則：

- `ocs_name.job_category_name` 與 `ocs_name.occupation_name` 兩鍵都必須存在。
- 若來源只給職業名稱，`job_category_name` 設為 `null`。
- `category` 使用陣列，支援多職類、多職業、多行業（例如 AIoT 職能）。

### 6.3 ocs_content

```json
"ocs_content": {
  "ocu_units": [
    {
      "ocu_code": "T1",
      "ocu_name": "業務開發與客戶管理",
      "tasks": [
        {
          "task_code": "T1.1",
          "task_name": "業務開發",
          "outputs": [
            { "output_code": "O1.1.1", "output_name": "客戶聯繫與拜訪紀錄" }
          ],
          "behavioral_indicators": [
            {
              "indicator_code": "P1.1.1",
              "indicator_text": "..."
            }
          ],
          "competency_level": 2,
          "knowledge_k": [
            { "code": "K05", "name": "法律/法規" }
          ],
          "skills_s": [
            { "code": "S01", "name": "人脈拓展" }
          ]
        }
      ]
    }
  ]
}
```

規則：

- `knowledge_k` 與 `skills_s` 必須為物件陣列，元素格式固定：`{ "code", "name" }`。
- 禁止只存代碼字串陣列（例如 `["K01", "K02"]`）。
- 若同一任務內行為指標具不同級別，可在指標上加欄位：

```json
{
  "indicator_code": "P4.1.3",
  "indicator_text": "...",
  "competency_level": 5
}
```

- 若任務層級與指標層級同值，可省略指標層級欄位。

### 6.4 ocs_attitude

```json
"ocs_attitude": {
  "attitudes": [
    {
      "attitude_code": "A01",
      "attitude_name": "主動積極",
      "attitude_description": null
    }
  ]
}
```

規則：

- `attitude_description` 永遠保留鍵名。
- 來源有描述時填完整文字；無描述時填 `null`。

### 6.5 notes_and_appendix

```json
"notes_and_appendix": {
  "requirements": [
    {
      "category": "建議擔任此職類／職業之學歷／經歷／或能力條件",
      "content": "無",
      "notes": null
    }
  ]
}
```

規則：

- `requirements` 為陣列，支援多段補充。
- `notes` 為可選補註欄位；建議保留，無值時 `null`。

## 7. Validation Checklist

每份輸出 JSON 在交付前應至少通過以下檢核：

- Top-level 五區塊鍵名完整存在。
- `ocs_profile.category` 三類別皆為陣列型別。
- `knowledge_k`/`skills_s` 元素都具備 `code` 與 `name`。
- `ocs_attitude.attitudes[*].attitude_description` 不可缺鍵。
- `version_info.versions` 存在且每筆具 `version`、`ocs_code`、`status`。
- 所有代碼欄位不應混入無結構長字串拼接。

## 8. Backward Compatibility

- 允許新增欄位（非破壞性）。
- 不允許移除既有欄位或改變既有欄位型別。
- 若來源資料品質不足，使用 `null` / `[]` 保持契約穩定。

## 9. Minimal Complete Example

```json
{
  "version_info": { "versions": [] },
  "ocs_profile": {
    "ocs_code": "THM9112-001v3",
    "ocs_name": {
      "job_category_name": null,
      "occupation_name": "房務人員"
    },
    "category": {
      "job_categories": [{ "name": "休閒與觀光旅遊／旅館管理", "code": "THM" }],
      "occupations": [{ "name": "辦公室、旅館及類似場所清潔工及幫工", "code": "9112" }],
      "industries": [{ "name": "住宿及餐飲業／住宿業", "code": "I55" }]
    },
    "job_description": "...",
    "ocs_level": 3
  },
  "ocs_content": { "ocu_units": [] },
  "ocs_attitude": { "attitudes": [] },
  "notes_and_appendix": { "requirements": [] }
}
```

## 10. Recommended Naming Conventions

- 檔名：`<職能基準名稱>-職能基準.json`
- 編碼：UTF-8
- 鍵名：`snake_case`
- 語系：內容可為繁中，鍵名統一英文

## 11. Change Policy

- 若欄位契約有變更，需更新本文件並標註版本。
- 建議以語意版本控制（例如 `schema_version: 1.1.0`）管理規範演進。
