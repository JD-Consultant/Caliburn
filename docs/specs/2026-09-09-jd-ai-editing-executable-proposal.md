# AI 與員工共同編輯 JD：可執行方案（待審）

**2026-09-09 後續修正／舊候選沿革：**Owner 已要求執行[免費開源研究→討論→設計計畫](../plans/2026-09-09-jd-editor-research-discussion-design.md)，並允許依共同做法重議「人改待審仍待審」。本稿下方推薦、工具組合及 I0 起點形成於免費開源限制之前，**不能再當成目前候選或直接施工依據**；可復用的情境與已知差距依[新研究主稿](2026-09-09-jd-oss-editor-capabilities-and-gaps.md)重新核對。原付費 Tiptap／CKEditor 路線只作行為參照，不因已寫方案就取得採用效力。

JD-R002/C03；2026-09-09；**G2 研究交付／待 G3 審閱**。這是一份有選型、接線、缺口及驗證門檻的設計建議，不是所有未知都已解決的施工計畫，也不是安裝／購買／付費測試／production 授權。

**同日進度核對：**Owner 已同意跨廠 App／編輯工具共同基礎（G3／WORKING），並要求完整串讀近期研究、延續不受舊產品／舊架構限制的新設計。下方選型及有限驗證仍是待審推薦；本次同意沒有擴張為框架採用或實驗授權。

## 0. 先讀什麼

- [C03 短入口](2026-09-09-ai-document-app-composition-research.md)：目前問題、決策狀態及結論。
- [C01 文件內容關係](2026-09-09-jd-document-relationships-working-research.md)＋[C02 審核情境](2026-09-09-jd-editing-and-review-working-design.md)：本方案必須服務的效果，不拿套件預設取代它們。
- [編輯框架事實 F01–F05](2026-09-09-jd-editor-framework-comparison.md)＋[Agent／錯誤事實 R01–R10](2026-09-09-jd-ai-app-runtime-official-evidence.md)：精確 API、來源及限制；[E01–E20](2026-09-09-jd-document-model-official-evidence.md)保留早先產品／文件證據。
- [內容核心入口](2026-09-09-job-analysis-and-jd-content-research.md)：JD 寫什麼及訪談方法。不重複搬入本技術稿，更不把全部研究塞進每輪 prompt。

**本輪結論：**共同的工具循環可以直接用成熟 agent 框架；文件也應先用編輯器原生操作及追蹤修訂。較難且沒有現成全覆蓋證據的，是 C02 的持續待審／人工修改／跨位置整組接受拒絕。首選先驗 Tiptap；CKEditor 是明確備選，不直接自寫通用審核引擎。

### 0.1 近期研究串讀後的真實進度

| 主線 | 已到哪裡 | 本次銜接的界線 |
|---|---|---|
| 職務分析與 JD 內容 | R001 的分析／欄位／深度方法及樣稿 r2 方向已獲可修訂同意，內容與來源已人工雙向核對 | 9/9 這組方法尚未轉成並驗收新的 JD 生成 Skill；人工樣稿不是模型效果證明 |
| 新隔離訪談與 Memory（LLM-Q019） | CT49 完成一個接案前端職位的 11 輪訪談、更正與來源回查；CT50 採用所測配置，另以真服務續談及空近期 context 回查補驗；CT51 保留 8192 輸出上限 | 已有可復用的對話、工具結果及來源深讀能力，但未接 JD 編輯／審核；不把所測情境泛化成所有職位可靠 |
| 文件結構與審核（C01／C02） | 可辨識結構＋完整敘述、最小完整改動群組、人改待審內容仍待審，已 G3／WORKING | 跨位置分組、連續修訂後回退、保存重開等效果仍需驗證；不由套件預設代決 |
| App 與工具共同基礎（C03） | Owner 本輪同意工具說明、可讀狀態、模型提案／App 執行／結果回饋及成果評估的分工 | 同意共同原則，不等於同意唯一 patch 格式或某套編輯器 |
| JD 編輯整合（C03） | 本稿已有端到端候選、已知差距與 I0–I4 門檻 | 尚無 editor 實測；下一個會改變選擇的證據是待審文件的實際行為，不是再增加通用架構研究 |

