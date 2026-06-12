# 使用者流程：從工作描述到客製化 JD

> 本文件描述 `jd-ocs-indexer` 服務的下游 — 客製化職務說明書（JD）產品的使用者流程，以及 indexer 在每一階段該提供什麼。本 repo 只負責「準備好結構化候選池」，實際對話與 JD 生成在 future `jobintel-ai` 服務做。
>
> 本文件不 commit，僅供專題報告與內部設計參考。

---

## 1. 設計核心：OCS 是參考，不是模板

### 1.1 一般人寫 JD 的真實困難

非技術使用者（HR、創業者、轉職者）寫不出格式化 JD 的原因不是「不知道自己做什麼」，而是「不知道工作內容怎麼歸類成正式語言」。

讓 LLM 一次性把使用者一段話直接生成 JD 有 4 個致命問題：

1. **使用者沒辦法驗證每一條敘述是否屬實** — LLM 容易把使用者沒做的事寫進去
2. **沒有事實 grounding** — 引用的能力代碼（K01、S03）可能是 LLM 編的
3. **使用者掌控感低** — 看到 AI 寫的東西不曉得可不可信
4. **不可迭代** — 要改就要整段重生

### 1.2 我們選擇的設計

```
OCS（職能基準）= 政府制定的職務參考資料 ＋ 詞彙池
JD（職務說明書）= 使用者自己的工作 ＋ 引用 OCS 部分內容（標明出處）
```

**OCS 不是模板**。同樣是「資料分析師」，A 公司做的事跟 B 公司可能差 60%。所以最終 JD 的 T1/T2/T3 是這份 JD 自己的編號，**不沿用 OCS 編號**。OCS 只是 1~3 份背景參考資料（使用者可複選），給 LLM 顧問當詞彙池與結構參考。

### 1.3 LLM 的角色：顧問，不是生成器

LLM 像獵頭顧問一樣**多輪對話**訪談使用者：

- 先問粗的問題（「你做什麼」）
- 給結構化選單讓使用者快速勾選範圍
- 針對勾選的內容細問
- 主動 probe 可能漏掉的細節（gap detection）
- 不斷迭代直到資訊足以產出 JD

**事實判斷在使用者，文字組合在 LLM**。LLM 只在使用者勾過的 atoms 內做最後的潤稿。

### 1.4 為什麼「先選單，再對話」

OCS 一份職務有 3-5 個 unit、8-15 個 task、20-40 個 block。如果 LLM 對每個都一個個問「你做嗎」，會卡死。

正確順序：
1. **批次選單階段**：把所有可能項目一次列出，使用者快速勾完整範圍
2. **針對性對話階段**：LLM 只對勾選的項目細問

選單階段 1 分鐘搞定範圍，對話階段才開始花時間補細節。

---

## 2. 完整使用者流程

### Round 0：初次描述

**使用者輸入**（一句到兩句即可）：

> 我在金融科技做資料相關，會用 Python SQL，也會處理 LLM 微調與部署

**indexer 提供**：profile-level hybrid retrieval（dense + sparse RRF）
**indexer 必要前提**：profile chunk text 必須包含技能雲（aggregated K/S names），讓「Python SQL LLM 微調」這種 tool-level term 能命中

---

### Round 1：候選參考 OCS（可複選）

**系統顯示** top-5 候選職務，使用者可複選 1~3 個當參考來源：

```
☑ SMS2512-002v1  AI 應用規劃師     (主要參考)
☑ INM3513-009v1  資料分析師         (次要參考)
☐ XXX-XXX-XXXv1  商業分析師
☐ YYY-XXX-XXXv1  機器學習工程師
☐ ZZZ-XXX-XXXv1  AI 應用工程師
☐ 都不是 → 重新描述
```

**為什麼複選**：「同職位但內容不同」很常見。使用者可能 60% 像 OCS-A，40% 像 OCS-B。讓使用者明示這件事比逼他選一個更誠實。

**indexer 提供**：
- profile chunk 含完整 `job_title` / `ocs_code` / `version` / `ocs_level` / `industry_names` / `occupation_names`
- profile payload 含 `job_description` 全文（供使用者瀏覽判斷）
- 預設只回 `is_current=true`（避免拿到舊版）

