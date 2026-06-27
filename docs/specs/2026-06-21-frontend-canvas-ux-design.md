# jobintel-ai v3 — 文件即工作台 UX 重設計（Design Spec）

> 日期：2026-06-21（D27，多輪討論後定稿）。分支 `feat/v3`。狀態：**已定案，待轉 plan**。
> 緣由：原 v3 前端是線性 wizard 煙霧殼。使用者提出「**文件（職務說明書）才是主角，流程只是把空格填起來的工具**」，要能隨時看、隨時改、走完也能回來改。改採 2026 主流 **document-as-interface（文件即介面）**。
> 權威依據（2026）：ShapeofAI《Auto-fill》（按需逐格填、先示範再套用）、Agent UX 2026 / builder.io（一個高價值 artifact + 漸進信任）、Google Cloud agentic patterns（結構化骨架 + 局部 bounded agent 最可靠）、CopilotKit CoAgents / Generative UI。**文件 schema 權威：`S:\jd-pdf-to-json` README（OCS JSON 契約）**。
> 決策：**D27**（decision log）。

---

## §0. 名詞：catalog 是什麼

**catalog（型錄）= `jd-ocs-indexer`（repo `S:\jd-ocs-indexer`）這個知識服務**：一份預先建好、可搜尋的 **OCS 職能基準資料庫**（官方 iCAP 標準，BGE-M3 embedding 存 Qdrant；`search()`/`pairs()`/`tasks_by_id` 查）。叫 catalog 是因為它是「**你從裡面挑東西的現成目錄**」，相對於「從零生成」。v3 核心轉向＝**從「LLM 對話推論」→「catalog 取出 + 人 curate」**。catalog 本身是**檢索、不是 LLM**。

**OCS schema 契約**由 `S:\jd-pdf-to-json` 定義（PDF→JSON 的規範）、indexer 供應、**我們產出**——三方同一份契約。我們產的職務說明書 = **一份符合此契約的 OCS JSON**。

## §A. 已定決策（D27）

| # | 決策 | 選擇 |
|---|---|---|
| 1 | 核心互動模型 | **Model 2 — 文件即工作台**：先 seed 骨架，之後攤開表格、自由點空格填 |
| 2 | 編輯/續做 | **同一張表，點格就改**；無獨立編輯模式；建立=編輯=續做同一畫面 |
| 3 | 填格順序 | **自由順序**（seed 後不強制逐任務走完） |
| 4 | 填格手段（MVP） | **β REST-first**：K/S/A/O/P 全走 `GET 候選池 + 表單 + PATCH document`；**MVP 不碰 LangGraph/AG-UI** |
| 5 | 手打優先原則 | 每格基準＝**使用者自己打**；catalog 候選 / LLM 是疊加的加速器（有就用、沒有照樣填） |
| 6 | LLM（核心、延後） | 不是每格小 graph，而是**全域 CoAgent over document shared state**（CopilotKit/AG-UI 在此回歸）；現在不做 |
| 7 | 文件 of-record | **採用 `jd-pdf-to-json` 的 OCS JSON 契約**（5 區塊）；連續儲存的 draft；finalize 產合法 OCS JSON |
| 8 | 任務顆粒度 | **每任務一個 competency_block**（schema 仍支援多 block，不鎖死） |
| 9 | competency_level | **block 的可空屬性**（每任務一個 level；K/S 才是 block 真正分界）；MVP 多半 `null`，catalog/LLM 帶才有；**不做輸入控制** |
| 10 | K/S 不重複 | K/S **每任務寫一次**（不 denormalize 到每個 P）；底下列多個 O 與多個 P |
| 11 | unit（主要職責） | **保留**為分區（`ocu_units`，對齊契約） |
| 12 | 樣式深度 | 先「乾淨可用的設計系統」（Tailwind + `components/ui/*`） |

**心智模型**：要完成的是**一張職務說明書（OCS 文件）**。所有流程都是「填某格的工具」：選職務→填職稱/代碼/任務；手打/深問→填任務的 O/P；選單→填 K/S + 全域 A。

---

## §B. 落地設計

### B1. 畫面（單一工作台，建立/編輯/續做共用）