**核對範圍：**本輪由主線與三路唯讀核對完整串讀近期主文群：內容入口及其分析、欄位、深度、樣稿、審查、國際／雇主證據共八稿，另讀 9/7 資訊取捨；C01／C02、C03 入口、本方案、E／R／F 證據及共同基礎共八稿；9/6 隔離版四份設計、9/7 runtime/context audit 與 native-first review、CT49／50／51 結果及隔離 README。另讀 MEM-Q005，核對 CT30 停放段落與 CT35。這是近期有效主線的全文串讀，不宣稱逐篇重讀全部歷史研究或重跑實驗。

最新 runtime 依 [CT50 的採用設定與測試結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct50-tested-profile-results.md)與[CT51 結果](../../.worktrees/analysis-only-agent/docs/specs/2026-09-09-ct51-output-budget-results.md)，不沿早期設計的 medium 或 README 歷史保存點。CT50 記錄 564 離線＋41 真 PostgreSQL 檢查；本輪只是讀取該證據，沒有重新執行。可復用的是新隔離版已測的能力與經驗；新文件方案仍依需求及原生框架能力選擇，不因舊語言、schema、DB、元件或 authority 設計而受限。

上述是**設計不受舊架構約束**，不等於研究稿自行變更正在執行的產品。若未來採用新設計會改 production authority，仍依流程提出 successor ADR 與通過 implementation gate；這個施工效力邊界不反過來要求新設計必須保留舊架構。

**下一輪必須保留的兩個銜接條件：**

- 內容設計引用[分析指南 §2–§6](2026-09-09-complete-work-analysis-guide.md)、[欄位指南](2026-09-09-jd-field-and-writing-guide.md)及[深度校準 §2–§6](2026-09-09-customized-jd-depth-and-interview-calibration.md)的保留效果：完整工作範圍、案例與持續責任的區分、未知與更正、必要細節、工作↔JD 雙向核對。CT49 的接案前端與 r2 的受僱前端是不同情境；各自保留來源，不把兩者內容直接拼成同一職位。
- 沿 [MEM-Q005 的 sibling effects 邊界](2026-09-04-memory-persistence-and-jd-effect-reconciliation.md)：未來接上 JD 後，若同一 product run 已形成通過內容驗證的理解，且 JD 候選通過自身驗證，不一律等背景 Memory 落盤才產生增量待審修改；單純 Memory 保存失敗不等於該 JD 候選語意失效。整份最終完成檢查另需核對完整有效依據。這是既有工作決策，並非聲稱目前隔離版已能形成或驗證 JD 候選。

**本輪唯一下一個裁決：**是否以 §2 的 Tiptap 組合作第一驗證候選，先進入 §7 所收斂的無 LLM 文件編輯／審核驗證。框架最終採用、agent 接線及真模型整合仍由結果決定，不重問已同意的內容、Memory 與共同基礎。

## 1. 大方向是否偏移

保留以下效果：

1. 人與 AI 讀寫**同一份目前文件**，包含尚未審核的最新內容；不是各編一份再由人合併。
2. AI 修改看得見；存進目前文件不等於核准。員工直接改待審內容仍待審，另按接受才確認。
3. 無關修改分開；移動／拆分的相依部分整組審。拒絕不抹去組外修改，未審不阻塞後續訪談。
4. 先理解實際工作，再按需要撰寫 JD；不是每輪必改，也不是逐案例建立永久任務。
5. 新任務／未歸屬內容可以逐步完善。不增加 A／能力級別、強制一對一 OPKS、iCAP 匯出或虛構必填事實。
6. 本機單操作者；AI 分析時暫鎖文件寫入及新訊息，完成／終止失敗後恢復操作。不新增多人協作／CRDT 產品需求。
7. Memory、對話、原生 reasoning 延續保持既定分工。JD 是產品文件，不是 Memory 的替代物，也不把原生推理內容當可供審核的文件資料。

