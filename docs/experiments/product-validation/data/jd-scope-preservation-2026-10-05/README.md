# 固定 Memory 下的 JD 必要限定保留比較

2026-10-05。隔離研究，未改正式產品。承接[自足理解單元實驗](../memory-coherent-units-2026-10-05/results.md)。

**本批已結案。**16 次皆完成；完整任務為原指引 21 完整／4 部分、候選 24 完整／1 部分，兩組局部片段皆符合必要條件及範圍。候選仍有讀後漏項與額外責任推論，未替換正式產品。見[結果與 token](results.md)、[逐題判讀](semantic-review.md)及[執行紀錄](execution-notes.md)。

## 問題與最小比較

上一批的三個部分項都已保存且被讀到，缺在 JD 產出；增加 Memory 層數或重讀原話不能直接解釋這個缺口。本批固定上一批候選生成的 Memory，只比較顧問新舊指引，檢查「精簡」是否能同時保留必要限定並排除無關資訊。

工作假說是：既有指引雖列出責任、數值等面向，卻未清楚區分完整任務與局部片段的必要資訊。候選把取捨改為先確定本次範圍，再核對省略是否改變責任或條件。這是待測假說，不宣稱已查明模型內部原因。

- `baseline`：上一批凍結的 reader 指引原樣沿用。
- `scoped`：相同指引加上 [scope-method.md](scope-method.md)；沒有題目答案或指定標題。
- 固定 `Luna/high`、16,384 輸出上限、相同唯讀工具、原生接續、來源權限與完成 schema。未測 compaction。
- 四題完整任務沿用舊問題與 16 項凍結判準；交付後與例行維護另各重複一次，共六個配對回歸題次。兩個單一細節反例各跑一對；合計 16 個獨立 episode。
- 每題從相同固定快照及空白讀者歷史開始，不帶前題答案；只給問題與 map，正文自行按需讀。兩個 Prompt 組別看到逐位元相同的 Memory。整理端不重跑。
- 既有工作及題目已被用於候選設計，屬已知案例回歸，不能估計跨職務泛化效果。兩次重複也不是兩名員工。

## 事前判準

沿用舊 `grading.json`，不改上一批分數。完整任務的 `shared_authority` 仍是組合判準：客戶確認需求、本人約定前端、同事後端規則及部署均須可辨識；有一部分則列 partial。另列各漏項，避免組合分數隱藏差異。這是本批獨立任務的完整度要求，不推定產品每個欄位都要重抄共通分工。

新增反例放在 [narrow-cases.json](narrow-cases.json)，事前列必要與不應帶入的資訊：只補期限句，需保留起算點與「初判而非修好」；只補超約核准句，需保留觸發條件及角色界線。不得為追求完整多寫其他案、周期、低頻工作或不相關問題。仍沿用相同 `task.title/work` 格式承載這個片段，問題明示不重寫整項 JD。

分開記錄：

1. 必要資料是否實際進入讀者 Context。
2. 最終正文完整／部分／遺漏／錯誤，以及是否加入無關工作。
3. 引用實際讀過、來源鏈可達及語意支持。
4. 正文讀取數、原話回查、重讀 map、input／cached／output／reasoning tokens、字元、延遲及估算費用。

品質優先：不能以 token 減少取代必要限定，也不能以正文變長當改善。若候選只改善某題，逐題呈現；不重試挑好結果。新反例與原 16 項分開呈現，不改舊分母。

## 借鑑與界線

- [工作分析指南 §4、§10](../../../../guides/2026-09-09-complete-work-analysis-guide.md#4-案例工作理解與-jd如何取捨而不丟失)及 [JD 指南 §3、§4、§6–7](../../../../guides/2026-09-09-jd-field-and-writing-guide.md#3-職務目的職責任務同一份工作的不同縮放程度)：不是每句填滿所有面向，但責任與條件不能因縮寫而改義；未知不能補造。
- [大數據研究補充](../../../../research/agent-systems/2026-10-05-demand-loaded-memory-and-incremental-updates.md#8-從查詢與增量系統進一步借鑑)：共讀資料適度放在一起、局部載入、依變更維護。這些有助組織與讀取，不能保證 LLM 使用正確。
- [OpenAI GPT-6 指引](https://developers.openai.com/api/docs/guides/latest-model/gpt-6-astra.md#prompting-best-practices)：明確風格與優先順序，檢查會影響行為的多份指引；頁面以 Astra 的觀察為出發點，本批維持 Luna 實測，不把兩者效果視為相同。[Prompt 組織](https://developers.openai.com/api/docs/guides/prompt-engineering#message-formatting-with-markdown-and-xml)支持把指令、例子及資料分清。

## 執行界線

使用者核准本批最多 **US$0.05／15 分鐘**，計入原累計 US$2。前批估算占用 US$1.285104650。本批只可執行 `live-01` 一次，開始記號防止重跑；成本／時間／API 失敗即停，不補跑、不以剩餘額度再開批。token-count 暫留估算占用，不能當作確定帳單。

使用既有 `Workspace`、`run_episode`、Structured Outputs 及外送護欄，不啟停服務、不改資料庫。`prepare`／`verify` 無外送；`run` 才讀本機金鑰。模型請求只含合成資料，不含 grading 或既有結果。原件、版本、hash、工具結果及失敗都保留。未 commit、push 或 merge。
