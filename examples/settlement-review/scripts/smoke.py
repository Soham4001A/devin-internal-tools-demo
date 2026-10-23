"""Real two-process HTTP smoke test: vendor + app as separate uvicorn processes over loopback.

Run from examples/settlement-review: python scripts/smoke.py
"""
import os
import secrets
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
APP, VENDOR = "http://127.0.0.1:9010", "http://127.0.0.1:9011"


def wait(url):
    for _ in range(50):
        try:
            if httpx.get(url, timeout=0.5).status_code < 500:
                return
        except httpx.HTTPError:
            time.sleep(0.2)
    raise SystemExit(f"timeout waiting for {url}")


def main():
    secret = secrets.token_urlsafe(32)
    tmp = tempfile.mkdtemp()
    base = {k: v for k, v in os.environ.items() if not k.startswith("RISK_VENDOR")}
    shared = {"RISK_VENDOR_CLIENT_ID": "settlement-review-smoke", "RISK_VENDOR_CLIENT_SECRET": secret}
    vlog, alog = open(f"{tmp}/vendor.log", "w+"), open(f"{tmp}/app.log", "w+")
    uv = [sys.executable, "-m", "uvicorn", "--factory", "--host", "127.0.0.1"]
    vendor = subprocess.Popen(uv + ["vendor.server:app_factory", "--port", "9011"], cwd=ROOT, env={**base, **shared},
                              stdout=vlog, stderr=subprocess.STDOUT)
    app = subprocess.Popen(uv + ["app.main:app_factory", "--port", "9010"], cwd=ROOT,
                           env={**base, **shared, "SR_DB": f"{tmp}/smoke.db", "SR_RESET": "1"}, stdout=alog,
                           stderr=subprocess.STDOUT)
    checks = []

    def check(name, ok):
        checks.append((name, ok))
        print(("PASS " if ok else "FAIL ") + name)

    try:
        wait(VENDOR + "/health"), wait(APP + "/")
        bad = httpx.post(VENDOR + "/oauth/token", data={"grant_type": "client_credentials",
                         "client_id": "settlement-review-smoke", "client_secret": "wrong"})
        check("vendor rejects wrong client secret over HTTP (401)", bad.status_code == 401)
        check("vendor rejects missing bearer (401)", httpx.get(VENDOR + "/v1/risk/STL-A-7781").status_code == 401)
        texts = []
        with httpx.Client(base_url=APP) as c:
            check("app unauthenticated -> 401", c.get("/api/exceptions").status_code == 401)
            r = c.post("/api/login", json={"username": "operator.a", "password": "operator-a-demo"})
            h = {"X-CSRF-Token": r.json()["csrf_token"]}
            d = c.get("/api/exceptions/SE-1001")
            texts += [r.text, d.text, str(r.headers)]
            check("risk enrichment fetched live from vendor process", d.json()["risk"]["status"] == "available")
            integ = c.get("/api/integration")
            texts.append(integ.text)
            check("integration status connected", integ.json()["state"] == "connected")
            dec = c.post("/api/exceptions/SE-1001/decision", headers=h, json={"action": "approve", "reason": "Smoke OK"})
            check("operator decision 200", dec.status_code == 200)
            check("duplicate decision 409", c.post("/api/exceptions/SE-1001/decision", headers=h,
                                                   json={"action": "reject", "reason": "again"}).status_code == 409)
            check("cross-tenant detail 404", c.get("/api/exceptions/SE-2001").status_code == 404)
            from concurrent.futures import ThreadPoolExecutor
            cookies = dict(c.cookies)

            def race(i):
                with httpx.Client(base_url=APP, cookies=cookies) as rc:
                    return rc.post("/api/exceptions/SE-1003/decision", headers=h,
                                   json={"action": "approve" if i % 2 else "reject", "reason": f"race {i}"}).status_code
            with ThreadPoolExecutor(10) as ex:
                codes = sorted(ex.map(race, range(10)))
            hist = c.get("/api/exceptions/SE-1003/history").json()["items"]
            check(f"10 concurrent decisions over HTTP -> one 200, nine 409, one history row ({codes})",
                  codes == [200] + [409] * 9 and len(hist) == 1)
            vendor.terminate(), vendor.wait(5)
            down = c.get("/api/exceptions/SE-1002").json()["risk"]
            check("vendor stopped -> risk unavailable, no score", down["status"] == "unavailable" and "score" not in down)
            check("vendor stopped -> integration unavailable", c.get("/api/integration").json()["state"] == "unavailable")
        time.sleep(0.3)
        logs = Path(f"{tmp}/vendor.log").read_text() + Path(f"{tmp}/app.log").read_text()
        check("secret absent from API responses", all(secret not in t for t in texts))
        check("secret absent from both process logs", secret not in logs)
        check("no bearer token in logs", "Bearer " not in logs and "access_token" not in logs)
    finally:
        for p in (app, vendor):
            p.terminate()
    print(f"{sum(ok for _, ok in checks)}/{len(checks)} smoke checks passed")
    sys.exit(0 if all(ok for _, ok in checks) else 1)


if __name__ == "__main__":
    main()
