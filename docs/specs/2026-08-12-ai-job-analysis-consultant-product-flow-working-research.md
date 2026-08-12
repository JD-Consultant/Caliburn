# AI 專業職務分析顧問：產品流程工作研究稿

- 日期：2026-08-12
- 狀態：Working Research；隨 owner 討論持續修訂
- 決策狀態：只記錄已確認的產品方向與待討論問題；不是 ADR，不授權 production 實作
- 優先順序：本稿先定義「產品如何像專業顧問工作」；元件、Context Engine、RAG 技術與 framework 選型後置
- 外部資料查核：Context Engine 小節依截至 2026-08-12 可取得的官方／第一手資料整理；大廠做法是設計證據，不是免評測的產品決策
- 相關研究：[`階段式 AI 職務分析顧問 runtime/framework 研究`](2026-08-12-staged-ai-consultant-runtime-framework-research.md)只能在本產品流程核准後評估，不得反向用框架能力定義顧問流程

## 0. 這份工作稿怎麼使用

這份文件用來避免長期討論遺失已確認的大方向。每次只把已對齊的內容寫成明確規則；尚未討論或仍可能翻案的內容列在「待討論」，不假裝已定案。

目前先回答四個問題：

1. 這個 LLM 專業職務說明書顧問，從開始到匯出大致怎麼工作？
2. 員工如何知道 AI 現在為何發問、訪談進度到哪裡？
3. Task、Duty、OPKS 與 Reference 在流程中如何互相影響？
4. 長訪談中哪些內容必須完整保存、哪些每輪必帶、哪些應按需取用？

目前不回答：

- 要不要採 LangGraph、LangChain、PydanticAI 或其他框架；
- Context Engine、memory、RAG、tool、skill 的最終 schema；
- API、資料表、畫面與 migration；
- 模型、參數、價格與 provider 選型；
- 實作切片與工期。

## 1. 產品北極星

產品不是填表精靈，也不是自由聊天後一次生成 JD。它應是一位由 AI 主導訪談、持續整理全局、但沒有文件修改權的專業職務分析顧問。

白話原則：

> 先大致理解員工的真實工作，再選一個目前最值得釐清的焦點深入訪談；當下專注一件事，但不漏掉回答中出現的其他工作線索；隨著證據增加，持續修正 Task、Duty 與 OPKS，所有正式改動都交給員工決定。

固定的是分析責任與權威邊界，不是固定題目或只能往前的階段。

## 2. 已確認的大方向

### 2.1 一個主要顧問，按需組合分析 Skills

- 第一版以同一個主要 AI 顧問維持對話責任。
- 「盤點工作、深入故事、釐清 Task 邊界、整理 Duty、分析 O／P／K／S、Reference challenge、收尾檢查」是可按需載入的方法 Skills，不是八個人格化 Agent，也不是固定通關階段。
- 一輪可依焦點同時載入一個或數個相關 Skill；沒有必要的 Skill 不進當輪 prompt／context。
- 新證據可讓系統換用其他 Skill，也可重新開啟已暫時收束的 Task、Duty、O、P、K 或 S。
- 注意力模式只描述 AI 當下主要目標，不限制同一輪可進行哪些分析，也不控制資料必須依固定順序通關。
- Skill 的獨立是「方法與載入邊界」獨立，不代表分析結果彼此隔離；所有 Skill 仍需在同一份工作假說、來源與權威模型中互相校正。

### 2.2 前景專注、背景全域吸收

- 每次訪談有一個主要焦點，避免自由聊天與一次追問多個欄位。
- AI 必須閱讀員工完整回答，不得只擷取與上一題直接相關的句子。
- 回答中出現的新工作、他人工作、更正、矛盾、工具、產出、標準或 OPKS 線索都要保存並分類。
- 一般旁支線索先保留，避免打斷當下訪談；若它會改變本人責任、Task 邊界或重大文件內容，可以優先澄清。

### 2.3 AI 預設帶路，員工可隨時改道

- 一個焦點收束後，由 AI 選擇下一個最高價值焦點並說明原因。
- 不要求員工每輪理解系統階段或自行規劃下一題。
- 員工可以跳過、切換工作、暫停、補充新故事或返回先前內容。
- AI 不因員工改道而遺失尚未處理的焦點與線索。

### 2.4 AI 只提出變更，員工決定正式內容

- Work Model 是可變動的分析假說層，不是 Current JD。
- AI 可以提出新增、改名、修改、重新歸類、排序、合併、拆分或撤回候選。
- AI 不得直接修改 Current JD，也不得把員工沒有說過的內容自動補入。
- 員工可以接受、修改後接受、拒絕、暫不處理或直接編輯自己的 JD。
- 先前接受的內容仍可被新證據重新挑戰，但修改仍需員工決定。

### 2.5 Task 與 Duty 都會隨訪談演化

- 分析初期允許 Task 尚未歸入 Duty。
- 初期可有暫定責任區域協助 coverage 導航，但不得把它當成固定 Duty 盒子。
- 隨 Task 增加、合併、拆分或改變邊界，Duty 可以改名、重新分組、合併或拆分。
- 不要求先完成 Duty 才能理解 Task，也不要求 Task 一被員工接受後就永久固定。

### 2.6 單一匯出，但缺口必須可見

- 產品只有一個匯出概念，不額外建立草稿／正式兩套資料或文件生命週期。
- 匯出前列出尚未分析、待補訪、待員工決定、結構問題與已保留未知。
- 員工可以在看過缺口後強制匯出。
- 強制匯出不會自動接受 Proposal、補造 OPKS、隱藏孤立 Task 或改變 Current JD。

### 2.7 員工回答先成為 durable source，AI 失敗不應讓原話消失

- 員工送出的回答先以穩定 input event／turn identity 保存為來源記憶，再交給 AI 分析；它不是等模型成功後才附帶寫入的欄位。
- provider timeout、拒答、parse、schema 或 verifier 失敗時，該回答仍保留並標示尚未成功分析；員工不必重新輸入。
- 重試必須沿用同一個 input event，不重複建立來源；每次實際 provider 嘗試另有 attempt identity。失敗期間 Work Model、Proposal 與 Current JD 都不得改變，但已完成的 model／tool result、verification report 與成本等**執行證據**可以先成為可恢復 artifact，避免 crash 後盲目重打 provider。
- 這項產品裁決取代 2026-07-30 最小完整迴圈中「模型失敗時 Journal 完全不變、只由 Web 保留草稿」的舊假設；實作前仍須以 ADR／plan 補齊交易、idempotency 與 migration 邊界。

### 2.8 一個員工回合可包含受限的內部工作，但仍由同一位顧問負責

- 一次員工送出與一次模型 inference 不是同一個概念；產品以一個可保存、可重試的 application run 承接一個員工回合。
- 預設先走一次主要顧問 inference 的快速路徑；資訊足夠時直接結束，不為了「可能更好」固定增加 planner、critic、extractor 或 OPKS 呼叫。
- 只有缺少本輪必要 context、需要唯讀工具結果，或有邊界明確且確實不同的專業判斷時，才在同一個 run 內增加受限步驟。
- 載入 Skill 不等於另開人格化 Agent，也不必然增加一次模型呼叫；同一位主要顧問仍擁有最後語意整合與員工回覆。
- application 決定 scope、工具權限、最大步數、token／時間／成本與停止規則；不得讓模型自由無限循環。
- 員工只看到一個連貫結果、必要 Proposal 與一個主要問題；內部 Manifest 可供重播與除錯，但不把 chain-of-thought 當成產品輸出。

### 2.9 Reference challenge 要記得員工裁決，但不永久化所有檢索命中

- 第一版 Reference 內容只使用 repo 已有的 iCAP 資產；不納入 O*NET、一般網路搜尋、公司文件、表單或既有 JD，也不把這些列為本輪延後需求。
- 一般檢索命中只是技術候選；只有真正被拿來詢問員工、影響訪談焦點／Proposal，或形成 coverage 判斷的內容，才成為持久的 Reference challenge。
- challenge 要保留被挑戰的工作範圍、提出原因、來源／版本／引用、員工回答連結、match／partial／no-match／conflict／unknown／deferred 裁決，以及後續是否仍有效。
- 同一個語意主張即使出現在多個 iCAP 片段，也只問一次；支持片段可以增加，但不得把同義公版內容包裝成新的問題反覆詢問。
- `no-match`、拒絕與其他已裁決結果必須被記住；沒有新員工 evidence、實質來源變更或工作邊界改變時，不得只因重跑檢索、更換模型／embedding 或分數變動而重開。
- Reference challenge 的裁決仍不是 Current JD；只有員工來源能改變 Work Model，只有 authority seam 能改變正式內容。

### 2.10 職務資料可送外部模型，但產品權威留在本地

- Owner 於 2026-08-13 確認：員工訪談、JD、Task／Duty、OPKS、Reference 與其他職務分析內容都可送給外部 LLM；第一版不做欄位遮罩、敏感資料分類、本機模型模式或逐回合同意。
- 產品只需在設定／開始使用時清楚告知內容會送往外部 AI 服務，不以每輪彈窗打斷訪談。
- 「可以送」不等於每輪傳入全部內容；Context Engine 仍依焦點與資訊價值選擇最小充分 context，避免成本、延遲與無關資訊干擾。
- Source、Work Model、Proposal、Current JD、進度與恢復依據仍由 Caliburn 保存；provider／gateway 的 conversation state、logging 或 cache 不得成為唯一權威。
- 第一版不要求 ZDR，但不主動加入模型訓練、資料折扣 logging 或完整遠端 prompt／response logging；模型與 provider 路由必須明確，不能以不透明 fallback 偷換模型。

### 2.11 框架承接工程機制，Caliburn 保留產品語意（2026-08-13 已確認）

Owner 已確認：保留 Source、Work Model、Proposal、Current JD、Task／Duty／OPKS 方法、deterministic verifier 與員工 authority，不代表這些責任的所有底層程式都必須自行維護。判斷原則改為：

- 框架可以取代或包裝通用的 model／tool interface、structured output、checkpoint／resume、Skills progressive disclosure、context lifecycle、token／usage、tracing、欄位與模型形狀驗證；
- 成熟標準可以改善現有 domain 元件的資料形狀，例如 quote anchor 可借用 W3C Web Annotation 的文字引用與位置選取模型，lineage 可借用 W3C PROV 語彙；
- 現有 Pydantic、SQLAlchemy 與 PostgreSQL 本身就是框架／平台，應先評估是否能以 validator、constraint、transaction、versioning 與 ORM 能力減少自寫 plumbing，再決定是否增加新套件；
- memory／agent／workflow 框架可以產生候選、保存執行 checkpoint 或組裝 context，但不得成為 Source、Work Model、Proposal 或 Current JD 的第二份權威；
- framework HITL 可以承接通用 pause／resume 與互動傳輸，但 Proposal 是 durable domain object，員工決策是獨立 domain command，最後仍須通過 Caliburn authority commit seam；
- 採用標準是語意覆蓋、可靠度、維護成熟度、遷移成本、可替換性與是否減少總維護面，不是套件功能數或刪除行數；
- 目前推薦分層組合主流框架，而不是要求一套框架全包，也不以 big-bang event-sourcing／agent-platform 重寫作為預設路徑。

因此產品流程仍是本文定義的顧問流程；framework 只能忠實承接它，不能因框架已有 `memory`、`state`、`approval` 或 `agent` 類別，就重新定義員工回合、資料權威、進度或正式修改權。

### 2.12 一個員工回合採三層持久化，不把 network call 偽裝成資料庫交易（2026-08-13 審核後確認）

本節把「員工原話先保存、衍生結果整包提交」說得更精確。它不是只有兩個模糊的 save，也不是把 provider call 包在長時間 PostgreSQL transaction 裡：

1. **Source acceptance transaction**：先以 client／application 提供的穩定 `input_event_id` 保存員工原話、speaker、document scope、canonical payload hash 與 processing status，再回報「回答已保存」。相同 ID＋相同 hash 回既有結果；相同 ID＋不同 hash 是 idempotency conflict。
2. **Execution durability**：transaction 外執行 Context、Skill、tool 與 model；每個不可免費重做的重要結果以 run／attempt checkpoint 或 immutable artifact 保存，例如 resolved model profile、ContextManifest、tool result、provider result、usage、parse／verification report。這些是恢復與診斷依據，不是 Work Model、Proposal 或 Current JD。
3. **Semantic commit transaction**：deterministic application layer 把通過檢查的候選編成一份 `VerifiedCommitPlan`；再於單一 PostgreSQL transaction 中重讀 document、驗 generation／read-set，並一起寫入 Work Model delta、agenda／progress、durable Proposal、可見 consultant turn 與 idempotent result receipt。這批業務變更要嘛全部可見，要嘛全部 rollback；Current JD 仍完全不動。
4. **Independent employee decision command**：員工日後接受、修改、退回、拒絕或延後 Proposal，是另一個有自己 idempotency／stale check 的 command；只有它能經 authority seam 改變 Current JD。正常 Proposal review 不依賴 consultant graph checkpoint 存活。

