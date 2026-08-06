---
title: AI 輔助主要職責（Duty）——機制分辨、reference 存取缺口與候選承載形狀（研究紀錄）
date: 2026-08-06
purpose: 為 AI-Duty 切片開 ADR 與 plan 的依據
---

# AI 輔助 Duty 研究紀錄

> **不重做的部分**：「由上而下 vs 由下而上 vs 混合式」已由
> [`2026-08-03-ai-conversational-job-analysis-discovery-route-research.md`](2026-08-03-ai-conversational-job-analysis-discovery-route-research.md)
> 逐條核對 iCAP／OPM／O\*NET 一手來源，並由 [ADR 0055](../adr/0055-hybrid-job-discovery-and-ttop-formation.md)
> Accepted。本研究**不重新論證方法論**，只處理「在現行碼上怎麼做」這一段。

## 1. 為什麼現在問這件事

owner 於 2026-08-06 提出兩個需求：員工應能**先做 Duty**，且 Duty 應有 **AI 輔助**。

第一項**今天就已經成立**：`DutyEditor` 獨立於訪談，員工開新文件後可以先建職責再訪談，
Duty 切片 T6 已交付。所以真正的新需求只有 **AI 輔助**。

而 AI 輔助 Duty **不牴觸任何既有裁決**——ADR 0055 決定 2 明文：

> 訪談開始時**可依職位範圍、既有 JD 與職能基準建立暫定職務框架**，但所有 Duty／Task 都只是可新增、
> 修正或否定的**假說**；參考候選不得冒充員工工作證據。

現況（Duty 純手動）是 Duty 切片 plan §4 選的**保守子集**，不是禁令。該節自己寫明
「若日後要翻案需先有真實使用摩擦的證據」。

## 2. Duty 切片 §4 的三個反對理由，逐一檢視

| 當時的理由 | 現在還成立嗎 |
|---|---|
| 1. ADR 0042 決定 7：「每個新增欄位都讓形狀離 A6 的已驗證配置更遠…只增加可機械檢查，或能直接診斷核心錯誤的欄位」。把 Duty 塞進 `task_analysis_result_v2` 是一大塊新的模型輸出面，無預算驗證 | **成立，但可規避**。該理由針對的是「擴充既有 Task Analysis 的輸出 schema」。若做成**獨立 operation ＋ 獨立 wire schema**（OPKS 的既有作法，ADR 0049），`task_analysis_result_v2` 一個欄位都不動，A6 的已驗證配置完全不受影響 |
| 2. 職責切分是純語意判斷（大小一致、跨公司共通），verifier 攔不住 | **成立，且無解**。這是 rubric 與員工審核的事，任何實作都改變不了。意味著候選必須由員工逐條決定，不能自動套用 |
| 3. 歸納 Duty 的前提是「跨敘事已形成穩定 Task」（ADR 0055 決定 4），目前沒有真人資料佐證 Task 的數量與穩定度 | **只對「歸納」成立，對「暫定框架」不成立**——見 §3 |

## 3. 兩種 AI-Duty 是不同的東西，風險與前提都不同

ADR 0055 與其研究把兩件事分別寫在**不同的步驟**，本 repo 先前的討論把它們混為一談：

| | (i) 暫定職務框架 | (ii) 歸納 Duty |
|---|---|---|
| 何時 | 訪談**開始前／初期** | Task 邊界穩定**之後** |
| 輸入 | 職位範圍、既有 JD、職能基準 reference | 已確認的 Task 集合 |
| 產出性質 | **假說**，待驗證清單 | 結構歸納結論 |
| 前提 | 無（不需要任何 Task） | **需要穩定的 Task** |
| ADR 0055 | 決定 2 | 決定 4 |
| 研究步驟 | 步驟 1「建立暫定框架」 | 步驟 4「歸納 Duty 並讓使用者確認」 |

owner 要的「先做 Duty」對應 **(i)**，而 (i) 剛好**繞開 §2 反對理由第 3 點**——暫定框架根本不是歸納，
不以 Task 穩定為前提。

