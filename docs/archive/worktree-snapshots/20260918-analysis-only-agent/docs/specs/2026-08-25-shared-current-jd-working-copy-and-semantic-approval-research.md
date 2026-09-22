# 共用「目前 JD」工作副本與語意核准研究

> **後續裁決：** 2026-08-27 owner 撤回本文件中由 application 判斷 `supersede／qualify／rebut` 並維護一般對話來源 lineage 的產品方案。一般補充或更正只新增普通 immutable chat turn，由近期對話、目前理解與目前 JD 承接；詳見 [`2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md`](2026-08-27-consultant-workspace-ui-and-pending-edit-semantics-design.md) 與 Proposed ADR 0070。其餘 shared current JD／derived diff 研究仍有效。

- 日期：2026-08-25
- 狀態：研究完成；建議方案待 owner 明確核准，尚未修改 Accepted ADR 或 production code
- 範圍：AI 與員工如何共用同一個 JD 編輯面、待審差異、部分接受／拒絕、員工直接編輯、必要澄清、匯出權威與框架邊界
- 不在本輪：RAG／Reference、能力級別、A、auto-accept、多使用者協作、CRDT／OT、版本歷史 UI、正式 eval
- 前置決策：產品大方向研究、ADR 0060、ADR 0066、ADR 0067

