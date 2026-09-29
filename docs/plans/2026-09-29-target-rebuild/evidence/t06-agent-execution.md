# T06：共用原生模型／工具執行

- 日期：2026-09-30；本頁只記研究、實測與接續，完成狀態在 [tasks](../tasks.md#t06-共用原生模型工具執行機制)。
- 契約：[共用執行](../../../specs/2026-09-27-shared-agent-execution-and-state-design.md)；工程唯一入口：[Agent 接線](../../../implementation/agent-execution.md)。沒有新造產品安全點、ResponseStore、Provider 平台或私有推理解讀。

## 1. 第一切片：原生回應保存與路由

主代理完整讀任務契約與工程規範，使用 OpenAI Docs 搜尋並取得官方原文，實際讀 stateless、部署、phase 及 function-calling 段落；再檢查新目標鎖定 SDK 3.20.0 的型別。研究子代理另唯讀核 LangGraph 官方頁／安裝原碼及記憶體 probe，分工與輸出遵守 Goal／文件路由；沒有代寫主代理的 Responses 元件。

### 研究結論與界線

- OpenAI 要求全部原生 output items、opaque reasoning、phase 與 call 配對接續。兩份官方 Python 範例對 output `status` 處理不同；依部署範例做最小出站投影，同時保存完整原件。沒有宣稱任意欄位遠端已接受；由有界 provider gate 解決，不能用假 HTTP 200 代替。
- `response.completed` 可能仍有工具呼叫，`output_text` 也可能只是 commentary。只有原生項目可確定下一個執行動作；模型 final 仍不是 JD／訪談／Memory 正式完成。
- 新目標安裝 LangGraph 1.2.12、checkpoint 4.2.0、PostgreSQL saver 3.1.2、psycopg 3.3.6。子代理核 `sync`、pending writes、一般 resume 與 replay；主代理亦直接讀 `pregel/main.py` 的 checkpoint 等待點及 `serde/jsonplus.py`。沒有因 saver 能 import 就認定完整恢復成立。
- 官方 `JsonPlusSerializer` 可重用；`pickle_fallback=False` 不等於禁止任意 msgpack 型別。此次保存 plain dict/list，明確 `allowed_msgpack_modules=None`；後續 prepared dataclass 若採原生 allowlist，需逐個遞迴型別與新程序測試，不自製 serializer。
- 子代理的記憶體故障 probe 提醒：`aput` 與 `aput_writes` 的成功／失敗可不同，只有完整 checkpoint 已成立時，pending-write 報錯不必然表示工具完全沒執行；兩種皆失敗則沒有原 R 可恢復保證。這是**子代理研究觀察、尚未成為主線持久故障驗收**，下一切片須重現。不能把所有 saver 例外都當成「模型必須重跑」或「工具肯定沒做」。

來源連結集中 [工程接線 §4.1](../../../implementation/agent-execution.md#41-已落地的原生回應邊界t06-第一切片)。LangGraph 官方入口：[checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)、[time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)。不把單一機制稱為全業界唯一共識。

### 實測

1. 行為 Red：路由初始直接視為 final；含 commentary＋function call 的案例 **1 failed**。實作原生項目判斷後通過，不是 import 失敗冒充 Red。
2. 21 項路由案例：零／一／多 call、final 與 call 共存、只有 commentary、refusal、未完成 response／item、重複 call 身分、未配置工具／模式、未知 phase；不解析私有 reasoning、不任意推測最終答覆。
3. 8 項 serialization／SDK mock 契約案例：原件含 metadata／alias／status 可原樣取回；出站只去頂層 status；全部 compact output 保留；結果有序配對；HTTP 捕獲確認實際 SDK 會送該 payload。未外連 provider。
4. 沿用 T01 的 `test_graph_postgres.py`／`checkpoint_worker.py`，將純範例接成實際原件 helper：第一程序保存 R，第二程序以 `None` 恢復、讀原 R 再配原 call；第二程序模型呼叫 **0**、觀察節點 **1**。不同 thread 無資料；只有新建隨機 test schema 被清理，共享 PostgreSQL 程序與 database 保留。

在 `apps/api` 執行：

```powershell
$env:PYTHONUTF8 = '1'
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
./.venv-target/Scripts/python.exe -B -m pytest tests/unit tests/contracts tests/integration/test_graph_postgres.py -q -p no:cacheprovider --tb=short
./.venv-target/Scripts/python.exe -m ruff check src tests --no-cache
./.venv-target/Scripts/python.exe -m ruff format src tests --check --no-cache
./.venv-target/Scripts/python.exe -m mypy --cache-dir ../../.research-tmp/mypy-t06 src
```

結果 **408 passed in 10.46s**；Ruff check／format（156 files）與 mypy（137 source files）通過。明確收緊 serializer allowlist 後，重跑相關契約與跨程序真 PG **9 passed in 3.19s**。沒有改 DB schema、API wire／生成契約或 UI，故沒有重跑所有業務／瀏覽器測試。這不是完整 T06、未知提交或模型效果驗收。

### 獨立審查後修正

唯讀子代理指出兩個具體反例，主代理補測得到 **5 failed、29 passed**：空白 final（含 refusal）不得交付；SDK compact 可保留 user/input_text，但重新 `CompactedResponse.model_validate` 會拒絕它。主代理重新查官方完整 window 契約及 SDK `_models.py`：不自訂 provider schema，不刪 user 訊息，使用 SDK 原有 JSON dump 並從已保存 output 容器完整承接。抑制該已知型別差異的 serialization warning，避免把原話印入警告；不是捕捉並忽略保存錯誤。曾試 Pydantic duck serialization，但鎖定 SDK 的 lazy schema 會觸發 `MockValSer` 錯誤，未採用。

修正後同一 unit／contract／跨程序 PG 集合 **413 passed in 7.84s**、無 warning。Ruff／format 156 files、mypy 137 source files 通過；文件 20 份／312 links 零錯、`git diff --check` 通過。mock 明確比對 compact 原 JSON 與回讀，仍不是 provider 真實 compact 接受性驗收。子代理已關閉，無付費或私人資料外送。

## 2. 第二切片：單一模型／工具 Step 與候選原效果接續

原生回應切片已提交 `5cfbb1da`。本切片直接重用官方 StateGraph，不手寫框架；主代理讀官方 durable execution／checkpointers 與 `pregel/main.py` 的 sync 等待位置。模型與工具依賴僅為窄 callable，Graph 不 import JD／Memory 業務。通過 R 保存才在下一 node 檢查／prepare，通過命令保存才 execute；恢復以 None、不用 checkpoint_id replay。

子代理分工實作 `graph_checkpointer.py` 與 serializer 契約測試，先讀 Goal／責任文件／coding standard，查官方 4.2.0 原碼；主代理審 code 及實際原碼後整合。未允許 constructor 的 Red **1 failed**，allowlist／三種命令／兩 layer／巢狀型別等 **28 passed**。官方 tuple 會還原為 list，即使 allowlist tuple 也不改變；不為此自造 codec，prepared payload 不含 tuple，原生 State 用 list。無 DB schema 或依賴變更。

### 實際反例與結果

- Graph 尚未派工具的初版：**3 failed** 行為 Red；完成 prepare／execute／finish 接線後通過。較早缺 API 名稱的 collection error 不算行為 Red。
- 單一 Step 兩筆工具按序執行；每個 handler 觀察到 R／prepared 已在 saver。第二筆失敗後只重入第二筆，model 與第一筆不重跑。未知 phase 保留 R 後才拒絕。
- 真 PG 模型 checkpoint：`aput` 寫前拋錯、寫後確認遺失都使工具派送為零；重開 saver 後以原生 pending writes／checkpoint 接回，模型總呼叫仍 1。沒有推論成「pending writes 也失敗仍保證可恢復」。測例最初錯誤期待不存在的 caller，已按 fixture 修正，不更動 product 行為掩蓋錯誤。
- 真 PG Memory：先 create 盤點，業務提交後人工注入確認遺失；恢復拿同一 prepared command，得到原建立結果，再 prepare／execute 改名月末盤點。呼叫序列是 model、prepare create、execute create、execute create、prepare update、execute update；原業務操作只有 start＋create＋revise 三筆、物件一筆，沒有正式 snapshot。未自建 receipt。
- 既有跨程序 worker 改用實際 Step 的私有 builder，不是另寫能力示範圖；第二程序模型 0、觀察 1、原生 items 與 opaque metadata 完整。Static interrupt 只用於測試切斷，不冒充使用者暫停。
- 完成 Step 關閉／重開 saver 再 resume 不重新添加 context；完整 final 只是交回下一層責任，不呼叫正式發布。

測試命令（同 §1 loopback test DB）：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit tests/contracts tests/integration/test_graph_postgres.py tests/integration/test_response_step_postgres.py tests/integration/test_memory_tool_step.py -q -p no:cacheprovider --tb=short
```

初次整合 **449 passed in 9.73s**；針對集合 **37 passed in 4.52s**。獨立唯讀審查指出：只靠 caller 記住 sync 不足，重送新 input 至未完成 thread 也會重新呼叫模型。新增公開 `run_response_step` 強制 sync／有界 recursion，拒絕既有 thread 的新 input，以及不存在 thread 的 resume；同原呼叫恢复只接受 None。每 Step 的 call 上限在任何工具派送前檢查。這些准入檢查不取代執行 owner 的單 writer／租約。

追加雙保存失敗反例時，原方案透過 `astream` 捕獲 update 得到 **1 failed**：保存拋錯可以先於 update 交付。改在實際 request callback 捕獲完整 SDK R，核對 saver 無原結果，透過官方 `aupdate_state(as_node="request_model")` 補存後 resume；模型總呼叫 1。這是能力證據，正式 supervisor／保留與工作資格核對尚未接線；不宣告 E03 完成，也不假設程序崩潰後記憶體 R 仍在。

上述追加後同集合 **452 passed in 9.40s**。Ruff check／format **162 files**、mypy **139 source files** 通過，文件 20 份／312 links 零錯、diff check 通過。獨立代理複核兩個 P2 已修，指定 4 tests 與 9 組有界離線 probe 通過（含 call 數恰達上限、完成後公開入口恢復），無新增重大發現。真正 DB 僅使用測例建立的隨機 schema，測後移除該 schema；共享 55439 server／database 留存。無付費、無 `.env`、無真員工外送。本段不是完整 E01–E04 或 T06 完成。

## 3. 第三切片：直連請求與安全失敗分類

第二切片已提交 `a52d76d9`。本切片重新搜尋並取得官方 reasoning、error codes、token counting、standalone compaction 原文，再核 SDK 3.20.0 的 retry、HTTP defaults 與方法簽名。沿 [工程接線 §4.3](../../../implementation/agent-execution.md#43-已落地的直連請求與失敗分類t06-第三切片) 記能力與限制，不自建 Provider／Responses store。

### 反例與驗證

- 初始未關 SDK retry 的 503 測例得到 **1 failed**：實際外送 3 次，不是上層看見的 1 次。明確 `max_retries=0` 後，create／count／compact 與 timeout 都只做原次請求；後續重試必須回執行責任。
- `ResponseRequest` 先複製 context；測例修改原輸入／tools 及曾取得的 payload，不影響 count／create 的一致性。SDK 原返回保留 opaque、phase 及 metadata；compact 保留完整 C，不修改原 W。這是 HTTP MockTransport 證據，不代表遠端已接受。
- 獨立唯讀審查指出 SDK 會跟隨 redirect，把正文轉往其他 host；新增注入不安全 client 反例先得 **1 failed**。改用官方 `DefaultAsyncHttpxClient(follow_redirects=False)`，並拒絕不安全注入；307／308 各覆蓋 create／count／compact，只收到官方 host 的一次請求。子代理重新跑 12 項契約測試通過，原 P2 關閉。
- 安全錯誤分類以已知 quota／permission／capacity／transient 狀態處理；不把 API exception 的原文帶入摘要，不把未知結果當未收費。分類器無自動重試或無限回圈。

受影響 adapter／分類測例 **23 passed in 0.67s**；全 unit／contract **469 passed in 7.86s**。Ruff check／format **166 files**、mypy **141 source files** 通過。命令沿 §1，這次沒有修改 DB／Graph 保存，故不為薄 adapter 重跑全部 PG／UI；既有 PG 證據仍為 §2，不把本次离線測試標成新增持久 gate。

`httpx2==2.13.1` 因直接 runtime import 由 dev 移到 runtime dependency；uv lock 僅變更依賴分組，沒有升版。預設 cache 權限／本機 offline metadata 不足時改用 repo cache，經授權網路取得公開套件 metadata；不把環境錯誤算產品 Red。本批沒有付費模型、`.env`、真員工或 repo 資料外送。

### 持久額度的下一切片方向（尚未實作）

研究子代理唯讀比較 Azure Retry、官方 SDK 與既有 executions owner；主代理採「原工作共用預算、每次外送先持久准入、查回原結果優先」作下一切片方向，不另建通用 scheduler 或 R／C 正文庫。外送許可與結果採用分開：晚到結果仍須計量，失效 writer 不得採用；重啟／B 回交不重置額度。未知費用保留估計占用，不能按零處理。

待驗反例：兩連線競爭最後一次額度；准入後中斷不能拿舊許可再外送；原 R／C 已保存只補結果不重呼；取消後舊結果可記帳但不可進下一步。Standalone compact 沒有 create 的輸出限制、計數 API 也不可假設免費，須在費用規則與預檢 manifest 說清楚。這是工程研究方向，不是上述能力已交付。

## 4. 第四切片：不可重置的工作額度與外送預留

直連切片已提交 `a48b39a1`。讀共用執行 §6–7、既有 executions owner、SQL 交易／程式規範後，核 PostgreSQL 行鎖與 Azure Retry 的當前官方契約：短交易裁決准入，網路在提交確認後；分類及原結果核對由單一工作流程處理，不讓 SDK／Graph 疊加。沒有新增框架或費率猜測。

在既有 executions 內新增固定 policy 與 outbound attempts；原生內容仍由 checkpointer 保存。確切表、程式責任、計量單位及未接線處集中 [工程 §5.1](../../../implementation/agent-execution.md#51-已落地的工作額度保存t06-第四切片)。操作不重置原 policy；logical request／每次 attempt 分開，重用原 attempt 只回紀錄，不能重送。未知成本保留預留；取消後已知成本仍可記入，不授權採用結果。

### Red／Green 與恢復證據

- 初次 migration 的前版識別字少寫尾碼，造成 setup error；修正後才取得真正行為 Red：兩連線爭同一最後額度都成功，**1 failed（2 != 1）**。這不是用 migration typo 當 TDD。
- 在原 execution 行鎖下核額度及新增預留後，兩連線只有一個准入成功。原 reservation／query／state 以獨立 session 讀回，未用 Python mutex 代替 DB。
- 新 attempt 確認遺失後再入返回 `created=False`，額度未加第二次；想再送的新 attempt 被已耗盡成本拒絕。相同 request 改 fingerprint／kind 拒絕；傳輸 attempt 可增加但模型 Step 只算一次。
- 已取消不能新准入；原 attempt 成本可重入記帳，不能改寫既有值。writer 替換後仍用同 policy／成本；新程序讀回原限制並拒絕超額准入。這不是程序中斷後原 provider response 的恢復測試。
- SQL 禁止刪除或改寫預算／原 attempt；全新 namespace migration、重複 upgrade、Alembic metadata／CHECK 比對通過。只清理由 fixture 新建的隨機 schema，保留共享 DB／server。

受影響集合：unit／contracts，加 execution budget／admission、migration，以及原有 Graph／Memory Step PG 回歸，**503 passed in 30.47s**。Ruff check／format（含 migrations，**185 files**）、mypy **144 source files**通過。新增測例皆用合成金額／範圍，不呼叫 provider，也不讀憑證。

獨立唯讀審查未發現阻擋缺陷；除上述 11 項 budget PG 測例外，另做 8 組不落檔探針，含相同 attempt 競爭、鎖等待跨期限、Session 舊資料刷新、取消／stale writer 與暫停續作。這些是代理補充觀察，不另充作完整產品 gate。文件 20 份／316 links 零錯；新增 ERD 用既有 Mermaid 11.17.2／Chromium 渲染並實際檢視，欄位與關係可讀。首次 sandbox 禁止啟動 browser，經准許的 headless 執行完成；不是略過圖稿驗證。

這仍是 T06 計量元件；沒有宣稱已將所有模型請求接入准入，沒有真實費用上限驗收。下一步需以有界 supervisor 綁定完整 payload、原 attempt、R／C 保存及費用採用，檢查 HTTP 等待不持有業務鎖；然後接共同 loop／compact。

## 5. 第五切片：原 R 保存失敗的公開恢復與工作資格

第四切片已提交 `6b0eb918`。主代理重讀本題契約／工程規範，OpenAI Docs search→fetch 核 stateless 完整 output；LangGraph 官方持久化／狀態更新與鎖定原碼支持既有 saver 補存。沿原 `tool_steps.py` 接線，不增加原生內容 DB、自製 serializer 或多層 retry。詳細介面／限制只放 [工程 §4.4](../../../implementation/agent-execution.md#44-已落地的原回應補存與資格接線t06-第五切片)。

- 行為 Red：checkpoint 與 pending writes 都失敗後，公開入口只拋保存錯誤，完整原 R 無法交回恢復呼叫者；新增反例 **1 failed**。保存原 update 並經明確 recovery handoff 回到原 thread 後通過；不靠 stream update 或重新請求模型。
- 原件已保存時核對後續位置；未保存時核原 input／node，再由公開入口使用官方 `aupdate_state`。原 operation seed 保持一致；重複 handoff 不清除已存工具結果、不重複 append。第二次保存故障仍交同一原件。
- 真 PG 的舊人工補存測例改走公開入口，不再由測例直接建 update；寫前失敗、確認遺失、雙保存失敗均保持模型呼叫 1。既有新程序恢復、Memory 原工具效果測例同步注入資格檢查並回歸。
- 新增真 PG 資格反例：模型等待時另一交易可取消；晚到 R 可保存但不派工具。雙保存失敗後取消／更換 writer，舊 writer 不能補存；新有效 writer 可承接原件而不重呼模型。這不是整體取消／安全基底採用已完成。
- 主代理及獨立子代理都找到重用 recovery 的同一 P2：若直接續跑 execute node，已保存 R 的暫存責任未清，會把後續工具／資格錯誤誤分類成模型保存失敗。追加反例 **1 failed**，改為確認原 R／seed 已保存後即釋放本次暫存責任；工具及 guard 兩分支通過。

完整受影響回歸：沿 §4 的 unit／contracts、budget／admission／migration、Graph／Memory Step，另加 `tests/integration/test_response_recovery_eligibility.py`。初次集合 **513 passed in 25.80s**；新增 P2 兩項測例後 **515 passed in 26.83s**。Ruff check／format **187 files**、mypy **144 source files** 通過；文件 **20 份／318 links** 零錯、diff check 通過。獨立子代理短複核修正並跑相關 unit **40 passed**，原 P2 關閉，無新增重大發現。不改產品 wire／DB schema／UI／圖稿，因此不新增無關瀏覽器或圖稿渲染驗證。無付費、未讀 `.env`，僅合成資料與隨機 test schema。

### 後續費用預檢研究（尚未執行）

另一唯讀子代理依規範查 [GPT-6 Luna](https://developers.openai.com/api/docs/models/gpt-6-luna)、[pricing](https://developers.openai.com/api/docs/pricing)、[token counting](https://developers.openai.com/api/docs/guides/token-counting)、[compact](https://developers.openai.com/api/docs/guides/compaction) 與 [Fast mode](https://developers.openai.com/api/docs/guides/fast-mode)。回報 create 可依明確輸出上限預留，但計數 API 未查到明確免費／費率承諾；standalone compact 沒有 create 的輸出限制，未查到足以保證單次帳單硬上限的官方條款。不能以未知按零或把 create 容量當 compact 計費保證。這是後續 manifest／計量需明示的限制，未啟用任何付費預檢，也未更改模型。compact 的明確 service tier 及有界單次風險仍需在對應接線處處理。

## 6. 第六切片：有界直連協定預檢

### 批次 manifest（2026-09-30；執行前設定）

目的只驗遠端接受 `store=false`／`all_turns`、strict function、原生 R 序列化／重送及原 call 配對，不驗職務分析品質、完整恢復或 compact。沿計畫既有真模型授權；腳本為 `apps/api/scripts/probe_responses_protocol.py`，直接呼叫已測的 adapter／serializer，不建立第二套產品 runner。

| 項目 | 本批界線 |
|---|---|
| 模型／資料 | `gpt-6-luna`、`low`、`service_tier=default`；只有腳本內合成協定文字及一個無參數虛擬唯讀工具；不送 repo／員工／JD 內容 |
| 請求 | `(input_tokens.count → responses.create) × 2`，最多 4 次 HTTP、2 次生成；SDK／腳本重試皆 0、並行 1；任何未預期結果立即停止 |
| 容量／時間 | 每次 count ≤ 4,096 才 create，`max_output_tokens=512`；每次 30 秒、整批 120 秒 |
| 金額 | 管理預算 US$1，不是 provider 硬帳單保證；生成以最保守全 input 按 cache-write US$0.125/M、output US$0.50/M 估兩次上界約 US$0.001536；計數 API 未查到明確免費／費率承諾，未知不記成零 |
| 停止／重跑 | timeout、quota／model 不可用、協定錯誤、超量即停；不換模型、不全批自動重跑。追加批次须先診斷、另記理由與上限 |
| 憑證／紀錄 | 僅取 `apps/api/.env` 的 `OPENAI_API_KEY`，不套舊配置；結果檔 exclusive-create，只記次數、型別、phase、usage、安全錯誤碼，不記 key／opaque／原始 error body |

主代理已取得上述官方 model／pricing／token-counting 原文（來源同 §5），生成估計含所有輸入按較高 cache-write 費率及隱藏 reasoning 的輸出上限。尚無足夠證據為 compact 設同樣硬成本上限，故本批不送 compact；也不拿逾時當未付費。

此腳本是有限相容性 probe，不是產品新行為，故不製造假 TDD Red；實際 SDK 序列化、工具配對及路由已有單元／契約證據，本批驗其遠端接縫。

### 實際結果：憑證前置條件未滿足，零外送

2026-09-30 03:59 台北時間執行第一批，安全結果留於忽略區 `.research-tmp/t06-protocol-preflight-01.jsonl`：`started` 後在載入必要金鑰時停止，**HTTP 0／生成 0／模型費用 0**。只輸出變數名稱確認授權檔案有 `OPENROUTER_API_KEY`，沒有 `OPENAI_API_KEY`；未使用或輸出任何金鑰、沒有用第三方 key 直連試錯，也沒有切換 provider。已請 Owner 在本機加入直連 key，等待時繼續不依賴 provider 的 T06 工作；這不是整個 Goal blocked。

腳本 Ruff 通過；mypy 連同 src **145 source files** 通過；`--help` 可執行。先單獨跑腳本 mypy 時，editable package 被當成無 py.typed 的外部依賴，改為與 src 一起檢查，不新增 ignore 或改變型別規範。無 DB／Graph／產品 wire 修改，不重跑無關整合測試。**原生接續／strict／計數遠端接受性仍未驗證**，上述離線檢查不能替代。

待憑證就緒，以相同限制、另一次性結果檔執行；上一批零外送不代表可無界反覆跑。命令：

```powershell
$env:PYTHONUTF8='1'
./.venv-target/Scripts/python.exe -B scripts/probe_responses_protocol.py --key-file S:/caliburn/apps/api/.env --output S:/caliburn/.research-tmp/t06-protocol-preflight-02.jsonl
```

## 7. 第七切片：固定請求與保存後計量

預檢脚本／限制已提交 `946c663f`，仍缺直連 key、零外送。同步推進本切片：主代理先沿既有 executions／saver／SDK，唯讀子代理比較官方耐久 node、同 node Held 與原生 task 三種方式。選 **R 先保存，再獨立結算 node**，因為既有 StateGraph 已有合適交界，無須重作 serializer／ResponseStore。子代理記憶體 probe 證明若把記費放在 request callback 返回前，記費拋錯會使 R 無法交給 Held，續跑重呼模型；這是錯誤組合方式的反例，不是已接 production 的故障宣稱。

實際接法集中 [工程 §4.5](../../../implementation/agent-execution.md#45-已落地的固定請求一次外送與保存後結算t06-第七切片)：初始 checkpoint 固定完整 request／logical ID，輸出保存原 attempt；workflow 只協調既有 budget 與 direct SDK。六個既有 fixture／測試由具明確寫入範圍的子代理更新必填介面，主代理審查並整合，保留原故障斷言與 native fixture。未新增業務表／依賴。

### Red／Green 與整合

- 准入接線前，真 PG＋SDK MockTransport 的行為 Red 為 HTTP 時看不到已提交 allowance（`0 != 1`，**1 failed**）。此前測例用錯本地 settings／close 名稱只是 fixture error，不計 Red。接線後一次外送前可由另一連線取得 execution 鎖並看到 allowance。
- `tests/integration/test_model_request_accounting.py` **6 passed**：結算前失敗／已提交但確認遺失 × 隨後正常恢復／取消；R 不重呼、原成本一致、取消零工具。准入 COMMIT 確認遺失時 HTTP 0；HTTP timeout 時 1；兩者新 saver／executor 恢復均找到原 request、保留未知預留、不拿舊 allowance 再發送。
- 獨立唯讀審查找到補存 R 期間取消的 P2：第二次 guard 拒絕，但 saved 仍是補存前狀態而漏記費。主代理追加單元反例先得 **1 failed**，改為承接已驗證且剛補存的 recovery 原件後通過，模型仍 1／結算 1／工具 0。不是重新查最新版資料或重做生成。
- 初次整合 unit／contracts／Graph／Memory Step／新 PG 集合 **489 passed in 12.31s**；後續加入 request snapshot／P2 回歸並納入 budgets、admission、migration 的完整受影響集合 **525 passed in 28.70s**。Ruff check／format **190 files**、mypy **146 source files** 通過；文件 **20 份／322 links** 零錯、diff check 通過。流程圖與既有 ERD 以既有 Mermaid／headless Chromium 實際渲染，主代理檢視新增流程圖，交易／保存／結算及失敗路徑可讀。
- 獨立代理短複核 P2 可關閉，新增測例 **1 passed**；無新增重大發現。子代理均已結束；無付費或新私人資料外送，僅合成 SDK transport 與 fixture 自建的隨機測試 schema，共享 PostgreSQL server／database 留存。

這些是 fake provider＋真 PostgreSQL 的控制／恢復證據，不是遠端接受或正式費率驗收。暫時只接**首次生成**；已有 attempt 先明確交回核對，尚未選擇自動重試／Retry-After／jitter 接線。容量／token count、compact、完整 loop／角色控制繼續施工，T06 不勾完成。

## 8. 下一個可執行切片

繼續共用 loop、容量計數／真實費率配置與單一有界 retry supervisor，再接 compact／角色控制。正常 Step 已固定完整 request、sync／recursion、原 R 恢復、首次外送准入及保存後結算。已有 attempt 必須先核對，不因本切片的明確停止省略產品要求的有界恢復。沿既有 execution／候選 owner，不增加模型全文 DB 或第二套業務回執；目前只有 Memory prepared 路徑證據，未驗 JD／角色完整整合。

一般恢復不用歷史 checkpoint_id；明確 replay 與 App 回退另走既定資格。SDK／Graph 不自行套多層 retry。完整原 R 還在時須保存／承接原結果，不能只靠重新 invoke 重呼付費模型。T06 預檢已有 §6 manifest／腳本，因欠直連 key 尚未外送，不假稱 provider 通過。
