# 聊天 Web API 獨立窄審

- 日期：2026-09-13；範圍：[api.ts](../../../../experiments/jd-relational-app/web/src/lib/api.ts)、[chat-api.test.ts](../../../../experiments/jd-relational-app/web/tests/chat-api.test.ts)，對照正式聊天 SSOT／HTTP／歷史投影。
- 結論：**PASS，本次未找到可重現 P1／P2。**採用最後已落檔的 `anchor_run_id`、初頁最新／舊頁前翻且頁內正序版本。初讀時 schema／fixture 尚在同步，不將中間缺欄狀態當成完成品缺陷。
- 本審查未修改被審 src／test；另受指派撰寫的 `chat-session.ts` 不包含在本文件的獨立審查結論，應由其他 reviewer 核查。0 provider、0 DB、無瀏覽器／宿主啟動、無套件變更。

## 1. 核查與排除的具體反例

| 題目／實際行號 | 對照與結論 |
|---|---|
| Human `message_id` 必須等於 `run_id`、頁內 run 延續：`api.ts:296–305` | [chat_history.py](../../../../experiments/jd-relational-app/src/jd_relational/chat_history.py) `_public_messages:162–177` 目前由每個 Human 的 canonical UUID ID 建立 run，後續 public AI 繼承到下一 Human。新的切頁仍是正序連續 slice，因此頁首是 assistant、跨頁切開 Human／AI，及同一頁含數個 run 都合法；前端不要求頁首 Human。沒有找到目前合法後端投影會被這兩檢查拒絕的反例。這是目前投影事實，不是通用 LangChain 限制；`ChatMessageId` 本身仍允許非 UUID 的 AI message ID，不能為前端檢查把它全面收窄 |
| 初頁末筆 run 与 anchor run：`api.ts:292`；舊頁不能用末筆猜最新 run：`api.ts:293–294` | [ChatHistoryPage SSOT](../../../../experiments/jd-relational-app/contracts/jd-chat-http.schema.json) 已明定初頁最新、後頁更舊且每頁正序；後端最後一個公開 Human 所屬 run 必須匹配原 anchored record。初頁因此可核最後一筆；舊頁以同一 `anchor`＋`anchorRunId` 比對，允許其所有訊息都屬於較早 run。測試 `initial history exposes the anchored latest run while an older page may belong to earlier runs` 是對此過度收窄風險的有效正例 |
| 頁框、scope 與原引用：`api.ts:271–294` | 正式 schema 檢查後再核 dataset／document、requested limit、原 anchor／anchor run、非空續頁及 cursor 不自循環；opaque token 未 decode。`ChatMessagesOptions` 的 anchor／anchorRunId 僅作 browser 比對，不送成額外後端 query。API 只回一頁，不自動掃全部歷史或把後頁當另一個新 anchor |
| 原請求誤重送：`api.ts:252–270` | 每個方法只有一個 HTTP 動作。start 保留原 body／run ID；status 只有 GET；cancel／recover 只送原 run 路徑及空 body。Location 驗證只比對，不自動 follow、不建立新 key、不換 expected revision。持久草稿與何時可以明示重試留在上層，不由 API 依錯誤猜測 |
| 已保存內容被當失敗／未知被當未存：`api.ts:96–114,236–250` | 網路失敗是固定 `response_unknown`，非 JSON／非正式 shape 是 `invalid_response`；它們都不是 `not_saved` 證據。`ChatProblem` 驗正式 schema／HTTP status 後才公開固定業務錯誤。run 及各筆 JD effect 仍是同一份正式回應；failed run＋confirmed committed JD 的正例通過，`not_found` 不被改成輸入未保存 |
| 不同 scope／較晚回應：`api.ts:225–239,287–294` | 請求前捕 dataset，回傳後核客戶端 dataset 未變，並核回應 document／run。等待期間更換 dataset 的成功回應被拒。**同文件兩個不同時間 GET 的先後、元件 dispose、已加载頁跨頁去重仍是上層 observer 的責任**，此 API 沒有冒充它們已完成 |
| HTTP 200／202、Location：`api.ts:123,240–248` | 與 [chat_api.py](../../../../experiments/jd-relational-app/src/jd_relational/chat_api.py) `response` 的控制路由一致：running／closing／recovery_required 為 202，其餘 200；控制回應都帶原 run Location；GET status 是 200。非法 Location 不會轉成新網路動作 |
| 原文／安全錯誤：`api.ts:60–66,96–114` | 先用 SSOT，再核原 UTF-8 128 KiB 及 unpaired surrogate，沒有 trim／normalize。private marker 的一般錯誤及非正式 payload 不直接回傳成可顯示文字；不因 validation error 輸出整份原 JSON。這不取代服務端固定錯誤出口的責任 |

