# Q019-APP-01 Task4：背景整理接線結果

> 2026-09-06，隔離 `codex/analysis-only-agent`，base `fb6f5bd5`。**Checkpoint B 隔離驗收通過；不等於 UI／真模型品質已驗收。** 本段本地保存標籤：`q019-background-dispatch-v1`；實際 commit 及 branch 狀態見 main current register。

## 路由與範圍

- [main current register](../../../../docs/current-decisions.md) → [已核准計畫 Task4](../../../../docs/plans/2026-09-06-analysis-only-agent-application-wiring.md#task-4背景喚醒與重啟重排)。
- 行為依據：[通知／結果政策 §§4–6](../../../../docs/specs/2026-09-06-memory-consolidation-request-wiring-design.md)；過程：[本段ledger](../plans/2026-09-06-background-dispatch-execution-notes.md)。
- 第一版仍只分析；不接舊產品、JD、UI、手動整理入口或付費模型；沒有修改B1/B2/C內容分析與發布演算法。

## 交付的接力

1. 通知工具仍只回覆收到要求。已安全封閉的問答才成為新整理來源。
2. APScheduler3.11.3的一個wake job呼叫單一dispatcher。獨立於A executor，全App一次一個B；不同文件輪流取得工作機會。
3. dispatcher讀通知／成功來源cursor，保存本次目標引用並分批交既有B1/B2。成功只推真正發布範圍；通知在前半段也不會吃掉後半段。
4. 重建clients後從舊B1/B2 checkpoint接續。已抽取不重抽、已執行工具不從頭再做、已發布但回覆遺失沿receipt對帳。
5. 背景成功不叫A多回答一輪。仍未恢復的失敗，下一正常A run會得到簡短可用性提示及真實來源範圍；不寫成員工訊息、工作事實或第二個同call工具結果。恢復後不注入過期失敗提示。
6. 關閉服務先拒絕新工作，再等待已進入的B/A安全退出，最後關HTTP／PG clients。直接dispatcher入口也不能在服務關閉後啟動模型。

## 框架與自訂責任

| 責任 | 實際持有者 | 沒有做的事 |
|---|---|---|
| wake、pool、合併漏跑時點 | APScheduler3.11.3 public BackgroundScheduler／ThreadPoolExecutor | 不把scheduler jobstore當Memory流程owner |
| B1/B2 durable進度與原始問答 | 原有LangGraph graph／PostgresSaver | 不另存訪談正文，不重寫Agent loop |
| 詳記、候選、理解、導覽 | 原有Store／backend／publication | 不增加第六種Memory，不因排程改來源authority |
| admission、blocked、unclean-restart計數 | SQLAlchemy小型 `q019_background_admission` 技術列 | 只存文件／來源引用／狀態／計數，不複製B1/B2產物 |
| 下一run的短提示 | 公開AgentMiddleware before_agent／wrap_model_call | 不發假HumanMessage，不解碼thinking，不額外喚醒模型 |

最後兩列是已核准應用接線需求的具體mapping，不宣稱OpenAI／Anthropic原生有同名欄位或資料表。

## 成本及尚未定案的數值

- 新文字量後備有可配置入口，未設定時只依耐久段落通知；不擅自採6000字、90秒或4回合。
- wake間隔與意外程序中斷的自動恢復上限要求部署明訂。測試使用的1次恢復／60秒wake只測邊界，不是產品推薦值。
- 一般caught error durable blocked，不由tick、新通知或restart重置。SDK暫時重試／B模型修工具参数沿原機制，不外加model retry。
- 未正常返回而留下running才消耗持久auto-recovery計數；確認已發布時優先無模型對帳。這不是曾撤回的「員工手動最多恢復一次」。
- 對來源／候選過大仍如實阻擋，不截掉中間文字。真正prompt與批次容量、live延遲／費用待小額驗收；呼叫計數不是金額保證。
- 部署的 `Q019_MAX_OUTPUT_TOKENS` 經模型設定傳給 A、B1 與 B2，不讓 B2 的 standalone 預設覆蓋它；這是每次回應上限，不是整次整理的費用上限。

## 測試證據

- 基線：276 passed／0 skipped，46.10s。
- 通知→真正B、無新來源零呼叫、無通知不自動整理、明訂文字量後備、重要短句仍保存。
- 分批後段保持pending、未決A不交B、安全關閉的失敗原話不漏、A/B並行、全域B限制及不同文件隔離。
- 真APScheduler喚醒／關閉join；API只回safe background status，沒有新增手動整理POST。
- 真PG重建clients：僅通知、B1已存、B2工具已存、Memory已準備、publish回覆遺失五個停止點；普通失敗跨重建仍blocked。
- Request-only可用性提示、不寫對話、不重複喚醒A；經技術恢復後提示消失。
- 第一輪完整294 passed／0 skipped，82.37s；第二輪296 passed／0 skipped，81.21s。這是中間證據，最終結果以下節為準。

**不是證據的部分：**沒有真API分析品質／Token費用結果，沒有真OS斷電測試，也不宣稱任意外部工具exactly-once。停止點注入及client重建證明所測框架恢復路徑，不延伸成所有故障都可自動恢復。

## 本段發現與修復

- 已發布但exception阻擋時，不能先看blocked就略過：先依真實cursor/receipt對帳，才判斷是否允許任何付費恢復。
- 當通知在第一批，成功後不能只重新搜尋未消費通知：本次目標引用保持到整段發布，避免後半段遺留。
- shutdown後直接呼叫dispatcher仍可能開模型：紅綠測試確認，再以service admission狀態及同一全域鎖收尾；不以Future.cancel冒充已停。
- 一項測試最初誤以為4000字必須是一段；讀取器原有3000字分頁會拆成多個完整保留的segment。改驗拼合後原文相同，沒有為滿足測試改掉分頁／刪細節。
- 獨立審核 **T4-R01／P2** 發現 B2 未沿用部署輸出上限。主代理新增實際 HTTP payload 測試，1000／6000 兩組先見紅：A/A/B1 沿設定，B2 卻固定4096。接線層明確傳入模型已設定的預算，15項背景測試轉綠；不新增另一套 A/B 預算或修改 B2 內部流程。最終複核狀態見下節。

## 官方資料（2026-09-06核對）

- [APScheduler stable user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)：wake job、coalesce、單job `max_instances` 與可重建排程；不提供本案記憶觸發政策。
- [APScheduler pool executor](https://apscheduler.readthedocs.io/en/3.x/modules/executors/pool.html)、[stable PyPI](https://pypi.org/project/APScheduler/)：3.11.3、Python>=3.8。另讀實際安裝的scheduler/executor source核對shutdown與單pool生命週期；沒有import private API。
- [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：既有checkpoint恢復，不把排程表當成執行結果。框架細節沿前段已驗證接線，不重做廣泛Memory研究。
- [LangChain middleware](https://docs.langchain.com/oss/python/langchain/middleware/custom)：request Context接點；是否傳達背景限制由本案mapping决定。
- [FastAPI lifespan](https://fastapi.tiangolo.com/advanced/events/)：client／executor生命週期；仍只有本機一個process。

## 最終review／closure

- **最終驗證：**專用PG已設定並核對容器label後，`uv run --no-sync pytest -q -rs --tb=short`：**298 passed／0 skipped，56.50s，exit 0**。`uv run --no-sync python -m compileall -q src tests`、`uv lock --check --offline`（80 packages）、`git diff --check` 均 exit 0。
- **已知warning：**上游 Starlette TestClient 使用 AnyIO 舊 `BlockingPortal` alias，1項 deprecation warning；未隱藏、不是產品執行失敗。本輪不為此patch上游私有API。
- **獨立review：**首位reviewer因服務capacity未執行，不計驗收。第二位完成全切片spec／quality審查，唯一重要finding **T4-R01／P2已CLOSED**；修復後限定複核PASS，另以假HTTP驗1000／6000／未設定三種wire行為，無新增finding。沒有未處理Critical／Important項目。
- **方向核對：**Memory五產物／引用／原文authority未變，沿框架保存與恢復；新增僅應用喚醒、技術admission及Context接線。沒有重新發明分析流程、增加JD、員工手動整理或每輪強制整理。
- **成本／作用範圍：**付費呼叫0，不載入舊 `.env`、未重啟Docker、不接production，未merge／push。測試期間僅清理專用實驗文件資料。
- **重開條件：**可重現接線缺陷、公開契約變更或Owner更改觸發／效果需求。單純新名詞不重開架構。
- **下一gate：**保存後段落回報，再寫最小聊天室及小額Luna／medium訪談計畫。新文字量門檻、真模型預算與Prompt迭代另段確認；不以本次測試代替長訪談記憶品質／費用驗收。
