# 0030. AI 層 v3:追蹤修訂直寫載體+一條腦+品質迴路

日期:2026-07-13
狀態:Accepted(部分修正 0025 的批審載體與 0028 的彈窗/徽章載體;0023/0024/0026/0027 骨幹不變)

## 脈絡

0029 §11 把 AI 共編載體延後另裁。現況:三條 AI 路徑並存(訪談引擎/隨叫 `/ai/*`/舊
LangGraph+CopilotKit,0023 裁退未清);AI 寫入走彈窗建議層(CurationDialog),產業已收斂到
「直寫+修訂標記」(Word Copilot 2025 被迫補上、Canvas/Gemini/Cursor 同構);evals 整套缺席。
六輪研究(16 份原始報告,見 [`../specs/2026-07-12-ai-layer-redesign-research.md`](../specs/2026-07-12-ai-layer-redesign-research.md))
+逐層討論收斂出本決定;工作紀律新增「設計裁決先找大廠先例,不自己試錯」。

## 決定

1. **一條腦**:訪談引擎=唯一 AI 腦;**scribe=唯一寫入口**(寫入單執行緒);`/ai/*` 隨叫服務
   降格 read-only 純函數(產出只進 UI 供人挑);舊 LangGraph(`app/authoring`)+CopilotKit
   (web 全家)退役。不上 agent 框架、不引 MCP runtime、無多 agent(讀可扇出寫不可)。
2. **載體=追蹤修訂直寫(甲案內嵌)**:文件節點加選填 `_pending`(op/舊值/出處;ocs-contract
   選填欄位,契約 #1 流程);四態=已確認/待審-新增/待審-修改/待審-刪除;條目級綠紅標
   (綠=增改、紅刪除線;修改舊值收副行);hover ✓/✗/?(?=出處卡:官方來源行+訪談原話);
   批量接受/拒絕常駐;筆級淡入(過 verify 才現身);匯出自動剝未審。**✓/✗=無聲 UI 事件**
   (不觸發 AI;記帳後下回合利用);人改綠字=視同接受且**不告知模型**(改寫只記 trace);
   拒絕進帳本(不重提、可追問);AI 可對**任何已確認內容**(不分作者)發提議,唯一禁令=
   無聲改動;AI 可自由修改/收回自己的綠字。
3. **verify 關(= output guardrail,blocking)**:scribe 唯一出口,六查全純程式——契約合法
   (enum 正規化)/引用存在性(quote 逐字比對,查無整筆拒收)/來源一致(ref∈參考集合、
   custom 必附 quote,兩者可並存至少一)/寫入權限/結構不變量/尺寸衛生。失敗=可行動錯誤
   →retry×2 回灌具體條目→丟棄記 trace,不打擾使用者。全欄位(D/T/O/P/K/S/A/L/三分類/
   自由文欄)一律走綠紅標;控制欄值∈官方枚舉;**表頭主基準 AI 可綠標提議**(值∈參考集合,
   接受後才觸發 rematch);位置碼誰寫都拒收。人類寫入只過契約驗證。
4. **對話層**:六 prompt 規則(一 turn 一題/短 turn 問完閉嘴/開放開場封閉定錨/訊號觸發追問
   +laddering 2–3 層+反 under-probe 清單/離題三步/覆述三時機+綠字即覆述);議程狀態機四態
   (covered/refused/held/**boundary**=受訪者劃線 AI 不得自行解除);疲勞偵測(確定性);
   收尾=coverage/疲勞/預算三選一+**結構化總結對帳**(併態度收尾 pass);開場議程預覽
   (Plan Mode 訪談版)+透明揭露+進度三態清單;chips=選項+推薦+Other。
5. **品質迴路**:few-shot 黃金範本 3–5 份(**與考題分池防洩題**)+skill 檔八份(SKILL.md
   格式、按欄位確定性載入、內容以 iCAP 官方欄位標準+國際框架規範為原料、改 skill=CI 跑
   回歸)+雙指標(Source Score 程式算/Answer Score rubric 裁判)+雙 suite(capability/
   regression)+畢業制+promptfoo 進 CI+pass^k 發版;裁判 Phase 2 上(rubric 二元+負分、
   pointwise-against-reference、跨模型家族、temp=0、校準集 100+ 看 TPR/TNR+κ、held-out、
   全繁中、模擬受訪者注入不合作人格);冷啟動=SME 手造 1–3 題+真實使用飛輪。
6. **工程橫切**:tracing 搬出 authoring 成 api 橫切層(`gen_ai.*` 命名、預設開、記 verify
   拒收/審閱事件/fallback);context 快取分層(穩定前綴在前)+近 10 輪全文舊摘要(DB 永存
   全文);模型分工(consultant 強推理/scribe 便宜 strict/judge 另一家/backstop 便宜);
   OpenRouter 顯式 fallback(備援模型必過 eval)+parallel tools+streaming(側欄字元級、
   表格筆級)。命名保留(consultant/scribe/verify/ledger/backstop),文檔標業界對映。

## 後果

- ✅ 與 2025–2026 產業共編終局同構(直寫+標記+accept/reject);審批不擋流程,防 93%
  無腦點准的 approval fatigue;每筆內容可溯源(Harvey 式拒收幻覺引用)。
- ✅ 單一寫入口+確定性守門+狀態外置,健檢與主流管線同構;品質可被考卷量化並防退步。
- ⚠️ ocs-contract 擴欄、大改 InterviewPanel 與寫入通道;舊件退場需照「新載體先上舊件後拆」
  排序;evals 冷啟動仰賴 SME 手造金鑰。
- ⚠️ 縫(觸發條件見研究紀錄):AI 主動度旋鈕、對話 rewind、雙帳本拆分、input guardrail、
  類別級抑制、分區批量、Caliburn-as-MCP-server、fine-tune/蒸餾、檢索升級包(獨立 plan:
  eval 集→metadata filter→中文分詞→reranker→Qwen3 評測)、trace per-tenant 隔離。

細節與全部出處:[`../specs/2026-07-12-ai-layer-redesign-research.md`](../specs/2026-07-12-ai-layer-redesign-research.md) §6(已鎖決策清單)。
