# JD 文件內容模型：官方證據與適用邊界

支援 [JD-R002/C01 建議](2026-09-09-jd-document-relationships-working-research.md)、[C02 編輯／審核](2026-09-09-jd-editing-and-review-working-design.md)及[C03 整體 AI 編輯應用](2026-09-09-ai-document-app-composition-research.md)。研究／查閱基準日 2026-09-09；本表只保存會影響內容關係或後續框架判斷的直接來源，不重抄 [JD-R001 跨國內容研究](2026-09-09-job-analysis-international-evidence.md)。§1–§4保留C01依據，§5為C02，§6為C03新增直接查閱結果；不代表每輪重新核驗所有舊來源。

**Official fact** 是官方公開的能力；**Mapping** 是本產品建議；**Unknown** 是尚未驗證的接法。多家相近原則不等於逐項共同契約，也不能據此宣稱某方案全球最好。

## 1. 職務系統與文件產品

### E01 SAP Job Profile Builder：內容與模板不同

- 官方：[Managing Job Architecture with Job Profile Builder](https://learning.sap.com/courses/sap-successfactors-platform-advanced-and-talent-intelligence-hub-academy/managing-job-architecture-with-job-profile-builder-jpb_ba59a2d8-e04d-41d9-812e-eea5a8387995)。定位：Job Profile Content Types／Dependencies／Job Profile Template。
- **Fact：**責任、技能與條件等有不同內容類型及關聯；模板另管區段、順序、必需性與格式。
- **Mapping：**支持內容、關係及外觀分開考慮，知識技能不必逐任務複製。
- **限制：**Family／Role 是職務架構，不能直接當 Caliburn 的 Duty／Task。沒有因此選 SAP、導入跨 JD 共用、組織、職等或其審批流程。頁面為現行官方教材，未提供本文能核實的整頁修訂日期。

### E02 Notion：自由內容仍可有結構

- 官方：[Working with page content](https://developers.notion.com/guides/data-apis/working-with-page-content)。定位：Page content versus properties／Modeling content as blocks／Reading nested blocks。
- **Fact：**properties 適合日期、分類與關係；正文適合較自由內容。正文由有種類的 blocks 組成，部分可有子內容；完整讀取巢狀內容需沿 children 讀取。
- **Mapping：**書寫自由不等於只能存沒有結構的一大段文字；有閱讀階層也不等於所有語意都只能是父子關係。
- **限制：**Notion 是服務 API 參考，不是已選為本機編輯框架；不複製其全部 block 或會議功能。查閱為現行官方 API 文檔，不從搜尋摘要的抓取日期推定 API release。

### E03 Google Docs：結構與呈現可區分

- 官方：[Structure of a Google Docs document](https://developers.google.com/workspace/docs/api/concepts/structure)。定位：Structural element／Paragraph structure／Property inheritance。
- **Fact：**Body 由結構元素構成；段落內容與樣式有不同欄位。其繼承章節說明的是最終視覺外觀。
- **Mapping：**工作內容不能僅由 PDF 欄線或 HTML 畫面判定；上層格式繼承不是上層工作條件自動套用的證據。
- **限制：**沒有宣稱所有段落都有可跨保存的業務 ID，也沒有因此引入 Google Workspace。

### E04 ESCO：概念身分與稱呼不同

- 官方：[Use ESCO](https://esco.ec.europa.eu/en/use-esco)、[Uniform Resource Identifier](https://esco.ec.europa.eu/en/about-esco/escopedia/escopedia/uniform-resource-identifier-uri)。定位：data model／Unique concept identifiers／Backward compatibility。
- **Fact：**職業、知識技能等概念有範圍描述及唯一 URI；識別可長期一致並供其他資料連結。頁尾標示 ESCO v1.2.1，更新日 2025-12-10，不能將網站 release 號當 ESCO 內容版號。
- **Mapping：**名稱、畫面順序與被引用項目的身分應能區分。
- **限制：**這是概念分類庫，不是員工 JD 編輯器；不要求 Caliburn 使用 ESCO ID、匯入全庫或建立全球技能本體。

## 2. 編輯框架的具體能力與陷阱

### E05 文件 state 與序列化

- 官方：[Tiptap Concepts](https://tiptap.dev/docs/editor/core-concepts/introduction)、[Tiptap Persistence](https://tiptap.dev/docs/editor/core-concepts/persistence)、[Lexical Editor State](https://lexical.dev/docs/concepts/editor-state)。定位：Structure／State／Content；Persistence；Why is it necessary／Understanding／Updating state。
- **Fact：**Tiptap 基於 ProseMirror 的結構及 transaction，提供 JSON／HTML 保存介面；官方建議 JSON 便於解析及外部編輯。資料庫保存仍由應用接線。Lexical 以 editor state 而非 DOM 作編輯器真實狀態，可序列化 JSON。
- **重要差異：**Lexical 的 pending state 是畫面更新中的暫態，不是 AI 待員工批准；其單次 editor update 也不等於資料庫 transaction 或員工審核群組。
- **Mapping：**可優先使用框架的內容編輯機制，不自行從 DOM 字串重建所有內容；不因看見 JSON 就提前決定一張 JSONB 表。
- **取得限制：**Tiptap Persistence 直接開頁本輪兩次逾時，已從搜尋服務取得該官方頁的完整相關正文（HTML／JSON／backend API 段落）；不是據第三方文章補猜。Tiptap 頁面為 3.x 文檔，Lexical 為現行文檔，本題未鎖定套件 release。

### E06 schema 合法與資訊保留不是自動相等

- 官方：[Tiptap Schema](https://tiptap.dev/docs/editor/core-concepts/schema)、[Invalid schema handling](https://tiptap.dev/docs/guides/invalid-schema)。定位：content／Content checking；Introduction／Enabling content checking。
- **Fact：**schema 定義節點、屬性與可巢狀內容；不符結構的輸入可能被移除。官方提供初始內容的 `enableContentCheck`／`contentError` 接點；checking 預設未開啟，HTML 檢查不如 JSON 完整。
- **檢查時機：**此處引用直接支持初始化內容檢查；貼上、後續程式寫入及保存路徑須各查其契約，不能推定全面受同一接點保護。
- **Mapping：**日後必須核對必要內容的輸入與保存往返，不能說「框架有 schema 所以不會丟資料」。
- **限制：**此 schema 是編輯器結構，不是供應商的 strict tool schema，更不能驗證某工作或標準是否真實。本題不新增語意 verifier。

### E07 Tiptap UniqueID

- 官方：[UniqueID extension](https://tiptap.dev/docs/editor/extensions/functionality/uniqueid)。定位：介紹／types／generateID／Server-side generation。
- **Fact：**對所配置的節點加入唯一 ID，提供生成與更新選項；`types` 預設空陣列，不能說安裝後所有節點自動擁有 ID。官方另提供 server-side 生成工具。
- **Mapping：**持久項目定位可先評估此能力，不要求模型生成 UUID。
- **Unknown：**自訂 JD 節點的移動、複製、拆合與引用能否全部滿足產品語意，尚未實測；不能把官方「追蹤節點」概括成任意業務關係均已維護。

### E08 Lexical NodeKey

- 官方：[Key Management](https://lexical.dev/docs/concepts/key-management)。定位：Key Lifecycle。
- **Fact：**NodeKey 不序列化，反序列化會產生新 key，只在對應 EditorState 範圍內有意義。
- **Mapping：**不能直接當重開後仍有效的 JD 項目 ID；這個限制不代表 Lexical 無法保存應用層身分，另見 E09。

### E09 Lexical NodeState

- 官方：[NodeState](https://lexical.dev/docs/concepts/node-state)。定位：Use Case／Serialization／Capabilities。
- **Fact：**可將應用狀態加到節點或根節點，參與 history 及 JSON serialization；文件說明此 API 起於 v0.26.0，**不是說當前最新版就是 0.26.0**。
- **Mapping：**如選 Lexical，可先用官方 metadata 能力承接需要保存的資料，不先手寫所有序列化。
- **Unknown：**自動生成唯一業務身分、複製時換身分、引用更新並非單憑 NodeState 文件已證明；是否需要、如何配置留待選型。

## 3. 下一題已有可查的審核接點

### E10 Tiptap AI review：兩條路徑的保存性不同

- 官方：[AI Toolkit — Review changes](https://tiptap.dev/docs/ai/ai-toolkit/client/agents/review-changes)。定位：Two approaches／Use with Tracked Changes。
- **Fact：**與 Tracked Changes 整合時，變更可存為文件一部分；另一條 AI Toolkit suggestions 是暫時、僅目前使用者可見的 decoration。Tracked Changes 是獨立付費產品，與 AI Toolkit 分開販售。
- **Mapping：**後續審核可以先查現成接點，不直接自寫；但同樣叫 suggestions 不代表都能關閉後繼續審核。產品成熟度另見 E20，不因編輯器核心成熟而將付費擴充一概當成穩定版。
- **限制：**本輪沒有訂購、安裝或選定此產品；本機需求、資料流、價格／授權與服務依賴均須在選型時核查。

### E11 Tiptap Tracked Changes：個別與批次決策

- 官方：[Basic usage](https://tiptap.dev/docs/tracked-changes/usage/basic-usage)。定位：Accepting and rejecting suggestions／Batch operations。
- **Fact：**提供個別、全部、範圍或使用者層級的接受／拒絕操作，並涵蓋格式變更。
- **Mapping：**已有通用審閱機制可研究，不應先說接受／拒絕必須全部自行發明。
- **Unknown：**範圍批次操作不自動等價於「JD 跨位置拆分／移動及相依內容須一組審核」；修改待審文字、再次 AI 修改與持久恢復也須逐情境核對。本輪不以 API 名稱相似判定完整覆蓋。

## 4. 證據如何影響推薦，以及不做的推論

1. E01–E03、E05 提供不同生態中的結構／內容／呈現分工先例，因此推薦可辨識內容項目＋完整文字；**共同原則不是同一資料 schema**。
2. E04、E07–E09 顯示識別有成熟能力也有生命週期差異，應先讀框架契約，不能只看 ID／key 名稱。
3. E06、E10 說明功能名稱對了仍可能接錯：結構檢查不保證內容無損，暫時建議不等於可持久審核。
4. E11 支持下一題有現成審閱接點，不支持未研究就保留舊審核機制，或立即選定套件。

這些來源足以支持本題的概念選擇，不足以宣稱框架選型、資料庫及 AI 編輯全部設計完成。未引用已淘汰的 Tiptap AI Changes 路徑，也未以搜尋到的舊 ProseMirror 0.x API 作為新版契約。官方文檔沒有公布統一 JD 編輯模型；本產品的內容分組及最終取捨必須明標為 Mapping。

## 5. C02 編輯與審核接點複核

查閱日2026-09-09。已直接重新讀取E10、E11，原先的保存性／付費限制及個別、範圍、批次能力仍成立。以下頁面為查閱時現行文件；未取得精確發布版本／日期者不以網站抓取日冒充 release，也不據此鎖套件版本。

### E12 VS Code 現行文件不再可當逐項待核准的依據

- 官方：[Review and revert agent changes](https://code.visualstudio.com/docs/agents/run/review-code-edits)。原`/docs/copilot/chat/review-code-edits`於查閱時重新導向此頁。定位：Review agent changes／Edit requests and restore checkpoints。
- **Fact：**此頁明示 agent 在 session 資料夾或 worktree 直接套用並保存修改，沒有逐項 pending approval；可繼續提示或手動編輯，以 diff、版本控制、PR等流程審閱。恢復 checkpoint 可回退該點之後的修改。
- **Mapping：**可借鑑共同最新文件、直接續改及差異檢視；不能把其當成 Caliburn 明確接受／拒絕的同一契約，也不將整個 checkpoint 回退直接映射為拒絕一組 JD 修改。
- **限制：**本輪不從現行頁面反推所有舊版行為或變更發生日期；不因此推翻 Owner 的明確審核要求。

### E13 Word 的追蹤與審閱是兩個動作

- 官方：[Track changes in Word](https://support.microsoft.com/en-us/word/training/track-changes-in-word)、[Accept or reject tracked changes in Word](https://support.microsoft.com/en-us/word/accept-or-reject-tracked-changes-in-word)。定位：Turn Track Changes on and off／Accept or Reject tracked changes／Web。
- **Fact：**可在文件內逐項及整批接受／拒絕；關閉追蹤或隱藏標記，不會處理已存在的未決修訂。文件包含Web說明；不是拿行動版的操作當本產品版面。
- **Mapping：**支持編輯、顯示及明確審核不必是同一動作。未指定必須照Word畫面，也未證明Word自動辨識JD的完整決策範圍。

### E14 Tiptap 分組與跨作者編輯的實際限制

- 官方：[Advanced usage](https://tiptap.dev/docs/tracked-changes/usage/advanced-usage)。定位：Suggestion grouping／Mixed content handling／Nested and stacked suggestions／Block splits／Table support。
- **Fact：**相鄰、同作者、同類型的連續修改可合組；他人編輯既有待審文字會形成巢狀修訂。接受外層時內層仍可待審，拒絕外層會移除其內層。巢狀支援限定inline，不含跨整塊巢狀。表格刪欄等另有結構性分組。
- **Mapping：**字元／作者分組與JD決策分組不同；框架跨作者預設不能直接當「員工改組內一句，再一次接受整組最新版」。也不能因有block split就推定已有職務分析的Task拆分。
- **Unknown：**能否透過既有接點配置出所需完整體驗、哪些情境需擴充，尚未實測；不宣稱一定要自寫，亦未選付費套件。

### E15 Tiptap 一項替換可包含刪除與新增

- 官方：[Commands](https://tiptap.dev/docs/tracked-changes/api-reference/commands)。定位：acceptSuggestion／rejectSuggestion／addTrackedInsertion／addTrackedDeletion／addTrackedReplacement。
- **Fact：**接受替換保留新內容、移除舊內容；拒絕則相反。可程式建立新增、刪除及替換建議；替換內容支援文字／HTML／JSON內容，不需先將整份文件打開追蹤模式。
- **Mapping：**單項改寫有成熟審閱接點，不需先發明每種欄位專用diff；但單一位置範圍替換不直接證明非連續位置的移動／拆合及資料庫原子提交。不是已選AI wire格式，也不要求模型計算位置。

本輪足以提出C02產品選項，暫停更廣泛搜尋。後續若選型，須再核對保存、重開、同組再次編輯、跨位置決策、取消影響及授權／本機部署，不能把本表當套件已完整驗收。

## 6. C03 整體 AI 編輯應用接法

查閱日2026-09-09。先研究官方已公開的端到端範例，不安裝套件、不以品牌或名稱相同判定整體等價。以下為官方事實；C03 的分工建議另外明標 Mapping。

### E16 OpenAI 工具循環與減少模型負擔

- 官方：[Function calling](https://developers.openai.com/api/docs/guides/function-calling)。定位：The tool calling flow／Best practices for defining functions；透過 OpenAI Docs 讀取正文及指定章節。
- **Fact：**模型產生 function call，由應用執行，再將結果送回模型，模型可以回答或繼續使用工具。官方建議不要求模型填程式已知的參數、將總是連續執行的功能合併，並保持初始工具集合精簡；大量或少用工具可按需載入。
- **Mapping：**不必每個 JD 欄位一個 tool，也不應讓模型重填目前文件身分、核准狀態等程式已知資訊。這不是已選工具集合或 SDK。
- **限制：**工具呼叫／schema 合法不等於工作內容正確；SDK 不會憑空提供 JD 審核與資料保存。一次工具內多操作，也不自動是員工的一組決策或資料庫原子操作。

### E17 Anthropic 的 client tools 與 SDK runner

- 官方：[Tool use overview](https://platform.claude.com/docs/en/agents-and-tools/tool-use/overview)。定位：Client tools／How tools work／Tool Runner。
- **Fact：**自訂工具與 Memory、text editor 等 client tools 在應用端執行；模型提出 tool use，應用回傳 tool result。SDK Tool Runner 可承接執行函數並送回結果的循環；server tools 的執行位置不同。
- **Mapping：**Memory 管理與 JD 編輯可共用「模型判斷、工具操作應用資料、結果回到模型」的整合概念，不代表兩者用同一種資料、權限或審核生命週期。
- **限制：**runner 可省循環接線，但不替應用定義持久化／交易／審核，也不保證所有失敗都自動重試成功。

### E18 Tiptap Client Toolkit 已提供讀取及編輯整合

- 官方：[AI agent chatbot](https://tiptap.dev/docs/ai/ai-toolkit/client/agents/ai-agent-chatbot)、[Tool definitions](https://tiptap.dev/docs/ai/ai-toolkit/client/agents/tools)、[Non-TypeScript backends](https://tiptap.dev/docs/ai/ai-toolkit/client/advanced-guides/non-typescript-backends)。定位：API endpoint／Client-side setup／tiptapRead／tiptapEdit／Generate tool definitions。
- **Fact：**範例由 agent SDK 接收訊息與工具定義；模型選讀／改工具，前端 `executeTool` 操作 editor，再以 `addToolOutput` 送回結果。讀取可從位置開始，編輯接受 operations 並回傳成功或錯誤。官方提供多家 SDK 的工具定義；非 TypeScript 後端可用 CLI 匯出 JSON 契約。
- **Mapping：**可先評估框架原生的讀取／編輯介面，不必手造所有 JD 欄位專用工具；後端語言不同不代表一定要改語言。
- **限制：**Client Toolkit 為 Pro package；完整操作格式部分只提供給客戶。公開概覽未證明 Caliburn 所需的分組、持久化與全部錯誤情境；不得推測未公開契約。前端執行路徑須另核對斷線／關閉後的行為。

### E19 Tiptap Server Toolkit 的另一條資料流

- 官方：[AI agent chatbot — Server](https://tiptap.dev/docs/ai/ai-toolkit/agents/ai-agent-chatbot)。定位：Get tool definitions／Execute tool／Document state management／Alternative: provide the document directly。
- **Fact：**工具定義由 API 提供；範例的 agent 將工具交服務執行，結果或捕捉到的錯誤回傳模型。Cloud 模式可由服務讀存文件；inline 模式由應用每次載入文件，`docChanged` 時保存回傳文件，連 read 都可能改變文件準備資訊。
- **限制：**inline 不等於完全本機執行；仍呼叫 Toolkit 服務。官方另列 inline 的 comments、作者關聯與版本歷史整合限制。Cloud 範例的授權／協作不因此成為本產品需求；本機儲存與遠端服務邊界須分別確認。
- **Mapping：**這是另一條完整接法，不能將 Client 與 Server 範例的功能隨意拼接後宣稱框架自動完成全部保存／同步。

### E20 AI 改動與審核可以分工，但成熟度尚須核實

- 官方：[Use with Tracked Changes](https://tiptap.dev/docs/ai/ai-toolkit/client/agents/review-changes/tracked-changes)、[Tracked Changes overview](https://tiptap.dev/docs/tracked-changes/getting-started/overview)、[AI Toolkit overview](https://tiptap.dev/docs/ai/ai-toolkit/overview)。定位：Separate product／Experimental／Show tracked changes／Client-side setup。
- **Fact：**整合範例於工具執行時設定 `reviewOptions`，把 AI 編輯送進追蹤修訂；審核選項與 AI 作者資訊由應用配置，不必叫模型生成。Tracked Changes 為另售產品。
- **版本資訊不一致：**整合頁明標 extension Alpha；產品 overview 只標付費 add-on，沒有相同 Alpha 標示；AI Toolkit overview 則標 Beta。尚未核定 release／授權契約，不能自行判斷哪頁落後，也不能宣稱完整 AI＋審核組合為已證實穩定版。
- **Mapping／Unknown：**有「AI 編輯＋追蹤審閱」的實際整合先例，但 C02 所需的組內人改、跨位置拒絕及重開保存仍要核對。E14 的巢狀限制不因這份示例而消失。

**此階段停止點：**E16–E20 已回答是否必須自造重型 AI App。後續深入比較現已另存 [R01–R10：Agent／錯誤](2026-09-09-jd-ai-app-runtime-official-evidence.md)及[F01–F05：編輯框架](2026-09-09-jd-editor-framework-comparison.md)，結論見[可執行方案](2026-09-09-jd-ai-editing-executable-proposal.md)。仍未正式選定／實測套件；不用本段早期「尚未比較」重開已補的研究，也不反過來把建議當已施工。
