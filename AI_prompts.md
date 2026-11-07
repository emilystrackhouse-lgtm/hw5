# Homework 5 — AI Prompt Log

This file is the running record of AI-assisted work completed during the Homework 5 session (Campus Customs Multi-Agent Operations). It is updated as we work. Each problem has its own section, and every section includes:

- **Problem number and title**
- **Original prompt**: at least one prompt typed in this session, describing the task in the student's own words
- **Follow-up prompt** (when used): the prompt as typed, plus one sentence on what was missing from the first response
- **Work completed**: files created or changed, key decisions, and outcomes

Each problem is described one at a time in the student's own words. The full assignment page and its URL are never pasted in.

## Problem 1 — Vibe Coder Prompts

### Original prompt

> here's context for Homework 5 - please create a new folder in AI Foundations for Managers accordingly

(Shared alongside a screenshot of the Homework 5 "Scenario and data" section.)

### Work completed

- Created `Homework/Homework 5/` alongside Homeworks 1–4, with an `output/` folder for deliverables.
- Unzipped the Homework 5 data pack (`~/Downloads/data (2).zip`) into `data/campus_customs.db`. Confirmed it has the nine tables from the assignment: `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `leases`, `cash_accounts`, `payments`, `invoices`. The shop's "today" (`desk.date_today`) is 2026-08-31.
- Made the working copy `data/campus_customs_new.db` for the MCP server and backend, and set the original to read-only so it stays untouched for resets.
- Added `.gitignore` (keeps `.env`, virtual environments, and `node_modules` out of the public repo) and `.env.example` with `PORTKEY_API_KEY`, `OPENAI_MODEL=gpt-6-luna`, and the database path.

### Follow-up prompt: Confirm and structure the prompt log

> Please double check you created a file called `AI_prompts.md` at the start of this assignment and update it as we work. Give each problem its own section, labeled with the problem number and title.
>
> For each section, include at least one prompt I actually typed describing the task in my own words. If I use a follow-up prompt, include it along with one sentence explaining what was missing from the first response.
>
> I'll describe each problem individually instead of pasting the entire assignment page or URL and asking you to complete everything.

**What was missing from the first response:** the first response created the log but did not set the rules for it: a section per problem, the student's own wording, and a one-sentence note on what each follow-up fixed.

### Work completed

- Confirmed `AI_prompts.md` was created at the start of Homework 5, in `Homework/Homework 5/`.
- Rewrote the header so it lists the rules: a numbered and titled section per problem, at least one prompt in the student's own words, and for each follow-up the prompt plus one sentence on what the first response was missing.
- Logged this prompt as Problem 1's follow-up. Every later prompt will be added to its problem's section in the same turn.

## Problem 2 — Study the Campus Customs Database

### Original prompt

> Problem 2: Study the Campus Customs Database
>
> Please explore `data/campus_customs.db` and review all its tables and fields. Create a working copy named `data/campus_customs_new.db` for changes in later problems, keeping the original intact.
>
> Examine the three open tickets and explain how their records connect to information in the other tables.
>
> Create `output/harness.md` to document the database. For each table, list its fields and briefly explain why the table is useful to the agents. We'll continue adding to this file as we work through the remaining problems.

### Work completed

- Reviewed all nine tables, field by field: `desk`, `tickets`, `inventory`, `pricing`, `vendors`, `leases`, `cash_accounts`, `payments` (empty), and `invoices`.
- Confirmed the working copy `data/campus_customs_new.db` (made in Problem 1) is byte-for-byte identical to the original and passes SQLite's integrity check. The original stays read-only.
- Traced the three open tickets:
  - **101, tee size S:** out of stock. Blocked by overdue invoice 501 ($840, Bulldog Print Co).
  - **102, rent:** $2,400 due 2026-09-02.
  - **103, 20 hoodies size M:** 12 short, and the restock depends on the same blocked vendor.
- Found the key tension: rent + invoice + hoodie restock = $3,504, but cash is $3,400. The agents can't do all three.
- Created `output/harness.md` with section 1 (each table, its fields, and why it matters to the agents, plus a table-connection map) and section 2 (how each ticket connects to the other tables, and the cash trade-off).

## Problem 3 — Build the MCP Server

### Original prompt

> Problem 3: Build the MCP server
> Please build an MCP server using FastMCP in the `mcp_server/` folder, configured to use `data/campus_customs_new.db`. For this problem, write the code without connecting or running the server.
> All agents in this assignment will use this server's tools. Start with three clearly named tools that will help address the tickets in the database. Base their behavior and results entirely on information in the database, without inventing data. We'll add more tools later.
> Update `output/harness.md` to document each tool, including:
>
> * The database table or tables it reads.
> * The ticket it supports: 101, 102, or 103.
> * One sentence explaining how the tool helps resolve that specific ticket. Make the connection concrete rather than simply describing the data it reads.
>
> Also create a brief `mcp_server/README.md` explaining the server's purpose, the database file it uses, and its three tools.

### Work completed

- Created `mcp_server/server.py`, a FastMCP server with three read-only tools. It points at `data/campus_customs_new.db`, which `DB_PATH` can override, and takes "today" from `desk.date_today`:
  - `check_stock_shortfall(sku, size, qty_needed)`: reads `inventory` and `pricing`. Supports ticket 103.
  - `check_invoice_and_vendor_hold(invoice_id)`: reads `invoices`, `vendors` and `desk`. Supports ticket 101.
  - `check_rent_due(lease_id)`: reads `leases`, `desk` and `cash_accounts`. Supports ticket 102.
- Checked the file's syntax only. As the prompt asked, the server was not run or connected.
- Added `requirements.txt` (`fastmcp`) and `mcp_server/README.md` (purpose, database file, and the three tools).
- Added section 3 to `output/harness.md`: each tool's tables, its ticket, and one concrete sentence on how it helps resolve that ticket.

## Problem 4 — Add the MCP Server to the Vibe Coder and Test Each Tool

### Original prompt

> Problem 4: Add the MCP server to vibe coder and test each tool
> Please connect the MCP server to this project so my vibe coder can access and call its tools. Save the connection settings in `.mcp.json` at the project root, or use the equivalent local configuration supported by my vibe coder.
> Once connected, call and test all three MCP tools through the vibe coder. Save evidence of these tests in `output/mcp_smoke.json`. For each tool, record:
>
> * The prompt used to request the tool call.
> * The tool's name.
> * The actual output returned by the tool.
>
> Verify that the returned values match the information stored in `data/campus_customs_new.db`.

### Work completed (in progress)

- Created `.venv` (kept out of iCloud) and installed FastMCP 4.1.6. Pinned `fastmcp>=4.1,<5` in `requirements.txt`.
- Wrote `.mcp.json` at the Homework 5 root. It registers the `campus-customs` stdio server (`.venv/bin/python mcp_server/server.py`) with `DB_PATH=data/campus_customs_new.db`.
- Claude Code detects the server (`claude mcp list` shows `campus-customs`) but marks it "pending approval". This session started in the parent course folder, so the tools can't load here. A new Claude Code session in the Homework 5 folder is needed to approve the server and call the tools.
- Pre-check: called all three tools over MCP using the `.mcp.json` settings. All returned values match the database: invoice 501 is $840, 3 days overdue, vendor on hold; rent is $2,400, due in 2 days, $1,000 left after paying; hoodies M have 8 on hand, 12 short, $264 to restock.

### Follow-up prompt: Finish Problem 4

> now you may complete problem 4 - do what you need to to get it done.

**What was missing from the first response:** the tools had only been tested by a script, not called by the vibe coder itself, so `output/mcp_smoke.json` didn't exist yet.

### Work completed (smoke test)

- Tried headless Claude Code (`claude -p --mcp-config .mcp.json`). It connected to `campus-customs`, but the standalone CLI isn't signed in on this Mac; only the desktop app is.
- Started a new Claude Code session in the `Homework 5` folder, where `.mcp.json` loads at startup. That session called `check_stock_shortfall` (CC-TEE-WHITE, S, 1), `check_invoice_and_vendor_hold` (501) and `check_rent_due` (lease 1) as native MCP tool calls, each in response to its own prompt.
- It wrote `output/mcp_smoke.json` with each prompt, tool name, arguments and the verbatim tool output. It then checked 33 values against `data/campus_customs_new.db` with read-only SQL and arithmetic: **all match**.
- The database was tested as it stands after Problem 9 (tee size S 0 on hand, invoice 501 paid, lease next due 2026-10-02, checking $160) and was not modified.

## Problem 5 — Build the Agent Team and Grow the MCP Tools

### Original prompt

> Problem 5: Build the agent team and grow the MCP tools
> Please use PydanticAI to create five Campus Customs agents: Boss, Inventory, Accounting, Facilities, and Customer Service. Set up their prompts, models, and execution loops so every agent can delegate work to any other agent.
> Organize the code as follows:
>
> * Store each agent's prompt in its own file under `backend/prompts/`.
> * Define the data types in `backend/models.py`.
> * Place the agent code under `backend/`, keeping the five roles clearly identifiable.
> * Use `PORTKEY_API_KEY` and only `gpt-6-luna` for all agents.
>
> Write detailed, original prompts explaining each agent's responsibilities, scope, and relevant shop rules.
> Expand the MCP server with any additional tools needed to handle the open tickets. Agents must obtain shop information through MCP tools backed by `data/campus_customs_new.db`. Do not create a separate tool layer that bypasses MCP or invent shop information.
> Configure the agents to append records to `output/audit_trail.json` during execution. Capture enough information at every agent-loop step to review what happened afterward, and preserve existing entries between runs.
> Update `output/harness.md` to list all agents and MCP tools, including newly added tools and the database tables each tool uses. Add a brief safety section describing safeguards for interactions involving customers and money, along with limits on token consumption.
> Finally, update `mcp_server/README.md` so its tool list reflects the expanded server.

### Work completed

- **MCP server:** grew from 3 tools to 13:
  - read tools: `list_open_tickets`, `get_ticket`, `list_vendors`, `get_cash_position`, `check_discount_margin`;
  - write tools: `request_payment_approval`, `request_purchase_order_approval`, `post_to_board`, `update_ticket_status`;
  - a human-only `record_human_decision`, the one tool that moves money.
  The server adds `approval_requests` and `board_posts` tables to the working copy.
- **Agents:** five PydanticAI agents, one role file each in `backend/agents/`, wired together in `backend/agents/team.py`:
  - every agent has an `ask_teammate` tool, so any agent can delegate to any other (no loops, depth and count capped);
  - each role sees only its own MCP tools, and no agent can see `record_human_decision`.
- **Prompts:** five detailed prompts in `backend/prompts/`, one per agent.
- **Data types and settings:** data types in `backend/models.py`. The model and limits live in `backend/config.py`, which refuses any `OPENAI_MODEL` other than `gpt-6-luna`.
- **Audit trail:** `backend/audit.py` appends every agent-loop step to `output/audit_trail.json` and keeps earlier runs.
- **Command-line tools:**
  - `python -m backend.run_ticket` works tickets;
  - `python -m backend.approve` is the human approval desk;
  - `python -m backend.reset_db` restores the working copy from the original.
- **Testing:** no AI model was called.
  - All 13 tools were tested on a scratch database. Every payment safeguard held: agent approvers rejected, vendor hold enforced, overdraft refused at −$104, duplicates refused, early `resolved` refused.
  - The full agent loop was tested with a scripted stand-in model. Boss → Inventory → Accounting delegation worked, loop-backs were refused, and the audit trail kept both test runs.
- **Incident during testing:** one early tool test accidentally wrote to `campus_customs_new.db`, because FastMCP's stdio launcher didn't pass the test's `DB_PATH`. The working copy was restored from the original and confirmed byte-identical. The backend now always passes `DB_PATH` explicitly.
- **Docs:** added sections 4 (agents and audit trail), 5 (all 13 MCP tools with their tables) and 6 (safety: money, customers, token limits) to `output/harness.md`. Rewrote `mcp_server/README.md` for the expanded tool list. Updated `requirements.txt` and `.env.example`.

### Follow-up prompt: Run it live

> Yes, run it live

**What was missing from the first response:** the team had only been tested offline with a stand-in model, never run with gpt-6-luna on the real tickets.

### Follow-up prompt: Reuse the Portkey key

> Yes, reuse it

**What was missing from the first response:** the live run couldn't start because Homework 5 had no `.env` with a Portkey key.

### Work completed (live run)

- Created `Homework 5/.env` (git-ignored, owner-only permissions). It copies only the `PORTKEY_API_KEY` line from `hw4/.env`, with `OPENAI_MODEL=gpt-6-luna` and the working database path. The key was never displayed.
- Ran `python -m backend.run_ticket --all --reset`. The database was reset, then all three tickets ran with gpt-6-luna and no errors. Each ended `awaiting_approval`:
  - **101** (Boss → Inventory, Accounting, Customer Service; 72,647 tokens): asks the owner to approve invoice 501 ($840) first, then a 1-unit tee restock ($8). Drafted a reply to Tauhid offering sizes M, L or XL in the meantime.
  - **102** (Boss → Facilities, Accounting; 49,984 tokens): rent request $2,400, due 2026-09-02. Drafted a reply to Elm City Properties.
  - **103** (Boss → Inventory, Accounting, Customer Service; 107,432 tokens): recommends 10% off ($52.20 each, $604 profit, 57.9% margin). Put the 12-hoodie restock ($264) on hold, because all pending requests ($3,512) would overdraw the $3,400 by $112. Drafted a partial-fill reply to the Yale AI Club.
- Verified: no payments made, cash still $3,400, invoice 501 still open, 4 requests pending, 12 board posts, nothing sent. The audit trail has 205 entries across the three runs.
- Issues spotted for follow-up:
  - Portkey reports the served model as `gpt-6-luna-global` in some audit entries.
  - Ticket 101's $8 restock may duplicate the rush reprint invoice 501 already covers.
  - The Yale AI Club draft says "your request for 10% off," but the club never named a percentage.

### Follow-up prompt: Fix the prompts

> Yes, fix the prompts

**What was missing from the first response:** the live run showed the agents ordering a tee that invoice 501 already covers, and a customer draft quoting a "10% off" request the club never made.

### Work completed (prompt fixes)

- `inventory.md`, `accounting.md`, `boss.md`: before ordering, read each open invoice's description. If it already covers the same SKU and size, pay that invoice instead of placing a duplicate purchase order.
- `customer_service.md`: restate only what the ticket says, never attribute the team's proposed discount to the requester, and reread the draft against the ticket notes.
- `backend/agents/team.py`: audit entries now record `requested_model` (`gpt-6-luna`) beside Portkey's `served_model_label`.
- Not re-run live yet, so these fixes haven't been checked against the model.

### Follow-up prompt: Re-run to check the fixes

> Yes, re-run

**What was missing from the first response:** the prompt fixes hadn't been checked against the live model.

### Work completed (second live run)

- Reset the database and re-ran all three tickets on gpt-6-luna: 185,270 tokens, compared with 230,063 in the first run. No errors, no money moved. The audit trail kept all 6 runs.
- Confirmed fixed:
  - no duplicate tee order (only invoice 501 and rent were requested);
  - the club draft says "your request for a bulk discount";
  - audit entries show `requested_model: gpt-6-luna`.
- New issue found: the Boss wrote a second customer draft for ticket 103. It presents 10% off as firm and adds "before any applicable taxes," which conflicts with Customer Service's draft. Not fixed yet.

### Follow-up prompt: Enforce draft ownership

> Yes, enforce it

**What was missing from the first response:** the prompt fixes alone didn't stop the Boss from writing its own customer draft that presented an unapproved 10% discount as firm.

### Work completed (draft ownership)

- `backend/agents/team.py`: `stamp_agent_identity` overwrites `author`, `updated_by` and `requested_by` on every write tool with the agent actually calling, so no agent can sign as a teammate.
- `mcp_server/server.py`: `post_to_board` now allows only Customer Service to post customer drafts, Facilities landlord drafts, Inventory or Accounting vendor drafts, and the Boss resolutions. Any agent may post internal notes.
- `boss.md`: ask the owner to revise drafts; treat unapproved discounts as "under review." `customer_service.md`: label revisions "Revised draft (replaces draft #N)."
- Tested offline: the Boss's spoofed customer draft was refused, and Customer Service's mislabeled post was saved under its real name. Not yet re-run live.
- Updated `output/harness.md` and `mcp_server/README.md`.

### Follow-up prompt: Skip the third live run for now

> Not now

**What was missing from the first response:** nothing; this postponed the live check of draft ownership. The rule has been tested offline only.

## Problem 6 — Plan the Three Tickets

### Original prompt

> Problem 6: Plan the three tickets
> Before connecting the backend, please create `output/desk_tickets.html` as a page I can open by double-clicking. Include separate tabs for tickets 101, 102, and 103, plus Cash and Reflection tabs with blank content or a brief "coming later" message.
> For each ticket, complete an Expected section describing the team's anticipated approach in original wording. Include:
>
> * Which agent the Boss should contact first and the reason for that choice.
> * Every delegation expected during the process, identifying which agent assigns work to which other agent.
> * The MCP tools likely to be used.
>
> Tailor each plan to the ticket's needs and involve only the relevant specialists. Make the delegation steps specific enough to compare with the agents' behavior later.
> Leave space for an Actual section on each ticket tab, but keep it empty until the agents have run.

### Work completed

- Created `output/desk_tickets.html`, a single self-contained file that opens by double-click (no internet or server needed), in the black-and-pink style. It has five tabs: 101, 102, 103, Cash, Reflection. The tabs work by click, keyboard arrows and links like `#103`.
- Each ticket's **Expected** section names who the Boss contacts first and why, lists numbered delegation steps (who → who, the task handed off, the tools expected, the expected result), lists the likely MCP tools by agent, says who is in or out, and gives a checklist to compare against the actual run:
  - **101:** Boss → Inventory first (stock decides everything; invoice 501 is a reprint of this exact tee) → Accounting (one $840 request, no new order) → Customer Service (draft to Tauhid). Facilities is out.
  - **102:** Boss → Facilities first (check the email against lease 1) → Facilities → Accounting (one $2,400 rent request, a nested hand-off); Facilities drafts the landlord reply. Inventory and Customer Service are out.
  - **103:** Boss → Inventory first (only 8 of 20 can be filled) → Accounting (10/15/20% margins; the $264 restock would overdraw by $104 after rent and invoice 501) → Customer Service (one draft, discount "under review"). Facilities is out.
