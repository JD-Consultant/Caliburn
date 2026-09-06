# Q019-MEM-SUMMARY-01 — 詳記重抽、引用及更正路由

2026-09-06 · **隔離切片已完成：226 passed／0 skipped；獨立 R1／R2 複核 CLOSED，無未處理的重要問題。不是 production 或模型品質報告。**

範圍與授權：[main register](S:/caliburn/docs/current-decisions.md)、[接法 §7](S:/caliburn/docs/specs/2026-09-06-interview-summary-correction-routing-proposal.md#7-已授權的小切片工程接線)。執行：[短計畫](../plans/2026-09-06-summary-reextraction.md)；使用：[README](../../experiments/analysis-agent/README.md#summary-re-extraction--q019-mem-summary-01)。基準 `e1a3cbf0`，分支 `codex/analysis-only-agent`。

## 1. 已接的流程

1. 普通 B1 仍處理新訪談，重送同一完成來源不重跑。Runtime 明確選既存詳記重抽時，取回同一 source/context 原文，不改員工聊天、不擴成全部歷史。
2. B1 原三字串結果另存詳記／候選。原詳記可回查，新的真實引用由 Runtime 提供，模型不填來源 ID、位置、版本或 Skill。
3. B2 收到新產物與新舊詳記地址，重新看目前理解及相關詳記，更新受影響結論與引用。普通跨段更正也要保留案例層目前說法，不能只看一般工作模式有沒有變。
4. 新正文／導覽準備及驗證後，沿現行 publication head 原子切換。重抽用 repair 語意，不回退或推進普通新來源游標。C 先發布則 B2 重讀新版本及必要修補問答；不重抽 B1。
5. 讀取仍是小導覽→相關目前正文→選中詳記→必要時原始問答。舊詳記不自動附带後來所有更正，也不自動跳到新版本。

## 2. 官方依據與映射差異

| 目的 | 已研究官方依據 | 本切片實現／界線 |
|---|---|---|
| 同邏輯來源可再抽取 | [Codex Phase1](https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/src/phase1.rs#L228-L325)、[Stage1 update](https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/state/src/runtime/memories.rs#L853-L942) | 按需同視窗重抽，而非重讀無限累積 thread；舊 artifact 不原地改写，另存新地址 |
| 目前知識維護更正及引用 | [Consolidation](https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/memories/write/templates/memories/consolidation.md#L306-L351) | B2 instructions＋public file tools；不做 deterministic 語意裁判，也不自創 Case table |
| 漸進深入而非每次讀到底 | [Reader](https://github.com/openai/codex/blob/ac192cd7937b0d73edc6dffe009940ae53782dd4/codex-rs/ext/memories/templates/memories/read_path.md#L33-L73) | A 固定／可修補讀取視圖皆提醒先看目前理解與更正，詳記只是其來源範圍的歷史敘述 |
| 公開框架保存／恢復 | [LangGraph durable execution](https://docs.langchain.com/oss/python/langgraph/durable-execution)、[DeepAgents backend](https://docs.langchain.com/oss/python/deepagents/backends) | Saver 保存技術 job，StoreBackend 保存內容；沒有 framework 私有 API patch |

本案 publication head、不可變地址、runtime header 和 job receipt 是已採框架的應用接線，不聲稱 OpenAI 使用相同 schema、資料表或交易方式。全部 source 細節與限制留在[原研究](S:/caliburn/docs/specs/2026-09-06-openai-rollout-summary-correction-source-review.md)，沒有為此次施工重新編造原廠事實。

## 3. 測到的問題與修正

- **同來源被當已完成：**原先只有 source 比較；改按實際抽取產物識別 B2 工作，重抽不再被跳過。
- **歷史工作重送再次收費：**僅最新 B2 checkpoint 不足；用 runtime 決定的工作 operation 查既有 receipt，跨其他工作重送也不重新發布。
- **前置問題遺失風險：**重抽沿已保存的 context-only 範圍，必需前置問題／中間員工回答保留；大小超出拒絕，不用不含前置問答的零 context 假設。
- **來源與模型文字混淆：**header 明確寫 none 及終止行；獨立 review R1 再發現舊格式正文仍可偽裝終止行，因此加上檔案最開頭的 Runtime 格式標記。舊格式原本固定以標題開頭，模型正文不可能冒充這個檔頭。舊實驗 header 沒此標記仍可讀，但不能自動重抽；沒有猜測性兼容或改寫舊資料。
- **放寬額度卻拒絕重抽（R2）：**來源30字、context2字原本可在40字內抽取；把context額度放寬至20後，重新planner會擴大可選context，反而分成兩窗。改為共用原文完整回合驗證、直接計算原保存範圍，不重新選窗。來源/context未改，上限仍有效。
- **HTTP 故障測試：**假 transport 的 RuntimeError 會被真 OpenAI SDK／LangChain 包成連線錯誤；測試依真例外類型檢驗 pending/resume，不改框架錯誤處理來迎合測試。

## 4. 驗證及審核

- RED→GREEN：8項 missing-feature 失敗→通過；再加2項重送／來源界線 RED→修正。之後補跨段更正、stale 及上限，focused 13 passed。
- 真框架＋假 HTTP；模型名稱只是既有 fixture 的 Luna，**付費 API 呼叫 0**，沒有遠端 tracing。
- 最終全 suite **226 passed／0 skipped，28.00秒**；包含15個新增行為用例及2個新增PG恢復用例，基準209個保留。先前222是中途快照，不當最後交付證據。
- 真 PostgresSaver／PostgresStore／SQLAlchemy publication：關閉重建所有 clients，分別恢復保存前中斷和已提交但回覆遺失；不重跑已完成模型，cursor、原文及新舊地址可回查。
- `compileall`、offline lock check（73 packages）通過；套件版本／lock 未改。Docker 現有 `caliburn-q019-postgres` 未重啟／reset，只用 loopback55433 的 `q019_agent_test`。清理僅限測試建立的唯一文件及其 checkpoint／Store／receipt，無使用者資料删除。
- 獨立 reviewer 找出 R1/R2，主 agent 重現2 RED後修正，focused70 GREEN；獨立限定複核再執行兩項回歸通過，**R1 CLOSED／R2 CLOSED**。本切片規格與品質審核通過，沒有未處理的重要 finding；不是 production／整分支 merge 審核。

## 5. 未承諾與下一步

這些測試證明資料流、隔離、引用可用、重試及發布；不證明真模型每個案例細節一定抽對／全部語意更正都識別。沒有自動找齊所有舊詳記同步、歷史 GC、案例資料表、API、UI、排程或 JD 編輯。第一版分析-only 範圍不變。

完成此段審核與本地保存後先回報；不自行開始 Q019-APP-01 Task3 或付費品質測試。若要任意舊詳記自動附全部後續更正，屬新的效果要求，需回到接法稿討論，不由本實作偷偷加入。
