# 中後期訪談換窗比較：材料與離線接線驗證（2026-10-05）

**真模型三組各8段、共24段已完成。**Memory組累計input比完整原話組少21.0%，與摘要組差1.4%；兩個衍生資料組完成最後的跨欄修正，原話組仍殘留一處舊門檻副本。詳見[結果與判讀](results.md)、[用量原件](prepared-01/result.json)。本批估算占用US$0.068770700，原累計US$1.391700015，無重跑。原話105則全數放得下，三組未觸發截斷或compact，不能將本批寫成超容量勝出。

以下§1–8保留材料選取與接線過程。執行前93項測試含真PostgreSQL＋腳本化模型，不冒充上述真模型結果。[凍結清單](prepared-01/manifest.json)記施測前材料，[started.json](prepared-01/started.json)另記本批有效授權；方法與容量界線沿[比較設計](../../2026-10-05-context-reset-comparison-design.md)，不另訂產品政策。

使用者補充早期訪談找回後，另核對[c01實際取用路徑](analysis/early-recall-audit.md)，並建立[獨立補測](../early-interview-recall-2026-10-05/README.md)；前批原件與判準不變。

## 1. 直接從第 52 段接續

- [baseline.json](baseline.json)：原件路徑、SHA-256、來源截止、JD／Memory 數量與歷史容量觀察。不複製整套產品匯出，避免多份底稿失去一致性。
- [continuation.json](continuation.json)：只保存八段合成員工輸入。模型每次只能收到當段文字，看不到後續題目或判準。
- [grading-cases.json](grading-cases.json)：研究者使用的來源帳本、37 個分段檢查項及引用判準。不得裝入模型 Context 或任一讀取工具。
- [reference-review-anchors.json.gz](reference-review-anchors.json.gz)：從原研究副本唯讀擷取第52段的207筆正式引用、156個核對基準及相應的歷史引用列；補上公開產品匯出未含的 `reviewed_revision_id` 與舊 JD 內容，不含後續續訪。

共同起點已有 13 項任務、33 項成果、47 項要求及 207 筆原話引用。Memory 有 12 個情境、1 個理解；單層摘要由相同來源分四批整理至序號 104。共同近期語境固定為 101–105，包含前問與最後兩個已完成的員工輸入／顧問答覆單位。R 依工作預算另保留較早原話；S 載入既有摘要；M 載入導覽並按需取正文。

八段分別檢查退貨精確時點、驗收規則生效期、採購代理分工、三張報表、模糊指涉、撤回未確認提議、已知未知，以及完整 JD 的跨欄一致性。新門檻為 **2026-11-01 起驗收不良比例超過 3%**；這是本批新增合成事實，不回填舊原件。八段之間各組保留自己的答覆、工具結果及 JD，不能把對照組的成功答案補給另一組。

## 2. 起點核對發現

第 52 段最後一次完整請求的原計數為 **144,455 input tokens**。該請求有 52 則 App 參考訊息，文字共 177,909 字元；另外 52 則員工輸入共 4,068 字元。字元不是 token，這個結果只能證明歷史請求已大，不能證明清理後的原話也超過容量。加密項目已遮蔽，不當作可重播的原生狀態。

JD 不是無資訊的白紙。起點已保存本次回問的多數數值與權責，尾段105也概述部分答案。因此每段要分開記錄既有 JD、近期原話、較早原話、摘要與 Memory 的可見資訊，不把答對一律歸因於 Memory。

接線時另外查明，207筆引用中有 **39筆原本即待核對**。它們不是新實驗造成的缺陷，不能初始化時清空狀態，也不能全部算成某組新犯的引用錯誤。本次原樣保留引用身分、目標、原話來源、待核對標記及核對時的 JD 修訂；續訪評分分開看既有狀態與本次變化。

另有兩個適合檢查實際改稿的部位：

- **跨任務數值副本：**設備備品要求雖以自己的 5% 為主，仍描述「驗收不良的 5% 提報門檻」。驗收改成分期適用的新規則後，這句可能需要加時期或刪掉多餘比較；設備自己的 5% 不應跟著變。
- **跨欄概括句：**退貨正文概稱倉庫判定可售，要求另列冷藏退貨由品質窗口判定。最終核對允許補清適用範圍，不把消除原有歧義當作「擅改未受影響內容」。

