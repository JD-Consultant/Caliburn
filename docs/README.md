# JobIntel AI — 開發文件索引

> 企業崗位知識萃取與職務說明書生成 AI

## 文件清單

| 文件 | 說明 |
|------|------|
| [architecture.md](./architecture.md) | 系統架構總覽、技術棧、資料流、環境變數 |
| [api.md](./api.md) | REST API 端點參考（SSE / 輪詢 / 匯出） |
| [graph-pipeline.md](./graph-pipeline.md) | LangGraph 訪談狀態機（8 節點流程、逐任務迴圈） |
| [ocs-schema.md](./ocs-schema.md) | OCS 職能文件 JSON 結構、Pydantic schema、代碼規則 |
| [icap-pipeline.md](./icap-pipeline.md) | iCAP Parser + pgvector 向量嵌入 + 6 個 RAG 檢索點 |
| [export.md](./export.md) | 匯出格式（JSON / DOCX / PDF / Excel）與 display_label |
| [roadmap.md](./roadmap.md) | 第一〜四階段完成狀態、Bug 修復紀錄、第五〜七階段計畫 |

## 系統現況（2026-05-20）

- **第一〜四階段全部完成**：工作者完整 Demo Flow 可端到端跑通
- **8 個關鍵 Bug 已修復**（含 STAR 無限迴圈 B6、task_id 流程鍵 B5、AI phase 持久化 B6）
- **iCAP 多粒度 RAG 已接入**：6 個檢索點覆蓋 competency / task / indicator / output / K / S / A
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
