# Campus Customs Multi-Agent Operations: Harness

This document explains, in plain language, how the Campus Customs agent team works: the data it uses, the tools it can call, the five agents, the backend routes, the dashboard a human uses, and the safety rules around customers and money. It was built up one problem at a time, and each section notes the problems it came from. Section 9 has the results of the final run that resolved all three tickets.

---

## 0. The system at a glance

```
 Human (browser)
     │  clicks: start a ticket · Approve / Reject · Reset
     ▼
 React dashboard   frontend/  (Vite, http://localhost:5173)
     │  HTTP + JSON
     ▼
 FastAPI backend   backend/main.py  (http://localhost:8000)
     │                          │
     │ starts runs              │ human Approve → record_human_decision
     ▼                          │
 Agent team (PydanticAI, gpt-6-luna via Portkey)
   Boss ⇄ Inventory ⇄ Accounting ⇄ Facilities ⇄ Customer Service
     │  every shop read/write is an MCP tool call
     ▼
 MCP server        mcp_server/server.py  (FastMCP, stdio)
     ▼
 data/campus_customs_new.db  (working copy; data/campus_customs.db = untouched original)

 Every agent step and human decision → output/audit_trail.json (append-only)
```

**How to run it:**

| Step | Command (from the project root `hw5/` unless noted) |
|---|---|
| 1. Install once | `python -m venv .venv && .venv/bin/pip install -r requirements.txt`; `cd frontend && npm install` |
| 2. Secrets | Copy `.env.example` to `.env` and set `PORTKEY_API_KEY`. `OPENAI_MODEL` must be `gpt-6-luna`. |
| 3. Backend | `cd backend && uvicorn main:app --reload --port 8000` |
| 4. Dashboard | `cd frontend && npm run dev` → http://localhost:5173 |
| 5. Fresh start | **Reset shop** button in the dashboard (or `python -m backend.reset_db`) |
| Vibe coder | `.mcp.json` registers the same MCP server as `campus-customs` |

**Where things live:**

| Path | What it is |
|---|---|
| `mcp_server/server.py` | The 15 MCP tools: the only door to the database |
| `backend/agents/` | One file per agent role, plus `team.py` (agent loops, delegation, audit, limits) |
| `backend/prompts/` | One prompt file per agent |
| `backend/models.py` | Data types: run state, agent reports, audit entries |
| `backend/config.py` | The only place the model name and limits live |
| `backend/main.py`, `backend/activity.py` | API routes and the activity feed |
| `frontend/src/` | The dashboard |
| `output/` | This harness, plans and results (`desk_tickets.html`), `resolved_tickets.json`, `resolved_board.html`, `design.md`, `audit_trail.json` |

---

## 1. The shop database (Problem 2)

The agents run the shop from one SQLite database.

| File | Role |
|---|---|
| `data/campus_customs.db` | The original database. It is read-only and never changed. It is the reset point. |
| `data/campus_customs_new.db` | The working copy. The MCP server reads and writes it as tickets are resolved. Reset copies the original over it. |

**"Today" for the shop is 2026-08-31** (from `desk.date_today`). Every agent and tool uses this date, never the real calendar, to decide what is due or overdue.

### The nine original tables

**`desk`: the shop's clock (1 row).** Every agent uses it to judge deadlines: it makes invoice 501 three days overdue and rent due in two days.

| Field | Meaning |
|---|---|
| `date_today` | The shop's "today": 2026-08-31 |
| `notes` | Free-text notes (empty) |

**`tickets`: the work board (3 rows).** This is the Boss's inbox. The ticket's type and linked IDs say which teammates to bring in, and `status` shows the human what's done.

| Field | Meaning |
|---|---|
| `id` | Ticket number (101–103) |
| `type` | `customer_order`, `rent_notice` or `price_override` |
| `requester` | Who asked |
| `subject` | Short title |
| `sku`, `size`, `qty` | Product, size and quantity (blank if not about a product) |
| `lease_id` | Links to `leases.id` for rent tickets |
| `invoice_id` | Links to `invoices.id` when a vendor bill is involved |
| `status` | `open` → `in_progress` → `awaiting_approval` → `resolved` |
| `notes` | The request in the requester's own words |
| `created_at` | When the ticket arrived |

