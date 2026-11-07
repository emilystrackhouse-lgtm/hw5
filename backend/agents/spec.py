"""What defines one agent role: its prompt file, output type and MCP tools."""

from __future__ import annotations

from dataclasses import dataclass

from pydantic import BaseModel

from backend.models import AgentName

# Every agent may read the shop through these MCP tools.
READ_TOOLS = frozenset({
    "list_open_tickets",
    "get_ticket",
    "check_stock_shortfall",
    "check_invoice_and_vendor_hold",
    "check_rent_due",
    "list_vendors",
    "get_cash_position",
    "check_discount_margin",
})

# Only the human dashboard may call this. It is never given to any agent.
HUMAN_ONLY_TOOLS = frozenset({"record_human_decision"})


@dataclass(frozen=True)
class AgentSpec:
    name: AgentName
    title: str
    prompt_file: str
    output_type: type[BaseModel]
    write_tools: frozenset[str]          # MCP tools beyond READ_TOOLS
    description: str                     # shown to teammates deciding whom to ask

    @property
    def mcp_tools(self) -> frozenset[str]:
        tools = READ_TOOLS | self.write_tools
        assert not tools & HUMAN_ONLY_TOOLS, f"{self.name} must not get human-only tools"
        return tools
