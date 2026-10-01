# 較早的有界實驗資料（2026-10-01 以前，T14／T16／T17）

這些是各次有界真模型實驗的**原始輸出**，由當時的探針或 `scripts/simulate_interview.py` 產生，**位元組不變地**從本機忽略目錄複製進來，供專題報告引用與重新核對。全部是合成資料（沒有真實員工、repo 內容或 Demo 資料），不含金鑰與 provider 的不透明 reasoning（探針只保存安全欄位）。每一組的目的、範圍、結論與限制以對應的任務證據頁為準；本頁只是索引，不是第二份結論。

雜湊見 [`SHA256SUMS.txt`](SHA256SUMS.txt)（在本目錄執行 `sha256sum -c SHA256SUMS.txt` 可核對）。證據頁若記載了某檔的雜湊，應與此一致。

## 舊預設 medium 的課程行政／倉庫六組 12 輪訪談基準

Q1 之前的基準；T17〈接手只處理影響成稿的兩個反例〉。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `b0-course_admin-1.json` | 59,650 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `b0-course_admin-2.json` | 16,126 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md)、[t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `b0-course_admin-3.json` | 52,473 | （同組） |
| `b0-warehouse-1.json` | 46,678 | （同組） |
| `b0-warehouse-2.json` | 58,699 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `b0-warehouse-3.json` | 49,814 | （同組） |

## 同一核心旅程改用 GPT-6.1 Sol／high 的對照

Owner 因成本維持 Luna；T14〈較高能力模型的核心 App 旅程對照〉。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `core-journey-sol-20261001.json` | 238,460 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md)、[t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `core-journey-sol-context-20261001.json` | 8,260 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `core-journey-sol-review-20261001.json` | 22,828 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |

## 核心 App 旅程與知識技能／更正的真後端驗證

T14、T17。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `core-capabilities-high-20261001.json` | 63,520 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `core-capabilities-high-retry-20261001.json` | 91,016 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `core-corrections-20261001.json` | 3,521 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `core-corrections-source-20261001.json` | 11,877 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `core-journey-20261001.json` | 47,821 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md)、[t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `core-journey-high-20261001.json` | 51,259 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |

## JD 來源選項 description 的有限比較

T14〈來源選項的參數語意對照〉，未採用。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `jd-tool-descriptions-20261001.json` | 95 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `jd-tool-descriptions-direct-20261001.json` | 7,943 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |

## Luna 長訪談收尾的有界接續

T17。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `luna-closing-turn-20261001.json` | 170,965 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |

## Memory 換版／人工改稿與來源保留的定向驗收

T17。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `memory-jd-recheck-luna-20261001.json` | 7,749 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `memory-jd-recheck-luna-audit-20261001.json` | 16,134 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `memory-jd-recheck-luna-network-20261001.json` | 10,094 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `source-only-recheck-luna-20261001.json` | 14,129 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `source-only-recheck-luna-audit-20261001.json` | 27,514 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |
| `source-retention-20261001.json` | 10,779 | [t17-course-administrator-journey](../../t17-course-administrator-journey.md) |

## 來源選擇診斷：壓縮、模型能力、欄位順序、範圍

T14，均未採用。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `source-compaction-20261001.jsonl` | 5,366 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `source-model-20261001.jsonl` | 6,258 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `source-order-20261001.jsonl` | 8,212 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `source-scope-20261001.jsonl` | 4,834 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |

## 推理 effort、B1 資訊精度與 Memory 品質的有限診斷

T14。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `luna-xhigh-20261001.jsonl` | 4,289 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `memory-quality-20261001.jsonl` | 81,709 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `reasoning-effort-high-20261001.jsonl` | 7,337 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `situation-precision-20261001.jsonl` | 1,133 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `situation-precision-network-20261001.jsonl` | 3,321 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |
| `situation-precision-remaining-20261001.jsonl` | 9,899 | [t14-job-analysis-quality](../../t14-job-analysis-quality.md) |

## 壓縮、輪前準備與帳戶額度的 provider 探針

T16；`step-160k` 是 160K 中途保險的真窗口驗收。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `a-preparation-count-diagnostic-20261001.json` | 168 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `a-preparation-native-provider-20261001.jsonl` | 4,002 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `a-preparation-offline-20261001.jsonl` | 1,322 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `a-preparation-offline-fixed-20261001.jsonl` | 2,362 | （同組） |
| `a-preparation-offline-native-20261001.jsonl` | 3,790 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `a-preparation-offline-ready-20261001.jsonl` | 3,790 | （同組） |
| `a-preparation-provider-20261001.jsonl` | 1,578 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `a-preparation-provider-network-20261001.jsonl` | 1,697 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `a-preparation-provider-valid-20261001.jsonl` | 1,697 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `compaction-continuity-20261001.jsonl` | 1,227 | [2026-09-30-pause-handoff](../../2026-09-30-pause-handoff.md)、[t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `compaction-continuity-followup-20261001.jsonl` | 6,643 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `luna-rate-headers-20261001.jsonl` | 1,439 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `preparation-quota-20261001.jsonl` | 3,948 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `runtime-compaction-20261001.jsonl` | 2,017 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |
| `step-160k-20261001.jsonl` | 4,298 | [t16-compaction-continuity](../../t16-compaction-continuity.md) |

## 早期課程行政冒煙

T17。

| 檔案 | 位元組 | 提及它的證據頁 |
|---|---|---|
| `smoke-course_admin.json` | 15,864 | （同組） |
