# 研究紀錄:給 LLM 看的文檔怎麼寫(agent-facing docs / context engineering)

- **日期**:2026-07-03(2026-07-04 補:dual-audience「怎麼放+怎麼寫」→ §1b / §2.6 / §3a / §3b)
- **狀態**:研究完成;歸檔採 blast-radius(§3a);是否開 ADR 待討論(§4)
- **動機**:維護者要一份「完整寫出流程/架構/model,連底層(點某某會發請求)都清楚,
  別人不看 code 就懂」的文檔,而且**主讀者是 LLM**——讓 agent 知道在幹嘛、**不亂寫**
  (不憑空編端點、不把退役路徑救回來)。
- **與既有研究的分工**:[`2026-07-03-app-developer-docs-research.md`](./2026-07-03-app-developer-docs-research.md)
  研究的是**人向 per-app README**(matklad/Diátaxis/arc42/Google);本篇補的是
  **agent-primary 的深度 explainer + 交付機制**。兩者是不同 genre,原則互證(見 §2)。

## 1. 來源(全部權威;類別標註)

| 來源 | 類別 | 要點 |
|---|---|---|
| Anthropic〈Effective context engineering for AI agents〉anthropic.com/engineering | **官方一手** | **right altitude**(Goldilocks:夠具體能導引、夠彈性留啟發);目標=「**最小的高訊號 token 集合**」;**minimal ≠ short**;`CLAUDE.md` **開場就載入** + 其餘細節檔用 **just-in-time** 動態讀(維持輕量指標:路徑/連結);Markdown 標題或 XML 標籤分區;**範例=一圖勝千言**(給典型、別窮舉邊界);結尾放 **anti-patterns 區**;長任務用**結構化筆記**(context 窗外持久記憶) |
| AGENTS.md — agents.md | **開放標準** | 2025-08 由 OpenAI+Google+Cursor+Factory 推;2025-12 捐給 **Linux Foundation** 的 Agentic AI Foundation;6 萬+ repo、20+ 工具採用。定位:**README 給人、AGENTS.md 給 agent**;純 markdown、無強制欄位;**巢狀就近生效**(agents read the *nearest* file;*closest takes precedence*;OpenAI 自家 repo 有 88 份) |
| llms.txt(Jeremy Howard / Answer.AI 2024-09)llmstxt.org | **提案標準** | 解「context 裝不下整份文件 + HTML 雜訊」;結構:**H1 名稱 → blockquote 一句摘要 → 細節區 → H2 分區列 `[名](url): 註` 連到 `.md` 細節檔**;`llms-full.txt` 把全部攤平供深讀。核心=**精簡入口 + 指向細節檔** |
| 〈Configuration Smells in AGENTS.md Files〉arXiv 2606.15828 | **實證研究** | 頭號壞味道 **Initialization Fossilization**(檔案沒跟著更新→agent 拿舊資訊亂做);其餘:文件不完整、過度複雜、命名不一致。對策:**定期審查週期、具體範例、精簡分組、命名一致** |

> 二手佐證(非權威,僅補充):Anthropic 2026 coding report 整理出的 CLAUDE.md 骨架
> (overview/tech stack → 架構原則 → 慣例 → 測試 → 指令 → 結尾 anti-patterns);
> Fern〈LLM-friendly docs〉:markdown 不用 PDF/HTML(HTML 多耗 ~90% token)、給可複製指令與輸入/輸出範例。

### 1b. 補研究:一份給人也給 LLM(dual-audience,2026-07-04)

| 來源 | 類別 | 要點 |
|---|---|---|
| Mintlify〈Structuring docs for AI & human readers〉 | 文檔平台實務 | **一份來源**:Markdown 為底(AI 可靠掃讀)+ 人向 UI 疊加;AI **分塊**檢索 → 需精準達意的**標題階層**、**清單優先**、**frontmatter** 供擷取;**摺疊/tab 內容 AI 常抓不到** |
| passo.uno(F. Ferri Benedetti,資深技術寫作者)〈Write differently for LLMs?〉 | 資深人物 | 「**Write for humans, let the AIs follow**」;為 LLM 改寫措辭會**害人 + poison the AI well**;LLM 是**新通路不是新讀者**——差異靠**交付**(semantic markup/metadata/llms.txt)不靠改內容 |
| kapa.ai〈Writing documentation for AI〉 | RAG 實務 | **每節自足**(檢索不保留文件順序,節要能單獨看懂)、front-load context;**明講不靠推論**(「沒寫=系統不知道」);語意化標題/清單;**別靠視覺排版/表格結構/圖片承載意義** |
| State of Docs Report 2026 | 產業調查 | 「**Good for humans is not good for agents**」;agent 有 token 上限、**會靜默截斷**、需更原子化;良性循環:清晰文檔→好 AI 答案→暴露缺口→再改 |
| Diátaxis(Daniele Procida)× AI | 官方框架應用 | 四型**按讀者意圖分**,正對 agent 意圖推理;乾淨 reference **減 RAG 幻覺**、按型分讓 agent **只載相關象限省 token**;**llms.txt 在 Diátaxis 已分型時最有效** |

