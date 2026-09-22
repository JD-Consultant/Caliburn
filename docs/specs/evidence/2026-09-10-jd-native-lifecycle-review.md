# JD native lifecycle 有限 G4 獨立 review

日期：2026-09-10。範圍：只審 `docs/specs/2026-09-10-jd-native-process-lifecycle-design.md` 與必要現行原碼／ER03。未施工、未跑模型、未提交，未修改原設計／register／plan。Task 2 `23bf0161` 的通過不重開；Task 3 三工具接線可繼續。

**判定：安全／authority spec PASS；作為完整 Task 5 restart 可執行設計，quality CHANGES REQUIRED。** 下列 NL-R01／NL-R02 是有限文件補正及後續驗收要求，不是要求先做通用 supervisor，也不是 Task 3 阻擋。

## 已核對且成立

- 每文件保留 native calls，call register 先於 spawn，Popen／I/O thread 的 owner 跨越工具返回，是合理的最小同程序解法。不是第二份 JD／Memory authority；不要將 ephemeral registry 寫成 operation running 表。
- 實際 `jd_engine.py:99–108` 的 BaseException 忽略 reap 回值、正常路徑 I/O 尚活仍拋預設 quiescent=True，確實支持 Task 5 統一 owner 的需求。`jd_service.py` typed read failure 亦不可抹除清理責任。exit 和 pipe/thread cleanup 要分開驗。
- Node 固定 bridge 沒有 DB 接線；`JdStore.publish` 才是 Python writer。失去 Node handle 造成停止證據不足，不代表 Node 能自行 commit。Node stopped 同樣不能證明 SQL 已 abort。稿件這項區分正確。
- 所有 pending binding 都須對帳，包含已有 provisional unconfirmed ToolMessage 或 child terminal。既有 `conversation.py:210–211,227–236` 會早退／略過 paired call，故 Task 5 必須改，而不是只在 missing ToolMessage 分支補 JD handler。沿 checkpoint 更新閉合資訊、不改寫歷史訊息／不重複 ToolMessage，是可落地的方向。
- receipt 前 cleanup 不變量只涵蓋該 operation；稿件已明文禁止以 receipt／Future.done／空 registry／PID／API port 直接解整文件 gate。failure receipt 也要遵守；尚未實作的新不變量不得回套 Task 2 舊 receipts。

## NL-R01 — 明確化 normal restart 的其餘 call 覆蓋證據

- 位置：原稿 §6 表格第 86–87 行、§8 NL05／NL07／NL10（133–138 行）。
- 原契約：ER03 §4.4 的全部 writer quiescent＋已發配 operation 閉合＋turn closure；原稿 §4.1 包含 selection／manual 的全部 native call。
- 缺口：第 86 行「查明其餘 pending calls／read 原生工作」「無其他 outstanding」目前是正確條件，卻沒有指定 restart 後用什麼有限資料證明**覆蓋完整**。read 只有 ephemeral token；manual／create 亦不必有 AI binding。舊 edit 有 receipt，不會使後來或並行的 selection 具有可恢復 handle／停止記錄。新 API 不可能從空 registry 補出那份全集。
- 反例：edit A 成功留下 receipt；同文件 selection B 進 Node（或返回 read_failed 但清理未完成）；API crash。A 可閉合，B 的停止仍 unknown。僅枚舉 write bindings／receipts 並全部 closed，不能解 gate。
- 產品影響：實作者若把第 86 行當一般 receipt restart 通道，可能錯誤解鎖；若一概無法回答，則正常可證明 restart 也會被不必要封住。
- 要求：把該行改成明確條件分支：受控 orderly shutdown 的完整清理／閉合證據，或具體 admission 序列與該輪所有 native-capable call 的 durable 邊界足以證明沒有其他未清理工作；沒有覆蓋證據就沿 uncertain 出口。**本輪不要求新增持久 process store**，可以明列哪種 restart 暫不支援。Task 5 用 A receipt＋B read pending 反例，以及無 B 的可證明正常閉合正例驗證。不把取得 A 的 receipt 當 B 的 proof。

### saved not-started 的精確適用條件

