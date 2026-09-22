# jobintel-ai — LLM Agent（員工 AI 訪談 + 工作台副駕）Design Spec

> 日期：2026-06-22。狀態：**草稿，待使用者 review**。決策擬為 **D28**。
> 緣由：D27 文件工作台已完成（建立/編輯/finalize/匯出皆通）。本 spec 設計把 LLM 加進來——**核心願景、之前刻意延後**。
> 權威依據（2026）：工作分析方法（Task Inventory、Critical Incident Technique、5W2H、結構化訪談效度 .55–.70）；CopilotKit「UI 層、非 agent 框架」+ frontend/backend action 分離 + Direct-to-LLM；HITL「propose/dispose」+ 微軟 Copilot Autofill（建議/來源透明/不自動存）；漸進揭露；Anthropic 多 agent 準則。

---

## §0. 使用者與工作流（最關鍵的前提）
- **兩種使用者**：職務說明書**顧問** + 客戶公司的**員工**。
- **舊做法**：顧問一對一深度訪談員工 → 手寫職務說明書（慢、貴）。
- **本專案**：系統先產**80 分草稿**省掉大半訪談 → 顧問拿草稿**跟員工一起優化到 100 分**。
- **順序**：**員工先用系統（產 80 分）→ 顧問再跟員工精修（100 分）**。
- **LLM 的本質定位**：≈ **顧問初始訪談的自動化版**，面對員工、把「員工口語描述的工作」轉成 **catalog-grounded 的結構化 80 分草稿**。工作台（D27 已做）＝顧問與員工後續精修的工具。

## §A. 已定原則（D28）
| # | 原則 | 說明 |
|---|---|---|
| 1 | **AI 提議、人定奪** | AI 只把草稿放進可編輯**暫存**；使用者**套用**才寫入文件。AI 永不自動寫 DB。 |
| 2 | **catalog 優先、AI 補** | 標準任務→直接取 catalog 官方 O/P/K/S（`tasks_by_id`）；個人化/自訂才用 AI 生成。 |
| 3 | **辨識 > 回憶** | 任務用 catalog 勾選清單（Task Inventory）讓員工認，不靠空想；CIT 補漏問抓非例行。 |
| 4 | **漸進揭露、按需深問** | 細節不前置一次問；**只在核心任務、走到時**才用 5W2H+CIT 深問。 |
| 5 | **重要度分流深度** | 核心任務深問、次要任務輕量（catalog 帶過）——CIT「聚焦關鍵時刻」。 |
| 6 | **解耦** | AI＝自家**無狀態專職端點**（可測/可換模型）；document JSONB＝單一真相源；**UI＝結構化面板直接 fetch**（MVP 不上 CopilotKit/聊天，列 Phase 2）。 |
| 7 | **透明 + 安全** | 每建議標**來源+極簡理由**（catalog 代碼 / AI 依描述）；警語「AI 可能有誤、未自動儲存、你決定」。 |

## §B. 員工 on-ramp 流程

**Phase 0 — 小訪談（3 題、可跳過）**：建立脈絡 + 餵後續 AI。
1. 職稱 / 這職務大概做什麼？　2. 主要負責哪些工作？　3. 有沒有特別、清單外的工作？
- AI：`職類比對`（向量搜尋，**已有**）→ 推薦職類**讓員工確認**（不自動定）；`任務萃取`→ 預勾可能任務 + 列候選自訂任務。
- 存：自述存 profile（`job_summary`+），當後續 AI 脈絡。形式：極簡（一頁 3 格 or 3 句小對話，待定見 §F）。

**Phase 1 — 任務盤點 + 補漏 + 重要度**：Task Inventory + 辨識。
- catalog 任務列成勾選清單（intake 已預勾）→ 員工勾「我有做的」。
- **CIT 補漏問**：「有沒有特別關鍵/棘手、清單沒有的？」→ 一句描述 → `自訂任務結構化`→ 提議任務（名+職責）→ 確認。
- **深淺由員工「動作」決定，不做顯式重要度欄位**：在意的任務 → 點 ✨ 深填；其他 → 一鍵帶 catalog 輕量。少一步分類。

**Phase 2 — 逐任務 elicitation（按需、分流）**：5W2H + CIT。
- **核心任務 ✨** → 結構化卡片（短欄、選填、AI 預填）：何時/多常、何地/情境、對象、做什麼+怎麼做、目的、**「做得好的一次」(CIT，選填+提示「給實例 AI 更準」)**。
  - 「✨ 產生」→ `O/P 草擬器`（O 來自產出/catalog；P 來自 CIT+步驟）+ `K/S 推薦器`（per-task catalog K/S 預勾+理由）→ **暫存**（可改/可勾）→ 套用 → PATCH。
  - 太薄 → `clarify` 回**一個**追問 → 員工答 → 再產草稿（最多一輪）。
