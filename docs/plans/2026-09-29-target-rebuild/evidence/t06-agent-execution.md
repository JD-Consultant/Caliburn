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

## 2. 下一個可執行切片

先接小型共用 StateGraph 的 `request_model → prepare_tool → execute_tool` 保存交界，每筆工具依序；以原生 saver／既有候選操作承接，不加第二份 owner。待執行命令型別須能嚴格往返，未知／降型結果不能進 execute。先做 E02／E03 的保存失敗／確認遺失反例及 E04 的真 PG 原工具重入，再接有界計量／compact／角色控制。

一般恢復不用歷史 checkpoint_id；明確 replay 與 App 回退另走既定資格。SDK／Graph 不自行套多層 retry。完整原 R 還在時須保存／承接原結果，不能只靠重新 invoke 重呼付費模型。T06 預檢仍需另備全合成 request／費用 manifest，目前無付費、無金鑰讀取、無真人資料外送。