本研究承接 [`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md) 與 [`2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md`](2026-08-22-persistent-ai-jd-working-draft-and-semantic-review-research.md)，但重新檢查其中「正式 JD 編輯器＋AI 工作草稿」在員工直接編輯時的產品效果。外部產品只用來辨識成熟機制；Caliburn 不複製 Git、IDE、程式碼 hunk、PR 或多使用者文件協作。

## 0. 建議結論

採用 **一個員工可見、AI 與員工共同編輯的「目前 JD」工作副本＋一份只讀核准基線＋由兩者即時計算的語意差異**。

白話效果：

1. 員工主要只看到並編輯一份「目前 JD」。它包含已核准內容，也包含尚待員工決定的 AI 修改；AI 下一輪也從這份目前狀態繼續，不會因員工尚未審核而忘記。
2. 底層仍必須保留「已核准基線」，否則無法可靠地顯示差異、局部拒絕、部分接受或只匯出已核准內容；但它不是第二個主要編輯器。
3. 「審核變更」是目前 JD 相對核准基線的 **derived semantic diff**，不是另一份文件、patch queue 或模型填寫的表單。
4. AI 可在目前 JD 的受限工作區內持續低階編輯，不逐次打斷員工；只有將 AI 內容納入核准基線時，才需要員工接受或修改後接受。
5. 員工直接編輯是 authority。儲存員工修改時，該次實際修改的語意範圍同時寫入目前 JD 與核准基線；若與 AI 待審內容重疊，以員工最後內容為準，該重疊差異被解決，無關待審差異保留。
6. 未處理的 AI 差異自然保留，不需要「稍後處理」狀態。待審本身也不鎖住聊天；真正缺少只能由員工決定的事實或有重大衝突時，才走獨立的必要澄清。
7. 匯出只讀核准基線；目前 JD 中尚未核准的 AI 差異不會因一般或強制匯出而被偷偷納入。

這是 coding-agent「同一 working surface 上持續編輯與事後看 diff」和文件系統「未核准建議不能成為正式內容」的混合，而不是照抄任一產品。

## 1. 這次澄清修正了什麼

### 1.1 先前容易產生的錯誤心智模型

先前文件與現行 UI 容易讓員工感覺有兩份可編輯內容：

- 「目前正式職務說明書」由員工直接編輯；
- AI 另有持久工作草稿；
- 員工直接改正式內容後，再把新正式內容 rebase 回 AI 草稿；
- 同一路徑兩邊都改過時，留下 `workspace-rebase-conflict`，要求員工再選一次。

底層兩個 snapshot 本身不是錯；問題是把它們做成兩個互相競爭的編輯面。員工原本只是要修正眼前 JD，卻可能看到「我的正式修改已成立，但 AI 草稿仍保留另一值」的衝突。

### 1.2 修正後的三個概念

| 概念 | 員工看到／操作什麼 | 底層用途 |
|---|---|---|
| 目前 JD | 唯一主要編輯面；顯示已核准內容與 AI 尚待審差異 | Deep Agents `StoreBackend` 中的 durable working copy |
| 已核准版本 | 次要、只讀的比較／匯出基線 | 員工 authority 已提交的 snapshot |
| 審核變更 | 在同一 JD 骨架上顯示紅刪除／綠新增、移動與 atomic group | application 由核准基線 ↔ 目前 JD 即時計算，不另存第三份文件 |

「只有一份主要文件」不等於資料庫只能有一個 snapshot。核准基線和目前工作副本是兩種不同 authority 狀態；只要不把兩者都做成獨立主要編輯器，就沒有兩套產品生命週期。

## 2. 最新官方資料顯示的共同模式

以下均查核官方第一方資料，最近查核日為 2026-08-25。官方產品行為能證明機制已成熟，不能直接證明職務分析品質。

### 2.1 VS Code：目前 Agent Host 是直接改工作面，再集中審查

VS Code 於 2026-08-19 更新的 Agent 文件明示：Agent 直接把修改保存到 session folder 或隔離 worktree，這些 edit **沒有 pending approval state**；使用者可以繼續下指令或直接編輯檔案，最後以 diff、Source Control 或 PR 審查。使用者或 Agent 再改檔後，先前的 `Mark as Reviewed` 會清除。文件也把舊 extension-host 的逐 edit `Keep／Undo` 流程標成另一種舊 session 行為。

來源：[VS Code — Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits)

可轉移到 Caliburn：AI 應先在同一 durable 工作面完成與修正結果，員工不必批准每一個 `write_file／edit_file`；員工與 AI 都可對目前成果繼續修改，審核狀態要隨實際內容改變而失效。不可轉移：Git stage、commit、branch、worktree UI 與「所有直接編輯都可直接進正式歷史」。

### 2.2 Codex：review 看實際 repository state，不只看 AI 自稱改了什麼

Codex IDE 讓使用者在原始內容旁查看 focused diff、保留需要的修改並在同一聊天要求後續調整。Codex review pane 反映真實 repository state，包含 Codex、使用者及其他未提交修改；可按整體、檔案或 hunk stage／revert。這表示審查來源應是「基線與真實 working state 的差異」，不是模型另外發布的一份 changeset 表單。

來源：

- [OpenAI — Codex IDE extension](https://learn.chatgpt.com/docs/codex/ide)
- [OpenAI — Code review](https://learn.chatgpt.com/docs/code-review)

可轉移到 Caliburn：semantic review 必須由 application 對真實目前 JD 計算，員工與 AI 對同一工作面後續修改後重新計算。不可轉移：line diff、Git index、commit 與 PR。

### 2.3 Claude Code：可直接編輯、事後 diff，也有 checkpoint 恢復

Claude Code 的 `acceptEdits` 模式允許 Claude 先編輯 working directory，再由使用者透過 editor／Git diff 事後審查；每次 user prompt 前建立 checkpoint，session 恢復後仍可 rewind。官方同時強調 checkpoint 只覆蓋特定工具造成的檔案修改，且不是永久版本控制。

來源：

- [Anthropic — Permission modes](https://code.claude.com/docs/en/permission-modes)
- [Anthropic — Checkpointing](https://code.claude.com/docs/en/checkpointing)
- [Anthropic — Claude Code Desktop](https://code.claude.com/docs/en/desktop)

可轉移到 Caliburn：目前 JD 與對話可跨輪恢復；員工可看 diff 後要求 AI 繼續改。不可轉移：Bash、Git、30 天 retention 與 IDE permission mode。

### 2.4 Google Docs：正式內容仍需要明確接受建議

Google Docs Suggesting 明示建議不會取代原文，owner 接受後才生效；新增以顏色顯示、刪除以刪除線顯示，可逐項或整批接受／拒絕。這一點比 coding agent 更接近職務文件的 authority 要求。

來源：[Google Docs — Suggest edits](https://support.google.com/docs/answer/6033474)

可轉移到 Caliburn：AI-origin 差異必須保持可辨識，核准前不得進入匯出基線；審核應在文件脈絡中顯示紅／綠語意差異。不可轉移：把每個文字字元都當 suggestion，或忽略 Duty／Task／OPKS 的結構依賴。

### 2.5 OpenAI Apply Patch：模型提出操作，harness 套用真實 after-state

OpenAI Apply Patch 的正式流程是：模型提出 create／update／delete patch，application harness 套用到 working directory、記錄成功或錯誤、把結果回送模型，再允許模型修正或完成。這支持「模型不能自己宣稱修改成功；真實工作面與 verifier 才是 ground truth」。

來源：[OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)

Caliburn 已用 Deep Agents 的低階 editor verbs 與 deterministic verifier 承接同目的，不需改成 OpenAI-only patch 格式，也不需為 Duty／Task／OPKS 各建一個 business Tool。

### 2.6 Git：baseline 與 working copy 分離是成熟心智模型，但不必引入 index

Git 官方把 HEAD 定義為最後提交 snapshot、Index 為下一次提交候選、Working Directory 為可編輯 sandbox。這能解釋為何 Caliburn 至少需要核准基線與目前工作副本，卻不代表產品也需要第三個 staging index。

來源：[Git — Reset Demystified／The Three Trees](https://git-scm.com/book/en/v2/Git-Tools-Reset-Demystified)

Caliburn 的 semantic review 已能直接從 baseline ↔ working copy 推導；再加入 index／patch queue 只會增加第三份狀態。

### 2.7 LangGraph／Deep Agents：通用機制已有成熟元件

Deep Agents 官方 `StoreBackend` 把虛擬檔案存進 LangGraph `BaseStore`，可跨 thread 持久；`CompositeBackend` 可依 path 路由不同 backend，內建 `ls／read_file／write_file／edit_file／delete／glob／grep`。LangGraph `interrupt()` 會保存 graph state並無限期等待 `Command(resume=...)`，適合真正需要員工先回答的必要澄清。

來源：

- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

LangChain HITL middleware 則是在 **Tool 執行前**依 policy 讓人 approve／edit／reject／respond。它適合寄信、刪資料、執行 SQL 等 side effect，或 `ask_user`；不適合拿來核准每一次 AI 在受限 JD 工作區內的低階編輯，否則會退回逐 Tool 打斷訪談，而且無法直接取代多輪並存的 JD semantic diff。

來源：[LangChain — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)

## 3. 三種產品模型比較

| 方案 | 效果／功能 | 成本與風險 | 裁決 |
|---|---|---|---|
| A. 兩個主要編輯面：正式 JD＋AI 草稿 | 最接近現行 code；核准權清楚 | 員工必須心算兩份內容；direct edit 後需要 rebase；重疊值形成不必要 conflict；UI 容易誤解哪份是「現在」 | 不採用 |
| B. 一個目前 JD 工作副本＋只讀核准基線＋derived semantic diff | AI 與員工都在同一成果上繼續；審核與匯出 authority 仍清楚；框架與現有底層大多可沿用 | 需精確定義員工修改與 AI pending 重疊時的語意範圍；API 要投影 working document | **建議採用** |
| C. 以 patch／suggestion ledger 作主要真相 | provenance、逐操作審核很明確 | 模型實際編輯 operation log，不是完整 JD；需重播 conditional after-state；容易再造 index、queue、reducer 與第三份 lifecycle | 不採用作主要工作面 |

另有一個看似簡單的變體：「只有目前 JD，連員工直接修改也全部待審」。它最像 Git working tree，但違反本產品已確認的員工 authority，也會讓員工審核自己的修改，因此不採用。

## 4. 建議方案的精確語意

### 4.1 底層只有兩份必要 state，review 是投影

```text
已核准基線 ───────────────→ 匯出
     │
     │ semantic compare
     ▼
目前 JD 工作副本 ─────────→ AI 與員工唯一主要編輯面
     │
     └─ derived review groups：接受／修改後接受／拒絕
```

- 核准基線：AI 唯讀、員工 authority commit 才更新。
- 目前 JD：Deep Agents `StoreBackend` 的唯一 active workspace；AI 與員工看到同一 after-state。
- review：核准基線與目前 JD 的差異＋來源／依賴／決策 metadata；不另存一份 document 或 raw patch queue。

### 4.2 AI 編輯

1. AI 透過既有低階 VFS Tool 編輯目前 JD。
2. framework／application 實際套用並驗證；失敗 diagnostics 回給 AI，在受限 budget 內修正。
3. 成功後，員工立即在目前 JD 看到結果；相對核准基線的新差異自動成為待審語意 group。
4. 員工不審也能繼續訪談；AI 下一輪讀同一份目前 JD，並知道哪些內容尚未核准。

### 4.3 接受與拒絕

- **接受**：把所選 semantic／atomic group 的目前值提升到核准基線；目前 JD 不跳動，差異自然消失。
- **修改後接受**：員工在同一目前 JD 中改成最終內容，server 驗證後把該 employee after-state 同時寫入目前 JD 與核准基線；員工輸入成為 source。
- **拒絕**：把該 semantic／atomic group 在目前 JD 還原成核准基線，保存拒絕裁決與可選理由；相依候選重新驗證。
- **未處理**：什麼都不做，差異原地保留。沒有獨立 `defer` command、狀態或按鈕。

單純接受只表示員工授權文件內容，不新增員工工作事實；員工實際改寫、直接編輯或提供拒絕理由時，新增文字才可成為後續分析可見的 employee source／feedback。

### 4.4 員工直接編輯

員工直接編輯不能再採「先改 approved，再嘗試把 AI 草稿 rebase 過來」；應以 **員工本次實際 delta** 為 authority：

1. UI 以目前 JD revision 為基礎送出 typed edits 或編輯後文件；server 必須用 exact before／after 自己計算員工實際 semantic delta，不信任 client 自稱改了哪些 paths，也不把整份目前 JD 當成全部由員工核准。
2. server 重新讀目前 JD 與核准基線，驗 expected revisions、權限與整份 prospective document invariant。
3. 沒有 AI 重疊的員工修改：同時寫入目前 JD 與核准基線。
4. 與 AI pending 重疊：員工最後 after-state 取代該重疊 semantic component，並立即成為核准值；舊 AI review identity 失效。
5. 不重疊的 AI pending group 完全保留，不因員工儲存其他欄位而被順便接受。
6. 若員工編輯的是 AI 新增、核准基線尚不存在的 entity，儲存代表「修改後接受」該 entity 所屬的最小合法 atomic group；UI 必須在儲存前說明實際涵蓋範圍，不能暗中只提交半個 Task／Duty／OPKS linkage。

若 AI 在員工開啟編輯後又改了同一 semantic component，server 應回 stale，不做隱藏 merge。第一版是本機單一操作者，不需要 CRDT／OT；沿用 per-document admission lock、expected revision 與可保留的瀏覽器輸入即可。

### 4.5 待審與必要澄清分流

- 一般 AI 文件差異只是待審，不鎖聊天、不鎖輸入框，也不要求員工先按接受。
- AI 可以把目前 JD 中的未核准內容當成「工作中的假設」繼續整理，但不得對員工宣稱已核准，也不得匯出。
- 若來源互相衝突、責任歸屬不明，或某個事實只能由員工決定，才建立必要澄清並以 LangGraph `interrupt／resume` 暫停真正相依的分析。
- 「文件要不要接受」不是必要澄清。若員工不同意，可拒絕或在聊天室說明；拒絕與修正才是新的後續 feedback。

因此目標設計不應讓 `blocked_branches`／`decision_required_before_more_interview` 由 pending review 驅動。若仍有 branch blocking，它只能來自獨立的 required clarification，而不是「還有 pending diff」。現行 backend 其實已把這兩個 review 欄位固定投影為空／`false`，但 contract 與 Web 仍保留可鎖聊天的舊支線；應一併移除，避免日後誤接回去。

### 4.6 匯出

- 一般與強制匯出都只讀核准基線。
- 強制匯出可以忽略 readiness gap，但不能自動接受目前 JD 中的 AI pending 差異。
- UI 在匯出前顯示「N 項 AI 變更尚未核准，因此不會出現在檔案中」，避免員工把目前畫面誤認為匯出內容。

### 4.7 分析失敗與聊天式更正

AI 分析失敗也不應把聊天框鎖成「只能重試」。員工原話已先 durable 保存，最後一份 valid 目前 JD 與核准基線仍可用；員工應能直接繼續說「我剛剛說錯了，是……才對」或補充新資訊。重試可以保留成快捷動作，但不能是唯一出口。

主要畫面不提供「找到一段原話後按更正」的操作。每則新訊息先成為 immutable employee source；顧問依對話與來源 context 判斷它是在 `supersede／qualify／rebut` 哪個既有說法，application 驗證 target 屬於同一文件與員工。若無法唯一判斷才走必要澄清。來源版本與 lineage 只供進階追溯，不要求一般員工操作。

這延續 Codex／VS Code／Claude 的「在同一對話給 follow-up、從 checkpoint／實際工作面繼續」模式，但來源 lineage 與更正傳播是 Caliburn 自己的 Evidence／職務分析責任，不能由聊天文字順序取代。

## 5. 建議 UI 心智模型

第一版不需要三個同級 tab「正式版／比較版／AI 草稿」。建議：

1. **`目前 JD`**：唯一主要查看與編輯頁。平時是乾淨 JD 骨架；有 AI pending 時顯示低干擾標記與數量，可進入審核。
2. **`審核變更 N`**：仍使用同一 JD 骨架，但展開紅色刪除線／綠色新增、移動前後位置與所選 atomic group；接受／拒絕靠近目前正在看的差異。
3. **`查看已核准版本`**：次要 read-only action／drawer，只在員工想確認匯出基線時使用，不是主要編輯 tab。
4. 聊天與工作地圖可收合；收合後目前 JD 取得主要畫面寬度。

審核頁和目前 JD 長得相近是合理的，因為兩者是同一文件骨架；差別是審核頁必須直接在變動位置顯示 before／after，不能只在頁尾另列「原本／建議」。

## 6. 成熟框架覆蓋與 Caliburn 最薄差額

| 產品責任 | 成熟框架／既有 primitive | 是否需要自寫 |
|---|---|---|
| 跨輪目前 JD 工作副本 | Deep Agents `StoreBackend`＋LangGraph Postgres Store | 只補 document namespace、canonical resource mapping |
| Skill／source／approved／workspace path 路由 | `CompositeBackend`＋backend permissions | 只補固定 policy 與 read-only projection |
| AI 低階編輯 | Deep Agents `read_file／write_file／edit_file／delete` | 不再自建 Duty／Task／OPKS CRUD Tools |
| 對話、run、失敗恢復 | LangGraph Postgres Saver／checkpoint | 只補 source-first idempotency 與產品錯誤碼 |
| 必要澄清 | LangGraph `interrupt／Command(resume)`；必要時可借用 LangChain `respond` 形狀 | 只補何時必問、問題內容與 affected branch |
| 一般工具執行前核准 | LangChain HITL middleware | 本產品正常 JD edit **不使用**；避免逐 Tool 打斷 |
| 目前 JD ↔ 核准基線差異 | 現有 semantic differ＋Pydantic domain model | 必須保留；通用框架不懂 Duty／Task／OPKS |
| atomic dependency 與 partial authority | LangGraph command／checkpoint 作執行基礎 | 必須保留最薄 domain grouping／commit policy |
| Evidence／更正 lineage | LangGraph Store＋Pydantic＋exact resolver | 必須保留 claim-support 與來源失效規則 |
| Web 語意 diff | React＋生成 contract | 必須做 domain UI；generic code diff 不足 |

結論是 **不新增框架**。現有 LangChain／LangGraph／Deep Agents 已覆蓋通用機制；這次應移除重複產品狀態與錯誤 UI 接縫，而不是再加 Git library、JSON Patch authority、CRDT、第二個 workflow engine 或另一套 document editor framework。

## 7. 現行實作差距

以下是 2026-08-25 直接對照 production code 的診斷，不是施工授權：

1. `ApprovedDocumentEditor.tsx` 以 `snapshot.approved_document` 建立另一份正式文件 draft，送到 `PUT /approved-document`；員工實際不是在 AI 當前 workspace 上編輯。
2. `prepare_direct_edit_rebase()` 先以 old／working／new 做三方 rebase；同一路徑 AI 與員工都改過時，`_three_way_value()` 保留 working 值並加入 conflict。這應改成「員工 touched semantic component 直接 override 並 commit」，無關 pending 才保留。
3. API snapshot 只公開 `approved_document`＋`document_review`，沒有一份已驗證、可供主編輯器使用的 current working document projection。
4. `WorkspaceDecisionKind.DEFER`、contract 的 `defer_changes`、Web「稍後處理」與 deferred metadata 仍存在；它們已沒有產品價值。
5. `blocked_branches`／`decision_required_before_more_interview` 雖由 backend 固定投影為空／`false`，contract 與 Web 仍有鎖聊天分支；這是無效且會誤導後續施工的 latent lifecycle。
6. `ConsultantConversation.tsx` 在 run failure 時以 `answerBlockedByFailure` 禁用 textarea，只允許重試或進入 source-specific 更正模式；這與聊天式自然更正不符。
7. Store-backed workspace、semantic differ、dependency／atomic group、stale digest、rejection memory、per-document admission、Evidence verifier 與 export baseline 都是可保留的正確基礎，不需要 Big-bang 重寫。

## 8. 若核准，文件與施工邊界

本研究改變 Accepted ADR 0066 的三個細節：

- 「正式 JD direct edit 後 rebase workspace，重疊形成 conflict」；
- `defer` 是獨立 decision；
- pending structural review 可以成為 interview branch blocker。

因此不能直接事後改寫 ADR 0066；owner 核准後應開新的 successor ADR（下一號為 0069）。ADR 0067 的 `StoreBackend` durable workspace 選擇仍成立；ADR 0060 的「AI 無 approved write edge、員工 authority、單一 durable owner」也仍成立。

建議施工切片：

1. 契約與 authority：公開 validated current document、以 server-derived employee semantic delta 更新 current＋approved、移除 defer／review-blocking。
2. Web：把正式 editor 改為目前 JD editor；保留同骨架 semantic review與次要已核准版本查看。
3. 對話與來源：失敗後保持輸入可用；一般更正由新訊息與 validated lineage 承接，移除主要畫面的 source-specific 更正操作。
4. 清理：移除舊 rebase-conflict 文案／分支與 deferred lifecycle，但保留真正 stale／concurrency guard。
5. 驗證：domain/API/Web/browser 後再做一次 Luna live smoke；不建立正式 eval 平台。

## 9. 最小驗收情境

1. AI 新增三個 Task；員工不審、關頁再開，三個 Task 仍在目前 JD，AI 可接續修改，核准基線與匯出仍無三項。
2. AI 改頻率；員工在目前 JD 直接改成第三個值並儲存。第三個值同時成為目前值與核准值，舊 AI 差異消失，不產生「正式 vs 草稿」衝突。
3. AI 同時改十項；員工只接受九項、拒絕一個 O。核准基線得到九項，目前 JD 的被拒 O 回復，其他不相依內容不跳動。
4. 員工編輯 AI 新增 Task 的文字。UI 明示儲存會修改後接受該 Task 與必要 linkage；不暗中接受無關 Duty／OPKS。
5. 員工正在編輯時 AI 改到同一 semantic component。server 回 stale、保留員工輸入供重新套用，不做不可見 merge。
6. 有待審結構變更時聊天仍可輸入；只有真正 required clarification 才顯示必答問題。
7. 分析失敗後 textarea 仍可輸入；員工以自然語句更正先前內容，舊來源與 validated lineage 可追溯，但主要畫面不要求點選舊原話。
8. 強制匯出時明示未核准 AI 變更不會輸出，檔案只含核准基線。

## 10. 來源與證據限制

- [VS Code — Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits)
- [OpenAI — Codex IDE extension](https://learn.chatgpt.com/docs/codex/ide)
- [OpenAI — Code review](https://learn.chatgpt.com/docs/code-review)
- [OpenAI — Apply Patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)
- [Anthropic — Permission modes](https://code.claude.com/docs/en/permission-modes)
- [Anthropic — Checkpointing](https://code.claude.com/docs/en/checkpointing)
- [Anthropic — Claude Code Desktop](https://code.claude.com/docs/en/desktop)
- [Google Docs — Suggest edits](https://support.google.com/docs/answer/6033474)
- [Git — Reset Demystified](https://git-scm.com/book/en/v2/Git-Tools-Reset-Demystified)
- [Deep Agents — Backends](https://docs.langchain.com/oss/python/deepagents/backends)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangChain — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)

沒有上述來源直接研究「AI 職務分析 JD 編輯器」。本研究的外部證據能支持 shared working surface、derived diff、checkpoint、正式建議核准與 Tool／HITL 邊界；Duty／Task／OPKS semantic grouping、員工 authority、來源 Evidence 與匯出規則仍是 Caliburn 的領域推論，必須用本專案測試與員工情境驗證，不能宣稱已由大廠 benchmark 證明最佳。
