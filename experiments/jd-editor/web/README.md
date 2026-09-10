# 隔離 JD 工作畫面

本機 3001 的文件入口與 `/workspace/{document_id}` 使用同頁訪談及唯一 Plate 工作稿，接同一個 8091 AnalysisService／catalog／PostgreSQL JD ports。這不是 production 3000／8001 的入口。

在上層 `experiments/jd-editor` 用隔離 Node 22.23.2 啟動：

```text
npm ci --ignore-scripts
npm run dev -w @caliburn/jd-editor-web
```

`predev`／`pretest`／`prebuild` 先建立共享 native package 的正式 dist。API origin 固定 `http://127.0.0.1:8091`；不讀 production Web 契約。Next 16.3.3 的 compiled React／RSC 與宣告 React 19.2.4 分開驗收，不做 override。

文件身分、metadata version、create request key 與 run-by-request 都由實際 API Pydantic 型別生成。JD DTO 來自同一 active v2 SSOT；codegen 不啟動服務。人工保存走完整 value 的 deterministic port；模型仍只有既有三個 JD factory tools。

一般 dirty 與未送聊天只在頁面 buffer；離頁要求保存或明示捨棄，瀏覽器關閉提示只是盡力保護。只有已送出請求以新的 localStorage namespace 保留原 key／exact payload。cache 寫入失敗不送；重開 manual 先同 key 對帳，run 先只讀 lookup、不自動 POST/resume。unknown 不新建身分；confirmed stale／failure 保留候選供查看、複製或明示捨棄，候選不覆 current。

「請 AI 改這段」要求當時的原生 selection；保存期間凍結輸入且保留同 candidate 的原生 range，保存後核對 range 未變才附同 base 送出。選取遺失或 API 拒絕會保留原問句。可明示改為純聊天。新版只在乾淨同 baseline 套官方 operations/history batch；其他情況重建 editor 並告知 session history 重設。exact before／after、computeDiff、歷史與來源均為唯讀。

零付費 browser fixture 在 `analysis-agent/tests/jd_browser_server.py`，組合實際 API／AnalysisService／官方 Saver/Store／原工具。transport 永遠是固定 MockTransport，沒有 live fallback。啟動前明確以 `scripts/setup_jd_web.py` 對專用 `q019_jd_app_20260910` 做 additive metadata setup；`create_all` 本身不會升級既有表格。需要外部提供 `Q019_TEST_DATABASE_URL`，不可使用 production DB 或把連線字串寫入檔案。

```text
npm run check-codegen -w @caliburn/jd-editor-contract
npm run test -w @caliburn/jd-editor-web
npm run typecheck -w @caliburn/jd-editor-web
npm run lint -w @caliburn/jd-editor-web
npm run build -w @caliburn/jd-editor-web
```

browser scripts 使用 Playwright 1.61.0 的既有 Chrome headed channel，保留 actual request／保存值／AX／畫面。CDP composition 不等於 Windows 真人 IME；OS 候選視窗、自然模型品質及完整取消／原生 worker 生命週期仍需各自後續驗收。完整更名／封存管理 UI 在 P5；這裡只提供共同 API 與封存唯讀入口。

Task4 review fix1：只接受原 request key 匹配的明確未 admission 回覆來解除候選 unknown，其他錯誤仍需原鍵對帳。尚待處理的候選阻止一般 current save 覆寫唯一 cache，員工明示捨棄後才允許新提交。create recovery 在列表 GET 前獨立檢查，未檢／讀失敗／有未解記錄均阻止新 key，handler 再次核對。受控 clipboard 驗證須先核實 DOM range 與「已選取正文」訊號、實際 clipboard 原文，再驗必要 marks／結構／新 ID／保存重開；初輪只核段數與 ID 的綠燈不足以證明複製保真。
