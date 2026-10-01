# 最早期專案原文

這裡保存本次沿革整理找到、原先只在 Git 歷史中容易取得的三份原文。它們是**當時的設計與自述紀錄**，不是現行規格，也不是本次重新執行的測試結果。舊文中的模型、相依套件、路徑、推論方式及「已完成」均按當時脈絡閱讀。

## 原件與出處

| 可直接閱讀的原文 | 原提交與原路徑 | 用途 |
|---|---|---|
| [2026-03-19 PDF 解析專案 README](2026-03-19-pdf-to-json-readme.md) | `3f37424f38caa64a9c0babd3f0d42d9cde38bcc3:README.md` | iCAP／OCS PDF 結構化資料的起點，早於 Caliburn monorepo |
| [2026-05-20 JobIntel 架構](2026-05-20-jobintel-architecture.md) | `9bbfe51b9c2130335065e495f102e84f1e2f6b11:docs/architecture.md` | 原本的 LangGraph 節點、pgvector、狀態保存與前後端分工 |
| [2026-05-20 訪談狀態機](2026-05-20-jobintel-graph-pipeline.md) | `9bbfe51b9c2130335065e495f102e84f1e2f6b11:docs/graph-pipeline.md` | 固定階段訪談，以及短答、重問、提前切換等早期修正紀錄 |

2026-10-02 從上述提交取出；正文不加新結論、不改原本主張。來源可用 `git show <提交>:<原路徑>` 核對。本機可讀不代表這次已推送至遠端。其餘舊檔與程式保留於 Git，不為這三份導讀複製整個舊專案。

## 更早期程式修改線索

| 提交 | 原檔案／可核對內容 |
|---|---|
| `7a21c19974f2940d3242501c2c79dc71bca5a709`（2026-03-27） | `src/jd_pdf_to_json/transformers/ocs_transformer.py` 與 `tests/test_ocs_transformer.py`：保留 `S01` 與以 `3D` 開頭技能名稱的邊界，提交含反例測試 |
| `5ed577973b273df79a9f6f8db932931dc3e3b22b`（2026-05-11） | README、model、transformer、validator、test 同步改為 P-centric `competency_blocks`，不是只改顯示名稱 |
| `4085249e9e328de2382802859404df367cf3cf37`（2026-05-13） | 合併儲存格的 outputs 繼承修正，提交含測試變更 |
| `cc13b6f98bf91f97259a755f121c2d116d0d3939`（2026-05-15） | 跨頁多個 T code、沒有 P-code 時誤建新 Task 的解析修正；此提交本身沒有新增測試，不能說本次已驗證 |

例如 `git show 7a21c199 -- tests/test_ocs_transformer.py` 可讀當時測試。提交中的測試程式只能證明當時留下了什麼檢查，不能代替保存的執行結果。

整段發展及其他主題由[開發演進素材索引](../../reports/development-history/README.md)串接；本頁只維護原件出處。