**這兩者不應該在同一個切片一起做。** (ii) 的價值與可行性取決於真人訪談究竟產出多少 Task、
有多穩定，那是 R9 pilot 才會知道的事。

## 4. 實測：`app/job_analysis` 對 reference 的存取是零

```bash
grep -rn "knowledge_http|KnowledgeHttp|indexer" apps/api/app/job_analysis/ --include="*.py"
# → 無任何結果
```

`app/job_analysis/providers/` 底下只有 `openrouter.py` 與 `openrouter_evidence.py`。
`app/job_analysis` **從來沒有讀過任何 reference**——現行 Task Analysis 與 OPKS 的 context packet
都只投影員工自己的材料。

而 reference 基礎設施本身是**真的存在且有資料**（2026-08-06 實測）：

| 項目 | 實測值 |
|---|---|
| 官方 OCS 來源 JSON | `apps/ocs-indexer/data/jd-json/` 共 **908 個檔** |
| Qdrant collection | `ocs_v4`，**9,449 points**，status `green` |
| 既有 typed client | `app/adapters/knowledge_http.py` 的 `HttpIndexerClient`：`search_occupations`／`search_tasks`／`occupation(ocs_code)`／`competencies(ocs_code)` |

**所以「依既有職能基準建立暫定框架」在資料層面是可行的，缺的是 `app/job_analysis` 到 indexer 的 port。**

注意 `HttpIndexerClient` 實作的是 `app/core/knowledge_dto` 的 port。`app/job_analysis` 的 AST guard
（`test_job_analysis_dependencies.py`）目前**不禁止** import `app.core`，但 greenfield 的既有慣例是
自帶 port（`application/persistence.py` 的 Protocol ＋ `providers/` 的 adapter），不共用舊 core 的型別。
沿用該慣例代價很低，且避免 greenfield 與 legacy core 產生新耦合。

## 5. 候選要承載在什麼形狀上——三個選項

Duty 目前是最薄的 domain 型別（`duty_id`／`statement`／`display_order`），
**沒有 evidence、沒有 lineage、沒有狀態**。這與 `JdTask` 一致（Current JD 是員工權威內容，
不像 Work Model `Task` 需要 `SupportLink`）。

| 選項 | 作法 | 代價 |
|---|---|---|
| **A. 輕量候選清單** | operation 回一組候選敘述，UI 呈現成可勾選清單；員工選取即呼叫既有 `add_duty()` | 最省。**不需要第三種 Proposal**。失去「AI 建議了 5 條、員工只採 2 條」的稽核軌跡（但 Journal 仍記錄實際建立的 direct edit） |
| **B. 第三種 Proposal** | 比照 `OpksProposal` 另建 `DutyProposal` 薄型別＋狀態機＋決策 route | ADR 0050 建立 `OpksProposal` 的理由是既有 `Proposal` 全綁 `TaskId`——同理 Duty 也不能複用。但 Duty 沒有 evidence／lineage／stale 語意，**整套狀態機大半用不到** |
| **C. 擴充既有 `Proposal`** | 把 Duty 塞進 `ProposalTarget` | ADR 0050 已明確否決過同型作法（「不塞進 `ProposalTarget` 也不抽通用 framework」） |

C 已被既有 ADR 排除。A 與 B 的差別是**稽核軌跡的粒度**：

- Duty 是**結構分組**，不是能力主張，不宣稱「員工會什麼」。ADR 0048／0049 那套 Evidence 白名單
  （只收 `employee_turn`／`direct_edit`、`proposal_decision` 不得為證據）是為了防止把「員工按了接受」
  記成行為證據——**Duty 沒有這個風險**，因為它不主張任何能力。
- 因此 Proposal 的重機具（stale、六態、edited 另鑄來源）在 Duty 上大半空轉。

**本研究傾向 A**，但這是取捨不是定論，留給 ADR。

