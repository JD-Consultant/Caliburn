"""Agent-run real-browser acceptance for taking back one whole AI turn.

Real Chrome over CDP, the real Next production build on 127.0.0.1:3002, the real
managed Windows host with chat enabled, the real Agent/Saver/SQL path and a real
dedicated PostgreSQL database. The only substitution is the Anthropic HTTP
transport, which the chat helper replaces with a fixed offline script: no
credential, no provider network, no paid call. Every effect goes through clicks
and keystrokes on the page an employee uses.

Usage: undo_journey.py <fixture directory> [document title]
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

APP = Path("S:/caliburn/experiments/jd-relational-app")
sys.path.insert(0, str(APP / "tests" / "support"))
from browser_cdp import (  # noqa: E402
    Chrome, BrowserError, FETCH_TRACE, alerts, text_button, traced_calls)

TARGET = Path(sys.argv[1]).resolve()
assert TARGET.parent == Path("S:/caliburn/.research-tmp") and TARGET.name.startswith("jd-ui-gate-")
HERE = Path(__file__).resolve().parent
SHOTS = HERE / "undo-shots"
SHOTS.mkdir(exist_ok=True)

TITLE = sys.argv[2] if len(sys.argv) > 2 else "整輪撤回驗收"
INTERVIEW = "我每週固定巡檢產線設備，發現異常會記錄並通知負責人，隔離確認後才交接。"
STEPS = []

DIALOG_INPUT = "document.querySelector('.MuiDialog-root input, .MuiDialog-root textarea')"
CHAT_INPUT = ("[...document.querySelectorAll('textarea')]"
              ".find(t => t.id && document.querySelector(`label[for=\"${t.id}\"]`)"
              " && document.querySelector(`label[for=\"${t.id}\"]`).textContent.includes('告訴顧問'))")
STATUS = ("(() => { const el = document.querySelector('[aria-live=\"polite\"]');"
          " return el ? el.textContent.trim() : null; })()")
# MUI renders a second, aria-hidden textarea per field to measure auto-resize;
# only the one the employee actually types in is read here.
DUTY_NAMES = ("[...document.querySelectorAll('[id^=\"jd-item-\"] textarea')]"
              ".filter(t => t.getAttribute('aria-hidden') !== 'true' && !t.readOnly)"
              ".map(t => t.value).filter(v => v.trim().length > 0)")


def step(chrome, name, **values):
    shot = SHOTS / f"{len(STEPS):02d}-{name}.png"
    chrome.screenshot(shot)
    STEPS.append({"step": len(STEPS), "name": name, "screenshot": shot.name,
                  "status_chip": chrome.evaluate(STATUS), **values})
    print(json.dumps(STEPS[-1], ensure_ascii=False), flush=True)


def report_failure(chrome, error):
    shot = chrome.screenshot(SHOTS / "99-failure.png")
    detail = {"failed_at": len(STEPS), "error": str(error), "screenshot": Path(shot).name,
              "alerts": chrome.evaluate(alerts()),
              "last_click_the_page_received": chrome.evaluate("window.__lastClick"),
              "buttons_now": chrome.evaluate(
                  "[...document.querySelectorAll('button')].map(b => b.textContent.trim())"),
              "edit_calls": [dict(item, body=None) for item in traced_calls(chrome, "/jd/edits")]}
    (HERE / "browser-undo-first-failure.json").write_text(
        json.dumps({"steps": STEPS, **detail}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FAILURE>>>", json.dumps(detail, ensure_ascii=False)[:3000], flush=True)


def journey(chrome):
    chrome.send("Page.addScriptToEvaluateOnNewDocument", source=FETCH_TRACE)
    chrome.open("http://127.0.0.1:3002/")
    chrome.until(f"!!{text_button('建立文件')}", timeout=30, what="catalog_ready")
    step(chrome, "opened")

    chrome.click(text_button("建立文件"))
    chrome.until(f"!!{DIALOG_INPUT}", timeout=15, what="create_dialog")
    chrome.type_into(DIALOG_INPUT, TITLE)
    chrome.click(text_button("建立", exact=True))
    chrome.until(f"!!{CHAT_INPUT}", timeout=40, what="chat_ready")
    step(chrome, "created", title=TITLE, duties_before=chrome.evaluate(DUTY_NAMES))

    # 1. One real interview turn. The AI writes the JD through its own tools.
    # The box stays disabled until this document's session has really loaded.
    chrome.until(f"!{CHAT_INPUT}.disabled", timeout=40, what="interview_box_ready")
    chrome.type_into(CHAT_INPUT, INTERVIEW)
    chrome.until(f"!!{text_button('送出', exact=True)}", timeout=20, what="send_ready")
    chrome.click(text_button("送出", exact=True))
    chrome.until(f"document.body.innerText.includes('已保存 1 次 JD 修改')",
                 timeout=180, what="ai_turn_saved")
    step(chrome, "ai-turn-done", duties_after=chrome.evaluate(DUTY_NAMES),
         edit_calls=len(traced_calls(chrome, "/jd/edits")))

    # 2. The JD says where it came from, and those words open. This has to
    #    happen before the undo, because taking the turn back takes its content
    #    -- and therefore its markers -- with it.
    chrome.until("document.body.innerText.includes('依據你說過的')", timeout=30,
                 what="source_marker")
    step(chrome, "source-marker",
         marker=chrome.evaluate(
             "(() => { const found = document.body.innerText.split('\\n')"
             ".find(line => line.includes('依據你說過的')); return found || null; })()"),
         open_buttons=len(chrome.evaluate(
             "[...document.querySelectorAll('button')].map(b => b.textContent.trim())"
             ".filter(t => t.startsWith('看第'))")))
    chrome.click(text_button("看第 1 段原話"))
    # Read the panel itself, not the page: the employee's own words also appear
    # in the interview column, so a page-wide match would prove nothing.
    panel = ("(() => { const found = [...document.querySelectorAll('.MuiDialog-root')]"
             ".find(node => node.innerText.includes('你當初說過的話'));"
             " return found ? found.innerText : ''; })()")
    chrome.until(f"{panel}.includes({json.dumps(INTERVIEW[:20])})", timeout=30,
                 what="own_words_in_the_panel")
    # This source holds the employee's own input for that turn and nothing
    # else, so the panel must show exactly that -- and must not caveat a
    # consultant line that is not in it.
    opened = {
        "own_words_shown": chrome.evaluate(f"{panel}.includes({json.dumps(INTERVIEW)})"),
        "labels_who_said_it": chrome.evaluate(f"{panel}.includes('你說的')"),
        "says_the_interview_itself_does_not_change": chrome.evaluate(
            f"{panel}.includes('這段訪談本身不會因為 JD 改動而變')"),
        "no_consultant_line_claimed": not chrome.evaluate(f"{panel}.includes('顧問當時的回覆')"),
    }
    step(chrome, "source-opened", **opened)
    assert all(opened.values()), opened
    chrome.click(text_button("關閉", exact=True))
    chrome.until(f"{panel} === ''", timeout=20, what="source_dialog_closed")

    # 3. The turn's own changes, offered as one thing to take back.
    chrome.until(f"!!{text_button('撤回這輪 JD 改動')}", timeout=60, what="undo_offered")
    step(chrome, "undo-offered", run_change_summary=chrome.evaluate(
        "(() => { const s = document.querySelector('section[aria-label=\"本輪 JD 改動\"]');"
        " return s ? s.innerText.slice(0, 400) : null; })()"))

    chrome.click(text_button("撤回這輪 JD 改動"))
    chrome.until(f"!!{text_button('確認撤回')}", timeout=20, what="undo_confirm_shown")
    step(chrome, "undo-explained", notice=chrome.evaluate(
        "(() => { const a = [...document.querySelectorAll('.MuiAlert-message')]"
        ".map(x => x.textContent.trim()).find(t => t.includes('一次取回')); return a || null; })()"),
        duties_still_there=chrome.evaluate(DUTY_NAMES))

    chrome.click(text_button("確認撤回"))
    chrome.until(f"{DUTY_NAMES}.length === 0", timeout=60, what="duties_taken_back")
    chrome.until(f"{STATUS} === '已保存'", timeout=40, what="settled_after_undo")
    step(chrome, "undone", duties_after_undo=chrome.evaluate(DUTY_NAMES),
         undo_call=[dict(item, body=None, response=(item.get("response") or "")[:120])
                    for item in traced_calls(chrome, "/jd/edits")][-1:])

    # 4. Only JD moved: the conversation and the turn's record are still there.
    kept = {
        "reply_still_shown": chrome.evaluate(
            "document.body.innerText.includes('已依合成訪談建立設備檢查任務')"),
        "own_words_still_shown": chrome.evaluate(
            f"document.body.innerText.includes({json.dumps(INTERVIEW[:20])})"),
        "turn_change_record_still_listed": chrome.evaluate(
            "document.body.innerText.includes('已保存 1 次 JD 修改')"),
    }
    step(chrome, "conversation-kept", **kept)
    assert all(kept.values()), kept

    result = {"format": 1, "journey": "undo_ai_turn",
              "ran_at_utc": datetime.now(timezone.utc).isoformat(),
              "ui_origin": "http://127.0.0.1:3002", "provider_network": False,
              "model_transport": "httpx2.MockTransport", "paid_model_calls": 0,
              "title": TITLE, "steps": STEPS,
              "edit_calls": [dict(item, body=None) for item in traced_calls(chrome, "/jd/edits")]}
    (HERE / "browser-undo-journey.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("undo journey OK")


with Chrome(TARGET / "chrome-profile") as browser:
    try:
        journey(browser)
    except (BrowserError, AssertionError) as failure:
        report_failure(browser, failure)
        raise