```
┌ 職務說明書：AIoT應用工程師   [自動儲存✓ 13:42]   [產生正式版本 v2] ┐
├──────────┬──────────────────────────────────────────────────────┤
│ 進度/狀態 │  職務說明書（可互動表格 = 主操作面，照 OCS 版型）        │
│ rail     │  表頭：code/名稱/category/工作描述/基準級別             │
│ 完成度    │  ── 單元 T1 AIoT標準與應用趨勢研究 ───────────────     │
│ 7/12 格   │   任務 T1.1 蒐集國際標準           級別[3]             │
│          │     O 產出[✅]  P 指標[✅]  K[✅]  S[⬜ 點此填]         │
│          │   任務 T1.2 …                      級別[ ]             │
│          │     O[⬜] P[⬜] K[⬜] S[⬜]                            │
│          │  ── 全域態度 A ── ⬜ 點此填                            │
│          │  ── 說明 notes（學經歷建議…）                          │
└──────────┴──────────────────────────────────────────────────────┘
        點空格 → 開該格 filler 面板（完成寫回該格 + PATCH）
```

- 兩欄：左=進度/完成度 rail（窄）、右=**可互動 OCS 表格**（主），照 PDF 版型：unit 分區 → task（級別欄）→ O/P/K/S。
- 點空格 → filler 面板（內嵌或側拉，plan 定）。點已填格 → 就地改/重填。
- **使用者永遠看不到「block」字眼**；只看到「任務 + 它的 O/P/K/S/級別」。
- 窄螢幕：表格優先、進度收頂部。樣式 Tailwind + `components/ui/*`。

### B2. 兩階段流程 + 各格 filler（皆非 LLM、皆 REST）

**① seed（不可避免、輕）**：`search` 選 OCS（複選=優先度）→ task pool curate → 撈候選池。產出**骨架 OCS 文件**（profile/units/tasks 皆有，O/P/K/S 空，A 空）寫成 draft。

**② 自由填**：任意順序點空格——

| 點的格 | filler（MVP） | 候選來源 | 加速器（延後） |
|---|---|---|---|
| O 產出 / P 指標 | **手打兩清單**（產出 + 績效/行為指標，加/改/刪） | （`tasks_by_id` 修好可加候選；現 502） | LLM 深問預填 |
| K / S | 選單（勾/加/改），**每任務一次** | catalog `pairs()` 職類池 | — |
| A 全域 | 選單 | catalog `pairs().attitudes` | — |
| 級別 | 不做控制（顯示用） | catalog/LLM 帶 | — |

每格完成 → 寫回 draft 該格 + PATCH 持久化。

### B3. 後端（β REST-first；LangGraph 留給未來 CoAgent）

- **MVP 完全不跑 LangGraph/AG-UI**。curate 本質是 CRUD：
  - `GET /job-profiles/{id}/ksa-pool`（catalog 候選池，快取）
  - `GET/PATCH /job-profiles/{id}/document`（讀/改 draft OCS JSON）
  - `POST /job-profiles/{id}/document/finalize`（snapshot final、驗 schema）
  - seed 的 `search`/`task_pool` 也走 REST（indexer 呼叫）。
- 既有 interrupt 審閱面 **UI 元件重用**（`CurateKsPanel` 等），只把「resolve→interrupt」換成「POST/PATCH」。
- **未來 LLM = 全域 CoAgent**：CopilotKit/AG-UI + LangGraph 掛在**同一份 document shared state**，讀整份文件+對話、提議填任一格、人核准（HITL）。這才是 CopilotKit 1.61 的正用途。現有 `deep_nodes`（逐任務 STAR）大概率被此 CoAgent 重塑，先保留不動。

### B4. Persistence（精修 D25：draft 連續寫）

- seed 後建 `document_versions(status='draft')`；每格 filler 完成 → **PATCH 更新 JSONB**。「自動儲存」「續做」皆靠它。
- checkpointer 角色縮小（MVP 幾乎不用；未來 CoAgent 才用）。
- finalize → 由 draft 組裝/驗證 → 寫 `status='final'` 版本（版號遞增）。
- `version_info` 用**我們自己的版本管理**（對應 `document_versions`），不照搬 OCS 標準版本史。

### B5. 文件 JSONB = OCS 契約（draft 與 final 同形；每任務一 block）

採 `jd-pdf-to-json` 五區塊契約；**代碼與名稱並存**（catalog 帶的保留 code，自訂的可無 code）：

