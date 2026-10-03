# Claude Code 與 Codex 的「對話互動層」設計研究

> 研究員紀錄。目的:給 AI 訪談系統的對話層當先例參照。
> 來源紀律:只收 Anthropic 官方(code.claude.com / anthropic.com)、OpenAI 官方(developers.openai.com,已 308 轉址到 learn.chatgpt.com,仍屬官方文件域)、兩家官方 GitHub repo。二手轉述一律拒收。
> 查閱日期:2026-07-12。各條標 URL。

---

## 產品一:Claude Code(Anthropic)

### Q1 向使用者提問的政策

**行為**:Claude Code 有專用工具 `AskUserQuestion`。官方定位:「當任務有多個有效路徑、Claude 需要更多方向時」才呼叫。形式是**多選一**(每次呼叫 1–4 題,每題 2–4 個選項),不是開放式問答;呼叫端(SDK/CLI)可額外提供 "Other" 讓使用者自填文字當答案。此工具預設可用。官方特別點出:**澄清式提問在 plan mode 最常見**——Claude 先探索 codebase、再問問題、才提計畫,把 plan mode 定位成「gather requirements before making changes」的互動流程。

> 官方引文:「When Claude needs more direction on a task with multiple valid approaches, it calls the AskUserQuestion tool. The input contains Claude's questions as multiple-choice options... Each AskUserQuestion call supports 1-4 questions with 2-4 options each.」

在 best-practices 也有主動邀請提問的段落「Let Claude interview you」:對大型功能,建議使用者用最小 prompt 起手,叫 Claude「Interview me in detail using the AskUserQuestion tool... Don't ask obvious questions, dig into the hard parts I might not have considered. Keep interviewing until we've covered everything, then write a complete spec to SPEC.md.」——注意這裡的**提問是使用者主動要求觸發**的一種工作法。

**頻率門檻與模式互動**:在 **auto mode** 下,官方明說會「nudges Claude to keep working without stopping for clarifying questions, though Claude still asks when your prompt or a skill explicitly relies on it」——即自主模式會**壓低發問頻率**,除非 prompt/skill 明確要求。

- URL: https://code.claude.com/docs/en/agent-sdk/user-input (查閱 2026-07-12)
- URL: https://code.claude.com/docs/en/best-practices (查閱 2026-07-12)
- URL: https://code.claude.com/docs/en/permission-modes (auto mode 段;查閱 2026-07-12)

### Q2 計畫審批模式(Plan Mode + permission modes 分級)

**Plan Mode(審計畫)**:官方定義「Plan mode tells Claude to research and propose changes without making them. Claude reads files, runs shell commands to explore, and writes a plan, but does not edit your source.」進入方式:`Shift+Tab` 循環、或單則 prompt 前綴 `/plan`、或啟動旗標 `claude --permission-mode plan`。

計畫做好後「Claude presents it and asks how to proceed」,審批選單(**審計畫、一次授權後續**)有:
- Approve and start in **auto** mode
- Approve and **accept edits**
- Approve and **review each edit manually**
- Keep planning with feedback(帶回饋繼續規劃)
- Refine with Ultraplan(瀏覽器端審閱)

關鍵語意:**核准計畫 = 離開 plan mode 並切換到該選項描述的 permission mode**,Claude 才開始改碼。`Ctrl+G` 可在核准前把計畫丟進文字編輯器直接改。

**Permission modes 授權分級(共 6 檔;決定「多久暫停問一次」)**:

| Mode | 不問就能做的事 | 語意 |
|---|---|---|
| `default`(CLI/IDE 標為 **Manual**) | 只讀 | 逐動作審批;最高監督 |
| `acceptEdits` | 讀 + 檔案編輯 + 常見檔案系統指令(mkdir/touch/mv/cp/rm/sed…限工作目錄內) | 你事後用 git diff 審 |
| `plan` | 只讀 | 探索/規劃、不動源碼 |
| `auto` | 幾乎全部,背景有 classifier 安全檢查 | 長任務、減少提示疲勞 |
| `dontAsk` | 只有預先核准的工具 | 鎖死的 CI/腳本(非互動) |
| `bypassPermissions` | 全部 | 只限隔離容器/VM |

官方一句話總綱:「When Claude wants to edit a file, run a shell command, or make a network request, it pauses and asks you to approve the action. Permission modes control how often that pause happens.」並強調「The mode is set through these controls, **not by asking Claude in chat**.」(授權檔位是使用者的控制項,不是叫 Claude 自己選)。

