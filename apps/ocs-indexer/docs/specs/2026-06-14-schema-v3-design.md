# jd-ocs-indexer Schema v3 設計

> 流程驅動的 chunk / payload 重設計：從 profile/unit/block 三層 → **profile + task 兩種 point**。
> 狀態：設計討論中（payload 已收斂，仍有 2 個 open 點）。
> 取代：v2 的 chunk 模型（[2026-06-13 整合設計](../../../jobintel-ai/docs/superpowers/specs/2026-06-14-jobintel-ocs-integration-design.md) 的 chunk 部分）。流程/角色分工不變。

---

## 1. 為什麼要 v3

v2 把整個 OCS 結構（profile/unit/block + 一堆平行陣列 + codes + terms + pairs）全塞進 Qdrant，造成：
- **chunk 太大 / embedding 雜**：profile 想塞技能雲與結構、unit/block 散落、payload 冗餘。
- **該被搜的沒被 embed**：K/S 只是 payload pair，沒有向量 → 使用者「改過的任務」要找對應 K/S 時搜不到。
- **散 chunk 重組**：任務清單要從 block 重組（會漏 block-less task、平行陣列錯位）。

v3 從**流程**倒推 embedding 單位，只 embed「真的需要語意搜尋」的東西，其餘走結構化 filter / retrieve。

---

## 2. 核心原則：只有兩件事需要向量

逐流程檢查「未知（要語意找）vs 已知（filter/撈）」：

| 流程動作 | 已知/未知 | 向量？ |
|---|---|---|
| 使用者描述工作 → 找職務 | 未知 | **要** |
| 選定職務 → 撈任務清單 | 已知 ocs_code | 否（filter） |
| 細節訪談 T/O/P | bottom-up 使用者內容 | 否 |
| 改過/自訂任務 → 找對應 K/S | 未知（內容 drift） | **要** |
| Gap：整 OCS 的 K/S/A 池 | 已知 ocs_code | 否（撈+聚合） |

→ **只有 2 個動作需要向量：(A) 描述→職務、(C) 改過的任務→K/S。**
→ 只 embed **profile** 和 **task** 兩種。其餘是「已知 key → filter/retrieve」或「使用者 bottom-up 內容」。

衍生原則：
- **embed 是「動作」不是「欄位」**：embed 字串在 index 時組好餵模型，**不回存**；要顯示就用已存的結構化欄位拼。
- **pair 是 canonical**：K/S/A/output 一律存 `{code,name}` pair（綁定不漂）；不存平行 codes/terms（碼是 OCS-local 沒人全域過濾、名在 pair）。
- **decouple**：向量搜尋（profile/task）vs 結構化查詢（scroll/retrieve by key）分開；後者不靠向量。
- **block 只在 index 時用**：能力區塊用來把每個 task 的 K/S 與活動句**聚合**好，**不存成 point**。

---

## 3. 兩種 point

### Collection
named vectors：`dense`(1024d, cosine) + `sparse`(BGE-M3 lexical)。兩種 point 都有。

### profile point（~904，每 OCS 一個）

**point id**：`uuid5("ocs:{ocs_code}:profile")`

**vector** = embed of：`職稱 + 職務描述 + 工作內容（任務名/活動摘要）+ 技能名`
> 要大、要全——使用者描述的工作/技能/工具詞都要能命中（tool-level term 如「Python SQL LLM 微調」）。

| 欄位 | 型別 | 角色 | 幹嘛 |
|---|---|---|---|
| `chunk_level` | str=`"profile"` | 🔍 | 過濾層級 |
| `ocs_code` | str | 🔍 | 識別 / scope / 算 point id |
| `ocs_code_base` | str | 🔍 | 找同職務所有版本 |
| `job_title` | str | 🔍 TEXT | 顯示 + 關鍵字搜 |
| `is_current` | bool | 🔍 | 只取現行版 |
| `version` | str\|null | 🔍 | 版本過濾 |
| `ocs_level` | int\|null | 🔍 | 職能級別過濾 |
| `industry_codes` | list[str] | 🔍 | 行業碼（全域）過濾 |
| `occupation_codes` | list[str] | 🔍 | 職業碼（全域）過濾 |
| `job_category` | str\|null | 📦 | 職類名（顯示） |
| `industry_names`/`occupation_names` | list[str] | 📦 | 顯示 |
| `version_seq` | int | 📦 | 版本排序 |
| `update_date` | str\|null | 📦 | 顯示 |
| `job_description` | str | 📦 | Round 1 瀏覽（也是 embed 的一部分） |
| `all_a_pairs` | list[{code,name}] | 📦 | 態度（profile 級，gap 用） |
| `prerequisites` | list[str] | 📦 | 建議學歷/經驗/能力條件（Step 5a 選單；多職位 union）。來源 `notes.prerequisites`（已 parse、v2 未寫入） |
| `supplements` | list[str] | 📦 | 其他補充說明（Step 5b **當參考**，不做硬選單）。來源 `notes.supplements` |
| `source_file` | str | 📦 | 出處 |
| `indexed_at` | str(ISO) | 📦 | 稽核 |

> 無通用 `text`（embed 在 index 時組、不回存；顯示用 job_description）。無 task 清單（task 是獨立 point）。