```jsonc
{
  "version_info": { "versions": [ /* 我們自己的版本記錄 */ ] },
  "ocs_profile": {
    "ocs_code": "...", "ocs_name": {"job_category_name": null, "occupation_name": "AIoT應用工程師"},
    "category": {"job_categories": [{"name","code"}], "occupations": [...], "industries": [...]},
    "job_description": "...", "ocs_level": 4
  },
  "ocs_content": { "ocu_units": [
    { "ocu_code": "T1", "ocu_name": "AIoT標準與應用趨勢研究", "tasks": [
      { "task_codes": [{"code": "T1.1", "name": "蒐集國際標準"}],   // 陣列；通常長度 1
        "competency_blocks": [                                       // ★ 每任務一個
          { "competency_level": 3,                                  // int|null（K/S 才是真正分界）
            "indicators": [{"code": "P1.1.1", "text": "..."}],      // P
            "outputs":    [{"code": "O1.1.1", "name": "..."}],      // O（可空 []）
            "knowledge":  [{"code": "K01", "name": "..."}],         // K（寫一次）
            "skills":     [{"code": "S01", "name": "..."}] } ] }    // S（寫一次）
    ]}
  ]},
  "ocs_attitude": { "attitudes": [{"code": "A01", "name": "多元思考"}] },  // 全域
  "notes": { "prerequisites": ["..."], "supplements": ["..."] }
}
```

- **每任務恰一個 competency_block**：避免 denormalize（K/S 不重複抄）；匯出即合法 OCS。schema 支援多 block，未來「同任務多級別」無痛展開。
- finalize 可直接套 `jd-pdf-to-json` 的 `validate`。
- 表格的 ✅/⬜ 與完成度由「各任務 O/P/K/S 是否非空 + 全域 A」推算。

### B6. 儲存 / 續做（resume 大幅簡化）

- 儲存：每格 PATCH → 頂部「✓ 已自動儲存」。
- 續做：重開 → `GET document` 載入 draft → 同一張表續點。**工作態落在 draft JSONB，不依賴 rehydrate LangGraph thread** → **CopilotKit v2 headless threadId SPIKE 在 MVP 直接消失**（MVP 無 graph thread）。

### B7. 進度 / 狀態 rail

完成度 = 已填格 / 總格（每任務 O·P·K·S 四格 + 全域 A + 表頭）。seed 步驟作導引；自由順序下以「完成度 + 哪些格空」為主。

### B8. Dashboard 狀態

由 draft/final 判定：**無文件=未開始、draft=進行中(完成度%)、final=完成**。`job_profiles` list 端點補 `doc_status`/`completion`（由 latest document_versions 算）。

### B9. 錯誤 / 復原

filler 失敗 → 友善 banner +「重試」（重送 PATCH/重開該格）。draft 已存，失敗不丟既有進度。不再露 raw console error。

### B10. 範圍

- **IN**：工作台版面 + 可互動 OCS 表格（unit/task/O/P/K/S/級別）+ 各格 REST filler（O/P 手打、K/S/A 候選選單）+ draft 連續儲存 + 同表編輯 + 續做 + finalize(驗 schema) + dashboard 狀態 + 錯誤 banner。
- **OUT（延後）**：LLM 全域 CoAgent（核心、之後）、匯出 docx/pdf、拖拉排序、同任務多級別 block、indexer 修正（`tasks_by_id` 502 → O/P/K/S 升級 per-task）、進行中 interrupt 跨 session 精準續答。

---

## §C. 待 plan / 待驗證

1. PATCH 粒度：整份 merge vs 細到 `/tasks/{key}/ks`——plan 定。
2. filler 面板呈現：內嵌中央 vs 側拉/modal——plan 定。
3. seed 是否仍用既有 LangGraph（pick_profile/task_pool）跑一次再轉純 REST，還是 seed 也改 REST——plan 定（傾向 seed 也走 REST，與 β 一致、MVP 全無 graph）。
4. `pairs()` 候選 → 我們的 K/S item（含 code）對應；A 同理。
5. 與既有 `_assemble`/`build_doc` 邏輯多少可重用於 finalize 組裝。

## 實作分塊（給後續 plan）

1. 後端：`ksa-pool` / `document` GET·PATCH / `finalize` 端點 + draft 持久化（OCS 契約）。
2. 後端：seed（search/task_pool）產骨架 OCS 文件（REST）。
3. 前端：工作台 shell（兩欄 + 響應式）+ `JobDocTable`（render OCS 契約：unit/task/O/P/K/S/級別、✅/⬜、點格事件）。
4. 前端：各格 filler 面板（O/P 手打兩清單；K/S/A 候選選單；完成 PATCH）。
5. 前端：自動儲存文案 + 續做（載 draft）+ 錯誤 banner/重試。
6. dashboard：`doc_status`/`completion` 端點 + 卡片狀態。
7. 進度 rail + 完成度。
8. （未來）LLM 全域 CoAgent 設計 — 另開 spec。