**auto mode(審每步、但由 classifier 代審)**:另一個 classifier 模型在每個動作執行前審查,只擋「escalates beyond your request / targets unrecognized infrastructure / hostile-content-driven」的動作;明確 ask rules 仍強制提示。並有「Boundaries you state in conversation」機制:使用者在對話裡講「don't push」「wait until I review before deploying」,classifier 會把它當**封鎖信號**,直到後續訊息解除;「Claude's own judgment that a condition was met does not lift it.」

- URL: https://code.claude.com/docs/en/permission-modes (查閱 2026-07-12)
- URL: https://code.claude.com/docs/en/best-practices#explore-first-then-plan-then-code (查閱 2026-07-12)

### Q3 進度可見性(todo / plan 顯示)

- **Plan Mode**:計畫以整份文件呈現、核准前可 `Ctrl+G` 進編輯器修改;核准的計畫還會**自動用計畫內容命名 session**。
- **狀態列**:目前 permission mode 顯示在 status bar(如 `⏵⏵ accept edits on`、`⏸ manual mode on`);官方建議用 custom status line 持續追蹤 context 用量。
- **`/goal` 條件**:可掛驗證條件,獨立 evaluator 每回合重檢,直到成立才停。
- Best-practices 反覆強調「Have Claude show **evidence** rather than asserting success」——用測試輸出、指令與回傳、截圖來讓「你沒盯著的 session」也可審。
- (Claude Code 也有 TodoWrite 類的內部待辦渲染,呈現給使用者當工作計畫;官方 SDK 文件把提問/審批/輸入串成 UI 事件。)

- URL: https://code.claude.com/docs/en/best-practices(Give Claude a way to verify its work;查閱 2026-07-12)
- URL: https://code.claude.com/docs/en/permission-modes(status bar 徽章;查閱 2026-07-12)

### Q4 中途打斷與轉向

官方 best-practices 有整節「Course-correct early and often」:「Correct Claude as soon as you notice it going off track. The best results come from tight feedback loops.」機制:
- **`Esc`**:中途停止,context 保留,可重新導向。
- **`Esc + Esc` 或 `/rewind`**:開啟 rewind 選單,還原「對話 / 程式碼 / 兩者」到先前 checkpoint,或從某訊息開始摘要。每則 prompt 都建立 checkpoint;Claude 每次改動前自動快照檔案。
- **`"Undo that"`**:叫 Claude 還原變更。
- **`/clear`**:不相關任務間重置 context。
官方經驗法則:「If you've corrected Claude more than twice on the same issue... `/clear` and start fresh with a more specific prompt.」

- URL: https://code.claude.com/docs/en/best-practices#course-correct-early-and-often (查閱 2026-07-12)

### Q5 模糊時的行為(先問 vs 先假設)

Claude Code 的官方姿態是**互動優先、但可調**:
- 預設/plan 模式鼓勵**先問清楚**(AskUserQuestion、plan mode「gather requirements before making changes」、best-practices 的「Let Claude interview you」)。
- **auto mode 明文反向**:「nudges Claude to keep working without stopping for clarifying questions」——自主時傾向少問、繼續做。想更強自主又保留提示,可用 Proactive output style。
- 換言之:Claude Code 官方沒有單一硬規則,而是**用 mode/output-style 把「問 vs 假設」做成可切換的旋鈕**;預設偏「有多路徑就問」。

- URL: https://code.claude.com/docs/en/permission-modes#eliminate-prompts-with-auto-mode (查閱 2026-07-12)

### Q6 收尾/回報

Best-practices 的核心規範是**證據優先**而非斷言成功:「Claude stops when the work looks done. Without a check it can run, 'looks done' is the only signal.」故要求給可跑的 check(測試/build/lint/截圖 diff),並「Have Claude show evidence rather than asserting success: the test output, the command it ran and what it returned, or a screenshot」。另建議收尾加 **adversarial review**:用 fresh-context subagent(或 `/code-review` skill)只看 diff 挑缺口,「Report gaps, not style preferences」,且提醒別追每個 finding(會過度工程)。

- URL: https://code.claude.com/docs/en/best-practices(Give Claude a way to verify its work / Add an adversarial review step;查閱 2026-07-12)

### Q7 常設指示(CLAUDE.md)

