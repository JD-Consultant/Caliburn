# 公版工具契約：修正與驗證

2026-10-05。使用者授權「優化審核 debug」，本輪完成原[契約審核](tool-contract-audit.md)三項修正，並處理獨立審查找出的重複工具宣告問題。只改公版 consumer 工具邊界、對應生成契約、可選角色指引及相關測試／文件；既有 RAG 搜尋回傳保持完整目錄。

## 實際效果

| 問題 | 修正與證據 |
|---|---|
| 選用參數容易被理解成追加 | description／schema 明說全集合替換，要保留的舊 ID 一起填。Domain 行為不變。 |
| query 錯誤卻提示 add/remove | 五項工具分別回合法填法，維持既有拒絕 envelope；外部錯誤區分連線、索引、來源及無效結果。 |
| 每次寫入重送完整 state | 新寫入固定回 `{"status":"updated"}`（20 字元）；完整 state 按需讀。Domain 操作結果仍保存完整 state，不在寫入後誤報未改。 |
| 原請求恢復可能套新格式 | handler 由原 captured request 的固定輸出契約後綴決定格式；舊輪次仍回完整 state。原 native output 不回寫，command shape／ID／scope 不變。 |
| 完整組追加重複唯讀工具仍可建立候選 | 原 set 判斷遺失重複，現改完整名稱集合及數量一併核對。五種工具重複均在 factory／candidate start 前拒絕。 |

相同合成排除文字的離線重播中，舊寫入為 **244 字元**，新寫入為 **20 字元**；兩者保存的排除範圍完整，讀取在相同 64 字元小上限下均明確拒絕。這是 handler 資料量反例，不是 production 超量事故或 token／耗時收益。[輸入、回傳及來源 SHA256](hardening-probes.json)與[重算程式](verify_tool_hardening.py)另存，不覆寫前輪基線。

## Red → Green 與獨立審查

1. 第一組回歸先執行：**9 failed／2 passed**，對應選用文字、跨工具錯誤提示、服務錯誤提示與完整寫入回傳；[原始 Red](hardening-red.txt)保留。
2. 補原請求相容性時，重複寫工具與格式混用檢查順序有 **2 failed／39 passed**；修正後三個工具相關檔為 **84 passed**。混用格式先驗再建立候選，缺漏／重複不能以舊模式降級。
3. 獨立 reviewer 唯讀重現追加重複 `read_occupation_reference_state`：candidate start 仍執行一次，列為 P2。五種重複宣告回歸先得到 **3 failed／2 passed**（三項讀取未攔）；修正後 **5 passed**，全部 factory／start 零次。reviewer 再以五種獨立 mock probe 覆核，關閉 P2，最終無剩餘 P0／P1／P2。
4. reviewer 另核對原 request 格式綁定、未改 command／native output、成功後序列化錯誤不誤包成未改，以及 generated DTO／錯誤指引。沒有改檔、操作服務或外送；PG／build 由主線驗證。

## 本輪驗證

| 層級 | 結果與範圍 |
|---|---|
| 工具／契約離線 | **567 passed in 7.88s**：公版 transport、feedback、registry、Prompt 契約、排除讀取、client／Domain／設定及所有 contract tests。[原始結果](hardening-unit-contracts.txt)。 |
| 真 PostgreSQL | **55 passed in 53.29s**：工具旅程、兩種結果格式、角色 runner、native template 接續、workflow／state／排除讀取。模型及 RAG provider 使用合成 MockTransport，並非真模型驗收。 |
| native 重入補驗 | 在上列驗證後補查「中斷前已存 selection output 不重新投影」，再跑角色 runner：**8 passed in 12.33s**，[原始結果](hardening-reentry.txt)。這是重驗其中八項，不與 55 相加冒充更多獨立案例。 |
| 靜態 | Mypy **319 source files** 無錯；受影響 Python 檔及離線 probe 的 Ruff check／format 通過。 |
| 契約／建置 | 三份 schema 由正式 generator 產生 Python／TypeScript／包裝 schema；根目錄 `pnpm build` 的全量 codegen drift、TypeScript／Vite build 通過。既有 JS chunk 大小提示未阻斷建置。 |
| 文件 | 接續維護架構入口、系統邊界與資料流、保存／部署／執行說明、工具規格及報告入口。11 份受影響架構文件的 272 個本機連結與錨點通過檢查；固定輸出格式標記保留，[檢查原件](architecture-maintenance-check.json)記錄各文件 SHA256。原審核與實驗原件留存。 |

工具與契約命令（根目錄）：

```powershell
apps/api/.venv/Scripts/python.exe -m pytest -p no:cacheprovider apps/api/tests/unit/test_occupation_reference_tool_feedback.py apps/api/tests/unit/test_occupation_reference_tools.py apps/api/tests/unit/test_reference_tool_registration.py apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_excluded_work_reads.py apps/api/tests/unit/test_occupation_reference_client.py apps/api/tests/unit/test_occupation_reference_state.py apps/api/tests/unit/test_occupation_reference_configuration.py apps/api/tests/contracts -q --tb=short
apps/api/.venv/Scripts/python.exe docs/experiments/engineering/2026-10-05-occupation-reference-tools/run_tests.py apps/api/tests/integration/test_occupation_reference_tool_journey.py apps/api/tests/integration/test_occupation_reference_runners.py apps/api/tests/integration/test_reference_template_reentry.py apps/api/tests/integration/test_occupation_reference_workflow.py apps/api/tests/integration/test_occupation_reference_state.py apps/api/tests/integration/test_excluded_work_reads.py -q --tb=short
apps/api/.venv/Scripts/python.exe docs/experiments/engineering/2026-10-05-occupation-reference-tools/run_tests.py apps/api/tests/integration/test_occupation_reference_runners.py -q --tb=short
pnpm build
```

靜態及重算命令（`apps/api`）：

```powershell
.venv/Scripts/python.exe -m mypy src/caliburn
.venv/Scripts/python.exe ../../docs/experiments/engineering/2026-10-05-occupation-reference-tools/verify_tool_hardening.py
```

Windows sandbox 的 Python 暫存目錄 ACL 與 Docker named pipe 造成初次生成／PG 命令環境失敗；沒有用此失敗當產品反例。經自動核准後以同一有界生成器、隔離資料庫 runner 及本地 build 完成。測試 runner 核對既有 `caliburn-jd-docker-test-postgres-1` 的 loopback 55441，使用獨立 `caliburn_docker_test` 與隨機 schema，不輸出憑證、不清 volume。

## 範圍界線

未重啟共用服務、改環境檔、套正式資料庫 migration、commit／push、呼叫付費模型或現行 GPU／RAG。正在執行的輪次仍使用原 template／輸出格式，新程式需依正常服務切換才對新請求生效。

本輪驗證工程契約、保存與恢復。顧問選公版、否認判讀、不重問、JD 收尾品質及實際 token／耗時仍沿原模型實驗範圍；三層候選概覽搜尋是另案比較，本輪未實作。
