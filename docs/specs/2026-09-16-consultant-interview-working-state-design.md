# JD-R002／CTX-W001：主顧問訪談 Working State 設計

- 日期：2026-09-16
- Topic：`JD-R002／CTX-W001`
- Stage：**G4 WORKING DESIGN；Owner 已確認需要與設計依據，精確欄位待本輪複核**
- 範圍：A 主顧問在 Memory 尚未整理、對話尚未觸發 compaction，或一次無法問完所有問題時，如何跨回合保留目前重點與待追查事項
- 不取代：canonical 原始訪談、`MEM-L001` 的案例／工作理解 Memory、`CTX-C001` 的對話延續摘要、required clarification、JD relational authority、既有顧問 Prompt／Skills 與背景通知語意

## 1. 決定摘要

主顧問需要一份**文件／對話 thread scoped、可恢復、非權威的訪談工作狀態**。它只保存：目前正在釐清什麼、還有哪些重要線索或問題尚未處理、為何會影響工作分析，以及下一步需要取得什麼資訊。

```text
canonical 原始訪談          = 員工實際說了什麼（唯一來源）
Interview Working State    = 顧問目前在處理什麼、還要釐清什麼（暫時工作面）
continuation_compaction    = 長對話縮短後如何接續（有損延續摘要）
B1／B2 Memory publication  = 已整理、可引用、可持續修正的案例與工作理解
current JD                 = 人與 LLM 共用業務規則編輯的產品文件
```

第一版不新增 Agent、SQL table、獨立資料庫、第二套 Memory、訪談 Agenda／Todo planner、逐欄位完成清單或額外摘要模型。狀態放進 A 已有的 LangGraph typed state，由同一文件的 Checkpointer 保存與恢復；同一主顧問只在語意真的改變時，以一個小型批次工具更新。

它保存的是**高階、可檢查的分析結果**，不是模型隱藏推理、逐步 chain-of-thought 或完整分析草稿。

## 2. 產品需求先於欄位：從滿分 JD 與工作分析反推

### 2.1 滿分 JD 真正需要顧問持續追蹤的內容

[完整工作分析指南](2026-09-09-complete-work-analysis-guide.md)、[JD 欄位與寫作指南](2026-09-09-jd-field-and-writing-guide.md)、[客製化深度與訪談校準](2026-09-09-customized-jd-depth-and-interview-calibration.md)及[完整樣稿](2026-09-09-frontend-engineer-jd-sample.md)共同要求顧問不能只填表，而要逐步建立：

- 完整工作範圍：日常、週期、專案、事件、維護、收尾、低頻與支援工作；
- 每件工作的觸發／輸入、本人實際動作、判斷與選擇、產出／接收者及有效完成要求；
- 責任、權限、交接、條件、負荷、風險、例外、知識、技能與工具；
- 個別案例的差異，以及哪些內容有足夠依據成為穩定共同工作；
- 尚未知、互相衝突、被更正或仍需確認的部分。

訪談會採「先畫廣度地圖 → 選有價值案例深入 → 比較案例 → 回到全貌」的循環。員工一則回答可能同時帶出多個新線索，但主顧問通常只問一個有用問題。因此，即使第一回合尚無 B1／B2 Memory，也必須能把未立即追問的線索留下，後續再回來。

### 2.2 不把分析指南做成固定欄位表

上述工作面向是 Skill／分析檢核角度，**不是十四個必填 state 欄位，也不是問卷進度表**。同一未知可能同時影響責任、條件與成果；若拆成固定欄位，會重複、製造假完整度，並誘導顧問照欄位訪談。

Working State 只保存足以讓顧問恢復分析的最小語意：

1. 在談哪個工作主題；
2. 目前知道與不知道什麼；
3. 為何值得再問；
4. 下一步需要哪類資訊；
5. 有哪些可回查的原話／Memory／JD anchor。

是否已足以寫 JD 仍依既有質性規則判斷，不新增百分比、案例數門檻或每欄完成狀態。

## 3. 大廠官方資料能支持到哪裡

查閱日期：2026-09-16。