## 2. 共識(四源收斂,並與人向 README 研究互證)

1. **兩層交付**:**常駐精簡**(`CLAUDE.md`/`AGENTS.md`,開場載入)+ **按需深度**(細節 `.md`,JIT 讀)。
   = Anthropic 混合式 × llms.txt「入口→細節」× AGENTS.md「巢狀就近」。**別把深文檔塞進常駐檔**。
2. **right altitude / 最小高訊號**:不是寫越多越好;優先放**從 code 讀不出來的**東西——
   不變量、精確名(欄位/端點)、禁令。(呼應 matklad:invariants「常是代碼裡讀不出的『沒有什麼』」)
3. **防亂寫三件**:① 明列**不變量與精確名**(欄位/端點寫死,模型就不自己發明)
   ② **具體範例**(一圖勝千言)③ 結尾 **anti-patterns/禁令**(「X 已退役,別叫」)。
4. **fossilization 是頭號殺手**:文檔沒跟碼走 → agent 把死路徑救回來。
   ⇒ **文檔跟 code 同一個 commit 更新**(與 Google「docs-with-code」、README 研究第 5 點同結論)。
   我們**剛退役 header-meta / task-candidates / task-catalogs / buildTasks 四端點**,正是最高風險點。
5. **順既有機制擴,不另造框架**:caliburn 根 `CLAUDE.md` 的「指路」段 = 一份**土製 llms.txt**;
   沿著它加,而不是發明新目錄慣例。
6. **一份來源、內容寫給人、結構服從機器**(dual-audience 收斂):**別為 LLM 另寫一份或改寫措辭**——那會
   同時害人也 poison the AI well(passo.uno);把 LLM 當**新通路不是新讀者**。分歧只在**結構**:agent 會
   分塊檢索、會截斷、看不到視覺排版 → 每節**自足**、**明講不靠推論**、**語意化標題+清單**、**表格 row-atomic**、
   關鍵資訊別藏圖/摺疊/tab。用 **Diátaxis 按意圖分型**當骨架:人照需求找、agent 只載相關象限(省 token、少幻覺)。

## 3. 套用到本 repo

**兩層落點**:

| 層 | 放什麼 | 落點 | 依據 |
|---|---|---|---|
| **T1 常駐·精簡** | 不變量／精確名／「已退役別叫」／指路 | 根 `CLAUDE.md`(已有);子系統可選 nested `CLAUDE.md` | Anthropic 開場載入 × AGENTS.md 就近生效 |
| **T2 按需·深度** | 端到端 explainer(流程/model/click→request) | `docs/design/<subsystem>.md`;從 T1 指過去 | Anthropic JIT × llms.txt 入口→細節 |

**T2 骨架**(對齊 Diátaxis 的 reference+explanation、arc42 runtime view;結尾 anti-patterns 照 Anthropic):

```
# <子系統> — 一句定位(+ 標明「主讀者=agent」)
角色與資料模型   誰擁有什麼狀態、精確欄位名(如 _ref / srcs / URN 三分)
端到端資料流     runtime 場景:選職類 → 抓知識包 → 各選單讀池 → 勾選 → autosave PATCH;每步標端點
UI 動作 → 請求   對照表:點 X → GET/PATCH Y
不變量           跨檔案、code 裡讀不出的規則(條列)
已退役 / 別做     anti-patterns 禁令(退役端點、別重構的刻意設計)
指路             ADR / spec / contract 連結(不複製內容)
```

- 語言**繁中**;**表格優先**;**living**(結構性改動同 commit 更新)。
- **分工不互抄**:`ARCHITECTURE.md`=跨 app 鳥瞰;per-app `README`(人向)=app 內部地圖;
  **`docs/design`(agent 向)=子系統端到端深度**;`docs/adr`=為什麼。彼此**連結,不複製**。
- **第一份 T2**:`docs/design/editor-knowledge-pack.md`(pack → 12 池 → 選單 → `_ref`/URN → autosave 寫回;
  含四端點退役)。這是全 repo 最複雜、最容易被下個 session 亂改的一段。

