# JD 導覽／按需讀取接點驗收（2026-09-24）

## 問題與選擇

先前保存的 C-W 續談檢查點顯示，A 的 request-only 視圖已失去 11 個目前 JD 項目的 ref；同稿重讀不是無故重複。該稿 `current` 三頁回傳 85,893 bytes，六章逐讀八步 88,650 bytes；單讀一個 Task 需要先有同版 ref。詳見[原始診斷](2026-09-23-gpt6-cw-natural-trial.md#同一已保存-checkpoint-的-jd-request-view聚焦讀取對照零付費)。

公開依據的共同原則是「先取得可導航的輕量線索，再按任務讀原文」；不是宣稱兩家公開了相同的內部檢索演算法。OpenAI 的 [Codex 公開指引](https://github.com/openai/codex/blob/main/codex-rs/protocol/src/prompts/base_instructions/default.md)偏好檔名與內容搜尋，OpenAI 的[大型 repository 實作經驗](https://openai.com/index/harness-engineering/)主張短入口作地圖、版本化文件作權威；[Claude Code 工具說明](https://code.claude.com/docs/en/tools-reference)公開了檔名／內容篩選、範圍讀取與可選的符號導覽，[Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)說明即時檢索、輕量 locator 與逐層展開的取捨。這些來源支持按需讀取，不證明 JD 的最佳路由或必須使用某一種索引。研究 [Agent Retrieval Bench](https://arxiv.org/abs/2607.24882)亦沒有找到所有任務通用的最佳檢索家族。

Caliburn 的最小選擇是既有 `jd_read` 增加只讀 `locator`，由同一 current snapshot 列六章與所有項目；必要時以該 ref 讀完整 `item/section`，範圍不明時回退 `current`。寫入仍只認已讀完、同版、模型當前可見的正文結果；不讓導覽、摘要、未讀／缺頁資料變成 JD 修改憑證。沒有新增 DB、Agent、向量索引、摘要權威或第二個 writer。

## 已執行證據

- 合約生成檢查一致；正式 App Python 全套 `3,207 passed / 323 skipped`；Web `310 passed`、TypeScript typecheck 與 production build 在本切片受影響版本通過。Windows 預設 pytest 暫存路徑曾遇 ACL 問題，改用新的隔離 basetemp 後全套通過，不計作產品缺陷。
- 同一保存 C-W 稿的唯讀離線量測：`locator` 六章＋11 項一頁 11,497 bytes；一項 Task 正文一頁 25,281 bytes，合計 36,778 bytes。此為工具回覆 bytes，**不是**完整 provider tokens、成本、延遲或品質收益。
- 正反例涵蓋同名異範圍、低頻未命名項、跨文件／版本／cursor、導覽 ref 不可寫、缺頁不能寫、讀甲改乙不能寫、完整多頁可寫、摘要移出舊正文後不得用舊 ref、無效舊讀取後仍可使用新有效讀取、摘要失效後與正式 middleware 的完整視圖回退一致。
- 有界真模型元件檢查：兩個同名職責分別指向庫存與出貨，GPT-6 Luna／OpenRouter Responses 在一個合成 `jd_read locator` 結果後，下一次請求選對出貨職責的 `jd_read item` ref。1 次實際外送，結算 **US$0.000521675**，零 JD 寫入。支出帳本留於本機忽略目錄，不含金鑰。這只證明一個小型合成情境的自然選擇與 provider tool wire。
- 同一全合成情境改以正式 `build_jd_tools()` 的 **10 個 JD 工具**提供給 GPT-6 Luna，模型仍在 1 次請求中選對 `jd_read item`，結算 **US$0.000954675**，沒有執行任何 writer。這是 JD 工具集合中的選擇檢查，**不是**完整 A 的所有 Memory／Working State 工具或自然訪談回合。
- 首次試圖對保存的 C-W 稿作真模型對照時，安全審核要求該份具體 JD 內容的明確外送授權；當時沒有發出請求。使用者隨後明確准許只送該稿的 17 筆唯讀定位清單到 OpenRouter／GPT-6 Luna。獲准後模型以 **1 次實際請求**（6,668 input、273 output tokens，結算 **US$0.000969925**）從 11 個項目中選對「出貨缺件」相關的既有 Task `jd_read item` ref，並由本機同版 `ReadService` 成功讀回正文；沒有發送整份原始訪談、沒有 JD 寫入。此為單一保存稿、單一題目的元件級 PASS，**未證明**模型會在完整 A 訪談中自發選擇、擴讀關聯或寫出高品質 JD。

## 尚未關閉

較大 JD 的更多題型候選命中／漏找、完整 A 的所有工具與自然訪談中的自發選擇、相鄰任務與共用 K／S 追查、來源語意、真實多輪步數與成本、完整專業 JD、瀏覽器旅程及最終品質 gate 仍 OPEN。若局部定位漏工作或多走模型步驟比全讀更差，先記 trace、沿現有 `current` 回退，不直接加搜尋服務或重做 Memory。自然模型測試不得替代完整訪談／來源／撤回驗收。
