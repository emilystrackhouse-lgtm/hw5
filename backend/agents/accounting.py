"""Accounting: watches cash and invoices, checks margins, prepares payments for human approval."""

from backend.agents.spec import AgentSpec
from backend.models import SpecialistReport

SPEC = AgentSpec(
    name="accounting",
    title="Accounting",
    prompt_file="accounting.md",
    output_type=SpecialistReport,
    write_tools=frozenset({
        "request_payment_approval",
        "request_purchase_order_approval",
        "post_to_board",
    }),
    description="Cash, invoices, margins and discounts; prepares payment and purchase-order requests for human approval.",
)
