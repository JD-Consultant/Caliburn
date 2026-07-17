# TI-07-responsibility-boundary 裁決紀錄

## 目的與產品風險

責任邊界錯置會把協助角色寫成完整職責,直接高估職等。

## required/optional/forbidden 標註依據

shared/assists/other-owner 三個邊界各一筆 required。

## 合法語意變體與不可接受強化

subject 用 employee_team 或 employee(搭配 shared)皆可;員工獨占最終送出為 critical。

## qualifier 與 correction target 裁決

ownership 是本 case 的主要計分欄位。

## 審核

- maintainer 自審(adjudicated_by_maintainer),2026-07-18。
- 尚無 domain reviewer;pilot_only=true,不冒稱 SME 標註。

## 已知限制

- synthetic constructed_edge,非真實訪談語料;challenge split 由
  maintainer 自建,非真 blind held-out(計畫 §15.6)。
