# JobIntel AI — 開發文件索引

> 企業崗位知識萃取與職務說明書生成 AI

## 文件清單

| 文件 | 說明 |
|------|------|
| [architecture.md](./architecture.md) | 系統架構總覽、技術棧、資料流、環境變數、Docker Compose |
| [api.md](./api.md) | REST API 端點參考（SSE / 輪詢 / 匯出） |
| [graph-pipeline.md](./graph-pipeline.md) | LangGraph 訪談狀態機（8 節點流程、逐任務迴圈） |
| [ocs-schema.md](./ocs-schema.md) | OCS 職能文件 JSON 結構、Pydantic schema、代碼規則 |
| [icap-pipeline.md](./icap-pipeline.md) | iCAP Parser + pgvector 向量嵌入 + iCAP 參考提示與 K/S/A 對應 |
| [rag-pipeline.md](./rag-pipeline.md) | RAG 完整流程：從 iCAP 候選信心到 5W2H 參考提示與 K/S/A 代碼對照 |
| [db-schema.md](./db-schema.md) | 完整資料庫 Schema（7 張表 + icap_embeddings + graph_state 欄位說明） |
| [frontend.md](./frontend.md) | 前端頁面行為、元件說明、API 呼叫、狀態管理 |
| [testing.md](./testing.md) | 測試指南（RAG 查詢 / 端對端訪談 / 匯出 / API / 手動冒煙） |
| [export.md](./export.md) | 匯出格式（JSON / DOCX / PDF / Excel）與 display_label |
| [roadmap.md](./roadmap.md) | 第一〜四階段完成狀態、Bug 修復紀錄、第五〜七階段計畫 |

## 系統現況（2026-05-27）

- **第一〜四階段全部完成**：工作者完整 Demo Flow 可端到端跑通
- **8 個關鍵 Bug 已修復**（含 STAR 無限迴圈 B6、task_id 流程鍵 B5、AI phase 持久化 B6）
- **主要職責分組已接入**：任務確認後會先整理 `主要職責 → 工作任務` 骨架，經使用者確認後才進 STAR/5W2H
- **SSE 多泡泡已接入**：節點可輸出 `ai_messages`，例如 5W2H 的 iCAP 參考提示與正式問題會分開顯示
- **iCAP 多粒度參考已接入**：覆蓋 competency / task / indicator / output / K / S / A；iCAP 是信心與參考，不是硬性套版
- **per-output 行為指標**：每個 output 對應獨立指標，可追溯 P/O 代碼
- **Schema 已穩定**：EvidenceRef 強型別、EnrichedExportJson、quality_score 全部 Pydantic 化

## 快速啟動

```bash
# Backend
cd backend
cp .env.example .env   # 填入 OPENAI_API_KEY、DATABASE_URL
pip install -r requirements.txt
uvicorn app.main:app --reload

# Frontend
cd frontend
npm install
npm run dev
```

Backend: `http://localhost:8000`
Frontend: `http://localhost:3000`
API Docs (Swagger): `http://localhost:8000/docs`

## 待決議

- **輸入驗證防護**：偏題/亂答防護三選項尚未實作（見 roadmap.md 第四階段）
- **Login / JWT**：目前 `user_id` 以 query param 傳入，已移入第七階段（暫緩）
- **iCAP unit / notes chunk**：P2 backlog，訪談節點注入任務參考與學歷要求
- **iCAP reranker / judge**：目前尚未實作；暫不使用職稱關鍵字硬性降權，後續應以任務證據與候選職種語意一致性提升匹配品質