- **次要任務** → 輕量：**一鍵取 catalog 官方 O/P/K/S**（`tasks_by_id`，非 LLM 生）→ 員工瞄一眼採用/略過。
- 面板內可「全部採用 / 全部捨棄」（單任務範圍）。

**Phase 3 — 態度 A + 說明**：A 從 catalog 全域、AI 建議常見幾項→確認；學經歷/補充可填可略。

**Phase 4 — 80 分 → 交顧問**：完成度條→送出。顧問開**同一張表**，針對薄弱處與員工深談、用同一套 AI 工具改到 100 分。

## §C. AI 專職後端端點（解耦的「腦袋」）
無狀態、單一用途、各自 focused prompt、回**結構化提議、不寫 DB**；catalog 經 indexer client 取用。皆可單測（輸入→輸出）。

| 端點 | 輸入 | 工具 | 輸出 |
|---|---|---|---|
| `POST /ai/extract-tasks` | intake 自述 + 職類 task_pool | task_pool | 預勾 task_id[] + 候選自訂任務[] |
| `POST /ai/structure-task` | 一句描述 + 職類脈絡 | — | {task_name, unit 建議} |
| `POST /ai/draft-op` | 任務 + 5W2H/白話 + catalog 該任務 O/範例(`tasks_by_id`) | tasks_by_id | {outputs[], indicators[]} + 來源標記 |
| `POST /ai/recommend-ks` | 任務 + 描述 + catalog 該任務 K/S(`tasks_by_id`) | tasks_by_id | {knowledge[], skills[]}（勾選+理由+來源）|
| `POST /ai/clarify` | 任務 + 目前太薄的輸入 | — | 一個追問字串 or null |
| （職類比對） | intake | **search 向量(已有)** | 推薦職類（免 LLM） |

- **catalog 優先序**：標準任務 → `tasks_by_id` 官方值為底/候選；AI 只做**個人化改寫 / 篩選 / 自訂任務**。
- LLM：OpenRouter / Anthropic adapter，模型走 **Claude 最新**。
- **K/S 升級**：用 per-task `tasks_by_id`（K01–04…）取代 occupation 整池 `pairs()`——補上 D24-c。

## §D. UI / 觸發（MVP＝甲：結構化、直接呼端點；聊天列 Phase 2）
- **核心流程全是 UI 觸發**：小訪談(表單)、勾任務、✨ 面板——**直接 `fetch` 呼 `/ai/*`**，**不需要 LLM 路由、不需要 CopilotKit**（使用者已明確指定哪格/哪任務，不必讓 LLM 猜意圖）。
- **HITL**：`/ai/*` 回**提議** → 面板**暫存**（可改/可勾、標來源+理由）→ 使用者「套用」→ 走現有 PATCH。AI 不自動寫。
- **✨ 面板＝核心 AI 入口**：5W2H 卡片 → 產生 → 暫存（O/P 文字 + K/S 勾選+來源/理由）→ 套用；可「全部採用/捨棄」（單任務）；警語。
- **聊天副駕（CopilotKit）＝ Phase 2（延後）**：服務「**開放式、跨整份文件**」問法（哪裡缺 / 語氣統一 / 改正式），主要在**顧問精修**階段；屆時才需要「LLM 路由到哪個 `/ai/*`」。AG-UI 保證**可無痛加上、核心前端不變**。舊 `/copilotkit` AG-UI 端點冰著。

## §E. HITL UX（對齊微軟 Copilot Autofill）
- AI 建議落在**可編輯暫存**；**從不自動儲存**；採用/捨棄/替換由人決定。
- 每建議標**來源**（`catalog Kxx` / `AI 依你的描述`）+ ⓘ 展開極簡理由。
- 單任務「全部採用 / 全部捨棄」。
- 小警語：「AI 建議，可能有誤，未自動儲存，由你決定。」

## §F. 已定（2026-06-22 review）
1. **重要度欄位 → 砍掉**：深淺由員工動作決定（✨深填 / 一鍵 catalog 輕量），不做分類步驟。
2. **5W2H 卡片精簡＋漸進**：必填只 1 格「這任務做什麼、產出什麼」；選填「做得好的一次(CIT)」＋收合的 5W2H 細節；提示「填越多/給實例 AI 越準」。
3. **小訪談＝一頁 3 格表單**（非對話；甲不上 CopilotKit）。
4. **工作筆記落點**：存任務底下非契約欄 `_notes`（餵 AI＋給顧問），**finalize/export 剝除**（同 `_uid/_tid/_pool`）。
5. **多帳號/權限 → 延後（很後面）**：MVP 同一份檔、同工作區，員工與顧問都開同一份編輯。
6. **LLM＝OpenRouter**（沿用 `OpenRouterLlm`），**預設便宜高 CP 模型、可 env 切換**；且**可 per-function 換模型**（簡單抽取用更便宜、O/P 草擬用較強），成本/品質可分別調。

