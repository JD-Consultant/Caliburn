# JD App／LLM 顧問接線文件對齊工作稿

> **2026-09-16 最新效力：**Owner 已結束「等待 OpenRouter／A-B2 direct OpenAI／替代策略」三選一，採 [OpenRouter／Luna App-side continuity compaction](../2026-09-16-openrouter-continuation-compaction-design.md)。canonical 原文不裁，summary＋涵蓋邊界只作 request-only 衍生 Context，不是第二套 Memory；A 按文件保存，B2 按 attempt 保存且 stale 清空。2026-09-15 adapter contract 與真 smoke 的 `SERVER-UNVERIFIED` 結果繼續作 transport 證據，但下文所有「等待 Owner transport 裁決」均已 superseded。此決定不重做顧問 Prompt、Skills、Memory ABC、JD writer 或 publication，也不表示正式 dispatcher／完整 App 驗收已完成。

日期：2026-09-15
狀態：CURRENT ALIGNMENT／第一個正式組裝切片已完成、尚未提交；本稿同時是後續接線盤點入口，不是 production authority 切換證明。

> 2026-09-15 複核：產品目的以 [Owner 確認的核心目標](../../product-notes.md) 為準。本輪先完成文件對齊，再按該基線完成兩個最小組裝切片：單一 OpenRouter credential、OpenAI-only Luna 顧問 graph、正式 `serve` chat 啟用與 model client lifecycle；其後把 B1 strict structured extraction 收斂到同一 OpenRouter route，並讓背景提示從每次 runtime 取得文件與 publication scope。第三個窄修只校正 Memory 同輪讀取基準：C 成功後固定在其實際產生的版本，B2 較晚發布不會偷偷推進前景本回合；原 publication CAS 與 B2 stale→reload→recompute 流程沿用。完整離線回歸 2934 passed／315 skipped，Memory 套件 155 passed；唯一警告是既有 Starlette／AnyIO alias 棄用提示。精確真 PG 競爭案例 1 passed，驗明 B2 stale 後會依新版重新產生不同 Memory；上述回歸沒有正式 key、provider 或自然模型呼叫。後續複核已把 compaction 缺口由錯誤的「B2-only」擴回正確範圍：完成版 A 與 B2 都有 request-only 長上下文處理，B1 是有界來源抽取；目前 OpenRouter Chat Completions 接線遺失 A 的能力，B2 則仍留在 direct Responses。零付費 adapter contract gate 已完成：本輪 contract／相關回歸合計 23 passed（其中新 adapter 考卷 4），Q019 原正向基準另 1 passed。它證明 official OpenAI direct Responses 與 `ChatOpenAI Responses`→OpenRouter 客戶端候選都能完整往返，並精確重現 ChatOpenRouter 只丟 compaction content block、仍保留文字／工具／reasoning；B2 新回歸也驗明 stale 重整不會帶入舊嘗試的 opaque context。不把 mock 全綠外推成 OpenRouter 服務端支援。其後另經 Owner 授權執行 1 次真 OpenRouter smoke，已確認 route 與費用、但沒有產生 compaction item，結果仍為 `SERVER-UNVERIFIED`。這是 transport／adapter 相容性缺口，不重做顧問 prompt、Memory 或 JD。以下仍含正式 dispatcher、完整 App 驗收與淘汰項目，不能把這些窄修誤報成 H4／完整 App 已接通。

## 0. Owner 已確認、後續不得再誤讀的基線

1. Caliburn 是**一個 App／一個後端服務**，產品概念類似 Codex／VS Code，但編輯目標是 JD。人工與 LLM 可以使用不同 endpoint，兩者最終都必須呼叫同一套 relational JD application service、validator、writer 與 transaction。
2. 已完成、經自然模型反覆試用與 prompt 校準的 LLM 顧問是接線基準，不是待重新設計的元件。接線只應加入 JD tools、App 提供的當前文件 context 與正式 host 組裝；原訪談方法、prompt、Skills、Memory 判斷及 `request_memory_consolidation` 的模型可見描述／判斷時機／觸發語意預設保持不變。只有可重現的框架相容性或正確性問題才允許最小修正，且須保存差異與回歸證據。
3. LLM 顧問是 App 內已完成的專用功能，不是第二個產品或裸 API 呼叫。正式產品目標路徑是 **LangChain／LangGraph → OpenRouter adapter → OpenRouter → OpenAI-only provider → `openai/gpt-5.6-luna`**；禁止 fallback，日後由 profile 換模型，不改 JD tools 或業務邏輯。這條目描述目標 transport，不把 Q019 後期 direct OpenAI Responses 的自然 compaction 驗收改寫成 OpenRouter 已驗證。顧問自行決定何時呼叫 `request_memory_consolidation` 純通知；通知不直接執行 B1／B2、不寫 Memory，也不表示背景整理完成。
4. JD、canonical conversation、來源、案例／Semantic Memory 與 framework checkpoints 可以放在同一個 PostgreSQL 服務與同一個 App database；各類資料仍有自己的 owner／tables／contract，全部以 `document_id` 隔離。共用資料庫不表示 Memory 要套 JD CRUD，也不表示 framework 可以直接寫 JD tables。
5. 人與 LLM 都直接編輯同一份 current JD，不建立 candidate／approved 雙稿。每輪完成後顯示該輪 LLM 真正造成的 JD 差異。
6. 第一版不要求完整 JD 歷史、任意 revision diff 或整份舊版還原。**已實作且穩定的能力可以保留，不必拆除**，但不再是接線前置，也不繼續擴張或重構成通用歷史／復原系統。
7. 必要的撤回只撤回指定 LLM 回合對 JD 的整組效果；若已有較晚 JD 修改而無法安全補償，必須誠實失敗，不得覆蓋。原始對話、來源、案例、Memory、工作理解、checkpoint 與原回合紀錄永久不隨 JD 撤回而倒退；後續資料錯誤用更正流程處理。
8. 2026-09-15 曾把「Q019 後期用 direct OpenAI Responses 驗過」錯誤外推成「正式產品必須全線改成單一 `OPENAI_API_KEY`」，並依此產生一批未提交改動，現已撤回。錯的是 production transport 外推，不是既有 direct Responses 驗收本身；該批撤回改動不屬目前實作基線，也不能作後續採用證據。

## 1. 目的與範圍

### 最新對齊結論：已決語意與尚待核實的接線

Owner 已同意：同一個 App 管理各類資料，但操作同一類資料才共用該類業務邏輯。JD 走 JD domain，來源走 source contract，案例／理解走 Memory contract，checkpoint 走框架介面。這不要求新增對話資料庫或把已有 runtime 儲存重寫成 JD CRUD；目前 `ConversationSourceService` 透過 `AiRunCheckpoints` 讀取已保存訊息，邏輯責任分層不等於新增一套實體資料表。

目前產品目標沒有已知的待裁決矛盾；仍有工程事實需要核實，不能據此宣稱全部接線理解完成：