- Each ticket has an empty **Actual** box marked "Not yet recorded." Cash and Reflection show "coming later."
- Checked in the browser: tabs switch correctly, no sideways scrolling at phone width (delegation tables stack into cards) or at desktop width.

## Problem 7 — Backend Routes

### Original prompt

> Problem 7: Backend routes
> Please build the FastAPI backend in `backend/main.py` so the React dashboard can call routes that:
>
> * List tickets 101, 102, and 103 with their current open or resolved status.
> * Accept a ticket ID and start the agent team working on that ticket.
> * Return recent agent messages and tool calls so the dashboard can refresh its activity display.
> * Process a payment or purchase only after a human clicks Approve. Agents should prepare the proposed transaction; this approval route performs the actual cash change.
> * Retrieve the current checking account balance from `cash_accounts`.
> * Restore the working database to its original values for a fresh run.
>
> Start the server from the `backend/` directory using:
>
> ```
> uvicorn main:app --reload --port 8000
> ```
>
> Make the backend available at `http://localhost:8000`.
> Update `output/harness.md` with one line per route showing its URL and explaining what it does.

### Work completed

- Built `backend/main.py` (FastAPI) with 12 routes: tickets list and detail, start a run, run status, activity feed, approvals list, approve, reject, cash, reset, and health. `/` redirects to `/docs`. It holds one long-lived MCP connection, so all shop data still goes through MCP. It adds the project root to the import path, so `uvicorn main:app` works from inside `backend/`.
- Added `backend/activity.py`, which turns the audit trail into readable feed items. Each item carries an index, so the dashboard can poll for only what's new.
- Added two MCP tools for the dashboard: `list_tickets` (all tickets with status) and `list_approval_requests` (the approval queue with the balance after each request).
- `run_ticket` now accepts a `run_id`, so a route can return it before the run finishes. Runs happen one at a time.
- Installed FastAPI 0.162 and uvicorn 0.54, added them to `requirements.txt`, and added an `hw5-backend` launch configuration. The server is running at `http://localhost:8000`.
- Tested every route without calling the AI model:
  - Read routes work, and unknown tickets return 404.
  - Approving as "boss" was refused (400), a missing name was refused (422), a human approval paid $840 and marked invoice 501 paid, and approving again was refused.
  - Reset restored all nine original tables value for value.
  - The run route was tested in-process with a scripted model on a scratch database: 202 to start, 409 while busy (for both a second run and a reset), and the activity feed showed every step.
