# 2026-09-15 進度與 worktree 地圖

## 目的

這份文件只整理目前現況、分支用途與接線邊界，不代表已完成 production cutover，也不取代各項研究／驗收證據。這一輪沒有 push；所有文件仍保留，淘汰的是已確認沒有當前產品價值的舊審查 worktree。

## 先講結論

- **LLM 顧問已完成。**目前正確基線是 OpenAI GPT-5.6 Luna；自然模型試用已完成，prompt 也已按試用結果校準。證據主要在 `codex/analysis-only-agent` 的 CT07／CT25／CT37／CT40／CT51 文件。
- **JD App（不含 LLM）已完成主要新架構施工，作為目前整合基線。**關聯式保存、編輯、歷史／撤回、來源與 H4 施工證據集中在 `refactor/current-only-architecture` 線；本地保全快照是 `tmp/save-all-20260914@5643d586`。
- **真正尚未閉合的是 App↔LLM 的完整接線驗收。**不是「還沒決定 Anthropic model id」，也不是要重新做 Luna prompt。現在要確認的是：已完成的顧問建構、Memory／來源讀取、B1／B2、通知／背景流程，是否真的由新 JD App 的日常入口以正確的狀態、設定與保存責任串起來。
- **文件全留。**現在不大量搬移或刪除文件，避免破壞歷史連結；改以本文件與 `docs/current-decisions.md` 最新更正作為入口。

## 接線為什麼會「做一半又像做錯」

目前看到的是兩條已完成程度不同的線被誤當成一條：

1. 舊／獨立的 LLM 顧問線已經完成實際 Luna 試用與 prompt 校準，並累積自然多輪、Memory 與輸出預算證據。
2. 新 JD App 線後來採用關聯式保存與新的 App 邊界，不是把 `analysis-only-agent` 整個 checkout 搬進來。
3. 新 App 確實已有分段接線提交：B1 extraction／OpenAI adapter、訪談來源、change notices、guidance／Skills，以及產品 provider convergence。
4. 但「有建構函式／有 adapter／有測試」不等於「新 App 的 daily entry 已經以真設定完成顧問呼叫、接收結果、保存 JD 與回傳對話」。早期文件把這些不同層級寫在一起，才造成「只差模型 id」的錯誤理解。

因此目前的正確工作單位是**接縫對照與端到端驗收**：逐一確認入口、設定、模型呼叫、工具／來源、結果保存及回覆投影；不能把舊顧問線或舊 editor 線整包 merge。

## 已確認的整合提交順序

以下是目前新 JD 線上最重要的接線證據，不代表每一項都已完成產品入口驗收：

| 提交 | 內容 | 現況判定 |
|---|---|---|
| `353c400b` | 採用已驗證的 B1 extraction workflow | 已採用的基礎能力 |
| `6c49cc02` | 採用 B2 consolidation workflow | 已採用的套件能力 |
| `9fdef9eb` | 將 B1 extraction 接到 App 的 OpenAI 路徑 | 分段接線，需核 daily entry |
| `dd25ecdc` | 將目前訪談來源接到 shared JD edits | 分段接線 |
| `710e2b6c` | 將 change notices 接到完整顧問回覆 | 分段接線 |
| `b6b6391e` | 顧問方法、Skills、Memory guidance、通知能力 | 建構能力已接入 |
| `dbddc368` | 產品顧問改用產品既定 OpenAI provider | 方向已更正為 Luna／OpenAI，仍需入口驗收 |

## Worktree 分類

### 保留：目前需要審查或可能作為證據

| worktree | 分支／HEAD | 用途與判定 |
|---|---|---|
| 根目錄 `S:\caliburn` | `tmp/save-all-20260914@5643d586` | 全部現況的本地保全快照；目前整理文件會先放這裡，暫不 push。 |
| `.worktrees/analysis-only-agent` | `codex/analysis-only-agent@2b16d11d` | LLM 顧問、Luna 真模型試用、prompt 校準、Memory／自然多輪證據。這是已完成顧問線，不是要整包搬進新 App 的分支；目前只看到測試產生的 `catalog.db` 刪除殘留，沒有把它判成產品改動。 |
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
