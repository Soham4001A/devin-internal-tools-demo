"""Browser journey (Playwright + locally installed Chrome): viewer -> operator A -> operator B isolation.

Needs scripts/run.sh running with SR_RESET=1. Usage: python scripts/e2e.py [out_dir] [chrome_path]
"""
import sys
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

URL = "http://127.0.0.1:9010/"
OUT = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts")
CHROME = sys.argv[2] if len(sys.argv) > 2 else None


def login(page, user, pw):
    page.fill("#u", user), page.fill("#p", pw), page.click("button[type=submit]")
    expect(page.locator("#appView")).to_be_visible()


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME) if CHROME else p.chromium.launch(channel="chrome")
        ctx = b.new_context(viewport={"width": 1360, "height": 860}, record_video_dir=str(OUT),
                            record_video_size={"width": 1360, "height": 860})
        page = ctx.new_page()
        page.goto(URL)
        page.fill("#u", "operator.a"), page.fill("#p", "wrong"), page.click("button[type=submit]")
        expect(page.locator("#loginErr")).to_have_text("Incorrect username or password")
        page.screenshot(path=OUT / "01-login-rejected.png")

        login(page, "viewer.a", "viewer-a-demo")
        expect(page.locator("#connPill")).to_have_text("Connected")
        page.click("tr[data-id=SE-1002]")
        expect(page.locator("#risk")).to_contain_text("/100")
        expect(page.locator("#decision")).to_contain_text("View only")
        expect(page.locator("#cannot")).to_contain_text("Approve or reject")
        expect(page.locator("#cannot")).to_contain_text("other tenant")
        expect(page.locator("#kv")).to_contain_text("redacted by server")
        assert page.locator("#approve").count() == 0
        page.screenshot(path=OUT / "02-viewer-readonly-redacted.png", full_page=True)
        status = page.evaluate("""async () => (await fetch('/api/exceptions/SE-1002/decision', {method:'POST',
            headers:{'Content-Type':'application/json','X-CSRF-Token':ME.csrf_token,'X-Role':'operator'},
            body: JSON.stringify({action:'approve', reason:'forged attempt', role:'operator'})})).status""")
        assert status == 403, status
        page.click("#logout")
        expect(page.locator("#login")).to_be_visible()

        login(page, "operator.a", "operator-a-demo")
        page.click("tr[data-id=SE-1002]")
        expect(page.locator("#kv")).to_contain_text("GB00DEMO00005678")
        page.fill("#reason", "Duplicate of batch STL-A-7781 confirmed with treasury")
        page.click("#reject")
        expect(page.locator("#history")).to_contain_text("Rejected by Omar Operator")
        expect(page.locator("#decision")).to_contain_text("Already rejected")
        page.screenshot(path=OUT / "03-operator-a-rejected-history.png", full_page=True)
        page.click("#logout")

        login(page, "operator.b", "operator-b-demo")
        expect(page.locator("#queueTitle")).to_contain_text("Bluefin")
        ids = page.locator("tr.row").evaluate_all("rs => rs.map(r => r.dataset.id)")
        assert ids and all(i.startswith("SE-2") for i in ids), ids
        cross = page.evaluate("async () => (await fetch('/api/exceptions/SE-1002')).status")
        assert cross == 404, cross
        expect(page.locator("#cannot")).to_contain_text("other tenant")
        page.click("tr[data-id=SE-2001]")
        expect(page.locator("#risk")).to_contain_text("/100")
        page.screenshot(path=OUT / "04-operator-b-tenant-isolation.png", full_page=True)
        html = page.content()
        assert "access_token" not in html and "client_secret" not in html
        ctx.close(), b.close()
    print("E2E PASS: wrong login rejected; viewer read-only + redacted + forged 403; operator A reject + history;"
          " operator B sees only tenant B, SE-1002 -> 404")


if __name__ == "__main__":
    main()
