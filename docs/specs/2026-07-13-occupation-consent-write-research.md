---
title: 訪談引擎看不見參考集合+新手口頭同意無法落地——研究與修法
date: 2026-07-13
purpose: 真人手測(新手 persona,session 6f807f1e)卡死在選職類;決定 AI 可否代辦
source_discipline: 一手證據=DB 逐字稿/稽核表;先例=Anthropic trustworthy-agents 框架、
                   agentic-UX 業界共識、本 repo ADR 0028 驗屍 + 0029/0030 決策
---

# 選職類卡死:診斷與「口頭同意=同意」修法研究

## 1. 事故(2026-07-13,session 6f807f1e,新手 persona 手測)

**現象**:22 回合,顧問三度提議職類(越搜越歪到行動遊戲程式設計師),員工口頭明確同意
(「這兩個我絕對都要加選進去!」),**文件零產出**(書記 guard 全空、document_versions 0 列)。

**因果鏈(兩段疊加)**:
1. **0029 脫鉤 × 0030 盲區**:0029 把〔選職能基準參考〕改成只寫 `job_profiles.
   selected_ocs_codes`、不動文件;而訪談引擎(0030,建於 0029 前)的
   `has_occupation`/`build_task_pool`/`build_pool_inputs` **只讀文件** →
   profile 上有 3 個碼,引擎全程視而不見,帳本永遠停在 `onboarding:occupation`。
2. **口頭同意無落地路**:0028 D1 設計=AI 開 picker、人點擊;新手 persona 不會去點
   UI,口頭同意在系統裡等於零。這正是 0028 驗屍(session eb2af457)死區的新形態重演。

**連鎖**:文件空 → 書記 schema 除 `none` 零變體 → 員工講的所有素材結構上無處可記。

## 2. 先例(外部權威)

