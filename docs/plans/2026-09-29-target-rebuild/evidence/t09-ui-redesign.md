# T09 前端 UI 改版（粗版）與 API 缺口交接

日期：2026-09-30。**粗版**：版面骨架、視覺規則、訪談欄、JD 閱讀／編輯、章節導覽、來源面板與 JD 項目來源徽章、檔案清單已接線；不是完整 UI 驗收，也不代表真模型旅程通過。責任與不變式見[介面設計 §1.6](../../../implementation/interface-and-delivery.md#16-工作畫面組裝t09-ui-改版)；本頁只記設計依據、已驗／未驗與交回後端的缺口，不另立產品規格。

## 1. 設計依據（實際查到的官方說明）

| 參考 | 採用 | 本次查證狀態 |
| --- | --- | --- |
| [Cloudscape 間距](https://cloudscape.design/foundation/visual-foundation/spacing/)／[字級](https://cloudscape.design/foundation/visual-foundation/typography/) | 4px 網格（2/4/8/12/16/20/24/32/40）；標題 24/30、20/24、18/22、16/20、14/18，內文 14/20 | 官方數值已核。中文內文改 15/26（行高加大），屬本案取值 |
| [Cloudscape 生成式 AI 對話](https://cloudscape.design/gen-ai/patterns/generative-ai-chat/) | 輸入固定在底部、只有訊息記錄捲動；使用者回看舊訊息時不強制捲動；限制氣泡寬度；每位作者一個頭像；錯誤附復原動作 | 官方文字已核 |
| [Cloudscape 產出物預覽](https://cloudscape.design/gen-ai/patterns/artifact-previews/) | 產出物（JD）在相鄰區域展開，不塞進對話氣泡；產出物動作與對話動作分開（PDF 在 JD 欄標頭） | 官方文字已核 |
| [Carbon for AI](https://carbondesignsystem.com/guidelines/carbon-for-ai/) | 「AI 層」與標籤區分尚未正式的 AI 內容 → 候選預覽用淡藍底＋「候選」標籤 | 只核到搜尋摘要，頁面本體被截斷 |
| [Linear 改版說明](https://linear.app/now/behind-the-latest-design-refresh) | 「結構要被感覺到，而不是被看到」：分隔線減少、邊界降低對比、中性色為主、次要控制降噪 | 原則已核；**官方未公開 px** |
| [Airtable Record detail](https://support.airtable.com/articles/5805061650-airtable-interface-layout-record-detail)／[Attio 記錄預覽](https://attio.com/help/reference/managing-your-data/records/create-and-view-records) | 側滑面板疊在原頁上、原頁仍可見；面板內列出項目、可上下切換 → 來源面板 | 結構已核；**官方未公開 px** |
| [Notion 版面](https://www.notion.com/help/layouts) | 屬性清單（標籤淡、值清楚）→ JD 基本資料 | 結構已核；**官方未公開 px** |

未取得：SAP Fiori Object Page 官方頁（403）、Carbon 間距／字級／表格頁（內容被截斷）、Storybook 量測（故事 ID 不符）。因此本案的 px 值是**在上述 4px 網格上的自選值**，並以下方實測自己的版面；不宣稱是這些產品的實測值。

## 2. 已實作

- **版面**：`WorkspaceLayout`——左訪談（`clamp(380px, 36vw, 520px)`）、右 JD，各自捲動，整頁不捲動；<900px 以「訪談｜JD」分頁切換，僅 CSS 隱藏，兩區保持掛載（輪詢、SSE、未送出草稿不受影響）。`FileBar` 顯示檔名、受訪者與伺服器確認的處理狀態徽章。
- **訪談欄**：訊息記錄自動跟到最新（僅在使用者接近底部時；回看舊訊息不被打斷）、發言者頭像、輸入與處理控制固定在底部（`InterviewComposer` 拆為捲動記錄＋固定底座，原命令識別／恢復邏輯未改）。
- **Turn 狀態讀取**：頁面以 `useCurrentTurn`（`useSyncExternalStore` 訂閱本分頁 Turn 識別＋唯讀 query 觀察者）取得處理狀態；最初版本曾用 Effect 把 composer 的狀態複製進頁面 state，違反[寫法規範 §6](../../../implementation/coding-standard.md)，已改掉（`fa271110`）。
- **JD 欄**：顧問處理或暫停時 JD **唯讀**並說明原因；候選預覽移到 JD 欄，用「候選」AI 層樣式，並可切回「正式稿」；PDF 只匯出正式版。次要動作改為圖示按鈕（保留原無障礙名稱），在指標裝置滑過或鍵盤聚焦才顯示、觸控裝置常駐；巢狀雙層框線改為分隔線。
- **長 JD**：章節導覽列（sticky、標示目前章節）、職責可收合（任務保持掛載）、`JdWorkEditor` 拆出 `AreaSection`／`TaskCard`；編輯工具列在桌面 hover 時浮在項目右上角（不佔版面），觸控與窄螢幕維持在流內。
- **檔案清單**：名稱即連結（無障礙名稱不變）、首字頭像、hover 列底色、圖示重新命名、載入骨架。
- **來源**：改成 JD 欄右側滑出面板；詳情在列表**上方**；JD 各項目旁顯示「來源 n 筆／待核對」徽章，點擊只列該項目來源。
- **小改後端（已獲授權，未動核心）**：`GET /jd/sources` 的 `Reference` 增加選用 `target`（項目身分：`kind`／`field`／`item_id`／`task_id`），沿用後端本來就有的 `JdSourceTarget`；只改 HTTP schema、DTO 映射與生成物。徽章**只用身分連結，不按名稱解析**。欄位為選用，舊後端仍可讀（無徽章）。

## 3. 驗證

| 項目 | 結果 |
| --- | --- |
| 前端 Vitest | 25 檔／**139** 通過（基線 18／115）。Red 先行：`turn-hint-store`、`use-current-turn`（5 項行為失敗後實作）、`JdOutline`、職責收合。事後補測（**非 TDD**）：`source-index`、`turn-summary`、`SourceViewer.sheet`、`JobFileWorkspace`（JD 唯讀鎖、分頁不卸載）；對 `targetKey` 做變異檢查（忽略 `task_id`）確認索引測試會失敗。`App.test.tsx` 1 項因候選改為獨立檢視而先切「正式稿」再驗 |
| 前端 tsc／ESLint／Prettier | 皆通過 |
| 後端 | `tests/contracts/test_jd_sources_target_contract.py` 通過（八種目標形狀、同名標籤以身分區分）；`generate_contracts.py --check` 無漂移；ruff、ruff format、mypy（`jd_evidence.py`）通過 |
| 真 PG（隔離叢集） | `test_jd_source_http.py`、`test_jd_source_persistence.py`、`test_jd_shared_source_queries.py` **15 通過**（含新的 `target` 預期）。叢集：repo 內可攜 PostgreSQL 18.6 於新資料夾、127.0.0.1:55450、空白 `_test` 資料庫；不接 Demo DB |
| Playwright e2e（隔離後端 8101＋第二組 dev server 5174） | 17 項中 **15 通過**（含新的 `workspace.spec.ts`：整頁不捲動、章節導覽、收合、窄螢幕分頁保草稿）。**2 項未通過且無法在本環境驗**：`jd-profile:86`、`jd-work:209` 需要「A 已准入」，隔離後端未設模型（`POST /inputs` 回 503 `model_not_configured`），依規不啟動付費模型。既有窄螢幕案例改為先切「JD」分頁。瀏覽器為系統 Chrome，**不是** lock 的 Playwright Chromium revision，不能視為等價證據 |
| 瀏覽器（Chrome，桌面 1440×900、手機 390，Demo 唯讀，非 GET 請求 0） | 整頁不捲動（文件高 900）；訪談欄 518px／JD 欄 922px；輸入區固定；無頁面錯誤。改版前同一檔案頁高 8,014px、79 顆按鈕 |
| 徽章畫面 | **合成**：Demo 後端尚是舊程式，沒有 `target`，此處在瀏覽器端依標籤對照後攔截回應，只驗視覺，**不是後端結果** |

**未驗**：需模型的兩項 e2e（見上）；真後端回傳 `target` 的徽章畫面（隔離環境沒有 AI 產生的來源；HTTP 層已由真 PG 測試驗證，畫面需重啟 Demo 後端載入新程式後看）；鎖定版 Playwright Chromium；完整鍵盤／焦點走查；窄螢幕 JD 分頁最終截圖；長訪談（200+ 則）效能；色彩對比只做計算（內文 #1b2420／#4d5b55 對白底約 15:1／7:1），未做工具掃描；未使用真模型。

## 4. 已知限制

- 顧問正式訊息含 Markdown 標記（`**粗體**`、`- 條列`），依「原文以轉義文字顯示」規範維持原樣；若要渲染需先決定是否允許改變原文呈現。
- 建立／改名對話框與空狀態尚未改版；JD 欄的載入骨架尚未做。
- 章節導覽的「目前章節」以捲動位置計算，jsdom 無版面故只測跳轉，高亮以瀏覽器實看。
- 候選檢視沒有章節導覽，也沒有相對正式稿的差異標示（API 缺口 2）。

## 5. API 缺口（交回後端處理）

1. **找回進行中的處理**——效果：換瀏覽器或清除儲存後，仍能看到並控制這份檔案進行中／暫停中的顧問處理，JD 唯讀提示也正確。缺少：以檔案查「目前 Turn」的契約（現只有 by execution／by command，識別存在瀏覽器 localStorage）。受影響：訪談控制區、檔案徽章、JD 唯讀鎖。同一瀏覽器多分頁不受影響。
2. **「AI 這一輪改了 JD 什麼」**——效果：完成後可檢視本輪 JD 變更再決定是否撤回（產品旅程第 5 步的已確認目標）。缺少：本輪 JD 變更檢視契約（現 HTTP 只有撤回）。受影響：歷史回答的 JD 操作、撤回確認。處理中「候選相對正式稿」的標示或可由前端用項目 ID 推導，需先驗證候選與正式稿 ID 穩定，未做。
3. 次要：訪談訊息無時間戳、歷史一次回傳全部（無分頁），長訪談導覽只能在前端處理。
4. 已小改：JD 項目↔來源對應（`Reference.target`）。Demo 後端須重啟才會回傳；穩定後可評估把 `target` 改為必填。

## 6. 主線承接（2026-09-30，保留上述原驗證紀錄）

- Demo 後端已於無 active／paused 工作時重新啟動載入 `Reference.target`；主線從 5173 的真 API 再次讀得 **33 筆來源／33 筆非空 target**，沒有攔截或合成替代。原徽章視覺驗證的限制仍保留，不擴大為完整來源鏈／全 UI 驗收。
- 隔離 proxy 不再覆寫 Origin。需在隔離後端明確設定 `CALIBURN_DEV_ORIGIN`，步驟沿 [web README](../../../../apps/web/README.md#合成資料瀏覽器驗收)；red→green、官方依據與安全邊界見 [T15 修正](t15-local-http-security.md#隔離前端的來源保留修正2026-09-30)。
- 缺口 1 的後端 `/consultant-turns/current` 已交付並通過相關真 PG／契約回歸，詳細回傳與限制見[發現入口證據](t09-current-turn-discovery.md)。**UI 尚待接線**：不要把有 API 說成換瀏覽器已可控制；未知原輸入仍走 by-command，不因 current=null 自動重新送出。
- 缺口 2「本輪 JD 變更」、完整鍵盤走查、兩項模型依賴 e2e 與真模型品質等仍未完成；訊息 Markdown 呈現不在本輪變更範圍。

後續：缺口 1 的 UI 已接線；Demo 後端已載入新 API，真來源徽章與訪談回查已唯讀確認。包含未知狀態、跨頁 hint 與已開啟草稿鎖定的修正／限制統一見[發現入口後續證據](t09-current-turn-discovery.md#ui-承接與多分頁取捨2026-09-30)，不將前文歷史驗證改寫成完整跨瀏覽器旅程已通過。
