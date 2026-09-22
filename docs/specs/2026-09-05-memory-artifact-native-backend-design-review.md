# Q017：中間產物採原生 StoreBackend 的接法審閱

> 2026-09-05 · **G4／流程效果已獲 Owner 暫時同意；②為可調整的研究接法，不是施工計畫**。
> 唯一問題：抽取產物的保存表示與 A／B reader。父稿：[三接法與引用接力](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#8-引用接力的框架覆蓋核對)；有效狀態：[register](../current-decisions.md)。
> 最新 Owner 澄清見[流程稿 §0.1](2026-09-05-work-understanding-memory-flow-working-design.md#01-owner-澄清流程效果必須達成實現方式不鎖死)：優先學 OpenAI 的目的／流程，再依框架生態及底層公開 API 接合；不鎖定引用格式或 reader 形式。下文 §0.1 的「待審」保留前輪說明脈絡，不再表示需 Owner 逐項選 SDK 接法。

## 0. 結論與研究邊界

**建議以②「Runtime 保存原生 StoreBackend 檔案，Agent 使用官方檔案工具」繼續設計。** 原因不是 Codex 使用 Markdown，而是本案已確認的使用方式——保存詳記、提供真實地址、B 列舉／補查、A 沿引用分段深讀——能直接使用同一組官方實作。尚無必要讓任意自訂 record 假扮檔案，也未出現一定要對詳記欄位做資料庫查詢的需求。

這個建議**沒有恢復先前①／③的優先序，也不表示 Owner 要求只能用②**。三者功能可以接近；②的優勢是既有讀取機制吻合、較少自行實作可造成漏讀的部分，不是已證明記憶品質或延遲最好。①／③的替代條件見 §4；選擇仍須符合流程稿 §0.1 的效果與研究要求。

已回讀現行 register／decision-process、單一訪談流程、框架官方事實圖、原文／摘要小元件、產物接力與整體組合提案。OpenAI 用途、引用 producer／consumer 沿用[已有研究](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)，不重做。這輪重新查官方開發頁並取得 Deep Agents 固定 source `4e5f9350e4d77b8bf19e472e8414662d3fa59dc0`，追讀實際呼叫鏈；不是只依 API 名稱或文件範例。

### 0.1 Owner 追問：回傳格式、保存表示與 OpenAI 流程不可混為一談

**本輪只是釐清，不新增選型。**「LangChain 結構化輸出」應讀作：**抽取 LLM＋抽取 instructions，由 LangChain 接收並解析結果**；不是 LangChain 自己理解訪談，也不是 Memory 引擎。外層少數命名欄位可以承載長篇文字，不代表把工作細節全部切成固定表單。`StoreBackend` 則在產物形成後提供保存／讀取表示，底下才是 LangGraph Store；回傳格式不決定保存位置，也不代表兩套 Memory。[官方 structured output](https://docs.langchain.com/oss/python/langchain/structured-output)、[官方 backend](https://docs.langchain.com/oss/python/deepagents/backends)

**OpenAI 事實與本案映射：**本輪重新取得 [Sandbox Memory 官方頁](https://developers.openai.com/api/docs/guides/agents/sandboxes#persist-memory-across-runs)及 [Codex local memories](https://learn.chatgpt.com/docs/customization/memories)，確認 extraction→consolidation 與未來逐層讀取；精確 Codex source 細節沿用[既有 artifact §4.3–4.5](2026-09-05-openai-memory-artifacts-to-framework-detailed-crosswalk.md#43-phase-1rollout_summaryrollout_slugraw_memory)及[引用 producer／consumer 研究](2026-09-05-memory-summary-routing-and-deep-read-source-review.md)，**沒有重新下載 Codex HEAD**。

- Codex 固定快照的抽取模型回傳 `rollout_summary／rollout_slug／raw_memory` 三個字串；Runtime 保存 Stage 1 DB record。這是少量欄位的回應封裝，不是要求每則知識填大量技術欄位；也不是所有 OpenAI Memory 產品固定不變的 schema。
- Phase 2 選取一批已存結果，同步候選／摘要及其真實來源位置，對照既有 Memory 與輸入變化；整併 Agent 按需補查摘要，再維護 `MEMORY.md`、相關引用與 `memory_summary.md`。它不是將每個 candidate 原樣追加到最終 Memory，也不是每次抽取後固定立即整併。
- 未來前台先用小型導覽、搜尋 Memory，足夠就停止；不夠再沿引用讀摘要，必要時查原始紀錄。既有 Codex Phase 2 的 summary-only 邊界不因此取消。
- 因此「抽取→保存→整併／引用→未來深讀」的責任形狀成立；**②將產物存為 StoreBackend 檔案，以及當次直接交接 parsed 候選，是本案尚待審的 framework mapping**，不能稱 OpenAI 原封使用此 DB／函式流程。Codex 的 DB＋檔案投影與 Sandbox SDK 的 workspace files 也不能混稱同一底層。

Closure：本輪補清表格過度壓縮造成的歧義；A/B/C 不變、②仍待審、未施工。下一個 gate 仍是表示／reader 的選擇；精確 extraction wrapper、schema、背景觸發與恢復另依原路由收斂，不以本次說明當作 Owner 核准。

## 1. 框架底層真正如何接力

```text
模型呼叫 read_file(已提供的 path, offset, limit)
  → FilesystemMiddleware 建立的 StructuredTool
  → 路徑檢查，Runtime 注入；不要求模型填 Store scope
  → CompositeBackend 依路由移除外層 prefix
  → StoreBackend 以 namespace＋key 呼叫 BaseStore.get／aget
  → FileData → ReadResult：內容窗口、總行數、續讀位置或錯誤
  → FilesystemMiddleware 加行號／大小限制／續讀提示
  → ToolMessage 回模型，由 create_agent 繼續工具循環
```

這是所讀官方程式的呼叫鏈；其中使用哪個 namespace、提供哪些可見工具與內容，是應用配置。原生檔案存於 Store item 的 `content／encoding` 等資料，不要求真實作業系統檔案。`read` 先取完整 item 再切窗口；不能稱資料庫只讀了返回模型的幾行。[StoreBackend 保存／讀取](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L100-L228)、[read](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L366-L470)

**兩個容易接錯的實際細節：**

- 路由前的模型地址與 Store key 不必相同。例如外層 `/notes/a.md` 路由到 `/notes/` backend 後，key 是 `/a.md`。Runtime 若繞過 Composite 寫入卻仍使用外層地址，後續 reader 可能找不到。建議 producer 經相同路由規則保存，以成功回傳的外層 path 交給模型；可信 writer 與只讀 reader 可以配置不同權限，但地址映射相同。[prefix 轉換](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/composite.py#L195-L225)、[write 還原外層地址](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/composite.py#L708-L738)
- Backend 的窗口與最後模型看到的窗口可能不同。官方 middleware 在大小限制再次截斷後，會重新計算續讀位置，避免跳過未展示的行；缺檔／讀取錯誤回成 error ToolMessage。**直接重用，不複製其 private formatter。** 一行超長等情況仍可能要求縮小／調整讀取；有此機制不等於任何內容一次全部送達。[窗口處理](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L929-L1036)、[模型結果與 reader](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1906-L2064)

模型不填 ReadResult、ToolMessage、DB namespace 或查詢時間；這些由框架／Runtime 產生。讀檔只提供資料，沒有另一個「reader LLM」。

## 2. 建議如何保存我們已討論的內容

以下是**待審接法，不是最終檔名或模型 schema**：

| 內容角色 | 建議表示／產生者 | 使用者與目的 |
|---|---|---|
| 訪談詳記 | 原生文字／Markdown 檔；模型整理正文，Runtime 加來源位置 header | A／B 用原生 read／list／grep；正文相關主題直接引用其地址 |
| 工作資訊候選 | 另一份原生 UTF-8 產物；如抽取契約是結構化值，由 Runtime 用標準 JSON 序列化保存 | B 本次直接使用已解析結果；恢復／重用時用 backend 完整讀取。不是再叫模型填一次存檔工具 |
| 工作理解正文 | 既定 StoreBackend 可修訂文字文件 | B 整併、C 局部修補；A 搜尋／深讀。仍不是 JD Task 表 |
| 小型工作理解導覽 | 同類文字文件，由 B 隨正文調整 | A 的 model hook 讀取注入；不是另一個摘要 Agent |
| 原始訪談 | 不改存放者，仍由既有主對話 messages／Checkpointer reader 讀取 | B1 抽取及 A 精確回查；不為檔案工具再複製原文 |

**候選的 JSON 是保存表示，不是要求增大模型輸出。** 既有抽取回應中的詳記／候選可以維持既定語意；是否字串、列表等精確抽取 schema 另行收斂，Runtime 保存不要求模型新增 ID／時間／source-ref／Skill 欄位。若最終候選本來就是文字，原生文字檔也可承接，沒有強制將它拆成 records 的理由。

**來源引用存進內容，不偷塞未支援 metadata。** FileData 的公開內容／encoding／時間欄位，不包含自訂 provenance；StoreBackend 的轉換只保留已知欄位。因此詳記開頭放 Runtime 提供的可讀來源定位；候選保存同批詳記地址及來源關係。這些是文件內容／序列化 payload，不是覆寫 private conversion，也不是新增引用資料庫。source locator 的精確格式仍未准。[FileData 契約](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L187-L245)、[Store conversion](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L170-L228)

Runtime 可在 graph 外用顯式 Store 與不依賴缺席 Runtime 的 namespace factory 保存；Agent 執行中則由可信 context 解析同一文件 scope。不要直接拿 B 的技術 thread ID 當 Memory scope，否則會與 A 分成兩份。也不能照抄官方較舊範例中的空 `StoreBackend()`：所查 constructor 要求明確 namespace。[官方 namespace factory](https://docs.langchain.com/oss/python/deepagents/backends#namespace-factories)、[constructor／graph 外行為](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L100-L168)

## 3. 保存、交接、讀取與限制

### 3.1 不多叫模型、不新增同內容副本

1. B1 使用公開 structured-output 接點取得詳記及候選；解析／修正策略仍依[既有比較 §2](2026-09-05-memory-extraction-artifact-framework-handoff-review.md#2-抽取有現成小元件不必讓模型兼做存檔)。
2. Runtime 加入本次輸入位置，經 backend 保存可再開啟的產物；檢查實際成功／錯誤。
3. 直接把手上候選及真正可讀的詳記地址交給 B2。不為了兩階段再從 DB 讀同一份，也不把引用只放在模型看不到的 artifact。
4. B2 使用官方工具讀工作理解／選中的詳記，編輯正文並更新導覽；相關詳記引用放在知識旁。如何分類與引用是整併 prompt 的工作，框架不自動建立語意關係。
5. A 從導覽／正文查到詳記地址，以同一個 reader 開啟；若需要原句，再沿詳記 header 呼叫原文 reader。**不是從詳記再繞讀候選才可查原文。**

保存／完整讀回可使用公開 `write/awrite`、`download_files/adownload_files`。後者讀既存 bytes，不自動生成新摘要；候選重用的程式讀取可避免誤拿附行號的 ToolMessage 當 JSON。一般 `write` 可能覆寫同 path，這不是 immutable store；不得自行宣稱 append-only、兩檔原子交易或 exactly-once。[寫入](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L428-L470)、[完整 bytes 讀取](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L689-L719)

### 3.2 原生工具能限制多少，何處仍需公開擴充

**[新補核官方能力]** standalone FilesystemMiddleware 的公開 `tools=[...]` 可以只註冊 read／ls／glob／grep 等必要工具；不是額外呼叫模型選工具，被排除的工具不進其可分派清單。但此 allowlist 是**工具層**，不能表達「edit_file 可改理解、不可改詳記」。[官方使用範例](https://docs.langchain.com/oss/python/langchain/middleware/built-in#file-system)、[constructor 與註冊](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1668-L1792)

因此 A/C、B2 同時具有不同目錄讀寫權時，仍建議用官方 backend subclass／wrapper 接點保護抽取產物；其讀取／搜尋沿用 StoreBackend，**不另寫 record→filesystem 的轉譯引擎**。Runtime 的可信保存入口與 Agent 的只讀入口共享內容，不共享修改權。只拒絕實際可到達的修改入口，涵蓋 sync／async；不一律先造所有方法，也不依賴 private `_permissions`。[官方 policy hooks](https://docs.langchain.com/oss/python/deepagents/backends#add-policy-hooks)

能力有 backend 差異：固定 StoreBackend 沒有實作 `delete`；Composite 雖暴露 delete，遇不支援的子 backend 會回錯誤。故不能只看工具清單就說原生檔案全 CRUD 都能用。詳記這輪只需模型讀取；Memory 整檔淘汰若需要 delete，另依其用途討論公開 Store.delete 等接法，不偷偷新增通用刪檔服務。[delete 是可選能力](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/protocol.py#L722-L752)、[Composite 實際處理](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/composite.py#L778-L807)

### 3.3 搜尋與 Context 副作用不能略過

- **原生 grep 是 literal text matching，不是向量或自動相關召回。** StoreBackend 的 ls／grep／glob 先分頁取 namespace 下的 items，再本地處理；grep 的 max_count 是結果限制，不會自動減少先前 Store 掃描。本案可用同一 Store 的獨立 scope／路由區分 current Memory 與詳記，避免平常只查正文卻總掃詳記；不把此配置說成新資料庫或已准 namespace schema。[pagination／ls](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L230-L364)、[grep／glob](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/backends/store.py#L593-L653)
- `grep(path=...)` 可限制模型查找範圍；跨 Composite 根查詢可能觸及多 route，不能依目錄名字承諾查詢成本。少量自動召回仍是未完成的 Context 接線，**本案②沒有取代它**。Store 若另配置 embedding index，寫入是否產生 embedding 成本也須核對，不能籠統稱所有存取零模型費用。[Store indexing](https://docs.langchain.com/oss/python/langgraph/stores#semantic-search)
- Middleware 不只有工具：大型 HumanMessage 可以被 offload；所查路徑保存的是加路徑標記、內容仍完整的 state message，預覽只替換 model request。這不等於刪除員工原文；但證明只裝檔案工具也須核對內部 offload 路由與 Context 配置。這輪不因此選定 compaction／門檻。[完整內容仍在 state](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L1577-L1598)、[tag 與 request 處理](https://github.com/langchain-ai/deepagents/blob/4e5f9350e4d77b8bf19e472e8414662d3fa59dc0/libs/deepagents/deepagents/middleware/filesystem.py#L3281-L3410)

## 4. 三選項比較與推薦依據

| 面向 | ① Record＋只讀檔案視圖 | ② 原生 backend 檔案（建議） | ③ Record＋專用 reader |
|---|---|---|---|
| 既定引用／A/B 深讀效果 | 可達到；需實作轉譯 | 可直接沿 path、原生列舉／分段讀取 | 可達到；需把 B 列舉／查找也接齊 |
| 程式處理產物 | 結構可直接 get | 當次 parsed 值直接交接；重用取原生 bytes／解析 JSON | 結構可直接 get |
| 主要自訂面 | path、render、read／list／search、錯誤與分頁 | 產物組裝、來源位置、讀寫政策配置 | 目錄／搜尋／精確 reader 的工具契約與呈現 |
| 風險／成本 | 自訂 view 漏讀／邊界；底層查詢仍要設計 | 檔案掃描成本、兩產物交接／恢復、Deep Agents Beta | 精確讀取不等於全文查找；長結果控制須接合 |
| 何時更合適 | 已有不可改的 canonical records，仍需統一 filesystem | 主要 consumer 本來就是模型讀文字、沿引用查找 | 主要需求是固定欄位查詢、結構化 API 或特定檢索 |

比較是依功能與已知實作的**組合分析**，不是 vendor benchmark。②仍使用同一 BaseStore，並未多存一份原生 record 再同步一份檔案；框架如何物理序列化是另一層。若未來需要詳記欄位查詢，或測得掃描成本不可接受，可重開①／③或替換 backend。保留內容及引用即可作後續轉換的基礎，但不能承諾更換表示完全零遷移。

**為何這次可以推薦：**已按寫入、Runtime 地址、內容保留、工具註冊、路由、Store 查詢、ReadResult、ToolMessage 追過資料流；沒有靠假設 A 遺失引用而增設全庫搜尋。②不新增模型步驟，保留詳記／候選的不同用途，又重用原生讀取機制。其缺口不比另兩方案憑空消失，但不必為尚未存在的欄位查詢需求先做更大的 adapter。

## 5. 明確未完成的責任與下一步

以下**不是此方案已自動完成的功能**：

1. 原始問答的精確 locator／輸入窗口／保留政策；公開 graph reader 已找到，接線尚待收斂。
2. B 的觸發、已處理範圍、兩產物部分寫入後如何恢復；不是 StoreBackend 提供 transaction／scheduler。
3. B/C 同時修改正文／導覽的協調與失敗恢復；沿用 Q018，不以原生 edit 的字串匹配冒充 CAS。
4. 最新導覽載入、少量自動召回、Compaction 與工具 offload 的組合；保留已有 Context 要求，不因選表示就當完成。
5. 內容 instructions：哪些資料值得抽取、如何留案例差異／未知資訊、去重與維護引用。框架提供執行，不替我們研究職務分析方法。

Owner 已同意目的與流程，可依②研究接法繼續細化，不再重問是否必須採某個表示。依原定順序收斂原文／Context 接點、B 生命週期、Q018；已有證據能回答的提出具體接法與取捨，不重做名詞研究。若改變流程效果或觸及未決協調，仍須討論；不是批准所有 schema 或開始施工。

### Closure

- **Status：**source-backed recommendation，②可繼續細化但不鎖死；①／③仍備選。Owner 同意的是流程效果及等價實現原則，A/B/C、單文件隔離及根 create_agent 不變。
- **自訂範圍：**內容／引用交接與官方政策接點，不自製 Agent loop、儲存引擎、檔案分頁或通用搜尋器；不宣稱「整套零自訂」或「所有大廠底層一致」。
- **驗證範圍：**官方頁＋固定 source review，未安裝／執行此組合、未付費模型測試、未改 production、未 commit／push。所查 API 為同日既有最新版本研究的快照；部署前仍需鎖相容 release。
- **後續最小相容性檢查（尚未執行）：**Runtime 寫的外層 path 經 Agent 能讀回；長中文內容續讀不漏；只讀產物的實際修改入口受限；A/B 共用同文件 scope 且不串到別份文件。這些可先不用 LLM 驗證機制，不用再做大型品質實驗來選資料表示。
- **文件路由：**本稿只持有底層證據與②建議；父稿保留三方案／歷史校正；register 記有效狀態，Owner 等價實現原則只由流程稿 §0.1 持有。其他未決責任不搬進本稿重寫。
