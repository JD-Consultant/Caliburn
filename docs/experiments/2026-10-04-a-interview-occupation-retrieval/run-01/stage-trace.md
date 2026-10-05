# 已評為 3 的公版：排序階段追蹤

這是事後診斷，只追蹤本輪前五聯集內已有的 3 分公版；不是完整相關來源集合，不能計完整 Recall。沒有新搜尋、模型呼叫或評分，沒有依結果調參。名次均從 1 起算。

| 員工／公版 | 方法 | 每個查詢的全庫 dense 名次 → 該方法候選池內名次 | 合併名次 | 最終前五名次 |
|---|---|---|---:|---:|
| H02／零售業倉儲管理人員 | I01 | H02-initial-1: 2 → 2 | 2 | 2 |
| H02／零售業倉儲管理人員 | I02 | H02-initial-1: 2 → 3 | 3 | 3 |
| H02／零售業倉儲管理人員 | R01 | H02-whole-1: 5 → 5 | 5 | 5 |
| H02／零售業倉儲管理人員 | R02 | H02-whole-1: 5 → 2 | 2 | 2 |
| H02／零售業倉儲管理人員 | R03 | H02-segments-1: 3 → 3; H02-segments-2: 6 → 6; H02-segments-3: 1 → 1; H02-segments-4: 4 → 4 | 3 | 3 |
| H02／零售業倉儲管理人員 | R04 | H02-segments-1: 3 → 5; H02-segments-2: 6 → 4; H02-segments-3: 1 → 3; H02-segments-4: 4 → 5 | 4 | 4 |
| H02／電商物流中心理貨員 | I01 | H02-initial-1: 1 → 1 | 1 | 1 |
| H02／電商物流中心理貨員 | I02 | H02-initial-1: 1 → 2 | 2 | 2 |
| H02／電商物流中心理貨員 | R01 | H02-whole-1: 2 → 2 | 2 | 2 |
| H02／電商物流中心理貨員 | R02 | H02-whole-1: 2 → 3 | 3 | 3 |
| H02／電商物流中心理貨員 | R03 | H02-segments-1: 1 → 1; H02-segments-2: 1 → 1; H02-segments-3: 21 → 未入 N20; H02-segments-4: 2 → 2 | 1 | 1 |
| H02／電商物流中心理貨員 | R04 | H02-segments-1: 1 → 1; H02-segments-2: 1 → 3; H02-segments-3: 21 → 未入 N20; H02-segments-4: 2 → 3 | 3 | 3 |
| H03／採購助理 | I01 | H03-initial-1: 1 → 1 | 1 | 1 |
| H03／採購助理 | I02 | H03-initial-1: 1 → 5 | 5 | 5 |
| H03／採購助理 | R01 | H03-whole-1: 4 → 4 | 4 | 4 |
| H03／採購助理 | R02 | H03-whole-1: 4 → 2 | 2 | 2 |
| H03／採購助理 | R03 | H03-segments-1: 2 → 2; H03-segments-2: 13 → 13; H03-segments-3: 5 → 5; H03-segments-4: 1 → 1; H03-segments-5: 5 → 5 | 2 | 2 |
| H03／採購助理 | R04 | H03-segments-1: 2 → 3; H03-segments-2: 13 → 1; H03-segments-3: 5 → 3; H03-segments-4: 1 → 2; H03-segments-5: 5 → 2 | 2 | 2 |

機讀原件：[known-strong-reference-stage-trace.json](known-strong-reference-stage-trace.json)。