| 接線位置 | 本輪核實 | 接續要求 |
|---|---|---|
| 模型與金鑰 | 已把 relational App 的雙 provider 分歧改為單一 OpenRouter credential；共用 adapter 固定 OpenAI-only `openai/gpt-5.6-luna`、禁止 fallback，並把 OpenRouter 的 route／完成／截斷／拒絕證據保留給既有接受邊界 | A／B1 的 OpenRouter 基本 wire 已閉合；但 A 的 request-only compaction 未沿用，B2 仍是 direct Responses。長對話能力尚未閉合，不能把未知 pass-through、只補 middleware 或通用超限刪截當等價完成 |
| 顧問與 host | `serve` 有 key 時建立既有 `build_consultant()` graph、交給 `managed_app` 並明確啟用 chat；缺 key 時使用 inspection graph 且人工 JD 照常 | graph／chat host 已接不等於完成顧問長對話能力；先閉合 request／response item 往返，再補真 PG／新程序完整 App 旅程與最後一條有界自然 smoke。背景 dispatcher 另接，不把前景完成外推成背景完成 |
| JD 寫入 | LLM tool 使用 `owner.execute_foreground`，共用 owner 的 SQL 執行處最終呼叫 `storage.execute(intent)` | 保留不同的人工／LLM 輸入及准入方式，共用 JD domain 與保存規則；不要把兩種操作強行改成同一個 HTTP endpoint |
| source／Memory context | 已有按 document/run 建立的 session；背景提示仍可綁定建構時 document id | 正式組裝必須讓提示、Memory publication、source 與當前文件一致；可先完成內部介面設計，不把 registry 或 graph 數量交給 Owner 當產品選項 |
| B1/B2 | workflow factory 與 LLM 純通知工具存在；src 未找到日常入口建立 dispatcher 的完整組裝 | source、admission、Saver、Store、publication 必須在每次工作時綁定同一 `document_id`。安全回合／啟動恢復的 wake 只消費已保存通知或續作既有工作；沒有有效通知且沒有未完工作就不啟動 B1／B2。接上受控 callback 並核對批次接續與關閉時序，不先發明另一個產品層 registry |
| C | 前景工具轉往 `memory_repair` 並返回 consultant | 沿既有 Memory repair／receipt 邏輯；不可放進 B1/B2 dispatcher 當下一階段 |
| 重試與恢復 | OpenRouter SDK 與 LangChain model retry 都設為 0；App 的 foreground recovery 仍只作原結果對帳／收尾。App 先排空，再關閉 caller-owned sync／async model clients | 「已有 runtime」不能推出所有錯誤皆自動重試或重啟後自動續跑模型；後續以真新程序驗正式 host 組合，不改顧問既有故障語意 |

另更正先前 G6 的解讀：`consultant_tools._message()` 雖使用名為 Anthropic 的 serializer，但只取出 content／is_error 轉成框架 `ToolMessage`，這行本身不能證明請求送到 Anthropic。應核實 LangChain／OpenRouter 的 tool-result contract，不先宣布 provider bug，也不以此為理由繞過 framework。

後續驗收以產品旅程收束：人編輯 → LLM 讀取同一 JD 並修改 → App 回報真實保存結果 → 人接續修改 → 下一輪讀到變更 → 重開查回；再加上跨文件隔離、模型失敗但 JD 已保存、背景未完成與恢復案例。目前已完成前景組裝與離線回歸，尚未執行真 PG／新程序完整產品旅程或新的付費自然模型驗收。

目前按已對齊基線逐刀施工；第一刀只修改前景模型／credential／正式入口／生命週期及其測試與狀態文件。不刪歷史文件、不合併 worktree、不 commit／push。

本稿只審查 **LLM 顧問與新 relational JD App 之間的接線層**，包括：

- 接線研究與採用映射；
- runtime／tools／Memory host 的接合文件；
- H4 接續計畫與其結果敘述；
- 實作者依上述文件完成的入口與測試；
- 分支／worktree 的責任與採用範圍。

下列兩條開發基線先視為 Owner 已確認且不在本輪重新審判。它們是**同一個 JD App 的兩條開發線**，不是兩個要合併的產品：

1. App 內專用的 LLM 顧問 runtime／功能：使用 LangChain／LangGraph framework，經 OpenRouter 的 OpenAI-only route 執行 `openai/gpt-5.6-luna`，並包含 agent 執行、工具、context、checkpoint／狀態、錯誤處理、有限重試與恢復等責任；自然模型試用與 prompt 校準已完成。它 only for this App，不是通用顧問產品，也不需要抽成其他產品的共用服務。
2. App 的 relational JD 核心：關聯式資料庫、JD authority、編輯／保存設計及主要施工基線大致正確；這條線施工時暫時不含 LLM 功能。

因此本輪不重新選模型、不重做 prompt、不重新研究 relational JD schema，也不把接線問題誤做成「合併兩個產品」或新的通用 Agent 平台。接線的意思是：讓同一個 App 在正確入口使用已完成的 LLM runtime，沿既定 runtime 生命週期執行，再由 App 使用自己的 context、JD writer、保存與對外狀態完成一條流程。

## 1.1 產品關係的明確補充

```text
同一個 JD App
├─ relational JD 核心功能
└─ App 內專用的 LLM 顧問 runtime／功能（only for this App）
```

`codex/analysis-only-agent` 是 LLM runtime／功能的隔離開發／驗證工作區，不代表另一個要獨立部署或整包合併的產品。它提供已完成的 Luna、prompt、顧問方法、runtime 行為與自然模型證據；新 App 要依接線契約接入正確的 runtime 邊界，不是繞過框架直接呼叫 OpenAI API，也不是只複製模型結果。

這個功能的責任邊界應先理解成：

```text
JD App
  ↓ 交給專用 LLM runtime：context、run、工具、checkpoint、錯誤／重試／恢復
LLM runtime
  ↓ LangChain／LangGraph 的 OpenRouter adapter
OpenRouter（固定 OpenAI provider、禁止 fallback）
  ↓
openai/gpt-5.6-luna
```

OpenAI 是 OpenRouter route 選定的模型 provider，不是 App 應直接綁定的 transport。後續審查要確認接線是否接到 framework runtime 的正式入口與生命週期，而不是只確認 `ChatOpenAI` 或 `OPENAI_API_KEY` 存在。

因此後續審查要問的是：

- App 是否在自己的日常入口呼叫這個內部 LLM 功能；
- App 是否提供正確的 JD／對話／Memory context；
- LLM runtime 的執行結果、錯誤與恢復狀態是否正確回到 App；
- 成功的 LLM JD 操作是否回到 App 自己的 relational JD authority；
- runtime 是否負責模型執行的錯誤、有限重試與恢復，而 App 是否負責 JD domain authority、保存、當輪變更與對使用者呈現的結果；
- 是否錯誤地把 LLM 做成獨立產品、通用平台、第二個 JD writer 或另一套資料權威。

## 1.2 Owner 的最簡單產品模型

目前兩個主要部分都大致開發完成：

1. LLM 顧問 runtime 已完成；一開始刻意不讓它直接製作 JD。
2. JD App 的人工編輯系統已完成；先把人可以使用的 JD 編輯、驗證與保存做好。已完成的歷史／整份還原屬可保留的額外能力，不是現在重新設計的前置。

現在的工作是把兩者結合：

```text
同一個 JD App
├─ 人工編輯 JD
└─ LLM 顧問透過 App tools 編輯 JD
             ↓
       共用同一套 JD 業務邏輯
```

LLM 不直接寫資料庫，也不自行決定文件身分、版本、欄位關係、operation 或保存結果。App 提供：

- 可用的 JD tools；
- 當前 JD、對話與必要 Memory context；
- 業務驗證與共用 domain writer；
- 保存、必要內部版本、當輪實際變更與撤回結果；
- 錯誤、未知結果、停止與恢復的對外狀態。

LLM runtime 則負責模型執行生命週期、工具呼叫、context 接續、checkpoint、錯誤處理、有限重試與恢復。這個關係類似 Codex：模型提出編輯意圖，App／host 執行受限工具並回傳真實結果；本產品的編輯目標不是程式碼，而是 JD。

因此本案的真正整合驗收不是「模型能不能自己生成 JD」，而是：

```text
人編輯與 LLM 編輯
→ 使用同一組 JD operations／validator／writer
→ 產生同一種 current、必要 revision／snapshot 與 operation receipt
→ 都能被 App 顯示、查回、對帳；LLM 回合另可查看並安全撤回該輪 JD 效果
```

這是 App 功能整合，不是重做 LLM，也不是新增第二個 JD 保存系統。

## 1.3 Runtime 資料與 App 業務邏輯的分層

LLM runtime 可能使用 PostgreSQL 保存原始對話、案例／工作理解 Memory、checkpoint、工具執行狀態與恢復資料；這不代表這些資料都要套用 relational JD 的 CRUD，也不代表 framework 可以自行決定產品語意。

判斷原則是：**同一個實體資料庫可以共享，但資料 owner、業務責任與公開接點不能混淆。**

