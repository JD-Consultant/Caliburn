# C 原生圖：每輪資源解析工廠驗證

2026-09-13；基準 `8403d7e2`。本次將已有 C 六步流程抽為同一個公開 graph factory，讓 App 靜態掛載原生子圖，執行時才依每輪的 Runtime 取得既有 `RepairWorkflow`。沒有改 App、依賴、adoption manifest、schema、資料表、worker 或 provider。

## 接口與責任

[repair.py](../../../../packages/consultant-memory/src/caliburn_memory/repair.py) 新增：

```python
build_repair_graph(
    resolve_workflow: Callable[[langgraph.runtime.Runtime], RepairWorkflow],
) -> CompiledStateGraph
```

- resolver 每個執行中的原生節點呼叫一次；edit 迴圈每次也重新解析，沒有跨 run 的資源快取。
- App 从 `runtime.context` 取得自己的 session，負責 doc／dataset／run／Store／原操作准入；核心只核回傳為 `RepairWorkflow`。錯誤回傳型別為固定 `TypeError("repair_workflow_unavailable")`；resolver 的未知 I/O 例外原樣往外，不誤轉 patch 可修錯誤。
- `seed → edit → validate → save → prepare → publish` 及 conditional edges 只保留在 factory 一處。原 `RepairWorkflow.graph` 使用 `build_repair_graph(lambda runtime: self)`，維持原調用方式與六步行為。
- factory 編譯時不取得資源；`get_graph`、`get_subgraphs`、`get_state` 不執行 resolver。子圖保持預設 per-invocation persistence，繼承父圖 Saver，沒有自己的另一份 checkpoint store。
- App 只用公開 factory，不需呼叫核心 `_seed` 等私有方法。factory 內部代理回已有步驟，不另寫一套修補邏輯。

取消政策沿本輪主代理決定：wrapper 進 C 前核 stop；已開始的有限六步完成後等待真 Future，再收尾。factory 不加逐步停止或補償，resolver 的 scope 校驗不能把取消當作死亡證據。此政策的 App 接線不在本次檔案範圍。

## 先反例、後實作

新增 [test_repair_graph_factory.py](../../../../packages/consultant-memory/tests/test_repair_graph_factory.py)，使用真 LangGraph `StateGraph`／`InMemorySaver`、真 `InMemoryStore`／MemoryArtifacts 與 SQLite PublicationStore；只有 SourceReader 是合成測試埠。未使用模型、網路 provider 或 PostgreSQL。

| 實際執行 | 結果 | 證明範圍 |
|---|---|---|
| 新測試，factory 尚不存在 | **6 FAIL，5.80 秒** | 六例都因缺公開 API 的 AttributeError 失敗；這是新增能力的首敗，不宣稱六項獨立既有資料毀損。 |
| 實作 factory 後，新檔 | **6 PASS，5.80 秒** | 見以下有限能力。 |
| 完整 package tests | **130 PASS，14.03 秒** | 包含原 124 例與新 6 例；既有修補、來源錯誤、原 request 對帳與 publication 回歸通過。 |

各次有已存在的 pytest cache 目錄 ACL warning，未影響測試執行；沒有放寬 assertion 或跳過測試以取得 PASS。

新測試實際覆蓋：

1. resolver 設為一呼叫就拋錯，建圖、列靜態子圖及讀空狀態仍成功，計數為零。
2. 同一 compiled graph 依序處理兩份不同文件、各兩個 patches；每份依序解析 `seed/edit/edit/validate/save/prepare/publish` 七次，publication 各自只前進到 2，原背景游標保留，原內容與保存狀態各自隔離。
3. 在 publish 執行前用官方 `interrupt` 暫停；不傳 Runtime context 也能讀固定 child checkpoint 與原 prepared operation，讀取不增加 resolver 計數。
4. 上例在核心測試中**明示** `Command(resume=True)`，以同份持久資源的新 `RepairWorkflow`／新 context 繼續；只重入 publish，证明 factory 未捕獲最初那輪的資源物件。這不代表 App 取消／崩潰恢復允許重播；App 仍只按原 request 查回。
5. resolver 回錯型別時，在來源讀取與 publication 前停止；resolver I/O 失敗保留原例外，不產生 invalid-edit feedback。
6. 非 callable resolver 在建圖入口即被拒絕。

執行環境與命令：新 App 既有 frozen lock／venv，`PYTHONUTF8=1`，cwd `experiments/jd-relational-app`。

```text
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q ../../packages/consultant-memory/tests/test_repair_graph_factory.py
uv run --offline --frozen --no-sync --cache-dir S:/caliburn/.research-tmp/uv-cache pytest -q ../../packages/consultant-memory/tests
```

## 依據與限制

沿已鎖 **LangGraph 1.2.11／MIT**。本輪直接讀已安裝官方 `langgraph/runtime.py`：`Runtime` 是 graph node 的原生注入物件，公開 `context`、`store` 與 execution info；[官方 graph API](https://docs.langchain.com/oss/python/langgraph/graph-api#runtime-context)提供每次 invoke 的 runtime context。[官方 subgraphs](https://docs.langchain.com/oss/python/langgraph/use-subgraphs)支持將 compiled graph 靜態加入父圖及父 Saver 傳播。未升級、未將文件概念當作未執行能力；上述六例是本版實測。

本檔是作者的實作證據，不是獨立審查。130 PASS 為核心 package 的真原生記憶內 Saver／SQLite 驗證，不等於真 PostgreSQL、新程序、完整 Agent 工具路由或自然模型修補品質。App 將此圖掛入实际 Agent、原 call 綁定／取消／receipt 查回／關閉及同輪讀版，仍由主代理本單位後續驗收。
