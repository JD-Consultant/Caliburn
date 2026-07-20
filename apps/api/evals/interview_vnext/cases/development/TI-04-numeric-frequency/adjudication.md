# TI-04-numeric-frequency 裁決紀錄

## 目的與產品風險

數字頻率是 verifier unsupported_quantification 的直接對象。

## required/optional/forbidden 標註依據

單一 required,kind 放寬 action/frequency;value=2、unit=per_month。

## 合法語意變體與不可接受強化

「每月兩次盤點庫存」語意等價;每週/每日、或新增數字皆 critical。

## qualifier 與 correction target 裁決

frequency value 取字串 "2",verbatim 含「每月」。

## 審核

- maintainer 自審(adjudicated_by_maintainer),2026-07-18。
- 尚無 domain reviewer;pilot_only=true,不冒稱 SME 標註。

## 已知限制

- synthetic constructed_edge,非真實訪談語料;challenge split 由
  maintainer 自建,非真 blind held-out(計畫 §15.6)。
