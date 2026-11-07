"""Campus Customs backend: FastAPI routes for the React dashboard.

Start it from the backend/ folder:

    cd backend
    uvicorn main:app --reload --port 8000

Then open http://localhost:8000/docs for the interactive route list.

Every shop read and write goes through the Campus Customs MCP server (one
long-lived connection opened at startup). The only route that moves money is
POST /api/approvals/{id}/approve, which a human triggers by clicking Approve.
Agents can only prepare requests.
"""

from __future__ import annotations

import asyncio
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Literal

# Running `uvicorn main:app` from backend/ puts backend/ on the path, not the
# project root. Add the root so `backend.*` imports work either way.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fastapi import FastAPI, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import RedirectResponse  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

from backend import config  # noqa: E402
from backend.activity import activity, contributions  # noqa: E402
from backend.agents.team import CampusCustomsTeam, build_mcp_toolset  # noqa: E402
from backend.audit import AuditTrail  # noqa: E402
from backend.models import AGENT_NAMES  # noqa: E402
from backend.reset_db import reset as reset_working_db  # noqa: E402


# --------------------------------------------------------------- app state ---

class RunState(BaseModel):
    run_id: str
    ticket_id: int
    status: Literal["running", "completed", "failed", "stopped_by_limit"]
    started_at: str
    finished_at: str | None = None
    outcome: dict[str, Any] | None = None
    error: str | None = None


class State:
    mcp = None                          # long-lived MCP connection
    team: CampusCustomsTeam | None = None
    runs: dict[str, RunState] = {}
    tasks: dict[str, asyncio.Task] = {}
    audit = AuditTrail()


state = State()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@asynccontextmanager
async def lifespan(app: FastAPI):
    state.mcp = build_mcp_toolset()
    async with state.mcp:               # one MCP server process for the app's lifetime
        yield
        for task in state.tasks.values():
            task.cancel()


app = FastAPI(
    title="Campus Customs Multi-Agent Operations",
    description="Routes for the ticket dashboard. Payments move only on a human Approve.",
    version="1.0",
    lifespan=lifespan,
)

# The React dashboard (Vite) runs on http://localhost:5173 during development.
# Any other local port is allowed too, in case Vite has to pick a different one.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1)(:\d+)?",
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)


async def mcp_call(tool: str, args: dict[str, Any] | None = None) -> Any:
    try:
        return await state.mcp.direct_call_tool(tool, args or {})
    except Exception as exc:  # MCP server error -> clear 502 for the dashboard
        raise HTTPException(502, f"MCP tool {tool} failed: {exc}") from exc


def _active_run() -> RunState | None:
    return next((r for r in state.runs.values() if r.status == "running"), None)


def _team() -> CampusCustomsTeam:
    """Build the agent team on first use, sharing the app's MCP connection."""
    if state.team is None:
        try:
            state.team = CampusCustomsTeam(mcp=state.mcp)
        except config.ConfigError as exc:
            raise HTTPException(503, str(exc)) from exc
    return state.team


# ------------------------------------------------------------------ health ---

@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """http://localhost:8000 opens the interactive route list."""
    return RedirectResponse("/docs")


@app.get("/api/health")
async def health() -> dict:
    """Server is up; shows the model and database in use."""
    return {
        "ok": True,
        "model": config.REQUIRED_MODEL,
        "database": str(config.WORKING_DB_PATH.relative_to(PROJECT_ROOT)),
        "agents": list(AGENT_NAMES),
        "active_run": _active_run(),
    }


# ----------------------------------------------------------------- tickets ---

@app.get("/api/tickets")
async def list_tickets() -> dict:
    """Tickets 101-103 with their current status (open, in progress, awaiting approval, resolved)."""
    data = await mcp_call("list_tickets")
    running = {r.ticket_id: r.run_id for r in state.runs.values() if r.status == "running"}
    for t in data["tickets"]:
        t["agents_working"] = t["id"] in running
        t["run_id"] = running.get(t["id"])
    return data


@app.get("/api/tickets/{ticket_id}")
async def get_ticket(ticket_id: int) -> dict:
    """One ticket with its drafts, notes and approval requests."""
    data = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if not data.get("found"):
        raise HTTPException(404, data.get("error", "Ticket not found."))
    return data


async def _run_in_background(run: RunState) -> None:
    try:
        outcome = await _team().run_ticket(run.ticket_id, run_id=run.run_id)
        run.status, run.outcome = "completed", outcome.model_dump(mode="json")
    except asyncio.CancelledError:
        run.status, run.error = "failed", "Cancelled because the server stopped."
        raise
    except Exception as exc:
        stopped = type(exc).__name__ == "UsageLimitExceeded"
        run.status = "stopped_by_limit" if stopped else "failed"
        run.error = str(exc)
    finally:
        run.finished_at = _now()
        state.tasks.pop(run.run_id, None)


@app.post("/api/tickets/{ticket_id}/run", status_code=202)
async def run_ticket(ticket_id: int) -> RunState:
    """Start the agent team on one ticket. Returns at once; poll /api/activity and /api/runs/{run_id}."""
    found = await mcp_call("get_ticket", {"ticket_id": ticket_id})
    if not found.get("found"):
        raise HTTPException(404, found.get("error", "Ticket not found."))
    busy = _active_run()
    if busy:  # one run at a time: tickets compete for the same cash
        raise HTTPException(409, f"Agents are already working ticket {busy.ticket_id} (run {busy.run_id}).")
    _team()  # fail fast with 503 if the Portkey key or model is wrong
    run = RunState(run_id=uuid.uuid4().hex[:12], ticket_id=ticket_id, status="running", started_at=_now())
    state.runs[run.run_id] = run
    state.tasks[run.run_id] = asyncio.create_task(_run_in_background(run))
    return run


