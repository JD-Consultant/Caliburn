# T5：整體回歸與效果比較的驗證界線

日期：2026-10-07。責任依 [INTPLAN](../../../specs/2026-10-06-consultant-interview-planning-and-focus-design.md) 與[施工計畫](../../2026-10-07-interview-plan-implementation-and-comparison.md)。本頁記工程驗證；真 API 訪談、披露政策、費用與最終 JD 效果沿[比較原件](../../../experiments/product-validation/interview-plan-comparison-2026-10-07/protocol.md)，不由工程測試推定。

## 核心收尾結論

T5 的工程檢查、核心真模型比較、匿名品質評閱、機制與文件交付已執行完成；**高品質完整 JD 與持久筆記穩定增益門檻未證**。八個有效案例各 20 Turn completed＋common closure，四個 P2 正式筆記皆非空，20／20／18／20 次編輯 updated、零 rejected。四組匿名判讀全部鎖定後解盲：兩組 P2 較好、一組 P1 較好、一組各有得失，八案均有重要缺口或錯誤。[完整結果及原件索引](../../../experiments/product-validation/interview-plan-comparison-2026-10-07/results.md)維護品質、披露、費用與原失敗沿革。

160 個 accepted source ID/body 與 144 個已送後續裁決接線一致，但課務 r1 P1 Turn 10 全部子問未知仍重播一般 refund，違反凍結政策，該組不能單獨承擔公平因果歸因。回答裁決代理曾接收營運 arm metadata，不宣稱全 context 盲；primary 品質仍為獨立 fresh 匿名 bundle＋rubric，先鎖後解盲。

四個 r2 真 within-Work C 均核 official saver adopted、原完整 C／同位置 projection→下一 A：倉儲 P1 19＋0、P2 19＋1；課務 P1 11＋0、P2 22＋1。公開 items 可重算，opaque 只有三處原 full hash witness 一致，不宣稱獨立重算原 bytes 或 numeric Step；兩個 r1 P2 是 pre-work C。焦點稽核另發現倉儲 r1 P2 留未知但未有效返回、r2 P2 問回仍未知、P1 r1 取得盤點後續，以及 P2 r2 將通則適用未知錯換為頻率未知。保存接續成立不代表語意取證成功。

核心累計 spent US$1.966786395、occupied US$2.014531895，包含舊失敗、短測、中斷及新案；三筆原未知預留全保留。八案自身 usage 換算合計 US$1.366484375，非 provider 發票。工程命令依執行時間與範圍分列如下，沒有重跑或把最後 74 tests 算入先前全套。

## 全套回歸收尾

第一次全 API 回歸以本輪自建 loopback `_test` PostgreSQL、pytest 隨機 schema 執行，provider 為替身：**2,431 passed、7 failed、2 skipped，920.50 秒**。以下定位與修正不改凍結的 production source、模型指引或工具契約：

- 六項來自公版角色歷史 fixture 的工具定義包裝未接受新的 `interview_plans_enabled` keyword。包裝轉傳原定義後，該檔 **8 passed**；既有舊能力測試仍以原捕捉定義恢復。
- 一項來自 JD 候選歷史測試期待 `ForeignKeyViolation`，但既有 migration 0025 早已以不可變 trigger 拒絕 cascade 刪除。使用尚未包含筆記表的 **0025** 新 schema 執行原測試，實際為 `CheckViolation: Fixed JD revisions and original results are immutable`，候選及原結果皆保留；[反證原件](api-baseline-0025-probe.json)。修正測試核該既有保護訊息，另驗刪除失敗後候選世代與原操作結果仍保留，不改弱資料庫保護。
- 兩個受影響測試檔合併重跑：**21 passed，22.93 秒**。

全 API 在原有 unit／integration 兩組同名 module 下，pytest 預設匯入模式會有既有收集衝突。正式 README 原本分兩組執行；此次全套用 `--import-mode=importlib` 收集，沒有改名或刪除歷史測試。新筆記 HTTP unit 檔已由切片改為獨有 basename。

第二次全 API 完整回歸：**2,438 passed、2 skipped、0 failed，955.77 秒**；命令及完整機器結果保留於 [JUnit](api-regression.xml)。兩項 skip 都是既有 `test_pdf_rendering.py` 的實體 Chromium 渲染，因未提供 `CALIBURN_TEST_PDF_FONT`；本題未改 PDF，沒有把 skip 算為通過。真 PostgreSQL 均已配置並執行。

```powershell
$env:CALIBURN_TEST_DATABASE_URL = '本輪自建 loopback _test 資料庫'
uv run --project apps/api --locked pytest apps/api/tests -q --import-mode=importlib --tb=short -rs --basetemp S:/caliburn/tmp/intplan-final-api-regression --junitxml docs/plans/evidence/interview-plan-2026-10-07/api-regression.xml
```

## 切片與獨立審查

各時間點實際範圍沿 [T1](t1-tools.md)、[T2](t2-storage.md)、[T3](t3-context.md)、[T4](t4-ui.md)；不把多次局部測試數合算為一次全面成功。Web 已有 **301 passed**、Chromium **4 passed**，並完成 TypeScript／lint／build。全 Web format 的 14 項既有提示保留，新切片格式通過；Vite 既有大 bundle 提示亦保留。

