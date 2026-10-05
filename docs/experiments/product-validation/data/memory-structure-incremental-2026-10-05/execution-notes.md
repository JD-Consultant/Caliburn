# 執行紀錄

## 外送前

本批已獲 US$0.10／20 分鐘授權，計入原累計 US$2；接續占用基準 US$1.253991040。只用合成訪談。正式產品、資料庫與服務不變。

新增程式只在本資料包。工作稿是記憶體資料結構加 JSON 原件，不是產品交易與恢復的替代實作。沿用正式工具 Schema、V4A 編輯器、ResponseRequest 及原生回傳序列化；費用預留、結算及速率等待沿用前批 `Recorder`。各角色共用同一預算，容量計數每次保守預留 US$0.0001，不算成模型生成實付。

原生接續依 [OpenAI reasoning 指南](https://developers.openai.com/api/docs/guides/reasoning#keeping-reasoning-items-in-context)：同一角色內保留 output items、reasoning 加密內容、message phase 與工具結果，不抽可讀摘要代替。公開 trace 只存加密內容長度與 SHA-256；角色結束後不把原生執行歷史傳給下批。

### 離線檢查

- `test_workspace.py` 先寫 11 項行為檢查，對未實作骨架執行為 11 failed；完成實作後為 11 passed。範圍包含未來訪談／逆序區間拒絕、角色與組別權限、快照獨立、改名保持引用、刪除解除引用、重名拒絕、無效來源及歧義 patch 原子拒絕。
- `test_episode.py` 先測原生 reasoning／commentary 保留、多工具依序執行、App Context 不重複追加；未實作時失敗。實作後發現測試用 `item['type']` 假設所有 user item 都有 type，改成讀取可省略欄位後通過。未因此改寫產品 serializer。
- `test_protocol.py` 四項為事後補測，不稱 TDD：本批訊息投影、B2 新增情境 diff、讀者只拿導覽、不能引用未讀正文。
- `test_budget.py` 兩項為既有護欄回歸：跨角色累計、預留超額、時間及外送次數拒絕，不外送。
- 本批 18 項離線測試通過，Ruff 檢查通過。只證明上述實驗邊界，不代替真模型品質。

命令（在 repo 根目錄；PowerShell 設 `PYTHONUTF8=1`）：

```powershell
apps/api/.venv/Scripts/python.exe -m pytest docs/experiments/product-validation/data/memory-structure-incremental-2026-10-05 -q -p no:cacheprovider
apps/api/.venv/Scripts/python.exe -m ruff check docs/experiments/product-validation/data/memory-structure-incremental-2026-10-05
```

材料、評分、提示、工具與依賴雜湊會在 `live-01/manifest.json` 固定。任何變更都須在執行前重新準備，不能改動已開始的原件。失敗不補跑。

獨立唯讀審查未發現阻擋外送的隔離、接續或護欄問題。審查提醒兩點：完成狀態不代表來源支持品質（空引用可完成，但另判為缺少依據）；失敗應以非零程序退出碼回報。後者已在凍結前修正，仍以 `run-summary.json` 的狀態及失敗原件為準。審查未外送或更動資料。

## 真模型執行與停止

- 執行目錄：`live-01`。開始時間 UTC 2026-10-05 04:46:33；程式基準 `13c0663a7d42e2e73b5c2ef45d20faa9e1b1fa11` 加 manifest 所列 dirty-workspace 檔案雜湊。
- 三批維護共九個角色完成；第一題顧問兩格完成。單集合第二題 final_answer 少了 task 結束括號，解析失敗，依原約定停止整批。不是 API 429、容量不足或超支；其餘三格沒有外送。
- 過程中單集合更正批一次 patch 缺少同一行前半句，被正式正文編輯器以 `patch_context_not_found` 拒絕；模型補回完整原句後成功。拒絕與修正都保留，未重跑該批。
- 雙層延伸批有一個語意錯誤：B2 以合法追加 patch 保留舊未知、再加新核准人。工具正確執行提交內容，但正文矛盾；見[語意核對](semantic-review.md)。不能用 strict schema 或唯一定位保證這種語意正確。
- 共 35 次容量計數、35 次模型回應，523.28 秒；生成估值 US$0.012598195，加計數預留 US$0.0035，占用 US$0.016098195，累計 US$1.270089235。不存在仍執行中的付費 session。
- `study.py verify live-01` 在停止後通過；原件與凍結依賴未變。`analyze.py` 只生成派生的 `analysis.json`，不修改原件。程序 exit 1，狀態為 stopped，沒有人工修復成成功。

下一批需用官方 Structured Outputs 約束讀者最終結果，而不只在 Prompt 要求 JSON；這是執行器改進方向，不擴充正式產品、不重寫本批結果。已完成的三批維護仍可比較，未完成閱讀不可代證。