## 3. 怎麼判讀

修訂有三個關注點：新資訊有寫入、舊正確條件仍在、引用支持新舊適用範圍。不能只看顧問答覆說「已更新」。c02／c03／c06 檢查保存後的 JD，c08 複核最終內容及引用；若只有研究提案、沒有實際套用，只能報提案品質，不能報產品 JD 修改成功。

37 個檢查項是八段觀察點，不是37個互相獨立的事實。c08會再次查核前段內容，單獨報最終保留情況；c05有2項條件式檢查，須先核對各組真實前文是否仍有多個合理表格目標。不適用或因護欄未完成的項目分列，不事後只挑成功題比較。

來源支持另行判讀。新生效日、3%及採購代理人只能由本批新有效來源支持；舊 Memory 不可能已包含它們。保留原有正確引用可以，不強迫模型為了展示改引用 Memory。只查閱較少、卻丟掉期限或權限界線，不能算效率改善。

## 4. 執行門檻

1. JD 交易及真實原生歷史接續的驗證見§6–7；整批排程、凍結及外送護欄沿§8，不另做研究版 JD 保存。
2. 三組採同一份專業指引，僅資料入口及 Memory 專屬工具不同。固定 Luna／high、64步、每步32工具及16,384輸出預留，不在觀察結果後調整。
3. R 的起始完整請求先計數，放得下就全部保留；超128K才按時間順序移除最早完整單位，101–105共同尾段不能移除。S／M不截摘要或map。計數、生成與輪中compact都須先取得外送授權。
4. 每段輪流執行R／S／M，下一段輪換先後。第一次遇到第二次輪前換窗需求，該組停止；整批費用／時間或provider失敗則停止整批，不補跑成功組。
5. `manifest.json` 固定程式、依賴、Prompt、工具、來源及判準；`sources.zip`保留實際程式副本，不只依賴有未提交修改的Git HEAD。另有本批明確付費授權才可執行；目前累計估算占用仍為US$1.322929315／US$2。

截至§7，本次新增了本機測試 schema 內的資料寫入及原研究副本的唯讀擷取；沒有新增模型／遠端計數請求、正式資料修改或服務啟停。累計費用估算未變。

## 5. 本輪離線核對紀錄

以 PowerShell `ConvertFrom-Json`、`Get-FileHash -Algorithm SHA256` 及原件欄位比對完成下列檢查：

| 檢查 | 結果 |
|---|---|
| baseline 所列五份原件 hash | 5／5 相符 |
| 續訪與評分 case_id | 八段順序一致，無重複 |
| 判準 ID | 37 個且唯一，其中 c05 有2個條件式判準 |
| 原訪談依據 | 全部存在於 product-052，且不越過整理截止104 |
| 新補充依據 | 僅引用本段或前段，不引用尚未發生的續訪 |
| JD 目標 | 全部存在於起始13項任務，不以字串猜測另一物件 |
| 初始內容與引用 | JD／訪談／Memory 數量與 baseline 相符；207筆既有引用均為訪談來源 |
| 模型輸入檔 | 每段只有排程 case_id 與 employee_input，沒有評分答案；執行時只送當段 employee_input |

這是資料完整性核對，不是執行器防洩漏測試、真模型驗證或品質成績。原件保持不變，之後執行前仍須重新驗 hash；不符時先查原因，不能直接重算覆蓋成新基準。

## 6. JD 接線與真 PostgreSQL 驗證

### 接線範圍