## 6. 錨定風險：兩份權威文件都明說這是「未經證實」

ADR 0055 負面後果：「需要防止**參考 taxonomy 過早錨定**」、
「『先自由敘事、後顯示 taxonomy』目前是**待驗證的產品假說**，不得宣稱為官方已證明的唯一最佳順序」。

其研究紀錄 §邊界 更直接：「『taxonomy 過早顯示會 anchoring』在本次限定的官方資料中**沒有直接比較試驗**」。

**兩邊都沒有證據。** 這代表：

1. 不能以「錨定風險」為由否決 AI-Duty——那個風險本身沒被證實；
2. 也不能宣稱「先給框架比較好」——同樣沒被證實；
3. 因此設計上應**讓兩種順序都可行**：候選是可整批忽略的輔助，不是必經步驟。員工要空手開始、
   或先講故事再回頭要建議，都不該被擋。

O\*NET 的實務支持這個形狀：既有清單與開放新增**並存**，並鼓勵提交清單外的 write-ins
（研究紀錄「taxonomy／既有清單」列）。

## 7. 硬性約束（任何實作都必須滿足）

1. **參考候選不得冒充員工工作證據**（ADR 0055 決定 2）。候選在被員工接受前不是 Current JD 的一部分。
2. **不得自動套用**。職責切分是語意判斷，verifier 攔不住（§2 理由 2）。
3. **不動 `task_analysis_result_v2` 與其 Static Instructions**，否則觸發 ADR 0042 決定 7 的顧慮，
   且需要重新做一次付費模型複驗。
4. **不得生成 `職能基準代碼`／`職類別代碼`**（ADR 0052 決定 8）——即使 reference 帶回了官方代碼，
   那是 reference 的識別，不得寫進本文件的 header 欄位。
5. reference 命中的官方 Duty 敘述**可以引用**，但必須讓員工看得出「這來自參考資料，不是你說的」。

## 8. 開放問題

1. **候選形狀採 A（輕量清單）或 B（第三種 Proposal）？**（§5）
2. **第一版要不要接 reference？** 兩條路：
   - **(a) 不接**：只用文件既有的 `title` 與 `JdHeader.work_description` 讓模型產候選。
     零新基礎設施，但候選品質完全靠模型先驗知識。
   - **(b) 接**：新增 reference port ＋ adapter，用 `search_occupations`／`occupation()` 取官方
     Duty 敘述。有 908 檔／9,449 points 的真實語料，但多一條跨 app 依賴與一組失敗模式
     （indexer 掛掉時要能降級——ADR 0018 的 reference enrichment 可回部分結果 ＋ `meta.partial`）。
3. **(ii) 歸納 Duty 要不要一起做？** 本研究建議**不要**（§3），但這是 owner 的範圍決定。
4. **候選要不要保留「來自哪個官方基準」的出處**給員工看？若採 §5 選項 A，Duty 型別沒有欄位放它，
   要嘛只在 UI 暫存不落庫，要嘛替 Duty 加 provenance 欄位（後者會動 migration）。

## 9. 建議走向（供 ADR 引用，本研究不拍板）

- 只做 **(i) 暫定職務框架**，不做 (ii) 歸納。
- **獨立 operation ＋ 獨立 wire schema**，比照 OPKS（ADR 0049）；`task_analysis_result_v2` 一個欄位不動。
- 候選採 **§5 選項 A（輕量清單）**：員工勾選即走既有 `add_duty()`，不建第三種 Proposal。
- 第一版 **(2a) 不接 reference**，先用 `title` ＋ `work_description`。理由是它能在零新基礎設施下
  驗證「AI 建議 Duty 對員工有沒有幫助」這個核心問題；若答案是否定的，接 reference 也救不了。
  接 reference 留給第二版，屆時有真實使用回饋可以判斷值不值得。
- 候選一律標示為假說、可整批忽略；**不擋任何既有路徑**（空手建 Duty、先訪談後建 Duty 都必須照常）。
