"""Inventory: checks stock by SKU and size, spots shortfalls, finds the restock vendor."""

from backend.agents.spec import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="inventory",
    title="Inventory",
    prompt_file="inventory.md",
    output_type=SpecialistReport,
    write_tools=frozenset({"post_to_board"}),
    description="Stock by SKU and size, shortfalls, which vendor can restock and how fast.",
)
