# 0071. 可修訂工作理解、最小 Context 與待審變更來源分層

- **狀態**：Proposed
- **日期**：2026-08-28
- **2026-09-02 重驗邊界**：本 ADR 仍是較早、未核准的產品／authority 候選，不是 Memory foundation 的施工依據。Memory 表徵、Store／checkpoint authority、revision／CAS、lineage 與 exact inventory 先依 [`2026-09-01-framework-independent-memory-contract.md`](../specs/2026-09-01-framework-independent-memory-contract.md) 及 [`2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md`](../specs/2026-09-02-memory-inventory-versioning-provenance-and-minimal-slice-revalidation.md) 驗證；若日後要 Accepted，必須先整體重寫與 ADR 0060 的 supersession，不能直接實作本文舊的 Case／Pattern／Unresolved 或 checkpoint authority 形狀。
- **Owner 對齊**：以 2026-08-28 最新逐項討論為準；owner 已確認「拒絕不要求理由，但要保留最小拒絕指紋，避免沒有新資訊時原樣重提」、「只有本輪新增／修訂理解會成為後續 JD 編輯的實際 basis 時，才先呼叫 understanding Tool；普通理解更新不固定增加 continuation」，並暫定接受「同一工作理解 collection 內保留具體案例、穩定工作模式、待釐清／矛盾，再由 Skills 形成角色層級 JD」、「案例→模式只保留最小 exact-revision 關係，員工更正先局部重看、必要時再依語意擴大」、「無 ID／Focus 的新訊息先看小型導航目錄，再由同一主顧問按需讀取精確紀錄」、「不數案例，依直接角色陳述或一次事件分流形成 Pattern」、「共同 application-owned envelope＋Case／Pattern／Unresolved internal variants；模型端改用小型 atomic tagged Tool variants，不再使用 flat all-required dummy wire 或固定巨型根表單」，以及「不另建 model-owned Agenda／Planning store，訪談導航由 Pattern／Unresolved／Focus／coverage 組成」。所有確認均可由後續研究、真實 transcript、成本／品質或實作證據推翻；本 ADR 在剩餘 JD 領域欄位與實作計畫收斂前維持 Proposed
- **研究**：[`2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md`](../specs/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md)
- **欄位契約稽核**：[`2026-08-28-llm-authored-field-contract-audit.md`](../specs/2026-08-28-llm-authored-field-contract-audit.md)
- **相關 UI**：[`0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md`](0070-consultant-workspace-ui-and-explicit-pending-edit-approval.md)
- **Supersedes when Accepted**：ADR 0048 決定 1–4 中把 `source_refs[]` 放進 OPKS 文件型別的實作形狀；ADR 0049 決定 1–9 中把 Evidence links／direct edit 當文件來源的部分；ADR 0050 的 `evidence_links[]` 與決定 5；ADR 0051 的 `deferred／edited／rejection_reason` 狀態與 payload；以及 ADR 0060 §4.2 決定 1／2／7、§5 決定 9／12、ADR 0064 決定 9／11、0066 決定 7／9、0069 決定 4／10 中 direct edit Evidence、逐項 Skill 證明、舊 review lifecycle 與可直接校準理解的相同部分；並澄清 Proposed ADR 0070 決定 10／14／16 的 provenance 與 interrupt 邊界
- **本輪重驗後沿用（可由 successor 推翻）**：ADR 0060 的 LangChain／LangGraph runtime、Saver／Store 單一 durable authority、AI 無 approved write edge、Task／Duty／OPKS Skills、deterministic validation、provider 可替換與 no-RAG；ADR 0064／0067 的 Deep Agents Store-backed JD workspace；ADR 0069／0070 的單一目前 JD 主編輯面、只讀核准基線、derived semantic review、atomic group、明確 Accept／Reject、active-run 單一 writer 與 approved-only export。沿用理由是本 ADR 的最新版機制比較仍判定其最符合目前產品，不是既有投入不可推翻；出現產品硬缺口時必須另開 successor 重驗整套替代架構

## Context

現行 runtime 已有 employee sources、`UnderstandingItem`、`GapItem`、`InterviewWorkItem`、required clarification、Store-backed JD workspace、approved baseline、review changeset 與 execution receipts，但其歷史演進留下數個重疊或相反的語意：

- `UnderstandingItem`、`GapItem` 與下一題各自保存未知，未回答事項可能只剩舊問句；
- 員工直接改 JD 會被鑄成工作來源，混淆「員工有文件編輯權」與「員工在訪談中陳述工作事實」；
- 模型在每個分析 basis 自報 `skill_ids`，即使 framework 已能記錄實際載入的 Skill；
- review 同時有 `deferred`、`edit-accepted`、拒絕理由與一般 pending，超過產品最新確認的「未處理就是 pending；編輯後仍待審；接受／拒絕」；
- 「AI 目前理解」曾被設計成員工可直接校準的卡片，但 owner 已確認員工只透過一般對話修正工作理解；
- Proposed ADR 0070 一方面需要可跨關頁恢復的 blocking confirmation，另一方面又把所有 `interrupt` 一併排除。

