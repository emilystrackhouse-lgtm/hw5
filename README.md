# Campus Customs Multi-Agent Operations (Homework 5)

Five AI agents (**Boss, Inventory, Accounting, Facilities, Customer Service**) run the back office of Campus Customs, a Yale apparel shop. They work the open tickets on the shop's board and prepare payments; a human approves every payment from a React dashboard.

```
React dashboard (frontend/, :5173) ─HTTP─▶ FastAPI backend (backend/main.py, :8000)
                                              │ runs the agent team (PydanticAI, gpt-6-luna via Portkey)
                                              ▼
                                    MCP server (mcp_server/server.py, FastMCP)
                                              ▼
                                    data/campus_customs_new.db  (working copy)
```

- **Every agent reads and writes the shop only through MCP tools.** Nothing bypasses the MCP server.
- **Only gpt-6-luna is used**, through Portkey. `backend/config.py` refuses any other model.
- **Money moves only when a human clicks Approve** in the dashboard. The pay step refuses anything that would make the balance negative.
- **Every agent step is appended to `output/audit_trail.json`.**

Full documentation: [`output/harness.md`](output/harness.md). Dashboard design: [`output/design.md`](output/design.md).

---

## 1. Requirements

- Python 3.11+ (built and tested on 3.13)
- Node.js 20+ and npm (built and tested on Node 24)
- A Portkey API key with access to `gpt-6-luna`

## 2. One-time setup

From the project root (`hw5/`):

```bash
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

cp .env.example .env               # then edit .env and paste your PORTKEY_API_KEY
```

`.env` holds your real key and is ignored by git. Only `.env.example` (placeholders) is committed. Keep `OPENAI_MODEL=gpt-6-luna`.

```bash
cd frontend
npm install
cd ..
```

> On an iCloud-, Dropbox- or OneDrive-synced folder, pause syncing (or exclude `.venv` and `node_modules`) while installing.

## 3. The databases, and resetting before a full run

| File | Purpose |
|---|---|
| `data/campus_customs.db` | The **original** shop data. Never modified. |
| `data/campus_customs_new.db` | The **working copy** the MCP server, agents and backend read and write. |

The working copy is committed in its **final state from the submitted run**: all three tickets resolved, $840 and $2,400 paid, checking at $160. **Reset it to the original before a complete run of tickets 101, 102 and 103.** Otherwise the tickets are already resolved and the cash is already spent.

Pick any one of these:

```bash
# A. Python (from the project root, with .venv active)
python -m backend.reset_db

# B. Plain copy (from the project root)
cp data/campus_customs.db data/campus_customs_new.db

# C. The dashboard: click "Reset shop" in the top bar (or POST http://localhost:8000/api/reset)
```

Each copies the original over the working copy. Afterwards, checking is back to **$3,400.00**, all three tickets are `open`, and invoice 501 is unpaid. The audit trail is kept; it's append-only. Pass `--clear-audit` to option A if you want an empty trail.

## 4. Start the MCP server

The backend starts its own copy of the MCP server automatically, so this step is only needed to use the tools directly.

```bash
# From the project root, with .venv active
python mcp_server/server.py
```

It speaks MCP over stdio and uses `data/campus_customs_new.db`. To use it from Claude Code (the vibe coder), open a session in the project root: `.mcp.json` registers it as `campus-customs`, so approve that server when asked. See [`mcp_server/README.md`](mcp_server/README.md) for the 15 tools.

## 5. Launch the FastAPI backend

```bash
# With .venv active
cd backend
uvicorn main:app --reload --port 8000
```

The backend runs at **http://localhost:8000**, and http://localhost:8000/docs lists every route. It allows requests from the dashboard at `http://localhost:5173`.

## 6. Start the React dashboard

In a second terminal:

```bash
cd frontend
npm run dev
```

Open **http://localhost:5173**. The dashboard calls the backend at `http://localhost:8000`, set in `frontend/.env.development`.

## 7. Resolve all three tickets

1. **Reset** the database (section 3). Checking should read $3,400.00.
2. Type your name in **Approving as** (top right).
3. Select **#101** and click **Start the agent team**. Watch the live feed. When it reaches *Needs your OK*, click **Approve**, then **Confirm**, on the $840 invoice. The ticket turns **Resolved** and checking drops to $2,560.
4. Do the same for **#102**: approve the $2,400 rent. Checking drops to $160.
5. Run **#103**. The Boss sets a discount and resolves it; no payment is needed, since a restock would overdraw the account.

Only one ticket runs at a time, because they share the cash. Each run takes about a minute and uses roughly 45–70k tokens; one ticket run is capped at 150k tokens.

You can also run tickets from the command line instead of the dashboard:

```bash
python -m backend.run_ticket --all --reset        # reset, then work every open ticket
python -m backend.approve list                    # see pending requests and cash
python -m backend.approve 1 approve --by "Your Name"
```

## 8. Project layout

```
hw5/
├── AI_prompts.md            log of every prompt used, by problem
├── README.md                this file
├── requirements.txt         Python dependencies (fastmcp, pydantic-ai-slim[openai,mcp], fastapi, uvicorn, python-dotenv)
├── .env.example             variable names with placeholder values (copy to .env)
├── .gitignore               keeps .env, .venv, node_modules out of git
├── .mcp.json                registers the MCP server for Claude Code
├── data/                    campus_customs.db (original), campus_customs_new.db (working copy)
├── mcp_server/              server.py (FastMCP, 15 tools), README.md
├── backend/
│   ├── main.py              FastAPI routes for the dashboard
│   ├── models.py            data types (run state, agent reports, audit entries)
│   ├── config.py            model (gpt-6-luna only), paths, token limits
│   ├── agents/              boss.py, inventory.py, accounting.py, facilities.py, customer_service.py, team.py
│   ├── prompts/             boss.md, inventory.md, accounting.md, facilities.md, customer_service.md
│   ├── audit.py, activity.py, reset_db.py, run_ticket.py, approve.py
├── frontend/                React + Vite + TypeScript dashboard (src/, vite.config.ts, package.json)
└── output/
    ├── harness.md           full documentation: tables, tools, agents, routes, dashboard, safety
    ├── mcp_smoke.json       Problem 4: vibe-coder calls of three MCP tools, verified against the database
    ├── desk_tickets.html    expected vs. actual for each ticket, cash reconciliation, reflection
    ├── design.md            dashboard design choices
    ├── resolved_tickets.json  outcome, agent contributions and approvals for each ticket
    ├── resolved_board.html  dashboard screenshots of each resolved ticket (opens by double-click)
    ├── screenshots/         the same screenshots as PNG files
    ├── audit_trail.json     every agent step and human decision (append-only)
    └── github_url.txt       this repository's URL
```

## 9. Safety at a glance

- **Agents can only *request* payments.** The amounts come from the database, and only the human Approve route moves money.
- **The pay step refuses** anything that would overdraw checking, or any order to a vendor with an unpaid invoice.
- **Nothing is ever sent.** Customer, landlord and vendor messages are drafts on the board, and each kind has one agent allowed to write it.
- **Token and loop limits** cap every ticket run, and no secrets are committed.