已安裝官方 `langchain/agents/factory.py:1663–1665,1705–1720,1787–1800` 讓最後一個 after_model 節點路由工具；`langgraph/pregel/main.py:2964–2989` 在 sync durability 等 checkpoint 完成才進下一 step。現行 `service.py:275`／`conversation.py:291` 使用 sync。

因此，對同一 latest child、同一目前 AI response，若持久 next 仍是**已知、無原生副作用、位於 tools 前的 after_model 節點**，且舊 Python 確認停止，確可證明該 response 尚未進 tools。不是一律不可信。但「binding 已保存」「saved next=tools」「沒有 task.error／receipt」皆不能證明未開始。還須排除較早 call、其他入口與自訂路由。建議將這些條件寫進 §6／NL01，勿僅照抄 `endswith('.after_model')` 作未來所有 middleware 的白名單。這是 NL-R01 的 proof 精確化，不另重開 framework 選型。

## NL-R02 — 缺 handle 的維運範圍不只極端 unreap

- 位置：原稿 §6.1 A，第 100 行「失去 handle 且缺 durable proof 的極端案例須維運」，及第 92–94 行出口敘述。
- 原契約：ER03 §4.2／4.4 明示可恢復入口、停止 spinner、零自動重播；G4 必須把代表性失敗與產品限制寫清楚。
- 缺口：這個窗口不需要 terminate／kill 皆失敗。一般 API 在 Node transform 中、native 正常退出後但 receipt 前、或 SQL 回覆未知且無 durable 停止證據時 crash，都可能落入 A 的維運分支。沒有證據可以把頻率或觸發條件縮成「極端 unreap」。反過來，orderly close、同程序 retained handle 清理成功、具有完整 scope proof 的 receipt restart 不應一律被擋。
- 產品影響：若據此當成只影響罕見 OS 異常，會低估一般 API restart 的人工恢復限制；現有 A 尚未提供可執行維運入口，不能稱可恢復成品。
- 要求：改成按可觀察 crash 窗口分類，明列 A 暫缺的出口與下一個有界 task。可先完成同程序 owner、orderly shutdown、operation receipt reconcile；另以一個受控 Python crash 的固定 barrier 案例確認上述缺證據窗口，回寫恢復出口狀態。再由相應 gate 決定接受明示維運限制並補可信入口，或定點設計有限啟動 owner。Windows Job Object 仍只可列候選；不要求先造 scheduler／通用 supervisor／DB lease。完整 OS reboot 也只能是待設計／授權的維運候選，不是既有自助功能。

## Task 3 與 Task 5 的必要分工

Task 3 現在確實需要：

1. 同一 JdToolSession／factory 綁定 exact request、digest、base、saved input／AI／tool identity；before-Node 持久 binding，非 handler 最末才保存。
2. 同文件既有 stop Event 傳至 JD wrapper／JdService 的實際 engine cancel 接點；selection 需要相同參數傳遞時可作窄 seam 補齊。維持三工具 schema、原 call ID 與正式描述。
3. 對 unconfirmed／reconcile_operation 阻止下一 JD intent／模型迴圈；保留 durable pending binding，不因已有 ToolMessage 標閉合。
4. 留可接受 owner 的內部 port／型別與明確 README 限制即可。若 owner 本體留 Task 5，Task 3 不應把空物件注入 runtime 後稱已追蹤 Popen；測到「同一物件傳到 adapter」僅證明 forwarding。

**完整留 Task 5**：實際 register／spawn／handle／pipe retention；publish 前 cleanup＋cancel 重核；manual／create admission（create 尚無持久文件 ID，要指定暫存入口 owner 或預配 ID 的映射）；兩階段鎖／generation；全部 close／startup／shutdown／abandon 路徑；全 binding reconcile；restart proof／明示恢復 UI；NL02–12 故障與跨程序驗收。若未做實際 owner，production seam 的 fail-closed 保證亦尚未成立，不能以 stub 宣稱完成。

第 7 行仍寫 Task 2 review／Task 3 尚未施工，與 current register 已前進狀態不符，主工作單位採用時順手更正；不構成新設計阻擋。

