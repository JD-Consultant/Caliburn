# 2026-09-15 進度與 worktree 地圖

## 目的

這份文件只整理目前現況、分支用途與接線邊界，不代表已完成 production cutover，也不取代各項研究／驗收證據。這一輪沒有 push；所有文件仍保留，淘汰的是已確認沒有當前產品價值的舊審查 worktree。

## 先講結論

產品核心目標以 [產品文件](product-notes.md) 為準：這是一個 JD App；人與 LLM 可走不同 endpoint，但共用 relational JD 業務邏輯。顧問在 framework 內經 OpenRouter 使用 OpenAI Luna。第一版只要求顯示及安全撤回當輪 LLM 的 JD 變更；已實作的完整 JD 歷史／整份舊版還原可保留，但不作接線前置或繼續擴張。原始對話、案例、Memory 與工作理解保留。本文 worktree 名稱只表示開發用途；「顧問線」也是這個 App 的內部功能開發線。詳細接線盤點見 [對齊工作稿](specs/evidence/2026-09-15-jd-integration-document-reconciliation.md)。

- **LLM 顧問已完成。**目前產品路由基線是 LangChain／LangGraph＋OpenRouter，固定 OpenAI provider 的 `openai/gpt-5.6-luna`；自然模型試用與 prompt 校準不重做。證據主要在 `codex/analysis-only-agent` 的 CT07／CT25／CT37／CT40／CT51 文件；該 worktree 後期出現的直連 `ChatOpenAI` factory 需當接線候選核對，不能覆蓋 Owner 本輪確認的 OpenRouter 邊界。
- **JD App 的 relational 核心已完成主要新架構施工，作為目前整合基線。**關聯式保存、編輯、當輪差異／撤回、來源與 H4 施工證據集中在 `refactor/current-only-architecture` 線；已額外完成的完整歷史／整份還原不屬目前首版必要需求，不因此成為接線前置。程式現況保全提交是 `5643d586`；目前整理分支 `tmp/save-all-20260914` 在本輪開始前的 HEAD 是後續文件提交 `355c9240`。
- **真正尚未閉合的是 App↔LLM 的完整接線驗收。**不是「還沒決定 Anthropic model id」，也不是要重新做 Luna prompt。2026-09-15 已把顧問正式入口、B1 OpenRouter route 與 runtime 動態文件 scope 接好。A／B2 共用的長對話 transport 門已完成離線考卷與一輪真 OpenRouter smoke：23,725 input tokens 高於 12,000 門檻、OpenAI Luna route 正確，但沒有產生 compaction item，故維持 `SERVER-UNVERIFIED` 並停在 Owner 的 transport／credential 裁決；此外仍須把通知／背景 dispatcher、真 PG／新程序與完整 App 旅程串起來。
- **文件全留。**現在不大量搬移或刪除文件，避免破壞歷史連結；改以本文件與 `docs/current-decisions.md` 最新更正作為入口。

## 接線為什麼會「做一半又像做錯」

目前看到的是兩條已完成程度不同的線被誤當成一條：

1. 舊／獨立的 LLM 顧問線已經完成實際 Luna 試用與 prompt 校準，並累積自然多輪、Memory 與輸出預算證據。
2. 新 JD App 線後來採用關聯式保存與新的 App 邊界，不是把 `analysis-only-agent` 整個 checkout 搬進來。
3. 新 App 確實已有分段接線提交：B1 extraction／provider adapter、訪談來源、change notices、guidance／Skills，以及 provider convergence；其中直連 OpenAI 的 adapter／factory 與 credential 做法已確認偏離 OpenRouter 基線，不能原樣採用。
4. 但「有建構函式／有 adapter／有測試」不等於「新 App 的 daily entry 已經以真設定完成顧問呼叫、接收結果、保存 JD 與回傳對話」。早期文件把這些不同層級寫在一起，才造成「只差模型 id」的錯誤理解。

因此目前的正確工作單位是**接縫對照與端到端驗收**：逐一確認入口、設定、模型呼叫、工具／來源、結果保存及回覆投影；不能把舊顧問線或舊 editor 線整包 merge。

## 已確認的整合提交順序

以下是目前新 JD 線上最重要的接線證據，不代表每一項都已完成產品入口驗收：

