# 資料與契約接線

HTTP、模型工具與內部用例是不同邊界。它們共用能力模組的規則，但不要求相同 envelope，也不把模型短碼當正式資料身分。原則見[契約策略](../standards/contract-strategy.md)，資料與交易由[系統規格](../../apps/backend/architecture.md#3-資料所有權與保存)及各 owner 維護。

## 唯一契約來源及生成

| 邊界 | 來源及消費方式 |
|---|---|
| HTTP／SSE | 各模組 `presentation/api` 的 Pydantic models 與正式 routes；由 FastAPI 匯出 OpenAPI，包含具名 SSE 事件。 |
| Web | [生成程式](../../apps/frontend/scripts/generate-contracts.mjs)產生 SDK、TypeScript 及 Ajv runtime guards；不手改生成物。 |
| Agent 工具 | 各 Bundle 的 StructuredTool、參數型別、description 及結果投影；以實際組裝結果作契約測試。 |
| 公版文件 | [ocs-contract](../../packages/ocs-contract/README.md) 的 JSON Schema 產生 Python model。 |
| 公版 HTTP 形狀 | [indexer-contract](../../packages/indexer-contract/README.md) 的 Pydantic models。 |

在 repository 根目錄執行：

```powershell
pnpm --filter @caliburn/frontend codegen
pnpm --filter @caliburn/frontend codegen:check
```

生成沿後端離線 OpenAPI 匯出，不啟動資料庫或模型；`codegen:check` 在暫存目錄生成後比對，不改產品檔。單獨匯出命令見[後端 README](../../apps/backend/README.md#api-文件與實作範圍)。

## 可信參數與正式結果

HTTP 驗證外部輸入後轉為內部型別；工具由 Bundle 綁定 Workspace、正式 UUID、執行身分及版本。模型提供內容意圖，能力模組仍須核對來源、歸屬及寫入資格。短碼解析成功不表示來源存在、有效或可引用。

人工與 AI 的 JD 修改呼叫相同用例；目前內容及完整快照在同一業務交易保存。一般版本前置、取消恢復及完成輪 JD-only 撤銷各有條件，沿 [JD](../../apps/backend/src/caliburn/modules/job_description/README.md)核對，不以工具回傳成功推定整輪完成。

執行原生 items、Task 與 Checkpoint 沿官方 SDK／LangGraph 格式保存。業務模組不直接 SQL 查框架私有表，公開查讀只投影可證實的值；未知不補成零、空資料或未執行。