工具／保存獨立審查沿[原件](review-tools-storage.md)；換窗及鎖交界審查沿[原件](t3-storage-review.md)。新的 capture absence、同交易 active 讀取與 parent 保存前後故障反例已接回修正，完整 C 與原筆記 projection 精確承接，不以後來 head 替換已保存輸入。

最後的[獨立 context 審查](review-context-final.md) 另找出 saved toolkit 的 numeric equality／額外 assertion 缺口。六個可辨 Red 已修，reviewer 的 19 cases 全部 Green；主代理修正後工具／projection 等 **103 unit passed** 與 **32 真 PG passed**，Ruff／format／mypy 通過。此次全套已在此前收集，這個最後修正以受影響新命令另列，不冒稱全套原命令已包含其後新增反例。

全 API 靜態檢查於全套期間另跑：Ruff **All checks passed**、format **507 files already formatted**、mypy **340 source files** 無問題，canonical generator `--check` exit 0；最後 guard 之後的窄檢查另如上。

最後 source 的完整 unit／contracts 新命令 `uv run --project apps/api --locked pytest apps/api/tests/unit apps/api/tests/contracts -q --tb=short --basetemp S:/caliburn/tmp/intplan-final-unit-contracts`：**1,481 passed，14.54 秒**，包含 19 個 saved schema cases；不呼叫 provider。

真實訪談先導與正式比較各自凍結 manifest，所有失敗與停止原件保留。只有指引和指引加筆記使用相同共同焦點指引、有效指南及既有 JD／Memory；差異是筆記指引／工具／保存／全文投影。兩組都透過產品 HTTP 寫入並讀取最終正式 JD。受控 45K 換窗與 production 原生門檻分開判讀；匿名語意評閱先鎖結果，再解盲，不以 UI 或筆記呼叫次數評 JD 品質。

## 真模型格式失敗後的窄修正

三個完整 P2 的八次筆記編輯皆遭格式拒絕、正式筆記皆為 null；使用者要求先處理，舊付費批次已停止。修正只補工具 description 與 `invalid_patch`／`patch_context_not_found` 的具體 V4A 更正範例，沒有放入職務答案或放寬 parser。空筆記建立及局部替換保留其他未知的範例均經實際 prepare 驗證；既有 nullable／no-op／保存結果重播反例仍通過。

缺少可執行說明的 1 個 Red 與格式／錯 anchor 提示的 4 個 Red 已轉 Green；受影響 unit／contracts **74 passed**、Ruff／format／該模組 mypy 通過。這是全套回歸之後的新窄命令，沒有把先前全套冒稱包含這次說明修正。真 API 短測先驗建立、局部更新與同筆記換窗承接；可用性通過後才恢復 JD 效果比較。[修正原件與命令](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/operational-evidence/format-repair/repair-evidence.json)

真 API 短測實際 **2 completed／3 edits updated／0 rejected**，兩輪正式筆記皆非空；局部 hunk 保留另一主題，後一輪保留其未釐清審核交接。工作中的完整 native C 與下一 A 採用同位置筆記已取得。該測試明確要求保留另一主題，只驗修正後可用性及精確承接，未判 JD 增益。[語意核對與原件索引](C:/Users/chenb/.codex/visualizations/2026/10/06/01a11182-e198-7652-87d2-d90d10463ed1/caliburn-intplan-comparison/note-tool-smoke/note-smoke-repair-20261007/semantic-receipt.json)

## 正式首批中斷與實驗層修正

正式首批在第一場第六 Turn 發生 Python 原生 access violation，前五 Turn 完成，沒有完整配對；該場保留為中斷原件，不列為完成的品質樣本。36 次已准入生成中有 35 次收到原 usage，已知費用換算 US$0.022429100，最後一筆未知用量的 US$0.013296750 預留仍占用原額度。[Windows 事件與帳務](../../../experiments/product-validation/interview-plan-comparison-2026-10-07/formal/interruption-audit.json)、[有限離線診斷](../../../experiments/product-validation/interview-plan-comparison-2026-10-07/diagnostics/results.md)及[獨立 public cleanup 審查](runtime-research.md)保留實際界線。

相同 SDK／原 checkpoint／GC 組合在原實驗監測包裝下重現兩次 native Red；移除該包裝的兩次對照及改用明確擁有所消費 iterator 的新包裝，均各完成 2,000 次 SDK／checkpoint 重播，零 provider、零業務寫入。新包裝兩次耗時 75.57／75.05 秒。這是消除可重現觸發的實驗層修正，不宣稱已定位 CPython 或 SDK 原生根因；production、鎖定套件、模型與指引沒有因此修改。

新包裝的分段原 bytes、提前 terminal 清理、未知用量、取消、重複關閉及清理失敗，加上額度承接，合計 **11 passed，1.73 秒**。獨立[額度審查](append-budget-review.md)另抓到建構耗時延長剩餘時間的 Red，修正為函式入口固定 monotonic anchor 後，原 120 秒延遲反例會拒絕逾原截止的新外送，五項 carry tests 通過。新批只能沿原絕對截止及全部剩餘計數／費用預留續接；原首批與 manifest 不覆寫。

測試 PostgreSQL 的[保存核對](test-database-retention.json)確認為本次自建 container、`AutoRemove=false` 與持久 volume；本次不移除 container、volume 或實驗 schema。原 opaque checkpoint 留在原 owner 的 DB；公開輸入、item hashes 與轉錄不冒充其原件。
