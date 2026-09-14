"""Minimal Chrome DevTools Protocol driver for agent-run browser acceptance.

Synthetic test support only; never imported by production. Checked 2026-09-14
against the official protocol viewer for the domains used here - Page, Runtime,
DOM and Input (https://chromedevtools.github.io/devtools-protocol/) - on the
locally installed Chrome. Clicks and keystrokes go through
Input.dispatchMouseEvent / Input.dispatchKeyEvent at real element coordinates,
so a control that is missing, disabled, invisible or covered is NOT clicked:
reaching it is part of the evidence, not an assumption. Transport is the
already-vendored `websockets` client; no new dependency, no automation
framework, no page instrumentation.

This driver never talks to the JD API itself; every effect goes through the
page the employee would actually use.
"""

import asyncio
import base64
import json
from pathlib import Path
import subprocess
import time
from urllib.request import urlopen

import websockets

CHROME = Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")


class BrowserError(RuntimeError):
    pass


class Chrome:
    """One real headless Chrome process attached to one page target."""

    def __init__(self, profile, port=9334, width=1280, height=1600):
        self.profile, self.port = Path(profile), port
        self.width, self.height = width, height
        self.process = self.socket = self.loop = None
        self._next = 0

    def __enter__(self):
        if not CHROME.exists():
            raise BrowserError("chrome_not_installed")
        self.profile.mkdir(parents=True, exist_ok=True)
        self.process = subprocess.Popen([
            str(CHROME), "--headless=new", "--remote-debugging-port=" + str(self.port),
            "--user-data-dir=" + str(self.profile),
            "--window-size=" + str(self.width) + "," + str(self.height),
            "--no-first-run", "--no-default-browser-check", "--disable-extensions",
            "--disable-background-networking", "--disable-sync", "--no-proxy-server",
            "about:blank",
        ], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        deadline = time.monotonic() + 40
        while True:
            try:
                listed = json.loads(urlopen(
                    "http://127.0.0.1:" + str(self.port) + "/json/list", timeout=2).read())
                page = next(item for item in listed
                            if item.get("type") == "page" and item.get("webSocketDebuggerUrl"))
                break
            except Exception:
                if time.monotonic() >= deadline:
                    raise BrowserError("chrome_devtools_unavailable") from None
                time.sleep(0.2)
        self.loop = asyncio.new_event_loop()
        self.socket = self.loop.run_until_complete(
            websockets.connect(page["webSocketDebuggerUrl"], max_size=64 * 1024 * 1024))
        self.send("Page.enable")
        self.send("Runtime.enable")
        self.send("DOM.enable")
        return self

    def __exit__(self, *error):
        try:
            if self.socket is not None:
                self.loop.run_until_complete(self.socket.close())
        finally:
            if self.loop is not None:
                self.loop.close()
            if self.process is not None:
                self.process.terminate()
                try:
                    self.process.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    self.process.kill()

    # -- protocol ---------------------------------------------------------
    def send(self, method, **params):
        self._next += 1
        message = json.dumps({"id": self._next, "method": method, "params": params})

        async def exchange():
            await self.socket.send(message)
            while True:
                raw = json.loads(await asyncio.wait_for(self.socket.recv(), timeout=60))
                if raw.get("id") != self._next:
                    continue  # Protocol events are not answers; keep waiting.
                if "error" in raw:
                    raise BrowserError("cdp_error:" + method + ":" + str(raw["error"].get("message")))
                return raw.get("result", {})

        return self.loop.run_until_complete(exchange())

    # -- page -------------------------------------------------------------
    # Server-rendered markup is clickable long before React attaches to it, and
    # a press that lands in that gap does nothing at all. React marks the nodes
    # it has taken over, so wait for that rather than for paint.
    HYDRATED = ("[...document.querySelectorAll('button, input, textarea')].some("
                "el => Object.keys(el).some(key => key.startsWith('__reactFiber$')))")

    def open(self, url, *, ready="document.readyState === 'complete'", timeout=60,
             hydrated=True):
        self.send("Page.navigate", url=url)
        self.until(ready, timeout=timeout, what="page_ready")
        if hydrated:
            self.until(self.HYDRATED, timeout=timeout, what="page_hydrated")

    def evaluate(self, expression, *, await_promise=False):
        result = self.send("Runtime.evaluate", expression=expression, returnByValue=True,
                           awaitPromise=await_promise)
        if "exceptionDetails" in result:
            raise BrowserError("page_exception:" + json.dumps(result["exceptionDetails"])[:400])
        return result["result"].get("value")

    def until(self, expression, *, timeout=30, interval=0.15, what=None):
        deadline, last = time.monotonic() + timeout, None
        while time.monotonic() < deadline:
            try:
                last = self.evaluate(expression)
            except BrowserError as error:
                last = str(error)
            if last is True:
                return True
            time.sleep(interval)
        raise BrowserError("condition_never_true:" + str(what or expression) + ":" + repr(last))

    # -- real input -------------------------------------------------------
    def box(self, selector_js):
        """Where the element really is, and whether a real click could land on it."""
        found = self.evaluate("(() => { const el = " + selector_js + ";"
            " if (!el) return null;"
            " const r = el.getBoundingClientRect();"
            " const mid = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);"
            " return { x: r.left + r.width / 2, y: r.top + r.height / 2, w: r.width, h: r.height,"
            "   disabled: !!el.disabled,"
            "   hit: !!mid && (mid === el || el.contains(mid) || mid.contains(el)) }; })()")
        if found is None:
            raise BrowserError("element_not_found:" + selector_js[:120])
        return found

    def reachable(self, selector_js):
        found = self.box(selector_js)
        if found["w"] <= 0 or found["h"] <= 0:
            raise BrowserError("element_not_visible:" + selector_js[:120])
        if found["disabled"]:
            raise BrowserError("element_disabled:" + selector_js[:120])
        if not found["hit"]:
            raise BrowserError("element_covered:" + selector_js[:120])
        return found

    def settled(self, selector_js, *, tries=40, gap=0.12):
        """The element's own box, once it has stopped moving.

        A page that is still laying out can slide a control out from under the
        pointer between measuring and pressing, which sends the press to
        whatever moved into that place instead.
        """
        previous = self.reachable(selector_js)
        for _ in range(tries):
            time.sleep(gap)
            current = self.reachable(selector_js)
            if abs(current["x"] - previous["x"]) < 1 and abs(current["y"] - previous["y"]) < 1:
                return current
            previous = current
        raise BrowserError("layout_never_settled:" + selector_js[:120])

    def click(self, selector_js):
        """Real mouse move, press and release at the element's own centre.

        The element the page reports as the click target must be the element
        that was aimed at, so "the employee pressed this control" is observed
        rather than assumed.
        """
        for attempt in range(3):
            found = self.settled(selector_js)
            # The listener only records; it never cancels or replays the event.
            self.evaluate("(() => { window.__lastClick = null;"
                          " window.__clickTarget = " + selector_js + ";"
                          " document.addEventListener('click', event => { window.__lastClick = {"
                          "   tag: event.target.tagName, trusted: event.isTrusted,"
                          "   x: event.clientX, y: event.clientY,"
                          "   intended: !!window.__clickTarget && (event.target === window.__clickTarget"
                          "     || window.__clickTarget.contains(event.target)),"
                          "   text: (event.target.textContent || '').trim().slice(0, 40) }; },"
                          " { capture: true, once: true }); return true; })()")
            self.send("Input.dispatchMouseEvent", type="mouseMoved", x=found["x"], y=found["y"],
                      button="none", buttons=0)
            for kind, buttons in (("mousePressed", 1), ("mouseReleased", 0)):
                self.send("Input.dispatchMouseEvent", type=kind, x=found["x"], y=found["y"],
                          button="left", clickCount=1, buttons=buttons)
            try:
                self.until("!!window.__lastClick", timeout=5, interval=0.05, what="click_received")
            except BrowserError:
                raise BrowserError("click_not_received:" + selector_js[:120]) from None
            found["received"] = self.evaluate("window.__lastClick")
            if found["received"]["intended"]:
                return found
        raise BrowserError("click_hit_other_element:" + selector_js[:80]
                           + ":" + json.dumps(found["received"], ensure_ascii=False))

    def type_into(self, selector_js, text, *, clear=True):
        """Focus with a real click, then insert through the browser's own input path."""
        self.click(selector_js)
        if clear:
            for kind in ("keyDown", "keyUp"):
                self.send("Input.dispatchKeyEvent", type=kind, key="a", code="KeyA",
                          windowsVirtualKeyCode=65, modifiers=2)
            for kind in ("rawKeyDown", "keyUp"):
                self.send("Input.dispatchKeyEvent", type=kind, key="Delete", code="Delete",
                          windowsVirtualKeyCode=46)
        self.send("Input.insertText", text=text)

    def blur(self):
        self.send("Input.dispatchKeyEvent", type="rawKeyDown", key="Tab", code="Tab",
                  windowsVirtualKeyCode=9)
        self.send("Input.dispatchKeyEvent", type="keyUp", key="Tab", code="Tab",
                  windowsVirtualKeyCode=9)

    def screenshot(self, path):
        result = self.send("Page.captureScreenshot", format="png", captureBeyondViewport=True)
        Path(path).write_bytes(base64.b64decode(result["data"]))
        return str(path)


def text_button(label, *, exact=False):
    """JS expression selecting a laid-out button by the label an employee reads."""
    match = "text === label" if exact else "text.includes(label)"
    return ("(() => { const label = " + json.dumps(label) + ";"
            " return [...document.querySelectorAll('button')].find(item => {"
            "   const text = (item.textContent || '').trim();"
            "   return " + match + " && item.getBoundingClientRect().width > 0; }) || null; })()")


def visible_text():
    return "document.body.innerText"


# Installed before any page script runs, because the app captures `fetch` while
# it first renders. Records what the page sends and what came back; it never
# changes, delays, repeats or answers a request.
FETCH_TRACE = """
  window.__jdTrace = [];
  const original = window.fetch;
  window.fetch = function (input, init) {
    const entry = { url: String(input && input.url ? input.url : input),
      method: (init && init.method) || (input && input.method) || 'GET',
      body: init && typeof init.body === 'string' ? init.body.slice(0, 400) : null };
    window.__jdTrace.push(entry);
    return original.call(this, input, init).then(async response => {
      entry.status = response.status;
      try { entry.response = (await response.clone().text()).slice(0, 400); }
      catch (error) { entry.response = null; }
      return response;
    }, error => { entry.failed = String(error); throw error; });
  };
"""


def traced_calls(chrome, contains=""):
    return [item for item in (chrome.evaluate("window.__jdTrace") or [])
            if contains in item.get("url", "")]


def alerts():
    return ("[...document.querySelectorAll('.MuiAlert-message')]"
            ".map(item => item.textContent.trim())")
