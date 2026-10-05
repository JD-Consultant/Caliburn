# 員工整體工作 → 職位候選：第二輪驗證

狀態：2026-10-04完成隔離合成驗證；固定前輪候選，沒有重選模型、表示法、方法或參數，沒有接正式JD App。

**搜尋能找出候選，但不能直接把第一名當員工職位。** 新8個正例的主要參考職位，B2與原話都進前五名；B2第一名符合預先主要標註4/8，原話5/8。新holdout中B2是3/4，原話4/4。兩種輸入整體nDCG幾乎相同，這輪不能宣告B2全面較好，也不依holdout反過來切換方案。

新6個負例都低於先前已被否定的0.675規則；這不消除前輪不足案例0.698433的反例，**正式接受門檻仍未定**。本輪沒有空B2，負例也產生了有未知界線的B2；沒有門檻或其他判斷時，最近鄰搜尋仍會給出職位候選。

## 怎麼測

- [生成前protocol](protocol.md)固定14情境：development/holdout各4正例、2資訊不足、1公版無適當主要參考。holdout正例領域不與development/前輪主要probes重疊；是新合成保留資料，不是真人或專家ground truth。
- [cases.json](cases.json)先標分、界線與難例，再[只讀複核](label-review.md)，再凍結hash。grade3是主要參考、grade2可接受相關、grade1弱相關；grade0僅未標註，不能當全部無關。主要參考不表示員工已符合標準全部任務。
- 每情境3段員工原話與3段一般提問，截止seq6，透過現行B1→B2→發布流程；預期職位、grades、domain與rationale沒有送入模型。使用gpt-6-luna/high，短訪談，不是長旅程或完整JD驗證。
- 固定同一805職位、BGE-M3 revision 5617a9f61b028005a4858fdac845db406aefb181、FP16/1024維及TOP正文，Qdrant exact cosine、候選top10。JSON是保存結構；embedding讀職能概述及T/O/P正文，職位名稱留在metadata，不額外拼入文本；移除OPKS代碼/表頭，保留項目名稱。K/S不在本輪固定候選中。
- B2查詢只用已發布body並核精確B1 revision；原話全文是診斷基準，不是另一個已選方案。這輪沒有重新比較DB產品、ANN、reranker或調參。新結果、cache皆另存，前輪132封存檔hash未改。

## 正例結果

Hit以grade≥2計算，nDCG用全部分級；負例不混進正例平均。以下同時保留主要職位排名，避免將任一相關任務命中當整體職位判對。

| 輸入/集合 | 正例 | Hit@1 | Hit@5 | Hit@10 | MRR | nDCG@10 | 主要參考進top10 |
|---|---:|---:|---:|---:|---:|---:|---:|
| B2/development | 4 | 0.250 | 1.000 | 1.000 | 0.500 | 0.632050 | 4/4 |
| B2/holdout | 4 | 0.750 | 1.000 | 1.000 | 0.875 | 0.925353 | 4/4 |
| B2/all | 8 | 0.500 | 1.000 | 1.000 | 0.688 | 0.778702 | 8/8 |
| raw_employee/development | 4 | 0.250 | 1.000 | 1.000 | 0.475 | 0.555034 | 4/4 |
| raw_employee/holdout | 4 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000000 | 4/4 |
| raw_employee/all | 8 | 0.625 | 1.000 | 1.000 | 0.738 | 0.777517 | 8/8 |

固定top10保留，沒有因本輪全進top5而回調k。整體B2 nDCG 0.778702、原話0.777517，差0.001184；development較有利B2，holdout較有利原話。短且整理好的合成原話，不代表長訪談原文也有相同表現。

| 案例 | 主要參考（凍結） | B2主要rank | 原話主要rank | B2第一名 | 第一名cosine |
|---|---|---:|---:|---|---:|
| E01 | 小型汽車維修廠技術人員 (SET7231-002v3) | 2 | 2 | 小型汽車售後服務接待人員 | 0.720705 |
| E02 | CNC車床技術人員 (MPM7223-002v3) | 4 | 5 | 高速車床技術人員 | 0.770105 |
| E03 | 西點、麵包烘焙助理 (TFB7912-002v3) | 1 | 1 | 西點、麵包烘焙助理 | 0.784943 |
| E04 | 網路資訊安全人員 (INM3513-001v4) | 4 | 5 | 網路建置維護人員 | 0.731146 |
| E05 | 房務人員 (THM9112-001v3) | 1 | 1 | 房務人員 | 0.767545 |
| E06 | 蔬菜育苗智慧生產人員 (NAO6010-003v3) | 1 | 1 | 蔬菜育苗智慧生產人員 | 0.774816 |
| E07 | 銲接技術人員 (MPM7212-001v3) | 2 | 1 | 機械設備銲接工程人員 | 0.788856 |
| E08 | 寵物美容專業人員 (PIC5193-001v3) | 1 | 1 | 寵物美容專業人員 | 0.798872 |

**職責界線反例：** E01本人明說不負責接待報價，B2亦保留，但搜尋第一名是小型汽車售後服務接待人員（0.720705），維修廠技術人員在第二名（0.711336，精確值見排名）。E07第一名是涵蓋更廣製造/設計的機械設備銲接工程人員，凍結為grade1；主要銲接技術人員第二。共享工作詞及正文範圍會影響cosine，高分本身無法證明主要職責或決定權符合。未標註的近似職位可有其他合理關聯，本輪沒有事後改grades來提高分數。

## 負例與門檻

