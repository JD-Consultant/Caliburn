# 訪談回合模型選擇研究紀錄(RC5;model_interview=gpt-4.1-mini)

> 觸發:真人試訪 + interview_sim 校準#2 發現 `model_select=gpt-4o-mini` 當訪談顧問**變異極大**。
> 決策落 ADR [0026](../adr/0026-interview-turn-model-role.md);紀律沿用 0024(換模型=重跑
> `validate_select_schema` + `interview_sim` 留紀錄)。

## 1. 問題

訪談回合(`service._llm_turn`)原走 `select_schema(role="select")` = `gpt-4o-mini`——
**同一個弱模型同時扛兩件難事**:(a) 顧問推理(讀結構化狀態+近窗對話→決定填哪槽/追問/抓漏);
(b) strict 結構化輸出。ADR 0024 選 gpt-4o-mini 是為了 **json_schema strict 零逃逸保證**
(deepseek 系不一定支援 strict),但它的**推理**撐不起 senior 顧問:

| 證據(interview_sim,黃金範本樣張,同 capture-first prompt) | gpt-4o-mini |
|---|---|
| 校準#2 run A | 覆蓋達標、關鍵字 **0.91** |
| 校準#2 run B | 覆蓋**未達標**、關鍵字 **0.45**(`collaborators=1.0` 數字灌文字槽、`volume='看當天build的東西'` 含糊照收) |

**同碼同 prompt 兩跑 0.91↔0.45** = 模型在複合任務上不穩。n=1 但落差結構性(非雜訊)。

## 2. 權威依據(OpenRouter structured outputs 支援面)

- OpenRouter 官方 structured outputs 文件 + models 篩選(`supported_parameters=structured_outputs`):
  **原生支援 json_schema+strict 的族**:OpenAI(GPT-4o 及之後,含 **gpt-4.1 / gpt-4.1-mini /
  gpt-4.1-nano**)、Google Gemini、Anthropic(Sonnet 4.5、Opus 4.1+)、多數開源、Fireworks 全系。
- 關鍵:**gpt-4.1 系與 gpt-4o-mini 用同一套 OpenAI strict 實作**——升級到 4.1-mini,
  ADR 0024 賴以成立的「零逃逸」保證**延續**,不是換一套沒驗過的機制。
- 4.1 系官方定位:主打 **instruction following + long-context reasoning**——正對症
  (病灶=指令遵循不穩、落槽/措辭多動作協調)。

## 3. 選項比對

| 選項 | strict 保證 | 顧問推理 | 成本(相對) | 判決 |
|---|---|---|---|---|
| 維持 gpt-4o-mini | ✅(同套) | ✗ 變異大 | 1× | 否——質不穩,違背 north star |
| **gpt-4.1-mini** | ✅(同套 OpenAI) | ✅ 穩 | ~4–5× | **採用**——質/穩/成本平衡,strict 延續 |
| gpt-4.1(full) | ✅(同套) | ✅✅ | ~15× | 備選——4.1-mini 若貼線再升 |
| deepseek-chat(model_deep) | ⚠️ 未證 strict | ✅ | 低 | 否——動搖 0024 零逃逸地基 |
| Gemini 2.x flash | ✅ | ✅ | 低–中 | 備選——但 schema 格式有已知坑(pydantic-ai#3617),先不冒險 |

**不選最貴**:north star 是效果最好,但 4.1-mini 已把 sim 拉到 1.0/0.91 且對抗驗收零逃逸;
full 4.1 留作「校準貼線再升」的 escalation 槽(對齊 0024 escalation 精神)。

## 4. 驗收(換模型紀律,ADR 0024 §3)

改 `settings.model_interview` + 新增 `role="interview"`(不動 model_select;survey select
與其對抗驗收不受影響)。兩道都過:

| 驗收 | 指令 | 結果 |
|---|---|---|
| 對抗性零逃逸 | `validate_select_schema.py --role interview --n 8` | **PASS,escapes=0**;提示#1 觸發 fail-closed(誘導池外 id → 受限解碼逼失控輸出 → 截斷 → 非法 JSON → LlmSchemaError,**非逃逸**,同 4o-mini 行為),avg 1.86s/呼叫 |
| 品質校準 | `interview_sim.py --max-turns 16`(×2) | **1.0 / 0.91**,覆蓋達標、quote 1.0/0.94、零 skip(對比 4o-mini 0.91/0.45) |

## 5. 後果與延後

- ✅ 訪談質從「靠運氣」變穩;strict 零逃逸保證未動;成本↑但屬 north star 該付的。
- ⚠️ 延遲 ~1.86s/呼叫 ×2 呼叫/回合 ≈ 3.7s/回合(與 4o-mini 相當,未惡化)。
- 📌 sim 現忠實鏡像 production(`slot_paths` enum 鎖 + `role="interview"`);n=1,多 persona/
  對抗版擴充仍在 backlog。校準貼線(連兩輪 <0.8)→ 升 full 4.1,重跑本兩驗收留紀錄#3。

## 來源
- OpenRouter Structured Outputs 文件 + models 篩選頁(`?supported_parameters=structured_outputs`)。
- ADR 0024 受限解碼判準 + 驗收紀律;select_schema 對抗驗收紀錄 `2026-07-05-select-schema-acceptance.md`。
- interview_sim 校準紀錄 `2026-07-05-interview-sim-calibration.md`(#2)。
