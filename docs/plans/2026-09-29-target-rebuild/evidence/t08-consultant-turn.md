# T08／T09 第一切片：固定 Context → 工具 → 正式完成 → 畫面重取

- 日期：2026-09-30；狀態：**局部接線通過合成 provider＋真 PostgreSQL，真模型 A／Memory／PDF 與暫停接續已有證據；T08／T09 整體未完成**。
- 權威：[A Context](../../../specs/2026-09-26-consultant-context-and-state-design.md)、[共用執行](../../../implementation/agent-execution.md)、[介面](../../../implementation/interface-and-delivery.md)。不另定產品規則。
- 初始真 API 阻塞已解除：Owner 已在 `apps/api/.env` 配置 key；只讀此鍵，不載入舊服務設定。直連協定結果見 T06，下方另記真產品 Demo；早先合成 provider 測試不升格為模型品質證據。

## 1. 已接上的 owner

`agents/job_consultant/context_binding.py` 以 sync checkpoint 固定一次本輪 request、Memory／訪談上界及 JD 候選基準。組裝先用合法歷史／完整 C，再 user-role App 參考資料，最後原始員工輸入；恢復不重取最新版 maps 或重加原文。

`agents/job_consultant/runner.py` 組合 direct Responses、共用 `run_response_loop`、工具 prepare／execute 與原預算 owner，不是另一份 retry engine。JD 原命令以型別化 JSON 保存後才執行，同回應的工具依序執行。A 輪前使用 128K 檢查，共用機制提供 272K 保險；不默改 history、不交給 server-side compaction。

`workflows/consultant_completion.py` 在同一短交易採用正式原話／答覆、候選 JD、合法接續歷史位置及完成資格。回應成功與正式提交不同。第一切片未註冊背景通知；後續 §5 已沿既有 Memory owner 接線，不用假的成功回傳。

`bootstrap.py` 的 lifespan 管理 DB、官方 saver、direct SDK 與本地 supervisor。輸入提交後只喚醒掃描，待執行事實仍在 PostgreSQL，不以 UI 或記憶體 task 作唯一保存。未配置模型時 `POST /inputs` 在接受前回 503；owner 測試顯式覆寫派送 dependency，正式應用沒有假模型 fallback。

已知不可續行的 provider 拒絕、模型／容量／預算界線，由 `run_supervised` 結束為失敗並撤回本輪候選，不分配正式訪談序號。不 catch-all 宣告失敗：保存不明、仍持有原 R／C、DB 中斷等保留给恢復責任，不丟原結果、不無限重跑。日誌只用固定訊息、類型與 execution identity，不輸出 SDK body／原話。

介面按需查 scoped 狀態，完成才重新讀取正式訪談／JD。原 POST 確認遺失可用既有 command 查回；localStorage 只保存定位、不保存原話全文。此切片使用輪詢，不宣稱已提供 SSE／逐字生成。

## 2. 有界驗證

沿相同 Node 24／Python 3.14 與隔離 PostgreSQL 測試環境，無舊資料遷移。

| 驗證 | 結果／層級 |
|---|---|
| runner＋completion＋工具路由 | 30 passed；真 PG、官方 saver、合成 SDK transport |
| HTTP 旅程及缺設定／401 | 3 passed；先 Red：缺設定仍接受、尚無派送、已知拒絕一直 active；修正後正式序號為 1／2／3，401 只請求一次且不正式化輸入 |
| 合併 HTTP／runner／status | 7 passed（與前列重疊，不相加） |
| 訪談 UI | 8 passed；含重開、原 command 確認與未完成狀態 |
| 前端 production build | 通過；764 KB 主 chunk 警告留 T15，不調高門檻掩蓋 |
| 靜態／文件 | mypy 190 source files；相關 Ruff；23 檔／397 連結通過 |

主要命令：`pytest tests/integration/test_consultant_http_execution.py -q`；`vitest run src/features/interview/InterviewComposer.test.tsx`；`pnpm --filter @caliburn/frontend build`。真 PG 需指定 `CALIBURN_TEST_DATABASE_URL`，skip 不算通過。

