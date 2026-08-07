---
title: 職務分析 Web 使用者體驗流程
audience: agent-primary(也給人)
scope: apps/web /workspace(畫面與旅程視角)+ apps/api job_analysis routes(對應請求)
updated: 2026-08-07
---

# 職務分析 Web 使用者體驗流程

> **這份文件回答「員工在瀏覽器實際會做什麼、按下去發生什麼」**——依畫面與點擊順序整理,
> 不是依 backend 元件。元件權責、domain 不變量、identity gate 等技術細節住
> [`task-analysis-engine.md`](./task-analysis-engine.md),這裡只連結、不重複。
> **living:改一個畫面的行為,同 commit 更新本檔對應那段。**

## 0. 唯一入口

`/`(`apps/web/src/app/page.tsx`)直接 `redirect("/workspace")`。**這是員工唯一會走到的路徑**——
沒有登入頁、沒有角色選擇。見 §5「已退役/別做」。

## 1. 畫面地圖

| 路徑 | 元件 | 這個畫面做什麼 |
|---|---|---|
| `/workspace` | `DocumentLibrary` | 列出本機保存的所有職務說明書;建立新的、改名、開啟既有的 |
| `/workspace/{document_id}` | `ConsultationWorkspace` | 單一文件的工作區:左欄 AI 顧問訪談,右欄 Current JD 四段編輯,頁首匯出 |

一次只開一份文件;沒有分頁、沒有背景多開。

## 2. 文件庫(`/workspace`)

| 員工動作 | → 請求 |
|---|---|
| 畫面載入 | `GET /api/v1/job-analysis/documents` → 列表(標題、`task_count`、`updated_at`) |
| 輸入職務名稱 → 按「建立文件」 | `createDocument(title)`:前端先產生 `crypto.randomUUID()` 當 `document_id`,呼叫 `PUT /api/v1/job-analysis/documents/{document_id}`(body `{title}`)→ 成功後 `router.push` 進 `/workspace/{document_id}` |
| 按文件卡片的鉛筆圖示 → 改標題 → 「儲存名稱」 | 同一支 `PUT /api/v1/job-analysis/documents/{document_id}` |
| 按「開啟」 | 純前端導覽到 `/workspace/{document_id}`,不發請求 |

**同一支 `PUT` 身兼「建立」與「改名」**(同 ID 存在則改名、不存在則建立)。這支路徑**不走
authority 交易**:不寫 Journal、不 bump `authority_generation`,只是文件 metadata。空文件庫顯示
「目前還沒有文件」提示卡,不擋任何操作。

## 3. 開啟文件(`/workspace/{document_id}`)

進場先發兩個查詢(`ConsultationWorkspace`／`JdHeaderForm`／`DutyEditor`／`TaskEditor`／`OpksEditor`
各自掛載,但共用同一份 `documentQueryOptions` 快取):

- `GET /api/v1/job-analysis/documents/{document_id}/consultation` → 對話紀錄、`active_question`、
  Task Proposal、OPKS Proposal
- `GET /api/v1/job-analysis/documents/{document_id}` → `jd_header`、`readiness`、`duties`、`tasks`、
  `opks_items`(右欄四段編輯器都讀這支)

版面固定兩欄(`lg` 以上並排,窄螢幕疊起來):**左欄訪談,右欄 Current JD**,同頁可見、不用切換分頁。
頁首有「返回文件庫」(帶 unsaved-changes 攔截,見 §6)與「匯出」按鈕(見 §4.5)。

### 3.1 左欄:AI 顧問訪談(`ConsultationPanel`)

1. **對話紀錄**是唯讀捲動區,依 `speaker` 左右對齊呈現(顧問靠左、我靠右)。
2. **回覆輸入框**:`placeholder` 顯示 `active_question.text`(顧問這輪在問什麼);
   Enter 換行、**Ctrl/Cmd+Enter 或按「送出」**才真的送出。
