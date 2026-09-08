# CT47：編輯指引局部候選

LLM-Q019／G5；Owner已授權局部prompt／同Luna effort調整。沿[CT45](../specs/2026-09-09-ct45-fixed-long-interview-results.md)失敗；CT46 xhigh同12cap仍失敗（12次估US$0.02371122，原PG未變），不再盲目提高effort或cap。

## 已核對與候選

完整閱讀安裝的OpenAI SDK `agents/apply_diff.py`（400行），其`_parse_update_diff`逐hunk更新cursor並只向後找，`_apply_chunks`拒重疊。CT46 #2各ID原本正確，但先改後方案例，再回上方引用，因此Invalid Context17；#6、8才另有ID抄錯。不是所有失敗都同根因，也不改matcher。SDK公開來源及既有接線見[CT11](../specs/2026-09-07-official-memory-patch-trial-results.md)；[官方patch harness](https://developers.openai.com/api/docs/guides/tools-apply-patch#implementing-the-patch-harness)規定回傳精確成功／失敗供模型修訂，不保證會成功。

只換一組**編輯操作指引**：短且全文可見、多處與引用要改時用現有write_file；小修改patch帶必要實際context，不抄無關長引用；同diff各hunk按原文先後；失敗後重讀，若仍要大段重抄、全文可見且輸出放得下就改whole-write。保留舊內容／引用与所有既有不確定、案例區分、引用驗證規則。這是依[GPT-5.6提示指南](https://developers.openai.com/api/docs/guides/prompt-guidance-gpt-5p6)的局部tool-routing校準，不宣稱每廠prompt相同。

## 驗證

- RED已有CT45 high與CT46 xhigh真實失敗；候選只在隔離replay程序注入，不修改product src，無新模型欄位／schema／tools。
- 回到high、相同CT45第8輪B1＋写前正文導覽、原12／12與8192；新24次／US$0.15有界帳本，原PG唯讀、官方Store/Saver複本。不重跑B1／訪談、不傳真實員工資料。
- 要核對發布、工具錯誤、內容保留、真實來源與guide；既有Q02錯引若沿用，不可稱已修复。不要把一次通過當成功率。
- 成功才考慮接入、以既有整體回歸驗接線及失敗恢復，再做新補充與完整訪談；不靠prompt文字存在的單元斷言冒充模型行為測試。
- 若仍不行，保留失敗重新查根因；不在未研究下加validator／Agent或换storage。

## 同候選額度對照（新增證據後）

第一次候選high在12步仍失敗；未再出現UUID抄錯／逆序hunk，但#7少列表前綴被拒，#10修正後#12又預檢，沒有剩餘final模型步。原失敗保留，不將格式檢查當發布。第二個**獨立複本**只把B2提高至16模型／15工具；不是resume、不是重新抽取、提示不變。尚未closed的CT47帳本上限24→32，USD0.15不變，記event；Owner已授權局部額度調整。不能從單次軌跡宣稱16是最佳值，仍看實際完成與內容、來源品質。
