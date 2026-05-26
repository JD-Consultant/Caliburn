# Chunking Strategy

本文定義 OCS JSON -> Markdown chunk 的轉換規則。

本 repo 不做一般 RAG 的 token-level chunking。因為上游 `jd-pdf-to-json` 已產出結構化 JSON，chunk 邊界直接由 OCS schema 決定。

Markdown 的用途是：

- 作為 embedding text。
- 作為未來 LLM context 的直接材料。
- 作為 optional dump 檔，方便人工檢查。

---

## 1. Principles

1. **JSON structure decides chunk boundary**：不依賴 Markdown heading 或 token splitter。
2. **三層都存，不是三選一**：同一份 OCS JSON 產生 profile、unit、block 三種粒度。
3. **chunk text 要人類可讀**：尤其 block chunk 要包含使用者會描述的工作活動、知識、技能文字。
4. **metadata 支援聚合與回溯**：用 `ocs_code`、`unit_id`、K/S、parent id、`source_file` 讓 future service 組上下文。
5. **不把完整 JSON 塞進 Qdrant**：完整 JSON 用 `source_file` 回讀。

---

## 2. Three Chunk Levels

| chunk_level | 對應 schema | 數量（908 份實測） | 主要用途 |
|---|---|---:|---|
| `profile` | 整份 OCS profile | 908 | 找候選職務、職務摘要、相似職務 |
| `unit` | `ocs_content.ocu_units[*]` | 3,272 | 找主要工作任務、產生遺漏提示 |
| `block` | `competency_blocks[*]` | 8,689 | 找具體能力、K/S、工作活動 evidence |

總計約 12,869 points。

---

## 3. Chunk Key Rules

chunk key 是穩定邏輯 ID，Qdrant point id 由它映射成 UUIDv5。

```text
profile: ocs:{ocs_code}:profile
unit:    ocs:{ocs_code}:unit:{unit_key}
block:   ocs:{ocs_code}:unit:{unit_key}:task:{primary_task_key}:block:{block_key}
```

範例：

```text
ocs:INM3513-009v1:profile
ocs:INM3513-009v1:unit:T1
ocs:INM3513-009v1:unit:T1:task:T1.1:block:0001
```

規則：

- 有穩定代碼就使用原始代碼。
- 缺代碼時用 zero-padded index fallback，例如 `unit:0001`。
- 多 task group 使用 `primary_task_key = sorted(task_keys)[0]`。
- 完整 task ids 保留在 payload `task_ids`。
- `T1`、`T1.1`、`P1.1.1`、`O1.1.1` 可保留於 `source_labels`，但不是主要搜尋入口。

---

## 4. Profile Chunk

每份 JSON 一個。

內容：

- 職務名稱與 `ocs_code`
- 職能基準等級
- 版本資訊
- 職類 / 職業 / 產業
- 工作描述
- 主要 unit 一覽
- 態度需求
- notes / 任職條件 / 補充說明

範例：

```markdown
# 資料分析師 (INM3513-009v1)

- 職能基準等級：L4
- 版本：V1
- 職類：資訊科技
- 適用產業：資訊服務業

## 工作描述
負責蒐集、整理、分析資料，協助組織理解營運狀況並支援決策。

## 主要工作任務
- T1 資料蒐集與需求確認
- T2 資料處理與分析
- T3 報表與分析結果呈現

## 態度需求
- 主動積極
- 溝通協調
```

future service 用途：

- 使用者提供職務名稱時找候選 OCS。
- 多個 block 命中同一職務時補職務定位。
- JD draft 前提供職務摘要。

---

## 5. Unit Chunk

每個 `ocu_unit` 一個。

內容：

- 職務名稱與 `ocs_code`
- unit 名稱
- 該 unit 下的 task 摘要
- 涵蓋知識 / 技能 terms
- 主要工作產出或行為摘要

範例：

```markdown
# 資料分析師 (INM3513-009v1)

## 職能單元：資料處理與分析

這個職能單元包含資料清理、資料品質檢查、資料轉換與分析準備。

## 工作任務
- 清理與轉換資料
- 檢查缺漏值、異常值與格式一致性
- 建立可供分析或報表使用的資料集

## 涵蓋知識
- 資料品質管理
- 資料格式
- 異常值處理

## 涵蓋技能
- SQL 查詢
- 資料清理
- ETL 流程整理
```

future service 用途：

- block 命中後用 `unit_chunk_id` 補同組工作任務。
- 產生「你是否也會...」確認問題。
- 用於工作任務層級的 similarity search。

---

## 6. Block Chunk

每個 `competency_block` 一個。

內容：

- 職務名稱與 `ocs_code`
- unit / task 上下文
- block 能力描述
- 行為指標
- 工作產出
- 必備知識
- 必備技能

範例：

```markdown
# 資料分析師 (INM3513-009v1)

## 職能單元：資料處理與分析

### 工作任務：清理與轉換資料

#### 能力區塊：資料清理與品質檢查

工作活動：
- 檢查資料缺漏值、異常值與格式一致性
- 使用 SQL 或資料處理工具清理資料
- 整理資料供報表、分析或決策使用

必備知識：
- 資料品質管理
- 資料格式
- 異常值處理

必備技能：
- SQL 查詢
- ETL 流程整理
- 報表資料準備
```

future service 用途：

- 從使用者工作活動命中具體能力。
- 聚合 K/S codes。
- 當作 evidence chunk。

---

## 7. Long User Description Support

本 repo 不負責拆使用者長段描述，但 chunk text 必須支援這種 future retrieval：

```text
使用者長描述
  -> future service 抽出多個工作活動
  -> 每個活動搜尋 unit/block
  -> 聚合命中的 ocs_code / unit / K/S
```

因此 block Markdown 應避免只列代碼，應包含自然語言活動：

```text
好：檢查缺漏值、異常值與格式一致性
差：P1.1.1 / K01 / S02
```

代碼仍存於 payload，用於 filter、citation、debug。

---

## 8. Parent and Source Trace

每個 block chunk payload 應至少能提供：

```json
{
  "profile_chunk_id": "ocs:INM3513-009v1:profile",
  "unit_chunk_id": "ocs:INM3513-009v1:unit:T1",
  "source_file": "output/0518/example.json",
  "source_json_hash": "sha256:..."
}
```

使用方式：

- `unit_chunk_id`：快速補 unit Markdown context。
- `profile_chunk_id`：快速補職務摘要。
- `source_file`：需要完整 JD 背景時讀回完整 JSON。

---

## 9. Edge Cases

### Multi-task group

- 一個 block-set 可能對應多個 task id。
- 不為每個 task 複製 block。
- `task_ids` 寫完整陣列。
- chunk key 使用排序後第一個 task id 作 `primary_task_key`。

### Missing version

- 從 `ocs_code` 尾端 `vN` 推導。
- 不可推導則 `version = null`、`version_seq = null`。

### Missing job category

- `job_category = null`
- `job_category_codes = []`
- Markdown 省略該行或顯示空集合。

### Missing level

- `competency_level = null`
- Markdown 可省略 level 或顯示 `L?`。

### Very large chunk

v1 不預先拆分。若未來單一 chunk 超過 embedding provider 合理上限，再針對 profile 補 `profile_head` / `profile_notes` 類型的新 schema version。

---

## 10. Not Doing

- 不做 sliding window。
- 不做 sentence splitter。
- 不做 token-level chunking。
- 不為均勻 chunk 大小合併 block。
- 不把完整 source JSON 塞進每個 Qdrant payload。
