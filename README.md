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

`ocu_units` 為主要職責（T1、T2…）的容器。每個單元下有 `tasks` 陣列，每個 task 條目以 `task_codes` 陣列識別一或多個工作任務代碼，並持有一至多個 `competency_blocks`。

#### 6.3.1 Task 條目的定義

一個 `tasks[]` 條目代表 **PDF 表格中共用同一組 competency blocks 的工作任務集合**。

- **大多數情況**：一格一個 T code → `task_codes` 長度為 1。
- **同格多 T code**：PDF 工作任務欄同一格包含 T1.1、T1.2 等多個代碼，且共用相同的 O/P/K/S → `task_codes` 長度 > 1，對應一個 task 條目。

`task_codes` 中每個元素包含：
- `code`：T code，如 `"T1.1"`
- `name`：該 T code 的工作任務名稱

#### 6.3.2 Block 分界規則

從 PDF 表格提取時，**同時滿足以下兩個條件**才視為新 block 的開始：

1. **出現新的 O-code**（工作產出欄有明確的 `O` 代碼）OR **`competency_level` 改變**（職能級別欄位非空且與前一個 block 不同）
2. **AND 同列有 K/S codes**（職能內涵欄位非空）

任何不符合上述條件的資料列（無論是否含有新 P-code 或新 O 名稱文字）均視為**同一 block 的延續**，其 P / O / K / S 全部 append 進前一個 block。

#### 6.3.3 常見 PDF 版型對應

| PDF 版型 | 特徵 | 結果 |
|---------|------|------|
| 每列各自有 O + P + K/S（如 T6.3） | 每列有 O-code 且有 K/S | 每列 = 一個 block |
| 同 task 多 P，K/S 只在第一列（如 T2.2、T3.3） | 後續列無 K/S | 全部 P 同一個 block |
| 同 task 多 P，K/S 只在第一列，但多個 O-code（如 T1.2） | 後續列有 O-code 但無 K/S | 全部 O + P 同一個 block |
| 同 task 一個 O，多個 P，各自有 level 和 K/S（如 T4.1） | 後續列 level 改變且有 K/S | 每個 level = 一個 block；O 重複宣告 |
| **同格多 T code**（如 T1.1+T1.2 同一格） | 工作任務欄含多個 T code，共用 K/S | 一個 task 條目，`task_codes` 長度 > 1 |
| **跨頁**（如 T1.3、T2.1） | 次頁無 O-code（O 名稱跨頁截斷）、無 level | 全部 append 到同一 block |

#### 6.3.4 跨頁處理

當 PDF 表格跨頁時，次頁通常：
- 工作任務（T）欄位空白
- 工作產出欄只剩 O 名稱的後半段文字（無 `O` 代碼前綴）
- 職能級別空白

此情況不滿足分界條件，次頁的 P / K / S 全部 append 進前一個 block，O 名稱後半段文字接續拼入前一個 output 的 `name`。

#### 6.3.5 JSON 格式範例

**一般情況（單一 T code）：**

```json
"ocs_content": {
  "ocu_units": [
    {
      "ocu_code": "T1",
      "ocu_name": "研發創意",
      "tasks": [
        {
          "task_codes": [
            {"code": "T1.1", "name": "研發劇本與概念"}
          ],
          "competency_blocks": [
            {
              "competency_level": 3,
              "indicators": [
                {"code": "P1.1.1", "text": "參與設計定檔會議"},
                {"code": "P1.1.2", "text": "彙整素材並確認需求"}
              ],
              "outputs": [
                {"code": "O1.1.1", "name": "建議舞台設計構思"},
                {"code": "O1.1.2", "name": "製作時程表"}
              ],
              "knowledge": [{"code": "K01", "name": "舞台技術"}],
              "skills": [{"code": "S01", "name": "排程管理"}]
            },
            {
              "competency_level": 4,
              "indicators": [
                {"code": "P1.1.3", "text": "完成場地評估報告"},
                {"code": "P1.1.4", "text": "確認人力需求"}
              ],
              "outputs": [
                {"code": "O1.1.3", "name": "執行檢核清單"}
              ],
              "knowledge": [{"code": "K02", "name": "場地規劃"}],
              "skills": [{"code": "S02", "name": "場務協調"}]
            }
          ]
        }
      ]
    }
  ]
}
```

**同格多 T code（task_codes 長度 > 1）：**

```json
{
  "task_codes": [
    {"code": "T1.1", "name": "分析市場/客戶需求"},
    {"code": "T1.2", "name": "評估現有技術能力"}
  ],
  "competency_blocks": [
    {
      "competency_level": 4,
      "indicators": [
        {"code": "P1.1.1", "text": "能夠善用資訊工具快速完成市場產品分析"},
        {"code": "P1.2.1", "text": "評估在不同應用環境下各種設計參數的可行性"}
      ],
      "outputs": [
        {"code": "O1.1", "name": "工具機產業調查分析報告"}
      ],
      "knowledge": [{"code": "K01", "name": "工具機產業未來發展、應用趨勢及市場分析"}],
      "skills": [{"code": "S01", "name": "基本統計及計算能力"}]
    }
  ]
}
```

