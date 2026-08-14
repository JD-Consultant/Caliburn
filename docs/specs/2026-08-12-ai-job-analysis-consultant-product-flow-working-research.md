# AI 專業職務分析顧問：產品流程工作研究稿

- 日期：2026-08-12
- 狀態：Working Research；隨 owner 討論持續修訂
- 決策狀態：只記錄已確認的產品方向與待討論問題；不是 ADR，不授權 production 實作
- 優先順序：先以「產品如何像專業顧問工作」約束架構；核心 runtime 已選 LangChain 1.x＋LangGraph 1.2.x，RAG 明確留待後續另案研究
- 外部資料查核：截至 2026-08-13 可取得的官方／第一手資料整理；大廠做法是設計證據，不是免評測的產品決策
- Framework 現況：§9.7–§9.12 已完成 persistence／runtime、Context／Skills／provider、frontend transport 與四個中立產品目的的 conformance，主方案收斂為 LangChain 1.x＋LangGraph 1.2.x。§9.10 因重新沿用 Work Model／Focus／Progress／Proposal／Current JD 等舊概念切割 target state，已撤回並只保留為錯誤案例；ADR 0060 與 Task 10 successor ADR 0061、施工計畫必須以「可修訂理解、動態訪談重點、可信進度、待審文件變更、員工核准成品」等目的與 framework primitive 命名。選型先看效果、功能完整、可靠性與員工體驗；只有效果相當時才比較自寫量
- 相關研究：[`階段式 AI 職務分析顧問 runtime/framework 研究`](2026-08-12-staged-ai-consultant-runtime-framework-research.md) 只能在本產品流程核准後評估，不得反向用框架能力定義顧問流程

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
3. Task、Duty 與 OPKS 在核心流程中如何互相影響；未來 Reference 若加入，不能破壞哪些邊界？
4. 長訪談中哪些內容必須完整保存、哪些每輪必帶、哪些應按需取用？

### 0.2 不得再遺失的「同目的框架替代」硬規則（2026-08-13 owner 再確認）

本次升級不是替 Work Model、Focus、Progress、Proposal、Current JD、operation 等現行概念更換底層，也不是先保留這些名稱再找容器。研究與選型必須遵守：

1. **先把需求寫成中立目的**，例如「持續記住並修正目前理解」、「決定現在與稍後訪談什麼」、「呈現已知與缺口」、「讓 AI 提議、員工裁決」、「保存目前核准成品」、「讓處理可恢復」；不得以現行 class、資料表、module 或概念名稱當比較單位。
2. **框架元件只要完成相同目的就有資格整體替代**，即使名稱、資料模型、API、生命週期或操作方式完全不同；通過後，原概念可以消失，不必保留 facade、mirror 或相容 schema。
3. **優先研究截至決策日最新 stable／LTS、主流且有官方或第一手證據的框架與大廠作法**；star、行銷功能表與舊版本文章不能代替版本政策、production persistence、failure semantics 與實際 conformance。
4. **框架優先不是單一 runtime 優先**。先逐目的選出真正可承接的成熟元件，再評估能否組成較少、相容且可操作的組合；不得因先選 LangGraph、PydanticAI 或其他主 runtime，就把其餘目的全部降成自訂 state 欄位。
5. **自寫只允許補已證明的產品差額**。每一段保留程式都要列出框架缺少的具體行為、證據與驗收；「這是 domain」、「現行已有」或「名稱不同」都不是保留理由。
6. **真正不可被改寫的是產品效果與權威條件**：專業職務分析方法、員工原話／更正不遺失、AI 不得偷改核准內容、員工能理解焦點／進度／缺口，以及最後產出可靠職務說明書。這些也可以借成熟框架與標準實現，不等於保留現有元件。
7. **conformance 必須驗同目的結果，不只驗能否儲存欄位**。把 `work_model`、`focus` 或 `proposal` 放入 framework state，只能證明容器可用；除非 framework primitive 已承接其更新、持久化、恢復、互動與失敗生命週期，否則不能宣稱該目的已被替代。

因此 §9.5 的目的層候選盤點仍有效；§9.10 把候選過早壓回舊概念名稱的 target state 已失效。§9.7–§9.9 的工程探針與 §9.12 的四個目的驗證共同構成目前選型證據：LangGraph typed state／checkpoint／Store／routing／interrupt 與 LangChain model／middleware／Skills 已證明能承接通用機制，新產品只保留職務分析方法、員工權威與框架尚未提供的最薄政策。不得再把舊名稱搬回 target architecture，也不重做已關閉的市場調查。

下列內容仍留給 ADR／plan 與施工 gate，不由產品方向段落假裝已完成：

- LangChain／LangGraph 的 production schema、framework table setup、migration 與版本 pin；
- context、source retrieval、tool 與 Skill 的最終 typed contract；
- RAG／Reference runtime 的串接；owner 於 2026-08-14 改為本次核心升級不做，維持隔離，日後另行研究與決策；
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
- 本次核心升級的第一版方法至少涵蓋「盤點工作、深入故事、釐清 Task 邊界、整理 Duty、分析 O／P／K／S、完成度／反方收尾檢查」，並以可按需載入的 Skills 承接；它們不是多個人格化 Agent，也不是固定通關階段。Reference challenge 保留為後續 RAG 階段，能力級別與 A 則等研究與 Skill 完成後再加入。
- 一輪可依焦點同時載入一個或數個相關 Skill。為讓模型能發現回答中的意外線索，第一版九個方法的短 metadata catalog 可以常駐；只有實際需要的方法才完整讀入 `SKILL.md`，未使用的 Skill 正文不進當輪 prompt／context。這是 Agent Skills progressive disclosure，不等於每回合執行全部方法。
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
- 員工可以跳過、切換工作、補充新故事或返回先前內容；想休息時只要停止傳訊息或關閉頁面，下次開啟同一文件自然續談，不需要「暫停訪談」或「結束本輪」操作。
- AI 不因員工改道而遺失尚未處理的焦點與線索。

### 2.4 AI 只提出變更，員工決定正式內容

- AI 對員工工作的目前理解可以隨新證據形成、修正或撤回，但它不是員工已核准的職務文件。
- 只要是 LLM 產生、準備寫進職務文件的內容，都先形成**待審文件變更**；員工接受或修改後接受，內容才真正進入核准文件。這項產品語意不要求新程式沿用 `Proposal` 名稱、class、table 或 API。
- 員工可接受、修改後接受、拒絕或暫不處理待審變更，也可以直接編輯自己的文件；員工直接編輯不需再審核自己的修改。
- 第一版 LLM 可處理職務名稱、工作描述、Duty、Task、重新分組、排序與 O／P／K／S；能力級別與 A 暫不交給 LLM，因為尚未完成對應研究與 Skill。既有欄位、員工直接編輯與匯出語意仍保留。
- 依 ADR 0052，`職能基準代碼`／`職類別代碼` 由 iCAP 計畫執行單位配發，產品保持空白、不得讓員工或模型填寫；`職業別`／`行業別` 的名稱與分類代碼可由員工填寫或日後由可信分類資料帶入，但 LLM 不得自由生成。
- 先前接受的內容仍可被新證據重新挑戰，但再次修改仍需員工決定；AI 永遠沒有直接寫入核准文件的路徑。

### 2.5 Task 與 Duty 都會隨訪談演化

- 分析初期允許 Task 尚未歸入 Duty。
- 初期可有暫定責任區域協助 coverage 導航，但不得把它當成固定 Duty 盒子。
- 隨 Task 增加、合併、拆分或改變邊界，Duty 可以改名、重新分組、合併或拆分。
- 不要求先完成 Duty 才能理解 Task，也不要求 Task 一被員工接受後就永久固定。

### 2.6 單一匯出，但缺口必須可見

- 產品只有一個匯出概念，不額外建立草稿／正式兩套資料或文件生命週期。
- 匯出前列出尚未分析、待補訪、待員工決定、結構問題與已保留未知。
- 員工可以在看過缺口後強制匯出。
- 強制匯出不會自動接受待審文件變更、補造 OPKS、隱藏孤立 Task 或改變員工核准文件。

### 2.7 員工回答先成為 durable source，AI 失敗不應讓原話消失

- 員工送出的回答先以穩定 input event／turn identity 保存為來源記憶，再交給 AI 分析；它不是等模型成功後才附帶寫入的欄位。
- provider timeout、拒答、parse、schema 或 verifier 失敗時，該回答仍保留並標示尚未成功分析；員工不必重新輸入，也可以關閉頁面後再回來。
- 重試必須沿用同一個 input event，不重複建立來源；每次實際 provider 嘗試另有 attempt identity。失敗期間可修訂理解、待審文件變更與核准文件都不得改變，但已完成的 model／tool result、verification report 與成本等**執行證據**可以先成為可恢復 artifact，避免 crash 後盲目重打 provider。
- 這項產品裁決取代 2026-07-30 最小完整迴圈中「模型失敗時 Journal 完全不變、只由 Web 保留草稿」的舊假設；實作前仍須以 ADR／plan 補齊交易、idempotency 與 migration 邊界。

### 2.8 一個員工回合可包含受限的內部工作，但仍由同一位顧問負責

- 一次員工送出與一次模型 inference 不是同一個概念；產品以一個可保存、可重試的 application run 承接一個員工回合。
- 預設走同一位顧問的最短可行 bounded-agent 路徑：不需工具時一次 inference 直接回 compact typed result；需要按需載入 Skill 或找回員工原話時，由同一 agent loop 呼叫唯讀工具後再回 compact result。provider-facing wire 與 rich application result 分離，不能把 framework state／rich schema 原樣當 provider contract；仍是一個 application run、同一模型 profile 與同一顧問責任，不是 planner／writer 多 Agent。
- 整個員工回合仍以三次 inference、兩波唯讀補查為 hard ceiling；只有 compact wire＋四個 production tools 的 exact conformance 仍失敗，才在同一 run 內拆 tool-enabled analysis 與 tool-free finalization。不得為了「可能更好」固定增加 finalization、critic、extractor 或 OPKS 呼叫。
- 載入 Skill 不等於另開人格化 Agent，也不必然增加一次模型呼叫；同一位主要顧問仍擁有最後語意整合與員工回覆。
- application 決定 scope、工具權限、最大步數、token／時間／成本與停止規則；不得讓模型自由無限循環。
- 員工只看到一個連貫結果、必要的待審文件變更與一個主要問題；內部 Manifest 可供重播與除錯，但不把 chain-of-thought 當成產品輸出。

### 2.9 Reference challenge 的後續產品原則（本次不實作）

Owner 於 2026-08-14 決定本次核心升級不串接 Reference／RAG；本節只保存日後重新討論時不得遺失的產品原則，不是目前 plan 的功能清單：

- 日後 Reference 內容只使用 repo 已有的 iCAP 資產；不納入 O*NET、一般網路搜尋、公司文件、表單或既有 JD。
- 一般檢索命中只是技術候選；只有真正被拿來詢問員工、影響訪談焦點／待審文件變更，或形成 coverage 判斷的內容，才成為持久的 Reference challenge。
- challenge 要保留被挑戰的工作範圍、提出原因、來源／版本／引用、員工回答連結、match／partial／no-match／conflict／unknown／deferred 裁決，以及後續是否仍有效。
- 同一個語意主張即使出現在多個 iCAP 片段，也只問一次；支持片段可以增加，但不得把同義公版內容包裝成新的問題反覆詢問。
- `no-match`、拒絕與其他已裁決結果必須被記住；沒有新員工 evidence、實質來源變更或工作邊界改變時，不得只因重跑檢索、更換模型／embedding 或分數變動而重開。
- Reference challenge 的裁決仍不是核准職務文件；它只能更新有來源依據的目前理解，正式內容仍須經員工文件變更審核。

### 2.10 職務資料可送外部模型，但產品權威留在本地

- Owner 於 2026-08-13 確認：員工訪談、JD、Task／Duty、OPKS 與其他職務分析內容都可送給外部 LLM；若日後加入 Reference，也適用相同外傳政策。第一版不做欄位遮罩、敏感資料分類、本機模型模式或逐回合同意。
- 產品只需在設定／開始使用時清楚告知內容會送往外部 AI 服務，不以每輪彈窗打斷訪談。
- 「可以送」不等於每輪傳入全部內容；LangChain context middleware 仍依目前訪談目標與資訊價值選擇最小充分 context，避免成本、延遲與無關資訊干擾。
- 員工原話與更正、可修訂理解、待審文件變更、核准文件、可信進度與恢復依據必須由**本機產品控制的唯一 framework-backed authority**保存；不得因舊系統曾把它們拆成不同元件，就重建同名 store。provider／gateway 的遠端 conversation state、logging 或 cache 不得成為唯一權威。
- 第一版不要求 ZDR，但不主動加入模型訓練、資料折扣 logging 或完整遠端 prompt／response logging；模型與 provider 路由必須明確，不能以不透明 fallback 偷換模型。

### 2.11 框架承接工程機制，Caliburn 保留產品語意（2026-08-13 已確認）

Owner 已確認：保留的是「記住員工原話與更正、持續修訂目前理解、選擇訪談重點、呈現可信進度、讓員工審核 LLM 文件內容、保存核准成品」等目的，以及 Task／Duty／OPKS 方法、deterministic verifier 與員工 authority；**不保留** `Source`、`Work Model`、`Focus`、`Progress`、`Proposal`、`Current JD` 等舊元件名稱、schema 或生命週期。判斷原則改為：

- 框架可以取代或包裝通用的 model／tool interface、structured output、checkpoint／resume、Skills progressive disclosure、context lifecycle、token／usage、tracing、欄位與模型形狀驗證；
- 成熟標準可以改善現有 domain 元件的資料形狀，例如 quote anchor 可借用 W3C Web Annotation 的文字引用與位置選取模型，lineage 可借用 W3C PROV 語彙；
- 現有 Pydantic、SQLAlchemy 與 PostgreSQL 本身就是框架／平台，應先評估是否能以 validator、constraint、transaction、versioning 與 ORM 能力減少自寫 plumbing，再決定是否增加新套件；
- memory／agent／workflow 框架在通過同目的 conformance 後，直接承接可修訂理解、動態焦點、待處理問題、進度、文件審核、核准成品與 per-document durability；舊 store、writer 與 projection lifecycle 必須刪除，不能建立第二份可寫權威；
- framework HITL、durable state、checkpoint、routing 與 command 可承接待審文件變更及必要澄清的通用生命週期；Caliburn 只補「什麼內容需審核、何時阻塞哪個分支、什麼命令可改核准文件」等產品政策，不保留舊 `Proposal` domain object 或 authority seam 實作；
- 採用標準是語意覆蓋、可靠度、維護成熟度、遷移成本、可替換性與是否減少總維護面，不是套件功能數或刪除行數；
- 目前推薦先找能覆蓋最多核心責任的**單一主 runtime**，再只為它確實缺少的能力補一個成熟元件；若一套框架能完整承接多項責任且讓舊機制退場，功能重疊是替代證據，不是扣分。遷移邊界依 §2.15 採 AI 顧問子系統受限 Big-bang，但不擴張成整個 Caliburn 的 event-sourcing／agent-platform 重寫。

因此產品流程仍是本文定義的顧問流程；framework 只能忠實承接它，不能因框架已有 `memory`、`state`、`approval` 或 `agent` 類別，就重新定義員工回合、資料權威、進度或正式修改權。

這裡的「保留」指**保留目的、專業方法、產品語意與可驗證的不變量，不是保護目前自寫的 class、module、schema、資料表、舊概念名稱或 orchestration code**。新架構一律使用產品目的與 framework primitive 命名；舊名稱只可出現在歷史診斷、刪除帳本與 migration 說明。後續施工必須逐項回答「成熟元件承接哪項產品責任、Caliburn 還要補什麼最薄政策、能刪除哪些舊碼、如何證明語意不變」，不能把舊元件換個容器後宣稱完成替代。

### 2.12 一個員工回合採三層持久化，不把 network call 偽裝成資料庫交易（2026-08-13 審核後確認）

本節把「員工原話先保存、衍生結果整包提交」說得更精確。它不是只有兩個模糊的 save，也不是把 provider call 包在長時間 PostgreSQL transaction 裡：

1. **Source acceptance transaction**：先以 client／application 提供的穩定 `input_event_id` 保存員工原話、speaker、document scope、canonical payload hash 與 processing status，再回報「回答已保存」。相同 ID＋相同 hash 回既有結果；相同 ID＋不同 hash 是 idempotency conflict。
2. **Execution durability**：transaction 外執行 context assembly、Skill、tool 與 model；每個不可免費重做的重要結果以 run／attempt checkpoint 或 immutable artifact 保存，例如 resolved execution snapshot、context-selection receipt、tool result、provider result、usage、parse／verification report。這些是恢復與診斷依據，不是可修訂理解、待審文件變更或核准文件。
3. **Semantic commit transition**：deterministic framework node 把通過檢查的候選編成一份概念上的 `VerifiedCommitPlan`，重讀 document、驗 generation／read-set，並在**一個可證明原子的 framework transition** 中一起成立可修訂理解、動態訪談工作、可信進度、待審文件變更、可見 consultant turn 與 idempotent result receipt。LangGraph checkpoint 是本次已選定的唯一 semantic-state owner，不再另建同目的 PostgreSQL aggregate writer。這批業務變更要嘛全部可見，要嘛全部不成立；核准文件仍完全不動。
4. **Independent employee decision command**：員工日後接受、修改後接受、拒絕或延後待審文件變更，是另一個有自己 idempotency／stale check 的 framework command；只有它能改變核准文件。一般文件審核不得依賴仍在執行中的 model call、暫時 interrupt 或 process memory；durable thread 本身必須能獨立承接審核與日後恢復。

因此「原子」描述的是**已驗證業務 commit plan 的本機權威可見性**，不是要求整個 LLM run 只有一次 commit，也不先指定一定由自寫 repository 或 framework checkpoint 完成。provider 已成功但 process 在 semantic commit 前崩潰時，恢復流程應讀取已保存的 provider／verification artifact；若 authority snapshot 仍相符，可以繼續 verify／commit，不應自動再付一次模型費。若 snapshot 已 stale，舊結果可保留作執行證據，但不得硬套到新 state，必須依 run policy 重新組裝或重跑。

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
- 優先保留已研究驗證的職務分析、Task boundary、Duty grouping、OPKS 方法，以及來源追溯與員工 authority；Reference challenge 方法保留為後續 RAG 階段的產品研究，不進本次施工範圍；
- 現有 Focus、Work Model、Current JD、gap、Proposal、Context、memory、operation、provider adapter 與 verifier 等舊實作全部是框架替代或刪除候選，不是 target architecture 名稱；
- 若成熟框架能完整承接同一目的、維護性更好且不建立第二份權威，優先移植、包裝或替換，不因「這是 domain 元件」就假設底層必須自寫；
- 目標流程不因現行系統暫時缺少 Duty hypothesis、Task reassignment、Duty Proposal、typed composite changeset 或按需 OPKS Skills 而縮小；
- 與 Accepted ADR 衝突的目標改變必須由 successor ADR 明確取代後才可施工，不能偷偷繞過，也不能反過來用舊 ADR 凍結已由 owner 確認的新產品方向。

為防止選型再回到保護舊系統的前提，後續任何「狀態重疊」判定都必須明列**同時存在的兩個 write owner**。若舊 mechanism 會隨切換刪除或降為可重建 read projection，新框架覆蓋相同責任是 `Replace` 證據，不是重疊風險；不得再以「現行 Work Model／Proposal／Current JD 已存在」作為扣分理由。

進入 plan 前必須建立「目標能力／現況／框架候選／`Replace|Wrap|Retain`／仍需自寫語意／successor ADR／驗收情境」差距矩陣。這張矩陣以產品責任為列，不以舊 module 為列，避免框架研究退化成替舊系統逐檔換套件。

### 2.15 AI 顧問子系統採受限 Big-bang，一次切換但不重寫整個 Caliburn（2026-08-13 已確認）

2026-08-13 repo 稽核顯示，目標升級會同時改變 consultation runtime、Context／memory、Focus／agenda、Work Model、Duty、Proposal、OPKS Skills、durable run 與對應 API／UI。若逐一包裝舊 Task Analysis／OPKS child 元件，必須長期維護兩套狀態語意、轉接契約與一次性 adapter，橋接成本很可能高於直接建立新垂直切片。Owner 確認可在隔離 worktree 完成新系統後再切換，因此採：

1. 在隔離 worktree 內建立新的完整 AI 顧問垂直切片；中間 commit 不需要把半套新流程接到主工作面；
2. 將 AI 顧問子系統視為一次重寫與一次切換的邊界，不替舊 Task Analysis／OPKS child 逐元件建立長期相容層；
3. 新 runtime 直接依本文產品語意、成熟框架與新的統一 contract 設計；完成後一次切換 API／Web，並刪除被取代的舊 AI runtime；
4. 不做 production 雙軌、雙寫或永久 façade；只有文件 catalog、核准文件 projection 與 deterministic 匯出等真正穩定 seam 才可成為切換交界；
5. PostgreSQL、SQLAlchemy、Pydantic、員工直接編輯與文件 authority 原則、deterministic export／XLSX 優先保留或深化；隔離 RAG 資產只維持 ADR 0057 現況，不在本次核心升級中深化或接線；
6. **Owner 於 2026-08-14 改為本次核心升級不做 iCAP Reference／RAG 串接。** 現有 PDF／OCS／indexer／embedder／Qdrant bounded context 繼續依 ADR 0057 保留並隔離，不新增 current API／Web consumer、query contract、composition-root dependency 或預設啟動服務；日後需要時再另行研究、討論與開 successor ADR。這項最新裁決取代本節先前把 RAG 列為同次 v1 completion gate 的暫定結論；
7. Owner 於 2026-08-13 確認目前沒有必須保留的真實 JD 或訪談資料，因此新系統採 fresh-schema hard cut：不遷移舊 Work Model、agenda、Proposal、checkpoint、turn 或 Current JD，不寫 compatibility converter，也不雙寫；這些名稱只描述被刪除的舊資料，開發資料庫依新 migration head 重建；
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

**與目標設計的關係**：不新增 `InterviewPlan`、第二份問題清單或固定問題表。開場內容由版本化顧問方法與 LangGraph durable state 的目前文件、訪談目標、待處理工作與進度 read projection 組成；之後仍由 §3.3 的動態訪談重點與 §4 的可解釋進度更新。它只建立員工的預期，不限制顧問只能依開場順序行動。

**研究選項與裁決**：

1. **不另外說明**：直接開始角色定位與工作盤點；畫面較短，但員工要從後續互動自行推測流程。
2. **一次性的簡短導航（採用）**：第一次開始時用 3–4 句說明「先大致盤點工作，再一次深入一個焦點；新線索會先記住，Task／Duty／OPKS 會隨證據調整；正式修改都要你接受；你可隨時離開並在下次接著談，系統會顯示目前已知範圍、缺口與下一步」。隨後立刻開始第一個自然問題，不要求員工核准一份計畫。
3. **先產生並核准完整訪談計畫**：員工可預覽所有預定主題，但容易形成固定階段與假分母，增加開場負擔，也會讓後續動態重整看起來像偏離計畫；目前不建議。

**產品裁決**：owner 於 2026-08-13 確認採方案 2。它只建立員工對訪談方式、動態重整、核准權與可恢復性的預期；不建立完整訪談計畫、不形成固定問題分母，也不要求開場核准。實作文案與視覺形式留到目標架構／Web 體驗關卡，不在此鎖定。

#### 3.1.2 訪談可自然離開與續談，不建立「暫停／結束本輪」狀態（2026-08-14 owner 修正確認）

LLM 回答完後，產品自然等待下一則員工訊息。員工想繼續就再傳訊息；想休息便停止傳訊息或直接關閉頁面，下次開啟同一文件時從原本對話、訪談重點、目前理解、缺口與待審文件變更繼續。員工不需要取得「本輪可停」許可，也不需要按「暫停訪談」「結束本輪」或建立返回點。

系統只需顯示執行事實，例如「回答已儲存」「AI 正在分析」「分析失敗，可重試」。若員工在 AI 完成前關頁，原話仍已保存；重新開啟時顯示既有完成結果或可恢復／重試狀態。必要澄清與結構性待審變更可以使依賴它的分析分支等待，但永遠不阻止員工離開。

不新增 `PauseSession`、`ResumeBrief`、專用返回 wizard、固定離開天數門檻或開頁即觸發的模型呼叫。若日後真實使用顯示員工經常無法接回脈絡，可從 durable state 增加短摘要 projection；目前不把它做成新生命週期。[OpenAI 官方 Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)、[Google ADK 長流程示例](https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk/)與 [Microsoft HAX — Remember recent interactions](https://www.microsoft.com/en-us/haxtoolkit/guideline/remember-recent-interactions/)支持的是持久狀態與跨互動連續性，不是要求使用者操作暫停狀態。

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

「新線索看起來重要」本身不足以立即打斷。判斷標準是它是否**現在就阻塞或推翻當前合法分析**，不是它最終可能有多高價值；高價值但不阻塞的線索先提高 framework pending-work item 的優先序，在目前訪談重點暫時收束後再選取。

研究依據與轉用（最近查核：2026-08-13）：

- [OpenAI 官方 Model guidance](https://developers.openai.com/api/docs/guides/latest-model)要求提供目前目標、相關 context、限制與核准邊界，並在重要歧義時提問；同時應讓安全且在 scope 內的工作持續，不因重複 approval 指令造成不必要停頓。這支持「一般線索不中斷，重要歧義才停」。
- [Anthropic — Trustworthy agents in practice（2026-04-09）](https://www.anthropic.com/research/trustworthy-agents)明確把過度詢問與一律自行假設都列為問題：可自行解決的缺口繼續處理，只有使用者才能決定的偏好、意圖或重大不確定才交還使用者。這支持分級處理，而不是每個新線索都切換。
- [Microsoft HAX — Time services based on context](https://www.microsoft.com/en-us/haxtoolkit/guideline/time-services-based-on-context/)要求依使用者當前 task／attention 決定何時打斷；[Support efficient correction](https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/)與[Convey the consequences of user actions](https://www.microsoft.com/en-us/haxtoolkit/guideline/convey-the-consequences-of-user-actions/)則支持讓員工容易修正，並立即回饋「已保存、稍後會怎麼處理」，而不是靜默停放。
- [U.S. OPM — Assessment and Selection](https://www.opm.gov/policy-data-oversight/assessment-and-selection/)要求 job analysis 保存 Task、角色／責任、competency、資源與工作情境的 linkage，並由具有直接、最新工作經驗的 SME 提供資訊。這支持責任與 Task 邊界矛盾要向員工釐清，不能由 Reference 或模型猜測。

可轉移限制：OpenAI／Anthropic 資料是通用 agent 行為，Microsoft HAX 是跨產品人機互動指引，OPM 說明職務分析證據與 SME，但沒有規定 LLM 訪談的 topic-switch 演算法；目前也沒有公開研究直接比較繁中單一員工職務訪談的三種切換策略。因此上述三級模型是將共同原則套入 Caliburn「一個主要訪談重點、完整吸收回答、員工 authority、可恢復 pending work」後的產品裁決，不得宣稱已由外部 benchmark 證明效果最佳。

當目前證據已足以形成待審文件變更、確認 `no-op`、留下具體 gap，或以有理由的 unknown／not applicable 暫時停止時，訪談重點才算暫時收束。這不是永久完成；後續證據仍可重新開啟。

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
3. 維持一個前景訪談重點與共同、可修訂的工作假說；
4. 根據回答內容、當前焦點與仍存在的 gap，按需載入零個、一個或多個分析 Skill；
5. 各 Skill 使用同一批證據形成 typed findings、候選、gap 或重新開啟既有結論的理由，不直接修改核准職務文件；
6. 對 Task、Duty、O、P、K、S 的分析結果做共同對帳，處理拆分、合併、重新分組與 linkage 變化；
7. 決定本輪的單一清楚下一步：繼續同一訪談重點、整理或提出待審文件變更、保存旁支線索、切換重點，或提示目前資訊已接近足夠；
8. 對員工呈現目前訪談重點、必要摘要、待審文件變更與一個主要問題，不暴露內部 Skill 編排為使用者必須理解的流程。

例如，員工描述某項工作時同時說出主要成果與驗收方式，當輪可一起使用 `task-boundary`、`output` 與 `performance-indicator`；若沒有能力需求的證據，就不載入 `knowledge`／`skill`。若 Indicator 顯示原 Task 包含兩種不同成果，也能回頭提出 Task 拆分。

這是產品的語意循環。2026-08-13 已確認其高階執行形狀為「預設單次 inference 快速路徑＋必要時受限補查／再判斷」：不固定每輪多呼叫，也不允許自由 Agent loop。至於同一 run 內的 tool loop、少數 specialist、final submit contract 與框架映射仍是實作選擇；不得反過來因框架或呼叫形式改變上述顧問責任。

### 3.7 小段落收束、重整與文件變更審核（2026-08-14 名稱與 authority 語意再確認）

完成一小段有意義的訪談後，AI 可以整理：

- 現在對工作故事的理解；
- Task 是新增、補充、重疊、需 merge／split，或只是工具／步驟；
- Duty 是否需要建立、改名或重新分組；
- 哪些 OPKS 已有依據、哪些仍有 gap；
- 哪些變更已足以形成待審文件變更；
- 哪些線索先保留到後面。

不要求每回合都產生待審文件變更；`no-op`、繼續追問或只保存線索都是正常結果。

文件變更審核採「有意義檢查點」節奏，不採每句回答都要求核准，也不等到整份訪談結束才一次處理：

- 一般補充先更新 AI 的可修訂理解，必要時以白話摘要校準，不立刻跳出正式核准；
- 理解仍不確定時繼續追問，不把猜測過早包裝成正式變更；
- 當證據已足以新增或修改第一版 LLM 支援的職務名稱、工作描述、Duty、Task、排序、重新分組或 O／P／K／S，才形成待審文件變更；能力級別與 A 暫不由 LLM 分析或產生；
- 若結構變更會影響後續訪談方向，例如 Task 拆分、Duty 重組或責任歸屬改變，應優先交員工決定，避免在錯誤假說上繼續深入；
- 員工要求 AI 協助重寫正式內容時，可以立即形成待審文件變更；員工自己直接編輯則直接依員工 authority 寫入，不繞一圈審核自己的修改；
- 同一批證據造成多個關聯變更時，應以共同理由整理為同一個審核脈絡，不讓各 Skill 分別跳出互不相干的卡片。

關聯變更採「共同脈絡、依相依性分組」：

Owner 於 2026-08-13 明確選擇**可編輯的 review bundle＋必要的原子子群組**，不採每個欄位各跳一張卡，也不把整批變更綁成全收全退。`review bundle` 是員工看到的一次審核脈絡；底層 framework-backed typed changeset 仍保存每項操作、目標、before／after、來源、相依關係與 stale/read-set。這是產品契約，不要求保留舊 `Proposal` class／table；成熟 framework primitive 直接承接持久化、恢復與 command lifecycle。

- 員工先看到這組建議的共同理由、來源證據與整體影響；
- 可以獨立成立的文字、名稱或 OPKS 候選，允許逐項接受、修改或拒絕；
- 只有必須一起成立才不會破壞結構的操作，才組成不可拆的子決策，例如建立 Duty 並完成必要的 Task reassignment；
- 員工修改任一項後，系統重新檢查剩餘變更是否仍成立，不提交失去前提或留下無效 linkage 的內容；
- 分組依據是 domain dependency，不是由哪一個 Skill 產生，也不把整批不相關的變更綁成全收全退；
- 拒絕、修改與暫不處理都要留下可追溯裁決；若沒有新員工來源、實質工作邊界變化或其他會推翻原理由的新證據，AI 不得換個措辭重複提出同一變更。

#### 3.7.1 待審文件變更依「是否改變後續分析前提」分級阻擋（已確認）

不是所有待審文件變更都中斷訪談。阻擋判斷依它是否為目前或後續訪談重點的語意前提，不只看 action 名稱：

- Task merge／split、Duty 建立或重組、Task reassignment、本人／他人責任與其他會改變分析邊界的結構性變更，若後續問題、OPKS linkage 或 Duty grouping 依賴該結果，先暫停受影響的分析，請員工接受、修改、拒絕或改道；
- 改名、文字潤飾、排序與不改變分析前提的一般 OPKS 補充，可以維持 pending，訪談繼續；
- 「阻擋」只作用於依賴該未決前提的分析分支，不封鎖整份文件、其他不相關工作、直接編輯、文件變更審核或匯出決策；
- 員工暫不處理結構性變更時，framework state 保存 blocked reason 與尚未完成的工作，改選不依賴它的訪談重點；若沒有可安全前進的重點，才明確提示需要先決定；
- 待審變更解決後，系統重新檢查其下游候選、gap、linkage 與待處理工作；不得把決定前的推論直接當成仍然有效，也不得因拒絕而偷偷採用同一假設繼續分析。

UI 與進度投影應說明「哪個分析目前被什麼未決前提擋住」，而不是只顯示一個無法理解的全域 blocked 狀態。

#### 3.7.2 可修訂的 AI 目前理解採觸發式校準，不把每次假說更新變成核准（已確認）

AI 的目前理解是隨證據持續修正的分析狀態；員工不需要逐筆審核每一個內部假說變化。但若 AI 長時間在錯誤理解上繼續追問，後面的訪談重點、Duty grouping、OPKS 與待審文件變更都可能一起偏掉。因此產品需要「理解校準」，但它和正式文件變更審核是兩種不同的互動。

平常的低影響理解更新可以在 framework state 內累積，並在畫面上隨時可查看；只有下列有意義時機才由 AI 主動顯示校準卡：

- 準備收束或切換目前焦點；
- 即將提出結構性文件變更，或後續問題將依賴某個尚未校準的工作假說；
- 新回答與既有理解矛盾，或涉及本人／他人責任、決策權、低頻高影響工作等高風險邊界；
- 久後恢復，或 AI 的目前理解自上次向員工顯示後已有重大修訂；
- 員工主動要求查看或修正 AI 的目前理解。

校準卡應以員工看得懂的白話呈現，而不是暴露內部 schema：

- 現在談的是什麼、AI 為何這樣理解；
- 一段簡短的目前理解，必要時列出 Task／Duty／OPKS 關係；
- 可展開的員工原話與修訂 lineage；本階段沒有公版 Reference 來源；
- 仍不確定、互相衝突或尚未訪談的部分；
- AI 建議的下一步，以及這張卡所依據的 durable state revision。

員工至少可以選擇「正確，繼續」、「直接修正」與「目前不確定／稍後再談」。其語意必須固定：

- 「正確」形成員工確認的來源事件，可提高或補強目前理解，但**不等於接受正式文件變更**；
- 「直接修正」保存新的 durable employee source，由 framework transition 修正、反駁或取代相關假說；若因此需要改核准文件，另行形成待審文件變更；
- 「目前不確定」保留明確 gap 或返回點，不得被解讀為肯定或否定；
- 提交時若 state revision 已過期，應重新組裝校準內容，不把對舊理解的回覆套到新狀態。

因此產品不設「核准整份 AI 理解」，也不每回合跳 modal。理解校準是防止 AI 假說漂移的可見修正點；文件變更審核才是 LLM 內容進入核准文件的 authority gate。

#### 3.7.3 「目前理解」採常駐投影＋情境式校準卡（已確認）

員工不應只能從長對話猜 AI 目前怎麼理解，也不應被迫在每一輪停下來審核。第一版採兩層互動：

1. **常駐但不打斷的「AI 目前理解」側欄**：跟著目前訪談重點更新，可收合；窄畫面改成可隨時叫出的 drawer。它是 durable consultant state 的可重建投影，不是第二份資料、不是核准清單，也不等於員工核准文件。
2. **只在 §3.7.2 trigger 發生時出現的校準卡**：預設放在對話流內，不用 modal；只有受未決前提影響的分析 branch 需要阻擋時，才要求先處理。

側欄預設只顯示與員工當前任務有關的高訊號內容：

- 目前訪談重點、為何現在談這件事，以及「探索中／需要釐清／足以形成文件變更／受未決前提阻擋」等可行動狀態；
- 2–4 點白話的目前理解，必要時顯示 Task／Duty／OPKS 關係；
- 最重要的未確定、矛盾與尚未訪談項目，超過上限只顯示數量並可展開；
- 本輪先保存、稍後再談的新線索或其他 Task；
- 可展開的員工來源、修訂關係與最後更新時間；
- 一個隨時可用的「修正目前理解」入口。

不要顯示沒有經過產品驗證的 LLM 數字信心或假精確的完成百分比。改用有明確資料語意的標籤，例如「員工已確認」、「依員工說法暫定理解」、「只有 AI 推論、尚未向員工確認」、「來源矛盾」與「尚未訪談」。最後更新也不得偽裝成最後確認。

校準卡預設只顯示**自上次校準後有意義的變化**及其影響，不重複整份目前理解。它至少要說明：

- AI 新增、修正或不再採用哪一項理解；
- 依據哪些員工原話、修訂或 AI 推論，以及為何現在需要確認；
- 若不處理，哪個下一步、Duty grouping、OPKS 或待審文件變更會依賴它；
- 「正確，繼續」、「直接修正」、「目前不確定／稍後再談」三種固定動作。

一般重點切換、久後恢復或大幅修訂屬 soft checkpoint：員工可略過、稍後處理，framework 保存未校準狀態。矛盾、高風險責任邊界或結構性文件變更的必要前提屬 branch-blocking checkpoint：只暫停依賴它的分析，不封鎖整份文件。相同內容未變時不得重複跳卡；相關變更應合併呈現，員工主動要求則不受節流限制。

員工修正後，介面要立即回報「已更新什麼、哪些後續分析會重算、核准文件是否仍未改變」，並同步刷新側欄。這是對修正效果的可見回饋，不是揭露模型 chain-of-thought；解釋只提供來源、重要推論與影響。所有 action payload 都視為不可信輸入，由 server 依 document、revision、generation／read-set 與 domain invariant 驗證。

#### 3.7.4 更正後的影響傳播範圍（2026-08-13 owner 已確認）

**問題**：既有裁決已決定最新有效員工更正優先、舊來源保留、AI 目前理解可修正而核准文件未經員工決定不變；但尚未明確選擇一則更正如何傳播。只改眼前欄位可能留下依賴舊說法的 Duty／OPKS／待審文件變更；每次整份文件重算則浪費成本，還可能讓無關且已確認的內容無故漂移。

**直接來源與實際支持**（最近查核：2026-08-13）：

- [OpenAI Cookbook — Context Engineering for Personalization](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization/)示範 local-first structured state、session／global notes、dedupe／conflict resolution 與明確 precedence，範例順序是 latest user input → session override → global default；它並指出 state-based memory 比鬆散 retrieval 更適合需要連續性、更新與衝突處理的工作。這支持「更正要進結構化目前狀態並有優先規則」，不直接定義 Caliburn 的 Task／Duty／OPKS 失效演算法。
- [Microsoft Research — LLMs Get Lost In Multi-Turn Conversation](https://www.microsoft.com/en-us/research/publication/llms-get-lost-in-multi-turn-conversation/)在超過 20 萬段模擬對話與六類生成任務中觀察到，模型常過早採用前期假設並持續依賴，發生錯誤轉向後不容易恢復。這支持不能只把更正追加在長聊天末端、期待模型自行修復所有下游理解。
- [Microsoft HAX — Convey the consequences of user actions](https://www.microsoft.com/en-us/haxtoolkit/guideline/convey-the-consequences-of-user-actions/)要求立即更新或說明使用者動作將如何影響 AI 後續行為。這支持更正後回報「哪些理解已改、哪些分析會重算、正式 JD 是否仍未改」。
- [W3C PROV-O](https://www.w3.org/TR/prov-o/)提供 primary source、quotation、derivation、revision 與 invalidation 等來源關係，可作 lineage／修訂語彙參考；它支持保留前後版本與衍生關係，但不是職務分析資料模型或 incremental recomputation engine。
- [U.S. OPM — Job Analysis FAQ](https://www.opm.gov/frequently-asked-questions/assessment-policy-faq/job-analysis/when-conducting-a-job-analysis-do-i-have-to-collect-ratings-eg-importance-required-at-entry-from-the-subject-matter-experts-sme-for-the-tasks-and-competencies/)要求描述 work behavior、Task、work product、KSA 及彼此關係，且保留支持重要性的 evidence。這支持一則責任／工作行為更正可能跨 Task、Output、Indicator、K／S linkage 傳播，不能只作文字 patch。

**可轉移限制**：OpenAI Cookbook 是 travel concierge 的實作示例，不是 API 保證或職務分析研究；Microsoft 多輪研究使用模擬對話與生成任務，沒有比較本產品三種重算策略；HAX 是通用 UX；PROV-O 只定義 provenance 語彙；OPM 主要面向正式甄選職務分析。以下方案 3 是把共同原則套入 Caliburn 的穩定 ID、evidence linkage、可修訂理解／核准文件分權與員工文件審核後的產品設計，不得宣稱已由外部 benchmark 證明成本或品質最佳。

**研究選項與裁決**：

1. **只修員工指出的欄位**：最快，但可能保留依賴舊責任邊界的 Task、Duty、OPKS、gap、待處理工作或待審文件變更；不採用。
2. **每次更正都重建整份目前理解**：最不容易漏掉遠端影響，但成本、延遲與無關內容漂移最高，也會讓員工難以理解為何一個小修正改動整份文件；不建議作預設。
3. **來源錨定＋依賴導向失效／重算（採用）**：更正先成為新的 durable employee source，明示 `supersedes／rebuts／qualifies` 哪項舊來源或理解；framework transition 依 evidence／derivation／stable ID／read-set 找出受影響的工作假說、Task／Duty／OPKS linkage、gap、待處理工作與待審文件變更，先標示 stale／challenged，再只對受影響範圍做 deterministic 對帳與必要語意重分析。無關且依據未變的內容保持原 revision。若重大更正的影響無法安全界定，才升級成較廣的 scope／document reconciliation，不能假裝局部修補已完整。

方案 3 仍不讓更正直接改核准文件：若正式內容受影響，產生、撤回或標記 stale 的待審文件變更，交員工決定。介面先立即確認更正已保存，再顯示「目前理解改了什麼、哪些工作範圍正在重新檢查、哪些未受影響、核准文件是否仍未改變」；branch-blocking 只作用於依賴舊前提的分析，不封鎖整份文件。

**產品裁決**：owner 於 2026-08-13 確認採方案 3。這裡確認的是產品語意與員工體驗；具體 dependency graph、失效 reason code 與 reconciliation run 由 LangGraph state／node／command 承接，production schema 留到施工 task 決定，不在產品流程層先發明第二套元件。

### 3.8 O／P／K／S 按需漸進分析

不需要等 Task 已穩定、已被員工接受或已進入核准文件，才開始看 O／P／K／S。只要目前的工作故事、Work Unit 或 Task hypothesis 已出現足以分析某一軸的證據，顧問就能按需載入該 Skill；沒有需要時不載入，也不是每回合都分析 OPKS。

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

### 3.9 Reference coverage challenge（保留方向，本次升級不實作）

本節保留後續 RAG 討論需要的產品語意；owner 於 2026-08-14 決定本次核心升級不串接 Reference／RAG，因此 ADR 0060 與目前 implementation plan 不得建立 consumer、tool、Skill 或 completion gate。日後若重新啟動這項能力，在已有員工工作理解後，AI 才以少量、按需的既有 iCAP 內容做 coverage challenge：

- 是否漏掉常見但員工尚未談到的責任；
- 是否有可以追問的 Output、Indicator、K/S 方向；
- 員工工作與參考職業內容是 match、partial、no-match 或 conflict；
- 是否需要中立追問，而不是直接採用公版答案。

公版內容只產生參考候選、問題或差異，不自動成為員工的工作事實。

這不是員工要操作的搜尋頁，也不是固定的 Reference 階段。主要顧問在盤點、Task／Duty 或 OPKS 訪談中判斷當下確實有補漏價值時，才按需查詢 iCAP，將命中內容改寫成一個中立問題；沒有明確價值就不查。員工可以回答、略過或稍後處理，但不需要自行挑選 iCAP 項目。

未來產品不保存每個 RAG 命中作為正式分析狀態。只有當候選真的被呈現給員工、改變當前／後續訪談重點、影響待審文件變更或形成 coverage 結論時，才保存一筆可追溯的 challenge receipt。receipt 記住「問過什麼、為何問、依據哪個版本的來源、員工如何裁決」，並連回原始員工回答，不複製或改寫員工來源。

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

系統可以建議「目前資料已足夠形成可用版本」並說明理由、剩餘缺口與繼續訪談可能改善之處；這不建立結束狀態。員工可以繼續傳訊息、直接離開、檢查文件或匯出。

### 3.11 員工視角端到端驗收情境

以下情境不是固定腳本，而是用來驗收產品體驗。假設員工是製造業採購專員；員工不會看到內部 Skill 名稱與編排。

1. **先知道怎麼進行，再建立工作地圖。** AI 先用 3–4 句白話說明會大致盤點工作、一次深入一個焦點、保存旁支線索、隨證據調整 Task／Duty／OPKS，且正式修改都由員工決定；不要求核准固定訪談計畫。接著請員工用自己的話說明一個月內主要工作，不要求 JD 用語。員工提到請購下單、供應商交期、缺料協調與偶爾整理庫存報表後，AI 顯示「目前已知四個工作範圍」，並說明先深入請購到下單的原因。
2. **專注但不漏線索。** 員工在下單故事中順帶提到新供應商評估與替代料；AI 把兩者顯示為稍後處理線索，仍用一個主要問題釐清下單責任，不立即換題。
3. **先理解，後提出文件變更；更正只重查受影響範圍。** AI 經數輪釐清主管核准邊界、採購單內容與供應商回覆，準備切換訪談重點前先用校準卡說明目前理解；員工可直接把「我決定供應商交期」修正為「我追蹤並提出建議，主管才決定」。系統保存新原話與取代關係，只重查依賴這項責任邊界的 Task、Duty、OPKS、gap、待處理工作與待審文件變更，並說明哪些無關內容維持不變；核准文件未經接受仍不改。第一句補充不會立即跳正式核准卡。
4. **員工保留 authority。** 員工指出「不是每次都要比價」，AI 修正 Task 後再讓員工接受。若目前只有一個 Task，可以先不建立 Duty。
5. **重大責任先澄清。** 訪談缺料處理時，員工說「決定哪些工單先拿到料」。因這可能改變正式權責，AI 暫停原焦點，確認員工只是提出建議、最後由生產主管決定，再回到原返回點。
6. **結構隨證據演化。** 當已有下單、缺料協調、供應商績效三項 Task，AI 可提出兩個 Duty 與 Task reassignment 的結構變更組；員工能修改 Duty 名稱。可獨立成立的 K／S 候選仍可逐項決定，不因接受 Duty 就被迫全收。
7. **本次不依賴 Reference／RAG。** 核心情境在 RAG 未啟動、沒有 Reference tool 的環境仍須完整運作；公版 coverage challenge 留到後續獨立設計與驗收。
8. **進度可解釋。** 畫面顯示目前訪談重點、為何現在處理、已足夠／訪談中／尚未深入／文件變更待審／OPKS gap／已確認不屬於本人與稍後線索，而不是顯示假精確百分比。
9. **足夠性只是建議。** AI 說明為何目前已足夠、仍缺什麼、繼續最可能改善哪裡。員工可以繼續傳訊息、直接關頁，或看過缺口後強制匯出；系統不補造答案、不偷收待審變更，也不隱藏未歸類 Task。
10. **失敗不會吃掉回答或製造半套結果。** 員工送出後先看到「回答已保存」。短暫錯誤由同一 run 受限重試；若仍失敗，畫面說明 AI 尚未完成分析、目前理解／待審文件變更／核准文件未改變，並提供重試、修正／取代；員工也可直接離開，日後回來。處理完成或被員工取代前，只暫停同一文件的新 AI 訪談回答；查看資料、處理既有待審變更、直接編輯、匯出與離開仍可使用。

此情境的驗收效果是：AI 主動帶路，員工不用理解分析方法；每輪知道正在談什麼與為什麼；旁支線索不遺失；正式內容只在有意義檢查點由員工決定。

### 3.12 AI 中斷與失敗時的員工體驗（2026-08-13 owner 已確認）

**問題**：§2.7、§2.12 與 §7.16 已確認「員工原話先保存、執行可恢復、業務結果整批提交」，但還需要把 timeout、斷線、provider／schema／verifier 失敗轉成員工看得懂的流程。尤其要決定：短暫失敗是否自動重試、重試用盡後員工能做什麼，以及能否越過一則尚未分析的回答繼續產生新訪談回合。

**直接來源與實際支持**（最近查核：2026-08-13）：

- [OpenAI 官方 Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)把一個 SDK run 視為一個 application-level turn，建議持久會話使用 application-controlled session；串流要完成後才算 settled，中止的同一回合應從保存的 state 恢復，而不是建立新的使用者回合。它也要求區分 runtime／validation failure 與預期的人工作業暫停。這支持「同一回答恢復同一 run、未完成不能偽裝成成功回覆」。
- [AWS Builders' Library — Making retries safe with idempotent APIs](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)說明 timeout 後無法知道操作是否已完成，盲目重試可能造成重複副作用；可自動重試的前提是穩定 caller-provided request ID、idempotent contract 與一致的結果語意。這直接支持沿用同一 `input_event_id／run_id`，不把 retry 當新來源。
- [Microsoft HAX — Support efficient correction](https://www.microsoft.com/en-us/haxtoolkit/guideline/support-efficient-correction/)要求 AI 出錯時讓使用者容易 edit、refine 或 recover。這支持失敗狀態必須有清楚的重試／修正／稍後返回入口，而不是只顯示技術錯誤或要求重打全文。
- [Google — Build long-running AI agents that pause, resume, and never lose context with ADK](https://developers.googleblog.com/build-long-running-ai-agents-that-pause-resume-and-never-lose-context-with-adk/)主張長流程使用顯式 durable state，與原始聊天歷史分離，才能跨重啟與等待恢復。這支持本地保存明確 run／processing state，不支持把 Google 範例的固定 onboarding state machine 複製成 Caliburn 的訪談階段。

**可轉移限制**：OpenAI、AWS 與 Google 資料主要證明 runtime／distributed-system 恢復形狀；Microsoft HAX 是通用人機互動指引。沒有來源直接研究繁中職務訪談中「前一則回答分析失敗時，是否允許繼續送出後續回答」。下列順序約束是依 Caliburn 必須全域吸收每則回答、後續問題依賴最新可修訂理解、且不可產生半套待審文件變更的產品推論，不冒充大廠 UX 標準。

**研究選項與裁決**：

1. **只在背景持續自動重試**：員工一直看到分析中，直到成功。操作最少，但 provider 長時間故障時沒有清楚停止點，可能累積成本，也無法讓員工修正造成 validation failure 的輸入。
2. **短暫錯誤受限自動重試，之後轉成可恢復待處理（採用）**：送出後先回報「回答已保存」；網路、rate limit 等明確 transient failure 在同一 run／attempt policy 內短暫自動重試。成功才出現正式顧問回覆。用盡上限後顯示「原話已保存、AI 尚未完成分析、正式 JD 未改變」，提供「重試分析」「修正／取代這則回答」「離開並稍後回來」。重整頁面或重啟程式仍回到同一狀態；若結果其實已提交，依 result receipt 顯示既有成功結果，不重打模型。
3. **允許後續回答越過失敗項目排隊**：訪談看似不中斷，但後面的顧問問題與分析可能沒有讀到前一則來源，之後還要處理跨回合重排、stale Context 與相互衝突的 semantic commit；第一版不建議。

採方案 2 時，第一版預設不讓同一文件產生新的 **AI 訪談回答**，直到該 input 已完成 semantic commit，或員工以新的 correction／withdraw intent 明確取代它；否則系統無法保證下一題建立在完整來源上。這只暫停該文件的 AI 訪談鏈：員工仍可查看來源與進度、處理既有待審文件變更、直接編輯核准文件、匯出或離開。這些其他動作若改變 authority generation，恢復時依既定 stale／read-set 規則重新組裝，不把舊結果硬套到新狀態。

**產品裁決**：owner 於 2026-08-13 確認採方案 2。尚未分析完成的回答會序列化同一文件後續 AI run，避免兩個模型結果競爭寫入；員工仍可關頁、重開、查看與直接編輯，不建立「訪談暫停」狀態。技術 retry 次數、backoff、錯誤分類與 UI 文案留到 run policy／施工 task，不在產品流程層假裝已有最佳數值。

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

Task、Duty、OPKS 與待審文件變更的狀態不能全部壓成一個總分。例如：

> 目前已知 11 個工作範圍；6 個已足夠、2 個正在深入、2 個尚未深入、1 個有重大矛盾；另有 3 個 OPKS gap 與 2 項文件變更待審。

所有數字都應標明「目前已知」，並可展開看到具體內容與原因。

Owner 於 2026-08-13 確認：員工需要同時知道「大致談了多少」、「每一塊分析到哪裡」與「還有什麼等自己決定」。因此進度是三個並列視角，不可混成一個分數：

1. **工作 coverage**：目前辨識出哪些工作範圍，哪些已深入、正在談、尚未深入、被排除或只留下線索。這回答「我的工作大致談到哪裡」。
2. **分析深度**：對每個工作範圍分別顯示 Task 邊界、Duty 歸組與 O／P／K／S 的 sufficiency／gap。Task 已足以成案，不代表其 Duty 或 OPKS 已經足夠；OPKS 也不必等 Task 永久穩定後才開始。
3. **員工決策**：顯示待接受、待修改、待拒絕或已延後的文件變更／結構調整。這回答「AI 已分析但還有哪些事情等我裁決」。

「工作範圍」是給員工導航與計算 coverage 的產品概念，由核准文件、可修訂理解、員工來源與 durable workflow state 產生可重建投影；它不是把 Task、Duty、OPKS、gap 與待審變更混算的新權威實體，也不先要求新增第二份工作清單。UI 與模型的受限全域索引應由同一組 projection 語意產生，但可使用不同 representation。新線索使地圖擴張時，系統應說明新增了什麼，而不是讓一個百分比無故倒退。

### 4.3 訪談足夠與匯出檢查是兩種不同判斷（2026-08-14 owner 修正確認）

員工永遠可以停止傳訊息、關閉頁面並在下次自然續談；這不是一個需計算或顯示的產品狀態。介面與 AI 只需區分：

1. **訪談目前已足夠**：主要 coverage 與高影響缺口已處理或留下理由，AI 說明目前已足以形成可用職務說明書；這只是可重新計算的顧問建議，不建立「訪談完成」狀態，也不關閉對話。
2. **文件通過匯出檢查**：目前核准文件符合一般匯出條件；若仍有缺口，系統列明原因，員工仍可明確選擇強制匯出。

### 4.4 「目前已足夠」採混合判斷

不得只靠固定題數／分數，也不得只靠 LLM 一句主觀宣告。系統以可檢查證據打底，由 LLM 做整體專業判斷與白話解釋；員工可以繼續訪談、查看文件、匯出或先離開，不需按「完成訪談」。

判斷面向至少包含：

- 工作範圍：主要、週期性、低頻高影響工作與責任邊界是否大致盤點；
- 重要工作：本人責任、主要結果、完成判準與關鍵例外是否足以形成可信描述；
- 結構：是否仍有可能顯著改變 Task merge／split 或 Duty 分組的重大矛盾；
- OPKS：重要 gap 是否已分析、排入待補訪，或有 unknown／not applicable／暫不處理等明確理由，而不是要求欄位全部填滿；
- 員工決策：是否仍有可能大幅改變核准文件的待審變更尚未處理；
- Reference challenge：本次升級不執行；日後接上 RAG 後才納入足夠性判斷，且不得把公版內容誤認為員工事實。

只有當沒有未處理的重大問題，而且剩餘缺口已清楚呈現、預期不會推翻整體 JD 時，AI 才建議「目前訪談已足夠」。同時必須說明：為什麼足夠、還缺什麼、繼續訪談最可能改善哪裡。員工仍可繼續、直接離開或強制匯出；新證據出現後重新計算即可，不存在需要重新開啟的「已結束訪談」狀態。

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
- Duty 需要自己的候選、來源、改名、重分組、merge／split 與員工文件審核生命週期，不能只在匯出時臨時分組；
- iCAP 要求主要職責／任務粒度盡量一致、以成果或功能表達，但沒有固定條數下限。

因此「一開始順便分析職責」是合理的；限制只是不能把早期 Duty hypothesis 當作後續 Task 的不可變分類。

### 5.3 O／P／K／S：方法可獨立載入，語意仍互相依賴

依 [`OPKS 設計裁決`](2026-08-01-opks-design-decisions-research.md)、[`OPKS 漸進蒐集`](2026-08-04-opks-progressive-elicitation-research.md)與[`OPKS gap 再分析研究`](2026-08-06-opks-gap-reanalysis-blocking-research.md)：

- 既有「以單一 Current JD Task 為一次 OPKS operation」是控制輸出量、prompt/schema 大小與 durable failure boundary 的現行實作決策，不應升格成產品流程必須等待 Task 穩定的證據；2026-08-04 研究中的獨立 OPKS child 也是當時架構限制下的方案，不是新顧問必須保留的模型呼叫或 profile 邊界；
- 未來可把 O、P、K、S 拆成各自的 Skill，根據當輪證據與焦點按需載入；Skill 是否獨立，不預先決定是否另開模型呼叫；
- 正式資料關係仍是 O/P 綁 Task，K/S 是文件層項目並與相關行為指標／Task 建立多對多 linkage，A 是文件層；但分析期間可以先連到 Work Unit／Task hypothesis，在形成待審 changeset 前再完成 identity reconciliation；
- K/S 應由實際 Task 與行為證據反推，不直接要求員工自列能力；
- 是否需要某個分析 Skill，可由可檢查的 policy、目前訪談目標／gap 與模型判斷共同決定；員工不需要按「產生 OPKS」；
- 證據不足要保存具體 gap，framework pending-work queue 一次選一個主要問題；unknown／not applicable 可以成為有理由的分析終止；
- OPKS 可能揭露 Task outcome 或邊界有問題，必須允許回頭修正 Task。

仍需保留的語意依賴是：O／P 必須能連回正在分析的工作；K／S 必須連回工作行為／Indicator，不能因 Skill 拆開就各自生成漂亮但無支持的清單。

現行研究仍有一項已知風險：active gap 可能讓後期 Task 的再分析出現尾端衰減。2026-08-06 的研究因缺少 10–15 回合真人資料而暫不翻案；未來流程評測必須量測 gap 開啟率、關閉率與 late-discovered Task 的產出，不能假設現行 gate 已是最優解。

### 5.4 AFFiNE 階段化需求稿：保留可見控制，不採剛性階段門

2026-08-12 逐段讀取 owner 提供的 `職務分析_AI_階段化狀態機需求稿 _ AFFiNE.html`。它是有價值的 stakeholder 草稿，但不是本 repo 權威，也不能覆蓋既有研究與已確認的產品流程。

整合裁決：

| 類別 | 處理 | 理由 |
|---|---|---|
| 單一主要 AI、明示目前目標／剩餘項目／下一步 | 保留 | 提升焦點、進度與可恢復性，不需要人格化多 Agent |
| 待訪談清單的來源、狀態、最近更新、自然離開／恢復 | 保留並擴充 | 由 LangGraph durable state 的 pending-work items 投影 Story、Work Unit、Task、Duty、OPKS gap、矛盾與待審 changeset，不建立第二份 authority store，也不建立「暫停訪談」狀態 |
| 候選區與核准文件分離；可接受、修改、拒絕、退回補訪 | 保留並交由 framework HITL／command | 符合員工 authority；採有意義檢查點與 dependency-aware changeset，不沿用舊 Proposal seam |
| 右側文件可直接編輯、排序並自然續談 | 保留 | 員工直接編輯與 AI 待審 changeset 都經 deterministic LangGraph command 更新核准文件 |
| Reference 不直接定義員工工作 | 保留為後續 RAG 原則 | 本次不串接 iCAP consumer、tool 或 Skill；日後另案仍須 employee-first、blind-first，且員工可略過 challenge |
| 「骨架／Duty／Task／OPKS」狀態機 | 改寫 | 只投影可見的訪談重點與 durable checkpoint，不限制當輪可載入哪些 Skills，也不是資料生命週期通關門 |
| 完成條件與狀態提示 | 改寫 | 從固定階段完成改成可重算的目前足夠性、export readiness、具體 gap 與 reason code；不建立訪談完成狀態 |
| 新線索先保存、不任意打斷 | 改寫 | 一般線索先停放；會推翻 Task 邊界、本人責任或重大結論者必須先澄清，並保存返回點 |
| Task 必須先有 Duty、禁止孤立 Task | 不採用 | 分析期間 Task 可暫無 Duty；Duty 是隨證據動態重組的假說與正式實體 |
| 只有已進 JD 的 Task 才能深入或分析 OPKS | 不採用 | Story、Work Unit 或 Task hypothesis 出現足夠證據時即可按需分析 O／P／K／S |
| AI 不得跨階段深入提問 | 不採用 | 與全回答理解、按需 Skills 及 OPKS 反向修正 Task 的需求衝突 |
| O＝工作行為、P＝工作產出 | 更正後才可使用 | iCAP 正確對位是 O＝工作產出、P＝行為指標；P 是成功完成 Task 的可觀察標準，可包含有依據的情境、行為、結果、條件與程度 |

主流架構佐證指向同一結論：Anthropic 建議從簡單、可組合的單一 agent pattern 開始，並以 Skills progressive disclosure 和最小高訊號 context 控制複雜度；OpenAI 現行 guidance 建議精簡 prompt、只暴露相關 tools，並明定 autonomy／approval boundary；Google ADK 2.0 則把 deterministic workflow 與 adaptive agent 組合，將業務規則、HITL 與可靠 transition 留給程式，把模糊語意判斷留給模型。

因此本產品採用的不是純自由 Agent，也不是純階段狀態機，而是：

> 員工看得見明確的訪談重點、待處理事項、進度與核准點；AI 在這些受控邊界內動態理解完整回答、選擇 Skills 並調整訪談；核准文件的寫入權、待審 changeset 的提交、資料 invariant 與不可跳過的員工核准，由 LangGraph command／HITL 與 deterministic transition policy 共同保證。

## 6. 第一階段實作方法 Skills；公版 Reference 留待後續

職務分析方法與公版職業內容是兩種不同知識。兩者仍必須保持不同來源與權威，但 owner 於 2026-08-14 已確認：**本次核心升級只實作方法 Skills，不串接公版 Reference／RAG。** 下列 §6.2 只保存後續研究方向，不屬於目前施工或驗收範圍。

### 6.1 從一開始可用：職務分析方法知識

例如：

- 如何辨識 Task、步驟、工具與他人工作；
- 如何做廣度盤點與具體事件訪談；
- 如何判斷 merge／split；
- 如何形成 Duty；
- 如何從行為與產出分析 OPKS；
- 如何停止、避免引導與做反方檢查。

這些是顧問方法、rubric 或 Skill，不是特定職業答案。第一版核心 Skill 至少包含：

- breadth／story interviewing；
- task boundary／merge／split；
- duty grouping；
- output；
- performance indicator；
- knowledge；
- skill；
- completion／red-team review。

Skill 採 progressive disclosure：平時只保留短名稱與用途，當輪命中才載入完整方法。這解決的是方法 prompt 膨脹；當輪需要哪些員工原話與職務狀態，則由 LangChain context middleware 依受限全域索引、目前訪談重點與可追溯來源按需組裝。

### 6.2 後續 RAG 階段才評估：既有 iCAP 內容

日後若另案接上 RAG，候選來源只使用 repo 已有的 iCAP 資產，不自動擴張到其他公版、一般網路搜尋或公司文件。iCAP 可以：

- 協助回憶；
- 做 coverage challenge；
- 提供可能追問方向；
- 提供術語與來源；
- 比較 match／partial／no-match／conflict。

它們不得：

- 因職稱直接定義 Task／Duty；
- 取代員工工作故事；
- 自動寫入核准文件；
- 把「公版常見」說成「員工本人負責」；
- 一次整包塞入每輪 context。

未來是否由主要顧問按需查詢、何時形成 challenge、如何保存來源與成本，必須在 RAG 另案重新研究與決策；目前 runtime 不提供這項 tool、Skill 或完成條件。

## 7. 長期記憶、文件權威與按需 Context v0.3

本節先定義產品必須記住哪些不同性質的內容，以及誰有權改變它們；不預先決定資料表數量、向量資料庫、framework 或實際 storage topology。

### 7.1 來源記憶：員工真正說過什麼

保存**同一位員工**在整段訪談與日後恢復時真正說過的原話、來源回合、時間、附件／引用位置，以及後續更正、否認或撤回的關係。它是回答「這項理解根據哪一句話」的 evidence layer，也是避免長訪談中忘記員工先前答案、反覆詢問同一件事的長期記憶。

- 摘要不得覆寫或取代原始來源；
- AI 不得改寫員工原話後冒充 source；
- 更正保留前後歷史並標示目前效力，不以刪除舊句偽造一致性；
- 準備再次詢問前，應先按焦點、穩定 ID、關聯與語意從該員工的完整歷史取回可能答案；只有找不到、彼此衝突、已過時或確實需要重新確認時才詢問；
- `speaker` 是來源識別與防止內容混淆的 metadata，不代表第一版要做多位受訪者、主管／同事訪談或多人 authority；
- 後續所有目前理解、待審文件變更與核准內容應可追溯到來源或明確的員工直接編輯。

### 7.2 可修訂理解：AI 目前怎麼理解

以 LangGraph durable state 保存 Story、Work Unit、Task／Duty hypothesis、O／P／K／S 候選、linkage、gap、矛盾、未映射線索與 retired candidate。它是可變動的分析內容，不是員工核准文件，也不建立名為 `WorkModel` 的新 domain 元件。

- AI 可以依新證據新增、修正、合併、拆分、重新連結或淘汰假說；
- 每項假說要保留穩定 identity、支持／反對證據、信心理由與生命週期狀態；
- `employee_denied`、過去工作、他人工作、一次性支援等 retired reason 不應被一般檢索重新當成 active candidate；
- 理解變化可以影響訪談重點與待審文件變更，但不得直接改變核准文件。

#### 7.2.1 可演化工作假說的產品契約（2026-08-14 framework replacement 校正）

Owner 已確認採用「**typed、evidence-linked、可持續修訂的工作假說關係模型**」作為目標語意。它不是一份長得像 JD 的 AI 草稿，也不是把聊天紀錄壓成一段 memory summary；它保存的是 AI 對這位員工工作的**目前理解及其依據**。新證據可以改變任務邊界、Duty 分組、O／P／K／S linkage 與 gap，所以早期結構不能被誤當成永久分類。

第一版先鎖定下列邏輯契約；LangGraph typed state／checkpoint 已由 §9.12 選為承接機制，但欄位名稱不沿用舊 Work Model schema：

1. **可不完整的 typed item**：Story、Work Unit、Task／Duty hypothesis、O／P／K／S 候選、gap、矛盾與未映射線索都可先存在；尚未判定為 Task／Duty／OPKS 的內容以「未映射線索」類型保留，尚未分組或尚未連到 Task 也不等於非法狀態。
2. **穩定 identity 與修訂生命週期**：後續改名、補充、合併、拆分、重新分組或淘汰不能只靠文字相似度判斷同一性，也不能以覆寫抹除舊理解；至少要能分辨目前有效、被挑戰、被取代與有理由 retired 的版本。
3. **一級 evidence linkage**：每項重要理解可連回一個或多個員工 source anchor，並區分支持、反對、更正或不確定；模型信心、embedding score 或任何檢索相似度不能取代來源關係。
4. **typed domain relation**：能表達工作故事如何形成 Work Unit／Task、Task 如何暫時歸於 Duty、O／P 如何連到 Task、K／S 如何跨 Task 關聯，以及新證據如何造成 regroup、gap 或 contradiction。這些是關係語意的例子，不是先決定一套封閉 edge enum。
5. **與文件 authority 分離**：一項理解可以比核准文件早出現、持續演化，也可以暫時與核准內容不同；只有待審 changeset 經員工 accept／edit-accept 後，framework authority transition 才能改變核准文件。員工修正 AI 理解不等於核准正式文件變更。
6. **以 framework transition 更新、以 projection 使用**：主要顧問或按需 Skill 只能產生 typed change intent；deterministic node 驗證來源、document scope、revision／read-set 與 domain invariant 後才更新 durable state。側欄、進度、待處理集合與受限全域索引都由此投影；context-selection receipt 只記錄執行時實際選用內容，不另存一份競爭真相。

「關係模型／graph」在這裡只描述**邏輯上可沿穩定 ID 與 typed relation 走訪**，不代表採用 graph database、GraphRAG、RDF ontology，亦不等於 LangGraph／其他框架的 execution graph。PostgreSQL 關聯模型、typed application model 或成熟框架的 store 都可能承接機制；是否採用要等 capability matrix 與 conformance spike，不能從 `graph` 一字反推技術選型。

研究佐證與可轉移限制如下：

| 第一手來源 | 直接支持 | 不能據此宣稱 |
| --- | --- | --- |
| [U.S. OPM — Assessment and Selection](https://www.opm.gov/policy-data-oversight/assessment-and-selection/) | Job analysis 要辨識 Task、role／responsibility、competency、resources 與 context，向具直接且當前工作經驗的 SME 蒐集資料，並記錄 Task－competency linkage | OPM 沒有規定 LLM Work Model、graph schema、OPKS ontology 或資料庫技術 |
| [OpenAI Cookbook — Context Engineering for Personalization](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization/) | 以 local-first structured state 保存可修訂資訊、處理衝突與 precedence，推理時只注入相關 slice | 案例是個人化／旅遊助理，不直接證明其狀態欄位適合職務分析 |
| [Google Cloud — Choose agentic AI architecture components](https://docs.cloud.google.com/architecture/choose-agentic-ai-architecture-components) 與 [Microsoft Agent Framework — Memory & Persistence](https://learn.microsoft.com/en-us/agent-framework/get-started/memory) | 區分 session／history、application state、long-term memory 與外部 persistence；context provider 可承接 application-specific memory | 這些是 runtime／deployment 指引，不知道 Task、Duty、OPKS、員工更正與 JD authority 的產品語意 |
| [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) 與 [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | 長流程可把 structured notes／durable store 留在 context 外按需取用；LangGraph 明確區分 thread checkpoint 與 cross-thread Store | 被框架保存不會讓 structured note、Store 或 graph state 自動成為可信 evidence；State 通過 conformance 並直接成為唯一 document authority 時，可取代舊 Work Model／Current JD writer，可信性仍來自 source、schema、reducer 與 authority policy，不是儲存容器本身 |
| [W3C PROV-O](https://www.w3.org/TR/prov-o/) 與 [W3C Web Annotation Data Model](https://www.w3.org/TR/annotation-model/) | 提供 derived-from、revision、quotation、primary source、invalidation，以及 quote／position selector 等可借鏡的來源與修訂語意 | W3C 不要求 Caliburn 採 RDF，也沒有定義職務分析的 domain model；position anchor 單獨使用對內容變更很脆弱 |

因此，外部資料直接支持的是「**結構化狀態、可追溯來源、明確修訂、分離 runtime checkpoint、按需傳入 context**」；把它們組成上述可修訂理解，是 Caliburn 結合 OPM 職務分析原則、既有 Task／Duty／OPKS 研究與員工 authority 所作的產品推論。現階段尚無可信公開 benchmark 證明某個 memory／agent framework 能直接提升繁中職務訪談或 JD 品質，後續不得把框架功能表當成效果證據。

### 7.3 核准職務文件：員工已授權的成品

只包含員工直接編輯，或待審文件變更經員工接受／修改後接受後，由 framework authority transition 寫入的正式內容。

- 核准職務文件是產品文件真相；
- AI 不能因摘要、重新分析、模型更換或任何工具／外部來源命中而直接覆寫；
- 新證據可產生挑戰或新的待審文件變更，但舊內容在員工決策前仍維持正式效力；
- 正式項目與其決策／來源 lineage 應可追溯。

### 7.4 動態訪談工作：現在為何問、之後要處理什麼

由 LangGraph routing／state 保存目前訪談重點、選擇原因、暫時收束條件、待處理問題、已停放線索、具體 gap、待審文件變更、進度投影與 blocked reason；不建立 `Focus`、`Progress` 或 `Agenda` 舊元件的新版複本。

- 關頁、久後恢復或切換重點後能自然續談，不靠模型從聊天猜測上次談到哪裡，也不建立暫停狀態；
- 待處理集合是 durable state 的可見工作投影，不成為第二份核准文件或第二份目前理解；
- AI 預設選下一個最高價值訪談重點，員工可改道；
- 已完成、已拒絕、已退休與 terminal unknown／not applicable 必須有理由，避免無限重問。

### 7.5 Reference 是獨立知識來源，但本次升級暫不串接

Reference 的已確認產品方向只使用既有 iCAP 內容，並保存其來源、版本、片段與 citation。iCAP 未來可支持 coverage challenge、術語與追問，但不能和員工原話混成同一 evidence authority，也不能因檢索相關度高就直接提高為工作事實。Owner 於 2026-08-14 決定本次核心升級不做 RAG／Reference runtime 串接；下列語意保留為後續研究輸入，不是目前 ADR 0060／施工計畫的完成條件。O*NET、一般網路搜尋、公司文件、表單與既有 JD 也不在目前需求範圍。

Reference 記憶分成兩種不同用途：

1. **檢索技術軌跡**：query、候選來源、實際送入模型的片段與排序等可放在 bounded run trace／context-selection receipt，供重播、成本與除錯使用；它不是目前理解或正式分析結論，也不要求所有命中永久留在產品狀態。
2. **具產品意義的 challenge receipt**：只有被拿來詢問、改變待處理工作／待審文件變更或形成 coverage 裁決的候選才持久保存。它連結來源版本、challenge fingerprint、目標範圍、提出理由、員工 source event、裁決與生命週期。

receipt 的裁決歷史採追加與 supersession，不以覆寫抹除員工先前說法；員工更正時保留舊裁決與新 evidence 的關係。同一 challenge 可掛多個 iCAP 片段或版本，但不能因另一個近義片段而繞過已存在的 no-match／拒絕紀錄。不同片段或版本有實質衝突時不合併成假共識，而是保留差異並在確有影響時中立詢問。

### 7.6 摘要、embedding 與模型 reasoning 都不是 authority

- 對話摘要、焦點摘要與壓縮筆記是可重建的 context artifacts；
- embedding、向量相似度與 rerank score 是檢索索引，不是事實真偽或員工認可度；
- provider 保存的 conversation state／reasoning state 可提高連續性，但不能取代本地持久化的員工來源、可修訂理解、核准文件與 framework checkpoint；
- 模型或 framework 可以替換，只要上述產品權威與 lineage 不被改變。

每輪 framework context middleware 可以從各層選取「最近必要對話＋訪談重點相關原話＋相關工作假說＋已接受內容＋當前 gap／待審變更＋命中的 Skill」；完整保存與當輪傳入是兩件不同的事。本次不加入 Reference retrieval。

### 7.7 LangChain context middleware 的第一輪權威資料結論

截至 2026-08-12，OpenAI、Anthropic、Google 與 LangGraph／LangChain 的官方資料沒有提供一份可直接套用到職務分析的「最佳 context 配方」，但共同支持以下方向：

- context 是有限注意力資源；可用窗口變大，不代表把完整歷史放入每輪會更準；
- 長流程應把可恢復的完整 session／event log 與本輪模型可見 context 分離；
- 業務進度與權威狀態應明確持久化，不由模型從聊天歷史猜測；
- 精簡且任務相關的 prompt、tools、Skills 與資料通常比全部常駐可靠；
- compaction、summary、provider conversation state 與長期 memory 可提高連續性，但都不能取代原始來源與業務 authority；
- context selection 沒有通用最佳值；核心成品完成後，先以長訪談、修正、跨題線索與 Task／Duty／OPKS 情境評測，Reference 情境留待 RAG 另案。

2026-08-12 進一步核對 OpenAI、Anthropic、Google、Microsoft Research 與 OPM 第一手資料後，新增一項較精確的產品結論：**全域結構要持續存在，但不等於每輪傳入全域細節。** Anthropic 的最新工程指引主張最小高訊號 context 與「少量預載＋just-in-time 探索」的 hybrid；OpenAI 建議注入當下相關的 structured-state slices，並精簡重複 prompt／tools；Google 將 durable state、session memory 與本輪 working context 分開，且其 Sufficient Context 研究顯示「相關」不等於「足以判斷」，額外但不充分的 context 也可能提高幻覺；Microsoft 的 GraphRAG／DRIFT 研究則支持先有全域概觀再深入局部，但 dynamic community selection 也說明靜態送入全部全域摘要昂貴且低效。OPM 的職務分析方法要求先維持可追溯的 preliminary Task／competency inventory，再由 SME 評定、修正與建立 linkage，支持本產品不能只把每個焦點孤立分析。

上述資料共同支持的是「**受限全域定位＋焦點細節＋按需展開**」的架構模式，不是「每輪把完整核准文件、可修訂理解、OPKS 與歷史全部塞入」。Microsoft 的量化結果來自 AP News corpus，Google 的 Sufficient Context 主要是 RAG QA；目前仍沒有公開 benchmark 直接證明同一配方能提高繁中職務訪談品質。以下產品裁決是依這些共同模式與 Caliburn 的跨 Task 線索、Duty 重組、OPKS linkage、員工更正和進度需求所作的領域推論，不能宣稱為外部研究已直接驗證的成效。

這些來源也形成一個重要限制：框架可以提供 session、checkpoint、store、summary middleware、retrieval hook、tracing 與 token accounting，但無法自行知道「哪句員工原話是必要證據」「哪項更正優先於舊說法」。日後加入 Reference 時，還要另補「公版來源不得混入員工事實」的政策；這些都是 Caliburn 的產品與 domain policy。

外部證據的可轉移性也有限：Anthropic 的主要案例包含 coding／research agent，Google 的長流程案例是 HR onboarding，Contextual Retrieval 的量化資料集也不是繁中職務訪談。目前沒有可信公開 benchmark 證明任何 Context framework 或固定配方會直接提高專業職務說明書品質；本節只能把共同架構模式轉成待驗證假說，不能把別的產品結果當成 Caliburn 成效。

### 7.8 三種 Context 組裝方案

#### 方案 A：完整歷史／provider state 優先

每輪延續 provider conversation、完整 message history 或 provider compaction，讓模型自己從長 context 找重點。

- 優點：初期程式少、對話自然、可快速建立 baseline；
- 缺點：舊 token 仍可能持續計費，長歷史會引入 context pollution；opaque compaction 不可檢查；provider lock-in 高；不能保證重大更正、權威邊界與跨題線索被正確使用；
- 結論：只適合作為連續性輔助與比較 baseline，不作產品唯一記憶或權威來源。

#### 方案 B：完全由程式預先組好固定 context bundle

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

1. **保存，不等於傳入**：員工原話先進 LangGraph Postgres Store 的 durable inbox；model／tool 原始結果與 verification 依 run boundary 保存為可恢復 artifact；只有通過驗證並完成 semantic transition 的 consultant turn 才成為正式對話。可修訂理解與 durable thread event 由 framework state／checkpoint 保存，不得用摘要取代原始來源。
2. **建立不可省略核心**：放入精簡 authority 規則、本次 run 的有效訪談目標／完成目標、員工當輪完整文字回答、受限全域工作索引、相關核准文件／可修訂理解，以及會影響本次判斷的最新更正、矛盾與待審 changeset。
3. **走直接關聯**：先依 document、穩定 ID、Task／Duty／OPKS linkage、source receipt、speaker、generation 與狀態查詢，不先用向量猜。
4. **找較遠候選**：對較早原話與未映射線索使用 lexical 與 semantic retrieval；結果保留 speaker、原回合、entity、前後片段與 authority metadata，再視需要 rerank。
5. **按需載入方法**：平時只讓模型知道可用 Skill 的名稱與用途；命中 task-boundary、duty-grouping、O、P、K、S 或 completion review 時才讀完整方法。
6. **允許受控補查**：若 context 顯示仍有未載入來源，模型可呼叫 document-scoped 唯讀工具取得特定 Task 的原話、相關 Duty／OPKS 或修正歷史；不得跨 document，也不得以工具結果直接寫核准文件。
7. **計數、裁切與降級**：依實際 model profile 計算 tokens，先保留 output／schema／必要 authority；超預算時先移除重複工具輸出與較遠候選，不靜默刪除當輪回答、最新更正或 blocking contradiction。
8. **留下 context manifest**：記錄實際載入、未載入、選取理由、來源 hash／generation、Skill／tool、tokens、model profile 與輸出 lineage，供 replay、除錯與成品後 eval。

附件與長文件不保證整份放入；當輪員工文字回答原則上完整傳入，附件則以可追溯片段或按需工具讀取。若單一回答本身超過模型安全預算，系統必須明示分段或 context budget 問題，不可無聲截斷。

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

這裡的「每輪」只指**可能更新可修訂理解、pending-work queue、待審文件變更，或決定下一個訪談方向的主要顧問 inference**；候選仍須通過 deterministic verifier、framework reducer 與 semantic transition，模型不直接寫入核准文件。deterministic projection 不需要模型 context；唯讀工具只接受 scope 明確的查詢；按需載入的 Task／Duty／OPKS Skill 只取得本次所需資料與必要 orientation，不自動複製完整 context pack，也不另開 specialist model。

因此主要顧問 inference 必帶一份 **bounded global orientation index（受限全域工作索引）**。它由核准文件、framework-backed 可修訂理解與 durable thread state 產生，是 deterministic、versioned、可重建的 read projection；不是 LLM 自由摘要、RAG 搜尋結果或另一份 authority store，也不因被放進 prompt 就改變任何項目的權威。

索引至少讓模型辨識：

- document／generation 與目前訪談目標；
- active Duty／Task 的穩定 ID、短名稱、基本歸屬與生命週期狀態；
- 每個項目屬於核准文件、可修訂假說，或 framework pending／gap 狀態；三者不得混成同一權威；
- 未歸類 Task、重大矛盾、blocking dependency 與待審 changeset 的存在及可查詢指標；
- 目前已知範圍的摘要數量，使模型與員工介面的進度投影能指向同一組可解釋對象。

索引平時不攜帶完整 Task 敘述、全部原話／evidence、完整 OPKS、完整待審 payload、整段歷史，或已退休／已否認候選的細節；這些依目前訪談目標、直接關聯與受控工具按需取得。最新有效更正、會推翻本次判斷的矛盾與其他 authority floor 仍由必帶核心另行保證，不能因索引精簡而遺失。

全域地圖本身也可能造成定錨：模型可能把目前 Duty／Task 分組誤認成完整且固定的世界。第一版必須同時施加以下邊界：

- 明示索引是「目前可修改的正式內容／假說／缺口投影」，不是完整 ontology 或員工已全部確認的清單；
- 當輪員工來源、最新有效更正與 blocking contradiction 不得被索引摘要覆蓋；
- 索引保留未歸類 Task、未映射線索、open gap、矛盾、待審 changeset 的數量、狀態與查詢指標，讓「目前結構以外仍有東西」保持可見；
- 主要顧問可以提出新 Task／Duty、重新分組或重新開啟假說，不能因現有 header 沒有對應位置就捨棄新線索；
- UI 進度與模型索引應由同一組 domain projection 語意產生，但各自使用適合人與模型的 representation，不共享一份由 LLM 生成的摘要文字。

索引也不能無限成長：

- 小型職務在預算內可列出全部 active Duty／Task headers；
- 超出預算後，確定性降級為全部 Duty 摘要、目前訪談目標及相鄰 Task、其他區域的數量／狀態／查詢指標；
- 模型需要遠端細節時，透過 document-scoped read-only lookup 展開，不把所有區域預先載入；
- 降級規則、被省略區域與實際載入內容寫入 context manifest，不可靜默假裝索引完整。

這項裁決把「前景專注、背景全域吸收」轉成可實作邊界：前景得到足以完成當輪判斷的細節；背景保有結構定位與異常訊號，而不是保有所有細節。它同時支援 Task／Duty 隨訪談演化、OPKS 按需分析、旁支線索停放與可解釋進度，不要求第一版先導入 GraphRAG、向量記憶或額外 planner model。確切欄位、大小，以及 active consultant model profile 的 context window／能力改變時如何確定性降級，仍屬 §7.15 未決實作參數，成品後再用真實長訪談 eval 調整。

#### 7.9.2 第一階段資料不足時的補查與詢問順序（2026-08-14 RAG scope 校正）

Owner 已確認「不要把能自行查到的內容反覆問員工」。第一階段的正式方向是：**本文件內可直接定位的相關資料先由 document-scoped 唯讀工具自動查；只有這位員工能確定的當前工作事實、意圖與裁決，才直接詢問員工。** 本次沒有 iCAP／Reference 查詢路徑，不能把尚未接上的 RAG 當作提問前置關卡。

外部資料支持的是「先利用既有高可信 context，再把只有使用者能決定的問題交還使用者」，不是一條固定搜尋流水線：

- OpenAI 最新 model guidance 建議只暴露當下相關工具、追蹤成長中的 context，並明示重要歧義何時必須提問；安全、唯讀且在範圍內的查詢可持續進行，重要歧義與核准邊界則停止並交還使用者。
- Anthropic 的 Context Engineering 建議以少量預載資料加 just-in-time 探索取得最小高訊號 context；其 Trustworthy Agents 研究進一步區分「可自行研究的缺口」與「只有使用者能決定的偏好／意圖」，並指出過度詢問與一律自行假設都會降低可靠性。
- Google Research 的 Sufficient Context 研究顯示，「找到相關內容」不等於「已足以回答」；額外但不足的 context 仍可能提高模型信心與幻覺，因此任何 lookup 都不能取代充分性判斷。
- Microsoft Research 在超過 20 萬段模擬對話中觀察到，模型會受早期錯誤假設牽制且難以恢復；這支持優先注入最新更正、保存結構化目前理解，並在會改變工作邊界時釐清，而不是讓模型沿長對話自行猜。
- OPM 將 job analysis 定義為系統性蒐集、記錄與分析工作內容、情境及要求，並以具有直接、近期工作經驗的 incumbent／supervisor 作為 SME 來源。這支持本產品把員工對「本人現在實際做什麼」的陳述視為核心來源；OPM 並未替 Caliburn 決定單一員工 authority，後者仍是本產品裁決。

因此，第一版 Context Policy 採下列**缺口分類與查詢階梯**；階梯是依缺口類型選路，不要求每輪走完所有步驟：

1. **先判斷缺口類型，不先盲目搜尋。** 區分為本文件可檢索事實、員工專屬工作事實／意圖／裁決，以及不阻塞目前分析的延後 gap。這可作為同一次主要 inference 的 typed sufficiency／next-action 欄位，不要求固定增加一個 planner call。
2. **本文件的直接關聯先自動讀。** 若答案可能已存在於當輪回答、最新更正、穩定 ID linkage、目前 Task／Duty／OPKS、相關待審變更或明確 source receipt，LangChain context middleware 應在 document scope 與 budget 內先查，不把內部查得到的內容原封不動再問員工。
3. **只有直接關聯不足時，才擴展本文件檢索。** 依 lexical／semantic 候選、相鄰回合與來源關係補查；若找到的只是舊假說、已否認內容或相互矛盾來源，仍視為不足，不得用相似度決勝。
4. **員工專屬或高影響歧義直接詢問員工。** 包含責任歸屬、實際做法、決策權、頻率／條件、本人意圖、來源衝突，以及會實質改變 Task 邊界、Duty 分組、OPKS 或待審文件變更的未決事項。問題應聚焦一個主要判斷，說明目前理解與缺口，不要求員工重述系統已知內容。
5. **非阻塞缺口可以明示延後。** 若不影響目前訪談重點、補查成本超過本次 run budget，或員工選擇稍後回答，就以 reason code 與 framework-backed pending-work item 保存；不得偷偷補值，也不得因未查遍所有可能資料而阻止本次形成有效的理解更新、gap 或下一個問題。

可先使用下列語意 reason code，名稱與 schema 之後仍可調整：

- `SUFFICIENT_FOR_CURRENT_ACTION`：對本輪合法產出已充分；
- `LOCAL_LOOKUP_NEEDED`：本文件仍有明確可查來源；
- `EMPLOYEE_CLARIFICATION_REQUIRED`：只有員工能回答，或影響重大到不能假設；
- `DEFER_WITH_VISIBLE_GAP`：本輪不阻塞，保留可恢復缺口。

「充分」是相對於**目前合法 action**，不是整份職務已完整。例如現有證據可能足以形成一個 Task 待審變更，但不足以形成其完整 OPKS；此時可以更新 framework-backed 可修訂理解並留下 OPKS gap，不必為了追求全域完整而無限補查。每次 read-only lookup 應有目標、理由、預期補足的缺口、scope、budget 與停止條件，實際讀取內容寫入 context manifest；停止條件是已足以形成待審變更、no-op、visible gap 或一個主要問題之一，而不是「所有可能 context 都載入完成」。

Reference anchoring 與 challenge receipt 已保存在 §3.9／§7.5 作為未來 RAG 研究輸入，本次不實作、不測試，也不預留假 tool call。

白話例子：訪談「月結」時，系統若已在舊回合記錄員工每月整理差異表，就先讀回該原話，不再問「你是否整理差異表」。若真正缺的是「你本人能不能核准調整」，應直接問員工，不用不存在的公版查詢猜答案。若員工順帶提到偶爾教同事 SAP，系統可保存為旁支線索；只要它不阻塞月結焦點，就不必立刻展開完整訪談。

此結論仍有可轉移限制：OpenAI／Anthropic 的材料主要是通用 agent 工程，Google 的量化研究是 RAG QA，Microsoft 的研究任務不是繁中職務訪談，OPM 也不是 AI context middleware 規格。上述順序是把多方共同原則套入 Caliburn 的 authority、成本與訪談負擔後形成的產品假說；正式品質 eval 依 owner 裁示留到核心成品完成後。

### 7.10 必帶、候選與按需三層

| 層級 | 內容 | 誰決定 | 可否因 budget 直接省略 |
|---|---|---|---|
| 必帶核心 | authority、run objective、當輪回答、受限全域工作索引、目前訪談 target、最新有效更正、blocking contradiction、相關待審 changeset | deterministic middleware policy | 索引本體不可省略；可依已記錄規則降低索引細節，仍超額才明確失敗或分段 |
| 候選 context | 較早原話、相鄰 Task／Duty／OPKS、open gap、未映射線索、少量近期對話 | 結構化 filter＋retrieval＋rerank | 可依可解釋順序降級 |
| 按需 context | 更遠員工來源、完整歷史片段、額外 Skill、低頻 lineage | 模型經受控唯讀工具請求，middleware 驗 scope／budget | 可拒絕並回報理由 |

第一版不先規定例如「Evidence 40%、Recent 20%」的固定比例。不同 run policy、模型窗口、輸出 schema 與資料密度不同；開發期先使用可設定、可觀測、可回退的保守上限，不為了等調參資料阻塞成品，成品完成後再由 eval 決定各類 floor／ceiling。

### 7.11 檢索不是只有向量搜尋

推薦候選順序：

1. deterministic relational／graph lookup：穩定 ID、linkage、speaker、generation、狀態與 source receipt；
2. lexical retrieval：保留職稱、術語、表單名、系統名與員工用字的 exact match；
3. semantic retrieval：找不同措辭但語意相關的舊故事與線索；
4. context expansion：補上 speaker、原回合、相鄰句、所屬 Task／Duty 與修正關係；
5. rerank／budget selection：只把最高價值且不重複的候選送入模型。

Anthropic 的 Contextual Retrieval 實驗中，contextual embeddings 加 BM25 在其資料集將 top-20 retrieval failure 由 5.7% 降至 2.9%；這只能證明 hybrid retrieval 值得成為實驗候選，不能證明相同 chunk、top-k、embedding 或 reranker 對 Caliburn 最佳。若第一版為完成產品而先採用，必須包在可替換設定後、保留檢索與來源紀錄；繁中長訪談 domain eval 延至可用成品完成後再做。

本節檢索只處理同一份文件內的員工來源與其 lineage，不串接公版 RAG。日後若加入 Reference，必須另用獨立 namespace／lane 與 source label；員工來源與公版內容不得因語意相似或去重而合併。

### 7.12 Compaction、provider state 與 cache 的位置

- 原始 session／event、員工原話、核准文件、可修訂理解與 workflow checkpoint 由 LangGraph 的本地 Postgres persistence 保存；
- provider `previous_response_id`、persisted reasoning 或 conversation state 可作短期連續性優化，不能成為唯一 resume 依賴；
- provider／framework compaction 可減少長會話 context，但 opaque 或生成式摘要只能當可重建 artifact；
- prompt cache 只優化穩定前綴，例如精簡 authority、固定 schema 與 Skill metadata；焦點、員工回答、檢索結果放在後段；
- 使用 provider 原生 token counting 或經 conformance 驗證的 tokenizer，在送出前估算，在回應後保存實際 usage；
- 換 provider／model 後可以由本地 state 重新組裝模型請求；不得因 provider reasoning state 遺失而失去來源、核准內容或訪談進度。

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
- 實際帶入多少、為何帶入及被省略區域寫入 context-selection receipt，之後再由成品 eval 調整，不先把 `last_n_messages` 寫成 domain invariant。

概念上有三項 runtime 責任，但不建立三套新的 domain 元件：

1. **LangChain model request／runtime context**：由 middleware 帶入 document、run objective、目前訪談 target、generation／read-set、authority floor、允許的 Skill／tool、model profile revision、run policy 與 budget。LLM 不能擴張 scope 或自行降低必帶內容。
2. **Middleware 組裝的 immutable model input**：包含必帶核心、近期連續性、受限全域索引、目標細節、候選來源、載入的 Skill 與可用工具目錄。每個 item 保留 authority／source／revision 標籤；它只是當次輸入，不是新的 durable state 或 authoritative store。
3. **Context selection receipt**：記錄每次 inference／tool wave 實際載入、按需取得、拒絕或省略的 refs／revision／hash、選取理由、tokens／成本、model／prompt／Skill／tool version、停止原因與結果 lineage。原始內容仍由 Store 保存，receipt 不複製另一份員工原話。

衝突不能用一條總排序解決，必須依問題的 authority 類型判斷：

| 問題 | 生效規則 |
|---|---|
| 員工目前對實際工作的說法 | 最新有效員工更正優先於較舊員工說法、摘要與模型記憶；舊來源保留但標示 superseded |
| AI 目前如何理解 | LangGraph state 中最新有效的可修訂理解優先於舊 hypothesis／summary，但仍須連回原始來源，不能把推論偽裝成員工原話 |
| 目前核准文件是什麼 | 核准文件 channel 是正式 authority；新的員工更正只先形成差異、理解更新、gap 或待審 changeset，未經 accept／edit-accept 不得直接覆寫 |
| 對話如何自然銜接 | 近期訊息與 provider state 可協助理解指涉及語氣，但不能覆蓋員工更正、最新可修訂理解、核准文件或 domain policy |

當輪員工輸入具有雙重角色：在互動上是近期對話，在成功保存後也是 durable employee source。前者可以為節省 context 而縮減相鄰對話，後者則必須依既有 source identity、document scope、correction linkage 與 idempotency 規則持久化；框架不得因 compaction、summary 或 message-window policy 把它降級成只有暫時效力的聊天文字。

因此「最新更正優先」與「核准文件未經員工決策前不變」可以同時成立：前者決定顧問如何理解與下一步要處理的差異，後者決定正式文件目前仍是什麼。Middleware 組裝模型輸入時必須明示這種 divergence，不能先把兩者合併成一個看似一致的欄位。

### 7.13 框架可替代的機制與不能遺失的產品語意

| 成熟框架可直接承接／替代的機制 | 不論由誰實作都必須成立的產品語意 |
|---|---|
| checkpoint／resume、thread state、interrupt／HITL、retry boundary、streaming、tracing | 員工是核准文件 authority；AI 只能提出可審核變更；stale／generation／read-set 不得失效 |
| typed state／reducer、session／store、history、summary、retrieval hook | 可修訂理解不是員工原話；最新有效更正、retire／lineage、文件隔離與可解釋進度必須保留 |
| model interface、structured output、tool schema、dynamic prompt／middleware hook | document scope、必帶核心、來源資格與最小充分 context |
| Skills loader／tool discovery、按需載入機制 | Task／Duty／OPKS 的專業分析方法、版本、eligible-set 與何時不該載入 |
| schema validator、ORM、constraint、transaction、標準 provenance／anchor 型別 | quote 必須能回到有效員工來源；待審 changeset／核准文件的多實體原子變更與 deterministic verifier 不可被一般 approval 偷換 |

本節最初曾把 LangGraph typed state 接管整份 document authority 列為可證偽假說：若它能通過 Source-first、revision／lineage、原子變更、並行 stale check、查詢／匯出、schema evolution 與刪除／保留，舊 store 就應刪除。§9.4–§9.5 曾誤把 checkpointer 與現行 store 並存視為 LangGraph 固有問題；§9.6 依直接替換原則修正，§9.7 又以實測把唯一 owner 細分為 Postgres Store 的 Source 與 Postgres checkpointer 的其餘 DocumentState。舊 Source／Work Model／Current JD write store 仍全部退出；Store 與 State 不寫同一事實，所以不是重疊。

LangGraph／LangChain 目前提供 persistence、HITL、typed state、Store、middleware 與 tracing；Microsoft Agent Framework 提供 session、context provider、Skills 與 workflow checkpoint；PydanticAI／DBOS 分別提供 typed agent capability 與 PostgreSQL durable transaction。它們證明已有多個主流候選可接手大量 plumbing，不代表應同時採用。Google 的託管 Memory Bank 也不符合 current-only 本機產品的預設部署邊界，現階段只學習其「session、memory、explicit state 分離」架構。

這項選型工作已由 §9.12 收斂為 LangChain 1.x＋LangGraph 1.2.x。施工時讓通過 conformance 的 framework primitive 直接承接責任並刪除舊機制；只補 framework 未提供的產品 policy，任何情況都不得建立第二份核准文件、第二份可修訂理解或另一條 AI 直接寫入路徑。

### 7.14 正式 Context eval 後置；開發期只留最小安全網

Owner 已於 2026-08-12 裁示：時間優先，先完成可用的端到端成品，再建立正式 eval。成品完成前不另開以下工作：

- framework-neutral eval dataset、golden transcript 與人工標註計畫；
- A／B、context ablation、LLM-as-a-judge、Pydantic Evals／Ragas runner；
- required-context recall、品質、成本與延遲的量化 release gate；
- 為了建立 baseline 而延後已可垂直交付的產品能力。

開發期仍保留下列最低安全網；它們是一般工程正確性與未來可回溯性，不是正式 eval 專案：

- 現有 unit／integration／contract tests 與 domain invariants 繼續通過；
- authority、document isolation、待審 changeset commit、generation／read-set 等 deterministic safety 不得因趕工取消；
- 每個垂直切片做一次簡單人工 happy-path／resume／approval smoke check，不建立評分資料集；
- context-selection receipt 保留 model／prompt／Skill／tool／source refs／tokens／結果 lineage，避免成品後無法重播；
- 新框架只做它要取代之介面的 conformance test，不比較模型回答分數。

可用成品完成後，再建立下列正式 Context eval 情境：

至少建立下列長訪談情境：

- 員工在後段更正前段說法；
- 回答焦點 Task 時順帶說出新 Task；
- 新線索迫使 Duty regroup；
- Task 尚未穩定時已出現 O／P／K／S 證據；
- 同一術語在不同員工回合出現互相衝突的說法；Reference contamination 情境留到 RAG 另案；
- 員工關閉頁面數日後自然恢復；
- 長歷史中同時存在 active、rejected、retired 與 superseded candidate；
- context 超預算，需要降級但不可丟掉 correction 或 authority。

屆時比較方案 A、B、C 及其變體，至少量測：

- required-context recall；
- irrelevant-context precision／duplicate rate；
- correction／contradiction carry-over；
- off-focus clue capture；
- false authority contamination；
- quote／source attribution correctness；
- 下一題與目前訪談目標／gap 的相關性；
- 待審 changeset 正確性與員工 edit／reject 率；
- input／output／reasoning tokens、cache hit、額外 tool call、延遲與成本。

正式 eval 啟動後，不能只用「token 變少」判定成功。接受候選的最低條件是：domain 品質與 required evidence 不劣於 baseline、authority 錯誤為零，且成本／延遲至少一項有可重現改善。具體門檻屆時依可用成品與真實操作形狀建立，不回頭阻塞第一版開發。

### 7.15 已選框架下仍待施工收斂的參數

- 每種 run policy 的確切 token floor／ceiling；
- adaptive bounded run 的最大 inference／tool step、elapsed time／成本上限，以及哪些 optional result group 能建立足以安全 drop 的 typed dependency contract；在此之前維持 fail-closed；
- 受限全域工作索引的最終 schema、大小門檻、摘要層級，以及 active consultant model profile 的 context window／能力改變時的降級參數；
- 是否第一版就使用 embedding、哪個 embedding／reranker 與 top-k；
- 哪些具體條件值得增加獨立 model-based context planner 或 specialist call；預設不得固定每輪增加；
- LangChain／LangGraph production dependency pin、FastAPI 升級相容 gate、Store／Saver lifespan 與 production schema 細節；主 runtime 選型已由 §9.12 收斂，不再把這些參數誤寫成框架仍未決；
- provider conversation state、compaction、prompt cache 的啟用條件；
- LangChain model request／runtime context 與 context-selection receipt 的 production schema、大小與保存期限。

上述第一版實作細節先由 current-only 邊界、可逆設定、介面 conformance 與人工 smoke 決定，不由「大廠有提供」直接決定；模型品質、最佳參數與成本調優延至可用成品完成後，以長訪談 eval 與實際數據收斂。

### 7.16 Durable input、模型語意結果與業務狀態分離（已確認方向）

Owner 於 2026-08-12 確認：員工回答即使遇到 AI 失敗也必須保存，之後以同一個 input event 重試分析。這項裁決同時收斂一輪處理的責任邊界：**來源事件、模型語意結果、業務狀態與稽核不是同一個 LLM output。**

建議的邏輯順序是：

```text
① application 保存 immutable employee input event
② LangChain context middleware 依 document、訪談重點與 authority 組裝本輪 context
③ 主要顧問按需載入 Skills 與 document-scoped read-only tools
④ 模型提交 typed semantic result
⑤ runtime 保存已完成的 model／tool result 與 execution evidence，deterministic node 驗證、對帳
⑥ verifier 只從通過的候選形成 VerifiedCommitPlan
⑦ 可修訂理解、動態訪談工作、可信進度、待審文件變更、成功 consultant turn／result receipt 在同一 framework transition 提交後才回給員工
⑧ 待審文件變更仍須等員工 accept／edit-accept，才可由 authority command 改變核准文件
```

若 ③–⑦ 任一步失敗：employee input event 保留為 durable source，記錄 typed processing failure；已成功的 provider／tool／verification artifact 可以保留作恢復與診斷，但目前理解、待處理工作、待審文件變更、核准文件與成功 consultant turn 不得出現半套變更。重試沿用同一 input event／run identity；已存在可安全重播的 provider result 時不得盲目重打，新的 provider attempt 才分配新的 attempt identity。

模型只負責必須由語意判斷產生、且有真實下游消費者的內容。邏輯上包含：

1. source-anchored findings：本輪明示內容、更正、矛盾、新線索、候選與 gap；
2. change intents：對可修訂理解或核准文件候選的新增、修正、合併、拆分、重新分組、連結或淘汰建議；
3. next move：維持／切換訪談目標、reason codes 與最多一個主要問題；這只是下一個回應內容，不建立「本輪可停」產品狀態；
4. employee-facing reply：簡短承接、必要摘要與問題，不得宣稱尚未提交的正式變更已生效。

上述是**語意表面**，不要求第一版必須把四類塞入一個巨大 JSON。可以由一次 bounded tool loop、少數按需 specialist result 或一個 final submit contract 實現；實際 topology 仍須以 provider conformance、schema 複雜度、延遲與可維護性決定。固定每輪跑 Extractor／Consultant／OPKS Coder／Projector，或讓罕見 Duty／split／OPKS 結構永久污染常見 schema，都不因本節而成立。

application／framework 應自行產生並保存 run ID、event ID、時間、model／prompt／Skill／tool version、generation、read-set、state revision、context-selection receipt、token／成本、驗證結果與 audit。LLM 不得自行宣稱這些欄位，也不得直接產生 authority commit outcome。§9.12 選定 LangChain／LangGraph 承接 tool loop、typed output、checkpoint／resume 與 tracing；Postgres Store 擁有完整員工來源，Postgres Saver 擁有其餘 durable thread state。任何舊 relational writer 或 frontend cache 都不得鏡射成第二份可寫理解、待審 changeset 或核准文件。

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

1. LangChain context middleware 明示尚有本次可查但未載入的必要來源，主要顧問提出 scope 明確的 document-scoped read-only request；
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

停止內部 run 時不得偽裝成功：已保存的員工回答維持 durable；若尚無可安全提交的語意結果，記錄 structured processing failure 或向員工提出必要問題，不更新可修訂理解、pending-work queue、待審 changeset 或核准文件。若已有可驗證的部分結果，是否允許 partial semantic result 必須由各 run contract 明定，不能由模型臨時決定。

對員工而言，這仍是一位顧問的一次回合：主要顧問負責最後整合、必要摘要、待審文件變更與一個主要問題。read-only context／Skill／tool activity 在既定 capability boundary 內可自動進行；任何核准文件變更仍只經員工 accept／edit-accept 或員工直接編輯。內部只保存結構化 event、tool request／result、context-selection receipt、版本、usage、validation 與 lineage，不要求或暴露模型私有 chain-of-thought。

這項產品裁決已映射到選定的 LangChain 1.x＋LangGraph 1.2.x：agent middleware／tool loop 承接 adaptive bounded run，checkpointer／Store 承接 durable resume，interrupt／Command 承接必要澄清與文件審核，deterministic nodes 保證核准文件 authority。其他框架比較只保留為 §9 的選型歷史，不再是目前 plan 的平行實作候選。

#### 7.16.2 迭代與補查 budget：沒有通用最佳次數（2026-08-13 研究結論）

進一步查核截至 2026-08-13 的官方實作後，不能把「最多補查兩波」宣稱成大廠標準或研究證明的最佳值。OpenAI 最新 guidance 要求依 bounded stage 明定 concurrency、retry、stopping limits 與 required evidence，但不給通用次數；Anthropic Tool Runner 提供 `max_iterations`，範例使用 10，官方同時允許 application 隨時 `break`；Microsoft Agent Framework 的 loop 預設上限也是 10，但明確警告 completion predicate 可能失敗、模型可能停滯、evaluator 也具有機率性，因此 autonomous loop 永遠要有上限，而且該 looping 功能仍標為 experimental；LangChain 則把 model-call 與 tool-call limit 拆成 run／thread／per-tool middleware。這些「10」是 runtime 安全預設或文件範例，不是互相獨立的職務訪談品質證據，不能直接複製成產品規則。

Google 2026 年 ADK 2.0 的方向更接近本產品：已知 routing、固定 business rule、錯誤與 HITL 用 deterministic workflow；只有模糊自然語言與動態判斷交給 LLM。其官方示例把 LLM node 設成 single-turn，並指出讓模型反覆執行可預知流程會增加 tokens、latency、prompt noise、重複工具與脫軌風險。OpenAI 也建議能由 bounded code 完成的 filtering／ranking／dedup／aggregation 由程式處理，語意判斷、approval 與最終驗證保留直接 model turn。共同趨勢不是「更長的自由 Agent loop」，而是 **hybrid agentic workflow：程式控制邊界與完成條件，模型只處理不可預先寫死的認知工作。**

因此 Caliburn 應把 budget 拆開，不使用單一 `max_steps` 混算所有事情：

- **model inference budget**：限制主要顧問與必要 specialist 的模型回合；
- **lookup-wave budget**：一次模型判斷可以提出多個彼此獨立的唯讀 request，由 application 安全批次／平行執行；一波不是一個 tool call；
- **per-tool／total tool budget**：限制 semantic search 或大型員工來源讀取，直接 relational lookup 可有不同上限；本次沒有公版 Reference tool；
- **technical retry budget**：網路／rate-limit／schema 等可重試失敗與語意探索分開計數，但仍累計 elapsed time、tokens 與成本；
- **no-progress budget**：重複 request fingerprint、相同結果 hash、沒有新 source／revision，或 sufficiency reason 沒有可解釋變化時提早停止；
- **human-interrupt boundary**：只有員工能回答、需要員工判斷或涉及 authority 時立即退出自動 loop，不消耗剩餘額度硬猜。

第一版可採下列**候選 run execution policy**，作為人工 smoke 的保守起點，而不是不可變 domain policy：

1. 直接快速路徑：deterministic context 已足夠且不需補查時，同一主要顧問一次 inference 直接提交 compact typed result。
2. 補查路徑：同一 bounded agent inference 可提出一批 scope 明確的唯讀查詢；工具結果回到同一 run 後，由同一主要顧問在後續 inference 提交 compact typed result，不新增 planner／scribe／critic 或第二位顧問。
3. 只有第一批結果揭露新的穩定 ID、source receipt、矛盾或先前不可知的明確指標，而且確實對 unresolved reason code 有預期貢獻時，才允許第二波。
4. 互動式正常回合的起始 hard ceiling 可設為 **三次 model inference 與兩波 lookup**；數值放在可替換的 run execution policy，模型與 provider 仍取自同一 consultant model profile，不寫進 Task／Duty／OPKS domain invariant。一次 wave 可批次多個獨立 read-only request，因此不以「兩波」誤限成只能查兩筆資料；不需補查時仍只做一次 inference。只有 exact conformance 失敗才把最後一次明確切成 tool-free finalization。
5. 到達上限、重複查詢或沒有新資訊時，不啟動額外 evaluator／judge loop；輸出 `EMPLOYEE_CLARIFICATION_REQUIRED`、`DEFER_WITH_VISIBLE_GAP` 或 structured processing limit。不能安全形成語意結果時不更新可修訂理解。

這個 run execution policy 選擇三次 inference／兩波 lookup，不是因為外部 benchmark 證明它最佳，而是它完整容納「初始判斷 → 一般補查 → 新指標例外補查 → 最終整合」，同時比 SDK 常見的 10-turn 通用上限更符合即時員工訪談的延遲、成本與可理解性。日後若某類核心 run 有獨立 success criteria 且確實需要更深探索，才另設 budget；不能默默放寬所有員工回合，也不因拆出 Skill 就自動換模型。

這也收斂框架需求：LangChain／LangGraph 必須分別限制 model／tool calls、攔截重複或錯誤工具、批次安全的唯讀查詢、在 limit／HITL 時保存可恢復 state，並輸出完整 trace／usage；只在框架沒有直接 primitive 的差額補最薄的 run、authority、progress 與成本 policy。

### 7.17 理解校準／可編輯假說的框架選型歷史（2026-08-12；現行裁決見 §9.12）

本節保留候選比較與當時使用舊名稱對照的選型歷史，不是目標 schema。現行施工只採 LangChain 1.x＋LangGraph 1.2.x，舊 `Work Model`／`Focus`／`Proposal`／`Current JD` 名稱不得回到新 code 或 contract。

主流框架沒有一個現成功能叫做「專業職務分析的目前理解」，但已共同提供組成它的通用元件：顯式 state、可序列化的人工輸入請求、pause／resume、事件或 checkpoint 歷史，以及把人工回覆送回原流程。這證明 Caliburn 不必自行重寫整套 durable HITL runtime；同時也證明不能把框架的 approval 直接等同於員工核准 JD。

| 候選 | 可直接借用的能力 | 對 Caliburn 的判斷 |
|---|---|---|
| LangGraph | `interrupt()` 可送出結構化 payload、暫停並保存 state；官方直接示範 review／edit state；checkpoints、`update_state` 與 time travel 保留舊路徑並可從修訂後狀態繼續 | **§9.7 v0.6 的主方案，核心 state／HITL 已通過探針**。StateGraph 可直接成為 Work Model／Focus／Proposal／Current JD 的唯一 write owner；Source 則由同一家族 Postgres Store 單獨擁有；node resume 仍會從節點開頭重跑，前置副作用必須 idempotent |
| PydanticAI V2＋Harness＋DBOS | model／provider abstraction、typed output、Capabilities／hooks、Agent Skills、compaction、deferred tools、dynamic model 與官方 durable-execution integration；DBOS 補 workflow／queue／transaction recovery | **§9.7 v0.6 的整套 fallback**。V2 已不是薄 wrapper，但若另以 SQLAlchemy／`eventsourcing` 重建 Work Model／Proposal／JD，對本案的同目的元件直接替換率低於 LangGraph-first；Gate 4-A 未觸發切換條件 |
| Google ADK 2.0 | graph `RequestInput` 可攜帶 message、structured payload 與 response schema；Session 分 events 與可變 state；rewind 恢復 session state 且保留被 rewind 的事件供稽核 | 技術形狀相容，但 ADK 2.0 graph HITL 很新，且 Google 託管 runtime／memory 不符合本機預設邊界；目前只作設計對照，不構成換框架理由 |
| OpenAI Agents SDK | approval interruption 與 resumable state 分離；run 暫停時回傳 interruptions＋state，人工決定後恢復同一 run | 適合 provider-specific tool approval，不能直接提供可編輯 Work Model；若作主 runtime 會提高 provider lock-in，較適合作 adapter 或 conformance 對照 |
| Microsoft Agent Framework | provider clients、session、context providers、memory、middleware、Agent Skills、graph workflows、typed request／response HITL 與 checkpoint；官方定位為 Semantic Kernel／AutoGen 的直接後繼 | 不是「整套 experimental」：graph workflow 與核心 agent 能力已有正式文件，Functional Workflow API 等局部仍 experimental；但 2026-07 官方 self-host 文件也明列 Python hosting helpers 仍 prerelease，且 application 自行負責 `SessionStore`、checkpoint mapping 與 durable storage。需先證明本機 PostgreSQL adapter 的淨成本，不能只看功能表判定成熟度 |
| Anthropic SDK／Managed Agents | tool runner 處理 tool loop、conversation state 與 validation；需要自訂 HITL／logging 時使用 manual loop；Managed Agents 可把 tool 設為 `always_ask` | 支持「敏感副作用由人決定」與 structured notes／外部 memory，但沒有現成的可編輯 domain hypothesis workflow；不值得只為本功能綁定 Anthropic runtime |

共同限制很明確：框架不知道何時一項可修訂理解的變化「重要到必須讓員工看見」，也不知道員工更正應如何影響 Story、Task、Duty、OPKS、gap、pending work 與待審 changeset。下列內容仍必須是產品 policy；以 framework state／interrupt／command、Pydantic 與 SQL constraint 表達，不另保留現行 class／table：

- 理解校準的 trigger policy 與 blocking／non-blocking 規則；
- LangGraph interrupt payload 所需的訪談目標、摘要、uncertainty、source refs、next move 與 revision；
- typed correction command 如何先保存員工原話、supersede／rebut 舊假說並重算下游；
- 理解校準、待審 changeset 與核准文件 authority 的硬邊界；
- stale revision、document isolation、generation／read-set 與原子提交。

本節原先把「graph state 與 Work Model 重疊」本身當成 LangGraph 扣分，這與 §2.11／§2.14 的 owner 裁決不一致。§9.4–§9.5 雖然擴大了候選面，仍反覆把既有 relational business store 當隱性前提；owner 於 2026-08-13 再次糾正後，由 §9.6 修正替代原則、§9.7 補上實測：DocumentState 直接成為 Work Model／Focus／Proposal／Current JD owner，Postgres Store 直接取代 Source journal。舊 writer 退出；兩個機制同時可改同一事實才叫重疊，按事實分工的直接替換不叫重疊。

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
| 現有 Next／React＋framework-neutral typed contract | 完全控制固定側欄、校準卡、來源展開、revision 與無障礙；可作 LangGraph state／interrupt 的自訂呈現 | 保留產品 UI 語意，不代表必須保留舊 UI state plumbing；若不採 LangGraph Agent Streaming Protocol，仍需一個薄 transport adapter |
| LangGraph frontend `useStream`／HITL | interrupt payload、durable pause／resume、React 等 client hook；review card 可放 transcript、queue、dashboard 或 modal，也支援 edit／respond 與自訂表單 | **§9.9 已完成實測後未選第一版**。若完整採用，它能直接替換 thread／run／replay／interrupt frontend；但本產品只需 verified product status、typed input 與 durable view，完整 protocol 會多出未使用的 agent surface，自建 compatible backend 又需自行承擔 replay／filter contract。由 Caliburn 定義並渲染 `UnderstandingCheckpoint`，runtime interrupt 仍由 LangGraph 承接 |
| OpenAI ChatKit widgets／actions | card、list、badge、editable text、form、typed action、server/client handler 與 loading state | 元件形狀符合，但綁 ChatKit／OpenAI conversation surface，且常駐產品側欄仍需自訂；不值得只為一張卡提高 provider／UI lock-in，可作 contract 與互動範例 |
| AG-UI＋CopilotKit／Microsoft Agent Framework | SSE、HITL、shared state、custom／generative UI、前後端 tool calling；Microsoft 2026 官方整合已支援 Python FastAPI，但目前安裝指令仍帶 `--pre` | 適合 agent 以遠端服務供多個 client、需要跨框架 state sync 時。Caliburn 是本機單一 Web 產品，現在引入會增加第二套 session／state protocol、authority 對映與 preview 成熟度風險，先不採用 |
| Google A2UI 0.9 | declarative JSON、受信任元件 catalog、incremental update、React renderer、client-defined validation 與多 transport | 是 2026 年重要趨勢，但仍是 pre-1.0，主要解決跨 agent／跨平台的動態 generative UI。Caliburn 的核心校準 UI 應固定且可審查，不需要讓 LLM 自由組版；目前只借用「白名單元件、資料與呈現分離、增量更新」原則 |
| Microsoft Adaptive Cards | JSON card、跨 host responsive rendering、inputs／actions、視覺層級與 progressive disclosure 指南 | 適合 Teams／Outlook／M365 多 host；目前不是 Caliburn 的部署面。可借設計原則，不引入 runtime |

#### 收斂後的第一版邊界

第一版只定義三種產品邊界 payload，由 LangGraph primitive 擁有生命週期，再由 Web 原生元件呈現；它們不是三個新的 domain 子系統：

1. **API read projection**：application 從 LangGraph durable state、員工來源與核准文件組裝側欄；status、source type、revision 與 blocked reason 不由 LLM 自報。
2. **LangGraph interrupt payload**：deterministic trigger policy 產生 soft／branch-blocking 校準請求，攜帶變更摘要、source refs、受影響範圍與允許動作。
3. **Typed correction command**：員工確認、修正或稍後處理；server 驗證 revision 後先保存 durable source event，再由 LangGraph reducer／node 重算。

依 §9.7 v0.6，校準生命週期由 LangGraph state／interrupt／Command 承接，不另建 durable domain queue；backend restart 已實測。§9.9 再比較 Agent Server、compatible custom backend 與產品 typed SSE：第一版由 FastAPI 原生 SSE 只投影 durable run／interrupt 狀態，瀏覽器另以 typed command resume；不把完整 LangGraph Agent Protocol 搬進產品 wire。這不是保留舊 transport，而是用 FastAPI／瀏覽器標準直接替換 framing、heartbeat 與 reconnect plumbing；AG-UI／A2UI 仍只在跨框架、多 client 或動態 generative UI 需求成立時評估。[LangChain frontend overview](https://docs.langchain.com/oss/python/langchain/frontend/overview)、[FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

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

1. **核心職務分析內容都可送。** 員工原話、目前理解、JD、Task／Duty、OPKS 與必要 quote anchor 都可由 LangChain context middleware 判斷送出；不另做欄位級允許清單。本階段沒有 Reference payload。
2. **只做一次清楚揭露。** 產品在設定或首次使用時說明會使用外部 AI provider；不對每輪 inference、Skill 或 read-only tool 重複詢問。
3. **本地是可恢復權威。** provider 端預設採不依賴持久 conversation 的推理方式；即使使用短期 cache、compaction 或 session 優化，也必須能從 LangGraph Postgres Store／Saver 的員工來源、可修訂理解、核准文件、durable thread state 與 execution receipts 重建，不得成為 resume 的唯一條件。
4. **不主動擴大遠端保存。** 接受商業 API 的標準 abuse／safety retention，不要求 ZDR；但不主動 opt in 訓練、data-discount sharing、完整遠端 Input／Output Logging，或為了方便除錯建立第二份長期 transcript。
5. **路由必須可說清楚。** 第一版維持一個明確 model ID 與 provider allow-list，不做無聲跨模型 fallback。至少記錄設定模型與設定 provider；若未來允許 gateway fallback，該次 run 必須記錄實際 model／provider、attempt chain、成本與停止原因，候選也必須來自明確設定，而不是任意 router alias。
6. **內容選擇仍由 LangChain context middleware 控制。** 不限制外傳不代表把完整歷史、所有 evidence 與全部 OPKS 每輪重送；仍採必要核心、受限全域索引、訪談目標細節與按需展開，以品質與成本為理由控制 context。
7. **provider-specific state 是可替換優化。** `store=false`、ZDR、region、cache TTL 等能力可由 adapter 顯式映射，但 domain 與 use case 不依賴任一廠商欄位。某 provider 不支援某項控制時，回到已核准的標準商業 API 政策，不偽裝成 ZDR。

這項裁決不等於永遠拒絕 fallback、provider state 或遠端 observability；它要求這些能力未來以顯式、可追溯、可關閉的 adapter／runtime 設定加入。第一版不需要建立讓員工挑選 retention policy 的複雜 UI，也不需要為尚未存在的企業合規需求預做多套資料模式。

### 7.20 模型、provider 與參數 profile 控制面（2026-08-13 維護者控制與第一版粒度已確認）

Owner 已確認：**模型、provider 與底層參數由本機維護者透過版本化 profile 管理；受訪員工不在訪談介面直接操作 `temperature`、reasoning effort、token limit 或 routing 等原始旋鈕。** 第一版可以由設定檔或維護者設定面承接，尚不要求獨立管理 UI。即使維護者與受訪員工在本機上可能是同一個人，產品責任仍分開：前者配置執行環境，後者提供工作事實並決定 JD 內容。

控制面必須分開四項責任，避免把「這輪要做什麼」誤寫成「這輪要換哪個模型」：

1. **Versioned consultant model profile**：保存人可讀名稱、requested provider／model、模型能力需求、品質／延遲／成本意圖、共同模型參數預設、允許的 routing／fallback 與 provider-specific 選項；修改產生新 revision，不回寫舊 run 的設定歷史。API key 只保存 secret reference，不進 profile 內容、trace 或 prompt。
2. **Versioned run execution policy**：依 run kind 保存允許的 Skills／tools、typed input／output contract、context／output／model-call／tool／時間／成本上限、retry 與內部終止規則。不同 run kind 可以有不同 policy，但這只改變工作範圍與執行預算，**不等於不同模型**，也不建立員工可見的「本輪停止」狀態。
3. **Resolved execution snapshot**：每個 model-bearing run 開始前，由 application／adapter 合併 model profile revision、run policy revision 與當時模型能力，解析成 immutable snapshot；至少記錄 requested provider／model、可在送出前確定的 resolved model ID／provider allow-list、實際送出的有效參數、能力檢查、budget、route policy 與 adapter version。動態 gateway 最後選到的 endpoint 留給 attempt receipt 記錄；LLM 不得自行改模型、提高預算或放寬 fallback。
4. **Run／attempt receipt**：回應後保存 provider 回報的實際 model／endpoint（若供應商提供）、attempt chain、usage、成本、latency、cache／state 使用情況、內部終止原因與錯誤。這是重播、歸因與日後比較的執行證據，不是可修訂理解或核准文件。

第一版的模型粒度收斂為：**整個生成式職務分析顧問只有一個 active consultant model profile。** 一個員工回合即使因補查而有多次 inference，或載入不同 Skill／tool，仍沿用該 run 開始時解析出的同一份 model profile snapshot。這裡的「一個」不是說整個 monorepo 只能出現一種 AI 模型；embedding、reranker、OCR 等非顧問型技術模型可以有各自的版本化設定，但不得被包裝成另一位職務分析顧問或取得產品 authority。

| 產品能力 | 第一版模型邊界 |
|---|---|
| 主要顧問、工具結果回來後的再整合 | 使用同一個 active consultant model profile |
| Task／Duty／O／P／K／S Skills | 是方法與 context 的 progressive-disclosure 邊界；不擁有 model profile，也不因載入而另開模型呼叫 |
| structured semantic result | 是 output contract，不是模型角色；無論最後由一次或受限多次呼叫形成，都使用同一個顧問 profile，schema／verifier 也不是另一個「結構化分析模型」 |
| 同文件內員工來源檢索 | relational／lexical lookup 為第一階段基線；若啟用 embedding／reranker，只是可獨立版本化的 retrieval 技術模型，不等於可見顧問或分析 authority |
| 未來 bounded specialist | 只有實際建立獨立 model call 與 typed contract 時才算呼叫邊界；預設仍繼承全域顧問 profile，第一版不配置 per-specialist model override |

公版 iCAP Reference／RAG 不在第一階段模型拓撲；日後另案加入時，檢索技術模型仍不得成為另一位顧問或取得 authority。

框架即使提供 dynamic model selection，也只代表**可以實作**，不代表產品應啟用。未來若要讓某個 model-bearing run kind override 全域 profile，至少要同時滿足：它具有獨立 input／output／evidence／success criteria；所需 modality／capability 無法由全域模型提供，或成品後代表性評測證明替換能在品質不退步下改善成本／延遲；路由由 application 的版本化政策決定並留下 receipt，而不是由 Skill、LLM 或 gateway 自由挑選。未達這些條件時，只調整 Skill、tool、schema 或 run policy，不拆模型。

生效與失敗規則如下：

- model profile 或 run policy 變更只影響之後新建立的 run；已開始的 run 與可安全恢復的 attempt 沿用原 resolved snapshot，不在中途偷偷換模型或預算；
- 若原模型已退役或原能力無法再取得，不假裝精確 resume：保留舊 artifact，建立帶新 snapshot 的新 attempt，重新檢查 authority generation／read-set，並讓 route change 可追溯；
- 不建立一組假裝跨廠商完全等價的 raw parameter bag。consultant model profile 表達共同意圖與能力要求，各 adapter 顯式映射；不支援的參數在啟動／解析時拒絕或明確省略並留下原因，不可靜默接受後假裝已生效；
- 第一版不允許 gateway alias、動態 router 或 provider fallback 在沒有 receipt 的情況下改變實際模型。若使用可漂移 alias，必須同時保存 requested alias 與 provider 可回報的實際 model ID；production 預設優先使用供應商建議的固定／stable ID；
- 員工可以看到目前使用的 profile／模型名稱與必要揭露，但不需要理解廠商特有參數。未來若提供「較快／平衡／品質優先」等核准 preset，仍由維護者把 preset 映射到版本化 profile，而不是把原始旋鈕放進每回合訪談。

這些規則有明確的一手資料背景：[OpenAI Model guidance](https://developers.openai.com/api/docs/guides/latest-model) 要求依 workload 明確選模型與 reasoning effort，以代表性工作比較品質、延遲與成本，並指出「有多個呼叫」本身不足以證明需要另一種工具編排路徑；其 [Skills 文件](https://developers.openai.com/api/docs/guides/tools-skills) 直接示範在一個指定 model 的 Responses request 掛載多個 Skills。[Anthropic Agent Skills](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) 把 Skills 定義為同一個 general-purpose agent 按需載入的可組合知識；[Google ADK Skills](https://developers.googleblog.com/en/developers-guide-to-building-adk-agents-with-skills/) 也以一個設定單一 model 的 root agent 掛載整組 SkillToolset。[LangChain Agents](https://docs.langchain.com/oss/python/langchain/agents) 把 model、tools 與 structured output 列為同一 agent 的不同元件，而 [dynamic model selection](https://docs.langchain.com/oss/python/langchain/middleware/custom#dynamic-model-selection) 是可選 middleware；[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/overview/) 則明示單次 LLM call（可含 tools）足夠時使用 agent，只有多個 agent／function 必須協調時才需要 workflow。

另一組來源處理版本與路由追溯：[Anthropic model versioning](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions) 區分 pinned model ID 與會指向較新 snapshot 的舊式 alias，其 [Messages API](https://platform.claude.com/docs/en/api/typescript/messages/create) 也顯示新模型可能不再接受 `temperature`／`top_p`；[Gemini Models](https://ai.google.dev/gemini-api/docs/models) 明確建議 production 使用 specific stable model，而 `latest` alias 會隨版本熱切換；[OpenRouter routing](https://openrouter.ai/docs/guides/routing/provider-selection) 則顯示 provider order、fallback 與參數支援都需要顯式控制。

可轉移限制：上述資料證明「同一模型可組合 Skills／tools／structured output」「動態換模型只是可選能力」以及「實際路由要可追溯」，**沒有公開 benchmark 證明單一模型或多模型對繁中職務訪談何者效果最佳**。因此第一版單一顧問 profile 是依本產品「一位顧問、按需 Skills、避免過早增加路由與失敗面」做出的保守裁決，不冒充外部研究結論。

本節仍不選定預設模型 ID、確切參數值、價格門檻或設定 UI；但第一版 profile 數量已定為**一個 active consultant model profile**，不再等待 run kind 分流策略決定。品質／成本最佳值仍依既定決定，等可用成品完成後再用代表性長訪談 eval 調整。

## 8. 已識別的流程風險與優化方向

### 8.1 焦點隧道效應

風險：AI 專注當前 Task 後漏掉回答中的其他工作。

方向：每輪先做全域理解，再做焦點追問；保存未映射線索與新 Task 候選；開發期以人工 smoke 確認基本保存路徑，成品完成後再以 capability eval 量測「旁支線索不丟失」。

### 8.2 Duty 過早定型

風險：初步 Duty 會成為分類盒子，後續 Task 被硬塞進去。

方向：初期只稱暫定責任區域／Duty hypothesis；有足夠依據時隨時可形成分組提案，但不得宣稱永久定稿；任何新 Task、O/P/K/S 線索都能觸發 regroup review。

### 8.3 文件變更審核疲勞

風險：每句話都跳出核准卡，訪談無法自然進行，員工也會機械接受。

方向：累積成一個有意義的小段落再提案；高影響 topology change 與低風險文字修改可採不同呈現，但不得降低員工 authority。

### 8.4 OPKS 填表與尾端衰減

風險：模型為填滿欄位虛構內容；或晚期 Task 的 gap 尚未全部關閉就結束訪談，已回答的新證據沒有重新形成候選。

方向：允許空白與 terminal reason；將 O／P／K／S 方法按需載入，避免每回合塞入完整 OPKS prompt；追蹤每個工作假說與各軸的分析／gap／receipt 狀態；以長回合 pilot 比較「現行獨立 OPKS operation」與「同一顧問按需 Skills」的品質、遺漏、成本與尾端衰減。

### 8.5 Reference 錨定（後續 RAG 階段風險）

風險：公版文字專業完整，使 AI 與員工把「可能有」誤認成「本人有」；若每個檢索命中都成為持久狀態，還會造成重複詢問、來源噪音與假權威。

方向：目前不實作。日後另案仍採 blind-first、獨立來源 lane、中立問題與有產品影響才持久化的 challenge receipt；公版來源永遠不自動提高事實權威。

### 8.6 假進度與假完成

風險：以 Task 數、固定問題數或 0–100% 宣稱完成；新線索出現時進度倒退。

方向：使用「目前已知」的 coverage、sufficiency、具體 gap、待審 changeset 與 reason code；「目前已足夠」只是可重算建議，不是完成／停止訪談狀態。

### 8.7 內部 Agent loop 膨脹

風險：因框架可用或希望回答更完整，讓每輪固定經過 planner、extractor、critic、OPKS coder 與多個 specialist，導致延遲、成本與錯誤路徑快速增加；員工仍只看到一個答案，反而難以理解為何卡住或失敗。

方向：預設單次主要顧問 inference；只因必要 context、工具結果或邊界明確的專業 contract 增加步驟；由 application 強制 no-progress、重複 request、步數、token、時間、成本與 authority 終止條件。每輪保存實際 topology 與 usage，成品完成後再由長訪談 eval 判斷哪些額外步驟值得保留。

## 9. 升級進度與下一步

> **現況與閱讀順序（2026-08-14）**：產品大方向以 §1–§8 為準；框架選擇以 §9.12 為準；自然續談、舊名稱不得回流、第一版 LLM 範圍與「本次不做 RAG」以 §9.13 為最新 owner 裁決；施工前覆蓋審核與後續逐 Task 防偏規則見 §9.14；Task 10 真模型與 Evidence 修正見 §9.15。§9.1.1–§9.11 是按時間保留的研究／反證歷程，其中 `Work Model`、`Focus`、`Progress`、`Proposal`、`Current JD` 等只描述被替換的舊機制，任何「RAG 是本次 final gate」敘述都已被 §9.13 取代，不得拿來施工。目標架構見已 Accepted 的 ADR 0060 與其部分 successor ADR 0061；施工順序見 `docs/plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md`。

### 9.1 討論與設計關卡（2026-08-14 現況）

討論依下列順序進行。框架研究可提前蒐證，但不得跳過產品情境與目標能力，反向把框架現成功能寫成產品需求；現行 module 只作現況與切換風險證據，不能當新架構模板。

| 關卡 | 狀態 | 要回答的問題 | 離開條件 |
|---|---|---|---|
| 0. 產品北極星 | 已收斂 | 顧問是誰、員工有何權力、何謂完成 | §1–§6 的大方向無已知根本衝突 |
| 1. 端到端情境 | 已收斂 | 正常、改道／更正與失敗恢復時，員工和顧問各自看到、知道、做什麼 | 情境涵蓋訪談重點、全域吸收、動態 Task／Duty／OPKS、進度、待審文件變更、自然離開／續談與匯出，且沒有未揭露的權威跳躍 |
| 2. 目標能力地圖 | **已收斂（2026-08-13 owner 確認）** | 為了實現情境，系統必須具備哪些能力與不變條件 | 每項能力都有輸入、輸出、authority、持久化責任、失敗語意與 `Replace／Wrap／Retain` 判準 |
| 3. 框架組合選型 | **已收斂（§9.12）** | 哪些成熟元件直接承接中立產品目的 | LangChain 1.x＋LangGraph 1.2.x 通過目的層與工程 conformance；其他候選只作歷史／fallback，不平行施工 |
| 4. 目標架構 | **ADR 0060 Accepted；ADR 0061 Accepted（schema-only）** | framework primitive 如何合作，資料／API／Web／context／恢復／切換如何落地 | 每個目的都有 framework owner、可刪除舊機制、最薄產品 policy 與驗收；compact wire 已核准，Tool／Skill loading 另議 |
| 5. 實作計畫 | **Tasks 1–9 已完成；Task 10 已依 §9.16 修訂** | 如何在隔離 worktree 內完成受限 Big-bang 並可驗證地切換 | Task 10 先 compact wire 與 deterministic gate，owner 授權後跑一次 exact live canary；RAG、能力級別／A 的 LLM 分析及正式 eval 均不在本階段 |
| 6. 實作與切換 | **進行中；Task 10 暫停於決策 gate** | 依核准計畫施工、審核、驗證與切換 | ADR 0061 核准、focused/full gate、真模型 smoke 與 owner review 完成後才可交付 |

每關卡收斂後應更新本表、在相鄰段落補齊 §0.1 的決策帳本，並以只包含該關卡文件變更的 commit 保存。若細節研究發現較佳方向但會改變已確認北極星，必須先回到產品層與 owner 討論；不得在 framework matrix、schema 或實作計畫中悄悄翻案。

#### 9.1.1 Gate 1 北極星回歸審核（2026-08-13 歷史紀錄；衝突處以 §9.12–§9.13 為準）

本輪重新對照 §1–§8、Task discovery／boundary、Duty／iCAP 欄位與 OPKS 裁決研究。結論是：移除 §3.1.2 的專用 `Resume Brief` 過度設計後，沒有發現會阻止進入能力地圖的產品層衝突。

- **產品角色未偏移**：仍是一位 AI 專業職務分析顧問主動帶路，不是填表器、固定 wizard 或員工可見的多 Agent 組織。
- **專業分析未被框架取代**：Task 仍是跨故事形成、有 meaningful outcome 的角色責任；Duty 是可重整的共同目的／責任分組；O／P／K／S 必須連回工作與行為證據，不能靠 schema、taxonomy 或 Reference 自動補滿。
- **流程未回到剛性階段**：廣度盤點與深度訪談可反覆切換；Task、Duty、O、P、K、S 都按當輪焦點與證據載入方法 Skill 並互相校正。2026-07-24 的 Phase 5／6 與 2026-08-04 的獨立 per-Task OPKS child 只描述當時的 prompt／operation 限制；§3.6、§3.8 與 §5.3 是本次升級的 successor 產品方向。保留的是 evidence linkage、gap、unknown／not applicable、輸出量控制與失敗邊界，不保留固定順序或呼叫拓撲。
- **員工 authority 未弱化**：AI 更新 Work Model、agenda 與候選；只有可編輯 Proposal／changeset 經員工決策，或員工直接編輯，才能透過 authority seam 改 Current JD。
- **記憶與 Context 未變成第二份真相**：同一員工的原話、最新有效更正與來源關係完整保存；模型只取得本輪必要 context，provider state／summary／旁路 memory 不得取代 document authority。通過 conformance 的 Postgres Store 單獨擁有 Source、framework State／checkpointer 單獨擁有其餘 DocumentState；它們不是同一事實的雙寫，舊 Source／Work Model／Current JD write store 必須退出。
- **進度與完成沒有假精確**：顯示目前已知 coverage、各範圍分析深度、具體 gap 與待決 Proposal；AI 解釋是否足夠，員工決定繼續、暫停或在看過缺口後強制匯出。
- **正常、改道、更正、失敗與恢復均有權威邊界**：旁支線索保存但不任意打斷；更正只使受影響依賴失效並重查；未完成模型處理不產生半套 Work Model／Proposal；正常重開只需恢復既有狀態，不建立專用子系統。
- **範圍仍受控**：不新增登入、多租戶、公司文件／SOP、多人協作或先期完整 eval；RAG 是核心顧問完成後的 final integration gate，不反向定義員工事實。

Gate 1 的離開條件已有對應情境與裁決，因此進度移到 Gate 2。現在仍未決的 §7.15 項目皆是 framework／architecture／operation policy 參數，不是要求繼續發明產品功能。後續若框架研究發現無法滿足既有不變量，先報告衝突；不得直接縮小產品目標或增加框架現成功能。

**防止再次過度設計的停止規則**：能力地圖只列端到端情境真正需要的責任；框架選型只比較能刪除／承接實作的成熟元件；沒有具體情境、失敗語意或可刪舊碼的能力不進第一版。GraphRAG、自由多 Agent、額外 planner model、專用返回流程與第二份 memory store 都維持不採用／延後，除非後續 conformance 證明核心情境無法以較簡單方案完成。

### 9.2 2026-08-13 當時的切換邊界與能力地圖（歷史；已由 §9.12–§9.13 取代）

產品北極星、白話流程、進度、記憶／Context、員工 authority、框架替換原則與「AI 顧問子系統受限 Big-bang」已確認。關卡 2 現在建立**與舊 module 無關的目標能力地圖與切換邊界**：

1. 顧問互動與受控 orchestration；
2. 同一員工的來源記憶、Context selection 與可恢復長流程；
3. 可演化的工作假說、焦點／agenda 與三層進度投影；
4. Task／Duty／O／P／K／S 按需 Skills 與 deterministic verification；
5. 跨 Task／Duty 的 typed changeset、員工審核與 Current JD authority；
6. iCAP Reference／RAG coverage challenge；
7. 可替換 model／provider、參數 profile、usage、trace 與失敗恢復；
8. 支援上述流程的 API／Web 體驗。

切換邊界已於 2026-08-13 收斂：iCAP Reference／RAG 是 final gate，worktree 內先做核心顧問、後接 RAG，完成後一次切換；目前也沒有需保留的真實 JD／訪談資料，因此採 fresh-schema hard cut，不做舊 AI 狀態 migration。跨 Task／Duty／OPKS 的 Proposal 粒度已確認為「可編輯 review bundle＋必要原子子群組」；「可演化工作假說」已於 §7.2.1 收斂；模型／provider／參數的維護者控制權、版本化 profile、run snapshot 與 route receipt 亦已於 §7.20 收斂，第一版採單一 active consultant model profile，operation 只配置 execution policy。現在先完成 framework-neutral capability map；確認後才建立 framework matrix，不能再以 Skill、structured output 或 Reference 的名稱預先切出多模型拓撲。

能力地圖確認後，再逐列建立「目標能力／現況／框架候選／`Replace|Wrap|Retain`／仍需自寫語意／successor ADR／驗收情境」矩陣，回答哪些成熟元件能真正取代現有實作。LangGraph／LangChain、OpenAI Agents SDK、Microsoft Agent Framework、Google ADK、Agent Skills、Pydantic＋SQLAlchemy＋PostgreSQL、W3C anchor／provenance 等目前都只是候選或標準；任何框架都不得以舊 module 拓撲作為新設計目標，也不得在 conformance 前取得產品 authority。研究稿仍不能直接當施工授權。

### 9.3 目標能力地圖 v0.1（Gate 2 研究候選）

這張地圖只從 §3.11 端到端情境與既有產品裁決倒推能力，不加入框架展示頁上看起來有趣、但沒有產品失敗要解決的功能。三種處置的意思是：

- `Retain`：保留產品目的、專業方法、不變量或穩定 seam；不等於保留現有 class／table／module；
- `Wrap`：讓成熟框架承接通用機制，但放在 Caliburn port／adapter 後，不能取得 domain authority；
- `Replace`：conformance 通過後刪除現有重複 plumbing／舊拓撲，不長期雙軌。

同一能力可以同時「Retain 語意、Wrap 框架、Replace 舊實作」。這不是含糊，而是把產品責任與工程機制分開。

| ID | 核心能力與 `input → output` | Authority／持久化責任 | 失敗語意 | 第一輪處置方向 |
|---|---|---|---|---|
| C1 | **員工來源接收與更正**：回答／直接修正／取代意圖＋idempotency identity → immutable source event、來源關係與已保存回執 | 員工原話是來源 authority；模型前先存 PostgreSQL；framework history 不是權威 | 重送不重複來源；AI 失敗不遺失原話，維持 pending／failed processing | `Retain` 來源語意；fresh schema 可 `Replace` 舊資料形狀；session／memory framework 只能 `Wrap` |
| C2 | **Context 與記憶選擇**：operation／focus、Source、Work Model、Current JD、gap／Proposal、budget → 必要核心、受限全域索引、按需候選與可追溯 manifest | 不產生新的業務 authority；完整資料留在本機唯一 PostgreSQL document aggregate；manifest 是 execution artifact，framework history／memory 不是 truth | 必帶核心缺失或超出安全 budget 時 fail-closed；optional context 不足形成 visible gap，不偷補 | `Retain` scope／precedence／來源資格 policy；Capabilities、retrieval、cache、compaction 可 `Replace` 大部分組裝／生命週期 plumbing，不只外包一層；刪除現行固定 packet 拼裝 |
| C3 | **受控顧問 run／orchestration**：已保存 input、Context、可用 Skills、execution profile → typed semantic result、tool receipts、整合回覆與一個主要下一題 | model／tool step 無 domain write authority；通過 verifier 的 datasource transaction 才可產生 semantic transition；run／attempt／checkpoint 只屬執行證據 | 同一短 run 受限 retry／resume；無合格完整結果就不做 semantic transition，不偽裝成功 | `Retain` adaptive bounded run contract；成熟 runtime 可 `Replace` consultation＋Task／OPKS 固定 child、retry／resume／HITL 拓撲，而非只 `Wrap` 外圍 |
| C4 | **職務分析方法 Skills**：焦點證據／工作假說／gap → Task／Duty／O／P／K／S typed finding、linkage、gap、reopen／no-op 理由 | Skill 只提候選；版本、prompt／schema 與實際載入集合進 run snapshot | 沒有足夠證據可回 no-op／gap；不合法、無 anchor 或越權候選被拒絕，不因 schema 必填補造 | `Retain` 已研究的分析方法；Skill registry／progressive loading 可 `Wrap`；`Replace` monolithic prompt、固定階段與 per-axis 呼叫假設 |
| C5 | **可演化 Work Model 與依賴對帳**：verified findings＋現有假說／lineage → 新增、修正、retire、merge／split／reassign、gap 與 dependency invalidation | Work Model 是本地分析 authority，不是 Current JD；新 aggregate 持久保存穩定 ID、來源與 revision | 與 agenda／Proposal 一次 semantic commit；更正只使受影響分支 stale／challenged，界線不安全才擴大重算 | `Retain` 語意與 dependency policy；因目標含 Duty hypothesis／跨軸 linkage，預期用 Pydantic／SQLAlchemy／PostgreSQL `Replace` 現有 schema／reducer；舊 Work Model 不雙寫、不保留相容層 |
| C6 | **焦點、agenda、三層進度與 readiness**：員工改道／延後意圖＋Work Model、Current JD、gap、Proposal、challenge → 建議焦點、返回點、稍後線索、coverage／depth／decision 投影與停止理由 | focus／agenda 的必要狀態保存於同一 aggregate；進度／readiness 優先為可重建投影，不取得 JD authority | 投影故障不改 domain truth；blocked 只作用於相依 branch；未知與不適用明示保留；員工改道不能遺失原焦點或旁支線索 | `Retain` 產品語意；Capabilities、context provider、DBOS short-turn execution 與新 aggregate 可 `Replace` 舊 focus／agenda／progress persistence 與 scheduling，不只 `Wrap` |
| C7 | **typed changeset、審核與 Current JD authority**：verified change intents＋before／after／dependencies → 可編輯 review bundle；員工 decision → Current JD commit／stale disposition | 只有員工 accept／edit 或直接編輯可經 authority seam 改 Current JD；Proposal 是 durable domain object | stale、部分原子群組失敗或 generation／read-set 改變時整組不硬套；決策命令 idempotent | `Retain` 員工 authority；建立跨 Task／Duty／OPKS typed changeset 以 `Replace` 分裂的舊 Proposal 拓撲；UI decision 是獨立 typed command，不需要暫停長 workflow |
| C8 | **deterministic verification、semantic commit 與恢復**：model result、anchors、generation／read-set、domain invariant → verified commit plan 或 typed rejection／receipt | application 驗證資格；一個 PostgreSQL aggregate transaction 原子成立 Work Model／agenda／Proposal／顧問回合，員工 decision 另作原子 transition；DBOS checkpoint 只承接 execution | 已安全保存的 provider artifact 可重播而不盲目重打；semantic transition 冪等且半套業務結果不可見；外部呼叫 outcome 未知的 crash window 仍可能重複計費；本機 transition 失敗不留下半套 authority | `Retain` invariants、原子性與 idempotency 語意；DBOS／Pydantic／SQLAlchemy `Replace` execution／validation／commit plumbing，舊實作退出 |
| C9 | **iCAP Reference／RAG coverage challenge**：目前工作模型／gap＋versioned corpus → retrieval candidates、中立問題、challenge receipt／no-match | Reference 無員工事實 authority；只保存真正呈現、改變 agenda／Proposal 或形成 coverage 裁決的 receipt | 檢索失敗不汙染 Source／Current JD；核心訪談可繼續，切換前 final integration gate 必須通過 | `Retain` 已隔離 PDF／OCS／indexer／embedder assets 與 challenge policy；retriever／reranker／tooling 可 `Wrap`；第一版不先建 GraphRAG |
| C10 | **模型／provider 控制與可觀測性**：active consultant model profile＋operation execution policy＋Context → provider result、actual model、usage／cost／latency、route／attempt receipt | 無 domain authority；本地保存 profile version、resolved snapshot 與 receipts | timeout、rate limit、schema、refusal、truncation、model mismatch 分型；只對 transient failure 受限重試 | `Retain` Caliburn routing／成本／資料政策；以通用 model interface／gateway／SDK `Wrap`，並 `Replace` OpenRouter-only adapter 與散落參數 |
| C11 | **API／Web／匯出產品面**：server commands／projections／Current JD → 一頁顧問工作區、來源／進度／Proposal／JD 操作、generated contracts 與 deterministic XLSX | server 重新驗 domain rules；Web 不重算 invariant、不建第二份 store；匯出只讀 Current JD | 顯示 durable saved／processing／failed／stale 狀態；dirty edit 不被覆蓋；匯出前揭露具體缺口並允許員工強制匯出；匯出失敗不改 authority | `Retain` 文件庫、契約策略、Current JD direct edit、deterministic assembly／XLSX；`Replace` 顧問 API／UI 舊流程；Gate 4-C 已選 FastAPI typed SSE＋`EventSource`＋TanStack Query 接手通用 transport／reconnect／cache 機制，產品只保留 typed event／command、authority 與 dirty-edit policy |

#### 9.3.1 Gate 2 的完成證據

Gate 2 不要求先決定 class、table 或框架。完成時必須能從每個 §3.11 情境追到上表至少一項能力，且每項都有 authority、持久化與失敗語意；同時形成下面三組可供 Gate 3 查核的初始範圍：

1. **優先保留／深化的穩定 seam**：PostgreSQL、Pydantic／SQLAlchemy、文件庫、Current JD direct edit 與 authority 原則、generated contract strategy、deterministic export／XLSX、隔離 RAG 資產；
2. **優先用框架取代或包裝的 plumbing**：consultant loop、checkpoint／resume、model／provider interface、tool／Skill registry、structured result、context provider／retrieval hook、HITL 傳輸、trace／usage；
3. **必須保留產品語意但可重寫實作的 domain**：Source precedence、Work Model、Task／Duty／OPKS 方法與 linkage、focus／agenda／progress、dependency invalidation、typed changeset、Proposal 與 employee authority、deterministic verifier。

**Gate 2 複核規則**：確認上表沒有缺少核心能力，也沒有把可延後功能偷放進第一版；通過後才以官方文件與最小 conformance spike 比較框架，不再回到功能腦力激盪。

#### 9.3.2 Gate 2 反向覆蓋與範圍審核（2026-08-13）

以 §3.11 十個員工情境反向追查後，所有情境都有能力承接，且 C1–C11 沒有孤立能力：

| §3.11 情境 | 必要能力 |
|---|---|
| 1. 導航與建立工作地圖 | C3、C4、C5、C6、C11 |
| 2. 專注但不漏線索 | C1、C3、C5、C6 |
| 3. 更正與受影響範圍重查 | C1、C5、C6、C7、C8 |
| 4. 員工保留 authority | C4、C7、C8 |
| 5. 重大責任先澄清再返回 | C1、C3、C5、C6、C8 |
| 6. Task／Duty／OPKS 隨證據演化 | C4、C5、C7、C8 |
| 7. Reference 只做補漏 | C2、C4、C9 |
| 8. 可解釋進度 | C5、C6、C7、C11 |
| 9. 員工決定完成與強制匯出 | C6、C7、C11 |
| 10. 失敗不吃回答、不產生半套結果 | C1、C3、C8、C10、C11 |

本次反方審核修正三點：C6 明列員工改道／延後與旁支返回；C11 明列缺口揭露後的單一強制匯出；C8 移除「重試不重複付費」的不實 exactly-once 暗示。PostgreSQL 可以保證本地 semantic commit 原子與冪等，但在外部 provider 已完成、結果尚未安全保存的 crash window，應用程式無法保證供應商不重複計費；框架只能縮小與觀測這個窗口，不能把它宣稱消失。

未發現需要新增產品功能才能完成既定情境。登入／多租戶、公司文件／SOP、多人協作、自由多 Agent、GraphRAG、獨立 planner model、第二份 memory store、專用 Resume 子系統與成品前正式 eval 仍不進第一版。安全、資料政策、prompt injection、授權、版本／授權條款、operability 與成本不是新產品功能，但必須成為 Gate 3 每個框架組合的橫向淘汰條件。

**Gate 2 研究結論**：能力地圖已通過內部覆蓋與範圍審核，owner 於 2026-08-13 確認後進入 Gate 3。後續不再追加產品角色或流程；若 framework conformance 暴露能力衝突，回報衝突並回到本表處理，不靜默改北極星。

### 9.4 Gate 3：框架組合研究 v0.3（歷史方案；已由 §9.6 取代）

> **版本註記（2026-08-13）**：本節保留為選型推理紀錄，但其中「不取 Harness Planning」、「Focus／agenda／progress 必須和所有 business state 一起重寫成一個自有 aggregate」，以及「只先測 Pydantic、失敗才測 LangGraph」先被 §9.5 逐元件重驗，再由 §9.6 的直接替換判準取代。本節所載 PydanticAI-first 只是歷史結論；目前主方案與正式理由以 §9.6 為準。

v0.2 修正「不可因舊系統已存在就保留舊機制」是對的，但把「替代率最高」過度等同於「讓 graph checkpoint 接管最多業務 state」，因此又被框架形狀帶偏。正確判準仍是：**保留職務分析目的、產品語意與不變量；成熟框架若能完整承接機制，就讓它成為唯一 owner 並刪除舊實作。** 但「使用最多框架功能」不是目的，把不適合的 framework state 當 Current JD／Proposal 業務資料庫也不算升級。

本輪重查 2026-06-23 正式發布的 PydanticAI V2、第一方 Pydantic AI Harness 與最新 DBOS integration 後，v0.2 有三個已失效的技術前提：

1. PydanticAI V2 core 已是 stable major，Capabilities／hooks、provider、typed output、dynamic model 與 on-demand loading 是核心設計，不再只是「薄 LLM wrapper」。[PydanticAI version policy](https://pydantic.dev/docs/ai/project/version-policy/)、[PydanticAI V2](https://pydantic.dev/articles/pydantic-ai-v2)
2. 第一方 Harness 已有 Agent Skills progressive disclosure、conversation compaction 與 tool-output limits；因此 Context／Skill 機制不必大多自寫。不過 Harness 仍是 0.x，minor 可 breaking，只能精準 pin 並選配，不可整套引入。[Pydantic AI Harness](https://pydantic.dev/docs/ai/harness/)、[Harness Skills](https://pydantic.dev/docs/ai/harness/skills/)、[Harness Compaction](https://pydantic.dev/docs/ai/harness/compaction/)
3. 最新 DBOS integration／API reference 已明列 `DynamicToolset` 與 `DynamicCapability` 可被 durable wrapper 接手，只要求 stable ID 與 deterministic factory；v0.2 所寫「動態 capability 自帶 toolset 不支援」已過時。由於較舊 capability 頁仍可搜尋到相反敘述，這是明確的版本漂移風險，必須以精準版本＋canary 驗證，不能只信文件摘要。[PydanticAI DBOS integration](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)、[DynamicCapability API](https://pydantic.dev/docs/ai/api/pydantic-ai/capabilities/)

現行 Python 3.13、FastAPI、Pydantic 2、SQLAlchemy async、PostgreSQL 與 OpenTelemetry 只作執行環境、可刪碼與相容證據；`consultation`、Task／OPKS child、Work Model、provider adapter、class 或資料表拓撲都不是目標架構模板。這次改判不是「保守地包住舊系統」，而是把通用機制交給 PydanticAI／Harness／DBOS，把 Source／Work Model／Proposal／Current JD **整體重寫成一個新的 PostgreSQL authority boundary**，再刪除舊 runtime 與舊 store。這裡的「一個 aggregate」指單一權威與 transaction seam，不是強迫塞進一個 JSONB row。

#### 9.4.1 橫向淘汰條件

候選組合必須同時通過：

1. 忠實承接「一位主要顧問＋受限內部 loop＋動態焦點」，不能強迫改成員工可見多 Agent、固定 wizard 或每輪固定多模型流水線；
2. 每項產品責任只有一個 authoritative owner；若 framework 接手 Work Model／memory／Proposal／Current JD，舊實作必須刪除或只留可重建 projection，禁止雙寫與雙向同步；
3. 支援 typed state／structured output，且 deterministic verifier 能在 framework schema validation 後獨立拒絕來源、authority、引用與跨實體語意錯誤；
4. Task／Duty／O／P／K／S 採 Agent Skills progressive disclosure；eligible set 先由 deterministic focus／gap policy 縮小，再讓模型於該集合選用，不能把全部方法與工具常駐 context；
5. model、provider、reasoning、token、timeout、fallback 與 route 由版本化 application profile 決定，可保存 requested／actual model、provider、usage、refusal、truncation 與 request receipt；
6. 員工輸入必須在 model call 前 durable；crash／resume、HITL、重試與 side effect 的語意可證明，不能把 at-least-once 外部呼叫誤寫成 exactly-once；
7. 第一版沿用本地 PostgreSQL，無強制雲端控制面、向量 memory service、graph database 或額外 workflow cluster；
8. framework 版本、state schema、node／workflow 變更、checkpoint retention、document delete 與資料加密／反序列化安全均有明確升級路徑；
9. 可沿用 OpenTelemetry 或輸出標準 OTel；員工原話、prompt、tool result 與 JD 內容預設不進 telemetry，因 OTel GenAI semantic conventions 明確警告這些欄位可能含敏感資料。[OpenTelemetry GenAI attributes](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
10. 以「刪除的自寫責任與概念－新增 adapter／migration／操作負擔」衡量淨複雜度；只有套件功能多、star 多或 LOC 看起來少都不算通過。

本輪官方資料呈現的共同趨勢不是「一切都交給自由 Agent」，而是把 agent 分成可組合責任：LangGraph／LangChain 分為 runtime、agent framework、middleware 與可選 harness；Microsoft Agent Framework 分 agent、Skills、context provider、session 與 deterministic workflow；Google ADK／AWS Strands 也各自分 state／session、tools、HITL 與 observability。Agent Skills 又把 domain instructions／references／scripts 收斂成跨產品的 progressive-disclosure 格式。這些大廠／主流實作共同支持「一位顧問＋顯式 durable state＋按需專業能力＋application-controlled side effects」，不支持把 Task、Duty、O、P、K、S 各拆成長駐 agent。[LangGraph product layers](https://docs.langchain.com/oss/python/concepts/products)、[Microsoft Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)、[Agent Skills overview](https://agentskills.io/home)、[Anthropic — Building effective agents](https://www.anthropic.com/engineering/building-effective-agents)

因此選型的分水嶺已不是誰有基本 agent loop，也不是誰能把最多欄位塞進 graph state，而是：誰能用最少新增概念承接**短回合 agent execution＋一份長期 document authority**，可靠升級、限制 context／tool／model 成本，並保留可審核 provider 與 authority receipt。Microsoft 也明確建議先用能滿足需求的最簡單 agent／Skill／context pattern，只有已知步驟與順序本身需要保證時才升級成 workflow graph；本產品的訪談路徑恰好是動態、不是固定流程。[Microsoft — Skills vs. workflows](https://learn.microsoft.com/en-us/agent-framework/agents/skills)、[Microsoft — Workflows](https://learn.microsoft.com/en-us/agent-framework/journey/workflows)

#### 9.4.2 產品責任替代矩陣

| 產品責任 | v0.3 選定的成熟機制 | 處置 | 仍屬產品的語意／待驗證 |
|---|---|---|---|
| model／provider／參數／fallback／typed response | PydanticAI V2 model/provider、OpenRouter settings、typed output／output validator、`SelectModel`／`ResolveModelId` | **Replace** 現行 provider ports、固定 child model 設定、wire parser 與 output repair plumbing | application profile 仍決定 model／provider／reasoning／budget，不讓 LLM 或 Skill 自行換模型；須驗 actual route、usage、refusal、truncation、cache 與 `allow_fallbacks=False`。[PydanticAI OpenRouter](https://pydantic.dev/docs/ai/models/openrouter/)、[PydanticAI output](https://pydantic.dev/docs/ai/core-concepts/output/) |
| bounded agent loop、tool loop、dynamic capabilities | PydanticAI V2 Agent＋Capabilities／hooks／toolsets | **Replace** 自寫 operation wrapper、agent loop、tool dispatch、一般 retry 與模型生命週期 | 仍由 application 設定最大 request／tool／token／timeout；同一員工回合只是一位主顧問的受限 loop，不產生員工可見多 Agent |
| Task／Duty／O／P／K／S 方法按需載入 | Agent Skills 規格＋精準 pin 的 Harness `Skills`／core on-demand Capability | **Replace** 自寫 Skill discovery、frontmatter validation、catalog 與 progressive disclosure | Caliburn 只保留研究過的方法內容、版本核准、deterministic eligible set 與資源授權。Harness `include` 是 construction-time filter，per-run 過濾須以 stable `DynamicCapability` 或有限 profile registry 證明；`Skills` 不讀 bundled resources，仍需一個只讀且鎖在核准 roots 的小型 resource tool。[Harness Skills](https://pydantic.dev/docs/ai/harness/skills/)、[On-demand capabilities](https://pydantic.dev/docs/ai/capabilities/on-demand/) |
| Context Engine／對話窗／token 與大 tool result | PydanticAI hooks／history processor、Harness Compaction／Tool Output Limits、provider prompt cache | **Replace** 訊息窗、tool-pair 安全裁切、compaction、超大結果 spill／paging、token／request accounting 與 cache plumbing | 仍需很薄的產品 `ContextPolicy`：來源資格、更正 precedence、focus slice、global index、Reference 分權、必帶核心與 `ContextManifest`。先採 zero-LLM compaction；summary 只能作 hint、不能取代 Source。[Harness Compaction](https://pydantic.dev/docs/ai/harness/compaction/)、[Tool Output Limits](https://pydantic.dev/docs/ai/harness/tool-output-limits/) |
| source-first durable execution、重試、queue、recovery | PydanticAI `DBOSDurability`＋DBOS workflow／partition queue／workflow ID／SQLAlchemy datasource | **Replace** `consultation/durable_turn`、自寫 replay／lease／operation receipt 與大部分 retry orchestration | 一份文件一個 queue partition、`concurrency=1`；`workflow_id` 由 `input_event_id` 推導。provider call 仍是 at-least-once，禁用重複 HTTP retry；只有同 DB datasource transaction 的業務 commit 可宣稱 exactly-once。[PydanticAI DBOS](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)、[DBOS queues](https://docs.dbos.dev/python/tutorials/queue-tutorial)、[DBOS datasource transactions](https://docs.dbos.dev/python/tutorials/transaction-tutorial) |
| 員工原話、correction、Work Model、Focus、agenda／gap、progress、Proposal、Current JD | PostgreSQL＋SQLAlchemy＋Pydantic 的**新單一 document aggregate boundary** | **整體 Rewrite 並刪除舊 store／class 拓撲**，不是保留現行 domain implementation | 通用 agent memory／checkpoint 不知道 source lineage、Task identity、Duty／OPKS dependency、retire、read-set、stale 與 authority。可用成熟 DB／validation framework 重寫機制，但這些產品語意必須顯式建模；可跨多表，只有一個可寫 authority |
| 員工 Proposal review／authority commit | typed changeset＋PostgreSQL transaction／constraint＋aggregate revision CAS | **重寫機制、保留產品決策權**；不把 Proposal 當暫停中的 tool call | AI 回合完成時保存 Proposal；員工接受／修改／退回／拒絕／延後是之後的獨立 idempotent command。這避免為等待數小時／數天的 UI 決策保留長 workflow，也減少 workflow 升版負擔 |
| deterministic verifier／quote anchor／provenance | Pydantic schema／output validator、DB constraints、W3C TextQuote／TextPosition／PROV-O，加產品純函式 verifier | **Replace 通用 validation plumbing，重寫並保留 domain rule**；不另加 Guardrails framework | 框架可驗形狀、型別與局部限制，不能判斷員工來源是否支持 claim、最新更正、Task／Duty／OPKS 語意或跨實體 authority；這些規則是產品本體，不是重複造框架。[W3C Web Annotation](https://www.w3.org/TR/annotation-model/)、[W3C PROV-O](https://www.w3.org/TR/prov-o/) |
| telemetry／usage／cost | PydanticAI Instrumentation＋DBOS OpenTelemetry | **Replace** 散落 tracing、usage 與 request correlation | 只記 ID、版本、workflow／step、model／provider、token、耗時、錯誤與 decision code；員工原話、prompt、JD 與 tool raw result 預設關閉或遮罩 |
| iCAP／Reference RAG | 現有隔離 bounded context；LlamaIndex ingestion／retriever／citation 與 Harness Tool Output Limits 是後續候選 | 最後整合關卡再 **Replace／Wrap** retrieval plumbing，不讓 RAG 先定義顧問核心 | RAG 只提供 Reference challenge／候選 context，不能建立員工事實、Work Model authority 或自行改 JD；第一版不加 GraphRAG |

這張表仍不寫「Caliburn domain 一律保留」。真正保留的是右欄的產品語意；現行 class、module、repo、table 與 packet 都可刪。另一方面，PostgreSQL／SQLAlchemy／Pydantic 本身也是成熟框架；讓它們重寫一個業務 aggregate，不等於「什麼都自己寫」，也比把 Current JD 硬塞進 agent checkpoint 更符合各框架原本的責任。

#### 9.4.3 Finalist A：PydanticAI V2 core＋選配 Harness＋DBOS＋新 PostgreSQL aggregate（優先 conformance）

這是目前產品吻合度與淨刪碼最平衡的組合，不是薄 fallback：

- **一位主顧問**：PydanticAI Agent 承接 model／tool loop、typed output、provider、usage、hooks 與有限 retry；Task／Duty／O／P／K／S 是同一 agent 可按需載入的 Capabilities／Skills，不拆成長駐 agent，也不建立固定 wizard；
- **穩定 core、窄用 Harness**：PydanticAI V2 core 依 stable major 使用；Harness 只先取 `Skills` 與必要的 zero-LLM compaction，精準 pin 0.x。Tool Output Limits 等到 Reference／RAG 真的接入再開。明確不取 Harness Memory、StepPersistence、ConversationSearch、Planning、Subagents、Dynamic Workflow、FileSystem、Shell 與 Code Mode；
- **短回合 durable workflow**：每次員工輸入是一個會正常結束的 DBOS workflow，不把整場數天訪談做成一條永不結束的 workflow。`workflow_id` 由 `input_event_id` 推導；partitioned queue 以 `document_id` 分區且 `concurrency=1`，同文件 AI 回合串行，不同文件可平行。[DBOS workflow IDs](https://docs.dbos.dev/python/tutorials/workflow-tutorial)、[DBOS partitioned queues](https://docs.dbos.dev/python/reference/queues)
- **一份長期業務 authority**：Source ledger、有效更正、Work Model、focus、agenda／gap、progress、Proposal、Current JD 與 revision/read-set 由新的 PostgreSQL aggregate boundary 擁有。DBOS 只保存 execution／step／queue 狀態，PydanticAI message history 只保存模型執行歷史；兩者都不是第二份可寫 Work Model／JD；
- **Proposal 不等於 suspended tool**：AI 回合輸出 Proposal 後就結束。員工稍後的 accept／edit／revision-request／reject／defer 是獨立 application command，透過 aggregate revision CAS 原子提交；不為 UI 等待濫用 deferred-tool resume；
- **可換模型但不自由漂移**：PydanticAI `SelectModel`／`ResolveModelId` 與 OpenRouter provider settings 讓主顧問、未來的受限結構化分析或 Reference operation 可使用不同 profile；是否換模型由版本化 application policy 決定，不是把產品拆成多 Agent，也不是讓 LLM 自己選最貴模型；
- **安全序列化與短資料**：DBOS 預設 Python serializer 是 pickle，目標架構改用 custom JSON／portable serializer，workflow input／step output 只傳小型 ID 與 typed DTO，原始文件與 aggregate 從 PostgreSQL 依 ID 讀取。PydanticAI 官方也建議 durable input／output 保持約 2 MB 以下。[DBOS custom serialization](https://docs.dbos.dev/python/reference/contexts)、[PydanticAI DBOS considerations](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)

同一個員工回合的參考執行如下；這是責任映射，不是新增固定產品階段：

1. API 以 `input_event_id` 冪等接受員工回答；首選讓 Source insert 與 DBOS enqueue 在同一 PostgreSQL transaction 成功，或以同等 outbox seam 證明兩者不會一半成功。DBOS Client 已支援在同一 system database 的 SQLAlchemy transaction 內 enqueue，conformance 必須驗現行 async stack 是否可直接採用。[DBOS enqueue in transaction](https://docs.dbos.dev/python/reference/client)
2. DBOS 依 `document_id` partition queue 啟動短 workflow；第一個 datasource transaction 讀取 expected aggregate revision 與本輪 Source ID，建立不可變 execution snapshot／receipt。
3. application 的 `ContextPolicy` 依目前焦點、具體 gap、未決 Proposal、有效更正與 token budget，選出 source／Work Model／Current JD／Reference slices，並產生 `ContextManifest`；framework 處理訊息生命週期與裁切，不替產品決定何者是合格證據。
4. application 先算 deterministic `eligible_skill_ids`；stable DynamicCapability 或有限 profile registry 只暴露該集合的 Skill metadata。模型需要時載入 Task／Duty／O／P／K／S 方法；global ingestion／source handling 規則永遠存在。
5. PydanticAI 在固定 request／tool／token／timeout 上限內執行同一主顧問 loop，按 application profile 選 model／provider／settings，產生 typed `ConsultantTurnResult`。
6. Pydantic schema／output validator 先擋形狀錯誤；產品純函式 verifier 再查 quote anchor、最新更正、來源資格、stable identity、Task／Duty／OPKS dependency 與 authority rule。驗證失敗只留下 Source 與 execution receipt，不產生半套業務結果。
7. `AsyncSQLAlchemyDatasource` transaction 重讀 aggregate revision／read-set，將 verified findings、Work Model、focus／agenda／progress、Proposal 與 visible turn 原子寫入；Current JD 只有員工 decision command 才可改。[DBOS datasource transactions](https://docs.dbos.dev/python/tutorials/transaction-tutorial)
8. workflow 正常結束並發布可查詢狀態；下一回合從 aggregate 取回最近對話＋相關 Source／Work Model／JD／gap，而不是相信模型自行維護的 notebook。

這個組合仍有真實風險：Harness 0.x 需精準 pin；最新動態 capability 文件與較舊頁面有版本差異；DBOS workflow code 必須 deterministic，model／network／DB I/O 要落在正確 step／datasource；step retry 不能區分所有 non-retryable misconfiguration；workflow code 改變 step 順序仍需 patch／version。採「每回合短 workflow、Proposal 決策另開 command」可讓絕大部分 workflow 在部署前自然 drain，大幅降低升版負擔，但不能宣稱風險消失。[DBOS workflow upgrades](https://docs.dbos.dev/python/tutorials/upgrading-workflows)

#### 9.4.4 Finalist B：LangChain Agent／middleware＋LangGraph runtime＋新 PostgreSQL aggregate（v0.3 當時的 fallback；已失效）

LangGraph 仍是成熟且功能完整的 graph runtime，但本輪不再優先測 graph-native authority：

- **A1 graph-native document state 淘汰為第一版目標**：LangGraph 官方把 checkpointer 定義成每個 superstep 的 thread state snapshot／short-term memory，不是具業務 CAS、任意查詢、跨表 constraint 與 domain migration 的 document database；預設又會在每個 superstep 寫各 channel 完整新值，`DeltaChannel` 仍是 beta。把 Source／Current JD 塞進 checkpoint 只是為了追求表面替代率，並不比 PostgreSQL aggregate 更成熟。[LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- **A2 仍可成立**：LangGraph 可接手 agent loop、middleware、checkpoint／resume、HITL 與 execution history，PostgreSQL aggregate 保持唯一業務 authority；這不是雙 truth。但與 Finalist A 相比，還要維護 LangChain＋LangGraph＋SkillsMiddleware、graph checkpoint schema／retention，以及另一個 per-document serialization 機制；
- **OSS 併發缺口**：reject／enqueue／interrupt／rollback 等「double texting」是 LangSmith Deployment 功能，不在 LangGraph OSS；本地產品仍要自建 queue／lease。DBOS partition queue 已直接提供此責任。[LangSmith double texting](https://docs.langchain.com/langsmith/double-texting)
- **升版與長 history 成本**：LangGraph 以最新 graph code 讀既有 checkpoint；node／state schema 是 persisted API，`update_state` 會 fork history、不是業務 rollback／CAS。這些能力若產品需要 time travel／長 interrupt 很有價值，但目前只會多一套生命週期。[LangGraph backward compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility)、[LangGraph time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)

只有在 Finalist A 的 conformance 證明以下任一**核心缺口**無法以小型 adapter 補齊時，才切到 B：per-run eligible Skills 無法 durable replay、PydanticAI agent loop 無法表達必要 bounded control、DBOS 無法在現行 async PostgreSQL seam 保證 source-first／atomic commit，或實測淨刪碼沒有下降。若未來產品真的出現固定多節點流程、必須跨數天原地 resume 的非 Proposal 工作、graph time travel／fork 成為正式產品能力，也應重評 LangGraph。不能把 DBOS 與 LangGraph 同時放進 production 做兩套 durable runtime。

#### 9.4.5 大廠與其他主流候選的具體定位

- **Microsoft Agent Framework**：不是「整套仍 experimental」。目前 agent、graph workflow、session、context provider、middleware、OpenTelemetry 與 Agent Skills 都有正式能力文件；Python Functional Workflow API 等局部仍 experimental。它的 Skills 實作最完整之一，包含四階段 progressive disclosure、filter／dedupe／cache 與 file／inline／class／MCP sources。[Agent Skills](https://learn.microsoft.com/en-us/agent-framework/agents/skills) 但 2026-07 self-host 文件同時明示 Python hosting helpers 仍 prerelease、`SessionStore` 預設只在 process memory，application 自己擁有 session／checkpoint mapping 與 durable storage；官方還建議長對話把 append-only history 與 session object 分開，避免每輪重寫持續增長的 session。這正好佐證 Caliburn 不應只因「一個 state object 什麼都放得下」就省略 storage-growth conformance。[Self-hosting](https://learn.microsoft.com/en-us/agent-framework/hosting/self-hosting/)、[Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/) 因缺少 first-class 本機 PostgreSQL persistence，列為本次正式 benchmark，不先成 finalist。
- **AWS Strands Agents**：AWS 宣稱已在內部 production 使用，SDK 走 model-first、tool／hook／session／OTel 路線，足以作大廠實務對照；但 Python built-in session persistence 主要是 local file／S3，自訂 repository 才能接 PostgreSQL，而且 session manager 有 thread-safety／locking 要求。對本地單機不比 LangGraph 少 glue，因此列 watchlist。[AWS — Introducing Strands Agents](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/)、[Strands session management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/)
- **Google ADK 2.0**：已 GA，`DatabaseSessionService` 支援 PostgreSQL、graph／session／compaction 完整；但 Skills 仍 experimental，非 Google model 常再經 LiteLLM，多一層 provider／參數翻譯。對既定 OpenRouter、多模型 profile 與本機單一 authority 而言，淨整合成本高於 A，暫不列 finalist。[ADK 2.0](https://adk.dev/2.0/)、[ADK Session](https://adk.dev/sessions/session/)
- **OpenAI Agents SDK**：官方 Agents 文件支援 backend orchestration、tool loop、session／resume 與 approval，走 OpenAI Responses path 時整合直接；但以 OpenRouter／多 provider 為既定需求時鎖定較高，也沒有比 PydanticAI＋DBOS 更直接的本機 PostgreSQL aggregate／queue 組合。因此作 provider／agent-loop baseline，不作主 runtime。[OpenAI — Running agents](https://developers.openai.com/api/docs/guides/agents/running-agents)
- **LlamaIndex Workflows／Agents**：typed Pydantic events、state、branch／loop／concurrency 與 HITL 很適合 document／RAG workflow；預設 Context 是 ephemeral，跨程序 durability 要自行 snapshot／restore 或加 DBOS，主顧問又需補 model／Skill／context layer，淨套件數較多。最適合在最後 RAG 關卡接管 ingestion、retrieval、citation，而不是第一個核心 runtime。[LlamaIndex Workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/)、[Durable workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/durable_workflows/)

#### 9.4.6 不另外引入的「記憶／證據／驗證」框架

- **Pydantic AI Harness Memory** 是本輪最接近「成熟元件可替換自寫記憶」的候選：它已有 PostgreSQL store、optimistic CAS、idempotency、namespace 與 bounded search，機制上確實比臨時自寫 notebook 完整。但官方也明確定義它是模型可寫的 Markdown notebook，內容是不可信的、沒有 source citation／verified provenance，CAS 只防 lost update、不能證明記憶是真的；DBOS 下其普通 function tools 還需 application 自行包 durable step。因此它可用於未來非權威偏好筆記，**不能替代員工原話、有效更正、Work Model、gap 或 Current JD**，第一版不引入。[Harness Memory — security and provenance](https://pydantic.dev/docs/ai/harness/memory/)
- **Harness StepPersistence／ConversationSearch** 不與 DBOS 並用。官方明列 StepPersistence 不是完整 graph-state checkpoint，PostgreSQL backend 也不在本版內建範圍；若同時採用會形成另一套 run history／resume owner。[Harness StepPersistence](https://pydantic.dev/docs/ai/harness/step-persistence/)
- **Mem0／Letta** 會讓模型抽取、衝突解決或自行編輯長期 memory；這適合偏好與個人化，不適合把員工原話變成另一份 LLM 維護的記憶。Mem0 的預設 `add` 會用 LLM 推論要保存／更新／刪除的 memory；Letta memory blocks 則是 agent 可自行編輯、常駐 context 的狀態。[Mem0 memory operations](https://docs.mem0.ai/core-concepts/memory-operations/add)、[Letta memory blocks](https://docs.letta.com/guides/core-concepts/memory/memory-blocks) 第一版用同一 document aggregate 的 Source ledger＋typed Work Model＋targeted retrieval 即可。
- **Graphiti／knowledge graph memory** 會新增 temporal knowledge graph、hybrid retrieval 與 GraphRAG 路徑；產品目前只需單份 JD 內的穩定 ID／typed relation，不需要全域 knowledge graph。[Graphiti overview](https://help.getzep.com/graphiti/getting-started/overview)
- **Guardrails AI 等通用 validator** 可以承接格式與常見 safety check，但 Pydantic、DB constraint 與 framework structured output 已涵蓋通用部分；來源資格、quote 支持度、Task／Duty／OPKS 與 authority 是 Caliburn 特有規則，再加一層框架不會消除這些 code。
- **對話 compaction** 只作模型工作窗壓縮，不能取代 Source。第一版先用 Harness 的 zero-LLM 策略清除舊 tool result／保留 recent tail；只有 token threshold 真的逼近且 targeted retrieval 不足時才啟用 `SummarizingCompaction`。官方會把 summary call 納入 request／token usage，且任何 history rewrite 都可能打破 provider prompt cache，成本必須可見。[Harness Compaction](https://pydantic.dev/docs/ai/harness/compaction/)

因此「記得員工之前說過什麼」不是買一個 memory notebook 就完成：它是 Source ledger、correction precedence、typed Work Model、operation-specific retrieval、recent conversation tail 與可重建 ContextManifest 的組合。框架接手 history、compaction、bounded search 與 token accounting；Caliburn 只保留「哪一段是有效員工證據、何時該取回」的產品政策。新的通用 memory 套件只有在成品後出現非權威偏好或跨文件需求時才重評。

#### 9.4.7 淨覆蓋與成本比較

| 判準 | A. PydanticAI V2＋Harness（選配）＋DBOS | B. LangChain＋LangGraph A2 | Microsoft Agent Framework benchmark |
|---|---|---|---|
| 與產品控制流吻合 | **高**；單一 adaptive agent＋短 durable turn，Proposal decision 另作 command | 中；能做，但 explicit graph／long interrupt／time travel 不是目前核心需求 | 中至高；single agent／Skills／context 完整，workflow 亦可選 |
| Context／Skill 機制替代 | **高**；Capabilities、Harness Skills、compaction、tool-output limits、prompt cache | 高；middleware、SkillsMiddleware、summarization、context editing | **高**；Skills provider／filter／dedupe／cache、context provider 完整 |
| 記得員工內容 | **高且不增第二 truth**；Source aggregate＋targeted retrieval，framework 管 history／compaction | 高；thread memory＋aggregate，但多一套 checkpoint history | 高；session/context provider，但 durable PG adapter 要補 |
| model／provider 可換 | **強**；原生 OpenRouter model/settings、dynamic model、typed output | 強；model middleware、OpenRouter integration，但 `ChatOpenRouter` 仍 beta | 強；多 provider，但 OpenRouter exact-route 須自訂／驗證 |
| PostgreSQL durable runtime／queue | **最貼合**；DBOS workflow ID、partition queue、async datasource transaction | 強 checkpoint；OSS per-document enqueue／reject 仍要自建 | 弱至中；production SessionStore／CheckpointStorage 要自行接 PG |
| 業務 transaction／CAS | **最強**；SQLAlchemy datasource outcome 與 app write 同 transaction | 強但另寫 transaction node；checkpointer 不提供 business CAS | 待 storage adapter 後再證明 |
| 必要新服務 | 無；既有 PostgreSQL，可分 `dbos` schema，無強制 Conductor／Logfire | 無；既有 PostgreSQL，但 LangSmith Deployment 不採，queue 自建 | 無強制服務，但 durable storage glue 較多 |
| 預期可刪舊機制 | **高**：provider、wire、operation、durable-turn、scheduler／receipt、Skill loader、history／compaction、context lifecycle；舊 domain store 整體重寫後退出 | 高：多數 runtime 可退場；另增 graph/checkpoint／queue lifecycle | 中至高；功能完整但 PG glue 可能吃回收益 |
| 主要風險 | Harness 0.x、動態 capability 版本漂移、DBOS deterministic workflow／serializer／retry 配置 | checkpoint growth／schema evolution、graph abstraction、OSS concurrency、skills 套件組合 | Python hosting／部分 API 仍演進、storage adapter 與 provider fit |

主流程度不能只看 star：LangGraph 仍是較成熟、較廣泛的 graph runtime；PydanticAI V2／Harness 是 2026 年較新的 capability-first 路線，DBOS 也比傳統 workflow 平台輕。此處選 A 是**產品 fit 與淨概念較少**，不是宣稱它絕對最流行。LangChain 自己也把 LangGraph 定位在 long-running stateful／complex deterministic＋agentic workflow，把一般 agent abstraction 放在 LangChain；Pydantic 與 Microsoft 最新文件同樣建議先用能完成需求的最簡單組合。[LangChain product layers](https://docs.langchain.com/oss/python/concepts/products)、[Pydantic Graph — when not to use a graph](https://pydantic.dev/docs/ai/graph/graph/)

模型成本方面，A 不需額外 planner／selector model：eligible set 先由 deterministic policy 縮小；真正載入 Skill 可能增加一個 tool iteration，`SummarizingCompaction` 也會增加一次模型 request，所以兩者都只能按需啟用並計入 PydanticAI usage。zero-LLM compaction、靜態 prefix prompt cache、有限 tool result 與較小 ContextPack 是第一順位。DBOS 會增加 PostgreSQL step writes，但不增加模型 call；conformance 要記錄 request 次數、input／output token、cache read/write、DB rows／bytes、resume latency 與新增 glue。

2026-08-13 現況盤點顯示候選重寫面約有 `consultation` 577 行、`task_analysis` 4,372 行、`opks` 2,542 行、OpenRouter adapter 741 行、PostgreSQL adapter 1,393 行，共約 9,625 行 Python。這不是可全部刪除的承諾：其中包含大量職務分析規則；它證明的是「包住舊系統」很容易留下兩套抽象。Gate 4 必須產出逐 module 的刪除帳本：

- **框架直接替代後刪除**：provider／wire parser、operation wrapper、durable-turn orchestration、一般 scheduler／retry／receipt、Skill discovery、message compaction 與 tool-output lifecycle；
- **用成熟資料框架重寫後刪除舊拓撲**：Work Model、focus／agenda／progress、Proposal／Current JD repository 與 split persistence seam；
- **移植成新 Skill／domain verifier 的產品資產**：Task／Duty／O／P／K／S 分析方法、Source／correction／quote anchor 語意、identity／dependency／authority 規則；
- **不得發生**：為了安全感保留舊 class／table 再加 adapter 雙寫，或因框架沒有產品語意就把該語意刪掉。

#### 9.4.8 歷史初步裁決與 conformance 清單（勿據此施工）

**v0.3 的研究建議是「PydanticAI-first conformance」，尚待 owner 確認，且不等於核准 production 實作。** PydanticAI V2＋窄用 Harness 接手 agent／provider／Skill／context mechanics，DBOS 接手短回合 durability／queue／transaction tracking，PostgreSQL／SQLAlchemy／Pydantic 重寫唯一 business aggregate。LangGraph A2 是核心能力失敗時的正式 fallback；Microsoft Agent Framework 是同級功能 benchmark；LlamaIndex 留給最後 RAG 關卡。

以下保留 v0.3 當時的淘汰條件供追溯，但「先只測 Finalist A」已由 §9.5.6–9.5.7 取代，Gate 4 應以兩個 finalist 的共用小情境比較，不得照本段直接施工。v0.3 原訂至少證明：

1. **Source-first submit seam**：相同 `input_event_id` 冪等；Source＋enqueue 同 transaction 或等價 outbox；source durable 後才可呼叫 model。在 enqueue 後、source 後、model 前、model 後與 semantic commit 前各 kill process，員工原話都不遺失；
2. **單一 business authority**：DBOS system state、PydanticAI history 與 aggregate schema 清楚分離；只有 aggregate 可寫 Work Model／Proposal／Current JD，API query／export 不讀 DBOS step blob 當業務 truth，另一份文件完全不可見；
3. **每文件序列化＋CAS**：partition queue `document_id`／`concurrency=1` 生效；不同文件可平行。直接員工編輯仍可能與 AI workflow 競爭，所以 semantic commit 必須重驗 expected aggregate revision／read-set；重複 submit、兩個 stale decision 與 workflow replay 不產生 duplicate Source／Proposal／JD mutation；
4. **原子 domain transition**：verified findings＋Work Model＋focus／agenda／progress＋Proposal＋visible turn 要嘛在一個 datasource transaction 全成功，要嘛全部不成立；employee accept／edit／revision-request／reject／defer 以獨立 command 原子更新 Proposal／Current JD；
5. **Dynamic Skills durability**：application 先算 eligible set，PydanticAI 只揭露該集合；同一主 agent 可按需載入 Task／Duty／O／P／K／S，未啟用 Skill 的完整內容不進 context。kill／resume 後 stable Capability／Toolset ID 不漂移，最新文件所述 DynamicCapability 行為要由 canary 鎖住；
6. **Skill resource boundary**：Harness `Skills` 只讀核准 `SKILL.md`；補充 resource tool 不可越出核准 roots、不追 symlink 越界，也不提供 write／shell／script。Skill 版本與實際載入 ID 寫進 receipt；
7. **Context／記憶／成本**：`ContextManifest` 列出實際 source／state／reference IDs、eligible／loaded Skills、token、cache 與排除 reason；zero-LLM compaction 保留 tool-call pair，summary 不取代 Source；員工更正後不再注入已失效 claim；
8. **provider contract**：OpenRouter exact model、provider order／only、reasoning、temperature／max tokens、timeout、usage、cache、refusal、truncation、actual route 與禁用 fallback 可 round-trip；DBOS runtime model registry／resolver 可忠實重建 custom provider profile，不完整才加窄 adapter；
9. **重試語意**：provider SDK HTTP retry 與 DBOS step retry 不相乘；misconfiguration 不浪費大量 retry；外部 model call 可能重打時 receipt 明確記錄，不宣稱 exactly-once；datasource transaction replay 則不得重複業務 write；
10. **schema／workflow evolution 與安全**：DBOS 使用 custom JSON／portable serializer，不用 pickle；workflow inputs／outputs 維持小型。以保存中的舊 workflow 測 patch／application version／drain；completed workflow retention 與刪除 document 時的 DBOS history 清理有 runbook；
11. **OTel／隱私與操作性**：HTTP、source event、workflow／step、model、Skill／tool、verifier、semantic commit 以 ID 串接；預設 span 不含員工原話、prompt、JD 或 tool raw result。以代表性假資料記錄 model／tool calls、tokens、cache、DBOS rows／bytes、resume latency、API query 與本機啟停；
12. **淨刪除門檻**：列出可刪的現行 module／class／table／concept，另列新增 Capability adapter、aggregate schema／migration、serializer、queue config、runbook 與 failure mode。只有產品語意完整且淨概念明顯下降才通過；若 PydanticAI／DBOS 的核心缺口需要另一套 runtime 或大量自寫 replay，停止 A，改用同一 slice 測 LangGraph A2，不雙疊。

這些是 framework conformance 與一般工程安全，不是 owner 已後置的模型品質 eval：不建立 golden dataset、不比較回答分數、不做 LLM-as-a-judge。它只回答「成熟框架能否忠實接手並讓舊機制退場」，避免真正施工後才發現又多了一套 state、memory 或 retry engine。

#### 9.4.9 北極星回歸審核

把 v0.3 重新逐項對照 §2、§3.11 與 C1–C11，框架研究目前沒有改寫產品方向：

- 仍是一位 AI 專業職務說明書顧問，不新增員工可見多 Agent、planner 角色或固定狀態機 wizard；
- 仍先大致理解工作全貌，再以明確焦點深入訪談；旁支線索先保存並排入 agenda，Task、Duty 與 OPKS 隨訪談動態修正；
- Task／Duty／O／P／K／S 仍是可組合的專業 Skills，不是固定串行階段，也不要求 Task 完全穩定後才做 OPKS；
- 「記憶」仍指同一份文件內記得員工之前說過的有效內容與更正，不是多 speaker、跨文件個人化或另一份模型自行維護的 memory；
- AI 仍只能提出候選；員工可接受、修改、退回、拒絕或延後，所有正式 Current JD 變更都要通過 authority rule；
- 進度仍以 coverage、深度、待決 Proposal 與具體 gap 說明，不造假百分比；單一匯出仍揭露缺口並允許員工強制匯出；
- iCAP／RAG 仍是 Reference challenge，最後才接入，不替員工建立工作事實；正式模型／context 品質 eval 仍在成品後；
- 受限 Big-bang 仍只涵蓋 AI 顧問子系統；登入、多租戶、公司文件／SOP、多人協作、GraphRAG、自由 Agent loop 與新雲端控制面沒有因框架功能表被偷渡進第一版。

本輪特別檢查了兩種偏離：一是因舊系統已有 Work Model／Proposal 就原封不動包住它，二是因 LangGraph 能存 typed state 就反過來把產品變成 graph。v0.3 兩者都不採：舊實作可整批重寫並刪除，但 Source／Work Model／Focus／gap／Proposal／Current JD 的產品語意仍由新的單一 aggregate 顯式承接；PydanticAI／Harness／DBOS 接手的是 agent、Skill、context lifecycle、durability、queue、retry、transaction tracking 與 observability 機制。

目前只剩可由 conformance 回答的實作問題：PydanticAI V2＋精準 pin Harness 是否能穩定做到 per-run eligible Skills；DBOS 與現行 async PostgreSQL 是否能完成 source-first atomic enqueue、partition queue、JSON serializer 與 datasource commit；完成同一 vertical slice 後淨概念是否真的下降。這些都不改產品需求。若其中有核心硬缺口，才測 LangGraph A2；任何結果都不得縮小產品流程、把員工 authority 交給模型、或保留兩套可寫機制。

### 9.5 Gate 3 v0.4：同目的元件替代稽核（2026-08-13）

> **版本註記**：本節正確擴大了替代範圍，但最後仍把「LangGraph state 直接承接 business authority」誤寫成容易重疊的風險，因而沒有完成同目的直接替換的比較。選型先由 §9.6 v0.5 修正，再由 §9.7 v0.6 的實測收斂；本節只保留候選盤點與錯誤如何被發現的研究歷史。

本節直接回應 owner 的修正：`Focus`、`Work Model`、`Proposal`、`Context Engine` 等只是目前對產品責任的命名，不是必須保護的自寫元件。只要成熟元件完成相同目的、保留已確認的職務分析流程與 authority，且導入後能刪掉舊機制，就應優先替代。反過來，框架只有相似名稱、卻讓來源、更正、員工核准或 Current JD 權威消失，不算替代。

#### 9.5.1 替代判準

每個候選都必須回答六題：

1. 它承接的是哪一項產品責任，不只是哪個現行 class？
2. 它提供哪些已完成的機制：資料型別、工具、持久化、並行控制、恢復、事件、UI 或可觀測性？
3. 哪些 Caliburn 特有語意仍要以薄 policy／validator／adapter 表達？
4. 採用後可以刪除哪些現行 module、table、store 或 orchestration concept？
5. 它能否成為該責任的唯一 owner；若只能建立 mirror／cache，該 mirror 是否可完全重建且不可反向寫入？
6. 新增的 adapter、服務、資料庫、升級與操作成本，是否小於刪掉的自寫複雜度？

「唯一權威」不等於所有責任必須塞進同一個 framework object 或一列 JSON。Source、Work Model、Focus／agenda、Proposal 與 Current JD 可以由不同成熟機制承接，但每個欄位只能有一個可寫 owner；需要同時成立的 semantic transition 仍必須在同一 PostgreSQL transaction、同一可證明的 framework state transition，或 staging 後的一次原子 commit 中完成。

#### 9.5.2 完整元件矩陣

| 產品責任／現行主要自寫面 | 成熟機制候選 | v0.4 判斷 | Caliburn 最後仍需保留的薄層 |
|---|---|---|---|
| model／provider／參數／usage；`adapters/openrouter/*` | PydanticAI V2 provider／dynamic model／typed usage；LangChain `init_chat_model`／model middleware；LiteLLM SDK／Router 作跨 100+ provider 備選 | **Replace**。兩個 finalist 都測 OpenRouter exact route；不先疊 LiteLLM Proxy，只有 finalist 無法忠實 round-trip provider order、ZDR、fallback、reasoning、cache 或 actual route 時才測 LiteLLM SDK | 版本化 application model profile、允許的 provider／model、成本與資料政策 |
| tool loop、structured output、wire parser；Task／OPKS `llm/wire.py`、`operation.py` | PydanticAI typed output、output validator、toolset／Capabilities、retry taxonomy | **Replace** 通用 schema 產生、解析、tool loop 與格式 repair；現行 wire／operation 拓撲應退出 | Task／Duty／OPKS 的專業 output schema、no-op／gap 語意與跨實體 invariant |
| prompt／專業方法載入 | Agent Skills open specification＋Harness Skills／on-demand Capabilities | **Replace** discovery、progressive disclosure、版本化載入與大部分 prompt 拼裝；**Retain** 方法內容 | 已研究的 Task／Duty／O／P／K／S 分析方法、eligible-set policy、Skill 核准版本 |
| conversation history、context window、過大 tool result；`task_analysis/context.py`、`opks/context.py` 的通用部分 | PydanticAI messages/hooks＋Harness Compaction／Tool Output Limits；或 LangChain dynamic prompt／Summarization／Context Editing／LLM Tool Selector；必要時 bounded conversation search | **Replace** history lifecycle、裁切／摘要、spill、tool selection、token／cache bookkeeping；**Rewrite thin policy** 取代固定 ContextPacket 組裝 | scope、來源資格、更正 precedence、Focus 必帶核心、Reference 分權、ContextManifest；summary 永不取代 Source |
| 員工原話、correction、append-only journal；`core/domain/sources.py`、`core/journal.py` 與 persistence plumbing | PostgreSQL／SQLAlchemy versioning＋append-only rows；`eventsourcing` 9.5.4 stable event store／outbox／snapshot／projection／DCB；W3C PROV-O／Web Annotation 作資料語彙 | **正式雙候選**。關聯式基線最貼合既有 async transaction；`eventsourcing` 能替代更多 journal、revision、outbox 與 projection code，必須做小型 conformance 後才選 | 「哪句員工原話有效」、更正取代範圍、document isolation、speaker 固定為員工／系統、quote support 規則 |
| Work Model 的新增、修正、retire、merge／split、lineage 與 dependency invalidation；`core/domain/work_model.py`、`task_analysis/transition.py` | Graphiti OSS temporal knowledge graph；LangGraph typed state／checkpoint／Store＋LangMem reducer；`eventsourcing` aggregate／DCB；SQLAlchemy／Pydantic relational model | **沒有單一現成元件已證明全覆蓋，四條路徑都不得先排除。** Graphiti 最接近 temporal facts＋episode provenance；LangGraph 最接近同 runtime 的 checkpointed typed state；`eventsourcing` 最接近版本、條件 append 與 projection；關聯式基線最容易直接查詢、編輯與匯出 | Task／Duty／OPKS identity、員工來源 linkage、retire／reopen、跨軸依賴、verified commit；任何 LLM memory update 先是候選，不可直接成真 |
| Focus／agenda／旁支／blocked／返回；`ActiveQuestion`、`ScheduledOpks`、`scheduler.py`、`question_targets.py` | **Pydantic AI Harness Planning**；LangChain `TodoListMiddleware`／LangGraph custom state；Microsoft Harness todo＋mode；Rasa CALM dialogue stack 作中斷返回設計對照 | **Pydantic Planning 升為優先 Replace 候選**。它已有 stable ID、ordered plan、subtask、dependency／blocked、progress summary、events、SQLite／Postgres／Redis store 與跨 run persistence；不再合理全部自寫 | work-unit ID 映射、焦點資格、員工改道／延後、gap reason、來源／Work Model linkage、semantic commit 前驗證 |
| 三層進度與 readiness | Pydantic Planning progress summary／events、framework streaming；SQL query／projection | **部分 Replace**。框架直接提供「目前 plan 做到哪裡」；產品仍從 Work Model／Current JD／Proposal 投影 coverage、depth、decision 與具體 gap | 禁止假百分比；「完成」是員工可理解的 coverage／depth／decision 狀態，不是 tool-call 數量 |
| Proposal／review bundle／員工 accept、edit、reject、revision request、defer；`proposal*.py`、部分 API/UI | Pydantic deferred tools＋`ToolApproved.override_args`／`ToolDenied`；AG-UI interrupts；Vercel AI SDK approval；LangChain HITL approve／edit／reject／respond | **Wrap／大幅 Replace 互動 plumbing，不直接刪除 durable domain lifecycle**。框架已能承接 typed args、暫停／續跑、編輯與審核傳輸；Caliburn Proposal 可改為「已保存的待核准 typed tool request／changeset」，但不能只存在 client history 或暫停中的 process | 多 proposal 並存、繼續訪談、defer／revision-request、跨實體原子群組、before／after、read-set、stale、獨立 decision command |
| durable turn、retry、queue、resume、idempotency；`consultation/durable_turn.py`、`opks/generation.py` 的通用部分 | DBOS workflow／step／queue／datasource transaction；LangGraph Functional API 是正式替代組合 | **Replace**。PydanticAI-first 組合用 DBOS；若改 LangGraph family 就只用 LangGraph durability，兩套不可並存 | source-first、每 document serialization、外部 model call at-least-once 事實、semantic commit CAS 與 receipt |
| verifier／guard；Task／OPKS `verifier.py`、`portable_schema.py`、DB constraint | Pydantic field／model／output validators、Harness Guardrails、SQLAlchemy／PostgreSQL constraint、W3C anchor／provenance 型別 | **Replace** 通用型別、格式、常見 input/output/tool guard 與 wiring；**Retain／重寫** domain verifier | source 是否有效、quote 是否真的被 anchor 支持、Task／Duty／OPKS identity／dependency、authority、read-set、stale；這些沒有通用框架可自動知道 |
| API chat streaming、tool／approval UI、shared run state；部分 Web hook／SSE／DTO | PydanticAI native Vercel AI adapter＋AI SDK `useChat`；或 LangGraph streaming／frontend hooks；需要 edited tool args／richer shared state 時用 AG-UI snapshot／delta／interrupt | **Replace** 大部分 chat stream、tool event、approve／deny round-trip 與前端 hook。Pydantic finalist 先試 Vercel AI，LangGraph finalist 用其原生 stream；任一路徑若 Proposal edit／Focus shared-state 的自寫量仍高，就整體改用 AG-UI，不疊兩套 protocol | server-side authority、generated product contracts、未信任 client history 清洗、Proposal／JD projection 與 dirty-edit 保護 |
| observability／usage／成本／trace | PydanticAI instrumentation＋DBOS OTel，或 LangSmith／LangGraph tracing；共同輸出 OpenTelemetry GenAI semantic conventions | **Replace** tracing plumbing；不因採 LangGraph 就強制使用 LangSmith cloud | 隱私預設、ID correlation、actual provider receipt、不能把員工原話／prompt／JD 默認送到 telemetry |
| Reference ingestion／dedup／retrieval／citation；隔離 RAG bounded context | LlamaIndex IngestionPipeline／doc hash／cache／async／Qdrant connector／CitationQueryEngine；Haystack pipeline／AnswerBuilder 作備選 | **最後關卡 Replace／Wrap 候選**。可替代大部分 ingestion、chunking、dedup、retrieval 與 citation assembly；既有 PDF／OCS assets 只作 input，不保護自寫 pipeline | iCAP corpus version、Reference 無員工事實 authority、實際呈現 receipt、exact quote anchor 與 no-match／challenge policy |
| Current JD、直接編輯、查詢、generated API contract、deterministic XLSX | SQLAlchemy／Pydantic／PostgreSQL、既有 contract strategy、XLSX library | **Retain 產品責任並可重寫實作，不交給 agent memory／checkpoint**。這本來已使用成熟框架；新 agent framework 不會比關聯式模型更適合 CRUD、FK、排序、匯出與 direct edit | 員工 authority、跨 Task／Duty／OPKS invariant、強制匯出時揭露 gap、deterministic assembly |

這張表修正了 v0.3 過度粗糙的二分法：框架不只承接 agent 外圍；Planning、HITL、UI、event store、memory reducer 等都能深入替代現行機制。另一方面，「產品語意仍需存在」也不等於保留舊 class。最終程式可以只剩少量 Caliburn policy／validator／mapping，而讓框架管理生命週期、持久化協定與 UI 事件。

#### 9.5.2.1 現行程式盤點與替代後可退出面

2026-08-13 重新查了 production manifest 與實際 imports：`apps/api/pyproject.toml` 目前直接依賴的是 Pydantic／SQLAlchemy 等基礎框架，`apps/web/package.json` 與 production source 沒有直接使用 LangChain、LangGraph、PydanticAI、DBOS、AG-UI、Graphiti、LlamaIndex 或 `eventsourcing`。`apps/api/uv.lock` 即使出現 LangChain／LangGraph 名稱，也只構成 lock-only evidence，可能是 transitive dependency 或歷史殘留，不能當成已採用或應沿用的架構。這代表新選型可從產品責任出發，不必保護一套其實已在 production 使用的 agent framework。

| 現行可重寫／刪除面 | 成熟元件接手的機制 | 通過後的處置；不是先包住舊碼 |
|---|---|---|
| `adapters/openrouter/*`、Task／OPKS `llm/wire.py`、`operation.py`、部分 `ports.py` | PydanticAI 或 LangChain 的 model/provider、typed output、tool loop、retry／fallback middleware | 刪除自寫 provider request／response normalization、JSON wire repair 與 operation loop；只留 application model profile、provider receipt 與專業 schema |
| `task_analysis/context.py`、`opks/context.py` 的 history／裁切／prompt 拼裝 | Harness Compaction／Tool Output Limits／Skills，或 LangChain dynamic prompt／summarization／context editing／tool selector | 刪除通用 message lifecycle、token 裁切與所有 Skill 常駐 prompt；重寫一個薄 `ContextPolicy` 與可重播 `ContextManifest` |
| `task_analysis/question_targets.py`、`opks/scheduler.py`、journal 內的排程狀態、舊 `ActiveQuestion`／`ScheduledOpks` | Pydantic Planning，或 LangChain `TodoListMiddleware`＋LangGraph state／checkpoint | 在 Focus slice 通過後刪除舊 scheduler／question-target state；只留 work-unit eligibility、gap reason、員工改道與 plan-item mapping policy |
| `consultation/durable_turn.py`、`opks/generation.py` 的 run／receipt／retry／resume 通用部分 | DBOS workflow／partition queue／datasource transaction，或 LangGraph Functional API／checkpoint／task | 只選一個 durable runtime；刪除自寫 lease、replay、一般 retry 與 execution receipt plumbing，保留 source-first、CAS 與 provider at-least-once 語意 |
| `core/domain/sources.py`、`core/journal.py`、`core/domain/work_model.py`、`task_analysis/transition.py`、`adapters/postgres/*` 的舊 persistence 拆法 | SQLAlchemy relational write model、`eventsourcing` DCB／projection、LangGraph typed state，必要時 Graphiti temporal facts | 不是保留舊 aggregate；由 Work Model／Source slice 選出唯一 write owner 後重寫 schema／repository，舊 store 與雙寫 seam 全退場。職務 identity、source lineage、更正與 dependency policy 移植到薄 domain 層 |
| `core/domain/proposal.py`、`core/domain/opks_proposal.py`、`task_analysis/proposal_decisions.py`、`opks/proposals.py` 與部分 API／Web review plumbing | Pydantic deferred tools、LangChain HITL／interrupt、Vercel AI 或 AG-UI | 刪除通用 approval transport、typed args round-trip 與暫停／恢復 glue；以新 durable changeset schema 保留多 pending、defer、revision request、stale/read-set 與 authority commit |
| Task／OPKS `verifier.py`、`portable_schema.py` 與散落 shape checks | framework structured output／validator、Pydantic、PostgreSQL constraint、W3C selector／provenance types | 刪除重複格式與 schema plumbing；把真正的 quote support、source authority、Task／Duty／OPKS invariant 收斂成少量 deterministic domain rules |
| `api/*mapper.py`、chat stream DTO、Web 自寫 streaming／tool／approval hooks | Pydantic Vercel adapter＋AI SDK，或 LangGraph frontend／AG-UI | 選一條 wire protocol 後刪除重複事件模型與前端狀態機；generated product contract、server authority 與 dirty-edit protection 保留 |
| Current JD direct edit／query、readiness、deterministic export | SQLAlchemy／Pydantic／PostgreSQL 與 XLSX library 已是成熟框架底座 | 可重寫舊 class／repository，但不改由 agent memory 或 checkpoint 擁有；這部分主要保留產品 authority 與輸出 invariant，不為提高「替代率」硬搬 |

因此「幾乎所有元件都納入替代研究」不代表每個檔案都換一個新套件。相同 framework middleware 能同時刪除多個現行 module；反之，若引入一個套件只多出 mirror、adapter 與同步工作，卻刪不掉任何 write owner，就不算升級。

#### 9.5.2.2 覆蓋率與成熟度分開判斷

| 家族／元件 | 2026-08-13 官方成熟度證據 | 對本產品的判斷 |
|---|---|---|
| PydanticAI core | V2.0 已於 2026-06-23 stable，公開版本政策承諾 major 內不故意 breaking。[Version policy](https://pydantic.dev/docs/ai/project/version-policy/) | provider、typed output、tool loop 與 validators 可直接列 production 候選 |
| Pydantic AI Harness Planning／Skills／Compaction | 第一方官方能力、Planning 已有 persistent store／stable item ID／dependency／event；但頁面明示 API 仍可能跨 release 改變。[Harness](https://pydantic.dev/docs/ai/harness/)、[Planning](https://pydantic.dev/docs/ai/harness/planning/) | 功能覆蓋高、成熟度低於 core；必須 pin 精確 release／commit、加 canary 與 staging adapter，未通過前不能直接成 authority |
| LangChain 1.x＋LangGraph 1.0 | LangChain 1.0 採 semver；LangGraph 1.0 是 LTS，官方 Postgres checkpointer 用於 production。[Release policy](https://docs.langchain.com/oss/python/release-policy)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence) | runtime 成熟度是決賽者中最高；Todo／Deep Agents middleware 的局部成熟度仍要分開看，不能把整包 coding-agent 預設全引入 |
| Microsoft Agent Framework | Microsoft 的 AutoGen／Semantic Kernel successor，Agents／Harness／Workflows 能力完整；Python hosting／部分 API 仍快速演進。[Overview](https://learn.microsoft.com/en-us/agent-framework/overview/) | 作大廠同級 benchmark；目前不能只因廠牌就略過本機 PostgreSQL storage／versioning conformance |
| Graphiti、LangMem、`eventsourcing` | 都是活躍且有明確專長的 OSS；沒有一個是跨產品通用的「職務分析 Work Model 標準」 | 只能以同一 Source／correction／lineage 情境證明能成為唯一 owner；功能多或名稱像 memory 不足以採用 |

成熟度重查後，不能誠實地把 LangGraph 留到 Pydantic 組合失敗才測：**PydanticAI V2＋Harness＋DBOS** 的 product fit 與 transaction seam 較好，**LangChain／LangGraph 1.x** 的 runtime 穩定度與同一家族覆蓋較高。兩者都成為 Gate 4 正式決賽者，以同一情境比較語意忠實、可刪舊碼、glue、資料生命週期與本機操作成本；Microsoft 維持 benchmark。這不是模型品質 eval，也不要求開發成品兩次，而是先做最小可丟棄 conformance，避免用整次 Big-bang 賭文件描述。

#### 9.5.3 Focus／agenda 的具體替代方式

> **版本漂移註記（2026-08-13）**：下列判斷描述較早研究到的 Planning API，已由 §9.11.4 的 0.13.0 實際匯入檢查推翻。0.13.0 的公開 `PlanItem` 只剩 `content／status`，plan 是每個 run 隔離的 ephemeral model-owned reminder；本節只保留研究歷史，不得再拿來選型。

Pydantic Harness Planning 的最新完整官方頁與 source 顯示：每個 `PlanItem` 有 stable `id`、`content`、`status`、`active_form`、`parent_id`、`depends_on`；可啟用 `blocked`、subtask 與 dependency，`read_plan()` 會回 progress summary，並有 granular events 與 `PostgresPlanStore`。[Planning](https://pydantic.dev/docs/ai/harness/planning/)、[PlanItem source](https://github.com/pydantic/pydantic-ai-harness/blob/main/pydantic_ai_harness/planning/_types.py)

可先把產品概念映射成：

- `in_progress`：目前主要訪談焦點，正常只保留一個；
- `pending`：待訪談 work unit／旁支線索／員工延後的焦點；延後不是 `cancelled`；
- `blocked`＋dependency：真的被另一個未澄清 work unit 封鎖的分支；一般「資料還不夠」仍是 Work Model gap，不濫用 dependency；
- `completed`：該焦點目前已達可說明的停止條件，未來有新證據仍可 reopen；
- `cancelled`：確認不適用或已被 merge／retire，不代表刪除歷史；
- `parent_id`：Task 下的 OPKS／子問題或 Duty 下的 Task 訪談層級；
- `depends_on`：只表達真正的 branch dependency，不拿來表示所有相關性。

但官方 source 也揭露三個不能忽略的限制：

1. `PlanItem` 欄位固定，沒有 evidence IDs、work-unit kind、gap reason、revision、return reason 或 employee-defer metadata；這些應由它所引用的 Work Model work unit 擁有，不能塞進自然語言 `content` 後再解析。
2. 內建 `PostgresPlanStore` 的 `set_items()` 是 transaction，但 granular `add_item()` 以 `MAX(seq)+1`、`update_item()`／`remove_item()` 是 read-modify-write；官方 source 明示同一 session 的 concurrent writers 可 race。因此不能原封不動拿來承接 Caliburn 的 semantic CAS。[PostgresPlanStore source](https://github.com/pydantic/pydantic-ai-harness/blob/main/pydantic_ai_harness/planning/_postgres.py)
3. `write_plan()` 是整份覆寫且不發 granular event；若 UI 只吃 event 會漏更新。每輪後必須讀 authoritative plan，或限制模型使用 granular tools。
4. Planning 沒有現成的「被旁支中斷後回到哪裡」stack，也沒有 employee defer／return reason。返回規則可由有序 pending plan＋最近 focus transition 推導；若仍需要 durable LIFO stack，就由很薄的 transition metadata 補足，不能假裝 dependency 已等價承接。

因此建議不是退回自寫 scheduler，而是實作一個很薄的 **staging `PlanStore` adapter**：model run 期間由 Planning 管 tool schema、plan ID、排序、dependency、reminder、progress 與事件，但變更先留在 run staging；新增 domain work unit 仍先經 typed finding／verifier，再由 application 配發 work-unit ID 並建立明確的 plan-item mapping，不從 `content` 解析。最後與 Work Model／Proposal 一起在 semantic transaction commit。commit 後的 table 是 Planning 的唯一 durable plan store，舊 `ActiveQuestion`／`ScheduledOpks`／scheduler 不雙寫。這個 adapter 是為了 identity 與 transaction seam，不是重做 Planning。

Rasa CALM 的 LIFO dialogue stack 很適合驗證「被重大旁支中斷後返回原焦點」的 UX；但它的 flow／slot 是事先定義的業務流程，而 Caliburn 的 work unit 是訪談中動態出現、可 merge／split／reassign 的假說。現階段借用 stack pattern 與 conversation repair，不把產品改成 Rasa flow wizard。[Rasa FlowPolicy](https://rasa.com/docs/reference/config/policies/flow-policy/)

#### 9.5.4 Work Model：四種成熟機制的實際差異

| 候選 | 真正可替代的機制 | 無法自動解決的問題 | v0.4 定位 |
|---|---|---|---|
| SQLAlchemy／Pydantic／PostgreSQL | typed rows、relationship、constraint、async UoW、`version_id_col` stale detection、transaction、直接 query／edit | event replay、projection／upcast、跨 entity lineage 仍要建模；`version_id_col` 只在 ORM flush 檢查該 row，document-wide read-set 仍要顯式設計 | **基準實作**；不是「全部自己寫」，而是以成熟資料框架承接機制，產品只寫 domain policy |
| `eventsourcing` 9.5.4 stable／DCB | immutable events、snapshot、event versioning、optimistic concurrency、atomic multi-aggregate save、outbox notification、projection、Postgres、Pydantic examples；DCB 可依 typed tags／read position 做 conditional append | 使用 Psycopg v3 與自己的 application／repository model；async FastAPI、DBOS datasource transaction、同步 read model／export 及 schema 操作成本要實測 | **優先資料層 conformance 對手**；若淨刪除 journal／revision／projection／CAS 明顯，允許取代關聯式 Work Model 寫入模型 |
| Graphiti OSS | raw episode、episode-to-fact provenance、temporal valid／invalid facts、incremental invalidation、custom entity／edge ontology、hybrid retrieval | 需要 Neo4j／其他 graph DB；entity／fact 由 LLM 抽取；無 Current JD authority、Proposal stale／read-set、精確 Task ID 保證；bulk ingest 不做 edge invalidation | **高覆蓋但高代價候選**。只有能成為唯一 Work Model store、保留 exact source linkage 且淨收益大於新增 graph service 才採用；不能只做第二份 graph mirror |
| LangGraph typed state／Postgres checkpointer／Store＋可選 LangMem | 每步 state snapshot、thread resume／history、typed custom fields、pending writes、namespace store；LangMem 可做 profile／collection 的 LLM insert／update／delete reconciliation | checkpoint 是 agent execution／short-term state，不自帶任意 domain query、Current JD FK／constraint 或與 direct edit 的 transaction；Store 與 state 若都可寫同一事實會成雙 truth。LangMem 更新仍是模型判斷，可能 over／under-extract | **LangGraph finalist 的完整替代路徑**；只有能讓 Work Model 成為唯一可寫 state、並提供 direct edit／export projection 與 atomic authority seam 才採用。否則 LangGraph 只擁有 execution state，Work Model 留在 relational write model |

Graphiti 不能再只因名稱含 knowledge graph 就直接淘汰：它的 episode provenance、temporal fact invalidation 與自訂 ontology，目的確實接近「記得員工說過什麼，遇到更正後更新工作假說」。但「目的接近」仍需證明它能保留穩定 Task／Duty／OPKS ID、exact source anchor、employee correction precedence、文件隔離與 deterministic commit；否則只是功能很多的第二份推測資料。[Graphiti episodes](https://help.getzep.com/graphiti/core-concepts/adding-episodes)、[Graphiti custom ontology](https://help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types/)、[Zep temporal facts](https://help.getzep.com/facts)

同樣地，`eventsourcing` 不是因為「event sourcing 聽起來正規」就全域採用。PyPI 目前最新正式版是 9.5.4；9.6.0b1 與 10.0.0a* 都是 pre-release。官方 `stable` 文件頁首一度顯示 9.5.5，與 PyPI 可安裝發行版不一致，因此 conformance 必須精確鎖 9.5.4，不以文件頁首猜版本。[PyPI release history](https://pypi.org/project/eventsourcing/) 9.5.x 已提供 PostgreSQL、Pydantic、projection、atomic multi-aggregate save、outbox 與 optimistic concurrency，DCB conditional append 也與 source ledger／read-set 的目的高度重疊；但它是專門化 OSS library，不是大廠 agent 標準，而且會新增一套 persistence mental model。[eventsourcing application／outbox／multi-aggregate save](https://eventsourcing.readthedocs.io/en/stable/topics/application.html)、[projections](https://eventsourcing.readthedocs.io/en/stable/topics/projection.html)、[DCB](https://eventsourcing.readthedocs.io/en/stable/topics/dcb.html) 若它無法讓持續理解、訪談控制、待審決策、可見回合與核准成品在同一 write model 原子成立，或只能靠另一個 SQLAlchemy write transaction 雙寫，就直接淘汰；不能只把 Source 放進 event store，其他狀態仍各自提交。

#### 9.5.5 Proposal、證據與 verifier 的框架邊界

Pydantic deferred tools 已支援 validated arguments、唯一 tool-call ID、approve／deny，以及 `ToolApproved.override_args`；AG-UI adapter 又把 edited args、reject reason 與 cancel 映射回這套 primitive。這足以讓「AI 提一份 typed changeset，員工看完修改或拒絕」不必自寫一套通用 tool-approval protocol。[Pydantic deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)、[Pydantic AG-UI approval](https://pydantic.dev/docs/ai/integrations/ui/ag-ui/)

它仍不能直接等同完整 Proposal，原因不是保護舊設計，而是產品行為不同：員工可以暫時不審、繼續訪談、同時有多份 pending bundle、日後 revision-request／defer，accept 時還要重驗 Current JD generation／read-set。Pydantic 的 stop-the-world approval 是一個 run 結束後由另一個 run 延續；Vercel adapter 也明示 client history 是未信任輸入，敏感 approval 需要 server-side record。因此 v0.4 採「框架 typed approval request＋本機 durable proposal record＋獨立 decision command」，並以新 schema 重寫舊 Proposal，不保留舊 class 拓撲。[Vercel AI trust／approval](https://pydantic.dev/docs/ai/integrations/ui/vercel-ai)

證據層也有成熟元件可借：

- W3C Web Annotation 提供 `TextQuoteSelector`／position selector 的可攜 anchor 形狀；PROV-O 提供 derived／revision／invalidation lineage；
- Graphiti episode association 可把 derived fact 追回 raw episode；
- LlamaIndex CitationQueryEngine 與 Haystack `AnswerBuilder` 可把回答連到 retrieved document／source node；
- Pydantic／Harness Guardrails／PostgreSQL constraint 可承接格式、欄位、常見 safety 與 DB invariant。

但沒有一個框架能僅憑 citation object 就判定「這句員工原話真的支持這個 Task／Duty／OPKS claim」。exact quote boundary、有效更正、來源權威與職務分析語意仍需要 deterministic verifier；應把它縮成 framework validator／constraint 上的少量 domain rules，而不是保留現行近千行 verifier 的結構。

#### 9.5.6 修正後的兩個正式決賽組合

Gate 3 不能只靠文件宣告唯一勝者。PydanticAI core 與 LangGraph core 都有 production 級版本政策，但 Pydantic 的 Planning／Harness 比 core 新，LangGraph 要承接 Work Model 又可能把 business authority 拖進 checkpoint／Store。故以下兩套都進 Gate 4；不是先完整做 A、失敗後才重做 B，而是共用同一組很小的 domain fixture／情境，各做最薄 adapter 後立即淘汰較差者。

**Finalist A：PydanticAI V2＋Harness＋DBOS**

1. PydanticAI V2 core 承接 model／OpenRouter／structured output／tool loop／usage；
2. 精選並精準 pin Harness Skills、Planning、Compaction、Tool Output Limits、Guardrails；Memory、StepPersistence、Subagents、Shell／FileSystem 不因功能表存在就引入；
3. DBOS 是唯一 durable execution／partition queue／retry runtime，並用 async datasource transaction 驗 semantic commit；不與 LangGraph checkpoint 或 Harness StepPersistence 疊用；
4. Focus 優先交給 Planning＋staging `PlanStore`；Work Model／Source 以 SQLAlchemy relational baseline 對 `eventsourcing` 做 conformance；
5. Pydantic Vercel AI adapter＋AI SDK 先接 chat／tool／approval UI；edited args／shared state 若需要大量 glue，則整體改用 AG-UI。

**Finalist B：LangChain 1.x＋LangGraph 1.0 LTS 家族**

1. `create_agent` 承接 model／tool loop／structured response，選配 Skills、TodoList、Summarization、Context Editing、Tool Selector、retry／fallback 與 HITL middleware；不直接採完整 Deep Agents 的 filesystem／shell／subagent 預設；
2. LangGraph Functional API＋`AsyncPostgresSaver` 是唯一 durable runtime，承接 checkpoint／resume／pending writes／thread history；不再引入 DBOS；
3. Focus 由 Todo state＋checkpoint 承接。Work Model 有兩個互斥作法：成為同一 typed graph state 的唯一 owner，或留在 relational write model、讓 checkpoint 只保存 execution state；Gate 4 必須證明前者的 direct edit／query／export／migration／authority transaction，不能以 Store mirror 補洞；
4. Proposal 先用 LangChain HITL approve／edit／reject＋interrupt／resume，另存 durable domain changeset；Web 用 LangGraph streaming／frontend，若仍需 richer shared state 才整體採 AG-UI；
5. LangMem 只有在它能刪掉自寫 reconcile 且所有更新仍先經 source／verifier 時才加入，不因同一家族就預設啟用。

兩套共用的非 runtime 選擇是：本機 PostgreSQL 的單一 authority、LlamaIndex 作 final RAG gate、W3C selector／provenance vocabulary，以及 Caliburn 的 Task／Duty／OPKS Skills 與最薄 deterministic policy。兩套不得彼此混裝成 Pydantic agent＋LangGraph checkpoint＋DBOS queue 的三重 runtime。

| 判準 | Finalist A | Finalist B |
|---|---|---|
| 穩定核心 | PydanticAI V2 stable；Harness 個別能力仍需 pin／canary | LangChain 1.x semver＋LangGraph 1.0 LTS；Deep Agents／個別 middleware 仍逐項 pin |
| 一家族覆蓋 | 中高；durability 由 DBOS 補齊 | 高；agent、middleware、checkpoint、memory、HITL、stream 同家族 |
| 與既有 async PostgreSQL authority 的吻合 | 較高；DBOS datasource 明確提供同 transaction outcome tracking | 待證明；checkpointer 很成熟，但不是 business transaction／CAS API |
| Focus 替代 | Planning 的 ID／dependency／store 較直接，但 API 仍可能變 | Todo 與 checkpoint 整合較自然，但產品 metadata／排序／返回仍需 mapping |
| 最大風險 | 新元件版本漂移、框架組合較多 | checkpoint growth／schema evolution、OSS 同 thread 併發與本機 run admission；只有錯誤保留第二個 relational writer 時才會重疊，不能把它算成直接替換的固有缺點 |

Microsoft Agent Framework Harness 已把 loop、per-call history、compaction、todo、mode、memory、approval、OTel、Skills 包在同一套，證明「這些不是都要自己寫」；但 Python self-host persistence／hosting 仍需要 application store adapter，且 framework 在快速演進，現階段維持同級 benchmark。Rasa CALM 只保留為 conversation stack／repair benchmark。

#### 9.5.7 Gate 4 要驗的三個小切片

這不是成品前模型品質 eval；不建立 golden dataset、不打分回答，只驗成熟元件能否忠實替代並減少程式碼。

1. **Focus slice**：同一份 fixture 建立三個 work units，切換焦點、插入旁支、建立 dependency、延後後返回、完成後因更正 reopen。A 用 Pydantic Planning＋staging store，B 用 TodoList／typed state＋Postgres checkpoint；兩邊都證明 stable ID、跨 run persistence、原子 semantic commit、UI event、無雙寫，並量出能刪除的 scheduler／question-target／journal state。
2. **Work Model／Source slice**：保存一句員工原話，建立 Task＋Duty＋OPKS lineage，再送入更正，使只受影響分支 stale／retire，未受影響分支不變；比較 SQLAlchemy baseline、`eventsourcing` DCB／projection，以及 LangGraph typed state／Store 路徑，只有在前三者皆不能合理承接時才加 Graphiti。檢查 exact source、stable ID、read-set conflict、直接 edit／query／export、process restart、document delete、依賴與新增服務。
3. **Proposal／UI slice**：同一 typed review bundle 橫跨 Duty／Task／OPKS，員工修改 args、defer、繼續訪談、日後 accept。A 測 Pydantic deferred tools＋Vercel AI／AG-UI，B 測 LangChain HITL＋LangGraph interrupt／stream；兩邊都驗 server-side pending record、stale rejection、Current JD 原子 commit、未信任 client history 與可刪 Web/API plumbing。

每個 slice 都要交付「舊責任 → 新元件 → 剩餘 policy → 可刪 module／table → 新增 glue／服務 → failure modes」帳本。比較只到足以暴露 authority、persistence 與 UI seam，不做兩套成品；一旦某候選只能再做一份 mirror、無法維持產品語意，或比關聯式基線新增更多概念，就立即淘汰，不因它最新、最流行或來自大廠而保留。

#### 9.5.8 北極星自審

本輪擴大框架替代面後，產品方向仍未改變：

- 員工看到的仍是一位專業職務說明書顧問，不是 Planning UI 裡的工程專案 agent，也不是多 Agent 組織；
- 先建立大致工作地圖，再以明確 Focus 深訪；旁支保存、稍後返回，Task／Duty／OPKS 隨證據動態調整；
- Task／Duty／O／P／K／S 是按需 Skills，不是固定階段，也不要求 Task 穩定後才分析 OPKS；
- 「記憶」仍是記得這位員工在該文件中說過的有效內容與更正；Graphiti／LangMem／eventsourcing 都只是候選機制；
- AI 可更新 Work Model、Focus 與 agenda 候選，但不能偷偷改 Current JD；正式變更仍由員工 accept／edit 或直接編輯；
- Progress 仍顯示 coverage、depth、decision 與具體 gap，不拿 plan 完成數製造假百分比；
- Reference／RAG 仍最後接入、只補漏與挑戰，不替員工創造事實；
- 仍先完成產品核心、後做正式 eval；未新增登入、多租戶、公司 SOP、多人協作、自由多 Agent 或雲端控制面。

**v0.4 結論**：幾乎每一塊自寫機制都有成熟元件可替代一部分，Focus／agenda 的替代甚至已相當直接；但 Work Model、Source、Proposal 與 deterministic evidence authority 沒有一個 agent framework 能零政策接管。最佳升級不是保護舊元件，也不是把所有 state 交給同一套展示用 memory；Gate 4 應讓 PydanticAI／Harness／DBOS 組合與 LangChain／LangGraph LTS 組合正面比較，讓勝出的 runtime、UI、資料與 RAG 元件接手通用機制。最後只留下 Caliburn 已研究驗證的職務分析方法與最薄的 authority policy，而不是現行 class／table／packet 拓撲。

### 9.6 Gate 3 v0.5：直接替換原則下改選 LangChain／LangGraph（2026-08-13）

#### 9.6.1 Owner 糾正與錯誤診斷

Owner 再次指出：如果 LangGraph 的 checkpoint／state／Store 能完成 Work Model、Focus、Proposal 或 Current JD 的目的，就應讓它**直接替換**現行機制；只有保留兩套都可寫的 owner 才叫重疊。v0.4 口頭選擇 PydanticAI-first 時又用了「LangGraph 容易和 relational authority 重疊」作扣分，實際上等於暗中保護舊系統，違反 §2.11、§2.14 與 §9.5.1 的替代判準。

驗證後這項糾正技術上成立：LangGraph 官方把 `State` 定義為 application 的目前快照；schema 可用 `TypedDict`、dataclass 或 Pydantic model，node 只回傳變更，reducers 決定各欄位如何套用。checkpointer 會把 thread state 保存成 checkpoints，支援 `get_state()`、`update_state()`、history、pending writes、replay 與 production `AsyncPostgresSaver`；`interrupt()` 會保存 state 並可無限期等待外部輸入。[Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[PostgreSQL checkpointer](https://reference.langchain.com/python/langgraph/checkpoints)、[Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)

因此正確問題不是「graph state 會不會跟 Work Model 重疊」，而是：**讓 graph state 成為唯一 owner 後，能否忠實承接來源、更正、職務 identity、員工 authority、直接編輯、查詢、匯出、併發與升級。** 若能，舊 tables／repositories／scheduler／proposal lifecycle 必須退出；若不能，才以實際缺口淘汰 LangGraph，不能拿自己選擇保留的第二套 writer 當框架缺點。

#### 9.6.2 選型修正

**目前主方案改為 LangChain 1.x＋LangGraph 1.0 LTS；PydanticAI V2＋Harness＋DBOS 降為整套 fallback。兩套不並用。**

改選理由不是 LangGraph 名氣較大，而是套用 owner 的真正優先序後，它勝在：

1. **直接替換覆蓋較高**：同一家族已有 agent／model／tools、structured response、custom typed state、reducers、Postgres checkpoint、durable execution、HITL、memory、context middleware、todo、streaming 與 frontend hooks；不必再以 Harness 管 Focus、DBOS 管 run、另一套 persistence 管 Work Model。[Prebuilt middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)、[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)
2. **成熟度較高**：LangChain 1.x 採 semver，LangGraph 1.0 是 LTS；PydanticAI V2 core 雖 stable，但本案會高度依賴的 Harness Planning／Skills／Compaction 仍明示 API 可能跨 release 改變。[LangChain／LangGraph release policy](https://docs.langchain.com/oss/python/release-policy)、[Pydantic Harness](https://pydantic.dev/docs/ai/harness/)
3. **產品形狀相容**：graph 不代表固定 wizard。可只保留少量技術 node 與動態 agent loop，下一個 Focus 仍由當下 Work Model／gap／員工改道決定；StateGraph 的 edges 是執行安全邊界，不是把員工訪談切成不可回跳階段。
4. **可讓舊 business state 機制退場**：每份 JD 一個 `thread_id`；§9.7 實測後由同一家族的 Postgres Store 單獨保存完整 Source，DocumentState 保存 Source refs、Work Model、Focus／agenda、Progress、Proposal 與 Current JD。員工直接編輯與 Proposal decision 都是 deterministic graph command／node，不再另寫一份 relational aggregate。
5. **Web 狀態與 HITL 機制也有直接替換路徑**：LangGraph streaming 與 frontend SDK 已支援 typed state、interrupt、approve／edit／reject 與 resume，不需要另選 Vercel adapter 或 AG-UI 才有這些語意。但 `useStream` 需 LangGraph server／Agent Streaming Protocol-compatible endpoint；官方 custom-backend 範例證明現有 FastAPI 可對接，Gate 4 仍要計入 transport adapter 與 protocol 版本成本，不宣稱 UI 完全零 glue。[LangGraph frontend HITL](https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop)、[LangChain frontend overview](https://docs.langchain.com/oss/python/langchain/frontend/overview)、[official custom-backend example](https://github.com/langchain-ai/streaming-cookbook/tree/main/typescript/react-custom-backend)

Pydantic 本身仍可用來定義 Task／Duty／OPKS／changeset／source 等 value object 與 validators；被撤回的是 **PydanticAI＋Harness＋DBOS 作主 runtime**，不是丟掉 Pydantic 資料驗證。

#### 9.6.3 唯一 document state 的建議形狀

本段是 v0.5 進入 Gate 4 前的初始假說；§9.7 的容量與崩潰實測已否定「完整 `source_events` 也放一般 State channel」，並以**按事實類型分配唯一 owner**取代。這不是保留兩套舊系統：每項事實仍只有一個可寫 owner。

- **DocumentState** 是可演化顧問狀態的 typed schema；包含 `work_model`、`focus_plan`、`progress_and_gaps`、`pending_proposals`、`current_jd`、必要 conversation／context receipts、Source refs 與 revision，但不複製完整員工原話 journal；
- **AsyncPostgresSaver** 是 DocumentState 的唯一 durable persistence／history mechanism，不另保留可寫的 Work Model／Focus／Proposal／Current JD tables；
- **AsyncPostgresStore 是 Source payload 的唯一 owner**。每份文件使用 `("job-analysis", document_id, "sources")` namespace，穩定 `input_event_id` 作 key，保存不可變原話／speaker／document scope 與可變 processing envelope；State、Work Model 與 Proposal 只保存 Source ID／receipt，不再存第二份原話；
- **Store＋Saver 不是單一 ACID transaction**，因此 Source row 先以 `pending` durable inbox 寫入，再進 graph；兩個崩潰窗口都以同 ID 重試與 reconciliation 收斂。這是通用 source-first plumbing，不是第二份業務 authority；
- 文件列表保留只擁有 `document_id`、title、thread pointer、刪除 tombstone、狀態與時間的 catalog，或建立可重建 read projection；它不得反向修改 Source／Work Model／Proposal／Current JD。刪除先 tombstone，再冪等清除 Store namespace 與 thread checkpoints，避免清到一半重新露出文件。

LangGraph 官方以跨 thread memory 說明 Store 的主要用途，但 namespace 可以是任意長度與任意應用 scope，Postgres 實作提供 key lookup、filter、search、delete 與持久化；Gate 4-A 已直接驗證 per-document Source journal。故「Store 只能放跨文件偏好」是 v0.5 過度限縮，不再採用。[LangGraph persistence／Store](https://docs.langchain.com/oss/python/langgraph/persistence)、[Postgres Store](https://reference.langchain.com/python/langgraph.store.postgres/aio)

建議的責任映射如下：

| 產品責任 | LangChain／LangGraph 直接承接 | Caliburn 保留的最薄內容 |
|---|---|---|
| 模型／OpenRouter／參數／tool loop／structured output | LangChain model abstraction、tools、structured response、retry／fallback／call-limit middleware | 版本化 model profile、實際 route／usage receipt、成本與資料政策 |
| Task／Duty／OPKS Skills | 獨立 `SkillsMiddleware`／Agent Skills progressive disclosure；只載入當下 eligible skills | 已研究的分析方法內容與 deterministic eligibility |
| Context／記憶 | thread state、messages、dynamic prompt、summarization、context editing、tool selector；Postgres Store 依 Source ID／filter 取回必要原話 | 哪些 Source／更正／Focus／JD／Reference 應進本次 context 的 policy 與 `ContextManifest` |
| Focus／agenda／旁支／Progress | typed `focus_plan` state、reducers、Todo middleware、checkpoint history | work-unit schema、選焦點與停止條件、gap reason、員工改道／延後語意 |
| Source | `AsyncPostgresStore` namespace／key／filter／delete 與 application-lifetime batching；`pending` row 作 source-first durable inbox | immutable payload hash、相同 ID 衝突、correction／supersede、pending reconciliation、document tombstone 與 Source ID 引用規則 |
| Work Model／Current JD | 同一 `DocumentState` 的獨立 channels；deterministic reducer／node 套用更新；Postgres checkpoint 持久化 | stable identity、lineage、Task／Duty／OPKS invariant 與 Current JD authority |
| Proposal | state 中的 durable typed changesets；blocking case 用 interrupt，non-blocking case 保存後正常結束；員工日後以新 graph command 決策 | bundle／atomic subgroup、before／after、defer／revision request、stale／read-set 與 accept 後 authority rule |
| durable run／恢復 | checkpointer、tasks、pending writes、interrupt／resume、thread history；Store pending inbox | source-first reconciliation、同 document run admission、外部 provider at-least-once 與 idempotency key |
| API／Web | LangGraph state／interrupt；FastAPI 0.135+ 原生 typed SSE；瀏覽器 `EventSource` 自動重連；TanStack Query 管 server projection | generated product contract、server validation、只投影 verified product status、dirty edit 與匯出 UX；不實作完整 Agent Protocol |
| RAG | 最後關卡可比較 LangChain retriever／Qdrant 與 LlamaIndex；不因主 runtime 已選就硬綁 | iCAP corpus、Reference challenge、來源版本與無員工事實 authority |

模型不能因為 state 由 LangGraph 保存就直接改 Current JD。正確結構是：模型只能呼叫「提出 finding／changeset」工具；deterministic verifier node 決定哪些更新可進 Work Model／Focus／Proposal；只有員工 direct-edit 或 accept／edit command 會經 authority node 更新 `current_jd`。框架取代的是 state、persistence、resume、middleware 與 UI 機制，產品的分析方法和權限仍以 schema／node policy 表達。

#### 9.6.4 真正要驗的風險（不再列「重疊」）

1. **source-first durability**：必須證明員工輸入已進 Store 的 durable `pending` inbox 後才打 provider；graph 只在後續 checkpoint 保存 Source receipt／處理狀態。model 前後 kill process 都不遺失原話，也不產生半套 Work Model／Proposal。
2. **同 thread 併發**：LangGraph OSS 不含 LangSmith Deployment 的 double-text enqueue／reject；本機單 process 第一版先用很薄的 per-document run-admission lock＋durable active-operation reconciliation，確保回答、直接編輯與 Proposal decision 不並行寫同一 thread；部署變成多 process 時才升級成 PostgreSQL advisory lock／queue。這是缺少 queue 的實際風險，不是 state 重疊。[Double texting scope](https://docs.langchain.com/langsmith/double-texting)
3. **checkpoint visibility／atomicity**：要證明已驗證的 Source refs／processing receipt、Work Model、Focus、Proposal 與可見 consultant turn 在同一 semantic checkpoint 一起可見，失敗時一起不成立；完整 Source payload 仍只在 Store，Current JD decision 亦同。
4. **state growth**：官方預設每個 super-step 對每個 state channel 寫完整新值；Source／messages／history 不能無限複製。要測代表性長訪談，調整 channel 粒度、node 粒度、retention 與 compaction；summary 永不取代原始 Source。[Checkpoint model](https://docs.langchain.com/oss/python/langgraph/persistence)
5. **schema／graph evolution**：LangGraph 會以最新 graph code 讀既有 checkpoint，node／state 欄位是 persisted API；需版本欄位、upcaster／migration、drain 規則與 document delete。第一版可 fresh schema，不代表未來不用升級策略。[Backward compatibility](https://docs.langchain.com/oss/python/langgraph/backward-compatibility)
6. **直接 edit／query／export**：必須從最新 state 完成員工直接編輯、文件重開、readiness 與 deterministic export；不能為方便查詢又建立可寫的第二份 JD。read projection 必須可刪除重建。
7. **side-effect replay**：官方要求非確定性與 I/O 放進 task 並自行做到 idempotent；provider call 仍可能在 crash window 重打，不能宣稱 exactly-once。[Functional API](https://docs.langchain.com/oss/python/langgraph/functional-api)
8. **本機操作、授權與 frontend transport**：主 runtime 以 OSS LangChain／LangGraph library 與 `AsyncPostgresSaver` 嵌入 FastAPI／PostgreSQL。§9.9 已實測後選擇更薄的 product typed SSE：新版 FastAPI 接手 SSE framing／heartbeat，瀏覽器 `EventSource` 接手重連，LangGraph checkpoint 接手恢復；不採需 license key、Redis 與額外 container 的 standalone Agent Server，也不自行重寫它的 Agent Protocol。未來若產品真的需要多 worker queue、exact run replay、token／tool／multimodal stream 或多 client，再整體重新評估 Agent Server＋`@langchain/react`。[Standalone Agent Server requirements](https://docs.langchain.com/langsmith/deploy-standalone-server)、[Agent Server architecture](https://docs.langchain.com/langsmith/agent-server)、[FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)

#### 9.6.5 Gate 4 與目前裁決

Gate 4 不再平行開發兩套完整 slice。先在隔離 worktree 做一個可丟棄的 **LangGraph-first vertical conformance**：一份 JD、三個 work units、一則旁支、一則員工更正、一份可延後 Proposal，以及一次直接編輯／accept／export；同時測 restart、同 thread 競爭、state migration、delete，以及瀏覽器中斷後重連／interrupt 恢復。frontend 至少比較 Agent Server-compatible 與 custom FastAPI transport 的總成本。交付物必須列出舊 module／table／concept 可刪清單與新增 glue，且不做模型品質 eval。

只有出現以下核心硬缺口才整套切回 PydanticAI＋Harness＋DBOS：OSS checkpointer 無法提供所需 semantic checkpoint、長訪談 state growth 無法以合理 channel／retention 控制、direct edit／export 必須建立第二個可寫 authority，或本機 run admission／升級成本使 LangGraph 的淨複雜度反而更高。不能因 adapter 還沒寫就保留舊 store，也不能把 DBOS 疊在 LangGraph 上補洞。

**v0.5 當時選擇：LangChain 1.x＋LangGraph 1.0 LTS 作主 runtime 與 document-state mechanism；PydanticAI＋Harness＋DBOS 是硬缺口時的整套 fallback。** 主方案已由 §9.7 v0.6 實測保留，但 Source mechanism 改由 Postgres Store 單獨承接。這個裁決遵守「目的與方法保留、機制可直接替換」：Task／Duty／OPKS 分析方法、來源與員工 authority 繼續存在，但現行 Work Model、Focus、Proposal、Context、durable-turn、provider、wire、repository 與 UI state plumbing 都不預設保留。

### 9.7 Gate 4-A v0.6：LangGraph document-authority conformance 實測（2026-08-13）

#### 9.7.1 範圍、版本與可重現邊界

Owner 核准後，在 `spike/langgraph-document-authority` 隔離 worktree 建立可丟棄探針；沒有修改 production dependency、現行資料表、API／Web 或模型 prompt。探針使用 Python 3.13.12、LangGraph 1.2.11、`langgraph-checkpoint` 4.1.1、`langgraph-checkpoint-postgres` 3.1.0 與獨立 PostgreSQL 16 資料庫；版本以 `uv run --with` 暫時解析，並在 Gate 4-B 解析出更新版本後重跑全部 14 項，沒有偷改產品 lockfile。這一關只驗工程語意，不呼叫 LLM、不建立 golden dataset、不比較回答品質。

最終探針共 14 個測試，涵蓋：

1. Source 先保存、後續分析崩潰時原話仍可恢復；
2. 穩定 `input_event_id` 的重送去重與不同 payload 衝突拒絕；
3. Work Model、Focus、Progress／gap、Proposal 與可見 consultant turn 在同一 semantic checkpoint 出現，AI 路徑不改 Current JD；
4. Proposal `interrupt()` 跨 graph／database connection restart 後仍可 approve／defer，只有 approve 改 Current JD；
5. 直接編輯以 revision CAS 拒絕 stale writer，query／deterministic export 直接讀最新 State，`adelete_thread()` 可清除 checkpoints；
6. 本機單 process 的 per-document run admission 可把同 revision 競爭序列化成一成功、一 stale；
7. 完成中的 checkpoint 可由新增 state 欄位與改過 node topology 的新 graph 開啟，非 additive 演化仍保留 migration 要求；
8. 普通累積 State、官方 beta `DeltaChannel` 與 Postgres Store 三種 Source 保存方式的實際 PostgreSQL 成長；
9. Store 已寫、source-receipt checkpoint 未寫，以及 analysis checkpoint 已寫、Store completion 未寫的兩個崩潰窗口；
10. Store namespace＋thread checkpoints 的完整、可重試、冪等刪除。

這不是完整產品 vertical slice：尚未接真模型、Task／Duty／OPKS Skills、Context token budget、OpenRouter profile、Web streaming 或瀏覽器重連。它回答的是「成熟框架能否取代核心 state／journal／HITL／恢復機制」，不能被誤報成產品已可施工或品質已驗證。

#### 9.7.2 State growth 的反例與替代結果

官方文件明確說明：一般 checkpoint 預設在每個 super-step 保存各 channel 的完整值，長期累積資料可能持續膨脹；1.2 新增 `DeltaChannel` 只保存增量並從 ancestor writes 重建，但目前仍標示 beta。[Persistence — Optimize checkpoint storage](https://docs.langchain.com/oss/python/langgraph/persistence)、[`DeltaChannel` reference](https://reference.langchain.com/python/langgraph/channels/delta)

探針各建立 25 與 50 回合、每回合一則唯一中文長原話的 thread，計算 `checkpoints`、`checkpoint_blobs`、`checkpoint_writes`，Store 方案另加 `store` row bytes。結果如下：

| Source mechanism | 25 回合 | 50 回合 | 50／25 | 判斷 |
|---|---:|---:|---:|---|
| 一般 reducer，把完整 `source_events` 累積在 State | 1,199,355 bytes | 3,935,508 bytes | **3.281×** | 淘汰；`source_events` blob 本身由 798,245 增至 3,131,520 bytes，是主要膨脹來源 |
| `AsyncPostgresStore` 每則 Source 一個 key，State 只留 receipt／狀態 | 366,154 bytes | 732,349 bytes | **2.000×** | 通過；完整原話只保存一次，可依 ID／namespace／filter 查詢 |
| beta `DeltaChannel` 保存 append delta | 321,440 bytes | 643,560 bytes | **2.002×** | 容量通過，但仍在開 thread 時重建整份 journal，且官方 on-disk／周邊 API 尚未 stable |

這組數據只比較 persistence mechanics，不預測真實模型 token 或品質。它足以否定 v0.5 的一般 `source_events` channel，也顯示不能只因 Delta 容量略小就讓 beta 元件承接唯一 Source authority。

#### 9.7.3 Source owner 與崩潰語意的修正裁決

**v0.6 選擇 `AsyncPostgresStore` 作完整 Source payload 的唯一 owner；`DocumentState`＋`AsyncPostgresSaver` 作 Work Model、Focus、Progress、Proposal、Current JD 與執行 receipts 的唯一 owner。** 兩者保存的是不同事實，不是相同 Work Model／JD 的雙寫：

- Source key 是 caller-provided `input_event_id`；不可變部分包含 document scope、speaker、原話與 canonical hash，狀態 envelope 可由 `pending` 轉 `complete`；
- 相同 ID＋相同 payload 回既有結果且不重跑分析；相同 ID＋不同 payload 拒絕，不由 Store 的 upsert 靜默覆寫；
- Store 先寫 `pending`，graph 才建立 source receipt 並分析。若 Store put 後、checkpoint 前崩潰，namespace query 可找回 pending Source；若 analysis checkpoint 後、completion 前崩潰，重送只補 completion，不再分析；
- Work Model、Proposal 與 ContextManifest 只引用 Source ID；Context Engine 按當輪 Focus／gap 查回必要原話，不把全部 Store 內容自動塞給模型；
- correction 是新的 Source event 並明列 supersedes／rebuts 關係，不改寫舊原話；processing envelope 的更新不改變 immutable employee payload。

這個 pending／reconciliation seam 是 Store 與 checkpointer 未提供跨元件單一 ACID commit 的必要薄 glue。探針已證明兩個窗口都不遺失 Source、可重試且不重跑已完成分析；因此不構成切回 DBOS 的硬缺口。若未來改成多 process／多 worker，單 process `asyncio.Lock` 不再足夠，屆時須以 PostgreSQL advisory lock／lease 或 Agent Server run queue 取代，不能假裝目前測試已覆蓋分散式併發。

文件刪除也不是只呼叫 `adelete_thread()`：catalog 必須先 tombstone 文件，再冪等清除 Source namespace 與 checkpoints；探針已驗 cleanup 重跑安全，但 catalog tombstone／crash sweep 尚待目標架構正式設計。`AsyncPostgresStore` 在本次版本採 application-lifetime background batch task，測試環境因沒有公開 close API 而需在 fixture 收尾；FastAPI lifespan／graceful shutdown 必須列入下一關 conformance，不能把這個套件生命週期細節藏掉。

#### 9.7.4 其他通過與仍需自寫的最薄政策

探針支持 LangGraph 直接替換現行機制，而不是包住舊系統：

| 責任 | 探針結論 | production 仍需的薄政策 |
|---|---|---|
| Work Model／Focus／Progress／Proposal／Current JD | typed State＋reducers／nodes＋Postgres checkpoint 足以成為唯一 owner | Caliburn schema、職務 identity、dependency invalidation、read-set／revision 與 authority 規則 |
| Proposal HITL | `interrupt()`／`Command(resume=...)` 跨 restart 可恢復；defer 不改 JD，approve 才改 | review bundle、edit／reject／revision request、atomic subgroup 與 UI wording |
| direct edit／query／export | latest State 可直接承接，不需第二份可寫 JD | deterministic readiness／assembly、generated API contract 與 stale UX |
| run admission | current local-only 單 process 可用薄 per-document lock＋revision CAS | lock ownership、timeout、取消與未來多 worker successor |
| schema evolution | additive state／graph topology change可開舊 checkpoint | persisted schema version、non-additive upcaster、drain／rollback 規則 |
| Source | 穩定 Postgres Store 已通過容量、查詢、衝突與 recovery | immutable payload contract、pending sweep、更正關係、刪除 tombstone |

`DeltaChannel` 不作 Source owner，但不是全面禁用。若 messages、operation receipts 或其他 append-heavy State 未來實測也膨脹，可在版本 pin、restart、prune、migration 與 restore conformance 後個別採用；不能因它是新功能就先把所有 list 換掉。

#### 9.7.5 v0.6 選型與下一關

**LangChain 1.x＋LangGraph 1.x 繼續作主 runtime；PydanticAI＋Harness＋DBOS 維持整套 fallback，這次沒有觸發切換條件。** 原因是核心 semantic checkpoint、HITL、restart、direct edit／query／export、local concurrency、additive evolution、Source lifecycle 與線性容量都有可行機制，而且沒有留下第二份 Work Model、Proposal 或 Current JD writer。

Gate 4-B 只做尚未被本探針回答的下一個最小 slice，不重新討論產品北極星：

1. 以 LangChain model／tool／structured output 組一個「主顧問快速路徑＋最多兩波唯讀補查」的 bounded run，驗證可替換 OpenRouter model／provider／參數 profile、usage 與錯誤映射；
2. 以 Task／Duty／O／P／K／S 六個小型測試 Skill 驗證 deterministic eligible set、progressive disclosure、當輪可組合載入與 durable replay；
3. 由 Postgres Store Source＋DocumentState 組裝受 token budget 約束的 ContextPack／ContextManifest，證明會記得早先原話與更正，但不每輪傳整份歷史；
4. 比較現有 FastAPI typed SSE 與 Agent Streaming Protocol-compatible transport 的 interrupt／重連／dirty-edit 成本；不因 `useStream` 存在就重寫半個 Agent Server；
5. 把 Gate 4-A／B 結果收斂成目標架構、successor ADR 與受限 Big-bang plan，回看本稿北極星後才請 owner 核准實作。

正式長訪談 eval 仍依 owner 裁示延後到成品完成後；Gate 4-B 只做 framework conformance、固定 fixture 與人工 smoke，不偷偷擴張成模型品質專案。

### 9.8 Gate 4-B v0.7：Context／Skills／provider bounded-loop conformance（2026-08-13）

#### 9.8.1 範圍、版本與測試結果

同一隔離 worktree 增加第二個可丟棄探針；仍未修改 production dependency、現行 API／Web、產品資料庫或模型 prompt。探針使用 Python 3.13.12、LangChain 1.3.15、`langchain-core` 1.5.4、LangGraph 1.2.11、`langchain-openrouter` 0.2.7 與 Deep Agents 0.7.5；以 deterministic tool-capable fake model 驗工程契約，不呼叫付費模型、不做回答品質 eval。

最新版套件下共 5 項測試通過：

1. 版本化 model profile 可直接映射 OpenRouter model ID、temperature、max completion tokens、reasoning、provider order、fallback 與 `require_parameters`；應用不需再自己拼 provider request wire；
2. 同一 bounded run 只預載當輪有效的員工更正、Focus、Progress、Current JD 與可用 Source ID；舊說法與旁支原話不先塞入，模型需要旁支時才透過唯讀工具取回；
3. Task／Duty／O／P／K／S 六個獨立 Skill 可由 deterministic eligible set 篩選；初始 context 只含 eligible metadata，完整 `SKILL.md` 在需要時才讀取；同一 thread 下一輪改變 Focus 後，上一輪 eligible Skill 不會殘留到新 prompt；
4. framework `ModelCallLimitMiddleware` 與 `ToolCallLimitMiddleware` 能把失控循環硬停在 3 次 model call、1 次 Skill read、最多 2 次 Source lookup；測試故意讓模型持續查詢，第三次嘗試即被停止；
5. structured output 之外再跑 deterministic verifier，未列入當輪 eligibility 的 Skill 或 ContextManifest 未授權的 Source 都會被拒絕，不能只相信模型自行申報。

主成功情境實際是 3 次 model call：第一次決定讀取 `opks-o`、第二次決定補查旁支 Source、第三次提交 typed `ConsultantTurn`。這正好是「快速路徑＋最多兩波唯讀補查」的上限形狀；若當輪已具 sufficient context，實際產品可以直接一次產出，不必為使用框架固定多跑兩次。LangChain 官方也把 context engineering 定義為在每一步選擇正確資訊與工具，而不是把所有可得資料塞進 prompt；middleware 是其控制 prompt、messages、tools、model 與 response format 的正式擴充面。[Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)、[Agents](https://docs.langchain.com/oss/python/langchain/agents)、[Structured output](https://docs.langchain.com/oss/python/langchain/structured-output)

時序註記：本節記錄 Gate 4-B 探針當時證明「成熟 framework primitive 足以承接機制」的結果，不是現行 Opus 5 output-strategy 裁決。Task 10 後續量測確認 rich output schema 本身超過 optional／union 公開限制，故現行修正見 §9.16：先 compact provider wire＋pure mapper、保留 bounded agent與 provider-native strategy，不沿用探針的 `ToolStrategy`，也不自動 fallback；exact canary 仍失敗才拆 tool-free finalization。產品目的、三次總上限與同一位主要顧問不變。

#### 9.8.2 成熟元件實際替代了什麼

| 產品責任 | 探針採用的成熟元件 | Caliburn 最後只留的薄政策 |
|---|---|---|
| 模型／provider／參數切換 | `ChatOpenRouter`＋LangChain model/tool binding | 版本化 profile、允許清單、資料政策、成本／route receipt |
| bounded consultant loop | `create_agent` 編譯出的 LangGraph＋model／tool call limit middleware | 每輪最多幾波補查、錯誤映射與產品可見訊息 |
| typed 顧問結果 | `ToolStrategy(Pydantic schema)`（僅 Gate 4-B 探針；現行裁決見上方時序註記與 §9.15） | 職務分析欄位、authority 與 domain verifier |
| Context 組裝生命週期 | custom middleware hook＋LangGraph Store／State | 哪些 Source 是有效更正、Focus 核心、token budget、ContextManifest |
| Skill registry／progressive disclosure | 單獨使用 Deep Agents `SkillsMiddleware`＋read-only `FilesystemMiddleware` | Task／Duty／OPKS 研究內容、當輪 eligibility、使用後驗證 |
| 失控保護 | `ModelCallLimitMiddleware`＋`ToolCallLimitMiddleware` | 第一版的具體上限與不同操作的政策 |

這證明「保留產品目的、替換自寫機制」可落地：Focus／Work Model／Progress／Proposal／Current JD 由 Gate 4-A 的 typed State 與 Store 機制承接；Gate 4-B 再讓框架接手 provider、tool loop、structured output、middleware lifecycle、Skill discovery/read 與 call limits。Caliburn 不必保留舊 ContextPacket、provider wire、operation wrapper 或 Skill 常駐 prompt，只需重寫少量可測的選擇與驗證規則。

#### 9.8.3 沒有盲目採用完整 Deep Agents

Deep Agents 的 `SkillsMiddleware` 是可單獨組裝的成熟元件，因此本案不必自己重寫 YAML metadata discovery、progressive disclosure prompt 與 `SKILL.md` 讀取協定；但完整 `create_deep_agent` 預設同時帶入 todo planning、檔案系統寫入、subagent、通用 summarization 與 coding-agent 式工作方式，這些不是本產品第一版需求，會把一位受限職務分析顧問改造成自由代理。因此裁決是：

- **採用元件，不採用整包產品形狀**：只評估／pin `SkillsMiddleware` 與唯讀 `read_file`；不開放 write、shell、subagent、自由 todo；
- **補一個必要且合理的薄 adapter**：原生 Skills middleware 會先載入 static source 的全部 metadata，本案需依 Focus／gap 在每輪 request 前篩出 eligible set。這不是重寫 Skill framework，而是 Caliburn 特有 eligibility policy；
- **成本仍需產品化時量測**：progressive read 會多一個 model round trip；若某個短 Skill 幾乎每輪都 eligible，直接由 middleware 確定性預載全文可能更便宜。第一版應保留兩種載入模式，以實際 token／latency telemetry 決定，不先做模型品質 eval，也不把所有六個 Skill 常駐 prompt。

官方文件將 Skills 定位為 metadata 先行、完整指示按需讀取；`SkillsMiddleware` 可獨立使用，支持目前的元件級採用，而不是要求採完整 Deep Agents。[Agent Skills specification](https://agentskills.io/specification)、[Deep Agents Skills](https://docs.langchain.com/oss/python/deepagents/skills)、[`SkillsMiddleware` reference](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware)

#### 9.8.4 大方向回歸與下一步

本輪沒有改變產品流程：仍是一位專業顧問；先建立可修正的工作全貌，再以明確 Focus 深訪；旁支先保存、必要時返回；Task／Duty／O／P／K／S 是同一訪談中的按需分析方法；員工原話與更正可長期找回；AI 只能提出 typed 候選，Current JD 仍只由員工 direct edit 或核准後的 authority command 改變；進度仍顯示 coverage、depth、decision 與具體 gap，不改成 agent tool-call 百分比。正式品質 eval 仍後置。

本段當時剩餘的 frontend transport 已由 §9.9 完成；三個探針合併後的目標架構見 §9.10。探針仍不是 production 施工授權；successor ADR、刪除帳本與受限 Big-bang plan 必須等 owner 審核 §9.10 後另開。

### 9.9 Gate 4-C v0.8：frontend transport／斷線恢復 conformance（2026-08-13）

#### 9.9.1 問題、現況與證據層級

這一關不是問「哪套 UI framework 功能最多」，而是問：**在不改變產品北極星的前提下，哪個成熟組合能讓員工送出的原話先保存、AI 在瀏覽器斷線後繼續、重開頁面能恢復、typed interrupt 能安全回覆、Current JD 編輯草稿不被背景更新蓋掉，且不用重寫半個 agent platform？**

現行 production `POST /job-analysis/documents/{id}/turns` 會同步等完整 LLM 回合完成，再回整份 `ConsultationView`；Web 以 TanStack Query 寫回 consultation cache 並 invalidate document。repo 沒有 SSE／WebSocket。另一方面，現行 Web 已有成熟的 header／Duty／Task／OPKS local draft、dirty flag 與離頁保護；新 transport 可重寫舊 consultation plumbing，但不能讓背景 state snapshot 覆蓋員工尚未儲存的文字。

證據分三層，避免把文件宣告寫成本機實測：

1. **官方 production 能力**：LangSmith Agent Server 有 PostgreSQL thread／run／checkpoint／store、Redis pub-sub／streaming、背景 queue、reconnect／replay 與 double-texting；standalone production 仍要求 Redis、PostgreSQL、LangSmith API key、`LANGGRAPH_CLOUD_LICENSE_KEY` 與 license egress。[Agent Server](https://docs.langchain.com/langsmith/agent-server)、[standalone requirements](https://docs.langchain.com/langsmith/deploy-standalone-server)、[reconnect streaming](https://docs.langchain.com/langsmith/streaming)
2. **官方 custom-backend 參考實作**：2026-07-16 的 LangChain streaming cookbook commit [`8c63965`](https://github.com/langchain-ai/streaming-cookbook/commit/8c63965f48d0c0a9da6485bdf119906cfaa79ea9) 使用 `@langchain/react`、`HttpAgentServerAdapter`、LangGraph 1.2 與 HTTP／SSE，證明不必採託管服務也能接 SDK；但 Python 範例的 `server.py`／`session.py`／`threads.py` 已有 873 行，另有 213 行 frontend thread bootstrap，且 `LocalThreadSession` 自己明示是 process-local demo，production 必須持久化 thread 並協調跨 worker replay。其 Python bridge 還抑制「v3 streaming protocol is experimental」警告；cookbook 首頁也把相關 event-streaming API 標為 preview。[Official cookbook](https://github.com/langchain-ai/streaming-cookbook)、[custom backend](https://github.com/langchain-ai/streaming-cookbook/tree/main/python/react-custom-backend)
3. **本機產品語意探針**：在隔離 worktree 新增不進 production 的 `frontend_transport_spike.py` 與 6 項固定測試，驗證 durable snapshot、idempotency、interrupt scope／revision、restart resume、wire allowlist 與 dirty-draft 行為。這不是 HTTP framework benchmark，也不是 production LOC 估算；其 in-memory operation store 只代替目標設計中的 LangGraph DocumentState，不能演變成第二個資料表。

FastAPI 本身在 0.135.0 起已原生支援 typed SSE；截至查核日 PyPI 最新為 0.141.1。官方介面直接以 Pydantic／JSON 產生 `data`，支援 `event`、`id`、`retry`、`Last-Event-ID`，並預設 heartbeat、`Cache-Control: no-cache` 與 `X-Accel-Buffering: no`。這些正好替代手寫 SSE framing。現行 API 仍是 FastAPI 0.115.0／Starlette 0.38.6，因此這是**待完整 API gate 驗證的升級候選**，不能直接在研究稿宣稱相容。[FastAPI SSE](https://fastapi.tiangolo.com/tutorial/server-sent-events/)、[FastAPI 0.141.1 source](https://github.com/fastapi/fastapi/blob/0.141.1/fastapi/sse.py)、[FastAPI PyPI](https://pypi.org/project/fastapi/)

另查了 `sse-starlette` 3.4.8：它是 production/stable、BSD-3-Clause，提供 disconnect、ping、send timeout 與 graceful shutdown；但最新版要求 Starlette >=0.49.1，仍會迫使現行 stack 升級。既然新版 FastAPI 已把本產品需要的 SSE 能力收進 core，第一版不再額外增加這個依賴。[sse-starlette 3.4.8](https://pypi.org/project/sse-starlette/)、[dependency source](https://github.com/sysid/sse-starlette/blob/v3.4.8/pyproject.toml)

嘗試以 `uv run --with fastapi==0.141.1` 做真正 HTTP smoke 時，隔離快取沒有套件，外部下載又被執行環境的 usage limit 拒絕；因此本節只把 FastAPI wire 行為列為**官方文件／原始碼確認**，不冒充本機跑過。進入 implementation plan 後，FastAPI 升級與 SSE route smoke 必須是第一個 prerequisite gate。

#### 9.9.2 三條正式候選比較

| 路徑 | 能直接替換的成熟機制 | 為本產品完整替換後的代價 | v0.8 裁決 |
|---|---|---|---|
| Agent Server＋`@langchain/react useStream` | thread／run API、queue、serialization、exact replay、join／rejoin、HITL、state/history、token／tool／multimodal stream、frontend projections | 新 Agent Server container、Redis、另一組 server resource／route、license key／egress；本機單一使用者仍須操作這些元件。這不是「與舊 state 重疊」：舊 mechanism 可全刪；問題是替換後產品仍承擔大量目前不用的能力與運維 | **第一版不採**；未來若需求真的變成 remote／multi-worker／多 client／exact replay，再整體評估，不在 FastAPI 上疊半套 |
| 自建 Agent Streaming Protocol-compatible FastAPI＋`HttpAgentServerAdapter` | frontend `useStream`、message／tool／interrupt projections、filtered subscriptions、replay／dedupe | 官方 adapter contract 要 backend buffer／replay 完整 run、處理 commands、state/history、filter／namespace、late subscription；官方最小 demo 仍是 process-local。SDK 1.9.20–1.9.29 連續修正 hydration、heartbeat reconnect、`since`、HITL resume 與 nested interrupt，表示能力成熟度快速提高，但 protocol edge 仍在密集硬化。[Transport contract](https://reference.langchain.com/javascript/langchain-react/transports)、[SDK changelog](https://github.com/langchain-ai/langgraphjs/blob/main/libs/sdk/CHANGELOG.md) | **第一版不採**；只為 4–6 種產品狀態實作完整 Agent Protocol，新增碼與風險大於刪除碼 |
| LangGraph embedded runtime＋FastAPI typed SSE＋browser `EventSource`＋TanStack Query | LangGraph 接 durable run／interrupt；FastAPI 接 typed encoding／heartbeat／headers；瀏覽器標準接 reconnect／`Last-Event-ID`；TanStack Query 接 durable view hydration／invalidation | 仍需一個很薄的 product operation contract、run-admission 與 dirty-draft 協調；沒有 Agent Server 的 exact event history、distributed queue 或 token／tool projection | **第一版採用**；它是多個成熟框架元件的組合，不是手寫 SSE。缺少的都是本機單人第一版不需要的能力 |

`@langchain/react` 的功能確實完整，而且可直接替換一整套 agent frontend；未選它不是保護現行 Web。官方 v1 root hook 會擁有 thread lifecycle、`values`、messages、tool calls、interrupts 與 history；若 Caliburn 完整採用，就也應把文件讀取／direct edit／Proposal／dirty draft 全改成其 thread／command shape。若只拿 loading 與 interrupt，backend 仍被迫履行完整 replay contract，反而不是節省程式。第一版選擇較窄的產品 contract，未來 switch trigger 成立時再整條換掉，不維持兩套同事實 writer。

#### 9.9.3 目標 transport 契約

第一版不把 LLM token stream 當產品輸出。模型產生的自由文字、tool args、Skill 名稱、reasoning 與未驗證 structured result 都不送到員工畫面；它們通過 schema／deterministic verifier 後，才以完整的顧問訊息、Work Model／Progress projection 或 Proposal 出現。SSE 只傳產品級狀態：

- `operation.accepted`：員工原話已 durable 保存；
- `operation.progress`：有限 enum，例如「理解回答／更新工作全貌／準備下一題」，不顯示虛構百分比；
- `input.required`：typed `UnderstandingCheckpoint`，含 interrupt ID、允許動作與 revision；
- `operation.completed`：已驗證顧問回合成立，附新的 document revision；
- `operation.failed`：員工原話仍在，畫面只顯示安全且可重試的錯誤；
- `operation.snapshot`：重開／重連時的最新 durable 狀態，而不是重播所有短暫 animation。

建議 public contract 由現有 JSON Schema SSOT 生成 Python／TypeScript，不直接暴露 LangGraph internal event：

1. `POST /documents/{document_id}/turns`：驗文字與 `Idempotency-Key`，先完成 Source acceptance，再回 `202 OperationAccepted`；同 ID＋同 payload 回既有 operation，不同 payload 回 conflict。瀏覽器在這一步成功後即可清空送出框，不必等模型完成。
2. `GET /documents/{document_id}/operations/{operation_id}`：回 durable `OperationView`；重開頁面先 hydrate，若仍 running 才開 SSE。
3. `GET /documents/{document_id}/operations/{operation_id}/events`：原生 `EventSource`。event ID 是 server 產生的 operation revision；`Last-Event-ID` 只作提示，server 仍以 route scope 與 durable snapshot 驗證，不信任 client cursor。
4. `POST /documents/{document_id}/operations/{operation_id}/inputs/{interrupt_id}/responses`：typed response＋idempotency key＋expected operation revision；server 驗 scope／interrupt／revision 後才轉成 `Command(resume=...)`。
5. non-blocking Proposal 仍是 DocumentState 中可日後審核的 durable changeset，以獨立 decision command 處理；不能把所有 Proposal 都誤做成會停止訪談的 interrupt。
6. `GET document／consultation projection` 仍是員工可見的完整 durable view；SSE 的 `document_revision` 只要求 refetch，不攜帶一份可直接覆寫 editor 的 Current JD。

WHATWG `EventSource` 標準會在連線中斷後自動重連，並以 `Last-Event-ID` 回報最後 event ID；它沒有替 server 保存 replay buffer。Caliburn 不需要重播每個「正在整理」短暫事件，因為恢復依據是 LangGraph checkpoint 的最新 operation snapshot；waiting／completed／failed 都必須 durable，遺失中間 progress animation 不影響業務事實。[WHATWG EventSource](https://html.spec.whatwg.org/multipage/server-sent-events.html)、[MDN SSE](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)

#### 9.9.4 可丟棄探針與結果

探針先寫測試並看過預期紅燈，再補最小實作；最後以 Python warnings 當 error 執行，共 6 項通過：

1. UI 關閉 async stream 不會取消 background operation；另一個 transport instance 只靠同一 durable store 就能 hydrate completed snapshot；
2. operation ID＋payload hash 冪等，不同 payload 無法借同一 ID 覆蓋；
3. interrupt response 必須同時符合 document scope、interrupt ID 與最新 operation revision；
4. 模擬 server restart 後，新 transport 會把 durable interrupt 交給 thin graph-resume port；真正 LangGraph `Command(resume)` 的 restart 行為已由 §9.7 驗證；
5. wire allowlist 只含 operation ID／status／phase／revision／typed input／verified visible message，不含員工原文、input hash、Skill、tool、reasoning 或 Current JD；
6. background document revision 到達時，dirty editor 保留 local draft 並標記 clean 後 refetch；clean editor 才立即前進 revision。

重跑命令：

```powershell
$env:PYTHONUTF8='1'
$env:UV_CACHE_DIR='S:\caliburn\.uv-cache-langgraph-spike'
uv run --offline pytest tests/test_frontend_transport_spike.py -q -W error -p no:cacheprovider
```

探針沒有建立 HTTP route，也沒有把 in-memory store 宣稱為 production persistence；它只證明 product transport semantics。正式實作必須直接讀 LangGraph state／interrupt，用 FastAPI 新版 SSE 做 wire，不能照抄探針造新的 operation authority。

#### 9.9.5 UI、失敗與切換規則

- 員工送出後先看到「已保存」，不是把一個長 HTTP request 當資料是否存在的唯一證據；provider 失敗時原話仍可重試。
- 瀏覽器關頁、換頁或 SSE 暫斷不取消 graph；員工明確按「停止本次分析」才是 cancel command。LangGraph JS SDK 1.9.8 已把 `stop()` 與 `disconnect()` 分開，支持這個區分，但本產品以自己的 typed command 表達，不引入整套 SDK。[SDK changelog](https://github.com/langchain-ai/langgraphjs/blob/main/libs/sdk/CHANGELOG.md)
- background revision 不直接 `setQueryData` 覆寫整份 DocumentView。若任一 editor dirty，只顯示「背景有新版本，儲存／放棄後更新」；save 本身需 expected revision，stale 時讓員工選擇重載或重新套用，不偷偷 merge。
- client conversation history、Current JD、interrupt payload、operation ID 與 `Last-Event-ID` 都是不可信 transport input；server 只以 document scope 下的 Store／checkpoint 重建 context。
- 第一版不做 token-by-token consultant answer。這避免未通過 schema／quote／authority verifier 的半句話先成為員工可見事實，也讓 retry 不必處理半段訊息。

未來同時出現下列任一類需求時，重新評估 **Agent Server＋`@langchain/react` 整體替換**，而不是在產品 SSE 上逐項仿造：多 worker／remote deployment、多人或多 client 同看一個 thread、需要 exact event replay、token／tool／multimodal streaming、server queue／double-text策略、time-travel／branch UI。單純「想少寫幾行 hook」不構成切換理由。

### 9.10 目標架構 v0.9（已撤回：同目的替代尚未完成，勿據此施工）

> **撤回註記（2026-08-13）**：本節雖選用了成熟 persistence／runtime／transport，卻又以 Work Model、Focus／agenda、Progress、Proposal、Current JD 與 operation 等現行概念切割 `DocumentState`，只證明能儲存這些欄位，沒有完成 §0.2 要求的同目的整體替代。下文保留為錯誤如何形成的研究紀錄，不是候選目標架構、ADR 輸入或實作授權。後續須回到 §9.5，逐目的重驗 memory／temporal state、planning／todo、progress、HITL／approval、approved artifact 與 durable run 等成熟元件後，另寫新版本取代本節。

#### 9.10.1 架構裁決摘要

三個 conformance slice 合併後，推薦組合是：

- **LangChain 1.x＋LangGraph 1.x**：主顧問 bounded loop、typed State／reducers、checkpoint／resume、interrupt、Store、middleware、structured output 與 tool limits；
- **`AsyncPostgresStore`**：每份文件的 immutable Source／更正與必要的大型 immutable artifact，按 namespace 隔離；
- **`AsyncPostgresSaver`**：Work Model、Focus／agenda、Progress／gap ledger、Proposal、Current JD、可見顧問回合與 operation status 的唯一 DocumentState；
- **LangChain OpenRouter＋Deep Agents `SkillsMiddleware`**：model／provider profile、按需 Task／Duty／O／P／K／S Skill；不採完整 `create_deep_agent`、subagent、shell、write-file 或自由 todo；
- **FastAPI 0.141.1 升級候選＋原生 typed SSE**：product command／view／operation stream；正式 pin 以前先跑完整 API 相容 gate；
- **Next／React＋TanStack Query＋現有 generated contract**：固定顧問工作區、durable view cache、local draft、dirty protection、Proposal／JD 操作；第一版不增加 `@langchain/react`、AG-UI 或 A2UI；
- **PostgreSQL 仍是唯一預設基礎服務**：不新增 Redis、Agent Server container、LangSmith license dependency 或另一個 graph database。

這不是「LangGraph 在外面包現行 Job Analysis」。AI 顧問子系統會受限 Big-bang：現行 Work Model／Focus／Proposal persistence、durable-turn orchestration、provider wire、Context packet、Task／OPKS 固定 prompt 與 consultation transport 都退出。保留的是經研究驗證的職務分析語意、來源／更正、員工 authority、deterministic verifier、generated contract 與匯出行為，不是舊 class／table／module 拓撲。

#### 9.10.2 每項事實的唯一 owner

| 事實 | 唯一可寫 owner | 其他層只能做什麼 |
|---|---|---|
| document catalog／title／tombstone／thread pointer | 現有 PostgreSQL catalog（可重寫 schema） | Web list、API route 與 cleanup workflow 讀取；不得反向寫 DocumentState 內容 |
| 員工原話、明確更正、Reference receipt／quote anchor | `AsyncPostgresStore` document namespace | DocumentState 只存 Source ID／lineage／選用結果；Context 按需取回，不複製整份 journal |
| Work Model、Focus／agenda、coverage／depth／decision／gap ledger | `AsyncPostgresSaver` 的 typed `DocumentState` | Web 看 generated projection；LLM 只能產候選，deterministic node 套用 |
| Proposal | 同一 `DocumentState` 的 typed changeset channel | UI 可審核；non-blocking Proposal 不依賴 process memory 或暫時 stream |
| Current JD | 同一 `DocumentState` 的 authority channel | 只有 direct-edit 或 employee decision node 可更新；AI node 永遠無 write edge |
| current operation／phase／pending interrupt／visible result | 同一 `DocumentState` 的 operation channels | FastAPI SSE 只投影；transport spike 的 operation store 不進 production |
| read projection／SSE／TanStack cache／editor draft | 非權威、可重建或 local-only | 不得在 background event 中覆寫 dirty draft，也不得被模型當 Source |

Store 與 Saver 同時存在不是重疊，因為它們不寫同一事實；若 implementation 又建立 `job_analysis_*` 舊表保存另一份 Work Model／Proposal／Current JD，就違反本架構。大型 append-heavy channel（visible conversation、operation receipt）仍須在 plan 中加容量 canary；若也出現 §9.7 的平方成長，應個別移到 Store reference 或經 migration/restart 實測的 delta channel，不因此重建完整 relational mirror。

#### 9.10.3 一個員工回合的實際資料流

1. API 驗 document scope、idempotency key 與 payload hash；Source 先寫 Store `pending`，DocumentState 建立 accepted operation，才回 202。
2. per-document run admission 只允許一個會改 DocumentState 的 graph run；本機單 process 先以薄 lock＋durable active-operation reconciliation 實作，不在 provider call 期間持有資料庫 transaction。
3. graph 讀最新 DocumentState 與有效 Source／更正，先更新可修訂 Work Model，再由 deterministic policy 選本輪 Focus／gap；旁支被保存但不搶走當前焦點，除非員工改道或它構成 blocking contradiction。
4. Context middleware 只帶最近自然對話、當前 Focus、必要 Work Model／Progress／Current JD、有效更正與少量高價值 Source；其餘原話與 Reference 由 allowlisted read-only tool 按需取回，每輪保存 `ContextManifest`。
5. deterministic eligible set 只暴露本輪可能需要的 Task／Duty／O／P／K／S Skill metadata；短且幾乎必用的 Skill 可預載，其他由 `SkillsMiddleware` 按需讀全文。模型最多快速路徑＋兩波唯讀補查，call limit 硬停。
6. model 回傳 typed `ConsultantTurn`／finding／changeset；schema 只保證形狀，domain verifier 另驗 Source、quote anchor、identity、dependency、authority、read-set 與 Skill／ContextManifest eligibility。
7. 通過後，一個 semantic checkpoint 原子更新 Work Model、Focus／Progress、Proposal、可見顧問回合與 operation completed；AI 路徑不改 Current JD。失敗則 operation failed，Source 保留。
8. FastAPI SSE 投影 durable operation snapshot；Web refetch verified consultation／document projection。若 editor dirty，只記錄 server 有新 revision，等待員工儲存／放棄後再更新。
9. 員工日後接受、修改、拒絕、退回或延後 Proposal，是新的 typed graph command；重新驗 stale／read-set 後才由 authority node 改 Current JD。可繼續訪談，不必先清空 Proposal。

#### 9.10.4 Focus、Progress、記憶與 Context 沒有偏掉

- **Focus** 仍是「現在深入哪個 work unit、為何、完成條件與返回點」，不是 agent 自由 todo。成熟替代機制是 LangGraph typed state／reducer／checkpoint；選焦點、旁支是否升級與何時返回仍是 Caliburn 專業 policy。
- **Progress** 仍呈現 coverage、depth、decision 與具體 gap，例如「這個 Task 的 P 已清楚，O 的時間／品質標準仍缺」；不顯示 graph node 數、tool-call 數或虛構百分比。
- **記憶** 是能找回員工先前原話與最新有效更正，不是多 speaker profile。Store 保存完整 Source，State 保存目前理解與 lineage；模型每輪不必重吃完整歷史。
- **Context** 是 application 在每個 model call 依 Focus／gap 組成的最小充分 context；framework middleware 管生命週期、summary／tool exposure 與 token limit，Caliburn policy 決定哪些事實有資格進入。
- **Task／Duty／OPKS** 不是先後固定階段。它們是同一顧問回合可組合的按需 Skills；Task 尚未「穩定」也可在證據需要時分析 O／P／K／S，Duty 也可隨訪談重命名、merge／split／reassign，但每個正式變更都要 employee proposal decision。

#### 9.10.5 反方審查

| 反方問題 | 審查結果 |
|---|---|
| 沒用 `@langchain/react` 是否又回到全自寫？ | 否。LangGraph、FastAPI、EventSource、TanStack Query 與 generated contract 已分別接手 durability、SSE wire、reconnect、server cache 與型別。自寫只剩產品 event enum、command validation 與 dirty policy；完整 Agent Protocol 的未用能力不應算「省碼」 |
| product SSE 沒有 exact replay，斷線會不會遺失進度？ | 中間 animation 可能不重播，但 accepted／waiting／completed／failed 是 durable snapshot；業務狀態不遺失。若未來要求逐 token／逐 tool exact replay，switch trigger 直接重評 Agent Server |
| 單 process lock 是否不夠「大廠」？ | 對目前明確限定的本機單一操作者／單 API process 足夠，並有 durable active-operation／restart reconciliation。不能為不存在的多 worker 需求預先引入 Redis queue；部署邊界改變時再升級 |
| 把 Current JD 放 checkpoint 是否不利 CRUD／export？ | §9.7 已用 direct edit、query、export、stale、delete 與 schema evolution fixture 實測可行；API projection／XLSX mapper 可直接讀最新 state，不需要第二份可寫 JD |
| Store Source 與 State Work Model 是否會失去 transaction 原子性？ | Source-first 本來就是兩階段：原話先 durable，分析 semantic state 後成立；pending Source reconciliation 已實測兩個 crash window。它不是同一事實雙寫，失敗時寧可保留未處理原話，不可遺失原話 |
| 不先做正式 eval 是否無法保證效果？ | 是，不能宣稱模型品質已證明；但 owner 已裁示先完成產品。第一版仍保留 deterministic fixture、schema／authority／restart／usage trace，成品完成後才做長訪談 eval，不以此為由刪掉可觀測性 |
| 會不會被舊系統帶偏成只換 adapter？ | 目標架構明確要求 AI 顧問子系統舊 writer／orchestrator／wire 退出；計畫必須有逐 module／table／concept 刪除帳本。若新 runtime 只是呼叫舊 consultation engine，直接判定不合格 |

這輪回看 §1–§8 與 Task／Duty／OPKS 研究，沒有改變產品角色、流程或員工 authority：仍是一位專業顧問，先建立可修訂工作全貌，再以清楚 Focus 深訪；旁支保存、原話可找回；Task／Duty／OPKS 按需組合；AI 只能提出 typed Proposal；員工知道目前焦點、進度、gap 與下一步。框架決策只替換工程機制。

#### 9.10.6 當時規劃的下一關（已失效）

下列內容是 v0.9 當時預定的下一步，已隨本節撤回而失效；目前不得開 ADR、刪除帳本或實作 plan，必須先完成 §0.2 所述目的層直接替代稽核：

1. 開 successor ADR，記錄 LangChain／LangGraph-first、Store／Saver 唯一 owner、FastAPI product SSE、不採 Agent Server 與 Pydantic fallback trigger；
2. 建逐 module／table／concept 的 `Replace／Delete／Retain` 帳本，特別防止舊 Work Model／Proposal／Current JD writer 殘留；
3. 寫受限 Big-bang implementation plan，第一個 task 先做 FastAPI 0.141.1 候選升級與完整 API/SSE gate，失敗才評估原生 `StreamingResponse` 或相容版本，不先加 `sse-starlette`；
4. 在新的隔離 worktree 施工，一個 task 一個 commit；完成前不 merge／push，不把可丟棄 spike 搬進 production；
5. 產品端到端完成後另開正式 eval plan；本次施工只做 deterministic conformance、人工情境 smoke 與完整現有 gate。

### 9.11 既有研究覆蓋稽核 v1.1：效果優先，只補真正未研究處（2026-08-13）

本節回應 owner 的兩次校正：§9.3–§9.9 已做過廣泛官方資料研究與 25 項工程探針，不能再從頭比較所有框架；同時，框架選型不能把「少寫程式」當主要目的。這次先把需求改寫成**中立產品目的**，再標示「官方資料已覆蓋／已有 conformance／仍只有推論」。現行名詞只供研究歷史追溯，不是新架構必須保留、包裝或相容的元件、schema 或生命週期。

#### 9.11.1 選型與驗證的優先順序（2026-08-13 owner 已確認）

框架候選依下列順序判斷；前一層不合格，不能靠後一層補分：

1. **產品效果與專業方法忠實度**：能否支撐本文確認的顧問流程、Task／Duty／O／P／K／S 按需分析、動態重整、來源與更正，以及可靠的職務說明書，而不是只提供名稱相似的 state／todo／approval。
2. **功能完整性**：能否完整承接目前焦點、可見待處理問題、必要澄清、文件變更審核、核准成品、恢復與匯出；不得因框架缺功能而縮小產品。
3. **正確性、authority 與可靠性**：AI 不偷改核准文件，員工原話不遺失，衝突／stale／崩潰可安全處理，每項事實只有一個可寫 owner。
4. **員工體驗**：員工能分辨現在在訪談什麼、哪些只是待處理 Gap、哪些必須先回答、哪些是待審文件變更，且關頁後能恢復。
5. **成熟度、版本穩定、操作與成本**：最新 stable／LTS、官方 persistence／failure semantics、本機安裝、資料服務與升級成本。
6. **自寫量與可維護性**：只有前五項效果相當時，才比較能刪除多少舊機制、還需多少 glue 與長期維護。淨刪碼可證明框架真的接手通用機制，但不是犧牲效果的主要目標。

本輪 conformance 仍不是正式模型品質 eval；它先驗證框架是否**有能力忠實實現產品效果**。長訪談回答品質、分析正確率與最終成品效果仍依 owner 裁示在產品完成後評測，不能因此把本輪退化成 LOC 競賽。

#### 9.11.2 三種人機互動不得混成同一個 HITL

1. **可審核的文件變更**：凡是 LLM 產生、準備寫入核准職務文件的 Task、Duty、O、P、K、S、名稱、分組、排序或文字，都先成為可檢查的 patch／changeset。員工可接受、修改後接受、拒絕或暫不處理；只有接受或修改後接受的部分才真正進入文件。它通常不阻塞訪談，可同時保留多筆待審。這個產品目的不要求物件名稱叫 `Proposal`，也不要求沿用現行 proposal class／table／API。
2. **必要的結構化澄清**：當來源互相衝突、責任邊界重大不明、缺少只有員工能決定的事實，或繼續推論會把後續分析建立在不安全前提上時，顧問必須像 Claude 的結構化提問卡一樣，說明問題、目前理解、衝突與可選回答，先取得員工回覆再繼續受影響的分析。這是 clarification／decision request，不是文件變更審核；回答成為新的員工來源，也不等於接受任何文件文字。只阻塞依賴該答案的分支；若沒有其他安全焦點，整個顧問回合才等待。
3. **可見的待處理問題與 Gap**：尚未深入的 Task、OPKS 缺口、旁支、新線索、可延後的問題與尚未分類事項，要形成 durable、可排序、可返回的待處理集合。它們不自動跳成 modal、不等於待審文件變更，也不阻塞目前焦點；員工可看見「還有什麼沒有分析、為何重要、之後可處理什麼」。目前焦點從這個集合與新證據中動態選出，而不是依固定 wizard 前進。

AI 可在內部持續形成、修正或撤回暫時理解，不需要員工逐筆核准；但這層永遠不是核准文件。若理解更新導致正式文件應修改，仍須產生第一類可審核變更。框架可以用完全不同的 primitive 承接三種目的，但若一個 interrupt／approval API 只能完成其中一種，就不能宣稱三者已全部替代。

#### 9.11.3 覆蓋表

| 中立產品目的 | 既有研究與證據 | 目前狀態 | 唯一還要補的工作 |
|---|---|---|---|
| 可換模型／provider／參數，限制 tool loop，取得 structured output、usage 與錯誤 | §4.8、§8、§9.5；LangChain／OpenRouter bounded run 已由 §9.8 五項探針驗證 | **已研究、已實測；關閉廣泛選型** | production pin 與 provider canary 留到實作，不再做框架市場調查 |
| 按當輪需要載入 Task／Duty／O／P／K／S 方法 | §4.7、§9.5；Agent Skills／`SkillsMiddleware` 的 eligible set、progressive disclosure 與 durable replay 已由 §9.8 驗證 | **已研究、已實測** | 只需把已驗證分析方法拆成正式 Skills；不再研究另一套 prompt framework |
| 每次模型呼叫取得最小充分 context，能找回早先原話與更正但不重送整段歷史 | §4.9–§4.13、§9.5；Store＋state 組裝、token budget、按需 lookup 已由 §9.7–§9.8 驗證 | **已研究、工程路徑已實測** | 成品完成後再用長訪談 eval 驗品質；目前不重開 Context Engine 選型 |
| 執行可 durable、restart、冪等、stream／reconnect，頁面離開不遺失工作 | §9.4–§9.9；LangGraph checkpoint／Store、FastAPI typed SSE、`EventSource`、dirty-editor policy 已有 20 項探針 | **已研究、已實測** | production lifecycle／migration／多 process trigger 留到實作；不再比較一般 agent runtime |
| 動態決定現在深入什麼、保存旁支、延後返回、更正後重開；同時維持可見待處理集合與可信 coverage／depth／decision／gap | §2–§3、§5–§7 定義產品語意；§9.5 已研究 Pydantic Planning、LangChain Todo、Microsoft Harness todo、Rasa stack；§9.12 已驗 LangGraph typed state／checkpoint | **已研究、最小產品語意已實測** | production 實作 work-unit eligibility、gap reason 與語意進度 projection；不得把 plan item／tool call 計數當產品進度 |
| 持續形成、修正與撤回對工作事實的理解，保留穩定 identity、來源 lineage、correction 與選擇性失效 | §2、§4.10、§9.5 已比較 SQLAlchemy、`eventsourcing`、Graphiti、LangGraph／LangMem；§9.7 與 §9.12 已驗 LangGraph state／Source、選擇性失效與 quote 保留 | **已研究、最小產品語意已實測** | production Skill 輸出明確 source dependency；長訪談 retrieval 品質留到成品後 eval |
| LLM 產生的文件內容先供員工接受、修改、拒絕或延後；多筆待審可與訪談並行；接受時原子更新核准成品 | §2.4、§3.7、§4.5、§9.5 已研究 Pydantic deferred tools、LangChain HITL／interrupt、Microsoft workflow HITL、AG-UI；§9.7、§9.9、§9.12 已驗生命週期與 transport | **已研究；多待審、任意順序、edit／defer／stale 已實測** | production 定義 typed operation／path read-set 與 deterministic verifier；不沿用舊 Proposal／Current JD 元件 |
| 發現重大衝突或安全推論缺口時，以結構化問題取得員工答案後再續跑 | §3.3、§3.7.1、§3.7.2 已定義 branch-blocking 規則；§9.12 已驗 LangGraph interrupt／resume | **已研究；typed card、answer-as-source、重建後恢復已實測** | production 定義必問門檻與 affected-branch eligibility；不得把答案誤當文件接受 |
| Reference／RAG 補 coverage、術語與挑戰，但不創造員工事實 | §4.11–§4.12、§9.5 已研究 LlamaIndex、Haystack、Qdrant 與既有 bounded context | **產品方向已研究；2026-08-14 owner 改為本次不做** | 維持 ADR 0057 隔離；不進 ADR 0060／目前 plan，日後另行討論與開 successor ADR |
| 模型回答品質與長訪談效果 | §7、§8 已定義之後要觀察的結果 | **owner 明確延後** | 成品完成後另開 eval plan；本輪不得偷做大型評測拖慢產品 |

所以不是「還要研究全部元件」。現在只補四個產品目的切片，其餘進入實作時的版本 pin／canary，不再消耗討論時間。

#### 9.11.4 只新增的版本與能力差異

1. **Pydantic Planning 的既有結論已被 0.13.0 推翻。** 本機以暫時環境實際安裝官方 0.13.0 後，公開模組只有 `Planning／PlanningToolset／PlanItem／TaskStatus`；`PlanItem` 只有 `content／status`，`Planning.for_run()` 每次建立隔離狀態，plan 只作 model-owned ephemeral reminder，不再提供先前研究到的 stable item ID、dependency／blocked、subtask 或 durable PlanStore。它仍可協助單一 run 的短期模型規劃，但不能直接承接跨回合訪談焦點、待處理 Gap、返回與可信進度，因此從這個目的的正式候選淘汰；不為保留舊結論而鎖舊版。[Pydantic AI Harness 0.13.0 release](https://github.com/pydantic/pydantic-ai-harness/releases/tag/v0.13.0)、[0.13.0 Planning source](https://github.com/pydantic/pydantic-ai-harness/blob/v0.13.0/pydantic_ai_harness/planning/_capability.py)
2. **LangChain Todo 不能因同一家族就視為等價替代。** 目前 `Todo` 主要只有 `content` 與 `pending`／`in_progress`／`completed` status，`write_todos` 是整份 list replacement；它適合讓 agent 分解短期任務與顯示進度，但沒有 product-stable ID、dependency、blocked、cancelled、defer／return reason 或 correction-reopen 語意。若用 LangGraph-first，這些仍要在 typed state 中建模；若它不能忠實承接產品效果，就不能只因整合較方便或少寫程式而勝出。[LangChain Todo schema](https://reference.langchain.com/python/langchain/agents/middleware/todo/Todo)、[Todo middleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
3. **一般 HITL 都偏向暫停目前 run，不能同時代表三種互動。** LangChain HITL、Pydantic deferred tools 與 Microsoft Workflow request／response 都能 durable 暫停、編輯或回應外部 request；Microsoft checkpoint 也會保存 pending requests。它們適合必要澄清或立即工具核准，卻不自動等於可延後、多筆並存的文件 patch review，也不等於待處理 Gap。產品應依目的選 primitive，不要求三者共享同一名稱或 storage shape。[LangChain HITL](https://docs.langchain.com/oss/python/langchain/human-in-the-loop)、[Pydantic deferred tools](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)、[Microsoft Agent Framework HITL](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
4. **成熟 durable workflow 可承接生命週期，但不會自動提供職務分析語意。** DBOS 已有 persisted workflow message queue、topic、idempotency key、workflow event 與 background workflow；Camunda User Task 更有完整 lifecycle、pause／resume／approve／reject action 與 audit，但對本機單一操作者新增獨立流程平台可能過重。兩者作機制 benchmark；先看能否完整實現員工互動與 authority，再看是否減少維護，不以刪碼數先淘汰功能較完整者。[DBOS workflow communication](https://docs.dbos.dev/python/tutorials/workflow-communication)、[Camunda user-task lifecycle](https://docs.camunda.io/docs/apis-tools/frontend-development/task-applications/user-task-lifecycle/)
5. **`eventsourcing` 候選版本已校正。** 截至 2026-08-13，PyPI 最新 stable 是 9.5.4；9.6.0b1 與 10.0.0a* 是 pre-release。官方 stable 文件顯示 9.5.5 的差異要視為文件／發行漂移，探針只鎖實際可安裝的 9.5.4。[PyPI release history](https://pypi.org/project/eventsourcing/)

#### 9.11.5 接下來只做四個目的切片

1. **動態訪談控制＋可見待處理議程＋可信進度**：三個動態工作單位，插入旁支、切換、employee defer、返回、dependency、完成後因更正 reopen；另保存多個不阻塞的 Gap，讓員工看見尚未分析什麼。Pydantic Planning 0.13.0 已因缺 stable identity、dependency 與跨 run persistence 淘汰；最小 probe 先驗 LangGraph typed state／reducers／checkpoint 能否完整承接。只有出現產品效果硬缺口，才針對該缺口加入 Microsoft Harness 或專門 workflow／planning 候選。先驗功能效果、恢復與可理解進度；只有效果相當才比較 glue。
2. **可修正理解＋來源**：一句早期原話形成 Task／Duty／OPKS 關係，後續更正只使受影響推論失效，未受影響部分與 exact quote anchor 保留；同時驗查詢、stale、restart 與 delete。只比較已列候選：LangGraph Store／state 路徑、SQLAlchemy 基線、`eventsourcing` 9.5.4；只有這三者都無法合理承接 temporal fact retrieval 時才加入 Graphiti，不再廣搜 memory framework。
3. **可審核文件變更＋核准成品**：一份 patch／changeset 橫跨 Duty／Task／OPKS，員工可 edit、defer、繼續訪談、再產生第二份待審，日後任意順序 accept／reject；accept 前重驗 read-set／stale，核准成品一次原子改變，直接編輯、查詢與匯出仍一致。候選可以使用 framework approval、durable state、user-task 或 message primitive，但新設計不需要出現 `Proposal`／`Current JD` 等舊元件名稱。
4. **必要結構化澄清**：製造一個員工說法衝突與一個重大責任邊界不明情境；框架必須保存 typed question、原因、選項與 affected branch，先暫停受影響推論，重啟後仍能等待；員工回答成為新來源後才恢復，且絕不被誤記為接受文件 patch。比較 LangGraph interrupt、Pydantic deferred／AG-UI 與 Microsoft RequestPort 等已研究 primitive，不再廣搜一般表單框架。

四個切片都必須交付同一份帳本：`產品目的與情境 → 效果／功能驗收 → 採用的成熟元件 → 仍需的最薄職務分析／authority policy → failure modes → 新增依賴與操作成本 → 可刪的舊機制`。可刪項放最後；通過後的新架構以產品目的與勝出的框架 primitive 命名，舊元件、舊名稱、舊 schema 與相容 adapter 原則上全部退出。只有框架無法完成且已由 conformance 證明的產品差額，才允許自寫。

#### 9.11.6 北極星複核

本次校正後沒有偏離產品大方向：員工仍面對一位專業職務分析顧問；先建立可修訂的工作全貌，再以清楚焦點深入訪談；旁支與 Gap 被記住但不任意搶焦；Task／Duty／O／P／K／S 是按需組合方法。AI 內部理解可以隨證據修正，但 LLM 產生、準備進入正式文件的內容都必須讓員工接受、修改或拒絕；重大衝突則以另一條結構化澄清互動先問員工，不能偷猜；進度顯示尚未分析、待處理、待審與受阻原因。框架的任務是以成熟能力忠實完成這些效果，省碼與維護收益只在效果相當後比較。

### 9.12 最小目的驗證結果與停止研究決定（2026-08-13）

依 owner 要求，本輪沒有做真實模型品質 eval、效能競賽或再跑市場調查。使用 LangGraph 1.2.11、`StateGraph`、typed state、`InMemorySaver` 與 `interrupt()/Command(resume=...)`，以固定採購訪談情境執行四個 deterministic tests；結果為 `4 passed in 1.21s`。既有 PostgreSQL Saver／Store probe 已於同一工作階段先重跑 `14 passed in 96.06s`，因此新 probe 未修改共用程式後不再重跑昂貴持久化套件。驗證程式是可丟棄證據，不得直接搬進 production：[`consultant_purpose_conformance_spike.py`](../../apps/api/consultant_purpose_conformance_spike.py)、[`test_consultant_purpose_conformance_spike.py`](../../apps/api/tests/test_consultant_purpose_conformance_spike.py)。

| 產品目的 | 採用的成熟 primitive | 實際觀察到的效果 | production 仍需的最薄產品政策 | 機制硬缺口 |
|---|---|---|---|---|
| 動態訪談、旁支、延後返回、更正重開、可見 Gap | LangGraph typed state、graph transition、checkpoint | 旁支不搶目前焦點；defer 後可返回；完成單位可因更正 reopen；Gap 持續可見，且沒有假百分比 | work-unit eligibility、優先理由、coverage／depth／decision／gap projection | 無 |
| 可修正理解與來源記憶 | checkpointed state、穩定 source reference | 更正只 challenge 依賴舊來源的理解；無關理解、舊原話與 exact quote anchor 保留；受影響訪談單位重開 | Skill 必須輸出 source dependency；來源可信度與 deterministic verifier | 無；語意檢索品質留待成品後 eval |
| LLM 文件變更由員工審核 | checkpointed review queue、typed patch action、graph transition | 多筆 patch 可並存；defer 不阻塞訪談；可任意順序 accept；可 edit-accept；同一路徑被直接改過時會 stale；只有接受內容改變核准成品 | change contract、path read-set、原子 authority 驗證與 UI | 無 |
| 必要結構化澄清 | LangGraph `interrupt`／`Command(resume)`／checkpoint | 卡片保留原因、選項與 affected branch；同一 Saver 重建 graph 後可續答；答案成為員工 evidence，沒有變成文件接受 | 何時必問、哪些分支可繼續、答案如何觸發重新分析 | 無 |

這個結果只證明**框架機制能忠實承接產品語意**，不證明 LLM 已能做好職務分析，也不代表 probe 的欄位就是 production schema。每列仍需的政策是 Caliburn 的專業方法或 authority invariant，不是把舊 Work Model、Focus、Progress、Proposal、Current JD class／table／生命週期改名後保留。

#### 9.12.1 選型收斂

1. **主 runtime 收斂為 LangChain 1.x＋LangGraph 1.2.x family。** LangChain 承接 provider、tool loop、structured output、Skills／middleware 與最小 context 組裝；LangGraph 承接可恢復流程、動態訪談狀態、來源依賴、待審文件變更、必要澄清與核准 artifact 的單一 durable owner。正式版本在施工 ADR pin 到當時 stable patch。
2. **不再為這四個目的加入 DBOS、Camunda、Microsoft Agent Framework 或另一套 memory／planning framework。** 四個效果皆通過，依 §9.11.5 stop rule，不以「可能功能更多」再堆第二個 workflow owner。若 production 才發現明確硬缺口，只針對該缺口重開候選，不翻掉已通過部分。
3. **Pydantic AI Harness Planning 0.13.0 不進主路徑。** 它可作單次 run 的短期提醒，但實際 API 不具本產品跨回合訪談所需的 identity、dependency、blocked／defer／reopen 與 durable store。這是版本實查結果，不是偏好。
4. **停止 spike，進入產品升級。** successor [ADR 0060](../adr/0060-langchain-langgraph-consultant-runtime-and-durable-authority.md) 與[受限 Big-bang implementation plan](../plans/2026-08-13-langgraph-consultant-runtime-big-bang-plan.md) 已依本文產品目的起草；owner 明確核准 ADR 後，在新 worktree 建第一條「員工回答 → 動態分析／按需 Skills → 可見焦點與 Gap → 文件 patch 審核／必要澄清 → 核准 artifact」production vertical slice。不移植 spike，也不加舊元件 compatibility layer。

本節機制判斷依據為 LangGraph 官方的 [Graph API](https://docs.langchain.com/oss/python/langgraph/graph-api)、[Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)、[Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts) 與 [Durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)；版本淘汰依據仍是 [Pydantic AI Harness 0.13.0 release](https://github.com/pydantic/pydantic-ai-harness/releases/tag/v0.13.0) 與 [0.13.0 Planning source](https://github.com/pydantic/pydantic-ai-harness/blob/v0.13.0/pydantic_ai_harness/planning/_capability.py)。

### 9.13 2026-08-14 owner 校正：自然續談、框架命名、LLM 範圍與 RAG

本輪重新對照 §1–§8、ADR 0060 草稿與施工計畫後，owner 明確修正／確認以下事項；這些是目前施工依據，若與較早段落的暫定說法衝突，以本節與已同步修正的產品方向段落為準：

1. **沒有「本輪可停」或「訪談結束」狀態。** LLM 回答後自然等待；員工想繼續就傳訊息，想休息就停止傳訊息或關頁，下次從 durable state 接著談。系統只顯示儲存／處理／失敗事實。
2. **「目前已足夠」只是可重新計算的顧問建議。** 它說明為何已足夠、仍缺什麼與繼續最可能改善什麼，不關閉對話。匯出檢查是另一項判斷；有缺口時仍可明確強制匯出。
3. **文件審核是一項目的，不是一個必須叫 Proposal 的舊元件。** 凡 LLM 生成且準備進入職務文件的內容，都先成為 framework-backed 待審 changeset；只有員工 accept／edit-accept 才改核准文件。員工直接編輯不需再審核自己的修改。
4. **第一版 LLM 分析範圍**包含職務名稱、工作描述、Duty、Task、重新分組、排序與 O／P／K／S。能力級別與 A 因尚未完成研究與 Skill，暫不交給 LLM；既有欄位、直接編輯與匯出不刪除。模型不得產生任何官方代碼；員工只可直接填 `職業別`／`行業別` 分類，iCAP 配發的 `職能基準代碼`／`職類別代碼` 維持空白且不可編輯。
5. **舊元件名稱不得成為 target architecture。** `Work Model`、`Focus`、`Progress`、`agenda`、`Proposal`、`Current JD` 等名稱只可用於歷史診斷與刪除帳本；LangGraph／LangChain 成熟 primitive 直接承接同目的機制，新 code／contract／plan 以產品目的與 framework primitive 命名。
6. **本次不做 RAG。** 現有 RAG bounded context 繼續依 ADR 0057 保留與隔離，不新增 current consumer 或完成 gate；日後另行研究、討論與決策。這取代 §2.15 舊版曾把 RAG 納入同一次 v1 cutover 的暫定結論。

因此 ADR 0060 與 implementation plan 在 owner 接受前必須同步包含：常駐「AI 目前理解」與觸發式校準、結構性未決變更只阻塞依賴分支、完整核心 Skills、受限全域索引 context、可編輯 review bundle、足夠性提示、模型 profile／resolved snapshot／attempt receipt、source-first 失敗恢復，以及無舊 writer／舊名稱 compatibility layer 的 hard cut。

### 9.14 施工前最終北極星與成熟元件覆蓋審核（2026-08-14）

Owner 要求施工前最後一次詳細確認：產品方向必須優先於舊系統；同目的的通用自寫機制應由成熟框架直接替換，只有框架確實不知道的職務分析／員工 authority 語意才可保留。完整逐項結果與日後每個 Task 的防偏紀錄統一寫在 [`2026-08-14-consultant-runtime-north-star-audit-ledger.md`](2026-08-14-consultant-runtime-north-star-audit-ledger.md)。結論為 **Pass**：

1. §1–§8 的一位顧問、前景專注／背景吸收、自然離開／續談、Task／Duty／OPKS 動態演化、文件先審後入、澄清／Gap／審核分流、可信進度、單一可強制匯出、source-first 失敗恢復與本輪不做 RAG，已全部在 ADR 0060／plan 有明確 behavior test 或 gate。
2. LangChain／LangGraph／Deep Agents／FastAPI／TanStack Query／Pydantic／PostgreSQL／OpenTelemetry 已承接 model binding、bounded loop、structured output、retry／limits、Skills、context lifecycle、Store／Saver、routing、interrupt、command、SSE、schema validation、transaction constraint 與 tracing；不再保留舊 Work Model／Focus／Progress／Proposal／Current JD 等通用生命週期。
3. 仍需自寫的只有 Task／Duty／OPKS 方法、工作單位 eligibility、來源／quote／lineage、changeset path read-set／atomic subgroup、Gap／sufficiency reason、文件 invariant、官方代碼與 export／dirty-draft policy。它們是 framework 無法通用推導的產品差額，不是舊元件 compatibility layer。
4. 計畫已補入 `ModelCallLimitMiddleware`／`ToolCallLimitMiddleware`／model/tool retry、LangChain `response_format`、只作用於非權威副本的 summarization／context editing、既有 OpenTelemetry、Postgres checkpointer security/setup、Beta integration canary，以及每個 Task commit 前的北極星回歸 gate。
5. 官方 PyPI 指定版本端點確認 LangChain 1.3.15、LangGraph 1.2.11、`langgraph-checkpoint-postgres` 3.1.2、`langchain-openrouter` 0.2.7、Deep Agents 0.7.5 與 FastAPI 0.141.1 均存在且未被 yank；先前一般搜尋頁未顯示最新版本，不能作降版依據。正式施工精確 pin 並以 lockfile／import canary 再驗。

Owner 已明確表示審核通過即可開始，故 ADR 0060 改為 Accepted。Big-bang 只代表最終硬切；每完成一個功能仍須回到帳本做產品效果與框架替代覆蓋審核。若實作中發現更好的方法，先討論並更新本研究／successor ADR，不能暗中改變北極星。

### 9.15 Task 10 真模型診斷後的 Opus 5／Evidence 回歸審核（歷史判斷；model-topology 結論由 §9.16 取代）

本輪重新從 §1–§8 的產品效果往下審核，而不是用目前程式替自己辯護。結論是：**產品北極星沒有偏移，但模型執行拓撲有一項已證實的 P1 機制偏差，Evidence 的成熟元件覆蓋也需要寫得更精確。**

#### 9.15.1 同一顧問不等於同一個巨大 provider request

Task 10 真模型診斷發現，production 仍把所有唯讀工具與完整 `ConsultantResult` strict schema 同時交給一個 `create_agent(response_format=...)`。目前 schema minified 後約 **10,317 bytes**，尚未計入 Skill／source tools；本 repo 2026-07-31 的 Opus 5 live smoke 已在 **6,818 bytes** strict schema 出現 `compiled grammar is too large`，而本輪真實路徑再次得到同類 provider request rejection。byte 數只作診斷，**不是通用上限**：同一 `ConsultantResult` 在不帶 read tools 的 provider-native structured-output 呼叫已成功；改用 LangChain ToolStrategy 則觀察到多個錯誤的輸出工具呼叫。這證明問題在 request 的 grammar／strategy 組合，不是單看 schema 大小，也不是 prompt 或職務分析品質問題：

1. **lookup／analysis** 需要 Skills、員工來源工具與自由但受限的專業推理；
2. **typed finalization** 需要完整 schema adherence，但不需要再看到工具定義。

修正後仍是一位顧問、一個 application run、一個模型 profile 與一個員工可見回覆：

```text
employee source
  -> tool-enabled lookup / analysis（最多 2 model calls、2 lookup waves）
  -> typed finalization without Skill / Source read tools（最多 1 structured-output call）
  -> deterministic verifier
  -> one semantic checkpoint
```

這不是加入 planner、scribe、critic 或多 Agent，也不讓 Skill 自行選模型。兩段共用同一份 context selection、source IDs、已讀 Skill IDs、run／attempt budget 與 lineage；finalization 只能把已取得的分析材料編成 typed result，不能偷偷再查資料。第一版 Opus 5 profile 明確使用已通過 live conformance 的 provider-native finalization，不讓 LangChain 自動改成 ToolStrategy；未來換模型／provider時，versioned profile 必須選擇自己已實測通過的 structured-output strategy，不能 silent fallback。若 context 與方法已由 deterministic path 充分載入，可直接走不帶 read tools 的 typed finalization 快速路徑。最多三次 inference 的原裁決不變。

Anthropic 的 Opus 5 官方指引支持的是**減少過時 scaffolding、明確控制輸出長度與 scope、以 effort 調整推理成本**，不是把所有 context／tools／schema 塞進一個 request。Opus 5 預設啟用 thinking，官方也警告舊式重複 verification 指令會造成過度驗證；因此 prompt 應刪除重複「再檢查一次」文字，真正不可省的 source／authority／document invariant 繼續由 deterministic verifier 負責。1M context 也不推翻 §7 的最小充分 context；Anthropic 的 context-engineering 指引仍主張 just-in-time retrieval。Mid-conversation tool changes 可在未來 direct-Claude adapter 保留 cache 時評估，但它是 beta 且目前主路徑是 OpenRouter，不列第一版必要條件。[Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) · [What's new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5) · [Mid-conversation system messages and tool changes](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages) · [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

#### 9.15.2 Evidence 沒有單一套件，但通用機制已有成熟 primitive

不再把 Evidence 當成一個必須保留或重建的舊巨型元件。依目的拆開後，正式對照如下：

| 中立目的 | 成熟 primitive／標準 | Caliburn 只保留的產品差額 |
|---|---|---|
| 員工逐字來源、更正與找回 | LangGraph `AsyncPostgresStore`＋checkpoint source refs | 哪些輸入可成為 employee evidence、document scope、supersession／correction policy |
| 模型回覆中的 citation transport | LangChain v1 `Citation` content annotation | 是否啟用、provider adapter conformance、如何映射回本機 source ID |
| 原始來源內的精確文字定位 | W3C Web Annotation `TextQuoteSelector`＋`TextPositionSelector` | Unicode／normalization policy、source revision hash、逐字與 speaker 驗證 |
| quotation／revision／invalidation lineage | W3C PROV 語彙 | 不要求 RDF；只借成熟關係語意並保持單一 Store／checkpoint authority |
| typed claim／引用形狀 | LangChain structured output＋Pydantic validators | Task／Duty／OPKS 語意支持、employee-only authority 與跨實體 invariant |
| provider／tool 執行證據 | LangChain callbacks＋OpenTelemetry GenAI conventions | 本機 correlation、payload-free receipt、route／usage／cost fail-closed policy |
| 員工文件裁決與恢復 | LangGraph checkpoint／`Command`／必要時 `interrupt` | 哪些變更需審、affected branch、read-set、stale 與 atomic subgroup |

兩項限制不可省略：

1. LangChain `Citation.start_index／end_index` 指向的是**模型回覆文字**，不是員工來源內的位置；所以它可取代 citation transport boilerplate，不能單獨取代 source quote anchor。Caliburn 的 employee source 是 immutable 且已有 `source_id + text_sha256`，核心 anchor 只需 W3C-aligned exact quote＋start/end；prefix／suffix 可留作未來跨格式 projection 的可選 re-anchoring 資訊，不應為形式對齊增加第一版狀態。[LangChain `Citation`](https://reference.langchain.com/python/langchain-core/messages/content/Citation)
2. Anthropic 原生 citations 比純 prompt 引用更可靠，但官方明確說它與 structured outputs **不能在同一 request 使用**。目前 pin 的 `langchain-openrouter 0.2.7` response converter 也沒有保存任意 citation annotations。因此第一版核心仍由 provider-neutral `source_id + W3C-aligned selector + Pydantic result + deterministic verifier` 承接；原生 citation 只能在 adapter conformance 通過後，作 lookup／analysis 段的選配能力，不能成為唯一 evidence truth，也不藉此提前接 RAG。[Anthropic Citations](https://platform.claude.com/docs/en/build-with-claude/citations) · [W3C Web Annotation](https://www.w3.org/TR/annotation-model/) · [W3C PROV-O](https://www.w3.org/TR/prov-o/)

#### 9.15.3 北極星裁決

- **不變**：一位專業顧問、前景專注／背景吸收、Task／Duty／OPKS 動態演化、員工原話可找回、文件先審後入、必要澄清／Gap／審核分流、自然離開／續談、可信語意進度、單一可強制匯出，以及 RAG／能力級別／A／正式 eval 延後。
- **當時的必修判斷（已由 §9.16 修正）**：曾判定必須把「工具＋完整 strict schema 同一 request」改成 tool-enabled analysis＋不帶 read tools 的 typed finalization；後續補回 compact-wire 既有證據後，兩段式已降為 exact canary 仍失敗時的 contingency。
- **成熟元件校正**：Evidence 的 persistence、citation transport、anchor shape、lineage vocabulary、typed validation、execution tracing 與 review durability 都由框架／標準承接；Caliburn 不重建 Evidence framework，只保留來源 authority 與職務分析支持規則。
- **不採**：為此新增第二模型人格、multi-agent、RAG、另一套 memory／evidence store、自由 JSON repair loop，或移除 deterministic verifier。

當時曾規劃以 successor ADR 0061 同時裁決 schema 與 Tool；§9.16 後續審核先把它退回 Proposed 並改採 compact wire 優先。owner 此後只核准 schema 範圍，故現行 ADR 0061 為 Accepted（schema-only），沒有授權任何 Tool／Skill loading 變更；ADR 0060 本體保持 Accepted 版本零差異。

### 9.16 strict schema、Skill／Tool 按需載入的更正審核（2026-08-14）

本節依 owner 要求再查官方限制、Opus 5 精簡方式與 repo 既有研究，**取代 §9.15.1、§9.15.3 對「預設拆成兩段 request」的機制結論**；§9.15.2 的 Evidence primitive 分工維持。這次不是重新討論產品大方向，而是發現前一輪漏看 2026-07-31 已完成的 compact-wire 研究與 live 證據。

#### 9.16.1 為什麼 schema 會超過

`10,317 bytes` 只是症狀，不是 Anthropic 的硬上限。對目前 `ConsultantResult.model_json_schema()` 的離線結構量測為：18 defs、68 object properties、**28 optional parameters、20 個 `anyOf`／union sites、最深約 15 層**。Anthropic Structured Outputs 官方目前明列：單一 request 內 JSON output 與 strict tools 合計最多 **24 optional、16 union parameters**，而且即使個別數字不超標，optional／union／巢狀／tools 的交互組合仍可能超過內部 compiled-grammar limit。故本次 output schema 在不計 tools 前已同時超過兩個公開維度；「tool-free 某 route 成功」不能推翻公開限制，最多只說明 route、轉換、cache 或 endpoint enforcement 可能不同。[Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)

repo 已有直接可重用的成功模式：2026-07-31 的 6,818-byte rich schema 也收到相同錯誤；改成 model-facing compact wire＋pure mapper，把 union 17→0、properties 54→32、nesting 9→6、wire 6,818→4,084 bytes 後，Opus 5 真 request HTTP 200，後續 Opus 5／Luna-Pro／Sonnet 5 三回合場景完成。這證明「保留 rich 產品能力，但換 provider contract 形狀」不是理論猜測。相關權威紀錄是 [`strict schema 研究`](2026-07-31-anthropic-strict-schema-grammar-limit-research.md)、[`model-facing contract 研究`](2026-07-31-context-engineering-model-facing-contract-research.md)、[`compact wire plan`](../plans/2026-07-31-task-analysis-compact-wire-contract-plan.md) 與 [`live smoke`](../experiments/2026-07-31-job-analysis-attributed-live-smoke/README.md)。

因此 Anthropic 官方建議的修正順序也應照做：先降低 optional、簡化 nesting／union，再考慮 split requests；不能因 tool-free 呼叫成功就直接把最後一招升格成預設架構。第一版修法改為：

1. rich application result 不直接送 provider；建立 compact provider wire，優先零 optional、零或極少 union、required fields＋明確中性值／空陣列；
2. pure mapper 遇到 discriminator／sentinel／payload 矛盾必須拒絕，不靜默補值；source／quote／authority／職務分析 invariant 繼續由 deterministic verifier 驗；
3. 先以 compact wire＋現有四個真工具保留單一 bounded agent loop；只有 exact live conformance 仍失敗，才拆 tool-enabled analysis＋tool-free finalization；
4. live canary 是付費外部動作，需另經 owner 授權。structured-output strategy 仍由 model profile 明選，不 silent fallback 到已觀察到錯誤多重輸出工具呼叫的 `ToolStrategy`。

#### 9.16.2 Skill 按需載入：目前機制大致正確，名稱需校正

Agent Skills／Deep Agents 的主流方式不是把所有 Skill 隱藏到模型無從發現，而是三層 progressive disclosure：短 name／description metadata 常駐、相關 `SKILL.md` instructions 被模型讀取時才進 context、額外 resources 再按需取。現行九個 Skill metadata 約 1.7 KB，完整正文合計約 16.6 KB；真正節省的是後者沒有全部常駐。這與官方 Agent Skills 與 Deep Agents 實作一致，不需再自寫 Skill router。[Agent Skills specification](https://agentskills.io/specification) · [Anthropic Agent Skills engineering](https://www.anthropic.com/engineering/equipping-agents-for-the-real-world-with-agent-skills) · [Deep Agents Skills](https://docs.langchain.com/oss/python/deepagents/skills)

但目前程式把九個 catalog entries 同時稱為 `selected` 與 allowed，容易讓人誤以為九份正文都載入。產品語意應校正為：

- `eligible`：本輪可被模型發現的短 metadata；第一版可包含九項，以免錯過員工回答中的跨焦點 Task／Duty／OPKS 線索；
- `loaded`：模型真的完整讀過 `SKILL.md`，由 backend receipt 記錄；只有 loaded Skill 才能被結果引用；
- 日後 metadata 若有可量測品質／成本問題，才依 typed state deterministic narrowing；不先加 keyword router 或另一個 LLM selector。

Opus 5 可借鑑的精簡不是刪除分析方法，而是把重複 scaffolding 移出 base prompt：角色／產品邊界／當輪目標常駐，Task／Duty／O／P／K／S 方法留在 Skills；移除模型已自帶或 verifier 已保證的重複「再驗證一次」指令；員工歷史與來源用 stable handles 即時取回。官方 1M context 仍強調 context 有限，應保留最小高訊號 context 與 just-in-time retrieval。[Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5) · [Effective context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)

#### 9.16.3 Tool 按需載入研究：候選方向，尚未裁決

現行只有 `read_file` 加三個 source lookup tools，全部定義約 2.9 KB；三個 source tools 合計約 1.0 KB，較大的單項是 framework 通用 `read_file` 約 1.2 KB description，描述了本產品沒有的 editing、PDF、paging 等。`FilesystemMiddleware` 已提供 `custom_tool_descriptions`，所以「縮成只描述完整讀取 eligible `/skills/<id>/SKILL.md`」是後續 Tool 討論的候選，不需要為此重寫工具 framework；本輪沒有核准或實作這項變更。

Anthropic Tool Search 官方建議在約 10 個以上工具、tool definitions 超過 10k tokens、選擇品質下降或多 MCP server 時使用；目前四個小工具不符合。`defer_loading` 也不解本次 strict schema 問題，因為 grammar 仍根據完整 deferred tool set 建立。研究上較合適的候選仍是 standard tool calling：definitions 小且穩定，**實際 tool call 與 tool result 才按需進 context**；只有 typed state 明確表示某工具不可能成功時，才考慮 LangChain 原生 dynamic tool filtering。Opus 5 mid-conversation tool changes 仍是 provider beta，OpenRouter／LangChain 端到端尚未驗證，不列核心依賴。以上只供下一輪 Tool 討論，不由 schema 決策自動生效。[Anthropic Tool Search](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-search-tool) · [LangChain dynamic tools](https://docs.langchain.com/oss/python/langchain/agents#dynamic-tools) · [Anthropic mid-conversation tool changes](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages)

現行 prompt 還把「第一波讀 Skill、第二波查 Source」寫死；研究上它不屬於產品需求，因為員工更正可能要先查 lineage，某些回答也可在同一波平行取得 Skill 與 source。是否保留兩波、如何排序與是否改為 typed availability，全部留待下一輪 Tool 討論；本輪維持現況。

#### 9.16.4 北極星與施工裁決

- **產品方向沒有偏**：一位顧問、前景焦點／背景吸收、動態 Task／Duty／OPKS、記得並可找回員工原話、LLM 文件內容先審後入、必要澄清／一般 Gap／文件審核分流、可信進度、自然離開／續談與單一可強制匯出皆不變。
- **修正的是 provider contract，不是刪產品能力**：rich result／framework state 可完整；只有送給模型的 wire 必須 compact，再映回產品結構。
- **Skill 已是按需正文**：保留成熟 middleware；把 selected／eligible／loaded 名詞與驗證分清。
- **Tool 尚未裁決**：本節保留 standard calling、縮 description、調整 wave 與 dynamic filtering 的研究證據，但 owner 已把 Tool／Skill loading 排除於 schema 本輪；工具集合、description 與排程維持現況，下一輪另議。
- **兩段式降為 contingency**：compact wire exact canary 仍失敗才啟用，不預先增加一次 inference 與 handoff。
- **決策狀態**：[ADR 0061](../adr/0061-compact-consultant-wire-progressive-skills-and-tools.md) 已由 owner 以 **schema-only** 範圍核准為 Accepted；compact provider wire 生效，Tool／Skill loading 沒有隨之獲得授權。ADR 0060 仍是 runtime 主決策。

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
- [Anthropic — Harness design for long-running application development](https://www.anthropic.com/engineering/harness-design-long-running-apps)
- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)
- [Anthropic — Trustworthy agents in practice（可自行研究的缺口與必須詢問使用者的意圖）](https://www.anthropic.com/research/trustworthy-agents)
- [Anthropic — Scaling Managed Agents: Decoupling the brain from the hands](https://www.anthropic.com/engineering/managed-agents)
- [Anthropic — How we contain Claude across our consumer products](https://www.anthropic.com/engineering/how-we-contain-claude)
- [Anthropic Docs — How tool use works](https://platform.claude.com/docs/en/agents-and-tools/tool-use/how-tool-use-works)
- [Anthropic Docs — Tool runner（自動 loop 與 custom HITL 邊界）](https://platform.claude.com/docs/en/agents-and-tools/tool-use/tool-runner)
- [Anthropic Docs — Managed Agents permission policies](https://platform.claude.com/docs/en/managed-agents/permission-policies)
- [Anthropic Docs — Structured outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)
- [Anthropic Docs — Prompting Claude Opus 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-opus-5)
- [Anthropic Docs — What's new in Claude Opus 5](https://platform.claude.com/docs/en/about-claude/models/whats-new-opus-5)
- [Anthropic Docs — Mid-conversation system messages and tool changes](https://platform.claude.com/docs/en/build-with-claude/mid-conversation-system-messages)
- [Anthropic Docs — Citations](https://platform.claude.com/docs/en/build-with-claude/citations)
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
- [LangGraph — Graph API（typed application state、reducer、node update）](https://docs.langchain.com/oss/python/langgraph/graph-api)
- [LangChain — Frameworks, runtimes, and harnesses](https://docs.langchain.com/oss/python/concepts/products)
- [LangChain／LangGraph — Release policy（LangChain semver、LangGraph 1.0 LTS）](https://docs.langchain.com/oss/python/release-policy)
- [LangGraph — Workflows and agents（predetermined workflow 與 dynamic loop）](https://docs.langchain.com/oss/python/langgraph/workflows-agents)
- [LangGraph — Persistence](https://docs.langchain.com/oss/python/langgraph/persistence)
- [LangGraph Reference — Checkpointing／AsyncPostgresSaver／serialization](https://reference.langchain.com/python/langgraph/checkpoints)
- [LangGraph — Functional API（determinism、idempotent side effects）](https://docs.langchain.com/oss/python/langgraph/functional-api)
- [LangGraph — Backward compatibility（latest code 對 persisted checkpoint 的責任）](https://docs.langchain.com/oss/python/langgraph/backward-compatibility)
- [LangGraph — Interrupts](https://docs.langchain.com/oss/python/langgraph/interrupts)
- [LangGraph — Time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)
- [LangGraph — Subgraph persistence／same-thread checkpoint conflicts](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)
- [LangGraph frontend — Human-in-the-loop](https://docs.langchain.com/oss/python/langchain/frontend/human-in-the-loop)
- [LangChain frontend — Overview（typed state、interrupt、checkpoint、`useStream`）](https://docs.langchain.com/oss/python/langchain/frontend/overview)
- [LangChain React reference — Transports／AgentServerAdapter replay contract](https://reference.langchain.com/javascript/langchain-react/transports)
- [LangGraph JS SDK changelog — reconnect／replay／HITL fixes](https://github.com/langchain-ai/langgraphjs/blob/main/libs/sdk/CHANGELOG.md)
- [LangChain official streaming cookbook — React custom backend（Agent Streaming Protocol over HTTP／SSE）](https://github.com/langchain-ai/streaming-cookbook/tree/main/typescript/react-custom-backend)
- [LangSmith — Agent Server architecture（PostgreSQL、task queue、per-thread run serialization）](https://docs.langchain.com/langsmith/agent-server)
- [LangSmith — Double texting scope](https://docs.langchain.com/langsmith/double-texting)
- [LangSmith — Standalone Agent Server requirements](https://docs.langchain.com/langsmith/deploy-standalone-server)
- [LangSmith — Streaming API／reconnect](https://docs.langchain.com/langsmith/streaming)
- [LangGraph frontend — Join／rejoin requires Agent Server](https://docs.langchain.com/oss/python/langchain/frontend/join-rejoin)
- [FastAPI — Server-Sent Events](https://fastapi.tiangolo.com/tutorial/server-sent-events/)
- [FastAPI 0.141.1 — SSE source](https://github.com/fastapi/fastapi/blob/0.141.1/fastapi/sse.py)
- [FastAPI — PyPI release history](https://pypi.org/project/fastapi/)
- [WHATWG HTML — Server-sent events](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [MDN — Using server-sent events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events/Using_server-sent_events)
- [sse-starlette 3.4.8 — PyPI](https://pypi.org/project/sse-starlette/)
- [LangChain — Context engineering in agents](https://docs.langchain.com/oss/python/langchain/context-engineering)
- [LangChain — Agents（model、tools、structured output 的組合邊界）](https://docs.langchain.com/oss/python/langchain/agents)
- [LangChain — Structured output（ProviderStrategy／ToolStrategy 與 schema 驗證）](https://docs.langchain.com/oss/python/langchain/structured-output)
- [LangChain Reference — `Citation` content annotation](https://reference.langchain.com/python/langchain-core/messages/content/Citation)
- [LangChain — Custom middleware（dynamic model selection 是可選 middleware）](https://docs.langchain.com/oss/python/langchain/middleware/custom#dynamic-model-selection)
- [LangChain — Prebuilt middleware（model／tool call limits、retry、HITL）](https://docs.langchain.com/oss/python/langchain/middleware/built-in)
- [LangChain — Todo schema／TodoListMiddleware](https://reference.langchain.com/python/langchain/agents/middleware/todo/Todo)
- [LangChain — OpenRouter integration](https://docs.langchain.com/oss/python/integrations/chat/openrouter)
- [OpenRouter — Provider routing（order、fallback、required parameters）](https://openrouter.ai/docs/guides/routing/provider-selection)
- [LangSmith — OpenTelemetry tracing／OTel backend routing](https://docs.langchain.com/langsmith/trace-with-opentelemetry)
- [LangChain — Short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)
- [LangChain — Memory overview](https://docs.langchain.com/oss/python/concepts/memory)
- [Deep Agents — Overview（planning、context、store）](https://docs.langchain.com/oss/python/deepagents/overview)
- [Deep Agents — Skills（metadata discovery 與按需讀取完整 `SKILL.md`）](https://docs.langchain.com/oss/python/deepagents/skills)
- [Deep Agents frontend — Todo list／shared state](https://docs.langchain.com/oss/python/deepagents/frontend/todo-list)
- [LangMem — Long-term memory concepts／profile／collection](https://langchain-ai.github.io/langmem/concepts/conceptual_guide/)
- [Agent Skills — Open specification（SKILL.md 與 progressive disclosure）](https://agentskills.io/specification)
- [Agent Skills — Overview／client ecosystem](https://agentskills.io/home)
- [Deep Agents Reference — 可單獨組裝的 SkillsMiddleware](https://reference.langchain.com/python/deepagents/middleware/skills/SkillsMiddleware)
- [PydanticAI — Version policy（V2 stable 與相容承諾）](https://pydantic.dev/docs/ai/project/version-policy/)
- [Pydantic — PydanticAI V2 capability-first／Harness 設計](https://pydantic.dev/articles/pydantic-ai-v2)
- [PydanticAI — Capabilities](https://pydantic.dev/docs/ai/capabilities/overview/)
- [PydanticAI — DynamicCapability API／durable stable ID](https://pydantic.dev/docs/ai/api/pydantic-ai/capabilities/)
- [PydanticAI — On-demand capabilities](https://pydantic.dev/docs/ai/capabilities/on-demand/)
- [PydanticAI — Typed output／output validators](https://pydantic.dev/docs/ai/core-concepts/output/)
- [PydanticAI — OpenRouter model／routing／cache settings](https://pydantic.dev/docs/ai/models/openrouter/)
- [PydanticAI — Graph 使用界線](https://pydantic.dev/docs/ai/graph/graph/)
- [Pydantic AI Harness — Overview／0.x version policy](https://pydantic.dev/docs/ai/harness/)
- [Pydantic AI Harness — Agent Skills](https://pydantic.dev/docs/ai/harness/skills/)
- [Pydantic AI Harness — Compaction](https://pydantic.dev/docs/ai/harness/compaction/)
- [Pydantic AI Harness — Tool Output Limits](https://pydantic.dev/docs/ai/harness/tool-output-limits/)
- [Pydantic AI Harness — Planning（stable ID、dependency、store、event）](https://pydantic.dev/docs/ai/harness/planning/)
- [Pydantic AI Harness source — PlanItem fields](https://github.com/pydantic/pydantic-ai-harness/blob/main/pydantic_ai_harness/planning/_types.py)
- [Pydantic AI Harness source — PostgresPlanStore concurrency boundary](https://github.com/pydantic/pydantic-ai-harness/blob/main/pydantic_ai_harness/planning/_postgres.py)
- [Pydantic AI Harness — Guardrails](https://pydantic.dev/docs/ai/harness/guardrails/)
- [Pydantic AI Harness — Memory security／provenance](https://pydantic.dev/docs/ai/harness/memory/)
- [Pydantic AI Harness — StepPersistence scope](https://pydantic.dev/docs/ai/harness/step-persistence/)
- [PydanticAI — Durable execution with DBOS](https://pydantic.dev/docs/ai/capabilities/durable_execution/dbos/)
- [PydanticAI — Deferred tools and human-in-the-loop approval](https://pydantic.dev/docs/ai/tools-toolsets/deferred-tools/)
- [PydanticAI UI — Vercel AI adapter／trust／approval](https://pydantic.dev/docs/ai/integrations/ui/vercel-ai)
- [PydanticAI UI — AG-UI shared state／interrupt](https://pydantic.dev/docs/ai/integrations/ui/ag-ui/)
- [DBOS — Workflows／recovery guarantees](https://docs.dbos.dev/python/tutorials/workflow-tutorial)
- [DBOS — SQLAlchemy Datasource transactions](https://docs.dbos.dev/python/tutorials/transaction-tutorial)
- [DBOS — Queues／concurrency／deduplication](https://docs.dbos.dev/python/tutorials/queue-tutorial)
- [DBOS — Partitioned queue reference](https://docs.dbos.dev/python/reference/queues)
- [DBOS — Atomic enqueue in application transaction](https://docs.dbos.dev/python/reference/client)
- [DBOS — Custom／portable serialization](https://docs.dbos.dev/python/reference/contexts)
- [DBOS — Workflow messages／events／streaming](https://docs.dbos.dev/python/tutorials/workflow-communication)
- [DBOS — Upgrading workflow code](https://docs.dbos.dev/python/tutorials/upgrading-workflows)
- [OpenRouter — Zero Data Retention](https://openrouter.ai/docs/guides/features/zdr)
- [OpenRouter — Provider routing and data-policy controls](https://openrouter.ai/docs/guides/routing/provider-selection)
- [OpenRouter — Input & Output Logging](https://openrouter.ai/docs/guides/features/input-output-logging)
- [Microsoft — Agent Framework overview](https://learn.microsoft.com/en-us/agent-framework/overview/)
- [Microsoft — Agent Framework Agent Skills](https://learn.microsoft.com/en-us/agent-framework/agents/skills)
- [Microsoft — Agent Framework Workflows](https://learn.microsoft.com/en-us/agent-framework/workflows/)
- [Microsoft — Agent Framework Checkpoints](https://learn.microsoft.com/en-us/agent-framework/workflows/checkpoints)
- [Microsoft — Agent Framework Memory & Persistence（history、context provider、session state）](https://learn.microsoft.com/en-us/agent-framework/get-started/memory)
- [Microsoft — Self-host Agent Framework applications（session 與 history 分離）](https://learn.microsoft.com/en-us/agent-framework/hosting/self-hosting/)
- [Microsoft — Agent Framework Harness](https://learn.microsoft.com/en-us/agent-framework/concepts/harness)
- [Microsoft — Agent Framework Harness quick start（plan／todo／history across turns）](https://learn.microsoft.com/en-us/agent-framework/get-started/harness)
- [Microsoft — Agent looping（completion condition、bounded iteration、approval escape）](https://learn.microsoft.com/en-us/agent-framework/agents/looping)
- [Microsoft — Agent Framework workflows human-in-the-loop](https://learn.microsoft.com/en-us/agent-framework/workflows/human-in-the-loop)
- [Microsoft — Agent Framework AG-UI integration](https://learn.microsoft.com/en-us/agent-framework/integrations/by-component/ui/ag-ui/)
- [Microsoft Azure Architecture Center — Strangler Fig pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/strangler-fig)
- [AWS Prescriptive Guidance — The strangler fig pattern](https://docs.aws.amazon.com/prescriptive-guidance/latest/modernization-aspnet-web-services/fig-pattern.html)
- [AWS Strands Agents — Session management](https://strandsagents.com/docs/user-guide/concepts/agents/session-management/)
- [AWS — Introducing Strands Agents](https://aws.amazon.com/blogs/opensource/introducing-strands-agents-an-open-source-ai-agents-sdk/)
- [LlamaIndex — Workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/)
- [LlamaIndex — Durable Workflows](https://developers.llamaindex.ai/python/llamaagents/workflows/durable_workflows/)
- [LlamaIndex — Ingestion Pipeline（cache、hash／dedup、async）](https://developers.llamaindex.ai/python/framework/module_guides/loading/ingestion_pipeline/)
- [LlamaIndex — CitationQueryEngine](https://developers.llamaindex.ai/python/examples/query_engine/citation_query_engine/)
- [Haystack — AnswerBuilder／referenced documents](https://docs.haystack.deepset.ai/docs/answerbuilder)
- [LiteLLM — Provider interface／Router／cost tracking](https://docs.litellm.ai/)
- [Mem0 — Memory add／LLM inference behavior](https://docs.mem0.ai/core-concepts/memory-operations/add)
- [Letta — Memory blocks](https://docs.letta.com/guides/core-concepts/memory/memory-blocks)
- [Graphiti — Temporal knowledge graph overview](https://help.getzep.com/graphiti/getting-started/overview)
- [Graphiti — Episodes／provenance](https://help.getzep.com/graphiti/core-concepts/adding-episodes)
- [Graphiti — Custom entity and edge types](https://help.getzep.com/graphiti/core-concepts/custom-entity-and-edge-types/)
- [Zep — Temporal facts／invalidation](https://help.getzep.com/facts)
- [eventsourcing 9.5.4 stable — PyPI release history](https://pypi.org/project/eventsourcing/)
- [eventsourcing stable docs — Application／outbox／multi-aggregate save](https://eventsourcing.readthedocs.io/en/stable/topics/application.html)
- [eventsourcing stable docs — Projections](https://eventsourcing.readthedocs.io/en/stable/topics/projection.html)
- [eventsourcing stable docs — Dynamic consistency boundaries](https://eventsourcing.readthedocs.io/en/stable/topics/dcb.html)
- [SQLAlchemy 2.0 — Version counter／stale detection](https://docs.sqlalchemy.org/en/20/orm/versioning.html)
- [Rasa CALM — FlowPolicy／dialogue stack](https://rasa.com/docs/reference/config/policies/flow-policy/)
- [Camunda 8 — User task lifecycle／custom actions](https://docs.camunda.io/docs/apis-tools/frontend-development/task-applications/user-task-lifecycle/)
- [OpenTelemetry — Generative AI semantic conventions／sensitive-content warning](https://opentelemetry.io/docs/specs/semconv/registry/attributes/gen-ai/)
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
