# ADR 0007 — LangGraph 留用 + 12-factor + MCP-ready

- **狀態**:Accepted（2026-06-27）

## 脈絡

agent 框架要不要換(Google ADK / Microsoft Agent Framework)?indexer 對外介面要不要用 MCP?

## 決定

- **留用 LangGraph 1.0**,不換框架(ADK/MS Agent Framework 沒有遷移價值,且大家靠 MCP/A2A 互通;換框架=大churn 無回報)。
- 套 **12-Factor Agents**:自掌控制流(#8)、無狀態 reducer(#12)、小而專注 agent(#10)、prompt 版本化(#2)。`apps/api/agent/` 為 agent 子系統。
- **indexer↔api 縫:MCP-ready,但現在不做 MCP**。單一內部 agent ↔ 單一內部服務,型別化 HTTP client 更簡單;**第二個消費者出現(別的 agent / Claude Desktop / 外部 agent)才把 indexer 包成 MCP server**(MCP 是包在既有 API 外的協定層,屆時是加法)。
- 可觀測:對齊 OTel GenAI 語意慣例 + Langfuse(接既有 OTel)。

## 後果

- ✅ 無框架churn;標準相容(MCP/A2A)。
- ✅ MCP 的稅(discovery/consent/OAuth 層)等到有第二消費者才付。
- 📌 deep-interview 刻意單層 loop(非 subgraph,langgraph#6792),別重構。

依據:LangGraph 1.0、12-Factor Agents(HumanLayer)、Anthropic MCP(Linux Foundation）。
