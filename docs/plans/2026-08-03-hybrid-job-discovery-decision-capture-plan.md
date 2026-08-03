# 混合式職務發現決策紀錄計畫

- 日期：2026-08-03
- 狀態：Completed
- 範圍：只沉澱研究、領域語言、ADR 與現行文檔指路；不實作 R1 runtime、schema、API 或 Web

## 工作切片

1. 以 iCAP、O*NET、OPM 第一方資料比較純上而下、純故事式與混合式路線，記錄來源與推論邊界。
2. 建立根 `CONTEXT-MAP.md` 與 JD 著作 `CONTEXT.md`，固定 Duty／Task／Output／Indicator／KSA、工作故事與暫定職務框架語言。
3. 以 ADR 0042 記錄 owner 確認的混合式職務發現、T–T–O–P 形成順序與禁止事項。
4. 同步 ADR／docs 索引、architecture orientation、R1 研究狀態與 professional consultant living design。
5. 驗證 Markdown 本機連結、`git diff --check`、正式 router 零 runtime diff。

## 執行結果

- 研究紀錄、context map、JD 著作 glossary 與 ADR 0042 已建立。
- 現行 orientation／design／索引已指向 ADR 0042；既有 Accepted ADR 未修改。
- 本 task 只有 Markdown 變更，沒有新增 route、schema、migration 或 runtime import。
- 本機連結檢查回報 `LOCAL_MARKDOWN_LINKS_OK`；`git diff --check` 與 docs-only status guard 通過。