**返回筆數**：top-5（內部可以撈 top-10 排序後給 5 個，留迴旋空間）

---

### Round 2：工作選單（合併參考 OCS 的 task 池）

使用者勾完參考 OCS 後，系統合併兩份 OCS 的 task 池，**by unit grouped**，讓使用者一次勾完做哪些事：

```
▸ T1 評估與分析AI技術  (來自 SMS2512)
  ☐ T1.1 掌握AI技術發展及應用趨勢
  ☑ T1.2 掌握目標並確立需求          ← 使用者勾
  ☐ T1.3 評估應用或發展效益

▸ T2 提出AI應用策略及建議  (來自 SMS2512)
  ☑ T2.1 制定AI技術應用發展計畫       ← 使用者勾
  ☐ T2.2 制定AI技術應用規範

▸ T1 蒐集分析需求  (來自 INM3513)     ← 不同 OCS 同編號不衝突
  ☐ T1.1 確認分析需求
  ☑ T1.2 整理資料來源                  ← 使用者勾

▸ T2 資料處理與分析  (來自 INM3513)
  ☑ T2.1 資料清理                      ← 使用者勾
  ☐ T2.2 整合多來源
  ☐ T2.3 建立分析資料集

➕ 新增自訂工作項目（例：LLM 模型部署）
```

**indexer 提供**：
- 給定 ocs_code list，scroll 所有 unit chunks
- 每個 unit chunk payload 含完整 task list（id + title）
- 每個 task 可顯示**代表性 activity 例句**（從 block 的 indicator_texts 取首句 truncate）

**這對 indexer 的要求**：unit chunk 的 markdown 與 payload 要清楚列每個 task 對應的 activity 例句，讓使用者一目了然「這個 task 大概在做什麼」。

**自訂項目處理**：使用者新增「LLM 模型部署」時：
- 系統用 cross-OCS block-level hybrid retrieval 找最像的 3-5 個標準 block
- 標明「這活動像 SMS2512-002v1 T3.3 確保AI應用部署與系統整合」
- 使用者確認後，自訂項目掛在最像的 task 下，繼承該 task 的 K/S/A 建議 pool

---

### Round 3：針對勾選項目的細節訪談

**LLM 顧問只針對使用者勾的 task 開始細問**：

```
LLM: 「你勾了 T1.2 掌握目標並確立需求 — OCS 標準寫『跟業務確認 AI 應用發展
      需求』。實務上你通常跟誰確認？業務、PM、還是高階主管？」
使用者: 「主要跟業務和 PM 確認」

LLM: 「了解。T2.1 制定計畫 — 你會獨立寫專案計畫書還是跟團隊一起？」
使用者: 「跟團隊一起，主要負責技術架構部分」

LLM: 「INM3513 T1.2 整理資料來源 — 你提到的『LLM 微調』通常需要什麼資料來源？
      內部資料庫、爬蟲、還是公開資料集？」
使用者: 「內部 + 公開資料集」
```

**indexer 提供**：
- 每個勾選的 block chunk payload 含 evidence 結構（indicator_code + activity_text）
- LLM 可引用 OCS 原句當問題的對照（「OCS 說...你的情況呢？」）
- block payload 的 k_pairs / s_pairs 是後續細問技能時的選項池

**訪談技巧（LLM 端）**：
- 不要問封閉題（「你做嗎」）— 問開放題（「你怎麼做」）
- 引用 OCS 原句當參考但不要逼使用者照唸
- 一次問 1-2 題，不要一次給 5 個問題
- 如果使用者描述不清，要 follow-up 追問

---

### Round 4：K/S/A 選單 + 細節訪談

任務細節問完後，系統依使用者勾選的 task 算出**對應 K/S/A 聯集 pool**：

```
─── 核心知識 (Knowledge) ───
☑ K01 AI 技術基本原理        (來自 SMS2512 T1.2 / T3.x)
☑ K02 AI應用場景知識         (來自 SMS2512 T1.2)
☑ K05 機器學習概論           (來自 SMS2512 多處)
☐ K08 專案管理知識           (來自 SMS2512 T2.1)
☑ K11 資料處理與分析概念     (來自 INM3513 T2.1)
☐ K13 資訊安全概念           (來自 SMS2512)
➕ 新增 / ✏️ 編輯
```

