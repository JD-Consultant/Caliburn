"""T9:回合服務 v2 整合(真 DB + StubLlm + StubKnowledge)。
管線:書記 pass(set_slot 直寫/建議)→ 帳本 → 顧問 chat_with_tools → 保底。
0028 T5:裁剪 declined/occupation widget/finish 態度收尾;0032 T5a:intake 邀請卡。"""
import json

import pytest
from uuid import uuid4

from app.adapters.interview_repo import InterviewRepo
from app.adapters.persistence import DocRepo
from app.adapters.stubs import StubKnowledge, StubLlm
from app.interview.service import NoActiveInterview, run_finish, run_turn
from app.models import JobProfile, User

TASK_PATH = "ocs_content.ocu_units.u1.tasks.t1"
FREQ = f"{TASK_PATH}.details.frequency"


def _doc():
    return {
        "ocs_profile": {"ocs_code": "X", "job_description": ""},
        "ocs_content": {"ocu_units": [{
            "_uid": "u1", "ocu_name": "測試",
            "tasks": [{"_tid": "t1",
                       "task_codes": [{"code": "T1.1", "name": "回歸測試"}],
                       "competency_blocks": [{"outputs": [{"code": "O1", "name": "報告"}]}]}],
        }]},
    }


async def _setup(db, *, doc=None, human_touched=None):
    u = User(email=f"{uuid4()}@x.com", name="n"); db.add(u); await db.flush()
    p = JobProfile(user_id=u.id, job_title="工程師"); db.add(p); await db.flush()
    await DocRepo(db).save(p.id, doc if doc is not None else _doc())
    repo = InterviewRepo(db)
    s = await repo.create(p.id)
    if doc is None:                                   # 預設情境=既有 deep 焦點
        await repo.update_session(s.id, phase="deep", focus={"task_path": TASK_PATH})
    if human_touched:
        await repo.merge_human_touched(s.id, human_touched)
    return p, s, repo


# 書記記一個細項槽(v2 是 scribe records,非 v1 turn commands)
SCRIBE_SLOT = {"records": [
    {"type": "set_slot", "path": FREQ, "value": "每雙週", "quote": "每兩週跑一次"}]}


async def _run(db, text, *, select_result, human_touched=None, chat_text=None):
    p, s, repo = await _setup(db, human_touched=human_touched)
    kw = {"chat_text": chat_text} if chat_text is not None else {}
    llm = StubLlm(select_result=select_result, **kw)
    out = await run_turn(p.id, text, db=db, llm=llm, knowledge=StubKnowledge())
    return p, s, repo, out, llm


@pytest.mark.asyncio
async def test_scribe_lands_slot_as_pending_and_consultant_replies(db_session):
    """v3(ADR 0030):寫入=值上綠字+集合式 _pending(prev/src),不再有 evidence 路。"""
    p, s, repo, out, _ = await _run(db_session, "我們每兩週跑一次回歸", select_result=SCRIBE_SLOT)
    assert out.doc_changed is True
    latest = await DocRepo(db_session).latest(p.id)
    task = latest["content"]["ocs_content"]["ocu_units"][0]["tasks"][0]
    assert task["details"]["frequency"] == "每雙週"
    mark = task["details"]["_pending"]["frequency"]
    assert mark["op"] == "mod" and mark["by"] == "ai"
    assert mark["src"]["quote"]["text"] == "每兩週跑一次"
    turns = await repo.list_turns(s.id)
    assert [t.role for t in turns] == ["employee", "consultant"]
    assert out.say and turns[1].text == out.say                    # 顧問回覆落逐字稿
    assert out.coverage["required"] > 0                            # 覆蓋率進度
    calls = await repo.list_llm_calls(s.id)                        # T13:稽核落庫(書記+顧問各一)
    assert {c.role for c in calls} == {"select", "interview"} and all(c.model for c in calls)


@pytest.mark.asyncio
async def test_human_touched_no_longer_diverts_pending_is_universal(db_session):
    """v3:AI 可對任何內容(含人碰過的)發**提議**;唯一禁令=無聲改。
    pending 本身就是提議載體 → human_touched 不再分流建議表。"""
    p, s, repo, out, _ = await _run(db_session, "每兩週跑一次",
                                    select_result=SCRIBE_SLOT, human_touched=[FREQ])
    assert out.doc_changed is True
    latest = await DocRepo(db_session).latest(p.id)
    details = latest["content"]["ocs_content"]["ocu_units"][0]["tasks"][0]["details"]
    assert details["frequency"] == "每雙週" and details["_pending"]["frequency"]["op"] == "mod"


