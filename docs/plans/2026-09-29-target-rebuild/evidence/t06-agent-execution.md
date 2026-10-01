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

### 憑證就緒後的真直連結果（2026-09-30 10:31 台北）

Owner 確認已在指定檔案放置直連憑證。第一次在 sandbox 的 count 發送遇 `APIConnectionError`；無憑證 GET 同樣得到 Socket `ConnectionRefused`，判定本機網路環境限制，不改 provider、schema 或模型。經工具批准，使用相同 manifest、另一個 exclusive-create 結果檔重跑；沒有 SDK／腳本自動重試。

正常網路批次 **4 HTTP／2 生成／0 重試** 通過：count 92、123；原生 `function_call` → 原 `function_call_output` → `message(phase=final_answer)`；原 R JSON round trip 相同；`store=false`、`reasoning.context=all_turns`、strict 與 default tier 被接受。生成 usage 合計 input 215、output 22，以已核費率估 US$0.0000325；計數費用仍不冒稱零。合成任務沒有產生 reasoning item，因此只確認參數接受及工具接續，**未驗加密 reasoning 跨步／跨輪、compact 或分析品質**。安全結果在忽略區 `.research-tmp/openai-protocol-20260930-b.jsonl`，未保存或列印金鑰／opaque。

為本機 Demo 共用既有 key-only parser，將其移至 `adapters/openai_credentials.py`，新增 `scripts/run_backend.py --key-file` 明確入口；不載入其餘舊配置。合成 parser **5 passed**、Ruff／mypy 通過；最初缺 module 及暫存 ACL 錯誤不算產品行為 Red。程序啟動與完整產品結果另由 T08 記錄。

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

## 8. 第八切片：有界多 Step 接續

