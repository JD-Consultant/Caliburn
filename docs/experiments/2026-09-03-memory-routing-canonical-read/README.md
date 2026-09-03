# Memory Routing 與 Canonical Read 隔離實驗

source_baseline_commit: 8979494dfe73634708e35a6c4b369e6af0fd8719

case_sha256: a39f668dbcb23f4b7c8b8396cb8593f115dda8da41d092efb4b24be63bf9b835
rubric_sha256: 7555260a65dd5882be1ab680c6ac1ecf3ebb45fb385048f0515d5d72682a0158
prompt_sha256: 91558055927742669fe1be8df33100a63a216490d95c2dac44e24c808d62c701

`case_sha256` 與 `rubric_sha256` 是檔案原始 bytes 的 SHA-256；`prompt_sha256`
是 UTF-8 編碼的 `System:\n{system}\n\nUser:\n{user}\n`。測試會在任何 live
call 前重新計算並比對，避免案例、判準或 prompt 被靜默修改。

## 狀態與目的

這是 `MEM-Q004` 核准的 G5 隔離 spike，不是 production 實作。它只驗證下列 read path：

1. LangGraph PostgreSQL Checkpointer 保存完整 synthetic canonical conversation；
2. LangGraph PostgreSQL Store 保存少量 current Semantic Memory；
3. 模型先搜尋相關 Memory，只有需要精確原句時才回讀 canonical conversation；
4. 所有模型可見工具維持最小 strict schema，scope 與 policy 由 Runtime 注入。

不驗證 Memory writer、JD 產生／編輯、RAG、UI、跨 JD Memory 或 production migration。

**目前執行狀態（2026-09-03）：** 唯一獲准的 revision-1 attempt 在免費 endpoint metadata
preflight 因 SDK operation-wrapper 接線錯誤停止；沒有 embedding／Luna call，也沒有模型語意輸出。
bounded 修復已以 pinned SDK typed response 完成 RED→GREEN，完整 deterministic suite 為
59 passed／1 optional skip；另以臨時 LangMem 0.0.30 執行該 optional characterization 為
1 passed。修復沒有附帶 live rerun 授權。

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

## Task 4 的實驗邊界

- disposable Store 的向量欄位與所有 embedding adapter 一律是 1536 維；這是
  pgvector schema 層級的一致性要求，不是 production embedding 選型。
- semantic search 最多回傳 2 筆；embedding 最多 8 個 request、每 batch 最多
  2 段文字。這三個數字都是本案例的安全邊界，不是 production 決策。
- receipt 的 `model_visible_turns` 是去除 provider-private reasoning 後的稽核投影。
  pinned framework 在同一 tool loop 內會暫時回傳原 reasoning blocks 以延續請求，
  但 receipt 與 Git artifact 都不保存它們。OpenRouter 官方亦要求 tool call 續跑時
  保留原 reasoning sequence：[Reasoning Tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)。
- receipt 狀態 `completed` 只表示 graph 正常跑完；是否通過案例仍由 rubric 的
  `overall verdict` 判定。

## Token／成本限制的已知邊界

OpenRouter 會在**回應後**以模型原生 tokenizer 回傳精確 token 數與實際 cost；
官方文件沒有為目前 Chat Completions／OpenRouter SDK 公開等價的付款前精確
input-token 計數。因此 18,000 input tokens 與 USD 0.20 在目前 harness 是：

1. call／output／embedding 數量的付款前 deterministic 上限；
2. endpoint metadata 的保守 preflight 估算；
3. 每次回應後立刻記錄官方 usage，超界便不進下一 call。

它們不是第一個 request 扣款前可數學證明的 account-level hard cap。這個限制
必須在執行 live 前由 Product Owner 接受，否則 Task 5 記錄
`preflight_blocked` 而不發 paid call。依據：
[Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)、
[Models pricing schema](https://openrouter.ai/docs/guides/overview/models)、
[Provider max price](https://openrouter.ai/docs/guides/routing/provider-selection#max-price)。
