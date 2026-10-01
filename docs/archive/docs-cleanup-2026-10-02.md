# 文件去重與證據歸位紀錄

整理前基準為 `target-rebuild@94424cea`。Owner 授權移除無用文件、以 Git 保留歷史，但要求有用的問題分析、研究、實驗、失敗與修正資料保持可直接閱讀。本次改文件分類、連結、程式檔內的指南路徑註解，以及舊 P3 測試 driver 的證據資料夾定位；不改產品邏輯、模型、資料庫、執行中的程序或其他 worktree。

## 分類與刪除範圍

- 從 3,094 份 branch／worktree 快照檔案中去除 2,396 份相同 Git blob 的副本；保留一份可讀內容，逐檔記錄保留位置。不同歷史修訂不按同名刪除。
- 1,673 份歸位：六份分析指南移到 `guides/`；舊 `specs/evidence/` 移到 `experiments/legacy-evidence/`；快照獨有實驗、報告、方法資產及早期 Agent 任務報告集中在 `experiments/historical/`。新目標的 task evidence 保持原責任位置，不複製。
- 另移除七份已核對的文件：兩份明示撤回的純施工計畫、五份僅三行的退役通知。它們不是實測報告；撤回原因與有效禁令仍由 ADR、研究及接續設計持有。
- 其餘獨有歷史規格、決策與含實測的計畫保留。此次不以日期或檔名判定所有舊文件無用，也不重分類正式產品權責。

[逐檔對照 CSV](docs-cleanup-2026-10-02.csv)記錄基準提交、原路徑、新位置、處置、Git blob 與整理前後 SHA-256。相同 Git blob 的 Windows checkout 可能只有 CRLF／LF 差別；不把這種情況宣稱為磁碟 bytes 全等。Markdown 只機械調整導航，原正文仍能從基準讀回；非 Markdown 移動原件須逐一雜湊核對。

## 僅留 Git 的七份文件

| 原路徑 | 理由及接續資料 |
|---|---|
| `docs/plans/2026-07-23-local-web-jd-workspace-plan.md` | 明示施工前撤回；保留 [ADR0039](../adr/0039-local-multi-document-canonical-public-form-workspace.md)與原多文件研究 |
| `docs/plans/2026-08-26-shared-current-jd-and-semantic-review-implementation.md` | 明示禁止沿該方案施工；[8/27 後繼歷史計畫](implementation-plans/2026-08-27-consultant-workspace-ui-implementation.md)保留演進，不當現行規範 |
| `docs/archive/retired-documents/ocs-schema.md` | 三行退役通知；正式權責由 ADR 判定 |
| `docs/archive/retired-documents/ocs-source-json.md` | 同上，不因此退役獨立 RAG |
| `docs/archive/retired-documents/service-split-framework.md` | 同上，不沿舊服務拓撲施工 |
| `docs/archive/retired-documents/design/editor-knowledge-pack.md` | 三行退役通知，不恢復舊 editor seam |
| `docs/archive/retired-documents/design/interview-engine.md` | 三行退役通知，不恢復舊訪談引擎 |

## 如何取回原件

先從 CSV 找到原路徑。完整整理前內容可唯讀查閱，例如：

```powershell
git show 94424cea:docs/plans/2026-07-23-local-web-jd-workspace-plan.md
```

若需要檔案而非閱讀，先選新的輸出位置或隔離 worktree，不覆蓋現有文件。原 tag／分支與 source snapshot 的歷史脈絡沿[歷史索引](worktree-history-index.md)；本次不刪 tag、不重寫提交、不 GC，也沒有 push。本機 Git 不等於異地備份。

## 有用材料的閱讀方式

- [共用問題分析與實驗案例集](../reports/research-casebook.md)面向教授與報告，分開問題、查證、解法、驗證與限制。
- [歷史證據入口](../experiments/historical/README.md)保留 CT37／38／42／43、舊 JD 編輯初審失敗與 closure、R1 方法資產。不能只留最後 PASS。
- [分析指南](../guides/README.md)、[研究分類](../research/README.md)、[目標驗收證據](../plans/2026-09-29-target-rebuild/evidence/README.md)各有用途，不搬成同一大包。
- ignored capture、資料庫、暫存及私人資料本輪未刪；有些歷史實驗仍依賴未入 Git 的原件，不能宣稱已完整保全所有可重播環境。

## 方法依據

依既有文件規範，以讀者任務區分用途、每份原始證據只維護一處。參考 [Diátaxis 的使用需求分類](https://diataxis.fr/)及 [Google Software Engineering 的文件章](https://abseil.io/resources/swe-book/html/ch10.html)；並未把它們解讀為必須照抄固定目錄模板。刪除只限已核對的副本及撤回通知，不為目錄美觀刪除獨有研究。

## 驗證

移動前已檢查所有操作路徑位於 `S:\caliburn\docs`，來源檔案與盤點 SHA-256 一致，移動不覆蓋既有檔案；刪除使用逐檔明確路徑。驗證結果：

- 4,076 筆處置均有可讀的保留／恢復入口；1,288 份搬移的非 Markdown 原件 SHA-256 不變。
- 新目標指引／長旅程資料包的 28 筆 `runs/SHA256SUMS.txt` 核對通過；未改數據或 PDF。
- 15 份主要導覽與新增報告的相對連結／章節檢查通過。搬移前存在的檔案連結對照後，沒有新增檔案斷鏈；歷史快照原本已有的缺檔引用未假造補齊，查精確原版仍須用 Git。這不是全 repo 所有歷史 anchor 都已修好。
- 舊 P3 driver 的新資料夾內，manifest 所列五份文件及結果模板均存在；兩個有路徑變動的 Python 檔案可被 AST 解析。沒有執行付費試驗、啟動服務或宣稱完整產品測試通過。
- `git diff --check` 通過。官方招生要求與共用案例的事實／限制另經唯讀交叉審查，未發現重大錯誤；個人貢獻與實際送件狀態仍待本人確認。

本次修正兩個入口狀態矛盾：退役的 `consultant-runtime.md` 不再被 design 索引稱為唯一 active 設計；R1 總索引補上已存在的 R1a 實測結果，不再一概稱為尚未跑 trial。沒有為了整理而改寫歷史結果。
