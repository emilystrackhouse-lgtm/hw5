"""Customer Service: drafts messages for customers (drafts stay on the board)."""

from backend.agents.spec import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="customer_service",
    title="Customer Service",
    prompt_file="customer_service.md",
    output_type=SpecialistReport,
    write_tools=frozenset({"post_to_board"}),
    description="Drafts replies to customers and campus groups; drafts stay on the board, never sent.",
)
