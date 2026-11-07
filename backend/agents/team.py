"""The Campus Customs agent team: five PydanticAI agents with full connectivity.

- Every agent uses the same model: gpt-6-luna through Portkey (backend.config).
- Every agent reaches the shop only through the Campus Customs MCP server
  (one stdio process per ticket run). Each role sees only the MCP tools in
  its spec; `record_human_decision` is never given to any agent.
- Every agent has one extra local tool, `ask_teammate`, so any agent can
  delegate to any other. Delegation is capped by depth and count, and an
  agent can't hand work back to someone already in the chain (no loops).
- All agents in a ticket run share one token/request budget (UsageLimits).
- Each step of every agent loop is appended to output/audit_trail.json.
"""

from __future__ import annotations

import sys
import uuid
from typing import Any

from fastmcp.client.transports import StdioTransport
from openai import AsyncOpenAI
from pydantic_ai import Agent, RunContext, Tool, UsageLimitExceeded
from pydantic_ai.mcp import MCPToolset
from pydantic_ai.messages import (
    RetryPromptPart,
    TextPart,
    ThinkingPart,
    ToolCallPart,
    ToolReturnPart,
    UserPromptPart,
)
from pydantic_ai.models import Model
from pydantic_ai.models.openai import OpenAIResponsesModel
from pydantic_ai.providers.openai import OpenAIProvider
from pydantic_ai.settings import ModelSettings
from pydantic_ai.usage import RunUsage, UsageLimits

from backend import config
from backend.agents import accounting, boss, customer_service, facilities, inventory
from backend.agents.spec import AgentSpec
from backend.audit import AuditTrail
from backend.models import AgentName, RunBudget, RunDeps, TicketOutcome

SPECS: dict[str, AgentSpec] = {
    s.name: s
    for s in (boss.SPEC, inventory.SPEC, accounting.SPEC, facilities.SPEC, customer_service.SPEC)
}


# ------------------------------------------------------------- connections ---

def build_portkey_model() -> Model:
    """gpt-6-luna through Portkey's OpenAI-compatible API (the only model allowed)."""
    key = config.portkey_api_key()
    client = AsyncOpenAI(
        api_key=key,
        base_url=config.portkey_base_url(),
        default_headers={"x-portkey-api-key": key},
        timeout=90,
        max_retries=1,
    )
    return OpenAIResponsesModel(config.model_name(), provider=OpenAIProvider(openai_client=client))


# Write tools and the argument that says who is acting. The backend always
# fills it with the real calling agent, so an agent can't sign as a teammate.
IDENTITY_ARGS = {
    "post_to_board": "author",
    "update_ticket_status": "updated_by",
    "request_payment_approval": "requested_by",
    "request_purchase_order_approval": "requested_by",
}


async def stamp_agent_identity(ctx: RunContext[Any], call_tool: Any, name: str, args: dict[str, Any]) -> Any:
    """Overwrite the 'who' argument of write tools with the agent actually calling."""
    field = IDENTITY_ARGS.get(name)
    deps = getattr(ctx, "deps", None)
    if field and isinstance(deps, RunDeps):
        args = {**args, field: deps.agent}
    return await call_tool(name, args)


def build_mcp_toolset() -> MCPToolset:
    """The Campus Customs MCP server, started as a child process over stdio.

    DB_PATH is passed explicitly: FastMCP's stdio transport does not inherit
    this process's environment.
    """
    transport = StdioTransport(
        command=sys.executable,
        args=[str(config.MCP_SERVER_SCRIPT)],
        env={"DB_PATH": str(config.WORKING_DB_PATH)},
        cwd=str(config.PROJECT_ROOT),
    )
    return MCPToolset(transport, id="campus_customs", process_tool_call=stamp_agent_identity)


# ---------------------------------------------------------- audit helpers ---

def usage_dict(u: Any) -> dict[str, Any]:
    if u is None:
        return {}
    inp, out = getattr(u, "input_tokens", 0) or 0, getattr(u, "output_tokens", 0) or 0
    return {
        "requests": getattr(u, "requests", None),
        "tool_calls": getattr(u, "tool_calls", None),
        "input_tokens": inp,
        "output_tokens": out,
        "total_tokens": inp + out,
    }


def describe_parts(parts: Any) -> list[dict[str, Any]]:
    """Turn model message parts into plain dicts for the audit trail."""
    out: list[dict[str, Any]] = []
    for p in parts:
        if isinstance(p, ToolCallPart):
            out.append({"type": "tool_call", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                        "args": p.args_as_dict()})
        elif isinstance(p, ToolReturnPart):
            out.append({"type": "tool_result", "tool": p.tool_name, "tool_call_id": p.tool_call_id,
                        "content": p.content})
        elif isinstance(p, RetryPromptPart):
            out.append({"type": "retry", "tool": p.tool_name, "content": p.content})
        elif isinstance(p, TextPart):
            out.append({"type": "text", "content": p.content})
        elif isinstance(p, ThinkingPart):
            out.append({"type": "thinking", "content": p.content})
        elif isinstance(p, UserPromptPart):
            out.append({"type": "user_prompt", "content": p.content})
        else:
            out.append({"type": type(p).__name__})
    return out


