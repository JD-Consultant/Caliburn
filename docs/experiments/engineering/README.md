# 工程驗證紀錄

這裡保存公版參考 API、模型工具及角色接線的反例、測試結果與重播資料。檢索相關性與訪談分析品質另見[實驗索引](../README.md)及[產品驗證](../product-validation/README.md)，工程測試不代替這些品質判斷。

## 公版參考 API

[API 驗證資料](2026-10-05-occupation-reference-api/README.md)記錄來源固定性、D／T 候選聯集、完整目錄、來源正文、模型身分及失敗處理。原回歸為 86 項；真 Qdrant 重播核對 805 份來源與 8,068 個任務單位。另有 F01 的新 query embedding、34 組重排序及 64 次任務讀取，與原前五一致。

數據、環境、原始結果與重現腳本都在同一資料夾。單次實測不是通用效能結論；現行行為依[API 契約](../../specs/2026-10-05-occupation-reference-api-design.md)。

## 公版參考工具

| 驗證主題 | 原件 |
|---|---|
| HTTP 邊界、候選保存、正式資格與重播 | [初版驗證](2026-10-05-occupation-reference-tools/verification.md) |
| 選取參考與明確否認範圍 | [排除範圍驗證](2026-10-05-occupation-reference-tools/excluded-work-verification.md) |
| B1／B2 固定範圍的唯讀入口 | [Memory 讀取驗證](2026-10-05-occupation-reference-tools/memory-read-verification.md) |
| 說明、參數、錯誤下一步與成功回傳 | [原審核](2026-10-05-occupation-reference-tools/tool-contract-audit.md)、[修正與驗證](2026-10-05-occupation-reference-tools/hardening-verification.md) |

各頁保留當輪版本、反例與限制；較早的 confirmations 方案是演進證據，不是目前並存的工具。現行 state 與角色權限依[工具契約](../../specs/2026-10-04-public-reference-completion-design.md)及 [ADR0080](../../adr/0080-opt-in-public-reference-agent-tools.md)。

## 角色接線

[接線驗證](2026-10-05-occupation-reference-tools/agent-integration-verification.md)使用合成 Responses／公版 HTTP transport 與真 PostgreSQL，核對可選設定、A 讀寫、B1／B2 唯讀、跨輪 state、固定 Memory 範圍，以及中斷後沿原請求與原生 checkpoint 恢復。它不代表已驗證公版查漏或 JD 收尾品質。

## Docker 公版參考模式

[配置與套件驗證](2026-10-06-docker-rag-startup.md)記錄基本／公版參考模式、查詢 API 容器化、六項實際 Compose 解析測試、鎖定安裝及 API 回歸。當輪 Docker 引擎未開，Linux 映像、GPU 與完整模式的真容器旅程尚未驗證，操作與後續檢查分別由該頁及[runbook](../../runbook.md#含公版參考的-docker-模式)維護。

## 原件與歷史路徑

這些資料原放在 `docs/plans/evidence/`，現在依用途歸入工程驗證。JSON、測試輸出與原始結果未改寫；Markdown 只更新檔案連結與重現命令。原 metadata 內的舊路徑仍代表當時位置，查閱時將 `docs/plans/evidence/` 替換為 `docs/experiments/engineering/` 即可。歷史提交的原樣文件依[歷史索引](../../history.md)取回。

重現腳本可能建立新的測試輸出。若要保留原件，請先取回固定提交並在獨立目錄執行，不直接覆寫本目錄的已保存結果。`run_tests.py` 僅指向已確認的本機測試 PostgreSQL；不會初始化或刪除示範資料庫。