- Note: that test approval wrote a `human_decision` entry from "Route test (Emily)" to `output/audit_trail.json`, before the reset.
- Added section 9 to `output/harness.md`: one line per route with its URL and what it does.

## Problem 8 — Agent Dashboard

### Original prompt

> Problem 8: Agent dashboard
> Please create a dashboard in `frontend/` using React, Vite, and TypeScript. Connect it to the backend routes from Problem 7 so users can:
>
> * View all three tickets and select one to start the agent team.
> * Follow each agent's messages and actions while the ticket is being handled.
> * See the ticket marked as resolved when the run finishes.
> * Read a brief summary of each agent's contribution to that ticket.
> * Approve a proposed payment or purchase when human authorization is required.
> * View the current checking balance and see it decrease after an approved payment.
>
> Give the dashboard a polished, creative layout that feels inviting and practical to use. Make the agents visually distinguishable and keep ticket progress, approval requests, and cash information easy to follow.
> Configure the frontend to call `http://localhost:8000`. Set up the backend to allow requests from the Vite frontend's origin, usually `http://localhost:5173`.
> Start the frontend from `frontend/` using:
>
> ```
> npm run dev
> ```
>
> Create `output/design.md` explaining the design choices and their purpose. Cover the layout, how users distinguish agents, how resolved tickets and cash appear, and the creative details that make the dashboard enjoyable to use.