| 資料／責任 | 主要 owner | 人與 LLM 是否共用同一套 App JD 業務邏輯 |
|---|---|---|
| JD current、relations、operation，以及必要的 revision／snapshot | App relational JD domain | **是**。人工編輯與 LLM tools 都走同一 writer／validator／transaction；技術 snapshot 不自動形成新產品需求 |
| 原始員工對話與來源 lineage | 對話／來源 owner，透過正式 source API 提供 | 不套 JD CRUD；App 與 runtime 依 source contract 讀取，不複製成第二份原話 |
| 工作理解、案例與長期 Memory | Memory owner／Memory workflow | 不套 JD writer；App 提供正確 scope 與 context，B1／B2／C 依既定 Memory contract 執行 |
| checkpoint、thread、tool call、run 狀態與恢復位置 | LLM framework／runtime | 不套 JD domain；由 runtime 的 Saver／checkpoint API 管理 |
| 對使用者顯示的聊天、當輪 JD 變更／撤回、保存狀態與錯誤出口 | App adapter／API／Web | **是 App 的呈現與業務結果責任**，但不能把 raw framework state 當成 UI authority |

所以正確關係不是「LLM runtime 使用 App 全部業務邏輯」，而是：

```text
App domain rules
  ├─ JD 操作：人與 LLM 共用
  ├─ context scope／資料可見性：App 依契約提供
  └─ 對外結果／保存／當輪變更與撤回：App 負責

LLM framework／runtime rules
  ├─ agent loop、tool call、checkpoint、thread
  ├─ 模型錯誤、有限重試、resume／recovery
  └─ runtime 內部資料保存
```

框架會影響接法，但不會取代產品業務邏輯。尤其要避免：

- LLM tool 直接寫 JD 資料表，繞過 App domain writer；
- App 直接修改 framework Saver／Store 的內部資料表；
- runtime retry 重新執行已成功的 JD operation，造成重複版本；
- 把 checkpoint、Memory artifact 或 framework state 當成 JD current authority；
- 把舊 production runtime 的資料表／owner 定義直接套到新 relational App。

LLM runtime 的重試與恢復也必須和 App 的 operation idempotency、保存回執及未知結果對帳接起來；「模型重試」不等於「JD 寫入可以重做」。

目前 [`docs/design/consultant-runtime.md`](../../design/consultant-runtime.md) 的開頭已標明它描述的是舊 production runtime 與退役中的目標邊界，因此只能作歷史／責任研究參考，不能單獨取代新 relational App 的接線契約。

## 2. 目前確認的有效基線

| 內容 | 目前有效依據 | 判定 |
|---|---|---|
| LLM 顧問已完成 Luna 試用與 prompt 校準 | [`current-decisions.md`](../../current-decisions.md) 最新現況更正；`worktree-progress-map-2026-09-15.md` | 本輪基線 |
| 模型經 framework／OpenRouter 使用 OpenAI Luna，禁止 fallback | [ADR0060](../../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md)；[Luna smoke](../2026-08-14-gpt-5-6-luna-live-consultant-smoke.md)；[prompt cache smoke](../2026-08-21-consultant-prompt-cache-live-smoke.md) | 本輪 provider／adapter 基線；不採直連 `ChatOpenAI` |
| 新 JD App 是 relational 架構候選基線 | [`current-decisions.md`](../../current-decisions.md)；ADR0075 與其設計文件 | 本輪基線；正式 authority 仍依 ADR 狀態 |
| 顧問與新 App 尚未完成完整日常入口驗收 | [`worktree-progress-map-2026-09-15.md`](../../worktree-progress-map-2026-09-15.md)；guidance／Skills 結果 | 目前真正的整合缺口 |
| B1／B2 是 Memory 背景流程，C 是前景即時修補；皆為 App 內部能力 | H4／B1-B2 adoption 文件與現有 runtime contract | 不得擴大解讀成多產品或第二個 JD writer |

## 3. 初步發現的接線文件問題

### 3.1 已確定的過期／衝突文字

`docs/plans/2026-09-14-jd-h4-runtime-integration.md` 原稿曾寫「A 的 Anthropic 配置不動」。這與 2026-09-15 Owner 現況更正的 Luna／OpenAI 基線衝突；該計畫現在已加校正並把這句標成失效，不能再作目前接線依據。

這類文字要標為「施工期舊假設／文件過期」，不應改寫成顧問本身未完成，也不應重新把產品接回 Anthropic。

`docs/specs/2026-09-14-jd-consultant-openai-convergence.md` 正確排除了 Anthropic 產品路線，卻把「OpenAI provider」誤推成直連 `ChatOpenAI`／`OPENAI_API_KEY` 與移除 OpenRouter。它因此是**部分無效的施工期文件**：OpenAI Luna、單一顧問與無 fallback 的方向可保留；transport／credential／factory 的做法不得採用。該文件已在頁首加上警告。

### 3.2 同一文件不同範圍被混讀

H4 計畫中的 `0 provider`、假 key、Mock HTTP 是該階段的工程驗收條件；它能表示該隔離測試沒有付費呼叫，不能表示已完成的 Luna 顧問沒有做過自然模型試用。

後續審查必須把下列兩句分開：

- 顧問本體的自然模型品質／prompt 校準已完成；
- 新 JD App 的完整日常接線／入口驗收尚未完成。

### 3.3 局部組裝完成不等於產品入口完成

`2026-09-14-jd-consultant-guidance-and-skills-slice.md` 已記錄 `build_consultant()` 的 guidance、Skills、Memory guidance 與工具組裝完成，但同一文件也明確記錄 `build_consultant()` 尚未接進 `managed_app` 日常入口。

這應分類為：

```text
顧問接線元件完成
≠ 新 JD App 日常端到端流程完成
```

### 3.4 Evidence 的通過範圍不能外推

接線 evidence 中有固定模型、Mock provider、InMemorySaver、隔離 PostgreSQL、測試宿主及局部流程。它們各自只能證明記錄的那一段。

沒有明確的真實 App 啟動入口、真實保存責任與完整旅程證據時，不標成「整體已接通」。

## 4. Worktree 與分支的初步責任

| worktree／分支 | 本輪理解 | 使用方式 |
|---|---|---|
| `codex/analysis-only-agent` | 已完成的 Luna 顧問、prompt、自然試用與相關 Memory 證據線；後期另有直連 `ChatOpenAI` factory | 採用顧問行為、prompt、runtime 與自然模型證據；provider factory 必須對照 OpenRouter 基線，不整包搬入新 App |
| `refactor/current-only-architecture` | 新 relational JD App 及其接線施工線 | 作為 App 端實作對照基線 |
| `tmp/save-all-20260914` | 目前本地保全快照及整理文件所在分支 | 只作盤點與保存，不代表新的產品 authority |
| `codex/consultant-workspace-ui` | 較早的顧問／JD workspace UI 候選 | 只作歷史比較，不直接接回 |
| `spike/langgraph-document-authority` | runtime／Saver／Store authority 研究 spike | 只作研究依據，不直接取代目前 App |
| `codex/memory-routing-canonical-read-spike` | Memory read／routing 研究線 | 只核對來源讀取，不直接接回 |
| `codex/shared-current-jd` | 較早的 shared current JD 候選 | 只作歷史比較，不取代 relational App |

上述是用途分類，不是刪除或 merge 指令。每條線仍要以其文件、commit、測試與目前採用關係逐項核對。

### 4.1 實際 checkout 狀態

只讀檢查目前六個 checkout 後，狀態如下：

- 根工作區 `tmp/save-all-20260914`：目前只有文件對齊改動；2026-09-15 錯誤開始的直連 OpenAI 產品／測試改動已撤回，沒有保留為產品差異。
- `codex/analysis-only-agent`：目前可見 426 筆 tracked deletion，集中在 pytest 產生的 `catalog.db`／暫存樹，並伴隨目錄權限警告。這些不能直接視為產品刪除，也不能在未確認前清理或還原；先當作該 worktree 的未整理測試現場。
- `codex/consultant-workspace-ui`、`spike/langgraph-document-authority`、`codex/memory-routing-canonical-read-spike`、`codex/shared-current-jd`：tracked content 目前無差異；完整 untracked 掃描會遇到舊 pytest 目錄權限警告，因此不宣稱整個檔案系統絕對乾淨。「tracked 無差異」也不表示內容是目前產品基線。
- Git 的 worktree 狀態與文件中的功能完成狀態是兩件事；前者只回答「checkout 是否有未提交檔案」，後者要回答「這份內容是否仍被採用、是否完成正式入口」。

