"""Facilities: handles the shop space (lease, rent, landlord)."""

from backend.agents.spec import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="facilities",
    title="Facilities",
    prompt_file="facilities.md",
    output_type=SpecialistReport,
    write_tools=frozenset({"post_to_board"}),
    description="The shop space: lease terms, rent amounts and due dates, landlord replies.",
)
