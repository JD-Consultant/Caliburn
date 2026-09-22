# Decision-to-Product Governance Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 建立單一、可追溯且有停止條件的討論到產品流程，先停止 Memory 文件互相矛盾與重複研究的惡化。

**Architecture:** `docs/decision-process.md` 定義穩定流程與 gate；`docs/current-decisions.md` 只保存目前有效狀態、未決題與權威連結。`AGENTS.md` 強制 agent 先讀決策表，`docs/README.md` 只作入口，不再讓文件清單本身冒充目前結論。

**Tech Stack:** Markdown、Nygard ADR lifecycle、repo-native link／status checks

**Spec:** `docs/decision-process.md`

## Global Constraints

- 保留現有未提交內容，不重寫或提交其他人的變更。
- 本輪不選 Memory framework、不修改 production code、不改 Accepted ADR 內容。
- 聊天紀錄、研究稿與施工計畫都不能單獨成為 production authority。
- Working Decision 在被明確 supersede 前約束後續討論，但與 Accepted ADR 衝突時不能授權 production。
- 所有外部方法主張都連到官方 AWS、Microsoft 或 Google 原始資料。

---

### Task 1: 建立穩定決策流程

**Files:**
- Create: `docs/decision-process.md`

**Interfaces:**
- Consumes: `AGENTS.md` 現有工作紀律與 `docs/adr/README.md` ADR lifecycle
- Produces: 後續研究、設計、spike、ADR、plan、implementation 都必須遵循的 gate 與模板

- [x] **Step 1: 寫出 authority 層級與 artifact 單一責任**

明定 North Star、Current Decision Register、research、spec、ADR、plan、current design 的不同用途；禁止用長研究稿或聊天取代目前決策。

- [x] **Step 2: 寫出 Decision-to-Product gates**

定義問題、證據、Owner 決策、可驗證設計、必要 spike、ADR、垂直實作與產品驗收的進入／退出條件。

- [x] **Step 3: 寫出停止、重開與每輪收尾規則**

只有需求改變、新權威證據、實驗推翻或內部矛盾可以重開；新資料若不改變決策只補佐證。

- [x] **Step 4: 自審官方來源與過度流程**

確認 AWS／Microsoft／Google 連結直接支持所述機制，且沒有聲稱 OpenAI／Anthropic 公開了未公開的內部產品流程。

### Task 2: 建立唯一現行決策入口並止血 Memory

**Files:**
- Create: `docs/current-decisions.md`

**Interfaces:**
- Consumes: `docs/decision-process.md`、Accepted ADR、現有 Memory research／design／plan
- Produces: agent 與 reviewer 的第一閱讀入口

- [x] **Step 1: 建立精簡決策表**

每列包含 ID、狀態、目前結論、權威／佐證、重開條件與下一個 gate。

- [x] **Step 2: 明確標記 Memory production authority**

保留 Accepted ADR 0060 與現行 code 的 production authority；新 Memory 研究尚未取得 production 授權。

- [x] **Step 3: 登記真正衝突與未決題**

把 Checkpointer／Store responsibility、完整 conversation 保存，以及相似 A／B 工作案例的保存／整併／召回列為待處理決策，不在登記表內偷選答案。

- [x] **Step 4: 暫停矛盾施工文件**

把 2026-09-02 Memory slice／review／plan 標為 reconciliation 前不可施工，但保留為研究證據。

### Task 3: 讓所有後續 agent 一定看見流程

**Files:**
- Modify: `AGENTS.md`
- Modify: `docs/README.md`
- Modify: `docs/plans/2026-09-03-decision-to-product-governance.md`

**Interfaces:**
- Consumes: Tasks 1–2 的兩份新入口
- Produces: repo orientation 與文檔路由的強制 preflight

- [x] **Step 1: 在 AGENTS.md 加入最小強制規則**

要求重大討論／研究／設計／施工前先讀 Current Decision Register，列出 topic ID、stage 與唯一待決題；若找不到目前狀態就先補登記表。

- [x] **Step 2: 在 docs/README.md 把兩份入口放到最前面**

保留使用者現有未提交內容，只增加精準連結與「清單不是施工授權」警告。

- [x] **Step 3: 驗證連結、狀態與 diff**

Run: `rg -n "decision-process|current-decisions|MEM-Q|GOV-D" AGENTS.md docs/README.md docs/decision-process.md docs/current-decisions.md`

Expected: 四個入口都互相可追溯，Memory 未決題有唯一 ID。

Run: `git diff --check -- AGENTS.md docs/README.md docs/decision-process.md docs/current-decisions.md docs/plans/2026-09-03-decision-to-product-governance.md`

Expected: no output。

- [x] **Step 4: 更新本計畫 checkbox 與 handoff**

只報告本輪建立的治理入口、Memory 被暫停的原因與下一個唯一決策題；不宣稱 Memory 技術設計完成。
