"""Agent-run real-browser acceptance for restoring an earlier JD revision.

Real Chrome over CDP, the real Next production build on 127.0.0.1:3002, the real
Windows host/FastAPI on the fixture's own port, and a real dedicated PostgreSQL
database. Zero provider: this journey never enables chat and never reaches a
model. Every effect goes through clicks and keystrokes on the page an employee
uses; nothing here calls the JD API directly. The fetch trace only observes.

Usage: restore_journey.py <fixture directory> [document title]
"""

from datetime import datetime, timezone
import json
from pathlib import Path
import sys

APP = Path("S:/caliburn/experiments/jd-relational-app")
sys.path.insert(0, str(APP / "tests" / "support"))
from browser_cdp import (  # noqa: E402
    Chrome, BrowserError, FETCH_TRACE, alerts, text_button, traced_calls, visible_text)

TARGET = Path(sys.argv[1]).resolve()
assert TARGET.parent == Path("S:/caliburn/.research-tmp") and TARGET.name.startswith("jd-ui-gate-")
HERE = Path(__file__).resolve().parent
SHOTS = HERE / "shots"
SHOTS.mkdir(exist_ok=True)

TITLE = sys.argv[2] if len(sys.argv) > 2 else "還原與撤回驗收"
JOB_TITLE = "資深設備維運工程師"
PURPOSE = "維持產線設備可用，讓生產排程不因設備停機而延誤。"
STEPS = []

DIALOG_INPUT = "document.querySelector('.MuiDialog-root input, .MuiDialog-root textarea')"
STATUS = ("(() => { const el = document.querySelector('[aria-live=\"polite\"]');"
          " return el ? el.textContent.trim() : null; })()")


def step(chrome, name, **values):
    shot = SHOTS / f"{len(STEPS):02d}-{name}.png"
    chrome.screenshot(shot)
    STEPS.append({"step": len(STEPS), "name": name, "screenshot": shot.name,
                  "status_chip": chrome.evaluate(STATUS), **values})
    print(json.dumps(STEPS[-1], ensure_ascii=False), flush=True)


def field(name):
    return f"document.getElementById('jd-field-profile-{name}')"


def value_of(chrome, name):
    return chrome.evaluate(f"(() => {{ const el = {field(name)}; return el ? el.value : null; }})()")


def saved(chrome, what):
    chrome.until(f"{STATUS} === '已保存'", timeout=40, what=what)


def report_failure(chrome, error):
    shot = chrome.screenshot(SHOTS / "99-failure.png")
    detail = {"failed_at": len(STEPS), "error": str(error), "screenshot": Path(shot).name,
              "alerts": chrome.evaluate(alerts()),
              "last_click_the_page_received": chrome.evaluate("window.__lastClick"),
              "buttons_now": chrome.evaluate(
                  "[...document.querySelectorAll('button')].map(b => b.textContent.trim())"),
              "edit_calls": traced_calls(chrome, "/jd/edits"),
              "status_chip": chrome.evaluate(STATUS)}
    (HERE / "browser-restore-first-failure.json").write_text(
        json.dumps({"steps": STEPS, **detail}, ensure_ascii=False, indent=2), encoding="utf-8")
    print("FAILURE>>>", json.dumps(detail, ensure_ascii=False)[:3000], flush=True)