### Work completed

- **Built `frontend/`** (React 19 + Vite 6 + TypeScript), the "Campus Customs Ops Floor":
  - **Left:** a ticket board with a status pill and a Resolved stamp on each card.
  - **Center:**
    - a ticket header with a Start button and a four-step progress tracker;
    - an agent roster that lights up whichever agent is working;
    - a live feed of messages, tool calls, results and hand-offs, refreshed every 1.5 seconds while agents work;
    - "Who did what" cards with the Boss's final call;
    - drafts shown as paper cards stamped NOT SENT.
  - **Right:**
    - the checking balance, which counts down, with a −$ chip and a meter;
    - the approval queue, where Approve needs a second Confirm click and a name in "Approving as."
  - Each agent has its own color, icon and role line. Black-and-pink style, with layouts for desktop, tablet and phone.
- **Configured the connection:** `frontend/.env.development` sets `VITE_API_BASE=http://localhost:8000`, and Vite is fixed to port 5173. The backend's CORS now explicitly allows `http://localhost:5173`.
- **Backend additions so a ticket can visibly reach "resolved":**
  - The approve and reject routes mark a ticket resolved once its last pending request is decided.
  - The Boss's prompt now treats discounts as its own call (only payments need a human), and the Boss resolves tickets that aren't waiting on money instead of leaving them in progress.
  - New route `GET /api/tickets/{id}/contributions` gives the per-agent summaries.
  - Runs from before the latest reset are hidden from the dashboard.
