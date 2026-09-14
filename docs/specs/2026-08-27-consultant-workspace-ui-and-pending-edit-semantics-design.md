# AI 職務分析顧問工作區 UI 與待審編輯語意設計

- 日期：2026-08-27
- 狀態：UI／編輯規格已由 owner 於 2026-08-27 複核；2026-08-28 最新工作理解、Context、來源與拒絕記憶裁決見 ADR 0071；2026-08-29 核心 JD 欄位、關聯與 K／S 生命週期已依欄位契約稽核 §18 同步。舊 8/27 實作計畫不得執行
- 範圍：顧問工作區資訊架構、目前 JD 編輯、AI 語意差異審核、Duty／Task／OPKS 階層、未歸屬內容、刪除與解除關係、訪談／工作地圖、一般對話修正、執行期唯讀、錯誤恢復，以及 Web UI framework 組合
- 不在本輪：RAG／Reference、A 與能力級別、auto-accept、多使用者協作、正式 eval 平台、公司文件、拖放、進階鍵盤捷徑、版本歷史 UI
- 上位產品方向：[`2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md`](2026-08-12-ai-job-analysis-consultant-product-flow-working-research.md)
- 現行架構：ADR 0060、0067、0069；UI／編輯由 Proposed ADR 0070 收斂，工作理解／Context／provenance 由 Proposed ADR 0071 收斂

這份文件記錄 2026-08-25 至 2026-08-27 的 UI 模擬、產品討論、現行 code 稽核與官方資料查核。模擬 HTML 只用來確認資訊層級、互動與視覺方向；production 不複製其 `contenteditable`、狀態管理或事件程式。

## 0. 結論

採用一個以 **目前 JD 為中心、左右可收合的三欄工作區**：

```text
訪談工作地圖 | 目前 JD | AI 職務分析顧問
```

員工與 AI 共同編輯同一份 Store-backed working copy；核准基線仍是只讀匯出權威。AI 造成的差異在目前 JD 原位置以語意 diff 顯示，員工可修改綠色 after-state，但修改本身不代表接受；只有另按「接受」才提升到核准基線。員工修改沒有 AI 待審差異的核准內容時，則依員工 authority 立即更新 working copy 與核准基線。

Web 組合採 **Next／React／Tailwind／shadcn＋Base UI 1.7.x＋TanStack Form v1＋TanStack Query v5＋react-resizable-panels v4**。LangGraph／Deep Agents Store workspace、Pydantic、PostgreSQL 與 generated contract 繼續承接後端 durability、validation 與 authority；不引入 Tiptap、Lexical、Monaco、XState、dnd-kit 或另一套 agent frontend。

## 1. 產品北極星稽核

| 產品目的 | 本設計怎麼做到 | 不採的偏離方向 |
|---|---|---|
| AI 像專業顧問持續訪談 | 右欄是一條可恢復對話；工作地圖顯示方向與待釐清，不做固定 wizard | 欄位填表精靈、一步一階段、員工自己規劃每一題 |
| 當下有焦點、背景不漏線索 | 工作地圖顯示白話訪談焦點；任何成果、完成標準或 K／S 線索可先保存於工作理解 | 強迫 Focus 綁定某個 Task 或 JD path |
| AI 可持續修訂目前成果 | AI 與員工讀寫同一份持久 working copy | 每回合一次性候選、另開一份 AI 文件 |
| LLM 不能偷改核准 JD | AI 差異永遠保持待審；員工修改綠色內容也不會暗中接受 | 把 Tool 執行當員工核准、把儲存等同接受 |
| 員工可接受、修改、拒絕 | 同骨架 semantic diff＋就近 review popover＋atomic group | 模型填 proposal 表單、逐個低階 Tool approval |
| Task／Duty／相關內容可動態演化 | 支援新增、改名、重新歸類、重排、一般增刪組合與原子審核 | 固定 Duty 盒子、先完成 Task 才能辨識成果／標準／K／S |
| 員工知道進度與缺口 | 工作地圖顯示 coverage、depth、一般待釐清與「需要你的確認」，不顯示假百分比 | 以模型自評百分比假裝完成度 |
| 長訪談可恢復且成本受控 | UI 只取投影；context／Skills 仍按需載入，不因顯示完整 JD 就每輪傳完整 JD | 把整份畫面狀態每輪塞入 prompt |
| 匯出可靠 | 匯出只讀核准基線，並依同一核心 JD contract 產生 Caliburn 自有格式 | 把待審 working copy、未定位線索或舊 iCAP schema 帶入匯出 |

稽核結論：方向未偏離。這是既有顧問 runtime 的工作面升級，不是重新發明訪談 engine，也不把 UI framework 反過來定義產品流程。

## 2. 官方資料與可轉移邊界

以下查核日均為 2026-08-27。官方產品證明互動機制成熟，不等於它已驗證繁中職務分析品質；職務分析語意仍以本 repo 最新欄位研究、跨國官方資料與員工 authority 為準。iCAP 是研究來源之一，不是產品 schema／匯出版面 authority。

### 2.1 同一工作面與事後審核

