"""Data types shared by the Campus Customs agent team.

- AgentName: the five roles.
- RunDeps / RunBudget: what every agent carries through one ticket run.
- SpecialistReport: what Inventory, Accounting, Facilities and Customer
  Service hand back when they are asked for help.
- TicketOutcome: the Boss's final call on a ticket.
- AuditEntry: one line in output/audit_trail.json.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field

AgentName = Literal["boss", "inventory", "accounting", "facilities", "customer_service"]
AGENT_NAMES: tuple[AgentName, ...] = (
    "boss", "inventory", "accounting", "facilities", "customer_service",
)

TicketStatus = Literal["open", "in_progress", "awaiting_approval", "resolved"]


# ---------------------------------------------------------------- run state ---

@dataclass
class RunBudget:
    """Counters shared by every agent in one ticket run (mutable on purpose)."""

    max_delegations: int
    delegations_used: int = 0


@dataclass
class RunDeps:
    """Passed to every agent. A delegated agent gets a copy one level deeper."""

    run_id: str
    ticket_id: int | None
    agent: AgentName
    depth: int
    chain: list[AgentName]
    budget: RunBudget
    max_depth: int

    def for_teammate(self, teammate: AgentName) -> "RunDeps":
        return replace(self, agent=teammate, depth=self.depth + 1, chain=[*self.chain, teammate])


# ------------------------------------------------------------ agent outputs ---

class Fact(BaseModel):
    """One fact an agent relies on, with the MCP tool it came from."""

    label: str = Field(description="What the fact is, e.g. 'tee size S on hand'.")
    value: str = Field(description="The value exactly as the tool returned it.")
    source_tool: str = Field(description="The MCP tool that returned it.")


class SpecialistReport(BaseModel):
    """What a teammate hands back to whoever asked for help."""

    agent: AgentName
    summary: str = Field(description="Two or three plain sentences answering the task.")
    facts: list[Fact] = Field(default_factory=list, description="Database facts used, each with its source tool.")
    actions_taken: list[str] = Field(default_factory=list, description="Anything written to the board or requested.")
    approval_request_ids: list[int] = Field(default_factory=list, description="Approval requests created (waiting on a human).")
    board_post_ids: list[int] = Field(default_factory=list)
    recommendation: str = Field(default="", description="What this agent suggests the Boss decide.")
    open_questions: list[str] = Field(default_factory=list, description="What is still unknown or needs a human.")


class TicketOutcome(BaseModel):
    """The Boss's final call on one ticket."""

    ticket_id: int
    decision: str = Field(description="The final call, in two to four plain sentences.")
    final_status: TicketStatus
    agents_consulted: list[AgentName] = Field(default_factory=list)
    key_facts: list[Fact] = Field(default_factory=list)
    approval_request_ids: list[int] = Field(default_factory=list, description="Payments or orders waiting on a human.")
    board_post_ids: list[int] = Field(default_factory=list, description="Drafts and notes left on the board.")
    human_next_steps: list[str] = Field(default_factory=list, description="What the human must approve or decide.")
    risks: list[str] = Field(default_factory=list, description="Cash, timing or customer risks still open.")


# ------------------------------------------------------------------- audit ---

AuditEvent = Literal[
    "run_start",            # a ticket run begins
    "agent_start",          # an agent loop begins (Boss or a delegated teammate)
    "user_prompt",          # the task text given to the agent
    "model_request",        # what was sent to the model this step (tool results, retries)
    "model_response",       # what the model answered (text, tool calls) + token usage
    "delegation_start",     # one agent asks another for help
    "delegation_end",
    "delegation_refused",   # limit hit, or asked itself
    "agent_end",            # an agent loop finished with its output
    "run_end",              # whole ticket finished, with total usage
    "error",
    "human_decision",       # a human approved or rejected a request
]


class AuditEntry(BaseModel):
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat(timespec="milliseconds"))
    run_id: str
    ticket_id: int | None = None
    agent: str
    depth: int = 0
    chain: list[str] = Field(default_factory=list)
    step: int | None = None
    event: AuditEvent
    detail: dict[str, Any] = Field(default_factory=dict)
    usage: dict[str, Any] | None = None