# -------------------------------------------------------------------- team ---

class CampusCustomsTeam:
    """Builds the five agents and runs tickets through them."""

    def __init__(
        self,
        model: Model | None = None,
        mcp: MCPToolset | None = None,
        audit: AuditTrail | None = None,
    ) -> None:
        self.model = model or build_portkey_model()
        self.mcp = mcp or build_mcp_toolset()
        self.audit = audit or AuditTrail()
        self.limits = UsageLimits(
            request_limit=config.RUN_REQUEST_LIMIT,
            total_tokens_limit=config.RUN_TOTAL_TOKENS_LIMIT,
            tool_calls_limit=config.RUN_TOOL_CALLS_LIMIT,
        )
        self.settings = ModelSettings(max_tokens=config.MAX_OUTPUT_TOKENS)
        self.agents: dict[str, Agent] = {name: self._build_agent(spec) for name, spec in SPECS.items()}

    # ----- building -------------------------------------------------------

    def _build_agent(self, spec: AgentSpec) -> Agent:
        prompt = (config.PROMPTS_DIR / spec.prompt_file).read_text()
        allowed = spec.mcp_tools
        shop_tools = self.mcp.filtered(lambda ctx, tool_def, allowed=allowed: tool_def.name in allowed)
        return Agent(
            self.model,
            name=spec.name,
            deps_type=RunDeps,
            output_type=spec.output_type,
            instructions=[prompt, self._run_context],
            toolsets=[shop_tools],
            tools=[Tool(self._ask_teammate, takes_ctx=True, name="ask_teammate")],
            model_settings=self.settings,
            retries=2,
        )

    @staticmethod
    def _run_context(ctx: RunContext[RunDeps]) -> str:
        """Per-run facts added to every agent's prompt."""
        d = ctx.deps
        teammates = "\n".join(
            f"- `{s.name}` ({s.title}): {s.description}"
            for s in SPECS.values() if s.name != d.agent
        )
        left = d.budget.max_delegations - d.budget.delegations_used
        can_delegate = d.depth < d.max_depth and left > 0
        return (
            f"## This run\n"
            f"- You are `{d.agent}`. Ticket: {d.ticket_id}. Run ID: {d.run_id}.\n"
            f"- Delegation chain so far: {' -> '.join(d.chain)} (depth {d.depth} of max {d.max_depth}).\n"
            f"- Delegations left for the whole ticket: {left}. "
            f"{'You may use `ask_teammate`.' if can_delegate else 'You cannot delegate further; finish with what you have.'}\n"
            f"- Teammates you can ask (not anyone already in the chain):\n{teammates}"
        )

    # ----- delegation tool -------------------------------------------------

    async def _ask_teammate(self, ctx: RunContext[RunDeps], teammate: AgentName, task: str) -> dict[str, Any]:
        """Ask another Campus Customs agent to do a specific task and get its report back.

        Args:
            teammate: who to ask: boss, inventory, accounting, facilities or customer_service.
                Not yourself, and not anyone already in the current delegation chain.
            task: a specific, self-contained request. Name the ticket ID and any SKU, size,
                quantity, invoice ID or lease ID the teammate needs, and say what answer you want.
        """
        d = ctx.deps
        refusal = None
        if teammate == d.agent:
            refusal = "You can't delegate to yourself."
        elif teammate in d.chain:
            refusal = f"{teammate} is already in this chain ({' -> '.join(d.chain)}); return your answer instead."
        elif d.depth >= d.max_depth:
            refusal = f"Delegation depth limit ({d.max_depth}) reached; finish with what you have."
        elif d.budget.delegations_used >= d.budget.max_delegations:
            refusal = f"Delegation limit for this ticket ({d.budget.max_delegations}) reached."

        base = dict(run_id=d.run_id, ticket_id=d.ticket_id, agent=d.agent, depth=d.depth, chain=list(d.chain))
        if refusal:
            self.audit.log(**base, event="delegation_refused",
                           detail={"teammate": teammate, "task": task, "reason": refusal})
            return {"ok": False, "refused": refusal}

        d.budget.delegations_used += 1
        self.audit.log(**base, event="delegation_start", detail={"teammate": teammate, "task": task},
                       usage=usage_dict(ctx.usage))
        try:
            report = await self.run_agent(d.for_teammate(teammate), task, usage=ctx.usage)
        except UsageLimitExceeded:
            raise  # the whole ticket stops when the shared budget is spent
        except Exception as exc:  # a teammate failing shouldn't crash the asker
            self.audit.log(**base, event="error", detail={"teammate": teammate, "error": repr(exc)})
            return {"ok": False, "error": f"{teammate} could not finish: {exc}"}
        self.audit.log(**base, event="delegation_end",
                       detail={"teammate": teammate, "report": report.model_dump(mode="json")},
                       usage=usage_dict(ctx.usage))
        return {"ok": True, "teammate": teammate, "report": report.model_dump(mode="json")}

    # ----- agent loop -------------------------------------------------------

    async def run_agent(self, deps: RunDeps, task: str, usage: RunUsage | None = None) -> Any:
        """Run one agent's loop step by step, logging every step to the audit trail."""
        agent = self.agents[deps.agent]
        spec = SPECS[deps.agent]
        base = dict(run_id=deps.run_id, ticket_id=deps.ticket_id, agent=deps.agent,
                    depth=deps.depth, chain=list(deps.chain))
        self.audit.log(**base, event="agent_start", detail={
            "task": task, "prompt_file": f"backend/prompts/{spec.prompt_file}",
            "mcp_tools": sorted(spec.mcp_tools), "output_type": spec.output_type.__name__,
        })

        step = 0
        async with agent.iter(task, deps=deps, usage=usage, usage_limits=self.limits) as run:
            async for node in run:
                step += 1
                if Agent.is_user_prompt_node(node):
                    self.audit.log(**base, step=step, event="user_prompt",
                                   detail={"prompt": node.user_prompt})
                elif Agent.is_model_request_node(node):
                    self.audit.log(**base, step=step, event="model_request",
                                   detail={"parts": describe_parts(node.request.parts)})
                elif Agent.is_call_tools_node(node):
                    resp = node.model_response
                    self.audit.log(**base, step=step, event="model_response", detail={
                        # What the code asked for, and what Portkey says served it
                        # (Portkey may label the gpt-6-luna deployment "gpt-6-luna-global").
                        "requested_model": getattr(self.model, "model_name", None),
                        "served_model_label": resp.model_name,
                        "finish_reason": getattr(resp, "finish_reason", None),
                        "parts": describe_parts(resp.parts),
                    }, usage=usage_dict(resp.usage))
            output = run.result.output
            total = usage_dict(run.usage)

        self.audit.log(**base, step=step + 1, event="agent_end",
                       detail={"output": output.model_dump(mode="json")}, usage=total)
        return output

    async def run_ticket(self, ticket_id: int, run_id: str | None = None) -> TicketOutcome:
        """Have the Boss work one ticket from start to finish."""
        deps = RunDeps(
            run_id=run_id or uuid.uuid4().hex[:12],
            ticket_id=ticket_id,
            agent="boss",
            depth=0,
            chain=["boss"],
            budget=RunBudget(max_delegations=config.MAX_DELEGATIONS_PER_RUN),
            max_depth=config.MAX_DELEGATION_DEPTH,
        )
        usage = RunUsage()
        base = dict(run_id=deps.run_id, ticket_id=ticket_id, agent="boss", depth=0, chain=["boss"])
        self.audit.log(**base, event="run_start", detail={
            "model": getattr(self.model, "model_name", str(self.model)),
            "database": str(config.WORKING_DB_PATH.relative_to(config.PROJECT_ROOT))
            if config.WORKING_DB_PATH.is_relative_to(config.PROJECT_ROOT) else str(config.WORKING_DB_PATH),
            "limits": {
                "total_tokens": config.RUN_TOTAL_TOKENS_LIMIT,
                "requests": config.RUN_REQUEST_LIMIT,
                "tool_calls": config.RUN_TOOL_CALLS_LIMIT,
                "max_output_tokens_per_reply": config.MAX_OUTPUT_TOKENS,
                "max_delegation_depth": config.MAX_DELEGATION_DEPTH,
                "max_delegations": config.MAX_DELEGATIONS_PER_RUN,
            },
        })
        task = (
            f"Work ticket {ticket_id} from start to finish. Read it with get_ticket, bring in the "
            "teammates it needs, make the final call, update the board, and return your TicketOutcome."
        )
        try:
            async with self.mcp:  # one MCP server process for the whole ticket
                outcome = await self.run_agent(deps, task, usage=usage)
        except UsageLimitExceeded as exc:
            self.audit.log(**base, event="run_end", usage=usage_dict(usage),
                           detail={"status": "stopped_by_limit", "error": str(exc)})
            raise
        except Exception as exc:
            self.audit.log(**base, event="error", detail={"error": repr(exc)}, usage=usage_dict(usage))
            self.audit.log(**base, event="run_end", usage=usage_dict(usage), detail={"status": "failed"})
            raise
        self.audit.log(**base, event="run_end", usage=usage_dict(usage), detail={
            "status": "completed", "final_status": outcome.final_status,
            "delegations_used": deps.budget.delegations_used,
        })
        return outcome