## 4.2 分支採用原則

目前先不決定 merge 順序。採用時要以最小責任切片為單位：

| 來源 | 可以拿來做什麼 | 不能直接推論什麼 |
|---|---|---|
| 顧問／Luna 線 | 核對模型組裝、prompt、runtime 行為與自然模型證據 | 不能推論新 App host 已接好 |
| relational JD App 線 | 核對 SQL domain、人工編輯、operation、必要 snapshots、當輪差異／撤回與 API | 不能推論 consultant 已接入；已完成歷史／整份還原可以保留，但不作接線前置 |
| B1／B2／Memory 線 | 核對 background contract、Saver／Store、admission、publication、recovery | 不能推論它們是使用者管理的 agent 或 JD writer |
| UI／workspace 候選線 | 核對交互與展示想法 | 不能繞過目前 App domain authority 直接採用 |
| research／spike 線 | 核對選擇理由與限制 | Proposed／spike 不等於 production authority |

在矩陣完成前，任何「整條分支已完成」的說法都降級為「該分支在某個時間點保留了一組工作成果」。

### 4.3 分支分歧程度與代表性提交

以 `refactor/current-only-architecture` 作為比較基準，現在各線不是小幅差異，而是不同責任與不同時期的保存現場：

| 分支 | 相對基準的狀態 | 代表內容 | 採用判定 |
|---|---:|---|---|
| `tmp/save-all-20260914` | 基準上多 2 個保存／文件提交 | `355c9240`、`5643d586` 的現況保存與路由文件 | 目前整理入口；不代表 production authority |
| `codex/analysis-only-agent` | 95 ahead／103 behind | 顧問自然模型／prompt 證據；另有 continuous working document、advisor tools、isolated editor 與 recovery | 顧問基線逐項採用；舊 editor 與暫存產物不整包採用 |
| `codex/consultant-workspace-ui` | 12 ahead／105 behind | workspace shell、inline current JD edit、AI review 與舊 endpoint 移除 | 只核對 UI 想法與交互，不直接取代 App domain |
| `spike/langgraph-document-authority` | 1 ahead／207 behind | framework 選型、LangGraph consultant runtime／authority 研究與 accepted runtime design | 研究／架構依據；不等於新 App 已完成接線 |
| `codex/memory-routing-canonical-read-spike` | 15 ahead／103 behind | canonical Memory read、bounded trial、Windows smoke 與 trial evidence | 只採用 Memory/source contract 證據，不整包合併 |
| `codex/shared-current-jd` | 18 ahead／107 behind | 較早 shared current JD、workspace、AI review／recovery | 舊候選基礎；除非新 App 明確引用，否則不回接 |

這個分歧數也解釋了為什麼「把全部 worktree merge 到 tmp」會造成誤導：會同時把研究、舊 UI、顧問本體、relational App 與測試暫存物混成一條歷史，反而更難審查。

## 5. 後續審查分類

每個文件、commit、實作點只使用以下分類：

1. **目前有效基線**：Owner 已確認，且沒有後續取代。
2. **元件已完成、入口未接**：局部測試通過，但尚未形成 App 日常流程。
3. **施工中**：計畫明確列為未完成，沒有完整結果證據。
4. **歷史或範圍限定**：在當時範圍內正確，但不能描述現在整體狀態。
5. **文件過期或互相衝突**：需由最新現況入口補充或標記，不直接拿來施工。
6. **實作偏離文件**：文件仍有效，但程式用了錯誤 provider、錯誤入口、錯誤 owner 或錯誤責任邊界。

## 6. 本輪採用的接線審查範圍

本輪已依下列順序完成第一輪文件／程式對照，結果見 §7–§13；其後只按差距清單完成前景組裝與 B1／runtime scope 兩個有限切片：

1. 接線文件是否仍把顧問誤寫成 Anthropic 或尚未完成；
2. App 啟動入口是否真的建立已完成的 Luna 顧問；
3. App 傳給顧問的 JD／對話／Memory context 是否符合既有設計；
4. 顧問結果是否回到 App 的既有 domain writer，而非新增第二份 JD authority；
5. B1／B2／C 是否按照文件定義作為內部 Memory 流程；
6. 固定測試、真 PostgreSQL、真新程序、自然模型與完整 App 旅程是否被正確分層；
7. 哪些文件只需補狀態標記，哪些實作真的做錯，哪些仍只是未完成。

後續施工仍不得依照任何單一過期計畫直接開始；先以 §13 的差距清單形成最小實作單位與驗收案例。

## 7. 目前程式與文件的第一輪對照

以下是第一輪盤點加上 2026-09-15 兩個實作切片後，依現有程式、測試與 evidence 能證明到的範圍。凡是寫成「元件存在」，都不等於正式 App 入口已經使用它。

| 接線面 | 目前可見實作／證據 | 目前判定 | 還缺什麼證據 |
|---|---|---|---|
| Luna／OpenRouter 模型 | `openrouter_model.py` 提供 App 共用 transport／route／terminal evidence；A 與 B1 都固定 OpenAI-only `openai/gpt-5.6-luna`、`allow_fallbacks=false`，credential 只剩 `openrouter` | **前景與 B1 基本 provider 組裝已閉合；A／B2 長對話門在真 smoke 後仍 `SERVER-UNVERIFIED`** | 真 smoke 已核 OpenAI Luna route，但 23,725 input tokens／12,000 門檻仍無 compaction item；transport／credential 選項見 §7.4，完整 App 自然驗收留到接法裁決後 |
| 顧問組裝 | `consultant_runtime.py` 建立 caller-owned sync／async clients 與既有 `build_consultant()` graph；App 排空後才關 clients | **正式前景 runtime lifecycle 已接** | 真新程序完整旅程；背景資源仍是下一切片 |
| App 日常入口 | `__main__.py` 有 OpenRouter key 時傳入真 graph 並設 `enable_chat=True`；缺 key 時傳 inspection graph 且 `False` | **入口條件已閉合並離線驗證** | 真 PG／新程序與自然 smoke，不把設定存在誤稱 key 一定有效 |
| LLM 編輯 JD | 顧問 tools 與 relational JD service／writer 的局部測試存在；evidence 也有 synthetic model 以 `jd_read → jd_create_task → final` 的流程 | **共享 writer 有局部證據，完整接線未驗收** | 人工編輯與 LLM tool 在同一正式 App 流程中產生同一種 current／operation／必要 snapshot 與當輪 change set 的完整證據 |
| App context | `memory_context.py`、source／Memory host 與 consultant guidance 元件存在；測試覆蓋部分 source、Memory、JD 讀取 | **元件與契約部分存在** | 正式 daily turn 傳入正確 document scope、對話來源、JD 狀態與必要 Memory，且多文件不串線 |
| B1／B2／C | admission、notification、dispatcher、bounded worker 等元件與隔離／PG 測試存在；`AiRuntime` 也接受 optional background。B1 provider 已收斂，背景提示已改從每次 runtime 取得 document／publication scope | **背景流程元件存在，正式 dispatcher 組合仍未閉合** | 正式 App 由受控 wake 入口按 `document_id` 綁定正確 source／Memory 資源，並證明 recovery／drain／publication 不重複；不增加全域 registry 產品概念 |
| runtime Saver／Store／Memory owner | host／runtime 的分層設計與部分開啟／關閉證據存在 | **責任方向一致** | 在正式 App 組合中確認 checkpoint、Memory、JD relational authority 沒有互相越權或雙寫 |
| 真實完整旅程 | 本切片為 synthetic OpenRouter transport 與全離線 App 回歸；既有隔離 PG／新程序證據尚未重新組成新的正式入口旅程 | **尚不能稱為 App 已完整接通** | 用專用 PG 做正式入口完整旅程，再以一條有界自然 smoke 驗真 route；自然模型品質與工程接線證據分開 |

