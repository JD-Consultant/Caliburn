# 使用者提供的 LLM 工具研究：本案核對與採用

查閱：2026-09-13。基準實作 `36cc1cb9`，另有本輪聊天准入／原回合查回施工。這份記錄補充研究依據，不另設產品決策權威。

## 閱讀範圍

已在瀏覽器讀完使用者提供的 [ChatGPT「LLM Tool設計研究」分享正文](https://chatgpt.com/s/t_6aa6186f80f08191b566955f57c5ef19)，共十五節。頁面聲稱另有二十二章報告、三十三來源及五十八項離線檢查，但本輪沒有取得該完整附件或重跑其測試；不能將作者陳述當成我們的驗證結果。分享內容是二手分析，非 OpenAI 或 Anthropic 官方立場。

## 核對後的判斷

| 分享主張 | 官方依據與適用界線 | 本案處理 |
|---|---|---|
| 工具須按任務設計，不能逐個照搬 HTTP API；用途、輸入、結果與失敗共同構成契約 | [OpenAI 工具規劃](https://developers.openai.com/plugins/plan/tools)是 ChatGPT／Codex plugin MCP 規劃指南，明定 coherent action 與風險／權限分界；[Anthropic 工程文章](https://www.anthropic.com/engineering/writing-tools-for-agents)強調為 Agent 設計與實測。兩者支持原則，沒有指定本案工具數量／資料表。 | 保留兩個讀工具與八個具名編輯工具；整項任務建立／相依工作更正已合併必要步驟，共用 domain／SQL。HTTP route 不直接成為模型工具。後續以自然訪談檢查選擇歧義，不先因作者例子拆掉共同規則。 |
| 已知資訊交程式，不要求模型猜 | [OpenAI function calling](https://developers.openai.com/api/docs/guides/function-calling#best-practices-for-defining-functions)明確要求卸除已知參數；Anthropic 工具文件要求解釋參數及回傳足夠識別資訊。 | dataset／document 範圍、run、操作識別與保存版次來自 App。此次新增的 `expected_jd_revision_ref` 是 Browser → App 的送出條件，內部 canonical start revision 納原請求核對；不新增為 LLM 必填參數。 |
| Description 說清用途、前提、結果；Skill 放工作方法 | [Anthropic define tools](https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools)要求明確說明何時用、限制與參數；OpenAI function calling 區分函式描述與跨工具 system 指引。 | 工具說明維持能力契約；完整工作分析／何時寫 JD／未知與案例界線沿顧問指引。先不機械套用六段描述模板或所有工具加入同一長文。source／Memory 接合時，須同時驗證來源工具是否實際可用。 |
| strict 與 SDK 型別不等於業務驗證；兩家 Schema 不完全相同 | 本輪直接讀 [OpenAI strict](https://developers.openai.com/api/docs/guides/function-calling#strict-mode)與 [Anthropic strict](https://platform.claude.com/docs/en/agents-and-tools/tool-use/strict-tool-use)。前者要求所有 property required，optional 用 nullable；後者現行範例有非 required property。這是各自 API 契約，不以作者跨家範例取代實際 adapter。 | 保留模型輸入 SSOT／生成型別、後端完整驗證與實际 SDK request 捕捉。新 run V1／V2 的 bool／float 版本值反例也須通過；不能因 Pydantic union 接受就視為合法 integer 版本。 |
| 成功要說明實際完成範圍，timeout 不表示未寫入 | OpenAI call_id／Anthropic tool_use_id 配對是模型協定；[AWS 安全重試](https://aws.amazon.com/builders-library/making-retries-safe-with-idempotent-APIs/)是原操作識別與副作用一致性的工程依據。AWS 不取代 LLM 資料來源。 | 現有業務結果已區分 committed／unchanged／unknown、原操作與下一步。聊天將另外區分原話已存、AI 回合狀態及 JD 已發生修改；AI failed 可與 JD committed 並存。此輪原結果先查回，新版次檢查只約束新准入。 |
| 小工具集合未必需要工具搜尋、PTC、通用程式工作區 | 分享本身也將這些列為有條件選項，不能由「官方提供」推成全業界已採用。 | 目前十個 JD 工具沒有新增這些能力的已觀察需求；不新增執行 sandbox／tool broker／另一份 Memory。若工具數量、延遲或成本實測出現具體問題，再核對當時 provider 與 framework 支援。 |

上表官方網頁均為 2026-09-13 查閱的現行公開文件；OpenAI／Anthropic API／plugin 文件為商業服務契約參照，不是本案新增套件。Anthropic 工程文章发表于 2025-09-11，仍被現行工具指南引用，作方法依據使用，不宣稱其模型／SDK 範例等於本案 lock。AWS 為現行 Builders’ Library 方法文。此次不新增依賴、不變更授權或產品模型設定。

## 不直接採用的情境假設

1. **Memory 先提案再審核**是分享作者給另一情境的建議，不是兩家共同要求。本案 AI 直接改 JD、使用者看確切差異、可更正／撤回 JD 的方向不因此改成逐筆接受；原始對話與 Memory 也不隨 JD 撤回。
2. **revision 一律讓模型填**不是共同原則。本案已由真正讀稿結果建立操作基準，不再讓模型重打一個可由 App 確知的版本號；目標與來源仍須從已讀結果選取。
3. **固定五層／六問／retry_mode 名称**是作者整理。本案保留已有等價責任與結果分支，不為名詞一致改介面。
4. **MCP 最新版、PTC、async tool calling 的完整可用性**不屬這次已採接點。沒有逐一驗證分享中每項版本宣稱，也沒有因此安裝或切換 SDK。日後真正需要才按目標 provider、模型、host 與鎖定版本驗證。

## 真正仍要驗的差距

- **模型可用性與成本：**本案目前使用 App 發配的 signed refs，而 Anthropic 文件偏好容易理解的穩定識別。簽章是本案範圍／資料集／用途校驗選擇，不是兩家指定格式；須在已排自然模型驗收觀察長 ref 的 token 負擔、複製錯誤和目標選擇，不能用離線 Schema 全綠宣稱模型好用。可讀名稱／文字仍伴隨識別，不讓 ref 代替語意。
- **自然操作評估：**固定 SDK、真 DB 與新程序證據只證明接合與恢復；尚須未指示工具順序的真訪談，驗該寫才寫、責任忠實度、工具誤選、來源支持及對錯誤結果的理解。付費範圍另按原計畫確認。
- **聊天准入／原 run 查回：**本輪正在實作；歷史分支不可只憑相同文字或 metadata 選取，沿已實測的 native parent 關係。有斷鏈或查找超界時保留未解狀態，不能宣稱原請求不存在並重新執行。

施工與驗收繼續沿 [RS 計畫](../../../plans/2026-09-13-jd-relational-app-implementation.md)，原格式與產品決策不因二手參考自動改寫。已知接點實作見 [transport](../../../../experiments/jd-relational-app/src/jd_relational/transport.py)、[consultant tools](../../../../experiments/jd-relational-app/src/jd_relational/consultant_tools.py)及 [AI runtime](../../../../experiments/jd-relational-app/src/jd_relational/ai_runtime.py)。
