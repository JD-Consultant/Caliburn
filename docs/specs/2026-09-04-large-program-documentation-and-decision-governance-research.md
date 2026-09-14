# 大型產品討論、研究、設計與文件治理研究

- **日期**：2026-09-04
- **狀態**：Working Research；建議先試行，尚未成為 Accepted process
- **Topic ID**：`GOV-Q004`
- **目的**：避免長文膨脹、重複研究、結論漂移、只討論不前進，以及實作者沒有看到最新討論
- **不處理**：任何 Memory、LLM runtime、JD、UI 或 production 實作決策

> 更正紀錄：最初曾把「父層地圖＋一次一個子決策」直接寫成結論。跨家核對後確認，這不是共同標準，只是可選的導航與切分方式；本稿已撤回該前提。

## 1. 結論

建議採用的是**分層的單一事實來源＋一份 coherent Working Design＋由粗到細的 review**，不是強制父子決策樹，也不是每個小問題都另開文件。

```text
短的 current index
    ↓
一份目前產品成果的 Working Design（可含數個不可分割的決策）
    ↓
需要時才讀官方 Evidence／專題附件
    ↓
重大決策核准後形成精簡 ADR
    ↓
ExecPlan／小型垂直實作／驗證
    ↓
更新 Current Design，Working Design 歸檔
```

只有同時存在多條真正獨立的 workstream、讀者無法找到入口時，才加一張 topic／program index。它只是導航，不是額外 authority。

## 2. 官方公開做法