- [baseline_store.py](baseline_store.py)：核對原件 hash，僅能在 loopback `_test` 資料庫的指定研究／測試 namespace 安裝起點；已有職務檔案即拒絕。保留13項任務、明細、關聯、105則原話、207筆引用及核對基準。匯入在單次交易內，不改原件。
- [capture_reference_baselines.py](capture_reference_baselines.py)：一次性補件程序，以唯讀、repeatable-read 交易讀固定的原研究 JD 修訂；輸出已存在即拒絕重寫。目前完整壓縮 JSON 為237,450 bytes，其 SHA-256 已加入 `baseline.json`。不把這份資料送進模型。
- [jd_workspace.py](jd_workspace.py)：只負責建立研究 Turn 與接上正式 `JdReadTools`、`JdWriteTools`；候選、短定位、引用、重播及提交沿用產品機制，不再設研究版 JD 編輯器或 `submit` 假保存。
- [memory_fixture.py](memory_fixture.py)：以正式 Memory 交易重建既有固定內容，保留12個情境、1個理解、原話來源與關係鏈。新副本取得新的物件／快照身分，內容不由模型重寫；這不是 B1／B2 生成品質實驗。舊匯出的引用為 repr 字串，使用固定格式解析，不執行 `eval`。
- [test_jd_workspace.py](test_jd_workspace.py)：不呼叫模型，使用原產品的隨機 schema fixture；只回收該次測試自行建立的 namespace。

這是新研究片段的資料起點，不是原執行恢復：不匯入舊 execution、operation、原生 reasoning／compaction 或歷史 checkpoint。JD 的舊核對修訂及其必要引用作為固定內容保存，不重建整段操作祖先鏈；模型一般 JD 讀取仍只見當前副本。新操作則正常產生產品修訂與交易紀錄。

### 先失敗，再補接線

| 發現方式 | 原因與處理 |
|---|---|
| 起點測試讀到0項任務，預期13項 | 空白產品建立不等於載入已有JD；補上固定內容、關聯與來源的研究種子 |
| 匯入驗證拒絕78個布林欄位 | 最初錯誤假設引用全已核對；實際39筆各有兩個待核對標記。唯讀追查原資料，補存156個核對基準，不清掉狀態 |
| 工具測試發現只有讀取，沒有寫入接線 | 補接正式產品準備／執行契約；不讓研究提案冒充已修改 |
| 理解導覽為0筆，預期1筆 | 補載固定Memory，並驗證讀取正文與JD引用落在同一快照 |
| 獨立程式審核指出舊引用列未載入，正式差異查詢重現 `JdEvidenceComparisonError` | 202筆引用的核對基準不是當前修訂。只有舊正文不足以通過正式資格核對，補擷取對應的歷史引用列，再用正式差異查詢逐筆驗證207筆引用的前後內容 |

這些是研究接線過程的反例，不是本批模型品質失敗。後加的取消／失敗與隔離測試沿用已存在的產品行為，並非每項都新做一次產品 Red–Green。

最初不完整的 [reference-baselines.json.gz](reference-baselines.json.gz) 保留為發現過程的證據，SHA-256為 `20d2dc84bc7431e85fe05ef8400b003043327e1913ed27336c87a7895d87d358`；不再由基準設定選用，不覆寫成新版。

### 已驗範圍

本批真 PostgreSQL 測試 **8項通過，約31秒（exit 0）**，檢查下列範圍；不是模型訪談成績：

| 檢查 | 實際驗證 |
|---|---|
| R／S／M 三份初始副本 | 各用獨立隨機 namespace，JD全文與正式原話逐項相等；207筆引用含39筆待核對與核對基準完全一致。這是初始化測試，尚非實際三組交錯執行器驗證 |
| 既有JD核對差異 | 正式 `JdEvidenceWorkflow.read_changes()` 能讀回207筆引用的正確舊／新正文，包含全部39筆待核對；原話不可變，不產生假的來源版本差異 |
| Memory與引用 | 理解及12個情境正文與原件相同，情境的原話序號集合一致；JD新增引用指向實際讀取的同一快照與修訂 |
| 工具修改與保存 | 短 `read_ref` 可讀寫；越界訪談106拒絕整次改動；改用 `current_input` 後候選立即可讀，重播不重改；完成交易後正式序號106與引用身分對齊，重連可讀，起始修訂不變 |
| 取消與最終失敗 | 兩種狀態都丟棄候選，正式JD與105則原話不變；另一檔案不能使用此檔案發出的任務定位 |

本節交易測試用的 prepared／completed context 位置是占位值，與既有產品完成交易測試相同，不能單憑本節宣稱原生接續。後續§7另以實際 checkpoint 驗證，未把占位值接入研究 runner。付費執行器與完整三組比較仍待§4的條件完成。

