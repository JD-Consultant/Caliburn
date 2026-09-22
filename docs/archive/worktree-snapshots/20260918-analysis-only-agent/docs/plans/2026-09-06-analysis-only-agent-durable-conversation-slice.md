# Q019 第二切片：Agent 循環與耐久對話

- 日期：2026-09-06；狀態：Owner 同意接續，隔離實作中。
- Topic：LLM-Q019／A conversation continuity。
- Stage：G5 isolated implementation，非 production。
- 本輪唯一問題：正式 compiled Agent 在工具接力、compaction、失敗續跑及重新開啟時，能否保留完整 native conversation？
- 最新設計在主 checkout：[Runtime](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-runtime-design.md)、[第一切片結果](S:/caliburn/docs/specs/2026-09-06-analysis-only-agent-native-continuity-results.md)、[決策入口](S:/caliburn/docs/current-decisions.md)。不要由 worktree 歷史 register 推論本輪 authority。

## 邊界

沿用 codex/analysis-only-agent，從 90fcc97 接續。無 JD、背景 Memory、live repair、Web UI、付費模型測試、production import 或資料搬移。不重設 Docker、不動既有資料庫；真 PostgreSQL 不可用時明列未驗證，不以 InMemorySaver 冒充耐久資料庫成功。

## 官方接法與本案選擇

1. LangChain create_agent 負責 model → tools → model；不自寫通用 Agent loop。
2. wrap_model_call + request.override(messages=...) 只改單次 model request；沿用第一切片 server_compaction_view，canonical messages 不刪改。instructions 獨立傳入 system_prompt。這不是 standalone /responses/compact 的裁切器。
3. LangGraph PostgresSaver 管 checkpoint；首次專用 DB 執行 setup。invoke 的 durability="sync" 用官方逐步保存語意。exception 後以同 thread、input=None 續跑，不能再附同一則員工訊息。
4. 以上是官方元件的公開組合點；「本案選 sync、canonical 不裁切」是依效果選擇，不冒稱所有廠商底層相同。框架 checkpoint 不保證外部副作用 exactly-once；本切片工具只有測試用 deterministic reader。
5. 同步介面先完成最小行為；串流、非同步 Web lifetime、同 thread lock、run budgets 後續切片再接，不宣稱這版已可給使用者上線。

來源（2026-09-06 複核）：

- [LC Context engineering](https://docs.langchain.com/oss/python/langchain/context-engineering)：transient request vs persistent state updates。
- [LC short-term memory](https://docs.langchain.com/oss/python/langchain/short-term-memory)：create_agent/checkpointer/PostgresSaver setup。
- [LG durability](https://reference.langchain.com/python/langgraph/types/Durability)：sync 在下一步前保存。
- [LG persistence](https://docs.langchain.com/oss/python/langgraph/persistence)：thread、state、pending writes/recovery；不等於外部系統 exactly-once。
- [OpenAI compaction](https://developers.openai.com/api/docs/guides/compaction)：inline compaction 與 standalone compact window 不同，沿用已完成 native continuity 證據。
- 實際安裝 source：langchain 1.4.0 agents/middleware/types.py 的 ModelRequest.override／wrap_model_call；langgraph 1.2.11 pregel/main.py invoke durability 文件。

## 單一 task／red-green 執行

1. 在 experiments/analysis-agent 新增 tests/test_agent_runtime.py。使用真 ChatOpenAI/SDK/create_agent，僅 HTTP 回應 synthetic：model-tool-model 的 reasoning/phase/tool pairing、compaction request 與 canonical 分離、失敗後續跑不重複輸入／已保存 reader、thread 隔離。先見到因 runtime 尚未實作而 RED。
2. 最小新增 src/analysis_agent/runtime.py：build_agent(model, checkpointer, instructions, tools)＋同步 request middleware；暴露官方 compiled graph，不再包一套 workflow/state。
3. 固定 langgraph-checkpoint-postgres 3.1.2 與可相容 psycopg binary 依賴，用 uv 更新 lock。新增 tests/test_postgres_conversation.py，明確 opt-in 專用 DB：
   - setup 官方 tables；
   - 兩個真正 Python process／獨立 saver 先寫後讀；
   - 在 HTTP 邊界從另一 DB 連線驗證員工 input 已保存；
   - reopening 後 opaque items/tool result 與原始對話仍在，compaction 只縮 request。
   - 不提供 DSN 時 skip 並清楚顯示；若指定而不可用則 FAIL，不吞失敗。
4. 新增有界 PostgreSQL 測試入口／README 說明。測試 thread 使用隨機 ID，只移除本次 thread；不用 drop DB 或清整庫。
5. 跑既有＋新增測試、差異審核、獨立 review。若 PG 無法完成，結果明寫 partial gate；若有新設計風險先回報，不繞過 gate。
6. 結果寫 docs/specs 的短結果稿、主 register；工作樹內只提交本切片檔案，留本地保存點，不 merge/push。

## 完成尺度

離線 wire/graph 行為與真 PostgreSQL durable proof 分開報告；兩者都不是模型實際分析品質證明。Memory 尚未完成。Docker 環境阻塞不得轉成重置既有資料的授權。
