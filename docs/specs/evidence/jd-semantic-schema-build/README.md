# v2 設計補正的重現材料

[build-v2.cjs](build-v2.cjs)記錄本輪如何從固定v1候選形成v2。執行前驗v1 SHA256為`ced26a3b625de891989a63d5f12e4ac884484083d7f677cf10ad8c54e318b973`，不修改v1或舊證據。

本腳本是**一次設計補正的歷史重現材料**，不是runtime、資料migration或後續codegen入口。後續唯一可編輯的active SSOT是[正式v2候選](../../contracts/jd-editor-v2.schema.json)；Task 1從該schema生成DTO，不從本腳本或v1重新產生文件格式。未來修改v2後不可再用本腳本覆蓋新決定。

本輪初次生成後由獨立review指出兩處v1顯示文字殘留（title及document description），已修正；不涉及grammar反例。最終105 defs，schema SHA256為`c6cc0f996b7a24b37cdf784a9d46e88cbb1d59f4d68d327e4167f3dfa40fb715`。有限驗證及後續範圍見[語意契約](../2026-09-10-jd-semantic-contract-closure.md)。

[整合核對腳本](check-integrated-evidence.cjs)唯讀比較新原生結果／完整fixture與active schema，以及SDK capture的三工具參數／說明；[結果](integrated-results.json)為16項0失敗。可從repo root以`node docs/specs/evidence/jd-semantic-schema-build/check-integrated-evidence.cjs`重現；不呼叫模型／DB，也不把shape能接受orphan誤當引用已驗。