@pytest.mark.asyncio
async def test_scribe_failure_does_not_block_consultant(db_session):
    bad = {"records": [{"type": "set_slot"}]}                      # 缺欄→pydantic 反覆拒
    p, s, repo, out, _ = await _run(db_session, "隨便講講一些很長但沒重點的內容",
                                    select_result=bad,
                                    chat_text="沒關係,再多說一點?")
    assert out.doc_changed is False
    assert out.say == "沒關係,再多說一點?"                        # 顧問仍回應(fail-open)
    assert any("backstop" in g for g in out.guard_log)
    turns = await repo.list_turns(s.id)
    assert turns[1].role == "consultant"


@pytest.mark.asyncio
async def test_consultant_silence_gets_fallback(db_session):
    p, s, repo, out, _ = await _run(db_session, "嗨", select_result={"records": []}, chat_text="")
    assert out.say.strip()                                         # 保底:靜默→合成問題


@pytest.mark.asyncio
async def test_no_active_session_raises(db_session):
    u = User(email=f"{uuid4()}@x.com", name="n"); db_session.add(u); await db_session.flush()
    p = JobProfile(user_id=u.id, job_title="x"); db_session.add(p); await db_session.flush()
    with pytest.raises(NoActiveInterview):
        await run_turn(p.id, "hi", db=db_session, llm=StubLlm(), knowledge=StubKnowledge())


@pytest.mark.asyncio
async def test_roles_scribe_select_consultant_interview(db_session):
    p, s, repo, out, llm = await _run(db_session, "每兩週跑一次", select_result=SCRIBE_SLOT)
    selects = [c for c in llm.calls if c["kind"] == "select"]
    chats = [c for c in llm.calls if c["kind"] == "chat"]
    assert selects and all(c["role"] == "select" for c in selects)       # 書記=便宜模型
    assert chats and all(c["role"] == "interview" for c in chats)        # 顧問=強模型


# ---- 0028 T5:裁剪 widget / declined / occupation widget / finish 態度 ----

def _doc_occ_only():
    """有職類、零任務(=task_curation 死區,v2.1 要接上的斷棒)。"""
    return {"ocs_profile": {"ocs_code": "KRM2421-001v4", "job_description": ""},
            "ocs_content": {"ocu_units": []}, "ocs_attitude": {"attitudes": []}}


def _curation_select(records):
    """callable select stub:裁剪 schema(含 precheck 變體)回 records,其餘回空。"""
    def sel(prompt, schema):
        if '"precheck"' in json.dumps(schema):
            return {"records": records}
        return {"records": []}
    return sel


@pytest.mark.asyncio
async def test_curation_quote_lands_official_task_with_unit_shell(db_session):
    """0032 T5c:quote-backed precheck → 綠字直落——官方殼(unit)+任務都帶
    `_pending` add;provenance/_refs 由池 URN 程式導出;文件有任務 → intake 不再邀。"""
    p, s, repo = await _setup(db_session, doc=_doc_occ_only())
    llm = StubLlm(select_result=_curation_select(
        [{"type": "precheck", "key": "KRM2421-001v4:T1.1", "quote": "例行設備巡檢"}]))
    out = await run_turn(p.id, "我每天做例行設備巡檢", db=db_session, llm=llm,
                         knowledge=StubKnowledge())
    assert out.doc_changed is True
    assert out.widget is None                       # 已有(綠字)任務 → 不發 intake 邀請
    units = ((await DocRepo(db_session).latest(p.id))["content"]
             ["ocs_content"]["ocu_units"])
    assert len(units) == 1
    u = units[0]
    assert u["ocu_name"] == "預防保養" and u["_pending"]["op"] == "add"
    assert u["_refs"] == [{"ocs_code": "KRM2421-001v4", "occupation_name": "",
                           "code": "", "ocu_code": "U1"}]
    t = u["tasks"][0]
    assert t["task_codes"][0]["name"] == "例行設備巡檢"
    assert t["provenance"] == {"ocs_code": "KRM2421-001v4", "task_code": "T1.1"}
    assert t["_pending"]["op"] == "add" and t["_pending"]["by"] == "ai"
    assert t["_pending"]["src"]["ref_urn"] == "ocs:KRM2421-001v4:T:T1.1"
    assert t["_pending"]["src"]["quote"]["text"] == "例行設備巡檢"


