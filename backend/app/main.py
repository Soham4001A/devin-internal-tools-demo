import json
from contextlib import asynccontextmanager
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import db
from .personas import DEFAULT_PERSONA, PERSONAS
from .tools import TOOLS

@asynccontextmanager
async def lifespan(_: FastAPI):
    db.init_db()
    yield


app = FastAPI(title="Ops Workbench API (demo)", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


def persona(x_demo_persona: str | None = Header(default=None)) -> dict:
    pid = x_demo_persona or DEFAULT_PERSONA
    if pid not in PERSONAS:
        raise HTTPException(401, "Unknown demo persona")
    return PERSONAS[pid]


def get_tool(tool: str):
    if tool not in TOOLS:
        raise HTTPException(404, "Unknown tool")
    return TOOLS[tool]


def _row(r) -> dict:
    data = json.loads(r["data"])
    return {"id": r["id"], "ref": r["ref"], "status": r["status"],
            "submitted_at": r["submitted_at"], "updated_at": r["updated_at"], **data}


OVERDUE_HOURS = 48


def is_overdue(item: dict, now: datetime) -> bool:
    """Pending and submitted strictly more than OVERDUE_HOURS before `now`."""
    if item["status"] != "pending":
        return False
    return now - datetime.fromisoformat(item["submitted_at"]) > timedelta(hours=OVERDUE_HOURS)


def _events(conn, tool: str, rid: int) -> list[dict]:
    rows = conn.execute(
        "SELECT * FROM events WHERE tool=? AND record_id=? ORDER BY created_at, id", (tool, rid)
    ).fetchall()
    return [dict(r) for r in rows]


@app.get("/api/health")
def health():
    return {"ok": True, "demo": True}


@app.get("/api/personas")
def personas():
    return {"personas": list(PERSONAS.values()), "default": DEFAULT_PERSONA,
            "note": "Demo personas only; no real authentication."}


@app.get("/api/me")
def me(p: dict = Depends(persona)):
    return p


@app.get("/api/tools")
def tools():
    return [t.public() for t in TOOLS.values()]


@app.get("/api/tools/{tool}")
def tool_config(tool: str):
    return get_tool(tool).public()


@app.get("/api/tools/{tool}/records")
def list_records(tool: str, q: str = "", status: str = "", overdue: bool = False,
                 _: dict = Depends(persona)):
    cfg = get_tool(tool)
    if status and status not in cfg.statuses:
        raise HTTPException(400, "Unknown status")
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT * FROM records WHERE tool=? ORDER BY submitted_at ASC", (tool,)
        ).fetchall()
    finally:
        conn.close()
    items = [_row(r) for r in rows]
    if status:
        items = [i for i in items if i["status"] == status]
    if overdue:
        now = datetime.now(timezone.utc)
        items = sorted((i for i in items if is_overdue(i, now)), key=lambda i: i["submitted_at"])
    if q.strip():
        needle = q.strip().lower()
        items = [i for i in items if any(needle in str(i.get(f, "")).lower() for f in cfg.search_fields)]
    return {"items": items}


@app.get("/api/tools/{tool}/summary")
def summary(tool: str, _: dict = Depends(persona)):
    cfg = get_tool(tool)
    conn = db.connect()
    try:
        rows = conn.execute(
            "SELECT status, COUNT(*) n, data FROM records WHERE tool=? GROUP BY status", (tool,)
        ).fetchall()
        amounts = conn.execute(
            "SELECT status, data, submitted_at FROM records WHERE tool=? AND status='pending'", (tool,)
        ).fetchall()
    finally:
        conn.close()
    counts = {s: 0 for s in cfg.statuses}
    for r in rows:
        counts[r["status"]] = r["n"]
    pending_amount = round(sum(json.loads(a["data"]).get("amount_usd", 0) for a in amounts), 2)
    now = datetime.now(timezone.utc)
    overdue = sum(1 for a in amounts if is_overdue(dict(a), now))
    return {"total": sum(counts.values()), "counts": counts, "pending_amount_usd": pending_amount,
            "overdue_pending": overdue, "overdue_hours": OVERDUE_HOURS}


@app.get("/api/tools/{tool}/records/{rid}")
def get_record(tool: str, rid: int, _: dict = Depends(persona)):
    get_tool(tool)
    conn = db.connect()
    try:
        r = conn.execute("SELECT * FROM records WHERE tool=? AND id=?", (tool, rid)).fetchone()
        if not r:
            raise HTTPException(404, "Record not found")
        return {"record": _row(r), "history": _events(conn, tool, rid)}
    finally:
        conn.close()


class DecisionIn(BaseModel):
    action: str
    reason: str = Field(default="", max_length=1000)


@app.post("/api/tools/{tool}/records/{rid}/decision")
def decide(tool: str, rid: int, body: DecisionIn, p: dict = Depends(persona)):
    cfg = get_tool(tool)
    if not p["can_decide"]:
        raise HTTPException(403, f"{p['label']} is not permitted to make decisions")
    action = cfg.action(body.action)
    if not action:
        raise HTTPException(400, "Unknown action")
    reason = body.reason.strip()
    if action.requires_reason and len(reason) < 3:
        raise HTTPException(422, "A decision reason is required")
    conn = db.connect()
    try:
        conn.execute("BEGIN IMMEDIATE")
        r = conn.execute("SELECT * FROM records WHERE tool=? AND id=?", (tool, rid)).fetchone()
        if not r:
            conn.execute("ROLLBACK")
            raise HTTPException(404, "Record not found")
        if r["status"] not in action.from_statuses:
            conn.execute("ROLLBACK")
            raise HTTPException(409, f"Already decided: this request is {r['status']}")
        ts = db.now_iso()
        cur = conn.execute(
            "UPDATE records SET status=?, updated_at=? WHERE tool=? AND id=? AND status=?",
            (action.to_status, ts, tool, rid, r["status"]),
        )
        if cur.rowcount != 1:
            conn.execute("ROLLBACK")
            raise HTTPException(409, "Concurrent decision detected")
        conn.execute(
            "INSERT INTO events(tool, record_id, action, actor, actor_role, reason, from_status, to_status, created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (tool, rid, action.key, p["name"], p["role"], reason, r["status"], action.to_status, ts),
        )
        conn.execute("COMMIT")
        r2 = conn.execute("SELECT * FROM records WHERE id=?", (rid,)).fetchone()
        return {"record": _row(r2), "history": _events(conn, tool, rid)}
    except HTTPException:
        raise
    except Exception:
        if conn.in_transaction:
            conn.execute("ROLLBACK")
        raise
    finally:
        conn.close()


def reset_enabled() -> bool:
    return os.environ.get("DEMO_RESET_ENABLED", "true").lower() == "true"


@app.post("/api/demo/reset")
def demo_reset(tool: str = Query(default="refunds")):
    """Restore synthetic fixtures for one tool. Disable with DEMO_RESET_ENABLED=false."""
    if not reset_enabled():
        raise HTTPException(403, "Demo reset disabled")
    get_tool(tool)
    db.reset_tool(tool)
    return {"ok": True, "tool": tool}


# Optional single-service mode: serve the built frontend from the API process.
_dist = Path(os.environ.get("FRONTEND_DIST", Path(__file__).resolve().parents[2] / "frontend" / "dist"))
if _dist.is_dir():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            raise HTTPException(404, "Not found")
        return FileResponse(_dist / "index.html")
