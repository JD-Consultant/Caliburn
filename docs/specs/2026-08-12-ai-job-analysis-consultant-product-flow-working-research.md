# AI 專業職務分析顧問：產品流程工作研究稿

- 日期：2026-08-12
- 狀態：Working Research；隨 owner 討論持續修訂
- 決策狀態：只記錄已確認的產品方向與待討論問題；不是 ADR，不授權 production 實作
- 優先順序：本稿先定義「產品如何像專業顧問工作」；元件、Context Engine、RAG 技術與 framework 選型後置
- 外部資料查核：Context Engine 小節依截至 2026-08-12 可取得的官方／第一手資料整理；大廠做法是設計證據，不是免評測的產品決策
- 相關研究：[`階段式 AI 職務分析顧問 runtime/framework 研究`](2026-08-12-staged-ai-consultant-runtime-framework-research.md)只能在本產品流程核准後評估，不得反向用框架能力定義顧問流程

## 0. 這份工作稿怎麼使用

這份文件用來避免長期討論遺失已確認的大方向。每次只把已對齊的內容寫成明確規則；尚未討論或仍可能翻案的內容列在「待討論」，不假裝已定案。

### 0.1 研究來源與決策追溯規則

文末參考資料只作來源總索引，不能取代決策附近的研究紀錄。從 2026-08-13 起，每項由外部研究支持的產品方向應在相鄰段落保留：

1. **裁決與狀態**：是研究候選、owner 已確認、未決參數或已被後續決策取代，並記錄日期；
2. **直接來源**：優先連到官方文件、原始研究、標準或本 repo 權威研究，不只寫廠商名稱或二手結論；
3. **來源實際支持的內容**：區分來源明說、來源實驗結果與 Caliburn 的領域推論；
4. **可轉移限制**：說明原資料的任務、語言、使用者、資料集、評量方式與本產品有何不同，不能把「大廠採用」寫成已驗證本產品效果；
5. **產品理由與取捨**：記錄為何適用到 Caliburn、保留哪些 authority／安全邊界，以及不採用方案的主要理由；
6. **修訂關係**：後續若反證或翻案，追加新結論與取代關係；保留舊理由供審核，不用無痕改寫讓歷史消失。
7. **每題收尾與進度**：每個討論題必須留下「問題、研究證據、可選方案、採用／不採用理由、owner 狀態、未決參數、下一題」；進度只標示「已收斂／當前／待研究／延後」，不以未經驗證的百分比假裝精確。

同一來源可在文末只列一次，但使用它作裁決的段落必須直接連結或明確指向來源項目。Stakeholder 草稿、owner 偏好、現行 code／ADR、通用工程建議與領域實證必須分開標示；它們提供的權威種類不同。連結內容可能更新時，紀錄最近查核日期與當時採用的具體主張；進入 ADR／實作計畫前應重新開啟關鍵來源查核，而不是只相信本稿摘要。

目前先回答四個問題：

1. 這個 LLM 專業職務說明書顧問，從開始到匯出大致怎麼工作？
2. 員工如何知道 AI 現在為何發問、訪談進度到哪裡？
3. Task、Duty、OPKS 與 Reference 在流程中如何互相影響？
4. 長訪談中哪些內容必須完整保存、哪些每輪必帶、哪些應按需取用？

下列內容不在產品方向段落預先鎖定，而是依 §9 的關卡逐步收斂：

- 要不要採 LangGraph、LangChain、PydanticAI 或其他框架；
- Context Engine、memory、RAG、tool、skill 的最終 schema；
- API、資料表、畫面與 migration；
- 具體模型、價格、provider 選型與數值參數調優（但 §7.20 已定義控制權與追溯契約）；
- 實作切片與工期；只有目標設計經 owner 核准後才可撰寫施工計畫或修改 production code。

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
- 目前推薦依責任分層組合主流框架，而不是要求一套框架全包；遷移邊界依 §2.15 採 AI 顧問子系統受限 Big-bang，但不擴張成整個 Caliburn 的 event-sourcing／agent-platform 重寫。

因此產品流程仍是本文定義的顧問流程；framework 只能忠實承接它，不能因框架已有 `memory`、`state`、`approval` 或 `agent` 類別，就重新定義員工回合、資料權威、進度或正式修改權。

這裡的「保留」指**保留目的、專業方法、產品語意與可驗證的不變量，不是保護目前自寫的 class、module、schema、資料表或 orchestration code**。`Focus`、`Work Model`、`Current JD`、`gap／agenda`、`Proposal` 與 `Context Engine` 是目前用來描述產品責任的名稱；若成熟框架能以更完整、可維護的機制承接同一責任，原則上優先 `Replace` 或 `Wrap`，只為 Caliburn 特有的職務分析與 authority 差異保留自寫程式。後續框架研究必須逐項回答「承接哪項產品責任、框架提供什麼、Caliburn 還要補什麼、能刪除哪些舊碼、如何證明語意不變」，不能只因框架有同名功能就直接採用。

### 2.12 一個員工回合採三層持久化，不把 network call 偽裝成資料庫交易（2026-08-13 審核後確認）

本節把「員工原話先保存、衍生結果整包提交」說得更精確。它不是只有兩個模糊的 save，也不是把 provider call 包在長時間 PostgreSQL transaction 裡：

1. **Source acceptance transaction**：先以 client／application 提供的穩定 `input_event_id` 保存員工原話、speaker、document scope、canonical payload hash 與 processing status，再回報「回答已保存」。相同 ID＋相同 hash 回既有結果；相同 ID＋不同 hash 是 idempotency conflict。
2. **Execution durability**：transaction 外執行 Context、Skill、tool 與 model；每個不可免費重做的重要結果以 run／attempt checkpoint 或 immutable artifact 保存，例如 resolved execution snapshot、ContextManifest、tool result、provider result、usage、parse／verification report。這些是恢復與診斷依據，不是 Work Model、Proposal 或 Current JD。
3. **Semantic commit transaction**：deterministic application layer 把通過檢查的候選編成一份 `VerifiedCommitPlan`；再於單一 PostgreSQL transaction 中重讀 document、驗 generation／read-set，並一起寫入 Work Model delta、agenda／progress、durable Proposal、可見 consultant turn 與 idempotent result receipt。這批業務變更要嘛全部可見，要嘛全部 rollback；Current JD 仍完全不動。
4. **Independent employee decision command**：員工日後接受、修改、退回、拒絕或延後 Proposal，是另一個有自己 idempotency／stale check 的 command；只有它能經 authority seam 改變 Current JD。正常 Proposal review 不依賴 consultant graph checkpoint 存活。

因此「原子」描述的是**已驗證業務 CommitPlan 的資料庫可見性**，不是要求整個 LLM run 只有一次 commit。provider 已成功但 process 在 semantic commit 前崩潰時，恢復流程應讀取已保存的 provider／verification artifact；若 authority snapshot 仍相符，可以繼續 verify／commit，不應自動再付一次模型費。若 snapshot 已 stale，舊結果可保留作執行證據，但不得硬套到新 state，必須依 operation policy 重新組裝或重跑。

模型輸出的逐項驗證與資料庫原子性也不是同一題。建議 verifier 產生 granular verdict 與 dependency：

- envelope、document／speaker／source identity、authority boundary、read-set、跨項不變量、next question／visible response 所依賴的 finding 發生錯誤時，視為 fatal，整份 semantic commit 不成立；
- 只有不被其他結果引用、也不影響員工可見回覆的附帶候選，才可被明確 drop／quarantine 並留下 reason code，其餘有效項目再組成 CommitPlan；
- 第一版若尚未有穩定 dependency contract，寧可沿用整輪 fail-closed，不以猜測判斷「這個錯誤大概不重要」。先保存 granular report，之後有真實 failure evidence 再放寬，不必改寫權威模型。

UI 只可在 semantic commit 成功後把 consultant turn 當正式本輪回覆；commit 前可以顯示「已保存／分析中／驗證中」等 processing status，但不可先把尚未驗證的串流文字當成已成立的分析。失敗時顯示「原話已保存、分析尚未完成」與可重試狀態，而不是要求員工重新輸入。