**`inventory`: stock on hand (10 rows, one per product and size).** Inventory checks whether an order can be filled and how big the shortfall is. Two items start out of stock: the Classic Bulldog Tee in size S and the Crest Mug.

| Field | Meaning |
|---|---|
| `sku` | Product code, e.g., `CC-TEE-WHITE` |
| `name` | Product name |
| `size` | S, M, L, XL or OS (one size) |
| `qty` | Units in stock |
| `location` | Aisle |

**`pricing`: cost and price (4 rows).** Accounting uses it to price restocks and to judge how deep a discount can go.

| Field | Meaning |
|---|---|
| `sku` | Product code |
| `unit_cost` | What the shop pays per unit |
| `list_price` | What the shop charges per unit |

| Product | Cost | Price | Margin per unit |
|---|---|---|---|
| Basic Hoodie `CC-HOOD-NAVY` | $22.00 | $58.00 | $36.00 (62%) |
| Classic Bulldog Tee `CC-TEE-WHITE` | $8.00 | $28.00 | $20.00 (71%) |
| Yale Cap `CC-HAT-BLUE` | $6.00 | $22.00 | $16.00 (73%) |
| Crest Mug `CC-MUG-CREST` | $3.50 | $14.00 | $10.50 (75%) |

**`vendors`: who can restock (3 rows).** Inventory matches a shortfall to a vendor and uses `lead_days` for realistic dates. A vendor **won't ship** while it has an open unpaid invoice.

| Field | Meaning |
|---|---|
| `id` | Vendor number |
| `name` | Vendor name |
| `specialty` | What it supplies |
| `lead_days` | Days from order to delivery |

| Vendor | Supplies | Lead time |
|---|---|---|
| 1. Bulldog Print Co | Apparel reprints (tees, hoodies) | 5 days |
| 2. Elm City Gifts | Mugs and small goods | 3 days |
| 3. QuickShip CT | Local courier | 1 day |

**`leases`: the shop space (1 row).** This is Facilities' table: what rent is owed and when.

| Field | Meaning |
|---|---|
| `id` | Lease number |
| `space_name` | Chapel Street shop |
| `landlord` | Elm City Properties |
| `monthly_rent` | $2,400.00 |
| `next_due` | 2026-09-02 at the start |
| `notes` | Free text (empty) |

**`cash_accounts`: money available (1 row).** Accounting checks this before proposing any payment. **No money comes in** during this homework, and a payment that would make the balance negative is refused.

| Field | Meaning |
|---|---|
| `name` | `checking` |
| `balance` | $3,400.00 at the start |
| `date` | Balance as of 2026-08-31 |

**`payments`: money paid out (0 rows at the start).** This is the payment record. Every row exists only because a human approved it, and `approved_by` names that person.

| Field | Meaning |
|---|---|
| `id` | Payment number |
| `kind` | `invoice`, `rent` or `purchase_order` |
| `ref_id` | The invoice or lease paid (for a purchase order, the approval request) |
| `amount` | Dollars paid |
| `account` | Cash account it came from |
| `paid_at` | Shop date of payment |
| `approved_by` | The human who approved it |

**`invoices`: bills owed to vendors (1 row).** An open invoice blocks its vendor. The one invoice, **#501**, is $840 owed to Bulldog Print Co for a "Rush reprint CC-TEE-WHITE S." It was due 2026-08-28, so it starts three days overdue.

| Field | Meaning |
|---|---|
| `id` | Invoice number |
| `vendor_id` | Links to `vendors.id` |
| `amount` | Amount owed |
| `due_date` | When it was due |
| `status` | `open` or `paid` |
| `description` | What it was for |

### Two tables the MCP server adds for the team's own work (Problem 5)

Both are created in the working copy when the server first connects, and both are empty after every reset.

| Table | Holds | Key fields |
|---|---|---|
| `approval_requests` | Payments and purchase orders waiting on a human | `ticket_id`, `kind`, `ref_id`/`vendor_id`/`sku`/`size`/`qty`, `amount` (always taken from the database), `reason`, `requested_by`, `status` (`pending` / `approved` / `rejected` / `refused`), `decided_by`, `payment_id` |
| `board_posts` | Drafts and notes on the board. **Nothing is ever sent.** | `ticket_id`, `kind` (`customer_draft`, `landlord_draft`, `vendor_draft`, `internal_note`, `resolution`), `author`, `recipient`, `subject`, `body` |