@app.get("/api/tickets/{ticket_id}/contributions")
async def ticket_contributions(ticket_id: int) -> dict:
    """What each agent did on the ticket's latest run: summary, tools used, who asked whom, tokens."""
    return contributions(ticket_id)


@app.get("/api/runs")
async def list_runs() -> list[RunState]:
    """Agent runs started since the server came up, newest first."""
    return sorted(state.runs.values(), key=lambda r: r.started_at, reverse=True)


@app.get("/api/runs/{run_id}")
async def get_run(run_id: str) -> RunState:
    """One run's status and, when finished, the Boss's final outcome."""
    if run_id not in state.runs:
        raise HTTPException(404, "Run not found.")
    return state.runs[run_id]


# ---------------------------------------------------------------- activity ---

@app.get("/api/activity")
async def get_activity(
    since: int = Query(-1, description="Return items after this audit index (use last_index from the previous call)."),
    ticket_id: int | None = None,
    run_id: str | None = None,
    limit: int = Query(100, ge=1, le=500),
) -> dict:
    """Recent agent messages, tool calls, tool results and hand-offs from output/audit_trail.json."""
    return activity(since=since, ticket_id=ticket_id, run_id=run_id, limit=limit)


# --------------------------------------------------------------- approvals ---

class Decision(BaseModel):
    decided_by: str = Field(min_length=1, description="Name of the human approving or rejecting.")
    note: str = ""


@app.get("/api/approvals")
async def list_approvals(
    status: Literal["pending", "approved", "rejected", "refused", "all"] = "pending",
) -> dict:
    """Payments and purchase orders the agents prepared, waiting on a human."""
    return await mcp_call("list_approval_requests", {"status": status})


async def _decide(request_id: int, decision: str, body: Decision) -> dict:
    result = await mcp_call("record_human_decision", {
        "request_id": request_id, "decision": decision,
        "decided_by": body.decided_by, "note": body.note,
    })
    state.audit.log(
        run_id=f"human-{uuid.uuid4().hex[:8]}", agent=f"human:{body.decided_by}",
        event="human_decision", detail={"request_id": request_id, "decision": decision, "result": result},
    )
    if "status" not in result:  # bad request: unknown id, already decided, agent name as approver
        raise HTTPException(400, result.get("error", "Decision not recorded."))

    # Once the human has decided every request on a ticket that was only waiting
    # on approvals, the ticket is done: mark it resolved.
    req = next((r for r in (await mcp_call("list_approval_requests", {"status": "all"}))["requests"]
                if r["id"] == request_id), None)
    if req:
        t = await mcp_call("get_ticket", {"ticket_id": req["ticket_id"]})
        still_pending = [r for r in t["approval_requests"] if r["status"] == "pending"]
        if t["ticket"]["status"] == "awaiting_approval" and not still_pending:
            await mcp_call("update_ticket_status", {
                "ticket_id": req["ticket_id"], "status": "resolved",
                "updated_by": f"human:{body.decided_by}",
                "note": f"All approval requests decided by {body.decided_by}. Ticket resolved.",
            })
            result["ticket_resolved"] = req["ticket_id"]
    return result


@app.post("/api/approvals/{request_id}/approve")
async def approve(request_id: int, body: Decision) -> dict:
    """HUMAN CLICK ONLY. Pays the request: lowers cash, writes payments, marks invoice paid or moves rent forward.
    Refused (nothing paid) if cash would go negative or the vendor still has an unpaid invoice."""
    return await _decide(request_id, "approve", body)


@app.post("/api/approvals/{request_id}/reject")
async def reject(request_id: int, body: Decision) -> dict:
    """HUMAN CLICK ONLY. Rejects the request; no money moves."""
    return await _decide(request_id, "reject", body)


# -------------------------------------------------------------------- cash ---

@app.get("/api/cash")
async def cash() -> dict:
    """Checking balance from cash_accounts, plus what pending requests would leave."""
    data = await mcp_call("get_cash_position")
    checking = next((a for a in data["accounts"] if a["name"] == "checking"), None)
    if checking is None:
        raise HTTPException(404, "No checking account in cash_accounts.")
    return {"checking": checking, "pending_requests": data["pending_requests"],
            "payments_made": data["payments_made"]}


# ------------------------------------------------------------------- reset ---

@app.post("/api/reset")
async def reset(clear_audit: bool = False) -> dict:
    """Restore data/campus_customs_new.db from the original for a fresh run (audit trail kept unless clear_audit=true)."""
    busy = _active_run()
    if busy:
        raise HTTPException(409, f"Can't reset while agents are working ticket {busy.ticket_id}.")
    reset_working_db(clear_audit=clear_audit)
    state.runs.clear()
    state.audit.log(run_id=f"reset-{uuid.uuid4().hex[:8]}", agent="human", event="human_decision",
                    detail={"action": "reset_database", "clear_audit": clear_audit})
    data = await mcp_call("list_tickets")
    return {"ok": True, "message": "Working database restored to the original values.",
            "tickets": [{"id": t["id"], "status": t["status"]} for t in data["tickets"]]}