- **npm setup:** npm's shared cache (`~/.npm`) has files owned by another account, so `npm install` used a private cache instead. `node_modules` is kept out of iCloud.
- **Verified in the browser:**
  - **Live run of ticket 102** (46,069 tokens): the feed showed Boss → Facilities → Accounting, matching the Problem 6 plan. Inventory and Customer Service stayed idle, and the ticket ended at "Needs your OK."
  - **Approving and confirming the $2,400 rent:** checking counted down from $3,400 to $1,000, the payment appeared in "Paid out," and ticket #102 flipped to Resolved with a toast.
  - **Bug fixed:** a duplicated feed divider caused by overlapping refreshes.
  - **Layout:** no sideways scrolling at 375px or 1440px, and no console errors.
- **Wrote `output/design.md`:** layout, agent identity, resolved tickets, cash, approvals, creative details. Added the contributions route and the auto-resolve rule to `output/harness.md`.

## Problem 9 — Resolve the Tickets

### Original prompt

> Problem 9: Resolve the tickets
> Please reset `data/campus_customs_new.db` to its original state and record the starting checking balance. Then use the React dashboard to run tickets 101, 102, and 103 until all three are resolved, completing any required human approvals.
> Update `output/desk_tickets.html` with evidence from this run. In each ticket's Actual section, describe which agents participated, how they delegated work, and which MCP tools they called. Preserve the Expected sections for comparison.
> Complete the Cash tab with:
>
> * The checking balance immediately after the reset.
> * Each ticket's effect on cash, identifying the payment or purchase, dollar amount, and reason.
> * The final checking balance, verified against `cash_accounts` in the working database.
>
> Check that all cash changes reconcile correctly.
> Also create:
>
> * `output/resolved_tickets.json`: For each ticket, include its ID, final status, brief outcome, each agent's contribution, and any human approvals.
> * `output/resolved_board.html`: A page that opens by double-clicking and contains a screenshot of the React dashboard for each resolved ticket.
>
> Append the genuine execution records to `output/audit_trail.json`, preserving earlier entries. Finish `output/harness.md` so it documents the database tables, MCP tools, five agents, API routes, dashboard, and safety rules.