### task point（~8,300，每任務一個）

**point id**：`uuid5("ocs:{ocs_code}:unit:{unit_key}:task:{task_key}")`

**vector** = embed of：`任務名稱 + 活動內容`
> 適中——用來讓「改過/自訂的任務」語意命中標準任務。

| 欄位 | 型別 | 角色 | 幹嘛 |
|---|---|---|---|
| `chunk_level` | str=`"task"` | 🔍 | 過濾層級 |
| `ocs_code` | str | 🔍 | 撈選單 / scope |
| `unit_id`/`unit_title` | str\|null | 📦 | 選單表格按單元分組 |
| `task_id` | str | 📦 | OCS 來源參考（引用 + by-id 取 K/S） |
| `task_title` | str | 📦 | 顯示 |
| `activity_examples` | list[str] | 📦 | 選單「內容」提示 + Round 3 引用 OCS 原句 + T/O/P 的 P 參考 |
| `k_pairs`/`s_pairs` | list[{code,name}] | 📦 | K/S 選單（命中/取得即給） |
| `output_pairs` | list[{code,name}] | 📦 | 產出（T/O/P 的 O、gap） |
| `competency_level` | int\|null | 📦 | 級別 |
| `source_file` | str | 📦 | 出處 |

> 無通用 `text`（embed 組自 task_title+活動；顯示用 task_title+activity_examples）。無 K/S 以外的 block 細節（block 不存）。

### Payload 索引（🔍 全部，~9 個）

| 欄位 | 型別 | point |
|---|---|---|
| `chunk_level` | keyword | 兩種 |
| `ocs_code` | keyword | 兩種 |
| `ocs_code_base` | keyword | profile |
| `job_title` | text | profile |
| `is_current` | bool | profile |
| `version` | keyword | profile |
| `ocs_level` | int | profile |
| `industry_codes` | keyword | profile |
| `occupation_codes` | keyword | profile |

（v2 是 18 個）

---

## 4. 流程 → 存取對應（覆蓋驗證）

| 流程動作 | 怎麼做 | 機制 |
|---|---|---|
| 描述 → 候選職務 | `query_points` profile 向量（含工作內容+技能，tool 詞命中） | 向量 |
| 選定 → 任務選單表格 | `scroll` task where `ocs_code in [選的]`，按 `unit_id` 分組 | 結構化（完整、含 block-less task）。**顯示輕量：task 名 + 1-2 句活動（秒認），O/完整 P 留細節訪談** |
| 自訂/新增任務 | 細問時向量比對 | — |
| 細節訪談 T/O/P | bottom-up 使用者內容；參考 task 的 activity_examples/output_pairs | — |
| K/S 選單（內容沒改） | `retrieve` task point by id（jobintel-ai 記住來源 task_id） | by-id |
| K/S 選單（改過/自訂） | `query_points` task 向量（用改後內容）→ 命中標準 task → 繼承 K/S | 向量 |
| Gap（整 OCS 池） | `scroll` task by ocs_code → union K/S/output + profile `all_a_pairs` | 結構化+聚合 |
| JD 引用 | profile（ocs_code/title/version/date）+ task（task_id + 帶名 pairs） | — |

> **task_id 是「OCS 來源參考」，不是使用者的任務身分。** 使用者的排序/編號/改名是 jobintel-ai 的 state，與 indexer 無關；排序/改名不影響 by-id 取 K/S（內容沒變），只有內容大幅 drift 才走向量。

---

## 5. v2 → v3 砍除清單

**整個 point 類型**：`unit` point、`block` point（block 只在 index 時聚合用）。

**欄位**：`knowledge_terms`/`skill_terms`、`k_codes`/`s_codes`/`attitude_codes`（flat+索引）、`indicator_codes`/`output_codes`、`block_id`/`block_title`、`task_ids`/`task_titles`（平行陣列）、`work_activity_terms`、`source_path`/`source_labels`、`schema_version`/`embedding_provider`（per-chunk+索引）、`text_format`、`source_root_alias`、`chunk_content_hash`、通用 `text`、`unit_order`/`task_order`。

**設計理由**：見 §2 原則（pair canonical、碼 OCS-local、embed 是動作、decouple、block index-time-only）。

---

## 6. 對 query API 的影響

- `/search`：涵蓋 profile（候選）與 task（改過任務 K/S 比對）兩種向量搜尋。reranker 計畫仍適用（重排 /search 候選）。
- `/task-pool`：改成 `scroll` task points by ocs_code（不重組 block、完整）。
- `/pairs`：改成 `scroll` task by ocs_code → union K/S/output + profile `all_a_pairs`（不另存 pool）。
- 自訂任務掛點：task 向量搜尋（取代 block 向量搜尋）。
- 需要 **re-index**（全量重建，~9,200 點）。

---

## 7. 仍 open（待續討論）

1. **profile embed 的確切組成**：工作內容要納入多少（全部任務名？活動摘要？）——使用者傾向「存多一點」。
2. **候選職務是否也用 task-level recall**：若 profile 直接搜召回不足（tool 詞），是否加「搜 task → 聚合到 profile」當補強。
3. `competency_level` 是否要在 task 之外提供其他級別過濾。
