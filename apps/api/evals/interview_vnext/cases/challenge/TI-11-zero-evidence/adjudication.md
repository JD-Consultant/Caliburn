# TI-11-zero-evidence 裁決紀錄

## 目的與產品風險

零證據回合必須是 typed no-op;把閒聊寫進 JD 是明確污染。

## required/optional/forbidden 標註依據

無 required observation;必須回報 no_work_fact。

## 合法語意變體與不可接受強化

user_signal 標 dont_know/decline/off_topic/mixed 皆可;任何 observation 都是 false positive。

## qualifier 與 correction target 裁決

不適用;state hash 三次都必須不變。

## 審核

- maintainer 自審(adjudicated_by_maintainer),2026-07-18。
- 尚無 domain reviewer;pilot_only=true,不冒稱 SME 標註。

## 已知限制

- synthetic constructed_edge,非真實訪談語料;challenge split 由
  maintainer 自建,非真 blind held-out(計畫 §15.6)。