### How the tables connect

```
tickets ──sku/size──▶ inventory ──sku──▶ pricing
   ├──invoice_id──▶ invoices ──vendor_id──▶ vendors
   └──lease_id────▶ leases
approval_requests ──ticket_id──▶ tickets          board_posts ──ticket_id──▶ tickets
payments ──kind + ref_id──▶ invoices · leases · approval_requests
payments ──account──▶ cash_accounts
```

---

## 2. The three tickets and the cash squeeze (Problem 2)

| Ticket | What it asks | What the data shows |
|---|---|---|
| **101** Tauhid Zaman: 1 × Bulldog tee, size S | Fill a customer order | 0 size S on hand. Invoice 501 ($840, 3 days overdue) is a rush reprint of this exact tee and is holding Bulldog Print Co (5-day lead time). |
| **102** Elm City Properties: rent due | Pay rent | Lease 1: $2,400 due 2026-09-02, two days away. |
| **103** Yale AI Club: 20 hoodies, size M, bulk discount | Price a bulk order | 8 of 20 on hand, 12 short. The restock costs 12 × $22 = $264. Cost $22 / list $58 leaves room to discount. |

The tickets compete for one **$3,400** balance with no money coming in. Rent ($2,400) + invoice 501 ($840) + hoodie restock ($264) = $3,504, which is **$104 more than the shop has**. The team has to set priorities (rent and the overdue invoice first) and can't do everything.

---

## 3. MCP tools (Problems 3, 5 and 7)

`mcp_server/server.py` (FastMCP) is the agents' **only** source of shop information. It points at `data/campus_customs_new.db` (`DB_PATH`), treats `desk.date_today` as today, and answers only from the database. Problem 3 started it with three read tools; Problem 5 grew it to 13; Problem 7 added two for the dashboard.

| # | Tool | Tables it uses | Reads / writes | Who can call it | Added |
|---|---|---|---|---|---|
| 1 | `list_open_tickets` | tickets, desk | read | all agents | P5 |
| 2 | `get_ticket` | tickets, board_posts, approval_requests, desk | read | all agents | P5 |
| 3 | `check_stock_shortfall` | inventory, pricing | read | all agents | P3 |
| 4 | `check_invoice_and_vendor_hold` | invoices, vendors, desk | read | all agents | P3 |
| 5 | `check_rent_due` | leases, desk, cash_accounts | read | all agents | P3 |
| 6 | `list_vendors` | vendors, invoices, desk | read | all agents | P5 |
| 7 | `get_cash_position` | cash_accounts, approval_requests, payments | read | all agents | P5 |
| 8 | `check_discount_margin` | pricing | read | all agents | P5 |
| 9 | `request_payment_approval` | tickets, invoices or leases, cash_accounts → writes approval_requests | write, **no money moves** | Accounting | P5 |
| 10 | `request_purchase_order_approval` | tickets, vendors, inventory, pricing, invoices, cash_accounts, desk → writes approval_requests | write, **no money moves** | Accounting | P5 |
| 11 | `post_to_board` | tickets → writes board_posts | write (drafts and notes only) | all agents, limited by post kind (section 8) | P5 |
| 12 | `update_ticket_status` | tickets, approval_requests → writes tickets, board_posts | write | Boss | P5 |
| 13 | `list_tickets` | tickets, approval_requests, board_posts, desk | read | dashboard | P7 |
| 14 | `list_approval_requests` | approval_requests, vendors, cash_accounts | read | dashboard | P7 |
| 15 | `record_human_decision` | approval_requests, cash_accounts, invoices, leases, vendors, desk → writes payments, cash_accounts, invoices or leases, approval_requests | write, **moves money** | **human only** (dashboard Approve/Reject) | P5 |

How each tool helped resolve the tickets (Problems 3 and 5):
- **101:**
  - `check_stock_shortfall` showed 0 tees in size S.
  - `check_invoice_and_vendor_hold(501)` showed the $840 bill holding Bulldog Print Co, and that its description covers this exact tee.
  - `request_payment_approval` put the $840 in front of the human.