| 提交 | 內容 | 現況判定 |
|---|---|---|
| `353c400b` | 採用已驗證的 B1 extraction workflow | 已採用的基礎能力 |
| `6c49cc02` | 採用 B2 consolidation workflow | 已採用的套件能力 |
| `9fdef9eb` | 將 B1 extraction 接到當時的 OpenAI 路徑 | 保留 workflow 接縫證據；直連 provider transport 不採用。2026-09-15 未提交切片已沿 OpenRouter profile 重接並通過完整離線回歸 |
| `dd25ecdc` | 將目前訪談來源接到 shared JD edits | 分段接線 |
| `710e2b6c` | 將 change notices 接到完整顧問回覆 | 分段接線 |
| `b6b6391e` | 顧問方法、Skills、Memory guidance、通知能力 | 建構能力已接入 |
| `dbddc368` | 施工期把產品顧問從 Anthropic 收斂到 OpenAI | OpenAI Luna／單一顧問方向可保留；直連 `ChatOpenAI`／`OPENAI_API_KEY`／移除 OpenRouter 的部分無效 |

## Worktree 分類

### 保留：目前需要審查或可能作為證據

| worktree | 分支／HEAD | 用途與判定 |
|---|---|---|
| 根目錄 `S:\caliburn` | `tmp/save-all-20260914@355c9240` | `5643d586` 保存程式現況，`355c9240` 是本輪開始前的後續文件提交；目前未提交的對齊文件放在這裡，暫不 push。 |
| `.worktrees/analysis-only-agent` | `codex/analysis-only-agent@2b16d11d` | LLM 顧問、Luna 真模型試用、prompt 校準、Memory／自然多輪證據。這是已完成顧問線，不是要整包搬進新 App 的分支；目前可見 426 筆 tracked deletion，集中在測試產生的 `catalog.db`／暫存樹，先視為未整理測試現場，不判成產品刪除。 |
| `.worktrees/consultant-workspace-ui` | `codex/consultant-workspace-ui@f4acb5a4` | 較早的顧問 UI／JD inline editing 候選，保留供比對，不當目前入口。 |
| `.worktrees/langgraph-document-authority-spike` | `spike/langgraph-document-authority@b6eaa15f` | LangGraph runtime、Saver／Store、文件 authority 的研究／接合 spike；不是目前產品 authority。 |
| `.worktrees/memory-routing-canonical-read-spike` | `codex/memory-routing-canonical-read-spike@a370af94` | Memory canonical read、routing、OpenRouter／LangChain 的研究線；可用來核對來源讀取，不直接接回產品。 |
| `.worktrees/shared-current-jd` | `codex/shared-current-jd@56db1249` | 較早的 shared current JD foundation；保留比較資料，不取代目前關聯式 JD App。 |

### 已淘汰：工作區移除，但歷史仍保留

這三個是舊 `origin/main`／job-analysis／OPKS 審查副本，與目前新 JD／LLM 主線無關，且當時工作區乾淨；已移除本地 worktree，分支改名保存：

- `archive/integrate-local-opks-review-20260915`（原 `integrate/local-opks-review`）
- `archive/integrate-reviewed-origin-main-20260915`（原 `integrate/reviewed-origin-main`）
- `archive/review-origin-main-20260915`（原 `review/origin-main`）

這是**本地工作區整理**，不是刪除 Git 歷史，也沒有刪除遠端分支或 push。

## 舊 `apps/api`／`apps/web` 怎麼處理

不要因為目錄名稱是舊架構就整個刪掉。新 JD App 的部分接點仍在這些正式產品目錄中；應該依目前 authority 淘汰舊模組、舊分支與舊入口，並在確認沒有引用後再做窄刪除。現階段先不動程式碼，避免把「舊模組淘汰」誤做成「整個正式產品目錄刪除」。

## 文件整理規則

目前先不刪文件，分成四類理解即可：

- **現況／權威入口：** `docs/current-decisions.md`、`docs/decision-process.md`、已 Accepted 的 ADR。
- **已完成證據：** `docs/specs/evidence/` 與各 CT／真模型結果文件。
- **候選／施工中：** `docs/specs/`、`docs/plans/`、Proposed ADR；不能因有測試就當成 production authority。
- **歷史／淘汰線：** 舊架構、舊分支、舊 provider 假設；保留以供審查，但不作目前下一步。

下一步審查只需要回到本文件的接縫表，再對照實際入口與測試，不需要重新讀完所有歷史文件，也不需要重做已完成的 Luna 顧問試用。
