# 0035. Interview AI vNext：OpenRouter-first provider boundary，直連供應商降為比較與備援

日期：2026-07-17

狀態：Accepted（provider 主線已核准；OpenRouter adapter 尚未實作）

Supersedes：

- 0034 決定 8 中「production 直接以 OpenAI Responses／Anthropic Messages 為第一條 provider
  主線」的部分；0034 的 provider-neutral port、app-owned state、Evidence workflow、Capture、
  eval gate 與不採大型 agent framework全部保留；
- V3 research／plan 中「官方 OpenAI live probe 必須先通過才可進 V3-5」的 release ordering。

保留：

- 已完成的 eval-only OpenAI Responses adapter、mocked fixtures與測試，作為 direct-vendor
  reference adapter；
- 官方 OpenAI／Anthropic直連 adapter作為後續同模型 gateway-effect比較與災難備援候選；
- 所有 provider-neutral request/result、ContextBuilder、durable attempt、artifact與 reducer contract。

詳細實作規格：
[`../plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md`](../plans/2026-07-17-interview-vnext-v3-4r-openrouter-first-adapter-plan.md)

## 脈絡

Caliburn 已完成 vNext 的 domain、durable workflow、Context Engine、typed turn operation與
OpenAI Responses eval-only adapter。原順序要求先以官方 `OPENAI_API_KEY`完成 direct OpenAI
live conformance，再用該 adapter跑 V3-5。產品決策現已改為：正式模型流量先經 OpenRouter，
以一個 gateway比較 Claude、GPT、Gemini與其他模型，降低一人團隊同時維護多套供應商接線的成本。

若仍要求官方 OpenAI live gate先行，實際只證明 Caliburn ↔ OpenAI direct 的 wire contract；
它無法證明 production 真正會經過的 OpenRouter routing、parameter transform、provider fallback、
錯誤正規化、usage/cost與 metadata。把錯誤的外部邊界設成 release gate，會再次得到「測試完整，
上線路徑卻沒被測」的假安全感。

截至決策日，OpenRouter 官方資料顯示：

- `/api/v1/chat/completions` 是完整文件化、OpenAI-compatible 的主要 REST 介面；
- OpenRouter Responses API明確標示 Beta、stateless，可能有 breaking changes；
- OpenRouter官方 Python SDK也明確標示 Beta；
- strict structured outputs可透過 `response_format.type=json_schema`使用，且官方要求
  `strict=true`與 `provider.require_parameters=true`；
- provider routing預設會做 load balancing，`allow_fallbacks`預設為 `true`；
- router metadata只有 opt-in才回傳，能揭露 selected provider/model、attempt、fallback與會修改內容的
  pipeline stages；
- plugins可由帳戶預設開啟，context compression、response healing等會修改 request或response；
- Chat Completions成功回應包含 normalized與 native finish reason、native tokenizer usage與 cost，
  generation ID可另查 generation metadata。

來源均為 OpenRouter官方文件：

