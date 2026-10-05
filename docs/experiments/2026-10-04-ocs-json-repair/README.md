# OCS PDF → JSON 補齊與來源檢核

- 日期：2026-10-04。
- 範圍：獨立 RAG 的 PDF → JSON 元件；使用者已授權開始轉換，已有資料可補齊。
- 設計責任：[元件設計](../../specs/2026-10-03-public-ocs-pdf-to-json-design.md)；操作及欄位語意：[App README](../../../apps/pdf-to-json/README.md)。
- 本輪結果：815 份通過並寫出新 JSON、53 份拒絕、40 份歷史檔排除；908 份來源全部有結果。原有 `apps/ocs-indexer/data/jd-json` 保留，不啟動 embedding、向量庫或 JD App 接線。

## 輸出與可追溯證據

來源為儲存庫內 908 份 PDF；排除檔名含「歷史資料」的 40 份。其餘文件沒有核對官方最新狀態，成功轉換不代表仍是官方現行版本。

815 份新 JSON 全部由生成模型載入並完成純 normalization，來源 SHA-256 與清單／結果一致；正常目錄檔名恰與 converted 清單相符。原 PDF 與原 908 份 JSON 相對 Git HEAD 沒有變動。新資料共 7,485 個任務代碼、20,656 個指標；含 43 個第六級 block 與 4 份無代碼態度正文。

與原 JSON 比較，778 份有變動、37 份相同；764 份變動涉及 content、327 份 notes、59 份 attitudes、4 份 profile，章節數可重疊。變動包含文字／排版修正，不能推論 778 份原本不完整。差異核對曾找出農務共表漏項及兩份指標前綴空白，已加回歸並重跑整批；最終沒有原有 task code 被移除。

- 新 JSON：`apps/pdf-to-json/data/json-checked-2026-10-04/`。
- 本機完整診斷：相鄰的 `json-checked-2026-10-04.diagnostics/`；每檔有來源雜湊、結果、階段及原因，可產生候選時另存 `rejected/`。
- [來源清單](input-manifest.json)：固定檔名與 SHA-256。
- [整批結果](batch-report.json)：每份來源恰有 converted、rejected 或 excluded。
- [前後差異](comparison.json)：只比較本輪通過文件，以生成模型補齊 optional 預設後再比對。包含正文／排版修正，變動份數不能當成原有缺漏份數。
- [輸出核對](verification.json)：清單與結果對帳、來源雜湊、新 JSON 載入及消費相容核對。
- [待處理文件](remaining.md)：本輪 rejected，按實際原因分組；不放入新正常輸出。

資料目錄是忽略的本機輸出，證據清單隨本紀錄保存。既有 JSON 沒有覆寫；需要接入下一元件時須明示使用新資料目錄。

## 已修正的效果

| 原因／反例 | 修正與驗證 |
|---|---|
| `3D` 被項目符號規則刪成 `D`；珠寶補充跨行被拆成六條 | 保留正文數字，按標記及續行拼接；珠寶四條原註完整保留 |
| 級別 6 或空白被預設為 3 | 共用 schema 上限改為 6 並重新生成；明確空白為 null，非法／歧義值拒絕 |
| 沒有 A-code 的機械設計態度整區消失 | 保留 code=null 的正文；消費者保留態度名稱且不生成代碼 |
| 說明未有子標題時成為任職條件；相關類別錯放 | 按明確條件標題分類，其餘說明與相關類別歸 supplements |
| CLI 抽取後，transformer 重開 PDF | 一次固定 bytes／雜湊並抽取 typed 頁面快照，關閉 PDF 後解讀；刪除原檔後仍可完成 transform 的反例通過 |
| 多層表頭與空白子欄造成欄位錯置；表頭「工作職責」、省略職責、態度標題異體 | 依每表表頭及 cell 位置唯一歸欄；博物館、都更危老、行動遊戲真 PDF 回歸通過；未知位置拒絕 |
| 農務人員 T4.2 與態度共用同一張表，整表被排除 | 用第一列分類整表，內容讀到後續獨立章節標題才停止；T4.2、P4.2.1 及工作日誌保留，刪除 T4.2 的變異會被來源檢核拒絕 |
| RF、資料庫的 `P 5.1.2`／`P 2.3.3` 併入前一指標正文 | 代碼解析單獨處理前綴與數字間的空白；保留兩項及原文，英文詞間空格規則保持 |
| 跨頁前綴與後續新代碼同格，前項正文被截斷 | 接回前一項後解析新項；電控 T2.2 產出與技能全文回歸通過 |
| K／S 字母、數字產出代碼與英文空格被正規化改寫 | 保存原文欄位中的 K／S、`04.2.1` 等來源代碼及有效英文詞間空格；有限反例通過 |
| 空 OCS、漏項或同 task 內 block 錯掛仍可成功 | 檢查非空內容，按來源列核對任務、級別、正文及同一 block 關係；不同級別／同級別 K／S 交換、共享 T-code 拆群均會拒絕 |
| 失敗可覆寫正常檔，批次缺少對帳 | 共用轉換流程、同目錄暫存後原子替換、三種結果與隔離候選；寫入失敗保留舊檔及混合批次測試通過 |