@pytest.mark.asyncio
async def test_curation_lands_into_existing_unit_no_duplicate_shell(db_session):
    """家職責已在文件(名稱對位)→ 任務掛入,不建第二個殼;既有殼不背 _pending。"""
    doc = _doc_occ_only()
    doc["ocs_content"]["ocu_units"] = [{"_uid": "u9", "ocu_name": "預防保養", "tasks": []}]
    p, s, repo = await _setup(db_session, doc=doc)
    llm = StubLlm(select_result=_curation_select(
        [{"type": "precheck", "key": "KRM2421-001v4:T1.1", "quote": "例行設備巡檢"}]))
    out = await run_turn(p.id, "我每天做例行設備巡檢", db=db_session, llm=llm,
                         knowledge=StubKnowledge())
    assert out.doc_changed is True
    units = ((await DocRepo(db_session).latest(p.id))["content"]
             ["ocs_content"]["ocu_units"])
    assert len(units) == 1 and "_pending" not in units[0]
    assert units[0]["tasks"][0]["task_codes"][0]["name"] == "例行設備巡檢"
    assert units[0]["tasks"][0]["_pending"]["src"]["quote"]["text"] == "例行設備巡檢"


@pytest.mark.asyncio
async def test_curation_declined_persists_and_shrinks_checklist(db_session):
    p, s, repo = await _setup(db_session, doc=_doc_occ_only())
    llm = StubLlm(select_result=_curation_select(
        [{"type": "decline", "key": "KRM2421-001v4:T1.2", "quote": "保養排程管理我沒有做"}]))
    out = await run_turn(p.id, "保養排程管理我沒有做", db=db_session, llm=llm,
                         knowledge=StubKnowledge())
    # declined 照記;文件仍無任務 → intake 邀請照出(0032)
    assert out.widget == {"kind": "open_picker", "picker": "task_board_intake"}
    sess = await repo.get_active(p.id)
    assert sess.ledger_state.get("declined") == ["KRM2421-001v4:T1.2"]


# ---- 0032 T5a:intake 邀請卡三布林+dismissed 知情 ----

@pytest.mark.asyncio
async def test_intake_not_reoffered_after_board_dismissed(db_session):
    """他按過「用聊的就好」→ 不再邀請;顧問 context 得知情指示。"""
    p, s, repo = await _setup(db_session, doc=_doc_occ_only())
    await repo.add_review_events(s.id, [
        {"doc_path": "*", "decision": "task_board_dismissed"}])
    llm = StubLlm(select_result={"records": []})
    out = await run_turn(p.id, "我做設備巡檢的工作", db=db_session, llm=llm,
                         knowledge=StubKnowledge())
    assert out.widget is None
    chat = [c for c in llm.calls if c["kind"] == "chat"][-1]
    joined = "\n".join(m["content"] for m in chat["messages"]
                       if isinstance(m.get("content"), str))
    assert "用聊的就好" in joined and "別再提任務盤" in joined


@pytest.mark.asyncio
async def test_no_intake_when_doc_has_tasks(db_session):
    """條件自癒:文件一有任務(人勾的/AI 落的)→ 邀請卡永不再出。"""
    p, s, repo, out, _ = await _run(db_session, "我們每兩週跑一次回歸",
                                    select_result=SCRIBE_SLOT)
    assert out.widget is None


@pytest.mark.asyncio
async def test_no_intake_without_references(db_session):
    """參考集合空 → 盤是空的,不邀請(先走職類卡的路)。"""
    blank = {"ocs_profile": {}, "ocs_content": {"ocu_units": []},
             "ocs_attitude": {"attitudes": []}}
    p, s, repo = await _setup(db_session, doc=blank)
    out = await run_turn(p.id, "嗨你好", db=db_session,
                         llm=StubLlm(select_result={"records": []}),
                         knowledge=StubKnowledge())
    assert out.widget is None


@pytest.mark.asyncio
async def test_onboarding_occupation_widget_from_consultant_search(db_session):
    """顧問這回合真的搜過職類 → 才開 occupation picker(預填它用的 query)。"""
    blank = {"ocs_profile": {}, "ocs_content": {"ocu_units": []},
             "ocs_attitude": {"attitudes": []}}
    p, s, repo = await _setup(db_session, doc=blank)
    llm = StubLlm(select_result={"records": []},
                  chat_text="你做的像「設備維護工程師」,請從右上〔選職類〕確認?",
                  chat_trace=[{"name": "knowledge_search_occupations",
                               "args": {"query": "設備 巡檢 維護", "top_k": 3},
                               "result_digest": "x"}])
    out = await run_turn(p.id, "我在工廠顧機台", db=db_session, llm=llm,
                         knowledge=StubKnowledge())
    # 0031 A 案(T2):widget 帶 precheck(top-2 真實命中+確定性理由)→ 前端建議卡
    assert out.widget == {"kind": "open_picker", "picker": "occupation",
                          "query": "設備 巡檢 維護", "precheck": [
        {"code": "KRM2421-001v4", "name": "設備維護工程師", "reason": "依你描述:「設備 巡檢 維護」"},
        {"code": "KRM2422-001v4", "name": "生產線技術員", "reason": "依你描述:「設備 巡檢 維護」"}]}


