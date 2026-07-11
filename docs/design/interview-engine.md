---
title: 訪談引擎 × 文件工作台 — 端到端設計(v2 顧問 agent)
audience: agent-primary(也給人)
scope: apps/api app/interview/* + routes/interview + apps/web 面板/稽核頁(引擎 v2)
updated: 2026-07-09
---

# 訪談引擎 × 文件工作台 — 端到端設計(v2:顧問 agent + 書記 + 帳本 + backstop)

> **主讀者 = coding agent。** 目的:不看 code 也能改對這條線——不亂發明端點、不把信任機制
> 交給 LLM、不繞過單一寫入路徑。**living:動到這條線的碼,同 commit 更新本檔。**
> 決策:ADR [0027](../adr/0027-interview-engine-v2-consultant-agent.md)(v2 四組件;修正 0025 #1)、
> [0023](../adr/0023-interview-engine-stateless-turns.md)(無狀態回合,留用)、
> [0024](../adr/0024-llm-wiring-select-schema.md)(受限解碼,留用)、[0026](../adr/0026-interview-turn-model-role.md)(模型 role)。
> spec:[`2026-07-08-interview-engine-v2-spec.md`](../specs/2026-07-08-interview-engine-v2-spec.md);
> 研究:[`2026-07-06-consultant-not-formfiller-redesign-research.md`](../specs/2026-07-06-consultant-not-formfiller-redesign-research.md)(八輪+§16 實作發現)。

## 1. 一句話

員工在工作台開「AI 訪談」側欄;每回合**兩個 LLM 各做一件事**——**書記**(便宜模型)把員工
發言受限解碼抽成結構化寫入、交 executor 確定性落地;**顧問**(強模型)拿著帳本缺口、無寫入權、
用 READ 工具查官方標準,自然對話、回述+追問。**確定性覆蓋帳本**(純程式非 LLM)追進度、
守完成閘門、偵測飽和推進;收尾**backstop**(便宜模型)複查漏記/出處只提案。信任靠「不是 LLM」
的帳本 + 寫入守衛(官方碼零幻覺、引文逐字驗證)。**無狀態回合:狀態=DB 進度列+文件本身。**

## 2. 四組件(ADR 0027)

| 組件 | 是什麼 | 碼 | 權力 |
|---|---|---|---|
| 🧠 顧問 | LLM 對話主導 + READ 工具(查職類/職能) | `consultant.py`+`tools.py`+`agent_loop.py` | **無寫入權**;說話+查 |
| ✍️ 書記 | 獨立 LLM pass:發言→結構化寫入(兩通道) | `scribe_schema.py`+`scribe.py` | 提命令,executor 執行 |
| 📋 帳本 | 純程式(非 LLM):覆蓋/閘門/飽和 | `ledger.py` | 決定「問完沒/該問啥」 |
| 🔍 backstop | 收尾便宜 LLM:漏記/出處複查 | `backstop.py` | **只提案**,不直寫 |

## 3. 資料模型(真名)

| 東西 | 住哪 | 要點 |
|---|---|---|
| 任務細項 `details`(11 槽) | 文件 `task["details"]`;契約 `TaskDetails` | 正式欄位;OCS 官方來源永遠無/`null` |
| 能力區塊 `competency_blocks[0]` | 文件;`outputs/knowledge/skills`(CodeName)、`indicators`(CodeText) | 書記兩通道寫:官方碼(池)/自訂(name+quote) |
| 態度 `ocs_attitude.attitudes` | 文件層(非逐任務;iCAP 合併呈現) | **收尾 attitudes_pass 整體編碼提建議**(0028 D3;書記池通道退場,僅剩自訂通道機會性提議;員工確認才落) |
| 進度列 `interview_sessions` | DB | status/phase/focus/**`ledger_state`**(attempts/tier_override/probe/last_gap;僅存不可重算態) |
| 逐字稿 `interview_turns` | DB | (session,seq) 唯一;quote 驗證真相來源 |
| 證據 `interview_evidence` | DB | doc_path↔quote↔verified↔**`review`**(auto/pending/accepted/reverted);不落文件 |
| 建議 `interview_suggestions` | DB | pending/accepted/rejected=未套用 diff(ADR 0025) |
| LLM 稽核 `interview_llm_calls` | DB | 每回合每次呼叫一列(role/model/耗時/tool_calls/guard_verdicts;多租戶 observability) |

## 4. 一回合資料流(runtime;`service.run_turn`)

```
面板 send(text) → POST …/interview:turn(注入 db+llm+knowledge)
  ① 載入 draft+session+逐字稿;append 員工 turn
  ② 書記 scribe_pass(便宜、序列先行;失敗不擋顧問=fail-open 對話、fail-closed 寫入):
       build_pool_inputs←knowledge.competencies(官方池;文件 block 預設空)
       select_schema(scribe_schema:兩通道 strict enum;role=select)→重試1
       apply_scribe(確定性守衛:quote 逐字驗、pool_id∈pools[kind]、跨任務歸位)
         池 K/S/O verified→直寫+evidence.review=pending;自訂/draft/add_task→建議層
         (態度池通道已退場 0028 D3;僅剩 record_attitude_custom 機會性提議)
  ③ 寫回 upsert_draft(雙 token)→409 重讀重放同 records 一次→再衝突放棄直改(人優先)
       evidence(帶 review)/suggestions 落庫
  ③½ build_task_pool←knowledge.occupation_tasks 聯集(0028 檢查表候選盤;fail-open)
  ④ 帳本:note_attempt(飽和計數)→ next_gap(doc,state,{},pool_tasks)→ ledger_state 存回
       (ledger_state 增 declined[]/writein_asked;0028)
  ④½ 裁剪 pass(0028;last_gap=curation:tasks 且有 unasked):curation_pass(便宜模型)
       → precheck→**widget 指令** {kind:open_picker,picker:task,precheck:[{key,name,unit,quote}]}
       (D9:widget 只帶 **AI 疊加層**;任務盤清單=前端知識包組,ADR 0021)
       → declined→ledger_state(檢查表不再反問);稽核落庫一列
  ⑤ 顧問 chat_with_tools(role=interview;messages=帳本摘要(含檢查表成組反問/write-in 抓漏)
       +文件+待核准+近窗對話;手刻迴圈 run_tool_loop)
  ⑤½ occupation widget(0028+D8 P2 統一):顧問本回合搜過職類且**首個 top-1 ∉ 現有 codes**
       → {kind:open_picker,picker:occupation,query:<顧問的搜尋詞>}(dispatch closure 截命中,
       確定性觸發)。涵蓋開場(codes 空)與**中途加選**(聊到超出現有職類的工作);
       查參考(top-1=已選)不彈不騷擾;顧問 prompt 同步明講建議「加選」
  ⑥ 保底:say 空→next_gap 合成問題;append 顧問 turn
  ⑦ 稽核落庫;回 {say, widget, doc_changed, pending_suggestions,
       progress:{phase=derive_phase(議程推導), coverage}}
收尾 POST …/interview:finish → service.run_finish:backstop_pass + **attitudes_pass**
  (0028 D3:全逐字稿→2–4 條態度建議、每條綁最強引文、MAX_A 硬上限)→建議化→phase=review
隨叫 POST …/interview:curation → service.run_curation(D8 P1a;D9):選完職類**立刻**
  鋪任務盤(零打字)——pool→unasked→curation_pass→**只回 {precheck}**(AI 疊加層);
  declined 落 ledger_state;llm 缺/無發言→precheck 空(fail-open:前端盤照開)
```

## 5. UI 動作 → 請求對照

> **⚠ ADR 0029(2026-07-11)動了共用編輯器 UI,本節的 AI 載體尚未重設計。** 編輯器選單已收斂成
> **三型(控制/參考/素材庫)、一律獨立視窗**(見 [`editor-knowledge-pack.md`](editor-knowledge-pack.md) 的 ADR 0029 段);
> 〔選職類〕改名〔選職能基準參考〕(只記參考、不寫表頭);任務 O/P/K/S 四格「點此填」+ CellFillerPanel **退役** →
> TaskRow 內 **OPLKS 全展開區**。**本輪 AI 元件(CurationDialog、`interview:curation`/precheck、D7 reviewMap 徽章、
> InterviewPanel)刻意不重設計**——只做維持編譯+測試綠的最小適配(D7 徽章改掛新格區對應列);AI 共編載體
> (直寫表格+顏色標記、逐筆確認/拒絕)之後另開研究+ADR(spec §11)。下表元件名/流程仍照舊,細節以碼為準。

| 動作 | 元件 | 網路 |
|---|---|---|
| 開始/續談 | InterviewPanel | `POST …/interview:start`(冪等;**空白 doc 也可起跑**=顧問引導選職類,§9.3) |
| 回答 | InterviewPanel | `POST …/interview:turn {text}` → 回 `progress.coverage` + **`widget`**(0028) |
| **深聊 meta 快速回覆** | 面板輸入框上 chips(跳過這題/沒有/先記到這)——**僅流程動作**(D8 P4) | (無;純 send 轉發走 turn;後端 skips 語彙認得「跳過」) |
| **AI 開職類 picker** | 面板 `onWidget` → page 開 `OccupationPicker(autoSearch)` | (無;widget 指令=`{kind:open_picker,picker:occupation,query}`,開窗即搜顧問用過的 query;開場+**中途加選**同一條 D8 P2) |
| **AI 任務盤確認** | `CurationDialog` **一窗兩步**(D8 P1b:步1 勾職責 → 步2 該職責任務;職責是閘門)。**盤=編輯器知識包全量**(D9 `buildBoard`:unitRows/taskRows 同宇宙;任務鎖=URN、職責身分=名稱),**列=編輯器選單同款**(Command 列:✓+序號+SourceLine,同 Unit/TaskPickerMenu 形式),AI 只疊 precheck+引文 | (無;widget `{picker:task,precheck:[…]}`=AI 疊加層;套用=前端 `addFromPool`→persist 同一寫入路徑) |
| **選完職類自動鋪盤** | `OccupationPicker.onApplied` → page 呼端點 → 開 `CurationDialog`(訪談開著才觸發;端點失敗盤照開=fail-open) | `POST …/interview:curation` → `{precheck}`(D8 P1a 零打字;D9 清單在前端) |
| 收尾 | (收尾流程) | `POST …/interview:finish` → `service.run_finish`(backstop+**態度收尾**+轉 review) |
| 批審套用 | **面板底部「N 項待審」計數鈕**(0028 D5:置頂看不見 bug 修正)→ SuggestionReview → decide | `POST …/interview:review {accept,reject}` → **前端** `applyAccepted`(自訂能力/態度=**append 陣列**;`appendAtPath`)→ persist |
| AI 直寫檢視 | **JobDocTable 同格追蹤修訂**(0028 D7):O/P/K/S 格 AI 徽章+hover 引文;**details 11 槽 chips 呈現**(`reviewMap.ts`;evidence.review=pending 為資料源) | `GET …/interview`(evidence 帶 `review` 欄) |
| 顧問稽核 | `/documents/[id]/interview` 頁 | `GET …/interview`(逐字稿+證據+建議) |
| 人直接改文件 | 既有編輯器 | PATCH(diff 記入 human_touched) |

## 6. 不變量(code 讀不出的規則)

1. **顧問無寫入權、書記無對話**:顧問只 `chat_with_tools`(READ 工具)說話;所有寫入經書記
   `select_schema`→`apply_scribe`→executor 守衛。兩次獨立呼叫(顧問說話零格式負擔、書記受限
   ——「兩邊都安全」;§10.4)。**別把 set_slot 語彙放回顧問 prompt。**
2. **官方碼零幻覺**:書記池通道 pool_id 走 strict enum(當回合合法池),對不上→自訂通道
   (name+quote)。「零幻覺」=宣稱官方的必真官方,不是全部得官方(§9.1)。
3. **風險分層寫入**(修正 ADR 0025 #1):低風險(池 K/S/O、細項槽 verified)直寫+`review=pending`
   批次審;高風險/影響結構(自訂任務、模糊歸類、**態度**)→建議層。不再「人沒碰過就直改不標記」。
4. **進度=帳本、不是 LLM**:next_gap/飽和/完成閘門全在 `ledger.py`(純函式);反例=無狀態機的
   LLM 自判進度→88% 該追未追(arXiv 2410.01824,§10.2)。門檻數字=v1 出廠值,改=跑
   `interview_sim.py` 校準留紀錄,不改碼形。
5. **path 文法全域一致**(`diff.py`/`executor.py`/`ledger.py`/web `interviewDoc.ts` 鏡像):
   段以 `.` 連接,list 段用穩定 id(`_tid/_uid/_id`)優先、index 後援。
6. **quote 溯源住 session 不落文件**;每筆寫入綁引文,executor 驗「NFKC+空白摺疊後為逐字稿子串」。
7. **手刻迴圈藏 `LlmPort` 後**(12-Factor F8);迴圈邏輯在 `agent_loop.run_tool_loop`(可測)、
   adapter 只提供真實呼叫。換模型=重跑 `validate_select_schema.py --target scribe` + `interview_sim.py`。
8. **員工輸入=資料非指令**(OWASP LLM01):顧問/書記 prompt 明示;工具唯讀、寫入鎖 enum+人審、
   無對外動作、max iterations——注入天生緩解。
9. **舊 authoring graph(LangGraph)+ v1 單 LLM 路徑(context.build_prompt/turn_output_schema)
   = 退役待清**:v2 全新實作;v1 `context.py`/`commands.py` 待 v2 穩定後一次清除。
10. **空白文件先 onboarding、不掉態度**(§16.16、0028):`next_gap` 文件無任務時回 `ONBOARD_OCCUPATION`
    (無 ocs_code)/`CURATION_TASKS`(有碼:AI 預勾裁剪/檢查表),無任務時**不受 is_stalled 影響**
    (選職類前不許 fall through 到態度);有任務後檢查表殘項(`checklist` unasked)→ `CURATION_TASKS`
    尊重 STALL_K(成組問兩輪無進帳讓路 deep);`derive_phase`=議程顯示用(doc 推導不落庫);`ledger_summary` 對 onboarding 吐引導語(問實際做什麼→查職類→提
    具體職類請他從〔選職類〕確認),顧問 prompt 硬規則「選職類前不問態度、不硬猜職類硬套」。
    反例=空白文件掉進態度縫→顧問問態度→模糊 query 語意搜尋→幻覺職類(production bug 8ba32711)。
    **書記無權設 `ocs_code`**;選職類靠既有〔選職類〕按鈕 + widget 指令自動開窗(0028)。
11. **widget=指令、非渲染**(0028 D1/D5):`TurnResult.widget` 是「開哪個 picker、預填/預勾什麼」
    的指令(`open_picker`),前端開**同一批編輯器 pickers**(同 UI、入口不同)——別在聊天室
    另做一套 UI、別復活 CopilotKit interrupt。高風險(職類/任務)=picker 阻斷確認;
    預勾**保守**且每列附引文理由(反 rubber-stamp:Claude Code 93% 盲簽教訓)。
    前端派發=**事件**(mutation onSuccess 一次),別存 state 用 effect 派發(§16.18 重彈迴圈)。
12. **態度=收尾整體編碼**(0028 D3):`attitudes_pass` 讀全逐字稿提 2–4 條(MAX_A 硬上限、
    引文逐字、只建議);**別把逐回合態度抽取加回書記**(反例=39 條逐句轟炸,session eb2af457)。
    檢查表(covered/declined/unasked)身分對位=**provenance**,別用 task_codes.code(位置碼)。
13. **結構=點選、深度=對話**(D8 鐵律):可枚舉的結構決策(職類/職責/任務的有無)→
    選單勾選,官方清單**全量照列**(recognition over recall,開放題答題負擔 4–6 倍/
    漏答 18% 的實證);裁剪窗照 DACUM **職責→任務兩步**,職責是閘門。個人化深度
    (怎麼做/標準/眉角的 BEI 故事)→ **只能用說的**;chips 僅 meta 流程動作
    (跳過/沒有/下一題),**別把內容答案做成 chips**——選單化深聊=把顧問降級成問卷。
14. **任務盤清單=前端知識包、後端只送 AI 疊加層**(D9;ADR 0021):`CurationDialog` 的
    職責/任務宇宙由 pack 組(`buildBoard`;身分機制同編輯器——任務=URN `taskUrns`、
    職責=名稱、寫入=`addFromPool`),widget/`interview:curation` 只回 `precheck(key+quote)`。
    **別讓後端回清單本身**(反例=v2.2 出廠的 unasked 殘表:已加入的任務在 AI 彈窗直接
    消失、職責只列殘餘、鎖定機制第三套——維護者實測抓到)。

## 7. Limitations(ADR 0027;誠實記載)

- **單信息源**:v1=單一員工自述+顧問人審(=第二來源最小版);主管確認、同職務多員工合併
  =路線圖(§17)。**純文字**:語音/情緒訊號=未來縫。延後:書記並行化、self-consistency、
  live critic、Pydantic AI 遷移。

## 8. 指路

- 碼:`apps/api/app/interview/`(ledger/slots/scribe_schema/scribe/**curation**/**attitudes**/
  tools/agent_loop/consultant/backstop/executor/commands/context/service/diff)
  + `routes/interview.py` + `adapters/interview_repo.py`。
- web:`components/interview/InterviewPanel|SuggestionReview|**CurationDialog**|JobDocTable(追蹤修訂)`
  + `lib/interviewDoc.ts|**curation.ts**|**reviewMap.ts**` + `hooks/useInterview.ts`。
- sim:`evals/interview_sim.py`(v3:裁剪 precision/recall + grounding + 態度收尾)。
- 黃金範本(品質尺):[`../specs/2026-07-05-golden-sample-software-tester.md`](../specs/2026-07-05-golden-sample-software-tester.md);
  問句庫=研究紀錄 §15;prompt 全文+sim 劇本=[`../specs/2026-07-08-interview-v2-prompts-and-scenarios.md`](../specs/2026-07-08-interview-v2-prompts-and-scenarios.md);
  驗收/校準紀錄=研究紀錄 §16(§16.1–§16.14)。
