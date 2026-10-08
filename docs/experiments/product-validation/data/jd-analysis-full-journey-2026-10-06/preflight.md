# 執行前核對

- 分支 `consultant-jd-analysis`，沿用未提交的已核准 A Prompt；其他工作中的規劃研究／候選議程沒有納入執行。
- 凍結 369 檔；A 指引 SHA-256 為 `69d3ba309d0a559104a102b0b40f3924941ccaba47fa3c589e9ae8cd0202d734`。新容器 `caliburn-jd-analysis-full-20261006` 已從凍結包載入後端並遷移獨立 schema，health 正常；未動舊容器。
- 真 RAG 預檢 2.19 秒，三份來源可固定回讀，非法定位拒絕。結果為 `rag-fresh-query.json`；不是固定 HTTP fixture。
- 既有護欄 14 項測試通過（0.43 秒）。先前兩次受 Windows 沙箱暫存權限阻擋：第一次 6 通過／8 fixture errors；第二次使用新基底仍遭 PermissionError。改以已核准的沙箱外專用暫存目錄驗證，沒有修改測試或產品。
- 薄接線初次 Ruff 檢查出 12 項格式／規範問題（import 排序、此設定未啟用 E402 的多餘 noqa、subprocess 缺明示 check）。它們不改模型行為；本批先保持已凍結執行原件，收尾時清理接線並另記差異，不能宣稱初版 lint 全過。
- 已建立新空白職務檔案 `b544f6c1-ea66-4726-b1d1-38ed2e1c7f7f`，建立步驟未呼叫 OpenAI；尚未有付費 trace。

以上是首次外送前的準備紀錄。開始執行後發現凍結程式未含套件的 JSON schema／HTML 資源，第一個 Turn 在任何 OpenAI 請求前失敗；原件保留於 `turn-01-*`。直接構造模型工具可重現缺少 `memory-map-arguments.schema.json` 的 FileNotFoundError。補凍 39 個同版本資源後，15 個基本模型工具可正常構造，才開始付費訪談；詳見 `resource-repair.json`。

原始 369 檔及補充 39 檔的雜湊均由 `audit.py` 核對，沒有改寫既有 ZIP、manifest、trace 或失敗輸入。收尾清理接線時，`prepare.py` 改為包含非快取的所有套件資源，避免未來再漏；`guarded_app.py` 在存在補凍包時載入它，並使用既有護欄接續機制。另移除多餘 noqa、整理 import、明示 subprocess 的 check。這些接線差異不改本批凍結的產品或 Prompt，初版接線仍在原 ZIP。

2026-10-06 第二次費用停止點後，實驗腳本 Ruff check 通過。此為薄接線及分析程式的配置檢查，不是假稱產品新行為已完成 TDD。接續前的 `/health` 探針曾使用錯誤路徑；正式契約是 `/api/health`，訪談及 JD API 當時均正常。這個探針問題不列為產品缺陷。