- **102:** `check_rent_due(1)` confirmed $2,400 due in 2 days, covered by cash. `request_payment_approval` put the rent in front of the human.
- **103:**
  - `check_stock_shortfall` showed 8 of 20 in stock.
  - `check_discount_margin` priced 10/15/20% off (15% → $49.30 each, 55.4% margin; break-even only at 62.1% off).
  - `get_cash_position` showed the $264 restock wouldn't fit the $160 left.
- **All tickets:** `get_ticket`, `post_to_board` (drafts stay on the board) and `update_ticket_status` move each ticket to resolved.

The vibe coder reaches the same server through `.mcp.json` (Problem 4). Claude Code called `check_stock_shortfall`, `check_invoice_and_vendor_hold` and `check_rent_due` natively, and `output/mcp_smoke.json` records each prompt, tool and real output. All 33 checked values matched the database.

---

## 4. The five agents (Problem 5)

Five PydanticAI agents, all on **gpt-6-luna through Portkey** (`PORTKEY_API_KEY`). The model name lives only in `backend/config.py`, which refuses to start if `OPENAI_MODEL` is anything else. Each agent has its own prompt file, its own role file and its own set of MCP tools.

| Agent | Role file / prompt | Responsibilities | MCP tools beyond the 8 read tools | Returns |
|---|---|---|---|---|
| **Boss** | `agents/boss.py` · `prompts/boss.md` | Reads each ticket, brings in only the teammates it needs, makes the final call (including how big a discount to offer), and closes out the board: `awaiting_approval` if money is pending, otherwise `resolved` | `update_ticket_status`, `post_to_board` (internal notes, resolutions) | `TicketOutcome` |
| **Inventory** | `agents/inventory.py` · `prompts/inventory.md` | Stock by SKU and size, shortfalls, alternative sizes, matching vendor, lead time and holds. Checks whether an open invoice already covers the item, to avoid duplicate orders. | `post_to_board` (internal notes, vendor drafts) | `SpecialistReport` |
| **Accounting** | `agents/accounting.py` · `prompts/accounting.md` | Cash position, invoices, margins and discounts. Prepares payment and purchase-order requests **for human approval**, ranks spending when cash is tight, and never orders twice. | `request_payment_approval`, `request_purchase_order_approval`, `post_to_board` | `SpecialistReport` |
| **Facilities** | `agents/facilities.py` · `prompts/facilities.md` | Lease, rent and landlord. Checks notices against the lease, asks Accounting to prepare rent, drafts the landlord reply. | `post_to_board` (landlord drafts) | `SpecialistReport` |
| **Customer Service** | `agents/customer_service.py` · `prompts/customer_service.md` | The only author of customer drafts. Quotes only facts and offers the team confirmed, never misquotes the requester, never reveals internal matters. | `post_to_board` (customer drafts) | `SpecialistReport` |

**Full connectivity:** every agent also has `ask_teammate(teammate, task)`, so any agent can hand a specific task to any other and get its report back. Example: Boss → Facilities → Accounting on ticket 102. `backend/agents/team.py` runs each agent's loop step by step (think → call a tool → read the result → repeat → typed answer). An agent can't ask itself or anyone already in the chain, and chains stop at 2 hand-offs, with at most 10 per ticket. One MCP connection serves the whole team.

### Audit trail (Problem 5)

