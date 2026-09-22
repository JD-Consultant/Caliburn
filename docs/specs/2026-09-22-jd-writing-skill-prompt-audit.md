# JD 撰寫方法 Skill 與主顧問提示審核

日期：2026-09-22；Topic：JD-R002。承接[官方預研](2026-09-11-jd-skill-current-official-preflight.md)、[顧問接線沿革](2026-09-14-jd-consultant-guidance-and-skills-slice.md)、[完整工作分析](2026-09-09-complete-work-analysis-guide.md)、[JD 欄位與成文](2026-09-09-jd-field-and-writing-guide.md)、[深度與訪談校準](2026-09-09-customized-jd-depth-and-interview-calibration.md)及現行 A／B1／B2 分工。本文件是 9/14「暫不採用 `write-customized-jd`」的窄幅 successor；不改寫該日的歷史證據。

## 1. 問題與結論

現行主顧問知道六章 JD 與可用工具，三項分析 Skill 的結尾也會要求在成稿前讀取 `write-customized-jd`，但正式套件沒有掛載該 Skill。結果是：模型可以訪談、讀 Memory 及操作 JD，卻沒有正式可達的責任／任務／O／P／K／S 成文方法；三項分析 Skill 還形成無法解析的路徑。

採用既有預研的最小方案：

- 保持同一個 A 主顧問與同一組 JD 工具；不新增 JD Agent、寫入者、審核引擎、資料表或 Domain 規則。
- system prompt 只增加觸發與路由：日常訪談不載入；實質撰寫、修訂或全面核對 JD 時才讀 `/skills/write-customized-jd/SKILL.md`。
- Skill 正文只保存任務契約、何時使用、依據順序、保存邊界與收尾標準；詳細成文規則及完整性核對分成兩份按需 reference。
- 目前 JD 是文件 authority；工作理解提供穩定工作範圍，案例保留條件／差異，必要原始訪談提供證據／更正／邊界，最新已保存但尚未被 Memory 承接的對話防止剛說完的內容遺失。手改不自動成為訪談事實。
- O／P／K／S 依本產品既有定義成文；不要求一對一、不為填欄位補造 KPI、時限、資格、知識或技能。

## 2. 與 A／B1／B2、Memory 及 compaction 的界線

- **A** 仍負責訪談、Working State、按需回查與 JD 操作。JD Skill 是 A 在特定工作階段讀取的方法，不是新的角色。
- **B1** 仍把原始訪談反覆整理成完整案例；**B2** 仍由案例反覆整理穩定工作理解。兩者不載入 JD 成文方法，也不因本切片改 prompt、publication、版本或引用規則。
- Skill 只讀既有 context 與使用既有工具，不修改 Memory。JD 需要的依據仍由 Runtime／工具提供，模型不產生持久 ID、版本、scope 或來源 token。
- continuation compaction 仍只處理 model request 的對話延續，不壓縮或改寫 Skill、JD／Memory context、Runtime 規則及當輪必須逐字可見的未處理輸入。

## 3. 提示設計依據

2026-09-22 複核：