3. 送出 → `POST /api/v1/job-analysis/documents/{document_id}/turns`
   (body `{text}`,帶 `Idempotency-Key: crypto.randomUUID()`)。送出期間輸入框整體 disabled,
   畫面顯示「顧問正在分析這段內容…」(`aria-live="polite"`)。
4. 回應**就是**新的 `ConsultationView`,直接寫回查詢快取(不必重打一次);同時
   `invalidateQueries` 觸發 `GET /{document_id}` 重取(因為 `readiness`／`duties`／`jd_header`
   不在 consultation 回應裡,見下方「不變量」)。
5. 失敗(網路、`consultant_unavailable`…)時**原文保留在輸入框**,訊息提示「原文已保留,可直接
   重試」——重試會沿用**同一把** `Idempotency-Key`,不是重新產生(見 §6)。

**待確認建議**(Task Proposal)與**待確認的 O/P/K/S 建議**(OPKS Proposal)各自成一區,只顯示
`pending`／`deferred` 的提案(其餘進「歷史建議」摺疊區)。同一輪 AI 產生的多筆 OPKS 建議會
分組顯示(`operationId` 分組),提示「同一輪產生的建議」。

**Task Proposal 卡片**(`ProposalCard`):

| 員工動作 | → 請求 |
|---|---|
| 「接受」 | `POST …/proposals/{proposal_id}/decisions`,body `{decision: "accepted"}` |
| 「修改文字」→ 改文字 →「儲存並接受」 | body `{decision: "edited", edited_jd_after: […]}`(**只能改 `statement` 文字**,`display_order` 等欄位不可改) |
| 「稍後處理」(僅 `pending` 狀態出現) | body `{decision: "deferred"}` |
| 「不採用」 | body `{decision: "rejected"}` |

卡片本身顯示「目前內容」(`jd_before`,過濾掉 `value === null` 的列——那代表「還不在 JD 裡」)與
「建議內容」(`jd_after`,`value === null` 代表「建議移除」);「查看相關原話」展開員工當初怎麼說。
`stale_reason`／`rejection_reason` 有值就直接顯示在卡片上。

**OPKS Proposal 卡片**(`OpksProposalCard`,多一種決策):

| 員工動作 | → 請求 |
|---|---|
| 「接受」 | `POST …/opks-proposals/{proposal_id}/decisions`,body `{decision: "accepted"}` |
| 「修改文字」→「修改後接受」 | body `{decision: "edited", edited_text}` |
| 「暫時無法判斷」 | body `{decision: "unknown"}` |
| 「不採用」→ 填原因 →「確認不採用」 | body `{decision: "rejected", reason}`(必填,不可空白送出) |

兩種決策 mutation 成功後都呼叫同一個 `applyView`:回應直接覆蓋 consultation 快取,並重取
`document`／`documents` 兩個 query。**決策不呼叫模型**——這是純狀態機操作。

### 3.2 右欄:Current JD 四段編輯(明確儲存,無 autosave)

四段共用同一條慣例:**開始編輯 → 本地草稿 → 明確按「儲存」/「取消」**;沒有一段是打字就存。
所有寫入都帶 `Idempotency-Key: crypto.randomUUID()`;失敗重試沿用同一把 key(見 §6)。

**① 表頭**(`JdHeaderForm`,iCAP 版型欄位):唯讀卡片右上角「編輯表頭」→ 展開表單(職能基準名稱、
工作描述、職類別、基準級別 1–6 下拉、職業別／代碼、行業別／代碼、說明補充)→「儲存」
→ `PUT /api/v1/job-analysis/documents/{document_id}/jd-header`。表單上方永遠嵌著
**缺漏提示**(`ReadinessNotice`,見下)。**沒有「AI 生成」按鈕**,也沒有職能基準代碼／職類別代碼
輸入欄(這兩碼由 iCAP 配發,畫面上刻意不給填)。

