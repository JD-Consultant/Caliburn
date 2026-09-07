# Q019／MP-02：小額 Memory prompt 真測與局部修復

> 2026-09-07；G5 有限實驗 → 兩個已重現接線缺陷的局部修復。**不是 Memory 品質通過、不是產品可用性驗收。**
> **最新續測：見 §6。**已保存兩修可跑過前兩次 B2，但整組仍未通過。新提示試驗未通過，已撤回這次四檔試改；保留 `04ce14d8` 程式，不提高上限。下方 §1–5 為先前3次試跑沿革，不把它們當最新累計。
> 最新決策入口：[主 checkout register](../../../../docs/current-decisions.md)。需求與方法：[Memory 設計／prompt 段](../../../../docs/specs/2026-09-06-analysis-only-agent-memory-design.md#2026-09-07memory-prompt-調整與驗收重點)。不重選 ABC 或五產物。

## 1. 範圍與結果先講

Owner 同意使用 `apps/api/.env` 的 key，先做獨立、小額 Luna／medium 實驗，不因 MP-01 的計數端點 404 停住所有 prompt 觀察；**沒有移除產品完整 Context 預算或更換正式 provider 接線。**

三次試跑都成功取得第一批詳記／候選，但都在第一次 B2 整併碰到既有 8 model steps 上限，沒有發布 Memory。因此後續補充、更正、fresh-context 回查尚未執行，不能說它們有效或無效。這輪停止付費試跑，不靠無限重試取得一次成功。

| 試跑 | 與原版差異 | 真實請求／結果 | provider 回報成本 USD |
|---|---|---|---:|
| baseline／`9107ee0ce90d` | 原 B1／B2 prompt、原工具說明 | B1 1次＋B2 8次；第一次驗證之後無下一步額度，未完成發布 | 0.00460172 |
| prompt-only／`79b74de72b85` | 只在 B2 補充精確地址可直接讀、GUIDE 已提供 | 1＋8次；仍列目錄、重讀導覽，另做同字串替換／重读，未完成 | 0.00431418 |
| prompt＋tool description／`4413f30bf7be` | 上項＋官方 `custom_tool_descriptions` 覆寫 `ls` 說明 | 1＋8次；沒有 ls；中文括號引用被拒後模型讀取、修正、再驗，無下一步額度 | 0.00360771 |
| 合計 | 3次有限試跑，非3次成功 | **27次 Responses 請求，均 HTTP 200／completed；流程均 stopped** | **0.01252361** |

HTTP 成功只代表模型回覆完成，不代表 B2 agent／發布成功。以上數值是回覆 `usage.cost` 相加，不是估算整份 JD 費用，也不是單輪日常訪談費用。

## 2. 測了什麼，沒有測什麼

- 模型固定 `openai/gpt-5.6-luna`、reasoning `medium`，不是 Opus、luna-pro 或 max。
- 使用官方 ChatOpenAI／Responses 接到原 key 對應的 OpenRouter；不把 OpenRouter key 送往 OpenAI 主機。不記錄 headers／key、不開外部 tracing。
- 重用實際 B1、B2、artifact／來源 reader、官方檔案工具與 publication 類別；Saver／Store 記憶體、publication SQLite 暫存，不改產品 DB／Docker。
- 問答是預寫的合成訪談，不是主顧問真實訪談能力測試。抽取／整併內容是模型實際生成，不是 mock 回覆。
- 每個獨立試跑 client 上限24次請求，每次最多4096 output tokens、request JSON 100KB；本輪3次合計27次，**不是合計低於24次**。本地每請求按 input bytes 與輸出上限先預留，回報 cost 後對帳；US$0.15 為本次實驗停止界線，非精確帳戶硬限額。未報費用時保留預留值，不當作0。
- SDK `max_retries=0`；B2 仍8個模型步驟／12次工具上限，沒有提額。函式呼叫要求與完成訊息都會用模型步數；8不是「允許8個工具後免費收尾」。
- 本 probe 不開 `all_turns` 或 compaction，不經產品 input-token counter。因此不證明原生跨輪推理、長 Context、正式 endpoint 契約或服務恢復。

### 預定材料與已執行界線

1. **實際執行**：接案前端工程師，青禾書店 A 案單次信用卡付款／商品頁／購物車／原先自述無障礙檢查，店長驗收；拾光課程 B 案月租課程／三種權限，營運經理驗收。DB／金流後端由合作後端負責，B 的備份不是本人工作；驗收期限未回答。
2. **未執行**：補 A 付款失敗保留購物車／輸入、手機斷線重連驗證；2024年一次設備搬運不屬目前接案。
3. **未執行**：明確更正 A 無障礙檢測由同事做，本人修前端問題，再由同事複查；B 不變、驗收期限仍未知。
4. **未執行**：新模型 context 只給導覽與既有回查工具，追問各案細節、更正、未知與舊工作。

三份已產生的首批詳記可見 A／B 案名、計費差異、權限細節、本人／後端分工與未答驗收期限；這只是短樣本的正向觀察，不是「長訪談完整保留」證明。第三次候選很精簡，B2 暫存正文未抄全部案例細節，這本身不必然錯；是否仍可被導覽／正文帶往詳記，需要完成回查才可判定。

## 3. 發現、官方依據與最小處理

### MP-02a：應用提示與框架目錄工具預設說明衝突

**直接證據：**已安裝 Deep Agents 0.7.13 的 `LIST_FILES_TOOL_DESCRIPTION` 鼓勵幾乎每次 read/edit 前先 ls；B2 同時已提供 `MEMORY_FILES` 及每筆 `summary_path`。前兩次確實先列目錄；只補 system prompt 沒消除。第三次透過官方覆寫入口改工具說明後，這個樣本沒有 ls，但仍未跑完整 B2。

**採用的小修：**只在 B2 建立官方 FilesystemMiddleware 時，使用公開 `custom_tool_descriptions={"ls": ...}`：地址未知才列目錄，系統已給精確地址可直接讀。沒有移除 ls、改工具 schema、自己重寫檔案工具或禁止必要深讀。試驗用加長 B2 prompt **未納入程式**；B1、B2 分析指令及三個 Skill 正文保持不變。

官方依據：[0.7.13 原始碼（預設描述、建構子與 tool factory）](https://github.com/langchain-ai/deepagents/blob/deepagents==0.7.13/libs/deepagents/deepagents/middleware/filesystem.py)、[官方 API 公開覆寫參數](https://reference.langchain.com/python/deepagents/middleware/filesystem/FilesystemMiddleware)。後者本輪搜尋可查，但直接頁面開啟錯誤；細節以成功讀取的固定版本原始碼與本地安裝檔核對。**框架支援覆寫是官方事實；這段用途說明是本案配置，不宣稱廠商採同一 prompt。**

### MP-02b：中文括號說明被誤算成地址

**真實模型輸出形狀：**`/interviews/<既有ID>/summary.md（接案前端專案分工與驗收）。`。系統原有散文地址辨識排除 ASCII 括號與部分中文標點，卻沒排除 `（ ）`，導致把中文說明附在路徑後一起驗，回 `Expected an existing runtime interview artifact address`。不是模型捏造 ID，也不是員工資訊不可信。

模型收到精確錯誤後，讀回正文、把路徑和說明分行、再呼叫驗證，證明本次錯誤有回進模型。這幾步修正用完剩餘額度，不能把框架停止誤稱成功發布。

**採用的小修：**既有散文地址 delimiter 補全形括號。CommonMark 的明確 link destination、inline code／code fence 仍採原樣精確地址驗證，不能把錯字／錯地址裁切成另一個有效來源；scope／存在性驗證不變。這是已有 controlled-address parser 的窄修正，不是新 Evidence／記憶機制。

依據：[既有 BG-01 引用修復原則](2026-09-07-memory-reference-repair-results.md)、[CommonMark links](https://spec.commonmark.org/0.31.2/#links)。**CommonMark 不替本產品定義散文中的本地路徑詞界**；全形括號的處理由真實失敗與本產品固定地址格式支持，明確記作本案局部實作，非「OpenAI 官方指定這個 regex」。

### MP-02c：完成率／額度仍未验收

[LangChain 官方 ModelCallLimitMiddleware](https://docs.langchain.com/oss/python/langchain/middleware/built-in#model-call-limit)支援 thread/run 上限與 error 停止。框架正確阻止後續模型呼叫；本輪不把它改成靜默成功、不只提高上限。

**待驗問題：**兩個局部修復後，既有 8 步能否完成正常整併與后續修訂／回查？現有三次資料不能回答，亦不能據此推論所有背景整理都需更多步驟。下一段先續原材料，不增加案例集、另造流程或擴成大型 eval。

## 4. 驗證與程式可讀性判斷

- 先寫實際 artifact 保存／發布與實際 tool wire 回歸：**RED 2 failed／20 passed**，分別重現中文括號誤拒與 ls 矛盾指令。
- 修復後6檔測試：`test_memory_references`、`test_consolidation`、`test_consolidation_feedback`、`test_extraction`、`test_extraction_feedback`、`test_analysis_skills`，**184 passed／12.04s**；`compileall`、`git diff --check`通過。
- 測試使用真正 framework、Store 與 publication，外部HTTP為合成資料；它驗證接線／規則，**不證明真模型會遵從提示或完整記憶品質**。沒有重跑全套 PostgreSQL／服務測試，不能拿前段514項當本次全套驗證。
- explicit link／code 裡把中文說明寫進地址仍拒絕，防止「修復散文」變成靜默改寫來源。
- 抽取、整併、來源／artifact、發布與讀取各自已有可組裝介面，本次可單獨測試。**目前不重構**，不為整理程式加入新抽象層。已找到的是工具描述與標點解析，不是需要改 Memory 架構的證據。
- 獨立 code review：指定四個程式／測試檔審核無重要 finding，reviewer 重跑兩個測試檔 **86 passed／6.68s**，diff check通過；未聲稱重跑184項。結果只承接這兩個修復，不擴成產品核准。

## 5. 紀錄、限制與下一步

[可攜式去重實驗紀錄 JSON](evidence/2026-09-07-memory-prompt-probe.json)保存每次實際 prompt／hash、合成訪談材料、B1 產物、模型工具呼叫／可見輸出、下一次請求中可见工具回覆、usage／成本與停止原因。刪除重複上下文、未收 headers／金鑰／opaque thinking。**最後一個工具若沒有下一次模型請求，其結果可能未被封包紀錄收錄**，不能由該紀錄自行補猜。

完整原始 probe JSON 與約200行一次性腳本只留隔離 worktree `.test-tmp/`，不把臨時 client／費用預留寫進產品；可攜紀錄含原始檔 hash 與位置。SQLite／Memory graph 為暫存，引用在這些實驗存活期間真實可讀，不承諾離開程序後可連回測試 Store。既有 canonical 持久性另有先前測試。

**狀態：**MP-02a／b局部修復；MP-02c與多輪 prompt 品質仍未驗收。MP-01計數端點相容仍 OPEN。下一步只重跑同組小額材料，確認整併可完成再看案例補充／更正與回查；若仍不成，先回報具體原因再決定，不提高成本或變更 ABC。不merge／push、不接 JD／UI／production。

費用來源：[OpenRouter Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)。提示研究依據：[OpenAI Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml)支持清楚區分指令與 Context；不保證單次提示改動一定改善模型行為。這輪以直接試驗結果區分事實、候選與尚未證明的效果。

## 6. 同組材料續測：有進展，但不能只靠再加提示收尾

### 6.1 兩次實測與成本

沿用同組材料、Luna／medium、8個 B2 model steps／12次 tools、每次試跑24次 HTTP／4096輸出上限；沒有加額、升 reasoning、SDK 自動重試、改 publication 或接產品資料庫。

| 續測 | 真實結果 | 請求／provider 回報 USD |
|---|---|---:|
| `209c625ee483`，只有已保存 `04ce14d8` 兩修，無 probe 提示覆寫 | 第1／2次 B2 分別6／8步完成發布；第3批 B1完成，但第3次B2尚未完成，測試的24次總上限擋住下一請求 | 24／0.01092880 |
| `c815bc309340`，局部 prompt 試改 | 第1次 B2 5步發布，但導覽為空；第2次B2兩次精確文字替換失敗，達8步上限，沒有第二次發布；第3批與回查未執行 | 15／0.00867193 |
| **本輪合計** | **不是39次成功流程，沒有 fresh-context 回查結果** | **39／0.01960073** |

與 §1 的3次試跑合計為66次請求、US$0.03212434。只代表這5次合成材料實驗，不是產品每輪費用。

第一個停止的表面型別是 `OpenAIConnectionError`，但已完成24次 HTTP，下一次被 probe 自身 `before` hook 的總上限擋住；SDK會包裝送出階段的一般例外。本地上限不是 provider 斷線，不能重試連線或放寬產品預算去「修」。其 B2-3 已用7步，尚有獨立的8步job限制，不能宣稱只差提高24次便必然成功。[SDK送出與例外包裝](https://github.com/openai/openai-python/blob/v3.8.0/src/openai/_base_client.py#L1098)

### 6.2 實際發現，而非猜測

1. **MP-02d／候選交接過窄（OPEN）：**`209...` 的首批詳記保留 A／B 各項工作，但 `raw_memory` 只有未答驗收期限。B2只依這個候選建立「驗收時限未知」主題；不是來源丟失，卻不足以讓導覽反映已談工作。試改後首批候選與正文都有 A／B 工作、角色／後端邊界，這是單樣本改善，未證明整體通過。
2. **MP-02e／未回答被誤當否定（OPEN）：**第2批追問無障礙分工尚未回答，並非新的否認。`209...` 卻將它和原本「我負責檢查」寫成歧義；真正更正是在第3批。試改明講邊界後，`c815...` 暫存正文仍變成「不宜推定由本人負責」。不能以提示已寫就說語意缺陷已修好。
3. **MP-02f／低階編輯負擔與完成條件（OPEN）：**`c815...` B2-2 把不存在的句尾 `。` 加進 `old_string`，大段替換失敗後又分多次改段落／關鍵詞／引用，引用那次仍多同一個句號而失敗，最後回讀，用完8步。官方 exact edit 正確回錯，不應加 fuzzy match 替模型猜要改哪段。第1次雖發布正文，導覽卻為空；現有 validator只檢查可讀格式／大小／引用，不保證語意或導覽完成，故驗證成功不等於產品效果完整。

詳記中的「員工要求保留已填資料」與「員工只明說測了購物車是否保留」也需區分；不能把尚未描述驗證方式誤寫成需求不確定。此處保留為內容判讀注意，不加入逐欄 schema／自動語意拒絕器。

### 6.3 官方研究與這次試改的效力

- **官方事實：**OpenAI GPT-5.6 提示指引建議用小型真實 traces 找失敗、先消除矛盾與不必要的必做步驟、明訂成果／停止條件後重測；沒有要求越失敗就越加長 prompt 或提高 reasoning。[GPT-5.6 提示指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)
- **官方事實：**OpenAI公開 Memory 的抽取產生對話摘要及可整併資訊，整併再歸納模式；不是把候選定義成只有未回答問題。SDK允許以使用情境的額外指示定義重要訊號。研究沿用既有五產物，不重開Memory總流程。[Memory生成與用途調整](https://openai.github.io/openai-agents-python/sandbox/memory/#generate-memory)
- **官方事實：**LangChain公開 `after_model` 等 middleware接點可驗證並跳回模型。現有 `ConsolidationFeedback` 已在這條路徑執行，collect／保存仍另驗；**不必模型自報驗證通過才安全**。[Middleware hooks／jumps](https://docs.langchain.com/oss/python/langchain/middleware/custom#agent-jumps)
- **已核對框架實作：**Deep Agents0.7.13 的 edit 是精確替換，會回找不到／多重命中錯誤；工具說明也要求先讀。不能只改應用提示讓它少讀，卻忽略工具自己的指令。`read_file` 的行號不是原文。此次句號錯配不是框架應自動吞掉的錯誤。[固定版本tool factory](https://github.com/langchain-ai/deepagents/blob/deepagents==0.7.13/libs/deepagents/deepagents/middleware/filesystem.py)、[替換規則](https://github.com/langchain-ai/deepagents/blob/deepagents==0.7.13/libs/deepagents/deepagents/backends/utils.py)

本次試改僅澄清 B1候選內容、B2未答問題與 GUIDE已提供，並讓驗證工具變可選預檢；沒有改實際驗證、檔案／來源權限、schema欄位數、步數或原子發布。**整組仍不合格，因此四檔試改已全部還原為 `04ce14d8`，不提交成正式修復。**候選語句與完整 diff 保存於證據JSON，不靠下次回憶重猜。這不表示已證明每一句修改都無效，只表示本試驗不足以採用整包修改。

### 6.4 驗證、剩餘決策與下一步

- 試改期間原6檔回歸 **184 passed／11.65s**。首次 sandbox 執行遇到 pytest暫存目錄 WinError5；改新專用目錄並取得執行權限後通過，未更動程式／Docker處理測試環境。
- 撤回試改後再跑同6檔：**184 passed／11.84s**；compileall／diff check通過，`git diff --numstat -- experiments/analysis-agent/src`為空。保存的兩修仍在，沒有把本輪未通過提示留在執行路徑。
- 限定獨立review亦判 **NOT PASS**：導覽完成條件、未答追問誤判、精確編輯恢復三項P2。reviewer另跑21項安全回歸通過；確認GUIDE描述與實際輸入相符、可選preflight沒有移除後端驗證，但不支持以此交付品質修復。這是試改的審核結論，非要求把每項語意都改成程式規則。
- 既有 `test_consolidation_feedback` 真框架合成HTTP測試已驗證：不呼叫validate工具，invalid final仍回模型修；失敗／refusal／超限不發布。它只能驗機制，不能證明 Luna 自然生成會完成導覽或保留正確語意。
- 下一題只聚焦 **「B2 的成果交付／工具操作怎麼降低出錯，而不降低記憶完整性」**。先不再追加付費試跑，也不提高額度。
- 候選1：保留官方檔案編輯，收斂完成條件及重複操作；優點是長正文仍可局部更新，缺點是精確替換仍需要模型複製旧字串。候選2：保留按需讀取，對可完整處理的正文與導覽採框架結構化成果交付；可少掉逐次替換，但整檔輸出有長度／成本邊界，不能未讀就重建長正文。**目前沒有選定或實作候選2**。
- LangChain `create_agent(response_format=...)` 是官方能力，但同時用工具與結構化輸出要求 provider支援；它保證形狀，不保證語意完整或直接替本產品處理原子發布。[Structured output／provider條件](https://docs.langchain.com/oss/python/langchain/structured-output#response-format)不能因看見這個API就宣稱已能承接所有Memory大小。
- 保留原文、詳記、理解、導覽及逐層回查，ABC責任不翻案；不新增Memory層、不將案例硬拆Task／OPKS、不做JD／UI，不重構或換框架。若確需改 B2輸出契約／資料流，先給 Owner 短設計確認。

[本輪可攜證據](evidence/2026-09-07-memory-prompt-followup.json)包含2次的實際prompt、精確試改diff、B1產物、已發布快照、可見模型／工具結果、成本與停止診斷；無key／headers／opaque reasoning。先前3次證據檔未覆寫。**本輪停止於已知品質缺口，不宣稱Memory已修完。**
