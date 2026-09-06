# Q019／MP-02：小額 Memory prompt 真測與局部修復

> 2026-09-07；G5 有限實驗 → 兩個已重現接線缺陷的局部修復。**不是 Memory 品質通過、不是產品可用性驗收。**
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