Every step of every agent loop is appended to `output/audit_trail.json`:
- run start and end, with model, limits, status and total tokens;
- each agent's start, with task, prompt file and allowed tools;
- every model request (tool results, retries) and response (text, tool calls with arguments, tokens, and `requested_model: gpt-6-luna` beside Portkey's served label);
- every hand-off: started, finished or refused;
- each agent's final answer;
- errors, resets and human approval decisions.

Each entry carries a `run_id`, ticket, agent, depth, chain and timestamp, so a run can be replayed in order. The file is **append-only** and written safely (temporary file, then swap), so earlier runs are always kept.

---

## 5. API routes (Problems 7 and 8)

`backend/main.py`. Start it from `backend/` with `uvicorn main:app --reload --port 8000`. It serves `http://localhost:8000` (the root opens `/docs`) and allows the dashboard's origin, `http://localhost:5173`. It keeps one long-lived MCP connection; every shop read and write goes through it.

- `GET http://localhost:8000/api/tickets`: tickets 101–103 with current status (open, in_progress, awaiting_approval or resolved), pending approvals, and whether agents are working on each.
- `GET http://localhost:8000/api/tickets/{ticket_id}`: one ticket with its drafts, notes and approval requests.
- `POST http://localhost:8000/api/tickets/{ticket_id}/run`: starts the agent team on that ticket in the background and returns a `run_id` right away. One run at a time, because tickets share the cash.
- `GET http://localhost:8000/api/runs/{run_id}`: a run's status (running, completed, failed, stopped_by_limit) and the Boss's outcome. `GET /api/runs` lists all runs.
- `GET http://localhost:8000/api/tickets/{ticket_id}/contributions`: what each agent did on the ticket's latest run (summary, tools, who asked whom, tokens) plus the Boss's call. Added in Problem 8.
- `GET http://localhost:8000/api/activity?since={index}`: new agent messages, tool calls, tool results and hand-offs since the last refresh. Can be filtered by `ticket_id` or `run_id`.
- `GET http://localhost:8000/api/approvals`: payments and purchase orders waiting on a human, each with the balance it would leave. `?status=all` shows decided ones too.
- `POST http://localhost:8000/api/approvals/{request_id}/approve`: **the only route that moves money**, triggered by a human's Approve click. In one transaction it lowers cash, writes `payments` with the approver's name, and marks the invoice paid or moves the lease due date forward. It refuses if cash would go negative or the vendor is on hold, and it rejects agent names as approvers. Once a ticket's last pending request is decided, it marks the ticket `resolved`.
- `POST http://localhost:8000/api/approvals/{request_id}/reject`: a human declines; no money moves. The ticket also resolves once nothing is pending.
- `GET http://localhost:8000/api/cash`: the checking balance from `cash_accounts`, plus pending requests and payments made.
- `POST http://localhost:8000/api/reset`: restores `data/campus_customs_new.db` to the original values. Refused while agents are working. The audit trail is kept.
- `GET http://localhost:8000/api/health`: the server is up; shows the model (gpt-6-luna) and database.

---

## 6. The dashboard (Problem 8)

`frontend/` (React 19 + Vite + TypeScript), the **Campus Customs Ops Floor**. Start it with `npm run dev` and open http://localhost:5173. It calls the backend at `http://localhost:8000` (`VITE_API_BASE`). Full design rationale is in `output/design.md`.

- **Left, ticket board:** one card per ticket with a status pill, a "payments waiting on you" flag, and a tilted **RESOLVED ✓** stamp once done. A link like `#ticket=103` opens a ticket directly.
- **Center, the stage:**
  - **Ticket header:** a **Start the agent team** button and a four-step tracker (Open → Agents working → Needs your OK → Resolved).
  - **Agent roster:** the five agents, each with its own color and icon. The one working now pulses, and agents not involved fade.
  - **Live feed:** chat bubbles, tool calls in plain English, foldable tool results, and two-color hand-off cards, with sub-agent work indented. It refreshes every 1.5 seconds while agents work.
  - **"Who did what":** the Boss's call plus a card per agent.
  - **"On the board":** drafts shown as paper notes stamped NOT SENT.
- **Right, money desk:**
  - The checking balance, which counts down after a payment, with a red −$ chip.
  - A meter showing cash left and cash promised.
  - A paid-out list.
  - The approval queue: each card shows amount, reason, which agent prepared it, and the balance after (with a red warning if it would overdraw). **Approve** takes two clicks (Approve → Confirm), and both Approve and Reject need a name in **Approving as**.
- **Reset shop** restores the database, after a confirm prompt.

---

## 7. Safety rules (Problems 5 and 8)

### Money
- **Only a human can pay.**
  - Agents can only *request* a payment.
  - `record_human_decision` is the only tool that moves money. It's hidden from all five agents (enforced in `backend/agents/spec.py`) and called only by the dashboard's Approve/Reject routes.
  - It rejects approvers named after an agent.
- **Agents can't choose amounts.** Request amounts come from the database: invoice amount, monthly rent, or unit cost × quantity.
- **No negative balances.** Approval re-checks cash inside one database transaction. If paying would overdraw, nothing is paid and the request is marked `refused`.
- **Vendor holds are enforced.** A purchase order to a vendor with an open invoice can't be paid.
- **No double payments.** A second request for the same invoice or rent is refused while one is pending or approved, and a paid invoice can't be requested again. The prompts also tell agents not to order an item an open invoice already covers.
- **Every payment is recorded.** Each one writes `payments.approved_by`, updates the invoice or lease, and is logged in the audit trail. Tickets can't be marked resolved while a payment waits on a human.

### Customers and outside parties
- **Nothing is sent.** There is no email or messaging tool. `post_to_board` only saves drafts and always returns `sent: false`, and the dashboard stamps every draft NOT SENT.
- **One author per kind of message**, enforced by the MCP server:

| Post kind | Only these agents may post it |
|---|---|
| `customer_draft` | Customer Service |
| `landlord_draft` | Facilities |
| `vendor_draft` | Inventory, Accounting |
| `resolution` | Boss |
| `internal_note` | any agent |

- **Agents can't sign as someone else.** The backend overwrites `author`, `updated_by` and `requested_by` with the agent actually calling (`stamp_agent_identity` in `team.py`).
- **Customer Service** quotes only facts and offers the team confirmed. It restates only what the requester actually asked, and never reveals unpaid bills, cash or margins.
- **No invented data.** Every fact comes from an MCP tool result, and agent reports list each fact with its source tool.

### Token use (all agents in one ticket run combined; set in `backend/config.py`)

| Limit | Default | When it's hit |
|---|---|---|
| Total tokens per ticket | 150,000 | Run stops; audit trail records `stopped_by_limit` |
| Model requests per ticket | 40 | Same |
| Tool calls per ticket | 60 | Same |
| Output tokens per reply | 1,500 | Reply is cut off |
| Delegation depth | 2 hand-offs | `ask_teammate` refuses; agent finishes with what it has |
| Delegations per ticket | 10 | Same |

Other ways the team saves tokens:
- Only gpt-6-luna is used.
- Agents are told to involve only the teammates a ticket needs.
- Loop-backs to someone already in the chain are refused.
- Only one ticket runs at a time.
- Every token count is logged.

---

## 8. How the agents were tuned (Problem 5 test runs)

Two earlier live runs from the command line (since reset) shaped the final behavior:
- **Run 1:** the team ordered a $8 tee that invoice 501 already covered, and a draft quoted "your request for 10% off," which the club never asked for. **Fix:** agents now read open invoice descriptions before ordering, and Customer Service may restate only what the ticket says.
- **Run 2:** both fixes held, but the Boss wrote its own competing customer draft. **Fix:** the one-author-per-message rule and identity stamping (section 7).
- **Problem 8:** the Boss now owns the discount decision (only payments need a human), and tickets resolve automatically once their payments are decided.
- **Model label:** some audit entries show Portkey's served label `gpt-6-luna-global`. That's the deployment that answered; the code only ever requests `gpt-6-luna`, and every entry records `requested_model: gpt-6-luna`.

---

## 9. Final run: all three tickets resolved (Problem 9)

The database was reset from the dashboard, then each ticket was started from the dashboard in order. Payments were approved in the dashboard by "Emily Strackhouse (via Claude)".

| Ticket | Agents and hand-offs | Outcome | Human approval | Cash | Tokens |
|---|---|---|---|---|---|
| 101 | Boss → Inventory, Boss → Accounting (×2), Boss → Customer Service | Invoice 501 already covers the tee: pay it, no duplicate order. Draft to Tauhid. | Request #1, invoice 501, **approved** | −$840 → $2,560 | 67,813 |
| 102 | Boss → Facilities → Accounting | Rent confirmed against the lease. Landlord draft. | Request #2, rent, **approved** | −$2,400 → $160 | 44,133 |
| 103 | Boss → Inventory, Boss → Accounting, Boss → Customer Service | 15% bulk discount ($49.30 each) on the 8 in stock. No restock: $264 would overdraw $160. | none needed | $0 → $160 | 55,772 |

- **Cash reconciles:** $3,400.00 − $840.00 − $2,400.00 = **$160.00**, matching `cash_accounts`. 2 payments, 2 approved requests, none pending or refused. Invoice 501 is paid, and the lease's next due date is 2026-10-02.
- **Evidence:**
  - `output/desk_tickets.html`: Expected vs. Actual for each ticket, plus the Cash tab.
  - `output/resolved_tickets.json`: outcomes, each agent's contribution, approvals.
  - `output/resolved_board.html`: dashboard screenshots.
  - `output/audit_trail.json`: every step, appended after all earlier entries.