def journey(chrome):
    chrome.send("Page.addScriptToEvaluateOnNewDocument", source=FETCH_TRACE)
    chrome.open("http://127.0.0.1:3002/")
    chrome.until(f"!!{text_button('建立文件')}", timeout=30, what="catalog_ready")
    step(chrome, "opened")

    # 1. Create the document through the real dialog.
    chrome.click(text_button("建立文件"))
    chrome.until(f"!!{DIALOG_INPUT}", timeout=15, what="create_dialog")
    chrome.type_into(DIALOG_INPUT, TITLE)
    chrome.click(text_button("建立", exact=True))
    chrome.until(f"!!{field('job_title')}", timeout=40, what="editor_ready")
    step(chrome, "created", title=TITLE)

    # 2. Two separate manual saves, so an earlier revision really exists.
    chrome.type_into(field("job_title"), JOB_TITLE)
    chrome.blur()
    saved(chrome, "first_save")
    step(chrome, "saved-job-title", job_title=value_of(chrome, "job_title"))

    chrome.type_into(field("purpose"), PURPOSE)
    chrome.blur()
    saved(chrome, "second_save")
    step(chrome, "saved-purpose", job_title=value_of(chrome, "job_title"),
         purpose=value_of(chrome, "purpose"))

    # 3. Open history and ask what restoring the earlier revision would do.
    chrome.click(text_button("改動與歷史"))
    chrome.until(f"!!{text_button('還原到第 2 版')}", timeout=20, what="history_ready")
    step(chrome, "history-open", restore_buttons=chrome.evaluate(
        "[...document.querySelectorAll('button')].map(b => b.textContent.trim())"
        ".filter(t => t.startsWith('還原到第'))"))

    chrome.click(text_button("還原到第 2 版"))
    chrome.until(f"!!{text_button('確認還原')}", timeout=30, what="preview_ready")
    step(chrome, "restore-preview",
         preview_text=chrome.evaluate(
             "(() => { const t = [...document.querySelectorAll('p')].map(e => e.textContent.trim())"
             ".find(t => t.startsWith('會有') || t.startsWith('這一版的內容')); return t || null; })()"),
         preview_shows_removed_purpose=chrome.evaluate(
             f"document.body.innerText.includes({json.dumps(PURPOSE)})"),
         jd_unchanged_by_preview=value_of(chrome, "purpose"),
         edit_calls_so_far=len(traced_calls(chrome, "/jd/edits")))

    # 4. While the comparison is open, the JD must not move under it.
    held = {"job_title_field_disabled": chrome.box(field("job_title"))["disabled"],
            "purpose_field_disabled": chrome.box(field("purpose"))["disabled"],
            "send_disabled": chrome.box(text_button("送出", exact=True))["disabled"],
            "hold_explained": chrome.evaluate(
                f"{visible_text()}.includes('正在確認一次還原，暫停送出')")}
    step(chrome, "held-while-deciding", **held)
    assert all(held.values()), held

    # Cancelling the comparison gives the editor straight back.
    chrome.click(text_button("取消", exact=True))
    chrome.until(f"!{field('job_title')}.disabled", timeout=20, what="editing_returns_on_cancel")
    # The send button stays disabled here for its own reason -- the interview
    # box is empty -- so only the hold itself is asserted, not that button.
    released = {"job_title_field_disabled": chrome.box(field("job_title"))["disabled"],
                "still_holding": chrome.evaluate(
                    f"{visible_text()}.includes('正在確認一次還原，暫停送出')")}
    step(chrome, "released-on-cancel", **released,
         send_disabled_for_empty_input=chrome.box(text_button("送出", exact=True))["disabled"])
    assert not any(released.values()), released

    # 5. Ask again, then confirm, and check the page the employee is looking at.
    chrome.click(text_button("還原到第 2 版"))
    chrome.until(f"!!{text_button('確認還原')}", timeout=30, what="preview_again")
    chrome.click(text_button("確認還原"))
    chrome.until(f"(() => {{ const el = {field('purpose')}; return !!el && el.value === ''; }})()",
                 timeout=40, what="purpose_restored_away")
    saved(chrome, "after_restore")
    step(chrome, "restored", job_title=value_of(chrome, "job_title"),
         purpose=value_of(chrome, "purpose"),
         restore_call=[dict(item, body=None, response=item.get("response", "")[:120])
                       for item in traced_calls(chrome, "/jd/edits")][-1:])

    # 6. Restoring adds a revision; nothing in history was removed.
    chrome.until(f"!!{text_button('還原到第 4 版')}", timeout=30, what="restore_made_new_revision")
    step(chrome, "history-after-restore", restore_buttons=chrome.evaluate(
        "[...document.querySelectorAll('button')].map(b => b.textContent.trim())"
        ".filter(t => t.startsWith('還原到第'))"),
        conversation_panel_present=chrome.evaluate(f"{visible_text()}.includes('你的工作顧問')"))

    result = {"format": 1, "journey": "restore_revision",
              "ran_at_utc": datetime.now(timezone.utc).isoformat(),
              "ui_origin": "http://127.0.0.1:3002", "provider_calls": 0, "chat_enabled": False,
              "title": TITLE, "steps": STEPS,
              "final_job_title": value_of(chrome, "job_title"),
              "final_purpose": value_of(chrome, "purpose"),
              "edit_calls": [dict(item, body=None) for item in traced_calls(chrome, "/jd/edits")]}
    assert result["final_job_title"] == JOB_TITLE, result["final_job_title"]
    assert result["final_purpose"] == "", result["final_purpose"]
    (HERE / "browser-restore-journey.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print("restore journey OK")


with Chrome(TARGET / "chrome-profile") as browser:
    try:
        journey(browser)
    except (BrowserError, AssertionError) as failure:
        report_failure(browser, failure)
        raise
