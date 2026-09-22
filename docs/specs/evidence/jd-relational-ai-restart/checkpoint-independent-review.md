# AI restart：checkpoint discovery 與 inspection 獨立窄審

- 日期：2026-09-13。
- 基準：`3980689a`；範圍為本輪 `consultant_context.py`／`consultant_tools.py` 差異、新 `inspection_model.py`、`ai_checkpoints.py` discovery 與相關測試。
- 狀態：**PASS；AR-R01（P2）已重現、原作者修正並經獨立窄複核關閉；指定範圍沒有剩餘阻擋項。**
- 審查者只新增本文件；沒有修改實作或測試。本輪自己先前編寫的 `manual_runtime.py` foreign owner 不列獨立審查證據；`consultant_tools.py` 只審本輪他人新增的 inspection 分支。
- 沿現有隔離版本：LangChain 1.4.0、LangGraph 1.2.11；未升級。0 DB、0 新程序／Win32、0 provider；不代表 foreign-host 的 OS／PG 驗收完成。

## 1. AR-R01：互斥 pending 必須在 discovery 前拒絕

**嚴重度 P2；修正前位置：[ai_checkpoints.py 的 `_material`](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py)。**

普通 root／child material 對 `jd_ai_run.status == "running"` 未檢查 `jd_manual_pending`；只有原始 START 分支檢查人工 pending。結果是同一原生 root 已保存 running AI 與人工待保存 identity 時，`discover()` 仍返回可供恢復的 AI observation。

獨立反例使用既有 `test_ai_restart.saved_turn()` 與原生 `graph.update_state(..., as_node="consultant")`，僅注入一份有效人工 identity，刻意製作不可能由正常准入產生的互斥 checkpoint；沒有修改 adapter 或用 wrapper 偽造讀值。執行前後記錄如下：

| 觀察 | 修正前結果 |
|---|---|
| `discover()` | 接受，AI `running`，原生 graph `closed=True` |
| `finish_startup()` | 固定 `checkpoint_unavailable`，`ready=False` |
| 固定 checkpoint | 位置已改變，AI 已被改為 `failed` |
| 人工 identity／恢復呼叫 | 原 identity 保留；0 次人工 SQL 恢復 |
| 模型 | 仍只有準備 fixture 的 1 次合成 node，恢復未重播 |
| `owner.close(timeout=2)` | `False`，沒有假報關閉 |

因此不能描述成「啟動已錯誤成功」；實際缺口是辨識互斥資料太晚，阻擋前已修改原 AI 記錄。最小修正是在共同 `_material` 的 running 分支拒絕非空人工 pending，讓 `observe`／`discover` 的普通 root／child 共用同一規則。`completed`／`cancelled`／`failed` AI 後的合法人工待保存仍應允許，交原 manual recovery 處理。

**窄複核：CLOSED。** 原作者已在 `_material` 完成 scope 檢查後加入 `record.status == "running" and values.get("jd_manual_pending") is not None` 的拒絕；root 與 child 都使用此函式，terminal 分支未被一律封鎖。新增原生互斥反例確認原 checkpoint config／values 不變、0 次 SQL 恢復、startup 不 ready，且 owner 可以正常關閉；合法 completed AI 後的人工恢復仍通過。獨立實跑這兩案 **2 PASS／8 deselected，0.76 秒**。

首次獨立 probe 因直接 Python 未加入 app 的 `src` 路徑而出現 `ModuleNotFoundError`，未執行產品邏輯；補上 `src`／`tests` 後得到上述可重現結果。此啟動設定錯誤與產品反例分開記錄。

## 2. 已核接點與證據