### Work completed

- **Prep:**
  - Links like `#ticket=102` now open a ticket in the dashboard, so screenshots show the right one.
  - On first load, the cash panel shows the real balance at once instead of counting up from $0.
  - "On the board" shows only outgoing drafts, not internal resolution notes.
- **Reset** from the dashboard's Reset shop button at 2026-11-07 03:11:10 UTC. Starting checking balance: **$3,400.00**, from both `GET /api/cash` and `cash_accounts`. All nine original tables matched the original value for value.
- **Ran each ticket from the dashboard** and approved payments in the dashboard (Approve → Confirm) as "Emily Strackhouse (via Claude)":
  - **101** (run 023d80dbbf19, 67,813 tokens):
    - Boss → Inventory, Boss → Accounting twice, Boss → Customer Service.
    - One $840 request for invoice 501, with no duplicate tee order.
    - Approved → checking $2,560, invoice 501 paid, ticket resolved.
  - **102** (run a204604c2f6a, 44,133 tokens):
    - Boss → Facilities → Accounting, exactly as planned.
    - Approved $2,400 rent → checking $160, lease due date moved to 2026-10-02, ticket resolved.
  - **103** (run f8876bb0ee7a, 55,772 tokens):
    - Boss → Inventory, Boss → Accounting (tested 10/15/20% off), Boss → Customer Service.
    - The Boss approved 15% off ($49.30 each) for the 8 in stock. No restock, since $264 would overdraw $160 by $104.
    - The Boss resolved it directly; no payment needed.