重現時先依 Runbook 提供 `CALIBURN_TEST_DATABASE_URL`，指向本機專用 `_test` 資料庫。本次使用55441的既有測試容器，憑證只在程序內由既有研究 helper 取得，沒有印出或寫入證據：

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -m pytest -c apps/api/pyproject.toml docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/test_jd_workspace.py -q --tb=short
apps/api/.venv/Scripts/python.exe -m ruff check --config apps/api/pyproject.toml docs/experiments/product-validation/data/context-reset-comparison-2026-10-05
$env:MYPYPATH = 'S:/caliburn/apps/api/src'
apps/api/.venv/Scripts/python.exe -m mypy --follow-imports=silent --strict docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/baseline_store.py docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/jd_workspace.py docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/memory_fixture.py docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/capture_reference_baselines.py
```

Ruff與四份研究接線程式的嚴格型別檢查通過。最初從根目錄直接跑 mypy 未指向產品原碼，出現 import-untyped；設定 `MYPYPATH` 後另修正一處連線名稱的型別收窄，未用 ignore 隱藏。測試 wrapper 預載舊研究 helper 產生兩個 pytest assert-rewrite 警告（anyio／langsmith），不影響本批斷言結果。

補件後重新核對 `baseline.json` 所列六份原件，SHA-256全部相符；三份材料JSON均可解析。本頁與比較設計的22個本機檔案連結存在，這項檢查不含標題錨點。Ruff格式與規則檢查通過，文件差異無空白錯誤；原始trace與模型產物未改寫。

另外執行產品既有 `test_consultant_completion.py` 與 `test_jd_model_item_roundtrip.py`，共13項通過，約11秒。涵蓋真正交易寫入後注入失敗的整體回滾、取消與完成競爭、原輸入正式化及原模型工具 codec；不把它們報成本研究新增的13項功能。

## 7. 原生歷史接續與研究執行接線

### 沿用產品機制，僅替換研究入口資料

[study_runner.py](study_runner.py)組合既有 `RoleContextHistory`、`run_response_loop`、模型請求計數與 `ConsultantCompletionWorkflow`，不另寫工具迴圈或保存機制。每次成功答覆都從真正的 LangGraph checkpoint 取得完成位置，再提交 JD 候選及正式訪談。

- [study_context.py](study_context.py)：第一段只載入該組規定的表示。R保留1–105；S為同來源摘要加101–105；M為固定兩層map加101–105，正文按需讀取。後續承接該組原生窗口，只追加目前可查上界與當次原文，不再次預載舊map、摘要或同一段原話。
- [study_tools.py](study_tools.py)：共用正式 JD 讀寫、差異查詢及原話工具；只有M列出並准許Memory讀取。即使資料庫有Memory，R／S猜工具名稱也會被拒絕。本批不重新整理Memory／摘要，也不提供背景整理或手動輪前壓縮工具。
- [test_study_runner.py](test_study_runner.py)：真資料庫、真工具、真checkpoint；`httpx2.MockTransport`提供合成計數及模型回應。測試不讀模型憑證、不送付費請求；模擬900／160,000的數值僅用來觸發程式分支，不是本批實際Context token。

原生輸出接續沿[OpenAI手動管理對話狀態](https://developers.openai.com/api/docs/guides/conversation-state#manually-manage-conversation-state)的完整項目原則：保留 reasoning、工具往返及 assistant `phase`。一般Response轉入下次請求時沿產品現有投影移除項目頂層的 `status`，原始回傳另存；這不是只取文字，更不是刪掉推理項目。standalone compaction則沿用**整份返回output**，不只留下加密項目。

### 實際核對範圍

| 測試 | 可支持的結論 |
|---|---|
| R／S／M各完成兩輪，兩輪間關閉並重開SDK client及Postgres saver | 第二輪由資料庫恢復第一輪完整可重播窗口；合成加密狀態、公開訊息階段、工具結果及順序均保留，不靠記憶體列表接續 |
| 每輪改JD並引用當次輸入 | 正式職務名稱確實更新；來源身分與新正式序號106／108一致，顧問答覆為107／109；不是只檢查模型宣稱成功 |
| 比對起始輸入與工具集合 | R/S/M分別取得規定表示；M未預載任何一份Memory正文。合成兩輪未出現後續生效日與grading欄位；完整凍結Prompt仍須再檢查，不能把此測試稱為所有洩漏路徑均已驗完 |
| R／S嘗試讀未提供的理解map | 即使有已發布快照，也返回 `scope_not_allowed`，不返回物件列表 |
| 第一個完整工具Step後模擬160K，返回含user項目與加密項目的compact output | 恰好壓縮一次，下一請求input與整份output相同；本次員工輸入及App參考沒有重複追加。壓前工具呼叫已有配對結果 |
| 已寫候選後，下一次生成回傳終止型錯誤 | 正式JD與105則原話不變；候選及checkpoint保留供診斷，沒有偷偷提交或自動另起新Turn。最終失敗清理是既有產品行為，本研究整批停止處置仍待接線 |
| 首次完整請求超128K、或下一輪已保存歷史需要再次換窗 | 在生成前停止，不呼叫輪前native compaction，也不重送下一次生成；原話初始選取的未完部分見§4 |

### 測試過程與結果

初版研究runner為未實作占位，三組測試先失敗後才接入產品流程。接線中補齊輪中compaction所需的 `recovery` 參數，並核對現有轉接格式：JD成功回傳是短文字 `updated`，不是JSON；一般Response重播不含頂層 `status`。獨立唯讀審核另指出正文未預載測試讀錯fixture欄位，已改為實際的 `objects[].content.body`。這些是研究接線與測試修正，不列為模型品質問題。

一次測試收集因共享工作樹的公版JD契約尚未生成而中止，當時未執行研究斷言。該契約可用後，最終測試仍使用產品原有PostgreSQL fixture，沒有保留第二套資料庫初始化或改動他人的功能。測試只建立及回收自己的隨機 `t02_…` namespace，不清理原研究資料庫。

完整研究資料包**17項通過，68.19秒，exit 0**：§6既有8項加本節9項。新增三份研究模組的嚴格型別檢查、整包Ruff規則與格式檢查通過。這是機制接線結果，**沒有新模型品質成績、實際壓縮率或三組成本排名**。

最後增補「下一輪輪前計數確實讀到上一輪完整窗口」斷言後，本節9項再次通過，24.75秒、exit 0。六份原件SHA-256仍全部相符，本頁及比較設計的27個本機檔案連結存在（不含錨點核對）。

重現方式沿§6設定本機測試資料庫，再執行：

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -m pytest -c apps/api/pyproject.toml docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/ -q --tb=short
$env:MYPYPATH = 'S:/caliburn/apps/api/src'
apps/api/.venv/Scripts/python.exe -m mypy --follow-imports=silent --strict docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/study_runner.py docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/study_tools.py docs/experiments/product-validation/data/context-reset-comparison-2026-10-05/study_context.py
```

