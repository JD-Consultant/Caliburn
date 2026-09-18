# ADR 0026 — 訪談回合獨立模型 role(model_interview,強推理 + strict)

- **狀態**:Accepted(2026-07-06)。
- **研究依據**:[`../specs/2026-07-06-interview-model-selection.md`](../specs/2026-07-06-interview-model-selection.md)
  (OpenRouter strict 支援面、gpt-4o-mini 變異證據、選項比對、驗收)。
- **關聯**:延伸(不翻案)ADR [0024](0024-llm-wiring-select-schema.md)的 per-role 分層與
  「換模型=重跑驗收」紀律;消費者=ADR [0023](0023-interview-engine-stateless-turns.md)訪談引擎。

## 脈絡

訪談回合原搭 `role="select"` = `gpt-4o-mini`,同一弱模型同時扛顧問推理與 strict 輸出。
interview_sim 校準#2:同碼同 capture-first prompt 兩跑 **0.91↔0.45**(數字灌文字槽、含糊照收)
——推理不穩。但 gpt-4o-mini 的 strict 零逃逸沒問題,不能只因推理弱就換掉沒驗過 strict 的模型
(deepseek 動搖 0024 地基)。

## 決定

1. **訪談回合獨立成 `role="interview"`**(`model_for_role` 新增一列;不動 `select`),
   `settings.model_interview` 預設 **`openai/gpt-4.1-mini`**——與 gpt-4o-mini **同一套 OpenAI
   strict 實作**(零逃逸保證延續),但推理/指令遵循強一階。`select` 仍 gpt-4o-mini(survey 池選)。
2. **換此模型 = 兩道驗收都重跑**(沿用 0024 §3):`validate_select_schema.py --role interview`
   (對抗零逃逸)+ `interview_sim.py`(品質校準),結果留 `docs/specs/`。已驗:零逃逸 PASS、
   sim 1.0/0.91。
3. **Escalation 槽**(不預建):校準連兩輪 <0.8 → 升 `openai/gpt-4.1`(full);
   strict 出現真逃逸 → 觸發 0024 的直連評估。

## 後果

- ✅ 訪談品質從「靠運氣」變穩;ADR 0024 的 strict 零逃逸保證與 per-role 分層皆不動。
- ⚠️ 成本 ↑(~4–5× 於 select 那條);屬 north star(取代顧問=效果優先)該付,非為省而降。
- 📌 `interview_sim` 現忠實鏡像 production(`slot_paths` enum + `role="interview"`);
  多 persona/對抗版仍 backlog。翻案(如全面改 Gemini/直連 Anthropic)開新號。
