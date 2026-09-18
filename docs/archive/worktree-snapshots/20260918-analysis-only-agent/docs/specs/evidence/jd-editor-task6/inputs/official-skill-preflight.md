# JD 專業方法接線：現行官方做法補核

2026-09-11，JD-R002/C03；依 Owner 繼續施工及主動研究要求，補核 Task6 的方法載入邊界。**這是既定設計的前置證據，沒有執行 Task6、變更模型／依賴／production authority。** Task5 窄複核因執行者額度中斷，仍未完成；不以本研究代替審查。

## 查閱範圍與共同原則

| 官方資料／查閱日期 | 可確認內容 | 適用範圍、狀態與授權界線 |
|---|---|---|
| [OpenAI：Build skills](https://learn.chatgpt.com/docs/build-skills)，2026-09-11，已搜尋後取得正文 | ChatGPT／Codex 先載名稱與描述，需要時才讀完整 SKILL.md；清楚描述用途與觸發條件。可只有指引，不必有程式。 | 現行滾動產品文件，頁面未標整體 Skills 為 preview；未聲稱各端所有功能同版。Codex 初始清單有自身截短規則，**不照搬成我們的預算**。此處研究行為，不採用其商業服務或複製完整 Skill。 |
| [Anthropic：Agent Skills](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/overview)，2026-09-11，已讀正文 | metadata→需要的指引→按需補充材料，分層讀取。Claude API 的託管 Skills 與 Claude Code 本機 Skills 有不同執行／配置條件。 | 現行滾動文件。API 路線需要 code execution；這是該服務契約，**不構成本案需要 VM／bash／額外付費執行器的依據**。不採用商業容器或文件 Skill。 |
| [Anthropic：Skill authoring](https://platform.claude.com/docs/en/agents-and-tools/agent-skills/best-practices)，2026-09-11，已讀相關正文 | 保持精簡；易錯且需一致的操作應更精確，需理解情境的工作保留判斷空間；方法效力要在實際採用模型驗證。 | 是寫法建議，不是專業 JD 品質保證。固定工具測試不能代替自然訪談驗收。 |
| [LangChain：Deep Agents Skills](https://docs.langchain.com/oss/python/deepagents/skills)，2026-09-11，已讀相關正文 | SkillsMiddleware 提供發現與按需讀取接點；引用檔可另讀。Backend 的能力／權限才是讀寫邊界。 | 網站為滾動文件，實作以本機 exact 0.7.13 為準。既有套件 MIT；其 package metadata 的 Development Status 為 **4 - Beta**，不可描述成已查明穩定級。沒有因此升級或新增套件。 |

**跨來源共同原則：**以用途明確的方法資產保留專業程序，先發現、再按需取得內容。沒有證據支持每輪重載全部方法、每輪改稿或把方法檔當員工事實。

**本案選擇：**沿已同意的一份 JD Skill＋兩份參考材料、同一顧問及原三工具。檔案數、觸發時機、JD 六章、共享 K/S、JSONB 與資料表名稱不是以上來源指定的統一實作。OpenAI／Anthropic 未公開的 JD App 內部保存結構仍未知。

## 核對實際已安裝版本，避免直接抄滾動範例

- `experiments/analysis-agent/pyproject.toml`／`uv.lock` 固定 `deepagents==0.7.13`；本機 dist-info/METADATA 實際版本 0.7.13、MIT、Beta 分類均已核對。未安裝／執行新 middleware。
- 已讀安裝檔 `deepagents/middleware/skills.py`：`before_agent` 約 L933–953，state 已含 skills_metadata 時會略過 metadata 載入；`modify_request` 約 L905–931 從 state 組成最終 system 附加內容。**新檔存在不等於舊中斷 checkpoint 已看到新方法**。
- 本案既有 `skills.py` 以唯讀 SkillAssets＋CompositeBackend 掛載 `/skills/`；無寫入／執行／網路能力。可沿同一讀取工具，不從官方 VM 範例推導新增主機執行權。
- 官方頁面說的 Memory（例如 AGENTS.md）與本案已驗訪談 Memory 的語意及 owner 不相同；不因同名而改成本案的背景 Memory、Store 或 checkpoint 新路線。

## 下一施工單位的精確變更與反例

沿[核心 Task6](../plans/2026-09-10-jd-editor-core-implementation.md)與既有 `task-6-method-preflight.md`／13 原始資料 hash，不新增方法事實或重開格式。

| 位置 | 必要修改／待驗效果 |
|---|---|
| `A/src/analysis_agent/skills/write-customized-jd/` | 只有 SKILL.md、references/complete-work-guide.md、references/writing-and-correction.md；將既有三指南轉成可讀方法，無資料庫欄位／schema 重抄／測試答案。 |
| `A/src/analysis_agent/api.py` | 除去「目前只做訪談分析，不製作或編輯JD」的否定句，保留周圍已驗的訪談／未知／條件／Memory 原則；以工具實際結果說明保存。 |
| `A/src/analysis_agent/skills.py` | 澄清方法資產本身不授權寫入；已提供的 JD 操作仍依原三工具契約。不得變每輪強制 read/edit。 |
| `A/tests/test_jd_skill_contract.py` | 沿既有 `test_analysis_skills.py` 真 create_agent／SDK MockTransport 接點：初始最終 request 有 metadata 但無正文，read_file 後才有正文／reference ToolMessage；三 JD schema 原樣、舊三方法仍可讀、路徑越界有界錯誤、沒有新增 mutator。 |
| 固定端到端及 browser | 原 Task6 六段順序：不足只問→足夠寫稿→有範圍更正→手改通知與續編→commit 回覆遺失／取消→真程序重開比全值。固定 provider 不證明模型自然學會訪談；使用真 Task5 bootstrap，不能另開縮水 API。 |

`A` 指 `experiments/analysis-agent/`。首個新反例應觀測**實際送給模型的 request**缺少新方法，以及現行能力宣告仍否定 JD；避免只測檔案有字串。先測 fresh invocation，再依已存 checkpoint 的實際狀態核對，不新增 hot-reload 或每輪清 metadata。

## 證據退出條件

本題的共同原則與現有 framework seam 已可確認，停止廣搜；下一證據必須來自 Task6 固定實作及後續有授權的自然模型驗收。這次 0 個產品模型／0 個付費呼叫，沒有讀真 key、試用員工或更改 production。

仍未完成：Task5 獨立 closure、Task6 實作／端到端、P3 自然模型及費用防護、P4 正式 authority gate、P5 日常啟停與備份還原、P6 真人驗收。不得將研究完成稱成品完成。
