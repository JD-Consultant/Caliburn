# 固定需求的代表職位前五實驗

授權：使用者同意五份需求、四組比較與逐份分級。研究依據為[評分 v2](../specs/2026-10-04-representative-occupation-scoring-protocol.md)；本批界線見[事前協定](../experiments/2026-10-04-representative-occupation-top5/run-01/protocol.md)，不作 production 接線、commit、push 或清資料。

1. 凍結原話、手動分段来源片段、七個校準例、Prompt／schema／版本／費用上限；先做融合去重與證據拒絕反例 Red–Green。輸出供 2／3 使用，同一 hash 必須保持。
2. 重用已確認的隔離 GPU／Qdrant，計算 15 個新查詢的向量與 805 全排名，核真 DB exact 前 20；rerank 300 pairs 並保存分窗，產生四組各五份。保存一次品質及三次暖機計時，來源／查詢 hash 供 3 綁定。
3. 校準七例後，盲評每個員工／公版唯一組合；使用原始員工而非縮小後查詢，保存全部請求／回應／證據／usage，遇到失配不默默改答案。最多 US$1／107 Responses，沿現有 pricing adapter。
4. 逐案報五份分級與代表範圍，不計總分／平均分；品質相近再比較成本。獨立核對去重／融合／排名／證據／封存原件，清楚寫開發案例及模型評判限制；停止本輪自有服務，保留 weights／資料及所有失敗。

Pre-flight：任務 1 的原話／查詢／rubric hash 被 2／3 消費；2 的查詢／公版全文 hash 被 3／4 消費。全部用同版工作原件及來源，評審分數不供 2 選前五；未見契約衝突。

進度原件：[run-01/progress.md](../experiments/2026-10-04-representative-occupation-top5/run-01/progress.md)。
