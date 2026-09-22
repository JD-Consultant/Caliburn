# 整輪差異公開契約與 Web client 驗證

- 日期：2026-09-13；JD-R002／CV-01 局部。這是作者的契約與用戶端實作結果，不是 UI 獨立審查或整體 CV-01 驗收。
- 範圍：[chat HTTP SSOT](../../../../experiments/jd-relational-app/contracts/jd-chat-http.schema.json)、[標準生成器](../../../../experiments/jd-relational-app/scripts/generate_contract.py)、[Web API client](../../../../experiments/jd-relational-app/web/src/lib/api.ts)。本組零 DB、零 provider、未啟服務；不增加模型輸入或資料表。

## 1. 實際交付

新增 `ChatRunChangePage`：固定 capture、run／document／dataset、settled／unconfirmed、連續性、captured operation count、首末歷史 refs、完整差異 records 及分頁資訊。全部欄位 required，closed object；`continuous` 必有操作及首末 refs，`none` 的操作數為零，非連續／空集合不冒充單一淨比較。差異 records 沿既有 `jd-read.schema.json#/$defs/ChangeReadRecord`。

標準生成後，Python 是 flat `ChatRunChangePage` BaseModel；TypeScript 同名 export 指向 `ChatRunChangePage1`。十八個生成輸出只有 `chat_http.py` 與 `jd-chat-http.ts` 內容改變；沒有手改生成檔。

`JdApi.runChanges(id, runId)` 只 GET 原 run 的 changes 路由，逐頁固定 capture、範圍、連續性、端點與總數，核 offset、cursor 進展及 change group 完整性，再回傳完整頁。它不計算 diff、不產新操作、不自動重送 mutation。

## 2. 首敗及修正

| 階段 | 實際結果 | 原因與處理 |
|---|---|---|
| 新 Python 反例先跑 | 63 FAIL，0.89 秒 | 新契約 root 尚不存在 |
| 新 Web 反例先跑 | 42 FAIL | `runChanges` 尚不存在；該次輸出截斷，不補造耗時 |
| 生成後 Python 接合 | 155 PASS／1 FAIL，14.92 秒 | 測試 fixture 用工廠重建合法 `none`，沒有構成預期矛盾；改為對既有 continuous payload 覆寫欄位 |
| Web 接合首輪 | 33 PASS／9 FAIL，798.2294 毫秒 | AJV strictTypes 要求條件分支的 `minimum`／`maxItems` 同時宣告型別；補正式 schema 的 explicit type。當時部分負例因較早編譯失敗而通過，未將其當完成 |

## 3. 最後實跑結果

以下是各組各自執行結果，不相加成全 Web 或整個 App 通過數字。

| 檢查 | 實際結果 |
|---|---|
| [新 run-change 契約](../../../../experiments/jd-relational-app/tests/test_run_change_contract.py)＋[原 chat 契約必要適配](../../../../experiments/jd-relational-app/tests/test_chat_contract.py) | 157 PASS，15.24 秒；64 新案例＋93 既有／適配案例 |
| [新 Web client](../../../../experiments/jd-relational-app/web/tests/run-change-api.test.ts) | 42 PASS，1231.0988 毫秒 |
| 原 `api.test.ts`＋`chat-api.test.ts` 回歸 | 98 PASS，1814.0488 毫秒 |
| 全組標準生成器 `--check` | PASS：Python／TypeScript 與來源一致 |
| API 與新測試的 strict scoped TypeScript | PASS |
| 所有 owned 變更的 diff／空白檢查 | PASS |

新 client 案例含完整多頁、空集合／改回無淨差異／不連續、capture／run／dataset 錯配、錯誤分頁、重複 cursor、缺少／重複／錯序 group、完整 oversized 多行內容、晚回 dataset 變化及網路未知結果不重送。

Python 沿 frozen uv；Web 使用已核 Node 24.19.0，路徑 `C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe`。沒有升級依賴。全 Web 型別檢查曾遇另一 writer 尚在寫入的 `HistoryPanel.tsx` 暫態語法錯誤，因此本作者只報自己的 scoped PASS；主代理整合結果另記。

## 4. 必須保留的生成邊界

現鎖定的 `datamodel-code-generator` 保留 flat 欄位，但不生成 `allOf` 中 `if`／`then` 的語意驗證。新測試明確記錄：continuous count 為零時，正式 JSON Schema 拒絕，生成 DTO 及其再輸出的 JSON Schema 仍接受。這不是放寬公開契約的依據；來源條件未刪除、未手改 DTO。

主代理採現有 `Draft202012Validator`＋`referencing.Registry` 從正式來源補 server 出站條件，OpenAPI 也須保留來源條件。此 root 的最小 registry 只有 `jd-chat-http.schema.json` 與 `jd-read.schema.json`；本次另以離線 probe 核合法 none 接受、none count 為一拒絕。隔離 App 已含 contracts；未來正式打包必須包含同一來源資源，不以另一份手寫 schema 取代。

本結果不證明 SQL capture 完整性、native run 歸屬、真瀏覽器標記／鍵盤操作、HR-02 撤回、自然模型品質或完整 App。UI 的獨立核對另見 [UI review](ui-review.md)。
