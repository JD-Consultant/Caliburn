# Memory Routing 與 Canonical Read 隔離實驗

source_baseline_commit: 8979494dfe73634708e35a6c4b369e6af0fd8719

## 狀態與目的

這是 `MEM-Q004` 核准的 G5 隔離 spike，不是 production 實作。它只驗證下列 read path：

1. LangGraph PostgreSQL Checkpointer 保存完整 synthetic canonical conversation；
2. LangGraph PostgreSQL Store 保存少量 current Semantic Memory；
3. 模型先搜尋相關 Memory，只有需要精確原句時才回讀 canonical conversation；
4. 所有模型可見工具維持最小 strict schema，scope 與 policy 由 Runtime 注入。

不驗證 Memory writer、JD 產生／編輯、RAG、UI、跨 JD Memory 或 production migration。

## 設計來源與分類

- 大廠／框架共同方向、Caliburn mapping 與實驗變數的逐層分類：[`final audit`](../../specs/2026-09-03-memory-read-spike-consensus-and-framework-final-audit.md)
- 已核准 read contract：[`MEM-Q004 research`](../../specs/2026-09-03-memory-routing-canonical-read-and-isolated-spike-research.md)
- 實作與停止條件：[`Revision 2 plan`](../../plans/2026-09-03-memory-routing-canonical-read-isolated-spike.md)
- 當前決策：[`current-decisions.md`](../../current-decisions.md)

凡不屬框架原生能力的常數或政策，只能是凍結的實驗變數，不得冒充 vendor 標準或 production 決策。

## 凍結環境

- Python：3.13.12
- uv：0.10.8
- Pydantic：2.13.4
- LangChain：1.3.15
- LangGraph：1.2.11
- LangGraph PostgreSQL Checkpointer／Store：3.1.2
- langchain-openrouter：0.2.7
- OpenRouter Python SDK：0.10.8
- LangMem characterization：0.0.30，僅以 `uv --with` 暫時載入
- PostgreSQL server：16.15（隔離容器 `pgvector/pgvector:0.8.6-pg16`）
- pgvector：0.8.6；只供本 spike 的 LangGraph Store semantic index

## 執行規則

- 只使用匿名 synthetic fixture。
- deterministic tests 不需要 API key。
- PostgreSQL tests 必須使用名稱含 `memory_routing_spike` 的 loopback disposable database。
- live smoke 只能使用 `openai/gpt-5.6-luna`、`medium`，且受 plan 的 call／token／cost 上限約束。
- live fixture、rubric 與 prompt 一旦凍結，不得為了讓失敗變成功而原地修改。
