# Q019-APP-01 Task3：最小 API 與服務接線紀錄

2026-09-06。**Task3 隔離驗證完成，獨立審核 CLOSED；不是完整產品或付費品質驗收。** 本地保存標籤：`q019-analysis-api-v1`（提交／建tag後由主工作區register記錄實際commit）。

## 閱讀路由與本輪邊界

- 狀態入口：[主工作區 current decisions](S:/caliburn/docs/current-decisions.md)。
- 有效設計：[應用接線](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-application-wiring-design.md) §4–7；[父計畫](S:/caliburn/docs/plans/2026-09-06-analysis-only-agent-application-wiring.md) Task3。
- 前段：[通知切片](2026-09-06-memory-consolidation-notification-results.md)。本段不重做通知政策或 Memory 五產物。
- 範圍：獨立 `experiments/analysis-agent`，主顧問 API／工作管理；不接舊 production，不做 JD／UI／B 排程，付費呼叫 0。
- 技能流程：執行既有計畫、TDD、遇錯先追因、獨立唯讀 review；Task3 入站／worker／狀態高度耦合，主 agent 實作，不平行派多個實作者寫同一狀態接點。

## 接線實際責任

| 部分 | 實現 | 不宣稱的能力 |
|---|---|---|
| 文件／請求路由 | SQLAlchemy catalog；UUID、輸入指紋、狀態、恢復次數 | 不存第二份訊息內容、不取代 LangGraph 執行進度 |
| 接收文字 | 公開 `update_state(..., as_node=START)` 寫根 checkpoint，再確認保存 | 不是先回202再期待背景有存到 |
| 執行／恢復 | 原 `build_conversation`，worker `invoke(None, durability='sync')` | 不重送 HumanMessage、不自製模型迴圈、不自動重啟付費工作 |
| 狀態查詢 | 根／子 `get_state(..., subgraphs=True)` 對帳 catalog | 子圖未開始的空 state 不能蓋掉根圖已保存輸入 |
| 安全停止 | 公開 before/after-model 與 model/tool entry middleware＋Event；既有 `close_turn` | 不用 Future.cancel 假裝同步 thread 已停止；已開始 SDK call（含內部 retry）／工具先安全返回 |
| API／生命週期 | FastAPI lifespan、同步路由 threadpool、單程序 Uvicorn | 不聲稱多worker／多機 queue；關頁不會關閉服務worker |
| 記憶／推理 | 原 Saver、Store、MemorySession、native request view | 不增加新 Memory／來源層，不解碼／顯示 opaque reasoning |

這些是已核准本機應用對官方 primitives 的映射，不宣稱 exact schema、endpoint 或 executor 配置是各大廠共同內部實作。

## 官方核對（本輪 2026-09-06）

