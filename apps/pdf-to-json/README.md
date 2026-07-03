# pdf-to-json — OCS PDF → 結構化 JSON(ETL)

「解析」bounded context:把官方職能基準(OCS/iCAP)**PDF** 轉成結構化 **JSON**(CLI 工具),
供 [`apps/ocs-indexer`](../ocs-indexer/) 索引。純離線批次、無伺服器、無狀態。

> **這份 README 一檔兩用**:上半是 **app 指南**(跑 / 架構 / codemap);
> **下半 §1–10 是權威的 OCS 來源 JSON 契約**——[`docs/ocs-source-json.md`](../../docs/ocs-source-json.md)
> 指向此為準;動 indexer/api 的 OCS 欄位前先讀(尤其 §6.3)。

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

## 架構 / 流程(Pipes-and-Filters)

```
PDF ─▶ parse ─▶ transform ─▶ [validate] ─▶ write JSON
      PDFPlumber   section 拆解    schema      JSONWriter
      (→ pages)    → OCSDocument   (可停用)
```

`convert` 照 **4 階段**跑;`batch` 對整個資料夾逐檔跑(**單檔失敗不中斷**,收尾寫 summary log)。
`transform` 是**薄編排**:re-open PDF,依序委派五個 section extractor 組成 `OCSDocument`——

`version → profile → content → attitude → notes`

其中 **`content_extractor` 最難**(§6.3 的區塊分界 / 跨頁 / 同格多 T code 規則都在它)。
**驗證不擋輸出**:schema 失敗仍寫 JSON(方便人工檢查)但 `exit 1`。

## Codemap

```
src/jd_pdf_to_json/
  cli.py                 # typer CLI:convert / batch / validate(4 階段編排 + log)
  parsers/               # base(port)+ pdf_parser(PDFPlumberParser:PDF → {metadata, pages})
  transformers/
    ocs_transformer.py   # 薄編排:依序呼叫 sections/*,組 OCSDocument
    sections/            # 五個 section extractor(version / profile / content / attitude / notes)
    support/             # 無狀態共用:text / tables / items / dedupe / scanning
  validators/schema.py   # OCSSchemaValidator → (is_valid, errors)
  writers/json_writer.py # JSONWriter(UTF-8 落檔)
  core/models.py         # OCSDocument 等 pydantic 模型(五大區塊)
  utils/                 # exceptions / logger
```

## 不變量

- **Pipes-and-Filters,單向**:parse → transform → validate → write;各階段可獨立測。
- **transformer 只編排、不解析**:每個 PDF section 的邏輯住自己的 extractor(Phase 3b 拆解;
  **別把規則塞回 orchestrator**)。
- **契約在下半(§1–10)且權威**:改欄位語意 = 改契約,牽動 indexer / api / `packages/ocs-contract`。

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
5. `notes`

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
  "notes": { "prerequisites": [], "supplements": [] }
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
| **跨頁多 T code 無 P-code**（如 T2.8–T2.11 接續 T2.1–T2.7） | 次頁工作任務欄有新 T code，但行為指標欄空白 | 新 T code 追加至前一 task 的 `task_codes`，O/K/S append 進前一個 block |
| **跨頁**（如 T1.3、T2.1） | 次頁無 O-code（O 名稱跨頁截斷）、無 level | 全部 append 到同一 block |

#### 6.3.4 跨頁處理

當 PDF 表格跨頁時，次頁通常：
- 工作任務（T）欄位空白
- 工作產出欄只剩 O 名稱的後半段文字（無 `O` 代碼前綴）
- 職能級別空白

此情況不滿足分界條件，次頁的 P / K / S 全部 append 進前一個 block，O 名稱後半段文字接續拼入前一個 output 的 `name`。

**跨頁多 T code 無 P-code：** 次頁工作任務欄出現新 T code，但行為指標欄空白（無 P-code）。此類列視為前一 task 的延續——新 T code 追加至前一 task 的 `task_codes` 陣列，O/K/S 同樣依 block 分界規則 append 進前一個 block。

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
    { "code": "A01", "name": "主動積極" }
  ]
}
```

規則：

- `attitudes` 依 A-code 順序排列。
- 部分 PDF 的 `name` 含描述文字（格式：`名稱：描述`），保留原文，不拆分。

### 6.5 notes

PDF 末頁「說明與補充事項」分為兩個子區塊：

```json
"notes": {
  "prerequisites": [
    "大專以上畢業，且具3年以上相關工作經驗。",
    "具備程式語言能力或相關工具應用能力。"
  ],
  "supplements": [
    "【註1】品質管理理論：包括品質政策、制度、程序、績效指標與檢核標準等。",
    "【註2】管理方法：如走動式管理（MBWA）。"
  ]
}
```

規則：

- `prerequisites`：「建議擔任此職類／職業之學歷／經歷／或能力條件」下的每一條文字，不含標題行本身。
- `supplements`：「其他補充說明」下的所有條文；無此區塊時為空陣列 `[]`。
- 兩個欄位均為 `List[str]`，每個元素為一條去除項目符號後的純文字。

## 7. Validation Checklist

每份輸出 JSON 在交付前應至少通過以下檢核：

- Top-level 五區塊鍵名完整存在。
- `ocs_profile.category` 三類別皆為陣列型別。
- `knowledge`/`skills` 元素都具備 `code` 與 `name`。
- `ocs_attitude.attitudes[*]` 具備 `code` 與 `name`。
- `version_info.versions` 存在且每筆具 `version`、`ocs_code`、`status`。
- `ocs_content.ocu_units[*].tasks[*].task_codes` 為非空陣列，每個元素具備 `code` 與 `name`。
- `notes.prerequisites` 與 `notes.supplements` 均為字串陣列。
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
      { "code": "A01", "name": "主動積極" }
    ]
  },
  "notes": {
    "prerequisites": ["大專以上畢業，且具3年以上相關工作經驗。"],
    "supplements": ["【註1】管理系統相關知識：組織程序、政策、結構、文化與策略。"]
  }
}
```

## 10. Recommended Naming Conventions

- 檔名：`<職能基準名稱>-職能基準.json`
- 編碼：UTF-8
- 鍵名：`snake_case`
- 語系：內容可為繁中，鍵名統一英文

## 指路

- 架構鳥瞰:根 [`ARCHITECTURE.md`](../../ARCHITECTURE.md)(Code map:pdf-to-json = Pipes-and-Filters)。
- 來源契約取用注意事項:[`docs/ocs-source-json.md`](../../docs/ocs-source-json.md)(指向本 §6.3 為權威)。
- transformer 拆解研究:[`docs/specs/2026-06-28-pdf-to-json-transformer-decomposition-research.md`](../../docs/specs/2026-06-28-pdf-to-json-transformer-decomposition-research.md)。
- 下游:[`apps/ocs-indexer/README.md`](../ocs-indexer/README.md)(索引消費本輸出);著作端 schema 見 [`docs/ocs-schema.md`](../../docs/ocs-schema.md)。
