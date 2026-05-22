# 前端文件

## 技術棧

| 項目 | 版本 |
|---|---|
| Next.js | 16（App Router） |
| TypeScript | — |
| Tailwind CSS + shadcn/ui | — |
| TanStack Query (React Query) | SWR-style 資料請求 |
| Zustand | 使用者狀態管理（`useUserStore`） |

---

## 頁面結構

```
/                        → 重定向到 /dashboard
/dashboard               → 職務列表
/profiles/new            → 新增職務表單
/profiles/[id]           → 訪談頁
/profiles/[id]/preview   → 預覽 + 凍結 + 匯出
```

---

## 頁面行為說明

### `/dashboard` — 職務列表

- 顯示該使用者所有 `job_profiles`，依 `stage` 分組顯示狀態
- 點擊「新增職務」→ `/profiles/new`
- 點擊任一職務 → `/profiles/[id]`（訪談中）或 `/profiles/[id]/preview`（已完成）

---

### `/profiles/new` — 新增職務

- 表單欄位：`job_title`（必填）、`department`、`job_summary`
- 提交後呼叫 `POST /api/v1/job-profiles`，成功後跳轉 `/profiles/[id]`

---

### `/profiles/[id]` — 訪談頁

**版面結構**：左右分割（`h-screen`）

```
┌─────────────────────┬────────────────────────────────────────┐
│  AI 聊天室  (36%)   │  iCAP 職能基準 Live Preview  (64%)    │
│                     │                                        │
│  訊息泡泡 + 輸入框  │  職能基準表格，隨訪談即時填入         │
└─────────────────────┴────────────────────────────────────────┘
```

**自動觸發**：頁面載入時若 `messages.length === 0 && profile.stage === "basic_info"`，自動以 `sendSilent("開始訪談")` 觸發第一次 iCAP RAG，不在聊天室顯示使用者訊息。

**SSE 串流**：`useInterview` hook 呼叫 `POST /api/v1/interviews/{id}/chat`，以 `text/event-stream` 接收 AI 回應，逐 chunk 更新 `streamBuffer`，串流結束後 flush 進 `messages`。

**phase 傳遞**：
```
stage = "star"      → phase = "star_{task_id}"
stage = "five_w2h"  → phase = "five_w2h_{task_id}"
其他               → phase = "general"
```

**主要元件**：

| 元件 | 說明 |
|---|---|
| `ChatBubble` | AI / 使用者訊息泡泡，支援 Markdown 渲染 |
| `IcapBadges` | 顯示 iCAP 候選職種命中結果（`icap_candidates`） |
| `ProgressTracker` | 顯示整體流程進度（stage） |
| `LiveDocPanel` | 右側 iCAP 職能基準表格（64% 寬）；以官方格式呈現：主要職責 / 工作任務 / 工作產出 / 行為指標 / 職能級別 / K知識 / S技能；未填欄位顯示 skeleton 動畫，隨訪談即時更新；OCS 文件完成後切換至完整資料 |

**`LiveDocPanel` 表格欄位對照**：

| 欄位 | 資料來源 | 狀態 |
|---|---|---|
| 職能基準代碼 / 名稱 | `profile.job_title` + `icap_candidates[0].ocs_code` | 訪談開始即顯示 |
| 主要職責（T1/T2…） | `extracted_tasks`（每 2 任務合為一職責） | 任務萃取後出現 |
| 工作任務（T1.1…） | `extracted_tasks[].task_name` | 任務萃取後出現 |
| 工作產出（O…） | `extracted_tasks[].outputs` | 5W2H 訪談後填入 |
| 行為指標（P…） | `behavior_indicators[].indicator_5w2h` | 指標生成後填入 |
| K 知識 / S 技能 | `ksa_items`（KSA 對齊後）或 `ocs_document` | OCS 建立後填入 |
| A 態度 | `ksa_items`（type=A）或 `ocs_document` | OCS 建立後填入 |

**hooks**：

| hook | 說明 |
|---|---|
| `useInterview(profileId)` | SSE 串流、訊息歷史、`send` / `sendSilent` |
| `useProfile(profileId)` | 取得 profile 狀態（stage、graph_state），串流結束後自動 invalidate |

---

### `/profiles/[id]/preview` — 預覽頁

**資料來源**：`useProfile` 取得 `profile.graph_state.ocs_document`

**凍結（Freeze）**：
- 呼叫 `POST /api/v1/documents/{id}/freeze`
- 凍結後 `profile.stage = "preview"`，按鈕變為禁用
- 凍結建立 `document_versions` 記錄（`status: "frozen"`）

**匯出**：支援四種格式，各自呼叫 `POST /api/v1/documents/{id}/export?format=<fmt>`：

| 格式 | 說明 |
|---|---|
| `docx` | Word 文件，含完整 OCS 結構 |
| `pdf` | PDF，中文字型依平台自動偵測 |
| `xlsx` | Excel，K/S/A 對照表格 |
| `json` | `EnrichedExportJson`（含 `evidence_refs` / `icap_reference_pack`） |

**主要元件**：

| 元件 | 說明 |
|---|---|
| `SourceBadge` | `[訪談確認]` / `[AI整理]` / `[iCAP參考]` / `[待確認]` 來源標籤 |
| `BehaviorIndicatorCard` | 顯示 5W2H / ABCD 雙版指標，含 `quality_score` |
| `EvidenceRefs` | 顯示任務/指標對應的原始訪談引用 |
| `QualityBadge` | 品質評分視覺化（ok / force_accepted） |
| `KsaSection` | K/S/A 分類顯示，標示 iCAP / 企業來源 |

---

## API 呼叫（`src/lib/api.ts`）

| 函式 | 端點 | 說明 |
|---|---|---|
| `listProfiles(userId)` | `GET /api/v1/job-profiles?user_id={userId}` | 職務列表 |
| `getProfile(id)` | `GET /api/v1/job-profiles/{id}` | 單一職務 |
| `createProfile(userId, data)` | `POST /api/v1/job-profiles` | 建立職務 |
| `deleteProfile(id)` | `DELETE /api/v1/job-profiles/{id}` | 刪除職務 |
| `getHistory(profileId)` | `GET /api/v1/interviews/{id}/history` | 對話歷史 |
| `streamChat(profileId, content, phase)` | `POST /api/v1/interviews/{id}/chat` (SSE) | 送出訊息 |
| `freezeDocument(id)` | `POST /api/v1/documents/{id}/freeze` | 凍結文件 |
| `exportDocument(id, format)` | `POST /api/v1/documents/{id}/export` | 匯出文件 |

---

## 狀態管理

**Zustand `useUserStore`**：
- 持久化 `userId`（localStorage）
- `ensureUser()` — 若無 userId，自動呼叫 `POST /api/v1/users` 建立匿名使用者

**TanStack Query cache key 規則**：

| queryKey | 說明 |
|---|---|
| `["profiles", userId]` | 職務列表 |
| `["profile", profileId]` | 單一職務（訪談結束後 invalidate） |
| `["history", profileId]` | 對話歷史（SSE flush 後 optimistic update） |
