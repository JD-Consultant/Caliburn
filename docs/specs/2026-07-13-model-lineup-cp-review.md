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

## 5. 未決/待確認

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
