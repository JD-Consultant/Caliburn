# 訪談模擬校準紀錄 #1(T14;evals/interview_sim.py)

> **紀律**:改覆蓋門檻/追問預算/core 判準/引擎 prompt = 重跑本 eval 留紀錄;
> 模擬只當回歸網(Sim2Real gap,輪 10),**上線前配真人試訪**。

## 紀錄 #1 — 2026-07-05

- **設定**:顧問=`model_deep`(deepseek-chat)組 context、`model_select`(gpt-4o-mini)
  受限解碼;模擬員工=`model_cheap` 綁事實表(黃金範本樣張 §4.2 王OO/T2.2 回歸測試,
  11 槽全載;規則:只准照表答、表外說不知道);max_turns=14。
- **結果**:**GATE PASS ✅**

| 指標 | 值 | v0 閘門 |
|---|---|---|
| 覆蓋達標(11 槽+outputs,扣 justified-skip) | ✅(14 回合內) | 必須 |
| 槽值關鍵字正確率 | **0.91**(10/11) | ≥0.6 |
| quote 驗證率(逐字稿子串) | **1.00** | ≥0.7 |

## 判讀

1. **數值推理正確**:員工說「大概占我四分之一的時間」→ `time_share_pct=25.0`
   (引擎途中曾 justified-skip 該槽,後續對話補齊——skip 不擋後補,行為正確)。
2. **細節保真好**:`wait_points` 完整收下「環境只有一套…平均等一兩個小時」含 nuance;
   `standards` 收齊三條件(100%/無 blocker/簽核)。
3. **唯一失分 = 過度抽象**:`trigger` 填成「事件觸發」,丟失「build 好 Slack bot 通知」
   的具體性。**改善縫(記,不立即動)**:ROLE_HEADER 加一句「值要保留員工的具體措辭,
   不要抽象化」;下輪校準驗證。
4. 閘門數字維持(0.6/0.7)——首輪即 0.91/1.0,留 buffer 容納模型漂移;連兩輪貼線再收緊。

## 紀錄 #2 — 2026-07-06(真人試訪後三根因修復 + 模型升級)

觸發:首次真人試訪(profile 02bc45a3)逐字稿暴露機械病(幽靈槽/靜默)+對話病
(不確認/重複問/爛答照收)。修復 RC1–RC3 後重跑校準,連環發現兩事:

1. **RC3 回歸 → 落槽優先修正**:ROLE_HEADER 一版把「先回述確認」放最前,gpt-4o-mini
   用回述**代替** set_slot(dump 見 turn 4/5/6/10/11 只出 `[reply,ask]`)→ 反覆問耗盡預算
   → 自動 skip 可填槽 → 覆蓋 0.91**→0.45**。改回 capture-first(落槽為不可違反的置頂硬規則,
   回述/追問不得取代)後恢復 0.91。**教訓**:prompt 動作排序會被小模型當優先序,capture 必置頂。
2. **模型變異 → 升級 model_interview**:同 capture-first prompt,gpt-4o-mini 兩跑 **0.91↔0.45**
   (`collaborators=1.0`、含糊照收)=模型太弱。獨立 `role="interview"` 配 **gpt-4.1-mini**
   (ADR 0026;同套 OpenAI strict)後兩跑 **1.0 / 0.91**、quote 1.0/0.94、零 skip。

| 指標 | 4o-mini(修復後) | **gpt-4.1-mini** | v0 閘門 |
|---|---|---|---|
| 覆蓋達標 | 不穩(run B 未達) | ✅ ×2 | 必須 |
| 關鍵字正確率 | 0.91 / **0.45** | **1.0 / 0.91** | ≥0.6 |
| quote 驗證率 | — | 1.0 / 0.94 | ≥0.7 |

sim 同步**忠實鏡像 production**:`turn_output_schema(slot_paths=…)` enum 鎖 + `role="interview"`;
加 `--dump` 逐回合印指令/guard(本次蒐證關鍵)。對抗零逃逸另見
[`2026-07-06-interview-model-selection.md`](2026-07-06-interview-model-selection.md) §4。