#### 6.3.6 欄位規則

- `task_codes` 為必填陣列，至少一個元素；每個元素包含 `code`（T code 字串）與 `name`（任務名稱字串）。
- `competency_blocks` 為必填陣列，至少包含一個 block。
- `indicators` 為必填陣列；一個 block 可包含多個 P-code。
- `outputs` 為可選陣列；無 O 時為空陣列 `[]`。
- `knowledge` 與 `skills` 為必填陣列，元素包含 `code` 與 `name`。
- 若同一 task 中某個 O 在多個 block 出現（例如 T4.1 的 O 跨 level），允許重複宣告。
- `indicators[*].text` 若跨行或分段，保留完整內容，不壓縮為代碼字串。
- `competency_level` 為整數或 `null`；無級別資料時填 `null`。

建議理解方式：

- `T`（ocu_unit）= 主要職責容器
- `tasks[]` 條目 = PDF 表格中共用同一組 competency blocks 的工作任務群
- `task_codes[]` = 該群內所有 T code 與名稱；通常長度為 1，同格多 T code 時 > 1
- `competency_block` = 一組 P/O/K/S 的能力切片，由 K/S 是否出現新值作為分界訊號
- `O` = 產出描述，可有可無，可跨 block 共用
- `K/S` = block 的「分界訊號」，同時也是該 block 所需的知識與技能

### 6.4 ocs_attitude

```json
"ocs_attitude": {
  "attitudes": [
    {
      "code": "A01",
      "name": "主動積極",
      "description": null
    }
  ]
}
```

規則：

- `description` 永遠保留鍵名。
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
- `knowledge`/`skills` 元素都具備 `code` 與 `name`。
- `ocs_attitude.attitudes[*].attitude_description` 不可缺鍵。
- `version_info.versions` 存在且每筆具 `version`、`ocs_code`、`status`。
- `ocs_content.ocu_units[*].tasks[*].task_codes` 為非空陣列，每個元素具備 `code` 與 `name`。
- 所有代碼欄位不應混入無結構長字串拼接。

## 8. Backward Compatibility

- 允許新增欄位（非破壞性）。
- 不允許移除既有欄位或改變既有欄位型別。
- 若來源資料品質不足，使用 `null` / `[]` 保持契約穩定。

## 9. Minimal Complete Example

```json
{
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
  },
  "ocs_profile": {
    "ocs_code": "FSI3311-001v3",
    "ocs_name": {
      "job_category_name": null,
      "occupation_name": "證券業-受託買賣業務人員"
    },
    "category": {
      "job_categories": [
        { "name": "金融財務／證券及投資", "code": "FSI" }
      ],
      "occupations": [
        { "name": "證券金融交易員及經紀人", "code": "3311" }
      ],
      "industries": [
        { "name": "金融及保險業／證券期貨及金融輔助業（證券業）", "code": "K6611" }
      ]
    },
    "job_description": "負責代理客戶買賣有價證券，並提供相關投資諮詢服務。",
    "ocs_level": 3
  },
  "ocs_content": {
    "ocu_units": [
      {
        "ocu_code": "T1",
        "ocu_name": "研發創意",
        "tasks": [
          {
            "task_codes": [
              { "code": "T1.1", "name": "研發劇本與概念" }
            ],
            "competency_blocks": [
              {
                "competency_level": 3,
                "indicators": [
                  { "code": "P1.1.1", "text": "參與設計定檔會議" },
                  { "code": "P1.1.2", "text": "彙整素材並確認需求" }
                ],
                "outputs": [
                  { "code": "O1.1.1", "name": "建議舞台設計構思" },
                  { "code": "O1.1.2", "name": "製作時程表" }
                ],
                "knowledge": [
                  { "code": "K01", "name": "舞台技術" }
                ],
                "skills": [
                  { "code": "S01", "name": "排程管理" }
                ]
              }
            ]
          }
        ]
      }
    ]
  },
  "ocs_attitude": {
    "attitudes": [
      {
        "attitude_code": "A01",
        "attitude_name": "主動積極",
        "description": null
      }
    ]
  },
  "notes_and_appendix": {
    "requirements": [
      {
        "category": "建議擔任此職類／職業之學歷／經歷／或能力條件",
        "content": "無",
        "notes": null
      }
    ]
  }
}
```

## 10. Recommended Naming Conventions

- 檔名：`<職能基準名稱>-職能基準.json`
- 編碼：UTF-8
- 鍵名：`snake_case`
- 語系：內容可為繁中，鍵名統一英文