- **Anthropic trustworthy-agents 框架**:可逆動作(讀檔/搜尋/**可一鍵撤銷的應用內狀態**)
  不需阻斷式核可;不可逆(寄信/付款/刪除)才要。且實測 **93% 核可率=確認疲勞**,
  阻斷式確認不是真安全網——安全要靠系統性防護(我們=verify+可撤+審計),不是靠人點。
- **Agentic UX 業界共識(2025-26,NN/g/Microsoft/Google 系整理)**:
  「先設計 undo 再設計 action」;撤銷要**一鍵、與授權同一表面**;Intent Preview →
  執行 → 審計軌跡+可撤,勝過每步彈窗。
- **同類產品**:Claude Code/Cursor(agent 直接改檔+diff 事後審=追蹤修訂)、
  Notion AI(直接改庫+undo)、ChatGPT canvas(直接落+版本史)——共同點:
  **應用內可逆變更=先做+可撤,不擋在 UI 手勢後面**。
- **本 repo 自家哲學(ADR 0030)**:「AI 大膽寫、人事後審」(`_pending` 追蹤修訂)。
  參考集合是**比文件內容更輕**的可逆狀態(選單資料源,一鍵可增刪),卻反而卡最死的
  人工手勢——與自家哲學矛盾。

## 3. 選項

| 選項 | 內容 | 評 |
|---|---|---|
| O1 **口頭同意→引擎代寫參考集合**(+可撤) | 員工肯定回應後,引擎把**本 session 搜尋命中過的碼**寫進 `selected_ocs_codes`;聊天回條+審計;picker 隨時可增刪(=undo) | ✅ 推薦:對齊 Anthropic 可逆判準+0030 哲學;新手零手勢 |
| O2 維持 D1(picker+人點)+UI 強化 | 自動開盤、預勾、一鍵確認 | 仍有手勢斷點;0029 後連點了引擎也看不見(仍需修盲區) |
| O3 參考集合也走 `_pending` | 在文件上做參考集合的待審標 | ❌ 過度設計:參考集合不在文件上,為它發明新 pending 載體=大改契約 |

**裁決:O1 + 盲區修復**(兩者都要;O2 的 UI 強化不衝突、可後補)。

## 4. 設計(O1;零幻覺紀律與書記同款)

**寫入守衛(確定性,零 LLM 判斷)**:
1. 引擎只能寫**本 session 顧問工具搜尋實際命中過的 ocs_code**(occ_searches 軌跡),
   模型憑空報碼=結構上寫不進(同書記池通道哲學:宣稱官方的必真官方)。
2. 觸發=顧問提議後、員工**下一則訊息**含肯定(確定性弱訊號會誤判——由**顧問 tool**
   顯式觸發:新增一個 WRITE 工具 `select_reference_occupations(codes[])`,顧問聽到
   同意才呼;工具層再驗 codes ⊆ 本 session 命中集)。這是**顧問唯一的 WRITE 工具**,
   寫的是 profile 參考集合,**不是文件**——文件寫入四路不變量不動。
3. 落地即回條:顧問下一句話向員工覆述「已把 X、Y 加入參考」(顯性覆述三時機之一:
   核心事實入檔前確認);審計=`interview_review_events` 記一列(decision=reference_add,
   含 codes+quote turn)。
4. **undo**=職類視窗/參考選單本來就能移除(0029 純工具不變);移除後知識包自然重組。

**盲區修復(前置,無論 O1 都要)**:訪談引擎的「參考碼集合」改為
`profile.selected_ocs_codes ∪ 文件碼`——影響點:`ledger.has_occupation`(改吃碼集合)、
`service.build_task_pool`、`scribe.build_pool_inputs`、`consultant._reference_block`
(前綴 2 顯示參考,顧問不再誤判空白)。修復後流程自然接回 0028 D6/D9:
gap→`curation:tasks` → 裁剪 precheck → 任務盤 → 任務入文件 → 書記開記。

**主基準(文件表頭)不需新機制**:verify ⑤ 已有 `mod ocs_profile.ocs_code`(值域=
header_codes,`_pending` 延遲生效,✓ 才寫+重算)——參考集合落地後書記即可提議主基準。

## 5. 波及面

- api:`interview/tools.py`(+1 WRITE 工具+守衛)、`service.py`(碼集合 union+
  occ_searches 供守衛+TurnResult 加 `knowledge_changed` 旗)、`ledger.py`
  (has_occupation 簽名)、`scribe.py`/`consultant.py`(碼集合參數)、review_events
  (decision 新值)。
- web:`useInterview` turn 後若 `knowledge_changed` → invalidate `["knowledge"]`
  (參考集合變了選單才會長出來);其餘沿用。
- 文檔:api/web README + CLAUDE.md 的「PUT occupations 刷表頭」0029 前化石一併清
  (本次事故的文檔根因之一);interview-engine.md 補「參考集合來源=profile∪doc」不變量。
- 測試:①profile 有碼+文件空 → next_gap=curation:tasks+池非空(回歸釘死本事故)
  ②WRITE 工具:池外碼拒收、命中碼落地、審計列存在 ③消費端 knowledge_changed。

## 6. 風險與不採納理由

- 「顧問拿到 WRITE 工具=破一個大腦唯一寫入路?」——**否**:0030 不變量是「**文件**寫入
  唯一路=op→verify→_pending」;參考集合在 profile,本來就有 PUT 這條人用的路,
  新工具=同一 profile 欄位的引擎入口,守衛強度(命中集白名單)≥人手點選。
- 誤選風險:守衛限縮到本 session 命中碼+顧問覆述回條+一鍵移除;最壞情況=多載一包
  知識參考,無文件汙染。
- 不做 O1 的代價:新手流斷頭(本次 22 回合全損,$0.2 花在鬼打牆),與產品「取代顧問」
  定位直接衝突(真顧問不會叫受訪者自己去點選單)。

## 7. 載體判準(卡片/彈窗/落文件;2026-07-13 大廠指南複核)

- **Microsoft HAX**(microsoft.com/haxtoolkit,MSR 2019 Amershi et al. 18 條):
  「依使用者當下任務與注意力決定何時行動/打斷」;Copilot 實證=心流中被建議打斷
  →生產力損失,**打斷要挑時機**。→ 彈窗只在 consent-triggered 時機(他剛口頭同意、
  正期待動作)彈;同回合一個 focal ask。
- **Google PAIR**(pair.withgoogle.com patterns):小而低風險→**inline 建議/預設**
  (=我們的綠字/卡片);要瀏覽比較多方向→**比較型大面**(=任務大盤);
  「**手動確認建議**能建立熟悉與信任」+「自動化必附 undo」→ 盤上人工勾選確認
  本身就是審查,確認後**直接 confirmed 不再套綠字**(雙重審查=多餘摩擦);
  mixed-initiative:act/suggest/defer/ask 分時機。
- **裁決**(維護者選 b+本節佐證):①任務=盤(彈窗)帶預勾+引文,consent-triggered;
  ②盤上確認→confirmed(0028 D9 原意);③widget 改清單、**前端一次只呈現最高優先**
  (職類卡>任務盤,依賴序),未呈現者入待辦 chip;④判準表落 interview-engine.md。

## 來源

- Anthropic《Our framework for developing safe and trustworthy agents》/《Trustworthy
  agents in practice》(可逆性判準、93% 核可率=確認疲勞)
- Smashing Magazine《Designing For Agentic AI》(2026-02;undo-first、consent 同表面撤銷)
- agentic-design.ai / AI UX Playground pattern 目錄(Intent Preview→Act→Audit)
- 本 repo:ADR 0028(驗屍+D1)、0029(脫鉤)、0030(追蹤修訂哲學);
  session 6f807f1e DB 逐字稿+interview_llm_calls 稽核(一手證據)