使用者快速勾完後，LLM 對勾選項目細問：

```
LLM: 「你勾了 S03 SQL 查詢能力 — 是純查詢還是會做複雜 ETL？比如 window 
      function、CTE 這些？」
使用者: 「主要是 PostgreSQL 跟 BigQuery，會用 window function」

LLM: 「你勾了 K05 機器學習概論 — 跟你做的 LLM 微調有關，你會微調哪幾類模型？
      LLaMA 系列、ChatGLM、還是 BERT 那種？」
```

**indexer 提供**：
- profile payload 的 `all_k_pairs` / `all_s_pairs` / `all_a_pairs`（該 OCS 全部代碼池）
- 給 LLM 一個完整的 OCS 詞彙宇宙，從中挑選並提問
- 自訂內容如果是新 K/S（不在任何 OCS 池），LLM 可建議但需要使用者明確同意，並標 `custom=true`

---

### Round N：Gap detection

LLM 主動 probe 使用者可能漏掉的內容：

```
LLM: 「我注意到 OCS 標準裡這個職務通常會產出 O1.2.1 需求訪談紀錄文件 — 
      你會寫類似文件嗎？沒寫的話 JD 裡要不要省略這項？」
使用者: 「我會寫，但稱呼不一樣，我們叫『需求討論會議記錄』」

LLM: 「了解，那 JD 裡就寫『需求討論會議記錄』，OCS 對應 O1.2.1。
      還有，你選的兩份 OCS 都有提到 A04 謹慎細心 — 是這樣嗎？」
使用者: 「對，特別是處理客戶資料時」

LLM: 「補充記下：『處理敏感資料時特別謹慎』。最後一個 — 你提了 SQL 跟
      Python，但沒提團隊協作工具。你用 Git / Jira / Slack 這類嗎？」
使用者: 「Git + Notion」

LLM: 「Notion 不在 OCS 標準裡，但專案管理算 S07 專案管理能力 — 要把
      Notion 寫進 S07 嗎？」
```

**indexer 提供**：
- profile payload 的 `all_*_pairs` 讓 LLM 可以 cross-reference「OCS 有但使用者沒提到」
- block payload 的 output_pairs 讓 LLM 可以問「你會產出這類文件嗎」
- profile payload 的 a_pairs 讓 LLM 可以問態度相關問題

**Gap detection 的兩種模式**：
1. **正向 gap**（OCS 有，使用者沒提）：LLM 提示「是不是漏了」
2. **反向 gap**（使用者提了，OCS 沒有）：LLM 確認「這是不是公司獨有的」

---

### Final：JD 草稿生成

LLM 拿著使用者全部確認過的 atoms（task 描述 + K/S/A + 自訂項目）產出 JD 草稿。

**JD 結構範例**：

```markdown
# 資料分析師（金融科技領域）

## 職務概述
負責跨部門資料蒐集與分析，協助業務理解市場與營運趨勢，並支援 AI 應用
導入規劃。

## 主要工作職責

### T1 需求蒐集與資料盤點
- 與業務、PM 確認資料分析需求
- 盤點內部資料庫與公開資料集
- 撰寫需求討論會議記錄

[參考來源]
- SMS2512-002v1 AI 應用規劃師 / T1.2
- INM3513-009v1 資料分析師 / T1.2

### T2 資料處理與分析
- 使用 PostgreSQL / BigQuery 進行複雜查詢（含 window function）
- 用 Python 進行多來源資料整合與清理
- 建立可供報表與決策使用的資料集

[參考來源]
- INM3513-009v1 資料分析師 / T2.1

### T3 LLM 模型微調與部署（自訂）
- 微調 LLaMA 系列模型應用於內部問答系統
- 部署模型至生產環境並監控運行狀況

[參考來源]
- SMS2512-002v1 AI 應用規劃師 / T3.3（啟發）

## 核心知識
- K01 AI 技術基本原理（含 LLM 概念）
- K05 機器學習概論（特別是 fine-tuning）
- K11 資料處理與分析概念
- K17 系統整合方法（自訂補充）

## 核心技能
- S03 SQL 查詢能力（PostgreSQL / BigQuery）
- S08 資料整合與分析能力
- S10 AI 技術/工具應用能力（LLaMA / Hugging Face）
- S18 技術部署能力（Docker / K8s）

## 工作態度
- A01 主動積極
- A04 謹慎細心（特別處理敏感資料時）

## 任職條件
- 3 年以上資料分析或 AI 工程經驗
- 熟悉 Python、SQL
- 有 LLM 應用實作經驗

---
本職務說明書參考以下職能基準：
- SMS2512-002v1 AI 應用規劃師（v1, 2025/12/31）
- INM3513-009v1 資料分析師（v1, 2025/12/31）
```

