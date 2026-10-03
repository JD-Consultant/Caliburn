# 聊天 Controller／JD 交接與畫面接線審查

- 日期：2026-09-13；Topic：JD-R002／RS-4 局部。延續 [API 獨立窄審](api-review.md) 與 [UI 前置研究](ui-preflight.md)。
- 本次 UI 唯讀範圍：[ChatPanel.tsx](../../../../experiments/jd-relational-app/web/src/components/ChatPanel.tsx)、[DocumentWorkspace.tsx](../../../../experiments/jd-relational-app/web/src/components/DocumentWorkspace.tsx)、[HistoryPanel.tsx](../../../../experiments/jd-relational-app/web/src/components/HistoryPanel.tsx)。不重審另有 writer 修改的 Workspace；僅核其既有 dataset／document key 對卸載界線的影響。
- **目前結果：本次兩項具體顯示／回合配對 P2 已修，追加獨立複核確認 UI-R01／UI-R02 CLOSED，未見新增 P1／P2。**Controller 新 B 修正為本審查者撰寫，下面明確列為自修與本機反例；獨立結論及實際元件呈現證據由另一位 reviewer 記於 [最後原回合／輸入狀態窄複核](final-run-label-review.md)。
- 0 provider、0 DB、沒有啟動瀏覽器／宿主；沒有新增 framework 或通用讀取／重試引擎。畫面互動、IME／focus 及新瀏覽器旅程另驗，不能由靜態接線審查代證。

## 1. 前次 Controller／bridge 四項 P2 的閉合追溯

這四項為先前另一 reviewer 的獨立反例，本節整理修後事實，不重新指派新需求或改寫原測試紀錄。

| 反例 | 已修的具體責任 | 獨立反例來源 |
|---|---|---|
| 初次 history 失敗且沒有本機 pending，按刷新只清錯誤而未重查 | `ChatController.refresh` 共用最新頁選 run 流程，真讀一次 latest，再以本機原請求優先／否則 `anchor_run_id` 查回。不是對 target=null 的空動作 | [chat-controller-review.test.ts](../../../../experiments/jd-relational-app/web/tests/chat-controller-review.test.ts) `explicit refresh recovers an initial history failure…` |
| 已讀 terminal A 後，刷新仍永久釘 A，看不到後來 B | 明示 refresh 重取最新固定 window；新 anchor 完整替換，允許再前翻舊頁。背景 poll 只查目前原 run；新保存原話／reply 未可見時才條件式取最新訊息 | 同檔 `explicit refresh rediscovers the current native anchor…`、`a new complete reply replaces loaded older windows…` |
| 舊 run 的延遲 observation 新鮮讀取，覆蓋較晚已確認人工 revision | [session.ts](../../../../experiments/jd-relational-app/web/src/lib/session.ts) `chatObserve` 先發布 gate，沿既有 `flight` 等待／追蹤接收，再取得目前 JD；未存內容遇到版次不同要比較，不以舊讀取結果蓋掉較晚保存 | [chat-handoff-review.test.ts](../../../../experiments/jd-relational-app/web/tests/chat-handoff-review.test.ts) `delayed old-run chat observation cannot replace a newer confirmed manual revision` |
| 一次本機保存錯誤使聊天候選只留 RAM，明示恢復仍無法完成保存 | `resume` 明確處理仍在 RAM 的 chatCandidate 並排入同一本機 queue；成功後清相符候選，不連帶丟掉原話，不借 JD 捨棄動作刪聊天 | 同檔 `explicit recovery retries RAM-only chat candidate…` |

主代理先前確認這組 **34 PASS**（Controller 29＋獨審 Controller 3＋bridge 2）。本次因 §2 新增四個同源反例，重新執行同三檔得到 **38 PASS**；不是把不同執行的數字加成一次驗收。

## 2. 本次接線發現、修正與來源分界

### UI-R01／P2：新 B 原請求未知時誤沿用 A 的完成與差異

**修前情境：**先完成 A，送出 B 並已在本機保存原請求，B POST 回覆遺失。Controller 當時只換 `runId`，仍保留 `run=A completed`；原 ChatPanel 直接顯示 `chat.run`，於是 B 的本機原話旁出現 A 的「本輪完成」及可能的已保存修改入口。

零 provider 記憶體 probe 精確重現：`selected_run=B`、`displayed_run=A`、`displayed_status=completed`、`error=response_unknown`、`pending_run=B`。這是程式反例，沒有聲稱曾在真瀏覽器發生。

**修正：**

