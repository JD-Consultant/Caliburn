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

## 5. 下一個可執行切片

繼續外層共用 loop 與單一有界計量／外送資格，將「checkpoint＋pending writes 都失敗，但原 R 還在」的能力證據接入有資格檢查的正式恢復路徑，再接 compact／角色控制。正常 Step 入口已固定 sync／recursion／新輸入與恢復界線。沿既有 execution／候選 owner，不增加模型全文 DB 或第二套業務回執。工具接線需核對還原巢狀型別；目前只有 Memory 的 prepared 路徑證據，未驗 JD／角色完整整合。

一般恢復不用歷史 checkpoint_id；明確 replay 與 App 回退另走既定資格。SDK／Graph 不自行套多層 retry。完整原 R 還在時須保存／承接原結果，不能只靠重新 invoke 重呼付費模型。T06 預檢仍需另備全合成 request／費用 manifest，目前無付費、無金鑰讀取、無真人資料外送。
