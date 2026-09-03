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

**目前執行狀態（2026-09-03）：** revision 2 已執行並以 infrastructure failure 停止。
OpenRouter metadata preflight 完成後，Windows CLI 使用預設 `ProactorEventLoop`，在第一個
Psycopg async connection 被拒絕；因此沒有 embedding、Luna、tool call 或模型語意輸出。
正常 receipt 尚未建立便退出，trial JSON 是依保存的 command result 重建之 attempt record。
結果為 `FAIL_UNPROVEN`；詳見 [`report.md`](report.md)。該結果當時不授權第三次執行或接 production；
後續另行授權見下一段。

**Post-report 狀態：** Product Owner 後續只核准的 Windows CLI event-loop bounded repair 已以真 CLI
Psycopg regression 完成 RED→GREEN，沒有在該 repair 中呼叫 Luna／embedding；原 revision 2 artifact
與 `FAIL_UNPROVEN` verdict 不變。Product Owner 已於 2026-09-04 另行核准一次 frozen live trial
revision 3；只可執行一次，保存後停止，不授權 revision 4 或 production。

**External-transfer gate：** 付款前 preflight 已通過，但執行環境要求 Product Owner 另行明確允許
將匿名 synthetic frozen fixture、prompt 與 tool results 傳送至 OpenRouter。第一次啟動請求在
process 建立前被拒絕，所以沒有 provider request、費用或 revision 3 artifact；取得該明確授權前
不得重送。Product Owner 隨後已明確同意本次匿名 synthetic payload 的 OpenRouter 外部傳輸；
現在只可執行一次 frozen revision 3，遇到新問題則保存並停止。

本實驗把兩種容易混淆的 `harness` 分開命名：外層 `live_smoke.py` 是**隔離 smoke
實驗執行器**，負責 preflight、限制、執行與 receipt；內層 LangGraph model／tool graph 是
**agent runtime**。本次 SDK wrapper 錯誤發生在前者。單一 smoke 只驗證代表性 read path
能否實際跑通，不是用來泛化模型品質的完整 eval suite。

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

## 實際結果

- [Revision 2 attempt record](trials/revision-2-luna-medium.json)
- [逐 trial 摘要](results.csv)
- [結案報告](report.md)

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
input-token 計數。因此 18,000 input tokens 與 USD 0.20 在目前隔離 smoke 實驗執行器是：

1. call／output／embedding 數量的付款前 deterministic 上限；
2. endpoint metadata 的保守 preflight 估算；
3. 每次回應後立刻記錄官方 usage，超界便不進下一 call。

它們不是第一個 request 扣款前可數學證明的 account-level hard cap。這個限制
必須在執行 live 前由 Product Owner 接受，否則 Task 5 記錄
`preflight_blocked` 而不發 paid call。依據：
[Usage Accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting)、
[Models pricing schema](https://openrouter.ai/docs/guides/overview/models)、
[Provider max price](https://openrouter.ai/docs/guides/routing/provider-selection#max-price)。
