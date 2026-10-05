# 快速驗證記錄

## 執行範圍

沿用現有實驗機制，只新增配對資料與兩段候選指引。正式 B1／B2／A、資料庫及服務均未修改。工作分支為 `jd-app-docker`，工作區另有 OCS／PDF／檢索等修改，本輪不收編、不提交。

本輪使用 verification-before-completion 的證據原則，提示修改核對 OpenAI Docs 的 GPT-6 指引；紀錄依 better-documents 先呈現結論及驗證範圍。既有對話已確認設計，本次不另重開架構或增加元件。程式與資料在實驗目錄隔離，沒有為小型研究另建產品 worktree。

## 執行前驗證

- 四項配對／時間範圍／來源角色／窄題測試先因案例未實作而失敗，實作後四項通過。
- 三項新編排的整合檢查為事後驗證，不稱 TDD：輸入被改時拒絕執行、非授權目錄拒絕執行、已開始批次不可重跑。共七項通過。
- 初次 `uv run` 無法使用使用者 cache；改用專案既有 `apps/api/.venv/Scripts/python.exe`。pytest 沙箱暫存權限錯誤不算品質反例；以獨立 `.tmp/pytest-memory-local-preservation-check` 提升執行後通過，未重裝套件。
- Ruff format／check 通過。`prepare`、`verify` 不連網。付費執行前確認新舊組工具與前批 frozen tools 完全相同，並凍結本批來源、提示、起始快照與題目。

命令：

```powershell
apps/api/.venv/Scripts/python.exe -m pytest docs/experiments/product-validation/data/memory-local-preservation-2026-10-05 -q -p no:cacheprovider --basetemp .tmp/pytest-memory-local-preservation-check
apps/api/.venv/Scripts/python.exe -m ruff check docs/experiments/product-validation/data/memory-local-preservation-2026-10-05
apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/data/memory-local-preservation-2026-10-05/study.py prepare
apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/data/memory-local-preservation-2026-10-05/study.py verify
```

## Context 離線投影

前批四題分層讀取共八次請求，完整原話四次。相同讀取指引下，分層 tools JSON 合計 35,936 字元、導覽 7,152、指引 6,840、完成格式 6,728、工具輸出 2,019；原話組原文 JSON 為 5,798 字元、指引 3,420、完成格式 3,364。這些含每次請求重送，分層 tools 單次約 4,492 字元。加密推理未解讀，沒有按其長度估 token。

API 實報 input 仍為 20,922／6,591。投影說明本例的工具契約與多一次往返有明顯文字負擔，不代表各欄位 token 可直接相加或工具佔比等於字元佔比。下一步可研究工具描述／schema 的無損精簡，但本批不改 schema，避免將品質修訂與成本改動混成同一變因。

重算（唯讀）：

```powershell
apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/data/memory-local-preservation-2026-10-05/analyze.py docs/experiments/product-validation/data/memory-layered-value-2026-10-05/live-01 --readers-only
apps/api/.venv/Scripts/python.exe docs/experiments/product-validation/data/memory-local-preservation-2026-10-05/analyze.py docs/experiments/product-validation/data/memory-local-preservation-2026-10-05/live-01
```

## 結案核對

十次真模型執行全部完成，程序 exit 0，未追加補跑。品質與用量見 [results.md](results.md)，逐項來源判讀見 [semantic-review.md](semantic-review.md)。獨立 B2 覆核與主執行者核對一致：候選修掉網站跨案舊期限，倉庫兩組皆符合；A 六次內容均符合，未觀察到候選額外品質提升。

`analyze.py` 重算為 27 次模型請求、27 次計數、37 次工具呼叫及零工具錯誤；10 個新片段與 17 次原生接續。付費階段 392.954 秒，本批估算占用 US$0.011193835，累計 US$1.322929315。27 筆 pending 均為每次 US$0.0001 的計數保守占用，沒有未結算的生成請求。沒有觸發 compaction。

本次仍是隔離子任務驗證：未測真 PostgreSQL 保存／發布、未改正式提示或程式、未啟停服務、未 commit／push／merge。原 trace、manifest、判準及輸入保持原樣。執行後七項離線測試通過（1.54 秒）；結案再驗七項通過（1.40 秒，專用暫存 `.tmp/pytest-memory-local-preservation-closeout`）。Ruff check／format check、凍結檔案 verify、兩份索引差異檢查及三份結果文件的 26 個本機連結檢查通過。

## 後續採用（2026-10-05）

使用者同意繼續優化後，只將本批 B2 候選新增的兩句跨案數值規則加入正式 `work_understanding_analyst/instructions.py`。沒有整份搬入實驗的 B2 基線；A 候選沒有顯示額外品質收益，因此未採用。B1、工具、資料庫、Context 組裝與恢復流程均未變動。

本次是已有真模型反例與配對結果後的提示採用，不稱為新增 Red–Green 測試，也不以檢查提示字串冒充效果驗收。重新執行角色請求組裝、工具權限及完成契約測試，25 項通過（1.43 秒）；Ruff check、format check 及程式 diff 空白檢查通過。

```powershell
apps/api/.venv/Scripts/python.exe -X utf8 -m pytest apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_memory_analysis_tools.py apps/api/tests/unit/test_memory_analysis_outcomes.py -q -p no:cacheprovider
apps/api/.venv/Scripts/python.exe -X utf8 -m ruff check apps/api/src/caliburn/agents/work_understanding_analyst/instructions.py
apps/api/.venv/Scripts/python.exe -X utf8 -m ruff format --check apps/api/src/caliburn/agents/work_understanding_analyst/instructions.py
```

另由[閱讀策略原件](../memory-reading-policy-2026-10-04/live-01/result.json)重算八格 usage／reads，與既有 metrics 逐格一致；trace 及 result SHA256 與原報告相符。兩組共同完成三對的 input 199,594／87,353、讀取 23／3，可支持充分性停止規則；不能歸因為本次 B2 兩句修改的效果。研究依據、數據定義與適用範圍集中於[研究 §10](../../../../research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md#10-研究收斂與可重算證據)。

沒有新增付費請求、重新執行本批、啟停服務或 commit／push／merge。累計估算占用仍為 US$1.322929315／US$2。正式提示組合及完整 B1 → B2 → A 尚未因這次採用新增真模型驗證結論；現存資料也不會因提示修改自動重整。

收尾時同組 25 項測試再次通過（1.44 秒），Ruff 檢查通過；四份更新文件的 146 個本機檔案連結有效。獨立唯讀覆核確認新增兩句與凍結候選相同，必要條件與未知保留規則沒有衝突；共同三對的數值重算一致，未發現重大問題。依覆核建議在原閱讀策略結果頁補明 33／33 的子集分母及比較範圍，沒有更動判準或原始結果。