- [OpenAI GPT-5.6 prompting](https://developers.openai.com/api/docs/guides/latest-model?model=gpt-5.6)：提示應給 domain context、硬限制、核准邊界、成功標準及重大歧義處理；偏向精簡、每條規則只說一次，不替模型規定所有執行步驟。
- [OpenAI GPT-6 Astra prompting](https://developers.openai.com/api/docs/guides/latest-model)：Skill／檔案中的指令會強烈影響行為，必須清楚標示優先順序並消除衝突。
- [OpenAI Build skills](https://learn.chatgpt.com/docs/build-skills)與[Anthropic Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)：先暴露名稱與用途，需要時才讀正文與補充材料。

本案因此把「何時使用」放 metadata／system route，把產品硬限制與成功標準放 Skill，把細節放 references。沒有把完整 JD 教材塞進每輪 system prompt，也沒有把提示改成固定逐步 SOP。成文方法本身需要層次與雙向核對，屬產品要求，不是要求模型展示隱藏推理。

## 4. 正式檔案與不變項

| 責任 | 正式位置 |
|---|---|
| 何時載入 JD 方法 | `experiments/jd-relational-app/src/jd_relational/consultant_guidance.py` |
| Skill discovery／唯讀檔案路由 | `packages/consultant-memory/src/caliburn_memory/skills.py` |
| 觸發、依據、工具與保存邊界 | `packages/consultant-memory/src/caliburn_memory/skills/write-customized-jd/SKILL.md` |
| 職務目的／責任／任務／O／P／K／S 與有界修訂 | `write-customized-jd/references/writing-and-correction.md` |
| 完整工作範圍與工作↔JD 雙向核對 | `write-customized-jd/references/complete-work-guide.md` |

不改 `WorkingStateUpdateInput`、Memory schema、A／B1／B2 graph、JD Domain／validator、tool name／args、provider、compaction、保存或撤回語意。既有工具 description 已通過 strict wire 與真實工具路徑，本輪不複製整套寫作教材到每個 tool description。

## 5. 驗收與後續 gate

反例先固定：四項方法都能從模型實際 `/skills/` 路由讀到；metadata 不預載正文；所有 Skill 內命名路徑可解析；JD Skill 明確排除日常訪談與 B1／B2，並保有目前的工作理解→案例→必要原話→最新未承接對話依據順序；O／P／K／S 與雙向完整性規則可按需取得。

完成後依序驗：

1. 提示／Skill 固定契約與相鄰 A／B1／B2／compaction 離線回歸；
2. 一次短而自然的真 Luna JD 撰寫／修訂，核對是否真的按需讀 Skill、使用正確依據、產生可保存且可自然收尾的結果；
3. 再執行正式 16K 自然長上下文驗收，確認 compaction 後仍保留未處理輸入、目前工作與 JD 寫作契約。

短測不能替代 16K gate；離線全綠也不能冒稱自然 JD 品質通過。

## 6. 離線結果

- 提示與 Skill 契約：**19 passed**；反例先因缺少正式 Skill／路由失敗，接線後轉綠。
- A／B1／B2、context、Memory context 與 continuation compaction 相鄰回歸：**99 passed**。
- `consultant-memory` 套件：使用新 App 已鎖定的同一 runtime 離線執行，**283 passed**。
- `uv build --offline` 成功；wheel 內含四份 `SKILL.md`，且含 `write-customized-jd/references/writing-and-correction.md` 與 `complete-work-guide.md`。
- 已知警告只有既有 Pydantic serializer 警告與 Windows pytest cache ACL；沒有由本切片產生的測試失敗。套件目錄直接執行 `uv run` 曾因隔離網路無法抓取既有依賴，改以正式 App lock/runtime 離線驗證；不是產品錯誤，也沒有修改依賴。

## 7. 短真 Luna 結果與正式 16K 前置修正

短真 Luna 已完成，JD 成文方法與提示 gate 通過：模型按需讀取 `write-customized-jd` Skill 與 references，依目前 JD、工作理解、案例及必要原話建立 duty、task、O／P／K／S 與 task↔K／S 關係；沒有把案例逐筆抄成任務，也沒有自創 KPI、班別或越權責任。六筆 JD mutation 均取得 confirmed／committed receipt，最後以自然繁中說明已完成內容及仍未知事項。首次錯誤 `container_ref` 依 tool error 重讀 `jd_read current` 後自行修正，證明 model-facing description 與既有 Domain／Runtime 邊界可合作，不需新增 JD Agent、validator、fallback 或 prompt 後處理器。

同一 run 也揭露正式 16K gate 前必須先修的 compaction 缺口：25 次 provider response 雖全部 HTTP 200，但 A 的最新 Human turn 保護把該訊息之後所有 completed tool waves 一併排除，導致 `continuation_compaction` 始終為空；25 次累計 2,085,926 input／9,874 output tokens，OpenRouter cost **US$0.37018134**。這不是 JD Skill 失敗，也不應靠縮短 JD 方法、降低 O／P／K／S 完整性或減少必要來源回查處理。

最小 successor 已沿唯一 `ContinuationCompactionMiddleware` 完成離線修正：最新員工原話仍逐字保留，但其後已完整配對並離開最近八則尾段的舊工具 wave 可進 summary；下一輪新員工訊息會接替 protected orientation。沒有修改 Skill、JD／Memory context、B1 未處理窗口、B2 fixed task、canonical history、provider 或 16K 門檻。真實舊 checkpoint 現可選出第 41 則安全邊界，相關離線集合 **201 passed**。

## 8. 正式 16K 真 Luna 結果

修後 gate 已以 production A middleware／profile、正式主顧問 guidance、`write-customized-jd` Skill 與 GPT-5.6 Luna `medium／8192` 執行。輸入約 17,467 approximate tokens；最新員工訊息位於同回合起點，後續含八組已完成案例回查，以及最近八則逐字保留的 Skill、寫作參考、工作理解與目前 JD。

結果為 **PASS**：第一個 summary request 使用 12,255 input／1,543 output tokens，第二個 compacted main request 降為 4,867 input／1,960 output tokens，兩次均由 OpenAI／`openai/gpt-5.6-luna` 回 HTTP 200，合計 cost **US$0.00811258**。state v2 逐字保留最新員工 HumanMessage，summary 只涵蓋已完成至 `tool-8` 的舊 wave；最近八則與 canonical 25 則訊息未改。摘要保留共同工作、權責界線及未知事項；主回答自然形成 O／P／K／S，沒有工具格式、虛構數字、KPI、班別或越權責任。

原始 probe 曾因兩個測試自身問題報紅，均未改產品：兩次 body-size preflight 在 HTTP 送出前即停止，為 0 request／0 cost；一輪 test-only 誤把主輸出設為 2,048，summary 完成後 main 精確用滿上限，Runtime 正確以 `incomplete_compacted_model_response` fail closed，cost **US$0.01924770**。這與既有 Luna 研究的 `medium／8192` 互動基線一致，改回 production 值後即完成。正式結果最初另因 probe 硬寫帶日期 snapshot 而只剩模型名稱檢查 false；OpenRouter 實際回傳值正是 production 設定的穩定別名，provider 為 OpenAI，離線修正 evaluator 後所有檢查通過，沒有再送請求。

本 gate 實際 paid cost 共 **US$0.02736028**。它驗證 compaction 後的 A 續作與 JD 寫作契約，不替代完整 App 的保存、來源、撤回及背景 publication 旅程；後續不再為此重開 Prompt、Skill、Memory 或 compaction 架構。
