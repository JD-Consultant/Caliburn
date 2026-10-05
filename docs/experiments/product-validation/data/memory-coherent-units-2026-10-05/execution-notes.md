# 執行與審查紀錄

## 準備

本批已獲 US$0.10／20 分鐘授權，計入原累計 US$2；先前占用 US$1.270089235。上一批已結案，不沿用其剩餘時間或修改失敗原件。

取捨：先比較同一集合結構下的整理方法，避免把角色數、工具與讀取指引同時改掉。此次是已知反例回歸；跨職類與長上下文驗證不包含在本批結論。

共用接線：只在實驗的送出邊界增加 Structured Outputs，兩組相同；不更動正式產品 ResponseRequest。SDK 的 input token count 已支援 text 欄位，需測實際送出而非只查 schema 常數。

## 離線驗證

- 共用 schema 邊界先跑既有不含 `text` 的請求：3 個測例因缺少 `text` 失敗；實作後 3 個通過（Red→Green）。
- 後補 SDK 傳送整合與凍結、隔離、禁止重跑檢查，非先測試後實作；沿用舊 workspace／episode 18 項回歸。合計 **25 passed**，2.18 秒。MockTransport 只替代 HTTP 外送，實際 SDK、payload 組裝、原生 items 都參與；這不是 provider 支援與分析品質驗證。
- 首次補測有一項把 map 空集合誤寫為 `[]`，按既有契約改為 `{"items":[]}`。sandbox 另阻擋 pytest 暫存目錄；在新隔離暫存目錄、核准權限下完成，沒有清除其他測試資料。不是產品故障。
- 命令：`apps/api/.venv/Scripts/python.exe -m pytest -p no:cacheprovider --basetemp=<新建隔離目錄> -q docs/experiments/product-validation/data/memory-coherent-units-2026-10-05 docs/experiments/product-validation/data/memory-structure-incremental-2026-10-05`。新目錄 Ruff check 通過。

研究文件另經兩位只讀審查，核對離線字數、反事實與資料平台類比的界線，未發現實質問題。付費前仍審查新 runner 的公平性與准入。

## 付費前審查修正

新鮮審查指出「每個輸出目錄只能跑一次」仍容許換目錄再取得同一批額度。已重現拒絕測試失敗，將 paid run 限定為本資料包唯一 `live-01`，保留 exclusive started 標記；同目錄重跑、另一目錄重用均拒絕。修正後 **26 passed**，1.79 秒。研究範圍、工具、prompt、資料及費用不變。

修正發生於首次外送前。原準備目錄改名為 `offline-preparation-01` 保留，未執行、不計成模型樣本；重新 prepare／verify 唯一付費目錄，避免改寫先前 manifest。分析程式為觀察投影，不供模型使用。

## 真模型執行與結案

- `live-01` 僅啟動一次；exec session 21330 exit 0，14 個單元完成，589.865791 秒。正式產品與資料庫沒有啟停或修改。
- 82 次 request、82 次 response；其中 41 次模型生成、41 次計數，沒有 provider 錯誤及 Compaction。每次模型請求恰有一則起始 user 資料，沒有重複加入；兩個 endpoint 的全部 82 次請求均帶相同角色的 strict JSON schema。
- 原方法 extension 先出現 `patch_context_not_found`、再 `invalid_patch`，皆未採用；模型重新讀取後修正成功。候選無工具拒絕。不把這兩次正常拒絕後修正藏掉，也不重跑挑較好結果。
- 本批生成估算 US$0.010915415＋count 預留 US$0.0041＝占用 US$0.015015415；累計 US$1.285104650。所有外送均已有回應，未續跑。
- 使用凍結判準逐項讀正文及 JD，另就一項語句量詞歧義作匿名片段助理複核：維持原判準評為完整，把措辭風險另列。判讀不是真人顧問盲測。
- 結案後 `verify` 通過，`analyze_coherent.py` 重算數據完成。結果與原件保留；不修改 Prompt／資料去追求較好分數，不推送、不合併。
- 最後核對：新、舊兩批凍結雜湊均通過；新腳本 Ruff 通過，相關 tracked diff 無空白錯誤。31 個本地文件連結有效。公開 trace 未檢出 API key 樣式，沒有明文 encrypted_content 字串；原生不透明內容沿既有去敏機制保存表示，不放進報告。
