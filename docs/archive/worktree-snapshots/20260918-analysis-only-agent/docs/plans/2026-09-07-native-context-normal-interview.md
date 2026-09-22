# CT-02 正常訪談 Context 窄修計畫

> **For agentic workers:** 依 superpowers:executing-plans 與 test-driven-development 分段執行；本次接線與驗收緊密相依，由主實作者處理，完成後作獨立 code review。不要重開已核准設計。

**Goal:** 正常訪談不再因缺少選用的遠端token計數接口而無法生成，保留原生延續、原文與可控的讀取／失敗行為。
**Architecture:** 保留現有 LangChain／LangGraph／Responses 及 ABC Memory。最終request hook保留本地契約檢查；遠端count改明確選用，native模式不假造精確count。沿用官方read工具限制和既有usage metadata，不新增摘要Agent或第二套訊息儲存。
**Tech Stack:** 現行隔離lock（LangChain1.4.0／langchain-openai1.6.0／Deep Agents0.7.13／OpenAI SDK3.8.0）；本輪不升級套件。
**Spec:** [核准CT-02](../../../../docs/specs/2026-09-07-context-engineering-native-first-review.md)；[唯一狀態入口](../../../../docs/current-decisions.md)。

## Global Constraints

- 只改 `experiments/analysis-agent` 與對應隔離文檔；root register／research只更新路由。不接 production／JD／UI，不merge／push。
- 保留 `store:false`、`truncation:disabled`、Luna／medium／all_turns、原生compaction、原文保存及ABC流程。
- A維持9-model／8-tool；不以提高上限或刪保護來偽造成功。不新增每輪摘要或自動fallback。
- 本輪真API上限：12次模型請求、US$0.10費用預留；所有A/B／重試共用同一額度。模型／重試結果不完整也計入，達界線停止。不同於任何前輪額度。
- 不打印／提交金鑰、headers、原生opaque推理；實測用合成訪談；記錄回覆、可見tool結果、status、usage及必要的opaque存在／hash。
- 沒有精確preflight時不宣稱事前總量保證；真overflow安全結束，不無限重試或丟原文。endpoint不支援原生能力時回報，不另造文字摘要降級。

## 實作前檢查與檔案責任

| 檔案／相依處 | 檢查／交付 |
|---|---|
| `src/analysis_agent/budget.py` | 最終request本地驗證＋選用count；保持現有SDK／LangChain錯誤型別 |
| `src/analysis_agent/api.py` | 解析native/exact模式，仍同一SDK解析的base URL／資源生命週期 |
| `src/analysis_agent/memory_tools.py`／`live_memory.py` | 僅必要時校準按需讀取指示；官方read工具已有限量，不重寫它 |
| `tests/test_context_budget.py`／`test_native_context_budget.py` | 原exact案例明確選用；新增native HTTP wire／API／ABC回歸 |
| `README.md` | 現行配置、兩模式差異、限制／結果入口；保留他人既有修改 |
| `.test-tmp/` | 有界合成實測工具／輸出，非新產品元件；可移植結果摘要放docs/specs |

Task1的模式旗標是Task2/3的輸入；兩task共用測試fixture但不能移除exact保護回歸。語意、schema、Memory publication及背景排程不變。初始HEAD `82ac2266`；既有README／前輪回查結果未提交，須分開暫存，不能混入本次程式commit。

## Task 1：計數改為明確選用

**Files:** Modify `src/analysis_agent/budget.py`, `src/analysis_agent/api.py`, `tests/test_context_budget.py`; Create `tests/test_native_context_budget.py`。
**Interfaces:** `ResponsesBudget(..., exact_count: bool = False)`；factory `Q019_CONTEXT_BUDGET_MODE=native|exact`，預設native。exact保留原完整count路徑；非法模式在建立DB/client前拒絕。

- [x] 寫失敗測試：用真ChatOpenAI／SDK序列化＋MockTransport，native模式counter transport若被呼叫即失敗；正常response仍生成。對照exact模式count的404須保持明確失敗，不能偷偷fallback。

```python
guard = ResponsesBudget(counter=counter, model='gpt-5.6-luna',
                        context_window_tokens=10000, exact_count=False)
# attach guard to real model HTTP client; collect actual serialized POST
result = model.invoke('我負責依客戶需求開發網站。', max_output_tokens=128)
assert result.response_metadata['status'] == 'completed'
assert counted == []
assert len(sent) == 1
```

- [x] 執行 `uv run --offline --no-sync pytest tests/test_native_context_budget.py -q --tb=short`，確認因缺新介面／行為而RED。
- [x] 最小GREEN：新增boolean旗標驗證；model／max_output_tokens／truncation／endpoint檢查兩模式皆保留。只在exact分支檢查count可接受的欄位並呼叫counter，native不改request body。

```python
# after shared local contract checks
if not self.exact_count:
    return
# existing supported-count-fields validation + SDK count + capacity comparison
```

