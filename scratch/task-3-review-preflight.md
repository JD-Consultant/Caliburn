# Task 3 獨立審查 preflight

2026-09-10。僅整理權威需求，尚未讀施工 diff、執行測試或作 verdict。

- Checkout：`S:/caliburn/.worktrees/analysis-only-agent`，branch `codex/analysis-only-agent`（已確認）。
- Topic：JD-R002/C03；隔離 G7，唯一目前施工 Task 3。基線 `23bf0161d3d61dc8517ec1ecf4ee9ad5cb8e5a6d`；Task 1/2 已接受，不重審其原生／PG 核心。
- 權威：`.superpowers/sdd/2026-09-10-jd-editor-core-implementation/task-3-brief.md`、`docs/current-decisions.md`、`docs/decision-process.md`、`docs/specs/2026-09-10-jd-app-tool-contract.md`、`docs/specs/2026-09-10-jd-model-view-change-notice-design.md` 及其 `evidence/2026-09-10-jd-model-view-design-review.md`、`docs/specs/2026-09-10-jd-native-process-lifecycle-design.md` §7 Task 3 有限補充。
- 下一問題僅為凍結的 Task 3 實作是否满足指定 spec 與品質；不重開已閉合設計。

## 待核對的必要條件

1. **同一契約與 App 完整驗證。** 僅三個 JD ModelInput；兩處歷史建立事件 description 納同一 SSOT 並重生。完整 Draft 2020-12 驗證在 operation／Node／SQL 寫入前，不能靠 dict BaseTool 自驗。雙 ref、未知 prop、非法遞迴內容不得進 engine。模型無 document/path/offset/profile/operation 自填入口。DTO 僅由 mapper 承接，service 維持內部 typed ports。
2. **factory identity 與最終 SDK。** composition、ToolNode、middleware 均保留原三件 factory instances，caller／middleware 同名替代 fail closed。只按 identity 將三 JD model-view 換成 raw function；最終實際 build_agent→ChatOpenAI→SDK MockTransport 的 parameters 與 SSOT refs 閉包、description 全等，recursive constraints 不剪枝，JD strict=false；其他工具 instance／schema／strict 與 provider、parallel、Memory、budget 設定不變。
3. **真發配、版本與完整續頁。** checkpointed issuance 綁 document/run/revision/read kind/target；可解析真 ID 不能冒充已讀。current 續頁保留同 base 且可給該版 current targets，提交再驗 head；explicit revision 即使為 head 仍 readonly，history 續頁不升格。selection/target、K/S 正反關係與 set/unset 按同版完整 revision 映射。混版、猜 ID、跨文件拒絕；先建→read→link 可做，unknown 不重複新增。change continuation 固定 exact event/pair，head 移動不換後頁；逐頁可收齊完整內容。no_change 可查空差異；任意两版比較不冒稱單一 AI 事件。
4. **來源沿原 owner。** 實際 ConversationReader／Memory read handle；同 run 已保存 current input 可用，history extraction 需 completed/safely closed window。缺 checkpoint、未讀／偽造、跨文件及 ToolMessage 假原話拒絕。逐字來源可回查，不複製進 JD store；本批只驗明示附著聯集，省略舊來源不清除，也不自動聲稱重新核實。
5. **真 API/native selection。** 真 POST runs optional SSOT jd_selection，current head admission→固定 read-selection 原生 fragment→重檢 head；checkpoint 綁本 run/saved input/base/block/range/fragment，jd_read 才首次發 ref。拒絕 stale／多 block／非法範圍，重複文字只改指定處；普通聊天與下一 run 不沿用舊 selection。Task 3 用 native editor range 經真 API，browser capture 留 Task 4。
6. **before-Node durable binding 與有限停止接點。** saved input→AI message→tool call→stable operation/digest/base/exact commands 在真正 ToolNode/engine 前 checkpoint；重開保留同 binding，原 ToolMessage ID。相同 document stop Event 由既有 CooperativeStop／factory 經實際 service edit/read-selection 到 engine keyword-only cancel，不只測 wrapper。unconfirmed/reconcile_operation 保留 pending，停止後續 JD intent 與 model loop，不能以 readonly 繼續或換 operation。
7. **事件基準與供給界線。** B 為最近成功 response-backed request manifest 的 current revision，(B,H] 計 committed 事件；當輪固定 (B0,H0] 摘要不能因第一個 response/compaction 消失，後續 current H 正確更新。manual revert 仍兩事件；marks/source/link-only 及 manual operations=null/affected=[] 仍計入。no_change/failed/dirty/unknown 不冒充新 revision。全文讀 change_refs 精確為該 revision 的 creating committed event，initial 空；可一路 change→before revision 查至 B，不把導航當正文已供給。
8. **模型請求投影與有界性。** 每次 compaction 後末尾重新注入唯一 request-only HumanMessage，JSON 明標 app_jd_context，不切斷 tool/result、不提升文件為 system authority、不改 canonical HumanMessage/Memory/extraction。必要 envelope 與 readonly refs 保留；payload ≤16,384 UTF-8 bytes、preview 合計 ≤2,048 bytes、最多四尾段事件並報完整區間 counts／省略。exact pair 放不下整筆省略，UTF-8/JSON 完整，可由三工具續讀。局部頁/edit feedback/被 compaction 裁除/尚未進 request 的 ToolMessage 都不得冒稱整版或目前已供給；原限額到達明示未全讀，不加預算。
9. **同 checkpoint、重開與故障。** official ExtendedModelResponse state-only Command 與有效 completed AI response 同 model checkpoint 保存有限 manifest，保留 response/其他 commands；root-child 同名共享且正常完成傳回。provider/preflight/checkpoint 失敗不推 B；舊 manifest 缺失合法 unknown，確定跨 scope/遺失 revision/非 ancestor 或 DB 失敗明示故障。通知查詢/組裝/容量失敗 handler=0，保留 saved input，不假 ToolMessage、不重播 edit。真 PG 新程序重開核 B，不能用 instance cache／dict state 代稱。MV01–17/19 要有實際 graph/request/state 指定證據。
10. **範圍、證據與文件。** README 正確敘述 tools/sources/binding/model-view 及限制，保留原 dirty recall 研究 hunk。0 付費/外部模型請求、未讀 key、未改 production/Memory/正式 authority；mock wire 不冒稱真 provider 接受、自然品質或成品完成。

## 明確不列本輪 blocker

完整 OS process owner/Windows Job/mutex/bootstrap、receipt reconcile/cleanup、manual descriptor/publish gate、真正 cancel/MV18、writer race 與 browser end-to-end selection 屬 Task 4/5。Task 3 不需空 owner stub，也不能以 forwarding 聲稱程序已停止。

## 凍結後的單次審查方式

等待 root 提供 frozen diff/report/hash manifest，再核對實際範圍與一次 diff，將必要條件對到程式及實作者證據。只針對新且具體的 code doubt 做 focused check，不 blanket 重跑或重審前兩 task。輸出分列 spec verdict、quality verdict、具體 actionable findings/證據限制；目前尚無 verdict。