另建獨立 `caliburn_target_demo` DB（loopback 55439），API 8100／Web 5173 啟動；無復用舊正式資料。local trust 僅為隔離本機 Demo，不是部署認證規範。Windows Vite 初次因 sandbox `spawn EPERM` 失敗，相同命令獲授權後成功，沒有修改 Vite／系統安全政策。

## 3. 第一切片後續範圍（歷史狀態）

第一切片當時尚缺控制 HTTP／UI、公開中間訊息／候選預覽、完整 JD 八入口、Memory 背景要求與 B1／B2 runner、真 provider、程序故障與自然長訪談品質。後續交付分見 §4–5、T09／T10／T11 證據；尚未驗收的整體任務仍以任務表為準，不因合成最短流程勾 T08／T09 或整個 Goal 完成。

依據：[FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)、[Python task 強參照與取消](https://docs.python.org/3/library/asyncio-task.html#asyncio.create_task)、[PG session advisory lock](https://www.postgresql.org/docs/current/explicit-locking.html#ADVISORY-LOCKS)。這些是機制契約；固定 context、訪談資格及整輪採用是本案既定保證，不聲稱框架自動提供。
## 4. 有界真產品 Demo 批次（執行前：2026-09-30 10:32 台北）

沿 T06 已通的直連協定，下一批使用已啟動的隔離 `caliburn_target_demo`，另建全合成職務檔案，不送私人訪談／repo。最多 **3 次員工輸入**，每輪沿產品上限 64 model Steps、32 calls/Step、5 attempts/request、512 outbound attempts、900 秒、US$1 管理預算；序列執行，整批最多 US$3 管理預算，遇相同故障先診斷，不自動換模型／重開 Turn。使用 `gpt-6-luna` medium、default、每回應最多16,384 output tokens。已核生成費率與 request 預留沿既有 owner；不是對供應商帳單硬保證。

目標：真 UI 輸入 → 專業引導／有據候選編輯 → 正式答覆與 JD 保存 → 重新讀取同一結果；PDF 沿 T13 已驗 renderer。先驗產業務效果，不以 HTTP 200 當品質。記錄輸出、引用、模型／工具次數及缺口；這個小型 Demo 不代替 T16／T17 長訪談。

### 4.1 第一輪拒絕與契約修正（10:38 台北）

第一個全合成 UI 輸入在 token count 遇 `request_rejected`，尚未生成；失敗輸入未正式化、JD 沒有修改。先讀 [token counting 官方契約](https://developers.openai.com/api/docs/guides/token-counting)、[strict function calling](https://developers.openai.com/api/docs/guides/function-calling#strict-mode) 與 [支援 schema](https://developers.openai.com/api/docs/guides/structured-outputs#supported-schemas)，再以單次 count、無生成／無重試的 `probe_consultant_tool_schema.py` 診斷取得：`read_jd` 的 `properties.view` 同時有 `$ref`／`description`，API 回 400 `invalid_function_parameters`。

根因是 `jd_reads.py` 唯獨从生成後 Pydantic type 再造 schema，沒有沿共同 `function_definition` 使用權威 JSON Schema。改回共同機制，保留 strict 與原驗證，沒有加第二套 schema 清洗器。兩個先失敗的契約反例轉綠，read／role routing 共 **21 passed**；同一全工具集再次單次 count 成功（4,288 input tokens）。這兩個額外診斷均只有全合成指令＋工具定義、每次最多 30 秒、1 HTTP、0 generation、0 retry；計數不宣稱免費。

修正後才透過 UI 取回原文，以新輸入身分開始批次第 2 輪；不是重啟失敗的原 Turn，也沒有把被撤回輸入塞回合法歷史。

### 4.2 第一個真模型完整 Turn（10:42 台北）

全合成庫存管理訪談由 IAB 輸入、非直接塞 JD：4 次模型請求／4 次 count，無重試，`execution=53ade73c-f02f-4657-9898-fc6e7101d1e6` 正式完成。保存 4 個 profile 欄位、1 個職責、1 個任務（1 成果、3 要求），10 個直接依據均綁成功輸入正式序號 2；失敗的前一輸入仍非正式，序號為 1 開場／2 員工／3 顧問，沒有跳號。資料庫核對引用不是只看回答宣稱。

模型保留月底頻率、主管核准、不可自行改帳／採購／補貨的界線；未虛構 KPI／K／S，最後針對尚未釐清的每日異常追蹤繼續提問，沒有宣稱全稿完成。這是單一具體案例的初步品質觀察，不代表所有指南或長訪談已驗收。

重新開啟同檔案可讀原正式答覆與同份 JD，不重生。實際 API 匯出 1 頁 PDF，文字抽取與 Poppler 視檢確認職稱／任務／成果／要求完整且中文正常，未輸出合成員工姓名。證據在本機 `.research-tmp/target-demo-ai-first-turn.png`、`target-demo-ai-jd.pdf`／`.png`；未提交合成產物。

資料庫報告生成費估計合計 **US$0.001645955**；count 費用未核，這不是完整帳單。背景 Memory、長訪談、真模型取消／暫停與 T16／T17 品質仍未驗，不因這次成功將 T08 或 Goal 勾完成。

## 5. 顧問 → 背景整理的整合（2026-09-30 10:57 台北）

沿 `request_memory_consolidation` 原無參數契約，canonical schema 生成 Python／TS。模型不填 file、execution、frontier 或 command；App 先保存可恢復 intent，工具才交原 `MemoryConsolidationWorkflow`。可整理資格由 A 完成與正式員工輸入推得，不新增第二份通知表。取消／失敗仍不能讓候選輸入被背景使用。

composition root 使用同一官方 saver、SDK 與程序 leader，組合 B1／B2 私有 runner 和既有 parent／supervisor。原生 saver serializer 明確允許所需 Memory checkpoint 型別；不以自訂序列化或第二套 persistence 替代。正常關閉先停止 Memory、再停止 A／釋放 leader，最後關閉 provider 與 DB；異常 leadership 故障另作驗證，不能用正常關閉證據冒充。

未恢復的背景失敗只在 A 新輪 user-role App 資料中提供已分類原因與可繼續訪談／原話回讀的提示；同輪不偷換 context。沒有失敗時不加入噪音狀態；不造技術例外全文給模型或使用者。

本輪驗證：

- 先 Red：新工具未被宣告、完成 A 後沒有背景發布、失敗狀態未進 App 資料。接線後相應測例 Green。
- 809 個 unit／contract tests 通過；mypy 234 files、相關 Ruff 通過。
- 46 個真 PostgreSQL 整合測試通過（completion／runner／recovery／controls／HTTP／Memory parent／supervisor／歷史定位）；包含一次完整合成 SDK 的 A → B1 → B2 → 下一輪 A。此處 provider 是 synthetic transport，不能稱為真模型。
- 回應／工具可恢復審查另確認：工具業務已提交但觀察未寫入，再接續承接原結果，沒有重複效果。尚不是所有作業系統強制終止時點皆已測完。

### 5.1 真模型背景旅程 manifest（執行前）

續用 §4 同一全合成檔案與尚餘第 3 次員工輸入，不另擴張 A 批次。增加**最多一個 Memory 批次**：同 `gpt-6-luna`／medium／default／store=false／all_turns，B1／B2 共享產品 execution 預算（64 model Steps、每 Step 32 calls、每請求 5 attempts、合計 512 outbound attempts、900 秒、US$1 管理預算；單回應最多 16,384 output tokens）。並行只有 A 與其完成後的背景工作，不啟動額外合成檔案。原角色 schema count 的兩次預檢另外記在 T10；不是生成／品質驗證。

目的：確認真員工回覆接續、A 自然要求整理、有效訪談固定範圍、B1/B2 產生與引用／快照正式發布。只送合成庫存案例與必要角色指引／工具 schema，不送 repo 或秘密。任一相同不可恢復故障先停、研究、離線修正；不能為展示偷偷發布合成 Memory 或無限重啟。管理預算不等於 provider 帳單硬限制，費率與 count 限制沿原證據。

結果見 §5.2；不提前勾 T10／T11／T16／T17。

### 5.2 真 A → B1 → B2 → 正式快照（11:09 台北核對）

同一 UI 中補充每日負庫存／帳物不符查核、現場同事複點、本人追蹤及主管核准界線，未人工編輯 JD。A execution `2ce38e7a-baa4-476a-ad4d-5617f21c4100` 以 4 次 model、5 次 count 完成，零重試；新增每日異常任務、2 成果／2 要求、知識／技能及任務關係、協作對象，保留前輪月末工作。正式序號接續為 4 員工／5 顧問，最後仍引導低頻／專案工作，不宣稱全稿完成。

A 在執行中提出整理要求，完成後 background execution `1d709227-d539-4ccf-bca7-6f16aa26d596` 才開始。B1／B2 合計 8 次 model、8 次 count、零失敗／重試，發布 snapshot `23deb276-1e4d-44b0-b72a-018871cbb71f`，處理邊界為 **4（員工輸入），不是 5（顧問答覆）**。SQL 沿已發布選用關係核對：

- 情境「月底庫存盤點與差異證據整理」引用正式訪談 2；「每日庫存異常查核與追蹤」引用 4。
- 理解「庫存核對、異常追蹤與差異證據整理」引用兩個情境；兩條引用的修訂均等於此快照選用的修訂。
- 正文保留兩種工作的責任差異、主管核准、非採購權責，以及尚未確認的結案條件，沒有把未知寫成已知。

生成 usage 估算：第二個成功 A **US$0.002398345**，B 批次 **US$0.002610745**；count 費用仍未核，不能當完整帳單。2 頁 PDF `.research-tmp/target-demo-ai-jd-expanded.pdf` 已實際渲染兩頁並視檢中文、任務／O／P／K／S 與協作對象；不含員工姓名。UI 證據 `.research-tmp/target-demo-ai-second-turn.png`，合成產物不提交。

品質限制：共用協作描述對「現場同事複點」的措辭需要繼續核對是否過度延伸到月末工作；Memory 情境／理解的資訊分配與重複量仍須 T14 rubric 審查。下輪 A 讀新快照尚待真模型驗證，不能由發布成功推論已完成。全 PG 回歸此時為 699 passed、2 failed、2 skipped；公開進度測試缺新 pause_requested 契約已修、專項 2 passed；App 重建後輸入重取的 503 正在診斷，不隱藏整體紅燈。

### 5.3 已發布 Memory 接續與更正 manifest（執行前）

在同一全合成檔案追加最多 **2 次 A 輸入、1 次 B 批次**，總管理預算最多 US$3；每個 execution 的模型、reasoning、輸出／Steps／calls／attempts／900 秒上限與 §5.1 相同。序列提交 A，不另建資料、無私人資料，不透過直接 SQL 修改 JD／Memory 造出結果。

目標：驗 A 綁已發布快照、按需使用已整理事實／來源；補充或更正責任條件後能續改，並與 T07 來源／核對工具相容。新來源 schema 先用既有 probe 作一次 count 預檢（1 HTTP、0 generation、0 retry、30 秒，全合成），另記結果，不假設免費。若 A 自然提出整理，只允許這一批；其他工作留後續 manifest。未知失敗不直接付費重送；先核對已保存原件與原業務效果。這仍是有界整合樣例，不等於長訪談品質與全故障 gate 通過。

### 5.4 第三輪更正、真模型暫停接續（11:29 台北核對）

14 個 A tools 的一次 count 預檢接受（4,646 tokens；definition SHA-256 `73d9bf2322d2ac534df39d97ab9a115e260fa4fd5ec08e10cb0e618a1f2a652f`）。隨後透過 UI 提交本批第 1 次輸入，明確區分月底／每日的複點责任及每日結案條件，execution `a9850a7e-bcd1-4673-96ef-0ece3202568f`。

- 點「暫停處理」先顯示等待安全點；重開頁面後顯示已暫停。DB 同時為 `paused`，正式訪談仍 1–5，未提前納入本次輸入。畫面保留原輸入及候選預覽、人工 JD 不可改。
- 點「繼續處理」沿同一 execution 接續。官方 saver 的 `initial_context.binding` 確認固定 snapshot `23deb276-1e4d-44b0-b72a-018871cbb71f`、歷史上界 5；沒有重開新 Turn 或換 Memory。
- 讀取保存的原生 function calls（不解讀／輸出 opaque reasoning）確認：A 先讀兩層 map、兩個情境及理解、JD map／局部資料，然後有序修訂／讀回候選。A 實際使用 `confirm_reference_alignment`，也用 `current_input` 建立新依據；不是只聲稱完成。
- 正式完成後序號 6 員工／7 顧問；月底本人先複點、每日請現場複點、結案條件及協作的每日適用範圍已在實際 JD UI 中確認。原先錯誤的籠統文字沒有殘留；核准權仍歸主管，最後繼續追問其他工作。
- 10 次 model、11 次 count，0 失敗／重試；生成 usage 估算 **US$0.007735485**，count 費用未核。較前輪多讀取、回讀與修订步驟是品質／效率後續評估資料，不以成功掩飾成本。
- A 自然提出整理，完成後第二個 Memory batch `62403926-de89-42cc-a39c-d3c3fda2ce09` 已完成：8 次 model、10 次 count、零失敗，生成 usage 估算 **US$0.003987115**，count 費用未核。發布 snapshot `08e75187-9ad6-477e-9f85-d2cefc779663`，position `44fce8ed-9220-4c2d-95d4-2c4e16efbfbb`，正式訪談邊界 **6**；SQL 確認理解的兩條情境引用修訂均等於本快照選用修訂。這是結構核對，不取代逐段語意審查。此項消耗 §5.3 唯一允許的 B 批次；下一次若再跑背景生成必須另記 manifest。

畫面證據 `.research-tmp/target-demo-ai-paused.png`、`target-demo-ai-corrected.png`。這證明一個真模型 Step 安全點的暫停／重開／接續，不是所有 crash 時點、長訪談或普遍品質保證；取消及未知原結果仍需原 gate 的專項證據。

同時窄回歸：unit／contracts **897 passed**；JD CRUD／source／diff／undo 真 PG **48 passed**，Ruff 與 mypy **236 source files** 通過。這不是完整 PG suite 已修復的宣告；其 503 重取問題仍由相應 owner 處理。

### 5.5 整合回歸與重啟（11:38 台北後）

前述 503 原命令重取已由原 HTTP／workflow owner 修正，見 [readiness 證據](t08-input-replay-readiness.md)。新工作仍須服務就緒，已接受的相同命令先承接原結果；不把失敗／取消復活。

- 完整 `tests/integration`：**725 passed、2 skipped**（448.95 秒）。兩個 skip 為真 Chromium PDF，原因是整套命令只設產品 PDF 變數、沒設測試專用變數；再以 `CALIBURN_TEST_PDF_FONT`／`CALIBURN_TEST_PDF_CHROMIUM` 明確補跑 `test_pdf_rendering.py`，**2 passed**（8.05 秒）。不將 skip 記成通過。
- 最新 unit／contracts **902 passed**（9.82 秒）；初次 sandbox 暫存目錄權限失敗不算通過，同命令在可用權限下重跑。Ruff check／format **355 files**、mypy **236 source files**、canonical codegen `--check` 通過。
- UI 焦點 race 經受控轉場反例修正後，主線獨立全前端 **86 passed**、TypeScript 與 production build 通過。仍有約 777 KB 主 JS chunk 警告，留 T15 量測，不調高門檻掩蓋。
- 確認 Demo 無執行中／暫停工作後，僅重啟已確認身分的自有後端，不動 DB。health 200、非法 Host 400、跨站 Origin 寫入 403。IAB 重開仍讀回正式序號 1–7、原完成狀態與更正後兩種工作，不新增模型請求。

這是目前整合版本的回歸，不等於 T06–T17 全部 gate。新發現的取消期間完整原件 handoff 與跨程序未明 attempt 調度仍待修；T09 即時逐片段公開串流仍待接線，目前只有已保存完整 commentary 的查詢／歷史回看。全套輸出保留本機 `.research-tmp/target-full-pg-20260930c.log`、`target-unit-20260930i.log`、`target-web-20260930f.log`，不提交原生推理或合成產物。

### 5.6 公開 commentary 真產品驗證 manifest（執行前）

承接 §5.3 尚餘 **1 次 A 輸入**，不增加 A 次數；若該輪自然通知整理，增加最多 **1 次 B 批次**。本次剩餘工作總管理預算最多 US$2，其餘模型、reasoning、輸出、Steps、calls、attempts、900 秒與資料範圍沿 §5.3。只在 shared 原件 handoff、HTTP／UI 串流專項及整合測試完成後重啟自有 Demo 服務；不改舊的已保存 request transport。

在同一合成檔案補充一項低頻工作，觀察公開 commentary 是否在正式完成前出現、候選與正式結果是否區分、完成後公開中間訊息是否可回看。模型可能不產生 commentary；不得以 App 編造文字或重跑直到出現來冒充成功。不顯示 reasoning／工具參數；不為此啟用另一個 reviewer／judge。失敗先保存證據診斷，不自動加測或提高預算。

此批目的為新串流整合，不代表全部職務分析品質、所有程序故障、T09 或 Goal 完成；實際結果另外追加。

### 5.7 串流接線後的第四個真 A Turn（12:02 台北核對）

以 UI 補充每季財務抽查佐證整理、缺漏補件及不負責查核結論／核准的界線；A execution `e1178998-0df0-44da-929d-bbef0ce33ae0` 正式完成，5 次 model、6 次 count、零失敗，usage 生成估算 US$0.007175850。完整公開 commentary 已可從該輪歷史回答展開，內容為核對 JD 架構並保留財務／本人責任界線；正式訪談只增加員工 8／顧問 9，commentary 無正式序號、不可引用。

正式 JD 新增季度抽查任務、調整職責與目的；最終答覆繼續詢問資料缺漏交主管後的責任，沒有自行猜測。A 自然通知整理，B execution `07be6b4c-d230-4c93-beb9-2d5fd1f710d5` 完成，6 次 model、8 次 count、零失敗，usage 生成估算 US$0.005738715；snapshot `48c31c96-f1db-4fc2-a099-89c6a23103e6`、position `17bf6b90-f80b-45f6-a9f2-3c1b1e79cfd4`、F=8。此批已消耗 §5.6 全部 A／B 額度；count 費用未核，以上不是完整帳單。

真 SDK 已使用 streaming request，瀏覽器 scoped SSE 連線回 200，原生完整 commentary 經原保存路徑成為歷史。**本次再次觀察畫面時 Turn 已完成，沒有截到完成前的即時 delta；不可宣稱已目視驗證真模型的逐片段顯示或斷線重連。**離線實際 SDK wire／ASGI SSE／UI 測試各自驗了該段傳輸，但不能替代尚未觀察的完整真產品時序。

接線後主線 fresh：unit／contracts **945 passed**；SSE／原件角色 handoff／A HTTP／Memory HTTP journey 真 PG **21 passed**；前端 **95 passed**、tsc 通過；Ruff check／format **361 files**、mypy **239 source files**、canonical codegen `--check` 通過。sandbox 的暫存目錄／spawn 錯誤以同命令升權重跑，不改驗證標準。這輪未重跑整套 PG；先前 725 項全 PG 結果仍只代表當時版本。

先確認無 active／paused 工作，再重啟已核身分的自有 backend；現於 loopback 8100／5173，沒有資料清除、舊碼切換或對外部署。瀏覽器確認序號 1–9 與歷史公開訊息，Demo 可操作；Goal 仍未完成，未知 attempt 自動恢復、長訪談品質及最終交付 gate 留原任務。
