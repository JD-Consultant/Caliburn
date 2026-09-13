# JD 六章手動管理畫面

此 Web 是隔離關聯式 App 的 RS-3 第一段實作。可建立、選擇、更名、封存／恢復文件，管理六章欄位、職責、任務、多成果、多要求及共用知識技能；可看實際歷史差異。AI 訪談、來源原文回查、整份還原與整輪 JD 撤回仍待接合。不是正式產品切換或完整交付。

## 執行

使用 Node 24.19.0 與本目錄 lock。API 先依[受管理設定](../../../docs/specs/2026-09-13-jd-managed-configuration-slice.md)明示初始化一次；一般開啟只使用原設定，不能重做 init。後端設定的允許來源必須包含 `http://127.0.0.1:3002`，API port 以該設定為準。

在已設定的獨立 API 程序執行 `uv run --frozen python -m jd_relational serve`；後端不開 reload。然後在本目錄：

```powershell
npm ci --ignore-scripts --no-audit --no-fund
# 例子；請填原設定中的本機 API origin。
$env:JD_API_ORIGIN='http://127.0.0.1:8767'
$env:NEXT_TELEMETRY_DISABLED='1'
npm run dev
```

開啟 `http://127.0.0.1:3002`。`JD_API_ORIGIN` 只是可公開的本機服務位址，由動態 Server Component 傳給畫面；不可放資料庫密碼或模型金鑰。未設定時顯示未連接服務，沒有猜測另一個 API 的預設值。Web 不直接讀資料庫、不保存正式 JD 副本、不引入旧實驗程式。正式 build 使用 `npm run build`，以相同公開 origin 執行 `npm start`；日常圖形啟停入口尚未完成。

## 使用與保存

- 既有文字欄位可換行，停止輸入後自動保存。新增／完整修訂／移動／刪除等表單按「完成」後整次保存；未完整任務可只填已知內容。
- 成果與要求是任務底下兩份獨立清單。知識技能定義可由多項任務共用；定義區顯示影響的任務。
- 刪除職責保留任務及其內容；確認畫面可同時補上仍適用的範圍。刪除任務會刪除其成果、要求與引用，共用定義保留。後端統一檢查規則。
- 未提交輸入與原保存請求保存在此瀏覽器 IndexedDB。關頁後重開可比較並繼續；未知結果先查回同一次操作，不自行發新身分重做。瀏覽器清除／配額問題不等於資料庫備份。
- 同一瀏覽器兩個分頁開同份文件，第二頁唯讀。不同瀏覽器／程序的正式寫入仍由後端保護。
- 歷史在同畫面查看；差異由實際保存前後內容產生。來源識別可查看，來源原文與 AI 摘要尚未接線。

## 驗證與責任

```powershell
npm run typecheck
npm test
npm run build
```

受限環境若 Node test worker 無法建立，可用官方 `--test-isolation=none` 跑純測；不代表已驗證 TSX 畫面。Next build 必須保留型別檢查，不能為略過程序限制而關掉。真瀏覽器、API、PostgreSQL 的分層結果、已知缺口與重現流程見[本次結果](../../../docs/specs/2026-09-13-jd-manual-ui-and-browser-drafts-slice.md)。

`src/lib/api.ts` 使用既有生成型別與七份 Schema 驗證回覆；`session.ts` 協調本文件的候選／原請求交接；`drafts.ts` 使用 idb 原生短交易。業務規則和保存只在共用 Python 服務，UI 不解碼 ref、不重算關係約束。套件版本與授權見[UI 前置](../../../docs/specs/evidence/2026-09-13-jd-react-ui-preflight.md)。
