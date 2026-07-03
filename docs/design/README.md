# docs/design/ — 子系統端到端設計(agent-facing)

> 這裡放**跨 app / seam** 的端到端說明:讓 agent(也讓人)**不看 code 也能改對**——不亂發明端點、
> 不把退役路徑救回來。**為什麼這樣做**見 [`../specs/2026-07-03-agent-facing-docs-research.md`](../specs/2026-07-03-agent-facing-docs-research.md);
> 這份是**怎麼做**(照著寫)。

## 什麼進來(blast radius)

| 文檔涵蓋 | 放哪 |
|---|---|
| 跨 app / seam / 契約(如 editor×knowledge-pack) | **這裡 `docs/design/`** |
| 單一 app 內部 | **該 app 底下**(README / AGENTS) |
| 決策「為什麼」 | `docs/adr/` |
| 研究 / 診斷 / 選項 | `docs/specs/` |
| 怎麼操作 | `docs/runbook.md` |

## 怎麼寫(一份給人也給 LLM)

內容寫給人;**別為 LLM 改寫措辭**(那會同時害人也 poison the AI well)。差別只在**結構讓機器不誤讀**。

**一句話**:把「它會猜的地方」全寫死——動作配請求、欄位用真名、不變量與退役禁令白紙黑字。

**4 條**:
1. 具體名詞取代模糊詞(不是「存檔」,是 `PATCH …/document`)。
2. 每個 UI 動作配一行「→ 發什麼請求」(或「→ 哪個純函式,不發請求」)。
3. 不變量 + 禁令寫死,尤其「**X 已退役,別叫**」。
4. 一個帶真實值的例子勝過三段說明。

**過關清單**(結構層,dual-audience):
- [ ] 每節自足(front-load context,單獨讀一節也懂)
- [ ] 明講不靠推論(前提 / 真名 / 預設值都寫)
- [ ] 語意化階層(標題達意、清單優先於長段落)
- [ ] 表格 row-atomic(每列自成一句,別靠跨格關係)
- [ ] 關鍵資訊別藏(不只圖 / 摺疊 / tab;附可複製範例)
- [ ] frontmatter 選配(`title / audience / updated`,供可靠擷取)

**自檢一問**:一個沒看過 code 的 LLM 讀完這段,**會不會去發明一個不存在的端點/欄位?** 會 → 還不夠具體。

## 骨架

```
# <子系統> — 一句定位(標明主讀者=agent)
角色與資料模型   誰擁有什麼狀態、精確欄位名
端到端資料流     runtime 場景,每步標端點
UI 動作 → 請求   點 X → GET/PATCH Y
不變量           跨檔案、code 讀不出的規則
已退役 / 別做     退役端點、刻意設計(別重構)
指路             ADR / spec / 契約連結(不複製內容)
```

## 例:同一段「選任務」,爛 vs 好

**❌ 爛**(害 LLM 去發明我們退役掉的 `buildTasks`):

> 選好職類後,系統列出候選任務讓你挑,挑完就建立任務結構。

**✅ 好**:

> **資料源**:知識包 `pools.tasks`(`taskRows(pack)`)——不是任何 task-candidates 端點。
> **動作 → 請求**:勾選 → `addTasksToUnit(doc, ui, […])`(純函式)→ `PATCH …/document`(autosave)。無 curation 專用端點。
> **已退役,別叫**:`…:buildTasks`、`…/task-candidates`(P3 已刪,web 無對應 client)。
> **例**:空職責首開「選任務 ▾」→ 自動帶官方 3 任務(預勾)→ 再勾一個他職責的(借用,`_ref` 記來源)→ `renumber` 給 `T1.1…T1.4` → PATCH 存草稿。

## 鐵律

- **動那條線的碼 → 同 commit 更這份文檔**(fossilization 是頭號壞味道)。
- **一定要被指到**:跨 app 從根 `CLAUDE.md` 指路;app 內從該 app `AGENTS.md`。沒被指到 = 白寫。

## 現有文檔

- [`editor-knowledge-pack.md`](./editor-knowledge-pack.md) — 編輯器 × 知識包(apps/web 著作 UI + apps/api knowledge/document 端點)
