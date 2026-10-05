# Memory 排除範圍唯讀工具：接續驗證

日期：2026-10-05。接續[否認範圍保存](excluded-work-verification.md)，不覆寫既有驗證或原始實驗。使用者授權完成工具、先不接模型，並要求整理資料供專題報告使用。責任見[唯讀契約](../../../specs/2026-10-04-public-reference-completion-design.md#memory-的排除範圍唯讀入口未接模型)。

## 本次效果

新增 `ExcludedWorkReadWorkflow(sessions)` 與 `ExcludedWorkReadTools(workflow, binding)`。唯一工具 `read_excluded_work({})` 只回 `excluded_work`；無模型提供的 ID／版本／上界，沒有寫入或 RAG HTTP 依賴。兩份正式 schema 由既有 generator 產生 Python／TypeScript／schema 副本。

`resolve_interview_scope` 從既有 Memory workflow 的私有 helper 提升為共用函式，沿用 ACTIVE execution、Candidate stage／generation 與持久 F，沒有重算新上界。正式公版 state 查詢抽出共用，以 completed＋formal exchange 的員工序號 ≤ F 取最新 state；原顧問 start 在 file lock 內取得當前 frontier 後也沿此查詢。未新增資料表、Memory 副本、validator 或發布機制。

## 反例與測試

| 範圍 | 反例／結果 |
|---|---|
| 讀取契約 | 24 項新 unit 先 Red 再 Green；空參數、未知工具、禁止 scope／ID、只有排除清單、完整輸出容量及錯誤映射 |
| 固定 F | 新 10 項真 PostgreSQL 先因缺 read 實作失敗，完成後通過；觸發員工序號是 F、顧問回覆 > F 時仍讀到觸發 Turn |
| 時序與資格 | 後輪新增／解除不回流舊 F；B1→B2、恢復後保留固定 F，舊 generation／stage、非 ACTIVE execution 拒絕；取消／未完成／無正式 exchange 不生效；職務資料隔離 |
| 真工具接縫 | 第 11 項 PostgreSQL 測試經 transport JSON → workflow → 真 DB，B1／B2 重建讀取及參數越權拒絕；Memory 未複製排除清單 |
| 獨立審查修正 | 保存層 `ReferenceStateError` 原本未映射。新增反例先失敗，再回 `source_not_available`；單檔最終 25 passed。非預期 RuntimeError 仍向上傳遞，未吞基礎設施故障 |

獨立審查另復驗 24 項 unit 及 11 項 PostgreSQL，固定 F／正式資格／未註冊邊界未發現其他實質問題。其後上列錯誤映射修正納入完整回歸。

## 最終命令與結果

```powershell
apps/api/.venv/Scripts/python.exe -m pytest apps/api/tests/unit apps/api/tests/contracts -q -p no:cacheprovider --tb=short
apps/api/.venv/Scripts/python.exe docs/experiments/engineering/2026-10-05-occupation-reference-tools/run_tests.py apps/api/tests/integration/test_excluded_work_reads.py apps/api/tests/integration/test_occupation_reference_state.py apps/api/tests/integration/test_occupation_reference_workflow.py apps/api/tests/integration/test_occupation_reference_tool_journey.py apps/api/tests/integration/test_memory_read_workflow.py apps/api/tests/integration/test_database_migrations.py apps/api/tests/integration/test_consultant_completion.py -m postgres -q --tb=short
apps/api/.venv/Scripts/python.exe -m ruff check apps/api
apps/api/.venv/Scripts/python.exe -m ruff format --check apps/api
apps/api/.venv/Scripts/python.exe -m mypy --config-file apps/api/pyproject.toml apps/api/src/caliburn
pnpm build
```

- **1,313 unit/contracts passed，14.74 秒**。
- **55 PostgreSQL passed，37.91 秒**：新唯讀 11、既有公版 state 9／workflow 10／旅程 1、Memory 讀取 7、migration 5、顧問 completion 12。
- Ruff 通過；474 份檔案格式核對通過；Mypy 317 份 source 通過。
- 全量 codegen drift、TypeScript、Vite build 通過；保留既有 bundle 大小提示。

沿既有安全 runner 私下設定 local test DB，憑證不輸出；每項 fixture 僅建立／移除自己的隨機 schema。正式資料庫未套用 migration。測試使用核准的本機權限處理 Windows 暫存／Docker pipe 存取，沒有外送或模型呼叫。

## 報告與界線

[專題報告 §6.3／B.14](../../../reports/project-report/report.md#b14-主要職位參考的廣蒐與精搜)依既存原始 JSON 整理輸入、廣蒐、精搜、候選縮減、否認反例與 API 重現。廣蒐 12／12 已知配對與最後 9／12 分開，原評分及排除疑義後的敏感度分開；目前控制是 D20／T20 完整聯集後 rerank、最多五份，並非通用最佳或稠密加稀疏。較省配置尚未以新案例及完整耗時驗證。

既有 `verify_evidence.py` 通過；新增 `verify_retrieval_evidence.py` 核對 B-28–B-30 共 15 列、4.48 倍／31.6% 算術、7,038 全部配置與 3,325 限定配置的分母，17 個本地來源連結存在。獨立核對的五個記憶體文字變異（配對量、評分欄對調、cosine、移除限定範圍及斷鏈）均被拒絕，未修改原稿或原資料。保存[核對結果與報告／程式雜湊](retrieval-report-check.json)，不將轉錄驗證稱為語意真值驗證。

工具仍未註冊 A／B1／B2、未改 runner／Prompt／bootstrap，也沒有新增 App HTTP 入口。接線時仍須將 reference position 放入既有 runner 的候選恢復範圍，再測真模型是否正確讀取、選公版、更新否認及產生正向 query。避免重問、未知工作發現、JD／PDF 收尾品質與成本效益均未由本次機制測試證明。
