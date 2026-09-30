# T09 歷史正式答覆的原 Turn 公開定位

- 日期：2026-09-30。
- 狀態：後端窄切片；不代表 T09／SSE／完整 UI 旅程驗收完成。
- 責任依據：[訪談保存](../../../implementation/interview-storage.md)、[介面交付 §2–3](../../../implementation/interface-and-delivery.md#2-串流不是保存權威)、[產品保存承諾](../../../product-concept.md)。

## 接線

`GET /api/job-files/{job_file_id}/interviews` 的 `messages[].execution_id` 為 required nullable UUID。只有正式 consultant reply 能由原 `interview_replies` 關係取得其原 Turn；App／員工訊息或無既有關聯時為 null。不從最近 Turn、說話者交替、序號奇偶或文字猜測。

UI 按需呼叫既有 `GET /api/job-files/{job_file_id}/consultant-turns/{execution_id}` 取得 `commentary`，既有白名單只投影公開 response/message identity 與文字；null 表示未提供 reader，不能當成空陣列。Halley 負責 UI；本切片不改 registry、runner、bootstrap，也不新增 store、migration 或 checkpoint 格式。

原 interviews owner 新增 `read_public_interview_history(session, job_file_id) -> list[InterviewHistoryEntry]`；entry 包含原 `InterviewMessage` 及 nullable execution ID。正式來源工具使用的 DTO、查詢與資格維持不變。SQL 為同 owner 正式資格／原文／答覆關聯的一次有範圍 JOIN，無 N+1 查詢。

Schema authority：`apps/api/contracts/http/interview-history.schema.json`；以既有 `scripts/generate_contracts.py` 生成 Python／TypeScript，未手改生成檔。

## Red／Green 與限制

新增反例先證實 HTTP 完成歷史缺 execution locator，authority schema 拒絕欄位。實作後窄測試 18 passed（其中真 PostgreSQL 整合 2，contract 16）：

- 正式 reply 定位原 execution；App／員工為 null。後續已接受與取消輸入不出現在歷史，也不改舊定位。
- 同名／不同檔案只讀各自歷史；其他檔案拿原 execution 查 status 為 404。
- 使用真正完成 workflow 授予正式資格；將實際 native checkpoint position 交完成交易，關閉並重開官方 PostgreSQL saver，再以 history locator 讀回公開 commentary。
- 重複 snapshot 不重複顯示，清除目前 context window 不刪舊公開訊息；final、reasoning、工具參數、metadata、原生 context／checkpoint 不洩漏。GET 不改正式訪談或授來源資格。
- reader 不可用維持 null；schema／DTO 拒絕錯誤 UUID 與未聲明私有欄位。

受影響回歸再驗：上述兩檔＋`test_job_files.py`、`test_interview_source_queries.py`、`test_consultant_completion.py`、`test_consultant_status.py`、`test_public_commentary.py`，**61 passed / 20.44s**。本切片 Ruff、5 個 production 檔案 scoped mypy、`git diff --check` 與生成器 `--check` 通過。

測試：`apps/api/tests/integration/test_interview_history_turns.py`、`apps/api/tests/contracts/test_job_file_contracts.py`。使用本機隔離測試 schema 與合成 provider response；沒有真模型、付費請求、.env、commit、migration 或正式資料異動。codegen 在 Windows sandbox 的 Python 暫存目錄 ACL 受阻後，已以核准的本機正常權限執行，exit 0。
