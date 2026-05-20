# Chunking 策略

本文定義 OCS JSON → Markdown chunk 的轉換規則。Markdown 同時是：
- **embedding 的輸入**（被向量化）
- **歸檔到 `output/md/` 的人類可讀檔**（每個 chunk 一份，可選輸出）

設計原則：
1. **結構決定 chunk 邊界**：以 JSON schema 中的自然單位（profile / ocu_unit / competency_block）為界，不依賴 MD 標題切分
2. **每個 chunk 自我完備**：MD body 必含完整定位資訊（職業名 + OCU + Task + Level），避免「靠 metadata 才看得懂」
3. **代碼 + 名稱並存**：P/O/K/S/A/T 等代碼保留，便於 retrieval 後的二次過濾與引用
4. **不壓縮原文**：indicator text 不縮寫、不去標點，保留原語意

---

## 1. 三層 Chunk

| 層 | 對應 schema | 數量（依 908 份實測） | 用途 |
|---|---|---|---|
| `profile` | 整份 OCS（不含 ocu_content 細節） | 1 / 檔 → **908** | 「依職位查職能內涵」首跳；跨基準比對的職業層 |
| `unit` | `ocs_content.ocu_units[*]` | 3.6 / 檔 → **3,272** | RAG 摘要型問答（auto-merge target）；OCU 層比對 |
| `block` | `ocs_content.ocu_units[*].tasks[*].competency_blocks[*]` | 9.6 / 檔 → **~8,689** | 細粒度檢索；「依技能查職位」反向查詢主力 |

**總計 ≈ 12,869 chunks × 2 vectors (dense + sparse) = 25,738 vectors**。Qdrant 本地單機輕鬆承載。

---

## 2. Chunk ID 規則

ID 必須穩定（同一份 JSON 內容產生同一 ID），讓增量更新可以 upsert：

| 層 | ID 格式 | 範例 |
|---|---|---|
| profile | `{ocs_code}::profile` | `FSI3311-001v3::profile` |
| unit | `{ocs_code}::unit::{ocu_code}` | `FSI3311-001v3::unit::T1` |
| block | `{ocs_code}::block::{ocu_code}::{primary_task_code}::{block_idx}` | `FSI3311-001v3::block::T1::T1.1::0` |

- `primary_task_code`：當 `task_codes` 長度 > 1，取陣列首位（按 spec 6.3.3 多 T 共享 block）
- `block_idx`：同一 task 內的 block 順序（0-based），對應 `competency_blocks[idx]`
- Qdrant 的 point id 必須是 UUID 或 unsigned int；上述字串作為 payload `chunk_key`，point id 用 `uuid5(NAMESPACE_DNS, chunk_key)` 確定性映射

---

## 3. Markdown 模板

### 3.1 `profile` chunk

```markdown
# {occupation_name} ({ocs_code})

- **職能基準等級**：L{ocs_level}
- **版本**：{version}（{status}，{update_date}）
- **職類**：{job_categories.name × N}
- **職業類別**：{occupations.name × N}
- **適用產業**：{industries.name × N}

## 工作描述
{job_description}

## 主要職責一覽
- T1 {ocu_name}（{tasks_count} 個任務）
- T2 {ocu_name}（{tasks_count} 個任務）
- ...

## 態度需求
- A01 主動積極
- A02 正直誠實
- ...

## 補充說明
### 任職條件
- 大專以上畢業...
### 其他補充
- 【註1】...
```

**設計理由**：
- 把 `category` 三類別、`attitudes`、`notes` 都摺進 profile chunk，這些「整份檔級別」的資訊在這層唯一出現
- `ocu_units` 只列代碼+名稱+task 數，**不展開內容**（內容留在 unit/block）
- 此 chunk 是「整份檔的摘要表」，向量化後對「列出 X 職業的所有職責」「適用於金融業的職位」這類查詢命中率高

### 3.2 `unit` chunk

```markdown
# {occupation_name} ({ocs_code}) · {ocu_code} {ocu_name}

> 本職能單元含 {tasks_count} 個工作任務，能力等級 L{min_level}–L{max_level}

## 工作任務
- {T1.1 name}（L{level}）
- {T1.2 name}（L{level}）
- ...

## 涵蓋知識
- K05 法律/法規
- K12 行銷策略
- ...（去重後的所有 K-code）

## 涵蓋技能
- S01 人脈拓展
- S09 顧客導向
- ...（去重後的所有 S-code）

## 主要產出
- O1.1.1 客戶聯繫與拜訪紀錄
- O1.2.1 客戶基本資料分類
- ...

## 行為指標（節錄）
- P1.1.1 在適法合規前提下持續性尋找資源與管道...
- P1.2.1 有效運用資訊設備建立客戶基本資料...
- ...（每個 task 取前 1–2 個 P 作為 representative；完整內容在 block chunk）
```

**設計理由**：
- 不重複輸出所有 P-code（會與 block chunk 大量重複，浪費 embedding 預算）
- 每個 task 取 1–2 個 P 做語意代表，足以讓向量檢索捕捉「這個 unit 在做什麼」
- K/S 去重後完整列出，因為這層是「unit 層 KS 集合」的標準展現
- `min_level` / `max_level` 抓取自旗下所有 block 的 `competency_level`，便於回答「這個 unit 需要什麼等級」

### 3.3 `block` chunk