- **Cash reconciles:** $3,400 − $840 − $2,400 = $160 = `cash_accounts`. 2 payments, 2 approved requests, 0 pending or refused.
- **Updated `output/desk_tickets.html`:**
  - Each ticket's Actual section has the run details, a step table (who → who, task in the agent's words, MCP tools called, result) and an Expected-vs-Actual checklist. Expected sections are unchanged.
  - Deviations recorded:
    - 101: Accounting was asked twice, and the draft hints at the reprint approval.
    - 102: the Boss checked the rent itself.
    - 103: the discount was firm and the ticket resolved directly, after the Problem 8 rule change; the vendor hold had already cleared.
  - The Cash tab is complete, with a reconciliation.
- **Created `output/resolved_tickets.json`:** generated from the audit trail and database. It has ID, final status, outcome, hand-offs, each agent's contribution and tools, human approvals, drafts, and the cash reconciliation.
- **Created `output/resolved_board.html`:** one self-contained file (2.6 MB) with full-size headless-Chrome screenshots of the dashboard, each taken right after that ticket resolved. Copies are in `output/screenshots/`.
- **Audit trail:** 162 new entries appended after the 429 earlier ones (591 total, 10 runs). The final runs requested only `gpt-6-luna`.
- **Rewrote `output/harness.md` as the finished reference:** system map and how to run it, all 11 tables, all 15 MCP tools with their tables and callers, the five agents, the audit trail, every API route, the dashboard, safety rules (money, outside messages, identity, tokens), tuning history, and final results.
- **Small fixes:** added the two dashboard tools to `mcp_server/README.md`, and the audit trail file is now readable by others, not owner-only.

