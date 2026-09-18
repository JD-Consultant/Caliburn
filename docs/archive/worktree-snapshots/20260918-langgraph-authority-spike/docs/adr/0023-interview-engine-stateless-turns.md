# ADR 0023 — 訪談引擎骨幹:無狀態回合服務 + 軟階段 + 指令詞彙表

- **狀態**:Accepted(2026-07-05)。
- **研究依據**:[`../specs/2026-07-05-llm-integration-wiring-research.md`](../specs/2026-07-05-llm-integration-wiring-research.md)
  (輪 1–10;判別場景、五路權威收斂、需求訪談、指令詞彙表)+ 上游
  [`../specs/2026-07-02-llm-interview-authoring-research.md`](../specs/2026-07-02-llm-interview-authoring-research.md)。
- **關聯**:互動模式=ADR 0020(不變);並發地基=ADR 0015;**接受後部分翻案 ADR 0007**
  (LangGraph 留用部分——見決定 6;0007 的 12-factor 原則保留且被本 ADR 強化)。

## 脈絡

終局:LLM 扮演資深職務說明書顧問訪談員工,邊談邊把文件「建好、修正好、優化好」;
人隨時可直接改文件(0020 混合主導權)。既有 LangGraph 訪談圖產舊 doc shape、無前端驅動、
與編輯器成兩條寫入路;維護者明示不受既有資產約束、重新選型。

研究判別場景(輪 3):訪談中員工直接在工作台改文件 → 有狀態圖的 checkpointer 私有狀態
過期成雙真相;無狀態回合每回合現讀文件,人的編輯自動生效。五路權威(Rasa CALM/Azure
架構中心/Anthropic/Harvey/TOD 文獻)獨立收斂:LLM 管理解與措辭,確定性碼管狀態/流程/
業務規則,狀態顯式存外面。維護者需求(輪 7):寫入節奏靈活(問到一定程度先寫、中途
發現漏職責回頭補),非固定回合。

## 決定

1. **引擎 = 無狀態回合服務**(api 內普通 REST,非圖 resume):每回合
   讀(文件 + DB 進度列)→ 算(顯式 Python)→ 寫(走編輯器同一條文件 seam)。
   狀態 = 進度列(階段/焦點/槽位/追問計數)+ **文件本身 = 唯一真相**;
   禁止引擎私有長壽命狀態(12-factor Factor 12)。
2. **軟階段**:宏觀六面向(定位→盤點→深掘→彙整→審閱→重要度;勞動部指引)只當
   **進度顯示與覆蓋率分組**;微觀導航 = LLM 每回合從**枚舉指令詞彙表**選(CALM Command
   模式):`set_slot / correct_slot / add_duty / add_task / ask / ask_choice / skip /
   advance / draft_section / revise_section / clarify / smalltalk`。
   靈活在指令選擇,安全在指令枚舉 + 確定性 guard。
3. **溯源內建於指令**:填槽類指令 `quote` 必填,程式驗證 = 逐字稿正規化後精確子串
   (Deterministic Quoting 先例);驗證失敗 retry 一次,再失敗 → 槽值收下、quote 標
   「未驗證」降信任級,不阻塞訪談。
4. **停止三重保險**(確定性,LLM 不能繞過):硬上限(每槽追問 ≤2 等)+ 覆蓋率門檻
   (core 任務 12 槽/淺掃 4 槽;`advance` 未達門檻 → 拒絕並回缺口)+ LLM 飽和信號。
5. **深問預算**:先便宜問完每任務「頻率+比重」,以 O*NET core/supplemental 判準分配
   全套深問(黃金範本 v0:[`../specs/2026-07-05-golden-sample-software-tester.md`](../specs/2026-07-05-golden-sample-software-tester.md))。
6. **全新實作,不整合舊碼**(維護者 2026-07-05 定調):新引擎按本 ADR 重新設計實作,
   **不承諾搬移既有 graph 任何程式碼**;既有圖(含 STAR/5W2H 槽定義、prompts、指標品質分)
   僅為**參考材料**,設計時可借鑑其領域知識、不受其形狀約束。退役時機照 Strangler Fig:
   舊圖/AG-UI/checkpointer/web CopilotKit provider 與 3 個 python 依賴,**在新引擎可用後
   一次清除**,期間互不干擾(舊圖本就無前端驅動)。

## 後果

- ✅ 人中途改文件自動被尊重(單一真相);兩條寫入路收斂成一條(縫 2 消失);
  每回合純函式可 fake 測;斷點續談免費(狀態靜置 DB);與 0015 樂觀鎖直插;
  全新實作不背舊 shape 債。
- ⚠️ 需新建:進度列 schema、指令執行器、覆蓋率門檻表;指令**語義**正確率要靠評測
  (模擬受訪者綁 persona 卡當回歸網 + 上線前真人試訪),結構正確率由受限解碼保證(0024)。
- ⚠️ 槽位表/門檻數字以黃金範本 v0 起算,實作驗證中修(維護者暫定通過)。
- 📌 詳細槽位表、指令參數 schema、UI 細節在立項 spec 定,本 ADR 只凍結骨幹形狀。
