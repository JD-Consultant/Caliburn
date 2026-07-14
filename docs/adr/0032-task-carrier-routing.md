# 0032. 任務載體路由:證據→綠字直落、盤=人拉(intake/自取)、不確定→卡片

日期:2026-07-14
狀態:**Accepted**

## Context

T12 後任務 widget(`picker:"task"` 帶 precheck)是前端黑洞:引擎發、web 不消費,
`interview:curation` 端點與 `lib/curation.ts` 疊加層也從未接線。研究紀錄
[2026-07-13 §7](../specs/2026-07-13-occupation-consent-write-research.md) 曾裁
「任務=盤(AI consent-triggered 彈窗)帶預勾+引文」(b 案)。維護者隨即質疑:
AI 已確定的任務為何不直接加(彈窗=重工)?盤的真價值是不是員工**自報**
(「第一次訪談讓 AI 知道他大概做什麼」),而非 AI 的審查介面?

重研先例(詳 [2026-07-14 研究紀錄](../specs/2026-07-14-task-carrier-routing-research.md)):
Copilot ghost text=高把握單筆 inline 直寫、備選面板人拉;PAIR=信任高/風險低→多自動化;
TurboTax=開場自我分段勾選、訪談只深問勾過的(+11% 續用);recsys 冷啟動=onboarding
粗勾建 profile、low-burden 必須可跳過。且本系統有**確定性信心判準**:verify ② 逐字
quote——不需 LLM 自報信心。

## Decision

1. **有逐字證據的官方任務→綠字直落**:裁剪(curation)quote-backed 結果由**確定性碼**
   映射成 add-task op(ref=池 URN+quote src)→ 既有 verify 六查 → `_pending`;
   人在表格 ✓/✗。家職責不在文件時確定性建**官方殼**(name/src 限池內官方,同標
   `_pending` add;✗=巢狀還原)。寫入唯一路徑不變量(0030)不破。
2. **盤(全域任務窗)永遠人開,AI 只遞邀請**:①開場 intake 邀請卡——觸發=確定性
   三布林(參考集合非空∧文件無任務∧無 dismissed 事件),widget 單槽職類卡優先,
   兩出口(開盤/「用聊的就好」=`task_board_dismissed` 記帳→知情換話術不重推);
   ②收尾補漏 offer;③隨時工具列自取。**AI 程式化彈窗路徑全數退役**。
3. **盤=乾淨自取,無 AI 預勾疊加層**:AI 確定的不等人來找(走 1)、不確定的不預勾
   (誤導)、人自報不需要 AI 意見。`interview:curation` 端點、web `lib/curation.ts`
   疊加層、run_turn `picker:"task"` widget 一併退役。
4. **AI 不確定(無 quote)且候選 ≤3 → 聊天卡片點頭**(職類卡同款模式);候選多或
   人想瀏覽→交盤(人拉)。盤上人工勾選=confirmed 直落不套綠字(0028 D9 維持)。

## Consequences

- ✅ 新手零手勢入任務(intake 2 分鐘=訪談枚舉十幾回合);訪談瘦身只做挖深與自訂
  任務;token 成本降(勾選=0 token);黑洞收屍。
- ⚠️ verify/land 需新增「官方任務落地+官方殼」能力(容器擴限官方 provenance,
  非自由新增職責——fail-closed 原則保持);intake 卡新前端元件。
- 修正 [0028](0028-interview-flow-shared-ui-curation.md) D1「AI 驅動 pickers」任務段
  (AI 不再開任何 picker);廢止 spec 2026-07-13 §7 裁決①③的 AI 彈盤+預勾段
  (②confirmed 直落與 focal-ask 單槽維持)。[0030](0030-ai-coedit-tracked-changes-one-brain.md)
  寫入路徑與 [0031](0031-occupation-suggest-card-refset-source.md) 參考集合不變量**不動**。
- 實作:[plan 2026-07-13 T5(v2)](../plans/2026-07-13-occupation-card-blindspot.md);
  載體判準表落 [`docs/design/interview-engine.md`](../design/interview-engine.md)。

## 否決的替代方案

- **b 案(AI consent-triggered 彈盤帶預勾)**:對 AI 已確定項=重工(Copilot 反例:
  高把握不開面板);打斷心流(HAX);疊加層複雜度養黑洞。
- **全綠字、無盤**:喪失「員工自報」這條 0 token 最便宜通道與收尾補漏 checklist 價值。
- **LLM 判 intake 時機/寫參考集合**:時機三布林可確定性判,交 LLM 引入不確定性;
  參考集合維持人選(0031 已裁,不動)。