## 驗證範圍

PDF 元件 67 個測試通過，包含既有 23 個測試及新增的真 PDF、缺漏／錯置變異、非法級別、未知表頭、檔案生命週期與 CLI 反例。新增行為先確認失敗，再修正；三份 golden 依來源修正正文、級別、跨頁職責／產出及註文，未以舊快照作真值。所有測試引用的來源 PDF 均為既有 tracked 檔案。

受影響消費者的 schema／normalizer 測試 5 個通過，包含新無代碼態度與第六級反例。此層只測生成模型及純 normalization；沒有重建索引或執行查詢品質評估。正式 codegen 在暫存檔重生 Python／TypeScript 並比對，生成物一致；受影響 PDF Python 檔案 Ruff 通過。

程式審閱曾發現來源檢核只查任務範圍會放過 block 內錯掛，以及共享 T-code 拆成不同 task group；已加反例並修正。最後的獨立審閱確認共享代碼反例被拒絕；對新增的農務／RF／資料庫修正，另以新 Python 程序唯讀核對三份基線及 8 個刪除／截斷變異，均符合預期。不把審閱當成所有 PDF 品質驗收。

原件人工證據沿用[工具比較](../2026-10-03-ocs-pdf-parser-comparison/README.md)：十份、55 頁，人工視檢十三頁及 31 個抽取檢查點。本輪另渲染與視檢[農務人員第 4 頁](source-pages/farm-worker-p4.png)及 [RF 研發工程師第 10 頁](source-pages/rf-engineer-p10.png)，確認共表的 T4.2 與分隔空白的 P5.1.2。其他新增版型以固定原 PDF 抽取內容回歸，未全部另做逐頁視檢。這些樣本用於診斷／修正，沒有宣稱是獨立隨機保留樣本。

## 重跑

以下命令從儲存庫根目錄執行；本次 Python 3.13.12、pdfplumber 0.11.9。

```powershell
& apps/pdf-to-json/.venv/Scripts/python.exe -m pytest apps/pdf-to-json/tests -q --no-cov --basetemp S:/caliburn/tmp/pdf-json-verification
& apps/pdf-to-json/.venv/Scripts/python.exe -m jd_pdf_to_json.cli batch apps/pdf-to-json/data/pdfs --output <新的輸出目錄> --exclude-historical
& apps/pdf-to-json/.venv/Scripts/python.exe apps/pdf-to-json/scripts/compare_json.py --old-dir apps/ocs-indexer/data/jd-json --new-dir <新的輸出目錄> --report <診斷目錄>/comparison.json
& apps/ocs-indexer/.venv/Scripts/python.exe -m pytest -q -p no:cacheprovider apps/ocs-indexer/tests/test_schema.py apps/ocs-indexer/tests/test_normalizer_task_pairs.py apps/ocs-indexer/tests/test_normalizer_category_pairs.py apps/ocs-indexer/tests/test_uncoded_attitude.py
& apps/ocs-indexer/.venv/Scripts/python.exe docs/experiments/2026-10-04-ocs-json-repair/verify_outputs.py
```

本次 Windows 沙箱的 pytest 暫存目錄有 ACL 限制，隔離測試採工具批准的外層執行；暫存目錄始終位於 `S:/caliburn/tmp/`。批次有 rejected 時 exit 1 是如實回報，不代表其他通過文件沒有寫出。

## 尚未驗證與下一步

自動來源檢核仍建立在 pdfplumber 的抽取結果上，無法獨立證明抽取漏字；profile／版本由原 section owner 重讀快照核對組裝，也不能獨立證明該 owner 已判讀所有欄位。來源官方最新身分、全部逐頁逐字內容、掃描／無框線文件及所有英文斷行均未驗收。

剩餘 rejected 須依原因處理；歧義級別先保留原件，不擅自降級或拆級別。來源維護與向量檢索屬後續元件，本輪不以強行產生 JSON 消除待處理清單。

本輪 53 份拒絕原因分為：儲存格位置 14 份、來源內容／關係 22 份、延續列 3 份、級別文字 6 份、重疊子表 8 份。這是本輪阻擋原因分類，不是對每份來源已完成的根因分析或品質評分；完整檔名與位置見待處理清單。
