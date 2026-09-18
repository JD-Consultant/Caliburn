# CT38：high 抽取接回 medium 整併的小型驗證

2026-09-08 · LLM-Q019 · Owner 同意 CT37 下一步；只做隔離驗證

## Preflight

- **Topic／唯一問題：**B1 改 Luna high 後，資料是否保真，並能沿現有 B2 medium 整併與增量更新，避免全面增加訪談成本？
- **Stage：**G3方向已同意，G4／G5局部驗證；不是production施工。
- **Binding：**[CT37結果](../specs/2026-09-08-ct37-prompt-effort-comparison-results.md)與[root register](../../../../docs/current-decisions.md)。提示／模型預設均未採用新候選；CT35/C停放、ABC架構、工具與背景通知時機不變。
- **已讀證據：**CT37兩份報告及原8則fixture；現有B1／B2 graph與測試。上一輪`pipeline`固定medium且重跑B1，不能用它冒充high接續。
- **不做：**JD、Web、production／PostgreSQL資料變更、完整長訪談、增加Agent／欄位／新語意驗證器。

## 最小步驟與停止規則

1. 用**現行提示＋B1 high**重測原8則來源，補CT37缺少的對照；不另改提示。若未通過，最多再用封存CT37候選＋high同來源測一次，不新增第三版提示。
2. 主線讀完B1實際輸出；可用的同一B1 graph／Store產物，直接交給**現行B2 medium**。不手改內容、不重建另一份假B1、不將舊成功輸出冒稱新生成。
3. 若第一個完整鏈路通過，追加一段合成補充：釐清技師爭議經驗與核准權限。再次B1 high→B2 medium，檢查更新到正確主題，且舊案例、頻率、權限、適用範圍沒有遺失。模型不知道人工評分規則。
4. 每階段存原始可見input/output、模型實際effort、來源與引用、前後Memory、模型/工具次數、usage。沿引用核對原文與未修改來源；在prompt保真失敗／框架錯誤／上限時停止，保留失敗，不偷偷調設定重跑。

使用既有官方模型接點及graph，以InMemorySaver／InMemoryStore及SQLite記憶型publication隔離；過程保留同一執行物件，人工查看後才續下一階段。這不是驗證服務入口、持久重啟、compaction或背景排程。合成後續對話不是CT15歷史的一部分，不改其封存資料。

**觀察標準：**沒有做過與沒有回答分清；員工的印象／不確定不升格為事實；後續明確補充更新相應內容；雲杉果汁機／海鷗除濕機與新增案例不混淆；每日收件、工作量、單案3工作日不變通用標準；同批候選/詳記交付全等、引用可回查。API完成或格式通過不等於語意通過。

## 費用與可追溯性

Owner本輪同意續驗；本輪新建CT38帳本，自設**最多20次實際HTTP嘗試／US$0.10**，含SDK重試與B1/B2。沿既有保守預留／官方usage計算，無usage不當零費用。單次輸出仍4,096；B2每job最多8模型步／12工具。到界停止、不自動追加，不重開CT37 closed帳本。主顧問不呼叫，保持medium產品預設。

研究依據沿CT37來源；本輪重讀[OpenAI reasoning effort指引](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6#reasoning-effort)：先建baseline、確認成功條件，high要有實測收益，不全域使用max。[官方agent model選擇](https://developers.openai.com/tracks/building-agents#how-to-choose)支持依工作難度／成本區分模型責任，但沒有指定本案B1 high／B2 medium必然最佳；後者是本次待驗映射。以上於2026-09-08讀取，不重做Memory全架構研究。

**退出：**支持／不支持／仍未明，回寫結果與register。即使通過，也只建議下一個局部設定變更，不宣稱完整訪談已穩定。若實際需改模型接線／預設，另列最小變更，不在測試中偷偷落地。

## Closure（2026-09-08）

- [逐段結果、成本與完整證據](../specs/2026-09-08-ct38-high-extraction-medium-consolidation-results.md)持有本輪結論，避免計畫重複堆全文。
- 步驟1–4完成：現行提示high未過；封存候選high→B2 medium及追加澄清鏈路局部通過，措辭瑕疵明列。未新增第三版prompt或改產品預設。
- 13請求／usage估US$0.01693435，帳本closed；118離線回歸通過。引用及來源、B1/B2實際交付核驗完成；不外推主顧問／長訪談／PG持久化。
- 下一唯一gate：Owner審是否在隔離app採用候選並分開B1 high注入；主顧問與B2維持medium，再續正常訪談驗收。