## §G. 範圍
- **IN**：員工 on-ramp（intake→盤點/補漏→核心 5W2H+CIT→A/notes）、`/ai/*` 5 端點、catalog-first sourcing、**✨ 結構化面板（直接 fetch `/ai/*`）**、HITL 暫存/套用、K/S 升級 per-task、工作筆記落點、顧問共用同一張表。
- **OUT（延後/Phase 2）**：**CopilotKit 自由聊天副駕**（開放式問整份、語氣統一、改正式——顧問精修用）、一鍵自動草擬整份（品質+需平行→未來多 agent 編排）、多帳號權限、PDF/docx 匯出、語音輸入。

## §H. 實作分塊（給後續 plan）
1. 後端 `/ai/*` 端點（extract-tasks / structure-task / draft-op / recommend-ks / clarify）+ OpenRouter/Claude adapter + prompt + catalog(tasks_by_id) 取用；各自單測（FakeLlm + stub indexer）。
2. document 資料：per-task 工作筆記欄（非契約，export 剝除，沿用 `_pool` 那類 `_` 前綴慣例）。
3. 前端：✨ 面板**直接 `fetch` `/ai/*`** + HITL 暫存/套用（來源/理由、全部採用/捨棄、警語）。（CopilotKit/聊天＝Phase 2，不在此）
4. 前端：✨ 面板（5W2H 卡片 + 暫存 + 來源/理由 + 全部採用/捨棄）；intake 小訪談頁；任務盤點預勾/補漏/重要度。
5. 次要任務「一鍵取 catalog」路徑（tasks_by_id）。
6. e2e：員工走一遍產 80 分 → 顧問精修。eval：抓結構/grounding（K/S 是否都在 catalog、有來源標記）。

## §I. 未來：AI 自主深度訪談（現在不做，但架構/函式必須預留）
- **願景**：員工可選「**深度訪談模式**」→ AI 進行**多輪對話式訪談**（跨所有任務、自適應追問）→ 訪談完**直接產出完整職務說明書**，不必逐格自己點。＝把顧問完整訪談自動化。
- **與 MVP 關係**：MVP「逐格 ✨」＝員工自助；未來「深度訪談」＝AI 主導。**兩者產出同一份 OCS 文件、共用同一批 `/ai/*` 函式**。
- **現在就要遵守的設計約束（才不會做死）**：
  1. `/ai/*` 函式**無狀態、結構化 I/O、不綁 UI、不綁觸發者**——既能被 ✨ 面板呼，也能被未來**編排器/訪談 agent** 在迴圈裡呼。輸入永遠是顯式的 `{任務, notes/描述, catalog}`，輸出永遠是結構化 `{O/P}`或`{K/S}`。
  2. document JSONB + PATCH 是唯一 of-record——未來 agent 也走同一條寫入（提議 →（批次）審核 → PATCH）。
  3. 未來「訪談 agent」＝**獨立編排層**（會話式、loop 全任務、可平行 → 屆時才符合多 agent/LangGraph 條件），**疊在現有函式之上、不重寫函式**。
  4. catalog-first / grounding / 工作筆記(`_notes`) 規則一致沿用。
- **一句話**：現在把 5 個函式寫成乾淨純函式（given 輸入→結構化輸出），未來的自主訪談只是換「**誰提供 notes、誰呼叫**」，函式不動。

> 方法論：定案後 writing-plans → subagent-driven TDD（後端端點先、各自可測）。

## §J. 測試 / 模型策略
- **單元測試＝FakeLlm**（確定性、免費、CI 安全）：測 `/ai/*` 的 catalog 取用、prompt 組裝、輸出解析、grounding 規則，不打真模型。
- **人工品質驗收＝OpenRouter 便宜款（Claude）**：代表真實行為、夠便宜；**不用本地小模型**（繁中+OCS 領域偏弱、會誤導 prompt 調校）。
- **本地/地端模型＝現在不做、架構保留可換**（LLM port + adapter）；唯一動機＝員工資料隱私/地端合規，屆時加 adapter、函式不動。
- **API key**：建置 + 單元測試**不需要**（FakeLlm）；只有跑真模型人工驗收才需 `OPENROUTER_API_KEY`。
