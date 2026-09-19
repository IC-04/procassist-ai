"""Record the demo flow to build/procassist/demo.gif. Requires Playwright + Chromium.

Neither was present on the machine this was written on, so the recording was NOT produced
here and this script is untested end to end — it is committed so that producing it is one
command rather than an afternoon:

    .venv/bin/pip install playwright && .venv/bin/playwright install chromium
    .venv/bin/python -m procassist.record_demo

It drives the same flow the e2e suite asserts, captures a frame every ~120 ms, and writes an
animated GIF with Pillow, which is already a project dependency. A human still clicks nothing:
the script plays the operator's part, and the assertions in
`tests/test_procassist_e2e_playwright.py` are what prove the tool did not.
"""
from __future__ import annotations

import io
import os
import socket
import threading
import time
from typing import Any, List

OUT_DIR = os.path.join("build", "procassist")
OUT_GIF = os.path.join(OUT_DIR, "demo.gif")
FLAG_RECORD = "P1-07106250-010"
VIEWPORT = {"width": 1400, "height": 950}
FRAME_MS = 120


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


def _serve() -> tuple[str, Any, threading.Thread]:
    import uvicorn

    from .api.app import create_app

    port = _free_port()
    server = uvicorn.Server(uvicorn.Config(create_app(), host="127.0.0.1", port=port,
                                           log_level="error"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    for _ in range(100):
        if server.started:
            break
        time.sleep(0.05)
    return f"http://127.0.0.1:{port}", server, thread


class Recorder:
    """Grabs frames on a timer while the script drives the page."""

    def __init__(self, page: Any) -> None:
        self.page = page
        self.frames: List[bytes] = []
        self._stop = threading.Event()

    def beat(self, seconds: float) -> None:
        end = time.time() + seconds
        while time.time() < end:
            self.frames.append(self.page.screenshot(type="png"))
            time.sleep(FRAME_MS / 1000)


def main() -> None:  # pragma: no cover - a recording tool, not library code
    from PIL import Image
    from playwright.sync_api import sync_playwright

    os.makedirs(OUT_DIR, exist_ok=True)
    base, server, thread = _serve()
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            ctx = browser.new_context(viewport=VIEWPORT,
                                      extra_http_headers={"Host": "127.0.0.1:5132"})
            page = ctx.new_page()
            rec = Recorder(page)

            page.goto(base + "/payroll-items", wait_until="networkidle")
            rec.beat(1.0)                                   # the queue, before

            page.click("#prepare-all")                      # the agent prefill cascade
            page.wait_for_selector("#beforeafter:not([hidden])", timeout=20000)
            rec.beat(2.5)                                   # the before/after strip

            page.goto(f"{base}/payroll-items/{FLAG_RECORD}", wait_until="networkidle")
            page.wait_for_selector("#pa-usedraft", timeout=10000)
            rec.beat(1.4)                                   # the panel, FLAG, the clause

            page.click("#pa-usedraft")                      # the draft, judgement empty
            rec.beat(1.2)
            page.click(".pa-chip.pa-judgement")             # a human chooses
            rec.beat(1.0)
            page.click("#btn-pi-ok")                        # a human disposes
            rec.beat(1.2)

            page.goto(base + "/_evidence", wait_until="networkidle")
            rec.beat(1.6)                                   # what was measured
            ctx.close()
            browser.close()

        images = [Image.open(io.BytesIO(f)).convert("P", palette=Image.ADAPTIVE, colors=128)
                  for f in rec.frames]
        images[0].save(OUT_GIF, save_all=True, append_images=images[1:],
                       duration=FRAME_MS, loop=0, optimize=True)
        size_mb = os.path.getsize(OUT_GIF) / 1e6
        print(f"wrote {OUT_GIF}: {len(images)} frames, {size_mb:.1f} MB")
    finally:
        server.should_exit = True
        thread.join(timeout=5)


if __name__ == "__main__":
    main()
