# 驗證責任與操作入口

測試按受影響責任選擇。根 `pnpm check` 執行文件、lint、型別、單元、腳本、前端契約與 build；真資料庫、真瀏覽器、公版模型與付費 provider 另行明示執行。

| 受影響範圍 | 必要證據及入口 |
|---|---|
| Domain／Application 規則 | 正常與失敗反例；[後端單元測試](../../apps/backend/tests/unit/) |
| 交易、版本、FK、隔離、保存與恢復 | 專用真 PostgreSQL 的[整合測試](../../apps/backend/tests/integration/)；不以 SQLite 或 mock 代替 |
| 公版索引、固定來源與查讀 | [公版測試及限制](../../apps/backend/src/caliburn/modules/occupation_reference/README.md#程式責任與驗證範圍)；真 Qdrant 及相容權重另外核對 |
| HTTP／SSE／工具格式 | 後端邊界測試、實際 Tool 初始化及前端生成比對；離線 payload 不等於真 provider 接受 |
| 使用者操作與頁面生命週期 | [前端測試](../../apps/frontend/README.md#可重跑的離線瀏覽器驗收)，沿正式 Host、真 PostgreSQL、離線模型及真瀏覽器 |
| Docker／原生交付 | [操作手冊](../operations/README.md)的明示安裝、遷移、啟動及代表路由；靜態 Compose 檢查不代替容器啟動 |
| Prompt／Tool／Context 品質 | [模型品質比較](../../CONTRIBUTING.md#模型品質比較)與[內容評閱](../product/quality-review.md)；沿正式保存與取消流程 |
| 文件與圖面 | `pnpm docs:check`、圖源引用與實際渲染／視覺檢查 |

真 PG 測試以 `CALIBURN_REBUILD_TEST_DATABASE_URL` 指向專用合成資料庫；真 Qdrant 以 `CALIBURN_REBUILD_TEST_QDRANT_URL` 指向專用 loopback server。各入口會建立／清理自己的 schema 或 collection，設定限制沿[後端 README](../../apps/backend/README.md#安裝與檢查)。未設定而 skip 必須明示，不能列為驗收成功。

完成回報保留命令、受測版本、依賴、通過／失敗／跳過與未驗範圍。已受影響的原測試須繼續有效，不刪除或放寬需求以消除失敗；沒有新變更或疑點時，不反覆追加同一批檢查。