因此「原子」描述的是**已驗證業務 CommitPlan 的資料庫可見性**，不是要求整個 LLM run 只有一次 commit。provider 已成功但 process 在 semantic commit 前崩潰時，恢復流程應讀取已保存的 provider／verification artifact；若 authority snapshot 仍相符，可以繼續 verify／commit，不應自動再付一次模型費。若 snapshot 已 stale，舊結果可保留作執行證據，但不得硬套到新 state，必須依 operation policy 重新組裝或重跑。

模型輸出的逐項驗證與資料庫原子性也不是同一題。建議 verifier 產生 granular verdict 與 dependency：

- envelope、document／speaker／source identity、authority boundary、read-set、跨項不變量、next question／visible response 所依賴的 finding 發生錯誤時，視為 fatal，整份 semantic commit 不成立；
- 只有不被其他結果引用、也不影響員工可見回覆的附帶候選，才可被明確 drop／quarantine 並留下 reason code，其餘有效項目再組成 CommitPlan；
- 第一版若尚未有穩定 dependency contract，寧可沿用整輪 fail-closed，不以猜測判斷「這個錯誤大概不重要」。先保存 granular report，之後有真實 failure evidence 再放寬，不必改寫權威模型。

UI 只可在 semantic commit 成功後把 consultant turn 當正式本輪回覆；commit 前可以顯示「已保存／分析中／驗證中」等 processing status，但不可先把尚未驗證的串流文字當成已成立的分析。失敗時顯示「原話已保存、分析尚未完成」與可重試狀態，而不是要求員工重新輸入。