「CLAUDE.md is a special file that Claude reads **at the start of every conversation**. Include Bash commands, code style, and workflow rules. This gives Claude persistent context it can't infer from code alone.」`/init` 生成起手版。官方寫作建議:
- **極簡**:每行自問「Would removing this cause Claude to make mistakes? If not, cut it.」「Bloated CLAUDE.md files cause Claude to ignore your actual instructions!」
- 只放廣泛適用的(偶爾才用的知識/流程改放 skills,按需載入)。
- 可加 IMPORTANT / YOU MUST 強調以提升遵從度。
- 位置分層:`~/.claude/CLAUDE.md`(全域)、`./CLAUDE.md`(入 git 共享)、`./CLAUDE.local.md`(個人、gitignore)、父/子目錄(monorepo 按需)。
- 「Treat CLAUDE.md like code: review it when things go wrong, prune it regularly, and test changes by observing whether Claude's behavior actually shifts.」
- **與「把使用者偏好寫成檔案」相關**:官方明說 CLAUDE.md 是放「code style rules that differ from defaults / testing preferences / repository etiquette / developer environment quirks」的地方——即**把偏好固化成常設指示檔**,而非每次重講。

- URL: https://code.claude.com/docs/en/best-practices#write-an-effective-claude-md (查閱 2026-07-12)

---

## 產品二:Codex(OpenAI)

### Q1 向使用者提問的政策

**行為**:Codex 官方最佳實務主張——模糊/複雜任務時,**由使用者主動叫 Codex 先反問**再動工:「ask Codex to question you first」把模糊想法逼成具體需求。這跟 Claude 的「Let Claude interview you」同構,但 Codex 文件把它放在「複雜/模糊/難描述」的條件下。Codex 沒有像 Claude `AskUserQuestion` 那樣被大幅文件化的「結構化多選一提問工具」;互動提問主要走一般對話 + approval 提示。

> 官方引文:「If the task is complex, ambiguous, or hard to describe well, ask Codex to plan before it starts coding.」+「ask Codex to question you first」。

- URL: https://learn.chatgpt.com/guides/best-practices (原 developers.openai.com/codex/learn/best-practices,308 轉址;查閱 2026-07-12)

### Q2 計畫審批模式(approval policies + sandbox modes)

Codex 把授權拆成**兩個正交維度**:approval policy(何時問你)× sandbox mode(能碰什麼)。

**Approval policies(核准政策)**:

| Policy | 語意(官方) |
|---|---|
| `on-request`(版控資料夾預設) | 需要升權時才問:「editing outside the workspace, accessing the network, or running commands with side effects」。標準互動模式。 |
| `untrusted` | 只自動跑「known-safe read operations」;會變更狀態或觸發外部執行(如破壞性 Git)一律要核准。 |
| `never`(`--ask-for-approval never` / `-a never`) | 關掉所有核准提示,只在 sandbox 限制內運作,不打斷你。 |
| `granular` | `approval_policy = { granular = {...} }`,可分類選擇性核准:對 sandbox 升權、MCP 提示、skill-script 核准等,個別保留互動 or 自動拒絕。 |

**Sandbox modes(沙盒)**:
- `read-only`:只能讀檔案/回答問題;「requires approval to make edits, run commands, or access network」。
- `workspace-write`(Auto preset 預設):「read files, make edits, and run commands in the workspace automatically」;網路預設關,除非設定開啟。
- `danger-full-access`:「no sandbox; no approvals」,完整系統存取,高風險、不建議用於不受信任 repo。

**升權/詢問語意**:Codex 是**沙盒為界、越界才問**——在 `on-request` 下,只有「越出 workspace、要上網、有 side effect」的動作才升權詢問。另有 `approvals_reviewer = "auto_review"`:合格的核准請求可**路由給自動審查 agent**(評 data exfiltration / credential probing / destructive patterns)而非直接問人——概念上等同 Claude 的 auto-mode classifier。

