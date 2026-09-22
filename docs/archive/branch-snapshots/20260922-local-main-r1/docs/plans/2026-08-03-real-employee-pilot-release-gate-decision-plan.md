# 真實員工試用發布門檻決策紀錄計畫

- 日期：2026-08-03
- 狀態：Completed
- 範圍：固定 release gate 與路線圖語意；不招募員工、不執行試用、不自行設定樣本數或數值門檻

## 工作與驗證

1. 以職務分析、使用者研究與 AI TEVV 第一方資料，區分工程 eval、真人試用與 release decision。
2. 以 ADR 0056 固定 R8 release candidate／R9 mandatory real employee pilot 的邊界及不可替代證據。
3. 同步產品範圍、架構 orientation、roadmap、production cutover plan、living design、領域語言與文檔索引。
4. 驗證本機 Markdown links、`git diff --check` 與 docs-only status guard。

## 後續決策

Pilot 開始前另開執行計畫，由 owner 決定首發涵蓋範圍、參與者與情境 coverage、樣本數、rubric 數值、blocker severity、
資料處理、獨立內容審閱者及最終 release authority。本 plan 不授權以方便取得的測試者代替實際在職員工。

## 執行結果

- 研究紀錄、ADR 0056、roadmap、產品／架構邊界、production cutover plan 與 glossary 已同步。
- 本機連結檢查回報 `LOCAL_MARKDOWN_LINKS_OK`；`git diff --check` 與 docs-only status guard 通過。
- 沒有新增 route、schema、migration 或 runtime 變更，也沒有執行真實員工試用。
