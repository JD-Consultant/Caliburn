# JD App 接線設計候選：文件、操作、保存與人工續編

**2026-09-10 active語意契約v2：**Owner已同意Task成果／要求平行分組、K／S引用及原生JSONB＋同PG保存方向。[語意契約與有限驗證](evidence/2026-09-10-jd-semantic-contract-closure.md)固定新grammar、模型refs／保存IDs及首次建立；本文件active設計已同步v2。v1及F01／F02的實測紀錄保留其舊範圍，不能代稱新增關係已完成runtime驗收。

前次格式確認及v1無共享引用的診斷見[保存研究](evidence/2026-09-10-jd-semantic-relations-storage-audit.md)；已由v2具體補正，不再等待同一產品決定。尚未完成的原生／DB／DOM／真模型項目仍依六切片逐項驗收。

**核心設計交接完成（2026-09-10）：**正式 profile、[工具及 schema](2026-09-10-jd-editor-contract-schema.md)、保存／單畫面／既有顧問接點與[六切片計畫](../plans/2026-09-10-jd-editor-core-implementation.md)完成獨立審查；人工失敗候選保留及首次 selection capture 兩項 P2 已關閉。schema 最終 85 defs 的[限定離線核對](evidence/jd-contract-schema/schema-validation.md)通過；provider 原格式接法只驗到本地 SDK 序列化。這是核心設計／隔離施工交接，不是產品實作或 production G6 通過。下方較早待定／待收斂紀錄依本條及 register 讀取；真人交付 PARKED，ADR0073 仍 Proposed。

**Owner 最新裁決（2026-09-10，G3／WORKING）：**同意 §9.1 核心接線推薦，並明示「先不用做真人交付核對」。前景 AI 暫停手改及同 PG 唯一 JD 保存已是後續設計依據；真人交付／核對與 HTML／DOCX 問答交付包延後，不列本版驗收／施工。以下交付內容保留為 PARKED 設計，不能因仍有正文就接入產品。Memory／原文回查保持既有功能，正式契約及 ADR 仍需收尾，未修改 production。