@pytest.mark.asyncio
async def test_midway_new_occupation_hit_triggers_picker(db_session):
    """D8 P2:已選職類,顧問搜到**不同的** top-1 職類(如全端聊到後端)→ 彈加選 picker。
    (實測 65b9aa3d:三度搜到系統設計 1.0 卻無回路 → 內容無家 18K 硬塞錯任務。)"""
    doc = _doc_occ_only()
    doc["ocs_profile"]["ocs_code"] = "X-OTHER"        # 現有職類 ≠ Stub 搜尋 top-1
    p, s, repo = await _setup(db_session, doc=doc)
    llm = StubLlm(select_result={"records": []},
                  chat_text="你也做維護?建議把「設備維護工程師」加選進來。",
                  chat_trace=[{"name": "knowledge_search_occupations",
                               "args": {"query": "設備維護 保養 巡檢", "top_k": 3},
                               "result_digest": "x"}])
    out = await run_turn(p.id, "我也會做設備保養那塊", db=db_session, llm=llm,
                         knowledge=StubKnowledge())
    # top-1 是新職類 → 出卡(帶 precheck);同回合 intake 條件也成立 → 職類卡優先佔槽(0032)
    assert out.widget == {"kind": "open_picker", "picker": "occupation",
                          "query": "設備維護 保養 巡檢", "precheck": [
        {"code": "KRM2421-001v4", "name": "設備維護工程師", "reason": "依你描述:「設備維護 保養 巡檢」"},
        {"code": "KRM2422-001v4", "name": "生產線技術員", "reason": "依你描述:「設備維護 保養 巡檢」"}]}


@pytest.mark.asyncio
async def test_no_picker_when_top_hit_already_selected(db_session):
    """top-1 = 已選職類(顧問只是查參考)→ 不彈,不騷擾。"""
    doc = _doc_occ_only()                              # ocs_code=KRM2421-001v4=Stub top-1
    p, s, repo = await _setup(db_session, doc=doc)
    llm = StubLlm(select_result={"records": []},
                  chat_trace=[{"name": "knowledge_search_occupations",
                               "args": {"query": "設備維護", "top_k": 3},
                               "result_digest": "x"}])
    out = await run_turn(p.id, "就是設備維護的工作", db=db_session, llm=llm,
                         knowledge=StubKnowledge())
    # 職類卡正確不出(top-1 已選);同狀態(有參考、無任務)intake 邀請照出(0032)
    assert out.widget == {"kind": "open_picker", "picker": "task_board_intake"}


# run_curation(隨叫裁剪端點)已退役(ADR 0032):盤=乾淨自取,無 AI 疊加層;
# precheck+declined 行為由 run_turn 裁剪縫測試覆蓋(上方 T5c 測試)。


@pytest.mark.asyncio
async def test_finish_runs_attitudes_pass(db_session):
    p, s, repo = await _setup(db_session)                      # 既有 doc(有任務)
    await repo.append_turn(s.id, role="employee", text="回歸沒跑完我絕不放行")

    def sel(prompt, schema):
        sj = json.dumps(schema)
        if '"pool_id"' in sj:                                  # 態度收尾 schema
            return {"attitudes": [{"pool_id": "A01", "quote": "回歸沒跑完我絕不放行",
                                   "rationale": "堅守放行標準"}]}
        return {"misses": [], "misattributed": []}             # backstop schema

    out = await run_finish(p.id, db=db_session, llm=StubLlm(select_result=sel),
                           knowledge=StubKnowledge())
    # T10(ADR 0030):態度收尾走 op→verify→`_pending`(綠標落文件),不再建議化
    assert out["phase"] == "review"
    atts = ((await DocRepo(db_session).latest(p.id))["content"]
            .get("ocs_attitude", {}).get("attitudes", []))
    assert atts and atts[-1]["code"] == "A01"
    assert atts[-1]["_pending"]["op"] == "add"                 # 綠標,✓ 才轉已確認
    assert atts[-1]["_pending"]["src"]["quote"]["text"] == "回歸沒跑完我絕不放行"
    assert any("細心負責" in ln for ln in out["summary"]["lines"])
