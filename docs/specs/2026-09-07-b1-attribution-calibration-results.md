# Q019／MP-02d/e：抽取內容歸屬與候選交接校準

> 2026-09-07 · **一組有限真測有改善；整組回查尚未通過。**只改 B1 提示與既有欄位說明，B2、schema 欄位、ABC、Store、來源、驗證及額度不變。不接 JD／UI／production。
> 入口：[主 register](../../../../docs/current-decisions.md)。有效要求：[Memory prompt 授權及情境](../../../../docs/specs/2026-09-06-analysis-only-agent-memory-design.md#2026-09-07memory-prompt-調整與驗收重點)；前因：[原實驗 §6](2026-09-07-memory-prompt-live-calibration.md#6-同組材料續測有進展但不能只靠再加提示收尾)；已完成機制：[B2交付修復](2026-09-07-b2-delivery-repair-results.md)。本稿只存本輪差異、證據及限制，不重述 Memory 總設計。

## 1. 問題在哪裡

- **MP-02d：**先前 `209c625ee483` 首批詳記已有 A/B 工作，候選卻只列未知驗收期限；整併者沒收到足夠的已知工作訊號。不是原文丟失，也不是需要新增 Memory 層。
- **MP-02e：**`c815bc309340` 第二段 B1 詳記寫「顧問追問……未取得員工回答，因此分工未知」，候選寫「不能推定」。下游 B2 隨後削弱第一段已記的本人責任。原始 B1 input 仍有 `role`，`CONTEXT_ONLY` 只含必要前一問答，不含完整舊 A 案；抽取者把本段沒回答擴成整體未知，是已觀察到的上游錯誤。兩者的因果關係屬待驗假設，不從可見輸出推稱知道模型內部推理。
- 上次同時加 B2「未答不是否定」沒有成功收斂。**本輪假設：**先讓 B1 在自然敘述中保留「誰說的、是陳述還是追問、未知的範圍」，能減少下游誤解；不先假定改 B2 或重設流程才有效。

先回讀上述短路由、方法授權、實際原文／詳記／候選／正文／工具結果及当前程式，再核對原廠提示。這是先前 Owner 已准的內容校準，不新增欄位、semantic validator 或拒絕規則。只有提示詞修改；既有真失敗是內容紅燈證據，不以文字包含斷言／mock 輸出假裝語意 TDD。

## 2. 官方依據與本案取捨

- **官方提示事實：**完整讀取 OpenAI Agents SDK 固定 revision `1d471a4775bf2f40179f411824da383deb4c3fca` 的562行 [rollout extraction prompt](https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts/rollout_extraction_prompt.md)。其詳記規則要求保留資訊確認程度、區分使用者明述與 assistant 提議，先具體依據再抽象，不把未採納討論升格為既定知識；候選也要求歸屬可辨識。[詳記與證據規則](https://github.com/openai/openai-agents-python/blob/1d471a4775bf2f40179f411824da383deb4c3fca/src/agents/sandbox/memory/prompts/rollout_extraction_prompt.md#L251-L291)。這是公開 SDK 提示快照，不是所有 OpenAI 產品皆如此的保證。
- **官方指引：**優先修正互相矛盾的提示契約，保留必要成果／證據限制，用既有 traces 比較，不一味增加規則／工具。[GPT-5.6 simplify prompts](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#simplify-prompts-first)。[Codex local memories](https://learn.chatgpt.com/docs/customization/memories#how-local-codex-memories-work)支持選擇性背景整理，不保證案例細節全覆蓋。
- **Caliburn mapping：**重要訊號是員工實際工作及案例差異，不照抄原廠 coding／偏好高訊號清單，也不搬其 task outcome／偏好表單。本輪把 B1 既有兩欄描述與相應短規則校準為：候選含已知工作和新增細節，不只未知；未答只記顧問具體追問及本段未答，不推成既有工作不成立；做法／要求已知與驗證細節未述分開；真正員工改口／不相容才寫更正／矛盾。
- **Unknown：**提示遵從率及跨題型效果不能由官方文件或單樣本證明。沒有借原廠名義保證零幻覺，也沒有使用字面否定詞偵測器。

## 3. 一次真測結果

基準 `57c336bf`，只改 `extraction.py`，精確 diff 和實際三欄 schema 在[可攜證據](evidence/2026-09-07-b1-attribution-calibration.json)。執行 `e9ce1bf79a87`，沿用原合成問答及回查題，Luna／medium、8個 B2 model steps／12個 tools、24個整組請求、每次4096輸出及 US$0.15 原實驗停止界線；SDK無自動重試。未改模型、測試材料、產品計數邊界或價格預留。

| 階段 | 實際觀察 | 請求／provider USD |
|---|---|---:|
| B1-1 → B2-1 | A/B案例、本人及後端分工均進候選／正文，非只剩未知；正文與導覽成對發布 | 1＋6／0.00340272 |
| B1-2 → B2-2 | 保留付款失敗時的購物車＋已填資料、手机驗證及一次搬運的過往範圍；顧問未答追問沒有撤銷先前 A 本人責任 | 1＋6／0.00374658 |
| B1-3 → B2-3 | 真正改口後，A 改為同事檢查、員工修前端、同事複查、店長驗收；B權限／驗收與 A付款細節保留，天數不捏造 | 1＋6／0.00358909 |
| 新 Context 回查 | 只載導覽／既有工具，先搜尋青禾、拾光、備份；第25次在送出前被測試24次上限擋住，無最終回答 | 3／0.00074854 |
| **本輪合計** | **3次整併發布完成；完整情境未完成** | **24／0.01148693** |

24個送出請求均 HTTP200／completed，不表示整組成功。SDK 將第25次 before-request hook 停止包成 `OpenAIConnectionError`；原腳本上限與24筆紀錄支持這個診斷，不是外部斷線。未重試、未放寬上限、未多開 client 續跑來繞過額度。

三次 B2 均6步／5工具，未觀察到工具格式、引用或 exact-edit 錯誤。模型仍選擇可選預檢，首批還讀了已提供的導覽；本次**沒有證明工具操作已最省成本**，也沒強迫它一定整檔重寫。新導覽未納入設備搬運別名，但該細節留在正文與詳記；能否靠日常自然問法找到，仍未驗證。

本輪可見內容支持 MP-02d/e 的限定樣本改善；沒有足夠證據聲稱所有問題已解決。過去5次66請求／US$0.03212434，加本次共 **6次90請求／US$0.04361127**，不是產品一輪訪談費用。真測重用現有流程，只有暫存 Saver／Store／SQLite；不代表產品原生推理、compaction、MP-01計數端點或長訪談都通過。

## 4. 驗證、記錄與下一步

- 內容證據保留完整 B1 產物、各批發布正文／導覽、每階段初始可見輸入、實際提示／schema、可見模型輸出及去重工具回覆、usage、精確 diff、原檔 SHA256。未收 key／headers／opaque reasoning；最後工具沒有下一請求時，回傳內容可能未被封包紀錄捕獲。
- 回歸：抽取／抽取修正／整併／整併修正／交付／引用六檔 **160 passed，9.73s**；`compileall src tests` 通過。這些測試保護機制，不是另一份模型品質驗收。
- 全套首次由主審漏設測試 DSN 的 `connect_timeout`，既有安全 fixture 拒絕：20 failed／489 passed／19 errors，43.43s。補正測試參數，不改產品／fixture，不重啟Docker；重跑 **528 passed／0 skipped，67.19s**，包含專用PG，1項既有TestClient deprecation warning。`uv lock --check --offline`／`git diff --check` 亦通過。
- **獨立 review 通過：**無 Critical／Important／Minor finding。reviewer 核對窄 diff、實際三批問答／產物、24筆費用、schema、原檔及提示hash、短稿／README；支持保留B1窄修為限定單樣本改善，不支持MP-02d/e全面CLOSED。全程唯讀、未派工／付費；528項為主審重跑，不冒稱reviewer也重跑全套。
- **下一個 gate：**先交付本次限定改善。完整 fresh-context 回查仍 OPEN；後續只設計可獨立執行的既有成果回查，不盲重跑抽取／整併，也不在本輪追加付費。若涉及新的恢復／保存機制或額度變更，先討論，不為測試而改產品。
- **不變：**MP-01 404與原生延續相容仍 OPEN。ABC／五產物／引用／員工工作方法不翻案；沒有新Memory欄位／框架、主顧問改動、JD／UI、production 或 merge/push。