本方案沒有建議翻案以上效果；但**不能宣稱框架已原生保證第2、3項的全部情境**。若驗證後必須取捨，先提出影響讓 Owner 決定，不默默縮水。

## 2. 推薦組合與替代條件

### 第一候選

**Tiptap 3 系列編輯器＋Client AI Toolkit＋持久 Tracked Changes；agent 主線優先 LangChain create_agent／LangGraph。**

- 理由是 Tiptap 有模型讀改工具及執行結果，LangChain 有工具循環、middleware、runtime 注入與前端執行接點；不是因為要保存舊程式。正式取相容版本，不能各自升 latest 後假設互通。[F01–F03](2026-09-09-jd-editor-framework-comparison.md)、[R05–R10](2026-09-09-jd-ai-app-runtime-official-evidence.md)
- 本機 embedded client 路徑優先，不先把 JD 送往 Tiptap Cloud；仍須核對付費套件授權、啟動驗證及部署條件。Beta／Alpha 是真實風險，不宣稱全套最成熟。[官方部署選擇](https://tiptap.dev/docs/ai/ai-toolkit/overview)
- 若採 Python agent，工具 schema 由同版本 Tiptap 官方工具 definitions／CLI 產生，透過 LangChain headless pattern 交 browser toolkit 執行。若選全 TypeScript，可用 Tiptap 官方 LangChain.js 工具定義；**這是不同接線選擇，不同時再跑兩個 agent loop。**Tiptap 該頁示範 bindTools，不是完整 create_agent／headless 端到端成品，仍須對齊 LangChain 正式執行接點。[官方非 TS 後端](https://tiptap.dev/docs/ai/ai-toolkit/client/advanced-guides/non-typescript-backends)、[官方 LangChain.js 工具](https://tiptap.dev/docs/ai/ai-toolkit/client/agents/tools/langchain-js)
- Python／JS 相容版及本機 transport 尚待最小接線確認。若這段比全 TS 複雜很多，先比較，不為沿用語言硬加另一層通用協議。

### 備選而非同時堆疊

1. **CKEditor Track Changes＋DocumentCompare**：若 Tiptap 無法可靠承接待審編輯，或授權／成熟度不適合，優先比較。其文件快照→外部處理→內建細粒度差異是不同、合理的修改路線；不是一定要 LLM 自己寫 patch。仍須通過相同審核測試。[F04](2026-09-09-jd-editor-framework-comparison.md#f04-ckeditor持久審閱有直接契約新-ai-patch-路徑另有風險)
2. **Plate／底層自訂接線**：前兩者具體不適用、且願意承擔更多維護才考慮。不能為避免付費而忽略審核正確性的開發成本。[F05](2026-09-09-jd-editor-framework-comparison.md#f05-plate可擴充底座不等於完整持久-ai-審核)

OpenAI Agents SDK 是正式 runtime 備選；具工具循環、continuation、tracing 等功能，但不自動解決上述 editor 的部分失敗及審核缺口。也不需要 OpenAI SDK＋LangChain＋Vercel 各包一層。SDK 的 provider 支援與原生 Responses 功能另核對，不因更換 SDK 就承諾所有 key 都有完全相同能力。[R03](2026-09-09-jd-ai-app-runtime-official-evidence.md#r03-openaisdk-接循環不替-app-寫產品政策)、[OpenAI Models](https://developers.openai.com/api/docs/guides/agents/models)

## 3. 端到端流程

```text
員工訊息／編輯意圖
    ↓
主顧問：既定對話延續＋相關 Memory＋目前 JD 可讀內容＋工具定義
    ↓
需要編輯才呼叫原生 read → edit
    ↓
編輯器：定位、結構檢查、套用為待審、產生實際結果
    ↓
應用保存目前文件＋修訂資料 → 結果回到同一個 agent loop
    ├─ 有錯：按實際結果重讀／修參數／停止；不能假稱完成
    └─ 成功：回答員工；文件顯示待審
                             ↓
員工直接編輯／接受／拒絕 → 保存同份目前文件
                             ↓
下次 AI 讀到當下最新內容與必要變更資訊
```

這是三個執行責任，不是三個新 Agent：主顧問判斷內容；編輯器做操作與修訂；應用接保存、權限與回傳。既有背景 Memory 整理不因此變成 JD 的第二個編輯者。

### A. 主顧問看到什麼

- 延續已核對的 conversation／reasoning／compaction 接法，不另造重複對話歷史。近期訊息、Memory 導覽／相關內容、已發生工具結果與本輪訊息按既有 context 工程管理。[R03、R10](2026-09-09-jd-ai-app-runtime-official-evidence.md)
- JD 讀取必須包含**目前有效的最新內容，包括 pending 的新增／修改**。供審核顯示的舊刪除文字，要能與目前內容區分，不能讓 AI 當成兩項都還有效的工作。
- 具體工具 read 是否能提供這個視圖，是驗證項，不先假設 `getText()` 或 `getJSON()` 自然正確。版本、範圍、選取位置由 runtime／編輯器給，不能叫模型自行推算。
- JD 很小可先完整讀取；變大按範圍讀。日常改一項不必全量重分析，但整體完成檢查需另盤點全文件及相關工作理解。沿原本能力需求，不在此新建檢索系統。
- 排版和操作規則精簡固定；專業分析／寫作方法按需要使用既有研究轉成的 Skill。不要求模型回報 skill ID、生成來源 UUID、完整抄對話或填所有欄位。

### B. 模型怎麼改

先使用 **三個現成文件工具**：read、edit、readSelection。它們是文件操作，不是三次固定呼叫，也不含目前 Memory 工具數。comments 等非必需工具先不開。工作內容拆分由一般操作組成，不新增 duty_split／task_merge 專用工具。[F01](2026-09-09-jd-editor-framework-comparison.md#f01-tiptap-的兩種接法不能混拼)

- 模型填「已讀到的目標＋新內容／操作」。完整 schema、定位語法、可用操作以鎖定版官方 definitions 為準；不從網頁範例手抄一套簡化文法。
- 文件 ID、作者、呼叫 ID、版本、是否待審、保存位置及權限由應用注入，不讓模型填，也不讓模型有 accept／approve 工具。[R06](2026-09-09-jd-ai-app-runtime-official-evidence.md#r06-langchain既有參數注入工具格式及前端執行)
- 說明「為什麼改」是模型可產生的簡短內容；如何關聯審核範圍沿框架 metadata／正式接點驗證，不為此先裝完整 Comments 系統。接受後不要求保留成 JD 正文，也不新增人工拒絕理由欄。
- read 出現同句、多個近似節點或過時目標時，應回查與重新定位，不發明 fuzzy matcher。框架仍可能使用內部 position／hash；**重點不是禁止任何數字，而是不叫模型憑空計算、猜測或把暫時定位當永久 ID。**[R01–R02、R09](2026-09-09-jd-ai-app-runtime-official-evidence.md)

### C. 執行與保存

瀏覽器有 editor 實例時，優先由它執行原生 client 工具。server 的 headless interrupt 只是「等待前端完成工具」，不需員工點選，亦非內容已審。模型續跑前，工具結果必須已回送。[R06、R10](2026-09-09-jd-ai-app-runtime-official-evidence.md)

第一版先不將未生成完整的 operations 邊流邊寫入 JD；聊天與處理狀態仍可串流。框架套用後，應用依其 serialization／adapter 保存**目前文件及必要修訂 metadata**，保存失敗要如實表示，不能把畫面已變當資料已落盤。[F02–F04](2026-09-09-jd-editor-framework-comparison.md)

本機同一文件在這段期間只有一個寫入者；UI 唯讀不等於後端安全驗證可省略。關頁時不暗中補建另一個 server editor：未執行呼叫按正式暫停／取消語意處理；已執行但結果未知則先查已保存結果再恢復，不重放新增動作。[R08](2026-09-09-jd-ai-app-runtime-official-evidence.md#r08-框架恢復不是外部寫入的-exactly-once-保證)

## 4. 文件、格式及審核怎麼保存

### 一份工作文件，不是兩份各自可編輯的 JD

建議以編輯框架正式序列化資料作目前文件載體，含必要追蹤標記；框架要求外置的 suggestion／作者 metadata 則按 adapter 配套保存。它們合起來是一個文件保存單元，不是第二份可獨立編輯的權威 JD。確切資料庫及同步交易機制待所選套件通過驗證後設計。

「只看已接受內容」是視圖／匯出投影要求，不因此另立第二份人工維護文件。框架若沒有可靠的 clean／accepted projection，須列為缺口；不可只刪紅字、保綠字就當已核准。

### 有結構，但不是讓模型填巨型表單

沿 C01 的內容結構，用 editor schema／標題、段落、清單和必要的業務 metadata 表達。先用原生節點能表達的範圍；必要自訂節點才擴充，並測 AI 讀寫、審核與序列化全鏈路，不只測畫面。

任務內容、結果／標準、適用條件保持完整敘述；視覺分組不等於必須逐欄新 API。字型、間距、OPKS 區分與印刷樣式由 UI／樣式管理，不讓 LLM 產生 CSS 或重畫頁面。新增內容不應因不完整就被悄悄捨棄。[C01](2026-09-09-jd-document-relationships-working-research.md)、[欄位指南](2026-09-09-jd-field-and-writing-guide.md)

### 審核分組是目前最重要的缺口

**不等號要保留：**一個 tool call ≠ editor transaction ≠ undo batch ≠ 一個員工決策 ≠ DB transaction。

可先探索的接線是：使用原生 suggestions 作實際修訂單位，應用將相關 suggestion 身分關聯為同一審核範圍；接受／拒絕仍呼叫框架正式命令，不用整文件舊快照回退。群組身分由 runtime 產生；哪些修改語意相依由主顧問判斷、讓員工看清楚，不加額外判斷 Agent。

**以上是候選 Mapping，尚非可保證的演算法。**要證明原生 suggestion 身分／lineage 足以追蹤後續人工修改、block 改動、跨位置刪增，且整組操作不漏內層 pending。Tiptap 目前只有 inline nesting 明文，接受外層不會自動接受內層；CKEditor multi-range 也不涵蓋任意異質群組。[F03–F04](2026-09-09-jd-editor-framework-comparison.md)

因此第一個隔離驗證必須直接包含人改 AI、跨位置移動及組外修改，不能只展示改一句成功就宣稱整體完成。**若需自行重做映射／回退引擎，先停下比較 CKEditor 或與 Owner 討論產品取捨；不以「薄接線」淡化實際工作量。**

## 5. 錯誤與重試：只接一套流程

| 情況 | 應用／框架處理 | 回到模型的必要事實 |
|---|---|---|
| 參數型別錯、目標不存在、讀取過時 | 官方 schema／tool error 接點；要求讀取或修參數 | 哪個操作、哪個目標失敗；目前能採取的下一步 |
| 內容不符 editor schema | 不把被剝掉的內容當成功；沿驗證結果修正 | 哪種節點／屬性不合法、是否已有其他內容套用 |
| 可安全重試的暫時連線問題 | 限定的 retry middleware／退避 | 成功結果或耗盡後的真實失敗；不多層重試 |
| 文件改了，但保存失敗 | 不回「已保存」；保留可辨識的未保存狀態／恢復入口 | 套用與持久保存的差別，不假裝都完成 |
| 回覆失聯、不知寫入是否已完成 | runtime 呼叫身分／已有結果核對；不能盲目重播 | 已有結果，或明確 unknown，接著先讀取 |
| 部分操作成功、部分失敗 | 原結果留存；重新讀目前文件再修未完成部分 | 已套用／失敗範圍，不只一個模糊 false |
| 錯誤持續無法修正 | 有界結束、誠實報告、解鎖可恢復操作 | 不說完成；不讓聊天框永久只能重試 |

前五類主要沿 [R04–R08](2026-09-09-jd-ai-app-runtime-official-evidence.md)；部分成功有 [F02／F04](2026-09-09-jd-editor-framework-comparison.md)直接證據。傳給模型的細節應短而可行動，不把 stack trace、金鑰或完整內部環境當錯誤訊息。

**重要：**不是所有失敗都保證文件沒動。對單一語意決策的跨位置操作，如果框架可能套一半，必須在群組完整前避免接受半套，並驗證修復／取消能恢復完整性。如何形成可靠邊界是 I3 的硬門檻；本稿未假裝 middleware 或 beforeOperation 已提供整批 rollback。若要 staged copy／額外 transaction adapter，屬需提出實證及範圍的新接法，不能直接施工。

模型也不保證看到 error 一定重試；runtime 有呼叫額度與終止狀態，完成說明需依工具結果。語意錯誤不是 deterministic parser 能保證排除，仍靠專業方法與員工審核，不能把 schema strict 當真實性驗證。

## 6. 一個 LLM App 的必要責任如何承接

下表是跨官方契約整理的責任清單，不是聲稱所有 App 必須啟用每項功能或長相完全相同。

| 責任 | 本案承接 | 本輪不新增 |
|---|---|---|
| 模型及能力相容 | 單一 agent runtime／provider adapter；tool use、reasoning、輸出與 context 上限按實際 provider 核對 | 多套模型 SDK 彼此包裝；任意換 key 就等價的承諾 |
| Context／對話／Memory | 接既定有效內容，加入目前文件 read 結果；避免重複 history | 重造 Memory、另存一份內部思考或全輪塞全部 JD |
| 專業方法 | 訪談／JD 研究轉成精簡規則及按需 Skill | 每個欄位一 Agent、模型必填使用過哪些 Skill |
| 工具與結果 | 官方 tools／ToolRuntime／headless execution；完整 call-result 對應 | 自建通用 loop、模型填 runtime 已知資訊 |
| 可靠性 | error／retry／limit／恢復接點，區分可重試與需修參數 | 無限重試、所有 write 直接自動重送 |
| 可觀察性 | runtime trace：模型／工具／耗用／錯誤；應用記保存及審核結果 | 強制外部雲端傳送全文、要求模型自報成功紀錄 |
| 權限與安全 | 工具白名單、文件範圍限制、AI 無接受權、內容視為資料 | terminal／瀏覽器全機控制、任意檔案或網路執行 |
| UI 及可恢復操作 | 原生編輯、實際 tool state、autosave 狀態及待審；失敗解鎖 | 多人協作、所有進階狀態都放主畫面 |
| 品質檢查 | 先離線編輯情境及失敗注入，再少量真模型驗證 | 以文件研究冒稱產品已測；這輪不呼叫付費 API |

能力來源以 [R01–R10](2026-09-09-jd-ai-app-runtime-official-evidence.md)為準。安全／保存／審核等是 App 正常責任；可以使用成熟框架接點，但不會因接一個 SDK 就自動具有所有產品政策。

## 7. 可以怎麼開始，而不掉進無限設計

### 本次推薦的第一範圍（待裁決，尚未執行）

沿既有 I0／I1／I3 收斂成一個**能保存重開的待審文件小樣**，不另外起一套產品設計。第一候選仍是 §2 的 Tiptap 組合；只有具體不適用時才用相同情境比較 CKEditor。

1. **先確認能合法在本機驗證。**固定 editor／擴充版本及可用授權，確認原生 client 工具接點；尚不建立完整 agent transport。套件條件不成立就列明影響，不默認購買或使用外部文件服務。
2. **固定文件、固定操作，直接測審核效果。**以已同意方向的虛構 r2 為起點，將新資訊明標為測試輸入。用預定操作模擬 AI 修訂→員工改同一待審段落及組外段落→再次修訂；在分開的測試分支接受／拒絕，再保存重開。另驗跨位置移動／拆分，以及中途部分套用失敗。固定操作只隔離 editor 能力，不能稱為 LLM 已會編輯。
3. **交付結果與下一個選擇。**保留操作前後內容、未審狀態、接受／拒絕結果及重開結果，對照下方 I3 的 editor 情境逐項判定。人改 pending 不得自動核准、接受取最新版、拒絕不抹除組外修改、相依決策不能只接受半套。無法由原生接點完成就列為差距；不悄悄改需求或補做通用回退引擎。

第一範圍只包含 I0 的套件／本機條件、I1 與 I3 中可直接驅動 editor 的情境。I3 的 agent 權限、完整工具回傳／失聯恢復等跨接線項保留到 I2，不能因小樣通過便稱 I0–I3 全通過。此範圍不耗付費模型、不購買套件、不接 production；通過後才進入假模型工具接線，再另提 I4 真模型內容驗收與成本範圍。

### I0：相容性與授權（不耗模型）

確認可合法取得的 Tiptap／Tracked Changes 版本、Client Toolkit schema 產生方法、chosen agent transport，及是否能在本機執行。鎖定一組版本及官方範例路線，不同時做三套。無套件存取權即記明阻擋；不默認購買或傳送文件至雲端。

### I1：沒有 AI 先驗證待審文件

用固定內容＋固定操作測 editor／suggestions。**I1 不過，不接真 LLM**，因為換 prompt／模型不會修好保存及回退語意。

### I2：工具循環與錯誤

用假模型回傳預定 tool calls，接原生 read／edit／結果與 error。確認查找目標、部分失敗、保存失聯及恢復；再決定有無必要擴充。沿 headless 接點而非額外建 queue／workflow 系統。

### I3：C02 關鍵邊界

| 測試 | 通過所代表的效果 |
|---|---|
| 繁中、標點／換行、兩段相同文字 | 定位改對一段；找不到明確報錯，不猜位置 |
| 讀後目標已變 | 不以過時定位誤改別段；重讀修正 |
| AI 新增任務與多項細節 | 一起可讀、可編輯、可保存，不要求完整欄位才存在 |
| 人改 pending 的一句／新增子段落 | 不自動接受；接受時取得當下最新版 |
| 人改組外正常段落 | 按一般人工編輯保存，不被其他組接受／拒絕抹除 |
| 任務跨職責移動 | 兩端同一完整決策；不能接受半邊造成遺失或重複 |
| 一任務替換為兩任務 | 通用操作完成；相依內容整組，不新增專用 split 服務 |
| 同輪兩個不相關修改 | 可以分開審，不以 tool batch 強制捆綁 |
| 同一 pending 再被 AI／人修改 | 最新內容及說明一致；拒絕仍只處理該組 |
| block／自訂必要 metadata 修改 | 編輯、accept／reject、保存重開都不丟資料 |
| 批次中間一項失敗 | 知道已改範圍；不誤報完成、不接受半套相依決策 |
| 保存成功但 result 遺失，或重開 | 不重複套用；恢復目前內容及 pending，接受狀態不亂跳 |
| 已核准視圖與目前視圖 | 正確區分待審及刪除歷史，不把紅綠內容當兩份現行工作 |
| AI 嘗試接受、跨文件或文內指令注入 | 被應用權限／工具範圍拒絕，不靠模型自己守規則 |

### I4：才做最小真模型驗收

通過前述門檻後另提授權，用已有穩定設定先做「訪談→按需改文件→讀回→人改→續改」短情境，測定位成功率、修復次數、未變內容保留及成本；才延伸長訪談。這裡不另訂任意 4／8 步產品上限；按實測與 provider 限制配置，不新增背景審核 Agent。

若 Tiptap I1／I3 失敗，先記具體失敗與原生接點能否修正；必要時只拿同情境比較 CKEditor。若兩者都需大量自建，再與 Owner 討論群組體驗或擴充範圍，不把未完成行為藏到「以後優化」。

## 8. 目前尚需確認的只有什麼

| 問題 | 為何不是再泛泛研究一次 | 處理時點 |
|---|---|---|
| 相容版本／授權／本機 transport | 官方方案存在，但套件與語言契約需實際對齊 | I0；未授權不購買 |
| 人改仍待審及跨位置群組 | 官方有明確限制，不能只靠名稱判斷 | I1／I3；不過即比較備選或討論取捨 |
| AI read 的有效內容投影、資料 round-trip | framework schema 可以擴充，不代表讀寫審核自動無損 | I1／I2 |
| 部分套用與持久結果的安全邊界 | SDK 重試不等於文件原子交易 | I2／I3，必要擴充先提案 |

不重問已確認的 JD 定義、工作案例與任務的差別、Memory 分層、編輯不等於接受。只有新證據改變效果、成本或必要流程才翻案。

另有後續產品子題，並非本輪已決：刪除職責／任務時保留或連帶刪除內容、待審未決的匯出政策、具體 UI 與匯出排版。沿 C01／C02 再細化，不能把 editor 的 delete 命令當成已決定業務級 cascade；「已核准視圖」也不要求新增第二個編輯頁面。

## 9. 本輪交付與效力

本輪用設計討論方式固定 C01／C02 使用情境，再分 agent／editor 研究；來源只採官方，並獨立比較三個 editor。研究已發現並明示：工具格式並非統一、Tiptap tracking 關閉的人改行為、inline-only nesting、兩套框架可能部分失敗、付費及試驗性功能。沒有把這些包裝成「共識自動全覆蓋」。

**獨立審查（2026-09-09）：**Reviewer 全文核對本方案、F表及R表，針對原生覆蓋誤稱、C01／C02漂移、不同工具路徑混用、保存／核准／部分失敗、隱藏自訂引擎與官方連結，未發現實質 finding；明確限定為 G2 可交付，不是 I1／I3 通過或施工核准。主線亦重新讀取方案與證據，做文檔路由檢查；未執行 editor 或應用程式測試。

**近期進度核對的後續審查（同日）：**兩路唯讀複核提出四項問題。JD-C03-PROGRESS-01（P2，§0.1 實測歸屬）已拆分 CT49 完整訪談與 CT50 採用／補驗，移除該列未由這兩項驗收的恢復能力宣稱；02（P2，MEM-Q005）已改成未來 JD 接線且理解／候選通過各自驗證的條件句；03（P1，內容入口下一題）已將舊討論順序標為沿革，current gate 統一為第一候選與有限驗證裁決。04（P1，綠地邊界可能被誤讀）已明示設計自由與 production 施工效力的區別；不採 reviewer 建議的「僅不受已刪除模組限制」，因 Owner 明確要求不考慮舊產品／舊架構。主線回讀修訂並核對六份路由文件的 325 個本地連結、編碼及 Markdown；以上為文件驗證，不是 editor 或模型驗收。

**可以交付的是：整體推薦、可直接用的接點、必要 App 責任、未覆蓋處及有停止條件的驗證順序。**不是保證任何新技術天然最好，也不是已完成程式／UI／保存實測。正式採用仍需 Owner 審閱，後續依既定 G3→G4→G5／ADR gate 進行；不回接舊程式、不改現有 Memory／prompt／模型／DB，沒有付費測試或外部部署。