這張表把目前問題收斂成一個核心判斷：**顧問本體與 JD 編輯本體不是主要未知；未知集中在正式 App host 如何組裝、如何傳 context，以及如何把工具結果收回同一個 JD domain writer。**

### 7.1 正式入口的實際呼叫鏈

第一個正式組裝切片後，程式的實際鏈條如下：

```text
__main__.py:serve
  → read_key("openrouter")
  → 有 key：open_consultant_runtime() → OpenRouter/OpenAI Luna → build_consultant()
            open_managed_app(..., consultant=graph, enable_chat=True)
    無 key：unavailable_consultant() + enable_chat=False（人工 JD 保持可用）
  → open_configured_host(..., consultant=...)
  → open_manual_host(..., consultant=compiled graph)
  → build_document_graph(consultant, PostgresSaver, PostgresStore)
  → AiRuntime(..., memory_engine=..., execution_enabled=enable_chat)
  → ChatService／HTTP API
  → 關閉時先排空 App，再關 OpenRouter sync／async clients
```

這說明幾個容易被混淆的事實：

- `build_consultant()` 與 `build_consultant_node()` 已由正式 `serve` 的 process-owned runtime 呼叫；沒有因接線重寫 guidance、Tools、Skills、Memory 或通知語意。
- `managed_app.py` 已收到正確 consultant 與 chat enable；目前仍缺正式背景 callback／dispatcher。
- `build_document_graph()` 讓顧問成為每個 document graph 的 child，並共用 host 提供的 Saver／Store。這不是第二個 writer；它是 runtime graph 的掛載方式。
- `AiRuntime` 在安全結束與 host recovery 後確實會呼叫 `_wake_background(document_id)`，但 `managed_app.py` 目前沒有把 `background=` callback 傳入，所以該 hook 會直接返回。這是「wake 點已寫、production composition 未接」的具體證據。
- `BackgroundAvailability` 也只讀取並把提示放進模型 context，不會自行啟動 B1／B2；即使把它接上，也不能把 context middleware 當成 background dispatcher。

因此目前最準確的描述是：**前景顧問 runtime 已進正式入口並通過離線回歸；背景元件仍未依責任契約接入同一條正式流程，完整 App 旅程也尚未驗收。**

### 7.2 多文件 context 的目前實作認知

這一點不能簡化成「建立一個全域背景 registry 就好」。目前程式已經有一部分正確的多文件隔離：

- `AiRuntime._run()` 依每次 foreground record 建立 `ConsultantContext(dataset_id, document_id, run_id, ...)`。
- graph 的 `thread_id` 使用該文件的 `document_id`，`ConsultantContext` 也會在模型呼叫前檢查兩者一致。
- source reader、Memory session、JD tool session、notice history 都以該 turn 的 document／run scope 建立；LLM 不自行填資料庫身分。
- 同一個 host／compiled graph 可以服務多份文件，靠 thread／context／signed reference 做隔離；這是 runtime 掛載方式，不代表文件共用內容。

2026-09-15 第二切片已把這個高風險點閉合：`build_consultant()` 不再接收組裝期 `document_id` 或 document-bound publication reader；`BackgroundAvailability` 每次執行只從 App runtime 發出的 `ConsultantContext` 取得 `document_id`，並使用本回合目前的 Memory 讀取基準。admission 與 conversation source 仍是可按 `document_id` 讀取的 App owner。模型不產生、不選擇也看不到這些資料庫身分；同一 middleware 以兩份 runtime scope 讀到兩份不同文件的反例已通過。這裡沒有新增共用 registry，也沒有把資料內容跨文件共用。

#### 7.2.1 Memory 版本：正式 head、回合起始證據與目前讀取基準

2026-09-15 Owner 校正後，這三個概念必須分開：

- **正式 publication head**：該文件目前最後成功發布的 Memory，可被 C 或 B2 推進。
- **`jd_memory_view` 回合起始證據**：記錄本回合開始時提供哪個版本；保持不變，用於 scope／恢復核對。
- **本回合目前的 Memory 讀取基準**：模型本回合一般推理與按需回查實際沿用的明確版本。開始時等於起始證據；只有準備修改 Memory 時的明確刷新，以及 C 保存成功後，才會更新。

一般回查不動態查 `latest`。背景發布新版不會中斷前景推理，也不會只固定摘要、細節卻改讀新版。C 準備修改時，後端先比較正式 head；若基準已過期，舊 patch 不得套用，工具回傳 stale 與明確新版，模型按需讀取相關內容後重新評估。即使事前已刷新，正式保存仍由 publication transaction 原子比較 `expected_revision`，不能用「先查版本再無條件寫」取代。

若 C 依 v4 先成功發布 v5，本回合基準更新成它**實際產生的 v5**。B2 依 v4 算出的候選隨後發布時必須失敗；既有 B2 graph 會重新讀取 v5、相關 repair receipts 與本次來源，重新整理後才可依 v5 嘗試發布 v6。不能把原 v4 候選只換成 v6 標籤。B2 成功發布 v6 後，前景本回合仍讀 v5；再次準備修改 Memory 才刷新，下一回合則從當時最新 head 開始。若 B2 先發布，C 對 v4 的保存同樣失敗並按新版重作，沒有「前景永遠優先」特權。

