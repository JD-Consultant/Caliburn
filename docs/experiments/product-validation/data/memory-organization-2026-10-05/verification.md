# 候選指引：離線驗證紀錄

本頁保留真模型執行前的離線驗證；接續的實際試跑已另記於[對照結果](results.md)與[執行紀錄](execution-notes.md)。以下「尚未」描述的是該離線階段，不是最新實驗狀態。

日期：2026-10-05。檢查時分支 `jd-app-docker`，HEAD `13c0663a7d42`；工作樹另有其他任務變更。本紀錄只涵蓋本資料包，不替其他修改背書。

結論：**候選已完成文字審查與離線契約檢查，可準備有界真模型比較；未採用到正式產品。**未發送模型請求、未連資料庫，沒有本批 API 費用或語意成績。

## 1. 檢查的範圍

[check_candidates.py](check_candidates.py)用現行 `memory_analysis_tool_definitions`、`ResponseRequest` 及 `parse_outcome` 檢查：

- B1 的工具集合不含工作理解，B2 沒有情境寫入工具；原工具集合為 6／8 個。
- 首階段模板只替換 instructions；另階段的工具候選只替換原允許工具的 description，參數、strict、名稱與其他欄位一致。
- 兩份候選的完成 JSON 都由現行結果解析器接受；不新增回交結果。
- 三種模板均能經現行請求快照還原，內容保持一致。

模板用空 input、Luna／high、16,384 輸出上限做本地序列化檢查；**這不是已凍結的付費設定，也不是拿空 Context 測模型品質**。正式比較還須提供相同、完整、合法的起始資料。此程式不建立 client，不讀金鑰、不保存或更新產品資料。

## 2. 實際執行

原先使用 `uv run --project apps/api --locked` 時，本機 uv 全域快取存取被拒，命令未進入測試。改用既有 App 虛擬環境執行，未安裝或更新套件。首次 pytest 的快取路徑亦不可寫；關閉 pytest 快取後重跑同一集合，無警告。這兩項是本機沙箱／快取限制，不是 Prompt 或模型失敗。

在儲存庫根目錄執行：

```powershell
& apps/api/.venv/Scripts/python.exe -X utf8 -B docs/experiments/product-validation/data/memory-organization-2026-10-05/check_candidates.py
& apps/api/.venv/Scripts/python.exe -X utf8 -B -m pytest -p no:cacheprovider apps/api/tests/unit/test_role_prompt_contracts.py apps/api/tests/unit/test_memory_analysis_tools.py apps/api/tests/contracts/test_memory_read_tool_dispatch.py -q
& apps/api/.venv/Scripts/ruff.exe check --config apps/api/pyproject.toml docs/experiments/product-validation/data/memory-organization-2026-10-05/check_candidates.py
& apps/api/.venv/Scripts/ruff.exe format --check --config apps/api/pyproject.toml docs/experiments/product-validation/data/memory-organization-2026-10-05/check_candidates.py
```

結果：候選契約檢查 exit 0；既有測試 **27 passed**，重跑耗時 1.60 秒；Ruff 檢查及格式檢查 exit 0。既有測試驗現行角色接線、工具權限及讀取契約；候選模板另由本地檢查驗證。沒有把既有測試通過說成候選的完整執行或自然語意改善。

| 指引 | 原版字元數 | 候選字元數 | 工具數 | 工具候選覆蓋數 |
|---|---:|---:|---:|---:|
| B1 | 938 | 1,378 | 6 | 3 |
| B2 | 906 | 1,501 | 8 | 5 |

字元數不是 token。候選補了組織判準，並非更短；後續需把指引成本納入總量，而非只報少查幾則原話。

指引 SHA-256（原版為 Python 常數原值；候選為 UTF-8 文字經 `.strip()`，即本地模板實際使用的值）：

| 項目 | SHA-256 |
|---|---|
| B1 原版 | `0f3abd516e55664ebff06ed4a03dbeb95426e16d204d49286fcb444f6c5a9447` |
| B1 候選 | `4e33a01ef4f61b307da10f95212b27c818e5d571a4851c3bdaea30f7c8d5028d` |
| B2 原版 | `4deac4a7f3b6715b2bab2af32fdbd03d6e01828a36ce5f56310b49a04260855c` |
| B2 候選 | `025d29b512c750405d0f8264a51131aec2dc8a3f91e60fe4eb0238c4e6fa75e6` |

## 3. 文字及權責審查

獨立唯讀審查對照指南與現行契約，沒有提出必須先修的角色越權或拆合規則衝突。檢查包含 B1 不能讀理解、B2 只改理解、單向不回交、未被引用的新情境、精確條件、已知未知、來源移轉及不逐條刷新版本。此結果是代理文件審查，不是模型受測表現。

工具參數與寫入說明經審閱後保留；模型已有合法方式表達目標、內容及來源變動，不因此新增工具或改 schema。舊式強制往下閱讀的語句只在候選修訂，正式指引仍保持原狀。

本資料包 5 份 Markdown 的 14 個本地檔案連結均存在，未發現行尾空白或衝突標記；另核對引用的指南與資料包內章節。研究頁及入口只新增候選狀態與路由，不將本地檢查寫成已採用決策。

## 4. 尚未驗證

尚未測 Luna 是否真的採取適當組織、保留全部有效事實，或讓 A 用更少無關 Context 完成相同品質的 JD。尚未建立本輪隔離工作稿、跑工具修改／發布、做增量 diff 真模型比較，亦未做超容量壓縮比較。

下一步依 [README 的階段 1](README.md#分開比較避免不知道哪裡有效)：先固定 B1 與工具，只換 B2 指引；經個別付費界線確認後才啟動。若候選較差，保留失敗輸出及原因，不為採用候選而改判準。
