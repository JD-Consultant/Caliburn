# TI-09-known-correction 裁決紀錄

## 目的與產品風險

更正沒有 supersede 舊事實時,JD 會保留錯誤頻率——資料完整性風險。

## required/optional/forbidden 標註依據

單筆 required correction,exact target=prior-inventory-report-frequency。

## 合法語意變體與不可接受強化

引文取全句或「是每月寄一次庫存報表」皆可;不指向 prior、或另立新頻率事實而不更正,皆 critical。

## qualifier 與 correction target 裁決

per_month 必須逐字支持;correction target 由 binding 注入。

## 審核

- maintainer 自審(adjudicated_by_maintainer),2026-07-18。
- 尚無 domain reviewer;pilot_only=true,不冒稱 SME 標註。

## 已知限制

- synthetic constructed_edge,非真實訪談語料;challenge split 由
  maintainer 自建,非真 blind held-out(計畫 §15.6)。
