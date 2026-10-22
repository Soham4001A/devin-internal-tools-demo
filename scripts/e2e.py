"""Browser journey for Refunds Review (synthetic data).

Usage (server already running on BASE_URL, default http://localhost:8000):
  cd backend && .venv/bin/pip install playwright==1.49.1 && .venv/bin/playwright install chromium
  .venv/bin/python ../scripts/e2e.py [--video out_dir] [--shots out_dir]
Resets refunds and merchant_reviews demo data first, so it is repeatable.
Then switches to Merchant Reviews via the sidebar, decides a case and verifies refunds are unchanged.
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
ap.add_argument("--db", default=None, help="SQLite path of the running server; enables 48h boundary rows")
a = ap.parse_args()
os.makedirs(a.shots, exist_ok=True)

for _tool in ("refunds", "merchant_reviews"):
    urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/demo/reset?tool={_tool}", method="POST")).read()

with sync_playwright() as p:
    browser = p.chromium.launch(slow_mo=a.slow, executable_path=os.environ.get("CHROME_PATH") or None)
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

    # over 48 hours: pending only, oldest first; approved/rejected never included
    expect(page.locator(".stat-overdue .stat-value")).to_have_text("4")
    page.get_by_label("Over 48 hours").check()
    expect(page.locator("tbody tr")).to_have_count(4)
    expect(page.locator("tbody tr td:first-child")).to_have_text(["RF-1007", "RF-1006", "RF-1005", "RF-1004"])
    page.get_by_label("Status filter").select_option("approved")
    expect(page.get_by_text("No requests match")).to_be_visible()
    page.get_by_label("Status filter").select_option("")
    page.get_by_label("Search").fill("skyward")
    expect(page.locator("tbody tr td:first-child")).to_have_text(["RF-1005"])
    page.get_by_label("Search").fill("")
    expect(page.locator("tbody tr")).to_have_count(4)
    page.wait_for_timeout(600)
    page.screenshot(path=f"{a.shots}/04-over-48h.png")
    if a.db:
        import sqlite3
        from datetime import datetime, timedelta, timezone
        now = datetime.now(timezone.utc)
        conn = sqlite3.connect(a.db)
        for ref, st, h in (("RF-B4759", "pending", 47 + 59 / 60), ("RF-B4801", "pending", 48 + 1 / 60),
                           ("RF-BOLDA", "approved", 300)):
            ts = (now - timedelta(hours=h)).isoformat(timespec="seconds")
            conn.execute("INSERT INTO records(tool, ref, status, data, submitted_at, updated_at) VALUES (?,?,?,?,?,?)",
                         ("refunds", ref, st, '{"customer": "Boundary Test"}', ts, ts))
        conn.commit()
        conn.close()
        page.reload()
        page.get_by_label("Status filter").select_option("pending")
        page.get_by_label("Over 48 hours").check()
        expect(page.locator(".stat-overdue .stat-value")).to_have_text("5")
        expect(page.locator("tbody tr td:first-child")).to_have_text(
            ["RF-1007", "RF-1006", "RF-1005", "RF-1004", "RF-B4801"])
        page.wait_for_timeout(600)
        page.screenshot(path=f"{a.shots}/05-48h-boundary.png")
        page.get_by_label("Over 48 hours").uncheck()
        expect(page.get_by_test_id("row-RF-B4759")).to_be_visible()
        page.wait_for_timeout(600)
        urllib.request.urlopen(urllib.request.Request(f"{BASE}/api/demo/reset?tool=refunds", method="POST")).read()
        page.reload()
    page.get_by_label("Over 48 hours").uncheck()
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
    expect(page.locator(".stat-overdue .stat-value")).to_have_text("3")
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
    page.get_by_label("Close").click()

    # --- Merchant Reviews: separate route, data, state and history ---
    page.get_by_label("Status filter").select_option("")
    page.get_by_label("Search").fill("skyward")
    expect(page.locator("tbody tr")).to_have_count(1)
    page.get_by_role("link", name="Merchant Reviews").click()
    expect(page).to_have_url(re.compile(r"/merchant-reviews$"))
    expect(page.get_by_role("heading", name="Merchant reviews queue")).to_be_visible()
    expect(page.get_by_label("Search")).to_have_value("")
    expect(page.get_by_label("Status filter")).to_have_value("")
    expect(page.locator("tbody tr")).to_have_count(8)
    expect(page.locator(".stat-pending .stat-value")).to_have_text("5")
    expect(page.locator("thead th")).to_have_text(
        ["Case", "Merchant", "Business category", "Submitted", "Owner", "Missing documents", "Review status"])
    expect(page.get_by_label("Over 48 hours")).to_have_count(0)
    expect(page.locator(".stat-overdue")).to_have_count(0)
    expect(page.get_by_text("Pending value")).to_have_count(0)
    expect(page.get_by_test_id("row-RF-1001")).to_have_count(0)
    page.wait_for_timeout(600)
    page.screenshot(path=f"{a.shots}/06-merchant-queue.png")
    page.get_by_label("Search").fill("insurance")
    expect(page.locator("tbody tr td:first-child")).to_have_text(["MR-2003"])
    page.get_by_label("Search").fill("")

    page.get_by_label("Demo persona").select_option("viewer")
    page.get_by_test_id("row-MR-2003").click()
    drawer = page.get_by_role("dialog")
    expect(drawer.get_by_text("Liability insurance certificate, Bank account letter")).to_be_visible()
    expect(drawer.get_by_text("has view-only access")).to_be_visible()
    page.wait_for_timeout(500)
    page.screenshot(path=f"{a.shots}/07-merchant-viewer-readonly.png")
    page.get_by_label("Close").click()

    page.get_by_label("Demo persona").select_option("reviewer")
    page.get_by_test_id("row-MR-2003").click()
    drawer = page.get_by_role("dialog")
    drawer.get_by_role("button", name="Reject").click()
    expect(drawer.get_by_text("Enter a decision reason")).to_be_visible()
    drawer.get_by_label(re.compile("Decision reason")).fill("Insurance certificate and bank letter still outstanding after reminders.")
    drawer.get_by_role("button", name="Reject").click()
    expect(drawer.locator(".badge-rejected")).to_be_visible()
    expect(drawer.get_by_text("Insurance certificate and bank letter still outstanding")).to_be_visible()
    expect(drawer.get_by_text("Priya Raman").first).to_be_visible()
    expect(page.locator(".stat-pending .stat-value")).to_have_text("4")
    expect(page.locator(".stat-rejected .stat-value")).to_have_text("2")
    page.wait_for_timeout(700)
    page.screenshot(path=f"{a.shots}/08-merchant-rejected-history.png")
    page.get_by_label("Close").click()

    # back to refunds: fresh search/selection, refund counts unchanged by merchant decision
    page.get_by_role("link", name="Refunds Review").click()
    expect(page).to_have_url(re.compile(r"/refunds$"))
    expect(page.get_by_label("Search")).to_have_value("")
    expect(page.get_by_role("dialog")).to_have_count(0)
    expect(page.locator("tbody tr")).to_have_count(12)
    expect(page.locator(".stat-pending .stat-value")).to_have_text("6")
    expect(page.locator(".stat-rejected .stat-value")).to_have_text("2")
    expect(page.locator(".stat-overdue .stat-value")).to_have_text("3")
    page.get_by_test_id("row-RF-1004").click()
    expect(page.get_by_role("dialog").get_by_text("Carrier photos confirm damage")).to_be_visible()
    expect(page.get_by_role("dialog").get_by_text("Insurance certificate")).to_have_count(0)
    page.get_by_label("Close").click()

    # deep link + persistence for the merchant decision
    page.goto(f"{BASE}/merchant-reviews")
    page.get_by_label("Status filter").select_option("rejected")
    expect(page.locator("tbody tr td:first-child")).to_have_text(["MR-2008", "MR-2003"])
    page.wait_for_timeout(700)
    ctx.close()
    browser.close()
print("E2E OK")
