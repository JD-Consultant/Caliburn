# T13 正式 PDF 匯出：獨立切片

- 日期：2026-09-30；狀態：**正式讀取與 renderer／HTTP 元件已實作，主線 bootstrap／UI 接線待主代理整合；T13 未整體完成**。
- 範圍：僅 PDF，不包含 T13 條件撤回。遵循 [T13 任務](../tasks.md#t13-正式-pdf-與條件撤回)、[交付 §4](../../../implementation/interface-and-delivery.md#4-pdf-與程序)、[V21](../../../architecture/verification.md)。沒有切換 production、付費模型或改動舊資料。

## 1. 公開接線與唯一權威

```python
renderer = PdfRenderer(font_path=Path(configured_font_path))
app.state.jd_export_workflow = JdExportWorkflow(database.sessions, renderer)
app.include_router(jd_export.router)
# lifespan shutdown:
await renderer.aclose()
```

- `GET /api/job-files/{job_file_id}/jd/export.pdf`：200 `application/pdf`，attachment `job-description.pdf`，`Cache-Control: no-store`。無需版本、候選或姓名參數。
- `JdExportWorkflow.export_current(job_file_id) -> bytes`：先驗檔案存在，讀正式 head **一次**，用該固定 revision 讀 profile 與 work collections；關閉 DB session 後才渲染。重用原 `persistence.read_revision`／`work_queries.read_work_at`，不另建儲存或快照表。
- `PdfRenderer(font_path=Path(...), executable_path: Path | None = None)`：`render_html(body_html) -> bytes`、`aclose()`。預設使用 Python Playwright 自己的已安裝瀏覽器；明示 executable 只供受控部署／驗證，不自動搜機器上的任意瀏覽器。
- 404 `job_file_not_found`；503 `pdf_export_unavailable`／`pdf_renderer_busy`／`pdf_font_unavailable`／`pdf_render_failed`；504 `pdf_render_timeout`。HTTP 不回傳 exception 原文或 JD 內容。

本切片未修改 bootstrap、UI、generated 或 JD persistence。由主線加入 lifespan 依賴與 router；未配置 workflow 時既有 dependency 明確拒絕，不假裝已可下載。

## 2. 研究與取捨

- [Playwright library：Windows／threading](https://playwright.dev/python/docs/library#incompatible-with-selectoreventloop-of-asyncio-on-windows)：driver subprocess 需要 Proactor；API 不是 thread-safe。本案在單一受控 worker thread 內建立 Runner／Playwright／browser，並在相同 thread 關閉；呼叫方可維持 DB 所需 Selector。不是每份 JD 一個常駐服務。
- [page.pdf](https://playwright.dev/python/docs/api/class-page#page-pdf)：使用 print CSS、PDF bytes、A4、頁碼、tagged／outline。直接採 Chromium 版面引擎，不造 Markdown/PDF parser 或報表平台。
- [Playwright library：cancellation](https://playwright.dev/python/docs/library#cancelling-asyncio-tasks)：不取消執行中的 Playwright call。HTTP 等待以 shield 隔離；worker 仍持有容量直到清理完成。browser 開啟後 50 秒觸發本 worker 的 close；外層 60 秒等待上限，launch／set_content 30 秒。清理失敗不假成功。
- [PyPI Playwright](https://pypi.org/project/playwright/) 查閱穩定版 1.63.0，Apache-2.0；加入 `pyproject.toml` 並以 uv 0.12.20 lock／sync。此套件 browser manifest 為 Chromium 153.0.8010.12 / revision 1243。

Renderer 限一次一份，繁忙直接拒絕，不排無界佇列；取消呼叫方不會提前釋放 slot。受信 HTML 模板與 print CSS 分工，所有 JD 字串 `html.escape`，保留換行；JS 關閉、CSP、offline、所有 page resource route 拒絕、service worker 禁用。指定本機中文字型以 data URI 內嵌，無外部字型／圖片請求。

## 3. 內容保證

完整輸出 profile、職責 scope、各任務（含未歸屬）、成果 O／要求 P、共用 K／S 定義與任務關係、協作及五類條件。任務引用 K／S 的成品編號／名稱，定義正文在總覽完整呈現，不複製整份正文。無省略／preview／分頁截斷。空正式 JD 可匯出並明示無內容，不捏造職責或宣稱審核完成。

資料來源只包含正式 JD 成品，沒有受訪者姓名／檔名、訪談原話、引用／內部 metadata。本文字型設定不是自動抹除使用者在 JD 正文中自行輸入的姓名；產品目前定義的是不另匯出受訪者姓名欄位。

## 4. 測試與實際證據

- Red：`test_jd_export_projection.py` 兩例在未實作 projection 時因 `NotImplementedError` 失敗；`test_pdf_renderer.py` 缺字型例、`test_jd_export.py` 正式／候選隔離例同樣先失敗再實作。HTTP 薄接線與執行緒取消另外作回歸，不冒稱都是獨立 Red。
- 真 PostgreSQL：建立正式職稱後啟用 A，候選修改職稱，PDF 投影仍取原正式職稱；姓名、檔名、候選、pending input 均不輸出。不存在檔案 404，字型錯誤 503 而非空 PDF 200。
- 真渲染：Python 3.14.7、Playwright 1.63.0、顯式 `S:/caliburn/.research-tmp/chromium-153.0.8010.12/chrome-win64/chrome.exe`、`C:/Windows/Fonts/NotoSansTC-VF.ttf`。版本與套件 manifest 相符，但此次使用既有 binary，**未驗證全新 Playwright install／Linux 容器／其他瀏覽器版本**。
- `.research-tmp/t13-pdf/jd-short.pdf`：1 頁；`jd-long.pdf`：3 頁。以 bundled Poppler 渲染全部 4 頁 PNG 並逐頁檢查：中文可讀、無缺字方框、無重疊／截斷，長任務自然跨頁、頁碼正常、末尾成果保留。
- 文字抽取有 CJK 相容字形碼位；驗證時用 Unicode NFKC 比對（僅 QA，未改寫產品正文）。80 個步驟與末尾成果均可回查。
- 環境限制：sandbox 下載與 Windows subprocess pipe 曾遭拒；授權後同命令成功。字型 tmp fixture ACL 失敗不是行為 Red；改用明確不存在的字型路徑才得到正確 Red。未用關閉 sandbox 保護改產品行為。

重現命令（從 `apps/api`；本機 DB 必須是隔離 `_test` database）：

```powershell
$env:PYTHONUTF8 = '1'
$env:CALIBURN_TEST_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
$env:CALIBURN_TEST_PDF_FONT = 'C:/Windows/Fonts/NotoSansTC-VF.ttf'
$env:CALIBURN_TEST_PDF_CHROMIUM = 'S:/caliburn/.research-tmp/chromium-153.0.8010.12/chrome-win64/chrome.exe'
$env:CALIBURN_TEST_PDF_OUTPUT = 'S:/caliburn/.research-tmp/t13-pdf'
./.venv-target/Scripts/python.exe -m pytest tests/unit/test_pdf_renderer.py tests/unit/test_jd_export_projection.py tests/integration/test_jd_export.py tests/integration/test_pdf_rendering.py tests/unit/test_import_boundaries.py -q --tb=short -p no:cacheprovider
```

最終上述命令 **23 passed（6.62 秒）**，包含 2 份真 PDF 與真 PG 隔離／HTTP 反例。四個新增 production 模組 mypy strict 通過；八個新增 code/test 檔 Ruff check／format 通過；依賴變更 `git diff --check` 通過。文字檢查確認 80 步驟與末尾成果存在。產物置 `.research-tmp`，不提交合成 PDF 或機器字型。

## 5. 留給主線與後續 gate

1. bootstrap／lifespan 注入 configured font、renderer 與 workflow；UI 真下載旅程及候選預覽中下載，仍需接線驗收。
2. 確認乾淨交付時 Playwright browser install、中文字型授權／安裝與可重現配置；本機已有字型不是跨平台交付證據。
3. T13 條件撤回不在此次範圍；T15 較廣壓力／程序硬崩潰／browser 無回應後 shutdown matrix 未驗。

不因本切片完成而勾 T13，亦不更改正式產品入口。

## 6. 主線接線與實際下載

主線已在 bootstrap 注入設定、renderer、workflow、路由與 shutdown；UI 加同源下載連結，明示正式稿非候選。設定由 `CALIBURN_PDF_FONT_PATH`／可選 `CALIBURN_PDF_CHROMIUM_PATH` 提供，不猜機器字型或瀏覽器。settings 聚焦 9 passed，PDF／HTTP 主線 5 passed；與前節數量有重疊。

2026-09-30 本機 `caliburn_target_demo`、Web 5173／API 8100：以 IAB 建立合成職務檔案、人工編輯職稱與目的，重新載入確認仍在，再從 UI 真下載 `job-description.pdf`（134,119 bytes）。Poppler 渲染 1 頁並視檢，中文／分隔／頁碼正常；文字抽取確認職稱與目的存在、示範員工姓名不在 PDF。這不是 AI 產稿或全部 T13 驗收。

下載 browser tool 發生異常長等待，約 02:20 UTC 才返回；雖呼叫已指定 30 秒事件／45 秒工具界線，實際工具延遲超出。後续驗證改用有界命令讀取下載產物；未以工具超时推導產品後端失敗，也未重複建立／匯出。產物與 QA PNG 留本機未提交。

## 任務完成對照與 PDF 文字層診斷（2026-09-30 恢復後）

沿[任務表 T13 的 Red 與完成條件](../tasks.md#t13-正式-pdf-與條件撤回)對照既有測試；只補一項瀏覽器驗證與一項診斷。路徑相對 `apps/api/tests`（除註明）。

| T13 Red／完成 | 代表測例 |
|---|---|
| 匯出候選／姓名 | `integration/test_jd_export.py::test_export_reads_formal_not_active_candidate_or_employee_name`；瀏覽器：[T09 旅程](t09-consultant-journeys.md)（有候選時 PDF 仍是正式版、200） |
| 中文缺字、長任務斷頁遺失、短／長實際渲染 | `integration/test_pdf_rendering.py::test_chinese_short_and_long_pdf_from_selector_loop`（真 Chromium；本輪設 `CALIBURN_TEST_PDF_FONT`／`CALIBURN_TEST_PDF_CHROMIUM` 後與另 5 案共 **6 passed**）、`unit/test_pdf_renderer.py`（缺字型明確拒絕、取消不放行第二個 worker）、`unit/test_jd_export_projection.py`；T17 課程行政 3 頁 PDF 逐頁目視 |
| 渲染失敗不冒充空 PDF | `integration/test_jd_export.py::test_renderer_failure_is_not_an_empty_pdf_or_success` |
| 正式版本固定 | 匯出讀固定正式修訂（上列匯出測例）；UI 說明「匯出目前已正式保存的版本，不包含本輪候選預覽」 |
| UI 下載 | **本次新增**：`apps/web/tests/e2e/consultant-journey.spec.ts` 第一個旅程在真 Chromium 點頁面上的「匯出目前 JD（PDF）」連結，取得 `.pdf` 檔且開頭為 `%PDF-` |
| 撤回只對允許基準成立、衝突明示不覆蓋、不倒退訪談／Memory | `integration/test_jd_undo.py`（10 案，含 `test_later_manual_edit_conflicts_without_overwriting_it`、`test_undo_restores_base_as_new_revision_without_rewinding_interview_or_context`、`test_undo_restores_relations_and_sources_but_keeps_new_memory`）、`test_jd_undo_migration.py`；前端 `UndoTurnJd.test.tsx` |

### PDF 文字層診斷（已知限制，不擴大處理）

T17 曾發現 PDF 文字抽取把「長」抽成部首字「⻑」。本輪用 `pypdf` 抽取產品的 `PdfRenderer` 輸出重現並定位原因：**取決於字型的 cmap，而非本案程式或 Chromium 版本**。Noto Sans／Serif（TC、HK、SC 變體字型）與微軟正黑體把 CJK／康熙部首字元也對到同一個字形，Chromium 產生 PDF 時反查 glyph→Unicode 就取到部首字，常見字如「長」「目」「黃」「齊」「鬼」「龍」「麥」「黑」「鼠」都受影響（康熙部首可經 NFKC 還原，CJK 部首「⻑」不行）；同一份內容改用標楷體（`kaiu.ttf`）抽出完全一致。**視覺輸出正確**，影響的是從 PDF 複製或搜尋文字。

取捨（Owner 要求不過度設計）：不新增字型加工或另一套 PDF 引擎。已知限制如實記錄；若之後認定需要，最小做法是操作者用字型工具移除字型 cmap 中 U+2E80–U+2FDF 的重複對應後再交給 `CALIBURN_PDF_FONT_PATH`（需先確認該字型授權允許修改與嵌入），或改用沒有此重複對應的字型；本輪不提供或驗證該加工流程。

**結論：**T13 在其範圍內成立，勾選。**不含**：乾淨環境安裝／建置／啟停的交付驗證（歸 T18）、PDF 文字層的複製／搜尋一致性（上述已知限制）。
