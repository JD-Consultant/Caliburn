# Q019 第二切片結果：Agent 循環完成，PostgreSQL gate 待驗證

- 日期：2026-09-06；狀態：**PARTIAL，不能宣稱資料庫 durable recovery 已通過**。
- 範圍：[第二切片計畫](../plans/2026-09-06-analysis-only-agent-durable-conversation-slice.md)。
- 實作：S:/caliburn/.worktrees/analysis-only-agent，codex/analysis-only-agent。
- 最新設計與決策仍在主 checkout：[Runtime](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-runtime-design.md)、[register](S:/caliburn/docs/current-decisions.md)。

## 1. 本段真正完成什麼

使用官方 create_agent；模型要求工具 → 官方工具執行 → 同一循環帶結果再呼叫模型。新增一個公開 wrap_model_call middleware，只縮小單次 request 的對話視圖。固定 instructions 不放進 canonical messages，也沒額外設計隱藏思考筆記或第二份對話儲存。

沿用第一切片的 inline compaction helper，沒有換成會永久移除 canonical messages 的 generic summarizer。這是 Q019 已核准的效果選擇，不宣稱所有廠商實作相同。
[LC transient/persistent context](https://docs.langchain.com/oss/python/langchain/context-engineering)、[OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)。

## 2. 檢查與誠實界線

- 原有 8 項測試仍通過。
- 新增 compiled Agent 離線測試：工具接力的 encrypted reasoning／phase／tool pair；下輪 request 從 compaction 延續，原對話及工具結果仍保留；模型失敗後 None 續跑不重複員工輸入／已保存的測試 reader；文件 thread 隔離。
- 目前合計 **11 passed、1 skipped**；compileall 通過。只替換 HTTP 邊界，LC／SDK／compiled graph／serializer 是真的。InMemorySaver 只能證明這些接線，不是磁碟保存證據。
- PostgreSQL opt-in test 已寫：官方 PostgresSaver + setup、真實兩個 Python process、另一連線在模型回覆前看見 employee input、失敗後重新開啟續跑、native items／compaction／thread 隔離。**本輪沒有執行成功，不能據此算完成**。
- 無 paid API、無 .env／金鑰讀取、無外部 tracing；API 費用 0。Synthetic opaque strings 不是服務端有效加密內容，不證明模型實際分析品質或 effective all_turns。

依據：[PostgresSaver setup](https://docs.langchain.com/oss/python/langchain/short-term-memory)、[sync durability](https://reference.langchain.com/python/langgraph/types/Durability)、[persistence/recovery](https://docs.langchain.com/oss/python/langgraph/persistence)。測試停在已保存工具結果後的 provider exception；不是 arbitrary power-loss／外部副作用 exactly-once 證明。

## 3. 實作中遇到什麼

### 測試假設修正，非 framework patch

初版測試期待 outgoing assistant text 仍有伺服器 msg ID。實際 source 顯示 store=False 時 adapter 刻意不輸出這個 lookup ID，但保留文字與 phase；reasoning encrypted content、call_id 也維持。測試改驗真正的延續內容，不修改框架 private converter、不捏造 ID。
版本依據：langchain-openai 1.6.0 的 chat_models/base.py，assistant content 重組區塊（store is not False 判斷）；[官方 adapter source](https://github.com/langchain-ai/langchain/blob/master/libs/partners/openai/langchain_openai/chat_models/base.py)為動態連結，重現以本切片 uv.lock 為準。

### Docker 環境 blocker

已安裝 Docker Desktop，但啟動時 backend log 明確顯示：
「initializing Inference manager… dockerInference… The file cannot be accessed by the system」。

這發生在 Docker engine／PostgreSQL 啟動前，不是 Saver 或 Agent 的錯誤。容器查詢無正常回覆；只啟動既有 Desktop 並讀取診斷，沒有 reset、移動 socket、終止其他服務、刪 DB 或資料。沒有另裝一套 PostgreSQL 迴避此 gate。需要先恢復 Docker，或明確提供可用的專用測試 PostgreSQL。

## 4. 尚未做與下一個 gate

沒有 UI、B extraction/consolidation、C live repair、Memory 搜尋、Skills、完整 token/run budget、非同步／串流或 JD；不接舊 App。這只是同步 Agent 的接線段落。

下一步：Docker 修復後建立／指定專用 q019_agent_test DB，跑目前已寫的雙 process 測試。失敗先依官方 API 找原因，不跳到 B/C；通過後再進 Memory artifact/read-path 的下一個小段。不存在新產品需求待裁決，当前 blocker 是測試環境而不是需要重新討論 Memory 選型。

## 5. 保存與 review

獨立 review：Critical 0、Important 程式阻塞 0；reviewer 獨立重跑 11 passed／1 skipped。兩項 Minor 已補強：直接斷言 canonical 的完整原生 AI 區塊；測試 DB 的 connection／statement／lock 等待有界。後者仍須 PostgreSQL 實測，不能把設定完成稱為 DB 測通。

Review 修正後再跑：11 passed／1 skipped、compileall、uv lock --check --offline 與 git diff --check 通過。工程初值是測試 connection 1–10 秒、SQL 10 秒、lock 5 秒、子程序 45 秒；不是模型費用上限或業界統一值。[PostgreSQL timeout 設定](https://www.postgresql.org/docs/current/runtime-config-client.html)。

本地保存 tag 預定 q019-agent-loop-offline-v1，精確 commit 見主 register；標籤只代表離線循環切片，不代表資料庫驗證通過。此稿不授權 merge／push／production。
