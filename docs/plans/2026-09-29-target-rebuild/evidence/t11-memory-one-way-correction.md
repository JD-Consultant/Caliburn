# T11：Memory 單向流程修正

- 日期：2026-10-02。
- 修正前基準：`a02d2181`；分支：`target-rebuild`。
- 範圍：B1 → B2 → 發布的提示、角色結果、批次編排、候選交接及相關文件。這是落實已確認設計，不是新增分析流程。
- 驗證層級：離線反例、真 PostgreSQL 與模擬 Responses 回應；沒有呼叫付費模型、重啟服務或遷移正式資料。

## 1. 如何發現問題

整理教授版架構報告時，比對單向設計與實際背景執行入口，發現文件與程式不一致。啟動流程確實建立 `MemoryBatchWorkflow`，因此不是未使用的舊程式。

在上述基準可查到四個相連的原因：

1. B2 指引要求遇到情境問題時輸出 `needs_situation`。
2. 結果解析器接受 `SituationRework` 與 `SituationGap`。
3. 批次編排預設 `max_feedback_rounds=2`，可將 B2 的結果送回 B1。
4. 候選交接可在情境與理解兩階段間雙向切換。

只改指引或將回交上限設成零，都會留下互相矛盾的介面；因此沿這四層移除舊路徑。原始查核見[報告附錄](../../../reports/system-architecture/references.md#本次文件校核範圍)，可用 `git show a02d2181:<路徑>` 檢查修正前程式。

## 2. 依據與處理方式

產品流程以[背景整理規格的有效狀態](../../../specs/2026-09-25-b1-b2-information-gap-lifecycle.md)為準。提示修訂參考 [OpenAI Prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering)：明確說明角色、限制與輸出格式。此來源支持提示的寫法，並不表示 OpenAI 規定 Memory 必須採單向流程。單向流程是 Caliburn 已確認的產品取捨。內容處理另核對[工作理解深度](../../../guides/2026-09-09-complete-work-analysis-guide.md#9-工作理解正文要寫到多清楚2026-09-25-研究補核對)、[訪談校準](../../../guides/2026-09-09-customized-jd-depth-and-interview-calibration.md)及[JD 資訊取捨](../../../guides/2026-09-09-jd-field-and-writing-guide.md#6-什麼留在分析什麼進-jd什麼留待下游)，保留未知與責任邊界，不將 Memory 改成 JD 草稿。

採用既有角色、執行與交易機制，沒有新增佇列、審查 Agent、通用協調層或保存系統：

| 部分 | 修正 |
|---|---|
| 角色指引與結果 | B1／B2 只以 `{"status":"complete"}` 表示本階段完成；B2 按需讀取允許的原話、保留未知，只維護工作理解，不回交或修改情境。 |
| 批次編排 | 移除回交次數、gap 傳遞及前次回交結果的分支。B1 完成後保存交接位置並提供情境差異；B2 完成後發布。 |
| 候選交接 | 只允許從工作情境交給工作理解；理解階段不能用交接操作返回情境。原交接的重送仍辨認同一結果。 |
| 歷史與恢復 | 保留同階段模型／工具接續、原回應保存失敗的恢復及跨批次角色歷史；不重送已保存的模型結果，不交換 B1／B2 私有歷史。 |
| 壓縮 | 移除只為回交而存在的壓縮分支；輪前 128K 與完整 Step 交界 160K 的共用機制不變。 |
| 發布 | Memory 快照、批次完成與兩角色歷史採納仍在同一個短交易內完成。A 仍只讀已發布快照。 |

未知資訊不必偽裝成完整事實；能忠實整理已知內容時，可以保留未知後完成。真正的執行失敗仍由原失敗處理收尾，不以 `complete` 掩蓋。

### 舊執行紀錄如何處理

若舊版未發布批次已保存 `needs_situation`，新流程不能直接把它當作正常 B1 工作重跑。派送模型前先驗證既有階段結果，辨認不相容紀錄後交給既有失敗處理，保留正式訪談及已發布 Memory，不新增遷移格式或無限重試。

已發布批次優先返回原快照，歷史結果不被這項檢查改寫。能按單向流程接續的 B1／B2 同階段進度仍正常恢復。最終失敗後何時另起新批次，沿既有政策，本次沒有修改。

## 3. 反例與驗證

### 先確認測試能找到原問題

第一組先新增兩個反例，再改程式：

- `test_rework_final_is_not_a_valid_analysis_completion`：舊 `needs_situation` 不得被接受為 B2 完成結果。
- `test_understanding_stage_cannot_handoff_back_to_situations`：B2 不得交回 B1。

窄測結果為 **2 failed、1 passed、19 deselected**。兩項失敗都是原程式沒有拒絕回交，而非環境錯誤；修正後通過。

接著測試舊版已保存回交紀錄的恢復。刪除回交分支但尚未加上相容檢查時，`test_legacy_recorded_rework_fails_before_any_new_model_work` 失敗：程式仍嘗試執行 B1。補上派送前檢查後，確認不呼叫模型，並由原失敗處理將未發布批次安全結束。

### 回歸範圍

| 測試 | 檢查效果 |
|---|---|
| 角色 prompt、結果解析 | 提示範例能按同一契約解析；舊回交、錯誤格式及非完成輸出不能假裝成功。 |
| 角色與工具整合 | B1 不讀理解、B2 不改情境；訪談上界固定；兩角色使用各自歷史；模型原生 reasoning、`phase`、工具配對與額外欄位保留。 |
| 模型／工具 Step 恢復 | 已保存結果重入不重送；原回應保存故障可接回原結果；159,999／160,000 token 的完整 Step 壓縮邊界仍成立。 |
| 候選與發布 | 同階段恢復、不相容舊回交安全失敗、B1 已完成不重跑、B2 保留未知後發布、提交確認遺失仍返回原快照、歷史快照不被新批次刪改。 |

舊版「B1→B2→B1→B2」整合測試改成單向發布；刪除情境的測試改在新批次執行，同階段安全點恢復另留反例。移除的是已退役的回交流程斷言，不是權限、資料或恢復保證。

### 執行結果

使用 Python 3.14.7、現有鎖定依賴及本機真 PostgreSQL。資料庫測試各自建立、清除隨機 `t02_<uuid>` schema；未讀寫 Demo 職務資料。以下 Responses 回應均為合成測試資料，不是遠端模型結果。

| 檢查 | 結果 |
|---|---|
| Memory 專項最終回歸 | **59 passed，22.98 秒**；涵蓋本次修改的 7 份測試檔。 |
| 首次完整後端套件 | **1,956 passed、4 failed、21 errors、2 skipped，580.09 秒**。4 項跨程序測試因從 repo 根執行，子程序找不到 `tests.fixtures`；21 項使用 `tmp_path` 的測試被 Windows 暫存 ACL 阻擋。 |
| 環境修正後重跑 | 對上述失敗涉及的 6 份測試檔重跑，**34 passed，22.76 秒**。已涵蓋全部 4 項失敗及 21 項 setup error，也包含同檔其他測例。未修改測試斷言或產品程式來消除這些環境錯誤。 |
| 靜態檢查 | Ruff 通過；433 檔符合格式；mypy 檢查 280 份來源檔，無錯誤。 |
| 文件檢查 | 23 份變更 Markdown 的本機連結／章節定位檢查通過；`git diff --check` 通過。圖檔未變，不重跑渲染。 |
| 獨立程式審查 | 靜態審查未發現 P1／P2；核對同階段恢復、舊回交處置、角色隔離及同交易發布。審查者未另行呼叫模型或跑測試。 |

**不是一次全套綠燈：**首次完整套件的環境失敗保留如上；修正執行環境後只重跑受影響的測試檔，沒有再跑第二次完整套件。原有 2 項 PDF 渲染測例因缺少指定字型環境設定而跳過，這次未驗證該部分。

重跑過程也曾在 repo 下另建隔離暫存目錄，但沙箱仍無法存取 pytest 建立的目錄；後來以核准的沙箱外執行重跑，使用全新隔離目錄才通過。沒有調整既有資料夾 ACL、刪除使用者暫存資料或繞過產品保護。

可重現命令如下。`CALIBURN_TEST_DATABASE_URL` 須指向允許建立測試 schema 的本機測試庫，不使用正式資料庫；本次沿既有測試庫 `127.0.0.1:55439/caliburn_t01_test`。

```powershell
# repo 根目錄：首次完整套件，結果與環境限制見上表。
& apps/api/.venv/Scripts/python.exe -X utf8 -m pytest apps/api/tests -q -p no:cacheprovider

# apps/api 目錄：Memory 最終專項回歸。
& .venv/Scripts/python.exe -X utf8 -m pytest `
  tests/unit/test_memory_analysis_outcomes.py `
  tests/unit/test_memory_analysis_tools.py `
  tests/unit/test_role_prompt_contracts.py `
  tests/integration/test_memory_candidates.py `
  tests/integration/test_memory_batch_orchestration.py `
  tests/integration/test_memory_outcome_failure.py `
  tests/integration/test_memory_analysis_runners.py -q -p no:cacheprovider

# apps/api 目錄：先確認 $testTempRoot 是本次專用的新暫存目錄。
# pytest 會清理 basetemp，不能使用既有資料目錄。
& .venv/Scripts/python.exe -X utf8 -m pytest `
  tests/integration/test_consultant_process_recovery.py `
  tests/unit/test_openai_credentials.py `
  tests/unit/test_packaged_migrations.py `
  tests/unit/test_simulation_resume.py `
  tests/unit/test_status.py `
  tests/unit/test_web_delivery.py -q -p no:cacheprovider --basetemp=$testTempRoot
```

憑證相關測試只使用臨時合成檔，不讀取產品 `.env`。這份紀錄保留命令、判定與可重現測例，沒有保存整份失敗終端輸出或任何模型私有內容。

## 4. 文件與驗證界線

同步工程執行／保存文件、系統責任與驗證表、產品介紹及教授版第五章。圖六原本就是單向流程，圖檔不需重畫；更新圖說及證據入口即可。過去的回交試驗和長旅程保留為歷史，不改成新流程已驗的證據。

本次沒有真模型長旅程或分析品質重驗，不改 Luna 選型、既有來源漏引限制及 Memory 失敗後重新整理政策。沒有啟停 Demo；執行中的舊程序須在正常重啟後才會載入新程式。