這項分層符合多個官方來源的共同模式，但外部來源不替 Caliburn 決定 domain 語意：PostgreSQL 將 transaction 定義為多步驟 all-or-nothing；AWS 的 idempotent API 指引要求 caller-provided request ID，並指出去重紀錄、mutation 與結果應在同一 ACID operation 中一致提交；LangGraph 建議把 API call 放進可 checkpoint、可重播且 idempotent 的 task，保存已完成 task result 以免 resume 時重算；OpenAI Agents SDK 的 output guardrail 也明確區分「已完成的 tool result 可持久化」與「被拒絕的 final output 不進 session」；DBOS datasource 則證明 workflow checkpoint 與 application transaction 可以在同一資料庫交易中原子記錄，但它是替代 runtime 候選，不代表應與 LangGraph 疊兩套 durable engine。[PostgreSQL — Transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)、[AWS Builders' Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)、[LangGraph — Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)、[OpenAI Agents SDK — Guardrails](https://openai.github.io/openai-agents-python/guardrails/)、[DBOS — Transactions and Datasources](https://docs.dbos.dev/python/tutorials/transaction-tutorial)

### 2.13 產品產出與不可宣稱的範圍（2026-08-13 已確認）

Owner 確認第一版產品的產出定位為：

> Caliburn 透過專業職務分析方法，由 AI 主導訪談、交叉檢查並持續修正，再由員工逐項審核，形成反映該員工目前實際職務的客製化職務說明書。

它不是聊天摘要或填表結果，但單一員工訪談與員工對文件的 authority 也不能自動升格為其他種類的效度。因此產品不得宣稱該文件：

- 已代表公司對此職位的正式定義；
- 已由主管、HR 或外部職務分析專家核准；
- 可直接作為招募甄選、績效考核、薪酬或法規判定標準；
- 已證明該員工具備文件列出的所有能力；
- 已通過 iCAP、法規或其他外部效度審查。

未來若組織要正式採用，可把本產品成果送入另一個組織核准或效度程序；目前不因此加入主管帳號、HR workflow、多人核准或外部認證功能。這延續[`專業顧問流程最終反方審查`](2026-07-25-professional-job-analysis-consultant-process-final-red-team.md#12-成品能合理宣稱什麼)的聲明上限，避免「專業顧問」被誤讀成已完成組織或甄選效度驗證。

### 2.14 目標優先、成熟框架優先承接、遷移受控（2026-08-13 已確認）

本次是**升級現有產品**，不是保留舊碼的小修，也不是把既有職務分析研究一起推倒重來：

- 新產品目標以本文已確認的白話流程為準；現行 code 是遷移起點與安全證據，不是產品天花板；
- 優先保留已研究驗證的職務分析、Task boundary、Duty grouping、OPKS、Reference challenge 方法，以及來源追溯與員工 authority；
- 現有 Focus、Work Model、Current JD、gap、Proposal、Context、memory、operation、provider adapter 與 verifier 實作都可成為框架替代候選；
- 若成熟框架能完整承接同一目的、維護性更好且不建立第二份權威，優先移植、包裝或替換，不因「這是 domain 元件」就假設底層必須自寫；
- 目標流程不因現行系統暫時缺少 Duty hypothesis、Task reassignment、Duty Proposal、typed composite changeset 或按需 OPKS Skills 而縮小；
- 與 Accepted ADR 衝突的目標改變必須由 successor ADR 明確取代後才可施工，不能偷偷繞過，也不能反過來用舊 ADR 凍結已由 owner 確認的新產品方向。

進入 plan 前必須建立「目標能力／現況／框架候選／`Replace|Wrap|Retain`／仍需自寫語意／successor ADR／驗收情境」差距矩陣。這張矩陣以產品責任為列，不以舊 module 為列，避免框架研究退化成替舊系統逐檔換套件。

### 2.15 AI 顧問子系統採受限 Big-bang，一次切換但不重寫整個 Caliburn（2026-08-13 已確認）

2026-08-13 repo 稽核顯示，目標升級會同時改變 consultation runtime、Context／memory、Focus／agenda、Work Model、Duty、Proposal、OPKS Skills、durable run 與對應 API／UI。若逐一包裝舊 Task Analysis／OPKS child 元件，必須長期維護兩套狀態語意、轉接契約與一次性 adapter，橋接成本很可能高於直接建立新垂直切片。Owner 確認可在隔離 worktree 完成新系統後再切換，因此採：

1. 在隔離 worktree 內建立新的完整 AI 顧問垂直切片；中間 commit 不需要把半套新流程接到主工作面；
2. 將 AI 顧問子系統視為一次重寫與一次切換的邊界，不替舊 Task Analysis／OPKS child 逐元件建立長期相容層；
3. 新 runtime 直接依本文產品語意、成熟框架與新的統一 contract 設計；完成後一次切換 API／Web，並刪除被取代的舊 AI runtime；
4. 不做 production 雙軌、雙寫或永久 façade；只有 Current JD、文件、匯出、RAG 等真正穩定的外部 seam 才可成為新舊交界；
5. PostgreSQL、SQLAlchemy、Pydantic、文件庫、Current JD 員工編輯與 authority 原則、deterministic export／XLSX、隔離 RAG 資產優先保留或深化，但若後續研究證明具體實作不再合適，仍以產品語意與驗收為準，不因已存在而免審；
6. iCAP Reference／RAG 納入同一次最終切換的完成條件，但在 worktree 內的實作順序是先完成核心顧問與 framework-neutral Reference contract，再接現有隔離 RAG bounded context；它是最後一個垂直能力，不先反向定義顧問核心；
7. Owner 於 2026-08-13 確認目前沒有必須保留的真實 JD 或訪談資料，因此新系統採 fresh-schema hard cut：不遷移舊 Work Model、agenda、Proposal、checkpoint、turn 或 Current JD，不寫 compatibility converter，也不雙寫；開發資料庫依新 migration head 重建；
8. 正式 context／model 品質 eval 仍依 §7.14 後置；切換前至少通過 authority／來源／文件隔離等 deterministic safety，以及本文 §3.11 的端到端人工情境。

這不是整個 repo 的無邊界 Big-bang。Microsoft 的 Strangler Fig 指引也明示，漸進 façade 是有暫時基礎設施與跨系統依賴成本的 transitional architecture，對小型系統或需要快速淘汰原解法時可能不適用；AWS 則把它定位為降低大型 monolith 改寫風險的方法。Caliburn 是本機單一操作者產品、已有清楚 bounded context、可使用隔離 worktree，且本次主要變更集中在一個高度耦合的 AI 顧問子系統，因此採「子系統 Big-bang、repo 邊界保留」是依本地條件作出的選擇，不宣稱是所有系統的通用最佳實務。[Microsoft — Strangler Fig pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)、[AWS — The strangler fig pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-aspnet-web-services/fig-pattern.html)

為防止框架與舊系統帶偏，新系統的**目標設計權威順序**是：

1. 本文經 owner 確認的產品北極星、白話流程與產品語意；
2. 已研究驗證的職務分析、Task、Duty、OPKS 與 iCAP 方法；
3. 後續核准的新目標架構與 successor ADR；
4. 舊 ADR 中仍未被取代的 authority、安全與資料不變量；
5. 現行 code／tests，只作已踩失敗、可保留 seam、安全網與刪除範圍的證據；
6. 更舊歷史文件，只作追溯。

現行 Accepted ADR 在 successor ADR 核准前仍是 production authority；上述順序描述的是**新目標如何形成**，不授權研究稿直接越過 ADR 修改 production。現有測試也要依產品語意分類：保留 authority、來源、文件隔離與 deterministic export 類安全網；以新流程重寫 Task／Duty／OPKS 與端到端情境；淘汰只鎖定舊 prompt、wire schema、operation 拆法、OPKS child、舊 Work Model／Proposal 形狀或固定呼叫次數的拓撲測試。新系統不以舊內部 API／class／schema 的行為相容為完成條件。

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

#### 3.1.1 第一次訪談前提供簡短導航（2026-08-13 owner 已確認）

**問題**：目前流程會在每輪顯示焦點、理由與進度，但 §3.11 的正常情境一開始就直接請員工盤點工作。員工可能要談過數輪才知道 AI 會先做什麼、過程中為何重整 Task／Duty／OPKS，以及自己何時需要決定正式變更。這不是缺少內部 workflow state，而是可能缺少一個開始時的共同心理模型。

**直接來源與實際支持**（最近查核：2026-08-13）：

- [Anthropic — Introducing Anthropic Interviewer](https://www.anthropic.com/research/anthropic-interviewer)將方法分成 planning、adaptive interviewing 與 analysis；其 interview rubric 維持共同研究問題，但允許個別訪談的變化與旁支。這支持「先有目標與涵蓋責任、路徑仍可動態調整」，不支持固定 wizard。
- [U.S. OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)把 Task、所需 competency 與兩者 linkage 視為 job analysis 的核心。這支持顧問一開始可白話說明會逐步理解工作與必要能力關係，但 OPM 沒有規定 AI 訪談 UI 或提問順序。
- [Google PAIR — Feedback + Control](https://pair.withgoogle.com/guidebook-v2/chapter/feedback-controls/)建議清楚傳達使用者投入的價值與影響時間、保留調整控制，並把追蹤進度列為可提供個人效用的方式。這支持在員工投入訪談前說明「回答會如何變成可檢查成果」，以及之後讓員工看見進度與修正效果。
- [OpenAI 官方 Model guidance](https://developers.openai.com/api/docs/guides/latest-model)要求提供 domain context、硬限制、approval boundaries 與 success criteria。這直接支持主要顧問 runtime 必須取得這些控制資訊；把其中與員工有關的部分轉成啟程說明，是 Caliburn 的 UX 推論，不是 OpenAI 明定的畫面規格。

**可轉移限制**：Anthropic 的公開案例是大規模質性研究訪談，研究計畫由研究者審閱，且不是繁中單一員工的 iCAP 職務分析；其 10–15 分鐘訪談長度不能轉用成本產品時限。OPM 是職務分析方法權威，不是生成式 AI 互動研究。Google PAIR 與 OpenAI 是通用 AI UX／模型控制指引。四者共同支持的是「目標明確、路徑可適應、員工知道控制與成果如何變化」，尚未直接證明任何啟程文案能改善 Caliburn 的完成率或品質。

**與既有設計的關係**：若採用，不新增 `InterviewPlan`、第二份 agenda 或固定問題表。內容由版本化顧問方法、當前文件狀態與既有 focus／agenda／progress 投影組成；之後仍由 §3.3 的動態焦點與 §4 的可解釋進度更新。它只建立員工的預期，不限制顧問只能依開場順序行動。

**研究選項與裁決**：

1. **不另外說明**：直接開始角色定位與工作盤點；畫面較短，但員工要從後續互動自行推測流程。
2. **一次性的簡短導航（採用）**：第一次開始時用 3–4 句說明「先大致盤點工作，再一次深入一個焦點；新線索會先記住，Task／Duty／OPKS 會隨證據調整；正式修改都要你接受；你可隨時暫停，系統會顯示目前已知範圍、缺口與下一步」。隨後立刻開始第一個自然問題，不要求員工核准一份計畫。
3. **先產生並核准完整訪談計畫**：員工可預覽所有預定主題，但容易形成固定階段與假分母，增加開場負擔，也會讓後續動態重整看起來像偏離計畫；目前不建議。

**產品裁決**：owner 於 2026-08-13 確認採方案 2。它只建立員工對訪談方式、動態重整、核准權與可恢復性的預期；不建立完整訪談計畫、不形成固定問題分母，也不要求開場核准。實作文案與視覺形式留到目標架構／Web 體驗關卡，不在此鎖定。

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

### 3.3 選擇本輪焦點與處理新線索（2026-08-13 研究後確認）

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

- **吸收到目前焦點**：與目前工作直接相關、能回答當前問題或補充其 Task／Duty／OPKS 的資訊，直接納入當前分析；換用相關 Skill 不等於換題。
- **停放到可見議程**：獨立且不影響當前判斷的新 Task、Duty、OPKS 或未分類線索，保存到待處理清單；顧問用一句話回報已記錄與稍後處理，不立刻展開第二個主要問題。
- **修正或切換焦點**：只有新資訊使當前問題前提失效、改變本人／他人責任、會實質改變 Task 邊界、形成重大來源矛盾，或延後會讓後續分析建立在錯誤理解上時，AI 才說明原因、暫停並詢問一個必要問題。
- **員工主動改道**：員工明確要求換題、返回或暫停時立即尊重，不要求先完成 AI 原定問題；尚未處理的焦點仍保留。
- **可恢復中斷**：每次中斷都保存返回點，之後能說明原焦點談到哪裡、為何中斷、還差什麼。

「新線索看起來重要」本身不足以立即打斷。判斷標準是它是否**現在就阻塞或推翻當前合法分析**，不是它最終可能有多高價值；高價值但不阻塞的線索先提高 agenda 優先序，在當前焦點暫時收束後再選取。

研究依據與轉用（最近查核：2026-08-13）：

- [OpenAI 官方 Model guidance](https://developers.openai.com/api/docs/guides/latest-model)要求提供目前目標、相關 context、限制與核准邊界，並在重要歧義時提問；同時應讓安全且在 scope 內的工作持續，不因重複 approval 指令造成不必要停頓。這支持「一般線索不中斷，重要歧義才停」。
- [Anthropic — Trustworthy agents in practice（2026-04-09）](https://www.anthropic.com/research/trustworthy-agents)明確把過度詢問與一律自行假設都列為問題：可自行解決的缺口繼續處理，只有使用者才能決定的偏好、意圖或重大不確定才交還使用者。這支持分級處理，而不是每個新線索都切換。
- [Microsoft HAX — Time services based on context](https://www.microsoft.com/en-us/haxtoolkit/guideline/time-services-based-on-context/)要求依使用者當前 task／attention 決定何時打斷；[Support efficient correction](https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/)與[Convey the consequences of user actions](https://www.microsoft.com/en-us/haxtoolkit/guideline/convey-the-consequences-of-user-actions/)則支持讓員工容易修正，並立即回饋「已保存、稍後會怎麼處理」，而不是靜默停放。
- [U.S. OPM — Assessment and Selection](https://www.opm.gov/policy-data-oversight/assessment-and-selection/)要求 job analysis 保存 Task、角色／責任、competency、資源與工作情境的 linkage，並由具有直接、最新工作經驗的 SME 提供資訊。這支持責任與 Task 邊界矛盾要向員工釐清，不能由 Reference 或模型猜測。

可轉移限制：OpenAI／Anthropic 資料是通用 agent 行為，Microsoft HAX 是跨產品人機互動指引，OPM 說明職務分析證據與 SME，但沒有規定 LLM 訪談的 topic-switch 演算法；目前也沒有公開研究直接比較繁中單一員工職務訪談的三種切換策略。因此上述三級模型是將共同原則套入 Caliburn「一個主要焦點、完整吸收回答、員工 authority、可恢復 agenda」後的產品裁決，不得宣稱已由外部 benchmark 證明效果最佳。

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

### 3.7 小段落收束、重整與提案（2026-08-13 review bundle 粒度已確認）

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

Owner 於 2026-08-13 明確選擇**可編輯的 review bundle＋必要的原子子群組**，不採每個欄位各跳一張 Proposal，也不把整批變更綁成全收全退。`review bundle` 是員工看到的一次審核脈絡；底層 `typed changeset` 仍保存每項操作、目標、before／after、來源、相依關係與 stale/read-set。框架的一般 HITL／approval 只能承接呈現、暫停與回傳選擇，不能把這個 domain grouping 壓成單一布林核准。

- 員工先看到這組建議的共同理由、來源證據與整體影響；
- 可以獨立成立的文字、名稱或 OPKS 候選，允許逐項接受、修改或拒絕；
- 只有必須一起成立才不會破壞結構的操作，才組成不可拆的子決策，例如建立 Duty 並完成必要的 Task reassignment；
- 員工修改任一項後，系統重新檢查剩餘變更是否仍成立，不提交失去前提或留下無效 linkage 的內容；
- 分組依據是 domain dependency，不是由哪一個 Skill 產生，也不把整批不相關的變更綁成全收全退；
- 拒絕、修改與暫不處理都要留下可追溯裁決；若沒有新員工來源、實質工作邊界變化或其他會推翻原理由的新證據，AI 不得換個措辭重複提出同一變更。

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

#### 3.7.4 更正後的影響傳播範圍（研究候選；owner 待確認）

**問題**：既有裁決已決定最新有效員工更正優先、舊來源保留、Work Model 可修正而 Current JD 未核准前不變；但尚未明確選擇一則更正如何傳播。只改眼前欄位可能留下依賴舊說法的 Duty／OPKS／Proposal；每次整份文件重算則浪費成本，還可能讓無關且已確認的內容無故漂移。

**直接來源與實際支持**（最近查核：2026-08-13）：

- [OpenAI Cookbook — Context Engineering for Personalization](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization/)示範 local-first structured state、session／global notes、dedupe／conflict resolution 與明確 precedence，範例順序是 latest user input → session override → global default；它並指出 state-based memory 比鬆散 retrieval 更適合需要連續性、更新與衝突處理的工作。這支持「更正要進結構化目前狀態並有優先規則」，不直接定義 Caliburn 的 Task／Duty／OPKS 失效演算法。
- [Microsoft Research — LLMs Get Lost In Multi-Turn Conversation](https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/)在超過 20 萬段模擬對話與六類生成任務中觀察到，模型常過早採用前期假設並持續依賴，發生錯誤轉向後不容易恢復。這支持不能只把更正追加在長聊天末端、期待模型自行修復所有下游理解。
- [Microsoft HAX — Convey the consequences of user actions](https://www.microsoft.com/en-us/haxtoolkit/guideline/convey-the-consequences-of-user-actions/)要求立即更新或說明使用者動作將如何影響 AI 後續行為。這支持更正後回報「哪些理解已改、哪些分析會重算、正式 JD 是否仍未改」。
- [W3C PROV-O](https://www.w3.org/TR/prov-o/)提供 primary source、quotation、derivation、revision 與 invalidation 等來源關係，可作 lineage／修訂語彙參考；它支持保留前後版本與衍生關係，但不是職務分析資料模型或 incremental recomputation engine。
- [U.S. OPM — Job Analysis FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/when-conducting-a-job-analysis-do-i-have-to-collect-ratings-eg-importance-required-at-entry-from-the-subject-matter-experts-sme-for-the-tasks-and-competencies/)要求描述 work behavior、Task、work product、KSA 及彼此關係，且保留支持重要性的 evidence。這支持一則責任／工作行為更正可能跨 Task、Output、Indicator、K／S linkage 傳播，不能只作文字 patch。

**可轉移限制**：OpenAI Cookbook 是 travel concierge 的實作示例，不是 API 保證或職務分析研究；Microsoft 多輪研究使用模擬對話與生成任務，沒有比較本產品三種重算策略；HAX 是通用 UX；PROV-O 只定義 provenance 語彙；OPM 主要面向正式甄選職務分析。以下方案 3 是把共同原則套入 Caliburn 穩定 ID、evidence linkage、Work Model／Current JD 分離與 Proposal authority 後的產品設計，不得宣稱已由外部 benchmark 證明成本或品質最佳。

**候選方案**：

1. **只修員工指出的欄位**：最快，但可能保留依賴舊責任邊界的 Task、Duty、OPKS、gap、agenda 或 pending Proposal；不採用。
2. **每次更正都重建整份 Work Model**：最不容易漏掉遠端影響，但成本、延遲與無關內容漂移最高，也會讓員工難以理解為何一個小修正改動整份文件；不建議作預設。
3. **來源錨定＋依賴導向失效／重算（目前建議）**：更正先成為新的 durable employee source，明示 `supersedes／rebuts／qualifies` 哪項舊來源或理解；application 依 evidence／derivation／stable ID／read-set 找出受影響的 Work Model hypothesis、Task／Duty／OPKS linkage、gap、agenda 與 pending Proposal，先標示 stale／challenged，再只對受影響範圍做 deterministic 對帳與必要語意重分析。無關且依據未變的內容保持原 revision。若重大更正的影響無法安全界定，才升級成較廣的 scope／document reconciliation，不能假裝局部修補已完整。

方案 3 仍不讓更正直接改 Current JD：若正式內容受影響，產生可編輯 Proposal／撤回既有 Proposal，交員工決定。介面先立即確認更正已保存，再顯示「目前理解改了什麼、哪些工作範圍正在重新檢查、哪些未受影響、Current JD 是否仍未改變」；branch-blocking 只作用於依賴舊前提的分析，不封鎖整份文件。

**待 owner 裁決**：是否採方案 3；具體 dependency graph、失效 reason code、reconciliation operation 與框架映射留到能力地圖／目標架構關卡。

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

1. **先知道怎麼進行，再建立工作地圖。** AI 先用 3–4 句白話說明會大致盤點工作、一次深入一個焦點、保存旁支線索、隨證據調整 Task／Duty／OPKS，且正式修改都由員工決定；不要求核准固定訪談計畫。接著請員工用自己的話說明一個月內主要工作，不要求 JD 用語。員工提到請購下單、供應商交期、缺料協調與偶爾整理庫存報表後，AI 顯示「目前已知四個工作範圍」，並說明先深入請購到下單的原因。
2. **專注但不漏線索。** 員工在下單故事中順帶提到新供應商評估與替代料；AI 把兩者顯示為稍後處理線索，仍用一個主要問題釐清下單責任，不立即換題。
3. **先理解，後提案。** AI 經數輪釐清主管核准邊界、採購單內容與供應商回覆，準備切換焦點前先用校準卡說明目前理解；員工可直接修正「交期只是追蹤，不是我決定」。修正先更新來源與 Work Model，證據足夠後才提出 Task、Output 與 Indicator 候選；第一句補充不會立即跳正式核准卡。
4. **員工保留 authority。** 員工指出「不是每次都要比價」，AI 修正 Task 後再讓員工接受。若目前只有一個 Task，可以先不建立 Duty。
5. **重大責任先澄清。** 訪談缺料處理時，員工說「決定哪些工單先拿到料」。因這可能改變正式權責，AI 暫停原焦點，確認員工只是提出建議、最後由生產主管決定，再回到原返回點。
6. **結構隨證據演化。** 當已有下單、缺料協調、供應商績效三項 Task，AI 可提出兩個 Duty 與 Task reassignment 的結構變更組；員工能修改 Duty 名稱。可獨立成立的 K／S 候選仍可逐項決定，不因接受 Duty 就被迫全收。
7. **Reference 只做補漏。** AI 在已有員工工作模型後，以公版資料詢問「供應商稽核是否為正式責任」。員工回答由品保負責後，系統記錄 no-match，不建立假的 Task。
8. **進度可解釋。** 畫面顯示目前焦點、為何現在處理、已足夠／訪談中／尚未深入／待決 Proposal／OPKS gap／已確認不屬於本人與稍後線索，而不是顯示假精確百分比。
9. **完成仍由員工決定。** AI 說明為何目前已足夠、仍缺什麼、繼續最可能改善哪裡。員工可以繼續、暫停或看過缺口後強制匯出；系統不補造答案、不偷收 Proposal，也不隱藏未歸類 Task。
10. **失敗不會吃掉回答或製造半套結果。** 員工送出後先看到「回答已保存」。短暫錯誤由同一 run 受限重試；若仍失敗，畫面說明 AI 尚未完成分析、Work Model／Proposal／Current JD 未改變，並提供重試、修正／取代與稍後返回。處理完成或被員工取代前，只暫停同一文件的新 AI 訪談回答；查看資料、既有 Proposal、直接編輯、匯出與離開仍可使用。

此情境的驗收效果是：AI 主動帶路，員工不用理解分析方法；每輪知道正在談什麼與為什麼；旁支線索不遺失；正式內容只在有意義檢查點由員工決定。

### 3.12 AI 中斷與失敗時的員工體驗（2026-08-13 owner 已確認）

**問題**：§2.7、§2.12 與 §7.16 已確認「員工原話先保存、執行可恢復、業務結果整批提交」，但還需要把 timeout、斷線、provider／schema／verifier 失敗轉成員工看得懂的流程。尤其要決定：短暫失敗是否自動重試、重試用盡後員工能做什麼，以及能否越過一則尚未分析的回答繼續產生新訪談回合。

**直接來源與實際支持**（最近查核：2026-08-13）：

- [OpenAI 官方 Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)把一個 SDK run 視為一個 application-level turn，建議持久會話使用 application-controlled session；串流要完成後才算 settled，中止的同一回合應從保存的 state 恢復，而不是建立新的使用者回合。它也要求區分 runtime／validation failure 與預期的人工作業暫停。這支持「同一回答恢復同一 run、未完成不能偽裝成成功回覆」。
- [AWS Builders' Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)說明 timeout 後無法知道操作是否已完成，盲目重試可能造成重複副作用；可自動重試的前提是穩定 caller-provided request ID、idempotent contract 與一致的結果語意。這直接支持沿用同一 `input_event_id／operation_id`，不把 retry 當新來源。
- [Microsoft HAX — Support efficient correction](https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/)要求 AI 出錯時讓使用者容易 edit、refine 或 recover。這支持失敗狀態必須有清楚的重試／修正／稍後返回入口，而不是只顯示技術錯誤或要求重打全文。
- [Google — Build long-running AI agents that pause, resume, and never lose context with ADK](https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk/)主張長流程使用顯式 durable state，與原始聊天歷史分離，才能跨重啟與等待恢復。這支持本地保存明確 run／processing state，不支持把 Google 範例的固定 onboarding state machine 複製成 Caliburn 的訪談階段。

**可轉移限制**：OpenAI、AWS 與 Google 資料主要證明 runtime／distributed-system 恢復形狀；Microsoft HAX 是通用人機互動指引。沒有來源直接研究繁中職務訪談中「前一則回答分析失敗時，是否允許繼續送出後續回答」。下列順序約束是依 Caliburn 必須全域吸收每則回答、後續問題依賴最新 Work Model、且不可產生半套 Proposal 的產品推論，不冒充大廠 UX 標準。

**研究選項與裁決**：

1. **只在背景持續自動重試**：員工一直看到分析中，直到成功。操作最少，但 provider 長時間故障時沒有清楚停止點，可能累積成本，也無法讓員工修正造成 validation failure 的輸入。
2. **短暫錯誤受限自動重試，之後轉成可恢復待處理（採用）**：送出後先回報「回答已保存」；網路、rate limit 等明確 transient failure 在同一 run／attempt policy 內短暫自動重試。成功才出現正式顧問回覆。用盡上限後顯示「原話已保存、AI 尚未完成分析、正式 JD 未改變」，提供「重試分析」「修正／取代這則回答」「離開並稍後回來」。重整頁面或重啟程式仍回到同一狀態；若結果其實已提交，依 result receipt 顯示既有成功結果，不重打模型。
3. **允許後續回答越過失敗項目排隊**：訪談看似不中斷，但後面的顧問問題與分析可能沒有讀到前一則來源，之後還要處理跨回合重排、stale Context 與相互衝突的 semantic commit；第一版不建議。

採方案 2 時，第一版預設不讓同一文件產生新的 **AI 訪談回答**，直到該 input 已完成 semantic commit，或員工以新的 correction／withdraw intent 明確取代它；否則系統無法保證下一題建立在完整來源上。這只暫停該文件的 AI 訪談鏈：員工仍可查看來源與進度、處理既有 Proposal、直接編輯 Current JD、匯出或離開。這些其他動作若改變 authority generation，恢復時依既定 stale／read-set 規則重新組裝，不把舊結果硬套到新狀態。

**產品裁決**：owner 於 2026-08-13 確認採方案 2，包含「未分析回答暫停同一文件的新 AI 訪談回答，但不封鎖其他既有功能」。技術 retry 次數、backoff、錯誤分類與 UI 文案留到 operation policy／目標架構關卡，不在產品流程層假裝已有最佳數值。

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

Owner 於 2026-08-13 確認：員工需要同時知道「大致談了多少」、「每一塊分析到哪裡」與「還有什麼等自己決定」。因此進度是三個並列視角，不可混成一個分數：

1. **工作 coverage**：目前辨識出哪些工作範圍，哪些已深入、正在談、尚未深入、被排除或只留下線索。這回答「我的工作大致談到哪裡」。
2. **分析深度**：對每個工作範圍分別顯示 Task 邊界、Duty 歸組與 O／P／K／S 的 sufficiency／gap。Task 已足以成案，不代表其 Duty 或 OPKS 已經足夠；OPKS 也不必等 Task 永久穩定後才開始。
3. **員工決策**：顯示待接受、待修改、待退回、待拒絕或已延後的 Proposal／結構調整。這回答「AI 已分析但還有哪些事情等我裁決」。

「工作範圍」是給員工導航與計算 coverage 的產品概念，可由 Current JD、可變 Work Model、來源與 workflow state 產生可重建投影；它不是把 Task、Duty、OPKS、gap 與 Proposal 混算的新權威實體，也不先要求新增第二份工作清單。UI 與模型的受限全域索引應由同一組 domain projection 語意產生，但可使用不同 representation。新線索使地圖擴張時，系統應說明新增了什麼，而不是讓一個百分比無故倒退。

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

- 既有「以單一 Current JD Task 為一次 OPKS operation」是控制輸出量、prompt/schema 大小與 durable failure boundary 的現行實作決策，不應升格成產品流程必須等待 Task 穩定的證據；2026-08-04 研究中的獨立 OPKS child 也是當時架構限制下的方案，不是新顧問必須保留的模型呼叫或 profile 邊界；
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

保存**同一位員工**在整段訪談與日後恢復時真正說過的原話、來源回合、時間、附件／引用位置，以及後續更正、否認或撤回的關係。它是回答「這項理解根據哪一句話」的 evidence layer，也是避免長訪談中忘記員工先前答案、反覆詢問同一件事的長期記憶。

- 摘要不得覆寫或取代原始來源；
- AI 不得改寫員工原話後冒充 source；
- 更正保留前後歷史並標示目前效力，不以刪除舊句偽造一致性；
- 準備再次詢問前，應先按焦點、穩定 ID、關聯與語意從該員工的完整歷史取回可能答案；只有找不到、彼此衝突、已過時或確實需要重新確認時才詢問；
- `speaker` 是來源識別與防止內容混淆的 metadata，不代表第一版要做多位受訪者、主管／同事訪談或多人 authority；
- 後續所有 Work Model、Proposal 與正式內容應可追溯到來源或明確的員工直接編輯。

### 7.2 工作模型記憶：AI 目前怎麼理解

保存 Story、Work Unit、Task／Duty hypothesis、O／P／K／S 候選、linkage、gap、矛盾、未映射線索與 retired candidate。它是可變動的分析層，不是 Current JD。

- AI 可以依新證據新增、修正、合併、拆分、重新連結或淘汰假說；
- 每項假說要保留穩定 identity、支持／反對證據、信心理由與生命週期狀態；
- `employee_denied`、過去工作、他人工作、一次性支援等 retired reason 不應被一般檢索重新當成 active candidate；
- Work Model 的變化可以影響焦點與 Proposal，但不得直接改變正式 JD。

#### 7.2.1 可演化工作假說的 framework-neutral contract（2026-08-13 已確認）

Owner 已確認採用「**typed、evidence-linked、可持續修訂的工作假說關係模型**」作為目標語意。它不是一份長得像 JD 的 AI 草稿，也不是把聊天紀錄壓成一段 memory summary；它保存的是 AI 對這位員工工作的**目前理解及其依據**。新證據可以改變任務邊界、Duty 分組、O／P／K／S linkage 與 gap，所以早期結構不能被誤當成永久分類。

第一版先鎖定下列邏輯契約，不在研究階段鎖資料表、class、序列化格式或供應商：

1. **可不完整的 typed item**：Story、Work Unit、Task／Duty hypothesis、O／P／K／S 候選、gap、矛盾與未映射線索都可先存在；尚未判定為 Task／Duty／OPKS 的內容以「未映射線索」類型保留，尚未分組或尚未連到 Task 也不等於非法狀態。
2. **穩定 identity 與修訂生命週期**：後續改名、補充、合併、拆分、重新分組或淘汰不能只靠文字相似度判斷同一性，也不能以覆寫抹除舊理解；至少要能分辨目前有效、被挑戰、被取代與有理由 retired 的版本。
3. **一級 evidence linkage**：每項重要理解可連回一個或多個員工 source anchor，並區分支持、反對、更正或不確定；模型信心、embedding score 或 Reference 相似度不能取代來源關係。
4. **typed domain relation**：能表達工作故事如何形成 Work Unit／Task、Task 如何暫時歸於 Duty、O／P 如何連到 Task、K／S 如何跨 Task 關聯，以及新證據如何造成 regroup、gap 或 contradiction。這些是關係語意的例子，不是先決定一套封閉 edge enum。
5. **與 authority 分離**：Work Model item 可以比 Current JD 早出現、持續演化，也可以與 Current JD 暫時不同；只有 typed Proposal／changeset 經員工 accept／edit 後，authority seam 才能改變 Current JD。員工修正 Work Model 不等於核准正式文件變更。
6. **以 delta 更新、以 projection 使用**：主要顧問或按需 Skill 只能產生 typed change intent；application 驗證來源、document scope、revision／read-set 與 domain invariant 後才提交 Work Model delta。側欄、進度、agenda、受限全域索引與 ContextPack 都由此投影，不各自保存一份競爭真相。

「關係模型／graph」在這裡只描述**邏輯上可沿穩定 ID 與 typed relation 走訪**，不代表採用 graph database、GraphRAG、RDF ontology，亦不等於 LangGraph／其他框架的 execution graph。PostgreSQL 關聯模型、typed application model 或成熟框架的 store 都可能承接機制；是否採用要等 capability matrix 與 conformance spike，不能從 `graph` 一字反推技術選型。

研究佐證與可轉移限制如下：

| 第一手來源 | 直接支持 | 不能據此宣稱 |
| --- | --- | --- |
| [U.S. OPM — Assessment and Selection](https://www.opm.gov/policy-data-oversight/assessment-and-selection/) | Job analysis 要辨識 Task、role／responsibility、competency、resources 與 context，向具直接且當前工作經驗的 SME 蒐集資料，並記錄 Task－competency linkage | OPM 沒有規定 LLM Work Model、graph schema、OPKS ontology 或資料庫技術 |
| [OpenAI Cookbook — Context Engineering for Personalization](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization/) | 以 local-first structured state 保存可修訂資訊、處理衝突與 precedence，推理時只注入相關 slice | 案例是個人化／旅遊助理，不直接證明其狀態欄位適合職務分析 |
| [Google Cloud — Choose agentic AI architecture components](https://docs.cloud.google.com/architecture/choose-agentic-ai-architecture-components) 與 [Microsoft Agent Framework — Memory & Persistence](https://learn.microsoft.com/en-us/agent-framework/get-started/memory) | 區分 session／history、application state、long-term memory 與外部 persistence；context provider 可承接 application-specific memory | 這些是 runtime／deployment 指引，不知道 Task、Duty、OPKS、員工更正與 JD authority 的產品語意 |
| [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 與 [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 長流程可把 structured notes／durable store 留在 context 外按需取用；LangGraph 明確區分 thread checkpoint 與 cross-thread Store | structured note、Store 或 graph state 不會自動成為可信 evidence，也不應變成第二份 Work Model／Current JD |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) 與 [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) | 提供 derived-from、revision、quotation、primary source、invalidation，以及 quote／position selector 等可借鏡的來源與修訂語意 | W3C 不要求 Caliburn 採 RDF，也沒有定義職務分析的 domain model；position anchor 單獨使用對內容變更很脆弱 |

因此，外部資料直接支持的是「**結構化狀態、可追溯來源、明確修訂、分離 runtime checkpoint、按需傳入 context**」；把它們組成上述 Work Model，是 Caliburn 結合 OPM 的職務分析原則、既有 Task／Duty／OPKS 研究與員工 authority 所作的產品推論。現階段尚無可信公開 benchmark 證明某個 memory／agent framework 能直接提升繁中職務訪談或 JD 品質，後續不得把框架功能表當成效果證據。

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

#### 7.9.1 主要顧問回合的全域定位：受限索引，不是完整資料（2026-08-13 研究後確認）

Owner 確認 AI 在深入單一 Task 時，仍可持續看到整份職務的精簡地圖，並要求以最新權威資料反證。研究支持這個**混合架構方向**，但沒有任何來源直接證明「繁中職務訪談的每一個模型呼叫固定帶同一張地圖」就是最佳值：

- OpenAI 2026 Context Engineering Cookbook 建議保存 coherent structured state、在每次 run 只注入當下相關 slices；最新 model guidance 也要求精簡重複 prompt／tools、追蹤成長中的 context，並保留完成工作所需的 facts、decisions、constraints 與 evidence。
- Anthropic Applied AI 團隊指出只靠 pre-inference retrieval 不足，主流方向正加入 just-in-time context；其資料認為部分場景可能以 hybrid 最有效：預載少量資料取得速度，再用輕量 identifier 與工具逐層展開，最終目標仍是最小高訊號 token 集合。
- Google Cloud 2026 架構指引把 progressive disclosure 列為 agent context／capability 的設計策略：相關內容需要時才解鎖，不預先載入全部；session、state 與 long-term memory 也分開處理。
- Microsoft Research 的 DRIFT／GraphRAG 顯示，局部問題可從高階 community information 取得更廣的起點，再向局部原文深入；其 AP News 實驗中 DRIFT 對 local questions 的 comprehensiveness／diversity 勝過 local search，但這是新聞語料與 LLM-judge 指標，只能支持「全域導向＋局部展開」值得採用，不能直接當成本產品效果證明，也不要求導入 GraphRAG。

三種產品方案比較如下：

| 方案 | 優點 | 主要問題 | 裁決 |
|---|---|---|---|
| 只帶目前焦點與 retrieval 結果 | token 最少、實作直觀 | 容易重複建立 Task、把旁支歸錯位置、錯過跨 Task 矛盾或延遲 Duty regroup | 不採用 |
| 每輪帶完整職務、原話、OPKS 與歷史 | 單次模型表面上資訊最多 | 成本與延遲隨訪談成長；過時假說、重複內容與無關細節持續污染 attention | 不採用 |
| 受限全域索引＋焦點細節＋按需展開 | 保留全局定位，同時控制成本並取得原始證據 | 需要明確索引、authority label、降級與唯讀 lookup 契約 | **採用** |

這裡的「每輪」只指**可能產生 Work Model／agenda／Proposal 變更候選，或決定下一個訪談方向的主要顧問 inference**；候選仍須通過既有 verifier、reducer 與 semantic commit，模型不直接寫入。deterministic verifier／projection 不需要模型 context；唯讀工具只接受 scope 明確的查詢；Task／Duty／OPKS specialist 只取得其 typed contract 所需的焦點資料與必要 orientation，不自動複製整份主要顧問 ContextPack。

因此主要顧問 inference 必帶一份 **bounded global orientation index（受限全域工作索引）**。它是從 Current JD、Current Work Model 與 workflow state 產生的 deterministic、versioned、可重建投影；不是 LLM 自由摘要、RAG 搜尋結果、第五份 authority store，也不因被放進 prompt 就改變任何項目的權威。

索引至少讓模型辨識：

- document／generation 與目前 focus；
- active Duty／Task 的穩定 ID、短名稱、基本歸屬與生命週期狀態；
- 每個項目屬於已授權 Current JD、可變 Work Model hypothesis，或 workflow gap／待決狀態，三者不得混成同一權威；
- 未歸類 Task、重大矛盾、blocking dependency 與待決 Proposal 的存在及可查詢指標；
- 目前已知範圍的摘要數量，使模型與員工介面的進度投影能指向同一組可解釋對象。

索引平時不攜帶完整 Task 敘述、全部原話／Evidence、完整 OPKS、完整 Proposal payload、Reference 內容、整段歷史，或已退休／已否認候選的細節；這些依焦點、直接關聯與受控工具按需取得。最新有效更正、會推翻本輪判斷的矛盾與其他 authority floor 仍由必帶核心另行保證，不能因索引精簡而遺失。

全域地圖本身也可能造成定錨：模型可能把目前 Duty／Task 分組誤認成完整且固定的世界。第一版必須同時施加以下邊界：

- 明示索引是「目前可修改的正式內容／假說／缺口投影」，不是完整 ontology 或員工已全部確認的清單；
- 當輪員工來源、最新有效更正與 blocking contradiction 不得被索引摘要覆蓋；
- 索引保留未歸類 Task、未映射線索、open gap、矛盾、待決 Proposal 的數量、狀態與查詢指標，讓「目前結構以外仍有東西」保持可見；
- 主要顧問可以提出新 Task／Duty、重新分組或重新開啟假說，不能因現有 header 沒有對應位置就捨棄新線索；
- UI 進度與模型索引應由同一組 domain projection 語意產生，但各自使用適合人與模型的 representation，不共享一份由 LLM 生成的摘要文字。

索引也不能無限成長：

- 小型職務在預算內可列出全部 active Duty／Task headers；
- 超出預算後，確定性降級為全部 Duty 摘要、目前焦點及相鄰 Task、其他區域的數量／狀態／查詢指標；
- 模型需要遠端細節時，透過 document-scoped read-only lookup 展開，不把所有區域預先載入；
- 降級規則、被省略區域與實際載入內容寫入 ContextManifest，不可靜默假裝索引完整。

這項裁決把「前景專注、背景全域吸收」轉成可實作邊界：前景得到足以完成當輪判斷的細節；背景保有結構定位與異常訊號，而不是保有所有細節。它同時支援 Task／Duty 隨訪談演化、OPKS 按需分析、旁支線索停放與可解釋進度，不要求第一版先導入 GraphRAG、向量記憶或額外 planner model。確切欄位、大小，以及 active consultant model profile 的 context window／能力改變時如何確定性降級，仍屬 §7.15 未決實作參數，成品後再用真實長訪談 eval 調整。

#### 7.9.2 資料不足時的補查與詢問順序（2026-08-13 研究後已確認）

Owner 已確認「不要把能自行查到的內容反覆問員工」，並要求先以最新、主流與權威資料反證後再收斂。研究後的正式方向是：**本文件內可直接定位的相關資料原則上先自動查；iCAP 不是每次詢問員工前都必須經過的固定關卡；只有這位員工能確定的當前工作事實、意圖與裁決，應直接問員工，不得由 Reference 補值。**

外部資料支持的是這個分流原則，而不是一條固定的「local RAG → iCAP RAG → 問員工」流水線：

- OpenAI 最新 model guidance 建議只暴露當下相關工具、追蹤成長中的 context，並明示重要歧義何時必須提問；安全、唯讀且在範圍內的查詢可持續進行，重要歧義與核准邊界則停止並交還使用者。
- Anthropic 的 Context Engineering 建議以少量預載資料加 just-in-time 探索取得最小高訊號 context；其 Trustworthy Agents 研究進一步區分「可自行研究的缺口」與「只有使用者能決定的偏好／意圖」，並指出過度詢問與一律自行假設都會降低可靠性。
- Google Research 的 Sufficient Context 研究顯示，retrieval 的「相關」不等於「足以回答」；額外但不足的 context 可能提高模型信心與幻覺，因此不能把「查過 iCAP」當成資料已充分。
- Microsoft Research 在超過 20 萬段模擬對話中觀察到，模型會受早期錯誤假設牽制且難以恢復；這支持優先注入最新更正、保存結構化目前理解，並在會改變工作邊界時釐清，而不是讓模型沿長對話自行猜。
- OPM 將 job analysis 定義為系統性蒐集、記錄與分析工作內容、情境及要求，並以具有直接、近期工作經驗的 incumbent／supervisor 作為 SME 來源。這支持 iCAP 可提供比較框架與 coverage 候選，但不能取代員工對「本人現在實際做什麼」的確認。OPM 並未替 Caliburn 決定單一員工 authority；後者仍是本產品既有裁決。

因此，第一版 Context Policy 採下列**缺口分類與查詢階梯**；階梯是依缺口類型選路，不要求每輪走完所有步驟：

1. **先判斷缺口類型，不先盲目搜尋。** 區分為本文件可檢索事實、Reference 可協助的 coverage／術語、員工專屬工作事實／意圖／裁決，以及本輪不阻塞的延後 gap。這可作為同一次主要 inference 的 typed sufficiency／next-action 欄位，不要求固定增加一個 planner call。
2. **本文件的直接關聯先自動讀。** 若答案可能已存在於當輪回答、最新更正、穩定 ID linkage、焦點 Task／Duty／OPKS、相關 Proposal 或明確 source receipt，Context Engine 應在 document scope 與 budget 內先查，不把內部查得到的內容原封不動再問員工。
3. **只有直接關聯不足時，才擴展本文件檢索。** 依 lexical／semantic 候選、相鄰回合與來源關係補查；若找到的只是舊假說、已否認內容或相互矛盾來源，仍視為不足，不得用相似度決勝。
4. **iCAP 只在它能改進 coverage、術語或中立追問時按需查。** 例如確認是否漏問常見產出、控制點或能力面向。若缺的是「這名員工是否負責核准、頻率是多少、實際例外怎麼處理」，iCAP 在設計上不可能回答，就不必為了形式先查一次。
5. **員工專屬或高影響歧義直接詢問員工。** 包含責任歸屬、實際做法、決策權、頻率／條件、本人意圖、來源衝突，以及會實質改變 Task 邊界、Duty 分組、OPKS 或 Proposal 的未決事項。問題應聚焦一個主要判斷，說明目前理解與缺口，不要求員工重述系統已知內容。
6. **非阻塞缺口可以明示延後。** 若不影響當前焦點、補查成本超過本輪 budget，或員工選擇稍後回答，就以 reason code 與可恢復 agenda item 保存；不得偷偷補值，也不得因未查遍所有可能資料而阻止本輪產生有效的理解更新、gap 或下一個問題。

可先使用下列語意 reason code，名稱與 schema 之後仍可調整：

- `SUFFICIENT_FOR_CURRENT_ACTION`：對本輪合法產出已充分；
- `LOCAL_LOOKUP_NEEDED`：本文件仍有明確可查來源；
- `REFERENCE_LOOKUP_HELPFUL`：iCAP 可能改善 coverage／術語／問題品質，但不能建立員工事實；
- `EMPLOYEE_CLARIFICATION_REQUIRED`：只有員工能回答，或影響重大到不能假設；
- `DEFER_WITH_VISIBLE_GAP`：本輪不阻塞，保留可恢復缺口。

「充分」是相對於**本輪合法 action**，不是整份職務已完整。例如現有證據可能足以提出一個 Task 候選，但不足以提出其完整 OPKS；此時可以更新 Work Model 並留下 OPKS gap，不必為了追求全域完整而無限補查。每次 read-only lookup 應有目標、理由、預期補足的缺口、scope、budget 與停止條件，實際讀取內容寫入 ContextManifest；停止條件是已足以產生 Proposal／no-op／visible gap／一個主要問題之一，而不是「所有可能 Context 都載入完成」。

Reference 形成問題時要降低 anchoring：介面或顧問話術應表明它是公版常見可能性，允許員工回答 match／partial／no-match／conflict／unknown／deferred，不能用「標準上應該有」暗示員工接受。員工否認或更正後，以員工來源更新 Work Model 並保留 challenge receipt；不得因 iCAP 分數較高而覆蓋。

白話例子：訪談「月結」時，系統若已在舊回合記錄員工每月整理差異表，就先讀回該原話，不再問「你是否整理差異表」。若 iCAP 顯示同類工作常見覆核控制，AI 可以中立追問「有些相近職務會做覆核；你的工作也包含嗎？」但若真正缺的是「你本人能不能核准調整」，應直接問員工，不先拿 iCAP 猜答案。若員工順帶提到偶爾教同事 SAP，系統可保存為旁支線索；只要它不阻塞月結焦點，就不必立刻展開完整訪談。

此結論仍有可轉移限制：OpenAI／Anthropic 的材料主要是通用 agent 工程，Google 的量化研究是 RAG QA，Microsoft 的研究任務不是繁中職務訪談，OPM 也不是 AI Context Engine 規格。公開資料沒有直接比較「先查 iCAP」與「直接問員工」何者能提高本產品成效；上述順序是把多方共同原則套入 Caliburn 的 authority、成本與訪談負擔後形成的產品假說，成品完成後仍需用真實訪談情境驗證。

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

#### 7.12.1 近期對話、結構化狀態與來源優先序（2026-08-13 研究後已確認）

Owner 已確認「少量最近對話維持自然銜接；完整保存並可按需找回同一位員工先前說過的話；事實判斷仍以原始來源、結構化目前狀態與最新有效更正為準」，並要求以最新主流資料佐證。交叉查核後，這個方向成立，但必須避免把它簡化成固定保留 N 則訊息、把完整歷史常駐 prompt，或使用全域 `latest wins`：

- OpenAI 2026 年 Context Engineering Cookbook 將 local-first structured state、session notes 與本輪注入分開，只注入相關 state slices，並示範 latest user input／session override／global default 的衝突優先序；OpenAI 最新 model guidance 也允許依過往 reasoning 是否仍相關選擇 `all_turns` 或 `current_turn`，沒有要求所有產品固定重送完整歷史。
- Anthropic 將 message history 也視為有限 attention budget，建議使用最小高訊號 context、compaction、外部 structured notes 與 just-in-time retrieval；完整保存不等於完整常駐 context。
- Google 2026 年 ADK 長流程指引直接指出，持續重播全部聊天會造成 context pollution、成本增長與虛構未發生步驟；production agent 應使用 durable memory schema 與 explicit state，並從 state 讀取目前位置，而不是從舊訊息猜。
- Microsoft HAX 要求記住近期互動，讓使用者可以自然地說「他」「剛才那個」；最新 Agent Framework 同時把 conversation `HistoryProvider`、application-specific `ContextProvider` 與輕量 session state 分開，長對話建議逐訊息保存 history，不把全部聊天塞進 session state。

這些來源共同支持的是**短期連續性＋結構化長期狀態＋按需來源**，不是某個固定訊息數。公開資料也沒有直接證明「最近 4 則」或「最近 8 則」對繁中職務訪談最好，因此第一版應按語意回合選取：

- 當輪員工完整輸入與他正在回答的顧問問題／校準卡必帶；
- 為理解代名詞、省略語、修正語氣或「剛才」引用所需的最短相鄰對話可帶；
- 更早對話不因時間接近就自動取得事實權威，依 source receipt、穩定 ID、lexical／semantic retrieval 按需取回；
- 若最近對話已被員工更正，仍可為對話連續性保留，但必須標示已 superseded，不能讓模型誤當現況；
- 實際帶入多少、為何帶入及被省略區域寫入 ContextManifest，之後再由成品 eval 調整，不先把 `last_n_messages` 寫成 domain invariant。

概念上採三個不同責任的 runtime artifact；本節只定責任，不提前鎖定最終資料表或 JSON schema：

1. **ContextRequest**：application 產生的本輪需求與政策，包含 document、operation、focus、generation／read-set、authority floor、允許的 Skill／tool／Reference、model profile reference、operation policy 與 budget。LLM 不能擴張 scope 或自行降低必帶內容。
2. **ContextPack**：送入某次 inference 的 immutable snapshot，包含必帶核心、近期連續性、受限全域索引、焦點細節、候選來源、載入的 Skill 與可用工具目錄。每個 item 保留 authority／source／revision 標籤；它不是新的 Work Model 或 authoritative store。
3. **ContextManifest**：記錄每次 inference／tool wave 實際載入、按需取得、拒絕或省略的 refs／revision／hash、選取理由、tokens／成本、model／prompt／Skill／tool version、停止原因與結果 lineage。原始內容仍由原 store 保存，Manifest 不複製另一份員工原話。

衝突不能用一條總排序解決，必須依問題的 authority 類型判斷：

| 問題 | 生效規則 |
|---|---|
| 員工目前對實際工作的說法 | 最新有效員工更正優先於較舊員工說法、摘要與模型記憶；舊來源保留但標示 superseded |
| AI 目前如何理解 | 最新 Work Model revision 優先於舊 hypothesis／summary，但仍須連回原始來源，不能把推論偽裝成員工原話 |
| 目前正式 JD 是什麼 | Current JD 仍是正式 authority；新的員工更正只先形成差異、Work Model 更新、gap 或 Proposal，未經 accept／edit 不得直接覆寫 |
| 對話如何自然銜接 | 近期訊息與 provider state 可協助理解指涉及語氣，但不能覆蓋員工更正、Work Model revision、Current JD 或 domain policy |
| iCAP 提供什麼 | 只能作 Reference／coverage challenge；不論多新、多相關或分數多高，都不能覆蓋員工來源或建立本人工作事實 |

當輪員工輸入具有雙重角色：在互動上是近期對話，在成功保存後也是 durable employee source。前者可以為節省 context 而縮減相鄰對話，後者則必須依既有 source identity、document scope、correction linkage 與 idempotency 規則持久化；框架不得因 compaction、summary 或 message-window policy 把它降級成只有暫時效力的聊天文字。

因此「最新更正優先」與「Current JD 未核准前不變」可以同時成立：前者決定顧問如何理解與下一步要處理的差異，後者決定正式文件目前仍是什麼。ContextPack 必須把這種 divergence 明示給模型，不能先把兩者合併成一個看似一致的欄位。

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
- 受限全域工作索引的最終 schema、大小門檻、摘要層級，以及 active consultant model profile 的 context window／能力改變時的降級參數；
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

#### 7.16.2 迭代與補查 budget：沒有通用最佳次數（2026-08-13 研究結論）

進一步查核截至 2026-08-13 的官方實作後，不能把「最多補查兩波」宣稱成大廠標準或研究證明的最佳值。OpenAI 最新 guidance 要求依 bounded stage 明定 concurrency、retry、stopping limits 與 required evidence，但不給通用次數；Anthropic Tool Runner 提供 `max_iterations`，範例使用 10，官方同時允許 application 隨時 `break`；Microsoft Agent Framework 的 loop 預設上限也是 10，但明確警告 completion predicate 可能失敗、模型可能停滯、evaluator 也具有機率性，因此 autonomous loop 永遠要有上限，而且該 looping 功能仍標為 experimental；LangChain 則把 model-call 與 tool-call limit 拆成 run／thread／per-tool middleware。這些「10」是 runtime 安全預設或文件範例，不是互相獨立的職務訪談品質證據，不能直接複製成產品規則。

Google 2026 年 ADK 2.0 的方向更接近本產品：已知 routing、固定 business rule、錯誤與 HITL 用 deterministic workflow；只有模糊自然語言與動態判斷交給 LLM。其官方示例把 LLM node 設成 single-turn，並指出讓模型反覆執行可預知流程會增加 tokens、latency、prompt noise、重複工具與脫軌風險。OpenAI 也建議能由 bounded code 完成的 filtering／ranking／dedup／aggregation 由程式處理，語意判斷、approval 與最終驗證保留直接 model turn。共同趨勢不是「更長的自由 Agent loop」，而是 **hybrid agentic workflow：程式控制邊界與完成條件，模型只處理不可預先寫死的認知工作。**

因此 Caliburn 應把 budget 拆開，不使用單一 `max_steps` 混算所有事情：

- **model inference budget**：限制主要顧問與必要 specialist 的模型回合；
- **lookup-wave budget**：一次模型判斷可以提出多個彼此獨立的唯讀 request，由 application 安全批次／平行執行；一波不是一個 tool call；
- **per-tool／total tool budget**：限制高成本 Reference、semantic search 或大型來源讀取，直接 relational lookup 可有不同上限；
- **technical retry budget**：網路／rate-limit／schema 等可重試失敗與語意探索分開計數，但仍累計 elapsed time、tokens 與成本；
- **no-progress budget**：重複 request fingerprint、相同結果 hash、沒有新 source／revision，或 sufficiency reason 沒有可解釋變化時提早停止；
- **human-interrupt boundary**：只有員工能回答、需要員工判斷或涉及 authority 時立即退出自動 loop，不消耗剩餘額度硬猜。

第一版可採下列**候選 operation execution policy**，作為 conformance／人工 smoke 的保守起點，而不是不可變 domain policy：

1. 正常快速路徑：一次主要顧問 inference，能提交合格 typed result 就結束。
2. 補查路徑：第一個 inference 可提出一批 scope 明確的唯讀查詢；工具結果回來後由同一主要顧問整合。
3. 只有第一批結果揭露新的穩定 ID、source receipt、矛盾或先前不可知的明確指標，而且確實對 unresolved reason code 有預期貢獻時，才允許第二波。
4. 互動式正常回合的起始 hard ceiling 可設為 **三次 model inference（初始＋兩次結果整合）與兩波 lookup**；數值放在可替換的 operation execution policy，模型與 provider 仍取自全域 consultant model profile，不寫進 Task／Duty／OPKS domain invariant。一次 wave 可批次多個獨立 read-only request，因此不以「兩波」誤限成只能查兩筆資料。
5. 到達上限、重複查詢或沒有新資訊時，不啟動額外 evaluator／judge loop；輸出 `EMPLOYEE_CLARIFICATION_REQUIRED`、`DEFER_WITH_VISIBLE_GAP` 或 structured processing limit。不能安全形成語意結果時不更新 Work Model。

這個 operation execution policy 選擇三次 inference／兩波 lookup，不是因為外部 benchmark 證明它最佳，而是它完整容納「初始判斷 → 一般補查 → 新指標例外補查 → 最終整合」，同時比 SDK 常見的 10-turn 通用上限更符合即時員工訪談的延遲、成本與可理解性。未來若某個 operation（例如獨立 Reference coverage audit）確實需要更深探索，應建立另一個有自己 success criteria 與 budget 的 execution policy，不默默放寬所有員工回合；這仍不自動代表要換模型。

這也收斂框架需求：候選 runtime 至少要能分別限制 model／tool calls、攔截重複或錯誤工具、批次安全的唯讀查詢、在 limit／HITL 時保存可恢復 state，並輸出完整 trace／usage。框架若只提供一個總迴圈次數，仍需由 Caliburn harness 補上 operation、authority、progress 與成本政策。

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
7. **provider-specific state 是可替換優化。** `store=false`、ZDR、region、cache TTL 等能力可由 adapter 顯式映射，但 domain 與 use case 不依賴任一廠商欄位。某 provider 不支援某項控制時，回到已核准的標準商業 API 政策，不偽裝成 ZDR。

這項裁決不等於永遠拒絕 fallback、provider state 或遠端 observability；它要求這些能力未來以顯式、可追溯、可關閉的 adapter／runtime 設定加入。第一版不需要建立讓員工挑選 retention policy 的複雜 UI，也不需要為尚未存在的企業合規需求預做多套資料模式。

### 7.20 模型、provider 與參數 profile 控制面（2026-08-13 維護者控制與第一版粒度已確認）

Owner 已確認：**模型、provider 與底層參數由本機維護者透過版本化 profile 管理；受訪員工不在訪談介面直接操作 `temperature`、reasoning effort、token limit 或 routing 等原始旋鈕。** 第一版可以由設定檔或維護者設定面承接，尚不要求獨立管理 UI。即使維護者與受訪員工在本機上可能是同一個人，產品責任仍分開：前者配置執行環境，後者提供工作事實並決定 JD 內容。

framework-neutral 控制面必須先分開四項責任，避免把「這輪要做什麼」誤寫成「這輪要換哪個模型」：

1. **Versioned consultant model profile**：保存人可讀名稱、requested provider／model、模型能力需求、品質／延遲／成本意圖、共同模型參數預設、允許的 routing／fallback 與 provider-specific 選項；修改產生新 revision，不回寫舊 run 的設定歷史。API key 只保存 secret reference，不進 profile 內容、trace 或 prompt。
2. **Versioned operation execution policy**：依 operation 保存允許的 Skills／tools、typed input／output contract、context／output／model-call／tool／時間／成本上限、retry 與停止規則。不同 operation 可以有不同 policy，但這只改變工作範圍與執行預算，**不等於不同模型**。
3. **Resolved execution snapshot**：每個 model-bearing run 開始前，由 application／adapter 合併 model profile revision、operation policy revision 與當時模型能力，解析成 immutable snapshot；至少記錄 requested provider／model、可在送出前確定的 resolved model ID／provider allow-list、實際送出的有效參數、能力檢查、budget、route policy 與 adapter version。動態 gateway 最後選到的 endpoint 留給 attempt receipt 記錄；LLM 不得自行改模型、提高預算或放寬 fallback。
4. **Run／attempt receipt**：回應後保存 provider 回報的實際 model／endpoint（若供應商提供）、attempt chain、usage、成本、latency、cache／state 使用情況、停止原因與錯誤。這是重播、歸因與日後比較的執行證據，不是 Work Model 或 Current JD。

第一版的模型粒度收斂為：**整個生成式職務分析顧問只有一個 active consultant model profile。** 一個員工回合即使因補查而有多次 inference，或載入不同 Skill／tool，仍沿用該 run 開始時解析出的同一份 model profile snapshot。這裡的「一個」不是說整個 monorepo 只能出現一種 AI 模型；embedding、reranker、OCR 等非顧問型技術模型可以有各自的版本化設定，但不得被包裝成另一位職務分析顧問或取得產品 authority。

| 產品能力 | 第一版模型邊界 |
|---|---|
| 主要顧問、工具結果回來後的再整合 | 使用同一個 active consultant model profile |
| Task／Duty／O／P／K／S Skills | 是方法與 context 的 progressive-disclosure 邊界；不擁有 model profile，也不因載入而另開模型呼叫 |
| structured semantic result | 是 output contract，不是模型角色；無論最後由一次或受限多次呼叫形成，都使用同一個顧問 profile，schema／verifier 也不是另一個「結構化分析模型」 |
| iCAP Reference | 檢索是 read-only tool／RAG pipeline；需要語意挑戰或整合時仍由同一位主要顧問判斷 |
| embedding／reranker | 是 Reference pipeline 的技術模型，可獨立版本化；不等於可見顧問或分析 authority |
| 未來 bounded specialist | 只有實際建立獨立 model call 與 typed contract 時才算呼叫邊界；預設仍繼承全域顧問 profile，第一版不配置 per-specialist model override |

框架即使提供 dynamic model selection，也只代表**可以實作**，不代表產品應啟用。未來若要讓某個 model-bearing operation override 全域 profile，至少要同時滿足：它具有獨立 input／output／evidence／success criteria；所需 modality／capability 無法由全域模型提供，或成品後代表性評測證明替換能在品質不退步下改善成本／延遲；路由由 application 的版本化政策決定並留下 receipt，而不是由 Skill、LLM 或 gateway 自由挑選。未達這些條件時，只調整 Skill、tool、schema 或 execution policy，不拆模型。

生效與失敗規則如下：

- model profile 或 operation policy 變更只影響之後新建立的 run；已開始的 run 與可安全恢復的 attempt 沿用原 resolved snapshot，不在中途偷偷換模型或預算；
- 若原模型已退役或原能力無法再取得，不假裝精確 resume：保留舊 artifact，建立帶新 snapshot 的新 attempt，重新檢查 authority generation／read-set，並讓 route change 可追溯；
- 不建立一組假裝跨廠商完全等價的 raw parameter bag。consultant model profile 表達共同意圖與能力要求，各 adapter 顯式映射；不支援的參數在啟動／解析時拒絕或明確省略並留下原因，不可靜默接受後假裝已生效；
- 第一版不允許 gateway alias、動態 router 或 provider fallback 在沒有 receipt 的情況下改變實際模型。若使用可漂移 alias，必須同時保存 requested alias 與 provider 可回報的實際 model ID；production 預設優先使用供應商建議的固定／stable ID；
- 員工可以看到目前使用的 profile／模型名稱與必要揭露，但不需要理解廠商特有參數。未來若提供「較快／平衡／品質優先」等核准 preset，仍由維護者把 preset 映射到版本化 profile，而不是把原始旋鈕放進每回合訪談。

這些規則有明確的一手資料背景：[OpenAI Model guidance](https://developers.openai.com/api/docs/guides/latest-model) 要求依 workload 明確選模型與 reasoning effort，以代表性工作比較品質、延遲與成本，並指出「有多個呼叫」本身不足以證明需要另一種工具編排路徑；其 [Skills 文件](https://developers.openai.com/api/docs/guides/tools-skills) 直接示範在一個指定 model 的 Responses request 掛載多個 Skills。[Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) 把 Skills 定義為同一個 general-purpose agent 按需載入的可組合知識；[Google ADK Skills](https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/) 也以一個設定單一 model 的 root agent 掛載整組 SkillToolset。[LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents) 把 model、tools 與 structured output 列為同一 agent 的不同元件，而 [dynamic model selection](https://docs.langchain.com/oss/python/langchain/middleware/custom#dynamic-model-selection) 是可選 middleware；[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/) 則明示單次 LLM call（可含 tools）足夠時使用 agent，只有多個 agent／function 必須協調時才需要 workflow。

另一組來源處理版本與路由追溯：[Anthropic model versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) 區分 pinned model ID 與會指向較新 snapshot 的舊式 alias，其 [Messages API](https://platform.claude.com/docs/en/api/typescript/messages/create) 也顯示新模型可能不再接受 `temperature`／`top_p`；[Gemini Models](https://ai.google.dev/gemini-api/docs/models) 明確建議 production 使用 specific stable model，而 `latest` alias 會隨版本熱切換；[OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection) 則顯示 provider order、fallback 與參數支援都需要顯式控制。

可轉移限制：上述資料證明「同一模型可組合 Skills／tools／structured output」「動態換模型只是可選能力」以及「實際路由要可追溯」，**沒有公開 benchmark 證明單一模型或多模型對繁中職務訪談何者效果最佳**。因此第一版單一顧問 profile 是依本產品「一位顧問、按需 Skills、避免過早增加路由與失敗面」做出的保守裁決，不冒充外部研究結論。

本節仍不選定預設模型 ID、確切參數值、價格門檻或設定 UI；但第一版 profile 數量已定為**一個 active consultant model profile**，不再等待 operation 分流策略決定。品質／成本最佳值仍依既定決定，等可用成品完成後再用代表性長訪談 eval 調整。

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

### 9.1 討論與設計關卡（2026-08-13 owner 已確認）

討論依下列順序進行。框架研究可提前蒐證，但不得跳過產品情境與目標能力，反向把框架現成功能寫成產品需求；現行 module 只作現況與切換風險證據，不能當新架構模板。

| 關卡 | 狀態 | 要回答的問題 | 離開條件 |
|---|---|---|---|
| 0. 產品北極星 | 已收斂 | 顧問是誰、員工有何權力、何謂完成 | §1–§6 的大方向無已知根本衝突 |
| 1. 端到端情境 | **當前** | 正常、改道／更正與失敗恢復時，員工和顧問各自看到、知道、做什麼 | 情境能涵蓋焦點、全域吸收、動態 Task／Duty／OPKS、進度、Proposal、暫停／恢復與匯出，且沒有未揭露的權威跳躍 |
| 2. 目標能力地圖 | 待研究 | 為了實現情境，系統必須具備哪些能力與不變條件 | 每項能力都有輸入、輸出、authority、持久化責任、失敗語意與 `Replace／Wrap／Retain` 判準 |
| 3. 框架組合選型 | 待研究 | 哪些成熟元件可承接能力，哪些產品語意仍由 Caliburn 擁有 | 比較 2–3 組可落地組合；逐項記相容證據、版本／授權／供應商鎖定、成本與不採用理由，不用「主流」代替 conformance |
| 4. 目標架構 | 待研究 | 元件如何合作，資料／API／Web／Context／恢復／切換如何落地 | 形成完整設計，通過大方向回歸審查、反方審查與 owner 核准；所有關鍵來源重新查核 |
| 5. 實作計畫 | 待研究 | 如何在隔離 worktree 內完成受限 Big-bang 並可驗證地切換 | 任務可獨立驗證、列明依賴與回滾點；正式 eval 依 owner 裁示延後到成品完成後，不得因此刪除必要 trace／usage／驗證邊界 |
| 6. 實作與切換 | 未授權 | 依核准計畫施工、審核、驗證與切換 | 另由 owner 明確授權；本研究稿本身不構成施工授權 |

每關卡收斂後應更新本表、在相鄰段落補齊 §0.1 的決策帳本，並以只包含該關卡文件變更的 commit 保存。若細節研究發現較佳方向但會改變已確認北極星，必須先回到產品層與 owner 討論；不得在 framework matrix、schema 或實作計畫中悄悄翻案。

### 9.2 已知切換邊界與下一批能力

產品北極星、白話流程、進度、記憶／Context、員工 authority、框架替換原則與「AI 顧問子系統受限 Big-bang」已確認。完成關卡 1 後，關卡 2 建立**與舊 module 無關的目標能力地圖與切換邊界**：

1. 顧問互動與受控 orchestration；
2. 同一員工的來源記憶、Context selection 與可恢復長流程；
3. 可演化的工作假說、焦點／agenda 與三層進度投影；
4. Task／Duty／O／P／K／S 按需 Skills 與 deterministic verification；
5. 跨 Task／Duty 的 typed changeset、員工審核與 Current JD authority；
6. iCAP Reference／RAG coverage challenge；
7. 可替換 model／provider、參數 profile、usage、trace 與失敗恢復；
8. 支援上述流程的 API／Web 體驗。

切換邊界已於 2026-08-13 收斂：iCAP Reference／RAG 是 final gate，worktree 內先做核心顧問、後接 RAG，完成後一次切換；目前也沒有需保留的真實 JD／訪談資料，因此採 fresh-schema hard cut，不做舊 AI 狀態 migration。跨 Task／Duty／OPKS 的 Proposal 粒度已確認為「可編輯 review bundle＋必要原子子群組」；「可演化工作假說」已於 §7.2.1 收斂；模型／provider／參數的維護者控制權、版本化 profile、run snapshot 與 route receipt 亦已於 §7.20 收斂，第一版採單一 active consultant model profile，operation 只配置 execution policy。下一步回到 framework capability matrix，不能再以 Skill、structured output 或 Reference 的名稱預先切出多模型拓撲。

能力地圖確認後，再逐列建立「目標能力／現況／框架候選／`Replace|Wrap|Retain`／仍需自寫語意／successor ADR／驗收情境」矩陣，回答哪些成熟元件能真正取代現有實作。LangGraph／LangChain、OpenAI Agents SDK、Microsoft Agent Framework、Google ADK、Agent Skills、Pydantic＋SQLAlchemy＋PostgreSQL、W3C anchor／provenance 等目前都只是候選或標準；任何框架都不得以舊 module 拓撲作為新設計目標，也不得在 conformance 前取得產品 authority。研究稿仍不能直接當施工授權。

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
- [Anthropic — Trustworthy agents in practice（可自行研究的缺口與必須詢問使用者的意圖）](https://www.anthropic.com/research/trustworthy-agents)
- [Anthropic — Scaling Managed Agents: Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents)
- [Anthropic — How we contain Claude across our consumer products](https://www.anthropic.com/engineering/how-we-contain-claude)
- [Anthropic Docs — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic Docs — Tool runner（自動 loop 與 custom HITL 邊界）](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Anthropic Docs — Managed Agents permission policies](https://platform.claude.com/docs/en/managed-agents/permission-policies)
- [Anthropic Docs — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic Docs — Model IDs and versioning（pinned ID 與 alias）](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)
- [Anthropic API — Create a Message（model-specific parameter support）](https://platform.claude.com/docs/en/api/typescript/messages/create)
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
- [Google AI for Developers — Gemini Models（stable／preview／latest／experimental）](https://ai.google.dev/gemini-api/docs/models)
- [Google Research — Sufficient Context: A New Lens on RAG Systems](https://research.google/blog/deeper-insights-into-retrieval-augmented-generation-the-role-of-sufficient-context/)
- [LangGraph — Overview](https://docs.langchain.com/oss/python/langgraph/overview)
- [LangGraph — Workflows and agents（predetermined workflow 與 dynamic loop）](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph — Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [LangGraph frontend — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop)
- [LangChain — Context engineering in agents](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Agents（model、tools、structured output 的組合邊界）](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain — Custom middleware（dynamic model selection 是可選 middleware）](https://docs.langchain.com/oss/python/langchain/middleware/custom#dynamic-model-selection)
- [LangChain — Prebuilt middleware（model／tool call limits、retry、HITL）](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain — Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [PydanticAI — Deferred tools and human-in-the-loop approval](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [OpenRouter — Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr)
- [OpenRouter — Provider routing and data-policy controls](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging)
- [Microsoft — Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Microsoft — Agent Framework Memory & Persistence（history、context provider、session state）](https://learn.microsoft.com/en-us/agent-framework/get-started/memory)
- [Microsoft — Self-host Agent Framework applications（session 與 history 分離）](https://learn.microsoft.com/en-us/agent-framework/hosting/self-hosting/)
- [Microsoft — Agent Framework Harness](https://learn.microsoft.com/en-us/agent-framework/concepts/harness)
- [Microsoft — Agent looping（completion condition、bounded iteration、approval escape）](https://learn.microsoft.com/en-us/agent-framework/agents/looping)
- [Microsoft — Agent Framework workflows human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- [Microsoft — Agent Framework AG-UI integration](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/ui/ag-ui/)
- [Microsoft Azure Architecture Center — Strangler Fig pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)
- [AWS Prescriptive Guidance — The strangler fig pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-aspnet-web-services/fig-pattern.html)
- [Microsoft Research — From Local to Global: A Graph RAG Approach](https://www.microsoft.com/en-us/research/publication/from-local-to-global-a-graph-rag-approach-to-query-focused-summarization/)
- [Microsoft Research — DRIFT Search: Combining global and local search](https://www.microsoft.com/en-us/research/blog/introducing-drift-search-combining-global-and-local-search-methods-to-improve-quality-and-efficiency/)
- [Microsoft Research — GraphRAG dynamic community selection](https://www.microsoft.com/en-us/research/blog/graphrag-improving-global-search-via-dynamic-community-selection/)
- [Microsoft Research — LLMs Get Lost in Multi-Turn Conversation](https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/)
- [Microsoft HAX — Guidelines for Human-AI Interaction](https://www.microsoft.com/en-us/haxtoolkit/ai-guidelines/)
- [Microsoft HAX — Time services based on context](https://www.microsoft.com/en-us/haxtoolkit/guideline/time-services-based-on-context/)
- [Microsoft HAX — Support efficient correction](https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/)
- [Microsoft HAX — Remember recent interactions](https://www.microsoft.com/en-us/haxtoolkit/guideline/remember-recent-interactions/)
- [Microsoft HAX — Make clear why the system did what it did](https://www.microsoft.com/en-us/haxtoolkit/guideline/make-clear-why-the-system-did-what-it-did/)
- [Microsoft HAX — Convey the consequences of user actions](https://www.microsoft.com/en-us/haxtoolkit/guideline/convey-the-consequences-of-user-actions/)
- [Microsoft — Adaptive Cards for agent design](https://learn.microsoft.com/en-us/agents/design-guidelines/adaptive-cards-for-agent-design)
- [Apple HIG — Generative AI](https://developer.apple.com/design/human-interface-guidelines/generative-ai)
- [U.S. OPM — Job Analysis](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/)
- [U.S. OPM — Assessment and Selection（Task／responsibility／competency linkage 與 current SME）](https://www.opm.gov/policy-data-oversight/assessment-and-selection/)
- [U.S. OPM — Job analysis evidence and methodology FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/when-conducting-a-job-analysis-do-i-have-to-collect-ratings-eg-importance-required-at-entry-from-the-subject-matter-experts-sme-for-the-tasks-and-competencies/)
- [U.S. OPM — Six Steps to Conducting a Job Analysis for Multiple Grades](https://www.opm.gov/policy-data-oversight/assessment-and-selection/job-analysis/six-steps-to-conducting-a-job-analysis-for-multiple-grades/)
- [U.S. OPM — Delegated Examining Operations Handbook（Job Analysis 與 SME）](https://www.opm.gov/policy-data-oversight/hiring-information/competitive-hiring/deo_handbook.pdf)
- [iCAP — 職能發展及應用推動要點（職能基準審查與更新）](https://icap.wda.gov.tw/Quality/quality_specification.aspx)
- [NIST — AI Risk Management Framework Core](https://airc.nist.gov/airmf-resources/airmf/5-sec-core/)
- [W3C — PROV-O: The PROV Ontology（來源、衍生、修訂與失效）](https://www.w3.org/TR/prov-o/)
- [W3C — Web Annotation Data Model（quote／position anchor）](https://www.w3.org/TR/annotation-model/)
