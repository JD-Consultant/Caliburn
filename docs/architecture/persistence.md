# 資料保存、取消與恢復

業務資料與 Agent Checkpoint 共用 PostgreSQL，但由不同責任存取，也不保證在同一交易提交。業務表由各模組 Repository／UoW 管理，執行保存由 LangGraph 官方 Saver 管理；任何模組都不能直接修改框架私有表。

完整資料所有權圖與交易界線見[系統規格](../../apps/backend/architecture.md#3-資料所有權與保存)。

## 正式資料與版本

| 資料 | 保存與恢復責任 |
|---|---|
| JD | 每次有效操作保存目前內容及完整快照；寫入使用版本前置，指定版本恢復建立新版本。沒有候選／採用流程。見 [JD](../../apps/backend/src/caliburn/modules/job_description/README.md)。 |
| Interview | 保存正式原話、逐題問答及順序；取消整輪後不再回傳該輪正文。見 [Interview](../../apps/backend/src/caliburn/modules/interview/README.md)。 |
| Memory | 情境、理解與分析進度由同一模組管理；B1 → B2 完成後發布不可變版本。見 [Memory](../../apps/backend/src/caliburn/modules/memory/README.md)。 |
| Plan | 保存目前工作安排與恢復快照；不取代事實、JD 或完成判斷。見 [Plan](../../apps/backend/src/caliburn/modules/plan/README.md)。 |
| Agent | 使用原生 Checkpoint、Task 結果及 interrupt；保存點不是第二份業務權威。見 [Agent](../../apps/backend/src/caliburn/modules/agent/README.md)。 |

## 整輪取消與 JD 撤銷

整輪取消先停止並等待在途 writer，再由能力 callback 撤回訪談、Plan 與 JD 等本輪效果，最後保存取消完成。這不是跨模組原子交易；中途失敗不能回報完成，重送取消可接續收尾。自然完成輪不能經整輪取消入口撤回。

完成輪的「撤銷此輪 JD 改動」是另一個用例：只撤銷 JD，在後續或交錯修改使基準不安全時拒絕；不刪訪談、Plan、Memory 或 Agent 紀錄。相關時序見 [JD Bundle](../../apps/backend/src/caliburn/bundles/job_description/README.md)與[取消流程](../../apps/backend/src/caliburn/modules/agent/README.md#等待回答與取消)。

## 中斷與清理

連線中斷不等於取消。先查已保存狀態，再由使用者明確恢復；未保存的模型結果或工具副作用仍可能在恢復時重做，不能承諾所有中斷均不重送。`recorded` 只表示結果已保存，`not_recorded` 也不能證明未執行。

Workspace Application 先要求停工，再刪業務資料及所屬 Checkpoint。Host 提供停工與 Saver 清理介面。兩段不共用交易，全部確認後才回成功，失敗可用同一 ID 重試。詳見 [Workspace](../../apps/backend/src/caliburn/modules/workspace/README.md)。本版不提供舊資料或舊中斷工作的自動遷移。