**2026-09-10 本單位結果：**[F02 官方插件四組實證](evidence/2026-09-10-jd-official-profile-probe.md)第二輪 4／4、15 項斷言通過；首輪 1／3 的子程序輸出缺檔失敗保留。這補上官方清單／表格及原生格式操作的 JSON／新程序證據，未驗 DOM／IME、API 或真模型。工具接口的三項缺口已收斂，[匯出附件](2026-09-10-jd-export-and-consultant-handoff.md)已齊；[§9.1 整體評審包](#91-整體接線評審包)集中呈現人工暫停、保存與交付取捨。以下較早「尚未新增實驗」等語句是當時紀錄，不取代本條；停止追加微型探針，下一步依 register。

**2026-09-10 收斂：**[§8.1](#81-同一工作畫面owner-釐清)記錄同一畫面、唯一可編稿；[Proposed ADR 0073](../adr/0073-plate-jd-app-working-document-and-revision-authority.md)具體提出唯一 JD 保存 owner 及舊 JD writers 的取代範圍。[§5.4](#54-保存資料的具體約束)與[§7.1](#71-寫入交接與取消的明確接點)補齊有限資料與實際 runtime 接點。[正式 profile 附件](2026-09-10-jd-plate-document-profile.md)定義官方插件／grammar／renderer，[工具附件](2026-09-10-jd-app-tool-contract.md)承接讀寫／來源／重播語意；兩附件的具体範圍優先於本文較早的候選簡表。這是設計收斂，未執行 migration 或新增實驗；尚未稱 S5／production 完成。

**最新狀態：**Owner 已明確選擇「持續工作稿，保留差異與更正（建議）」，採[審閱工作稿 §7.7](2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正) 的 B 為 WORKING 方向。正文主路線為 **clean authoritative working value＋綁定真實 actual_changes 的不可變 revisions**；人與 AI 接續同份最新版，不再要求個別 pending accept／reject 或 accepted projection。Plate、人工與前景 AI 的互斥及保存路線 B 已同意；真人交付延後，正式契約與 successor ADR 仍需收尾。原生 diff／history 反例及 pending／codec 研究保留為歷史證據，不因流程改選而改判。

2026-09-09；JD-R002/C03，連動 C01／C02。**審閱 B 與 Plate 底座為 WORKING；其餘為可評審接線候選，非已採用 schema、production 設計或施工授權。**承接[框架候選](2026-09-09-jd-editor-framework-decision-candidate.md)，狀態與下一題只由 [register](../current-decisions.md)維護。本文把已查清的原生能力落成具體責任與失敗契約；本次同意與仍未決的範圍集中在 §9。

## 1. 推薦組合與證據效力

核心的機器可讀邊界見[JSON Schema 與消費者附件](2026-09-10-jd-editor-contract-schema.md)，交接見[六切片施工計畫](../plans/2026-09-10-jd-editor-core-implementation.md)。[官方契約複核 §2.13](evidence/2026-09-09-jd-app-tool-and-review-contracts.md#213-契約定稿前的官方複核參數結果版本與重試)區分文件驗證、provider 參數、工具結果與交易保證；本機 schema 驗證不能取代真實 provider binding 驗收。

2026-09-10 [全流程責任與證據稽核](2026-09-10-jd-responsibility-and-evidence-audit.md)引出的補正已落入工具 §4.3／§6、同一 SSOT、[模型參數附件](evidence/2026-09-10-jd-model-input-contract-closure.md)、[錯誤策略](evidence/2026-09-10-jd-error-recovery-contract-closure.md)及[保存約束](evidence/2026-09-10-jd-storage-contract-closure.md)。模型只填一次來源及單一 span 意圖，App 承擔推導／驗證與恢復；設計閉合與尚未實作的整合能力分開，不重開已同意的產品方向。

推薦 **Plate 原生結構文件＋既有 Python 顧問工具＋本機無持久副作用的 Node 編輯運算＋同一 PostgreSQL 內唯一 JD 文件交易**。人與 AI 使用同一份乾淨工作稿；保存後的 working revision 是後續編輯、閱讀及比較的權威基底。每次實際改動與其前後版本固定綁定，後續更正產生新版，不改寫較早紀錄；保存不等於員工批准或專業品質通過。原文、理解與 Memory 流程沿既有成果，JD 編輯不兼任 Memory。文件保存採 §5 的 B／WORKING，A 作有反證時的替代；**保存路線 B 與審閱流程 B 是不同決策，目前兩者均已取得方向同意**，正式 schema 與 production authority 依後續 gate 完成。

這不是 OpenAI 或 Anthropic 公開了相同內部架構。兩家的共同可觀察基礎是：工具有明確說明、App 提供可讀狀態、模型提出操作、App 執行並回傳真實結果，失敗後可重讀／修正；不同定位介面仍並存。此处的結構節點及本機程序是本案映射。[OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling)、[OpenAI apply patch](https://developers.openai.com/api/docs/guides/tools-apply-patch)、[Anthropic text editor](https://platform.claude.com/docs/en/agents-and-tools/tool-use/text-editor-tool)。Codex／ChatGPT 與 Claude 的現行產品能力、模式與沿革已分列於[官方證據 §2.6–2.9](evidence/2026-09-09-jd-app-tool-and-review-contracts.md)，不能從產品介面推定未公開的保存或拒絕演算法。

| 已有證據 | 能支持 | 不能代替 |
|---|---|---|
| [原生 probe](evidence/2026-09-09-jd-native-editor-probe.md) | 固定結構、原生操作、JSON 保存重開及兩個 diff 反例 | DB 交易、模型定位、所有 schema／貼上／人工輸入 |
| [完整 r2 呈現](evidence/2026-09-09-jd-native-editor-ui-probe.md) | 完整正文、真表格／子清單、同 ID 刪增呈現、保存材料重開 | 所有業務 metadata 已可讀、正式 editor 或真人試用 |
| [原生 history／同步](evidence/2026-09-09-jd-native-history-and-sync-probe.md) | 分批接點、固定 ID 配置及危險反例的實際內容結果 | DOM／IME、任意 mixed batch、正式 profile 或 DB 保存 |
| [P01 固定保存](evidence/2026-09-09-jd-native-save-probe.md) | Python→Node、完整 r2／新程序重開、過期與錯基底、交易回滾、commit 後 writer 退出／回執查回的六組實證 | 同步並發、實際 Agent 身分綁定／來源查證、正式人編或完整工作稿流程 |
| [F02 官方插件](evidence/2026-09-10-jd-official-profile-probe.md) | 完整 r2 的官方清單／表格組合、插字及原生增刪列、Task 移動／unwrap、canonical JSON 重開；固定格式 operations 的普通 JSON 及新程序 apply | 全 grammar、DOM／IME、剪貼簿、所有表格操作、API／來源 owner、任意歷史比較或全部 operations |
| [既有顧問接點](evidence/2026-09-09-jd-app-tool-and-review-contracts.md#210-既有-python-顧問與-javascript-原生編輯器接線) | LangChain tools／ToolRuntime、錯誤及已研究的來源／操作對帳原則 | JD 寫入已接妥或 CT49–51 已驗 JD 品質 |

實證固定 `platejs@53.3.11`／`@platejs/diff@53.0.0`，授權依[逐套件證據](evidence/2026-09-09-jd-oss-plate.md)。新增必要套件須逐一核對版本／授權，不以 monorepo release 號推定 package 版本。以下型別與欄名是評審用具體候選，正式跨語言契約依 [contract strategy](../contract-strategy.md)由單一 JSON Schema 生成，不能各端手寫一份。

### 1.1 採 Plate 後，哪些工作仍需本專案完成

Owner 已同意 Plate 文件底座方向；這表示不從零重寫文字／結構編輯器，不表示 JD App 不需開發。分工依[官方與本地核對](evidence/2026-09-09-jd-app-tool-and-review-contracts.md#211-plate-與-deep-agents-的分工不用從零造編輯器app-接線仍必要)：

| 責任 | 由誰承接 |
|---|---|
| 文件樹、文字與結構編輯、選取及原生操作 | Plate 免費核心與已核對擴充；按固定 profile 接線，原 diff／history／pending 反例保留 |
| 訪談、工作理解、何時撰寫及要修改什麼 | 既有顧問／Memory 與 JD 方法；維持 LangChain create_agent，沿用已採的 Deep Agents 公開元件 |
| 讓模型讀取／使用 JD App | 本專案提供有限 JD tools，交給同一既有 agent 呼叫；不另建主 Agent |
| JD 節點／畫面、版本／引用檢查、保存、錯誤結果與完整變更可查 | 本專案必要整合，優先使用現成 OSS 與正式接點；它們不是 Deep Agents 自動生成的產品契約 |
| 持續工作稿、歷次實改與更正 | 本專案接妥同一 clean value、不可變版本與 actual_changes、前後查閱及更正保存；個別待審結算、accepted projection 與 pending codec 不列為現行必需 |

Deep Agents 在此是顧問側的可用元件，不是 Plate 替代品；其通用 edit_file 或工具批准不能直接充當結構 JD 的審閱模型。開發時使用 coding agent 協助寫接線程式，也不改變上述責任或把自製程式變成框架原生能力。

## 2. 文件格式：業務內容在文件中讀得到

### 2.1 保存表示與內容容器

主路線保存一份 **乾淨 Plate working value**，外附 `format_version` 及 `engine_profile`；成功提交後，它是同文件當前 authoritative working revision。這裡的 authority 指接續編輯基底，沒有專業核准效力，也不再另建 accepted projection。`engine_profile` 指固定套件、base plugins、NodeId 與 normalization 配置的組合；不是要求模型填版本。比較用 diff 刪除節點、游標、選取、busy、已看過標記及整個 React editor 不作正文保存。前後版本及真實 actual_changes 供唯讀查閱，比較結果不回灌正文。

**歷史證據保留：**[R01／R01-F](evidence/2026-09-09-jd-native-pending-review-comparison.md)記錄原生 pending 的個別結算、續改及順序限制；[SuperJSON 2.2.6 四項實證](evidence/2026-09-09-jd-native-pending-codec-probe.md)支持完整 json＋meta envelope 保留已測 undefined，原 raw JSON 失敗仍成立。這些 source／codec 材料保留，不改判成框架修復，也不再作審閱 B 的必要接線或繼續分組研究的 gate。主路線不以先產生 pending、剝除 metadata 或自動 accept 模擬工作稿保存。

建議少量 JD 容器承載可辨識範圍，內部仍用原生段落、標題、清單、子清單、表格與文字格式。具體候選為 `jd_section`、`jd_duty`、`jd_task`；專業總覽可在 section 內用原生表格列／清單項，不為每個知識或條件另造必填關係物件。section 的用途可辨識，但數量、名稱、顺序及哪些區塊存在不照 r2 固定。

- 每個可定位的 block 使用原生可序列化 `id`；`type` 表示內容／排版類型，兩者不等於審核群組。
- Task 可直接位於主要工作 section，沒有 Duty 不必補假父項。Duty 可有標題、說明及 Task；Enter 在 Task 內只拆段，不自動成為新任務。
- 名稱、完整任務敘述、產出、要求、時機、適用條件與 K／S 用途，優先放在可編輯的具名段落、清單或表格欄中。沒有必要就不拆欄；不以欄位齊全判斷能否保存。
- 先出現但尚不能歸屬的成果／要求可留為有意義內容，不造第二份 Gap／工作理解。未知以有根據的文字明示，不以空值推定不存在。
- Text leaf 僅支持 `text` 與明列的文字格式。數字、真假、條件、來源及核准狀態不掛在 leaf；數字可以完整存在正文，並非禁止 0 或 false 所代表的工作事實。
- Element metadata 只放確有機器用途的身分、種類及指向既有 owner 的來源引用。同一條件不另存一份隱藏 props 再與正文雙向同步。

這些是 C01 的「可辨識結構＋完整敘述」映射，不是國際統一 JD schema。[內容關係](2026-09-09-jd-document-relationships-working-research.md)、[欄位與寫作指南](2026-09-09-jd-field-and-writing-guide.md)。[F01](evidence/2026-09-09-jd-native-content-profile-probe.md)已觀察三種普通容器、normalization 及特定 headless 操作；仍未驗完整 parent／child grammar、任務語意拆分身分或 DOM 編輯。不能把較早普通節點 probe 或 F01 局部正證擴成全套完成。

### 2.2 身分、位置、來源與必要呈現

| 情境 | 契約候選 |
|---|---|
| 改名／移動同一內容 | 保留 block 身分及完整隨行內容；位置按目前樹重新取得，不沿用舊 path；移到新 Duty 不自動取得其工作條件 |
| 複製／外部貼上 | 新內容取得新身分；外部 ID、來源引用或核准效力不直接成為本文件的權威。先核對原生 parser／NodeId；不支持的必要內容不能靜默丟棄 |
| 明確拆 Task | 提供兩項的實際內容及條件分配；建議延續原工作者保留原 ID，新增工作者取新 ID。若原工作已不再是任何一项，兩者新建並保留該次版本前後；不把這變成新的工作 lineage 系統 |
| 合併 Task | 由操作明示哪項延續及哪些完整內容納入；不靠文字相似度自動合併，也不默默刪掉條件 |
| 取消 Duty 分組 | 原生 unwrap 保留孩子；與刪除 Duty 及其全部內容是不同命令 |
| 刪除 Task | 明示整個 Task 的實際移除內容；不按隱含關聯自動刪職務總覽中的 K／S；舊版仍可查看 |
| 原生 ID 重複 | 乾淨 current 必須唯一；未經支持的消歧規則不得取第一個命中。diff 的同 ID 刪／增兩份是合法比較結果，不用 current 的唯一性規則刪掉其中一份 |

來源引用只表示可回查的依據，不等於所引用文字已自動證實每個句子。手改或 AI 再改後，不把舊引用標為重新核實；既有原文與更正 lineage 的 owner 保持不變。必要來源資訊以可讀的「依據」入口呈現，在前後版本也可展開。不同文件的來源不能借用，模型不能自行創造引用。

**UI probe 的 Task3 scope 缺口：**正式設計優先把真實適用範圍寫成 Task 內的「適用範圍：……」內容。若某欄確需 props，則必須在目前、前版、後版及原生刪／增兩份都使用同一有限欄位 renderer；不能只在 `diffOperation=update` 才顯示。probe 的合成 scope 不加入實際 r2 工作事實。

**兩個反例不刪除：**禁止 leaf 上的業務欄位只排除 `score:1→0` 的精確輸入形狀，不是修好 diff。空文字的格式仍保留；候選以支持格式的明確前後資訊及必要原生操作提示揭露，不默默清掉空 leaf marks。此有限呈現須單獨通過，否則不得稱全部改動可理解。新格式／屬性必須有對應呈現與保真驗收才能加入。

## 3. LLM 看什麼、如何指定修改

### 3.1 不每輪改稿的顧問接點

沿[寫作時機](2026-09-09-jd-field-and-writing-guide.md#何時開始寫何時修正)：對某項工作已有足夠理解與依據才寫；實質補充／更正才改。新案例、例證或 Memory 技術性更新本身不是改稿事件。不新增完整度評分 Agent、每輪固定工具呼叫或「填滿所有欄位才寫」的 gate。

主顧問先使用既有 current understanding／詳記／必要原文；需要動 JD 時才讀目前工作稿及受影響範圍。範圍不足就擴讀，找不到不能推定員工沒說。工具結果回到同一 Agent loop。整份收尾做工作→JD、JD→來源雙向核對，不能只因每次格式驗證通過就稱專業內容滿分。

**人工改稿後的接續：**目前 JD 是下一次編輯的基底，Memory 是可修訂的工作理解；兩者不同不構成把 JD 改回舊 Memory 的理由。`jd_read` 提供目前內容、保存版本及可查的人工改動來源／change reference，顧問先分辨措辭整理、內容增刪與可能的事實衝突。`origin=manual` 只證明員工改過這份文件，不把每次改字一律解讀成明確更正工作事實，也不自動更新 Memory。最新一版的修改者是 AI，也不會讓較早且仍保留的人工改動失去效力；讀取實際內容及可回查歷史即可，不另建逐字人工所有權索引。

若差異會改變責任／範圍，且既有原文及目前脈絡仍不足以判斷，就先不改該處，必要時在正常訪談釐清；不要求每次手編都另外按確認，也不阻塞其他無關工作。原文引用留下來不代表人改後已重新核實；App 的版本記錄不能變成第二份 canonical 訪談／更正 lineage。這是「同份最新稿、未知不補造、明確更正保留其他有效工作」的產品映射，不新增 Memory 同步流程或分類 Agent。

**2026-09-10 Owner 補充／跨輪變更感知（WORKING）：**員工手編並保存後，下一輪顧問開始回應前，App 必須主動讓模型知道 JD 有更新、哪些內容由員工改過，以及修改前後的內容如何取得；不能只提供可選的讀取工具，再假設模型自然知道要查。比較須有明確的前後版本及範圍，涵蓋兩次顧問互動間多次保存；通知不等於模型已完整讀過整份 JD。短改動可隨當輪文件 context 呈現實際前後內容，较長內容沿既有 `jd_read`／`jd_change_read` 按需取得，省略部分須明示，不能用生成摘要取代可查的完整差異。未確知模型先前取得何版／哪些內容時，明示基準未知並重新提供目前內容，不假報「沒有改動」。未保存或保存失敗的人工候選不得當成已保存新版通知。

這是 Owner 要求的產品效果及驗收補充，**不是宣稱各廠採相同 context 格式或已完成接線實證**。通知仍是 App 提供的文件狀態，不偽裝成員工聊天原話、不自動寫回 Memory，也不迫使每輪修改 JD。[官方定點研究](2026-09-10-jd-context-change-and-source-research.md)已核對 OpenAI／Codex、Anthropic／Claude 的模型注入、限定人工變更通知、UI-only 反例、大小與恢復限制，及現有 LangChain `wrap_model_call`／`request.override` 接點。沿此正式 model-view 機制整合，不採 Codex experimental API 作新依賴；[施工 Task 3](../plans/2026-09-10-jd-editor-core-implementation.md#task-3同一既有顧問的三工具已發配-refs-與來源)接線前固定本案比較基準／呈現預算及恢復契約並審查，再驗实际請求與重開。沿用唯一文件版本及既有顧問接點，不新增通用同步引擎或第二份文件。先前核心審查不自動涵蓋此新增要求的實作。

### 3.2 三個讀寫能力與明確範圍

| 能力候選 | 模型提供 | App／runtime 提供及返回 |
|---|---|---|
| `jd_read` | 可省略的 App 已發配範圍／歷史 revision reference；省略即讀當前文件 | runtime 注入文件身分；App 返回已保存版本、内容、附近上下文、可用 block／selection references、可回查的人工／AI 修改來源。模型不傳一份自稱「目前稿」的文件。歷史引用綁同文件，明標唯讀；不接受任意 checkpoint ID 或猜測版本，無 current 寫入效力 |
| `jd_edit` | 有意義的一批有限操作、所用 target reference、必要新內容及可回查的依據 | 真實 document／input／operation 身分、引用對應的 baseline、驗證／執行／保存結果；模型不填 UUID、Slate path、offset 或保存狀態 |
| `jd_change_read` | App 已提供的 change reference，或明示前／後的兩個同文件 revision references | change reference 綁定一次實際改動的確切基底與結果；版本對比返回該兩版的實際差異。返回前後內容與可展開依據；不以 LLM 自述摘要代替結果。不把任意兩版比較稱為單次 AI 修改，也不從比較取得 current 寫入效力 |

App 另有按 operation 身分讀狀態的端點／port，供重開與對帳；模型若需要，只能用 runtime 已提供的操作引用，不能要求它重新發明去重鍵。

三者的 wire shape 由[正式 schema 附件](2026-09-10-jd-editor-contract-schema.md)承接。`jd_edit` 一批只能使用同文件、同一已保存基底的 references；不能把不同版本的兩個有效引用拼成一次修改。App 驗引用、建立候選及檢查來源後，在保存邊界重檢 operation／request digest／baseline／目前 head；只有同一交易成功才發布內容及結果。P01 支持這個提交邊界，不代表實際 Agent 的 durable operation 身分接線已完成。no-change 的改動引用可查，但其實際內容差異為空；過期失敗只能讀結果／當前狀態，不冒出一筆已完成的內容修改。

**target reference 的有效性：**App 在讀取時給出不透明 reference，綁定同文件、特定已保存 revision 與實際 block ID；選取引用另外綁該版的原生 range。引用解析是讀取已發配的目標，不是模糊文字搜尋引擎。保存後舊 references 失效；另讀其他範圍不會把先前 reference 偷偷升成新版。任意過期、跨文件或不存在的 reference 都不執行。

第一次空稿已有帶 ID 的空 `p`；`jd_read` 發它的 target 與合法 root sibling before／after 位置，模型可同批新增已理解內容並移除仍空白的 placeholder，無需另建 root reference 或生成全份 JD。新增 Element 不讓模型填 ID，由固定 NodeId 配發；來源 handle 可直接沿用既有 conversation／Memory read 或已保存本輪 input 提供的引用，不要求先存在於 JD。文字修改的目標 union 固定 `p | h1 | h2 | h3 | lic`；表格儲存格讀其內文字容器，官方清單讀 `lic`。員工已選取文字時可使用 App 捕捉的 range。**沒有員工選取或其他已發配的精確 range，就修改已讀的完整文字容器；再讀一次不會憑空產生任意局部 range。**不讓模型算繁中字元索引，也不默默取第一段相同文字。

同批前序操作會改變位置。候選在開始執行前，以原生 `editor.api.rangeRef` 追蹤已發配範圍，採 `affinity: 'inward'` 避免把邊界新增文字默認納入；用完必須 `unref()`。ref 失效、移出支持的正文範圍，或選取內容已被前序操作改掉時，整批不發布，回報操作衝突；不僅檢查 offset 還合法。App 用原生 fragment 讀取結果核對基底選取，不自造 range mapping 或模糊 matcher。這個組合是待驗接線，官方只保證 ref 隨操作更新，不保證 JD 語意不變。[Plate 原生 refs](https://platejs.org/docs/api/slate/editor-api#rangeref)

首次選取的端到端入口固定見[工具契約 §2.1](2026-09-10-jd-app-tool-contract.md#21-首次畫面選取如何進入工具)：先確認 dirty 保存，Browser 捕捉真實 range，以既有 run request 的可選 `jd_selection` 交 App admission 驗證並綁當次 run，`jd_read({})` 才發出首次 selection_ref。這些原生座標只在 App 間傳遞，不交模型計算；無選取不要求補任何 context。過期或內容已變就保留訪談輸入供重選，不自造定位引擎。

### 3.3 有限操作及原生對應

| 模型操作候選 | 原生接點與必要約束 |
|---|---|
| `insert_content` | `insertNodes`／`insertFragment`；parent／before／after 均來自已讀引用；新 IDs 由 App／NodeId profile 產生 |
| `replace_block_content` | 僅替換 `p/h1/h2/h3/lic` 的文字與支持 marks；原生 transforms 保留外層 ID／允許 metadata，不以整節點 `replaceNodes` 假定可保留。表格讀其內 `p`／清單 `lic`；不藉改標題替換整個 Task 或整個 `li` |
| `replace_selection` | 第一版限上述同一文字容器內、由 App 發配的原生 range；替換該處文字／支持格式，外部內容保持。跨 Task／容器調整走明確結構操作；不承諾跨 block 刪插後所有身分原樣保留 |
| `set_properties` | `setNodes`；只允許明列的內容類型／格式／可修改 metadata，沒有任意物件 patch。來源引用另外驗證，不接受核准狀態或 document ID |
| `move_content` | `moveNodes`；完整節點隨行，目標位置也須有效；當批前面已移動時依 ID 重新取 path，不拿舊 path 續用 |
| `unwrap_group` | `unwrapNodes`；保留子內容；不與整棵刪除共用含糊的 delete 含義 |
| `remove_content` | `removeNodes`；實際刪除範圍必須回傳並在員工視圖可查 |

拆合是上述有限操作組合，含保留／新增內容及 ID 政策；不聲稱 `splitNodes` 就理解業務任務拆分。一批只代表一次保存的完整操作單位，**不等於永久審核群組或自動推得的語意依賴**。相互無關的修改可各批保存，避免一次失敗把不相關工作綁住。

工具說明須含：用途與不適用情境、read 前置條件、操作範圍、保留規則、例子、錯誤及可重試方式。保留既有順序工具配置；即使模型／provider 意外返回多個相依寫入，App 也不能在同一 baseline 平行發布。Schema 限制只處理結構，不判斷工作事實是否正確。

### 3.4 專業 JD 方法進入既有顧問

不新增專業評分或檢查 Agent。沿隔離 [SkillAssets／SkillsMiddleware](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/skills.py) 的唯讀 `/skills/` 資產與按需 `read_file`，新增一份 JD 撰寫方法及必要引用附件，讓同一主顧問在需要撰寫、實質修正或整份核對時讀取。方法名稱／描述只作原生 discovery；已讀且仍在有效上下文不用每輪重載，不以 Skill 被讀過當效果驗收。這只是方法資產，JD 寫入權限仍由三個工具提供，不給 Skill 主機寫檔能力。

| 指引必須承接的內容 | 既有權威與對應效果 |
|---|---|
| 寫什麼與深度 | [欄位指南 §1–§5](2026-09-09-jd-field-and-writing-guide.md)及[完整 r2／核對](2026-09-09-jd-sample-basis-and-review.md)：完整工作敘述、要求／產出、專業用途與必要範圍；不只保留短標題，不從樣稿複製員工未提供的工作 |
| 何時動稿 | 同指南「何時開始寫、何時修正」與本文 §3.1：某項理解足夠才寫，有實質補充／更正才改；零碎訪談、單一案例或 Memory 技術更新不必觸發 JD |
| 哪些先保留／追問 | 案例≠永久任務、未知不補造、本人≠團隊全部工作；更正只修受影響範圍，既有獨立工作與必要條件保留。只有真實脈絡不足才追問，不要求補齊固定欄位 |
| 人改後如何續編 | 先讀已保存目前稿，不以舊 Memory 自動蓋回；辨認可查的更正與措辭差異，必要時回原文。人改／來源存在不自动等於專業核准或重新核實 |
| 整份核對與完成說法 | 指南 §7 與樣稿雙向核對：工作→JD 查漏、JD→來源查無據／誤解／錯誤範圍。模型自評分、schema valid 或一次工具成功都不能宣稱所有職位「滿分」 |

接线時只調整主顧問與工具能力相矛盾的「只分析／沒有 JD 能力」宣告，補上需要時可使用 JD 工具及須依真實保存結果回覆的責任；保留既有訪談、來源、Memory B／C 與成本邊界。方法內不重抄全套工具 JSON Schema，不硬編模型／工具輪數或強制每輪編輯。

驗收分開：離線固定工具呼叫可證方法資產可發現、讀取有界、正確工具注入、來源及保存結果相符；不能證明模型會自行在適當時機撰寫。後者另用短情境、持續訪談與未參與調整的新職位，按本表判斷誤改／漏改、內容保留、修復、延遲及成本，另經付費資料／預算 gate。真人交付／核對功能延後，不移除 AI 顧問本來就應做的內容自我核對。

## 4. Python 與原生編輯器的正常流程

**推薦固定本機子程序作第一個接法。**Node entrypoint 為 App 安裝／打包的固定程式；Python 用固定引數、stdin JSON 與 stdout JSON，無 `shell=True`、無模型程式碼、無模型提供的檔案路徑。Node 只計算候選，不開 DB、不寫正式文件、不管理 conversation／Memory。這讓模型可以在沒有瀏覽器掛載時使用 App。

固定原生入口為 `transform`（七種已選操作）、`validate-value`（人工完整稿）及 `read-selection`（App 原生 range 的唯讀 fragment）。三者共用 profile 與同一 schema；最後一項讓 Python admission 有真正原生讀取接點，並非額外模型工具或新的定位器。具體輸入輸出及過期／normalization 檢查见[工具契約 §2.1](2026-09-10-jd-app-tool-contract.md#21-首次畫面選取如何進入工具)。

1. 既有 runtime 先確認 canonical 原始對話成功保存；沿 MEM-Q005，不把當輪有效 JD 候選與 Semantic Memory 的技術保存成敗硬綁一起。此流程發布的是工作稿，保存不等於員工批准或專業品質通過；舊 production 的核准文件 authority 仍待 successor ADR 正式切換。
2. App 解析已讀引用與固定 baseline，取得乾淨文件；核對單文件寫入及 operation 身分，已提交同一操作先返回已保存結果。
3. 在 Node 建立 disposable headless editor，載入相同 `engine_profile`。先驗輸入 schema／支援類型／身分，再按序執行原生 transforms；同步捕捉原生 operations。
4. 任一步失敗就丟棄這個候選 editor。`withoutNormalizing` 只合併 normalization 時機，不是 rollback；不拿受損實例繼續套用。
5. 所有操作完成後，Node 驗候選完整形狀、ID、支援 props、引用表示與未指定內容保留，形成 clean value、actual operations 與受影響範圍。Python App 向既有來源 owner 核對引用存在、同文件及更正狀態；Node 不讀 Memory，也不能判定原文已支持全部敘述。若原生 normalization 產生額外改動，必須算入實際結果，不能只報模型要求的操作。
6. App 在唯一保存邊界再次核對 baseline，提交整批不可變文件版本、綁定前後版本的 actual_changes 與結果。後續更正另產新版；不回寫歷史，也不等待個別建議接受／拒絕才更新工作稿。未成功提交就不向模型／UI 宣稱「已保存」。若 value 無實際改變，只保存可對帳的 no-change 結果，不產生新 JD 內容版本。
7. 模型取得已證明的結果再續答；UI 從同一保存結果讀取目前稿與前後差異。原生 operation 僅供同基底同步／呈現，重開以乾淨保存版本為準，不以重播全部 operations 重建唯一文件。

程序超時／取消要終止並回收子程序，stdout 專作協定、diagnostics 有界留在 stderr；無效 JSON、錯誤 profile、過大輸入／輸出都成為可辨識錯誤，不截斷成合法內容。精確 byte／time limits 在固定完整 JD 與最大預期文件量測後列入運行配置，不能用沒量過的低上限剪掉內容。[Plate Node 官方接點](https://platejs.org/docs/installation/node)、[Python subprocess](https://docs.python.org/3.12/library/subprocess.html)、[asyncio subprocess](https://docs.python.org/3.12/library/asyncio-subprocess.html)。P01 已驗固定 Python→Node→保存、重開及回覆遺失；超時／取消、I/O 上限及實際 Agent durable-operation binding 仍待正式接線驗證，不重跑 P01 作為新單位。

MCP 不作必要依賴；既有 LangChain tool 即可呼叫此 port。若日後確有另一個客戶端需要同一 App，再評估 MCP。現行 `langchain.mcp.MCPAdapter` 仍 beta，不能拿舊 adapters 範例直接接成另一套 agent 或保存 owner。

### 4.1 接合目標與正式切換邊界

**設計接合目標固定為 CT49–51 已驗證的隔離 `analysis_agent`，不是舊 production 顧問。**其 [pyproject](../../.worktrees/analysis-only-agent/experiments/analysis-agent/pyproject.toml)使用 Python `>=3.12,<3.13`、LangChain `1.4.0`、Deep Agents `0.7.13`，provider／native compaction 與工作理解沿已驗成果；確切其餘依賴依同目錄 `uv.lock`。API 的 [open_service／create_app](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/api.py)只允許 localhost `q019_` DB，既有啟動埠為 8091／單 worker。這是可沿用的本地研究基線，不是 production 已採用的宣告。

目前 [apps/api main](../../apps/api/app/main.py)仍組裝 ADR0060 `PostgresConsultantRuntime`、`ConsultantTurnProcessor` 與 OpenRouter；[production pyproject](../../apps/api/pyproject.toml)是 Python `>=3.13`、LangChain `1.3.15`、Deep Agents `0.7.5`，正式本地 API 預設 8001。它是切換時要處理的現況，不限制新 JD 設計，也不作此次顧問接合目標。不能用改 URL、加 `sys.path`、直接 import `.worktrees` 或混用兩份 lock，冒稱已沿用最新 Memory。

施工分為兩個明確出口：

1. **核心隔離接合：**在隔離 checkout 完成 Plate／文件交易／三工具／來源引用／結果對帳及同頁人工編輯，接到上述固定顧問。保留其 canonical 原文、理解及 Memory owner；JD 只新增文件與操作結果，沒有第二份訪談庫。API origin、文件 identity、run admission 與新 JD endpoints 在該入口顯式接妥，不能只改瀏覽器網址測得畫面就稱通過。
2. **正式產品切換：**在上述核心接合驗收後，先完成獨立且有限的 Memory authority 正式化，明列採用的已驗版本、取代範圍、owner／namespace／setup、刪除／恢復及 Python／依賴／composition root 統一。依既有證據做採用與接點回歸，不重選 Memory 架構、模型或重跑全部訪談。ADR0073 僅處理 JD，不能代替該 gate；也不能為跳過它而接回舊 JD VFS／pending writers。

隔離 catalog 目前只有文件 ID／標題／建立時間，沒有刪除 API 或 deleted／active 欄位。核心接合驗文件 scope、catalog 存在性，以及新 catalog 與初始 JD head 同交易；不假稱完整文件刪除已沿用。牽動原始來源／Saver／Store 的整份文件刪除生命週期，由上述正式化接點承接，不在核心編輯器另造刪除流程。JD 內刪除某項 Task／Duty 仍按 §2 的內容操作處理，兩者效力不同。

這是已知外部採用依賴，不是重新交給 Owner 的產品問題，不阻止核心 JD 設計與隔離接合。交接與驗收必須分別記「核心設計／隔離接合／production 切換」狀態，不宣称整合無依賴。真人交付／核對仍 PARKED。

## 5. 保存選項與可觀察的交易契約

### 5.1 所有可行保存路線都須滿足

保存單位是**單文件一次有意義改動的完整 clean value＋實際操作／結果＋基底與新版識別**。版本不可原地改寫；actual_changes 與確切前後版本綁定，包含原生 normalization 的實際影響。較早修改仍可回查，不能只留最近一次摘要。原生 undo stack 不是 durable revision，模型文字回覆也不是保存回執。不按每次聊天室回合產生 JD 版本；人工連續輸入可以在明確保存邊界合併，但不能把 AI 之後的人工更正藏進同一個 AI 改稿事實。

AI 的 `operation_id` 由 App 依已保存的 input、AI message 與 tool call 綁定；其命令、reference baseline 與 request digest 在進入 Node／SQL 前須已可 durable 找回，重開沿用同一 binding，不能重新配 ID。這沿既有操作身分原則，不把 call ID 本身當去重保證。人工保存由 App 發配／綁定 submission identity，UI 在同次提交與未知结果對帳期間保留它；正式提交結果同樣以該身分查询，不能在重試時新配。

**人工首次提交的具體接點：**App 的 browser 程式以 `crypto.randomUUID()` 配 `request_key`，不由模型或員工填；只送該鍵、原已保存 revision reference 與完整候選 value。Python 從路由／schema／目前 scope 注入文件、profile，計算 exact payload digest，映射為人工 submission identity；不另設先向 server 預約 operation 的端點或 token store。同次網路重送／未知結果對帳保持原鍵及原 payload，新編輯意圖才建立新鍵。這沿[既有 client 的 idempotency header](../../apps/web/src/shared/api/jobAnalysisApi.ts)與[App 發配 key 的既有用法](../../apps/web/src/features/consultant/ApprovedDocumentEditor.tsx)之分工，不沿用舊 approved 格式或舊 block UUID。

人工完整 value 的 Node 入口明分為 validate-value：以同一官方 profile 做完整預檢、獨立 editor normalization 與後檢，回 canonical value 及真實 normalize operations；不填假 `jd_edit`、空 command 或 no-op 來繞過 AI 命令規則。它不增加模型工具，也不是新的 normalization engine。

Browser 在送出前以原生 localStorage 新 namespace 保存本次 document／request key／base／exact value 的非權威送出記錄；關頁重開先以同鍵及原 payload 對帳。只有 `committed`／`no_change` 且 receipt confirmed 才可直接清除；查到 stale／save_failed 等 confirmed failure 時，仍保留 exact 人工候選並在同頁提示恢復，不能自動覆蓋新 head，也不能只放入暫存畫面就清除唯一恢復材料。待候選已形成另一份持久的新提交記錄，或員工明示捨棄後，才清舊記錄。寫入記錄失敗就保留 dirty 且不發送；unknown 不清除或另配鍵。這只用來恢復已送出人工請求及其失敗內容，不把普通 dirty buffer、舊 approved draft cache 或 localStorage 當成已保存 JD，不做離線同步／合併。正式目前稿與差異始終來自 JD 保存層。Task 4 必須覆蓋「POST 後关頁→重開查到終局失敗→再次重開」仍不丟候選。

request digest 包含文檔、基底、命令與格式 profile。同 ID 不同 payload 是錯誤。若 stale 後重讀並改了基底或命令，先把原操作確定為未發布／零影響，再建立新的 operation；不是以相同 ID 偷換 payload。操作成功後同時可查：`base_revision`、`result_revision`、`origin`（AI／人工）、`actual_changes`、已保存狀態及必要來源引用。來源內容仍由既有 owner 保有。

運算基底由 App 讀取該已保存 revision 的乾淨 value，版本號與完整內容必須綁定，不能只檢查數字正確就接受另一份稿。對下節推薦的 B 路線，SQL 交易取得同文件寫入鎖後重查 operation 回執及 digest，再檢查基底；鎖前的查詢只是快速路徑，不能單靠唯一鍵錯誤處理重送競爭。這是保存接線的責任，不交給 LLM 猜測或重新寫稿，也不要求 A 直接查改 Saver 私有表來仿造 B。

UI 已看過狀態、員工明確確認、專業品質通過是不同效力。審閱 B 不以逐項確認或 accepted projection 作工作稿保存前提，也不能讓寫入正文同時自動核准。是否另提供整版確認及具體已讀資訊，仍依 §9 收斂，不預先造角色／簽核流程。

### 5.2 兩個具體保存路線

| 路線 | 原生／既有機制 | 代價與定案條件 |
|---|---|---|
| A：LangGraph Saver 作唯一 JD owner | typed state 保存工作稿、JD revision 及 operation result；官方 checkpoint／state history 讀回當時文件；人工透過 deterministic 更新接點 | 須證明同一個完整 checkpoint 才發布「已保存」，分清 pending writes；人工更新不啟動模型、不覆寫父子 graph 尚未同步狀態。不可把整個 conversation time travel 當 JD 還原 |
| B：同一 PostgreSQL 中，JD App 作唯一文件 owner | `head` 指向 immutable `revision`；operation receipt 與 revision／head 在同一 transaction；LLM 與人工走同一命令邊界 | 需要明確 successor ADR 移除舊 JD writer；不是旁加一份 mirror。不改 Memory／conversation owner。須驗 head／revision／receipt 原子性與未知結果對帳 |

**具體推薦 B，按獨立 App 文件生命週期選擇，不受舊 ADR 保存形式限制。**最新隔離顧問的 root／child 只跨 `messages`、`turn_outcome`、`closed_turns`；把 JD 放進 child 不會自然成为 root 的 current 文件。若等整輪完成才複製，仍須處理工具已成功但回合失敗／人工更新的 owner 問題。本地目前沒有可直接沿用的 `Command.PARENT` 接法，也不能假定它不改 Agent loop。來源見 [conversation.py](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py)、[MemorySession](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/live_memory.py)。這是 source 診斷，並非 A 不可能實現。

B 讓人工、AI、版本比較及匯出讀同一份文件；Saver 僅持有 Agent loop 所需的 JD revision／operation reference，**不再保存 JD value mirror**。同一 DB 仍有不同事實 owner：canonical conversation／Memory 沿最新已研究接線，JD 文件由此唯一交易承接。正式切換須以 successor ADR 移除旧 JD writer，不雙寫、不搬旧資料。A 只有在固定驗證證明官方 sync checkpoint、root／child current、歷史讀取與人工更新不需額外狀態協調時，才作較薄替代重新比較。下一個 P 驗證先驗 B，不同時建兩套保存實作。

B 的最小邏輯資料（不是已執行 migration）為：

- `jd_head`：同文件目前 revision；可沿用 catalog 的文件身分，不再複製完整 catalog。
- `jd_revision`：文件與 revision 身分、父版、clean value、format/profile、作者來源及時間。版本不可原地改寫。
- `jd_operation`：文件內唯一 operation 身分、request digest、基底、terminal result、新版引用及實際原生操作；no-change 可無新 revision。已確定未提交的失敗回報零文件變更，不把未知偽裝成 failed。

**回執的唯一責任候選：**進入 JD App 且完成 operation 身分／payload 綁定後，由 JD App 保存終局結果，包含 no-change、過期與執行前後的確定失敗；Agent checkpoint 只引用該結果，不另裁定同次 JD 寫入成功與否。尚未進入此邊界的格式錯誤可由既有 tool validation 返回，沒有 JD operation reference，也不宣稱建立過回執。失敗回執不產生 JD 內容 revision。若記錄失敗回執本身失敗，須分清「已知文件未變」與「此操作結果尚未持久確認」，不能用同一個 durable 布林值混過去。

這比 P01 實測範圍更完整，**仍是待驗設計**：P01 保存 committed／no_change／stale_base 回執，原生執行失敗與錯基底測試沒有建立回執。後續正式接線需驗證錯誤結果的同鍵恢復及 Agent 重播；此處不補寫研究 DB 或修改既有 probe 來冒充已驗。保存交易故障後，只有確認原交易已結束且未提交，才可另外記錄該次失敗結果；失敗回報也不能覆蓋另一執行者已提交的同鍵結果。

提交在短 transaction 內以預期 head 作條件；更新不匹配就全批不發布。版本內容、head 與成功 receipt 必须同成同敗；模型生成及 Node 運算在 transaction 外。唯一鍵防同操作重复發布，不能拿 `ON CONFLICT` 靜默覆盖不同 payload。[PostgreSQL transactions](https://www.postgresql.org/docs/current/tutorial-transactions.html)、[Read Committed 的條件重檢](https://www.postgresql.org/docs/current/transaction-iso.html)、[constraints](https://www.postgresql.org/docs/current/ddl-constraints.html)。查閱 2026-09-09 的 current 文件為 18 系列；這是契約證據，未升級本 repo 的 PostgreSQL。

A 的存取只用正式 graph／Saver API，不直接 INSERT 或修補框架內部表。`get_state`／`get_state_history` 的存在不等於可無成本列出所有 JD 修訂；模型回合的 checkpoint 與 JD 内容 revision 不一一對應。checkpoint 保留策略不得刪掉仍承諾可查的 JD 版本或 canonical 原文。[LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)。實際 schema／交易／回執的單一推薦須在有限接線驗證後收斂，這不是要重開已選 Memory。

### 5.3 新格式與重開

載入先識別 `format_version`／profile，再建立 editor；未知版本不得先用當前 normalizer 讀寫而丟資料。可讀但不支持編輯時保留原件並明示限制。新格式升級須有版本化轉換、來源副本、前後保真檢查及明確結果；不搬旧產品資料，不同時維持兩份可寫 JD。

歷史版本比較應選支援該版的 renderer；需要轉換才能比较時，對 disposable copy 转換，不就地改歷史。來源失效或回查失敗要呈現，不補造原文。關頁後只承諾恢復已確認保存內容；未保存 buffer 不可在 UI 上被標為已保存。

### 5.4 保存資料的具體約束

2026-09-10 Owner同意保存方向，active格式沿[語意契約v2](evidence/2026-09-10-jd-semantic-contract-closure.md)：Task成果／要求兩組、K／S完整item及Task單向IDs同revision保存。App建立版本、映射issued refs及推導反向對應，完整性由整批候選驗證。新版固定profile為2／`jd-plate-clean-v2`，不新增表、不暗中搬移v1。首次先建立內容、成功後read新base再連結，不能宣稱跨兩次保存全成全敗。

三表、完整JSONB快照及保留粒度是本案需求的具體映射；官方可支持的基底／版本／操作結果原則、近期不同保存實例與不可擴張的結論見[共識效力核對§7](evidence/2026-09-10-jd-semantic-relations-storage-audit.md#7-json關聯與三表現行公開證據能支持到哪裡)，不能稱為大廠統一資料表規範。

2026-09-10 工程推薦，供 ADR 0073／正式 schema 審查；只採 §5.2 B，不並建 A。保存完整快照，operation 是去重與结果證據，不是需要重播的文件事件庫。

| 邏輯資料 | 固定責任與約束 |
|---|---|
| `jd_head` | 每份 catalog 文件一列；`document_id` 為主鍵，`current_revision_id` 以同文件複合外鍵指向 revision。建立文件時在短交易初始化 clean 空稿；不允許無可讀基底的 head |
| `jd_revision` | 複合鍵 `(document_id, revision_id)`；父版必須同文件，初版才無父版；不可變 clean `value` 以 JSONB 保存，另有 `format_version`、`engine_profile`、`origin`（AI／manual／initial）、建立時間。非初版的產生操作由唯一 committed receipt 反查，不在 revision 重複保存反向 FK；不為每個 Task 拆另一份正文資料表 |
| `jd_operation` | 複合鍵 `(document_id, operation_id)`；保存綁定 request digest／base revision、真實 terminal result、可選 result revision 與 native operations。結果中所有 revision reference 限同文件。`committed` 連確切新版本，`no_change` 連已檢查基底；確定失敗不產內容版。已終局不可覆寫 |

內部欄名與對外 `*_ref` 由 mapper 分隔，模型不取得資料庫權限。模型 `tool_call_id` 與文件／前景 run 的綁定、manual request 身分由 App 配發／核對；不以文字相似度去重。digest 只由 Python 對 schema 驗證後的固定 JSON 表示產生，包含 operation 語意、確切 base 與 profile；Node 不另算一個互不相容的 request digest。timestamp、通知送達時間及候選隨機新 ID 不作模型 request 語意。

**提交順序：**先查既有同鍵結果；需要運算時在交易外計算。提交交易取得該文件 head row lock，再查一次同鍵結果；若已有結果，先比 digest，匹配則返回原結果、不匹配則 operation_conflict。仍無結果才檢查 head 與 base，依结果同交易寫 revision／head／receipt 或不改正文的 terminal receipt。不能在取得 lock 前判一次 head 就發布。不同 operation 用同 base 競爭，只允許一個更新 head，另一個返回 stale。這是 PostgreSQL 官方鎖與條件重檢的本案映射，P01 只有交錯連線正證，真正同步競爭列入整合驗收。[PostgreSQL 16](https://www.postgresql.org/docs/16/transaction-iso.html)（2026-09-10 查閱）。

**DB02–04 已固定的約束：**所有 FK 即時，operation 單向引用 result revision；committed 的 result 有部分唯一限制，no_change 的 result 可以多筆引用同一 base。新版本實際順序為 revision→receipt→head→commit；不插暫時假回執，也沒有雙向 FK。初版及每父版最多一後繼以限定索引補強，恰有 head／producer 由同一建立／發布交易保證。完整欄位、null／CHECK／mapper 的責任只在[保存契約 §2–4](evidence/2026-09-10-jd-storage-contract-closure.md)維護；JSON Schema 不代替同文件 FK 或跨列不變量。

no_change 以鎖內已核基底與 canonical candidate 的 PostgreSQL JSONB `=` 作最後判據，保留 array 次序，不用 containment／摘要。只寫回執、不造版，actual_changes 的 before／after 均為 base、affected IDs 為空、native operations 為 null。Node.changed 是診斷，不是保存權威。confirmed terminal 只包含成功／no_change 或六種已綁定確定失敗；busy／unknown／conflict projection 不能覆寫原回執。

成功內容版的真實差異由其完整前後快照決定；AI 的 native operations 可幫助同基底 browser 同步與格式說明。人工送完整新 value 時不偽造「逐鍵原生操作」；保留 exact before／after 及 origin，伺服器驗證內容／結構與來源。AI 候選中未發布的 operations 不成為已保存差異。比較 projection 可重算，不另保存第三份可寫 value。

本隔離接合依 §4.1 的實際 catalog 檢查文件存在與 scope；它沒有 active／deleted 欄位或整份文件刪除 API，不將 production 的刪除生命週期列成核心先決條件。整份 catalog 文件的刪除／來源生命週期，留在 production adoption 時對照其正式 authority；不自行新增保留天數、清理或硬刪任務。JD 內職責／任務刪除仍依原有編輯契約。fresh setup／同 scope 驗收由施工計畫負責，本設計不授權清 DB。鍵、版本產生與引用及初版交易的問題沿[資料關係稽核](evidence/2026-09-10-jd-storage-relations-audit.md)保留；單向FK與具體約束已於[保存補正](evidence/2026-09-10-jd-storage-contract-closure.md)固定，Task 2 實作驗收。

### 5.5 原生操作與比較投影的保存分界

2026-09-10，依官方契約與既有固定安裝 source 收斂三種表示，避免把舊 pending／diff codec 問題帶入工作稿。

| 表示 | 保存／使用方式 |
|---|---|
| clean `value` | profile 僅接 JSON-native nodes，完整快照存入 immutable revision；重開直接讀它 |
| Slate 原生 `operations` | 只收固定引擎實際產生、驗過可 JSON 序列化的內容操作；當次同步／變動說明可使用。Node→Python→Web 不自行改寫其省略／null 語意，也不靠重播 operations 建 current truth |
| `computeDiff` 比較投影 | 從指定兩份 clean 快照現算，可能含刪除表示的 `undefined`；不保存為可恢復文件，不作 AI current read。前端用同 profile 在記憶體中渲染；必要有限屬性／格式前後說明不能只遍歷 newProperties |

**官方及固定 source：**[Slate normalization](https://docs.slatejs.org/concepts/11-normalizing)第6／7條要求 nodes 可 JSON 序列化，node 值不使用 `null`；操作以特殊表示處理屬性不存在。既有 lock 的 `slate@0.126.2/dist/index.es.js` 中，`setNodes`（5037–5140）將已移除欄位省略於 `newProperties`；`unsetNodes`（5269起）透過 `setNodes` 完成；apply 的 `set_node`（2174–2211）會刪除 old properties 中新集合已沒有的 key。這與 `computeDiff` 的 update metadata 不同。來源是固定 native lock 可重現的官方套件，不是本案新演算法；查閱 2026-09-10。

**設計選擇與實證界線：**採原生 JSON operation 表示，不新增自製 codec。[F02-D](evidence/2026-09-10-jd-official-profile-probe.md)已實測固定 add underline／remove bold，原生 operations 無 own undefined，普通 JSON 檔案深相等；另一 Node PID 的同基底 fresh editor apply 後整份 value 深相等。這只證該四個原生操作，未證所有變種或 DB／Web 接線，也沒有修好 computeDiff 反例。若插件實際產生不受該表示支持的內容，先保留反例再檢查官方接法；不能直接 `JSON.stringify` 吞欄位、復用 pending codec 當全解或改原操作讓測試通過。先前 native 13／3、history H09 與 pending codec 結果各自保留。

人工保存只有 before／after snapshot 也必須能查真正內容及有限 profile 屬性前後；不能因沒有逐鍵操作就隱藏更改。原生文字差異高亮是便利呈現，完整前後內容與所支持的格式／屬性可读才是驗收要求。比較投影永遠不自動更新 current head。

任意兩歷史版本也以完整 immutable before／after 作必需輸入，不要求每次人工操作都有 native ops。沒有可靠 affected-block 高亮时，完整前後以同 profile renderer 在原畫面唯讀展開；不只展示 `computeDiff` 判定的範圍，以免已知漏標使改動查不到。必要前後比較不新增第二個編輯頁或通用 diff 引擎。[工具契約 §5](2026-09-10-jd-app-tool-contract.md#5-jd_change_read)。

## 6. 成功、失敗及回覆遺失

（原生操作及比較投影的編碼邊界見 §5.5；下列結果描述文件保存效果，不是記憶體候選或 diff preview。）

結果候選區分：`status`、`operation_ref`、`base_revision`、`result_revision`、文件效果、回執是否持久確認、`actual_changes`、`error` 及必要 `next_action`；正式欄名依 [schema 附件](2026-09-10-jd-editor-contract-schema.md)，狀態與下一動作依[工具 §6.1](2026-09-10-jd-app-tool-contract.md#61-狀態與下一步的封閉關係)的優先規則及封閉矩陣。文件效果為未變／已提交／未知，不能與回執保存成敗混成一個 `durable_effect`。`actual_changes` 由 App 取得，不是模型自由填的完成摘要。結果可以先讓 App／UI 查閱，再以精簡文字和引用回給模型；不把完整長文件每次全部塞進 ToolMessage。

| 狀態／原因 | 真正效果 | 模型／App 下一步 |
|---|---|---|
| `committed` | 指定 result revision 已保存，回執可重讀 | 依实际结果續談；UI 顯示變更，不重送同批。回覆時 head 可能已前進，不把結果版本說成永遠仍是最新版 |
| `no_change` | 沒有新內容版本；同樣檢查 baseline，結果可對帳；result revision 等於該次 baseline | 實際內容差異為空，不說改好了某些不存在的內容，不為零改動造新審閱項 |
| `invalid_input`／`unsupported_content` | 未發布候選 | 指明不支持的欄位／類型／操作，保留原文；模型修正工具參數 |
| `target_missing`／`stale_base` | 零新 durable 文件影響 | 提供目前版本及重讀接點；重新規劃，禁止模糊硬套或換新 op 盲重送 |
| `engine_failed` | disposable candidate 可能部分改了，正式文件未提交 | 回報失敗 operation index／類型與已知原因；丟棄實例，不能說框架已 rollback |
| `save_failed` | 已確認 JD transaction 未提交／已回滾；不能只凭斷線或 timeout 判定 | 保留可恢復輸入；基礎設施恢復／停止由 App 管，不要求模型改文字修 DB。UI 不無限忙碌，但若已發配 operation 的失敗回執尚未確認，仍保留對帳入口且不開新 writer；必要閉合後顯示未保存並恢復手編 |
| `outcome_unknown` | commit 嘗試後，是否發布新版本尚不能確認 | **先對帳同一 operation**；未釐清不得再次新增、不得猜成功或失敗。App 找到已保存結果就返原結果 |
| `busy`／人工保存未完成 | 此次 AI 寫入不啟動 | 依已同意 §7／§7.1 的前景 run 互斥，先完成既有保存／必要對帳再續行；不吞人工輸入。完成或取消後，只待已發配未閉合 JD 操作對帳完成才恢復手編，背景 Memory 不延長鎖定 |

對帳查不到不總等於未執行：原提交仍可能在進行。先確認原 writer 已停止、權威保存層證明未提交且沒有 terminal receipt，才可在另次顯式 resume／重開沿原 identity／digest 受控恢復；不能以先重做來取得安全證據，也不把「讀不到 receipt」交給模型猜。已有 terminal 只返回原結果；已保存後通知／模型最後一句失敗，不回滾已提交稿或要求模型再新增。

同 operation 身分搭配不同 payload 是 `operation_conflict`：保留原回執、拒絕新 payload，不作 upsert 覆寫。確定過期／參數錯誤後若重新讀取並重新規劃，屬新的修改意圖，由 runtime 發配新 operation；網路重送、程序恢復與查結果則沿用原 operation，模型不決定這兩者。失敗候選裡捕捉的部分原生 operations 只能作診斷，不放进表示「已發布變更」的 `actual_changes`。

確定文件未變、但失敗回執尚未保存時，返回已知原因與「回執未確認」，不把文件效果改報未知；runtime 先處理原 operation 閉合。v1 每個明示 Node／SQL／必要失敗回執／lookup 階段一次 attempt、零自動重播，依[ER03](evidence/2026-09-10-jd-error-recovery-contract-closure.md)停止並提供恢復入口。已持久記錄的終局失敗保持原結果；若其後員工重新提交或模型依允許動作重新規劃，才是核對最新基底後的新意圖，由 App 配新 operation。不能由 runtime 自動換新鍵繞過失敗，也不沿同鍵把已終局失敗改成成功。

可修參數／過期目標走既有 tool error → 同模型修正；超時、取消、重複無效參數與不明寫入結果走既有有界停止／對帳條件，不新增修補 Agent。不對每個回合另作一次「必定用工具」攔截。

## 7. 人工編輯與 AI 接續的最小策略

**已同意的同文件單一寫入者方向（2026-09-10，WORKING）。**人工有未保存內容時，先保存成功並得到 revision，才啟動 AI run；AI run 期間 JD 暫為唯讀，仍可閱讀原稿與差異，且 **App／API 命令邊界同時拒絕人工保存**，不能只依 UI 防住延遲請求／另一分頁。對話送出／取消沿既有 run 行為，不另造併發聊天。AI 完成、失敗或取消後先依 §7.1 確認必要保存結果，再開放手改；純訪談回合也暫停，但不等待不存在的 JD 回執。具體時點已依 §9.1 裁決收斂，不再重問。

這是可討論的 UX 代價，不是大廠唯一共識。好處是避免員工尚未保存的輸入被 AI 新稿覆盖；單靠 DB revision 檢查看不見 browser buffer。若要 AI 運行中也可手改，必須另驗 dirty buffer 保留、衝突呈現及重新規劃；不能把多 writer 合併藏在「採用 Plate」裡。

正常 AI 更新可在**相同且乾淨的已保存基底**上，用原生 operations 套入既有 browser editor，形成一批可 undo 的改動。新增[原生 history 實證](evidence/2026-09-09-jd-native-history-and-sync-probe.md)已確認：`withNewBatch` 本身不能阻止後續相鄰人編合批；搭配 `setSplittingOnce(true)` 的固定情境分開成功。默认 NodeId 的 redo 会改 split 後項 ID；明設 `reuseId:true`、`initialValueIds:'always'` 的固定 split／異生成序列對照通過，不等於任意 mixed batch 或缺失初始 ID 已驗。正式 browser profile 仍須按這些條件驗證。不能把 `setValue` 當只更新畫面而不影響 history，也不能以 `withoutSaving` 隱藏 AI 變更卻沿用已失效的人編 undo；兩者風險已有實際反例。

重開以保存的 clean value 初始化，原生 session undo 不承諾跨重開延續。收到的 revision 與本地基底不一致，或原生套入出錯時，先保留本地未保存內容並停止套入；在已證明沒有 dirty buffer 的候選單 writer 流程，才可重載 authoritative clean value、清楚重設 session history。這是可恢復的整體讀回，不是選擇性 rollback 引擎。

人工 undo／redo 若改變 JD，就與人工編輯一樣形成後續保存結果；它不抹去歷史上 AI 曾改過什麼。游標或尚未輸入文字的格式選擇不另外產生 JD 內容 revision；已保存空 leaf 的格式則依 §2 保留與呈現。

### 7.1 寫入交接與取消的明確接點

2026-09-10 前景 AI run 使用同文件寫入 admission、背景 Memory 不鎖住 JD 的取捨已獲 Owner 同意，效力為 WORKING。下列時點是正式接線要求，仍須實作與故障驗收；ADR 0073 承接 authority 正式化。

1. 員工送出對話時先暫停 editor 接受新輸入，完成原有 dirty buffer 保存。保存失敗保留內容，不從舊版啟動 JD 寫入；未發配 operation 或 writer 已停且必要回執已閉合，才恢復手編。若文件確定未變但已發配 operation 的失敗回執仍未確認，先沿原操作完成恢復，不能用新 request key 繞過。
2. 保存成功後取得同文件 run admission；若另一請求先取得，返回 busy、保留已保存稿，不排第二個同文件 AI writer。原文問答持久化的次序沿既有 Memory 契約，不能為取得 JD admission 重寫來源。
3. AI run 期間，畫面可讀同份 JD 與差異，手編及 manual save 在 Web／API 兩端暫停。其他已開分頁收到新 head 時，有 dirty buffer 則保留、不自動 refetch 覆蓋；其後提交仍須通過 base 檢查。
4. 正常完成、取消或中斷時，確認該 run 的 writer 已停止；**只對已發配 JD operation 且結果尚未閉合的工具呼叫**，以原 operation 查 JD 結果，僅補缺失且匹配原 tool_call_id 的 ToolMessage。已保存的工具結果不重複追加；沒有 JD operation 的訪談回合沿既有流程結束，不等不存在的 receipt。完成必要閉合後開放手改；不得只在 finally 解鎖，讓仍可能提交的 writer 與新人工操作重疊。
5. 結果仍未知時顯示「保存結果確認中」，繼續允許讀取；由 App 對帳，不能要求模型換 operation 再新增一次。確認未提交而沒有 receipt 的情況，只在原 writer 已停止後依原綁定恢復／記錄，不把暫時查無結果当未執行。

**實際接點缺口：**[production admission](../../apps/api/app/adapters/langgraph/postgres.py)有 process-local `active_consultant_run`／`employee_mutation_admission`；[最新隔離 conversation close](../../.worktrees/analysis-only-agent/experiments/analysis-agent/src/analysis_agent/conversation.py)目前只辨識 Memory 寫入／讀取／修補，不能自然對帳新 `jd_edit`。正式接入須新增 JD outcome port 與 ToolMessage 回補分支，並驗 commit 後丟回覆、取消、重播與重新啟動。這是確定需要的薄接線，不另建 Agent loop；已有 Memory 測試不代表此 seam 通過。

單機單 process admission 不聲稱跨 worker 互斥；正式本機啟動維持單 API worker。資料庫 revision 檢查仍作最後防線，不將 SQL transaction 持有到模型完成。若此推薦暫時唯讀體驗不被採用，才回來比較支援 dirty buffer 的並行方案，不偷偷補 CRDT／OT 或 rebase。

## 8. 可核對的員工情境與匯出

**範圍更新：**本節的日常訪談／更正及 §8.1 單畫面要求仍有效；真人交付／核對、HTML／DOCX 問答包的段落依 Owner 裁決轉 PARKED，不列本版施工。一般 JD 匯出若另有需求再獨立確認，不以本附件自動新增交付能力。

以下為另設的假想操作，不修改 r2 的工作事實：

```text
訪談：先談網站維護，資訊仍零碎。
文件：保持原稿；理解／原文照既有方式保存。

後來釐清：只有含月檢約定的專案按月檢查。
AI 改稿：新增或修正「定期前端檢查」及其適用條件。
文件：標示這次修改，能讀到之前及之後的完整工作範圍。

員工更正：B 案只有交付後缺陷修正，沒有固定月檢。
AI：先讀目前相關工作及來源，再修正有誤的範圍；不刪別項已寫好的故障處理。
員工也可直接改該句；AI 下一次讀保存後的新稿。
```

畫面草圖表示同一工作畫面內的必要資訊，不指定按鈕名或固定左右欄；不是兩個頁面或兩份可編輯稿：

```text
訪談／更正                         目前 JD（已保存版本可辨識）
員工：B 案沒有月檢                 定期前端檢查
顧問：釐清後只改這項範圍           對包含定期維護的專案……
                                  適用條件：B 案不在固定月檢範圍

這次實際變更：維護條件              可讀：之前／之後、完整稿、依據
保存結果：已保存／未保存／確認中     較早修改仍可回看
```

與審閱 B 一致的匯出映射是取**明示且已保存的確切 working revision**，標明工作稿與版本，不需要 accepted projection，也不把已看過變成專業核對完成。2026-09-10 [交付設計](2026-09-10-jd-export-and-consultant-handoff.md)推薦第一版使用 Plate 官方 static／serializeHtml 產生自足離線 HTML，完整 JD＋固定範圍原始可見問答與依據；需外部文書軟體續改才考慮 DOCX 替代，不兩套並做。推薦預設為當下明示的已保存版；dirty 先保存，忙碌時只匯出已確認版，JD 與問答各固定可重讀識別。匯出不含比較刪文，不遺漏未歸屬內容或條件，不新增「確認整版」核准狀態。具體格式與互動仍待整體審閱；正式 authority 切換依 §9。

真人後續取得同文件的原始問答與指定 JD 版本。交付應帶可識別的文件／版本及訪談讀取範圍；完整問答不是 Memory 摘要，也不包含不應當作員工話語的工具結果／不透明推理。文件在交付後仍可續談，另產新版本；不建立真人角色權限。

現有 ConversationReader 單頁上限與 continuation 不能被忽略；完整問答須由既有 owner 固定從文件起點至截止，連續讀完所有頁。任意一頁缺失就不能交付冒稱完整的包；缺某筆引用則保留內容與引用識別、明示無法回查，不補造來源。這個 export read port 尚待接線，不能拿最近聊天或 Memory 代替原始問答。它是唯讀交付，不另建来源／export workflow store。

### 8.1 同一工作畫面：Owner 釐清

2026-09-10，Owner 表示若「目前稿／請 AI 更正後」是兩個頁面則不同意。舊示意的 tab 已移除；更正前後是同一份文件的時間差異，不是產品的兩個操作頁面。採以下介面約束：

- 同一工作畫面提供聊天室與唯一可編輯 JD。AI 保存成功後更新原稿，保留使用者閱讀位置；不另開「更正後」頁，也不要求在兩個稿之間選擇。
- 本次改动有可見提示，相關位置可展開實際新增、刪除與前後內容；歷次改動在同畫面唯讀查看。聊天摘要不能取代完整差異。
- 歷史刪文／比較節點不混入可編輯 current value、LLM current read 或匯出；比較是同畫面的參照資訊，不是第二個寫入 owner。
- 原地顯示只定產品效果；標示方式、展開控制名稱及欄寬可於實作調整。這不新增接受／取消操作，也不以關閉差異代表核准。

同一可編稿與多個不可變歷史 revision 並不矛盾：前者是工作介面，後者讓員工追查 AI 實際改了什麼。正式差異呈現仍須通過原生 diff 反例、完整刪除及格式變更驗收，示意圖不是已實作的編輯器。

## 9. 已選流程的效力與仍待收斂的接線

**Owner 已選 B／WORKING：**「持續工作稿，保留差異與更正（建議）」。效力依[審閱工作稿 §7.7](2026-09-09-jd-editing-and-review-working-design.md#77-owner-裁決持續工作稿保留差異與更正)：不再提供原 B05／B06 的個別待審接受／取消操作，B04 的人工續改 pending 狀態分支不再適用；這不是把人工或 AI 修改自動標為 accepted。保留同份最新版、獨立內容不被誤刪、相依內容完整更正、真實差異及歷史查閱。先前詢問與「不太清楚」的 OPEN 狀態已由這次明確選擇取代，不再等待同一裁決。

對月檢誤改的具體效果：員工指出範圍錯誤或直接手改，App 在目前工作稿完成新修正並保存新版；正確故障處理須保留，前次誤改與本次更正皆可查。這是工作稿更正流程，不宣稱等同 deterministic reject，也不新增任意歷史修改一鍵撤回的保證。顧問修正仍須核對實際內容及必要相依項，不能以流程簡化降低 JD 保真要求。

| 項目 | 已同意或可據此映射 | 尚未由本次同意核准 |
|---|---|---|
| 工作稿與變更查閱 | 同一 clean authoritative working value；更正形成新 revision，實際 before／after 及 actual_changes 保留；不需個別 pending 結算或 accepted projection | 完整格式／內容 profile、所有必要變更可讀、正式 schema 與端到端驗收 |
| 人工與 AI run | 保留人工編輯能力，AI 讀人工保存後最新版；2026-09-10 又同意 §7／§7.1 前景 run 暫停手改與必要結果確認後恢復 | DOM／IME、dirty buffer 與故障情境的實作驗收，並非仍在等待相同產品裁決 |
| 工作稿匯出與真人核對 | Owner 明定真人交付／核對先不做，HTML／DOCX＋原始問答包 PARKED；保存、已看過均不等於專業核准 | 未重啟前不列核心施工；不新增「確認版本」或角色流程 |
| 保存與 production authority | 2026-09-10 同意 §5 保存 B；Memory／原文 owner 沿既有成果，§4.1 固定隔離顧問接合與正式切換依賴 | 正式 schema、實作驗收、ADR 正式化與 production 切換；不是仍在重選 A／B |

**有限接線邊界：**App 解析已讀引用與 baseline、調用原生操作、核對結果、保存不可變工作稿版本及真實改動，並呈現前後內容。現行主路線不建立語意 pending 群組、通用相依結算／排序或選擇性回退引擎；R01-F 與 codec 不再是該類機制的施工入口。原生 session undo／redo 依 §7 保留原證據邊界；整版還原不因選 B 自動成為必備功能。技術契約與效力差異由設計稿明列，production 仍依[決策流程](../decision-process.md)及 successor ADR 正式化。

### 9.1 整體接線評審包

**裁決：Owner 已回覆「可以，但是先不用做真人交付核對」。**下表前 3 項採 WORKING，最後一項真人交付 PARKED；不再等待同一問題。§7／§7.1 的暫停與恢復規則及 §5 的保存路線 B 据此收斂，這不等於正式 schema／DOM／模型驗收已完成。下文「尚未裁決」是送審時的效力說明，由本條更新。

2026-09-10；下表保留送審時的完整效果與代價，裁決依上條。Plate、持續工作稿、同一畫面、訪談主導與既有 Memory／JD 方法不重選；文件、工具與保存細節留在責任章節／附件，交付部分只留作 PARKED 研究。

| 一個完整使用流程 | 推薦行為與實際代價 | 詳細依據 |
|---|---|---|
| 員工正在手改，接著送出訪談 | 先暫停新手編、保存原有輸入，才讓 AI 開始；保存失敗保留輸入，writer已停且必要回執閉合後恢復手編。前景 AI 回應期間可讀 JD／差異，暫停直接修改；這包含最後沒有改 JD 的純訪談回合。回應完成或取消後恢復手編；只有已發配且未閉合的 JD 操作須先對帳其保存結果，純訪談不用等不存在的回執。背景 Memory 不延長暫停。代價是等待 AI 時不能同時打 JD | §7／§7.1；這是單人、AI 主寫的本案取捨，沒有宣稱 OpenAI／Anthropic 都採整輪唯讀 |
| AI 已理解某項工作，開始撰寫或更正 | 既有顧問讀目前稿，使用 App 提供的定位與原生操作；一批全部有效才保存。原畫面更新同份 JD，可展開實際前後及來源。資料不足則繼續訪談，不必每輪改稿 | §3、§8.1、[工具契約](2026-09-10-jd-app-tool-contract.md)；既有工具 loop＋Plate，沒有新主 Agent |
| 保存成功但回應遺失，或關頁後重開 | 唯一 JD 保存處記完整版本及同操作結果；重開讀保存版，只對已發配且未閉合的操作先查原結果，避免重複新增。JD 放同一 PostgreSQL 的專屬交易；Memory／原文保留既有 owner。代價是必要的文件版本／回執接線，以及明確移除舊 JD writers | §5／§6、[ADR 0073](../adr/0073-plate-jd-app-working-document-and-revision-authority.md)；不是另建 Memory 或同步 mirror |
| 真人顧問接手核對 | 本地 App 仍可直接讀原始對话與同份 JD。需要帶走時，首版推薦下載單一離線 HTML，含指定已保存 JD 與固定範圍完整原始問答／依據。代價是不承諾在外部文書軟體無損續編；明定需要該能力時，才改選已列的免費 DOCX 替代 | §8、[交付設計](2026-09-10-jd-export-and-consultant-handoff.md)；沒有角色權限或第二個編輯頁 |

**可替代而非必然要自建：**如果員工必須在 AI 回應期間同時手改，保留 Plate 與已選工作稿，只重議 §7 的並行輸入保存、衝突顯示與 AI 重讀策略；不能直接推定需要 CRDT，也不能聲稱目前有限實證已涵蓋。若交付需要外部續改，只重議輸出格式。這兩項是可感知的产品選擇，工具欄名、SQL 約束與固定插件設定由研究者依契約收斂。

G3 核心取捨已固定，接續完成跨語言 schema 與施工切片，對整體作最後獨立審查；[decision process](../decision-process.md) 的 G6 所要求的正式 authority 仍以 ADR 狀態為準。方向同意不等於本輪即可改 production 或清空資料庫，也不等於 DOM／IME 與真模型品質已驗收。

## 10. 有限驗證與施工交接出口

不重跑三套完整框架，也不直接搭完整產品。以下是證據與後续施工驗收範圍，不是自動啟動 H／F／P／U 四輪新研究的指令；已有固定正反證直接重用。F02 結束後停止插件微型探針，先收斂 §9.1 的產品取捨與正式契約；新實驗僅限出現會改變選擇的新反證。

| 驗證單位 | 通過必須看到的結果 | 停止／返回設計 |
|---|---|---|
| H：原生批次、人編及 ID | 同基底原生套入、AI→人編分開 undo／redo、固定 ID profile 的序列化結果 | 為過測試而關 ID、丟 metadata 或自造 undo／rebase，均停止該接法 |
| F：最小正式內容 profile | 完整 r2、未歸屬內容、Task4／8條件、move／split／paste、必要欄位及空格式前後可讀 | 無法保真或需通用自訂 diff，回框架／表示法比較，不默默刪欄 |
| P：固定 Python→Node→保存 | stale／部分 transform／保存失敗／保存成功回覆遺失／同鍵重送，不重複新增；人工保存與模型同成功界線 | 無法證明唯一 owner 或需直接改框架私有保存表，換另一保存候選 |
| U：最小真實人工輸入 | 繁中輸入／選取、表格／子清單、人改後 AI 續編與讀回、關頁重開、所有實際改動可查 | headless／SSR 不能代替 DOM／IME；不以工具是否返回正常代替員工效果 |

每單位先明列固定 profile／操作與失敗注入，保存實際 before／after、結果與界線。固定測試只證明文件能力；真模型付費驗收另列短情境、長訪談及未用於調整的新職位、資料與預算，沿既有 JD 方法評估。不得以虛構 r2 或 Memory CT49–51 當此驗收。

**現行內容證據與歷史審閱證據（2026-09-09）：**[F01](evidence/2026-09-09-jd-native-content-profile-probe.md)六組最終 5／1，原 normalization 空 leaf 差異保留，首輪測試 aliasing 修正另列；正式 grammar 與員工可讀仍須在工作稿主路線核對。[R01／R01-F 待審比較](evidence/2026-09-09-jd-native-pending-review-comparison.md)的 Plate 首次 2／2、已知成員多 ID 順序結果，以及 PM A／B 正證、C 格式／AttrStep 缺口，全部保留為歷史；[codec 四項通過](evidence/2026-09-09-jd-native-pending-codec-probe.md)亦不改原 raw JSON 失敗。審閱 B 已選，停止將 pending 分組／格式結算或 codec 列為正式必要驗證，不為它們追加 probe。實際 diff 的兩個反例與必要呈現驗收仍保留，不能因不再有 pending 就宣稱全部改動已可見。

### P01 固定驗證範圍（歷史執行前紀錄）

以完整 r2 fixture、既有 Plate 53.3.11／diff 53.0.0 安裝環境與 Python 3.12／psycopg 3.3.5，驗 B 的本機文件保存接點。Node 本輪只支持按 App 提供的 ID 原生追加文字、新增段落及空操作；這些足以觸發新版本／重複新增／中途失敗，不是完整 JD 工具已實作。新容器 profile、選取／IME、接受／拒絕、模型提示與來源解析不在此 probe 宣稱範圍。

- 隔離：只在 `.research-tmp/jd-editor-save-probe` 寫研究腳本／結果；PostgreSQL 使用新的 `jd_editor_probe_p01_20260909` 資料庫。若已存在且來源不能證明為本次建立即停止，不覆蓋／清空。連線驗證 localhost:55433 與確切 DB 名；不寫原有 q019／production、Saver／Store 或 Memory 表。
- 預定資料：彼此隔離的固定情境文件，完整 r2 乾淨 value、固定命令、App 操作身分／request digest、原生 operations；不使用真員工資料或 LLM 請求。DB 憑證只由既有本機設定讀取，不寫進封存／輸出。
- 預定情境：保存／新程序重開；同操作重送不重複新增；同 ID 不同 payload 拒絕；過期基底零發布；第二個原生命令失敗不改 DB；transaction 寫入中故障令 head／revision／receipt 全回滾；commit 成功後刻意遺失回覆，再以同操作在新程序對帳；no-change 不增內容 revision；人工走同保存邊界；兩連線同基底競爭僅一個發布。
- 判準：逐案記前後內容／雜湊、revision／operation 數及真實结果。注入點必須在對應動作發生之後，不能只 mock 一個錯誤字串。資料庫不可讀、程序超時或腳本錯誤不得算通過；發現問題先保存反例再定點修正 probe 接線。
- 停止：若需改 Memory、查改框架私有保存表、自造通用差異／回退引擎或實作尚未同意的審閱政策，停止本接法並回報。正證只供 B 定案，不把此研究腳本接入 production。

**P01 執行結果（2026-09-09）：**[保存實證與封存](evidence/2026-09-09-jd-native-save-probe.md)第二輪六組固定情境通過，含完整 r2／新程序重開、去重、錯基底、部分失敗零發布、SQL 回滾、commit 後退出再對帳及交錯 CAS。首輪不足及原碼保留。只新增隔離 DB，未改 Memory／production 或使用付費模型；未證同步並發、Agent durable binding 或正式人工接線。乾淨值保存正證可支援目前工作稿路線的有限保存候選，不等於整套 B 流程或 production owner 已驗收。

產品取捨與有限驗證收斂後，將唯一文件 owner、工具 schema、版本／交易與正式 profile 定稿，經獨立審查及 successor ADR，再拆可獨立驗收的核心切片：契約／原生接線、保存與回執、讀取與工具、人工 editor／比較、顧問 Skill 與固定情境驗收。真人交付／核對及 HTML／DOCX 不列本版。付費模型驗收另有資料／預算 gate；production 另有 §4.1 的 Memory 採用依賴。本文列的是依賴順序，**尚不是已核准施工計畫或 S5 完成**。

### 本輪獨立審查

**2026-09-10 最終核心總審：**獨立 reviewer 串讀主稿、正式 profile、三工具、85-def schema、施工計畫及 ADR0073。兩項 P2 已修正並限定複核通過：一是人工 POST 後關頁、重開才查到 confirmed failure 時保留唯一候選；二是 browser selection→既有 run admission→原生 `read-selection`→checkpoint→`jd_read` 首次發配的完整入口。另對齊 current 續頁可發同基底 targets、history 不升格；Task1／3／4 的實作依賴無前向循環。無剩餘阻擋核心設計／隔離施工交接的 finding。最終 schema hash `6B42BA220C0102590DC651692BE7497AE400BD713CB6F0D86FA1C5103F753F67`，計畫 hash `8433A04D4ECD0F7BD08B295DE0F200865288A8F114595A9AA8EAE359635D4C30`；後續只加入口／結果路由不改此兩檔。

原生編輯／保存／格式反例保持原判；此審查不宣稱新 `read-selection`、完整 ToolNode、真 provider、DOM／IME 或自然 JD 品質實跑。相關驗收已落六切片計畫，不藉設計審查跳過。production 仍依 §4.1 的 Memory authority 採用依賴與 ADR G6，真人交付不在本版。

內容與原生操作、Memory／保存接點兩路唯讀審查完成；指出的同批 range 漂移、replace 身分保留範圍、來源驗證主詞、stale 後 operation 更替及 server 寫入門檻，已在本文收斂。保存推薦改按已讀 source 選 B，沒有因舊 ADR 偏好 A；A 保留清楚的反證條件。此為先前候選的審查紀錄；本輪按 Owner 已選的審閱 B 更新主路線，不把它擴成保存路線定案。H／F／P 的各項限定結果保留，U、寫入互斥及匯出細節仍未驗收或全部核准。

2026-09-10 獨立架構複核：已處理舊 JD 全部 writer／approved／VFS 取代範圍、實際 conversation close 不識別 JD、單 writer handoff 三項 finding。再指出「每輪都查 JD receipt」會誤傷純訪談，已限縮為有 operation 且尚未閉合才對帳、僅補缺失 ToolMessage。Reviewer 未發現阻擋此設計收斂包送審的其他問題；不等於正式 profile／工具全部實作、S4／S5 或 production 驗收通過。單畫面澄清已直接記為有效需求，沒有再問 Owner。

同日接口獨立複核 2 P1／1 P2 已收斂：文字容器含官方清單 `lic`；空 `p` 首寫的 target／插入位置、新 Element ID 及既有來源入口合成一條；任意歷史比較以完整快照作必要輸入，不依賴人工未必有的 native operations 或可能漏標的 affected-block 集合。它們使用既有原生操作與 renderer，不新增通用 engine；完整插件能力由 F02 有界驗證，不以文件修正冒稱實作已測。

F02 獨立唯讀複核：四組／15 斷言、完整實際後版、219 份材料 hash／大小及兩輪 source hashes 均與報告一致；首輪失敗保留、修正未改 assertions，無影響選擇或可信度的 finding。§9.1 另作一次使用效果複核，修正簡述對帳範圍為僅已發配且未閉合 JD 操作，避免讓純訪談等待不存在的回執；其餘範圍與共識標示清楚。這是可送產品裁決的研究／設計包，不是 S5 或完整正式 editor 的通過聲稱。