不建議為本次審查新增通用訊息協議驗證器。Human／run 關係已由後端的原生資料投影決定，前端這兩項檢查目前不阻擋合法資料；如未來投影契約改變，應同步刪除／調整具體冗餘檢查，不能倒過來要求原話／歷史為迎合前端而變形。

## 2. 最新頁與按需前翻：定點官方核實

查閱日 2026-09-13；成功讀到 [OpenAI Conversations Items — List](https://developers.openai.com/api/reference/resources/conversations/subresources/items/methods/list) 的正式 endpoint reference：`GET /conversations/{conversation_id}/items`，有 `order=asc|desc`（預設 desc）、`after` cursor 及 limit。**該端點沒有 `before` 參數，不補造一套官方接口。**專用 docs fetch 首次只有導覽 stub，因此再直接開官方頁及定位 Query Parameters，未用搜尋摘要充作完整讀取證據。

這支持「取資料的方向可以先較新、再用 cursor 取更多」的有限技術做法，**不是 ChatGPT Web 內部實作或所有聊天 UI 的共識證明**。本案讓員工開文件便看到最近訪談，舊頁按需前翻，是根據目前產品情境的呈現取捨。頁內仍正序，上方插入較早頁；不把 OpenAI wire 的 desc 直接搬成畫面裡倒序的 Human／AI 對話。

目前本地新契約與後端已採：初頁取最新完整訊息區間，縮小字節頁時保留最新完整 rows；`next_cursor` 在同一固定 root/source snapshot 向較早範圍移動，頁內維持正序。`anchor_run_id` 表示原 anchor 的 run，不是頁首 run，也不是後頁讀取當下的新 run。Web 重新讀最新頁時換一個範圍；不可把不同 anchor 的頁不加區分地混接。

本次也讀適用 [web/AGENTS.md](../../../../experiments/jd-relational-app/web/AGENTS.md) 及已安裝 Next 的 `dist/docs/01-app/02-guides/client-side-data-fetching/index.md`。該指南對共享 browser cache 的建議承接 [UI preflight §6](ui-preflight.md#6-只讀查回要不要新-query-庫)，不要求為此 API review 另裝 Query 庫或自造通用分頁引擎。

## 3. 實際驗證與限制

以已指定 bundled **Node 24.19.0** 執行：

```powershell
# 工作目錄 experiments/jd-relational-app/web
& 'C:/Users/chenb/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node.exe' --experimental-strip-types --test-isolation=none --test tests/chat-api.test.ts
```

結果：**60 PASS，0 FAIL，335.8052 ms**。這是 mock fetch＋真 Ajv／正式生成契約的離線 API 接點測試，不是 FastAPI／真 PG／瀏覽器或真 provider 驗收；沒有重新合計既有其他層數字。首次誤在 repo 根尋找此測試的命令只得到檔案路徑不存在，修正工作目錄後執行上述一輪，不把該命令錯誤記成業務反例。

仍需其他測試承接的有限責任：原 request 的本機持久 ACK／晚打草稿、跨頁 prepend 與重複 ID、元件離開後晚回、同 scope 較舊 response 不覆蓋新狀態、長回合觀察／取消的真正服務效果。它們不由這 60 個 API 測試或本次 PASS 代證；CV-01 整輪淨差異及 HR-02 也未因此完成。
