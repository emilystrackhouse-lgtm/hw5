"""Turn the audit trail into a simple activity feed for the dashboard.

output/audit_trail.json records every agent-loop step in detail. The
dashboard only needs readable lines: who said what, which tool was called
with which arguments, what it returned, and who handed work to whom. Each
item keeps the index of its audit entry, so the dashboard can poll with
`?since=<last index>` and only receive what's new.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from backend.config import AUDIT_PATH

PREVIEW_CHARS = 600


def _preview(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= PREVIEW_CHARS else text[:PREVIEW_CHARS] + "…"


def load_audit(path: Path = AUDIT_PATH) -> list[dict]:
    try:
        data = json.loads(path.read_text())
        return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _items_for(index: int, e: dict) -> list[dict]:
    base = {
        "index": index,
        "timestamp": e.get("timestamp"),
        "run_id": e.get("run_id"),
        "ticket_id": e.get("ticket_id"),
        "agent": e.get("agent"),
        "depth": e.get("depth", 0),
    }
    d = e.get("detail") or {}
    ev = e.get("event")

    if ev == "model_response":
        out = []
        for p in d.get("parts", []):
            if p.get("type") == "text" and p.get("content"):
                out.append(base | {"kind": "message", "text": _preview(p["content"])})
            elif p.get("type") == "tool_call":
                tool = p.get("tool")
                if tool == "final_result":
                    continue  # the agent_end item shows the final answer
                if tool == "ask_teammate":
                    continue  # shown as a delegation item instead
                out.append(base | {"kind": "tool_call", "tool": tool, "args": p.get("args")})
        return out
    if ev == "model_request":
        return [
            base | {"kind": "tool_result", "tool": p.get("tool"), "text": _preview(p.get("content"))}
            for p in d.get("parts", [])
            if p.get("type") == "tool_result" and p.get("tool") not in ("final_result", "ask_teammate")
        ]
    if ev == "delegation_start":
        return [base | {"kind": "delegation", "to": d.get("teammate"), "text": _preview(d.get("task", ""))}]
    if ev == "delegation_refused":
        return [base | {"kind": "delegation_refused", "to": d.get("teammate"), "text": d.get("reason", "")}]
    if ev == "agent_end":
        out_ = d.get("output") or {}
        summary = out_.get("decision") or out_.get("summary") or ""
        return [base | {"kind": "agent_done", "text": _preview(summary)}]
    if ev == "run_start":
        return [base | {"kind": "run_start", "text": f"Ticket {e.get('ticket_id')} started"}]
    if ev == "run_end":
        return [base | {"kind": "run_end", "text": d.get("status", ""), "usage": e.get("usage")}]
    if ev == "error":
        return [base | {"kind": "error", "text": _preview(d.get("error", ""))}]
    if ev == "human_decision":
        return [base | {"kind": "human_decision", "text": _preview(d.get("result", d))}]
    return []


def last_reset_index(entries: list[dict]) -> int:
    """Index of the most recent database reset in the trail (-1 if none)."""
    for i in range(len(entries) - 1, -1, -1):
        if (entries[i].get("detail") or {}).get("action") == "reset_database":
            return i
    return -1


def contributions(ticket_id: int) -> dict:
    """Per-agent summary of the latest run on a ticket, built from the audit trail."""
    entries = load_audit()
    reset_at = last_reset_index(entries)
    starts = [(i, e) for i, e in enumerate(entries)
              if i > reset_at and e.get("event") == "run_start" and e.get("ticket_id") == ticket_id]
    if not starts:
        return {"ticket_id": ticket_id, "run_id": None, "status": "not_run", "agents": [], "outcome": None}
    start_index, start = starts[-1]
    run_id = start["run_id"]
    agents: dict[str, dict] = {}
    status, outcome, usage = "running", None, None

    def slot(name: str) -> dict:
        return agents.setdefault(name, {
            "agent": name, "summaries": [], "tools": [], "asked": [], "asked_by": [],
            "approval_request_ids": [], "board_post_ids": [], "tokens": 0,
        })

    for e in entries[start_index:]:
        if e.get("run_id") != run_id:
            continue
        ev, d, name = e.get("event"), e.get("detail") or {}, e.get("agent", "")
        if ev == "agent_start":
            a = slot(name)
            chain = e.get("chain") or []
            if len(chain) > 1 and chain[-2] not in a["asked_by"]:
                a["asked_by"].append(chain[-2])
        elif ev == "model_response":
            a = slot(name)
            a["tokens"] += (e.get("usage") or {}).get("total_tokens", 0) or 0
            for p in d.get("parts", []):
                tool = p.get("tool")
                if p.get("type") == "tool_call" and tool not in ("final_result", "ask_teammate"):
                    a["tools"].append(tool)
        elif ev == "delegation_start":
            slot(name)["asked"].append(d.get("teammate"))
        elif ev == "agent_end":
            out = d.get("output") or {}
            a = slot(name)
            text = out.get("decision") or out.get("summary")
            if text:
                a["summaries"].append(text)
            a["approval_request_ids"] += [x for x in out.get("approval_request_ids", []) if x not in a["approval_request_ids"]]
            a["board_post_ids"] += [x for x in out.get("board_post_ids", []) if x not in a["board_post_ids"]]
            if name == "boss" and e.get("depth", 0) == 0:
                outcome = out
        elif ev == "run_end":
            status, usage = d.get("status", "completed"), e.get("usage")

    for a in agents.values():
        counts: dict[str, int] = {}
        for t in a["tools"]:
            counts[t] = counts.get(t, 0) + 1
        a["tools"] = [{"tool": t, "calls": n} for t, n in counts.items()]
    return {"ticket_id": ticket_id, "run_id": run_id, "status": status,
            "agents": list(agents.values()), "outcome": outcome, "usage": usage}


def activity(since: int = -1, ticket_id: int | None = None, run_id: str | None = None,
             limit: int = 100) -> dict:
    """Readable feed items for audit entries after index `since` (newest last)."""
    entries = load_audit()
    items: list[dict] = []
    for i in range(max(since + 1, 0), len(entries)):
        e = entries[i]
        if ticket_id is not None and e.get("ticket_id") != ticket_id:
            continue
        if run_id is not None and e.get("run_id") != run_id:
            continue
        items.extend(_items_for(i, e))
    return {"last_index": len(entries) - 1, "last_reset_index": last_reset_index(entries),
            "items": items[-limit:]}