1. [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)：資源在啟動／關閉管理。本段最後才關閉 HTTP／DB clients，先等待 worker 靜止。
2. [FastAPI async 技術細節](https://fastapi.tiangolo.com/async/#path-operation-functions)：同步路由移到 threadpool；async 路由不能直接堵住 event loop。圖工作另有服務executor，非 HTTP response 的 BackgroundTasks。
3. [LangGraph update state](https://docs.langchain.com/oss/python/langgraph/use-time-travel#update-state)：公開 state 更新與節點路由；本段只操作 latest root，不拿歷史checkpoint重播來接收新訊息。實際 `START`、首次無child、重建Saver行為有本地測試。
4. [Python Future.cancel／shutdown](https://docs.python.org/3.12/library/concurrent.futures.html)：running 工作不因 cancel 被殺掉，shutdown(wait=True) 等待已開始工作。此限制已寫入服務與測試。
5. [OpenAI retry 與時間界線](https://developers.openai.com/api/docs/guides/rate-limits#retrying-with-exponential-backoff)：SDK retry、單attempt timeout、整體工作時間不同；不疊 retry、不把timeout當精確金額保證。SDK3.8.0沿用原生retry設定。
6. [FastAPI套件](https://pypi.org/project/fastapi/)、[Uvicorn套件](https://pypi.org/project/uvicorn/)：安裝前直接查發行metadata；0.141.1／0.52.4均Python≥3.10，適用本隔離Python3.12。原已鎖定LC/LG/OpenAI套件不盲升；新增依賴完整記uv.lock。
7. [LangChain 自訂 middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)：wrap hooks 可不呼叫 handler；在工具入口收到停止時，回傳「確定未執行」ToolMessage，再於下一模型入口收尾。不是偽造已進行的工具失敗；after_model 單一檢查不足以涵蓋後續hook窗口。
8. [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：恢復依保存的節點與結果；本段仍用 `invoke(None)`，C 的冪等發布由前段已核准的 operation/CAS/receipt 接點承擔，不由 endpoint 再生成操作。
9. [OpenAI API error codes](https://developers.openai.com/api/docs/guides/error-codes#api-errors)：429也可能是credits／spend／usage限額；公開`error.code`有`credit_balance_exhausted`、`organization_spend_limit_exceeded`、`project_spend_limit_exceeded`、`organization_usage_limit_exceeded`，較廣`type`仍可為`insufficient_quota`。本段使用SDK公開code/type分辨，不靠錯誤文字比對；只修API的手動恢復判斷，不修改官方SDK內層retry。此查核是R07有重現後的窄幅補證，不重做provider或Memory研究。

## 已遇到的問題與處理

- 測試目錄沙箱ACL不允許pytest讀其暫存目錄：改用獲准本機測試執行，沒有改產品功能或關閉驗證。
- fakeHTTP測試用 `model_copy(max_retries=0)` 不會重建既有SDK client；實際binding欄位0、SDK仍2。移除誤導性test設定，注入足夠次數的錯誤真正耗盡官方retry；不修改product retry政策。
- catalog已插入但input未存，或input已存而worker未啟動：靠原message identity核對checkpoint，分別為not_received／interrupted；同key重送不永遠卡receiving、不新增第二份原話。
- admitted root已有輸入而child尚無首個checkpoint：官方回空child snapshot。來源／API以根資料為準；安全收尾同樣處理空child，不猜已執行工具。
- 最新Starlette1.6.0的TestClient引用`anyio.abc.BlockingPortal`產生上游deprecation warning；不隱藏警告，不為測試提示更換已驗證provider依賴。它不是產品呼叫失敗。

## 驗證狀態

工作區 `S:/caliburn/.worktrees/analysis-only-agent`，分支 `codex/analysis-only-agent`；只改隔離package／本段結果。父計畫與current register在main更新路由，不暫存其他歷史修改。沿用專用 `caliburn-q019-postgres`／`127.0.0.1:55433/q019_agent_test`；執行前核對container label，密碼只進程序環境，測試只清理自己的document IDs，未重啟／reset Docker。

| 驗證 | 本輪最終結果 |
|---|---|
| `uv run --no-sync pytest -q -rs --tb=short`，設定專用PG DSN | **276 passed／0 skipped，45.47s** |
| `uv run --no-sync python -m compileall -q src tests` | exit0 |
| `uv lock --check --offline` | exit0，78 packages |
| `git diff --check`／提交前 staged diff check | 必須exit0才提交；執行結果由register保存 |
| 獨立review | T3-R01–R07全部CLOSED，無新增finding |
| 真模型呼叫／API費用 | **0／0**；所有模型HTTP由測試替代 |

版本：FastAPI0.141.1、Uvicorn0.52.4；原LC1.4.0、LG1.2.11、langchain-openai1.6.0、OpenAI3.8.0、Saver/Store依賴維持已鎖版本。Starlette1.6.0上游TestClient deprecation warning仍顯示（1 warning），不是測試失敗、不壓警告。

測試入口：[service](../../experiments/analysis-agent/tests/test_service.py)、[API](../../experiments/analysis-agent/tests/test_api.py)、[真PG接線](../../experiments/analysis-agent/tests/test_postgres_service.py)。包含：double-submit、保存前／後回覆遺失、舊run不能取消新run、provider等待中停止、工具入口停止、原生reasoning不出UI、輸出／compaction／timeout真正傳至request、同input恢復、不明C的commit前／後全client重建、API真正lifespan資源啟閉。先前219 passed／25 skipped為開工前離線baseline；270 passed是中途快照，不代替本段276最終結果。

**方向複核：**仍為只分析／單文件一聊天室；原文與native items在官方Saver，Memory仍走Store＋既有發布；無第二份訊息正文、額外memory分析agent或自製模型loop。所有新增模型欄位只屬部署設定，沒有要求LLM填run UUID、timeout、usage或恢復狀態。未新增JD、UI、自動B排程或「每輪強制整理」。

## 獨立 review 與可重現修復

Reviewer 先以真實安裝套件／假 HTTP 獨立重現；主實作者加回歸，確認修復前失敗、修復後通過。R01–R06先限定複核CLOSED；R07另限定複核CLOSED，不重新開啟已修問題。Reviewer未重跑全套／PG；全套是主實作者上列最終結果。

| ID | 問題／影響 | 修正與證據 | 狀態 |
|---|---|---|---|
| T3-R01 P1 | HTTP client 的 timeout 被 LC 建 SDK 的 `timeout=None` 覆蓋，可能無限等 | `build_model` 建構時明確 timeout；檢查實際 request extensions，並測預設 API lifespan 的整條接線 | CLOSED |
| T3-R02 P1 | 舊 receiving 寫入失敗，另一個 run 忙時重送仍回202 | 同 key 也核實自身 message ID 已在根 Saver；未存且其他工作忙則409 | CLOSED |
| T3-R03 P1 | 停止舊 receiving 會關掉正在執行的新 run | 核實 pending input ID；只有該 run 能設 stop，靜止才可 close | CLOSED |
| T3-R04 P1 | C commit前失敗無receipt，API沒有恢復出口 | 只對已有canonical operation binding的未配對C提供顯式resume；PG測commit前／後結果遺失及完整client重建，同operation且revision只增加一次 | CLOSED |
| T3-R05 P2 | 工具剛好用完卻擋掉下一次合法回答 | 工具額度不當成一律禁模型恢復；仍由官方middleware攔額外呼叫，測1 tool／2 model成功且不重置counter | CLOSED |
| T3-R06 P2 | after_model後至工具入口間收到stop仍執行通知 | 在公開wrap_tool_call再次檢查；不呼叫handler，存確定未執行的配對結果；測後續hook被阻塞時stop不留下整理request | CLOSED |
| T3-R07 P2 | 帳務額度未修時仍提供manual-resume | 依SDK公開code/type分類billing_error，安全關閉為configuration_error；重開後仍不顯示假恢復，沒有餘額查詢或計費系統；限定複核也確認普通slow_down仍可恢復、SDK內層2次retry未改 | CLOSED |

另外補測：provider 最終傳輸失敗前已要求停止，也應安全取消而非再次邀請恢復；已安全關閉的API outcome須從checkpoint對帳，不只更新catalog狀態。未觀察到的用量保持unknown。這些均為既有Task3要求的修復，不變更Memory分層或觸發政策。

## 還沒做／下一段

- Task4真正背景dispatcher、B1/B2喚醒、失敗狀態進下一正常run。已有通知回執不等於B已開始整理。
- 新文字量後備數值仍未定；不復活90秒／固定回合數／舊6000字。
- API啟動需顯式配置原生compaction閾值、單request timeout、輸出上限；本段不猜跨模型通用預設。
- API恢復白名單不代表所有runtime／未知工具錯誤都能自行修好；程序錯誤仍須定位修復。長Retry-After由SDK判斷是否在該次呼叫內等待；UI尚未提供倒數或整份工作總時限，本段不宣稱有自訂全域deadline／帳務額度保證。
- 最小UI／Skill內容與Prompt集中優化、Luna medium小額實訪驗收按既有後續路線，未做不宣稱分析效果已達標。