承接 `082d4d5f`。重新取得 OpenAI function-calling 與 LangGraph Graph API 官方文件，核 conditional edges、State／super-step 與 recursion limit；比較在現有 Graph 接邊和再加 parent／child thread。選前者延續已有保存責任，不增第二份 cursor／窗口庫。機制、界線及圖集中 [工程 §4.6](../../../implementation/agent-execution.md#46-已落地的有界多-step-接續t06-第八切片)。本輪使用計畫執行／TDD／OpenAI 文件技能；依使用者既有授權接續，不重開產品審批或新規格副本。

- 真正行為 Red：三個模型 Step（多 calls／commentary／final）只呼叫一次模型，`1 != 3`，**1 failed**。加入共用 Graph 的有界循環後，原生 reasoning／message／calls／各結果順序完整，固定設定不刷新；工具與 final 同時存在不誤停。
- 完成步數與限制隨原 checkpoint 恢復；已耗盡再 resume 仍停止，調高限制、改成單步入口或重新提交初始 input 均拒絕。最後一步 final 可返回，不強迫多呼叫一次。無新增額度表，工作總額度仍是原 executions owner。
- 第二步兩工具中最後一筆失敗，只重入原固定命令，已完成工具不重跑；第二個 R 的 checkpoint／pending writes 皆失敗時由原 Held 補存，不能混成第一個 R。下一 request 保存前／提交確認後拋錯都不提前 HTTP，恢復同一 request ID，不重加 items。取消出現在完成 Step 後時不再呼叫模型。
- 獨立唯讀 reviewer 發現 P2：初始 input checkpoint 保存、但 `__start__` 展開尚未保存時，`values` 空導致新限額檢查誤拒恢復。主代理新增反例取得 **1 failed**；改為原生恢復後、外送前再次驗固定限額，原測例通過，另驗此邊界不能提高限制偷送。沒有解析 checkpointer 私有表或自行重建 input。
- 新 `response_loop_worker.py` 用真 PG、兩個獨立 Python 程序：write 程序模型 2／工具觀察 1，第二個 R 保存後注入中斷；resume 程序模型 0／工具觀察 0，完整原視窗接到 final，重複 resume 不變。沿既有 fixture 僅清理自己的隨機 schema，不停止共享 PG。

受影響回歸沿 §7 全集合（unit／contracts＋budgets、migration、admission、Graph／Step／Memory tool、eligibility、model accounting），**534 passed in 32.00s**。Ruff check／format **192 files**、mypy **146 source files**通過。新增測例的中途斷言曾誤貼到取消案例，按失敗行號修回原案例；不把測試編輯錯誤當產品 Red。原內部 builder 測例補齊初始固定限額，未刪除原故障斷言。

文件 20 份／325 links 零錯，diff check 通過。三張工程 Mermaid 圖用既有 headless Chromium／Mermaid 渲染成功，主代理實際檢視新增循環圖，條件、保存、停止與非產品提交界線可讀；首次 sandbox `spawn EPERM` 後經准許渲染，不以失敗當通過。Reviewer 已結束，P2 的關閉依主代理新增 Red／Green 及完整回歸，沒有冒稱第二次獨立複核。

本次無 provider 呼叫、未讀 `.env` 或外送私人資料。仍缺 §6 的直連 provider 證據；沒有把假 provider＋真 PG 當模型品質、產品 UI 或整個 T06 完成。

## 9. 第九切片：固定計數與容量准入

承接 `62e463fe`。主代理讀 OpenAI 最新 token-counting／per-run spending controller 原文，核對本機 SDK。選現有 Graph 保存計數、現有 executions 管所有外送預留；不新增 cache、owner 或通用 quota 引擎。正式接法見[工程 §5.2](../../../implementation/agent-execution.md#52-已落地的固定請求計數與容量准入t06-第九切片)。本輪使用計畫執行、TDD、OpenAI 文件及獨立審查技能；既有施工授權不重開。

- 首批行為 Red **5 failed**：容量超限仍生成、沒有計數、下一請求未停在 272K。接線後 **5 passed**；另補已知模型／輸出設定不合法時應零 count 的 **2 個行為 Red**，前移無需遠端資訊的檢查後通過。測例編輯時曾誤放三行斷言導致 NameError，修回原案例，不計作產品 Red。
- 固定完整 payload／capacity policy；已存 count 於模型節點失敗後原樣恢復，容量不合仍不重計，不能恢復時放寬 policy。不合法 count 不當零；count 失敗無估算 fallback。首請求高於272K但符合模型限制不誤觸中途保險；第二請求達門檻保存原歷史、停止於未接線的 compact 需求，不冒稱已壓縮。
- `test_request_capacity_postgres.py` 真 PG＋SDK MockTransport：HTTP 時另一連線可取 execution 鎖並看見 count 預留；count 算外送但不算模型 Step。重開 saver 後沿用 count；488＋512＝1000 可發生成、489＋512 超限零生成。未知 count 成本保留合成預留，不記免費。
- `test_model_request_accounting.py` 原 model 准入確認遺失／timeout 測例延伸到 count：前者 HTTP 0、後者 1，恢復均先核對原 attempt 不再發送。原 R 記帳／取消／工具恢復測例仍保留。與容量 PG、新程序測例初次整合 **10 passed**，加入 count 故障後 accounting **8 passed**。

完整 backend 測試命令（`pytest -q -p no:cacheprovider --tb=short`，使用既有 loopback 測試 PG）**908 passed in 210.31s**。其啟動後另補 271,999 可接續、final 不再多計數的邊界測例，容量檔單獨重跑 **13 passed**；不把後加案例冒充已在該次 908 全集合中。Ruff check／format **196 files**、mypy **147 source files**通過。

獨立唯讀 reviewer 未發現阻擋提交的問題；其另跑四個受影響 unit 檔 **36 passed**，並以記憶體故障注入核 count 保存確認遺失、272K 重入、count 途中取消。這是 reviewer 回報的額外證據，主代理的全套／PG 結果如上，兩者不混算。真 provider 校準、動態費率、compact 接線、原 count 完全未保存時的恢复及單一 retry supervisor 均明確留在後續切片；未把缺口移出 T06。

文件 **20 份／328 links** 零錯、diff check 通過。三張工程 Mermaid 圖實際渲染，主代理檢視更新的 loop 圖，計數保存、容量 gate、停止與返回路徑可读；sandbox 的 `spawn EPERM` 後使用獲准的既有無頭瀏覽器渲染，未以首次失敗當通過。Reviewer 已結束。未讀 `.env`、無真 provider 呼叫；所有 model／capacity／費率數值均為合成測試配置。T06 維持施工中，未把此 gate 當產品旅程完成。

## 10. 第十切片：完整 C 安全採用與中途接續

承接 `00c3449b`。主代理重新讀 OpenAI standalone compaction、SDK 3.20.0 compact／construct 原碼，以及 LangGraph 私有子圖與持久執行文件。採用既有 saver 保存完整 C、原 executions 計量，不增加儲存系統；一次 compact 的小型私有 Graph 可由輪前準備及中途交界共用。正式接法及限制見[工程 §5.3](../../../implementation/agent-execution.md#53-已落地的完整-c-保存採用與中途接續t06-第十切片)。本輪使用計畫執行、TDD、OpenAI 文件、平行分工、診斷及獨立審查技能，未重開已授權產品決策。

- 初始測例先因缺少新模組／接縫失敗，這只記為 API 施工起點，**不當業務 Red**。行為反例包括：空 C 原先可覆蓋非空歷史；compact wire 未指定 default；父圖取消後漏掉子圖既存 C 的補帳。各自取得失敗後修正、保留原斷言。
- Graph 整合時發現條件路由拋容量拒絕可能在重入時不重跑，原容量恢復測例及壓後超門檻測例出現 **3 failed**；把判斷放到正式 `check_capacity` node 後通過，不削弱限制。框架 Runtime 注入曾因參數名稱不符失敗，核本機 `_runnable.py` 後更正為框架契約名稱，非產品設計變更。
- 完整 C／pending writes 雙失敗及保存確認遺失均保留原件，恢復不再 compact；記帳失敗承接已保存 C。取消仍可結算但不得採用；舊 W 在安全採用前可取回。完整 output（含保留 user message）送入下一請求，沒有重貼原輸入／maps。採用後重新計數；仍達272K保留位置並拒絕重壓，真正新增完整 Step 後可再次壓縮。
- `compaction_worker.py` 使用真 PG 與兩個 Python 程序。第一程序完成模型／工具 Step，C 已採用但父圖未接上時中斷；第二程序原 C 接續，compact **0**、新 count **1**、新模型 **1**，原工具觀察不重讀。新增 worker 的專項實跑 **1 passed**。採用既有隨機 schema fixture，沒有停止共用 PG 或刪除既有資料。
- 子代理完成 compact 外送計量：沿既有 `COMPACTION` 預留，獨立 DB 連線在 HTTP 時能看見已提交額度且無長交易鎖；原 C 先交回 Graph、後結算。未配置／未知費率不當免費；原 attempt 重入不取得第二次 HTTP 許可。主代理核 SDK service_tier 預設 auto 的差距，建立唯一 `compaction_payload()`；子代理據實際 wire／已提交指紋不一致的 Red 同步使用該 helper，不留兩份 payload。
- 獨立 reviewer 發現 P2：子圖 C 已保存、結算失敗後取消，父入口只認父 R，漏掉 C 補帳。主代理重現 **1 failed（settled 0，應為1）**，讓原 compact 邊界在取消恢復時重入受 guard 保護的子圖對帳，仍禁止採用。reviewer 再驗「子圖尚未開始」「已保存 C」「Held C」，確認零新增 compact、既存 attempt 結算及未採用；P2 關閉。reviewer 的五個 unit／contract 檔 **53 passed** 為獨立補充證據，不冒充 PG 或真 provider。
- 收尾反例：模型回傳空 output、窗口未增加資料，僅換 request ID 不應再次壓縮同一份 C。先取得 **1 failed**（第二次 compact 被觸發）；改為只有實際增加 items 才清除已壓縮判定，空 output 仍跨 request 保留，原斷言通過。

完整後端回歸 **938 passed in 206.04s**；上述最後小修後，依風險重跑 unit／contracts、Graph PG、compact／model 計量及容量 PG，**545 passed in 28.24s**。不將前一次全套宣稱為小修後的新全套結果。最終 Ruff check／format **200 files**、mypy **148 source files** 通過。三張工程 Mermaid 圖已實際渲染，主代理檢視更新的 loop 圖；圖稿清楚區分計數、准入、完整 C 採用及重新計數。首次 sandbox 的 `spawn EPERM` 由獲准的既有 headless renderer 解決，沒有跳過圖稿驗證。

最後窄範圍 reviewer 複核 **4 passed**，另查連續空回應／多次恢復仍只 compact 一次，以及空回應後確有新增 items 可以再次 compact；無阻擋發現。文件 **20 份／331 links** 零錯、diff check 通過，子代理均已結束。

本輪未讀 `.env`、未呼叫真 provider，沒有外送私人訪談。compact 輸出品質／真實價格、輪前128K／B起始準備、完整 pause／取消回退及 retry supervisor 尚未驗收；不能以此切片宣告 T06 或產品完成。

## 11. 第十一切片：完整 Step 暫停與原生續作

承接 `4266ee0d`。主代理重讀本題產品控制契約、程式分層／撰寫規範與 LangGraph 原生 interrupt 文件，沿現有 StateGraph 接控制節點，不新增另一套停止／恢復引擎。子代理只修改既有 executions owner、單一 migration 與專項 PG 測試；主代理負責共用 Graph、薄 workflow 接線、程序恢復及文件。具體機制、尚未接上的競爭交界集中 [工程 §4.7](../../../implementation/agent-execution.md#47-已落地的完整-step-暫停與原生續作t06-第十一切片)，不是第二份產品狀態機。

- 原生 pause API 起初因新符號不存在而 collection error，只是施工起點；補齊介面但未接行為時，取得 **4 個行為 Red**：final／非 final 越過暫停、錯誤續作身分未拒絕、停妥確認故障未傳回。接線後保留原斷言通過。
- 完整 Step 才停；兩個工具中第二個結果未明時仍未停妥，恢復沿原 command 完成後才 interrupt，第一工具／模型均不重跑。interrupt 自身保存失敗不能確認暫停；停妥 callback 確認遺失可重入，不重做模型。這些是原生 saver 的故障測試，不是 mock success。
- `test_response_loop_controls.py` 用真 PG saver 與 execution owner：模型在途另一短交易受理要求，status 仍 ACTIVE；完整 Step 後才 PAUSED。重新建立 saver 普通重開零生成；明確原 interrupt 續作保留歷史／限制。取消或更換 writer 後，舊 runner 不得重開或回報有效 PAUSED。Graph 完成仍為 ACTIVE，未冒稱產品已提交。
- 新 `response_pause_worker.py` 用真 PG 與兩個獨立 Python 程序：write 生成 1 次後停在完整 final；resume 程序普通重開仍 paused，明確續作才返回原 final，count／模型／工具均 0。fixture 只清理自己的隨機 schema，保留共享資料庫。
- 工作模型、工具與暫停聯合專項 **21 passed in 15.66s**。薄 binding 新模組首次 import 缺失記為 API 施工起點，不冒充行為 Red；真 PG 接線後 **3 passed in 2.59s**。測例編輯過程誤置原 assertion 時先修回原案例，沒有更動預期。Ruff check／format **206 files**、mypy **149 source files** 通過；全後端回歸與獨立審查另於下方記錄。

子代理回報 execution 專項 **22 passed**，並以原 SQL 越過 PAUSED 完成及 8 個 pending／清旗標反例作 Red；主代理檢視變更並重新跑完整後端：`pytest -q -p no:cacheprovider --tb=short`，明確 loopback test DB，**971 passed in 238.04s**。此為主線自身的整合證據，不混用子代理較早的全套數字。包含 in-flight JD 候選可以繼續、但 pending pause 使正式採用與完成同交易回滾，以及暫停／完成兩連線競爭只有一個勝出。

獨立唯讀 reviewer 初次檢查與相關 **101 項**測試／靜態檢查通過，另實跑出控制交界反例。主代理判斷其中「已保存 continue，故障後新受理 pause 卻跳過重核」應在本切片補強，沒有僅因 T08 未開始就略過。新測例先 **2 failed**：非 final 多執行一個 Step，final 原樣返回未停妥；核官方 node successor 更新契約後，於當前完整 Step 的恢復入口重新安排純控制節點，**16 passed**（pause＋loop）。不回放舊 checkpoint、不重做模型或工具、不增加另一份游標。上面的 971 是此修正前全套，不冒充修正後新全套。

Reviewer 另用真 PG 領域＋記憶體 saver 模擬「領域 resume 已提交、尚未送 Command」後普通重開，觀察 PAUSED／已清意圖；這是兩段呼叫間的模擬，**不是 kill 程序測試**。仍由 T08 supervisor 的持久控制接線處理，與外送准入／正式提交競爭一併明列工程 §4.7；不能讓後續實作者誤認普通 None 已具備完整 resume 調度。

首次控制重核修正後，同一受影響集合 **576 passed in 39.74s**。後續 reviewer 找到 P1：`finish_step` 完整 checkpoint 寫入前失敗、但 pending writes 已存時，`get_state` 已顯示完成結果；此時用控制更新覆蓋，會遺失 Step 完成步數與部分接續內容。主代理加入 final／非 final 反例先 **2 failed**，沿公開 `StateSnapshot.tasks` 排除尚待保存的 `finish_step`，交由框架原生恢復。另將控制 checkpoint 故障擴為保存前／後兩種，保留原重核要求；pause＋loop **20 passed in 1.31s**。

最終依風險重跑 unit／contracts、Graph PG、execution 控制／准入、pause 薄接線、原 Step／資格及 migration，**580 passed in 39.65s**；Ruff check／format **206 files**、mypy **149 source files** 通過。獨立 reviewer 另重跑上述 **6 案，6 passed in 0.84s**，確認 P1 關閉、未重做模型／計數。這 6 案是記憶體 saver 故障測試，不冒稱真 PG kill；跨程序 PG 證據仍以前述專項為準。沒有因修正只重跑新增測例，也沒有把早期 971 全套數字當成最終修正版全套。

三張工程 Mermaid 圖已用既有 renderer 渲染，主代理實際檢視更新的 Step loop 圖；先處理 pause、再 final／下一請求的方向與中途 compact 路徑可讀。首次 sandbox `spawn EPERM` 後使用獲准 headless renderer，不把失敗當通過。文件 **20 份／334 links** 零錯、diff check 通過。流程圖表示已接好的元件流程，不代表完整 UI／調度已驗收。

本次未讀 `.env`、無真 provider 呼叫；沿用已有直連預檢前置缺口，不用第三方 key 替代。T06 仍在施工，pause 元件不等於完整 UI／supervisor、Turn 取消回退或背景角色控制已交付。

## 12. 第十二切片：原計數結果補存

承接暫停切片 `0641beff`，補第九切片已記錄的 count 原件保存缺口。重讀[官方計數契約](https://developers.openai.com/api/docs/guides/token-counting)、本機 OpenAI 3.20.0 `InputTokenCountResponse` 及既有原 R／C 補存路徑：遠端 count 是固定 payload 的觀察，不是 provider 保存的 Response，也沒有成本 usage；沿原 saver 與 attempt 補存即可，不增加 cache／資料表／另一套結算。

- 先以保存前／保存後確認遺失反例得到 **2 failed**：原程式只丟 `ConnectionError`，仍完整的 count 未交給恢復方。新增受限 `HeldInputCount`／`InputCountSaveError`，沿原 `recovery` 入口核 thread、request 及固定 payload，保存或承接既有结果後再檢查容量；原 R 恢復語意不變。
- 第一輪相關 **45 passed in 1.63s**。再加 pending writes 優先、補存重複失敗仍保留原件、跨 request 拒絕、取消不可採用、超容量仍停止等代表性反例。測例編輯誤置舊 assertion 的 `NameError` 已修回原測例，不記為產品 Red；沒有放寬斷言。
- `test_request_capacity_postgres.py` 擴充原有真 PG saver／execution 預算／SDK MockTransport 接線，計數保存前／後故障，關閉再開 saver 後補存或承接既有結果。HTTP 計數只一次；原 count 已超容量則零生成，否則只新增一次生成；未知計數費用預留仍保留。專項 **13 passed in 4.57s**，不把合成 HTTP 當真 provider。
- 首輪主代理受影響回歸：unit／contracts、計數／R 保存／資格／pause、模型與 compact 記帳、Graph PG，**579 passed in 36.81s**。Ruff check／format **207 files**、mypy **149 source files** 通過；文件 **20 份／336 links** 零錯、diff check 通過。這是明列範圍回歸，不冒稱全後端或真 provider 已驗收。
- 獨立 reviewer 發現 P2：原 count 已補存且 Step 已完成後，重帶同一 handoff 會因 `recovery != None` 跳過新 pause。新增 final／非 final 反例先 **2 failed**；共用控制判斷改為「是否仍有待補存原件」，而非呼叫是否帶 handoff。保留前切片的 pending Step 防覆寫條件；相關 **52 passed in 1.76s**。修的是跨 count／原 R 與控制的共同邊界，不另造暫停特例或改既定產品語意。
- 修正後相同受影響集合 **581 passed in 35.84s**，Ruff／mypy 與文件檢查再通過。PG 測例最後只把巢狀條件表達式展開以提升可讀性，專項再驗 **6 passed in 3.61s**。Reviewer 窄複核 **9 passed**，另 4 組原 R handoff 探針保持第 1 Step 暫停、原 R／operation seed／窗口及外送次數不變，確認 P2 關閉；該複核為記憶體 saver，不混同 PG／provider。

本切片不改 Graph 節點／流程圖、不改業務儲存或計量契約；未讀 `.env`、無付費外送。process-local 原件不是跨程序備份；此處的真 PG 測試是重新連線，不冒稱 kill 後能取回尚未保存的 count。重試 supervisor／輪前準備及角色整合仍未完成。

## 13. 第十三切片：共同外送的持久有界重試

承接 `9d38e038`。重讀當前 [OpenAI 錯誤／Retry-After 指引](https://developers.openai.com/api/docs/guides/error-codes#python-library-error-types)、本機 SDK 3.20.0 的 header 與 jitter 處理，以及 [Azure Retry pattern](https://learn.microsoft.com/en-us/azure/architecture/patterns/retry)。借鑑單一重試責任、故障分類、服務端等待及整體交易語意；沒有把多廠商名字當共識證據，也沒有啟用不承接本案持久預算的 SDK／Graph 隱含重試。責任、機制及圖只維護於[工程 §5.4](../../../implementation/agent-execution.md#54-已落地的單一外送重試責任t06-第十三切片)。

主代理使用計畫執行、TDD、OpenAI 文件與獨立審查流程；子代理只負責既有 executions 的安全故障保存、migration 與專項測試，主代理接共同 workflow、錯誤／等待策略及跨層測試。並行修改範圍分開，最後由主代理整合；沒有第二套 validator／receipt／queue／全文庫。

- 初始真正行為 Red：429 已確認失敗後未取得第二次受預算限制的外送，**1 failed**。同 request／同完整 payload、新 attempt 准入後通過；create、count、compact 共用同一路徑，HTTP 期間另一連線可取 execution 鎖並讀已提交預留。
- 保存安全 failure 與最早 retry 時間；重開沿用原時間，不重新抽 jitter。failure 保存前失敗不重送；COMMIT 確認遺失先查原紀錄。准入確認不明仍拒絕重送，兩個 runner 不能沿同一失敗各送一次。重試保留原次數／成本／期限；未知成本不按零，取消／writer 更替不恢復資格。
- 初次整合 **3 failed／49 passed** 是既有 timeout 測例仍要求首次直接拋 SDK error；已依本切片新政策改驗「確認的 timeout 受原三次上限限制、再入不加次數」，沒有放寬准入確認遺失時零外送的保證。更新後同集合 **52 passed**。Retry-After unit 包括毫秒、秒、HTTP-date、無效／超大值及 jitter，**16 passed**。
- 獨立審查與主代理找到三项 P2。其一為成本／總次數已耗盡卻仍等非零 Retry-After；主代理 **2 failed** 後將原准入檢查抽為同 owner 共用方法，等待前拒絕，不新增假 admission。其二、三為永久 API error 進 Graph ERROR，以及 failure 保存出錯時原 SDK body 經例外鏈進 traceback；真 PG Graph／標準 traceback 的合成敏感標記 **5 failed**，安全型別與抑制 chaining 後通過。超大 Retry-After 停止也覆蓋安全出口。
- 上述修正後，retry／failure／execution-budget 真 PG 專項 **60 passed in 25.12s**；Ruff check／format **212 files**、mypy **150 source files** 通過。修正前完整後端曾 **1051 passed in 261.59s**；不把該次數字當修正後全套證據，最終回歸與 reviewer 結論另於下方補記。
- 窄複核找到取消例外鏈殘餘：`CancelledError` 不屬於 `Exception`。主代理先測 COMMIT 前取消通過，沒有冒充 Red；再加入連線取得前取消，得到 **1 failed／1 passed**，確認真正失敗交界。明確保留取消型別並抑制 SDK chain，兩分支與整個 retry 檔 **21 passed in 10.88s**；不吞取消、不新增外送，保存未確認再入仍停在原 attempt。

四張工程 Mermaid 圖已用既有 Mermaid／headless Chromium 實際渲染，主代理檢視新增 retry 圖；交易、等待、原件優先與不明結果停止路徑可讀。首次 sandbox `spawn EPERM` 後經准許啟用 renderer，不略過圖稿驗證。沒有修改模型 wire／prompt、讀取 `.env` 或呼叫真 provider；HTTP 為合成 SDK MockTransport，PG 為既有 loopback 測試庫內 fixture 自建 schema。

最終整合：取消例外鏈小修前啟動的完整後端 **1055 passed in 245.33s**；小修後依風險重跑 unit／contracts **552 passed in 7.64s**，以及 outbound retry／failure、execution budget、model／compact accounting、migration、Graph PG **96 passed in 54.38s**。不把前次全套當作最後兩項取消測例也已包含。最終 Ruff check／format **212 files**、mypy **150 source files** 通過。文件 **20 份／339 links** 零錯，diff check 通過。

独立 reviewer 首次修正複核 **13 passed**，其指出的取消殘餘再以兩項實跑 **2 passed** 確認關閉，沒有本次增量新增的重大發現；任意 tracing locals、角色 supervisor 與真 provider／費率未在本次審查承諾中。子代理均已結束。這些數字是各次明列集合，不加總宣稱為互不重複的產品案例。

**仍未交付：**原程序確已遺失、沒有可核對 failure 的 attempt，不由此切片自動放行；角色 supervisor、輪前準備、原件保存的有界調度、真費率／provider 與 UI 都有後續任務。這不是 E15／T06 整體完成，更不是產品訪談品質已驗收。

## 14. 第十四切片：輪前歷史的門檻判斷與可恢復準備

承接 `bbe55f59`。重讀共用執行 §6.2–6.3、工程 §3／§5.3 及當前 OpenAI standalone compact、LangGraph checkpoint 官方契約；沿原私有 Graph 增加歷史計數與條件路由，未另建 ContextStore、儲存表或角色各自的 compaction loop。[工程 §5.5](../../../implementation/agent-execution.md#55-輪前歷史準備元件t06-第十四切片)維護接法及尚未交付的角色邊界。

- 新入口先以原無条件 compact 流程作可執行骨架，127,999 tokens／無 Agent 要求反例 **1 failed**：錯將完整歷史換成 C。加入原參數保存、先存 count 再判斷及沿用分支後，與既有 compact 單元測試 **28 passed in 1.12s**。這是行為 Red，不將缺少 import 或測試路徑打錯算成 Red。
- 新增 128K 交界、低於門檻但有要求、空歷史零外送、未壓縮決定重入、count 保存前／後與 pending writes、補存再次失敗、原 C 確認遺失、跨身分／改原參數拒絕、超容量及失效 writer 等代表例。返回窗口是獨立複本；測例追加被取消輸入後重讀原基底不受影響。此複本測試不是產品取消驗收。
- 主代理 unit／contracts **570 passed in 7.78s**；Ruff check、mypy **150 source files** 通過。獨立子代理新增真 PG 連線重開／SDK MockTransport 三案，主代理已讀取變更，整合回歸與獨立審核結果於下方補記。

主代理整合回歸：輪前準備三案、compact／model accounting、capacity、原 Graph 新程序、pause、資格及單 Step PG 集合 **48 passed in 32.77s**。三個新案使用真 saver 重開，另把返回歷史接到真 SDK MockTransport 的下一個模型請求，驗完整 C／原 W＋新輸入，以及原外送次數與預算不重置；不是程序 kill 或真 provider。既有四個新程序測例為共同機制回歸，不冒稱新準備角色已驗取消／跨批。

Ruff check／format **214 files**、mypy **150 source files** 通過；文件 **20 份／342 links** 零錯，diff check 通過。五張工程 Mermaid 已渲染，主代理檢視新增輪前準備圖，實線共用準備與虛線待角色接線的界線清楚。首次 sandbox 拒絕 headless Chromium 後經准許渲染，沒有略過圖稿檢查。

獨立 reviewer 未發現本次增量需修正的可重現缺陷；其重跑準備／原 compact 單元 **30 passed**，另報告 48 組保存故障、5 種基線 checkpoint 接續、11 組資格及 2 組 opaque／可變輸入探針通過。後者為 reviewer 的記憶體 saver／執行探針，非主線真 PG／程序故障或 provider 證據，不與前述測例加總。Reviewer 已核 API／文件一致，跨工作基底、角色綁定、要求消耗及取消回退保留於後續責任；沒有因此將 T06 勾完成。

本切片不讀 `.env`、不外送真模型，不增加套件或 migration。原完整接續資料仍由官方 saver 保存；已採用位置跨工作選用、角色 maps／原話固定及自動恢復 supervisor 尚未完成，T06 維持施工中。

## 15. 第十五切片：跨工作合法歷史與取消後基底

承接 `62d547f9`。重讀當前 LangGraph checkpoint／StateSnapshot 與 PostgreSQL 行鎖契約：框架保存完整窗口，執行領域只保存「哪個既有位置可採用」的參照。機制、交易、圖及未完成角色交界只維護於[工程 §3.1](../../../implementation/agent-execution.md#31-跨工作的合法歷史選用t06-第十五切片)，不另造全文庫、通用恢復引擎或第二份 Graph 路由。

主代理負責原生窗口讀取、`RoleContextHistory` 及真 saver 整合；子代理限定 executions 的 reference-only 模型／保存／migration／測試。共同保留既有 writer fencing、短交易與 caller transaction；B 的兩角色位置必須共同採用，Graph final 不能自行當產品正式完成。

- 原生窗口讀取骨架先得到行為 Red **2 failed／2 passed**：完整已保存窗口尚不能取回；實作後加入控制交界，**5 passed**。保存的完整 reasoning／工具配對按原順序回讀；呼叫方改返回值不改原件；未採用 C、暫停 final 均拒絕。明確 checkpoint 缺失不改讀最新位置。
- Workflow 真 PG 反例先 **1 failed**：準備返回空列表但沒有固定採用基底。補接既有 saver 準備與 executions 採用；施工期間尚缺子代理完成函式的 AttributeError 不算有效 Red。
- `test_role_context_history.py` 驗正常與採用交易回滾兩條路徑：完整 C 已保存、採用尚未提交可重入；A 取消後重連 saver，新工作 b 使用同一完整 C＋新 App 資料＋b，不帶入已取消的 a、不重計或重壓；較舊完成結果重入不倒轉目前位置。兩案與原生單元合計 **7 passed in 2.52s**。

上述模型為合成 runtime probe，PostgreSQL 與 AsyncPostgresSaver 為實際元件；不是 SDK 遠端接受、程序 kill 或完整 A 產品取消驗收。未讀 `.env`、未呼叫真模型。本切片尚未交付 maps／訪談固定組裝、正式 JD＋訪談共同完成、背景安全點調度及自動恢復 supervisor，T06 不勾完成。整合回歸、圖稿與獨立審查結果接續補記。

子代理回報 executions 保存專項 **40 passed**，包含 caller transaction 回滾、取消／完成雙連線競爭、兩角色共同採用、舊完成重送、讀取不寫表及 DB 約束。主代理讀取整合變更後，重跑 unit／contracts、上述 domain／workflow、Graph PG、輪前準備、compact／model accounting、execution control 與 migration，**676 passed in 69.42s**。這是明列範圍回歸，不冒称全後端或產品 E01–E15 全完成。

Ruff check／format **223 files**、mypy **154 source files** 通過。文件 **20 份／345 links** 零錯，diff check 通過；六張工程 Mermaid 已渲染，主代理檢視新增歷史選用圖，固定基底、取消保留與正式完成採用方向可讀。首次 sandbox 拒絕 headless Chromium 後經准許完成渲染。未部署 production migration、未新增依賴或對外傳送專案資料。

獨立 reviewer 接受本切片，未發現可重現的阻擋缺陷；其窄複核真 PG **4 passed**，另以 **6 個 probe** 檢查 pending Step／control、輪中 C、未提交準備位置、缺失位置及返回複本。這是 reviewer 的分層複核，不與主代理 676 項加總。角色固定輸入、正式業務完成及 B 候選共同回退仍按上述後續任務交付；兩位子代理均已結束。

## 16. 第十六切片：原件補存的有限自動恢復

承接 `cc564072`。依當前 LangGraph 節點重試、Azure Retry pattern、Tenacity 異步重試及 Psycopg／PostgreSQL SQLSTATE 契約，選擇原件 handoff 層的有限調度，不對模型 node 加無差別 retry。機制、圖及精確限制只維護於[工程 §5.6](../../../implementation/agent-execution.md#56-原件補存的有限自動恢復t06-第十六切片)。Tenacity 9.1.4 原已在 lock，現在列直接依賴；無新增套件版本、資料表或第二套保存。

主代理接四個既有入口、原請求／interrupt 續作及跨 saver 整合；子代理限定 driver 錯誤分類與單元測試。按 TDD／驗證 skill 保留反例、再獨立審查，不把工程細節再交 Owner 審批。

- 新測試最初缺少 module 的收集失敗不算行為 Red。子代理分類骨架的行為 Red 為 **17 failed／54 passed**；主線接上分類骨架時原件不會重試，**11 failed／9 passed**。分類實作後主線 **20 passed**，追加既有 pause 恢復與下游工具錯誤界線後 **22 passed**。
- 自動接回同一完整 R／C／count、確認遺失先讀原保存、永久錯誤不自動嘗試、用盡保留原 handoff、程序取消直接傳遞、已取消 writer 不派工具；恢復已消耗 interrupt 後若保存失敗，不重送 resume。工具已進入而失敗不被保存 retry 接管。
- 真 PG＋官方 AsyncPostgresSaver 六案：R／C／count 各在保存前／實際提交後失去確認，程序仍持有原結果時自動核對；關閉並重開 saver 後相同結果、原外送／記帳不重複。主代理新專項（22 項追加前）**97 passed in 4.42s**，含 71 分類、20 流程、6 PG。這是合成 SDK MockTransport、實際 saver 提交與重新連線，不是外部 provider 或整程序 kill 後找回未存原件。

無 SQLSTATE 的 Psycopg `OperationalError` 可能亦是認證設定問題，只能有限嘗試；不解析錯誤文字猜測。永久錯誤／語意衝突不改成成功，未知外送仍停在原 attempt。未讀 `.env`、未外送真模型、無 production schema 操作。本切片不等於 T06／完整產品恢復驗收；整合回歸與獨立審查結果接續補記。

獨立 reviewer 找到 P2：task 在 Tenacity backoff 被取消時，原完整結果仍在程序裡，但 plain `CancelledError` 沒有 handoff，呼叫方無法承接。主代理以真正的 task cancellation 重現 R／C／模型計數／準備計數 **4 failed**（皆缺原 handoff）；核 Python 取消與 Tenacity sleep hook 後，在共用等待層交回仍屬取消的型別及原保存錯誤。四案接續原結果而不重呼，連既有測例 **26 passed**；再驗補存完成後於工具期間取消，不附上舊 handoff，整檔 **27 passed**。没有新增原件 DB 或各角色的取消處理副本。

後段取消測例最初直接在 node 拋 `CancelledError`，LangGraph 將其轉為 `NodeCancelledError`；受影響回歸因此 **1 failed／742 passed**。這不是外層 task 被取消的等價情境，已改成 Event 確認抵達工具後對實際 task 取消，沒有放寬產品斷言或改框架行為。最終回歸與 reviewer 複核於下方記錄；上一次取消補正前 **738 passed** 不當作最終版本證據。

獨立窄複核 **98 passed**（27 流程＋71 分類）及另 5 個探針：原 R／request／attempt／operation seed 未換、等待取消仍為 cancelled、後段真 task 取消沒有 stale handoff；另核巢狀 compact、timeout 與標準 traceback。Reviewer 已關閉原 P2，未發現本次增量需要修正的缺陷；這次複核沒有重跑 PG／全套，不能與主代理回歸加總或當成完整角色恢復。兩位子代理均已結束。

最終主代理完整後端 `pytest -q -p no:cacheprovider --tb=short`，使用明確 loopback 測試 PostgreSQL：**1229 passed in 269.71s**。這次包含取消補正與真 PG 整合，不使用前次未修測例的回歸數字。Ruff check／format **228 files**、mypy **156 source files** 通過；文件 **20 份／349 links** 零錯、diff check 通過。七張工程 Mermaid 圖已渲染並檢視新增補存圖；首次 sandbox headless 啟動受限後沿獲准 renderer 完成。之後只補取消交接文字，未再改圖。

`uv sync --locked --offline` 通過（86 個既有相依，重建本地 target package）；僅將已鎖定 Tenacity 列為直接依賴。全部測試仍為離線模型／SDK 合成資料與真測試 DB，不是 OpenAI 遠端／訪談品質驗收。T06 與整個 Goal 均未完成；原件可恢復不等於完整角色 supervisor 已接好。

## 17. 第十七切片：固定費率與原 usage 結算

承接 `7c4a383d`。主代理使用既有 SDD／TDD 計畫，核官方 pricing、cache read／write 算式及 SDK 3.20.0 usage；研究子代理獨立查 compact 與 count 收費契約，主代理再讀 compact reference 的 default 條件。採小型不可變費率配置及 Decimal 計算，接原 `ModelRequestAccounting`；不用新增費用平台／依賴／資料庫保存。責任、估算限制與來源由[工程 §5.7](../../../implementation/agent-execution.md#57-固定費率與-usage-成本估算t06-第十七切片)維護。

- 算術骨架 Red **11 failed／13 passed**，涵蓋正常／快取／寫入、長 context 門檻、輸出、費率身分與預留。首輪實作 **1 failed／23 passed**：SDK `construct` 已把測試的 bool 轉成 int，原測例並未保留其聲稱測試的非法值。改用 SDK `model_copy` 保留該值測邊界，不修改產品算式；追加缺失欄／合法零後 **29 passed**。
- Compact 與 factory 接線最初七案缺少方法，不算有效行為 Red。補 factory 骨架後 **6 failed／34 passed**：compact 未估算，模型不符仍抵達 HTTP。補實作後 **40 passed in 3.90s**，含真 PG 七案：原 usage 結算重入、compact 原模型配置、缺 cache-write 保留預留、三種請求模型不符均零准入／零 HTTP，以及不同費率依據不得結算舊工作。
- 真 PG fixture 的 budget 改為使用傳入 accounting 的既有 `cost_basis`，舊合成政策不變；沒有新增 receipt、原件副本或假 provider 帳單。使用 SDK MockTransport，未知費用不改零；這不是遠端接受、程序 kill 或模型品質測試。
- 主代理受影響回歸：unit／contracts 全部＋price/model/compact/budget/result-save 真 PG，**755 passed in 32.99s**。不是完整後端回歸，不重複宣稱前次 1229 項涵蓋本增量。mypy **157 source files** 通過；最終靜態／文件檢查及獨立審查接續補記。

當次未讀 `.env`、無付費 API、無 production migration、無新依賴。Count 端點費用查不到明確官方承諾後停止廣搜，保留既有行政預留；Compact default 使用標準費率有文件依據，但當前 SDK 沒有回傳模型／tier 的正式欄位，仍標示推估，不冒充核帳。T06 及整體 Goal 未完成。

最終 Ruff check／format **231 files**、mypy **157 source files** 通過；文件 **20 份／354 links** 零錯、`git diff --check` 通過。本次只補計價接線文字，既有 R→結算→資格→工具流程與圖不變，不為未改圖重跑 renderer。

獨立 reviewer 未發現可重現的實質缺陷，專項 **57 passed**，另驗 **34 組異常 SDK usage** 與原生序列化往返、cost basis 跨程序穩定。它是窄審查補充，不與主代理 755 項加總、不當作新程序完整產品恢復或真帳單驗證。研究與審查子代理均已完成，無額外檔案變更。

## 18. 下一個可執行切片

接角色控制、費率／容量配置的正式組裝及未明 attempt 的恢復調度。共同 loop 已有完整 request、sync／局部步數、原 R／C／count 保存恢復、外送准入、保存後結算、計數、中途完整 C 採用、完整 Step pause 與已確認 provider 故障的有界重試；未配置 compact 接縫仍明確停止。第十四、十五切片已有輪前可恢復準備與合法跨工作基底；準備後固定並追加角色資料、B 兩角色與候選安全點共同回退，以及 §11／工程 §4.7 的控制要求競爭與持久續作調度仍須在同一上位契約內接好。已有 attempt 必須先核對，不因明確停止省略產品要求的有界恢復。沿既有 execution／候選 owner，不增加模型全文 DB 或第二套業務回執；目前只有 Memory prepared 路徑證據，未驗 JD／角色完整整合。

一般恢復不用歷史 checkpoint_id；明確 replay 與 App 回退另走既定資格。SDK／Graph 不自行套多層 retry。第十六切片已為仍完整的原 R／C／count 接上有限補存，不重呼原付費請求；不能據此跳過未知 attempt 或角色恢復責任。T06 預檢已有 §6 manifest／腳本，因欠直連 key 尚未外送，不假稱 provider 通過。

第十七切片已接公開費率估算與模型綁定，實際帳戶／invoice 尚未驗。後續依原 capacity 和 fee manifest 組裝行政預留，不把 create 輸出上限搬給 compact、不因 SDK usage 型別相同推定帳單已核實；T16 必須辨明這些界線。

先按任務表的 T06 完成契約收斂剩餘缺口：共用機制在 T06，正式 A 控制／提交屬 T08，B 角色／批次屬 T10／T11，不能把所有角色交付無限併入本任務。T07 的 T03／T04／T05 前置條件已滿足，可繼續 JD／來源工具垂直切片；未驗 provider gate 必須保留，不阻止不依賴它的工作。

2026-09-30 獨立只讀範圍審查進一步定位：`workflows/model_requests.py` 的 `_reserve_request` 對已存在但没有 failure 記錄的原 attempt 會明確停止；目前 reopen 整合測例只驗停止，未驗核對後的受控再准入。**最小共用缺口是區分原結果可承接、仍在途／不明、已確認本機原件不可恢復，並僅在最後一類及工作／額度仍有效時准許新 attempt。**不能直接刪舊 reservation、重置預算或將查不到視為未送出。觸發／接管／角色通知仍屬 T08／T11，不另建 retry framework；T12 驗 kill／競爭，T16 驗 provider。

審查者另跑 13 個相關離線單元／契約檔 **210 passed in 2.81s**；沒有新 PG、provider 或程式修改，不與前述主代理數量相加。本輪轉進 T07 導覽以推進 M2，沒有把此缺口視為已修復或將 T06 勾選完成。

### 18.1 未明 attempt 的受控再准入接縫（2026-09-30）

**後續 Owner 收斂範圍：**以下保留為當時的低層能力與限制，不再要求首版完成 production 原件遺失證明 callback。既有結果照常恢復；不能安全接續時由原業務 owner 核對並結束本次工作，依[共用執行 §6.4](../../../specs/2026-09-27-shared-agent-execution-and-state-design.md#64-首版恢復範圍能續作不能續作則安全退出)及 [T12 §6](t12-consultant-process-recovery.md#6-首版恢復減法與最外層失敗收尾2026-09-30)。下方「下一步完成 callback」是歷史建議，不覆蓋此 successor。

本次只補 `workflows/model_requests.py` 的共用准入；不修改 bootstrap／supervisor／runner、不新增表、failure code 或另一套原件保存。既有 execution 行鎖、request payload fingerprint、工作 budget 仍是唯一准入權威。**共用接縫已實作，角色 owner 的可信核對與正式調度尚未接入，不據此勾選 T06 或宣稱自動重啟恢復已完成。**

公開接縫為 `ModelRequestExecutor(..., reconcile_prior_attempts=callback)`；callback 的型別為 `async (ExecutionWriter, tuple[OutboundAttempt, ...]) -> PriorAttemptRecovery`，只給 App 注入，不是模型／HTTP 的可填旗標：

| 本次對原 attempts 的核對 | 共用端行為 |
|---|---|
| `ORIGINAL_AVAILABLE` | 不新增 reservation／HTTP；原 kind 的 `Prior*AttemptError.recovery` 回報可承接，沿既有 Held／原生 Graph 恢復。callback 不搬運或另存 R／C／count。 |
| `IN_FLIGHT_OR_UNKNOWN`／未配置 callback／核對失敗 | 保留原件、預留及停止狀態；不拿空查詢、writer 取代、timeout 或重啟當重送許可。未型別化字串也不准入。 |
| `LOCAL_ORIGINAL_UNRECOVERABLE` | 只對此次已核對的原 attempts 有效；重新取得 execution 行鎖，重核 active writer、相同 payload／kind、原 attempts 的完整觀察及全部原工作 budget，再新增獨立 attempt。 |

核對 await 不持 DB transaction；重新准入時比較未明 attempts 的集合（不依 SQL 回傳順序）。競爭者新建未明 attempt、原 attempt 新結算或 writer 被取代會使舊判定失效；同次呼叫不再對新出現的不明 attempt 反覆詢問核對器。後續明確 transient failure 仍走原 retry policy／Retry-After 和原預算，不新增第二套重試。原預留不刪除、不偽造 provider failure、不把未知費用當零；新 attempt 的 COMMIT 確認後才外送，SDK 返回後仍立即交原結果給 Graph。

**Process owner 可提供的證據與缺口：**目前 `ConsultantSupervisor.has_runner`／`wait_for_runner` 可觀察該 supervisor 的本地 task，`failures` 保留 typed result handoff，`hold_dispatch` 可阻止交錯派送；`PostgresProcessLock` 的本機 OS fence＋專用 PG session 防止同一部署的重疊 owner。它們各自不是「原結果遺失證明」：`test_response_recovery_eligibility.py::test_late_or_held_response_requires_current_writer_before_tools[replace]` 明確驗過 writer 已取代，完整 R 仍可交新 writer 補存。新 supervisor 的空 failures 也不能證明前一個同程序 owner 沒有保留原件。

故 owner callback 必須在排除原 producer 仍可返回／寫入及新的競爭派送後，核對原生最新狀態（包含 pending writes）與仍保留的 R／C／count handoff；有原件先承接，查詢失敗或原 producer 來源不明則停在 UNKNOWN。需要跨 owner 的核對時，不能在 `allow_reentry` 清除 failure handoff 後才猜測它是否存在。目前沒有把 writer UUID 當 process generation，也沒有將 lock 成功硬轉成不可恢復。這是 T08／T11 owner 接線的明確前置條件，不新增產品重試按鈕或新的身份 registry。

**2026-09-30 官方複核：**[LangGraph checkpointers](https://docs.langchain.com/oss/python/langgraph/checkpointers)承接 checkpoints 與 pending writes，成功 task 的原生待整合輸出可在恢復時重用；不能只查 checkpoint `channel_values` 就宣告原件不存在，也不以歷史 checkpoint replay 代替普通恢復。[OpenAI conversation state](https://developers.openai.com/api/docs/guides/conversation-state)說明 `store=false` 關閉供後續取回的 response 保存；本案不能把 response ID 當遺失原件的遠端備份。這不證明遠端停止計算或沒有收費，故仍保留未知費用。上述是官方機制；三態核對與 exact-attempt 再准入是本案既定 §6.1／E03／E15 的工程實作。

**本次新證據：**`tests/integration/test_unknown_attempt_readmission.py` 新增 16 個真 PG＋SDK MockTransport 案例，涵蓋可承接／不明零重送、writer takeover 本身不准重送、R／count／C 新 attempt 舊預留保留、總次數／每請求次數／cost／deadline 不重置、核對中取消／換 writer／原件結算、核對失敗、競爭者只一個新准入，以及再准入後仍共用既有 transient retry。型別骨架後的行為 Red 為 **9 failed／1 passed**；不是將最初缺少 enum 的 import error 當有效 Red。

本次定向回歸包含上述新檔，以及既有 `test_outbound_retry.py`、`test_response_recovery_eligibility.py`、`test_model_request_accounting.py`。既有測試仍負責 native Saver／Held 原 R 的承接、commit ack 遺失、已知 timeout 的有界重試和保存後結算；新測試的 callback 是合成 owner 判定，不冒充已驗 process-death 證據產生器。最終命令結果另附於本節；未使用 `.env`、未外送 provider、未 commit，也未執行 Demo migration。

最終驗證（工作目錄 `apps/api`，既有 `.venv-target` Python、隔離 loopback `_test` DB；每案自建／回收獨立測試 schema）：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/integration/test_unknown_attempt_readmission.py tests/integration/test_outbound_retry.py tests/integration/test_response_recovery_eligibility.py tests/integration/test_model_request_accounting.py -q -p no:cacheprovider --tb=short
```

結果 **48 passed in 26.44s**（16 新增＋32 既有，不與前述歷次數量相加）；Ruff check／format check **2 files**、mypy `--follow-imports=silent` **1 source file**、本次 tracked 差異 `git diff --check` 通過。不是全套回歸、production owner 組裝、kill／跨程序 handoff 或真 provider 證據。下一個安全動作是 owner 以既有 task／原生恢復／handoff 證據實作上述 callback，先驗「舊 runner 已退出但仍有完整 R」仍走原件，而非僅因 takeover 啟用再推論。

## 19. 產品移除金額攔截與按請求計數預留（2026-09-30）

承接 `459d0b57`。Owner 明確採納「產品不再用預估金額攔截執行，保留 token 容量、呼叫／重試次數與時間上限；付費測試另行控管預算」。政策只維護於[共用執行 §6.5](../../../specs/2026-09-27-shared-agent-execution-and-state-design.md#65-容量與費用分開產品不設金額攔截)，接線、migration 及官方依據見[工程 §5.8](../../../implementation/agent-execution.md#58-產品與付費驗證的金額界線2026-09-30)；本節記證據，不另造規格。

### 原反例與最小修正

T17 失敗批次的唯讀核對發現，舊 runner 每次以最大可用輸入 922K 預留金額，並非當次 context 大小。模型估算累計 0.005708160、count 行政預留 0.001700000，合計 0.007408160；下一個固定預留 0.242788000 使總額 0.250196160 超過該測試的 0.25 上限。這是 App 預留算法造成的攔截，不是 provider 額度不足；原 trial 仍為失敗，不因診斷或修正改成通過。

- A／B1／B2 共用正常 `ModelSettings` 的空金額上限，沿既有 executions owner 檢查所有非金額限制。新增 nullable migration，不新增表、第二套保存或巨大假上限；既有執行的固定政策不被改写。
- 付費測試明確設定上限時仍攔截。其生成預留改用已保存且配對同一請求的 count 與實際 output cap；不多呼叫一次 count，不改送出 payload、compaction 或歷史組裝。
- 產品的 R／C 若缺完整計費明細，原件照常接續，金額保持未知；明確有限額的評測仍保守停止。未放寬原件保存、attempt 配對、writer 或資料庫失敗。

### Red／Green 與實際範圍

1. 先用 A／B 真 PG runner 的小額明示測試上限重現固定最大輸入誤攔：**2 failed／4 passed**；改按已保存 count 後同組 **6 passed in 11.41s**。
2. 新產品預設、舊環境變數不再啟用 gate、無金額政策三案在修改前 **3 failed**（其中 `None` 政策尚不能建立）；接線後設定／budget／runner 定向 **26 passed in 16.02s**。
3. 產品缺計費明細但已有完整 R／C 的兩案，修改前 **2 failed**，均為 `ModelUsageUnavailableError`；修正後包含於下方最終回歸。既有明示預算的缺失 usage 停止測例保留，沒有把未知費用補零。

最後回歸使用既有 `.venv-target`、loopback `_test` PostgreSQL，每案獨立 schema；模型走 SDK MockTransport，不是遠端 provider：

```powershell
./.venv-target/Scripts/python.exe -B -m pytest tests/unit tests/contracts tests/integration/test_execution_budgets.py tests/integration/test_database_migrations.py tests/integration/test_response_pricing_accounting.py tests/integration/test_consultant_runner.py tests/integration/test_memory_analysis_runners.py tests/integration/test_compaction_accounting.py tests/integration/test_model_request_accounting.py tests/integration/test_request_capacity_postgres.py tests/integration/test_outbound_retry.py tests/integration/test_unknown_attempt_readmission.py tests/integration/test_response_step_postgres.py tests/integration/test_response_loop_controls.py tests/integration/test_response_recovery_eligibility.py tests/integration/test_memory_tool_step.py -q -p no:cacheprovider --tb=line --basetemp=<新建且事先確認不存在的測試暫存路徑>
```

首次整合結果 **1105 passed in 78.83s**。涵蓋 nullable 新建／migration、原有限額、無限額仍受模型步數／attempts／deadline 限制、A／B runner、容量計數、compaction 與原恢復接縫。前次 sandbox 對 pytest 暫存目錄拒絕存取，出現 fixture／session cleanup 環境錯誤，不算通過；以正常權限和新 GUID 路徑重跑取得上述結果，未刪舊暫存目錄。Ruff check／format **406 files**、mypy **252 source files** 通過；以下為審查後補正，不把本次 1105 當補正後證據。

獨立 reviewer 發現 P2：僅直接測 accounting 會漏過 Graph 原件還原；SDK 可以收到缺少 `cache_write_tokens` 的部分 usage，但原 `Response.model_validate` 會先擋住，尚未進到放行分支。主代理新增 SDK 原件往返及部分工具後 Graph 恢復反例，先取得 **2 failed／16 passed**；核已安裝 SDK 3.20.0 `_models.py` 的原生 `model_construct` 後，僅對 `usage` 借用此能力，其他回應欄位仍驗證。補驗缺計費明細時壞 `call_id` 仍拒絕，兩檔 **18 passed in 1.07s**。原件／reasoning／phase／工具配對保持相同，恢復不重呼模型或重準備已完成工具；沒有新增資料欄位、服務或依賴。

補正後重跑上述同一回歸命令：**1108 passed in 88.64s**；Ruff check／format **406 files**、mypy **252 source files** 通過。新增本地文件連結 11 處及 diff check 通過。Reviewer 窄複核原件往返、未知成本、Step／部分工具恢復及壞 call_id，關閉 P2，無新增發現；未冒稱 reviewer 重跑完整套件。這是本切片最終證據，不與前次 1105 加總。

本切片未讀 `.env`、未呼叫真模型、未修改／重啟 Demo 8100／5173、未對 Demo 執行 migration，也未重驗 UI／PDF／自然訪談品質。舊資料與已受理測試仍保留原限制；本次測試不證明 T17 的漏引／更正泛化已修好。T06、T16、T17、T18 及 Goal 未據此勾選完成。

## 20. 真 compact 協定預檢（2026-09-30 恢復後）

### 批次 manifest（執行前設定）

任務表要求 T06「提前消除遠端風險」含 compact，但 §6 第一批因無法為單次 compact 設硬成本上限而刻意不送，至今**沒有任何一次真 API 的 compact 證據**；離線測例（§10、§14）只證明本機序列化與採用流程。本批只驗遠端是否接受：一步原生工具視窗 → standalone compact → 經本專案 serializer 的 JSON 往返取出完整 output window → 作為下一個 count／create 的前綴。不驗分析品質、輪前／輪中時點、取消或成本上限。沿計畫既有的有界真模型授權；腳本為 `apps/api/scripts/probe_responses_protocol.py --stage compaction`（原 `protocol` 階段行為與輸出事件不變），直接呼叫已測 adapter／serializer，不建立第二套 runner。

| 項目 | 本批界線 |
|---|---|
| 模型／資料 | `gpt-6-luna`、`low`、`service_tier=default`；只有腳本內合成協定文字及一個無參數虛擬唯讀工具（沿 §6）；不送 repo／員工／JD 內容 |
| 請求 | `count → create`（一步工具視窗）→ `compact`（該完整視窗）→ `count → create`（compact 返回視窗＋一則新 user 訊息）；共 **5 次 HTTP**（2 生成、1 compact、2 count）；SDK／腳本重試 0、並行 1；任何未預期結果立即停止 |
| 容量／時間 | 第一次 count ≤ 4,096、compact 後 count ≤ 8,192 tokens 才續送；create `max_output_tokens=512`；每次 60 秒、整批 240 秒 |
| 金額 | 管理預算 US$0.05，不是 provider 帳單保證；官方未提供 compact 單次硬上限，故實質界線是「視窗只有數百 token 的合成內容」；生成沿 §6 的估算約 US$0.0001 量級；count 與 compact 費用未知不記成零 |
| 停止／重跑 | 任何錯誤、逾時、模型不可用、item 形狀不符即停；不換模型、不自動重跑；追加批次須先診斷並另記理由與上限 |
| 憑證／紀錄 | 僅取 `apps/api/.env`（git 忽略）的 `OPENAI_API_KEY`；結果檔 exclusive-create 於忽略區 `.research-tmp/`，只記次數、item 型別、usage 與安全錯誤碼，不記 key／opaque／原始 body |

腳本靜態：Ruff check／format、mypy（連同 src **254 source files**）通過，`--help` 可執行；程式為有限相容性 probe，不是產品新行為，故不製造假 TDD Red，實際 serializer 已由 §10 與 `test_response_serialization.py` 覆蓋離線往返。

### 實際結果（2026-09-30 23:04 台北）

```powershell
$env:PYTHONUTF8='1'
./.venv-target/Scripts/python.exe -B scripts/probe_responses_protocol.py --stage compaction --key-file S:/caliburn/apps/api/.env --output S:/caliburn/.research-tmp/openai-compaction-20260930-a.jsonl
```

**5 HTTP／2 生成／1 compact／0 重試，全部被接受，約 7 秒，未觸及任何停止條件。**安全結果檔在忽略區 `.research-tmp/openai-compaction-20260930-a.jsonl`，沒有 key、opaque 或原始 body。

| 步驟 | 觀察 |
|---|---|
| 一步原生工具視窗 | count 92 tokens；create 回 `function_call`，usage 92 入／16 出；`store=false`、`all_turns`、strict 被接受；原 R JSON 往返相同 |
| standalone compact | 輸入視窗型別 `message, function_call, function_call_output`；**返回 `message`（保留的原 user 訊息）＋ 一個帶加密內容的 `compaction`**，usage 61 入／42 出；工具呼叫與結果已被折進 `compaction`，沒有另留可讀的摘要 |
| 本專案 serializer | `snapshot_compaction` → JSON 往返 → `compaction_input_items` 取回 **2 個完整 output items**，可直接作下一請求的前綴 |
| 從 C 續作 | 以「返回視窗＋一則新 user 訊息」count＝132（遠低於 8,192）被接受；create 回 `reasoning`（含加密內容）＋ `message(phase=final_answer)`，內容如指示為 `compact-ok`，usage 132 入／24 出（16 為 reasoning）；原 R 往返相同 |

生成估算沿 §6 費率約 US$0.00004，compact 用量僅 61／42 tokens；count 與 compact 的實際計費未由 API 回傳，**不記為零**，也不是帳單核對。合計 usage 約 367 tokens，遠小於 manifest 的 US$0.05 管理預算。

**因此確認的遠端契約：**standalone compact 接受本專案送出的 payload（`model`、完整 `input`、`service_tier=default`）；返回視窗須以完整 output 原型別、原順序承接（此例是 2 項，其中之一是不可讀的 `compaction`），與 §10 的採用設計一致；count 與 create 都接受含 `compaction` 的視窗。**未驗證：**大視窗（數十萬 token）的 compact 延遲與費用、視窗內已有 `reasoning` 加密項時的 compact、對已含 `compaction` 的視窗再次 compact、compact 後的長期品質（細節損失）與不同 `service_tier`。這些歸 T16／T17，不能由此單次推定。無憑證外洩；未動 Demo。

## 21. 任務完成對照（2026-09-30 恢復後）

沿[任務表 T06 的 Red 與完成條件](../tasks.md#t06-共用原生模型工具執行機制)逐條對照**既有**測試，沒有新增機制。路徑相對 `apps/api/tests`；同一測例只列代表，不重複貼各切片已記的命令輸出。

| T06 Red | 代表測例（層級） |
|---|---|
| R 已保存卻重呼模型 | `integration/test_response_step_postgres.py::test_model_checkpoint_failure_does_not_dispatch_and_pending_writes_recover_original`、`integration/test_graph_postgres.py::test_native_items_survive_process_restart_without_reexecuting_saved_node`（真 PG＋新程序）；`integration/test_model_request_accounting.py::test_saved_response_is_settled_after_ack_loss_without_querying_model_again` |
| 只存 output_text | `contracts/test_response_serialization.py::test_snapshot_and_replay_are_distinct_without_losing_received_metadata`、`contracts/test_openai_native_items.py::test_sdk_replays_all_native_items_without_remote_storage`（真 SDK mock transport） |
| 兩工具平行／配錯 call | `unit/test_response_steps.py::test_multiple_calls_remain_ordered_even_when_final_text_coexists`、`test_duplicate_call_identity_is_not_silently_deduplicated`；`contracts/test_response_serialization.py::test_saved_result_prefix_cannot_skip_repeat_or_exceed_calls`、`test_results_keep_call_identity_and_direct_caller` |
| 公開文字誤判 final | `unit/test_response_steps.py::test_commentary_and_calls_do_not_complete_the_turn`、`test_missing_phase_is_not_guessed_from_visible_text` |
| serializer 丟 opaque／phase | 上列 serialization／native items 契約、`contracts/test_graph_serialization.py`（含拒絕 pickle 與明確 allowlist）、`integration/test_graph_postgres.py`（官方 PostgresSaver 往返） |
| role namespace 污染 | `integration/test_context_histories.py::test_thread_identity_separates_roles_and_window_kinds`、`test_roles_cannot_cross_execution_kind`、`test_database_rejects_cross_job_bindings_and_partial_references` |
| SDK 隱含 retry | `contracts/test_openai_responses.py::test_transient_failure_is_one_outbound_attempt_not_sdk_retries`、`test_injected_redirecting_client_is_rejected_before_dispatch`、`test_default_client_does_not_forward_post_body_to_redirect` |

| T06 完成條件／E gate（框架部分） | 對照 |
|---|---|
| E01 原生 R／C 序列化與下一 request | 同上契約與 saver 往返；遠端接受性另有 §6（create／count／工具接續／strict／`store=false`／`all_turns`）與 §20（compact 視窗） |
| E02 R 已存、工具未做 | `integration/test_response_step_postgres.py::test_saved_step_reopens_without_repeating_window_items`、`unit/test_tool_steps.py::test_saved_first_result_and_pending_second_do_not_recall_or_reprepare`；跨程序 hard-exit 見 [T12 §6](t12-consultant-process-recovery.md#6-首版恢復減法與最外層失敗收尾2026-09-30) 的 `integration/test_consultant_process_recovery.py` |
| E03 R 在但保存失敗／確認遺失 | `unit/test_response_recovery.py::test_public_step_preserves_original_response_when_both_saver_writes_fail`、`integration/test_response_step_postgres.py::test_public_step_recovery_saves_held_model_result_after_both_writes_fail`、`integration/test_result_save_retries_postgres.py::test_saved_original_survives_automatic_recovery_and_saver_reopen` |
| E04 框架部分、`sync` 先 R 後工具 | `unit/test_tool_steps.py::test_model_and_each_prepared_operation_are_saved_before_effects`、`integration/test_memory_tool_step.py`；候選 owner 的原操作效果歸 T05／T07 |
| E11 compact 採用／中途接續 | `unit/test_context_compaction.py`、`integration/test_compaction_accounting.py`、`integration/test_context_preparation_postgres.py::test_reopened_preparation_reuses_original_history_count_and_next_context` |
| E15 不疊 retry、不重置預算、未知不算零、模型等待不持交易 | `integration/test_outbound_retry.py`（10 案）、`integration/test_execution_budgets.py`（10 案）、`integration/test_request_capacity_postgres.py`、`integration/test_response_recovery_eligibility.py`（若模型 I/O 期間持有交易，該測例會死鎖）；首請求超量的有界縮減見 [T08 §7](t08-consultant-turn.md#7-近期訪談預載超量的有界縮減2026-09-30-恢復後) |
| 零／一／多 call | `unit/test_response_steps.py`、`unit/test_response_loop.py`、`unit/test_tool_steps.py` |
| 真 PG 新程序 round trip | `integration/test_graph_postgres.py`、各 `tests/fixtures/*_worker.py` 驅動的獨立程序案例 |

**結論：**T06 的共用機制成立，勾選。仍有的相關工作都已有 owner，不併入本任務：A 的正式控制／完成屬 T08；B1／B2 角色與調度屬 T10／T11；跨程序故障矩陣屬 T12；官方 API 的大視窗 compact 延遲與費用、加密 reasoning 跨輪的 gate、實際帳單核對屬 T16／T17。Owner 2026-09-30 的首版恢復 successor（[共用執行 §6.4](../../../specs/2026-09-27-shared-agent-execution-and-state-design.md#64-首版恢復範圍能續作不能續作則安全退出)）已把「未明 attempt 的 production 原件核對」移出首版必做；§18.1 的共用再准入接縫與 16 案保留，未接 production owner，不宣稱自動恢復。

**完整後端回歸（提交 `478abcf8` 之上）：**`pytest tests`（真 PG `caliburn_t01_test` 的隔離 schema、合成 SDK transport）**1847 passed、2 skipped in 600.46s**；跳過的是 `test_pdf_rendering.py` 兩案（需 `CALIBURN_TEST_PDF_FONT`，T13 另驗）。命令與環境同 [T08 §8](t08-consultant-turn.md#8-任務完成對照2026-09-30-恢復後)。Ruff format／check 384 files、mypy 254 files（含 probe 腳本）通過。

## 22. 串流中的限流被誤判為協定錯誤（2026-09-30 恢復後的診斷與修正）

**問題與影響：**用模擬員工對真後端同時跑 6 個訪談做品質評測時（[T17](t17-course-administrator-journey.md#核心分析品質模擬員工基準與有界改善2026-09-30-恢復後)），6 個 Turn 各失敗一次，失敗碼都是 `response_protocol`，且集中在同一個約 10 秒窗口。這不是評測工具的問題：使用者的訪談 Turn 會因此直接失敗，長訪談（上下文大、每輪多次請求）更容易撞到限額。

**診斷（先量證據，不猜）：**同批 18 個 6 路並行的直接串流請求全部成功，排除單純並行；在評測後端外包一層只印安全欄位的診斷（類別、狀態、錯誤 `code`／`type`，不印訊息或金鑰），同樣情境重跑，記到 **10 次** `APIError status=None code=rate_limit_exceeded type=tokens`（串流途中的錯誤事件）與 6 次 `RateLimitError status=429`（HTTP 層），全是 token 每分鐘限額。原因在 [`classify_response_failure`](../../../../apps/api/src/caliburn/adapters/openai_failures.py)：HTTP 狀態錯誤會依狀態與 `code` 分類（429 → 暫時性，會依單一重試責任有界退避重試），但**串流已開始（HTTP 200）後才送出的錯誤事件**，SDK 只丟沒有狀態的一般 `APIError`，原邏輯一律歸為不可重試的 `response_protocol`，忽略 `error.code`。

**Red／Green：**新增 `tests/unit/test_openai_failures.py` 兩個測例（11＋3 個參數化案例：限流／伺服器錯誤／過載類代碼應為暫時性、額度耗盡與容量代碼沿用與 HTTP 相同的判斷、未知或讀不到代碼仍是終止性）與 `tests/integration/test_outbound_retry.py` 兩案（真 PostgreSQL＋真 SDK 串流路徑，MockTransport 在 HTTP 200 串流中送出限流事件）。修改前 **10 failed**，整合案直接重現現場症狀（`ModelRequestFailedError … response_protocol`）；「未知代碼不重試」的守門案修改前就通過。修改後同組加既有分類／重試／契約測試 **109 passed**；Ruff、mypy（253 files）通過。

**修正（單一分類點，沒有新機制）：**串流錯誤事件與 HTTP 狀態錯誤共用同一組封鎖與容量代碼判斷；只有 `rate_limit_exceeded`、`server_error`、`server_is_overloaded`、`slow_down`、`service_unavailable` 視為暫時性，交給既有的有界重試、額度與 `retry_not_before`；沒有這些代碼或讀不到明確代碼的仍終止，不猜為可重試。重試前沒有已保存的原結果與工具效果，重送安全；失敗的嘗試與其預留仍保留在原預算。

**限制：**是依 OpenAI 實際回傳的欄位與 SDK 3.20.0 行為修正，代碼清單只含目前見到與文件記載的暫時性類型；串流事件的官方完整錯誤代碼表未逐項核對。限額本身不消失：重試最多依原政策（每請求 5 次、退避 1–30 秒），持續限流仍會使 Turn 失敗，評測改為低並行避免長時間貼著限額。

**後續（同日，修正上面之後仍有 Turn 失敗）：**改成一次只跑一個訪談後，Turn 仍偶爾失敗，失敗紀錄是**同一請求連續 5 次 `transient_service`、約 20 秒內用盡**，且發生時都有背景整理批次同時在跑（修正後這是被重試而非直接失敗，證明分類修正有效，但重試耐心不足）。讀回應標頭確認帳號對 `gpt-6-luna` 是 **200,000 token／分鐘、500 請求／分鐘**；官方[限流指南](https://developers.openai.com/api/docs/guides/rate-limits)（經工具轉述，未逐字核對原頁）說限流用量取 `max(max_tokens, 依字元估算的輸入)`，且**失敗的請求也計入每分鐘額度**，建議降低 `max_tokens` 與退避重試。我們的 A 請求輸入約一萬多 token（14 個工具的 schema 就佔大宗）、`max_output_tokens=16,384`，一個訪談加背景整理很容易貼近上限。

取捨：降低 `max_output_tokens` 收益有限（輸入本身已接近 16K），且截斷（`incomplete`）會讓整個 Turn 失敗，風險大於收益，維持 16,384。改的是**重試耐心**：預設初始退避 1 秒→2 秒、每請求上限 5 次→8 次，最短總等待由約 11 秒增至約 90 秒（先寫測試 `test_default_schedule_outlasts_a_one_minute_rate_limit_window`，修改前 **1 failed**：`assert 11.25 >= 60`；同步兩個以舊預設數字當例子的既有測例）。相關 unit／contracts／重試與預算整合 **1134 passed**。限制：更高的 TPM 等級才是根本解；這只讓單一使用者的訪談在偶發限流下撐得過去，持續超量仍會失敗；沒有做用戶端節流或依 `x-ratelimit-reset-tokens` 的精準等待（HTTP 429 有 header 時仍用既有的 `Retry-After` 邏輯）。

## 23. 保留安全 provider 診斷（2026-10-01）

基準 `143783e3`。[T17 收尾補驗](t17-course-administrator-journey.md#2026-10-01luna-長訪談收尾的有界接續)只留下 `transient_service`，不足以確認是 HTTP 限流、串流限流或服務錯誤。核對共用 `_send`：原 `APIError` 有可用資訊，但只把粗分類寫入 attempt，沒有安全診斷出口。本次補的是既定[必要觀測](../../../architecture/delivery-and-operations.md#5-必要觀測不先造監控平台)，不是修好 provider 或 JD 漏引。

2026-10-01 查閱 [OpenAI 官方 error codes](https://developers.openai.com/api/docs/guides/error-codes)：429 可能是短暫限流，也可能是額度／用量限制，不能只看 HTTP 狀態。Caliburn 的取捨是保留已知 code 白名單，未知值捨棄；這不是廠商完整代碼表或新增重試分類。

**改動：**`ResponseFailure` 增加可選的安全 code；共用模型外送捕捉例外時記一則標準 warning，含操作、分類、status、code 及 App execution／request／attempt ID。create／count／compact 共用，不新設表或 logger 平台。既有 failure 保存、預算、重試、取消、原生 Context 與產品 Luna／high 均不變。警告先於故障保存，只是觀察，不作恢復權威；沒有 HTTP status／白名單 code 時如實記 `None`。

**TDD：**新增分類診斷六案先見 **6 failed**（缺安全 code 欄位）；HTTP 權限／額度／容量三案及串流限流一案先見 **4 failed**（診斷紀錄為零）。修改後第一組 **54 passed**。隨後為 count／compact 與未知惡意 code 補回歸斷言，這部分是事後補驗，不冒稱全部先 Red。

最終相關回歸從 `apps/api` 執行，使用 `.venv-target`；PG 為 loopback `caliburn_t01_test`，每例隔離隨機 schema，provider 為 SDK MockTransport，沒有真 API 外送：

```powershell
# CALIBURN_TEST_DATABASE_URL 明確指向隔離的 _test DB；不讀產品 .env。
./.venv-target/Scripts/python.exe -m pytest tests/unit/test_openai_failures.py tests/unit/test_execution_failures.py tests/contracts/test_openai_responses.py tests/integration/test_outbound_retry.py tests/integration/test_outbound_failures.py tests/integration/test_execution_failure_boundary.py -q -p no:cacheprovider
# 107 passed in 31.63s
./.venv-target/Scripts/python.exe -m pytest tests/unit/test_response_streaming.py tests/unit/test_response_retries.py tests/unit/test_import_boundaries.py -q -p no:cacheprovider
# 52 passed in 1.62s
```

合計 **159 個相關測試**；文件整理後將上述九檔合併重跑為 **159 passed in 30.64s**。四個改動的 Python 檔 Ruff check／format、兩個 source 檔 mypy 通過。涵蓋原重試／停止行為、串流與 HTTP 錯誤、記錄和 App 原 attempt 配對、例外正文及未知 code 不外洩；不是全產品回歸。主代理另檢查 diff，JD 工具／Context 的平行唯讀審查無可證實的新缺口，未為此更改工具。四份改動文件的214個相對檔案連結存在，新連結錨點已對照標題。

**限制／下一步：**先前遺失的細項無法回補，不把原串流清理警告判為已修。未新增付費測試、未動 Demo／憑證／資料表；後續真實失敗可用此資訊縮小原因，不為取得 log 重播原收尾。T14 品質、T16 容量、T17 整體旅程及 T18 切換仍未完成，不因此擴大恢復要求或放寬 gate。

## 24. 限流是等待，不是失敗（2026-10-01）

**起因（Owner 2026-10-01）：**被帳戶 TPM 200K 擋下只是服務要我們慢一點，「可以多等，這應該不叫做失敗」。原本每個請求被擋 8 次（2→30 秒退避，約 3 分鐘）就讓整輪（或整批背景整理）以預算用盡結束，這叫「最終失敗」；Memory 批次最終失敗還會停到訪談再前進三輪。

**現場證據（T14 Q1／Q2／Q2b 的 18 份模擬訪談）：**對 provider 的嘗試中被 429 重試吸收的比例 Q1 95／1,133（8%）、Q2 281／1,349（21%）、Q2b 274／1,457（19%）；Q2b 有兩個 A Turn（都在第 12 輪、上下文最大時）連續 8 次被擋而失敗；員工模擬 harness 自己的模型呼叫也被擋而崩潰一次。每份訪談處理 1.6M–5.4M 輸入 token，耗時約等於「總輸入 token ÷ 每分鐘 20–29 萬」，也就是**速度與穩定性都由 TPM 決定**。

**官方契約（2026-10-01 查 [OpenAI 限流指南](https://developers.openai.com/api/docs/guides/rate-limits)）：**用量取「`max_tokens` 與依字元估計的輸入 token 的較大者」；失敗的請求也計入每分鐘用量（所以快速重試只會讓桶一直是空的）；建議指數退避。快取輸入是否計入沒有在該頁明講；社群說法與本機觀察一致（94% 的輸入 token 是快取，吞吐仍貼著上限），標為**公開說法＋本機觀察，未取得官方原文**。

**改動（沒有新機制，沿原單一重試責任）：**

- `classify_response_failure` 新增獨立的 `rate_limited`（HTTP 429 或串流中的 `rate_limit_exceeded`／`slow_down`；被封鎖／額度類代碼與 `x-should-retry: false` 仍優先，5xx／408／409／連線中斷維持 `transient_service`）。保存的失敗代碼同步放寬（migration `0021_rate_limited_failures`，只改兩個 CHECK）。
- `ResponseRetryPolicy`：有 `Retry-After` 照做；沒有則限流用 10 秒起、60 秒封頂的退避（其他暫時故障仍是 2 秒起、30 秒封頂）。
- 預算准入：限流的 attempt **不占**每請求 8 次的額度；整個工作的外送總數（512）與工作期限仍會收尾，期限預設由 900 秒改為 1,800 秒（TPM 下的牆鐘由 token 量決定，晚期的大輪次需要更久）。
- 取消、暫停與 writer 資格照舊在每次等待中重核；不改 `max_output_tokens`（限流用量取較大者，輸入大時降低輸出上限沒有收益，截斷反而讓整輪失敗）。

**TDD：**先寫失敗的測例再改（單元：分類 5 個新案例、等待排程 2 案、預設期限 1 案；整合真 PG：限流等待不占額度、限流後服務故障仍在額度內停止、無止境限流仍在總次數停止、保存／約束接受新代碼，並把原先用 429 驗「每請求額度」的案例改用 503）。修改前單元分類測例收集即失敗（沒有 `RATE_LIMITED`）、排程測例 `2.0 != 10.0`；修改後相關 **160 passed**（outbound retry／failures／budgets／compaction accounting／model request accounting／migrations／policy／分類／重試／packaged migrations），Ruff、mypy（279 檔）通過。

**限制：**
- 這只讓限流被「等過去」，**不降低 token 用量**；速度仍由 TPM 決定，一輪可能等得更久，介面目前沒有「服務忙碌、等待中」的獨立提示（只看到該輪仍在進行，可取消）。
- 沒有做用戶端節流（依本地用量預先排隊以避免送出必被拒的請求）；若之後仍有大量被拒的嘗試浪費額度，這是下一個選項。
- 真模型下的效果待 T17 長旅程實測；本節只有離線與真 PG 證據。
- 容量面的底層優化（A 每個 Step 重送完整歷史，其中工具結果與呼叫約占六成 token；背景 Memory 批次與 A 重疊）另列為已知不足，不在本節處理。