```markdown
# {occupation_name} ({ocs_code}) · L{competency_level}
## {ocu_code} {ocu_name} / {task_codes_joined}

> 工作任務：{task_names_joined}

### 行為指標
- P1.1.1 在適法合規前提下持續性尋找資源與管道,執行各種客戶開發方案開拓客源,完成公司之開戶目標並維持穩定之開戶成長率。
- P1.1.2 在適法合規前提下提供業務執行必要之服務,維持實動戶數。

### 工作產出
- O1.1.1 客戶聯繫與拜訪紀錄

### 必備知識
- K05 法律/法規
- K12 行銷策略

### 必備技能
- S01 人脈拓展
- S09 顧客導向
```

`task_codes_joined`：
- 單一 T code：`T1.1 業務開發`
- 多 T code：`T1.1, T1.2`（H2 標題）+ `task_names_joined` 列每個名稱

**設計理由**：
- 每個 block 是「能在合理上下文下回答 P/O/K/S 配對」的最小單位
- H1 標題刻意包含 `ocs_code` 與 `competency_level`，讓 BGE-M3 dense vector 自然學到「這個 chunk 屬於哪個職業哪個等級」
- 不放 `attitudes`（attitudes 在 profile 層級，與 block 無關聯）

---

## 4. 邊界情況

### 4.1 同格多 T code（53 個 task 命中）
- 一個 `task` 條目對應一個 block-set，但 `task_codes` 長度 > 1
- **chunk 仍以 block 為單位**，不為每個 T code 各自複製
- MD H2 寫成 `T1.1, T1.2`，並用 `task_names_joined` 在 quote block 中列出所有名稱
- payload 中 `task_codes` 為陣列，filter 時 `match.any` 可命中任一 T code

```markdown
## T1.1, T1.2

> 工作任務：
> - T1.1 分析市場/客戶需求
> - T1.2 評估現有技術能力
```

### 4.2 同 task 多 block（多 level、T4.1 樣式）
- 同一 task 旗下 `competency_blocks` 長度 > 1（最常見原因：competency_level 不同）
- 每個 block 各自成為獨立 chunk
- `block_idx` 區分；MD 內 `L{competency_level}` 自然標示差異

### 4.3 跨版本（同 OCS 有 v1/v2/v3）
- 上游 schema 只在 `version_info.versions[]` 列舉版本，但 JSON body 只描述 `ocs_profile.ocs_code` 指向的當前版本
- **每份 JSON 視為一個獨立 OCS**：v1 / v2 / v3 各自獨立索引，payload 標記 `version` 與 `is_current`
- `is_current = (status == "最新版本")`；同一 occupation_name 在多版本下會有多個 profile chunk
- 跨版本去重交給檢索層的 filter（預設 `is_current=true`），不在索引層去重
- 若 `version_info.versions[]` 缺失，從 `ocs_profile.ocs_code` 尾端 `vN` 推導 `version` / `version_seq`；不可推導則寫 null，`is_current` 預設 true

### 4.4 跨頁延續
- jd-pdf-to-json 已在 schema 層處理（spec 6.3.4），輸出 JSON 是「已合併」狀態
- indexer 不需特殊處理，照 block 邊界切即可

### 4.5 `competency_level = null`
- MD 寫成 `L?` 或省略 level 標示
- payload `competency_level` 直接寫 `null`（Qdrant 支援 nullable）
- range filter 時要小心處理 null（細節見 [SCHEMA.md](./SCHEMA.md)）

### 4.6 多產業 / 多職類 / 多職業（AIoT 樣式）
- profile chunk MD 中用 bullet list 列出全部
- payload 中各為 `string[]`：`industry_codes`、`job_category_codes`、`occupation_codes`
- 反向查詢「資訊服務業有哪些職位」直接走 array filter，不依賴向量
- 若 `job_category` 缺失，MD 省略該行或顯示為空集合；payload 寫 `job_category_codes=[]`、`job_category_names=[]`，不視為錯誤

### 4.7 `notes.prerequisites` / `supplements` 缺失
- 900/908 檔有 notes，仍有 ~1% 缺失
- 缺失時 MD 對應段落整段省略，不顯示空白標題
- payload 中 `has_prerequisites` / `has_supplements` 為 bool 旗標

### 4.8 `attitudes[].name` 含描述（「主動積極：不需他人指示...」）
- 上游規範要求保留原文不拆分
- profile chunk MD 中原樣輸出
- payload 中 `attitude_codes` 仍只取 code（A01、A02...），name 不入 payload

---

## 5. Chunk 大小預估（依 BGE-M3 tokenizer）

| 類型 | 預估字數 | 預估 tokens | 備註 |
|---|---|---|---|
| profile | 500–2000 | 250–1000 | AIoT 類多產業會偏長 |
| unit | 300–800 | 150–400 | 平均規模 |
| block | 200–500 | 100–300 | 73% block 原始 < 200 字，加 header 後落在 250+ |
| **單一 chunk 上限** | — | **2048 token** | BGE-M3 推薦上限 8192，但保守用 2048 |

對於極長 profile（例如 AIoT 完整列 7 個 occupations + 5 個 industries + 多段 job_description）：
- 預估 token < 1500，不需切分
- 若未來真碰到 > 2048 token 的個案，profile chunk 拆 `profile_head`（基本資料）+ `profile_attitudes_notes`（態度與補充）兩個 chunk；目前不為此預做拆分

---

## 6. 不做的事

- **不做 sliding window**：block 已是語意自然單位，重疊只會放大重複
- **不做 sentence splitter**：indicator text 在 block 內整段保留，跨 indicator 不切分
- **不做 token-level chunking**：所有 chunk 邊界由 schema 決定，token 數只是事後檢驗
- **不為了均勻 chunk 大小而合併小 block**：保留 schema 結構優先於 chunk 大小均勻性
