# 測試指南

## 前置條件

```bash
cd backend
cp .env.example .env   # 填入 OPENAI_API_KEY、DATABASE_URL
pip install -r requirements.txt
uvicorn app.main:app --reload   # 需在背景執行
```

---

## 一、RAG 查詢測試

直接測試 `icap_retriever.py` 的向量搜尋品質，不需要跑完整訪談流程。

```bash
cd backend
python -m scripts.test_rag --query "資料庫備份還原" --type task
python -m scripts.test_rag --query "SQL 查詢語法" --type knowledge
python -m scripts.test_rag --query "主動積極" --type attitude
python -m scripts.test_rag --query "定期備份 還原測試" --type indicator --ocs-code DAT-001
```

**支援的 `--type`**：`task` / `output` / `indicator` / `knowledge` / `skill` / `attitude`

**輸出範例**：
```
query: 資料庫備份還原  chunk_type: task  top_k: 5

#1  similarity: 0.847  code: T2.1
    name: 資料庫備份與還原作業
    breadcrumb: 資料庫管理師 (DAT-001) > 系統維運 > T2.1

#2  similarity: 0.761  ...
```

> `scripts/test_rag.py` 尚未建立，可執行 `python -c "import asyncio; from app.services.icap_retriever import search_tasks; print(asyncio.run(search_tasks('資料庫備份還原', top_k=3)))"` 快速驗證。

---

## 二、端對端訪談測試

模擬完整訪談流程（需 backend 在 `http://localhost:8000` 執行）：

```bash
cd backend
python -m scripts.test_full_interview
```

**測試職稱**：`倉庫管理員`（`物流部`）

**流程覆蓋**：
```
basic_info → icap_rag → interview（3 輪）
→ task_extraction（確認） → responsibility_grouping（確認） → star（STAR 四槽）
→ five_w2h（9 欄補洞） → indicator → ocs_builder → preview
```

**驗證項目**：
- `ocs_document` 正確寫入 DB
- OCS JSON 結構符合 schema（含 `ocu_units` / `knowledge` / `skills` / `attitudes`）
- `icap_mode` 正確設定（`reference` / `hybrid` / `company_defined`）

---

## 三、OCS 匯出測試

測試所有匯出格式（需先有一筆含 `ocs_document` 的 `job_profile`）：

```bash
cd backend
python -m scripts.test_ocs_export
```

**覆蓋格式**：JSON / DOCX / PDF / XLSX

---

## 四、API 端點測試

測試 OCS preview / freeze / export REST API：

```bash
cd backend
python -m scripts.test_ocs_api
```

**流程**：
1. 建立測試用 `job_profile`（直接寫入 DB）
2. 呼叫 `GET /api/v1/documents/{id}/preview`
3. 呼叫 `POST /api/v1/documents/{id}/freeze`
4. 呼叫 `POST /api/v1/documents/{id}/export?format=docx` 等四種格式

---

## 五、手動冒煙測試（前端）

```bash
# Terminal 1
cd backend && uvicorn app.main:app --reload

# Terminal 2
cd frontend && npm run dev
```

開啟 `http://localhost:3000`，執行以下流程：

1. **新增職務** — 填寫職稱、部門、工作摘要
2. **訪談** — 描述工作內容，直到出現「整理任務清單」提示
3. **確認任務清單** — 說「確認」後進入主要職責分組
4. **確認主要職責分組** — 檢查 `主要職責 → 工作任務` 是否合理；正確則說「確認」，需要調整則直接描述移動方式
5. **STAR + 5W2H** — 依提示回答每個任務；若出現 iCAP 參考提示，應和正式問題分成兩個 AI 泡泡
6. **行為指標生成** — 確認指標品質評分 ≥ 0.60
7. **預覽頁** — 確認 OCS 文件結構正確，匯出 DOCX / PDF

---

## 六、Swagger UI

backend 啟動後可在 `http://localhost:8000/docs` 直接測試所有 API 端點，支援：

- `POST /api/v1/users` — 建立使用者
- `POST /api/v1/job-profiles` — 建立職務
- `POST /api/v1/interviews/{id}/chat` — 送出訊息（SSE，需用 curl 測試）
- `GET /api/v1/documents/{id}/preview` — 預覽 OCS
- `POST /api/v1/documents/{id}/export` — 匯出

**curl 測試 SSE**：
```bash
curl -N -X POST http://localhost:8000/api/v1/interviews/{profile_id}/chat \
  -H "Content-Type: application/json" \
  -d '{"content": "我負責每天的進出貨管理", "phase": "general"}'
```
