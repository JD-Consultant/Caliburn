# 完整原話已可容納時，Memory 是否增加 JD 分析價值

狀態：八次配對分析已完成，兩組均通過 42／42 個核心判準；原話＋Memory 組未呈現穩定額外收益，累計輸入多 37.3%。新增估算占用 US$0.024165235，耗時 5.66 分鐘。見[結果與設計建議](results.md)、[語意判讀](semantic-review.md)及[方法與腳本審查](review.md)。這是新的小型配對實驗，不續跑或修改先前停止的四組實驗，也不據此切換正式產品。

## 問題與比較

完整訪談原文可放進 Context 時，額外提供已整理的 Memory，是否能改善 JD 的分析、更正或依據選擇？

- **原話組**：完整正式訪談、同一 JD 底稿、原話查閱工具。
- **原話＋Memory 組**：上述材料，加上自然生成的情境／理解導覽與按需讀取能力。

兩組均為 Luna/high，以全新 Context 開始，不帶入舊 reasoning、工具結果或 compaction。共兩項複合任務、每項兩次重複，共八次獨立分析；第二次重複交換兩組先後順序。共同方法沿用現行顧問指引及工作分析／JD 指南，不強制 Memory 組閱讀、不替原話組削弱指示。

本次交付是**修改提案**，不寫入正式 JD，也不測資料庫交易、恢復或新摘要機制。讀取資料取自已保存的真產品輸出，Memory 工具的名稱、schema 與正文格式沿用產品契約；研究用的 `submit_jd_review` 只蒐集指定欄位的新文字、依據及待釐清問題，不代表產品工具已修改 JD。

## 素材與公平性

原件來自相鄰資料包 `compaction-long-interview-2026-10-04/main-03/compaction_hierarchical_memory/` 的 `product-052.json` 與 `memory-e052.json`。前者有第 52 段成功完成後的正式對話；後者的處理上界為訪談序號 104。後續回提測試的第 53–60 段不進入本次素材。

兩組保有相同員工與顧問完整原話，明確標示序號、說話者和原文。從同一份 JD 投影出可編輯文字，研究者植入相同的人工錯誤與缺漏，作為更正試題；不把這些植入錯誤說成正式產品曾犯的錯。原始 JSON 不修改，來源檔、程式、共同指引、工具與試題均在外送前保存雜湊。

評分準則另存，不進入 App 參考資料、工具結果或模型指引。允許等價表達、不同查閱路徑及合理不改稿；不能僅依包含關鍵詞、來源存在或 API 成功判為正確。

## 任務與判讀

1. **更正與範圍**：退貨的週一時點與交表期限、驗收不良比例的分母／嚴格門檻、月末帳齡表交付時點；保留未受影響的設備備品、收貨及週報要求。
2. **分散資訊與責任**：召回範圍待確認的判斷、休假交接中的本人責任、文件保存年限及冷藏退貨溫度門檻的未知；不補造權限或數字。

逐項對照正式員工發話，分開判讀：提案內容是否正確、是否有無關更改、直接來源是否足以支持主張、未知是否保留。統計每次實際輸入／輸出／推理／快取 tokens、模型請求、閱讀次數與回傳長度、耗時及本機估算費用。Memory 已有生成成本另列；不得把本次免重建誤寫為 Memory 沒有成本。

兩次重複只用來觀察穩定性，不足以作統計顯著性或所有職務的普遍結論。若 Memory 沒有改善，或多讀資料反而增加負擔，照實記錄。

## 有界執行

使用者本次授權：新增估算占用至多 **US$0.20**、付費階段至多 **30 分鐘**，計入原累計 **US$2**；已知先前估算占用 **US$1.000591120**。護欄屬本機研究管理，不是供應商帳單的硬上限，也不恢復產品金額攔截。

SDK 自動重試關閉。每次生成前，以同一完整請求遠端計數並預留輸出費用；未知回應不退還預留。最多 64 次外送（含計數）、32 次生成，每次最多 8,192 output tokens，每項分析最多六次模型回應。速率等待依官方回應標頭；時間、費用或次數界線到達即停止，不改 prompt 或重送同一未知請求。第一個 provider 失敗停止整批，保留已完成與未完成部分。

不連資料庫、不啟停其他程序、不改正式產品、不 push／merge。生成原件存於新的 `live-01`；拒絕覆寫既有 run。公開 trace 以長度與雜湊代替加密內容，模型接續仍保留原生完整 reasoning items。

## 工作順序

1. 完成素材投影、錯誤版本、獨立判準、資料隔離與費用護欄測試。
2. 離線檢查兩組共同材料完全相同、來源鏈可解析、原件雜湊一致。
3. 凍結 manifest，執行八次配對分析；逐次保存實際請求、工具結果及提案。
4. 按來源逐項語意判讀，整理內容、依據及用量差異；代理判讀與真人複核、通過與未施測分開寫。

## 保存資料與離線查閱

- `cases.json`：凍結題目與獨立判準。
- `live-01/manifest.json`、`initial-*.json`、`tools-*.json`：實際使用的來源雜湊、各格初始材料與工具。
- `live-01/trace.jsonl`、`result-*.json`、`result.json`：外送、回應、工具讀取、提案及用量原件。
- `live-01/metrics.json`、`after-*.json`、`memory-preprocessing.json`：可從原件重算的指標、提案後欄位與既有 Memory 成本。
- `live-01/executed-experiment.py`：當時執行碼；研究腳本後來有停止分支修正，保留此副本供雜湊核對，不追改 manifest。
- `live-01/executed-support.py`：本批實際使用的 support 原件。下一批替代價值比較參數化共用費用／時間護欄前保存，其雜湊與本批 manifest 相同；本批結果與原件不因共用碼後續調整而改寫。

在儲存庫根目錄離線重算；不讀金鑰、不連模型或資料庫：

```powershell
uv run --project apps/api --locked python -X utf8 -B docs/experiments/product-validation/data/memory-added-value-2026-10-04/analyze.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/live-01
uv run --project apps/api --locked python -X utf8 -B -m pytest docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_support.py docs/experiments/product-validation/data/memory-added-value-2026-10-04/test_runner.py -q -p no:cacheprovider
```

重算指標不會重做語意判讀。既有 run 不可覆寫；任何新的付費比較需另外確認範圍與界線，不因本頁保存 `--live` 程式便取得重跑授權。

## 方法參考

[OpenAI Memory Evals](https://developers.openai.com/cookbook/examples/agents_sdk/context_personalization#memory-evals)建議以相同任務比較有無 Memory，並評估生成、整理與注入整條流程；本次縮小到完整原話可容納的附加價值，保留前處理成本。分析方法依[工作分析指南](../../../../guides/2026-09-09-complete-work-analysis-guide.md)、[訪談校準](../../../../guides/2026-09-09-customized-jd-depth-and-interview-calibration.md)及[JD 寫作指南](../../../../guides/2026-09-09-jd-field-and-writing-guide.md)。
