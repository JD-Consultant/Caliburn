# AI 專業職務說明書顧問：從現有成果到可用成品

2026-09-10；Topic JD-R002／JD-R001-C06。Owner 已明確要求實作本總計畫。狀態：開始執行，尚未交付成品。

> **2026-09-23 優先序更新：**本計畫保留完整產品旅程、自然品質與真人試用 gate；下方 Plate／三工具／「Task 6 是唯一下一單位」是當時起點，已被 relational JD、分層 Memory、完整 App 驗收及 [ADR0077 正式權責切換](../adr/0077-relational-jd-app-production-authority-and-pnpm-entrypoint.md)取代。Owner 現將備份／空庫還原移出首版核心驗收，只要求一般中斷後既有已保存資料與進度可查回。當前短路由以 [`current-decisions.md`](../current-decisions.md) 最上條為準；歷史階段與問題解決順序仍保留。

> **2026-09-23 P3 最新入口：**GPT-6 Luna／OpenRouter Responses 的第二次獨立有界 smoke 已完成 2 筆真實模型請求、合成工具往返與非空 final；同筆回覆提供 OpenAI 路由及成本，逐筆結算。首次 smoke 曾因 test-only `provider_model_mismatch` 停止，舊帳本未重開；兩次結果與邊界皆保留於[GPT-6 接線證據](../specs/evidence/2026-09-23-gpt6-responses-offline.md#第二次獨立有界真實工具往返最新)。這只關閉有限服務端 gate，**自然 C-W／16K 長上下文／B1、B2 真模型／同批 Browser 仍未驗收**。下方 P3 表格的「0 外部 request／未付費授權」及「現行後續」是撰寫時歷史狀態，不可當成最新外送數或費用授權；下一批自然測試要另列實際請求與費用界線。

## 1. 成品與範圍

員工在目前這台電腦開啟 App，透過持續訪談建立忠實反映自己實際工作的客製化 JD，能看修改、更正、保存、日後續談。旅程：建立文件 → 訪談 → 理解 → 資料足夠才撰寫 → 查看／更正 → 全稿核對 → 保存／續談。

- 本機單一操作者、多份彼此隔離文件。首版 App 內完整使用；建立、暫定命名、更名、列表、封存與恢復。
- 封存收起常用列表中的文件，保留 JD、訪談、Memory 與歷史，可查看、恢復後續談／編輯。正在執行或未保存的工作先依恢復流程處理。永久刪除 PARKED。
- 同畫面聊天與唯一可編 JD；實際差異及歷史原畫面唯讀查看。持續工作稿，無個別 pending accept/reject、accepted projection 或第二份可編稿。
- 前景 AI 回合期間暫停手改（含純訪談），可閱讀／查改動。不是每輪必須改稿。
- Plate 免費開源能力，沿六章、Task 平行成果／要求組、同份 JD 共享 K／S 引用及語意 v2。暫用「工作執行要求」，名稱微調不阻塞施工。
- 其他電腦安裝、下載／匯出、真人顧問交付／問答包、永久刪除、登入／ACL／多人／雲端／RAG／舊資料搬移 PARKED。

本總計畫不取代細部契約，不使 Proposed ADR 自動 Accepted。沿 [register](../current-decisions.md)、[process](../decision-process.md)、[六切片](2026-09-10-jd-editor-core-implementation.md)執行。production authority 已由 Owner 接受的 ADR0077 完成硬切換；已驗 Memory／顧問／JD 直接採用，不重新選架構或模型。

## 2. 階段、依賴與完成證據

| 階段 | 工作與交付 | 出口 | 狀態 |
|---|---|---|---|
| P0 基線 | 本計畫、有效決策、需求／證據／驗收對照；修正舊三表 DOM 驗收，active 全走 v2 | 每項效果有工作包；已決定與待實證分開 | 完成，見[基線審查](../specs/evidence/2026-09-10-jd-product-baseline-review.md) |
| P1 核心 | 原 Task 1–3：schema 生成、原生 profile／adapter／validator、PG 保存、三工具、手改通知 | 固定操作保存／重開／定位／恢復，錯誤不重複套用或部分發布 | Task 1–3完成；原生／保存／三工具固定工程驗收通過，完整lifecycle仍留P2 |
| P2 畫面 | 原 Task 4–6：聊天＋JD、手改／真選取、差異／歷史／來源、取消／恢復、單一 JD Skill；入口防重複及未保存保護 | 真瀏覽器完整固定旅程；API／DB／模型所見一致 | Task4–5已接受；接Task6完整固定旅程，OS真人IME未驗 |
| P3 自然縱切 | 既有真顧問自行訪談→初稿→K／S首建及引用→更正→全稿核對→重開 | 1個不指定 tool calls 的完整案例；結果、來源、失敗、延遲、用量可查 | [C-W v2校準包](../specs/evidence/jd-product-p3-calibration/README.md)及 AI 操作者測法接合 review 通過；[正式新 App 測試入口](../specs/evidence/2026-09-23-jd-p3-trial-entry-offline.md)／OpenRouter 支出閘門、A 單回合 Saver 對帳與固定合成 B1／B2 背景 checkpoint→publication；受影響離線及真 PG **59 項通過**（含逐次 redirect 護欄），可重開的 12 次 chat POST 上限及三角色逐請求記錄已備，0 外部 provider request。非真人／非盲，0 次自然 trial／未付費授權。v3 結果模板已列入入口 hash；正式 Web **310 項**、typecheck／build／codegen 複核通過；仍待同一自然旅程的 A 自主通知與逐輪事件、exact runtime 凍結、真 Browser 與 Owner 付費裁決。 |
| P4 正式整合 | 採用已驗 Memory／來源 runtime、獨立 successor ADR；統一依賴／composition／契約 | 正式 API/Web 唯一 JD owner；舊 pending／approved writers、UI 與下載入口退出；無 research/worktree runtime imports | **完成**；ADR0077 Accepted，舊可執行 authority 已移除，正式根入口通過 |
| P5 日常使用 | 更名、封存／恢復、基本啟停及中斷後查回；備份／空庫還原／跨電腦恢復不作本輪 gate | 已確認保存的原話、JD、進度在一般重開後可查回；未知提交不自動重做副作用 | **部分已驗，非 P3 前置**：新 App 已有更名／封存／恢復真 PG、根入口啟停、Host／Saver 重啟及 Browser 重開證據。剩餘只按核心真實旅程中實際出現的中斷／恢復缺口補驗。9/14 [整庫備份演練](../specs/2026-09-14-jd-backup-and-restore-slice.md)保留為歷史研究，無須為首版補做設定檔副本或還原庫續談。 |
| P6 品質試用 | 3異質未見職位各2自然流程、長訪談／compaction／晚期更正／手改／重開、3名目標員工操作 | 重大忠實度／資料／旅程問題處理完；固定回歸及失敗保留 | [真人操作空表](../specs/evidence/jd-product-p6-usability/README.md)已備且有限review通過；自然及真人驗收未開始 |
| P7 交付 | 固定版本／依賴、使用及維護說明、獨立審查、驗收與後續清單 | 日常入口可用，不需研究者代操作；code/design/ADR/register 一致 | 技術交付 gate 完成；PR／merge 進行中，P6 真人品質試用仍獨立未完成 |

主依賴 P0→P1→P2→P3→P4→P5→P6→P7。P4採用研究、P5旅程設計、P6評量材料與P1/P2並行，在受影響施工前閉合。P3隔離驗證不代稱正式驗收；P4不跨過核心及authority gates。

## 3. 有界補研究與設計

| 工作包 | 必須回答的問題 | 交付／停止條件 |
|---|---|---|
| R1 專業收尾 | 足夠寫稿／完整工作／低頻／未知矛盾；最新訪談未進 Memory 如何核對 | 單一顧問指引與正反材料，能由有限案例驗證即停止廣搜 |
| R2 員工旅程 | 開始、未保存、取消、重開、切文件、封存、建立或聊天回覆遺失 | 畫面／狀態及可操作出口；錯誤都有真實保存判準與恢復情境 |
| R3 結構可讀 | 成果／要求、共享K／S、來源、歷史、原生diff未高亮資訊 | 完整v2樣稿真DOM驗收，不以聊天摘要／空diff稱沒有修改 |
| R4 模型接點 | 參數/context負擔、手改基準、壓縮／重開、自然選工具、修復／停止 | 真model request／tool result／保存結果，只對新證據缺口校準 |
| R5 正式保存 | 原文／Memory／JD owner、namespace／setup、封存／恢復、版本與備份 | 有限採用ADR、責任圖及初始化／恢復設計，不建第二權威 |
| R6 品質效率 | 異質職位評量、一般／深讀／更正等待、非專家障礙 | 未見案例、操作表、實測與P6前固定界線，不事後降標 |

責任文件：R1/R6為`docs/specs/2026-09-10-jd-product-quality-acceptance.md`；R2/R3為`docs/specs/2026-09-10-jd-employee-journey-design.md`；R5為`docs/specs/2026-09-10-jd-production-adoption-design.md`。R4沿現有context／工具／責任稽核，Task3.3a補在[跨輪通知設計](../specs/2026-09-10-jd-model-view-change-notice-design.md)，有限review通過，不另建SSOT。入口只記狀態與路由。

優先核對 OpenAI/Codex/ChatGPT、Anthropic/Claude 及所選框架官方資料；每項採用記查閱日／適用版本／穩定狀態／免費授權，區分 Official fact、共同原則、Caliburn mapping、Unknown。能力缺口列具體替代／代價，不默默補造通用定位、編輯、diff或回退引擎。

## 4. 分工與介面

- AI：理解、追問、寫稿時機、內容組織、已取得依據引用、更正及完整性核對。
- App：文件／選取context、人工變更通知、ID／scope／版本、關係與定位檢查、執行／保存結果、取消／恢復。
- Plate：原生編輯／選取／清單／表格／operations／history／diff，只作必要JD有限整合。
- PG與顧問保存機制：各自唯一保存責任資料、維持文件隔離；Web不重算invariant。
- 員工：提供真實工作、指出誤解、補充或手改；專業寫作及完整性核對由顧問承擔。

歷史三工具與 `job-analysis-contract` 路線已由 relational JD 的正式 generated contract、細粒度 JD tools 與同一 Domain／Runtime 取代；Web 型別仍由正式 schema 機械生成，不手改生成檔。人工通知是 App context，不偽裝 HumanMessage、不自動改 Memory。金鑰、診斷及模型資料流已納入正式接合。

## 5. 驗收與執行邊界

1. **專業**：工作→JD無重要遺漏／錯合；JD→依據無補造責任、KPI、資格、成果、K／S。案例不變永久任務、未知不填滿、更正保留其他有效工作。依內容指南判完整，不用模型自評滿分。
2. **編輯**：繁中／IME、重複文字真選取、貼上、移動／拆分、共享引用、undo／redo；AI→人→AI與下一輪人工通知。
3. **恢復**：保存失敗、回覆遺失、取消、關頁／服務重啟／切文件；無跨文件污染、已保存資料遺失、重複套用或誤報完成。普通dirty、送出候選、正式保存稿分別驗。
4. **自然模型**：先1完整縱切，再3異質未見職位各2自然流程及長訪談；案例不放提示示例。每次失敗保留，不以指定tools代稱自然成功，不以平均分掩蓋重大錯誤。
5. **員工**：3名目標員工能開始、看稿、辨識改動、更正、保存／續談；協助及放棄点據實記。真人試用不是交付／核對權限功能。
6. **本機**：日常啟停、缺設定／DB或模型失敗提示；一般中斷／重開後查回已確認保存的原話、JD 與進度，不重送未知副作用。9/10 原列的全體備份／還原演練不再是首版 gate；既有演練留存。資料版本不合停止說明，不自動清空或永久刪除。
7. **交付紀律**：每包追溯decision/spec、測試、獨立review、North Star核對及closure。綠燈後只提交本task，不reset或混入既有dirty，不push。Git受限時保留未提交diff與證據，不跳過驗收。

原六切片0付費模型請求。P3/P6先備妥資料、案例、呼叫數及美元上限，Owner確認後逐批執行；CT49–51舊授權不延用。首例交付實測及下一批建議；品質／等待界線在P6前固定。缺人員／預算仍推進無依賴工程，不冒稱自然／真人驗收完成。

2026-09-10查閱：[OpenAI評估方法](https://developers.openai.com/api/docs/guides/evaluation-best-practices)、[Anthropic agent evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)支持情境評估、實際 outcome 及人工校準；只採方法及本地帳本，不引入已公告棄用的 OpenAI Evals 平台／API，效力核對見 R6 材料。[GOV.UK](https://www.gov.uk/service-manual/user-research/using-moderated-usability-testing)支持觀察目標使用者完成任務。案例數為本案映射。現行備份依 [PostgreSQL 18](https://www.postgresql.org/docs/18/backup-dump.html)，不能只備份 JD JSON。

## 現行後續

正式程式、依賴、根入口與操作文件已由 ADR0077 完成技術交付；目前產品驗收主線是 P3 自然縱切：9/22 正式新 App 的同文件真 Luna A 通知→B1／B2 發布→A 回讀→JD／Browser 旅程直接沿用，不重做固定接線；另有 A 單回合與 B1／B2 固定合成背景工作的 Saver／P3 ledger 零付費對帳。接著凍結 exact revision，取得 Owner 對本批 12 回合／180 requests／US$1.00 的付費裁決後，才執行 C-W 自然 Luna 與同批真 Browser，核對自然追問下 A 自主通知、逐輪事件、背景整理及完整 JD 品質。既有合成旅程、固定模型 Chrome 旅程及零付費 Web／PG 預檢不代替本批自然品質；P6 異質職位及真人試用仍是後續獨立 gate。尚無 P3 完成證據，不把提交、PR 或 merge 當成產品驗收出口。