- [API overview](https://openrouter.ai/docs/api/reference/overview)
- [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)
- [Router metadata](https://openrouter.ai/docs/guides/features/router-metadata)
- [Structured outputs](https://openrouter.ai/docs/guides/features/structured-outputs)
- [Responses API Beta](https://openrouter.ai/docs/api/reference/responses/overview)
- [Python SDK API reference（Beta聲明）](https://openrouter.ai/docs/client-sdks/python/api-reference/endpoints)
- [Errors and debugging](https://openrouter.ai/docs/api/reference/errors-and-debugging)
- [Models API](https://openrouter.ai/docs/guides/overview/models)

## 決定

1. **OpenRouter 是 vNext 第一個 production provider boundary**。對 domain/application 而言，
   `provider=openrouter`；實際模型作者與 hosting endpoint是 Capture中的 resolved routing facts，
   不能混成同一欄。這是第一個adapter選擇，不是唯一provider：Caliburn-owned `LlmPort`仍是上層
   abstraction，OpenRouter／OpenAI／Anthropic等各自位於adapter層。
2. **不再要求官方 OpenAI live gate阻擋 V3-5**。已完成的 OpenAI adapter保留為 reference；
   official OpenAI live probe改為 optional comparison gate。
3. **新增 V3-4R OpenRouter eval-only adapter與 live conformance gate**。V3-5只能在 V3-4R
   mocked matrix與至少一次真 OpenRouter probe通過後開始正式 live trials。
4. **第一條主線使用 `/api/v1/chat/completions`**。OpenRouter Responses與官方 Python SDK在
   解除 Beta前不是唯一 production authority；可做平行 conformance spike，但不得跳過主線 gate。
5. **V3-4R 使用現有 `httpx.AsyncClient`直接呼叫官方 REST**，不新增 Beta SDK，也不把既有
   OpenAI adapter改成可任意換 `base_url`的混合 adapter。這使 request body、headers、timeout、
   response/error raw shape與一次 HTTP call可被精確測試。
6. **benchmark routing 必須可歸因**：exact canonical model slug、exact upstream endpoint、
   `allow_fallbacks=false`、`require_parameters=true`、單一 model、非 streaming；禁 `auto`、
   `free`、`latest`、`nitro`、`floor`、多模型 fallback與會漂移的 alias。
7. **benchmark 禁止隱性內容改寫**：response healing、context compression、web/file plugins、
   server tools、response cache與 provider conversation/session state均不得影響結果；router metadata
   缺失、attempt大於1、selected provider/model與pinned endpoint snapshot不符或出現 mutating pipeline
   stage時，trial判為 contaminated，
   不得計入品質分數。
8. **OpenRouter routing是被測對象，不是黑盒便利功能**：每次 run保存 requested/resolved model、
   configured endpoint slug、selected provider/model、router strategy/attempts/pipeline、generation ID、
   HTTP request ID、usage、cost、
   normalized/native finish reason與 config/model-catalog snapshot hash。
9. **fallback分兩階段**：benchmark全部關閉；production resilience只有在每個 model/endpoint個別通過
   conformance與品質 gate後才能開。多模型 fallback的 resolved model必須在已核准 allowlist。
10. **直連供應商測試依模型而定**：若主模型是 Claude，對照 Anthropic direct；若是 GPT，對照
    OpenAI direct。直連比較用來量 gateway effect與備援，不是 OpenRouter主線的前置儀式。
11. **OpenRouter Agent SDK、server tools與 provider memory不進核心**。Context、workflow、Evidence、
    reducers與人工審閱 authority仍由 Caliburn掌握。
12. **模型選型不寫死在 ADR**。V3-5在 run開始前從 Models/Endpoints API建立 immutable snapshot，
    只使用具 exact canonical slug、structured outputs與所需參數的 model/endpoint，再以 task-specific
    multi-trial eval裁決。

## 被否決的選項

### 先完成官方 OpenAI，再測 OpenRouter

否決作為 mandatory ordering。它多花成本卻仍未測 production gateway；僅在需要 GPT direct
對照或備援時保留。

### 直接把 OpenAI adapter的 base URL換成 OpenRouter

否決。OpenRouter有自己的 provider routing、embedded error、native finish reason、cost、generation
與 router metadata；共用 adapter會讓 provider-specific語意互相污染，也無法精確限制 request body。

### 直接採 OpenRouter Responses API Beta

否決作為唯一主線。它符合未來方向且保持 stateless，但官方仍警告 breaking changes；先以獨立
candidate spike驗證，不讓 Beta wire format成為 V3品質實驗的額外變因。

### 直接採 OpenRouter官方 Python SDK

目前否決。SDK自動由 OpenAPI生成且長期值得重評，但官方仍標示 Beta；V3-4R只需一個非 streaming、
strict JSON operation，直接 HTTP較小、可稽核且沒有未知 SDK retry。SDK解除 Beta後以 parity tests
重新裁決，而非永遠禁止。

### 從第一天開啟 auto router與多模型 fallback

否決。它優化 availability，卻會讓同一 case/trial實際使用不同模型或 endpoint，無法把品質差異
歸因到 context、prompt、model或 provider。

## 後果

- V3主線多一個 V3-4R adapter切片，但之後所有品質試驗都測到真正會上線的 gateway。
- 已完成 OpenAI adapter不是廢工；它保留了 portable schema、artifact、error與 SDK conformance證據，
  並成為 direct GPT comparison能力。
- benchmark與 production routing分成兩個明確 profile；不能拿高可用 profile的混合結果宣稱某模型
  通過品質 gate。
- OpenRouter內部即使只收到一個HTTP call，也可能做多個 upstream attempts。benchmark以
  `allow_fallbacks=false`加 router metadata gate限制；production開 fallback後，Capture必須把 sub-attempts
  當 gateway facts保存，不能宣稱「一個 durable attempt等於一次上游推論」。
- 現有 neutral `ModelCallResult`沒有獨立 upstream provider、generation ID與 dollar cost欄；V3-4R先用
  supporting artifacts無損保存，不在此切片改 migration。若 V6/V7證明這些欄需作查詢或 SLA索引，
  另提 versioned neutral contract/migration。
- OpenRouter建議對429/503尊重 `Retry-After`，而目前 executor只有 bounded attempts、沒有 provider-aware
  backoff。V3-4R先保存 header且不做 SDK retry；正式 production promotion前必須另行完成 retry scheduling
  contract，不能在 adapter內 sleep或偷偷重試。
- response healing、caching、provider fallback與 Responses API可能日後提升可靠度／成本；它們只能作
  具名 ablation，通過後產生新的 config hash，不可無聲開啟。
