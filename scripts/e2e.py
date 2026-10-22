"""Browser journey for Refunds Review (synthetic data).

Usage (server already running on BASE_URL, default http://localhost:8000):
  cd backend && .venv/bin/pip install playwright==1.49.1 && .venv/bin/playwright install chromium
  .venv/bin/python ../scripts/e2e.py [--video out_dir] [--shots out_dir]
Resets the refunds demo data first, so it is repeatable.
"""
import argparse
import os
import re
import urllib.request

from playwright.sync_api import expect, sync_playwright

BASE = os.environ.get("BASE_URL", "http://localhost:8000")

ap = argparse.ArgumentParser()
ap.add_argument("--video", default=None)
ap.add_argument("--shots", default="artifacts")
ap.add_argument("--slow", type=int, default=0)
a = ap.parse_args()
os.makedirs(a.shots, exist_ok=True)

urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/demo/reset?tool=refunds", method="POST")).read()

with sync_playwright() as p:
    browser = p.chromium.launch(slow_mo=a.slow)
    ctx = browser.new_context(viewport={"width": 1440, "height": 900},
                              record_video_dir=a.video, record_video_size={"width": 1440, "height": 900} if a.video else None)
    page = ctx.new_page()
    page.goto(BASE)
    expect(page.get_by_test_id("row-RF-1001")).to_be_visible()
    expect(page.locator(".stat-pending .stat-value")).to_have_text("7")
    page.wait_for_timeout(600)
    page.screenshot(path=f"{a.shots}/01-queue-baseline.png")

    # search + filter
    page.get_by_label("Search").fill("skyward")
    expect(page.locator("tbody tr")).to_have_count(1)
    page.get_by_label("Search").fill("")
    page.get_by_label("Status filter").select_option("pending")
    expect(page.locator("tbody tr")).to_have_count(7)

    # viewer cannot decide
    page.get_by_label("Demo persona").select_option("viewer")
    page.get_by_test_id("row-RF-1004").click()
    expect(page.get_by_text("has view-only access")).to_be_visible()
    page.wait_for_timeout(500)
    page.screenshot(path=f"{a.shots}/02-viewer-readonly.png")
    page.get_by_label("Close").click()

    # reviewer: reason required, then approve
    page.get_by_label("Demo persona").select_option("reviewer")
    page.get_by_test_id("row-RF-1004").click()
    drawer = page.get_by_role("dialog")
    drawer.get_by_role("button", name="Approve").click()
    expect(drawer.get_by_text("Enter a decision reason")).to_be_visible()
    drawer.get_by_label(re.compile("Decision reason")).fill("Carrier photos confirm damage on arrival; merchant agreed.")
    drawer.get_by_role("button", name="Approve").click()
    expect(drawer.locator(".badge-approved")).to_be_visible()
    expect(drawer.get_by_text("Approved", exact=True).first).to_be_visible()
    expect(drawer.get_by_text("Carrier photos confirm damage")).to_be_visible()
    expect(drawer.get_by_text("decided. Decisions are final")).to_be_visible()
    expect(page.locator(".stat-pending .stat-value")).to_have_text("6")
    page.wait_for_timeout(700)
    page.screenshot(path=f"{a.shots}/03-approved-history.png")
    page.get_by_label("Close").click()
    expect(page.locator("tbody tr")).to_have_count(6)

    # persistence: reload shows decision
    page.reload()
    page.get_by_label("Status filter").select_option("approved")
    page.get_by_test_id("row-RF-1004").click()
    expect(page.get_by_role("dialog").get_by_text("Carrier photos confirm damage")).to_be_visible()
    page.wait_for_timeout(700)
    ctx.close()
    browser.close()
print("E2E OK")
