# Q019-APP-01 Task4 執行紀錄

此檔是已核准 Task4 的施工／review ledger，不是新產品決策；parent：[main 接線計畫](../../../../docs/plans/2026-09-06-analysis-only-agent-application-wiring.md)。

## Preflight

- Topic：Q019-APP-01／Q019-MEM-CADENCE-01；stage：隔離 G7 Task4。
- 已完整回看 main decision-process、parent plan、application wiring design、failure recovery review、cadence review、notification wiring design。最新 main register 優先於 worktree 歷史 register。
- Binding：A不等B，單process／全App一個B；來源僅Saver，五Memory產物／B1/B2/C不重設；成功不喚醒A，未恢復錯誤只放下次正常run Context；零付費，不接JD／production。
- 唯一未定值：新文字量後備門檻。不補舊6000／90秒／4回合；保留明確可配置、未配置不啟用的後備。段落通知仍可正常工作。
- 狀態：`fb6f5bd5` clean；基線276 passed／0 skipped，46.10s；上游Starlette warning 1。
- 本task的來源投影、背景admission與Context接線互相依賴，由主代理按TDD實作，完成後獨立review；不拆成競爭修改同一seam的平行worker。

## 接線檢查點

1. 來源從既有canonical順序與成功cursor選出，不從UUID大小／壓縮context推算；有界批次不遺失後半段。
2. APScheduler只喚醒單一dispatcher；B1/B2 checkpoint與publication仍持有實際進度。catalog只增加技術admission／blocked／恢復記錄，不放第二份來源或Memory。
3. 暫時provider錯誤只沿既有SDK retry；catch後blocked，不因tick／新通知重置。程序意外結束的自動恢復次數用明確配置及耐久計數，不暗訂最佳值；無限重開不能無限刷新額度。不是撤回過的「員工手動只能恢復一次」。
4. 下一正常A run讀當前失敗狀態，程式提示不寫成員工訊息／記憶事實；恢復後不再注入已失效提示。
5. 模型／工具步數沿既有B1/B2；應用已配置的每次輸出額度必須傳入B2，不被standalone預設覆蓋。不把dispatcher recovery count聲稱為美元上限。

## 新查官方來源

2026-09-06：[APScheduler stable3.x user guide](https://apscheduler.readthedocs.io/en/3.x/userguide.html)、[pool executor](https://apscheduler.readthedocs.io/en/3.x/modules/executors/pool.html)、[PyPI](https://pypi.org/project/APScheduler/)；PyPI實際stable為3.11.3，requires Python>=3.8。`max_instances`限單job，pool大小限executor；`coalesce`不是業務來源消費。固定wake job可重建、不需要另存scheduler job表。細節使用其public APIs；本案觸發／恢復預算是已核准mapping，不冒稱各家相同。

## 實作與驗收

- 實作已接來源投影、單一B dispatcher、API/lifespan、當前失敗Context；新增tests先見紅再實作。
- 最終完整回歸：298 passed／0 skipped，56.50s，付費0；compileall／offline lock（80packages）／diff check通過。上游Starlette warning仍1，未壓掉。此前296項為中間結果。
- 首位reviewer未能執行，服務回報model capacity；第二位完成獨立review，提出T4-R01／P2：B2覆蓋部署輸出上限。主代理實際wire測試1000／6000各先見紅，接線層傳入明訂值後背景15項轉綠；限定複核PASS，T4-R01 CLOSED，無新增finding。reviewer另驗未配置時沿原預設；未改B2內部、不補第二套預算。
- 實測修正：部分batch持續target、已發布lost-reply先對帳、shutdown後禁止新dispatcher模型工作及join直接入口。來源分頁測試改驗各segments拼合不遺失，沒有改成全量一次回傳。

## Closure

Task4／Checkpoint B 已通過隔離驗收。本段14檔於同一task保存；標籤 `q019-background-dispatch-v1`，實際SHA／工作樹狀態由 main register 持有。[結果](../specs/2026-09-06-background-dispatch-results.md)集中保存測試、finding、官方來源、限制及重開條件，不再重複研究。接續為最小聊天室設計與獨立小額驗收計畫；不自行開付費模型、不merge／push。
