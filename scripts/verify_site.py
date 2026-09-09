"""Headless check that the built page renders: every tab must draw canvases and
produce no console errors. Run in CI after refresh_all.py so a bad payload is
caught before it is published rather than after.
"""
import os, sys
from playwright.sync_api import sync_playwright
from common import SITE, log

MIN_TABS = 5   # tolerate a missing optional dashboard, fail if the page is gutted


def main():
    page_path = os.path.join(SITE, "index.html")
    if not os.path.exists(page_path):
        log("site/index.html missing"); return 1

    errors, frames = [], []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={"width": 1260, "height": 1400})
        page.on("console", lambda m: errors.append(m.text) if m.type == "error" else None)
        page.on("pageerror", lambda e: errors.append(f"pageerror: {e}"))
        page.goto(f"file://{page_path}", wait_until="networkidle")
        page.wait_for_timeout(7000)
        for f in page.frames:
            if f == page.main_frame:
                continue
            try:
                n = f.eval_on_selector_all("canvas", "els => els.length")
                frames.append((f.title()[:40], n))
            except Exception as exc:
                errors.append(f"frame read failed: {exc}")
        browser.close()

    for title, n in frames:
        log(f"  {title}: {n} canvas")

    blank = [t for t, n in frames if n == 0]
    if len(frames) < MIN_TABS:
        log(f"FAIL: only {len(frames)} tabs rendered"); return 1
    if blank:
        log(f"FAIL: tabs rendered no charts: {blank}"); return 1
    if errors:
        log(f"FAIL: {len(errors)} console error(s)")
        for e in errors[:10]:
            log(f"   {e}")
        return 1
    log(f"OK: {len(frames)} tabs rendered, zero console errors")
    return 0


if __name__ == "__main__":
    sys.exit(main())