- [x] factory先解析mode，非法值raise ValueError；建guard時傳 `exact_count=(mode == 'exact')`。不捕獲404改成功，不新增近似tokenizer。
- [x] 舊exact測試所有guard建構顯式 `exact_count=True`；加native錯誤max/truncation/model、unknown count-only mapping不阻擋原生create等邊界。
- [x] 跑兩份測試GREEN；README同步。僅暫存本task檔案，commit `fix: make exact context preflight optional`。

## Task 2：整體Context與正常訪談離線驗收

**Files:** `tests/test_native_context_budget.py`；必要的局部提示修正才改 `memory_tools.py`／`live_memory.py`；不新增Memory工具或工具參數。
**Interfaces:** Task1的native mode、現有service_harness／create_app、官方read_file offset/limit、現有canonical reader及usage metadata。

- [x] 寫API情境：第一輪成功、第二輪一般更正／追問、兩輪原文各存一次；確認實際請求保留前轮原生item，原生compaction後canonical仍可回讀，最新人類訊息不重複。
- [x] 寫native provider overflow情境：官方error code回傳後run退出、不無限retry；原文仍在，下一個新訊息可提交。這測的是我們的service分類，不是自造overflow判斷。
- [x] 將既有A完整payload與B1／B2接線情境擴充跑native：規則、guide、工具、Skill／tool結果和B1 schema仍經最終hook且沒有count HTTP；actual raw/AIMessage usage保留。
- [x] 對官方read工具做一個局部整合檢查：長而多行的中文檔案受限、回傳續讀位置，按位置可取得後段；不在產品另寫裁切器。單一極長行的限制寫進結果，不當本輪一般訪談通過的證據。
- [ ] 如真測前段顯示固定ls→grep→read造成多餘步數，只將現有工具／提示改清楚「已知路徑直接讀、資料足夠即回答、不要每輪重讀」；不改分析方法、不放寬calls。
- [x] 跑相關回歸及全套（包括專用PG，不能用skip掩蓋）；compileall、lock檢查、diff check；commit本task必要變更。

## Task 3：小額真實服務入口與交付

**Files:** 有界臨時測試腳本（先離線檢查）；`docs/specs/2026-09-07-native-context-normal-interview-results.md`、README結果路由。
**Interfaces:** 真 `open_service`／FastAPI application、隔離本地q019 DB、已授權本機直連設定；12請求共用帳本。

- [x] 沿用既有測試的ledger／有限請求機制，不新增產品計費系統；確認實際計價依據及保守費用預留。先離線驗證上限能阻擋第13次；SDK自動重試也不得繞過。
- [x] 先普通訪談（網站接案、案例補充、更正、追問），正常A成功後才看餘額是否足夠回查。若觸發B亦記入同一帳本；必要時重用既有成功Memory測回查，不為回查重跑B。
- [x] 記錄完整可見合成訪談與usage；HTTP200但incomplete不算完成。沒有實際壓縮產物就不得宣稱真壓縮已驗成；不是本輪大型壓測。
- [x] 有底層能力缺口／新產品選擇或額度用完便停並報告；不換模型、不提高上限。
- [x] 獨立review核對改動、測試證據與核准設計；修正必要finding，補結果／root入口；本地commit＋tag，不merge／push。

## 進度／結論（唯一施工紀錄）

- 基線：54 passed／9.79s（沙箱外離線執行）；沙箱內两次失敗均為pytest暫存ACL，非產品測試失敗。既有1項Starlette deprecation warning。
- Task1／Task2機制完成：新增native介面先14項RED，完整離線＋專用PG **547 passed／0 skipped，70.45s**；compileall／offline lock／diff check通過。共用最終hook及native/exact接線測試作為同一個窄修提交，沒有另加產品機制。
- 官方分頁測試已存在，沿用 `test_official_model_visible_pagination_preserves_every_long_line`，刪掉本輪重複fixture，不在產品再寫裁切器。
- 獨立review無Critical／Important；CT02-R01為README native／exact錯誤碼敘述，已對照service修正。沒有藉測試移除framework行為。
- Task3完成核准範圍：真factory三輪正常訪談／6次模型成功；獨立reader用剩餘6次，沒有最終答案，第13次在transport前被擋。合計12次／usage估算US$0.00642272，停止付費；不是長訪談／全部Memory驗收。
- 回查提示優化仍待後續：先完整回看OpenAI read-path研究及新查官方來源，核對Deep Agents literal search契約，未因步數自行增工具／上限／改prompt。
- 完整結果、來源、腳本、已知限制只放[本輪短結果](../specs/2026-09-07-native-context-normal-interview-results.md)及其evidence，不把原始tool軌跡塞進本計畫。保留隔離worktree，不merge／push；舊回查未提交檔案保持獨立。
- 程式窄修已本地commit `e3b93aa7`；紀錄與證據另作文件commit。Evidence獨立review無finding，不追加真API。