這沿用既有架構，不新增 registry、table、refresh tool 或另一套 publication。官方依據是 [AWS optimistic locking](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/DynamoDBMapper.OptimisticLocking.html) 與 [AWS conditional version control](https://docs.aws.amazon.com/amazondynamodb/latest/developerguide/BestPractices_ImplementingVersionControl.html) 的寫入時條件檢查，以及 [Anthropic Memory API](https://platform.claude.com/docs/en/managed-agents/memory) 在內容前置條件不符後重新讀取再處理的原則。本案的「只按需讀相關內容」與「前景本回合不追後續背景版」是 Owner 產品決策，不外推為供應商框架強制規則。離線回歸已驗 C applied v5 後即使模擬已重整背景發布 v6，同輪 read 仍是 v5；B2 測試則驗 stale 候選依 v4 失敗後會用 v5 的 guide／repair source 重新產生不同 Memory，而非換版號重送。相同 B2 情境的真 PostgreSQL 案例已用既有合成 PG18.6 fixture 重跑，1 passed。

### 7.3 B1／B2／C 的正確定位

目前正確理解如下：

```text
前景 A：員工對話／工作理解／JD tools
  └─ 可提出 Memory consolidation request，但不直接執行 B1/B2

前景 C：由顧問工具進入 Memory repair，再返回顧問
  └─ 沿 Memory publication／receipt 契約修補；不屬於 B1/B2 dispatcher

安全終局後或 host recovery：
  └─ BackgroundDispatcher.wake(document_id)
       ├─ admission 決定是否有固定 target
       ├─ B1 讀固定 source window、保存 extraction
       └─ B2 讀已完成 B1、發布 Memory
```

B1／B2 的成果是 Memory／工作理解，不是 JD current；它們不應成為第二個 JD writer，也不應由每一句對話直接觸發。`jd_memory_admission` 是背景准入／恢復責任的持久落點，不是 Memory 本體、原始對話或 JD current 的替代品。程式目前已具備多數這些零件與測試，但正式 App 尚未把 dispatcher、host 啟動恢復與日常 turn 的 wake callback 完整組合。

觸發責任要再分清：顧問判斷資訊累積足夠時呼叫純通知工具；App 只在回合已安全保存後辨識該通知。dispatcher 的 wake 可以在安全收尾或啟動恢復時重複呼叫，但它只依持久通知、publication cursor 與既有工作狀態決定下一步。安靜回合即使被 wake 也不開始新整理；同一個已通知的長 target 若尚有尾端，則可以在後續 wake 繼續分批，不要求模型重複通知。

### 7.4 A／B2 的長對話能力與 OpenRouter 相容性界線

2026-09-15 查閱 [OpenAI Create a model response](https://developers.openai.com/api/reference/cli/resources/responses/methods/create)、[OpenAI Compact a conversation](https://developers.openai.com/api/reference/java/resources/responses/methods/compact)、[OpenRouter Responses API overview](https://openrouter.ai/docs/api_reference/responses/overview)、[OpenRouter Responses basic usage](https://openrouter.ai/docs/api_reference/responses/basic-usage) 與 [OpenRouter Message Transforms](https://openrouter.ai/docs/guides/features/message-transforms)，並對照完成版 Q019、目前 App 與本機鎖定套件。不能再把這個問題縮成 B2-only。

四個責任維持既有分工：LangGraph Saver 保存每份文件的完整 canonical conversation；模型 request view 只為 token 壓力縮小當次 wire；版本化 `knowledge.md`／`guide.md` 保存工作理解；B1／B2 的 admission、checkpoint 與工具歷史保存背景執行狀態。Compaction 不取代其中任何資料 owner，也不新增對話摘要 Memory。

完成版 Q019 的 A 與 B2 使用的是 **Responses create 自動 compaction**：每次 `/responses` 帶 `context_management=[{"type":"compaction","compact_threshold":12000}]`；超過門檻時回應中出現 opaque compaction item，下一次 stateless input-array request 才從最新 item 接續。`native_context_view` 只縮小 request，不修改 canonical messages。這與獨立 `/responses/compact` 不同；獨立端點回傳的是完整 compacted output window，若未來改用，不能只套現在「從 inline item 切開」的 helper。

目前 App 的實際差異分兩層：

1. **A 的 App 組裝漏接既有 request-only view。**`build_consultant()` 沒有 `native_context_view`，所以 checkpoint 中的 conversation 目前會全量進模型請求。
2. **目前 OpenRouter adapter 本身不是 Responses item 往返。**`langchain-openrouter==0.2.7` 的 `ChatOpenRouter` 呼叫 `client.chat.send`；序列化 `AIMessage` list content 時只保留 `type=text` block，會丟掉 Responses `compaction` item。它另外保留標準 tool calls／results 與 OpenRouter reasoning 欄位，也支援自己的多模態輸入，因此不能把本缺口擴寫成「所有非文字資料都不支援」。App 的 `ReceiptChatOpenRouter` 只補 route、finish、refusal 證據，沒有改這個 message contract。

鎖定 `openrouter==0.10.8` 另有 beta `responses.send`，input union 也能表示 compaction item；但其 request signature 沒有 `context_management`、client 沒有 compact 方法、output union 也沒有 compaction item。這比單看 stateless 更精確：目前套件可描述某種 compact input，不等於能要求 provider 產生、自身解析並完成下一輪往返。`provider.only=OpenAI` 只限制路由，不會把 Chat Completions adapter 變成 OpenAI Responses 契約。

OpenRouter 的 `context-compression` plugin 是移除／截短 prompt 中段的另一種能力，不是完成版顧問的 opaque continuation。不能以名稱相近、未知欄位 pass-through、只補 `native_context_view` 或只改 `base_url` 冒充等價完成。這些證據也不需要靠付費請求重複確認；在找到受支援的生成與往返接點之前，盲送未知欄位不會形成可維護的 production 證據。

### 7.5 可直接沿用的元件與最小接法提案

下列完成內容直接保留，不重做：

- 顧問 prompt、三項 Skills、A 的 16／15 執行額度、Luna high／8192 profile、工具錯誤與終局判斷。
- canonical conversation 的 Saver、每文件 `thread_id`、完整原文與 source reference。
- `server_compaction_view`／`native_context_view` 的 **Responses inline 模式**語意，以及「canonical 不裁、wire 才裁」的既有測試；不得把 helper 單獨接到 Chat Completions。
- App 的 `ConsultantContext`、JD notice／source notice、固定 Memory guide 與按需 `read_file`／`read_conversation`；這些 system context 每次 request 重新組裝，不塞進 opaque item。
- B1 固定 target、有界 source windows、詳記／候選與引用；B1 不需要同一種長任務 compaction。
- B2 staged Memory、詳記按需讀取、16／15 額度、validation、CAS、stale→reload→重新產生；C 與本回合 Memory 基準規則完全不動。

現在缺的不是新 Memory 架構，而是一個能同時完成以下五步的 transport capability：送出自動 compaction 設定、收到 opaque item、框架無損保存、下一次原樣帶回、工具／reasoning call pairing 仍成立。最小工作順序如下：

1. **零成本 adapter contract gate 已完成。**`tests/test_compaction_adapter_contract.py` 只替換 HTTP 邊界，讓真 request 組裝、SDK／adapter 轉換、LangGraph Saver 重載與下一輪 request 都執行。同一考卷中，official OpenAI direct Responses 正向基準與 `ChatOpenAI Responses`→OpenRouter base URL 候選都完整保留 `context_management`、compaction／reasoning item、canonical 原文與工具 call/result；OpenRouter 候選也送出 OpenAI-only／no-fallback route。current `ChatOpenRouter` 的 characterization test 則精確證明 compaction content block 在 chat 序列化時消失，但文字、工具與 reasoning 仍在。鎖定 SDK seam 測試同時固定「input 可表示、request／output／compact 不完整」；B2 組合回歸驗明 stale 後的新 graph 不會重用舊嘗試的 opaque item。正式 A builder 目前是非串流，因此本輪不以非串流 fixture 冒充串流驗收；未來若開啟 streaming，須用同一契約補串流 item 組裝。測試保持全綠，不靠刻意紅燈表達已知差異。
2. **客戶端完整、服務端未確認的窄候選已完成真實 smoke。**OpenAI 官方契約清楚提供 inline `context_management` 與 standalone `/responses/compact`；OpenRouter 公開資料也確認 `/api/v1/responses` 使用 OpenAI Responses format，且可用 OpenAI SDK 替換 base URL。可是 OpenRouter 的 Responses request 文件與鎖定 SDK 都未列本案所需的 `context_management`，也未承諾產生及接受 inline compaction item。因此這個候選先只取得 CLIENT-PASS，不以 synthetic 回應或欄位能送出證明服務端能力。
3. **有界服務端 smoke 已執行，結果 `UNVERIFIED`。**Owner 授權最多四次／US$0.03，SDK 自動重試為 0；實際第 1 次即由 OpenAI route 的 `openai/gpt-5.6-luna-20260709` 回 HTTP 200，provider 回報 input 23,725／output 683 tokens、US$0.00556460。請求確實帶 `context_management` 12,000 且 input 已超過門檻，但 response output 為 0 個 compaction item，所以無 item 可進入保存、續用及工具配對後半段。依用量護欄停止，沒有為湊滿四次重送。精確證據見 [OpenRouter live smoke](2026-09-15-openrouter-inline-compaction-live-smoke.md)。
4. **這不是全域不支援宣告，但不足以正式改線。**本次模型／route／參數組合仍維持 SERVER-UNVERIFIED；HTTP 200、route 正確與一般回答成功不能代替 opaque item。若要繼續，Owner 需在等待可引用的 OpenRouter 等價契約、允許 A／B2 direct OpenAI Responses，或另驗新的長上下文策略間裁決；第三項是新設計。

因此目前狀態是 **adapter contract gate CLOSED；OpenRouter Responses 候選 CLIENT-PASS；真服務端 smoke UNVERIFIED；正式改線 PAUSED**。這不是要重談 Memory 或顧問架構，也不再缺同一候選的第一輪付費 smoke；現在真正需要的是 Owner 裁決 transport／credential 限制。正式 dispatcher 的文件與責任盤點可繼續，但在 A／B2 長上下文尚未閉合前，不能宣稱完整顧問已接通。

## 8. 已確認的程式／文件衝突

下列是原始衝突及第一刀處理狀態；已修項不再列為待做：

1. `consultant_app.py` 的舊 Anthropic docstring、`provider_keys.py` 的雙角色、前景 direct `ChatOpenAI` factory 與正式入口 unavailable graph 已在第一刀改成 Owner 指定的 OpenRouter 目標；第二切片再把 B1 改走共用 OpenRouter adapter。但前景 A 的原生 request-only compaction 同時遺失，不能再把這刀標成完整顧問 transport 已閉合。B2 暫留 Responses adapter，只因已驗 inline compaction 尚無等價 OpenRouter 契約，不代表正式決定回到雙金鑰或雙產品。
2. 正式 `serve` 現以 key 是否存在決定真顧問／chat enable 或人工-only；測試同時核 graph 身分、基本 Chat Completions 參數與關閉順序。這只證明短對話離線組裝，不是假裝已完成長對話 item 往返、真 route 或自然模型驗收。
4. `AiRuntime` 的 `background` 是 optional，`BackgroundDispatcher` 本身存在，但目前程式搜尋到的組裝主要在測試／支援碼；不能把 dispatcher 的單元／PG 測試外推成正式 daily background 已接通。
5. `BackgroundAvailability` 原本以 document id 組裝背景可用性，與共用 graph 衝突；已改成每次執行由 trusted runtime context／Memory session 提供文件與 publication scope，沒有 registry。
6. H4 計畫及部分 evidence 是按時間追加的施工紀錄；早期「未完成」與後來附錄的「元件已完成」可以同時正確，但只代表不同時間／範圍。必須以段落日期、結果與目前程式三者判讀。
7. 程式內所有 `Anthropic` 字樣也不能全部用同一個結論處理：研究文件中的 Anthropic 可只是外部研究來源；`change_transport.py`／`read_transport.py` 的 Anthropic 分支是舊 provider wire serializer。活躍 A／B1 組裝已是 OpenRouter；B2 仍是待相容處理的 Responses seam。必須依 import graph、正式入口與測試用途分層，不能用全域搜尋結果直接刪除所有文字。
8. `consultant_tools.py` 目前有一處工具結果封裝呼叫 `serialize("anthropic", ...)` 的實作線索；它可能只是內部訊息投影，也可能與 LangChain／OpenRouter 的 tool-result contract 不一致，需沿 framework adapter 與既有測試核實後才能決定是否修正。
9. 2026-09-15 曾按錯誤的直連 OpenAI 文件開始修改 App 組裝與測試；該批變更已撤回。現在的 OpenRouter 第一刀是之後依 Owner 基線重新施工的不同改動，不可混為同一批。

這些問題的共同特徵是「接線契約與目前實作不一致」，不是證明 Luna prompt、自然模型試用或 relational JD 設計本身失敗。

## 9. 目前不能直接下的結論

為避免再次誤解，以下幾件事在對齊完成前都不能直接做：

- 不能因為 `apps/api`、`apps/web` 看起來像舊架構，就現在整包刪除。要先核對哪些文件、測試、入口或正式決策仍引用它們；確認淘汰後再做有界、可復原的處理。
- 不能把 `codex/analysis-only-agent` 整條分支 merge 到 relational App。它同時包含顧問基線、舊 JD editor、測試／暫存產物與歷史施工，必須按 commit／責任切片採用。
- 不能把一個 worktree 的 HEAD 當成產品真相。產品真相要由最新決策、有效 ADR、當前設計與實測證據共同確認。
- 不能因為有 `ChatOpenAI`、有 provider key 儲存或有一個成功的 synthetic turn，就標記「LLM 已接入 App」。真正要驗收的是 OpenRouter profile／provider 限制、正式入口、runtime lifecycle、context scope、共用 writer、保存回執與錯誤／恢復。
- 不能把 framework checkpoint、原始對話、Memory artifact 或 background admission row 當成 JD current。它們各自有 owner，必須透過既定 contract 互相讀取。

## 10. 本輪「完整對齊」的完成定義

文件盤點作為每個接線切片的持續準入條件，必須能回答以下問題，而且每個答案都要有文件或程式證據：

1. **哪一份是產品基線**：Luna／prompt／consultant runtime 與 relational JD App 各自的有效來源，以及哪些舊文件只保留歷史。
2. **哪一份是接線契約**：App 如何建立 consultant、傳入 context、啟用 chat、接收 tool 結果、保存 JD、呈現狀態。
3. **誰擁有哪種資料**：JD、source／raw conversation、Memory、checkpoint／thread／tool call、對外 UI state 不互相越權。
4. **哪些元件真的完成**：分成完成本體、完成局部接線、完成正式入口、完成真實端到端，不用一個「完成」掩蓋四種狀態。
5. **每個 worktree 要不要採用什麼**：列出可採用的 commit／文件／測試、只供參考的內容、明確淘汰的內容；不以整條分支粗暴合併。
6. **哪些錯誤是文件錯、哪些是實作錯、哪些只是尚未做**：三者分開，才能避免修錯地方或重做已完成的 Luna／JD 本體。

## 11. 接線施工的交接順序

第一輪只讀盤點與文件標記已完成；前景與 B1／runtime scope 兩個切片也已依此順序施工。後續繼續沿同一交接順序，避免重新發散：

1. 以 §0、`docs/current-decisions.md` 與 ADR 0060／0075 為基線；不要從歷史正文重新推導 provider、JD 歷史或產品邊界。
2. 依 §13 把正式入口拆成最小施工單位：A／B2 長對話 transport capability、OpenRouter/Luna composition、chat 啟用、per-turn context、共用 JD writer、B1／B2 wake 與生命週期；B1 的有界抽取不與 compaction 綁成同題。
3. 長對話先使用 §7.5 的同一份 synthetic adapter contract 考卷；其他單位同樣先建立可重現固定反例，再做最小修改。不得整包 merge `analysis-only-agent`、不得只把 `native_context_view` 塞進 Chat Completions，也不得未經 Owner 直接把正式產品全線接回 direct `ChatOpenAI`。
4. 候選 transport 通過離線 item 往返與真 PostgreSQL 接線驗收後，才依 §7.5 的上限提出一條有界自然 smoke 核對真 route 與完整 App 結果；不重做 prompt 或廣泛品質研究。
5. 接線完成且 successor authority 確認後，才按引用盤點淘汰舊模組／入口；仍不以整個 worktree 或 `apps/api`／`apps/web` 目錄作粗粒度刪除單位。

## 12. 文件有效性矩陣（第一輪）

| 文件 | 目前用途 | 應採用的部分 | 必須防止的誤讀 |
|---|---|---|---|
| `docs/current-decisions.md` | 現況入口與路由 | 最上方 2026-09-15 更正：Luna／prompt 已完成，新 App 與顧問尚未完成完整日常端到端 | 同頁較早的「Anthropic 尚未選 model id／0 provider」是歷史，不得再作目前路由 |
| `docs/worktree-progress-map-2026-09-15.md` | worktree、分支與採用範圍入口 | 顧問完成線、relational App 線、接線尚未閉合及各 worktree 的角色 | 「有提交」不等於「已採用」；「保留」不等於「要 merge」 |
| `docs/specs/2026-09-14-jd-consultant-openai-convergence.md` | 部分無效的施工期 provider convergence | OpenAI Luna、單一 App 內顧問、B1/B2 與 C 是內部 Memory 能力、不要新增第二套 writer／authority | 直連 `ChatOpenAI`、`OPENAI_API_KEY`、移除 OpenRouter 的部分不得施工；頁首警告優先 |
| `docs/specs/2026-09-14-jd-consultant-guidance-and-skills-slice.md` | 顧問 guidance／Skills 組裝結果 | guidance、Skills、Memory guidance 與 tools 的局部完成證據 | `build_consultant()` 完成不能外推成 `managed_app` daily entry 完成 |
| `docs/plans/2026-09-14-jd-h4-runtime-integration.md` | R1/R2/R3 施工計畫與時間順序 | B1→B2→publication、背景准入、有限 wake、錯誤／恢復與接線順序 | 施工期的「A Anthropic」及早期「未完成」段落不能覆蓋最新現況；計畫也不是完成報告 |
| `docs/specs/2026-09-13-jd-consultant-b1-b2-adoption-mapping.md` | B1/B2/C 的採用映射與責任界線 | selected decision、Memory owner、new admission responsibility、不要整包採用舊 editor／host | 同文件保留的候選／待判定敘述不能當成已選方案 |
| `docs/specs/evidence/jd-b1-adoption/r3-notification-and-background-results.md` | R3 的分段實測紀錄 | notification、admission、dispatcher、bounded worker、新程序 recovery 各自的證據 | 本稿明示「未寫段落就是未做」；局部 recovery 通過不代表正式 App 已呼叫 `wake()` |
| `docs/specs/evidence/jd-relational-chat-http/http-results.md` | Chat HTTP 局部接合證據 | 原 run、保存回執、JD operation／必要 snapshots 與 synthetic model 的安全邊界 | Mock／synthetic／隔離 PG 不能標成自然模型或真實完整 App 旅程 |
| `docs/design/consultant-runtime.md` | 舊 production runtime／資料 owner 研究 | 可用來理解歷史 Saver／Store／source owner 邊界 | 它的舊入口與舊 authority 不能單獨取代新 relational App 接線契約 |

第一輪的結論是：文件不是全部錯，而是**同一 repository 同時保存了最新決策、施工計畫、逐段結果、歷史設計與實作者遺留文字**。下一輪要做的是加上「有效範圍／時間／是否採用」標記，不是把歷史證據刪掉。

## 13. 目前接線差距清單與第一刀狀態

| 編號 | 差距 | 類型 | 目前判定 | 是否需要新產品決策 |
|---|---|---|---|---|
| G1 | 正式 `serve` 沒有建立已完成的 Luna consultant，仍使用 inspection／unavailable graph | **第一刀已閉合** | 有 OpenRouter key 時建立既有 `build_consultant()` graph；缺 key 才用 inspection graph | 否，Owner 已確認 framework／OpenRouter／OpenAI Luna |
| G2 | 正式入口沒有明確啟用日常 chat；`enable_chat` 仍維持安全的預設關閉 | **第一刀已閉合** | 正式入口有 key 時明確 `True`，無 key 時 `False`；仍待真 PG／新程序完整驗收 | 否，除非要改產品啟用策略 |
| G3 | OpenRouter credential、Luna profile、runtime factory 與 App host 的基本組裝已接；A／B2 長對話尚待 App-side compaction 程式切片 | **Owner 已裁決 `CTX-C001`；G4 CLOSED／G7 OPEN** | 單一 `openrouter` credential、OpenAI-only／no-fallback、canonical 原文不裁；2026-09-15 adapter gate／真 smoke 只保留為 native item `SERVER-UNVERIFIED` 證據 | **依 2026-09-16 設計與 H4 R2C 實作 summary＋安全 boundary＋digest，修正 JdNotice Command 組合，完成 A／B2 受影響離線回歸** |
| G4 | `ConsultantContext` 已能按 document／run 組裝，但 `BackgroundAvailability` 的固定 document scope 是否可服務共用 graph 尚未被正式證明 | **第二切片已閉合；第三窄修校正同輪版本語意** | middleware 從每次 trusted runtime 取得 `document_id` 與本回合目前的 Memory 讀取基準；同一實例跨兩文件反例通過。C 成功後固定在 applied head，後續 B 發布不偷推基準；無 registry、模型不提供 scope | 否 |
| G5 | `AiRuntime` 有 wake 呼叫點，`BackgroundDispatcher` 有 bounded wake，但正式 `managed_app` 沒有把 callback／dispatcher 傳入 | 實作未接 | 先補 composition，不把 middleware 當 dispatcher | 否，已有 R3／ADR 的背景責任方向 |
| G6 | 工具結果封裝仍有 Anthropic serializer 線索，且 provider wire 測試同時覆蓋兩種格式 | **已核實，非 provider route bug** | 該 helper 只投影框架 `ToolMessage`；OpenRouter 真 adapter 的讀取→工具→結果→最終回覆離線路徑已通過。歷史 serializer 測試保留，不全域刪除 | 否 |
| G7 | 人工修改與 LLM tools 皆有局部測試，但尚未以同一正式 App 旅程驗證共同 current／operation／當輪差異與安全撤回 | 驗收缺口 | 補一條正式、可重現、可查回結果的 E2E；不新增第二 writer，不擴張完整歷史 | 否 |
| G8 | B1/B2/C 的局部／PG／新程序證據不少，但 production host 的啟動、wake、drain、錯誤隔離尚未全部接成一條旅程 | 驗收／組合缺口 | 分開驗證背景生命週期與前景回應，不把背景錯誤污染 JD turn | 否 |
| G9 | 舊文件、舊 provider docstring、舊測試 helper 與最新 Luna 基線同時存在 | **活躍 A／B1 基本入口已清理；A／B2 長對話 seam 與歷史仍保留** | App README、H4、本稿與活躍 helper需以 §7.4 最新校正為準；A 不能因 chat 已啟用就標完整，B2 docstring 明標尚未 convergence，不全域刪歷史 | 否 |
| G10 | `apps/api`、`apps/web` 與舊 worktree 是否可淘汰尚未完成引用／authority 盤點 | 淘汰風險 | 先列引用與仍被使用的接點，再做有界可復原淘汰 | 若發現仍有正式 authority，需先裁決 successor |

### 13.1 目前沒有發現的問題

截至這一輪，沒有證據支持以下說法，因此不把它們列為待修問題：

- 沒有證據顯示 Luna／prompt／自然模型校準需要重做。
- 沒有證據顯示 relational JD schema、人工編輯或既有 revision／history 實作需要重做或拆除；也沒有首版理由繼續擴張它們。
- 沒有證據顯示要把 LLM runtime 拆成 App 外的獨立服務。
- 沒有證據顯示要建立第二個 JD writer、第二個 JD current authority 或讓 LLM 直接寫資料表。
- 沒有證據顯示 B1／B2 應變成使用者可管理的多 agent；目前文件定義仍是 Memory 的內部背景流程。

這份差距清單完成後，才有安全基礎討論下一步施工；在此之前只應繼續補證據與標記文件狀態，不應開始「順手修 provider／重寫 context／合併整條分支」。

## 14. 舊 `apps/api`／`apps/web` 與新 App 的淘汰界線

這裡有一個需要明確分開的層次：

```text
正式 production authority（目前仍由既有 ADR／入口描述）
  apps/api + apps/web + job-analysis-contract

新 relational JD App 候選／整合施工線
  experiments/jd-relational-app
```

所以「新設計是目前要走的方向」與「舊正式目錄現在可以整包刪除」不是同一件事。現行進度地圖也明確要求先淘汰舊模組／舊入口，再做窄刪除；不能直接刪掉整個 `apps/api` 或 `apps/web`。原因不是要保留舊產品繼續開發，而是：

- 舊 production authority 尚未透過 successor ADR 完成切換；
- 舊文件、契約、測試與設計研究仍有引用，全部刪除會破壞審查鏈；
- 新 App 目前仍屬候選／整合施工線，先刪正式目錄會讓 rollback、差異審查與責任追蹤消失。

目前正確處理方式是：

1. 文件全部保留，對舊文件加「歷史／不作目前施工入口」的狀態。
2. worktree 只保留需要審查的現場；已確認無當前產品價值的舊審查 worktree 已改名 archive，沒有刪歷史。
3. 程式淘汰等接線差距與 successor authority 確認後，按模組／入口／測試做窄刪除，並保留可追溯提交。
4. 直到那時，`apps/api`／`apps/web` 只應被視為舊正式 authority 的保留範圍，不應被新接線繼續擴充，也不應被現在整包清掉。

## 15. 提交署名檢查

因為後續還要保存與提交，先把署名現況記錄清楚：

- Git 目前設定的 author identity 是 `ArIs0x145 <aris0x145@gmail.com>`。
- 對目前所有可見分支的提交 author／committer 做檢查，沒有發現以 `Claude` 作為 author 或 committer 的提交。
- 搜尋結果中出現的 `Claude` 是文件／commit subject 的產品或研究文字，不是提交署名。
- 本輪尚未提交這份工作稿，因此目前沒有新增提交署名可檢查。