**② 主要職責**(`DutyEditor`):「新增主要職責」/ 卡片上的鉛筆(改名)/ 上下箭頭(排序)/
垃圾桶(刪除,刪除前跳確認框「底下的工作任務會保留,但會變成尚未歸入職責」)。

| 員工動作 | → 請求 |
|---|---|
| 新增 | `POST …/duties`,body `{statement}` |
| 改名 | `PUT …/duties/{duty_id}` |
| 刪除 | `DELETE …/duties/{duty_id}`(204,無回應內容;變成未指派的 Task 靠重讀文件看到) |
| 上/下移 | `PUT …/duty-order`,body `{ordered_duty_ids}` |

**畫面不顯示 `T1`／`T1.1` 這類位置碼**——那是匯出版面才有的東西,見 §4.5。

**③ 工作任務**(`TaskEditor`,`embedded` 模式嵌在右欄):任務**依主要職責分組顯示**
(空職責照樣顯示一個空區塊;沒有職責的任務落在獨立的「未指派」區,且只在真的有未指派任務時
才出現)。每張任務卡顯示敘述、目的／結果、職能級別、情境／條件、頻率、責任角色、
工具／方法／知識／技能;鉛筆進入表單編輯(可改「所屬主要職責」「職能級別」兩個下拉,
兩者皆可清空為未填)。

| 員工動作 | → 請求 |
|---|---|
| 新增工作 | `POST …/tasks` |
| 編輯 | `PUT …/tasks/{task_id}` |
| 刪除(跳確認框) | `DELETE …/tasks/{task_id}` |
| 上/下移 | `PUT …/task-order`,body `{ordered_task_ids}` |

**④ 工作產出與職能內容 O/P/K/S/A**(`OpksEditor`):依任務分區,每個任務卡有四欄
(工作產出／行為指標／知識／技能)各自可「+新增」;每一筆有上下移／編輯／刪除。
每個任務卡右上角有「產生建議」按鈕。

| 員工動作 | → 請求 |
|---|---|
| 「產生建議」(該任務的 O/P/K/S) | `POST …/tasks/{task_id}/opks-proposals` → 只回 `outcome`(`proposed` 或 `no_grounded_candidates`)與 `proposal_ids`;**不直接寫入文件**,產生的是左欄「待確認的 O/P/K/S 建議」 |
| 新增/編輯一筆 O/P/K/S | `POST …/opks` / `PUT …/opks/{entity_id}` |
| 刪除(K/S 若連到多個任務會先跳確認框說明「這一筆也連到其他工作」) | `DELETE …/opks/{entity_id}` |
| 上/下移(範圍限同一 `entity_kind`) | `PUT …/opks-order`,body `{entity_kind, ordered_entity_ids}` |

卡片外還有兩個獨立區塊:「尚未連結的知識與技能」(原任務被刪除後留在文件層的 K/S)與
「文件層態度」(A,**純手動填寫,沒有 AI 生成按鈕**)。

### 3.3 缺漏提示(`ReadinessNotice`)

只出現在表頭卡片裡,**只呈現 `GET /{document_id}` 回來的 `readiness.issues`、不自行重算**。
零 issue 時整個元件不渲染任何東西——**沒有綠色「已完成」狀態**,措辭固定是「iCAP 版型欄位尚有
X 項未填」。缺漏**只提示,不阻擋**訪談、儲存或匯出。

### 3.4 匯出

頁首「匯出」按鈕 → `GET /api/v1/job-analysis/documents/{document_id}/export` → 瀏覽器下載 XLSX。
**永遠可按**(不因 readiness 有缺漏而 disabled,唯一 disable 條件是文件本身還沒載入完或匯出中);
是純讀取,**沒有 dirty guard**、不影響任何權威狀態。缺漏由檔案內第二張工作表呈現,不是跳出視窗
擋下載。

## 4. 跨畫面共同的 UX 慣例(改任何一段編輯器前先確認這條還在)