成熟框架已提供通用機制，但沒有替產品定義職務事實。LangGraph checkpoint 會按 thread 保存 graph state，支援 human-in-the-loop、conversation memory 與 fault recovery；Store 則保存 application-defined durable data。[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) 直接支持這項分工，但不會決定什麼算員工工作事實。OpenAI 與 Anthropic 也都把長期狀態、近期對話與當輪 Context 視為不同問題，而不是把整段歷史永久重播。[OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) · [Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

## Decision

### 0. Claude／Codex 是產品方法參考；框架選擇獨立裁決

Claude／Codex 只用來研究成熟 agent 產品如何組織共同工作面、實際差異審核、Tool feedback、可恢復修改、長對話 Context 與按需載入。OpenAI 將 Codex 的可重用核心描述為管理 Context、Tool、進度、失敗與核准的 harness，同時讓 host application 自己決定介面、可用資料、system of record 與 approval boundary；這正是本 ADR 採用的研究順序。它們不決定 Caliburn 應採哪一家 framework、哪一種 storage schema，也不把 Git／file／branch／staged 等 coding 名稱搬進職務分析產品。[OpenAI Codex agent harness](https://developers.openai.com/blog/codex-as-a-platform) · [Codex Code Review](https://learn.chatgpt.com/docs/code-review) · [Claude Code — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) · [Claude Code Checkpointing](https://code.claude.com/docs/en/checkpointing)

框架另依官方實際能力比較：它是否能以更好的效果、可靠性、成本與維護性承接 checkpoint、Store、VFS、interrupt、structured output、Tool 與 recovery。只有「產品方法成立」與「框架 primitive 確實適配」兩條證據都成立才採用；不得因參考某產品就選其技術，也不得因已選 framework 就讓其抽象反過來定義產品。

### 1. 四種產品事實分工，不再用 `Evidence` 一詞包辦

1. **員工來源**是 Store 中 immutable 的 employee conversation turn。它保存原文、speaker、時間與 source identity；歷史原話不被改寫。
2. **工作理解**是 Saver typed state 中可修訂的細緻 semantic collection，保存目前成立、待釐清、矛盾、已修訂／被取代與未定位線索。它不是聊天摘要，也不必長成 Duty／Task／OPKS。
3. **目前 JD**是 Deep Agents `StoreBackend` 中員工與 AI 共用的 current working copy；**核准基線**是 Saver 中 approved-only export authority。兩者不是兩個員工可編輯文件。
4. **待審變更**是 application 從 approved baseline ↔ current workspace 推導的 semantic group；不是模型填寫的 Proposal form，也不是第三份 JD。

LangGraph 的 typed checkpoint／Store 與 Deep Agents backend 承接 persistence、resume、VFS 與 read/write/edit/delete；Caliburn 只定義上述 authority、職務語意與 review grouping。[LangGraph Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) · [Deep Agents Backends](https://docs.langchain.com/oss/python/deepagents/backends)

### 2. 一般補充與更正只走一般對話

員工說「我剛才說錯了，是……才對」時只新增一則 employee turn。模型用本輪訊息、最短必要的近期雙向對話與相關工作理解判讀；application 不要求員工定位舊訊息，也不建立 `supersede／qualify／rebut` classifier、source picker 或「更正這段原話」按鈕。

「員工來源優先」精確表示 **source over inference**，不是 **latest source wins**：

- 可依期間、例外或範圍同時成立時，保存帶條件的多筆理解；
- 明確更正時建立新理解版本並保留新舊 source references，舊 employee turn 仍 immutable；
- 互斥但不明確時保存矛盾並詢問，不依時間、模型信心或 JD 現況猜答案。

Claude Code 與 Codex 的多輪互動支持使用者在同一 conversation 內 follow up／修正；官方資料沒有要求一般使用者先挑選要更正的歷史訊息。[Claude Code — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) · [OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state) 這只支持互動形狀；上述職務理解版本規則仍是 Caliburn 產品決策。

### 3. 員工直接編輯 JD 是 authority delta，不是工作來源

沒有 active AI difference 的普通員工編輯會立即更新 current workspace 與 approved baseline。它不自動產生 employee source、quote anchor 或工作理解；下一個顧問 run 只取得「自上次成功分析後的員工 JD delta」。

- 純措辭／排版調整不必改工作理解；
- 若 delta 新增工作事實或與理解衝突，顧問在一般聊天中詢問；
- 員工回答後，那則對話才成為 employee source 並修訂工作理解。

這保留員工文件 authority，也避免 application 把沒有口頭語境的文件文字冒充訪談證據。Web／server 仍以 revision、digest 與 server-derived delta fail stale，不信任 client 自稱 touched paths；`If-Match` 類條件更新是成熟的 optimistic concurrency 形狀，但不替產品決定語意。[RFC 9110 — If-Match](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match)

### 4. 工作理解承接來源；待審 JD 只引用工作理解

1. 已成立或互相矛盾的工作理解必須引用 employee source；需要精確支持時保存 deterministic exact quote anchor。
2. 純資料缺口本來就沒有原話，可沒有 source／quote，但必須明確寫出「不知道什麼、為何會影響分析」。
3. AI 待審 semantic group 必須引用 1～N 筆相關工作理解，另有一段簡短、員工可讀的「為什麼這樣改」。模型不複製完整對話，也不把理由寫入核准 JD。
4. 模型不再逐項輸出 `skill_ids`。實際載入的 Skill、版本、context refs、模型與成本由 framework callback／run receipt 自動記錄；deterministic verifier 驗證真實 receipt、來源／quote、stable references、revision 與 JD invariant，不接受模型自報作證明。
5. current／approved JD 的領域型別與 public contract 不保存 source ID、quote、AI reason 或 Skill ID；現行 `ApprovedOpksItem.evidence_source_ids` 與對應 transport 欄位退役。來源可追溯性由工作理解承接，待審理由只存在於尚未決定的 semantic review metadata。

LangChain Structured Output／Pydantic 可約束 effect schema，但 schema adherence 不代表內容正確；source resolution 與 domain invariant 仍需 deterministic validation。[LangChain Structured Output](https://docs.langchain.com/oss/python/langchain/structured-output) · [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

### 5. Accept／Reject 的產品狀態只剩最小集合

- **pending**：未操作自然留在 current workspace；沒有 `defer` 狀態或按鈕。
- **accept**：將 atomic group 的最新 working values 提升到 approved baseline；員工曾編輯綠色 after-state 仍必須另按 Accept。
- **reject**：整組還原 approved baseline，不要求理由，也不推測員工為何拒絕。
- **stale**：revision、workspace digest、dependency 或理解 basis 已改變，舊 command 不得套用。

接受後只保留最小 command receipt（command ID、group／payload digest、decision、revision 與完成狀態），供 idempotency、crash recovery 與 audit；員工畫面與核准 JD 不保留 AI 理由。拒絕另保留最小 semantic／understanding／boundary fingerprint：只有相同工作理解與相同變更仍成立時抑制原樣重提；只要相關工作理解、內容或邊界實質改變，AI 可重新分析並提出新建議。這筆 rejection memory 不是工作事實，也不推導拒絕原因。

LangChain HITL middleware 的 `approve／edit／reject` 是「暫停某個 tool call 等待決策」的通用 primitive；Caliburn 的多筆、可跨輪、文件層 semantic review 不由該 middleware 直接承接，但使用相同的人類決策原則與 LangGraph persistence。[LangChain Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)

### 6. 一般待釐清屬於工作理解；Focus 只是 runtime bookmark

- 刪除獨立可寫 `Gap` authority；一般待釐清是 unresolved／contradicted 工作理解的投影。
- 單純缺 O／P／K／S、coverage warning 或 validator error 是內部 Skill／deterministic signal；只有能轉成具體、可回答且會影響理解或 JD 的問題，才形成待釐清理解。
- ordinary follow-up 保存 underlying understanding reference；實際問句留 conversation history，不另建 question queue。
- `Focus` 的產品名稱是「目前訪談重點」，是可跨關頁恢復的 thread runtime bookmark；直接指向理解紀錄、待釐清問題或一次查詢選擇，不必綁 Task／Duty／OPKS，也不指向另一個可寫 `WorkScope`；它沒有 source，也不由員工直接編輯。
- 工作理解首先是給 LLM 跨輪使用的內部 durable state，第一版不必建專用員工 UI。若核心交付後仍有餘力且可廉價從同一 state 投影，可增加唯讀、可收合的「AI 目前的理解」進階檢視；員工仍透過一般聊天修正，不使用 confirm／later／direct-correction calibration lifecycle。

LangGraph Memory 把可更新 profile 與可增刪的 collection 都列為常見記憶形狀；工作理解採 collection，因為多件工作、矛盾、未知與版本不能安全壓成單一 profile。[LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) framework 提供儲存／更新 primitive；狀態分類仍由 Caliburn 定義。

### 6A. 工作理解採一份完整語意 collection；不預設引入 generic memory manager

工作理解不是一份會反覆整份覆寫的摘要，也不是只有 free-text `kind + text`、一句一筆的平面陣列。每筆必須在可獨立修訂的邊界內保留完整條件、行動、責任、判斷、順序、結果與例外關係；同一 LangGraph typed collection 目前區分三種語意角色：

1. **具體工作案例**：保存某次實際工作完整發生方式與 source linkage；案例不是正式 Task；
2. **目前穩定工作模式**：由員工直接說明或跨案例歸納出的持續責任／流程／變化範圍，並以最小關係指回支持案例或直接來源；
3. **待釐清／矛盾**：保存仍未知、說法不能安全並存或會影響後續理解／JD 的問題。

三者共用 stable identity、revision、source／quote 規則與 supersession lineage；它們不是三個 Store、三個 writer 或三份權威。internal domain 以共同 application-owned envelope 承載 stable／version identity、`active／superseded／retired` lifecycle 與 lineage，再以 Pydantic discriminator 區分 Case／Pattern／Unresolved payload；role 不可在同一 stable identity 內改變。Case 必須有 employee source；Pattern 必須有 direct employee source 或 `supported_by` Case；Unresolved 可用 `about` 指向 Case／Pattern，純缺口或未定位線索可無 source／about。`current` 是目前 active version，不是 role；矛盾以 Unresolved 表達，`unlocated／needs_reconciliation／coverage` 都是 projection，不成為持久 status。JD 仍由工作理解按需分析，資料可以 Task、O、P、K、S 或其他工作線索的任意順序出現。正式 Task 要抽取角色層級的一般工作活動，不能把每一個客戶、案件或專案直接各寫一條；但也不能為了通用而抹去員工確實只負責固定標的的事實。[O*NET 2025 Emerging Tasks](https://www.onetcenter.org/dl_files/EmergingTasks_RevisedApproach.pdf) 以 incumbents／experts 的具體 write-ins 找重疊、差異與核心元素，再形成足夠廣而仍具體的 Task；[OPM Assessment and Selection](https://piv.opm.gov/policy-data-oversight/assessment-and-selection/) 也把 critical incidents 當描述職務功能的案例，而不是直接等同正式 Task。

模型端不使用單一扁平、所有欄位 required、靠空陣列／空字串模擬 optional 的 effect。Work Understanding 以一個小型 atomic Tool 暴露 role／operation-specific tagged variants，讓 Case、Pattern、Unresolved 與 create／revise／retire 的非法組合在 schema 中不可表示；若實際 provider preflight 顯示單一 union 不相容，才依本輪可用角色動態曝光 2～4 個更小的 role-specific Tools，不退回 dummy wire。共同 envelope 中的 stable ID、revision、lifecycle、時間、run receipt 與 expected revision 都由 application 注入／產生；模型只填當次職務語意、必要 relation 與 exact quote。authoritative Pydantic type 同時產生 provider schema 與本地 validation，application 再驗 relation direction、source closure、exact revision 與 lifecycle 後原子提交。依據與方案比較見[欄位契約稽核](../specs/2026-08-28-llm-authored-field-contract-audit.md)。

`WorkScope` 不作另一個 LLM 可寫、具 stable identity 的 semantic owner。穩定工作模式承載工作語意；工作範圍、Context orientation 與進度由 current collection 的 pattern／case／unresolved 關係重建成 projection。尚未定位的線索保留在 unresolved／unlocated 投影，不強迫歸入 Pattern、Duty 或 Task。若日後固定長訪談證明 Pattern 數量過多、且更高層分組具備不等同 Pattern／Duty 的穩定 invariant 與可量測效果，才以 successor ADR 重開；UI 折疊或 filter 本身不構成新增 authority 的理由。Owner 於 2026-08-28 暫定確認本段；ADR 整體仍為 Proposed。

案例與模式的 active semantic relation 第一版只保留 `Pattern.supported_by → Case` 與 `Unresolved.about → Case／Pattern`；每個 reference 同時保存 stable record ID 與分析時的 exact version。相同 identity 的一般修正走 revision chain，只有 record boundary 真正 split／merge 才記 `derived_from` lifecycle lineage。員工更正仍是新的 immutable source turn：application 由 reverse index 找出直接依賴舊 Case revision 的最小候選集合，顧問再依新訊息語意決定 rebase、revise、追問、重整或擴大影響範圍；不得把「直接依賴」誤當語意傳播上限，也不得全域 invalidation。未完成 reconcile 時，只投影可重建的 `needs_reconciliation`，舊 Pattern 不供新的 JD edit 作 basis；不得建立 graph database、第二個 memory owner、固定第二模型呼叫或由 application 自動改寫 Pattern。Owner 於 2026-08-28 暫定確認本段；依據與方案比較見[研究 §15.15](../specs/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md#1515-案例模式關係與更正傳播最小-typed-dependency不做通用知識圖譜目前基線可推翻)。

當員工新訊息沒有 stable ID 或 Focus anchor 時，每輪 L1 Context 只常駐 current Pattern、active Unresolved 與未定位線索的小型導航目錄；Focus、required input、pending JD basis、JD delta basis、最近修訂紀錄及 direct dependents 等明確 refs 由 middleware deterministic 預載完整內容。其餘候選由同一主顧問透過現有 VFS `grep／read` 即時探索，實際改寫前仍須讀到並引用 exact current revision；找不到安全 match 就保留未定位或追問，不猜測關聯。第一版不固定增加 router model、embedding 或第二 Store index；只有真實長訪談證明目錄超出預算或語意召回反覆失敗，才以可由 checkpoint 重建的 derived semantic index 與 successor ADR 重開。Owner 於 2026-08-28 暫定確認本段；依據與方案比較見研究 §15.16。

Case→Pattern 不採固定案例數。員工明確陳述目前、本人負責的角色常態時，一則 employee source 可形成可修訂 Pattern；一次事件先保存為 Case，只有員工直接說明一般性、多個一致案例且無反證，或針對典型性追問後確認，才建立新 Pattern。一般性不明時保留 Case＋Unresolved；低頻但固定、重要的責任不得只因頻率被排除。新內容先對既有 Pattern 做 duplicate／overlap／new 語意判斷；成立 Pattern 不代表機械建立 Task，文件 Skill 仍須獨立判斷局部充分性與 JD boundary。第一版不新增 `provisional_pattern`、`confidence score`、固定 count gate 或 classifier model。Owner 於 2026-08-28 暫定確認本段；依據與方案比較見研究 §15.17。

訪談概況不顯示百分比或固定 stage。每個 stable pattern 只投影「待補充／目前足夠」兩個常態 coverage label；Focus、一般待釐清、`需要你的確認`、未定位線索與待審變更數分開呈現。`目前足夠` 是綁定 exact understanding basis、可被後續新來源重開的顧問判斷，不是員工已確認、永久完成或文件變更的前置 gate。projection 可在同一 checkpoint 以 basis digest 快取，但不得反向覆寫 Work Understanding 或成為第二 writer。Owner 於 2026-08-28 暫定確認本段。

### 6B. 不另建 model-owned 訪談 Agenda

第一版不建立 `InterviewWorkItem`、`AgendaItem`、`PlanTask`、另一個 planning store 或 Pydantic Planning dependency。一般尚待了解的事項由 active Unresolved 保存；已問未答仍保存 underlying Unresolved，問句留 conversation history；Focus 只是可切換的 runtime bookmark；coverage 是 derived projection；blocking ambiguity 才使用 LangGraph interrupt。每輪由同一主顧問依 current Pattern、active Unresolved、小型導航目錄、Focus 與本輪訊息選擇下一步，不固定增加 planner node、第二模型或 agent todo checklist。Owner 於 2026-08-28 暫定確認本段；依據與最新版 Pydantic Planning 能力校正見研究 §15.19。

[Pydantic AI Harness Planning](https://pydantic.dev/docs/ai/harness/planning/) 已具 stable ID、dependency、Postgres store 與 cache-safe reminder，但其產品責任是長時間 agent execution plan；[Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 也把 todo／structured notes 放在具清楚里程碑的長任務，並警告功能重疊的 Tool 集。這些成熟能力沒有提供本產品在 Pattern／Unresolved／Focus／coverage 之外的獨特語意，因此第一版不因框架存在而建立重複 writer。若未來出現可重現的長時間自主批次工作，才以 successor ADR 針對該不同目的重開。

[O*NET Content Model](https://www.onetcenter.org/content.html) 的 generalized／intermediate／detailed work activity hierarchy 有跨職業 taxonomy 與 Task linkage 的獨特用途，不能只憑「有階層」就推導本產品也要新增一層；其 [DWA methodology report](https://www.onetcenter.org/dl_files/DWA_2014.pdf) 反而要求相鄰層必須有不重複的內容。[LangChain long-term memory](https://docs.langchain.com/oss/python/langchain/long-term-memory) 已提供 namespace／key／filter／search 等索引 primitive；[Claude Code memory](https://code.claude.com/docs/en/memory) 則以精簡 index 導航、詳細 topic 按需載入。可轉移結論是「導航可投影、詳細語意維持單一 authority」，不是再建立一份 scope knowledge base。

[OPM Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 與 [O*NET Content Model](https://www.onetcenter.org/content.html) 支持同時理解工作內容、情境、活動、產出及能力關係；它們不替 Caliburn 定義 schema，也不要求內部理解長成 Duty → Task → OPKS。[LangGraph Memory](https://docs.langchain.com/oss/python/concepts/memory) 支持 semantic collection 與 hot-path update，但不定義職務語意。

[LangMem](https://langchain-ai.github.io/langmem/) 與底層 [Trustcall](https://github.com/hinthornw/trustcall) 是同目的的 framework 候選：前者提供 typed memory create／update／delete，後者用 JSON Patch 修訂既有 schema。它們截至本 ADR 補充日仍為 pre-1.0（LangMem `0.0.30`、Trustcall `0.0.39`），且通用 API 沒有直接保證 Caliburn 所需的 source／quote、版本 lineage、同批原子性、JD review basis 與單一 model-run 成本邊界。[LangMem PyPI](https://pypi.org/project/langmem/) · [LangMem Releases](https://github.com/langchain-ai/langmem/releases) · [Trustcall PyPI](https://pypi.org/project/trustcall/)

本輪機制稽核已足以判定：不把 LangMem／Trustcall 納入 production，也不為了「多用框架」預設執行一個無產品缺口驅動的 canary。Work Understanding 由主顧問產生 typed effects，application 以 Pydantic、deterministic gate 與 LangGraph checkpoint transition 原子 reconcile；這個薄 reducer 只保留 source／revision／lineage／狀態轉換等產品語意。只有真實 transcript 顯示 reconcile 品質、成本或維護性存在明確缺口時，才以固定失敗案例重開 evidence-triggered successor；屆時候選必須完整替代同目的機制，不得雙寫或保留第二 owner。

Claude／Codex 只作機制佐證，不作 domain framework：Codex 官方把必須遵守的團隊規則留在 `AGENTS.md`／checked-in docs，把模型自行整理的 summaries／durable entries／supporting evidence 放在另一個可檢視 memory layer；Claude Code 也把人寫的 `CLAUDE.md` 規則與模型生成的 auto memory 分開，並以小型 `MEMORY.md` index 常駐、topic files 按需載入。[Codex Memories](https://learn.chatgpt.com/docs/customization/memories) · [Claude Code Memory](https://code.claude.com/docs/en/memory) 這支持「產品規則、可修訂工作理解與 immutable employee sources 分層」，但兩者都沒有提供本產品所需的 typed work scope、source transaction 或 employee authority。

同理，[Codex Code Review](https://learn.chatgpt.com/docs/code-review) 反映同一 repository 內 AI／人類共同造成的真實 diff；[Claude Code Checkpointing](https://code.claude.com/docs/en/checkpointing) 將可復原的 agent edit checkpoint 與永久 Git 歷史分開。Caliburn 借用「同一 current workspace＋review projection＋可復原 receipt」的概念，不搬 staged／commit／file checkpoint 名稱，也不讓 coding agent 的工具限制決定 JD authority。

### 7. 「需要你的確認」使用 durable interrupt，但不做中途 steer

只有下列情況才建立 blocking required input：存在會導致不同理解／JD 的實質歧義或矛盾、猜錯會改壞成果、最小 Context 與按需舊來源仍無法解決、且只有員工能裁決。

1. 同一顧問結果先建立或修訂 1～N 筆相關工作理解；確認卡固定引用它們，不要求 Task、Duty、branch、quote 或 Skill ID。
2. 本輪可安全成立的理解與無關結果先 deterministic commit；相依 JD 分析停止。
3. 專用、沒有前置 side effect 的 wait node 呼叫 LangGraph `interrupt()`；員工可關頁，狀態仍由 checkpointer 保存。
4. UI 用「需要你的確認」卡取代 composer；有誠實離散答案時提供 2～4 個選項，永遠允許自行輸入；沒有合適選項就只顯示必填自由文字。第一版一次一題。
5. 員工答案保存為一般 employee turn，以 `Command(resume=...)` 恢復後啟動下一次正常顧問推理，先更新工作理解，再完成相依 JD 分析。

LangGraph 官方規定 interrupt 會保存 graph state、等待外部輸入並以 `Command(resume=...)` 恢復；resume 時 node 可能重跑，因此 interrupt 前副作用必須 idempotent。[LangGraph Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) Claude 的 `AskUserQuestion` 則支持少量選項與人類輸入的 UI 形狀；它不替 Caliburn 定義職務問題或 authority。[Claude Agent SDK — User input](https://code.claude.com/docs/en/agent-sdk/user-input)

本決定不引入執行中 queue／steer、rollback、parallel branch 或 Agent Server double-texting。`interrupt` 只發生在一個模型回合與 durable commit 完成後的安全 graph boundary，不是把正在生成的模型暫停在半句。

### 8. 每輪重建最小充分 Context，不重播完整 prompt

每次正常顧問 run 依序選取：

1. versioned 顧問規則與本輪目標；
2. 本輪員工完整訊息；
3. 解讀代名詞、更正與「剛才」所需的最短近期雙向對話；
4. 相關工作理解、unresolved／contradicted items 與目前訪談重點；
5. current-workspace orientation、validation 狀態與 compact pending provenance；
6. 自上次成功分析後的員工 JD delta、Accept／Reject 結果；
7. Skills 短 catalog；完整 Skill、舊來源、JD resource、review details 按需讀取。

不每輪傳入完整歷史、完整 approved＋current 兩份 JD、全部 pending diff、上一輪完整 prompt、已消耗 Tool output 或 chain-of-thought。prompt cache／provider conversation 可以作 transport 與成本優化，但不能成為產品記憶或 semantic authority。[Anthropic Context Engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) · [OpenAI Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)

Compaction 的邊界固定如下：employee turns 原文、完整 Work Understanding collection／revision／source basis、current JD、approved baseline 與 pending review 都不得作有損 compaction。每輪常駐的工作理解短索引只是 derived Context projection；相關完整 claims 必須直接載入，其餘可按需讀取，不能用索引覆寫本體。只有送入模型的較舊對話與單一 product run 的 Tool trace 可以縮減；先由 `ContextEditingMiddleware／ClearToolUsesEdit` 清除已消耗 Tool outputs，第一版預設移除 16k automatic `SummarizationMiddleware`，只有固定真實情境證明清理後仍超 budget 才重評 provider compaction。任何對話摘要或 opaque compaction item 都是 `authority=none` 的 transport，不得成為 employee source、工作理解或 JD basis。[OpenAI Compaction](https://developers.openai.com/api/docs/guides/compaction) · [Claude Code — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) · [Claude Code Memory](https://code.claude.com/docs/en/memory)

### 9. 每個工作回合先理解；JD 採有界 Tool-feedback loop

對員工仍是一個訊息對應一個顧問 product run，不採多 Agent。每個與員工實際工作有關的回合都必須吸收本輪訊息、必要近期對話、相關工作理解與 JD delta，重新理解／校正 Work Understanding，並產生 Focus／追問／required input 與可見回答；資訊沒有實質改變時可以不建立新 understanding version。任何 JD 工作都必須讀取已通過 deterministic gate 的 current Work Understanding，不得繞過它直接從原話產生文件。

本文的 `validated Work Understanding` 只表示 **已通過 strict schema、employee source／exact quote、stable reference、revision、lineage、狀態轉換與 domain invariant 的 current AI interpretation**；不表示員工已確認，也不保證模型理解是不可推翻的真相。互斥語意不能由 deterministic gate 裁決時，顧問保存矛盾／未知並依 blocking 規則詢問；後續 employee turn 可建立新版本或取代舊理解。[OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) · [OPM Job Analysis](https://www.opm.gov/agency-services/talent-management-services/assessment-and-evaluation/hiring-assessments/)

不建立 `should_edit_jd`、`值得進行 JD 分析` 或等價的 durable classifier。是否要改 JD 只有在顧問比較 validated Work Understanding、目前 JD 與相關 pending workspace 後才知道；預先分類會重複同一語意判斷。讀取／比較 JD 不需要 gate；模型實際呼叫 JD edit Tool 才表示要操作，沒有呼叫就是 no-op。

同輪若建立或修訂了 JD 所依賴的工作理解，application 必須先 deterministic 驗證並原子提交該理解，再把 canonical stable ID／revision 當 Tool result 回給同一 product run；後續 model continuation 才可按需讀 JD／Skill 並呼叫文件 Tool。若沒有本輪新工作事實，文件工作只依賴既有 canonical understanding，則可直接讀取／編輯，不強迫額外 understanding round-trip。這是有界 Tool-feedback loop，不是固定 Stage 1／Stage 2 pipeline，也不是開放式 agent。[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) · [OpenAI GPT-5.6 Model guidance](https://developers.openai.com/api/docs/guides/latest-model) · [LangGraph Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api#command) · [Anthropic Building Effective Agents](https://www.anthropic.com/engineering/building-effective-agents)

分流不靠另一個模型先猜「該不該改 JD」，而由 application 對實際 JD diff basis 做可驗證判斷：只引用既有 canonical understanding revision 時不要求額外 receipt；引用本輪 local understanding ref 時必須先有成功 Tool receipt。沒有 receipt 的 final result 負責提交本輪 effects（空集合表示已理解但無實質變更），已有 receipt 的 final result 不得重複提交。兩條都寫、兩條都沒處理，或讓未提交 local ref 支撐 JD，都拒絕該 run。

只有兩個文件相關 gate：依賴本輪理解的 JD 操作必須取得已提交的 canonical basis；具體 bounded change 必須通過理解 basis、blocking ambiguity、dependency closure、schema、read-set 與 document invariant 才能發布成待審變更。整體訪談是否「目前足夠」只服務進度與訪談規劃，不是每筆文件變更的前置 gate。[研究 §14](../specs/2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md#14-四項施工前缺口的補充研究2026-08-28)

目前採可推翻的局部充分性：不等待整份職務或整個工作範圍完成。某一局部理解若已有來源支持、足以形成具體且可審核的 atomic change，並且沒有影響該 change 的 blocking ambiguity，即可產生局部待審 JD；其他未知不連帶阻塞。這不是整體訪談完成宣告，後續理解仍可修訂 workspace 或再次提出 approved JD 變更。若實際 transcript 顯示造成過量 churn／review fatigue／stale，必須重開此門檻。

模型 calls／steps 是 runtime 成本與實作選擇，不是產品狀態，也不寫死成產品 invariant。沒有同輪理解依賴的回合不強迫成兩次 call；若外部驗證結果會改變下一個文件決定，就必須把 Tool result 回給模型。validated Work Understanding 是主要文件依據，本輪訊息與最短相關對話只作理解校正，舊來源／quote、JD slice 與完整 Skill 按需讀取；repair 與文件 pass 必須有小上限。

錯誤依「誰能真正修復」分流，而不是一律 retry 或一律問員工：[LangGraph Thinking in LangGraph](https://docs.langchain.com/oss/python/langgraph/thinking-in-langgraph) 的 transient／LLM-recoverable／user-fixable／unexpected 分類直接承接 runtime；[Anthropic Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents) 支持只回精簡、具體、可操作的 Tool diagnostics。

- rate limit、timeout 與暫時 provider failure 由 LangGraph `RetryPolicy` 小上限重試；
- strict output／source handle／quote／local ref／state transition／revision 等可修復錯誤，回最多五筆 typed diagnostic 給同一顧問；每個 authority stage 在整個 product run 最多一次 validation-driven model repair；
- deterministic error 絕不建立「需要你的確認」；只有員工才能裁決、且不回答就會實質改壞理解／JD 的 semantic ambiguity 才 interrupt；
- 第二次 repair 仍失敗或遇到 unexpected error 時，該 transaction rollback、run terminal、UI 解鎖；先前已安全提交的理解保留，JD 不留下半套變更。

普通員工可見回覆使用 assistant text，不再要求模型填固定 `ConsultantModelOutput` 根物件。current employee turn 的 source identity 由 `ToolRuntime` 注入且不進模型 schema；模型只挑選 exact quote 與職務語意 effects。application 做逐字唯一匹配：若同一 quote 出現多次，回 typed diagnostic 要求擴大 quote，不要求模型填 occurrence、Unicode offset 或 source UUID。只有低頻舊來源 recall 路徑才讓模型從已讀取結果選 model-safe handle。understanding Tool result 使用 `committed／no_change／repairable_error` typed shape；Skill、版本、模型、token、revision 與其他執行事實只由 framework receipt 記錄。required input 是模型依職務語意提出的獨立 effect，不是 verifier error。第一版不加入 critic model、semantic judge、confidence threshold 或 fuzzy quote matcher。模型可修復 Tool error 的 provider pairing、共同小型 envelope、錯誤分流、一次 repair 上限與 rollback／unlock 細節，以[欄位契約稽核 §19](../specs/2026-08-28-llm-authored-field-contract-audit.md#19-模型可修復-tool-錯誤與有界回饋協定owner-可翻案同意)為準，不得退回自由文字萬用錯誤或巨型 model-authored error schema。[OpenAI Function Calling](https://developers.openai.com/api/docs/guides/function-calling) · [LangChain Tools／ToolRuntime](https://docs.langchain.com/oss/python/langchain/tools)

理解更新與待審 JD publication 必須各自原子；文件工作失敗不得回退已安全成立的理解，也不得留下半套 JD。deterministic validation 只證明 source／quote、schema、stable reference、revision 與 domain invariant 有效，不把模型理解變成不可修訂的客觀真理。正式 eval 仍依 owner 裁決延後；施工只做 deterministic tests、三個固定情境的窄真模型 Luna Max proof 與 browser acceptance。

### 10. 名稱是產品投影，不是舊元件復活

產品第一版顯示「目前 JD」「目前訪談重點」「待釐清」「需要你的確認」與待審差異；「AI 目前的理解」只是可選進階唯讀 projection，不是交付 gate。禁止重新建立舊 `CurrentJd`／`WorkModel`／`GapStore`／`Proposal`／`Focus` writer 或 compatibility layer。實作名稱可以採 framework state／Store namespace／projection，只要達成相同行為且只有一個 authority owner。

### 11. Fresh-root hard cut 與範圍

本產品不搬舊 checkpoint／Gap／calibration／review lifecycle，不雙寫；開發資料依 fresh-root runbook 重建。第一版不接 RAG／Reference，核心 JD、Web 編輯與匯出均不包含 A／能力級別；也不做 auto-accept、多 Agent、正式 eval 平台或版本歷史 UI。

## Consequences

- 工作理解成為「員工說了什麼」與「JD 為何這樣分析」之間唯一可修訂 semantic bridge；JD 不再背負逐字 Evidence。
- 員工直接編輯 JD 不再偽造工作來源；代價是新增工作事實時要等下一輪一般對話確認，不能由 application 猜。
- 一般待釐清、工作理解與下一題不再有三套 durable truth；Focus 與 required input 仍是清楚分離的 runtime projections。
- pending review 只需 pending／accepted／rejected／stale 語意；編輯綠色 after-state 不會偷渡接受。
- 最小拒絕指紋避免無新資訊的原樣重提，又不把拒絕永久封鎖或誤寫成工作事實。
- framework 承接 persistence、interrupt／resume、VFS、structured output、context middleware 與 execution receipts；Caliburn 保留職務分析 Skills、source truth、semantic diff、dependency closure、deterministic verifier 與 employee authority。
- 工作理解可同時保留具體案例、跨案例的穩定模式與待釐清／矛盾，而不把訪談內部理解鎖死在當下 JD 階層；導航不再新增可寫 `WorkScope`，coverage 採可重建的質性 projection；案例→模式的 active relation 被限制為兩種 exact-version typed references，降低更正時全量重算與任意 graph 的成本，但模型仍須判斷語意影響是否超過直接依賴。
- 無 anchor 召回採小型導航目錄、deterministic preload 與同一主顧問按需探索，避免每輪全量 Context 或固定多一次模型／embedding 路徑；代價是必須量測目錄預算與真實長訪談漏召回，才能判斷何時值得升級 semantic index。
- Case→Pattern 依陳述語意與職務支持判斷而非數量門檻，能保留直接常態陳述與低頻重要責任，又避免把臨時事件一般化；代價是主顧問仍須判斷 ownership／typicality／scope，deterministic validation 只能約束來源、版本與關係，不能假裝證明職務語意。
- LangMem／Trustcall 不因品牌或 API 相似而自動成為 production authority；目前沒有真實產品缺口支持額外 canary，因此不引入。若未來由固定失敗案例重開 successor，候選必須完整替代同目的機制，不保留半套 adapter。

## Rejected alternatives

- **把員工直接編輯的 JD 文字自動鑄成 employee source**：文件編輯可能只是措辭，缺少訪談語境，會污染工作理解。
- **核准 JD 永久附上 quote／AI 理由**：員工已核准且仍可直接修改，這些資料會快速失真；來源應留在工作理解，理由只服務待審 UI。
- **拒絕後完全不留任何紀錄**：相同 Context 可能立即產生相同建議，讓員工反覆拒絕。
- **拒絕即永久禁止相似內容**：新資訊可能使原方向後來成立；只抑制同 basis、同 boundary、同 semantic change。
- **把所有未知變成選單 interrupt**：訪談會退化成 wizard；一般未知應留待釐清，只有 blocking ambiguity 才 interrupt。
- **完整 transcript／prompt replay**：隨訪談輪數線性增加成本與干擾，且把過時推論混入 authority。
- **第一版固定增加 router model、embedding retrieval 或第二份 semantic owner**：尚無真實長訪談失敗證明小型導航＋VFS 不足，先增加路徑會引入額外 calls、索引版本與刪除一致性；若日後由可重現 recall／budget 證據觸發，只能作 checkpoint 可重建的 derived index，不得變成第二個權威。
- **每一則工作敘述都直接建立 Pattern，或固定湊滿 N 個案例才建立**：前者會把臨時事件一般化，後者會把 O*NET occupation publication 的群體門檻誤套到單一員工並漏掉明確、低頻的重要責任；第一版依員工實際陳述的角色常態／事件語意判斷。
- **為了框架覆蓋率先做 LangMem／Trustcall canary 或直接寫 production memory**：通用單筆 create／update／delete 沒有直接保證本產品的來源、版本、整批原子性與 JD basis；沒有真實 reconcile 缺口時，額外 model／patch layer 只增加成本與 owner 邊界。未來只有 evidence-triggered successor 才重開比較。
- **因 LangMem／Trustcall 尚未完全符合就同時保留兩套 memory owner**：框架候選只能完整替代同目的機制或不引入；不能以雙寫迴避取捨。
- **把工作範圍直接等同 Duty 或 Task**：訪談線索可能先出現 O／P／K／S，Duty／Task 也會隨理解與審核變動；綁定會讓內部理解被文件骨架帶偏。
- **另建 LLM 可寫 `WorkScope`，只為導航／進度再同步 Pattern**：這會重複 stable identity、membership、merge／split、lineage 與 stale 規則；第一版由 current collection 投影索引即可。若真實長訪談證明 projection 不足，再以 successor ADR 重開有獨特 invariant 的上層語意。
- **用第二個 LLM／critic 宣告工作理解正確**：增加 calls、latency 與不同模型意見的處理成本，仍不能取代員工的職務事實；第一版只使用 strict schema、deterministic gate、同一顧問的一次受限 repair 與必要的人類澄清。
- **任何驗證失敗都詢問員工**：會把 quote、ID、revision、provider 與程式錯誤偽裝成訪談問題；只有真正 user-fixable 的工作語意才可 interrupt。

## Acceptance gate

1. contract／state 不再有 production `GapItem` writer、understanding calibration decision、`DEFERRED／EDIT_ACCEPTED` review status、必填拒絕理由或 model-authored `skill_ids`；
2. 已成立工作理解有 employee source，純未知可無 quote；待審 semantic group 固定引用 1～N 筆工作理解與短理由；
3. direct JD edit 不建立 employee source，下一輪可讀 delta；若與理解衝突，只透過一般聊天確認；
4. Accept 只留最小 command receipt；Reject 整組回退、無理由且保留最小防重提 fingerprint；
5. 未回答問題跨關頁／process restart／context compaction 仍由 unresolved understanding 恢復；
6. required input 在 safe boundary durable interrupt，卡片支援 2～4 選項或自由文字，回答後先更新工作理解；
7. active run 期間所有員工寫入 fail typed 409；required input 等待期間只允許該 request 的 answer command，其他聊天、JD 編輯、Undo 與 Accept／Reject 同樣 fail typed 409；回答觸發的下一輪分析完成、失敗或 timeout 後解鎖；
8. 真實 Skill receipt 而非模型自報能證明載入方法；source／quote／revision／JD invariant 均由 deterministic verifier 驗證；`validated` 不得投影成員工已確認；
9. transient／repairable／semantic ambiguity／unexpected 各有獨立測試；deterministic error 不 interrupt，每個 authority stage 最多一次 validation-driven model repair，第二次失敗 rollback 並解鎖 UI；
10. Work Understanding 是單一 typed collection，以共同 application-owned envelope＋Case／Pattern／Unresolved variants 保存完整語意；role 與 `active／superseded／retired` lifecycle 分離且同一 stable identity 不換 role；provider Tool 使用 atomic tagged variants，不使用 flat all-required dummy wire、固定巨型 `ConsultantModelOutput` 或 empty sentinel；free-text `kind + text + scope`、混合 `CURRENT／UNRESOLVED／CONTRADICTED／UNLOCATED` status 與「一句 claim＋facets」draft 均不得施工；production 不保留獨立可寫 `WorkScope`，Orientation／Context selection／Progress 只能由 current collection 重建；
11. Pattern 只以 `supported_by` 引用 Case，Unresolved 只以 `about` 引用 Case／Pattern，且都 pin exact revision；更正先重看 direct dependents、可依訊息語意擴大，未 reconcile 的 Pattern 不得成為新 JD basis；不得引入任意關係圖、全域 invalidation 或 application 自動語意修正；
12. 訪談概況不含百分比／固定 stage；每個 current pattern 只有「待補充／目前足夠」常態 label，Focus、一般待釐清、required input、未定位與待審數分開投影，basis 變更可精確使 projection stale；
13. production dependency／owner 不含 LangMem／Trustcall；Work Understanding 只由 LangGraph checkpoint 中的 typed collection 擁有，reconcile 經主顧問 typed effects、Pydantic 與 deterministic transition 完成；若未來重開替代研究，必須由可重現的真實失敗案例與 successor ADR 觸發；
14. 無 ID／Focus 的新訊息可由小型 Pattern／Unresolved／未定位目錄與同一主顧問 VFS 按需讀取找到候選；明確 refs deterministic 預載，改寫前 pin exact revision；找不到時不猜；production 不固定增加 router model、embedding 或第二 Store index；
15. 直接角色常態可由一則 current employee source 形成 Pattern；一次事件預設只成 Case，一般性不足建立 Unresolved；低頻不得單獨否決 Pattern，duplicate／overlap／new 與 JD publication 各自有獨立 gate；production 不含固定案例數、`provisional_pattern`、confidence threshold 或額外 classifier；
16. production 不含 `InterviewWorkItem`、Agenda／Plan task writer、Pydantic Planning dependency 或另一個 planning store；未回答語意由 Unresolved、目前注意力由 Focus、進度由 coverage projection、blocking ambiguity 由 interrupt 承接；
17. 完整 API／Web／contract gates、真瀏覽器 acceptance 與 GPT-5.6 Luna Max 窄 smoke 通過；核心 JD、Web 與匯出均無 A／能力級別，也沒有接入 RAG／auto-accept／多 Agent／正式 eval。
