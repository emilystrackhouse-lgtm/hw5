"""The human's approval desk (until the dashboard exists).

    python -m backend.approve list
    python -m backend.approve 3 approve --by "Emily Strackhouse"
    python -m backend.approve 4 reject --by "Emily Strackhouse" --note "Not this month"

Calls the MCP tool `record_human_decision`, which no agent can reach. No AI
model is involved. Each decision is appended to output/audit_trail.json.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import uuid

from backend.agents.team import build_mcp_toolset
from backend.audit import AuditTrail


async def main(args: argparse.Namespace) -> None:
    mcp = build_mcp_toolset()
    async with mcp:
        if args.request == "list":
            data = await mcp.direct_call_tool("get_cash_position", {})
            print(json.dumps(data, indent=2))
            return
        result = await mcp.direct_call_tool("record_human_decision", {
            "request_id": int(args.request), "decision": args.decision,
            "decided_by": args.by, "note": args.note,
        })
    AuditTrail().log(run_id=f"human-{uuid.uuid4().hex[:8]}", agent=f"human:{args.by}",
                     event="human_decision", detail={"request_id": int(args.request),
                                                     "decision": args.decision, "result": result})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("request", help="'list', or an approval request ID")
    p.add_argument("decision", nargs="?", choices=["approve", "reject"])
    p.add_argument("--by", help="your name (a human, not an agent)")
    p.add_argument("--note", default="")
    a = p.parse_args()
    if a.request != "list" and (not a.decision or not a.by):
        p.error("give a decision (approve/reject) and --by NAME")
    asyncio.run(main(a))