## 紀錄 #3 — 2026-07-15(v4 事件/收割接線 + 真模型 gpt-5.4-mini)

觸發:ADR 0033 v4(事件驅動議程 + harvest=P 的家)後,舊 sim 迴圈只跑書記+顧問、
**沒接 harvest**,驗不到「v4 到底產不產 P」(BUG-2 的核心疑慮)。把 sim 從 v3 升 v4:
顧問工具補 `AG.agenda_tools`(open/close_episode)+ `agenda_view` 注入,鏡射
`service.run_turn` 的 open/close→`pending_harvest`→`harvest_pass` 接線(in-memory 無 DB),
新增量尺 `indicators_total`/episodes/harvest,GATE 加 **P≥1**。

- **設定**:顧問+select=`gpt-5.4-mini`、cheap/deep/indicator=`deepseek-v4-flash`;
  模擬員工同 §4.2 王OO/T2.2;max_turns=16;`--dump`。
- **結果**:**GATE FAIL**(唯一卡 `verify_pass_rate=0.74 < 0.8`;主目標 P 達成)。

| 指標 | 值 | 閘門 |
|---|---|---|
| **indicators_total(P;收割是 P 的家)** | **11** | ≥1 ✅ |
| episodes 開→收 / harvest_landed | 2→1 / **1/1** | — |
| curation precision / recall / declined 全對 | **1.0 / 1.0 / ✅** | precision ≥0.8 ✅ |
| attitudes(A03/A04/A06,皆有 quote) | 3 | cap ✅ |
| progressed_turn_rate | 0.81 | ≥0.8 ✅ |
| avg_quote_len | 44.1 | — |
| **verify_pass_rate** | **0.74** | **≥0.8 ❌** |

### 判讀

1. **v4 產 P 確認(BUG-2 證死)**:11 條指標,書記在 episode 內即時起草(P 0→…)+
   close 時 harvest 補;逐字稿見顧問正確 BEI 深挖、換事件、遇「我不確定」優雅跳過。
2. **GATE FAIL 唯一因 `verify_pass_rate=0.74`,且成分=dedup 非 grounding**:14 條
   verify-reject **幾乎全是 `invariant:…已存`**(重複),不是 quote 對不上(grounding
   實際近滿分,avg_quote_len=44)。病灶=**書記在深挖同一 task 時反覆重 draft 已存的
   K/S/O**,verify dedup 正確擋掉。指標把 dedup 拒收也算失敗,才被拖到 0.74。
   → 這正是 [`2026-07-14-interview-agenda-architecture-research.md`](2026-07-14-interview-agenda-architecture-research.md)
   §3.5 兩支筆(書記/收割)重疊的**實測證據**。
3. **小瑕疵:非回答起草垃圾指標**:turn 11–16 模擬員工反覆「我不確定/事實表沒寫」,
   書記仍從**非回答**draft 了 2–3 條雜訊 P。一半 sim 假象(真員工不說「事實表」)、
   一半真(書記不該從非回答起草 P)。
4. **紀律:不反射性調閾值/改指標**(門檻改=重跑不改碼)。verify_pass_rate 的
   dedup/grounding 混淆 + 書記深挖冗餘,**根治=Option A(crisp division:深挖時 P/K/S
   歸收割、書記只抓事實/enum)**——記 backlog,不現在治標。

## 已知限制

單一 persona/單任務/單輪;n=1 不做統計宣稱,定位=回歸網基線。擴充(多 persona、
含「愛離題員工」對抗版——真人試訪證實這類最會踩雷)記入 backlog,K/S 表面接線前再擴。
**backlog(紀錄 #3 後)**:① `verify_pass_rate` 指標拆分——grounding 拒收(quote 對不上,
算失敗)vs dedup 拒收(已存,正確行為,不算失敗);② **Option A crisp division**(書記/收割
分工切乾淨,治書記深挖冗餘 + 相似重複);③ 書記「非回答不起草 P」守衛。①②③ 屬同一根,
隨 Option A 決策一併處理(當前使用者擱置,先記不做)。