## 有界 closure

完成 NL-R01 的 proof 分支／反例與 NL-R02 的實際 crash 窗口分類，即可窄複核文件。Task 3 繼續既定接線；Task 5 的 owner 與 restart 故障驗收才產生實作通過證據。沒有必要重啟廣搜或先採 Job Object。此次 review 未主張任意 crash 自助完成，亦未要求讓所有一般 restart 永久 uncertain。

# 2026-09-10 窄複核：§6.1–6.6 修訂

**判定：NL-R01 CLOSED、NL-R02 CLOSED；本次有限設計 Spec PASS／quality PASS。** 推薦 B 仍須相應採用 gate／隔離實作與真故障測試；本判定不代表 Windows／PG restart 已實測，也不回套 Task 2 receipts。沒有新增設計阻擋，以下列出成立條件及 Task 5 必驗接點。

## 修訂是否回答原 finding

- NL-R01：§6.3 的整 App kernel job proof 覆蓋舊 API 與全部 Node，§6.4 明列 AI、HTTP selection、manual、create，已不再試圖用 edit receipt 枚舉 read。無其他 call 與 A receipt＋B pending 的正反例均有明確判斷。saved not-started 已限定同一 latest child／AI response／sync／已知無副作用節點，排除任意 suffix、next=tools 與較早 call。原缺口閉合。
- NL-R02：§6.1／6.6 明列 transform 中、transform 後 receipt 前、SQL／COMMIT 等一般 crash 窗口；A 只是施工中間狀態，B 提供有限恢復流程。未把 ordinary crash 歸為 unreap 極端，未以 OS reboot／手按確認代替 proof。原缺口閉合。

## Job／mutex 的定點官方核對