本節完成後的整批接線進展見§8；既有底稿、來源與判準不需重做。

## 8. 三組共用指引、排程與外送護欄

### 指引與方法差異

[共用指引](prompts/common.md)保留工作分析、責任邊界、精確條件、局部修訂與直接來源規則；[原話](prompts/raw.md)、[摘要](prompts/summary.md)、[Memory](prompts/memory.md)只說明各自入口。由[組裝函式](study_prompt.py)載入兩份固定文字，不讀未來續訪或評分檔，也不混入正在開發的公版JD檢索。

Memory正文足夠就停；摘要也能直接支持分析與答覆，不強迫逐條回查。摘要目前不是產品可引用的物件，因此新增JD來源時仍須讀必要原話；M可引用已讀理解或情境。這是**現有來源能力下的方法比較**，不是只換文字表示而其他一切完全相同的消融。必要的來源回查成本照實列入，不能藏掉這個差別。

共用內容由既有工作分析、訪談校準與JD撰寫指南收斂，沒有按八題補答案。依[OpenAI Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering#version-prompts-in-code)，將角色規則與當次資料分離、提示存入版本管理；依[模型提示指引](https://developers.openai.com/api/docs/guides/latest-model#prompting-best-practices)，效果須以選定模型及工作負載實測。這些是設計依據，不是本批品質成績。

### 執行與可回查原件

- [prepare_study.py](prepare_study.py)：只在本機驗原件hash、保存來源程式包及manifest，不建立模型client或讀取金鑰。已存在的目的目錄拒絕覆寫。
- [study_window.py](study_window.py)：R先測完整原話，必要時逐單位計數，第一次符合128K即保留；不用離線字數冒充provider token，也不假定刪字後token必定單調。
- [study_batch.py](study_batch.py)、[run_study.py](run_study.py)：三組各自使用新研究namespace、同一起始JD與自己的歷史。每段保存exchange、正式product及事件；單組容量停止不改其餘組，未知失敗不另送新Turn。
- [study_guard.py](study_guard.py)：三組共享一個外送帳本，生成前須有相同請求的計數；限定官方直連及Luna／high設定。先持久保存占用再外送，未知結果不釋放占用，也不自動重送。時間、次數及累計估算US$2同時限制；本批金額／時間依下方授權。
- [study_manifest.py](study_manifest.py)：檔案、Prompt、工具或依賴變動即拒絕，`started.json`與既存trace阻擋無聲重跑。這是單次研究執行，不另建自動恢復系統；停止後原件及研究資料保留供判讀。

trace保存明文請求／回覆、工具與用量；加密reasoning／compaction只保留hash及長度，不輸出憑證。完整原生項目由研究資料庫的產品checkpoint保存。發生中斷時，已完成exchange、每段product、namespace定位及外送帳本可以互相核對，不把沒有收到結果當成零花費。

本機USD是固定單價下的估算，不是帳單。遠端計數每次保留US$0.0001行政估占；standalone compact沒有輸出上限參數，採模型128K最大輸出作預留假設，不能保證供應商最終帳單恰在預留內。已知使用量超界先記錄、再停止下一筆外送。HTTP錯誤（含429）先停止，不擴張重試；後續是否續跑需另決定。

### 反例、修正與驗證

| 發現方式 | 修正及驗證 |
|---|---|
| 原話選取的四個行為測試先失敗 | 放得下保留1–105，超量才依序縮短；共同101–105不能移除。全程使用同一完整請求計數，不靠評分答案選擇資料 |
| 凍結／排程測試先失敗 | 保存不可覆寫來源包、拒絕來源變更與同批重跑；輪換R／S／M並分開單組容量停止與一般失敗 |
| 首次完整整合試跑在第一筆計數前出現 `missing_frozen_policy` | 補接manifest至HTTP護欄；之後24段試跑完成，三份JD各自改寫、各保存8段exchange，正式歷史由105增至121則 |
| 獨立審查指出壓後仍超門檻會誤判一般故障 | 只將有合法容量證據的超量、壓後仍超限列為該組capacity stop；設定或計數格式錯誤仍停止整批。新增兩個先失敗反例及一個不得吞錯的反例 |
| 獨立審查指出新加入migration不在舊hash清單 | 使用同一選檔規則比對完整集合，新增／刪除都拒絕，再驗內容hash；不掃與本研究無關的其他目錄 |

最終整包測試 **93項通過，75.79秒，exit 0**。其中18項使用真PostgreSQL（含完整三組24段排程），其餘75項檢查Prompt組裝、凍結、窗口與外送護欄。模型端全為`MockTransport`；沒有使用真金鑰或發出新provider請求。整包Ruff、格式與15份研究程式的strict mypy通過。

測試只回收自有的隨機namespace；正式資料、原研究副本及服務均未啟停或改寫。`prepared-01`保存本次可重現的Prompt、工具schema、程式／依賴hash、六份來源hash、固定24段順序及來源程式包。若工作樹之後改動，執行前會拒絕；應重新審核準備，不可覆寫舊manifest掩蓋差異。

### 本批授權

使用者於2026-10-05明確同意新增最多 **US$0.25／45分鐘**，計入原累計US$2。啟動前估算占用為US$1.322929315，因此本批估算總占用不得超過US$1.572929315；未知結果的預留也算占用。固定Luna／high、資料及判準，達界線即停止、不補跑。原前52段及Memory／摘要不重建；兩種材料建立成本另見原研究，不能因本批重用而算成零。
