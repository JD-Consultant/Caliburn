# JD 六章管理與同頁訪談畫面

此 Web 是新關聯式 JD App 的管理畫面。可建立、選擇、更名、封存／恢復文件，管理六章欄位、職責、任務、多成果、多要求及共用知識技能；同頁訪談已接正式 A 顧問、原回合查回、實際修改、來源原話、整輪差異與只撤回本輪 JD。2026-09-22 已以同一 production build、API、PostgreSQL 與真實 OpenRouter／Luna 完成瀏覽器來源查看；較早完整旅程也已驗證撤回後對話、來源與 Memory 保留。這些是受控樣本的實測證據，不等於所有長期訪談品質或錯誤分支都已驗畢。

## 執行

使用 Node 24.19.0、pnpm 12.5.1 與根目錄 lock。API 先依[受管理設定](../../../docs/specs/2026-09-13-jd-managed-configuration-slice.md)明示初始化一次；一般開啟只使用原設定，不能重做 init。後端設定的允許來源必須包含 `http://127.0.0.1:3002`，API port 以該設定為準。

日常直接在 repository 根目錄執行：

```powershell
pnpm install --frozen-lockfile
pnpm dev
```

開啟 `http://127.0.0.1:3002`。根啟動器從受保護 App 設定取得 `JD_API_ORIGIN`；它只是可公開的本機服務位址，不含資料庫密碼或模型金鑰。未設定時 fail closed，不猜測另一個 API。Web 不直接讀資料庫、不保存正式 JD 副本、不引入舊架構程式。正式 build／serve 使用根目錄 `pnpm build`／`pnpm start`。

## 使用與保存

- 既有文字欄位可換行，停止輸入後自動保存。新增／完整修訂／移動／刪除等表單按「完成」後整次保存；未完整任務可只填已知內容。
- 成果與要求是任務底下兩份獨立清單。知識技能定義可由多項任務共用；定義區顯示影響的任務。
- 刪除職責保留任務及其內容；確認畫面可同時補上仍適用的範圍。刪除任務會刪除其成果、要求與引用，共用定義保留。後端統一檢查規則。
- 未提交輸入與原保存請求保存在此瀏覽器 IndexedDB。關頁後重開可比較並繼續；未知結果先查回同一次操作，不自行發新身分重做。瀏覽器清除／配額問題不等於資料庫備份。
- 聊天原話和原請求也由同文件的候選保存機制保護。送出前先保存手改；未完成表單需先完成或取消。AI 執行時 JD 暫停手改，可輸入下一段，下一段不自動送出。Enter 換行，按鈕送出。
- 原回合狀態、原話是否保存及 JD 修改結果分別呈現。初頁顯示最新已保存的公開對話，可往前載入；關頁只停止畫面觀察，不等於取消 AI。連線不明後停止自動觀察，明示查回原回合；不換身分重送。
- 同一瀏覽器兩個分頁開同份文件，第二頁唯讀。不同瀏覽器／程序的正式寫入仍由後端保護。
- 歷史在同畫面查看；差異由實際保存前後內容產生。JD 修改的來源入口可回到 canonical 訪談原話；UI 不自行解碼或重算內部 ref。Memory 與 compaction 摘要不是可由使用者撤回或直接編輯的 JD 內容。

## 驗證與責任

```powershell
pnpm --filter @caliburn/jd-relational-web typecheck
pnpm --filter @caliburn/jd-relational-web test
pnpm --filter @caliburn/jd-relational-web build
```

受限環境若 Node test worker 無法建立，可用官方 `--test-isolation=none` 跑純測；不代表已驗證 TSX 畫面。Next build 必須保留型別檢查，不能為略過程序限制而關掉。2026-09-22 最新驗證為 **310 tests passed**、TypeScript 通過、production build 通過；真瀏覽器／API／PostgreSQL／Luna 證據見[元件與完整 App 驗收](../../../docs/specs/evidence/2026-09-22-jd-component-first-acceptance.md)。聊天旅程中曾有 fetch 中斷，明示查回後完成且 DB 一致；限定重現的連線原因仍未定位，不宣稱所有瀏覽器故障通過。

`src/lib/api.ts` 使用生成型別與八份 Schema 驗證回覆；`session.ts` 協調本文件的人工／聊天候選與原請求交接；`drafts.ts` 使用 idb 原生短交易，舊 v1 列只在 claim 時驗證升成 v2。`chat-session.ts` 只負責觀察及明示控制，不建立第二份持久聊天。業務規則和保存只在共用 Python 服務，UI 不解碼 ref、不重算關係約束。套件版本與授權見[UI 前置](../../../docs/specs/evidence/2026-09-13-jd-react-ui-preflight.md)及[聊天前置](../../../docs/specs/evidence/jd-relational-chat-web/ui-preflight.md)。