- Controller 由原作者（亦即本文件整理者）新增固定 `selectRun`，切新原請求／查新 target 時先清除不屬該 run 的結果並同步通知；send、status（含 retry）、cancel、recover 及 latest 選擇共用。回覆未知仍只保留原 B request，不新生 key／ref，也不自動重送。
- 主代理修 [ChatPanel.tsx:24](../../../../experiments/jd-relational-app/web/src/components/ChatPanel.tsx#L24)：`chat.run.run_id` 須等於 `chat.runId`；有本機原請求時也須同原 run，才顯示狀態及 committed 差異。即使收到不一致的 controller snapshot，畫面不把 A 當 B。
- [chat-session.test.ts](../../../../experiments/jd-relational-app/web/tests/chat-session.test.ts) 新增新 B POST 前／回覆遺失、不同原請求 retry GET 失敗、cancel／recover 不同 target 的四個反例。首輪 **29 PASS／4 FAIL**；有限修正後同檔 33 個案例均通過。

**證據分界：**Controller 是自修，不列成作者自己的獨立 PASS。ChatPanel 為主代理修改，本審查者只讀核對其 matching 條件；另一 reviewer 已完成 Controller／Panel 的 [追加獨立複核](final-run-label-review.md)，確認兩項 P2 關閉。

### UI-R02／P2：已確認保存的原話不在可見頁，仍被說成待接收

**修前情境：**原 run 已有 `input_state=saved`，但最新 50 條不包含該 Human，或補讀 history 失敗。原 Panel 僅因可見訊息沒有 Human 就把本機原文卡標成正在確認接收，和已知保存事實矛盾。

**修正及唯讀複核：**[ChatPanel.tsx:42](../../../../experiments/jd-relational-app/web/src/components/ChatPanel.tsx#L42) 仍保留使用者可讀的原文，標題改依已匹配原 run 的 `input_state`：saved 為「原話已保存；目前對話頁未顯示這段原文」；not_saved 說明尚未保存；沒有相符保存證據才說待確認。沒有用頁面缺列推定資料未保存，也沒有把本機草稿當新增的原始對話 authority。

## 3. 修後 TSX 接線核對

| 接點 | 核對結果與實際限制 |
|---|---|
| 同頁唯一 JD | DocumentWorkspace 只掛一個原 `JdEditor`；ChatPanel 是純 public Human／assistant text 與操作入口。沒有另一份可編輯 JD、隱藏接受／核准流程；聊天文字不被解析成正文或可執行 HTML |
| 建立／卸載 | DocumentWorkspace effect 在已取得 JD view 後建立一個 ChatController；cleanup 先 dispose observer，再 dispose 原 JdSession。JdSession disposed 後不再 emit，Controller 抑制晚回與 timer。呼叫者既有 key 綁 api origin＋dataset＋document，使切文件重建對應 owner；沒有新增第二個 Web Lock／DB owner |
| busy 與手稿交接 | 送出／取消／恢復／更多／刷新由 controller 的明示按鈕觸發；busy 防重入。Composer 在首個交接／封存／無 row 時停用，AI 進行中可保留下一段文字；能否送出沿 `snapshot.chatReady`，能否手改沿 `snapshot.readOnly`。TSX 不因 spinner 結束自行解除 App gate |
| 離頁提示 | `dirty`／`submitting`／`chatSaving` 未完成時保留 beforeunload／切頁保護。已持久的原 request 可留給重開查回，不把關頁當取消／已停止；此處不宣稱純 UI 能提供 OS／SQL 停止證明 |
| 原操作差異 | ChatPanel 只從 matching run 的正式 committed results 取原 `change_ref`，交 DocumentWorkspace 開同頁 HistoryPanel。面板讀該原 change 的 immutable base/result refs，再用普通 history read 取兩側完整正文；沒有讓 Web 生成差異、猜 operation 或拿較晚 current 拼接原操作 |
| 差異切換／晚回 | HistoryPanel 以 selection generation 阻止較早選取或卸載後的結果取代新選擇；revision 列表有 effect cleanup。新點擊相同 change 也會推進 selection sequence，不靠元件重掛碰運氣 |
| 來源呈現 | HistoryPanel 保留確切來源識別、basis 與順序，明示原話回查尚未接合；沒有偽造可讀來源或將 technical ref 當使用者原話。查看／收起不寫資料 |
| 無自動重送 | mount／refresh／poll 皆走讀取；POST start 只在送出或明確 retry 的原請求分支。取消／恢復只由明示動作，沒有 effect 自動繼續模型；unknown、not_found 不被 TSX 改成已失敗／未保存 |
| 完成界線 | 畫面目前是逐次已保存 operation 的入口，不是完整 CV-01：目前稿具名標记、整輪 S→E 淨差異仍待接合。HR-02 撤回仍未落地。沒有用「停止本輪」代做撤回，也沒有因本次 PASS 宣稱自然 AI／來源／Memory／完整 App 完成 |

已讀本地 web/AGENTS 及目前 Next bundled Server／Client Components 文件；這次沒有為三個元件重新比較框架或引入新庫。

## 4. 本次實際驗證

以 bundled Node **24.19.0**，在 `experiments/jd-relational-app/web` 執行：

```powershell
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' --experimental-strip-types --test-isolation=none --test tests/chat-session.test.ts tests/chat-controller-review.test.ts tests/chat-handoff-review.test.ts
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' node_modules/typescript/bin/tsc --noEmit --incremental false
```

結果：**38 PASS／0 FAIL，276.082 ms；完整 Web 型別檢查 PASS。**這次真實單次 38＝33 個 Controller 案例＋3 個先前獨立 Controller 案例＋2 個 bridge 獨立案例。未重新執行、不混合 API 60、draft tests、Python／PG 或瀏覽器數字。

上述是記憶體 API／本機 store port doubles 與真業務轉換接點，TSX 本次採靜態接線核對。它們不代證原生 IndexedDB、React DOM 事件、IME、焦點、窄畫面或真瀏覽器保存／重開旅程；這些須在主代理後續驗收中分開記錄。

追加獨立 reviewer 另外執行同三檔，得到 **38 PASS／0 FAIL，272.9204 ms**；另以本版 Next bundled Babel 與實際 React／MUI `renderToStaticMarkup` 核對 ChatPanel 的 A／B 錯配及三種 input_state 等 **7 個分支 PASS**。這兩次執行與本節作者的 38 PASS 各自記錄，不相加為單次驗收；七個分支是實際元件的靜態 HTML 呈現，仍不是瀏覽器互動。完整方法、限制與驗收腳本首次失敗見 [獨立報告 §3／§4](final-run-label-review.md#3-審查者實際驗證)。