- **明確儲存,無 autosave。** 四段 Current JD 編輯器與 Proposal 決策全部靠使用者主動按按鈕;
  沒有 debounce 自動送出,也沒有第二份本地 document store——本地草稿只在編輯期間存在
  (`useState`),成功後立刻丟棄,回頭讀 `GET /{document_id}` 的現況。
- **離開有草稿的畫面會被攔。** `UnsavedChangesGuard` 掛 `beforeunload`(重整/關頁跳瀏覽器原生
  確認框);`GuardedLink`(返回文件庫的箭頭)在有未儲存草稿時跳 `window.confirm`。四段編輯器各自
  回報 dirty 狀態給 `ConsultationWorkspace`,任一段有草稿就會擋。**訪談送出與 Proposal 決策不算
  dirty**——那些是逐次即時送出,沒有本地草稿。
- **失敗重試沿用同一把 `Idempotency-Key`,不是重新產生。** 每段編輯器都比對「上一次失敗的
  mutation 參數是否跟這次要送的完全相同」,相同就重送原 key,不同才換新 key
  ——這樣「按太快點兩次」不會在後端造成兩筆操作。
- **AI 只能提案,不能直接寫 Current JD。** 訪談送出與「產生建議」都只會在待確認清單裡多幾張卡,
  Current JD(表頭／主要職責／任務／O/P/K/S)只有員工按下「接受」/「修改後接受」/ 直接編輯
  四段才會真的改變。這是畫面上看得到的行為,底層 identity gate 規則見
  [`task-analysis-engine.md` §6](./task-analysis-engine.md#6-identity-gate什麼時候可以直接改-work-model)。
- **必填欄位在畫面就擋,不是送出後才報錯。** 例如「儲存並接受」在編輯文字被清空時直接 disabled、
  OPKS 拒絕原因未填時「確認不採用」disabled——避免半成品打到後端才被拒。

## 5. 已退役/別做

- `/dashboard`、`/documents/[id]`、`/documents/[id]/intake`、`/documents/[id]/interview`
  這組頁面(`useProfiles`／LangGraph checkpointer 那條舊訪談路徑)**程式碼仍在但已是孤兒**:
  根路徑 `/` 直接 redirect 到 `/workspace`,`/workspace` 內沒有任何連結指向這組頁面。
  **別把它們當成現行使用者旅程的一部分,也別接新功能進去**——技術背景見
  [`interview-engine.md`](./interview-engine.md)、退場決策見
  [ADR 0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md)。
- **沒有登入、沒有角色選擇、沒有多人協作畫面。** 第一版是單機本地文件庫,`/workspace` 列出的是
  「這台電腦保存的文件」,不是「這個帳號有權限的文件」。
- **匯出按鈕不會因缺漏被 disable。** 不要因為想「引導員工填完再匯出」就加阻擋邏輯——ADR 0052
  決定 5／ADR 0058 決定 11 已經明文缺漏只提示不阻擋。

## 6. 指路

- 元件權責、domain 規則、identity gate、durable transaction 語意:
  [`task-analysis-engine.md`](./task-analysis-engine.md)(本檔的技術對應文件,**主讀者相同、
  切入角度不同**)
- 匯出版面與位置碼規則:[ADR 0058](../adr/0058-jd-deterministic-export-shape-and-format.md)
- Readiness 範圍與缺漏不阻擋:[ADR 0052](../adr/0052-jd-readiness-assessment-and-official-code-boundaries.md)、
  [ADR 0053](../adr/0053-jd-header-authority-boundary-and-readiness-scope.md)
- Local Web transport 邊界(Idempotency-Key、problem+json 錯誤形狀):
  [ADR 0045](../adr/0045-job-analysis-local-web-contract-and-shared-authority-commit.md)
- 舊訪談路徑(**已退場,勿救回**):[`interview-engine.md`](./interview-engine.md)、
  [ADR 0030](../adr/0030-ai-coedit-tracked-changes-one-brain.md)