| 來源 | 官方事實 | 本案可採用的限制 |
|---|---|---|
| [OpenAI Model guidance](https://developers.openai.com/api/docs/guides/latest-model) | 長任務做 compaction 時應保留已完成行動、有效假設、識別、工具結果、未解阻塞與下一個具體目標 | 支持「對話摘要要保留進度」，沒有提供職務訪談欄位 schema |
| [OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) | compaction 用來縮小模型當前 context，讓後續 request 延續先前狀態 | 支持 compaction 與 canonical history 分離；不能證明摘要本身足以承接所有未問線索 |
| [Codex Memories](https://learn.chatgpt.com/docs/customization/memories) | durable memory 由背景流程整理；活躍或短暫工作不一定立即形成長期 Memory | 支持在背景 Memory 尚未發布時仍需要短期、可恢復工作面；不代表照抄 Codex 資料格式 |
| [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | compaction、structured note-taking、JIT retrieval 與 multi-agent 是不同且可組合的技術；長任務 notes 可保留進度與依賴 | 支持 working notes 不應被 compaction 或長期 Memory 混為一物 |
| [Anthropic Memory tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/memory-tool) | 應用程式控制持久儲存，模型可寫入並按需讀取，不需把全部內容常駐 context | 支持 App 持有狀態及漸進回查；沒有規定 Caliburn 的待訪談事項欄位 |
| [Anthropic Managed Agents](https://www.anthropic.com/engineering/managed-agents) | session 記錄與模型當下 context window 是兩件事；被壓縮移出 context 的訊息必須另有可恢復 owner | 支持 canonical 對話、working state 與 request projection 分權 |
| [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) | Structured Outputs 能限制輸出符合 schema，但官方明確提醒內容仍可能出錯 | schema 負責擋格式／enum 錯誤；「是否已回答、是否被 Memory 承接」仍須以產品不變量與情境測試驗證 |
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling) | 工具應可預測、避免可形成矛盾的參數，且程式已知的值不應再要求模型填寫 | state 儲存欄位不等於每次 Tool 都要完整重送；ID、scope、version、時間、預設值與 transition 由 Runtime 處理 |

跨來源可稱為共同原則的是：**可恢復的完整記錄、當前工作狀態／structured notes、compaction 與長期知識應分開管理，Context 再按需要組裝。**

下列不是大廠共識，而是 Caliburn 依滿分 JD 與訪談流程作出的產品映射：狀態要區分案例追問、跨案例比較、更正／衝突與工作範圍線索；優先順序要以員工要求、更正及 JD 影響判斷；B1／B2 Memory 仍是案例與穩定工作理解的唯一整理 authority。

## 4. 為何現有元件仍有缺口

| 現況 | 判定 |
|---|---|
| 新 App 的 `ConsultantState` 有 messages、JD／Memory view 與 AI run bindings，但沒有可跨回合恢復的 Focus／待追查狀態 | **真缺口**：第一輪尚無 Memory、也未 compaction 時，未立即追問的分析線索只能留在模型短期注意力 |
| 已完成的自然顧問主要依完整 conversation／provider continuity 與既有 Memory 工作 | 顧問能力可沿用，但改成 App-side compaction 後不能假定隱藏分析會被摘要看見 |
| 舊 `apps/api/app/consultant` 曾有 `InterviewWorkItem`、Gap、Focus 與恢復測試 | 可作工程反例與欄位證據；它混入舊 OPKS／直接 A 更新理解等前提，不能整套恢復為新 authority |
| 2026-08-27 研究拒絕另建 model-owned Agenda | 此裁決維持：本稿沒有順序、依賴、截止、完成計畫或第二個 planner；只補目前架構中尚未被即時 Memory 承接的暫時工作面 |
| `continuation_compaction` 會記住當前談到哪裡 | 它只在達門檻時產生，且只能讀到可見 messages；不能成為第一輪、多個未問線索或未觸發 compaction 時的唯一 owner |

這個缺口來自架構前提已改變：舊研究曾假定 A 可把重要未知隨本輪 Work Understanding 一起保存；目前確認的 `MEM-L001` 則由非每輪執行的 B1／B2 背景 Agent 維護 Memory。因此需要一個**發布前的暫時工作面**，但不需要復活舊 Agenda 或讓 A 再成為 Memory writer。

## 5. 第一版精確狀態

### 5.1 Root state

```json
{
  "interview_working_state": {
    "format_version": 1,
    "memory_basis_revision": 12,
    "focus_item_id": "wi_...",
    "items": []
  }
}
```

| 欄位 | Owner 與語意 |
|---|---|
| `format_version` | Runtime 填寫；只用於狀態格式遷移 |
| `memory_basis_revision` | Runtime 填入「主顧問產生這份 current Working State 時，實際可用來判斷的 Memory publication revision」；不是模型猜測的 latest，也不代表所有 item 已被 Memory 吸收或解決 |
| `focus_item_id` | 目前優先深入的一項；Runtime 驗證 ID 與 scope，主顧問可建議切換；可為空 |
| `items` | 尚需在訪談工作面保留的項目；只保存 current view，不累積已關閉項目的第二份歷史 |

`document_id`／thread 身分、checkpoint revision、建立時間、更新時間與 operation receipt 由 App／Checkpointer 擁有，不讓模型重複填進 payload。

### 5.2 Working item

```json
{
  "item_id": "wi_...",
  "subject": "重大故障初判與升級",
  "known_and_open": "已知本人先蒐集紀錄並做初判；尚不清楚哪些條件必須交主管，以及本人可否直接通知其他單位。",
  "why_it_matters": "會改變責任邊界、判斷權與有效完成要求。",
  "information_needed": "取得一個實際升級案例，確認觸發條件、本人決定與交接結果。",
  "status": "open",
  "priority": "high_jd_impact",
  "source_refs": ["source:..."],
  "related_refs": ["case:...", "understanding:...", "jd-task:..."]
}
```

| 欄位 | 用途與限制 |
|---|---|
| `item_id` | Runtime 產生的 thread-local stable ID；模型不可自行命名或跨文件引用 |
| `subject` | 短而可辨識的工作主題，不是 JD 標題或穩定工作理解 |
| `known_and_open` | 自足地寫出目前已知、未知或衝突；未知不得改寫成假設，已更正內容不得保留舊結論冒充現況 |
| `why_it_matters` | **可空。**只有影響不明顯、需說明為何值得保留，或選 `high_jd_impact` 時才優先填；不為了必填反覆寫「提升 JD 完整性」 |
| `information_needed` | 下一步需要的資訊／比較，不保存固定問句；實際問題由顧問依當輪語境自然表達 |
| `status` | `open`、`parked`、`captured_pending_memory`。目前焦點只由 root `focus_item_id` 表示，不再重複一個 `active` status |
| `priority` | 單選的**目前主要排序原因**：`employee_requested` ＞ `correction_or_conflict` ＞ `high_jd_impact` ＞ `normal`；同時符合多項時取最前者，其他脈絡留在文字。Tool 未提供時由 Runtime 預設 `normal`。required clarification 仍由既有 blocking 機制處理，不塞進 priority |
| `source_refs` | **選填。**只引用已存在的 canonical employee message／來源 handle；沒有來源的純未知可以為空，不能製造假引用 |
| `related_refs` | **選填。**已有案例、工作理解或 JD handle 時才提供，協助按需回查；只接受 Runtime 已提供且 scope 正確的 handle |

第一版不保存 `kind`。原先的 `work_lead`、`case_detail`、`cross_case_comparison`、`conflict_or_correction`、`scope_coverage` 會互相重疊，而且目前沒有必須依它執行的唯一行為：主題與追查內容由三個核心文字欄位表達；更正／衝突的載入優先度由 `priority` 承接；案例、理解與 JD 定位由 `related_refs` 承接。日後只有出現不能由這些資料完成的實際 routing 缺口，才用新證據重開分類，不先為了標籤要求模型判斷。

刻意不加入：confidence score、完成百分比、固定 JD 欄位矩陣、Skill ID、模型推理稿、逐步計畫、依賴圖、deadline、另一份 Memory version、員工可編輯旗標，以及完整問句歷史。

### 5.3 三個 status 的精確意義

- `open`：有價值且可在適當時機處理；若 `focus_item_id` 指向它，就是目前主要深入項。
- `parked`：顧問或員工明確暫時改道，問題仍存在但現在不追問；不是已解決或不重要。
- `captured_pending_memory`：本輪已取得足以停止立即追問的原話／更正，等待 B1／B2 publication 或明確 no-op 後對帳；不能當作 Memory 已更新。

當項目已被 Memory 正確承接、不再需要追問、已證實與工作無關，或被新版項目完整取代時，就從 current items 移除。其歷史仍可由 checkpoint／canonical conversation 查得，不在模型 context 中累積 `resolved` 墓碑。

### 5.4 儲存物件不等於每次 Tool 輸入

持久 state 可以有上述欄位，但模型建立新 item 時第一版只必填：

```text
subject
known_and_open
information_needed
```

`why_it_matters`、非 `normal` 的 `priority`、`source_refs` 與 `related_refs` 只在有實際內容時提供。`item_id`、初始 `status=open`、`priority=normal` 預設、文件 scope、Memory／checkpoint revision、時間與 receipt 全由 Runtime 產生或補入。

這裡的「必填／選填」是產品語意，不預先假定某個 provider adapter 的 JSON Schema 表達。若正式 strict schema 要求所有 properties 出現，選填內容就以 `null`／空陣列等合法空值表達；不能為了滿足格式，要求模型捏造無意義文字。鎖定 SDK／adapter 的實際 schema 仍在 G7 以生成結果與契約測試固定。

修改既有 item 時採 patch 語意：沒有出現在本次 patch 的欄位與沒有被點名的其他 items 全部保持不變，不能把「模型這次沒重送」解讀成清空或刪除。Stored state 仍使用完整 validated object；Tool input 則只表達本次改變。

## 6. 更新與恢復流程

### 6.1 同一主顧問更新，不新增第四個 Agent

A 取得一個小型、可選的批次工具，例如 `update_interview_working_state`。只有發生下列語意變化時才呼叫：

- 新發現一個不能在本輪立即追完的重要工作線索；
- 目前已知／未知、衝突、更正、優先順序或 Focus 真正改變；
- 員工回答「不知道」、暫時改題，或答案只解決部分問題；
- 新 Memory publication 已承接、推翻或改變現有 item，需要更新或移除。

工具一次可批次表達下列責任分離的 operation：

- `create`：只提交新項目的核心文字與必要選填內容；Runtime 配發 ID、預設 open，並可在同一 operation 指定新項目成為 Focus；
- `revise`：只提交 `item_id` 與真的有變化的內容 patch；不可同時自行改 `status`；
- `park`／`reopen`／`mark_captured`：只提交 Runtime 已提供的 `item_id`，狀態由 operation 唯一決定，不另收一個可能衝突的 `status`；
- `remove`：除 `item_id` 外，必須給單一理由 `memory_reconciled`、`no_longer_relevant` 或 `superseded`。`memory_reconciled` 必須引用本次 read session 實際讀過的同版 Memory handle；`no_longer_relevant` 必須引用主顧問採用的 canonical 員工回答；`superseded` 必須指向仍存在的 replacement item。Runtime 驗證 handle 已讀／存在、scope、版本及 replacement 等可判定前提，不能只因 publication 版本前進就接受移除；
- `set_focus`：指向一個現有 open item 或清空 Focus；不改 item 內容與狀態。

同一批次內，同一 item 最多一個 lifecycle operation；若同時需要補答案並轉成 `captured_pending_memory`，可以是一個 `revise` 加一個 `mark_captured`，兩者修改不同責任且原子套用。App 驗證 item ID、scope、enum、引用、transition 與大小，再透過同一次 graph state update 保存；非法組合整批不生效並回傳可修正錯誤。沒有變化就不呼叫，不為每回合固定增加模型 request，也不另開 planner node。

上述 remove guard 只能攔截「沒讀就宣稱 Memory 已承接」「跨 scope reference」「替代項不存在」等可判定錯誤，不能由 schema 保證模型的語意判斷正確；部分回答、無關 publication 與錯誤對帳仍必須用代表性情境測試驗收。

員工看得見的下一個問題照常留在 canonical conversation。Working item 保存的是「為何要問、需要取得什麼」，不是把上一輪句子複製成問題 queue。

### 6.2 第一輪沒有 Memory

```text
員工開始描述工作，帶出 A／B／C 三個線索
    ↓
主顧問選 A 作目前 Focus，只問一個問題
    ↓
Working State 保存 B／C 及 A 尚缺的資訊
    ↓
關頁／重開或下一回合
    ↓
Checkpointer 恢復 Focus 與所有未完線索，不依賴 Memory 或 compaction 已經產生
```

原始員工訊息仍是事實來源；Working State 只是讓顧問記得去哪裡回查與接下來分析什麼。

### 6.3 員工回答、改道與「不知道」

- 完整回答：更新 `known_and_open`；若不再需要立即追問，轉為 `captured_pending_memory` 或移除無關項。
- 部分回答：保留新已知與剩餘未知，可繼續作 Focus 或 park 後稍後回來。
- 「不知道／無法確認」：這是有效回答，不可反覆逼問；記錄目前不可確認的狀態及其影響，依重要性 park、轉交背景整理或觸發既有 required clarification 規則。
- 員工主動改題：員工要求優先，切換 Focus；舊項 park，不丟失。
- 明確更正：優先更新或新增 `conflict_or_correction` 項，保留更正原話 reference；真正案例／工作理解更新仍走 C 或 B1／B2。

### 6.4 與 B1／B2 Memory publication 對帳

Working State 不能成為 B1／B2 的事實輸入，B1／B2 仍只依 canonical source、現行案例／工作理解與其引用工作。它也不與 Memory 雙寫。

當 Runtime 發現目前正式 Memory head 已高於 `memory_basis_revision`：

1. Runtime 提供明確新 revision 與既有 Memory guide／按需讀取入口；
2. A 依相關 item 按需讀新案例或工作理解，不要求重讀全部 Memory；
3. A 判斷哪些 item 已被承接、仍未解、被推翻或需重開，再以同一小型工具更新；
4. A 以新版 guide 與按需讀到的相關內容重新考慮整份 current item map；Runtime 只在這次 Working State 更新成功時，把 `memory_basis_revision` 填成實際採用的版本。仍未解的 item 可以原樣保留，不等於已被 Memory 吸收。

只更新 revision 變數、未讓模型看到相關新版內容，不算對帳。反過來，背景 publication 的一般成功也不需要插入一段自然語言「背景結果」干擾當輪；只有版本／可讀入口、錯誤或需恢復的明確狀態由 Runtime 提供。

## 7. Context 與 compaction 如何配合

A 每個 model step 的常駐 orientation 只包含：

- current Memory／JD revision 等 Runtime metadata；
- `focus_item_id`；
- 所有 current items 的 `item_id`、`subject`、`status`、`priority` 小型目錄；
- Focus、員工明確提及、`priority=correction_or_conflict` 及本輪 deterministic refs 命中的完整 item。

其他 item 細節沿既有唯讀 context／VFS 投影按 ID 讀取。若目錄超過本輪預算，必須保留總數、分組與可讀入口，不能靜默截斷後讓顧問誤以為沒有其他事項；第一版不因此導入 embedding／RAG 或另一個搜尋 Agent。

`continuation_compaction` 可以描述當時的訪談目標、最後問題與近期進度，但它不是 Working State owner：

- Working State 在尚未觸發 compaction 時也存在；
- compaction 不需要複製所有 item 內容，下一次 request 由 middleware 重新注入 current orientation；
- summary 損壞或重做不會刪除 items；
- items 的來源仍指向 canonical conversation，不把 summary 當員工證據；
- 模型隱藏推理不保存；只有主顧問主動外部化的高階判斷能進 state。

不同 Agent 的 compaction profile 仍各自依任務設計：A 偏重訪談目標、目前 Focus、已確認更正、未回答事項與已完成 JD／Tool 結果；B1 偏重本批 canonical source、案例比對、staged 變更與驗證；B2 偏重固定整併任務、base publication、讀取過的相關案例／理解、staged 變更、衝突與下一步。三者共用安全切點與非破壞原則，不共用 Working State。

## 8. 與既有特殊狀態的責任邊界

| 既有狀態 | 與 Working State 的關係 |
|---|---|
| required clarification | 只有不取得員工明確決定就不能安全前進時使用；可引用一個 working item，但仍是獨立 interrupt／blocking authority |
| qualitative coverage／sufficiency | 從案例、工作理解、未知與 JD 反推的可推翻判斷；不是 writable working item，也不產生百分比 |
| B1／B2 notification | 主顧問依既有校準規則通知背景整理；不因 items 存在就由 Runtime 自動製造通知 |
| C immediate correction | 真正發布案例／工作理解修補；working item 只保留更正待處理／對帳狀態，不取代 C |
| JD pending／AI run | 顯示與撤回當輪 JD 效果；不承接訪談未知或 Memory 工作 |

## 9. 第一版禁止事項

- 不把 `items` 當成員工工作事實、B1 source、B2 knowledge 或 JD basis。
- 不讓 Runtime 從缺少某個 JD 欄位自動建立問題，也不要求依六章順序問完。
- 不新增 `InterviewWorkItem`／Agenda／PlanTask 的步驟、依賴與完成語意。
- 不把 14 個工作分析面向各做成一筆固定待辦，或用數量／百分比宣稱完整。
- 不保存 chain-of-thought、逐 token reasoning、模型內部信心或所有可能問題。
- 不因 working state 存在而每輪強制更新 Memory、強制 compaction、強制背景通知或多一次模型呼叫。
- 不把完整 stored item schema 原封不動當作每次 Tool 的必填輸入；不以漏傳欄位代表清空，也不讓 `park` 與另一個 `status` 同時表達同一 transition。
- 不在文件間共用 item、Focus、source ref 或 checkpoint。
- 不在未讀相關新版 Memory 時自動標示 item 已解決。

## 10. 代表性驗收

1. **首次訪談、無 Memory：**一則回答帶出三個工作線索；A 問一個，其餘兩個跨回合／重開仍可恢復。
2. **非 checklist：**缺少某 JD 欄位不會自動產生 item；顧問依案例與影響選擇問題。
3. **改道：**員工插入新主題後，原 Focus 可 park，新主題成為 Focus；稍後能返回且不重問已知內容。
4. **部分回答／不知道：**狀態區分已知、剩餘未知與不可確認，不把「不知道」當未回答而無限追問。
5. **多案例比較：**A／B／C 類似任務各自細節保留；comparison item 指向三者，但不先把差異合併成共同結論。
6. **明確更正：**更正優先，受影響 item 更新；未受影響工作不被重開；真正 Memory 修補仍走 C／B1／B2。
7. **Memory 晚到：**B1／B2 發布後，A 按需讀相關新版再移除或更新 item；只看到版本號不能自動關閉。
8. **Compaction：**觸發摘要前後及 App 重開後，Working State 相同；摘要未複製完整 items 也能由 checkpoint 注入恢復。
9. **大量項目：**Context orientation 不靜默遺漏，A 可由同一 state 的唯讀投影按需載入；沒有新增第二資料服務。
10. **文件隔離：**兩份 JD 的 Focus／items／references 不互相污染。
11. **零無謂呼叫：**普通回答若未改變工作狀態，不呼叫更新工具；第一版沒有固定 planner／summarizer step。
12. **非權威：**Working item 的文字不能直接通過 B1／B2／JD source validation；只有其 canonical source reference 可被回查採用。
13. **局部更新：**只 park 一項時不重送整筆內容；只 revise 一欄時其他欄位與其他 items 不變；`park＋status=open` 等矛盾輸入無法形成。
14. **移除保護：**未讀相關新版 Memory 時，`memory_reconciled` remove 被拒絕；不相關 publication 不會清掉 item；superseded／不再相關也必須提供可解析的替代項或 canonical basis。

## 11. 下一步與 gate

本稿先固定產品效果、欄位最小集合、Context projection、Memory 對帳與驗收，不授權把舊 consultant aggregate 整套接回新 App。

Owner 複核欄位後，G7 才做一個窄切片：

1. 在新 App `ConsultantState` 增加 typed `interview_working_state`；
2. 沿現有 Checkpointer／document thread 保存，不建表；
3. 增加一個小型批次更新工具與唯讀 projection，沿現有 scope／receipt／錯誤邊界；
4. 只補本稿 1、3、4、7、8、10、12 的最小反例；
5. 不改 Memory schema、B1／B2 publication、compaction transport、模型／credential 或已校準訪談 Prompt，除非測試證明精確接點無法表達既定效果，再先提出衝突。

完成此切片只代表 A 的訪談工作面可恢復，不代表 B1／B2 新分層 Memory、三種 Agent compaction 或完整 App journey 已完成。