| 案例 | 類型 | B2第一名 | B2最高cosine | 原話最高cosine | 0.675是否接受B2 |
|---|---|---|---:|---:|---|
| E09 | 資訊不足 | 綜合零售業商品採購人員 | 0.656818 | 0.654170 | 否 |
| E10 | 資訊不足 | 工藝產業產品經理 | 0.652744 | 0.674180 | 否 |
| E11 | 805公版無適當主要參考 | 測量工程人員【註1】 | 0.631619 | 0.640497 | 否 |
| E12 | 資訊不足 | 音樂(唱片)製作人 | 0.647577 | 0.671071 | 否 |
| E13 | 資訊不足 | 綜合零售業商品採購人員 | 0.610682 | 0.614218 | 否 |
| E14 | 805公版無適當主要參考 | 木質文物修護技術助理人員 | 0.641454 | 0.623995 | 否 |

固定舊規則在本輪保留8/8正例輸入、誤接受0/6負例；這只檢查是否給候選，不代表給出的第一名正確。全部14例B2非空，沒有以空查詢拒絕而提高負例成績。空B2正例仍算0分的行為另有guard測試。

先前[0.675反例](../2026-10-04-occupation-retrieval/candidate-01/threshold.json)仍是0.698433：資訊不足卻會接受。因此本輪不能把0.675升格正式規則，也不能把cosine乘100解作員工職位符合率。資訊不足、資料庫缺主要參考、近似職位權責不符，是不同問題。

## Memory品質及資料庫核對

14例已發布，所有B2精確引用的B1 revision及B1員工來源均核對。逐例人讀原話的[part1](memory-review-part1.md)、[part2](memory-review-part2.md)、[part3](memory-review-part3.md)保留結論；四個Minor（E02/E03/E06頻率措辭、E14研究步驟先後）原樣保留，不修模型輸出或重跑；未見改變核心工作或決定權的重大錯誤，不能宣稱所有細節無誤。非空B2仍可能明列未知，不能把「Memory已完成」當「職務已完整」。

逐點核Qdrant 805個payload及dense向量，再核28次exact查詢，每次前十名的足額、唯一、有序、分數與同分容許排名均與NumPy一致。[離線驗證](verification.json)重算28份完整805排名、metrics與摘要，並核原始cache prefix、原話/labels與309份生成時來源。這證明已保存結果與精確搜尋一致，不證明語意標註全面正確或ANN效能。

## 用量、失敗及重現

現行Luna/high共116次生成、input 482,982（cached 404,922）、output 33,918。按[2026-10-04官方標準價](https://developers.openai.com/api/docs/pricing)估US$0.028814；將全部input按最高短context cache-write率估的保守上界US$0.077332，低於US$2。不是官方帳單。

run-01因Windows Proactor不支援psycopg async，在0模型呼叫時停止，失敗原件/schema保留；改用既有研究harness的Selector後run-02完成，沒有成功案例重跑。公開trace排除私人推理及加密內容（只留hash/長度），不含金鑰。

只用既有loopback研究_test DB與兩個隨機eval_occ2_schema，schema與快照保留。驗證後只停止本輪自有embedding/Qdrant；既有研究PostgreSQL保留，實際狀態見[service-state.json](service-state.json)。

```powershell
& 'apps/ocs-indexer/.venv/Scripts/python.exe' -X utf8 -m pytest 'docs/experiments/2026-10-04-occupation-retrieval-generalization/test_support.py' 'docs/experiments/2026-10-04-occupation-retrieval-generalization/test_audit.py' -q -p no:cacheprovider
& 'apps/ocs-indexer/.venv/Scripts/python.exe' -X utf8 'docs/experiments/2026-10-04-occupation-retrieval-generalization/verify.py' --check-seal
```

最終[獨立審查](final-review.md)補上top1摘要及漏例/重複的audit反例，實際保存結果未改。離線重算不呼叫模型、不需啟服務。[test-evidence.json](test-evidence.json)記11個guards（7個準備/評分、4個audit錯改反例），沒有把測試通過說成語意品質已達標。

## 原件位置

- [run-02/manifest.json](run-02/manifest.json)、supporting-sources.json：生成前條件、指引全文、所有用到的來源。
- [run-02/trace.jsonl](run-02/trace.jsonl)、capture.jsonl、E01～E14/messages.json與snapshot.json：公開請求/回應、每個scope/快照與原話。
- [run-02/source-evidence.json](run-02/source-evidence.json)：從PG只讀匯出的來源UUID/seq/speaker及published head。
- [queries](run-02/retrieval/queries.json)、[全部排名](run-02/retrieval/fixed-rankings.jsonl)、[CSV](run-02/retrieval/metrics.csv)、[摘要](run-02/retrieval/summary.json)、[資料庫核對](run-02/retrieval/database-checks.json)：28份配對結果。
- cache/*.jsonl：保留原2454筆及新28筆向量/文字hash/token；[artifact-hashes.json](artifact-hashes.json)封存本輪原件，verification.json排除以允許重算。

## 本輪決定與未完事項

維持B2＋TOP＋exact dense＋top10作為固定研究候選，證據支持跨這8類工作找出主要候選。沒有把它採納為正式架構，沒有宣告B2比原話全面較好；需要更接近實際且含分散、更正及多職混合的獨立案例，再比較最終輸入選擇。

下一個有證據的問題是主要職位判定：如何用本人已確認工作與決定權，排除只有交接詞相近或範圍更寬的參考，以及何時應繼續詢問或承認公版未涵蓋。正式接受參數需在另批資料上固定/校準/驗證，不能回用本輪holdout調完再稱通過。

JD任務覆蓋與訪談結束仍未實作／驗證；即使主要參考進top10，也不代表底下全部任務已問過、員工已說完或JD已完整。805公版的官方最新身分/全部逐字品質也仍依前輪限制，不能由這輪排名驗收取代。