| 接點 | 核對結果 |
|---|---|
| 相同 native factory | [build_consultant_node](../../../../experiments/jd-relational-app/src/jd_relational/consultant_context.py) 的 inspection 路徑仍走同一 `create_agent`、實際 JD 工具及 state schema；[inspection 測試](../../../../experiments/jd-relational-app/tests/test_consultant_inspection.py) 比對正常 provider factory 的 node／channel 集合及 graph edges 完全一致。只建構帶合成 key 的 provider 物件，沒有呼叫 provider。 |
| 保留 pending | 真 `InMemorySaver` 保存的 `tools`／`AiToolMiddleware.after_model` 暫停位置，換成 inspection 圖後，固定 root／child 的 values、next、task ID／名稱／路徑／error／interrupts 與 observation 保持相同。原 messages、bindings、read、paired model view 未被刪成空白。 |
| 禁止執行 | [InspectionGuard／InspectionOnly](../../../../experiments/jd-relational-app/src/jd_relational/inspection_model.py) 為 model／tool 的同步及非同步 wrap 入口，不呼叫下一 handler；原 `after_model` 的 inspection 分支先拋固定 `execution_disabled`。測試從 model、tools、after_model 三位置誤 `invoke`／`ainvoke`，均在 notice `_project` 與 tool `_session` 前阻擋；模型 backstop 也不能返回回覆。 |
| 原 provider 不降級 | 普通 `ConfirmedChatAnthropic` 的 streaming、terminal usage、無重試及 `cache=False` 檢查保留；新增例外只允許 exact `InspectionOnly`。inspection 不接受該類別的 subclass 或任意額外 middleware，避免新增未被包住的 hook。沒有改 provider SDK 或原模型串流實作。 |
| discovery 同一解碼路徑 | [discover／observe](../../../../experiments/jd-relational-app/src/jd_relational/ai_checkpoints.py) 共用 `_observe_current`；只讀一次 latest 定位，再以明確 checkpoint ID 讀 root，child 也以固定 namespace／ID 重讀。不先猜 run 再另讀一次 latest，沒有把 pending write overlay 當永久 root。 |
| 原始 START | native input checkpoint 的 START payload 只接受原四欄，透過同一固定 Saver `get_tuple` 核 scope／request digest／原 HumanMessage。discovery 從該 payload 選新 run，不誤取 root values 中上一個 terminal run。只組合觀察材料，不重新 invoke 原 input。 |
| scope／unknown／closed manual | 既有 scope、固定 root／child 身分、paired view、未知 root 路由、缺 record 卻存在 messages／pending 等反例保留。`None` 只表示沒有 AI 材料，不授予 writer／死亡證明。合法 terminal AI 後的人工 pending 由[啟動恢復案例](../../../../experiments/jd-relational-app/tests/test_ai_restart.py)確認會走原人工恢復；running 與人工同時存在則依 AR-R01 補強。 |

「禁止執行」不等於把整張圖變成不可寫物件：刻意錯用 `invoke` 仍可能先產生框架自己的 input／error checkpoint，實作檔已明列此限制。真正 discovery 只使用 `get_state`／`get_tuple`；此結果不能解讀成允許 startup 呼叫 `invoke`。

## 3. 原生行為核對與本案取捨

本輪只核既有安裝版的必要原碼，沒有重開模型或框架品牌研究。LangChain 1.4.0 `agents/factory.py` 的 `_chain_model_call_handlers` 明列第一個 handler 為最外層；wrap hook 由 factory 組合，`after_model` 才形成獨立 graph node。本案把 `InspectionGuard` 放第一個且只新增 wrap，並在原同名 after_model 內阻擋，因此能維持原有節點圖。實際同步／非同步效果由上述 native 測試核對，並非只依註解推定。

LangGraph 1.2.11 `pregel/main.py:get_state` 將 `apply_pending_writes` 設為「config 未提供 checkpoint ID」；本案先定位再固定 ID 重讀，避免只用 latest 的 overlay。這是本案對已安裝原生 API 的使用方式，不是另外保存 checkpoint／run 狀態的權威。

相關責任路由：[host 前置與驗收範圍](host-validation-preflight.md)、[既有 AI 工具結果](../../2026-09-13-jd-ai-runtime-and-tools-slice.md)、[施工計畫](../../../plans/2026-09-13-jd-relational-app-implementation.md)。OS 所有權、SQL 原回執、完整 source／selection／Memory 及聊天 HTTP 各依原切片，不以本次檢查圖通過替代。

## 4. 實際驗證與關閉條件

獨立執行於 app 根目錄：

```powershell
$env:PYTHONUTF8='1'
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_consultant_inspection.py tests/test_ai_checkpoint_discovery.py tests/test_ai_checkpoints.py -q -p no:cacheprovider
```

結果：**82 PASS，2.77 秒**。這是本次獨立離線組；不與主代理的全組／PG／新程序數字相加。

AR-R01 修正後獨立窄驗：

```powershell
uv run --offline --frozen --cache-dir S:/caliburn/.research-tmp/uv-cache pytest tests/test_ai_restart.py -k 'conflict or previous_terminal_ai' -q -p no:cacheprovider
```

結果：**2 PASS／8 deselected，0.76 秒**。修正由原作者完成，審查者只核差異及必要反例；與前述 82 項分次列示，不合併為新的全組數字。這兩案使用原生 InMemorySaver、合成 SQL／OS ports；不充當自己 owner 實作的獨立全面審查，也不宣稱跨程序／真 DB 驗收完成。
