"""Run the agent team on tickets from the command line.

    python -m backend.run_ticket 101          # one ticket
    python -m backend.run_ticket --all        # every open ticket, in order
    python -m backend.run_ticket --all --reset  # reset the database first (full run)

Every step is appended to output/audit_trail.json. Payments are only
*requested*; approve them with `python -m backend.approve`.
"""

from __future__ import annotations

import argparse
import asyncio
import json

from backend.agents.team import CampusCustomsTeam
from backend.config import ConfigError


async def main(ticket_ids: list[int], run_all: bool) -> None:
    team = CampusCustomsTeam()
    if run_all:
        async with team.mcp:
            data = await team.mcp.direct_call_tool("list_open_tickets", {})
        ticket_ids = [t["id"] for t in data["open_tickets"]]
        print(f"Open tickets: {ticket_ids}")
    for tid in ticket_ids:
        print(f"\n=== Ticket {tid} ===")
        outcome = await team.run_ticket(tid)
        print(json.dumps(outcome.model_dump(mode="json"), indent=2))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("tickets", nargs="*", type=int)
    parser.add_argument("--all", action="store_true", help="run every open ticket")
    parser.add_argument("--reset", action="store_true", help="reset the database to the original first")
    args = parser.parse_args()
    if not args.tickets and not args.all:
        parser.error("give ticket IDs or --all")
    if args.reset:
        from backend.reset_db import reset
        reset()
    try:
        asyncio.run(main(args.tickets, args.all))
    except ConfigError as exc:
        raise SystemExit(f"Setup problem: {exc}")