- [VS Code — Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits) 顯示 Agent 可先修改 session folder／worktree，使用者之後從真實 working state 查看、修正與整合；舊 extension-host 流程則能在原位置 Keep／Undo。可轉移的是「AI 與人繼續編輯同一目前成果、審核實際差異」；不可轉移 Git、branch、commit 或程式碼 hunk。
- [Google Docs — Suggest edits](https://support.google.com/docs/answer/6033474) 使用顏色與刪除線表示新增／刪除，接受後才成為正式內容。可轉移的是文件脈絡中的明確接受／拒絕；不可轉移多人協作、留言與 email 通知。
- [Apple HIG — Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai) 要求清楚標識 AI 內容、保留人的控制、允許捨棄與還原。這支持 AI badge、拒絕與復原，但不規定 Caliburn 的 authority schema。
- [Primer — Delegate](https://primer.style/product/scenario-patterns/delegate/) 建議讓人查看成果、提供接受／要求修改／還原，並在失敗時給可行動的下一步；不支持自動發布未審內容。

因此 Caliburn 採 coding agent 的共同 working surface，加上建議模式的核准邊界；不照抄其中任一產品。

### 2.2 三欄工作區與階層導覽

- [Apple HIG — Sidebars](https://developer.apple.com/design/human-interface-guidelines/sidebars) 建議大量內容用 disclosure 分組、允許隱藏 sidebar，且深層內容不應全塞進 sidebar。故左欄只放訪談導航與 Duty→Task 大綱，完整 OPKS 留在中央文件。
- [shadcn/ui — Resizable](https://ui.shadcn.com/docs/components/base/resizable) 以 `react-resizable-panels` 提供可存取的 panel group；其 wrapper 已支援 v4 API。
- [`react-resizable-panels` npm registry](https://www.npmjs.com/package/react-resizable-panels) 目前 stable tag 為 4.12.3；官方 GitHub release notes 說明 4.x 的 layout persistence、collapse／expand 與標準 separator 語意。版本只在 compatibility gate 通過後寫入 lockfile，不因「最新」兩字跳過驗證。
- [Base UI — Scroll Area](https://base-ui.com/react/components/scroll-area) 保留原生 scroll container，適合讓三欄各自滾動，不讓整頁滾到最底才看得到輸入框。

### 2.3 複合表單與自動儲存

- [TanStack Form — Arrays](https://tanstack.com/form/latest/docs/framework/react/guides/arrays) 原生處理 nested object arrays 的新增、移除、移動及對應 field state，適合 Duty／Task／關鍵產出／完成標準與 K／S links 編輯；它只管理瀏覽器編輯狀態，不成為 document authority。
- [TanStack Form — Basic concepts](https://tanstack.com/form/latest/docs/framework/react/guides/basic-concepts) 支援細粒度 selector，避免大型 JD 每個按鍵都重繪全部欄位。
- [TanStack Query — Mutation scopes](https://tanstack.com/query/latest/docs/framework/react/guides/mutations#mutation-scopes) 明載同一 `scope.id` 的 mutations 會序列執行；用它避免同一 JD 的 autosave 彼此覆蓋，且送出訪談訊息前可等待該 scope 清空。
- [RFC 9110 — `If-Match`](https://www.rfc-editor.org/rfc/rfc9110.html#name-if-match) 以條件式 state-changing request 防止 lost update。Caliburn 的 revision／generation／digest guard 採相同原則；UI 唯讀只是體驗與降低競態，不取代 server guard。
- [Primer — Customize](https://primer.style/product/scenario-patterns/customize/) 警告同一 form 不要混用含糊的自動與手動儲存，並要求操作結果可感知。因此所有 inline 欄位統一採自動儲存，畫面只顯示「儲存中／已儲存／儲存失敗」，不再出現另一顆 Save。
- [Atlassian Design System — Inline edit](https://atlassian.design/components/inline-edit) 支持在閱讀位置直接轉入編輯，避免每個短欄位開獨立頁面或 dialog。

### 2.4 移除、刪除與復原

- [Primer — Delete](https://www.primer.style/product/scenario-patterns/delete/) 明確區分 `Remove`（解除關係）與 `Delete`（實體消失），建議可逆操作用 Undo，高影響且不可逆操作才增加確認摩擦，並在確認前說清 blast radius。
- [Kubernetes — Garbage collection](https://kubernetes.io/docs/concepts/architecture/garbage-collection/) 的 cascade／orphan 是成熟的 ownership 類比：是否連帶刪除取決於真正 ownership，而不是 UI 階層看起來誰包住誰。它只作生命週期類比，不是職務分析來源。

因此 Duty→Task 是可選分組關係；Task→關鍵產出／完成標準是 ownership；Task↔K／S 是多對多參照。刪除規則必須依此，而不是一律全刪。

### 2.5 Job Analysis 關係

- [LLM 欄位契約稽核](2026-08-28-llm-authored-field-contract-audit.md) §18 綜合 O*NET、OPM、UK NOS、iCAP 與企業產品研究，將產品語意收斂為 Task 下的可選關鍵產出、完成標準，以及文件層 canonical K／S 與 Task 多對多關聯。
- [U.S. OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/) 強調 Task、competency 與兩者連結；這支持在成為正式職務內容前說清 K／S 支援哪些工作，但不替 Caliburn 定義欄位名稱或版面。

因此「先發現」不等於「先寫入 JD」：AI 可以先理解任何成果、完成標準或 K／S 線索，待 Task 邊界與關係足夠清楚後才形成待審文件變更。

### 2.6 對話延續、Agent 寫入與同輪併發

- [Anthropic — How Claude Code works](https://code.claude.com/docs/en/how-claude-code-works) 把修正描述成同一對話中的 follow-up，並以持久 session history 支援 resume；這支持「員工自然說剛才說錯，顧問依上下文調整」，不支持另造一個一般員工必須理解的 source-supersession workflow。
- [OpenAI — Model guidance: apply patch](https://developers.openai.com/api/docs/guides/latest-model#the-apply-patch-tool) 的 agent loop 是模型提出結構化操作、application 套用並把成功／錯誤回傳模型；[Codex IDE 說明](https://openai.com/index/introducing-upgrades-to-codex/) 則讓人預覽並直接編輯目前變更。可轉移的是「模型操作受控 working surface、真實 application state 與 verifier 才算數」；不可轉移程式碼 patch 格式與 Git。
- [VS Code — Send messages while a request is running](https://code.visualstudio.com/docs/chat/chat-overview#_send-messages-while-a-request-is-running) 明確提供 queue／steer／stop 三種政策；Claude 也提供 interrupt／queued correction。這證明「執行中再輸入」必須有明確 harness 語意，並非把 textarea 留著就完成。
- [LangGraph — Double texting](https://docs.langchain.com/langsmith/double-texting) 正式列出 enqueue／reject／interrupt／rollback；`reject` 會阻止第二個 run 與 concurrent execution，而且這組能力屬 Agent Server／LangSmith Deployment，不是 OSS LangGraph 內建。Caliburn 第一版採 reject，不為尚未需要的 queue／interrupt 引入 Agent Server。
- [WHATWG HTML](https://html.spec.whatwg.org/multipage/input.html#the-readonly-attribute) 區分 `readonly` 與 `disabled`；[WAI-ARIA 1.2 `aria-busy`](https://www.w3.org/TR/wai-aria-1.2/#aria-busy) 用來表示區域正被更新。故執行期間只停用 mutation controls，閱讀、選取、捲動、展開／收合仍可操作，並以 status／`aria-busy` 說明狀態。

這些來源沒有證明「一般口頭更正應由 application 自動判斷 supersede／qualify／rebut」。因此本設計不把那個 Caliburn 自創機制誤稱為大廠標準；員工原話保留為對話歷史，現在的可修訂理解與目前 JD 才承接語意更新。

## 3. 員工心智模型與三種狀態

### 3.1 目前 JD

唯一主要編輯面。它是 Deep Agents／LangGraph Store 中持久 working copy 的 application projection，包含：

- 與核准基線相同的普通內容；
- AI 新增、修改、移動或刪除後仍待審的差異；
- 員工尚在編輯、已自動儲存的目前值。

AI 下一輪從這份 working copy 繼續，不因員工尚未審核而忘記先前結果。

### 3.2 已核准版本

員工 authority 已提交的只讀 snapshot，也是 readiness 與 XLSX export 唯一輸入。它可從「匯出版本／已核准版本」次要面板查看，但不是另一個主要 editor。

### 3.3 審核變更

application 由核准基線與目前 JD 即時計算 semantic diff。它不是第三份 draft、patch queue、Git index 或模型填寫的 proposal form。review metadata 只保存穩定 identity、1～N 筆工作理解 references、AI 短理由、dependency、stale guard 與最小 command／rejection fingerprint；逐字來源與 quote 留在工作理解，實際 Skill 使用留在 execution receipt。

## 4. 工作區資訊架構

### 4.1 寬螢幕

```text
┌──────────────┬──────────────────────────────┬──────────────────┐
│ 訪談工作地圖 │             目前 JD          │ AI 職務分析顧問 │
│ 獨立滾動     │             獨立滾動         │ 訊息獨立滾動    │
│ 可收合／調寬 │                              │ 輸入框固定底部  │
└──────────────┴──────────────────────────────┴──────────────────┘
```

- 左右 panel 都可收合與調整寬度；中央永遠不被 panel overlay。
- 儲存 panel 開關與寬度到 local UI preference；它不是 document authority。
- top bar 固定顯示返回、職務名稱、連線／儲存狀態與匯出。
- 中央、左欄與聊天訊息各自滾動；聊天 composer 固定在右欄底部。

### 4.2 中等與窄螢幕

- 中等寬度一次只展開一側，中央仍是主要工作面。
- 窄 Web viewport 以 Base UI positioned Dialog／Drawer 顯示工作地圖或訪談；這是 responsive Web，不建立行動 App 導覽架構。
- side panel 預設不永久遮住「尚未歸屬」或 review action。

### 4.3 視覺語言

- 暖灰 app background、白色文件 canvas、細分隔線、低陰影與足夠留白。
- 藍色表示互動；綠色表示 AI after-state；紅色表示被移除 baseline；琥珀表示待釐清／警示。
- 顏色必須搭配文字、圖示或刪除線，不能成為唯一狀態訊號。
- Duty 像文件章節，Task 像內容單元，避免每一層都套重卡片造成巢狀框線爆炸。

## 5. 訪談工作地圖

工作地圖是訪談導航與可信進度投影，不是第二份 JD，也不直接編輯文件。

### 5.1 訪談概況

- 已辨識的工作範圍數量；
- 各工作目前分析深度，例如 Task 邊界、Duty 分組、成果／完成標準與 K／S 的 `尚待辨識／已有線索／目前足夠`；分析成功後立即依最新工作理解重算，分析失敗則顯示失敗，不另保存容易過時的「需重看」狀態；
- 待審變更與未歸屬 Task 數量；
- 不顯示模型自評的總完成百分比。

### 5.2 目前訪談焦點

- 使用白話顯示「現在主要要理解什麼」與原因；
- Focus 可以是責任邊界、故事、決策權、完成界線或缺口，不強迫對應 Task／OPKS ID；
- Focus 是可恢復但沒有員工來源、不可由員工直接編輯的 runtime attention bookmark；員工可用自然對話改變方向；
- 放在工作地圖正常內容流，不長期 sticky 佔住畫面。

### 5.3 一般待釐清

- 只顯示 AI 與員工都應記得、具體可回答且會影響工作理解或 JD 的未解問題與矛盾；
- 單純「Task 尚缺完成標準／K／S」或「尚未跑某個 Skill」只作內部完整度訊號，不直接顯示成待釐清；已有工作線索只有在能形成具體、可回答且確實需要員工補充的問題時才轉成白話問題；
- 不一定屬於目前 Task，也不要求員工立刻回答；
- 點擊後回到聊天脈絡，員工用自然對話回答；不以 checkbox 假裝完成分析。

### 5.4 需要你的確認（內部：required input／interrupt）

- 產品名稱固定為「需要你的確認」；只用於存在衝突、責任歸屬不明或缺少員工選擇，使相依分析無法安全繼續的情況。
- 每題引用 1～N 筆相關工作理解；不要求 Task、Duty、branch、quote 或 Skill ID，也不把內部 understanding ID 顯示給員工。本輪才出現的衝突先在同一結果建立 unresolved／contradicted understanding，再用 local handle 引用。
- 模型本輪先保存可安全成立的理解，停止依賴該歧義的文件分析；transition durable commit 後才進 LangGraph interrupt。UI 此時不是顯示失敗或分析完成，而是在聊天輸入區顯示確認卡；員工關頁再回來仍可回答。
- 第一版每次只顯示一題最高優先、真正 blocking 的確認；其他未知繼續留在工作理解。員工回答並完成下一輪分析後，AI 再依最新理解決定是否仍需提出下一題，避免批次問題互相依賴或過時。
- 有真正互斥的答案時提供 2～4 個簡短選項，永遠保留「其他／自行輸入」；若沒有誠實的離散選項，就只顯示必填文字回答，不硬湊選單。
- 員工答案保存為一般 immutable employee message／source，resume 後啟動下一次正常顧問分析，先修訂工作理解，再完成相依 JD 分析；選項只是輸入輔助，不是工作事實來源。
- 等待回答時中央 JD 暫時唯讀：保留閱讀／查看差異，停用直接編輯、Undo 與接受／拒絕；確認卡是唯一寫入入口。員工回答並完成下一輪 analysis 後再解鎖，避免 blocking 歧義尚未解決時又產生新 delta。
- 一般待釐清、普通下一題、待審文件差異、拒絕結果、執行錯誤與產品問題都不得冒充「需要你的確認」。完整語意與官方依據見 [`2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md`](2026-08-27-consultant-conversation-continuity-and-understanding-context-research.md) §12。

### 5.5 AI 目前的理解

- 工作理解必須讓員工可查看，否則員工無法知道 AI 目前如何理解其工作；但它不是第二份 JD，也不長期完整攤在工作地圖。
- 工作地圖只顯示摘要與入口；完整內容放在可收合、唯讀的次要面板，依「目前理解／待釐清／有不同說法／已更新」分組，其他未定位工作線索只在需要時顯示。
- 員工不直接編輯工作理解；發現錯誤時在一般聊天中補充或更正，由下一輪顧問分析依 immutable employee source 修訂。
- exact quote、來源 lineage 與歷史版本預設收在按需進階查看，不和日常訪談導航搶畫面。
- `Gap` 不作產品名稱或第二份可寫 authority：真正未知投影為「待釐清」，阻塞歧義投影為「需要你的確認」，單純欄位／coverage 缺失留作內部訊號。

### 5.6 JD 大綱

- 只顯示 Duty→Task 導覽與狀態；
- 不展開 Task 子內容，避免左欄複製中央文件；
- 點擊定位中央相應章節。

## 6. 目前 JD 結構

### 6.1 表頭

主要區顯示：

- 職務名稱（必填）；
- 職務目的（必填）；
- 儲存狀態與待審 AI 變更數。

有可靠 authority 時才顯示所屬單位／團隊、直接回報職位與管理責任。職務層另有整區可選的「工作關係與重要條件」；無內容時不顯示。核心 JD 不包含 iCAP 代碼、A 或能力級別。

### 6.2 文件階層

```text
Duty
└─ Task
   ├─ 關鍵產出（0..N）
   ├─ 完成標準（0..N）
   ├─ K 所需知識（0..N links）
   └─ S 所需技能（0..N links）

職務層：所需知識與技能總覽（同一 canonical K／S 的去重 projection）
```

Task 的唯一必要成品文字是一段 canonical statement。動作、對象、目的／結果、情境、頻率、責任角色、工具與方法是工作理解或 Task Skill 的分析／寫作品質資訊，不各自成為正式 JD 欄位。Duty 可暫時沒有 Task；Task 可暫時沒有 Duty，後者顯示在「尚未歸屬」。

一個 Task 可以有多個關鍵產出、完成標準、K 與 S。K／S canonical item 可被多個 Task 共用；中央 UI 在每個相關 Task 下投影同一 stable item，並標示「共用於 N 個任務」。在 Task 下移除 K／S 代表解除連結；若仍有其他 links 就保留 canonical item，若失去最後 link 則在同一 server command 中移出核心 JD。

### 6.3 編號

- stable UUID／workspace handle 只供 application、AI VFS 與 stale guard，不作員工主要識別。
- 編輯畫面不持久顯示容易因移動而跳號的 D1／T1／O1／P1／K1／S1；使用「職責／工作任務／關鍵產出／完成標準／知識／技能」標籤、標題與局部數量辨識。
- stable ID 與排序由 application 管理；Caliburn 自有匯出依核准排序決定性投影，不沿用 iCAP 的 T1／T1.1／O1.1.1 位置碼作內容 identity。

## 7. 分析順序與尚未定位內容

### 7.1 分析可以先於結構

Task、Duty、關鍵產出、完成標準、K、S 都可由按需 Skills 協助分析；不要求先有 Task 才能在訪談中辨識相關線索，也不要求 Task 穩定後才分析 K／S。

例：員工先說「每週會交異常分析報告」。AI 可以立即保存有來源的「關鍵產出線索」，但在確定是哪一項工作產生之前，不把它偽裝成合法 JD 子項。後續確認 Task 後，AI 可一次提出 Task＋關鍵產出＋完成標準的 atomic group。

### 7.2 工作地圖與 JD 的邊界

- 未定位的成果／完成標準／K／S：先保留在有來源的工作理解，不是 JD item；只有形成具體、可回答且會影響分析的問題時，才投影到工作地圖「一般待釐清」。
- 未歸屬 Task：已是 Task，只是沒有 Duty；可有自己的關鍵產出、完成標準與已連結 K／S。
- 關鍵產出／完成標準：成為目前 JD item 時必須恰好連到一個 Task。
- 新的 AI K／S：在能說明至少一個 Task linkage 後才形成待審 JD 變更，避免累積通用空話。
- 已核准 K／S 若因 Task 重組失去最後一個 link：在同一 server authority command 中移出核心 JD，並列入 dependency closure／blast radius；不自動修改 Work Understanding。

因此中央文件的尚未歸屬區為：

```text
尚未歸屬
└─ 未歸屬 Task（可有合法的 Task 子內容與 K／S links）
```

不建立未連結的關鍵產出／完成標準、孤立 K／S 或「待重新連結 K／S」文件狀態。

## 8. 編輯與語意審核

### 8.1 普通核准內容

員工點擊文字就地編輯；TanStack Form 保存 local field state，停止輸入短暫時間或離開欄位後由 TanStack Query mutation 自動送出。server 依 expected revision／workspace generation／digest 重新讀取 before／after、驗證並提交 employee authority；成功後 working copy 與核准基線一致。

### 8.2 AI 待審內容

- AI 新增內容顯示綠色與「AI 待審」文字／圖示；被取代的 baseline 顯示紅色刪除線且唯讀。
- 員工只編輯綠色 after-state；修改自動保存回 working copy。
- **保存綠色內容不等於接受。** semantic group 繼續保持待審，員工可修改多處後再一次接受整組，也可拒絕還原核准基線。
- 員工修改後，application 重新推導 group digest、semantic diff 與 dependency；舊 review identity 失效，不能把核准套到舊內容。

這項語意取代 ADR 0069 決定 6／7 中「碰到 AI pending 就直接進 authority」與「儲存 AI 新 entity 等於 edit-and-accept」的部分。

### 8.3 差異呈現

- 修改：原值紅色刪除線；目前值綠色、可編輯。
- 新增：整個 entity／field 綠色。
- 刪除：整個 baseline entity／field 紅色刪除線。
- 重新歸類：舊位置顯示紅色移出、新位置顯示綠色移入；兩端共用 stable identity 與 atomic group，不製造兩個 Task。
- 拆分：舊 entity 紅色，新的多個 entity 綠色，必要的 OPKS linkage 一起成為 atomic group。
- 「修改／拆分／合併」是 application 對一般 add／revise／withdraw／reassign 組合的語意說明，不要求 LLM 填額外 label，也不新增 Duty／Task／OPKS business Tool。

### 8.4 審核控制

- 中央只有一個「目前 JD」工作面，不另開 AI 草稿 editor 或 proposal 清單頁。
- 點擊 AI 差異才在附近開 contextual review popover；點擊其他地方關閉。
- popover 顯示目前 atomic group 的白話摘要、AI 短理由、1～N 筆相關工作理解摘要，以及「接受／拒絕」。不把「修改」設成第三種審核決定；員工直接在綠色 after-state 編輯，逐字來源只在工作理解的按需進階查看出現。
- 編輯 group 內任一欄位只更新待審 working copy；整組仍保持 pending，不得把單一欄位 autosave 解讀成局部或整組接受。
- 接受：把整個最小合法 atomic group 的最新值提升到核准基線，working copy 不跳動。彼此獨立的變更應形成不同 group；具相依關係的 Task／OPKS 由 application 重新推導 dependency closure 與 digest，不能只靠模型或 UI hunk 任意分組。
- 拒絕：將該 group 還原核准基線，不要求員工填理由；AI 下一輪只記得真實核准內容與精簡拒絕結果。員工若在聊天中另行說明，該訊息才是可修訂工作理解的新來源。
- 第一版不做全域「全部接受」、`稍後處理`、每個 Tool approval 或另一套 review drawer。

## 9. 新增、移動、解除與刪除

### 9.1 新增與移動

- Duty 章節、Duty 下 Task、Task 下關鍵產出／完成標準／K／S 都有就近 `＋`。
- 新 Task 建立後立即顯示 canonical statement 與可按需新增的子區塊；不預建空白子 entity，也不要求同輪補滿完成標準或 K／S。
- K／S 新增入口提供「新增 K／S」與「連結既有 K／S」；大量既有項目使用 Base UI Combobox 搜尋。
- 第一版 Task 移動使用「移至其他職責」可搜尋 menu／combobox，不做 drag-and-drop。
- 重排使用簡單上移／下移或位置 menu；不建立自訂鍵盤拖放。

### 9.2 Ownership 規則

| 操作 | Authority 結果 |
|---|---|
| 解散 Duty、保留工作 | Duty 消失；Task 整棵移到未歸屬，其合法子內容與 K／S links 保留 |
| 刪除 Duty 及其工作 | Duty、所含 Task、關鍵產出與完成標準刪除；K／S 解除相關 Task links，失去最後 link 者移出核心 JD |
| 移動／取消 Task 歸屬 | Task 移到其他 Duty 或未歸屬；整棵內容保留 |
| 刪除 Task | Task、關鍵產出與完成標準刪除；K／S 解除該 Task link，失去最後 link 者移出核心 JD |
| Task 內移除 K／S | 解除 link；若是最後 link，同 command 將 canonical K／S 移出核心 JD |
| 刪除仍被多 Task 使用的 canonical K／S | 先列出所有受影響 Tasks，再明確確認並移除其全部 links 與 canonical item |

若員工想保留關鍵產出／完成標準，就必須保留 Task，改用移至未歸屬；不提供「刪 Task 但保留孤立子項」。

### 9.3 操作摩擦

- 解散、移動、取消連結等可逆操作立即生效，顯示短暫 Undo。
- 一般單項刪除若可完整逆轉，可立即執行並提供 Undo。
- 「刪除 Duty 及其多個 Task」等高影響 cascade 必須先列出 Task／關鍵產出／完成標準數量、會解除的 K／S links，以及會因失去最後 link 而移出核心 JD 的 K／S，再要求確認。
- 選單文字使用「解散／移除／解除連結／刪除」準確描述結果；不使用模糊的 `×` 代表所有生命週期。
- Undo 是一個短期反向 authority command，仍須通過 expected revision／generation；若期間已有新改動而 stale，就保留新狀態並說明無法自動復原，不做隱藏 merge。

## 10. 訪談、修正與執行失敗

### 10.1 對話修正

員工直接在聊天說「我剛才說錯了，是……才對」，和任何普通補充訊息完全相同：新訊息成為 immutable conversation turn，舊訊息原文不改；application 不先分類 `supersede／qualify／rebut`，不要求 target、不建立專用 model output／表單，也不自動修改 source lineage。

顧問每輪取得本輪訊息、受 token budget 限制的近期員工＋顧問對話、可修訂的目前理解，以及可讀取的目前 JD／待審工作面。它用既有 Skill／Tool 正常更新理解與 JD；若「哪件事說錯」本身真的不清楚，才像顧問一樣在同一聊天室追問；只有不回答就無法安全繼續時才進「需要你的確認」。較舊原話仍可透過既有同文件 source lookup 按需讀取，不把完整歷史每輪塞入 prompt。

員工來源高於 AI 推論，但不採「最新訊息自動覆蓋舊訊息」。新舊說法能依期間、例外或範圍同時成立時，工作理解改為帶條件的多筆事實；明確口頭更正時修訂目前理解並保留舊 source；無法判定時保留矛盾、停止受影響的 JD 推導並詢問員工，不依時間或模型信心猜答案。

### 10.2 一個 workspace 同時只跑一輪分析

- idle：composer、目前 JD 編輯、結構操作與審核操作可用。
- send preflight：先 flush／等待同 document 已排程的 autosave；若保存失敗，不送出員工訊息、不啟動模型，保留聊天草稿並顯示保存錯誤。
- running：從送出開始先由 Web 樂觀進入唯讀，durable `SOURCE_SAVED`／active run 是重整與多分頁後的權威狀態。顯示「AI 正在分析；完成後可繼續編輯」，停用 composer、目前 JD 編輯、新增／刪除／移動／重排、Undo、Accept／Reject。
- running 仍允許閱讀、選取文字、捲動、Duty／Task 展開收合、左右 panel 收合／調寬，以及查看 diff／工作理解來源；不用全頁 overlay。
- success：立即解鎖並以最新 snapshot 更新畫面。
- error／timeout：一定解鎖；原員工訊息仍在，顯示 inline error 與「重試分析」，也允許員工忽略錯誤後送任何普通新訊息。
- retry 沿用同一 input event，不重複建立員工訊息；provider attempt 另有 identity。

API 對同一 document 的 duplicate active run 或 employee document mutation 回既有 typed `409 …/consultant-run-active`。guard 同時檢查 process-local admission 與 durable latest run，不能只靠單一 React disabled 或單一 process set。第一版不做 queue、正在生成時的 steer／interrupt、rollback 或 concurrent branching；真正 blocking 的「需要你的確認」仍在本輪 model output 與 deterministic commit 完成後，由專用 wait node 使用 [LangGraph durable interrupt](https://docs.langchain.com/oss/python/langgraph/interrupts)。

## 11. Framework 方案 A

### 11.1 採用組合

| 目的 | 成熟元件 | Caliburn 只補什麼 |
|---|---|---|
| Next Web shell | 現有 Next 16／React 19／Tailwind 4／shadcn | 產品 layout 與視覺 token |
| Accessible primitives | Base UI 1.7.x Accordion、Menu、Dialog、Popover、Combobox、ScrollArea、Toast | Duty／Task／OPKS 文案與狀態映射 |
| 三欄 layout | shadcn Resizable＋react-resizable-panels 4.x | panel 最小寬度與 responsive policy |
| Nested editing | TanStack Form v1 | generated contract adapter、semantic group／authority policy |
| Server state／mutations | 現有 TanStack Query v5 | query keys、optimistic boundary、stale／error 文案 |
| Persistent AI workspace | 現有 Deep Agents StoreBackend／LangGraph Store | JD canonical resources 與 scope policy |
| Conversation／run recovery | 現有 LangGraph Saver、FastAPI SSE | token-bounded 雙向近期對話、產品 snapshot event 與 reject run-admission |
| Schema／validation | 現有 Pydantic＋generated contract | Duty／Task／OPKS invariant、工作理解 references／來源、atomic closure |

[Base UI releases](https://base-ui.com/react/overview/releases) 顯示 1.7.0 是 2026-08-04 latest stable，包含多項 accessibility、performance 與 bug fixes；現行 Web 為 1.4.1，實作前先跑 compatibility gate 再升級。Base UI 官方也明載其元件依 [WAI-ARIA APG 提供基本鍵盤可及性](https://base-ui.com/react/overview/accessibility)。

### 11.2 不使用的框架

- 不用 Tiptap／Lexical／Monaco：JD 是 typed entity editor，不需要 rich-text AST、協同文字編輯或程式碼語言服務。
- 不用完整 Carbon／Primer UI 套件：只採其官方設計證據，不混入第二套視覺系統。
- 不用 XState：LangGraph 已承接 durable workflow；UI local state 不需要第二套 workflow authority。
- 不用 dnd-kit：第一版移動／重排用 menu，避免拖放與可及性成本。
- 不先用 TanStack Virtual：先以折疊章節與細粒度 subscriptions；只有量測大型 JD 確有渲染問題才加入。
- 不用 `@langchain/react`／AG-UI：現行 typed product projection、SSE 與 Query 已足夠，不為少量 UI state 承擔完整 Agent Server transport contract。

### 11.3 套件整併規則

- 新畫面統一使用 Base UI primitives；改到既有 Radix Popover／cmdk consumer 時逐一遷移，沒有 consumer 後才移除依賴。
- 不同 primitive library 不得同時承接同一種 popup／focus lifecycle。
- framework 只擁有通用 UI／form／server-state mechanism；semantic diff、工作理解／來源規則、dependency closure 與 authority transaction 留在 application，因通用 framework 不理解 Duty／Task／OPKS。

## 12. 必要後端與契約變更

這不是純前端換皮，但不改 runtime 核心，也不新增資料表或第二份 document store。

1. **目前 JD projection**：現行 `ConsultantSnapshotView` 只有 `approved_document` 與 review actions；API 必須另投影 validated current working document，Web 不得自行從 patch 重算 domain state。
2. **pending workspace edit command**：新增 typed command，讓員工修改 AI after-state 只更新 Store-backed workspace，帶 expected approved revision、workspace generation／digest；不得因此 authority commit。
3. **普通 direct edit command**：沒有重疊 AI pending 的 touched semantic group 繼續由 server-derived delta 更新 working＋approved；client 不自稱 accepted paths。
4. **accept／reject command**：以最新 semantic group identity／digest 操作目前值；editing 與 acceptance 拆開，不把 `edit_and_accept` 當主要 UI 儲存動作。
5. **結構 command**：以一個 discriminated typed command 承載 dissolve Duty、cascade delete Duty、unassign／move／delete Task、link／unlink K／S。這是 employee UI application command，不是新增 LLM business Tool。
6. **current projection 狀態**：提供每個 semantic group 的 pending identity、1～N 筆相關工作理解摘要、AI 短理由、dependency 與 stale guard；Web 只負責呈現。逐字來源／quote 由工作理解按需展開，不複製到每個 JD action。
7. **durable run admission**：`SOURCE_SAVED`／active run 時，同 document 的第二個 answer、direct edit、pending edit、結構 command、Undo 與 Accept／Reject 都 fail typed `409`；process-local guard 仍保留作同 process 快速互斥。成功、失敗或 timeout 後 snapshot 必須回到可寫狀態。
8. **一般失敗恢復**：`FAILED` 可 retry 同一 input event，也可建立全新的普通員工訊息；不再要求新訊息必須 `supersedes_source_id` 指向失敗訊息。
9. **移除專用更正與舊 lifecycle**：契約／composition root／Web 不再提供 `defer_changes`／`deferred`、`edit_and_accept` 狀態、必填拒絕理由、source-specific correction mode、direct-correction 表單、application correction classifier，或「編輯 AI 新內容即接受」語意。歷史 employee turns 與工作理解來源仍保存，但普通訊息不觸發 application 自動來源 lineage mutation。
10. **工作理解 hard cut**：`GapItem`、下一題與 understanding calibration 不再各自擁有未知；改成單一 source-linked 工作理解 collection＋當輪問題 projection。員工直接改 JD 只留下下一輪 delta，不鑄 employee source。
11. **執行來源分層**：移除 model-authored `skill_ids`；framework receipt 自動記錄真實載入 Skill，待審 JD 只引用工作理解與短理由，核准 JD 不保存理由。

現行 O／P 恰一個 Task、K／S 多對多與 approved-only export invariants 全部保留。

## 13. 可及性與效能最低要求

- 使用原生 button／input／textarea 與 Base UI 提供的 focus／Escape／Enter／Space 行為。
- 第一版只要求 Tab 可到達、Enter／Space 可操作、Escape 可關閉 popup；不自建全域快捷鍵、Ctrl+Z、keyboard drag 或 ARIA tree。
- review、pending、錯誤與 AI authorship 不能只靠顏色。
- running 在中央工作區使用 `aria-busy`／status；文字欄位採原生 `readonly` 或 `disabled` 的正確語意，mutation buttons 明確 disabled。失敗使用可行動的 alert，但不把整頁遮住，也不停用純檢視 controls。
- 每欄獨立 scroll；composer 永遠可在聊天欄底部找到。
- TanStack Form／Query 使用 field selectors 與局部 mutation，避免每次輸入重繪整份 JD。

## 14. 驗收情境

### 14.1 Authority

1. AI 修改一個已核准 Task statement：舊值紅色、新值綠色；匯出仍是舊值。
2. 員工把綠色新值改兩次：working copy 跨重整保留，仍顯示待審；匯出仍是舊值。
3. 員工接受：目前畫面不跳動，核准基線與匯出改為最新值。
4. 員工拒絕：working copy 還原舊值，不要求理由；AI 只取得精簡拒絕結果，不把拒絕本身推論成新的工作事實。
5. 員工修改沒有 AI pending 的核准內容：自動儲存後直接成為核准內容，不要求審核自己的修改。

### 14.2 結構

1. 新 Task 可在沒有 Duty 時存在，且可逐步加入關鍵產出、完成標準與 K／S links。
2. 先發現成果／完成標準／K／S 時先進工作理解；確認 Task 關聯後才能成為待審文件 group。
3. 移動 Task 時其關鍵產出、完成標準與 K／S links 不遺失，review 在舊／新位置顯示同一 identity。
4. 解散 Duty 時 Tasks 移到未歸屬；cascade delete 才刪 Tasks 及其 owned 子項。
5. 刪除 Task 不會刪掉仍被其他 Task 使用的 K／S；最後 link 消失時，同一 command 將該 K／S 移出核心 JD並可 Undo。

### 14.3 Workspace 與訪談

1. 左右欄收合／調寬後中央仍可滾完整 JD；各欄 scroll 互不綁定。
2. running 時 composer、JD 寫入、結構操作、Undo 與 Accept／Reject 都不可用；閱讀、捲動、展開收合、panel 控制及查看 diff／工作理解來源仍可用。
3. success／error／timeout 後立即解鎖；error／timeout 可重試或送任何普通新訊息，不進 retry-only 死路。
4. 員工以自然語句更正前文時只送一般訊息；近期雙向對話與目前理解足以讓模型處理，不出現舊訊息 target、source-specific payload 或自動 lineage mutation。
5. 工作地圖 Focus 不綁 Task；單純缺 O／P／K／S 不顯示成待釐清，只有具體可回答的未解工作問題才顯示。

### 14.4 驗證層級

- API／domain deterministic tests：projection、pending edit、accept／reject、stale、dependency、delete／unlink、durable run admission、失敗後新訊息與 context 組裝。自然語句理解品質只做 Luna smoke，不偽裝成 deterministic unit test。
- generated contract codegen gate。
- Web component／integration tests：三欄、autosave、semantic diff、popover、panel collapse、chat lock／unlock。
- browser smoke：寬／中／窄 viewport、長 JD、長聊天、AI pending 修改後仍待審。
- 本輪不建立正式 LLM quality eval；完成產品切片後再依 owner 時程另做。

## 15. 施工切片的北極星回看

後續 implementation plan 至少拆成：framework／layout foundation、current projection 與 pending edit authority、JD hierarchy、semantic review、結構操作與 lifecycle、工作地圖／聊天／錯誤恢復、browser／full gate。每個切片完成後都要重答：

1. AI 內容是否仍需員工明確接受才進核准基線？
2. 員工與 AI 是否仍在同一目前 JD 上持續工作？
3. Task／Duty／OPKS 是否仍可按證據動態演化，而非固定 wizard？
4. 一般待釐清、「需要你的確認」與待審文件是否仍是三種不同目的？
5. 是否誤加 RAG、A／能力級別 AI、自動接受、多 Agent、第二份文件 store 或重型 editor？
6. 是否先使用成熟 framework primitive，再只補有證據的產品差額？
7. 普通口頭更正是否仍是普通對話，而非 source-specific workflow？
8. active run 是否只鎖寫入且 server 也能拒絕競態，完成／失敗後必定恢復？
9. 員工直接改 JD 是否仍只是文件 authority delta，而沒有被偽造成 employee source？
10. 待審 JD 是否只引用工作理解與短理由，Skill 使用由真實 framework receipt 證明，Accept／Reject 後沒有把理由塞進核准 JD？

任何一題失敗就暫停該切片，回到本設計與 owner 討論；不得以「舊 code 原本如此」當保留理由。