**使用者最後 review**：可編輯任何文字，可移除參考來源標註，可換 JD 格式（招募版 / 內部版 / KPI 版）。

---

## 3. 各層 chunk 在這個流程的角色

| Chunk Level | 數量 | 主要用途 | 用於哪些 Round |
|---|---|---|---|
| `profile` | ~908 | 找候選 OCS（Stage 1 entry point） | Round 0-1 |
| `unit` | ~3,272 | 列工作選單 + 群組顯示 | Round 2 |
| `block` | ~8,689 | 細節訪談的證據 + 自訂內容匹配 + K/S/A 來源 | Round 3-N |

三層粒度不是冗餘，而是**對應顧問訪談的問題粒度由粗到細**：
- profile = 「你是什麼職位？」
- unit = 「你做哪類型的工作主題？」
- block = 「你具體怎麼做？用什麼工具？產出什麼？」

---

## 4. Indexer 責任界線（明確）

### 4.1 indexer 必須做的事

| 責任 | 為什麼 |
|---|---|
| 三層 chunk + Markdown render | 不同粒度對應不同訪談階段 |
| profile / unit / block payload 結構完整 | curator 拿到 hit 後不用再回頭查 |
| code-name pair 完整配對 | 防止 LLM 配錯代碼 |
| profile 含 all_*_pairs | curator 從完整詞彙池挑選或建議 |
| dense + sparse hybrid retrieval | 混語料命中（自然語言 + 工具術語） |
| source_file + source_json_hash | citation 與審計 |
| `is_current` 區分版本 | 避免推薦舊版 OCS |

### 4.2 indexer 不做的事

| 不做 | 原因 |
|---|---|
| LLM 對話 | 是 jobintel-ai 顧問端的事 |
| JD 文字生成 | 同上 |
| 工作選單 UI | UI 端組合 indexer 提供的 task list |
| 自動 follow-up 問題 | LLM 該即時生成 |
| 預生 follow-up 問題庫 | 限制 LLM 創意 + 維護負擔 |
| 自訂內容代碼產生 | 是 curator 的創作行為 |
| 使用者編輯狀態管理 | 是 consumer 端的事 |
| 多輪對話 state machine | 是 consumer 端的事 |
| 排序候選 OCS 是否最終呈現 | UI 端決定 top-5 vs top-10 |

---

## 5. 與其他模組的契約

### 5.1 indexer → jobintel-ai 端的契約

**indexer 保證**：
1. Qdrant collection 內每個 chunk 都有 `chunk_key` / `chunk_level` / `ocs_code` / `job_title`
2. block chunk payload 含 evidence 結構（indicator + output 配對清楚）
3. profile chunk payload 含 all_k_pairs / all_s_pairs / all_a_pairs（完整 OCS 詞彙池）
4. 所有 chunk payload 含 `source_file` 可回讀原始 JSON
5. payload index 涵蓋 `ocs_code` / `chunk_level` / `k_codes` / `s_codes` / `attitude_codes` / `is_current` 等過濾欄位
6. dense + sparse named vectors 都存在每筆 point

**jobintel-ai 端要做**：
1. 使用者描述 → embedding → hybrid retrieval（profile level）
2. 候選 OCS 排序 + UI 渲染
3. 多 OCS task pool 合併 + UI 渲染
4. 自訂項目 → block-level hybrid retrieval → 建議掛點
5. LLM 訪談 state machine
6. 使用者編輯狀態管理
7. JD 文字組合與輸出

### 5.2 UI 端契約

UI 端可以對 indexer 做的事：
- 直接呼叫 Qdrant REST API 用 collection
- 或經過 jobintel-ai 一層 wrapper

兩者都能滿足。實際選擇看 jobintel-ai 設計。