### 3a. 怎麼放(歸檔:blast radius + docs-as-code)

- **按 blast radius 歸檔**:整條線只住一個 app → 放**那個 app 底下**(README/AGENTS/其 `docs`);
  **跨 app / seam / 契約** → 根 `docs/design/`(沒有單一 app 擁有,塞一邊會讓另一邊漂)。對照現況:
  根 `docs/`(ADR/specs/contract/ARCHITECTURE)本就管跨 app;per-app README/AGENTS 管 app 內。
  首份 editor×knowledge-pack **跨 web+api → 放 `docs/design/`**。
- **monorepo 讓「放哪」退化成整潔問題**:中央 `docs/` 與 `apps/*` 同一棵樹、**同一個 commit 就能一起改**;
  「不漂」靠 **living 鐵律**(動碼同 commit 更文檔),不是資料夾距離(那是 polyrepo 的痛)。
  docs-as-code:**版本控管、review、跟碼一起改**(State of Docs / Google docs-with-code)。
- **可發現性 ≠ 位置**:跨 app 靠根 CLAUDE.md 指路;app 內靠該 app AGENTS/README 指。
  指標防「看不見而 fossilize」,資料夾只是收納。

### 3b. 怎麼寫(一份給人也給 LLM 的過關清單)

內容照 T2 骨架寫給人(別為 LLM 改寫措辭);**結構過這關**(dual-audience):

- [ ] **每節自足**:front-load context;一節被單獨讀到也懂(部分載入/RAG 友善)。
- [ ] **明講不靠推論**:前提、精確欄位/端點名、預設值都寫出來(「沒寫=系統不知道」)。
- [ ] **語意化階層**:標題精準達意、清單優先於長段落;巢狀層級反映結構。
- [ ] **表格 row-atomic**:每列自成一句,別靠「跨格關係」表意;複雜關係改用清單或重複脈絡。
- [ ] **關鍵資訊別藏**:不要只放圖/摺疊/tab;附可複製指令與輸入/輸出範例。
- [ ] **frontmatter(選配)**:`name/description/audience/updated` 供可靠擷取(Mintlify)。
- **本 repo 關鍵限定**:我們的 design 文檔是**指標→整檔 JIT 載入**(非 RAG 分塊),故「每節自足」比重較低、
  **明講+精確名+不變量+不 fossilize** 比重最高;**日後若把文檔餵進嵌入/RAG,再把自足與原子化拉滿**。

> **落地**:操作總則(taxonomy / 擺放 / 寫作 / 維護)= [`../README.md`](../README.md);
> design 文檔 how-to = [`../design/README.md`](../design/README.md)。本 spec 只管「為什麼」(研究/來源)。

## 4. 待決(留給討論)

1. **要不要開 ADR 記這個慣例?**
   - (a) **輕**:只寫本 spec + `docs/design/…` + 根 CLAUDE.md 指路一行。(avoid-overengineering)
   - (b) **重**:開 **ADR 0022「agent-facing docs 慣例」**,讓「深文檔住 docs/design、agent 主讀、跟碼走」
     成為可查權威 + 進 adr/README 索引。
   - 傾向:先 (a) 落地一份試水;若確實有效再補 (b) 定為慣例。
2. **T1 交付**:只靠「根 CLAUDE.md 指路 → docs/design」(最小),還是**加子系統 nested `CLAUDE.md`**
   (自動載入、但多一份常駐檔)。傾向:先最小,nested 之後有需要再加。
3. **`CLAUDE.md` vs `AGENTS.md`**:查證後修正——**repo 已兩者並用**:`apps/web/CLAUDE.md` 只寫 `@AGENTS.md`
   匯入、`apps/web/AGENTS.md` 放該 app 規則。續用此 idiom(CLAUDE.md 匯入/指向、AGENTS.md 放內容),
   不需另做選型。
4. **root `CLAUDE.md` 追蹤?**(2026-07-04 研究+決議)——查主流:**Anthropic 模型 = `CLAUDE.md` 是
   *committed* 的 team memory(每 session 開場載入)、只有 `CLAUDE.local.md` gitignore**;`AGENTS.md`
   更是**設計上就 check-in**(version-controlled infrastructure)。本 repo 原把 root `CLAUDE.md` ignore
   (疑似 Claude Code `/memory` 早期自動加,anthropics/claude-code#633)。**決議:改為追蹤 root
   `CLAUDE.md`、`.gitignore` 改留 `CLAUDE.local.md` 供個人筆記**——順帶讓 #7 與指路隨 repo 共享。
