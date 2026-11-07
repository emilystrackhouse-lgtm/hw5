"""Boss: reads each ticket, decides who works on it, and makes the final call."""

from backend.agents.spec import AgentSpec
from backend.models import TicketOutcome

SPEC = AgentSpec(
    name="boss",
    title="Boss",
    prompt_file="boss.md",
    output_type=TicketOutcome,
    write_tools=frozenset({"update_ticket_status", "post_to_board"}),
    description="Leads the team: reads tickets, assigns work, makes the final call.",
)
