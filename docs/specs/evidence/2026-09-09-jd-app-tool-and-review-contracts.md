# JD App 工具、結果與審閱契約：官方／原始碼證據

- **日期**：2026-09-09
- **決策題**：JD-R002／C03（App、LLM 工具、文件保存與人機續編的責任邊界）
- **階段**：G2 官方文件與原始碼證據稿
- **性質**：研究輸入；不是 API schema、資料庫 schema、編輯器選型或施工核准
- **採用限制**：產品候選只考慮免費開源編輯器；OpenAI Codex／ChatGPT 與 Anthropic Claude 是必查的一手參照，Google Docs、Microsoft Word 及 VS Code 補充交叉核對；商業產品能力不混入 OSS 採用組合
- **既有邊界**：沿用已完成的 Memory／agent runtime 研究，不藉編輯器選型重開其責任或資料模型

## 0. 讀法與證據等級

最新產品方向依[綜合稿 §6.2](../2026-09-09-jd-oss-editor-capabilities-and-gaps.md#62-owner-已同意的產品方向訪談主導ai-持續撰寫)。後文 pending 選項及舊 probe 是比較材料；「人改待審仍待審」可重議，尚未指定持久逐項修訂引擎。新版情境與驗證順序依[App 能力對照](../2026-09-09-jd-app-native-capability-crosswalk.md)。

本文逐項區分：

- **Fact**：來源直接陳述或原始碼直接呈現的行為。
- **Inference**：由一項或多項 Fact 可合理推出，但來源未直接保證的結論。
- **Mapping**：把外部證據映射到 Caliburn 新 JD app 的研究問題；不是已決設計。
- **Unknown**：來源未證實、版本未固定，或必須由候選 OSS 的限界測試回答。

頁面未公開更新日期或套件版本時，本文只記「2026-09-09 存取」，不把當日誤寫成發布日期。會變動的官方文件與 `main` 分支原始碼仍須在選型 gate 固定版本後重查。

## 1. 可先確立的共同原則

1. 模型產生工具呼叫，不等於工具已執行；工具執行成功，也不等於文件已保存或使用者已接受。
2. App／tool harness 必須持有實際執行權，驗證 app 已知的文件、操作者與目標版本，並把可解讀的結果回給模型與 UI。
3. 「成功」必須指出成功到哪個邊界：已產生、已套用、已保存、待審、已接受。跨廠商不存在一個可直接沿用的單一 `success` 語意。
4. 目標版本不相符時應先重讀並重新規劃；部分成功或結果未知時應先對帳，不可盲目重播可能有副作用的操作。
5. 「人工修改 AI 待審內容後仍維持待審」有公開產品先例，但不是共同規則。它是 Caliburn 必須明確選定並由 OSS 能力驗證的產品政策。
6. 編輯器文件格式與保存形狀必須由免費 OSS 候選的實際序列化、重開與審閱行為推導；本文不先發明 schema，也不承諾自建審閱引擎。

## 2. 官方與原始碼證據

### 2.1 OpenAI：function calling 與 apply patch

**來源與版本**

- [Function calling](https://developers.openai.com/api/docs/guides/function-calling)，OpenAI 官方現行文件，2026-09-09 存取；頁面未公開固定 API 版本或更新日期。
- [Apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)，OpenAI 官方現行文件，2026-09-09 存取；頁面未公開更新日期。
- [Agents SDK：Results](https://openai.github.io/openai-agents-js/guides/results/)、[Running agents](https://openai.github.io/openai-agents-js/guides/running-agents/)、[Tools](https://openai.github.io/openai-agents-js/guides/tools/)，OpenAI Agents SDK JavaScript 現行文件，2026-09-09 存取；頁面未釘選本文適用的 npm 版本。

**Fact**

- Function calling 的流程是模型產生呼叫，應用程式執行函式，再以相同 `call_id` 回傳 `function_call_output`。模型不替應用程式完成外部副作用。
- Strict mode 約束工具輸入符合所宣告的 JSON Schema。
- `apply_patch` 由模型提出結構化 diff；整合端解讀、套用並對每個 call 回傳一個 output。結果狀態可為 `completed` 或 `failed`，整合端自行決定整批原子套用或逐檔套用。
- Apply patch 文件以「檔案不存在」「上下文不符」等可行動錯誤示範模型重新讀取或調整 patch。
- Agents SDK 將一次 run 的 items、tool output、interruptions 與 state 暴露給應用程式；串流完成、失敗與取消是不同狀態。工具 timeout 可選擇把錯誤當成結果或拋出例外。
- SDK 可保存只供應用程式使用、不進模型歷史的 metadata；這和送回模型的文字／結構化 tool output 是不同通道。

**Inference**

- Strict mode 只能提高參數形狀可靠度，不能保證選對文件、內容語意正確、變更已保存，或已獲人工接受。
- `call_id`／tool call ID 是呼叫與結果的關聯鍵；官方文件沒有說重送相同 ID 會替外部副作用去重。replay same call ID 不等於 idempotency 或 deduplication。
- `apply_patch_call_output.status=completed` 只證明整合端所定義的 patch 操作完成；不能直接映射成 JD 已保存或已核准。
- `failed`／`is_error` 只證明回報失敗。若整合端採逐項套用或在副作用後失去回應，失敗不等於「沒有副作用」；仍須用 authoritative state 對帳。
- Agent run state 可幫助續跑與呈現執行結果，但不是外部文件 exactly-once 保存的證明。

**Mapping**

- JD 工具描述應明說它操作的是候選變更、直接編輯或唯讀查詢中的哪一種，並由 App 注入或核對文件身分、actor 與目標版本。
- App 要保留可供 UI 與重試決策使用的執行事實，不能只把模型最後一句自然語言當成功憑證。
- 是否整批原子套用是產品與編輯器 adapter 的能力／政策，不能從 OpenAI 工具名稱推定。

**Unknown**

- 官方頁面沒有替任意第三方文件儲存定義「已保存」「待審」「已接受」或 idempotency；這些仍屬 App 契約。
- 官方頁面沒有替自訂工具提供以 `call_id` 為鍵的副作用去重保證。
- 在固定 SDK 版本前，錯誤類型與序列化細節仍須依實際套件版本重查。

### 2.2 Anthropic：text editor 與錯誤結果

**來源與版本**

- [How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works) 與 [Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，Anthropic 官方現行文件，2026-09-09 存取。
- [Text editor tool](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)，工具型別 `text_editor_20250728`，供 Claude 4 系列使用；文件 changelog 記載 2025-07-28 版本，並記載 2025-04-29 版移除 `undo_edit`。
- [Writing effective tools for agents](https://www.anthropic.com/engineering/writing-tools-for-agents)，Anthropic Engineering，發布 2025-09-11。

**Fact**

- Client tool 由模型請求、應用程式執行，結果以相同 `tool_use_id` 回傳；錯誤以 `is_error: true` 表示。
- 官方建議錯誤內容具可行動性。模型可能依錯誤修正呼叫，文件描述常見為重試二至三次，但沒有承諾外部副作用的 idempotency。
- `text_editor_20250728` 的 `view` 可回傳 1-based 行號；`insert` 使用 `insert_line`。行號雖非每次必需，卻是範圍與插入操作的重要定位資訊。
- `str_replace` 的 `old_str` 必須含空白完全相符，且整合端必須驗證它恰好只出現一次。零次或多次符合、路徑或權限問題應回報錯誤。
- 備份、路徑安全、權限與工具實作均是應用程式責任；內建工具定義不會代替執行端完成這些工作。
- 工具設計文章建議清楚描述用途、輸入、輸出與限制，並以實際任務 eval 驗證；錯誤應讓 agent 知道如何修正。

**Inference**

- 唯一符合與明確目標位置可降低錯改，但文字檔行號／字串替換模式不能直接證明適合結構化 rich-text JD。
- 模型會因錯誤再呼叫，不代表 App 可以對未知或部分成功的副作用安全重播。

**Mapping**

- 新 JD 工具需要穩定且可驗證的結構定位方式；到底是 node ID、range、step 或其他形式，應由入選 OSS 的原生模型決定。
- 工具錯誤至少要讓模型與 UI 分辨目標不存在、目標不唯一、版本過期、權限／驗證失敗，以及結果未知；本文不規定 wire schema。

**Unknown**

- Anthropic text editor 沒有定義 rich-text suggestion 的合併、接受、拒絕或保存語意。
- 其重試敘述沒有提供 exactly-once 保證或跨應用程式的通用重試次數。

### 2.3 VS Code：同一產品內已有兩種審閱模型

**來源與版本**

- [Review AI-generated code edits](https://code.visualstudio.com/docs/agents/run/review-code-edits)，Visual Studio Code 官方文件，頁尾日期 2026-09-02。

**Fact**

- 新 agent host 模式把 agent 變更直接套用並保存到 session folder／worktree，沒有「pending changes」批准狀態；使用者改由 diff、source control、PR 或 checkpoint 審閱。
- 檔案標記為 reviewed 後，只要人或 agent 再改該檔案，reviewed 狀態便會清除。
- 舊 extension host 模式把變更保存到磁碟並標記為 pending；重新開啟 workspace 後 pending 仍可恢復。使用者可逐項或整批 Keep／Undo，Git staging 會自動接受對應 pending change，discard 則拒絕。
- 敏感檔案的 pre-apply approval 和變更套用後的 review 是不同控制點。

**Inference**

- 即使同一產品，也可因執行環境選擇「先保存、後看 diff」或「先保存為 pending、再 Keep／Undo」。因此供應商產品不能提供唯一共同政策。
- 「已保存」和「已接受」可以是兩個獨立狀態；新版也證明產品可以完全不設持久 pending。

**Mapping**

- Caliburn 必須先決定 JD 的批准語意，再選擇能原生承載它的免費 OSS；不能把 VS Code 的 Git/worktree 模型直接搬成 rich-text 實作。
- 若採 reviewed 標記，後續人／AI 修改是否清除 reviewed 狀態是必須明定的產品規則。

**Unknown**

- 文件沒有承諾把這兩種 code review 狀態映射到結構文件中的 suggestion identity、作者 lineage 或局部接受／拒絕。

### 2.4 Google Docs：穩定版本前置條件與預覽 suggestions 必須分列

**來源與版本**

- [documents.batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)，Google Docs API 官方文件，更新於 2026-07-07 UTC。
- [documents.get](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get)，Google Docs API 官方文件，更新於 2026-08-27 UTC。
- [Requests](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request)，Google Docs API 官方現行文件，2026-09-09 存取。

**Fact — 一般可用契約**

- `batchUpdate` 會先驗證每個 request；其中一個無效時整批不套用。通過驗證後，該批更新以原子方式套用。
- `requiredRevisionId` 不符合目前 revision 時不處理更新並回 HTTP 400。
- `targetRevisionId` 允許伺服器把變更對近期協作者更新做 reconciliation；revision 過舊時回 HTTP 400，呼叫端應重新讀取最新文件。
- 原子套用不表示呼叫端可預測協作者後續改動；回應後的文件仍可能繼續改變。
- `documents.get.suggestionsViewMode` 可選擇建議內容的讀取視圖，該欄位未標 Developer Preview；不能與新增的 comment 讀取或 suggestion 寫入能力混為一談。

**Fact — Developer Preview**

- 2026-07-07 的 `batchUpdate` 文件列出 `writeMode=SUGGEST`、`suggestionResponses` 與 `commentUpdateState`，並清楚標示為 Developer Preview。
- Requests 文件中的接受、拒絕、刪除 suggestion 請求亦標示 Developer Preview。
- Preview response 可回報 suggestion IDs，以及 comment 更新為 `ALL_SAVED` 或 `ALL_FAILED_UNKNOWN_REASON` 等狀態。
- `documents.get.commentsViewMode` 標 Developer Preview；細部 suggestion／comment 能力仍須逐欄核對，不能因位於同一份文件就視為同等穩定。

**Inference**

- Google 的穩定 revision 前置條件與原子 batch 是版本衝突處理的強證據；它們不等於任何本機 OSS editor 已提供相同能力。
- `ALL_FAILED_UNKNOWN_REASON` 顯示官方 API 也需要把「原因未知」當成一等結果，而不能硬轉成成功或可安全重試。

**Mapping**

- JD App 應研究「要求精確基準版本」與「容許在近期版本上協調」兩種策略；具體能力須由本機編輯器／保存層驗證。
- Google Preview suggestions 可當產品行為參考，不得當成免費本機採用元件，也不能被描述成成熟、正式或完整覆蓋。

**Unknown**

- Preview 的可用資格、穩定性、覆蓋範圍及未來相容性均不能視為 GA 保證。
- Google 的 server-side collaboration／revision reconciliation 不代表 Caliburn 單機文件應複製同一模型。

### 2.5 Microsoft Word：全員追蹤是另一種政策

**來源與版本**

- [Track changes in Word](https://support.microsoft.com/en-us/word/training/track-changes-in-word)，Microsoft Support；適用清單涵蓋 Microsoft 365、Word 2024／2021／2019／2016、iOS 與 Web，2026-09-09 存取，頁面未公開精確更新日期與 build。
- [Review mode in Word](https://support.microsoft.com/en-us/office/review-mode-in-word-647b5ad8-0e52-47d5-9d3c-9b07c1d506a1)，Microsoft Support，2026-09-09 存取，頁面未公開精確更新日期與 build。

**Fact**

- Track Changes 可選 For Everyone 或 Just Mine；啟用後新增、刪除等修改會保留標記，不同作者可有不同顏色。
- Review mode／受保護的 review 流程可讓 reviewer 的修改成為 tracked changes，再由有權限者接受或拒絕。
- 隱藏 markup 只改顯示，不會從文件移除 tracked changes。

**Inference**

- 「所有人的編輯都進審閱」是可行產品政策，會比只追蹤 AI 更強調作者、批准權與顯示模式。

**Mapping**

- Word 只作付費產品參照。若 Caliburn 考慮全員追蹤，免費 OSS 必須證明作者 lineage、重開、局部接受／拒絕和有效正文投影能成立。

**Unknown**

- 公開支援文件沒有精確規定「使用者直接改寫另一位作者尚未接受的 insertion／deletion」時，原 suggestion 會被合併、分裂、取代或保留哪個 identity。本文不替 Word 推測答案。

### 2.6 Claude Code 與 Codex：公開 UI 契約顯示政策差異

**來源與版本**

- [Claude Code IDE integrations](https://code.claude.com/docs/en/ide-integrations)、[Permission modes](https://code.claude.com/docs/en/permission-modes)、[Desktop](https://code.claude.com/docs/en/desktop) 與 [Checkpointing](https://code.claude.com/docs/en/checkpointing)，Anthropic 官方現行文件，2026-09-09 存取；頁面未公開固定產品版本或更新日期。
- [Code review in Codex](https://learn.chatgpt.com/docs/code-review)，OpenAI 官方現行文件，2026-09-09 存取；頁面未公開固定產品版本或更新日期。

**Fact**

- Claude Code VS Code extension 的 Manual mode 在編輯前顯示 proposed diff 並詢問；使用者能在接受前直接編輯 proposal，Claude 會得知使用者已改動。
- Claude Code 另有 `acceptEdits`／Desktop auto accept：變更可直接套用，再從 editor、Git diff 或 checkpoint 審閱。
- Codex review pane 以整個 Git repository 為範圍，可能同時包含 Codex、人與其他來源的未提交變更；使用者可依檔案或 hunk stage／revert，並選 Unstaged、Staged、Commit、Branch 或 Last turn 等比較範圍。

**Inference**

- Claude proposed diff 是「人改候選後仍待接受」的直接公開先例；同一產品的 auto-accept 又證明它不是所有情境的共同規則。
- 這個 precedent 證明的是 Manual mode 中接受前可編輯的互動政策。官方未提供 proposal 保存與檔案交易的完整契約，不能再推成 proposal 本身已 durable save、跨重開可恢復，或具有 JD 所需的持久 suggestion lineage。
- Codex 的 review 是 Git 差異審閱，不是持久 inline suggestion；不可由 stage/revert 推出 rich-text suggestion 的身份與保存語意。

**Mapping**

- Caliburn 可以把「人編輯 AI 候選後，對編輯後版本按接受」列為正式候選政策，但須明定原 AI 建議與人工修訂的 lineage、拒絕後回到哪個基準，以及模型續談讀到哪個版本。
- 付費產品只用來證明產品政策存在，不是 editor 採用候選。

**Unknown**

- 公開文件沒有揭露 Claude／Codex 的內部資料模型、交易邊界或 exactly-once 保存；本文不推測。
- Claude proposed diff 是否 durable、多久保留、重開後能否繼續編輯，在上述公開文件中沒有保證。

### 2.7 免費 OSS 邊界：Plate／ProseMirror 目前只足以支持「需驗證」

**來源與版本**

下列是本工作線的初讀履歷，不另作最新套件權威。採用比較以[Plate 固定版本證據](2026-09-09-jd-oss-plate.md)及[Lexical／Tiptap／ProseMirror 固定版本證據](2026-09-09-jd-oss-alternatives.md)為準；後者已核對搬家後的 PM transform 1.12.1／changeset 2.4.2，不能把以下 2.4.0 沿革當最新版。

- [Plate Suggestion](https://platejs.org/docs/suggestion) 與 [Controlled value](https://platejs.org/docs/controlled)，Plate 官方文件，2026-09-09 存取。
- [`@platejs/suggestion` package.json](https://github.com/udecode/plate/blob/main/packages/suggestion/package.json) 與 [`rejectSuggestion.ts`](https://github.com/udecode/plate/blob/main/packages/suggestion/src/lib/transforms/rejectSuggestion.ts)，Plate GitHub `main` 原始碼，2026-09-09 存取；讀取時 package 版本為 53.2.3、授權 MIT，但 `main` 仍會變動。
- [Plate v53.2.3 release](https://github.com/udecode/plate/releases/tag/v53.2.3)，release 顯示 2026-06-27；包含 block removal suggestion 缺少 `userId` metadata 的修正。
- [ProseMirror changeset](https://github.com/ProseMirror/prosemirror-changeset)，MIT；v2.4.0 changelog 日期 2026-02-14，加入 JSON serialization；repository 於 2026-04-01 封存並移至新位置。

**Fact**

- 免費 `@platejs/suggestion` 支援文字／block suggestions、IDs、`userId`、`createdAt`、類型與接受／拒絕 transforms；suggestion metadata 位於文字 marks 或 block 屬性。`withoutSuggestions` 可讓指定操作不建立 suggestion。
- Plate editor value 可由應用程式控制、序列化並重新初始化；editor 同時持有 selection、history 與 plugin state。
- Plate 文件中的完整 Suggestion／Comment example 與較完整 UI 標為 Plate Plus，不能算免費 OSS 能力。
- ProseMirror changeset 提供變更 spans／metadata 與 JSON serialization，是差異計算 primitive；它本身不是完整的持久審閱產品。

**Inference**

- Plate 免費 core 有機會承載「人工修改後仍待審」，但文件與 source 尚未證明跨重開、交疊編輯、局部接受／拒絕、undo／redo 和 lineage 全部符合產品政策。
- suggestion metadata 位於 editor value，表示保存候選應從該原生 value 驗證；不能據此推定所有 plugin／review state 都已持久化。

**Mapping**

- 下一個限界驗證應用固定 OSS 版本測試 serialize → close → reopen → edit pending → accept/reject，而不是先設計自有 suggestion engine 或 DB schema。
- 若免費 OSS 缺少必要行為，應列出證據與選項回到 owner 決策，不得默默放寬需求或承諾自建引擎。

**Unknown**

- 目前尚無證據證明任何候選免費 OSS 已完整滿足 Caliburn 所需的文件、suggestion、保存、重開與人機續編組合。

### 2.8 必查補證：ChatGPT、Codex 與 Claude 的現行文件體驗

以下均於 **2026-09-09** 查閱。OpenAI／Anthropic 是兩個發布者，不將同家多個產品算成多家共識。這些是託管產品的官方功能契約，**不提供可採用的 OSS 編輯器授權**；方案限制只是證據適用條件，不是採購建議。未標固定 build 的頁面不虛構版本。

| 來源／適用狀態 | Fact：直接公開的能力或改版 | Unknown／映射限制 |
|---|---|---|
| [OpenAI Model Release Notes](https://help.openai.com/en/articles/9624314-model-release-notes)，2026-05-28 條目 | GPT-5.5 Instant／Thinking 不再支援 Canvas；寫作／程式產出改由聊天中的 writing／code blocks 支援；付費者透過 legacy models 限時續用 Canvas | 不能擴大為所有 ChatGPT 平台全面停用，也不能推出新 writing blocks 已具舊 Canvas 的全部版本／差異功能 |
| [Introducing canvas](https://openai.com/index/introducing-canvas/)，2024-10-03，**沿革** | 現行頁首已說本文描述 launch，並把 current writing／coding 導往 release notes。當時描述手編、選取及回到前版 | 只保留歷史功能／研究理由，不當現行標準；原 9930697 Help URL 本輪無可讀頁面，搜尋快取不替代有效契約 |
| [Create and edit files with ChatGPT Work](https://help.openai.com/en/articles/20001278-creating-and-editing-documents-spreadsheets-and-presentations-with-chatgpt-work)，現行指南、顯示 12 天前更新 | 可依指示／來源建立或編輯文件，後續繼續要求修改；desktop 側欄開啟支援檔案後，可選取局部提出變更。雲端 Library 與本機 project／folder 分開，不自動同步 | 功能依方案、workspace、檔案及介面；未公開完整逐筆 diff、手編追蹤身分、跨重開修訂與保存交易。既有成品可反覆改不等於同一 rich-text 審核引擎 |
| [Codex Code review](https://learn.chatgpt.com/docs/code-review)，現行 app 文件 | Review pane 讀實際 Git 狀態，含人與 Codex 的修改；Last turn、unstaged／staged／commit／branch 是不同比較範圍。可附行級回饋並續談修正；file／hunk 可 stage 或 revert | 需要 Git repository；「這次 AI 改動」與「全部未提交改動」不同。是比較基準與可修正成果的先例，不要求 JD 採 Git，也不證明任意結構修改安全回退 |
| [Claude／Desktop Artifacts](https://support.claude.com/en/articles/9487310-what-are-artifacts-and-how-do-i-use-them)，現行指南、顯示本週更新 | 聊天要求更新 artifact；Markdown 可選文字並輸入修改請求，由 Claude 原地修改；版本 selector、複製／下載已公開。官方說選取可避免另在聊天描述位置 | 適用 Free／Pro／Max／Team／Enterprise 並須啟用 Code execution and file creation；本文限 Claude／Desktop。這裡的 edit in place 是 AI 代改，不足以證人能直接打字編本文、完整 diff 或無損還原 |
| [Claude Cowork Artifacts](https://support.claude.com/en/articles/14729249-use-artifacts-in-claude-cowork)，2026-08-19 起新系統，現行指南、本週更新、GA | Pro／Max／Team／Enterprise 的 Cowork Desktop／cloud 可用既有 artifact 連結續改；每次更新存新版，可比較舊版與目前版、還原。8/19 前 live artifacts 仍可讀，但不能原地續改 | 部分受管設定仍用舊系統。未公開差異粒度、任意相依／組外修改的選擇性回復或 JD 結構保真；也不能外推一般 Claude 聊天已具相同功能 |

**Inference：**兩家均有持續對話驅動可見成果、局部指示及後續修正的正式參照；Codex 與 Cowork 顯示比較／回復可有不同基準。這支持研究「對話＋實際文件＋修正通道」，**不支持唯一批准時機、所有產品完整 diff、永久 pending 或共用內部資料格式的宣稱**。

**Mapping：**Caliburn 仍依 Owner 要求提供全部實際新增／刪除／改寫可查；某參照產品沒有公開保證，不會取消這項需求。對「為什麼這樣做」，可引用 Claude 對選取能免除描述位置的公開理由；其餘降低錯誤或負擔的判断標為本案推論，不代廠商發明內部研究結果。

### 2.9 Word／Google：補充交叉核對，不代替兩家必查來源

均於 2026-09-09 讀官方現行頁，未公開精確 build；皆為商業功能參照，不列入免費 OSS 採用組合。

- **Word 候選改寫（Fact）**：[Rewrite text](https://support.microsoft.com/en-us/word/copilot/rewrite-text-with-copilot-in-word) 明示可選文字、看改寫候選，並直接在 suggestion box 打字，最後 Replace；也可 Insert below。這是人改候選後仍另行套用的先例，不證明持久 tracked-change lineage。可用性依 Microsoft 365 授權／設定。
- **Word 直接續編（Fact）**：[Edit with Copilot](https://support.microsoft.com/en-us/word/edit-with-copilot-in-word) 是直接改目前文件，可 Undo／查看前版；若 Track Changes 已開，AI 修改會追蹤，但 Copilot 不能開關或接受／拒絕 tracked changes。Work IQ 用於 shared document 時則先預覽確認，官方理由為避免向協作者意外分享內容；本案不擴張多人需求。功能仍分批往 GA，Preview／Frontier 及方案条件分列；同頁提示改動附有 comment 的段落可能刪除 comment，不能假定所有附加資料皆保留。
- **Google 文件內建議（Fact）**：[Write & edit with Gemini](https://support.google.com/docs/answer/13447609?hl=en) 支援對話或選取改寫，建議出現在正文，逐項／全部接受或全部拒絕；[現行總頁](https://support.google.com/docs/answer/14206696?hl=en) 把此功能標為 Gemini Beta／Workspace Experiments，不能泛稱所有帳號 GA。總頁也區分側欄 Preview／Insert 與正文；側欄對話恢復不能直接當文件保存證據。

**Inference：**同一產品可同時存在候選→套用及直接修改→檢視兩種流程；是否提供審閱與何時接受是兩個問題。「人改待審仍待審」有先例，但不是跨產品唯一規則。這些頁未公開的存儲、原子性、回覆遺失修復與持久身分仍為 Unknown。

### 2.10 既有 Python 顧問與 JavaScript 原生編輯器接線

2026-09-09 再查現行文件、隔離分析 Agent 的 `pyproject.toml`／`runtime.py` 與實際安裝原始碼。以下是接線證據，**未加入 JD Tool、未選 transport、未更換既有 Agent／Memory**。

| 證據 | 事實、版本及本案適用界線 |
|---|---|
| [LangChain tools](https://docs.langchain.com/oss/python/langchain/tools) | Fact：函式／`@tool` 形成模型工具，`ToolRuntime` 由框架注入且不出現在模型 schema，可讀執行 context／state；`Command` 可同時回傳 state 更新與匹配 ToolMessage。這不使外部文件寫入自動成為 checkpoint 交易的一部分 |
| 既有隔離 runtime | Local fact：`langchain==1.4.0`、`langgraph==1.2.11`；`build_agent` 已接受 `Sequence[BaseTool]`，由 `create_agent` 使用。`live_memory.py` 已使用 ToolRuntime，`consolidation_request.py` 已使用 `content_and_artifact`。JD 能接既有工具面，不必另建主 Agent；現階段此入口仍沒有 JD tools |
| [LangChain MCP](https://docs.langchain.com/oss/python/langchain/mcp)、[正式遷移說明](https://docs.langchain.com/oss/python/migrate/langchain-mcp-adapters) | Fact：現行是 `langchain[mcp]>=1.4.0` 的 `MCPAdapter`，**beta**，替代獨立 `langchain-mcp-adapters` 的 MultiServerMCPClient 路線。支援 stdio／Streamable HTTP；舊 session 方法不直接等價搬入，新工具每次呼叫管理自身 session。工具 isError 轉 ToolMessage error，transport 失敗拋錯。已核對本地 1.4.0 namespace 的 beta 警告，不把舊範例當現行穩定契約 |
| [Python 3.12 subprocess](https://docs.python.org/3.12/library/subprocess.html)、[asyncio subprocess](https://docs.python.org/3.12/library/asyncio-subprocess.html) | Fact：標準庫支援固定程式的參數、stdin／stdout／stderr、退出結果；同步 run 可有 timeout，非同步版本需自行安排等待／取消清理。PIPE 需正確 drain，資料量需有界；啟動時間不一定可被 timeout 即刻打斷。Windows 要使用有效事件迴圈及正確 process cleanup，不由結束程序推論外部保存沒發生 |

**Mapping／推薦：**先用既有 LangChain tool 接點包住有限 JD App 能力，由 App 呼叫固定本機 headless 編輯引擎。模型給資料與已讀到的目標，不給可執行程式、shell 或任意磁碟路徑；文件 scope／版本／操作關聯由 runtime 帶入。引擎負責原生文件運算，App 負責保存及回傳真實結果。MCP 是有需要時可選的標準邊界，不是「讓 LLM 用 App」必備條件；不為跨語言而默認採 beta 或重寫現有 Agent。

**Unknown／有限驗證：**固定呼叫的繁中往返、原生引擎失敗／取消、輸出截斷或失聯，以及文件保存與回執如何形成同一可查結果。成功 ToolMessage、process exit 0 或 editor transform 完成，都不能取代 durable save 的證據。若完整部署需要持續 process／MCP，再以實測延遲、生命週期及維護代價決定；不預先造通用工作排程器。

上述本地核對位置位於 `.worktrees/analysis-only-agent/experiments/analysis-agent/`，是既有隔離成果，非 root production 行為；其 Memory 與對話 owner 沿用原有設計，不因 JD 橋接改判。

**隔離 current code 的精確接點（另一路唯讀複核）：**

| 可沿用 | 不可照抄／仍需證明 |
|---|---|
| [runtime.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/runtime.py) 的 BaseTool 注入；[service.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/service.py) 的 document→thread／run 綁定 | 此 factory 不是新 JD 工具或保存已實作的證據；保留工具名稱及依文件綁定的檢查 |
| [live_memory.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py) 的 App 綁 scope／input／版本與 checkpointed operation identity | 重用由 App 產生身分的責任，不能把 Memory source refs 或 head 欄位照抄為 JD 的文件定位協議 |
| [conversation.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py) 的無效 JSON 不執行、同 call 回錯、有上限修正及 quiescent 後封存 | JD 未知寫入效果不能套入既有 read／notification／Memory repair 恢復白名單；`input=None` 不是任意外部寫入的安全重播權 |
| [publication.py](../../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/publication.py) 的 operation identity、request digest、expected revision、receipt＋head 同交易及 uncertain 對帳 | 該交易保證限已知 Memory publication；immutable artifact、processed-source cursor、repair_sources 不直接成 JD schema。JD 的實際文件＋版本＋保存結果仍須獨立形成可查保存單位 |

CT49 的錯誤後成功修正與 CT50／51 的訪談、重開、容量證據可支持沿用 runtime；它們沒有驗收 JD 寫作、文件編輯或文件交易，既有 minor 措辭問題也未被編輯器測試解決。最新效力仍依 register，不以較早稿內的測試數字替代。

### 2.11 Plate 與 Deep Agents 的分工：不用從零造編輯器，App 接線仍必要

2026-09-09，Owner 已同意 Plate 框架方向，詢問是否仍要自建、或使用 Deep Agent 自建。以下不重新選擇主 Agent 或 Memory。

**Official fact：**[Deep Agents 現行概覽](https://docs.langchain.com/oss/python/deepagents/overview)將它定位為 agent harness：提供工具、檔案／context、子代理及可選規劃，底層使用 LangChain／LangGraph；可注入自訂工具。[Customization](https://docs.langchain.com/oss/python/deepagents/customization)亦以 tools 配置接應用能力。這些能力不提供結構 JD 的 editor schema、畫面、差異或 suggestion 持久化契約。不能把工具呼叫暫停／批准當成文件持續審閱引擎。

**Local fact：**既有隔離成果已鎖定 `deepagents==0.7.13`，不是本輪新增套件。`runtime.py` 主迴圈使用 LangChain `create_agent`；`consolidation_tools.py` 已用 Deep Agents 的 CompositeBackend、StateBackend、FilesystemMiddleware，`skills.py` 已用 FilesystemBackend、SkillsMiddleware。核對位置為 `.worktrees/analysis-only-agent/experiments/analysis-agent/` 下的 pyproject 與 `src/analysis_agent/`，此次未改任何 runtime／Memory。

**Mapping：**Plate 承接文件編輯 primitives；既有顧問透過 JD App 工具使用它。需要本專案實作的是 JD 內容／畫面配置、工具 wrapper、引用與版本檢查、保存／真實錯誤結果，以及尚未完成的審閱整合。Deep Agents 不會自動補齊 Plate 的 R4 codec 或 logical-group 缺口。若「用 Deep Agent 自建」意指叫 coding agent 協助寫程式，那是開發方式；產出的接線程式與正確性責任仍屬本專案，不能當成現成框架能力。

### 2.12 Plate 選定後的審閱取捨複核

2026-09-09，停止廣搜與新增 probe；針對 C02／C03 的續改／取消問題複核既有材料及三份官方頁。

**官方產品事實：**[Codex code review](https://learn.chatgpt.com/docs/code-review)仍提供基於 Git 的比較、行級回饋及 file／hunk revert，不能拿它證明個別取消已淘汰。[Claude Cowork artifacts](https://support.claude.com/en/articles/14729249-use-artifacts-in-claude-cowork)仍明列每次更新保存版本、版本比較及還原；本文適用 2026-08-19 起的新系統，未公開語意建議分組或任意續改鏈結算。[VS Code review](https://code.visualstudio.com/docs/agents/run/review-code-edits)本次頁尾為 2026-09-09（前次讀取為 9/2）；新 Agent Host 直接套用保存、舊 extension host 保存 pending 的區別仍成立。三者都是商業產品的行為參考，沒有提供本機 Plate 的免費完整審閱實作。版本／比較與可修正成果有共同先例，單一接受時機沒有共同規定。

**固定原始碼事實：**Plate commit `cee7a4ec0328718d8cf147094466b597215f5406` 的 [findSuggestionProps](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/queries/findSuggestionProps.ts)18 行的參數為 at／type；36–77 行可找目前、後一點、前一點的 suggestion；100–124 行在 active type／作者符合時可沿用 ID／createdAt。84–95 行的 block 起點與前段 line-break 分支亦可沿用 ID，該分支未比較作者／type。[getSuggestionKeys](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/getSuggestionKeys.ts)39–42 行核對 current user，[getSuggestionId](https://github.com/udecode/plate/blob/cee7a4ec0328718d8cf147094466b597215f5406/packages/suggestion/src/lib/utils/getSuggestionId.ts)5–19 行取最後一個 suggestion key 作 active。此路徑沒有 App 語意群組條件。

**Inference／仍未知：**不能只把每個 jd_edit 批次當一群、收集新生 IDs，就宣稱不同產品建議必然獨立；原生 ID 可沿用，App 記錄不能代替原生隔離能力。**尚未實测兩個不同產品群組共用 ID**，不能列為已重現反例；R01 兩處獨立和 R3 三作者三 ID 的原結果不變。即使限制群組不重疊，鄰接仍須考慮，因此「不重疊＋有問題就停止」也不是完整 B05／B06 已交付。

**本案映射：**現在足以向 Owner 提出完整生命週期取捨，無須再用零碎正證拖延產品裁決。若要跨多次續改仍可整組接受／取消，成員、相依、結算範圍需設計；若改為工作稿＋歷史查閱，必須明說不再提供上述操作保證。推薦與效力分開，見[審閱提案 §7](../2026-09-09-jd-editing-and-review-working-design.md#7-plate-選定後的審閱生命週期取捨)。此複核不授權變更 Memory、production 或自造引擎。

### 2.13 契約定稿前的官方複核：參數、結果、版本與重試

**查閱日：2026-09-10。**Owner 再次要求契約也須向大廠現行做法學習。以下是實際開啟官方全文後的增量，補足前文；不因本案 schema 已寫出就倒推它是共識。產品體驗仍依 §2.8／§2.12 的 Codex／ChatGPT／Claude 證據，不能用 API 文件猜測閉源產品內部保存法。

| 官方來源／適用範圍 | Official fact | 本案映射及不能推得的保證 |
|---|---|---|
| [OpenAI Function calling](https://developers.openai.com/api/docs/guides/function-calling)，现行 Responses／function tools；非預覽頁，未提供本文固定發布版號 | 工具描述應包含用途、參數及輸出含義；App 已知的參數由程式帶入。模型發出呼叫後由 App 執行，結果以 `call_id` 配對；結果內容可由 App 定義為 JSON／文字／錯誤碼 | 模型不填文件 scope、保存 identity、digest 或原生 path。三工具／七命令及欄位名是 Caliburn 對 Plate 的有限映射，官方沒有相同 JD 契約 |
| [OpenAI Strict mode](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)與[Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)，現行支援子集 | 官方推薦 strict；需封閉 object、所有欄位 required，選填可用 nullable；不支援 `allOf`／`if`／`then` 等完整 JSON Schema 能力。Responses 未設定 strict 會嘗試正規化，不能相容時退為 non-strict，回傳工具顯示 `strict:false`；明設 false 才固定採非嚴格模式 | 本機 Draft 2020-12 通過不等於 provider wire 通過。要檢查實際 adapter 送出的 schema 與模式；如因現行 provider 限制採 non-strict，須明列代價及完整 App 驗證，不能稱永久最佳解或默默降級 |
| [Anthropic Define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)、[Strict tool use](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)及[Schema limitations](https://platform.claude.com/docs/en/build-with-claude/structured-outputs#json-schema-limitations)，現行非 beta 介面，具模型／子集限制 | 自訂工具用 description＋input_schema；strict 约束輸入形狀。但 strict 子集不支援遞迴 schema，和 OpenAI 可支援遞迴的能力不同。官方 SDK 的 structured-output helper 可對部分不支援約束作轉換，再按原 schema 驗回覆 | 不宣稱同一遞迴 JD schema 可原樣在兩家 strict 運行；helper 的存在也不證明既有 LangChain／provider 接線已採用它。不得自造跨廠通用 schema compiler，或移除必要文件 grammar 只求 API 接受 |
| [Anthropic Handle tool calls](https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls)，現行自訂 client tool 契約 | App 執行後以匹配 `tool_use_id` 回結果，錯誤可用 `is_error`。工具結果與呼叫需按正式訊息順序接續 | call/result 配對不等於外部文件交易或自動去重；既有 harness 負責原生訊息接線，JD 保存結果由 JD App 證明 |
| [OpenAI apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)（沿 §2.1）與[Anthropic text editor](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)，`text_editor_20250728` 仍為現行文件示例 | Patch 與精確替換／行位置介面並存；Anthropic 要求替換恰好一個完全匹配，找不到／多處匹配回具體錯誤 | 可共同學習「可驗證的目標及可行動錯誤」；不能稱行號已淘汰，也不能據此要求 rich-text JD 自建字串 matcher |
| [Google Docs batchUpdate](https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate)，v1，頁面更新 2026-07-07；正常 edits／requiredRevisionId 與 Developer Preview suggestions 分列 | 整批預先驗證，任一無效則不套用；更新原子套用。requiredRevisionId 非最新版會拒絕。targetRevisionId 的協作合併是另一種契約 | 本案採基底檢查與整批發布有成熟參照；不採多人合併，也不借預覽 suggestion 功能聲稱免費 Plate 已具同等能力 |
| [AWS Well-Architected：mutating operations idempotent](https://docs.aws.amazon.com/wellarchitected/latest/framework/rel_prevent_interaction_failure_idempotent.html)及[Builders’ Library：safe retries](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)，前者現行指南仍引用後者 2021 原文 | 同次意圖保留 request token；同 token 重試回已記錄結果，同 token 不同參數應拒絕。記錄 token 與相關變更需滿足同一 ACID 邊界。現行指南也列不必要或過度複雜的去重為反模式 | JD 修改與回執同一 PG 交易、原 request 對帳、同鍵異 payload 拒絕採此原則；只接有限 JD 寫入，不建立通用重试服務。timeout 本身不證明未提交；不能把 call ID 當這項保證 |

**跨來源共同原則（Inference）：**工具可理解、App 執行與驗證、原生 call/result 正確配對、格式保證和實際副作用分開。兩家都提供 strict，但子集／預設／適用工具並不相同，不能稱「一份 schema 原樣跨廠」是共識。基底版本與防重複發布另有 Google／AWS 的直接契約支持；這不是 OpenAI／Anthropic 未公開的內部設計。

**對定稿的約束：**[正式 schema 附件](../2026-09-10-jd-editor-contract-schema.md)須列本機 SSOT、實際模型參數及 runtime 注入的分界，並指定既有 provider 的具體 binding 路徑與未驗限制；施工驗收要查實際送出形狀。模型工具輸入仍須經 App 完整驗證，strict 不替代來源、同文件／同版本、保存或專業品質檢查。文檔引用沒有帶入商業 SDK／服務授權；免費 OSS 採用仍按正式 profile 的逐套件 license 證據。現行 API／契約和成熟度是查閱時狀態，不擅自升級既有 Memory 模型／provider。

## 3. 跨廠共同原則與產品政策差異

**2026-09-10 定點複核：**Owner 再次強調參考大廠而非自行發明。重新開啟上節三份官方現行頁並讀取相關正文：Codex 仍列實際 diff、後續修訂及 file／hunk revert；Claude Cowork 新 artifacts 仍列逐次版本、比較與還原；VS Code 仍區分 Agent Host 直接保存與舊 extension-host pending。沒有新證據要求本案回到兩個操作頁、逐筆 pending 或自建審核引擎。這些頁面也**沒有**證明本案的整段 AI run 唯讀、三張 JD 資料表或某個版面布局是跨廠共識；它們保持明示的本案推薦／示意。工具／編輯能力需另依 Plate 官方插件和本案實證驗收，不以產品相似外觀當成可採用實作。

| 問題 | 可跨廠支持的共同原則 | 明顯的產品政策差異 | 對新 JD app 的意義 |
|---|---|---|---|
| 誰執行工具 | 模型提出呼叫；App／harness 執行並回傳結果 | 各家結果結構、error 通道不同 | App 保留實際執行責任，不能信任模型自報完成 |
| 目標定位 | 目標必須可驗證；失配要明確失敗 | exact string／line、revision ID、Git hunk、結構 node 各異 | 由入選 editor 原生模型決定定位，不能先套文字 patch |
| 原子性 | 必須清楚說明操作範圍 | Google batch 原子；OpenAI apply patch 把原子策略交給整合端 | 每種 JD 操作需在能力驗證後聲明，不能假定整個 turn 原子 |
| 保存 | 套用和保存是不同可觀察邊界 | 新 VS Code host 直接套用並保存；Claude Manual 顯示編輯前提案，proposal 的保存契約未完整公開 | UI／runtime 必須知道目前僅預覽、已套用未保存，或已保存 |
| 審閱 | 人需要可看見並判斷變更 | pending Keep/Undo、direct apply + diff、tracked changes、proposal-before-accept 都存在 | 審閱方式是產品決策，不是 LLM 供應商規定 |
| 人改 AI 待審 | 沒有跨廠共識 | Claude proposal 可先改再接受；VS Code 新 host 無 pending；Word 可追蹤所有人 | C02 政策必須獨立裁決並驗證 OSS |
| 錯誤 | 應回傳可行動且可歸因的失敗 | `is_error`、failed output、HTTP 400、unknown reason 各異 | UI 與模型都不能只收到模糊「失敗」 |
| 重試 | 先知道目前事實再決定 | 模型可修正參數；revision stale 要重讀；未知結果需對帳 | 不將 agent 自動再呼叫等同安全重試 |
| 版本／歷史 | 後續編輯會使先前審閱資訊過期 | revision、checkpoint、Git commit、suggestion IDs 模型不同 | 文件基準與 review freshness 必須由 App 明定 |

## 4. 結果語意：研究用狀態梯，不是 wire schema

討論 JD 工具結果時，至少要能指出以下哪一層有證據。名稱只是研究詞彙，不是欄位、enum 或 API 承諾。

| 邊界 | 能證明的事 | 仍不能證明的事 |
|---|---|---|
| 已提出 | 模型產生了具 call identity 的操作提案 | 工具執行、內容有效 |
| 目標已核對 | 文件／位置／基準版本在執行前符合 | 套用後仍沒有競態、已保存 |
| 已套用到 editor | editor 已接受全部或部分操作 | durable save、review 狀態 |
| 已保存 | 保存層已確認某一文件版本 | 人已接受、後續沒有修改 |
| 已保存且待審 | durable state 包含未決變更 | 該變更會被接受 |
| 已直接生效 | 依選定政策，保存即進 effective document | 有人工 review 或批准 |
| 已接受／拒絕 | 人對明確候選與基準作出決定 | 所有後續版本仍相同 |
| 部分成功 | 已知一部分已套用，另一部分未套用或失敗 | 整個操作可安全重播 |
| 結果未知 | timeout／斷線後無法證明是否產生副作用 | 成功、失敗或可重試 |

### 4.1 重試與版本原則

1. **目標或版本過期**：讀取最新 authoritative document／editor state，再讓 runtime 重新規劃；不得把相同位置或 patch 盲目重播。
2. **已證明尚未產生副作用的暫時失敗**：可以考慮有界重試；次數屬 runtime 政策，不從供應商文件照抄。
3. **部分成功**：先列出已套用與未套用範圍，接著對帳；除非該 operation 本身具已驗證 idempotency，不重播整批。
4. **結果未知**：先讀目前文件版本、operation receipt 或等價 authoritative fact。若無法對帳，UI 應保留 unknown 並要求人工處理。
5. **已保存但回應遺失**：再次插入／刪除可能重複副作用；先比對目標版本與內容。
6. **語意不合格**：schema strict 或工具呼叫成功不能解決，應留在候選、驗證或人工審閱流程處理。

同一 `call_id` 的 replay 只維持 protocol correlation，除非 Caliburn 自己有已驗證的 operation receipt／dedup 契約，不能視為安全重試。反過來，收到 `failed` 或 `is_error` 也不能自行推論「零副作用」；原子驗證前失敗、逐項套用中途失敗與回應遺失後的未知結果必須分開處理。

## 5. 「人改 AI 待審內容仍待審」：不是共識，應作 C02 政策裁決

本節 A–D 只是外部政策分類，不是產品決策代號；Owner 面前的先行選項統一依[綜合稿 §6](../2026-09-09-jd-oss-editor-capabilities-and-gaps.md#6-可供討論的具體審核生命週期)。原 C02 已有 WORKING 決策，最新補充只重開人工續改 pending 的政策；接受當下最新版及 AI 讀目前最新文件等方向不因此全部重問。

### 選項 A：編輯候選後再接受

- **證據先例**：Claude Code VS Code Manual mode 的 proposed diff 允許人在接受前修改，再允許執行或拒絕。
- **產品語意**：人改的是 proposal；修改後版本仍 pending，明確接受才成為 effective document。
- **優點**：保留批准 gate；人可修正 AI 草稿而不必先接受錯誤內容。
- **代價／待決**：本案接受當下最新版、模型續談讀最新文件的方向已定；仍須決定修訂歸屬、拒絕基準、交疊 suggestions 與必要的原文／待審呈現，並驗證其保存與讀取能力。
- **OSS gate**：固定版本實測 pending 上的插入、刪除、重寫、undo／redo、局部接受／拒絕與重開。

### 選項 B：直接套用與保存，事後看 diff／checkpoint

- **證據先例**：VS Code 新 agent host、Codex Git review、Claude Code `acceptEdits`／auto accept。
- **產品語意**：不存在 durable pending；人和 AI 直接改 effective document，review 是回顧或回復機制。
- **優點**：文件權威較單純，可能更接近多數免費 editor 的直接編輯路徑。
- **代價／待決**：改變目前「AI 只產生待審 changeset」的產品批准語意；錯誤內容可能在 review 前已生效。
- **決策要求**：若選此路，需由 owner 明確接受產品語意改變，不能以 OSS 缺口默默導入。

### 選項 C：所有人的編輯都成為 tracked change

- **證據先例**：Word Track Changes For Everyone／Review mode。
- **產品語意**：人工和 AI 都有作者歸屬，修改持續待審，直到有權者接受或拒絕。
- **優點**：來源與審閱一致，適合需要逐作者追蹤的流程。
- **代價／待決**：UI 與 lineage 更複雜；本人是否可批准自己的 edit、批次接受範圍、effective view 都要定義。Word 公開資料也沒有回答 edit-over-suggestion 的 identity 行為。

### 選項 D：人工直接編輯有效，AI 編輯待審

- **證據性質**：這是 Caliburn 可討論的混合 Mapping，並非單一來源的完整共同模式。
- **產品語意**：人在 pending 範圍以外直接改即生效；但人在 AI pending 區域的編輯需另選「仍 pending」「取代並解決原 suggestion」或「轉成人工 tracked change」。
- **優點**：保留日常人工編輯的低摩擦與 AI gate。
- **代價／待決**：交疊編輯、基準漂移、拒絕回復與 attribution 最容易含糊；不得在未驗證時假定 editor 會正確處理。

**本稿結論**：A 有真實公開先例；原 C02 的人工續改政策已有 WORKING 紀錄，現依 Owner 補充重議，替代政策尚未採用。沒有證據顯示免費 OSS 已完整承載所有效果。先依綜合稿選一個驗證方向，再用原生行為與具體缺口收斂產品規則，不把放寬一條規則誤寫為全部決策失效。

## 6. 責任分界（概念契約，不是模組或 schema）

| 參與者 | 應負責 | 不應被誤認為已負責 |
|---|---|---|
| LLM | 依上下文提出內容與工具呼叫；依可行動錯誤修正提案 | 執行副作用、確認保存、授予自己批准 |
| Agent runtime | 編排 call/result、停止條件、錯誤與續談；使用既有 Memory、當輪訊息及來源提供相關理解並保留其確定程度與更正 | 成為第二份文件／revision／suggestion store；從自然語言臆測保存成功 |
| Editor core／adapter | 依其原生文件模型套用或拒絕操作；回報實際作用範圍；提供經驗證的 serialize/reopen/review primitives | 決定產品批准政策；以 demo 宣稱 durable persistence |
| JD App／保存邊界 | 提供真實文件與 actor；核對目標版本；協調 editor 操作與 durable save；對帳 partial／unknown | 讓模型自帶 app 已知權威欄位；把 tool completion 當人工接受 |
| Review policy | 定義 pending、effective、接受、拒絕、人改 pending、review freshness | 由 LLM provider 或付費參照產品自動決定 |
| UI | 呈現目前可證明的 working／applied／saved／pending／effective／partial／failed／unknown 狀態，讓人處理衝突與審閱 | 把樂觀畫面當 durable fact；隱藏 markup 後宣稱變更已解決 |

Memory 提供相關理解、未知、更正及可回查的來源上下文，不新增「所有理解都先人工接受」的 gate。依[MEM-Q005](../2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)，同一 run 的理解與 JD 候選各通過自身驗證時，不因背景 Memory 技術性保存失敗一律阻擋 JD；最終全面盤點仍須滿足既有完整性條件。JD 文件、版本、候選變更與接受／拒絕由未來 editor／App 設計承接；本文不更改 production authority。Editor 候選不得迫使 Memory 重新設計，也不得讓 Memory 兼任文件 store。

## 7. 現有 JD 提案仍缺的決策與證據

1. **結果邊界**：happy path 仍容易把「tool 已完成」「editor 已套用」「已 durable save」「待審／已生效」寫成同一個成功。必須先選產品語意，再落契約。
2. **partial／unknown**：尚未明定何時可能部分套用、回應遺失時由哪個 authoritative fact 對帳，以及 UI 如何阻止盲目重試。
3. **版本前置條件**：尚未決定哪些操作要求精確基準，基準過期後是拒絕、協調或重新規劃；不能先假定 Google 式 reconciliation 存在。
4. **文件格式**：尚無固定免費 OSS 版本的 serialize → save → reopen 證據，因此不能定 editor JSON、suggestion metadata 或 DB 欄位。
5. **人工修改 pending**：A／B／C／D 尚未裁決；尤其 A 的 lineage、拒絕基準、交疊編輯與模型可見視圖未定。
6. **有效正文視圖**：AI 續談讀最新文件的效果已定，仍須驗證正確排除已刪正文；export 與一般閱讀如何選目前內容、已接受內容或顯示修訂，需與政策一起定義。
7. **免費能力界線**：Plate 免費 core 與 Plate Plus 展示不可混用；Tiptap／CKEditor 等付費能力只能作參照，不得進採用路徑。
8. **完整審閱能力**：目前 source 能證明部分 primitive，不能宣稱免費 OSS 已具有完整 suggestion persistence、lineage、review UI 與 recovery。

以上缺口都不是要求現在設計新 DB 或自建 engine。若 OSS 證據顯示缺口，先列能力缺口、可接受的產品政策選項與成本，交 owner 共同決定。

## 8. 後續研究依賴順序

以下是技術依賴，階段及唯一下一題統一依[執行計畫](../../plans/2026-09-09-jd-editor-research-discussion-design.md)與[App 能力對照 §5](../2026-09-09-jd-app-native-capability-crosswalk.md#5-下一個可決定的單位)。先在 S3 收斂必要政策並寫出有限驗證的正常／失敗流程；原保存重開、連續修改與組外修訂反例依新政策分層，未預定必採 pending。下面完整清單只在相關政策需要時適用，不要求一次全驗，也不由本證據稿另加安裝許可流程。

1. **固定免費 OSS 候選、版本與授權**：排除 Plus／cloud／commercial-only 能力，鎖定實際可採用 source。
2. **文件與審閱限界驗證**：不用 LLM，測 serialize/reopen、pending 人工插刪改、交疊變更、局部／整批 accept/reject、undo/redo、history 與作者 metadata。
3. **裁決人工／AI 審閱政策**：以驗證結果比較 A／B／C／D；若沒有候選完整支援，回報缺口與選項，不自造 engine。
4. **定義文件權威與讀取視圖**：決定 effective、pending、export、模型續談與歷史各讀哪個經驗證表示。
5. **定義結果與版本語意**：依 editor 真實 transaction／transform 能力，定義 apply、save、partial、unknown、stale target 與 reconciliation；此時才有足夠依據形成正式契約。
6. **推導 durable 保存與 DB 邊界**：從已選文件格式、版本與 review transaction 推導，不反向逼 editor 符合預設 schema；沿用主線既有 PostgreSQL／內容映射研究。
7. **設計 UI 與人機續編**：UI 只呈現可由前述事實支持的狀態；runtime 使用既有 Memory，讀選定的 JD view，不重開 Memory ownership。
8. **形成 ADR／contract gate**：將已選政策、OSS 證據、錯誤／版本語意與 remaining Unknown 寫回 current decision register，通過後才規劃施工。

## 9. 停止線

本輪證據足以開啟具體產品討論，但不足以：

- 宣稱某個免費 OSS 已滿足完整需求；
- 決定 JSON／API／DB schema；
- 把 Google Developer Preview 當正式成熟能力；
- 從 OpenAI／Anthropic 的工具成功推定 JD 已保存或已核准；
- 用付費產品的 UI 行為取代 Caliburn 的政策裁決；
- 因 editor 候選而重做既有 Memory／runtime；
- 未經產品裁決便選定人工續改的待審政策，或承諾自建 suggestion engine。