| 來源 | 官方直接支持的做法 | 不可外推的部分 |
|---|---|---|
| [OpenAI：Harness engineering](https://openai.com/index/harness-engineering/) | 短 `AGENTS.md` 作目錄；repo 內分開 design docs、product specs、references、active／completed plans；索引、verification status、progress／decision logs、文件 lint 與 gardening；細節 progressive disclosure | 是 OpenAI 某個 agent-first 工程團隊公開做法，不是所有組織都必須複製其目錄 |
| [Claude Code：Memory and project instructions](https://code.claude.com/docs/en/memory) | 常駐規則保持具體、精簡、不衝突；topic／path-scoped rules 與按需 Skills 分流細節；小型 `MEMORY.md` 索引，topic 文件按需讀；重複犯錯才加入持久指引 | 200 行／25KB 是 Claude auto-memory 首次載入邊界，不是所有設計文件的通用長度限制 |
| [Anthropic：Effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents) | 長工作使用結構化 feature/progress artifact、git history、每次一個可完成增量、結束留下可接手狀態，並做端到端驗證 | 官方明確定位為長期 coding harness 的實驗做法；JSON feature list 不是產品研究標準 |
| [Google：Software Engineering at Google — Documentation](https://abseil.io/resources/swe-book/html/ch10.html) | 文件有 owner、版本控制與 review；指定 canonical source、去除重複；一文件一目的／受眾；重大工作先 review design doc，寫 goals、策略、選項與 trade-offs | 不要求每個小決策一文件，也不指定 Caliburn 的目錄與狀態名稱 |
| [Google：Navigating a change](https://google.github.io/eng-practices/review/reviewer/navigate.html) | 先看變更是否合理與整體設計，再看細節；方向有問題就及早停止，避免後續審查成為浪費 | 是 code review 指南；本稿只映射其 broad-to-detail review 原則 |
| [Amazon：Working Backwards](https://www.aboutamazon.com/news/workplace/an-insider-look-at-amazons-culture-and-processes) | 先寫清楚顧客體驗與價值再倒推建置；以有篇幅約束的 PR/FAQ 反覆 review，先高階回饋再逐段檢查；紀錄會議結果 | PR/FAQ 的一頁／五頁格式是 Amazon 產品流程，不是 Caliburn 的固定模板 |
| [AWS：ADR process](https://docs.aws.amazon.com/prescriptive-guidance/latest/architectural-decision-records/adr-process.html) | decision log 提供可掃描入口；ADR 記 context、decision、consequences、owner、狀態；Rejected 保留理由；Accepted 後 immutable，以新 ADR supersede | ADR 只適合 architecturally significant decision，不是研究筆記或 implementation guide |
| [Microsoft：Maintain an ADR](https://learn.microsoft.com/en-us/azure/well-architected/architect-role/architecture-decision-record) | ADR 保持精簡、聚焦、事實化；記 problem、options、trade-offs、confidence、status；詳細設計用連結，不把 ADR 寫成設計指南 | 不提供通用 research 流程，也不要求每個產品問題都升格 ADR |

## 3. 跨來源共同原則

以下是多份官方資料共同支持的 **Inference**，不是任何一家公司逐字規範：

1. **先對齊產品成果，再進技術細節。**
2. **每項知識有 canonical owner／位置，並放在版本控制與 review 流程內。**
3. **文件按目的與受眾分層，不把指引、研究、決策、施工與 current design 混成巨型長文。**
4. **入口短而可掃描，細節透過連結按需展開。**
5. **先 review 整體方向，再 review 架構，最後才是 schema、函式與 UI 細節。**
6. **工作以可完整理解、驗證與接手的 coherent increment 推進。**
7. **重大決策記理由與狀態；已接受的決策不靜默改寫，而以 successor 保存歷史。**
8. **文件必須持續維護：移除死文件、避免複製、檢查 freshness／links／ownership。**

## 4. 不是跨家共識的項目

以下只能是 Caliburn 候選，不得再冒充大廠共同規範：

- 必須先建父層 Program map；
- 每輪只能處理一個很小的子決策；
- `G0`～`G8` 的名稱與數量；
- 每輪都輸出完整 preflight／closure 表；
- 每次查資料都另開 research 文件；
- `Evidence gap`、`NO CHANGE` 等固定詞；
- 所有 Markdown 共用一個行數上限；
- Anthropic 實驗中的 JSON feature list 或多 agent 結構。

## 5. Caliburn 現況診斷

2026-09-04 實測：`docs/current-decisions.md` 只有 108 行，卻有約 18.5 KB，最長單行 1,959 字元。這表示問題不是單純「文件行數」，而是 current index 的一格同時保存結論、完整實驗歷史、限制與下一步，失去可掃描性。

目前重複討論主要來自四件事：

1. 聊天、research、register 與 plan 都重述同一段背景；
2. 同一主題因每個小問另開文件，卻沒有一份清楚的 current answer；
3. current register 混入證據與執行紀錄，下一輪仍需重讀大量文字；
4. 把「一次一個 blocking question」理解成每個細節都要另開一輪，造成無限串行討論。

## 6. 方案比較

| 方案 | 優點 | 問題 |
|---|---|---|
| A. 父層地圖＋每題一份子決策 | 追蹤精細 | 容易把緊密相依的設計切碎，文件與對話數量持續增加 |
| B. 每個大主題一份完整母文 | 上下文集中 | 很快變成巨型長文，current、歷史與細節互相淹沒 |
| **C. 短索引＋coherent Working Design＋按需 Evidence＋ADR／Plan 分流** | 保留全貌與理由，又不必把每個小問題拆檔；最接近跨家共同原則 | 需要維持 canonical link 與定期整理舊文件 |

**建議試行 C。**「coherent」的界線是同一個可審核產品成果；幾個決策若必須一起看才不會誤解，就留在同一份 Working Design。只有成果、受眾或 authority 真正分叉才拆檔。

## 7. 建議文件分層

| Artifact | 只回答什麼 | 不保存什麼 |
|---|---|---|
| `AGENTS.md` | 每次工作都必須遵守的穩定規則，以及去哪裡找 current 資料 | 專題研究、長歷史、task-specific 步驟 |
| `docs/current-decisions.md` | ID、狀態、一句 current outcome、canonical link、下一個 review／reopen trigger | 完整來源分析、逐次實驗紀錄、長篇理由 |
| Working Design（`docs/specs/`） | 一個 coherent 產品成果目前應怎麼運作、為什麼、還缺什麼 | 逐輪聊天摘要、已搬入 ADR 的重複全文 |
| Evidence appendix（選用） | 被多個設計重用，或過大而妨礙閱讀的官方事實／比較矩陣 | Caliburn 決策；每份 Working Design 仍須直接說明 mapping |
| `docs/adr/` | 已核准且重大／難逆的決策、理由、後果 | 探索過程與詳細 implementation guide |
| `docs/plans/` | 核准設計如何施工、驗證、回報進度與發現 | 新增產品語意或暗中翻案 |
| `docs/design/`／README | production 現在如何運作 | 候選、已淘汰流程與討論歷史 |

Working Design 頂端固定提供短的 current view：

```text
Status / Owner
Product outcome
Current recommendation
Decided constraints
Open risks or decisions
Next review gate
Canonical evidence links
```

正文才放 user scenarios、資料流、選項／trade-offs、錯誤與成本；底部只記**有改變方向的** decision delta。不要保存每輪「同意／OK」的聊天轉述。

## 8. 討論到產品的試行流程

### 8.1 Orient（代理人先做，不拿模板轟炸使用者）

1. 讀 `AGENTS.md`、current index、當前 Working Design 與有效 ADR；
2. 搜尋 topic ID、同義詞與既有官方來源；
3. 說明目前答案、尚未解決的差距與本段要完成的產品成果。

### 8.2 Frame

先確認使用者效果、成功／失敗情境、限制與不處理事項。討論單位是一個 coherent outcome，不強迫拆成單一小問；但與成果無關的旁支另列，不當場展開。

### 8.3 Research delta

只有下列情況才新增外部研究：

- 現有來源不能回答會改變方案的問題；
- 資料具有時效性，可能已變；
- 實驗／實作出現新反例；
- 不同權威來源直接衝突。

新研究先寫清楚「現有證據缺什麼」。找到資料後更新原 Working Design 或其 Evidence appendix；不為換句話說另開文件。若沒有新事實或結論，文件不變。

### 8.4 Review：由粗到細

1. **Product review**：這是不是要解決的問題與員工體驗？
2. **System review**：完整流程、authority、資料生命週期、失敗、成本是否合理？
3. **Contract review**：Tool、schema、API、狀態與 UI 細節是否可驗證？
4. **Implementation readiness**：決策是否足以寫 ADR／plan，是否仍藏有產品選擇？

前一層有阻塞問題時先停，不投入下一層。這不是四份文件，也不要求每層各開一個 chat；它們是同一 Working Design 的 review 視角。

### 8.5 Record only the delta

每段討論後只做三件事：

- 更新頂端 current recommendation／open risks；
- 將真正的新決策以 `日期／決定／理由／來源或觸發證據` 寫入 decision log；
- 明列下一個 review gate 或開始施工的條件。

已說過且沒改變的內容只連結，不重新摘要。Rejected／superseded 的理由要保留，避免下一輪把它當新方案重談。

### 8.6 Build and verify

重大決策先形成精簡 ADR；施工用一份 living ExecPlan，按可端到端驗證的垂直成果切片。每片完成後核對產品成果與方向，再進下一片；完成後更新 Current Design 並將 Working Design 標成 implemented／archived。

## 9. 防止膨脹的具體規則

1. **不以行數機械拆文。**以目的、受眾、產品成果是否分叉判斷；短索引另有掃描性要求。
2. **current index 只放摘要。**實驗時間線、完整來源與理由全部留在 canonical document。
3. **同一事實只分析一次。**其他文件以 section link 引用；需要不同結論時只寫新的 mapping。
4. **Working Design 維持 current answer。**歷史只保留會解釋方向轉折的 decision delta。
5. **Accepted ADR 不改寫。**新方向以 successor supersede；Working 文件則可整理，不必保留每次措辭。
6. **不把聊天當 authority。**討論造成結論改變時才寫回；沒有改變就不產生新版本。
7. **穩定、反覆出錯的規則才放 AGENTS／Skill。**一次性處理留在 plan 或 Working Design。
8. **完成與過時文件要標狀態並退出 current path。**不以檔名中的 `final`／`latest` 爭奪 authority。

可在流程證明有效後再加機械檢查：重複 topic ID、active 文件唯一性、broken link、缺少 owner／status／successor、current index 過長。現在不先建一套重型文件平台。

## 10. 立即套用到下一個產品討論

`LLM-Q001` 已有一份涵蓋 invocation、provider capability、Tool loop、錯誤、重試、receipt 與成本的 coherent Working Design；這些部分必須一起看才不會再次把某個 provider 參數誤當產品要求。

因此下一步：

- 不建立額外 Program map；
- 不另開 strict／Tool／retry 小文件；
- 先做整體 System review，決定是否採 provider-neutral capability contract＋第一個 OpenRouter adapter；
- 方向核准後，才在同一 Working Design 做 contract review；
- Memory revision 4、UI、RAG 與 production 施工仍不在本段範圍。

## 11. 試行驗證與重開條件

先用後續三個 coherent design outcome 試行。若出現任一情況就重開：

- 進場仍需重讀大量歷史才能知道 current answer；
- 同一題仍有多份 active 文件互相矛盾；
- 緊密相依決策被切碎，造成反覆問答；
- Working Design 再次膨脹成 current＋完整歷史＋plan 混合體；
- 實作者無法只靠 current index、Working Design、ADR／plan 找到最新要求。

評估重點是「找到 current answer 的時間、重複研究次數、矛盾 active 文件數、從決策到可驗證產品的時間」，不是單純追求更少 Markdown 行數。