這項分層符合多個官方來源的共同模式，但外部來源不替 Caliburn 決定 domain 語意：PostgreSQL 將 transaction 定義為多步驟 all-or-nothing；AWS 的 idempotent API 指引要求 caller-provided request ID，並指出去重紀錄、mutation 與結果應在同一 ACID operation 中一致提交；LangGraph 建議把 API call 放進可 checkpoint、可重播且 idempotent 的 task，保存已完成 task result 以免 resume 時重算；OpenAI Agents SDK 的 output guardrail 也明確區分「已完成的 tool result 可持久化」與「被拒絕的 final output 不進 session」；DBOS datasource 則證明 workflow checkpoint 與 application transaction 可以在同一資料庫交易中原子記錄，但它是替代 runtime 候選，不代表應與 LangGraph 疊兩套 durable engine。[PostgreSQL — Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)、[AWS Builders' Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)、[LangGraph — Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)、[OpenAI Agents SDK — Guardrails](https://openai.github.io/openai-agents-python/guardrails/)、[DBOS — Transactions and Datasources](https://docs.dbos.dev/python/tutorials/transaction-tutorial)

## 3. 白話產品流程 v0.1

### 3.1 開始或恢復

新文件先簡單理解：

- 這個職位為什麼存在；
- 主要服務誰、產生什麼結果；
- 員工目前大致負責什麼；
- 是否有兼任、支援、已不再做或尚未正式接手的工作。

恢復舊文件時，AI 先說明：

- 上次談到哪裡；
- 目前已理解什麼；
- 尚待決定或補訪什麼；
- 建議從哪個焦點繼續。

角色定位只提供方向，不根據職稱套用公版 JD。

### 3.2 廣度盤點：建立「目前已知的工作地圖」

AI 從不同角度協助員工回想工作：

1. 每日、每週的例行工作；
2. 每月、每季、每年的週期工作；
3. 低頻但出錯影響大的正式責任；
4. 監控、檢查、維護與預防；
5. 對外、跨部門與上下游交接；
6. 需要判斷、協調、核准或承擔風險的工作；
7. 緊急、例外與問題處理；
8. 最近新增、已停止、只支援他人或未來構想的內容。

這一步產生的是工作線索、故事、工作邊界假說、Task 候選與暫定責任區域，不要求全部立刻成為正式 Duty／Task。

廣度盤點與深入訪談不是先後通關。當某項工作已值得深入，就可以進入焦點訪談；深入時若發現新範圍，也可以回到盤點。

### 3.3 選擇本輪焦點

AI 根據最新狀態選一個最值得處理的問題。優先考量：

1. 更正、矛盾、本人／他人責任；
2. 會改變 Task merge／split／邊界的未知；
3. 高影響、低頻但重要或高風險工作；
4. 缺主要 outcome、責任或完成標準的 Task；
5. 影響 Duty 分組的缺口；
6. 有必要補證據的 OPKS gap；
7. 其他 coverage 與低風險細節。

AI 應告訴員工：現在談什麼、為什麼現在談、要釐清到什麼程度。

焦點採分級切換，不採「一定問完才換題」，也不追著每個新線索跳轉：

- 與目前工作相關的新資訊，直接吸收到當前分析；
- 不影響當前判斷的新 Task、Duty 或 OPKS 線索，保存到待處理清單；
- 若新資訊會推翻目前 Task 邊界、改變本人責任、揭露重大矛盾或高風險遺漏，AI 應說明原因後暫停並切換；
- 員工明確要求換題時立即尊重，但保留尚未處理的焦點；
- 每次中斷都要保存返回點，之後能說明原焦點談到哪裡、為何中斷、還差什麼。

當目前證據已足以形成 Proposal、確認 `no-op`、留下具體 gap，或以有理由的 unknown／not applicable 暫時停止時，焦點才算暫時收束。這不是永久完成；後續證據仍可重新開啟。

### 3.4 深入一件具體工作

抽象描述優先回到最近一次或代表性的具體事件。訪談可涵蓋：

- 什麼情況觸發；
- 收到什麼輸入；
- 員工本人做了哪些關鍵行動與判斷；
- 哪些由他人、共同或上級處理；
- 產生什麼結果、交給誰；
- 如何知道可以完成、交付或結案；
- 例外、失敗、重工與風險如何處理；
- 這是例行、週期、正式低頻、一次性、過去工作或未來構想。

5W1H 是問題工具，不是必須逐欄問完的表格。問題由當前缺口決定，一次只問一個主要 answer target。

### 3.5 背景保存其他線索

即使正在深入 A Task，AI 仍要辨識：

- A Task 的新證據或更正；
- 可能屬於 A 的步驟、工具、方法或 OPKS；
- 可能屬於既有 B Task 的資訊；
- 可能形成新 Task／Duty 的線索；
- 暫時無法安全分類的內容。

一般情況先保存，不立刻換題；下一個焦點選擇時重新評估。

### 3.6 每輪訪談的核心循環

每輪不是先判斷 Task、再依序跑 Duty 與 OPKS，而是先理解員工的完整回答，再依當輪需要組合方法：

1. 接收完整回答，不限制員工只能回答上一題；
2. 做全域理解，保存來源事實、更正、新線索、矛盾與尚無法分類的訊號；
3. 維持一個前景焦點與共同 work hypothesis／focus anchor；
4. 根據回答內容、當前焦點與仍存在的 gap，按需載入零個、一個或多個分析 Skill；
5. 各 Skill 使用同一批證據形成 typed findings、候選、gap 或重新開啟既有結論的理由，不直接修改 Current JD；
6. 對 Task、Duty、O、P、K、S 的分析結果做共同對帳，處理拆分、合併、重新分組與 linkage 變化；
7. 決定本輪的單一清楚下一步：繼續同一焦點、整理或提出變更、保存旁支線索、切換焦點，或提示已接近可停止狀態；
8. 對員工呈現目前焦點、必要摘要、Proposal 與一個主要問題，不暴露內部 Skill 編排為使用者必須理解的流程。

例如，員工描述某項工作時同時說出主要成果與驗收方式，當輪可一起使用 `task-boundary`、`output` 與 `performance-indicator`；若沒有能力需求的證據，就不載入 `knowledge`／`skill`。若 Indicator 顯示原 Task 包含兩種不同成果，也能回頭提出 Task 拆分。

這是產品的語意循環。2026-08-13 已確認其高階執行形狀為「預設單次 inference 快速路徑＋必要時受限補查／再判斷」：不固定每輪多呼叫，也不允許自由 Agent loop。至於同一 run 內的 tool loop、少數 specialist、final submit contract 與框架映射仍是實作選擇；不得反過來因框架或呼叫形式改變上述顧問責任。

### 3.7 小段落收束、重整與提案

完成一小段有意義的訪談後，AI 可以整理：

- 現在對工作故事的理解；
- Task 是新增、補充、重疊、需 merge／split，或只是工具／步驟；
- Duty 是否需要建立、改名或重新分組；
- 哪些 OPKS 已有依據、哪些仍有 gap；
- 哪些變更值得提出 Proposal；
- 哪些線索先保留到後面。

不要求每回合都產生 Proposal；`no-op`、繼續追問或只保存線索都是正常結果。

Proposal 採「有意義檢查點」節奏，不採每句回答都要求核准，也不等到整份訪談結束才一次處理：

- 一般補充先更新 Work Model，必要時以白話摘要確認，不立刻跳出正式核准；
- 理解仍不確定時繼續追問，不把猜測過早包裝成正式變更；
- 當證據已足以新增或修改 Task、Duty、O、P、K、S，才形成 Proposal；
- 若結構變更會影響後續訪談方向，例如 Task 拆分、Duty 重組或責任歸屬改變，應優先交員工決定，避免在錯誤假說上繼續深入；
- 員工明確要求修改正式內容時，可以立即形成 Proposal；
- 同一批證據造成多個關聯變更時，應以共同理由整理為同一個審核脈絡，不讓各 Skill 分別跳出互不相干的卡片。

關聯變更採「共同脈絡、依相依性分組」：

- 員工先看到這組建議的共同理由、來源證據與整體影響；
- 可以獨立成立的文字、名稱或 OPKS 候選，允許逐項接受、修改或拒絕；
- 只有必須一起成立才不會破壞結構的操作，才組成不可拆的子決策，例如建立 Duty 並完成必要的 Task reassignment；
- 員工修改任一項後，系統重新檢查剩餘變更是否仍成立，不提交失去前提或留下無效 linkage 的內容；
- 分組依據是 domain dependency，不是由哪一個 Skill 產生，也不把整批不相關的變更綁成全收全退。

#### 3.7.1 Proposal 依「是否改變後續分析前提」分級阻擋（已確認）

不是所有 Proposal 都中斷訪談。阻擋判斷依它是否為目前或後續焦點的語意前提，不只看 action 名稱：

- Task merge／split、Duty 建立或重組、Task reassignment、本人／他人責任與其他會改變分析邊界的結構性 Proposal，若後續問題、OPKS linkage 或 Duty grouping 依賴該結果，先暫停受影響的分析，請員工接受、修改、拒絕或改道；
- 改名、文字潤飾、排序與不改變分析前提的一般 OPKS 補充，可以維持 pending，訪談繼續；
- 「阻擋」只作用於依賴該未決前提的 focus／agenda branch，不封鎖整份文件、其他不相關工作、直接編輯、Proposal review 或匯出決策；
- 員工暫不處理結構性 Proposal 時，AI 保存返回點與 blocked reason，改選不依賴它的焦點；若沒有可安全前進的焦點，才明確提示需要先決定；
- Proposal 解決後，系統重新檢查其下游候選、gap、linkage 與 agenda；不得把 proposal 前的推論直接當成仍然有效，也不得因拒絕而偷偷採用同一假設繼續分析。

UI 與進度投影應說明「哪個分析目前被什麼未決前提擋住」，而不是只顯示一個無法理解的全域 blocked 狀態。

#### 3.7.2 Work Model 採觸發式理解校準，不把每次假說更新變成核准（已確認）

Work Model 是 AI 隨證據持續修正的分析層；員工不需要逐筆審核每一個內部假說變化。但若 AI 長時間在錯誤理解上繼續追問，後面的焦點、Duty grouping、OPKS 與 Proposal 都可能一起偏掉。因此產品需要「理解校準」，但它和正式 Proposal 是兩種不同的互動。

平常的低影響 Work Model 更新可以在背景累積，並在畫面上隨時可查看；只有下列有意義時機才由 AI 主動顯示校準卡：

- 準備收束或切換目前焦點；
- 即將提出結構性 Proposal，或後續問題將依賴某個尚未校準的工作假說；
- 新回答與既有理解矛盾，或涉及本人／他人責任、決策權、低頻高影響工作等高風險邊界；
- 暫停較久後恢復，或 Work Model 自上次向員工顯示後已有重大修訂；
- 員工主動要求查看或修正 AI 的目前理解。

校準卡應以員工看得懂的白話呈現，而不是暴露內部 schema：

- 現在談的是什麼、AI 為何這樣理解；
- 一段簡短的目前理解，必要時列出 Task／Duty／OPKS 關係；
- 可展開的員工原話與 Reference 來源，並清楚區分兩者；
- 仍不確定、互相衝突或尚未訪談的部分；
- AI 建議的下一步，以及這張卡所依據的 Work Model revision。

員工至少可以選擇「正確，繼續」、「直接修正」與「目前不確定／稍後再談」。其語意必須固定：

- 「正確」形成員工確認的來源事件，可提高或補強 Work Model，但**不等於接受正式 JD 變更**；
- 「直接修正」保存新的 durable employee source，由 reducer 修正、反駁或取代相關假說；若因此需要改 Current JD，另行形成 Proposal；
- 「目前不確定」保留明確 gap 或返回點，不得被解讀為肯定或否定；
- 提交時若 Work Model revision 已過期，應重新組裝校準內容，不把對舊理解的回覆套到新狀態。

因此產品不設「核准整份 Work Model」，也不每回合跳 modal。理解校準是防止 AI 假說漂移的可見修正點；Proposal 才是改變 Current JD 的 authority gate。

#### 3.7.3 「目前理解」採常駐投影＋情境式校準卡（已確認）

員工不應只能從長對話猜 AI 目前怎麼理解，也不應被迫在每一輪停下來審核。第一版採兩層互動：

1. **常駐但不打斷的「AI 目前理解」側欄**：跟著目前焦點更新，可收合；窄畫面改成可隨時叫出的 drawer。它是 Work Model 的可讀投影，不是第二份資料、不是核准清單，也不等於 Current JD。
2. **只在 §3.7.2 trigger 發生時出現的校準卡**：預設放在對話流內，不用 modal；只有受未決前提影響的分析 branch 需要阻擋時，才要求先處理。

側欄預設只顯示與員工當前任務有關的高訊號內容：

- 目前焦點、為何現在談這件事，以及「探索中／需要釐清／足以形成提案／受未決前提阻擋」等可行動狀態；
- 2–4 點白話的目前理解，必要時顯示 Task／Duty／OPKS 關係；
- 最重要的未確定、矛盾與尚未訪談項目，超過上限只顯示數量並可展開；
- 本輪先保存、稍後再談的新線索或其他 Task；
- 可展開的來源與最後更新時間，員工原話和 Reference 必須分開；
- 一個隨時可用的「修正目前理解」入口。

不要顯示沒有經過產品驗證的 LLM 數字信心或假精確的完成百分比。改用有明確資料語意的標籤，例如「員工已確認」、「依員工說法暫定理解」、「只有 Reference、尚未向員工確認」、「來源矛盾」與「尚未訪談」。最後更新也不得偽裝成最後確認。

校準卡預設只顯示**自上次校準後有意義的變化**及其影響，不重複整份 Work Model。它至少要說明：

- AI 新增、修正或不再採用哪一項理解；
- 依據哪些員工原話或 Reference，以及為何現在需要確認；
- 若不處理，哪個下一步、Duty grouping、OPKS 或 Proposal 會依賴它；
- 「正確，繼續」、「直接修正」、「目前不確定／稍後再談」三種固定動作。

一般焦點切換、久後恢復或大幅修訂屬 soft checkpoint：員工可略過、稍後處理，AI 保存未校準狀態與返回點。矛盾、高風險責任邊界或結構性 Proposal 的必要前提屬 branch-blocking checkpoint：只暫停依賴它的分析，不封鎖整份文件。相同內容未變時不得重複跳卡；相關變更應合併呈現，員工主動要求則不受節流限制。

員工修正後，介面要立即回報「已更新什麼、哪些後續分析會重算、Current JD 是否仍未改變」，並同步刷新側欄。這是對修正效果的可見回饋，不是揭露模型 chain-of-thought；解釋只提供來源、重要推論與影響。所有 action payload 都視為不可信輸入，由 server 依 document、revision、generation／read-set 與 domain invariant 驗證。

### 3.8 O／P／K／S 按需漸進分析

不需要等 Task 已穩定、已被員工接受或已進入 Current JD，才開始看 O／P／K／S。只要目前的工作故事、Work Unit 或 Task hypothesis 已出現足以分析某一軸的證據，顧問就能按需載入該 Skill；沒有需要時不載入，也不是每回合都分析 OPKS。

方法可拆成：

1. `task-boundary` Skill：判斷這是 Task、步驟、工具、他人工作、既有 Task 的補充，或仍需追問；
2. `duty-grouping` Skill：從目前 Tasks／工作假說找共同目的、責任與分組，也能建議改名或重組；
3. `output` Skill：辨識實體交付、服務結果、決策或狀態改變；
4. `performance-indicator` Skill：辨識可觀察的行為、結果、條件與標準；
5. `knowledge` Skill：由實際工作、判斷、規則與概念需求形成 K 候選；
6. `skill` Skill：由實際操作、分析、協調、溝通、判斷與解題行為形成 S 候選。

這些 Skill 可獨立載入，也可在同一輪組合。例如一段具體故事可能同時需要 `task-boundary`、`output` 與 `performance-indicator`；若員工談到關鍵判斷依據，才再載入 `knowledge`。Skill 組合是 context／prompt 最佳化，不是把一個完整工作拆成互不相干的答案。

各分析方向必須雙向校正：

- O 顯示兩個不同主要結果時，Task 可能需要拆分；
- P 無法共同描述時，Task 邊界可能太粗；
- K／S 只支持工作的一部分時，可能揭露不同責任；
- Duty 分組無法解釋共同目的時，可能需要重組；
- Task／Duty 改變後，既有 O／P／K／S linkage 需要重新檢查。

因此需要的是一個共同的 evolving work hypothesis／focus anchor，不是「先完成 Task 再跑 OPKS」的階段門。證據不足時，對應 Skill 產生具體 gap，加入後續訪談議程；有足夠證據時才形成候選。

不得直接問「你需要什麼能力」後照單生成 K/S；應優先問員工實際怎麼做、判斷什麼、出錯會怎樣，再形成候選讓員工否決、修改或接受。

不是每個欄位都必須有內容。操作型 Task 可沒有獨立有形 Output；員工不知道、不適用或已有理由無法取得的內容要誠實保留，不為完整表格而補造。

### 3.9 Reference coverage challenge

在已經有員工工作模型後，AI 才以少量、按需的既有 iCAP 內容做 coverage challenge：

- 是否漏掉常見但員工尚未談到的責任；
- 是否有可以追問的 Output、Indicator、K/S 方向；
- 員工工作與參考職業內容是 match、partial、no-match 或 conflict；
- 是否需要中立追問，而不是直接採用公版答案。

公版內容只產生參考候選、問題或差異，不自動成為員工的工作事實。

這不是員工要操作的搜尋頁，也不是固定的 Reference 階段。主要顧問在盤點、Task／Duty 或 OPKS 訪談中判斷當下確實有補漏價值時，才按需查詢 iCAP，將命中內容改寫成一個中立問題；沒有明確價值就不查。員工可以回答、略過或稍後處理，但不需要自行挑選 iCAP 項目。

產品不保存每個 RAG 命中作為正式分析狀態。只有當候選真的被呈現給員工、改變當前／後續焦點、影響 Proposal 或形成 coverage 結論時，才保存一筆可追溯的 challenge receipt。receipt 記住「問過什麼、為何問、依據哪個版本的來源、員工如何裁決」，並連回原始員工回答，不複製或改寫員工來源。

同一 challenge 以「被挑戰的語意主張＋工作範圍」去重，不以 chunk id 去重。多個 iCAP 片段可共同支持一次中立詢問；相關度、rerank 分數與片段數量都不會提高為員工事實。

已裁決 challenge 原則上不重問。只有以下情況可重新開啟：

- 新的員工 evidence 會實質改變先前裁決；
- Task／Duty／OPKS 邊界、歸屬或責任範圍改變；
- 員工主動要求重查；
- 原本是 unknown／deferred，且現在進入適合確認的焦點；
- 來源內容或版本真的改變了被挑戰的主張。

單純更換模型、embedding、reranker、索引，或檢索排名改變，不構成重開理由。來源版本更新只先形成「可能過期」狀態；確認相關主張有實質差異後才重問，不能每次資料更新都打擾員工。

### 3.10 收尾與匯出

當主要範圍大致收束，AI 做最後反方檢查：

- 是否被少數精彩事件主導而漏掉例行工作；
- 是否漏掉低頻高影響責任；
- 是否誤收過去、他人或一次性工作；
- Task 是否過度拆分、合併或重複；
- Duty 分組是否仍可合理解釋；
- OPKS 是否有工作行為支持；
- 是否因公版而加入員工沒做的內容；
- 是否仍有會顯著改變 JD 的矛盾或未知。

系統可以建議「本輪可結束」或「目前已足夠進入最後檢查」，但員工決定何時停止與匯出。

### 3.11 員工視角端到端驗收情境

以下情境不是固定腳本，而是用來驗收產品體驗。假設員工是製造業採購專員；員工不會看到內部 Skill 名稱與編排。

1. **先建立工作地圖。** AI 請員工用自己的話說明一個月內主要工作，不要求 JD 用語。員工提到請購下單、供應商交期、缺料協調與偶爾整理庫存報表後，AI 顯示「目前已知四個工作範圍」，並說明先深入請購到下單的原因。
2. **專注但不漏線索。** 員工在下單故事中順帶提到新供應商評估與替代料；AI 把兩者顯示為稍後處理線索，仍用一個主要問題釐清下單責任，不立即換題。
3. **先理解，後提案。** AI 經數輪釐清主管核准邊界、採購單內容與供應商回覆，準備切換焦點前先用校準卡說明目前理解；員工可直接修正「交期只是追蹤，不是我決定」。修正先更新來源與 Work Model，證據足夠後才提出 Task、Output 與 Indicator 候選；第一句補充不會立即跳正式核准卡。
4. **員工保留 authority。** 員工指出「不是每次都要比價」，AI 修正 Task 後再讓員工接受。若目前只有一個 Task，可以先不建立 Duty。
5. **重大責任先澄清。** 訪談缺料處理時，員工說「決定哪些工單先拿到料」。因這可能改變正式權責，AI 暫停原焦點，確認員工只是提出建議、最後由生產主管決定，再回到原返回點。
6. **結構隨證據演化。** 當已有下單、缺料協調、供應商績效三項 Task，AI 可提出兩個 Duty 與 Task reassignment 的結構變更組；員工能修改 Duty 名稱。可獨立成立的 K／S 候選仍可逐項決定，不因接受 Duty 就被迫全收。
7. **Reference 只做補漏。** AI 在已有員工工作模型後，以公版資料詢問「供應商稽核是否為正式責任」。員工回答由品保負責後，系統記錄 no-match，不建立假的 Task。
8. **進度可解釋。** 畫面顯示目前焦點、為何現在處理、已足夠／訪談中／尚未深入／待決 Proposal／OPKS gap／已確認不屬於本人與稍後線索，而不是顯示假精確百分比。
9. **完成仍由員工決定。** AI 說明為何目前已足夠、仍缺什麼、繼續最可能改善哪裡。員工可以繼續、暫停或看過缺口後強制匯出；系統不補造答案、不偷收 Proposal，也不隱藏未歸類 Task。

此情境的驗收效果是：AI 主動帶路，員工不用理解分析方法；每輪知道正在談什麼與為什麼；旁支線索不遺失；正式內容只在有意義檢查點由員工決定。

## 4. 焦點與進度 v0.1

### 4.1 焦點有兩層

本輪訪談目標示例：

> 釐清「處理客戶申訴」的邊界，判斷它是一個 Task，或需要拆成受理、調查與回覆。

當前問題示例：

> 最近一次收到申訴時，從收到訊息到結案，你實際做了哪些事情？

員工應能看到：

- 焦點名稱；
- 為什麼現在處理；
- 這個焦點還差什麼可以暫時收束；
- AI 下一步建議；
- 訪談中另外發現但先保留的線索。

### 4.2 進度不用單一百分比

因為新 Task、Duty 與 gap 可能持續出現，總分母未知。進度應呈現為「目前已知的工作地圖」：

- 已足夠；
- 訪談中；
- 尚未深入；
- 待補訪；
- 待員工決定；
- 已保留未知／不適用／暫不處理；
- 重大矛盾或結構問題。

Task、Duty、OPKS 與 Proposal 的狀態不能全部壓成一個總分。例如：

> 目前已知 11 個工作範圍；6 個已足夠、2 個正在深入、2 個尚未深入、1 個有重大矛盾；另有 3 個 OPKS gap 與 2 項 Proposal 待處理。

所有數字都應標明「目前已知」，並可展開看到具體內容與原因。

### 4.3 三種不同的停止感

介面與 AI 說法要區分：

1. 本輪可以先停：已有自然停點，下次可恢復；
2. 訪談目前已足夠：主要 coverage 與高影響缺口已處理或留下理由；
3. 可以匯出：匯出檢查已列出所有剩餘缺口；若仍有缺口，員工可明確選擇強制匯出。

### 4.4 「目前已足夠」採混合判斷

不得只靠固定題數／分數，也不得只靠 LLM 一句主觀宣告。系統以可檢查證據打底，由 LLM 做整體專業判斷與白話解釋，最後由員工決定停止或繼續。

判斷面向至少包含：

- 工作範圍：主要、週期性、低頻高影響工作與責任邊界是否大致盤點；
- 重要工作：本人責任、主要結果、完成判準與關鍵例外是否足以形成可信描述；
- 結構：是否仍有可能顯著改變 Task merge／split 或 Duty 分組的重大矛盾；
- OPKS：重要 gap 是否已分析、排入待補訪，或有 unknown／not applicable／暫不處理等明確理由，而不是要求欄位全部填滿；
- 員工決策：是否仍有可能大幅改變 Current JD 的 Proposal 尚未處理；
- Reference challenge：是否做過當下有必要的 coverage 檢查，且沒有把公版內容誤認為員工事實。

只有當沒有未處理的重大問題，而且剩餘缺口已清楚呈現、預期不會推翻整體 JD 時，AI 才建議「目前訪談已足夠」。同時必須說明：為什麼足夠、還缺什麼、繼續訪談最可能改善哪裡。員工仍可繼續、暫停或強制匯出；新證據出現後也可重新開啟。

## 5. 從既有研究回查後的修正

### 5.1 Task：焦點不等於 Task 抽取

依 [`Task Discovery 深入研究`](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)與[`Task 邊界研究`](2026-07-28-task-boundary-merge-split-and-identity-research.md)：

- 員工訊息、Source Claim、未映射線索、故事、Work Unit 與 Task Candidate 是不同層次；
- 一個故事可支持零到多個工作假說，多個故事也可能支持同一 Task；
- Task 要有 meaningful outcome、本人目前責任、可指派／查核與相對穩定性；
- 工具、方法、單一步驟、過去工作、他人工作與一次性支援不得自動升格；
- 每輪沒有新 Task、只補證據或 `no-op` 是正常結果。

因此本流程的焦點可以是故事、責任邊界、矛盾、coverage 或 OPKS gap，不一定每次都以既有 Task 為起點。

### 5.2 Duty：可提早分析，但保持為可變動假說

依 [`專業顧問流程最終反方審查`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)與[`iCAP 欄位標準`](2026-07-13-ai-redesign-raw-icap-field-standards.md)：

- 初期責任區域與已出現的工作線索足以啟動 `duty-grouping` Skill，但形成的是可變動 Duty hypothesis，不是固定盒子；
- Duty 可隨 Task／Work Unit 增加，依共同 purpose、責任、outcome、workflow stage、服務對象或領域動態整併；
- Duty 需要自己的候選、來源、改名、重分組、merge／split 與 Proposal 生命週期，不能只在匯出時臨時分組；
- iCAP 要求主要職責／任務粒度盡量一致、以成果或功能表達，但沒有固定條數下限。

因此「一開始順便分析職責」是合理的；限制只是不能把早期 Duty hypothesis 當作後續 Task 的不可變分類。

### 5.3 O／P／K／S：方法可獨立載入，語意仍互相依賴

依 [`OPKS 設計裁決`](2026-08-01-opks-design-decisions-research.md)、[`OPKS 漸進蒐集`](2026-08-04-opks-progressive-elicitation-research.md)與[`OPKS gap 再分析研究`](2026-08-06-opks-gap-reanalysis-blocking-research.md)：

- 既有「以單一 Current JD Task 為一次 OPKS operation」是控制輸出量、prompt/schema 大小與 durable failure boundary 的現行實作決策，不應升格成產品流程必須等待 Task 穩定的證據；
- 未來可把 O、P、K、S 拆成各自的 Skill，根據當輪證據與焦點按需載入；Skill 是否獨立，不預先決定是否另開模型呼叫；
- 正式資料關係仍是 O/P 綁 Task，K/S 是文件層項目並與相關行為指標／Task 建立多對多 linkage，A 是文件層；但分析期間可以先連到 Work Unit／Task hypothesis，形成 Proposal 前再完成 identity reconciliation；
- K/S 應由實際 Task 與行為證據反推，不直接要求員工自列能力；
- 是否需要某個分析 Skill，可由可檢查的 policy、當前 focus／gap 與模型判斷共同決定；員工不需要按「產生 OPKS」；
- 證據不足要保存具體 gap，agenda 一次選一題；unknown／not applicable 可以成為有理由的終止；
- OPKS 可能揭露 Task outcome 或邊界有問題，必須允許回頭修正 Task。

仍需保留的語意依賴是：O／P 必須能連回正在分析的工作；K／S 必須連回工作行為／Indicator，不能因 Skill 拆開就各自生成漂亮但無支持的清單。

現行研究仍有一項已知風險：active gap 可能讓後期 Task 的再分析出現尾端衰減。2026-08-06 的研究因缺少 10–15 回合真人資料而暫不翻案；未來流程評測必須量測 gap 開啟率、關閉率與 late-discovered Task 的產出，不能假設現行 gate 已是最優解。

### 5.4 AFFiNE 階段化需求稿：保留可見控制，不採剛性階段門

2026-08-12 逐段讀取 owner 提供的 `職務分析_AI_階段化狀態機需求稿 _ AFFiNE.html`。它是有價值的 stakeholder 草稿，但不是本 repo 權威，也不能覆蓋既有研究與已確認的產品流程。

整合裁決：

| 類別 | 處理 | 理由 |
|---|---|---|
| 單一主要 AI、明示目前目標／剩餘項目／下一步 | 保留 | 提升焦點、進度與可恢復性，不需要人格化多 Agent |
| 待訪談清單的來源、狀態、最近更新、暫停／恢復 | 保留並擴充 | 改為跨 Story、Work Unit、Task、Duty、OPKS gap、矛盾與 Proposal 的 agenda projection，不建立第二份 authority store |
| 候選區與正式 JD 分離；可接受、修改、拒絕、退回補訪 | 保留並對齊 Proposal seam | 符合員工 authority；Proposal 採有意義檢查點與 dependency-aware changeset |
| 右側 JD 可直接編輯、排序與重新啟動訪談 | 保留 | 員工直接編輯與 AI Proposal 都回到同一 authority seam |
| Reference 不直接定義員工工作 | 保留並改成 blind-first | 員工不需操作檢索；AI 預設在已有 employee-first work model 後才按需查詢現有 iCAP，形成 just-in-time coverage challenge，員工可略過 |
| 「骨架／Duty／Task／OPKS」狀態機 | 改寫 | 僅作可見的 focus／attention mode 與 durable checkpoint，不限制當輪可載入哪些 Skills，也不是資料生命週期通關門 |
| 完成條件與狀態提示 | 改寫 | 從固定階段完成改成 focus sufficiency、global readiness、具體 gap 與 terminal reason |
| 新線索先保存、不任意打斷 | 改寫 | 一般線索先停放；會推翻 Task 邊界、本人責任或重大結論者必須先澄清，並保存返回點 |
| Task 必須先有 Duty、禁止孤立 Task | 不採用 | 分析期間 Task 可暫無 Duty；Duty 是隨證據動態重組的假說與正式實體 |
| 只有已進 JD 的 Task 才能深入或分析 OPKS | 不採用 | Story、Work Unit 或 Task hypothesis 出現足夠證據時即可按需分析 O／P／K／S |
| AI 不得跨階段深入提問 | 不採用 | 與全回答理解、按需 Skills 及 OPKS 反向修正 Task 的需求衝突 |
| O＝工作行為、P＝工作產出 | 更正後才可使用 | iCAP 正確對位是 O＝工作產出、P＝行為指標；P 是成功完成 Task 的可觀察標準，可包含有依據的情境、行為、結果、條件與程度 |

主流架構佐證指向同一結論：Anthropic 建議從簡單、可組合的單一 agent pattern 開始，並以 Skills progressive disclosure 和最小高訊號 context 控制複雜度；OpenAI 現行 guidance 建議精簡 prompt、只暴露相關 tools，並明定 autonomy／approval boundary；Google ADK 2.0 則把 deterministic workflow 與 adaptive agent 組合，將業務規則、HITL 與可靠 transition 留給程式，把模糊語意判斷留給模型。

因此本產品採用的不是純自由 Agent，也不是純階段狀態機，而是：

> 員工看得見明確焦點、議程、進度與核准點；AI 在這些受控邊界內動態理解完整回答、選擇 Skills 並調整訪談；Current JD authority、Proposal commit、資料 invariant 與不可跳過的核准由 deterministic application control 保證。

## 6. 「方法知識」與「公版 Reference」必須分開

owner 提到「公版 RAG 讓 LLM 知道可以問什麼方向」，需拆成兩類：

### 6.1 從一開始可用：職務分析方法知識

例如：

- 如何辨識 Task、步驟、工具與他人工作；
- 如何做廣度盤點與具體事件訪談；
- 如何判斷 merge／split；
- 如何形成 Duty；
- 如何從行為與產出分析 OPKS；
- 如何停止、避免引導與做反方檢查。

這些是顧問方法、rubric 或未來 Skill，不是特定職業答案。第一版 Skill 候選至少可包含：

- breadth／story interviewing；
- task boundary／merge／split；
- duty grouping；
- output；
- performance indicator；
- knowledge；
- skill；
- reference challenge；
- completion／red-team review。

Skill 採 progressive disclosure：平時只保留短名稱與用途，當輪命中才載入完整方法。這解決的是方法 prompt 膨脹；當輪需要哪些員工原話、工作狀態與 Reference，仍是 Context Engine 的另一個問題。

### 6.2 有初步工作模型後按需使用：既有 iCAP 內容

第一版只使用 repo 已有的 iCAP 資產，不新增其他公版、一般網路搜尋或公司文件來源。iCAP 可以：

- 協助回憶；
- 做 coverage challenge；
- 提供可能追問方向；
- 提供術語與來源；
- 比較 match／partial／no-match／conflict。

它們不得：

- 因職稱直接定義 Task／Duty；
- 取代員工工作故事；
- 自動寫入 Current JD；
- 把「公版常見」說成「員工本人負責」；
- 一次整包塞入每輪 context。

主要顧問自行判斷當下是否需要查詢，員工不必進入獨立搜尋流程或手動挑選 iCAP。查詢可以發生在 Task、Duty、O、P、K、S 或收尾 coverage 檢查中，但不是每輪必做，也不是固定階段。

## 7. 記憶責任、權威分層與 Context Engine v0.2

本節先定義產品必須記住哪些不同性質的內容，以及誰有權改變它們；不預先決定資料表數量、向量資料庫、framework 或實際 storage topology。

### 7.1 來源記憶：員工真正說過什麼

保存員工原話、來源回合、時間、附件／引用位置，以及後續更正、否認或撤回的關係。它是回答「這項理解根據哪一句話」的 evidence layer。

- 摘要不得覆寫或取代原始來源；
- AI 不得改寫員工原話後冒充 source；
- 更正保留前後歷史並標示目前效力，不以刪除舊句偽造一致性；
- 後續所有 Work Model、Proposal 與正式內容應可追溯到來源或明確的員工直接編輯。

### 7.2 工作模型記憶：AI 目前怎麼理解

保存 Story、Work Unit、Task／Duty hypothesis、O／P／K／S 候選、linkage、gap、矛盾、未映射線索與 retired candidate。它是可變動的分析層，不是 Current JD。

- AI 可以依新證據新增、修正、合併、拆分、重新連結或淘汰假說；
- 每項假說要保留穩定 identity、支持／反對證據、信心理由與生命週期狀態；
- `employee_denied`、過去工作、他人工作、一次性支援等 retired reason 不應被一般檢索重新當成 active candidate；
- Work Model 的變化可以影響焦點與 Proposal，但不得直接改變正式 JD。

### 7.3 正式文件記憶：員工已授權的 Current JD

只包含員工直接編輯，或經 Proposal 決策後由 authority commit seam 寫入的正式內容。

- Current JD 是產品文件真相；
- AI 不能因摘要、重新分析、模型更換或 Reference 命中而直接覆寫；
- 新證據可產生挑戰或修改 Proposal，但舊內容在員工決策前仍維持正式效力；
- 正式項目與其決策／來源 lineage 應可追溯。

### 7.4 訪談流程記憶：現在為何問、之後要去哪裡

保存目前焦點、選擇原因、完成目標、返回點、待處理 agenda、已停放線索、focus gap、待決 Proposal、進度投影與停止理由。

- 暫停或切換後能自然恢復，不靠模型猜測上次談到哪裡；
- agenda 是由其他權威物件與 workflow metadata 形成的工作投影，不成為第二份 JD 或第二份 Work Model；
- AI 預設選下一個最高價值焦點，員工可覆寫；
- 已完成、已拒絕、已退休與 terminal unknown／not applicable 必須有理由，避免無限重問。

### 7.5 Reference 是獨立知識來源，不是第五種員工事實

第一版 Reference lane 只包含既有 iCAP 內容，並保存其來源、版本、片段與 citation。iCAP 可以支持 coverage challenge、術語與追問，但不能和員工原話混成同一 evidence authority，也不能因檢索相關度高就直接提高為工作事實。O*NET、一般網路搜尋、公司文件、表單與既有 JD 不在目前需求範圍，也不預先列為 backlog。

Reference 記憶分成兩種不同用途：

1. **檢索技術軌跡**：query、候選來源、實際送入模型的片段與排序等可放在 bounded run trace／ContextManifest，供重播、成本與除錯使用；它不是 Work Model 或正式分析結論，也不要求所有命中永久留在產品狀態。
2. **具產品意義的 challenge receipt**：只有被拿來詢問、改變議程／Proposal 或形成 coverage 裁決的候選才持久保存。它連結來源版本、challenge fingerprint、目標範圍、提出理由、員工 source event、裁決與生命週期。

receipt 的裁決歷史採追加與 supersession，不以覆寫抹除員工先前說法；員工更正時保留舊裁決與新 evidence 的關係。同一 challenge 可掛多個 iCAP 片段或版本，但不能因另一個近義片段而繞過已存在的 no-match／拒絕紀錄。不同片段或版本有實質衝突時不合併成假共識，而是保留差異並在確有影響時中立詢問。

### 7.6 摘要、embedding 與模型 reasoning 都不是 authority

- 對話摘要、焦點摘要與壓縮筆記是可重建的 context artifacts；
- embedding、向量相似度與 rerank score 是檢索索引，不是事實真偽或員工認可度；
- provider 保存的 conversation state／reasoning state 可提高連續性，但不能取代本地持久化的來源、Work Model、Current JD 與 workflow checkpoint；
- 模型或 framework 可以替換，只要上述產品權威與 lineage 不被改變。

每輪 Context Engine 可以從各層選取「最近必要對話＋焦點相關原話＋相關工作假說＋已接受內容＋當前 gap／Proposal＋命中的 Skill／Reference」，但完整保存與當輪傳入是兩件不同的事。

### 7.7 Context Engine 的第一輪權威資料結論

截至 2026-08-12，OpenAI、Anthropic、Google 與 LangGraph／LangChain 的官方資料沒有提供一份可直接套用到職務分析的「最佳 context 配方」，但共同支持以下方向：

- context 是有限注意力資源；可用窗口變大，不代表把完整歷史放入每輪會更準；
- 長流程應把可恢復的完整 session／event log 與本輪模型可見 context 分離；
- 業務進度與權威狀態應明確持久化，不由模型從聊天歷史猜測；
- 精簡且任務相關的 prompt、tools、Skills 與資料通常比全部常駐可靠；
- compaction、summary、provider conversation state 與長期 memory 可提高連續性，但都不能取代原始來源與業務 authority；
- context selection 沒有通用最佳值，必須以本產品的長訪談、修正、跨題線索、Task／Duty／OPKS 與 Reference 情境評測。

2026-08-12 進一步核對 OpenAI、Anthropic、Google、Microsoft Research 與 OPM 第一手資料後，新增一項較精確的產品結論：**全域結構要持續存在，但不等於每輪傳入全域細節。** Anthropic 的最新工程指引主張最小高訊號 context 與「少量預載＋just-in-time 探索」的 hybrid；OpenAI 建議注入當下相關的 structured-state slices，並精簡重複 prompt／tools；Google 將 durable state、session memory 與本輪 working context 分開，且其 Sufficient Context 研究顯示「相關」不等於「足以判斷」，額外但不充分的 context 也可能提高幻覺；Microsoft 的 GraphRAG／DRIFT 研究則支持先有全域概觀再深入局部，但 dynamic community selection 也說明靜態送入全部全域摘要昂貴且低效。OPM 的職務分析方法要求先維持可追溯的 preliminary Task／competency inventory，再由 SME 評定、修正與建立 linkage，支持本產品不能只把每個焦點孤立分析。

上述資料共同支持的是「**受限全域定位＋焦點細節＋按需展開**」的架構模式，不是「每輪把完整 JD／Work Model／OPKS／歷史全部塞入」。Microsoft 的量化結果來自 AP News corpus，Google 的 Sufficient Context 主要是 RAG QA；目前仍沒有公開 benchmark 直接證明同一配方能提高繁中職務訪談品質。以下產品裁決是依這些共同模式與 Caliburn 的跨 Task 線索、Duty 重組、OPKS linkage、員工更正和進度需求所作的領域推論，不能宣稱為外部研究已直接驗證的成效。

這些來源也形成一個重要限制：框架可以提供 session、checkpoint、store、summary middleware、retrieval hook、tracing 與 token accounting，但無法自行知道「哪句員工原話是必要證據」「哪項更正優先於舊說法」或「Reference 何時不得混入員工事實」。這些仍是 Caliburn 的產品與 domain policy。

外部證據的可轉移性也有限：Anthropic 的主要案例包含 coding／research agent，Google 的長流程案例是 HR onboarding，Contextual Retrieval 的量化資料集也不是繁中職務訪談。目前沒有可信公開 benchmark 證明任何 Context framework 或固定配方會直接提高專業職務說明書品質；本節只能把共同架構模式轉成待驗證假說，不能把別的產品結果當成 Caliburn 成效。

### 7.8 三種 Context 組裝方案

#### 方案 A：完整歷史／provider state 優先

每輪延續 provider conversation、完整 message history 或 provider compaction，讓模型自己從長 context 找重點。

- 優點：初期程式少、對話自然、可快速建立 baseline；
- 缺點：舊 token 仍可能持續計費，長歷史會引入 context pollution；opaque compaction 不可檢查；provider lock-in 高；不能保證重大更正、權威邊界與跨題線索被正確使用；
- 結論：只適合作為連續性輔助與比較 baseline，不作產品唯一記憶或權威來源。

#### 方案 B：完全由程式預先組好固定 ContextPack

應用程式依固定 lanes、配額與排序一次選完，模型不能再查其他內容。

- 優點：成本、隔離、重播與測試最容易控制；
- 缺點：規則難預知某句舊話何時重新重要；固定 lane／比例容易隨模型進步而過時；選漏後模型沒有補救能力；
- 結論：適合 authority floor、document scope 與不可省略項，不適合承擔全部語意相關性判斷。

#### 方案 C：可恢復記憶＋必要核心＋受控按需檢索（產品方向已確認）

完整來源與狀態留在本地可恢復 store；應用程式先提供一個小而可靠的必要核心，再以結構化關聯、lexical／semantic retrieval 形成候選；模型若仍需要更多資料，只能透過 document-scoped、read-only 工具按需取得。

- 優點：保留 authority、來源與重播能力，又讓模型能處理程式無法預列的語意關聯；可替換模型與檢索實作；
- 缺點：需要明確工具契約、budget 與停止規則；正式 context eval 後置期間，若工具設計不良，較可能到人工使用時才發現漏查、重查或追逐無關內容；
- 結論：最符合本產品「前景專注、背景全域吸收、長期可恢復、員工核准」的需求；owner 已於 2026-08-12 確認採此產品方向，但這不直接裁決 framework、schema、token 門檻或 production 實作。

推薦方案不是「都交給模型」。程式仍決定 scope、authority、必帶資訊、可用工具、token 上限與降級；模型只在這些邊界內判斷還需要讀什麼。

### 7.9 每輪的白話 Context 流程

1. **保存，不等於傳入**：員工原話先以 source transaction 完整保存；model／tool 原始結果與 verification 依 execution boundary 保存為可恢復 artifact；只有通過驗證並完成 semantic commit 的 consultant turn 才成為正式對話。Work Model 變化與 workflow event 依各自交易保存，不得用摘要取代原始來源。
2. **建立不可省略核心**：放入精簡 authority 規則、本輪 operation／focus／完成目標、員工當輪完整文字回答、受限全域工作索引、焦點相關 Current JD／Work Model，以及會影響本輪判斷的最新更正／矛盾／待決 Proposal。
3. **走直接關聯**：先依 document、穩定 ID、Task／Duty／OPKS linkage、source receipt、speaker、generation 與狀態查詢，不先用向量猜。
4. **找較遠候選**：對較早原話與未映射線索使用 lexical 與 semantic retrieval；結果保留 speaker、原回合、entity、前後片段與 authority metadata，再視需要 rerank。
5. **按需載入方法**：平時只讓模型知道可用 Skill 的名稱與用途；命中 task-boundary、duty-grouping、O、P、K、S 或 Reference challenge 時才讀完整方法。
6. **允許受控補查**：若 context 顯示仍有未載入來源，模型可呼叫唯讀工具取得特定 Task 的原話、相關 Duty／OPKS、修正歷史或 Reference；不得跨 document，也不得以工具結果直接寫 Current JD。
7. **計數、裁切與降級**：依實際 model profile 計算 tokens，先保留 output／schema／必要 authority；超預算時先移除重複工具輸出、低價值 Reference 與較遠候選，不靜默刪除當輪回答、最新更正或 blocking contradiction。
8. **留下 Manifest**：記錄實際載入、未載入、選取理由、來源 hash／generation、Skill／tool、tokens、model profile 與輸出 lineage，供 replay、除錯與 eval。

附件、長文件與大型 Reference 不保證整份放入；當輪員工文字回答原則上完整傳入，附件則以可追溯片段或按需工具讀取。若單一回答本身超過模型安全預算，系統必須明示分段或 context budget 問題，不可無聲截斷。

#### 7.9.1 每輪全域定位的裁決：受限索引，不是完整資料

每輪模型需要知道「目前整份職務大致長什麼樣、現在在哪裡」，否則只靠焦點 retrieval 容易重複建立 Task、把旁支線索歸錯位置、錯過跨 Task 矛盾，或延遲 Duty regroup。反過來，完整傳入所有 Task 描述、Evidence、OPKS、Proposal 與歷史，會讓過時假說和無關資訊反覆佔用注意力。

因此每輪必帶一份 **bounded global orientation index（受限全域工作索引）**。它是從 Current JD、Current Work Model 與 workflow state 產生的 deterministic、versioned、可重建投影；不是 LLM 自由摘要、RAG 搜尋結果、第五份 authority store，也不因被放進 prompt 就改變任何項目的權威。

索引至少讓模型辨識：

- document／generation 與目前 focus；
- active Duty／Task 的穩定 ID、短名稱、基本歸屬與生命週期狀態；
- 每個項目屬於已授權 Current JD、可變 Work Model hypothesis，或 workflow gap／待決狀態，三者不得混成同一權威；
- 未歸類 Task、重大矛盾、blocking dependency 與待決 Proposal 的存在及可查詢指標；
- 目前已知範圍的摘要數量，使模型與員工介面的進度投影能指向同一組可解釋對象。

索引平時不攜帶完整 Task 敘述、全部原話／Evidence、完整 OPKS、完整 Proposal payload、Reference 內容、整段歷史，或已退休／已否認候選的細節；這些依焦點、直接關聯與受控工具按需取得。最新有效更正、會推翻本輪判斷的矛盾與其他 authority floor 仍由必帶核心另行保證，不能因索引精簡而遺失。

索引也不能無限成長：

- 小型職務在預算內可列出全部 active Duty／Task headers；
- 超出預算後，確定性降級為全部 Duty 摘要、目前焦點及相鄰 Task、其他區域的數量／狀態／查詢指標；
- 模型需要遠端細節時，透過 document-scoped read-only lookup 展開，不把所有區域預先載入；
- 降級規則、被省略區域與實際載入內容寫入 ContextManifest，不可靜默假裝索引完整。

這項裁決把「前景專注、背景全域吸收」轉成可實作邊界：前景得到足以完成當輪判斷的細節；背景保有結構定位與異常訊號，而不是保有所有細節。它同時支援 Task／Duty 隨訪談演化、OPKS 按需分析、旁支線索停放與可解釋進度，不要求第一版先導入 GraphRAG、向量記憶或額外 planner model。

### 7.10 必帶、候選與按需三層

| 層級 | 內容 | 誰決定 | 可否因 budget 直接省略 |
|---|---|---|---|
| 必帶核心 | authority、operation／focus、當輪回答、受限全域工作索引、焦點 target、最新有效更正、blocking contradiction、相關待決 Proposal | deterministic application policy | 索引本體不可省略；可依已記錄規則降低索引細節，仍超額才明確失敗或分段 |
| 候選 context | 較早原話、相鄰 Task／Duty／OPKS、open gap、未映射線索、少量近期對話 | 結構化 filter＋retrieval＋rerank | 可依可解釋順序降級 |
| 按需 context | 更遠來源、完整歷史片段、額外 Skill、Reference、低頻 lineage | 模型經受控唯讀工具請求，程式驗 scope／budget | 可拒絕並回報理由 |

第一版不先規定例如「Evidence 40%、Recent 20%」的固定比例。不同 operation、模型窗口、輸出 schema 與資料密度不同；開發期先使用可設定、可觀測、可回退的保守上限，不為了等調參資料阻塞成品，成品完成後再由 eval 決定各類 floor／ceiling。

### 7.11 檢索不是只有向量搜尋

推薦候選順序：

1. deterministic relational／graph lookup：穩定 ID、linkage、speaker、generation、狀態與 source receipt；
2. lexical retrieval：保留職稱、術語、表單名、系統名與員工用字的 exact match；
3. semantic retrieval：找不同措辭但語意相關的舊故事與線索；
4. context expansion：補上 speaker、原回合、相鄰句、所屬 Task／Duty 與修正關係；
5. rerank／budget selection：只把最高價值且不重複的候選送入模型。

Anthropic 的 Contextual Retrieval 實驗中，contextual embeddings 加 BM25 在其資料集將 top-20 retrieval failure 由 5.7% 降至 2.9%；這只能證明 hybrid retrieval 值得成為實驗候選，不能證明相同 chunk、top-k、embedding 或 reranker 對 Caliburn 最佳。若第一版為完成產品而先採用，必須包在可替換設定後、保留檢索與來源紀錄；繁中長訪談 domain eval 延至可用成品完成後再做。

Reference 必須使用獨立 namespace／lane 與 source label。員工來源與公版內容即使語意相似，也不得因去重而合併；semantic score、rerank score 與 memory confidence 都不是 authority。

### 7.12 Compaction、provider state 與 cache 的位置

- 原始 session／event、員工原話、Current JD、Work Model 與 workflow checkpoint 由本地持久層保存；
- provider `previous_response_id`、persisted reasoning 或 conversation state 可作短期連續性優化，不能成為唯一 resume 依賴；
- provider／framework compaction 可減少長會話 context，但 opaque 或生成式摘要只能當可重建 artifact；
- prompt cache 只優化穩定前綴，例如精簡 authority、固定 schema 與 Skill metadata；焦點、員工回答、檢索結果放在後段；
- 使用 provider 原生 token counting 或經 conformance 驗證的 tokenizer，在送出前估算，在回應後保存實際 usage；
- 換 provider／model 後可以重建 ContextPack；不得因 provider reasoning state 遺失而失去來源、正式內容或訪談進度。

### 7.13 框架能接手與不能接手的部分

| 能交給成熟框架的通用能力 | Caliburn 仍須保留 |
|---|---|
| checkpoint／resume、thread state、interrupt／HITL、retry boundary、streaming、tracing | Current JD authority、generation／read-set、proposal commit seam |
| model interface、structured output、tool schema、dynamic prompt／middleware hook | ContextPolicy：scope、必帶核心、來源資格、最新更正與 retired exclusion |
| session／store 介面、summary middleware、retrieval connector、token／usage telemetry | 員工原話與 Reference 分權、quote anchor、evidence lineage、ContextManifest |
| Skills loader／tool discovery、按需載入機制 | Task／Duty／OPKS 專業方法、Skill 版本核准與觸發語意 |

LangGraph／LangChain 目前提供的 persistence、HITL、Store、middleware 與 tracing 與本需求相容；OpenAI Agents SDK 也有 session、compaction 與可序列化 HITL；Google Agent Platform 提供 Sessions／Memory Bank。它們證明目前已有多個由主流團隊維護的通用 plumbing 候選，不代表候選在 Caliburn 已驗證成熟，也不代表本產品應同時採用或直接交出 authority。Google 的託管 Memory Bank 也不符合 current-only 本機產品的預設部署邊界，現階段只學習其「session、memory、explicit state 分離」架構。

框架選型必須後於這份產品 policy，並以小型 conformance spike 驗證；不得為了使用框架而建立第二份 JD、第二份 Work Model 或另一條 AI 直接寫入路徑。

### 7.14 正式 Context eval 後置；開發期只留最小安全網

Owner 已於 2026-08-12 裁示：時間優先，先完成可用的端到端成品，再建立正式 eval。成品完成前不另開以下工作：

- framework-neutral eval dataset、golden transcript 與人工標註計畫；
- A／B、context ablation、LLM-as-a-judge、Pydantic Evals／Ragas runner；
- required-context recall、品質、成本與延遲的量化 release gate；
- 為了建立 baseline 而延後已可垂直交付的產品能力。

開發期仍保留下列最低安全網；它們是一般工程正確性與未來可回溯性，不是正式 eval 專案：

- 現有 unit／integration／contract tests 與 domain invariants 繼續通過；
- authority、document isolation、proposal commit seam、generation／read-set 等 deterministic safety 不得因趕工取消；
- 每個垂直切片做一次簡單人工 happy-path／resume／approval smoke check，不建立評分資料集；
- ContextManifest 或等價紀錄保留 model／prompt／Skill／tool／source refs／tokens／結果 lineage，避免成品後無法重播；
- 新框架只做它要取代之介面的 conformance test，不比較模型回答分數。

可用成品完成後，再建立下列正式 Context eval 情境：

至少建立下列長訪談情境：

- 員工在後段更正前段說法；
- 回答焦點 Task 時順帶說出新 Task；
- 新線索迫使 Duty regroup；
- Task 尚未穩定時已出現 O／P／K／S 證據；
- 同一術語由員工與 Reference 提供不同內容；
- 訪談暫停數日後恢復；
- 長歷史中同時存在 active、rejected、retired 與 superseded candidate；
- context 超預算，需要降級但不可丟掉 correction 或 authority。

屆時比較方案 A、B、C 及其變體，至少量測：

- required-context recall；
- irrelevant-context precision／duplicate rate；
- correction／contradiction carry-over；
- off-focus clue capture；
- false authority contamination；
- quote／source attribution correctness；
- 下一題與目前 focus／gap 的相關性；
- proposal 正確性與員工 edit／reject 率；
- input／output／reasoning tokens、cache hit、額外 tool call、延遲與成本。

正式 eval 啟動後，不能只用「token 變少」判定成功。接受候選的最低條件是：domain 品質與 required evidence 不劣於 baseline、authority 錯誤為零，且成本／延遲至少一項有可重現改善。具體門檻屆時依可用成品與真實操作形狀建立，不回頭阻塞第一版開發。

### 7.15 本節仍未決定

- 每種 operation 的確切 token floor／ceiling；
- adaptive bounded run 的最大 inference／tool step、elapsed time／成本上限，以及哪些 optional result group 能建立足以安全 drop 的 typed dependency contract；在此之前維持 fail-closed；
- 受限全域工作索引的最終 schema、大小門檻、摘要層級與不同 model profile 的降級參數；
- 是否第一版就使用 embedding、哪個 embedding／reranker 與 top-k；
- 哪些具體條件值得增加獨立 model-based context planner 或 specialist call；預設不得固定每輪增加；
- 主要 runtime 採 LangGraph、OpenAI Agents SDK、PydanticAI 或薄型自有 orchestration；
- provider conversation state、compaction、prompt cache 的啟用條件；
- ContextRequest／ContextPack／ContextManifest 的最終 schema 與資料表。

上述第一版實作細節先由 current-only 邊界、可逆設定、介面 conformance 與人工 smoke 決定，不由「大廠有提供」直接決定；模型品質、最佳參數與成本調優延至可用成品完成後，以長訪談 eval 與實際數據收斂。

### 7.16 Durable input、模型語意結果與業務狀態分離（已確認方向）

Owner 於 2026-08-12 確認：員工回答即使遇到 AI 失敗也必須保存，之後以同一個 input event 重試分析。這項裁決同時收斂一輪處理的責任邊界：**來源事件、模型語意結果、業務狀態與稽核不是同一個 LLM output。**

建議的邏輯順序是：

```text
① application 保存 immutable employee input event
② Context Engine 依 document／focus／authority 組裝本輪 context
③ 主要顧問按需載入 Skills 與 document-scoped read-only tools
④ 模型提交 typed semantic result
⑤ runtime 保存已完成的 model／tool result 與 execution evidence，application 驗證、對帳
⑥ deterministic reducer 只從通過的候選形成 VerifiedCommitPlan
⑦ Work Model／agenda／Proposal／成功 consultant turn／result receipt 原子提交後才回給員工
⑧ Proposal 仍須等員工 accept／edit／reject，才可經 authority seam 改 Current JD
```

若 ③–⑦ 任一步失敗：employee input event 保留為 durable source，記錄 typed processing failure；已成功的 provider／tool／verification artifact 可以保留作恢復與診斷，但 Work Model、agenda、Proposal、Current JD 與成功 consultant turn 不得出現半套變更。重試沿用同一 input event／operation identity；已存在可安全重播的 provider result 時不得盲目重打，新的 wire attempt 才分配新的 attempt identity。

模型只負責必須由語意判斷產生、且有真實下游消費者的內容。邏輯上包含：

1. source-anchored findings：本輪明示內容、更正、矛盾、新線索、候選與 gap；
2. change intents：對 Work Model 或 Proposal 的新增、修正、合併、拆分、重新分組、連結或淘汰建議；
3. next move：維持／切換焦點、reason codes、停止建議與最多一個主要問題；
4. employee-facing reply：簡短承接、必要摘要與問題，不得宣稱尚未提交的正式變更已生效。

上述是**語意表面**，不要求第一版必須把四類塞入一個巨大 JSON。可以由一次 bounded tool loop、少數按需 specialist result 或一個 final submit contract 實現；實際 topology 仍須以 provider conformance、schema 複雜度、延遲與可維護性決定。固定每輪跑 Extractor／Consultant／OPKS Coder／Projector，或讓罕見 Duty／split／OPKS 結構永久污染常見 schema，都不因本節而成立。

application／framework 應自行產生並保存 operation ID、event ID、時間、model／prompt／Skill／tool version、generation、read-set、state revision、ContextManifest、token／成本、驗證結果與 audit。LLM 不得自行宣稱這些欄位，也不得直接產生 authority commit outcome。LangGraph／LangChain／provider session 可以承接 checkpoint、tool loop、typed output 與 tracing plumbing，但 framework state 不能成為第二份 Source、Work Model、Proposal 或 Current JD。

這項分離與外部主流做法一致：OpenAI 將 final output、history、interruptions 與 resumable state 分開，並區分 function calling 與 user-facing structured response；Anthropic 將 session 定義為 harness 外的 append-only event log，工具呼叫只代表模型提出結構化要求、由 application 執行；Google ADK 也把 event content、tool event 與 state delta 分開；LangGraph 則把 message stream、state snapshot、interrupt 與 final output 分開。這些框架只證明通用責任邊界，不替 Caliburn 決定職務分析語意與 authority。

#### 7.16.1 一個員工回合採 adaptive bounded run（2026-08-13 已確認）

外部主流做法沒有支持「每一輪固定多跑幾次模型」是普遍較好的方案。OpenAI 建議在一次工具呼叫已足夠時維持直接路徑，只有 bounded filtering、ranking、aggregation、validation 等工作才增加受控流程，並先定義 evidence、retry 與 stopping limits；Anthropic 建議從單次 LLM＋retrieval／examples 等最簡單可行方案開始，只有可清楚分解且品質改善值得延遲與成本時才加入 chaining、routing 或 evaluator loop；Google 與 Microsoft 也都把已知順序、business rule 與 function 留給 deterministic workflow，把真正開放的語意判斷留給 agent。這些是跨產品的工程模式，不是職務分析品質已被公開 benchmark 驗證的證據。

本產品比較三種方案後的裁決如下：

| 方案 | 優點 | 主要問題 | 裁決 |
|---|---|---|---|
| 固定單次模型呼叫 | 最低延遲、成本與操作複雜度 | 模型缺少必要遠端 context 或工具結果時，只能猜測、失敗或把所有資料預塞入 prompt | 保留為預設快速路徑，不作唯一能力 |
| 自由 Agent loop | 能動態規劃、反覆查詢與自我修正 | 步數、成本與完成時間不可預測；可能重複工具、無進展循環、累積錯誤或模糊 authority | 不採用 |
| adaptive bounded run | 簡單回合維持直接，複雜回合才按需增加工具或模型判斷 | 需要明確權限、budget、停止與失敗契約 | 採用為產品方向 |

`employee turn`、`application run`、`model inference` 與 `tool call` 必須分開：員工送出一次回答後，application 先保存 durable input event，再啟動一個可觀測、可恢復的 run。這個 run 預設只讓主要顧問 inference 一次；主要顧問若已能提交合格 typed result 就立即結束。只有下列條件之一成立，才允許在同一 run 內增加步驟：

1. Context Engine 明示尚有本輪可查但未載入的必要來源，主要顧問提出 scope 明確的 document-scoped read-only request；
2. deterministic tool／verifier 的結果會改變本輪語意判斷，需要交回同一位主要顧問整合；
3. 某項工作具有與主回答明確不同的輸入、方法與 typed contract，值得呼叫少數 specialist；specialist 只回傳受限結果，不接管員工對話；
4. provider／schema 的一次可重試失敗符合 application policy，且不會建立重複來源或半套業務狀態。

相反地，「Skill 被命中」「本輪可能有 OPKS」「想讓答案再漂亮一點」或「框架支援 multi-agent」都不足以自動增加模型呼叫。Task、Duty、O、P、K、S Skill 是 progressive-disclosure 的方法邊界，可以在同一次主要 inference 中組合；只有實際 context、工具結果或獨立 contract 需要時才拆步。

每個 run 至少具有以下終止條件，且由 application／framework harness 強制執行：

- 主要顧問已提交通過 schema 與 deterministic checks 的 typed semantic result；
- 必要資訊只能由員工補充，轉成一個主要問題後停止；
- 工具結果沒有新增資訊、模型重複相同 request，或連續步驟沒有可辨識進展；
- 工具、provider、schema 或 verifier 失敗已達可設定重試邊界；
- 達到最大 inference／tool step、token、elapsed time 或成本上限；
- application 發現 scope、document、authority 或 approval boundary 不允許繼續。

停止時不得偽裝成功：已保存的員工回答維持 durable；若尚無可安全提交的語意結果，記錄 structured processing failure 或向員工提出必要問題，不更新 Work Model、agenda、Proposal 或 Current JD。若已有可驗證的部分結果，是否允許 partial semantic result 必須由各 operation contract 明定，不能由模型臨時決定。

對員工而言，這仍是一位顧問的一次回合：主要顧問負責最後整合、必要摘要、Proposal 與一個主要問題。read-only context／Skill／tool activity 在既定 capability boundary 內可自動進行；任何 Current JD authority 變更仍只經 Proposal 與員工 accept／edit／reject。內部只保存結構化 event、tool request／result、ContextManifest、版本、usage、validation 與 lineage，不要求或暴露模型私有 chain-of-thought。

這項裁決仍是 framework-neutral。LangGraph、OpenAI Agents SDK、Google ADK 或 Microsoft Agent Framework 可以承接 loop、checkpoint、pause／resume、typed tool 與 tracing plumbing；薄型自有 orchestration 也可以。後續 conformance spike 應比較誰能忠實承接上述 `application run` contract，而不是讓框架重新定義員工回合、記憶權威或 Current JD commit seam。

### 7.17 理解校準／可編輯假說的框架調查（2026-08-12）

主流框架沒有一個現成功能叫做「專業職務分析的目前理解」，但已共同提供組成它的通用元件：顯式 state、可序列化的人工輸入請求、pause／resume、事件或 checkpoint 歷史，以及把人工回覆送回原流程。這證明 Caliburn 不必自行重寫整套 durable HITL runtime；同時也證明不能把框架的 approval 直接等同於員工核准 JD。

| 候選 | 可直接借用的能力 | 對 Caliburn 的判斷 |
|---|---|---|
| LangGraph | `interrupt()` 可送出結構化 payload、暫停並保存 state；官方直接示範 review／edit state；checkpoints、`update_state` 與 time travel 保留舊路徑並可從修訂後狀態繼續 | **最接近理解校準的 runtime 形狀**。但 node resume 會從節點開頭重跑，前置副作用必須 idempotent；graph state 只能承接執行，不得成為第二份 Work Model 或 Current JD |
| PydanticAI | model／provider abstraction、typed output、deferred tools、人工 approve／deny，且可覆寫待執行 tool arguments；外部 UI 可在取得結果後以 message history 與 correlation 繼續 | **較薄、較符合現有 Python／Pydantic 技術面的候選**。適合把「提交 Work Model correction／Proposal」建成 typed command；但 stop-the-world 是新的 agent run，不是通用 state review/checkpoint，durable 業務狀態仍要由 Caliburn 保存 |
| Google ADK 2.0 | graph `RequestInput` 可攜帶 message、structured payload 與 response schema；Session 分 events 與可變 state；rewind 恢復 session state 且保留被 rewind 的事件供稽核 | 技術形狀相容，但 ADK 2.0 graph HITL 很新，且 Google 託管 runtime／memory 不符合本機預設邊界；目前只作設計對照，不構成換框架理由 |
| OpenAI Agents SDK | approval interruption 與 resumable state 分離；run 暫停時回傳 interruptions＋state，人工決定後恢復同一 run | 適合 provider-specific tool approval，不能直接提供可編輯 Work Model；若作主 runtime 會提高 provider lock-in，較適合作 adapter 或 conformance 對照 |
| Microsoft Agent Framework | provider clients、session、context providers、memory、middleware、graph workflows、typed request／response HITL 與 checkpoint；官方定位為 Semantic Kernel／AutoGen 的直接後繼 | 是 2026 年最新且功能完整的候選，但框架本身仍新；不能因功能表完整就優先遷移，需先證明 Python 成熟度、Postgres／本機適配與 authority seam 不重複 |
| Anthropic SDK／Managed Agents | tool runner 處理 tool loop、conversation state 與 validation；需要自訂 HITL／logging 時使用 manual loop；Managed Agents 可把 tool 設為 `always_ask` | 支持「敏感副作用由人決定」與 structured notes／外部 memory，但沒有現成的可編輯 domain hypothesis workflow；不值得只為本功能綁定 Anthropic runtime |

共同限制很明確：框架不知道何時一項 Work Model 變化「重要到必須讓員工看見」，也不知道員工更正應如何影響 Story、Task、Duty、OPKS、gap、agenda 與 Proposal。下列內容仍必須是 Caliburn 的 domain contract：

- 理解校準的 trigger policy 與 blocking／non-blocking 規則；
- `UnderstandingReview` 的 focus、摘要、uncertainty、source refs、next move 與 revision；
- `WorkModelCorrection` 如何保存員工原話、supersede／rebut 舊假說並重算下游；
- 校準與 Proposal／Current JD authority 的硬邊界；
- stale revision、document isolation、generation／read-set 與原子提交。

本輪建議不是立即全面導入框架，而是把上述 contract 保持 framework-neutral，第一個 conformance spike 只比較兩條最有價值的路徑：

1. **PydanticAI＋既有 Postgres domain state**：驗證較薄 model／tool／typed-result 層能否承接校準與 Proposal 命令；
2. **LangGraph interrupt＋Postgres domain state**：驗證 checkpoint／review-edit／resume 能否減少 orchestration 程式，又不產生第二份權威狀態。

Microsoft Agent Framework 保留為追蹤候選；OpenAI、Google、Anthropic SDK 作 provider 能力與介面 conformance 來源，不以它們的託管 session 取代 current-only 本地 authority。若第一版每輪都是短而原子的 request／response，PydanticAI 路徑可能更省；若很快需要跨請求的多步中斷、可編輯 state、分支與恢復，LangGraph 的收益才會明顯高於薄型 orchestration。

### 7.18 「目前理解」UI 與 agent-interface 框架調查（2026-08-12）

這次調查以仍在維護的 Microsoft HAX、Google PAIR v2、Apple HIG，以及 2026 年的 OpenAI ChatKit、Google A2UI、Microsoft Agent Framework／AG-UI 與 LangGraph frontend 為主。HAX 的原始研究較早，但目前仍由 Microsoft 維護並提供近期 GenAI 產品案例；因此用它作經驗證的人機互動原則，再用較新的官方 UI／protocol 文件確認技術趨勢，不把單一廠商元件當成產品需求。

官方資料共同支持的方向如下：

- Microsoft HAX 要求依使用者當前工作決定何時打斷、只顯示情境相關資訊，並讓錯誤理解容易忽略、修正或復原；解釋應按需要提供，過多解釋反而可能造成過度信任。
- Google PAIR v2 建議說明 AI 使用了哪些來源、把解釋連到當下行動、以 progressive disclosure 提供更多細節，並在收到回饋後說明它何時、如何改變體驗；其官方也提醒數字 confidence 容易被誤解，只有在能改善決策且經使用者研究後才適合顯示。
- Apple HIG 要求保留人的控制權，把 Edit／Undo／Retry／Adjust 放在生成內容附近，並在修正生效後給清楚回饋；回饋入口應容易找到但不打斷工作。
- OpenAI 最新 model guidance 要求集中定義 autonomy／approval boundary，讓安全範圍內工作持續進行，避免重複「先詢問」造成不必要停頓。ChatKit 已提供 card、可收合內容、editable text、form、confirm／cancel、型別化 action 與 server handler，證明結構化校準卡不必退回純對話文字；官方同時要求 server 把 client action 當不可信資料。
- OPM 的職務分析流程要求 preliminary task／competency 保留來源，並由 SME 評定 task 的重要性、頻率與 linkage。這支持在重大語意與結構節點向員工校準，但不支持把每個中間假說都變成正式核准。

#### 可借用的 UI／protocol 候選

| 候選 | 已提供能力 | 適配判斷 |
|---|---|---|
| 現有 Next／React＋framework-neutral typed contract | 完全控制固定側欄、校準卡、來源展開、revision 與無障礙；可直接沿用現行契約與 authority seam | **第一版建議**。元件少且語意固定，沒有必要先引入新的 agent UI protocol；代價是自行寫少量 presentation 與 action glue |
| LangGraph frontend `useStream`／HITL | interrupt payload、durable pause／resume、React 等 client hook；review card 可放 transcript、queue、dashboard 或 modal，也支援 edit／respond 與自訂表單 | 若 runtime 選 LangGraph，最值得直接借用；仍由 Caliburn 渲染 `UnderstandingCheckpoint`，不可把通用 approval card 當成 Work Model／Proposal 語意 |
| OpenAI ChatKit widgets／actions | card、list、badge、editable text、form、typed action、server/client handler 與 loading state | 元件形狀符合，但綁 ChatKit／OpenAI conversation surface，且常駐產品側欄仍需自訂；不值得只為一張卡提高 provider／UI lock-in，可作 contract 與互動範例 |
| AG-UI＋CopilotKit／Microsoft Agent Framework | SSE、HITL、shared state、custom／generative UI、前後端 tool calling；Microsoft 2026 官方整合已支援 Python FastAPI，但目前安裝指令仍帶 `--pre` | 適合 agent 以遠端服務供多個 client、需要跨框架 state sync 時。Caliburn 是本機單一 Web 產品，現在引入會增加第二套 session／state protocol、authority 對映與 preview 成熟度風險，先不採用 |
| Google A2UI 0.9 | declarative JSON、受信任元件 catalog、incremental update、React renderer、client-defined validation 與多 transport | 是 2026 年重要趨勢，但仍是 pre-1.0，主要解決跨 agent／跨平台的動態 generative UI。Caliburn 的核心校準 UI 應固定且可審查，不需要讓 LLM 自由組版；目前只借用「白名單元件、資料與呈現分離、增量更新」原則 |
| Microsoft Adaptive Cards | JSON card、跨 host responsive rendering、inputs／actions、視覺層級與 progressive disclosure 指南 | 適合 Teams／Outlook／M365 多 host；目前不是 Caliburn 的部署面。可借設計原則，不引入 runtime |

#### 收斂後的第一版邊界

先定義三個 framework-neutral 契約，再由現有 Web 原生元件呈現：

1. `UnderstandingProjection`：由 application 依 Work Model、來源、Current JD 與 workflow state 組裝側欄；status、source type、revision 與 blocked reason 不由 LLM 自報。
2. `UnderstandingCheckpoint`：由 deterministic trigger policy 產生 soft／branch-blocking 校準請求，攜帶變更摘要、source refs、受影響範圍與允許動作。
3. `UnderstandingCorrection`：員工的確認、修正或稍後處理命令；server 驗證 revision 後保存 durable source event，再由 reducer 重算。

若之後 conformance spike 選定 LangGraph，可把 `UnderstandingCheckpoint` 映射到 interrupt／`useStream`；若未來真的出現多 client、remote agent 或大量動態表單，再評估 AG-UI／A2UI。這樣跟上「declarative、typed、trusted component、server-validated action」的主流方向，又不為尚未存在的跨平台需求提早付出協定與狀態同步成本。

### 7.19 外部 LLM 資料、保存與路由邊界（2026-08-13 已確認）

本節處理的不是「職務資料能不能送」，而是資料送出後由誰處理、是否建立遠端長期狀態，以及更換模型或路由時是否仍能追溯。Owner 已確認所有職務分析內容都可交給外部 LLM，因此第一版不需要 PII classifier、欄位遮罩、逐次 consent、本機模型或 per-document privacy mode。API key、credential 與系統 secret 不屬於職務資料，仍不得進入 prompt、模型工具結果或內容紀錄。

官方政策顯示「不拿 API 資料訓練」與「完全不保存」是兩件不同的事：OpenAI API 預設不以資料訓練模型，但一般 abuse-monitoring log 最長可保留 30 天，Responses／Conversations／Files 等功能另有 application-state 規則；Anthropic 商業 API 預設不訓練且通常在 30 天內刪除輸入輸出；Gemini 付費 API 不以 prompts／responses 改善產品，但 Interactions、Files、明確 cache 與 Search grounding 仍有各自的保存行為。這些差異說明產品不能只寫「使用商業 API」就假設所有狀態語意相同。

OpenRouter 又多一層 routing：它本身預設不保存 prompts，除非使用者主動開啟 prompt logging；但實際請求仍會交給某個 provider endpoint。OpenRouter 可依 `only`／`order`／`allow_fallbacks` 鎖定路由，也提供 provider data-policy 與 ZDR 篩選。完整 Input／Output Logging 是獨立 opt-in，啟用後內容至少保存三個月；因此它不應被當成一般 telemetry 的無成本預設。

本產品比較三種政策：

| 方案 | 優點 | 主要問題 | 裁決 |
|---|---|---|---|
| 完全交給 gateway 預設路由與 logging | 設定最少、可取得最大可用性 | 實際 provider、保存政策、fallback 與模型品質可能漂移；難以重播與歸因 | 不採用 |
| 全部職務資料可送＋明確路由＋本地權威 | 不增加使用阻力；保留模型選擇、可替換性、追溯與既有 authority seam | 仍需少量 provider policy、route receipt 與設定管理 | **採用** |
| ZDR-only／本機模型優先 | 保存面最小 | 不符合目前需求，且會縮小模型／endpoint 選擇、增加費用或資格門檻 | 第一版不採用；未來若客戶要求再加 |

收斂後的第一版規則如下：

1. **全內容可送。** 員工原話、目前理解、JD、Task／Duty、OPKS、必要 Reference 與 quote anchor 都可依 Context Engine 判斷送出；不另做欄位級允許清單。
2. **只做一次清楚揭露。** 產品在設定或首次使用時說明會使用外部 AI provider；不對每輪 inference、Skill 或 read-only tool 重複詢問。
3. **本地是可恢復權威。** provider 端預設採不依賴持久 conversation 的推理方式；即使使用短期 cache、compaction 或 session 優化，也必須能從本地 Source、Work Model、workflow state 與 ContextManifest 重建，不得成為 resume 的唯一條件。
4. **不主動擴大遠端保存。** 接受商業 API 的標準 abuse／safety retention，不要求 ZDR；但不主動 opt in 訓練、data-discount sharing、完整遠端 Input／Output Logging，或為了方便除錯建立第二份長期 transcript。
5. **路由必須可說清楚。** 第一版維持一個明確 model ID 與 provider allow-list，不做無聲跨模型 fallback。至少記錄設定模型與設定 provider；若未來允許 gateway fallback，該次 run 必須記錄實際 model／provider、attempt chain、成本與停止原因，候選也必須來自明確設定，而不是任意 router alias。
6. **內容選擇仍由 Context Engine 控制。** 不限制外傳不代表把完整歷史、所有 Evidence 與全部 OPKS 每輪重送；仍採必要核心、受限全域索引、焦點細節與按需展開，以品質與成本為理由控制 context。
7. **provider-specific state 是可替換優化。** `store=false`、ZDR、region、cache TTL 等能力可由 adapter profile 映射，但 domain 與 use case 不依賴任一廠商欄位。某 provider 不支援某項控制時，回到已核准的標準商業 API 政策，不偽裝成 ZDR。

這項裁決不等於永遠拒絕 fallback、provider state 或遠端 observability；它要求這些能力未來以顯式、可追溯、可關閉的 adapter／runtime 設定加入。第一版不需要建立讓員工挑選 retention policy 的複雜 UI，也不需要為尚未存在的企業合規需求預做多套資料模式。

## 8. 已識別的流程風險與優化方向

### 8.1 焦點隧道效應

風險：AI 專注當前 Task 後漏掉回答中的其他工作。

方向：每輪先做全域理解，再做焦點追問；保存未映射線索與新 Task 候選；開發期以人工 smoke 確認基本保存路徑，成品完成後再以 capability eval 量測「旁支線索不丟失」。

### 8.2 Duty 過早定型

風險：初步 Duty 會成為分類盒子，後續 Task 被硬塞進去。

方向：初期只稱暫定責任區域／Duty hypothesis；有足夠依據時隨時可形成分組提案，但不得宣稱永久定稿；任何新 Task、O/P/K/S 線索都能觸發 regroup review。

### 8.3 Proposal fatigue

風險：每句話都跳出核准卡，訪談無法自然進行，員工也會機械接受。

方向：累積成一個有意義的小段落再提案；高影響 topology change 與低風險文字修改可採不同呈現，但不得降低員工 authority。

### 8.4 OPKS 填表與尾端衰減

風險：模型為填滿欄位虛構內容；或晚期 Task 的 gap 尚未全部關閉就結束訪談，已回答的新證據沒有重新形成候選。

方向：允許空白與 terminal reason；將 O／P／K／S 方法按需載入，避免每回合塞入完整 OPKS prompt；追蹤每個工作假說與各軸的分析／gap／receipt 狀態；以長回合 pilot 比較「現行獨立 OPKS operation」與「同一顧問按需 Skills」的品質、遺漏、成本與尾端衰減。

### 8.5 Reference 錨定

風險：公版文字專業完整，使 AI 與員工把「可能有」誤認成「本人有」；若每個檢索命中都成為持久狀態，還會造成重複詢問、來源噪音與假權威。

方向：blind-first；Reference 分 lane；先顯示差異與中立問題；只持久化有產品影響的 challenge receipt；以語意主張與工作範圍去重；公版來源永遠不自動提高事實權威。

### 8.6 假進度與假完成

風險：以 Task 數、固定問題數或 0–100% 宣稱完成；新線索出現時進度倒退。

方向：使用「目前已知」的 coverage、sufficiency、具體 gap、待決 Proposal 與停止理由；完成是可解釋的條件組合，不是填滿率。

### 8.7 內部 Agent loop 膨脹

風險：因框架可用或希望回答更完整，讓每輪固定經過 planner、extractor、critic、OPKS coder 與多個 specialist，導致延遲、成本與錯誤路徑快速增加；員工仍只看到一個答案，反而難以理解為何卡住或失敗。

方向：預設單次主要顧問 inference；只因必要 context、工具結果或邊界明確的專業 contract 增加步驟；由 application 強制 no-progress、重複 request、步數、token、時間、成本與 authority 終止條件。每輪保存實際 topology 與 usage，成品完成後再由長訪談 eval 判斷哪些額外步驟值得保留。

## 9. 下一輪待討論

外部模型資料邊界與「框架承接工程機制、Caliburn 保留產品語意」的責任分界已確認。按產品優先、元件後置的順序，下一輪建議討論：

> 在不改變本文顧問流程的前提下，LangGraph／LangChain／Agent Skills／既有 Pydantic＋SQLAlchemy＋PostgreSQL／W3C anchor 與 provenance 標準應如何組成最小而完整的目標架構？

下一步先確認元件邊界與資料流，再選最小 capability spike；仍不得直接據研究稿實作。LangGraph 是目前外層 runtime 的推薦候選，不是 Accepted 決策；必須與現有 durable turn／Journal 及 PostgreSQL transaction 做 conformance，證明沒有第二份權威、重複副作用或新的 durability 缺口後才可採用。

## 10. 本稿依據

Repo 研究：

- [`AI 專業職務分析顧問流程：最終反方審查與品質設計`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md)
- [`AI 專業職務分析顧問 R1：Task Discovery 深入研究`](2026-07-25-professional-consultant-r1-task-discovery-deep-research.md)
- [`Task 邊界、merge/split 與同一性判準研究`](2026-07-28-task-boundary-merge-split-and-identity-research.md)
- [`專業顧問第一個最小完整迴圈`](2026-07-30-professional-consultant-minimal-complete-loop-research.md)
- [`iCAP 逐欄位標準`](2026-07-13-ai-redesign-raw-icap-field-standards.md)
- [`OPKS 設計裁決研究`](2026-08-01-opks-design-decisions-research.md)
- [`OPKS 漸進式蒐集研究`](2026-08-04-opks-progressive-elicitation-research.md)
- [`OPKS 缺口與再分析的封鎖關係`](2026-08-06-opks-gap-reanalysis-blocking-research.md)

Stakeholder 草稿（非權威，只作需求來源）：

- `C:\Users\chenb\Downloads\職務分析_AI_階段化狀態機需求稿 _ AFFiNE.html`（2026-08-12 完整讀取並依 §5.4 裁決）

官方／第一手來源：

- [Anthropic — Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)
- [Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Scaling Managed Agents: Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents)
- [Anthropic — How we contain Claude across our consumer products](https://www.anthropic.com/engineering/how-we-contain-claude)
- [Anthropic Docs — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic Docs — Tool runner（自動 loop 與 custom HITL 邊界）](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Anthropic Docs — Managed Agents permission policies](https://platform.claude.com/docs/en/managed-agents/permission-policies)
- [Anthropic Docs — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic — Contextual Retrieval](https://www.anthropic.com/engineering/contextual-retrieval)
- [Anthropic — Equipping agents for the real world with Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills)
- [Anthropic Privacy Center — Commercial API model-training policy](https://privacy.claude.com/en/articles/7996885-how-do-you-use-personal-data-in-model-training)
- [Anthropic Privacy Center — Commercial API data retention](https://privacy.claude.com/en/articles/7996866-how-long-do-you-store-my-organization-s-data)
- [OpenAI Docs — Model guidance（lean prompts、relevant tools、approval boundaries）](https://developers.openai.com/api/docs/guides/latest-model)
- [OpenAI Docs — Running agents（application turn、inner loop、session、resume）](https://developers.openai.com/api/docs/guides/agents/running-agents)
- [OpenAI Docs — Orchestration and handoffs（manager ownership、bounded specialists）](https://developers.openai.com/api/docs/guides/agents/orchestration)
- [OpenAI Cookbook — Context Engineering for Personalization（structured state、relevant slices、memory precedence）](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization/)
- [OpenAI Docs — ChatKit widgets](https://developers.openai.com/api/docs/guides/chatkit-widgets)
- [OpenAI Docs — ChatKit actions](https://developers.openai.com/api/docs/guides/chatkit-actions)
- [OpenAI Docs — Results and state](https://developers.openai.com/api/docs/guides/agents/results)
- [OpenAI Docs — Guardrails and human review](https://developers.openai.com/api/docs/guides/agents/guardrails-approvals)
- [OpenAI Docs — Structured model outputs](https://developers.openai.com/api/docs/guides/structured-outputs)
- [OpenAI Docs — Function calling](https://developers.openai.com/api/docs/guides/function-calling)
- [OpenAI Docs — Conversation state](https://developers.openai.com/api/docs/guides/conversation-state)
- [OpenAI Docs — Compaction](https://developers.openai.com/api/docs/guides/compaction)
- [OpenAI Docs — Counting tokens](https://developers.openai.com/api/docs/guides/token-counting)
- [OpenAI Docs — Prompt caching](https://developers.openai.com/api/docs/guides/prompt-caching)
- [OpenAI Docs — Data controls in the OpenAI platform](https://developers.openai.com/api/docs/guides/your-data#default-usage-policies-by-endpoint)
- [OpenAI Docs — File Search（citation、結果顯式 include、metadata filter）](https://developers.openai.com/api/docs/guides/tools-file-search)
- [OpenAI Docs — Skills](https://developers.openai.com/api/docs/guides/tools-skills)
- [OpenAI Docs — Tool search](https://developers.openai.com/api/docs/guides/tools-tool-search)
- [Google — Why we built ADK 2.0](https://developers.googleblog.com/en/why-we-built-adk-20/)
- [Google — Build long-running AI agents that pause, resume, and never lose context with ADK](https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk/)
- [Google — Developer's Guide to Building ADK Agents with Skills](https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/)
- [Google — Introducing A2UI](https://developers.googleblog.com/en/introducing-a2ui-an-open-project-for-agent-driven-interfaces/)
- [Google — A2UI v0.9](https://developers.googleblog.com/en/a2ui-v0-9-generative-ui/)
- [Google PAIR v2 — Mental Models](https://pair.withgoogle.com/guidebook-v2/chapter/mental-models/)
- [Google PAIR v2 — Explainability + Trust](https://pair.withgoogle.com/guidebook-v2/chapter/explainability-trust/)
- [Google PAIR v2 — Feedback + Control](https://pair.withgoogle.com/guidebook-v2/chapter/feedback-controls/)
- [Google ADK — Session](https://adk.dev/sessions/session/)
- [Google ADK — Human input for graph workflows](https://adk.dev/graphs/human-input/)
- [Google ADK — State](https://adk.dev/sessions/state/)
- [Google ADK — Rewind sessions](https://adk.dev/sessions/session/rewind/)
- [Google ADK — Events](https://adk.dev/events/)
- [Google Cloud — Gemini Enterprise Agent Platform（Sessions、Memory Bank、evaluation、observability）](https://docs.cloud.google.com/gemini-enterprise-agent-platform/scale)
- [Google Cloud — Choose your agentic AI architecture components（state、memory、progressive disclosure）](https://docs.cloud.google.com/architecture/choose-agentic-ai-architecture-components)
- [Google Cloud — Choose a design pattern for your agentic AI system](https://docs.cloud.google.com/architecture/choose-design-pattern-agentic-ai-system?hl=en)
- [Google AI for Developers — Zero data retention in the Gemini Developer API](https://ai.google.dev/gemini-api/docs/zdr)
- [Google Research — Sufficient Context: A New Lens on RAG Systems](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)
- [LangGraph — Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph — Workflows and agents（predetermined workflow 與 dynamic loop）](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph — Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [LangGraph frontend — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop)
- [LangChain — Context engineering in agents](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [PydanticAI — Deferred tools and human-in-the-loop approval](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [OpenRouter — Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr)
- [OpenRouter — Provider routing and data-policy controls](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging)
- [Microsoft — Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Microsoft — Agent Framework workflows human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- [Microsoft — Agent Framework AG-UI integration](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/ui/ag-ui/)
- [Microsoft Research — From Local to Global: A Graph RAG Approach](https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/)
- [Microsoft Research — DRIFT Search: Combining global and local search](https://www.microsoft.com/en-us/research/blog/introducing-drift-search-combining-global-and-local-search-methods-to-improve-quality-and-efficiency/)
- [Microsoft Research — GraphRAG dynamic community selection](https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/)
- [Microsoft HAX — Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/)
- [Microsoft HAX — Time services based on context](https://www.microsoft.com/en-us/haxtoolkit/guideline/time-services-based-on-context/)
- [Microsoft HAX — Support efficient correction](https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/)
- [Microsoft HAX — Remember recent interactions](https://www.microsoft.com/en-us/haxtoolkit/guideline/remember-recent-interactions/)
- [Microsoft HAX — Make clear why the system did what it did](https://www.microsoft.com/en-us/haxtoolkit/guideline/make-clear-why-the-system-did-what-it-did/)
- [Microsoft HAX — Convey the consequences of user actions](https://www.microsoft.com/en-us/haxtoolkit/guideline/convey-the-consequences-of-user-actions/)
- [Microsoft — Adaptive Cards for agent design](https://learn.microsoft.com/en-us/agents/design-guidelines/adaptive-cards-for-agent-design)
- [Apple HIG — Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- [U.S. OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)
- [U.S. OPM — Job analysis evidence and methodology FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/when-conducting-a-job-analysis-do-i-have-to-collect-ratings-eg-importance-required-at-entry-from-the-subject-matter-experts-sme-for-the-tasks-and-competencies/)
- [U.S. OPM — Six Steps to Conducting a Job Analysis for Multiple Grades](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/six-steps-to-conducting-a-job-analysis-for-multiple-grades/)
- [iCAP — 職能發展及應用推動要點（職能基準審查與更新）](https://icap.wda.gov.tw/Quality/quality_specification.aspx)
- [NIST — AI Risk Management Framework Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