**Plan Mode(對應機制)**:Codex 另有社群/官方推進中的 read-only 迭代式 Plan Mode(`Shift+Tab`,可設定 planner;見 openai/codex PR #4769),與 `update_plan` 工具(進度清單)是**分開的兩件事**;plan mode 是「只讀、迭代規劃」,`update_plan` 是執行中的 TODO 渲染。

- URL: https://learn.chatgpt.com/docs/agent-approvals-security (原 developers.openai.com/codex/agent-approvals-security;查閱 2026-07-12)
- URL: https://developers.openai.com/codex/config-reference (config 內 approval_policy/sandbox;查閱 2026-07-12)
- URL: https://github.com/openai/codex/pull/4769 (Plan Mode PR;查閱 2026-07-12)

### Q3 進度可見性(update_plan)

Codex 有 `update_plan` 工具:官方定位為 **TODO/checklist/progress** 工具,與 Plan Mode、與 `<proposed_plan>` 輸出三者分開。`PlanUpdate` 事件在 TUI 渲染成 **checkbox 清單**,狀態為 `pending / in_progress / completed`,可帶一句解釋。目前限制(官方 issue 揭露):core session 不把最新未完成 plan 當成「active execution state」,模型仍靠一般 transcript 記憶清單;且清單在助理回覆後、等待使用者輸入時不會持久渲染(#18920、#19749)。TUI 用字也在調整(把 "Updated Plan" 改成 task-list 標籤,#16765)。

- URL: https://github.com/openai/codex/issues/18920 (update_plan 三態清單、持久化;查閱 2026-07-12)
- URL: https://github.com/openai/codex/issues/16765 / #19749 (查閱 2026-07-12)

### Q4 中途打斷與轉向

Codex TUI 支援執行中送訊息插話:當模型還在輸出時按 Enter,會排入佇列並顯示「Messages to be submitted after next tool call (press esc to interrupt and send immediately)」——即**預設等下一個 tool call 邊界才插入;按 Esc 可立即打斷並馬上送出**。方向大改則官方建議用 `/fork` 分支工作,以刻意 checkpoint 轉向,而非硬中斷。

- URL: https://github.com/openai/codex/issues/15842 (TUI 插話/Esc 立即打斷語句;查閱 2026-07-12)
- URL: https://learn.chatgpt.com/guides/best-practices (`/fork` 轉向;查閱 2026-07-12)

### Q5 模糊時的行為(先問 vs 先假設)

Codex 官方姿態:**模糊就先規劃/先反問**——「If the task is complex, ambiguous, or hard to describe well, ask Codex to plan before it starts coding」以及「ask Codex to question you first」。強調把模糊需求在動工前轉成具體 spec。整體哲學把 Codex 當「a teammate you configure and improve over time」。相對 Claude,Codex 的提問較倚賴使用者主動觸發 + sandbox 越界升權,而非一個高度文件化的內建提問工具。

- URL: https://learn.chatgpt.com/guides/best-practices (查閱 2026-07-12)

### Q6 收尾/回報

官方最佳實務:「Don't stop at asking Codex to make a change」——要 Codex **確認結果符合請求**、並**提供 diff 給人類審**再接受。強調 review/validation 而非只交付變更。(與 Claude 的「evidence over assertion」同向,但 Claude 文件更細:測試輸出、adversarial subagent review。)

- URL: https://learn.chatgpt.com/guides/best-practices (查閱 2026-07-12)

### Q7 常設指示(AGENTS.md)

「Codex reads AGENTS.md files to apply persistent instructions before performing work.」官方定位:「By layering global guidance with project-specific overrides, you can start each task with consistent expectations, no matter which repository you open.」

**載入/優先序(三層,root→cwd 串接,越靠近 cwd 越後、覆蓋前者)**:
1. 全域:先找 `~/.codex/AGENTS.override.md`,否則 `~/.codex/AGENTS.md`(CODEX_HOME 可改)。
2. 專案:從 Git root 往下走到目前目錄,逐層找。
3. 合併:「Files closer to your current directory override earlier guidance because they appear later in the combined prompt.」串接時跳過空檔,累積到 `project_doc_max_bytes`(預設 32 KiB)為止。

**建議內容**:working agreements(測試協定、套件管理器偏好、相依核准流程)、repository expectations(lint/文件標準)、service-specific rules(專用測試指令、安全協定)。支援 `AGENTS.override.md` 做暫時全域覆蓋,及自訂 fallback 檔名(如 `TEAM_GUIDE.md`)。

- URL: https://learn.chatgpt.com/docs/agent-configuration/agents-md (原 developers.openai.com/codex/guides/agents-md;查閱 2026-07-12)

---

## 兩家對照表

| 維度 | Claude Code(Anthropic) | Codex(OpenAI) |
|---|---|---|
| 提問工具 | **`AskUserQuestion`**(內建、文件化):1–4 題、每題 2–4 選項、多選一、可加 "Other" 自填 | 無等價的高度文件化多選工具;靠一般對話 + 「叫 Codex 先反問」+ 越界升權 |
| 何時問 | 「多個有效路徑時」;auto mode 會壓低發問 | 「複雜/模糊/難描述時」由使用者觸發;sandbox 越界才升權詢問 |
| 計畫審批 | **Plan Mode**(審整份計畫),核准=切到指定 permission mode 才動手 | **Plan Mode(read-only 迭代)** + `update_plan` 進度;approval 走越界升權 |
| 授權分級 | 6 檔 permission modes:default/acceptEdits/plan/auto/dontAsk/bypassPermissions | 2 維正交:approval(on-request/untrusted/never/granular)× sandbox(read-only/workspace-write/danger-full-access) |
| 代審機制 | auto mode **classifier** 逐動作審 + 對話內 boundaries 當封鎖信號 | `auto_review` reviewer agent 審核准請求(exfiltration/destructive) |
| 進度顯示 | plan 文件 + status bar 徽章 + `/goal` 條件 + 證據優先 | `update_plan` 三態 checkbox 清單(pending/in_progress/completed) |
| 打斷/轉向 | `Esc` 停、`Esc Esc`/`/rewind` checkpoint 還原、`"Undo that"`、`/clear` | TUI 排隊插話 + `Esc` 立即打斷;`/fork` 分支轉向 |
| 模糊時 | 預設偏「先問」;auto mode 偏「繼續做」(可切) | 偏「先規劃/先反問」,由使用者觸發 |
| 收尾 | **證據優先**(測試輸出/指令回傳/截圖)+ adversarial subagent review | 確認符合請求 + 提供 diff 給人審 |
| 常設指示檔 | **CLAUDE.md**(每次對話開頭載入;極簡、可分層、可 import) | **AGENTS.md**(動工前載入;root→cwd 分層覆蓋、override 檔、32KiB 上限) |
| 互動哲學 | 互動式為主、可調成自主;「問 vs 假設」做成 mode/output-style 旋鈕 | 沙盒界定自主邊界、越界才互動;偏批次自主 + 事後審 diff |

---

## 對「AI 訪談對話層」的可抄清單

1. **結構化提問工具**(抄 Claude `AskUserQuestion`):把提問限制成 1–4 題、每題 2–4 選項的**多選一**,並永遠附一個 "Other"(自由文字)。多選一降低使用者負擔、也讓答案好結構化——訪談系統尤其適用。
2. **提問門檻明文化**:官方口徑是「**有多個有效路徑 / 任務模糊複雜時才問**」,不是每步都問。訪談系統應設「只在分歧點提問」的門檻,避免疲勞。
3. **「先訪談成 spec、再乾淨開新 session 執行」**(Claude 的 interview→SPEC.md 工作法):把訪談產物固化成一份自足文件,再進下一階段——直接對應訪談系統的「訪談→產出文件」骨架。
4. **審計畫 vs 審每步兩檔**:Plan Mode(審整份計畫一次過)與逐步審批要分清;核准一份計畫應等於**切換到更自主的執行檔位**,而非每步再問。
5. **授權分級當旋鈕**:提供「逐步審 / 自動接受 / 全自主(背景 classifier)」多檔,讓使用者按信任度選;不要只有全開或全關。
6. **對話內邊界即約束**(抄 auto mode 的 boundaries):使用者說「先別 X」要當硬封鎖信號,且**agent 自認條件達成不得自行解除**——訪談系統處理使用者中途設限時的關鍵語意。
7. **進度三態清單**(抄 `update_plan`):pending/in_progress/completed 的 checkbox,讓使用者隨時知道訪談做到哪一題/哪一段。
8. **廉價打斷 + checkpoint 還原**:一鍵停(Esc)、排隊插話、rewind 到任一 checkpoint;訪談長流程尤其需要「回到上一題/改前面答案」。
9. **收尾證據優先、非斷言**:結束時交「做了什麼 + 佐證」而非「完成了」。訪談系統收尾應回放/摘要使用者的關鍵回答供確認。
10. **偏好固化成常設檔**(CLAUDE.md / AGENTS.md):反覆出現的使用者偏好寫進一個每次載入的檔、極簡、可分層覆蓋;訪談系統可把受訪者/情境的常設設定外置成類似檔案。
11. **模糊處理的官方分歧**:Claude 預設「先問」但用 mode 可切成「先假設繼續」;Codex 偏「先規劃/先反問」。訪談系統宜**預設先問、且把行為做成可切換**,而非寫死。

---

### 附:未能一手確認/需注意處
- Codex 部分互動細節(TUI 插話字句、update_plan 三態、Plan Mode PR)來自 **openai/codex 官方 GitHub repo 的 issues/PR**(屬官方 repo,但為工程討論非正式 docs);已標註 issue/PR 編號。approval/sandbox 與 AGENTS.md 為官方 docs(developers.openai.com,308 轉址到 learn.chatgpt.com 官方學習域)。
- Codex 沒有找到與 Claude `AskUserQuestion` 對等的、被正式文件化的「結構化提問工具」;若後續版本新增,需重查。
