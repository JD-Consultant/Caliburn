---
title: 模型陣容盤點與 CP 值分析(2026-07 全家桶更新後)
date: 2026-07-13
purpose: ai-layer-v3 上線前,決定五個 role 的模型要不要換
source_discipline: 只收官方一手定價頁 + OpenRouter 模型頁;二手聚合僅當線索,逐條回官方核實
---

# 模型陣容盤點(2026-07-13)

## 0. 現役配置(apps/api/app/config.py)

| role | 現役模型 | 官方價(in/out per 1M) | 用途 | 問題 |
|---|---|---|---|---|
| `interview`(顧問) | `openai/gpt-4.1-mini` | $0.40/$1.60 | 每回合 chat+tools,**品質最關鍵** | 2025-04 模型,已落後兩個世代 |
| `select`(書記/curation/態度) | `openai/gpt-4o-mini` | $0.15/$0.60 | strict json_schema、temp=0 | 2024 模型,抽取品質=文件品質 |
| `cheap`/`deep`/`indicator`(/ai/*) | `deepseek/deepseek-chat` | $0.14/$0.28 | read-only 提議 | **舊名 2026-07-24 淘汰**(DeepSeek 官方) |
| fallback ×2(T13) | 空 | — | models=[主,備] | 待過考卷後填 |
| judge(Phase 2) | 未定 | — | cross-model-family | — |

## 1. 2026-07 各家最新陣容(官方一手,已核實)

**OpenAI**(developers.openai.com/api/docs/pricing,2026-07-13 取):
- `gpt-5.6-sol/terra/luna` $5/$30 · $2.50/$15 · $1/$6(cached in 0.1x)——**2026-07-09 GA**(6/26 起政府審查限預覽,7/9 全面開放;openai.com/index/gpt-5-6)。
- `gpt-5.5` $5/$30;`gpt-5.4` $2.50/$15;**`gpt-5.4-mini` $0.75/$4.50**(2026-03-17,400K ctx;OpenRouter 已核);`gpt-5.4-nano` $0.20/$1.25。

**Anthropic**(platform.claude.com/docs/en/about-claude/pricing,2026-07-13 取):
- Fable 5 $10/$50;Opus 4.8 $5/$25;**Sonnet 5 $2/$10(intro 至 2026-08-31,之後 $3/$15)**;Sonnet 4.6 $3/$15;Haiku 4.5 $1/$5。
- Cache read=0.1x;**注意:Opus 4.7+/Sonnet 5/Fable 5 新 tokenizer 同文多 ~30% tokens**(實算成本 ×1.3)。
- OpenRouter 路由 Anthropic 系:**前綴須帶 `cache_control` 否則完全不快取**(驗證報告 H1;T13 已在 adapter 註記)。

**Google**(ai.google.dev/gemini-api/docs/pricing,2026-07-13 取):
- `gemini-3.5-flash` $1.50/$9(2026-05-19);`gemini-3.1-pro-preview` $2/$12(≤200k);
  **`gemini-3.1-flash-lite` $0.25/$1.50(GA 2026-05-07,1M ctx;OpenRouter 已核)**;`gemini-3-flash-preview` $0.50/$3。

**DeepSeek**(api-docs.deepseek.com,2026-07-13 取):
- **V4-Flash** $0.14/$0.28(cache hit in $0.0028;1M ctx)、V4-Pro $0.435/$0.87。
- **`deepseek-chat`/`deepseek-reasoner` 舊名 2026-07-24 淘汰**(現映射 V4-Flash 非思考/思考模式)。
- OpenRouter `deepseek/deepseek-v4-flash`:$0.077/$0.154(比官方直連還便宜;已核)。

## 2. 成本量級(把帳算清楚:換貴模型到底多花多少)

顧問一回合估算(context 三層 ~8k in、~400 out、工具迴圈 ×1.5;30 回合/場):

| interview 候選 | $/回合(無快取) | $/場(30 回合) |
|---|---|---|
| gpt-4.1-mini(現役) | ~$0.0056 | ~$0.17 |
| gpt-5.4-mini | ~$0.012 | ~$0.36 |
| gpt-5.6-luna | ~$0.016(快取後 ~½) | ~$0.5 |
| **claude-sonnet-5(intro)** | ~$0.026(含 tokenizer×1.3;cache_control 後 ~⅓) | **~$0.8** |
| gemini-3.5-flash | ~$0.023 | ~$0.7 |

**結論:最貴選項一場訪談 <$1。** 對「取代顧問級 JD」的產品,模型成本不是約束——
品質是唯一優先(north star),CP 值的「C」在本案幾乎可忽略,選型看「P」。

## 3. 逐 role 建議

| role | 建議 | 理由 |
|---|---|---|
| `cheap`/`deep`/`indicator` | **必換**:`deepseek/deepseek-v4-flash` | 舊名 7/24 淘汰(不換=斷);V4-Flash 官方同價、OpenRouter 更便宜、1M ctx;/ai/* read-only 低風險 |
| `interview` | **升級**:首選 `openai/gpt-5.4-mini`;對照組 `deepseek/deepseek-v4-flash` | 顧問=產品本體;5.4-mini 是同價位帶最新一代(400K ctx、tools 成熟),~$0.36/場;V4-Flash 是 CP 王(~$0.07/場)當挑戰者。**兩者都上 T11 考卷 A/B,分數定案**。維護者裁決(2026-07-13):Sonnet 5 否決——CP 值不合(~$0.8/場+tokenizer×1.3+OpenRouter 需 cache_control 小改) |
| `select` | **升級**:`openai/gpt-5.4-mini`(保守替代 `gpt-5.4-nano` $0.20/$1.25) | 書記抽取正確性直接進文件;4o-mini 已兩代舊;5.4-mini 同價位帶最強 strict 系;換=重跑 `validate_select_schema` + 考卷(ADR 0024 紀律) |
| fallback(T13) | interview 備=A/B 敗者;select 備=`google/gemini-3.1-flash-lite` | 跨家備援;**先過考卷才填**(config 註記之紀律) |
| judge(Phase 2) | `google/gemini-3.1-pro-preview` | cross-model-family(引擎若用 Anthropic+OpenAI,裁判用第三家) |

**暫不採用**:`claude-sonnet-5`(維護者否決:CP 不合)、gpt-5.6 家族(GA 才 4 天,等穩+等考卷基準;luna 的 cached in $0.10 對前綴穩定 context 有利,下輪重評)、gpt-5.5/opus/fable(旗艦價位對本工作負載無對應增益)、gemini-3.5-flash($1.50/$9 在 CP 導向下輸 5.4-mini;留當第三候選)。

## 4. 換模行程(不改碼,照既有紀律)

1. 先換 `deepseek-v4-flash`(deadline 7/24;.env/config slug 一行)。
2. select:改 `model_select` → 跑 `scripts/validate_select_schema.py` 留紀錄 → 跑 T11 考卷。
3. interview:gpt-5.4-mini vs deepseek-v4-flash 各跑一輪 T11 考卷(deterministic 斷言+Simulated User 四 persona)+`interview_sim`,分數+人工試聊定案。
4. 勝者進 config、敗者(若分數可接受)進 fallback 欄。

## 5. 換模驗收紀錄(2026-07-13 實跑)

**探針發現(scratchpad probe,4 發實測)**:
- `openai/gpt-5.4-mini` **不支援 `temperature`**(reasoning 系;OpenRouter
  `supported_parameters` 無此項)——配 `require_parameters:true` 送了=404「No endpoints
  found」。去掉 temperature 即 200。
- **現役 bug**:`gpt-4.1-mini` 的參數表也沒列 `parallel_tool_calls`,T13 在
  `chat_with_tools` 顯式送它+require_parameters → **interview 回合整路 404**。
  OpenAI 官方(function-calling 指南):Chat Completions **預設即並行**,顯式送是冗餘。
- 修法(adapter):`sampling_params(model, t)` 濾掉 GPT-5/o 系的 temperature;
  `parallel_tool_calls` 不再顯式送(語義不變)。這是 require_parameters 的紀律:
  **只送關鍵參數(strict/tools),可選參數不送**(OpenRouter provider-selection 文件)。

**validate_select_schema(--target scribe,n=8,對抗性)**:
- `openai/gpt-5.4-mini`:**PASS,0 逃逸**,avg 1.15s;7/8 對抗誘導直接回 `none`
  (當非事實不記),1/8 只記合法池碼、丟非法碼。行為優於 4o-mini 基線。
- turn 靶已移除(v1 commands.py 隨 v3 顧問改 chat+tools 退役;受限解碼只剩書記一路)。

## 5.1 快取確認(2026-07-13 實證)

**規則(官方)**:OpenAI 經 OpenRouter **自動快取**(≥1024 tokens,前綴逐位元相同,
hash 涵蓋 messages+tools 定義+structured output schema;讀 0.25–0.5x);DeepSeek 自動
(讀 0.1x);Anthropic 要 `cache_control` 才有(現陣容已無 Anthropic,註記留 adapter)。
回報統一在 `usage.prompt_tokens_details.cached_tokens`(OpenRouter prompt-caching 文件+
OpenAI prompt-caching 指南)。

**實證探針(真實前綴 1=CONSULTANT_SYSTEM+總則教材,同前綴兩發)**:
- `gpt-4.1-mini`(interview 現役):第二發 **cached=1792/1919(93%)** ✅
- `gpt-5.4-mini`(select 新役):第二發 **cached=1792/1918** ✅
- `deepseek-v4-flash`:cached=0——OpenRouter 定價 $0.077(官方半價)表明路由到第三方
  託管,不走 DeepSeek 官方快取。cheap/deep/indicator 是一次性 read-only 提議、無重複
  前綴,**影響趨近零**;未來縫:要快取可 `provider.order=["deepseek"]` pin 官方(一行)。
- v4-flash 預設**未開 reasoning**(completion_tokens=6),行為同舊 deepseek-chat
  非思考模式——`/ai/*` JSON 解析路不受影響。

**碼側核對**:consultant 三層(前綴1 常數+前綴2 禁時間戳+動態在後)與 CONSULTANT_TOOLS
(模組常數)符合「靜態在前、變動在後」;`_record_usage`(openai SDK 路)與 `complete_text`
(langchain 路,本輪補)都記 `gen_ai.usage.cache_read.input_tokens`,快取命中率上線後
可直接從 trace 讀。未來縫(一行):動態區塊現排在對話窗**之前**,對話 tokens 永遠不進
快取;若把動態塊移到對話窗後可加深命中,屬 prompt 結構變更,須過考卷再動。

## 6. 未決/待確認

- gpt-5.6-luna 待生態穩定後可重評(cached in $0.10 對前綴穩定的 context 三層很有利)。
- deepseek-v4-flash 若 A/B 拿下 interview:確認 OpenRouter 路由商 tools/strict 支援面(T13 的 `require_parameters:true` 會自動過濾,但要看剩餘路由容量)。

## 來源總表

| 家 | 文件 | URL | 取用日 |
|---|---|---|---|
| OpenAI | API pricing(官方) | https://developers.openai.com/api/docs/pricing | 2026-07-13 |
| OpenAI | GPT-5.6 發布/GA | https://openai.com/index/gpt-5-6/ ; https://openai.com/index/previewing-gpt-5-6-sol/ | 2026-07-13 |
| Anthropic | Pricing(官方 docs) | https://platform.claude.com/docs/en/about-claude/pricing | 2026-07-13 |
| Google | Gemini API pricing(官方) | https://ai.google.dev/gemini-api/docs/pricing | 2026-07-13 |
| DeepSeek | Pricing + 舊名淘汰公告 | https://api-docs.deepseek.com/quick_start/pricing | 2026-07-13 |
| OpenRouter | gpt-5.4-mini / gemini-3.1-flash-lite / deepseek-v4-flash / gpt-4.1-mini 模型頁 | https://openrouter.ai/... | 2026-07-13 |
