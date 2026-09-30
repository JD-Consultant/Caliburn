# T09 瀏覽器旅程：腳本化模型上的處理中、暫停、取消與重連（2026-09-30 恢復後）

T09 的最後缺口是「A 已准入」時的畫面行為：先前 17 項 e2e 有 2 項因隔離後端沒有模型而無法驗（[T09 UI 改版 §3](t09-ui-redesign.md#3-驗證)）。本次用**最小**的離線腳本化模型補上，不擴成評測或模擬平台；模型品質仍由 T14／T16／T17 的真模型驗證，本頁不宣稱任何品質結論。

## 做了什麼（刻意保持小）

- `apps/api/tests/fixtures/scripted_model.py`（約 240 行）：用 httpx `MockTransport` 在真 SDK 路徑上回覆 token 計數與串流回應。行為只由員工輸入文字決定：`職稱：X；主管：Y…` 讓 A 呼叫 `revise_jd_profile` 寫入並回覆一個問題；`[[hold]]` 讓本輪最後一個回應卡住等測試放行（有職稱資料時，先讓工具步驟寫入候選再卡住）；`[[reject]]` 回 400 已知拒絕。`tests/unit/test_scripted_model.py` 8 案驗它在產品自己的 `create_response`／串流消費路徑上行為正確（含卡住中被取消不遺留許可）。
- `apps/api/tests/fixtures/scripted_backend.py`：只替換 SDK 的 HTTP transport，其餘用真的 `create_app`、PostgreSQL、Graph 與 supervisor；掛上僅此程序才有的 `/__script/state`、`/__script/release`；只接受名稱以 `_test` 結尾的資料庫。不改任何 production 程式。
- `apps/web/tests/e2e/consultant-journey.spec.ts`：4 個旅程。

## 實測結果

真 Chromium 153、真後端＋真 PostgreSQL（隔離 schema `e2e_journey`）、Vite 5174：

| 旅程 | 已驗行為 |
|---|---|
| 一輪訪談 | 送出後顧問答覆與「已完成並保存」出現；JD 顯示職稱與主管；重開後答覆與 JD 相同且模型只被呼叫 2 次；回看該答覆可見公開訊息與「這輪 JD 變更」；正式版 PDF 匯出為 `%PDF-`；畫面不含加密推理內容與工具名稱；無瀏覽器錯誤 |
| 處理中 | 卡住時即時看到公開 commentary、「顧問處理中」、JD 唯讀並說明原因；重開與另一分頁都找回同一處理且**不重送輸入**；暫停先顯示「等待安全點暫停」，放行後停妥為「已暫停」；繼續後完成同一答覆，**模型請求數不變**，JD 恢復可編輯 |
| 處理中取消 | 候選預覽顯示「JD 候選預覽」且標示尚未正式保存，正式 JD 與 PDF 仍是正式版；取消後候選消失、正式職稱仍空、原輸入未列入正式訪談，「取回原文編輯」把原文放回輸入框 |
| 模型拒絕 | 顯示「未完成」與原輸入未列入正式訪談的說明；之後可主動開始下一次訪談並完成 |

整套 e2e **21 passed（1.2 分鐘）**：既有 17 項（含先前無法驗的 `jd-profile`「A 已准入拒絕人工修改」與 `jd-work`「A 已准入不能新增人工任務」）加新增 4 項。第一次整套跑曾有 1 項 `jd-context` 失敗，原因是測試：API 已是新順序但畫面尚未重繪就點到舊的第二項；加一行等畫面更新後，整套與單獨都通過，不是產品問題。前端 Prettier、ESLint、`tsc --noEmit` 通過；後端 Ruff／format 通過。

## 環境與執行

```powershell
# 1) 隔離 schema（同 backend README 的初始化，用 _test 資料庫）
$env:CALIBURN_DATABASE_URL = 'postgresql://caliburn_test@127.0.0.1:55439/caliburn_t01_test'
$env:CALIBURN_DATABASE_SCHEMA = 'e2e_journey'
./.venv-target/Scripts/python.exe -m alembic -c alembic.ini upgrade head          # cwd apps/api
# 2) 腳本化後端（另設 CALIBURN_PDF_FONT_PATH／CALIBURN_PDF_CHROMIUM_PATH 才有 PDF；CALIBURN_DEV_ORIGIN 對應第二組前端）
./.venv-target/Scripts/python.exe -m tests.fixtures.scripted_backend --port 8101   # cwd apps/api
# 3) 第二組前端 5174（CALIBURN_API_PROXY=http://127.0.0.1:8101），再執行
$env:CALIBURN_E2E_BASE_URL = 'http://127.0.0.1:5174'
$env:CALIBURN_E2E_SCRIPT_URL = 'http://127.0.0.1:8101'
node node_modules/@playwright/test/cli.js test                                     # cwd apps/web，Node 24
```

沒有設 `CALIBURN_E2E_SCRIPT_URL` 時，新旅程 skip；skip 不代表通過。本機 `corepack`／pnpm 簽章驗證失敗，因此直接用 Node 24 呼叫 `node_modules` 內的執行檔。

## 未驗與限制

腳本化模型是合成替身：不證明模型品質、provider 接受性或真實延遲；沒有捕捉真模型完成前的逐片段畫面（真實串流仍只有伺服器端保存與離線事件測試）；只跑 Chromium，沒有完整鍵盤／焦點走查與跨瀏覽器；沒有長訪談（200+ 則）效能；Demo 8100／5173 未動。這些不屬本切片，也不是核心分析效果的阻擋項，留 T15／T17 依需要驗。