## Problem 10 — Reflection

### Original prompt

> Problem 10: Reflection
> Please complete the Reflection tab in `output/desk_tickets.html` with a detailed discussion written in my own voice. Address these points:
>
> * Evaluate the agents' performance on each of the three tickets and explain your assessment using specific examples.
> * Compare each ticket's actual execution with its original Expected plan, explaining any differences.
> * Identify which parts of the work would have been simpler with a single agent using tools, and explain why.
> * Propose three additional Campus Customs problems that the existing team could handle with its current tools.
> * Propose three additional problems that the current setup could not handle. For each, explain which additional tools and agent roles would be needed.
>
> Ground every answer in this application and the actual runs of tickets 101, 102, and 103. Use the ticket tabs and Cash tab as supporting evidence, including relevant actions, delegations, outcomes, and cash changes. Keep the reflection specific to Campus Customs and base claims about performance on the recorded results.

### Work completed

- Pulled exact figures from the Problem 9 audit trail:
  - tokens per agent (the Boss used 45%, 59% and 53% of each run);
  - repeated lookups (invoice 501 checked 4× in 101, rent 3× in 102, hoodie stock 3× in 103);
  - MCP call counts.
- Wrote the Reflection tab in first person, grounded in the recorded runs:
  1. **Performance per ticket:**
     - 101: strong outcome, average execution (Accounting asked twice, the draft over-explains).
     - 102: cleanest, but heavy overhead for a one-lookup task.
     - 103: best judgment (15% off, no unaffordable restock).
     - Each ticket ties back to its cash change and to the earlier test-run failures that the prompt fixes solved.
  2. **Expected vs. Actual table:** every first contact and every "who stays out" prediction held, and cash ended at the predicted $160. Differences were extra hand-offs and repeated lookups, plus 103's ending, which changed because of the Problem 8 rule change and because ticket 101 cleared the vendor hold.
  3. **Single agent vs. team:** 102 could be about 5 MCP calls instead of 13; fact re-gathering and draft rebuilding happen at every hand-off. The team helped on judgment calls, but money safety comes from the MCP server, not the number of agents.
  4. **Three problems the current team can handle:** Crest Mug restock ($21 PO via Elm City Gifts), a 30-cap bulk discount, and the October rent warning ($2,400 due against $160).
  5. **Three problems it can't handle, with tools and roles:**
     - completing sales and receiving stock (`record_sale`, `receive_shipment`, `record_payment_received`; a Sales and Fulfillment agent);
     - two-way vendor and customer messages (`send_message` behind approval, `read_inbox`, `create_ticket`; a Vendor Relations agent);
     - cash-shortfall planning (`forecast_cash`, `schedule_payment`, `propose_payment_plan`; a Treasury agent).
- Fixed phone layout: the page's table cards had used the delegation-table labels on every table. Each cell now shows its own table's column name. Checked at 375px (no sideways scrolling) and on desktop.