[CreateJobObjectW](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-createjobobjectw) 說明既存名稱回同一 object、ERROR_ALREADY_EXISTS、NULL security attributes 不繼承 handle、最後 handle／成員退出的銷毀條件及 kill-on-close。[AssignProcessToJobObject](https://learn.microsoft.com/en-us/windows/win32/api/jobapi2/nf-jobapi2-assignprocesstojobobject) 支持 Windows 8+ nested job、子程序預設繼承 job chain，並明列 terminating job 不可加入；本稿的先加入自身、後 spawn Node 可消除逐 Node assign gap。這是 membership，並非把 job handle 傳给 Node。

[ActiveProcesses](https://learn.microsoft.com/en-us/windows/win32/api/winnt/ns-winnt-jobobject_basic_accounting_information) 下降需程序退出且 process references 釋放，因此 0 是保守的完整停止證據，非 0 不等於仍可能寫 DB。現稿已承認 reference 拖延並提供有界失敗。[WaitForSingleObject](https://learn.microsoft.com/en-us/windows/win32/api/synchapi/nf-synchapi-waitforsingleobject) 的 abandoned mutex 只涉及 owning thread 終止，不能證明 API 全退；現稿已在取得 mutex 後仍核舊 job。

據此，B 的因果鏈在**所有入口不繞過 bootstrap、同安裝 key／session、私有 ACL、無 breakaway／handle 洩漏、舊版受控切換**下成立。新 API 清舊 job 時未加入、不重用 terminating object、自身 job handle 保留到 process 最终退出，是必要細節；現在均已明列。nested job 成功是本機需驗的相容條件，失敗時不可 fallback。API 整組死亡會波及兩文件，現稿亦明示此代價，未冒稱每文件 OS 隔離。

## head-lock known-none 的界線

已對照現行 `JdStore.publish`：同一交易先 head FOR UPDATE，之後才 mutation／receipt；同步 execute，無 pipeline。[PG16 row locks](https://www.postgresql.org/docs/16/explicit-locking.html) 支持衝突 lock 等到交易結束。

在 job proof 已確認舊 Python 無法再發語句後，新交易成功取得 head lock，再以後續 statement 查 scoped operation，的確可區分原 transaction 已發布或 known-none。若舊 backend 尚等 lock，死亡 Python 也不能在鎖取得後再發 mutation；如果 mutation／COMMIT 已送，原交易仍持 lock 到結束，新 reader 會越過該邊界。這是依固定語句順序的本案推論，不是一般 receipt absence 的保證。

故此限定 port 合理；SQL pipeline、先 mutation 後鎖、其他 bypass writer 任何一項改變就要重開 proof。receipt lookup 與 failure closure 仍分階段／分預算；clear descriptor 只能發生在確認 terminal 後。不能用 alive/closed connection 布林代替此 barrier。

## manual descriptor 是否必要／是否第二 authority

**對 OS 停止證據不必要；對現行「所有 admitted manual operation 終局閉合」契約，仍有必要。** 新 job 可以免逐 read 枚舉，也能證明所有舊 manual writer 停止；head lock 可以證明舊 mutation 邊界已越過。兩者都無法回答「沒有 receipt 的那個 manual request 的 operation／digest 是什麼」。當 browser submission cache 消失，DB 只含 terminal rows，原 identity 就無從找回，亦無法按原 identity 寫終局 failure。

若只關心新 head 不被舊 writer 汙染，OS＋DB barrier 足以安全開新工作；但那會留下未閉合且無法枚舉的舊 operation，與原 ER03 全閉合 gate 不同。稍後舊 cache／延遲 POST 出現時，也必須有政策避免同 identity 被当成從未收到的新 attempt。要省 descriptor，須明確改成「允許遺忘未終局 manual」並另定舊 request 的拒絕／恢復機制，或放寬全閉合要求；不是當前已授權的免費簡化。此 review 不推薦為省一筆 binding 重開該契約。

目前建議的最多一筆 root `jd_manual_pending` 是 admitted intent 的非終局 binding；browser cache 保存 exact candidate，PG receipt 唯一決定 terminal outcome，JD revision/head 唯一保存內容。descriptor 既不重建候選，也不覆寫 terminal receipt，因此**不是第二 operation 結果 authority／第二 JD store**。它确實新增 durable admission 資料，而非既有 code 事實；需按現稿進採用與 Task 5 review。schema／README 要用 binding 而非「只是 cache」掩蓋其責任。

## 不阻擋設計的 Task 5 接線驗收

1. before-Node descriptor 保存失敗／結果未知：本 attempt 不 spawn；重開 latest root 對帳，最多留下可終局失敗的 admitted identity，不假造原 candidate。
2. 同文件序列化、一筆最多一個 pending；收到相同 key／不同 digest 必 conflict；先讀 terminal 再拒 busy／archived；descriptor 不可被新請求覆寫。終局已寫但 clear 失敗時再次回原 receipt，再清除，不新增 failure。
3. root channel 必須是 root-only，manual admission 時 root 無 pending AI；透過明確公開 state update 接點保存，不能 `invoke` 假 input。現行 root `analysis -> END` 可供有限 `update_state(as_node='analysis')` 接法，但實作要驗無歷史消息的新文件、已有 closed turn 的文件及首個真實 input：messages／turn_outcome／closed_turns 不造假，next 仍空、模型 invocation=0，之後真聊天仍正確啟動。不得為讓 update 通過塞空 HumanMessage／AI run。
4. descriptor 的 scoped base／origin／digest 來自已驗的 App admission。cache 缺失時限定 failure port 只核該 binding／receipt，不能給 caller 任意指定 digest 便造 terminal。保存原 digest 不需重造 payload；payload 回來才另驗 exact digest。failure receipt 仍由同 JdStore transaction 寫入。
5. 同 key response 晚到、cache 已消失、terminal receipt 已存但 descriptor 尚未清除，都須有固定反例。舊身份的 POST 不得因目前 head 一樣／receipt 暫缺而悄悄重跑 Node。

Task 3 修訂已排除空 owner stub／提前 lifecycle 宣稱；實際同 stop Event、saved binding 與原 call identity 接點可獨立施工，與上述 Task 5 工作無實作矛盾。沒有要求 Task 3 先建立 Windows job、manual descriptor 或完整 cleanup owner。

本次只 append review。未修改設計／production／ADR，未安裝 pywin32、未啟動 job／DB、未做模型或 process fault test。
