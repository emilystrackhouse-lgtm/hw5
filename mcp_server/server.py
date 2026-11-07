"""Campus Customs MCP server.

The single doorway between the agent team (Boss, Inventory, Accounting,
Facilities, Customer Service) and the shop database. Every answer comes from
the database; nothing is invented.

Database: data/campus_customs_new.db (the working copy). Override with DB_PATH.

Money rules enforced here, not just in the prompts:
- Agents can only *request* a payment. The amount is always taken from the
  database (invoice amount, monthly rent, unit cost x qty), never typed in.
- Money moves only through `record_human_decision`, which needs a named human
  approver. The backend hides that tool from every agent.
- A payment that would make a cash balance negative is refused.
- A purchase order to a vendor with an open unpaid invoice is refused.
"""

from __future__ import annotations

import calendar
import os
import sqlite3
from contextlib import closing
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Literal

from fastmcp import FastMCP

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = Path(os.getenv("DB_PATH", PROJECT_ROOT / "data" / "campus_customs_new.db"))
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_ROOT / DB_PATH

# Names the human decision tool will not accept as an approver.
AGENT_NAMES = {"boss", "inventory", "accounting", "facilities", "customer_service", "customer service"}

TICKET_STATUSES = ("open", "in_progress", "awaiting_approval", "resolved")

# Which agent may post each kind of board post. Outside messages each have one
# owner, so the board never holds two conflicting replies from different agents.
# Internal notes are open to every agent. Authors who are not agents (a human
# using the vibe coder or dashboard) are not limited.
POST_AUTHORS = {
    "customer_draft": {"customer_service"},
    "landlord_draft": {"facilities"},
    "vendor_draft": {"inventory", "accounting"},
    "resolution": {"boss"},
}

mcp = FastMCP("Campus Customs")


# ---------------------------------------------------------------- helpers ---

def _connect() -> sqlite3.Connection:
    """Open the working database, adding the two board tables if missing."""
    if not DB_PATH.exists():
        raise FileNotFoundError(
            f"Database not found at {DB_PATH}. Copy data/campus_customs.db to "
            "data/campus_customs_new.db first (python -m backend.reset_db)."
        )
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    _ensure_board_tables(conn)
    return conn


def _ensure_board_tables(conn: sqlite3.Connection) -> None:
    """Tables for work the agents produce. They start empty after a reset.

    approval_requests: payments and purchase orders waiting on a human.
    board_posts: drafts and notes that stay on the board (nothing is sent).
    """
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS approval_requests (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            kind TEXT NOT NULL,              -- invoice | rent | purchase_order
            ref_id INTEGER,                  -- invoices.id or leases.id (NULL for purchase orders)
            vendor_id INTEGER,
            sku TEXT, size TEXT, qty INTEGER,
            amount REAL NOT NULL,
            account TEXT NOT NULL,
            reason TEXT NOT NULL,
            requested_by TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',   -- pending | approved | rejected | refused
            decided_by TEXT, decided_at TEXT, decision_note TEXT,
            payment_id INTEGER,
            created_at TEXT NOT NULL
        );
        CREATE TABLE IF NOT EXISTS board_posts (
            id INTEGER PRIMARY KEY,
            ticket_id INTEGER NOT NULL,
            kind TEXT NOT NULL,              -- customer_draft | vendor_draft | landlord_draft | internal_note | resolution
            author TEXT NOT NULL,
            recipient TEXT,
            subject TEXT,
            body TEXT NOT NULL,
            created_at TEXT NOT NULL
        );
        """
    )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _shop_today(conn: sqlite3.Connection) -> date:
    """The shop's 'today' comes from desk.date_today, never the real clock."""
    row = conn.execute("SELECT date_today FROM desk LIMIT 1").fetchone()
    return date.fromisoformat(row["date_today"])


def _add_month(d: date) -> date:
    year, month = (d.year + 1, 1) if d.month == 12 else (d.year, d.month + 1)
    return date(year, month, min(d.day, calendar.monthrange(year, month)[1]))


def _ticket(conn: sqlite3.Connection, ticket_id: int) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM tickets WHERE id = ?", (ticket_id,)).fetchone()


def _open_invoices(conn: sqlite3.Connection, vendor_id: int) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, amount, due_date FROM invoices WHERE vendor_id = ? AND status = 'open'",
        (vendor_id,),
    ).fetchall()


def _live_request(conn: sqlite3.Connection, kind: str, ref_id: int) -> sqlite3.Row | None:
    """An existing pending or approved request for the same bill (stops double payment)."""
    return conn.execute(
        "SELECT id, status FROM approval_requests "
        "WHERE kind = ? AND ref_id = ? AND status IN ('pending', 'approved')",
        (kind, ref_id),
    ).fetchone()


def _account(conn: sqlite3.Connection, name: str) -> sqlite3.Row | None:
    return conn.execute("SELECT * FROM cash_accounts WHERE name = ?", (name,)).fetchone()


# ------------------------------------------------------- read-only tools ---

@mcp.tool
def list_open_tickets() -> dict:
    """List every ticket that is not resolved yet, with the shop's 'today'.

    Reads tickets and desk. The Boss starts here.
    """
    with closing(_connect()) as conn:
        today = _shop_today(conn)
        rows = conn.execute(
            "SELECT * FROM tickets WHERE status != 'resolved' ORDER BY id"
        ).fetchall()
    return {"shop_today": today.isoformat(), "open_tickets": [dict(r) for r in rows]}


@mcp.tool
def list_tickets() -> dict:
    """List every ticket (open or resolved) with its status and board activity.

    Reads tickets, approval_requests (how many wait on a human) and
    board_posts (drafts and notes). Used by the dashboard's ticket list.
    """
    with closing(_connect()) as conn:
        today = _shop_today(conn)
        rows = conn.execute(
            """SELECT t.*,
                      (SELECT COUNT(*) FROM approval_requests a
                        WHERE a.ticket_id = t.id AND a.status = 'pending') AS pending_approvals,
                      (SELECT COUNT(*) FROM board_posts b WHERE b.ticket_id = t.id) AS board_posts
               FROM tickets t ORDER BY t.id"""
        ).fetchall()
    return {
        "shop_today": today.isoformat(),
        "tickets": [dict(r) | {"is_resolved": r["status"] == "resolved"} for r in rows],
    }


@mcp.tool
def list_approval_requests(status: Literal["pending", "approved", "rejected", "refused", "all"] = "pending") -> dict:
    """List payment and purchase-order requests, newest first, with what each would pay for.

    Reads approval_requests, vendors (vendor name), cash_accounts (balance)
    and payments (the payment made, if approved). Used by the dashboard's
    approval queue.
    """
    with closing(_connect()) as conn:
        where = "" if status == "all" else "WHERE a.status = ?"
        params = () if status == "all" else (status,)
        rows = conn.execute(
            f"""SELECT a.*, v.name AS vendor_name
                FROM approval_requests a LEFT JOIN vendors v ON v.id = a.vendor_id
                {where} ORDER BY a.id DESC""",
            params,
        ).fetchall()
        balances = {r["name"]: r["balance"] for r in conn.execute("SELECT name, balance FROM cash_accounts")}
    out = []
    for r in rows:
        d = dict(r)
        bal = balances.get(r["account"])
        d["balance_now"] = bal
        d["balance_after_if_approved"] = None if bal is None else round(bal - r["amount"], 2)
        d["would_overdraw"] = bal is not None and bal - r["amount"] < 0
        out.append(d)
    return {"status_filter": status, "requests": out}


@mcp.tool
def get_ticket(ticket_id: int) -> dict:
    """Get one ticket with everything the team has done on it so far.

    Reads tickets, plus the board_posts (drafts and notes) and
    approval_requests (payments waiting on a human) linked to the ticket.
    """
    with closing(_connect()) as conn:
        t = _ticket(conn, ticket_id)
        if t is None:
            return {"found": False, "error": f"No ticket with id {ticket_id}."}
        posts = conn.execute(
            "SELECT * FROM board_posts WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
        reqs = conn.execute(
            "SELECT * FROM approval_requests WHERE ticket_id = ? ORDER BY id", (ticket_id,)
        ).fetchall()
        today = _shop_today(conn)
    return {
        "found": True,
        "shop_today": today.isoformat(),
        "ticket": dict(t),
        "board_posts": [dict(p) for p in posts],
        "approval_requests": [dict(r) for r in reqs],
    }


@mcp.tool
def check_stock_shortfall(sku: str, size: str, qty_needed: int) -> dict:
    """Check whether an order can be filled from stock, and price any shortfall.

    Reads inventory (units on hand for this size and the other sizes) and
    pricing (unit cost and list price). Returns the shortfall, what restocking
    it would cost at unit cost, and the order's value at list price.
    """
    with closing(_connect()) as conn:
        rows = conn.execute(
            "SELECT size, qty, name, location FROM inventory WHERE sku = ?",
            (sku,),
        ).fetchall()
        if not rows:
            return {"found": False, "error": f"No inventory rows for SKU {sku}."}

        match = next((r for r in rows if r["size"].upper() == size.upper()), None)
        if match is None:
            return {
                "found": False,
                "error": f"SKU {sku} has no size {size}.",
                "sizes_available": [r["size"] for r in rows],
            }

        price = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()

    on_hand = match["qty"]
    shortfall = max(qty_needed - on_hand, 0)
    result = {
        "found": True,
        "sku": sku,
        "name": match["name"],
        "size": match["size"],
        "location": match["location"],
        "qty_needed": qty_needed,
        "qty_on_hand": on_hand,
        "can_fill_from_stock": shortfall == 0,
        "shortfall": shortfall,
        "other_sizes_on_hand": {
            r["size"]: r["qty"] for r in rows if r["size"] != match["size"]
        },
    }
    if price is not None:
        result.update(
            unit_cost=price["unit_cost"],
            list_price=price["list_price"],
            margin_per_unit=round(price["list_price"] - price["unit_cost"], 2),
            order_value_at_list=round(qty_needed * price["list_price"], 2),
            restock_cost_for_shortfall=round(shortfall * price["unit_cost"], 2),
        )
    else:
        result["pricing_note"] = f"No pricing row for SKU {sku}."
    return result


@mcp.tool
def check_invoice_and_vendor_hold(invoice_id: int) -> dict:
    """Look up a vendor invoice and whether it is stopping that vendor from shipping.

    Reads invoices (amount, due date, status), vendors (name, lead time) and
    desk (the shop's 'today'). Shop rule: a vendor will not ship new product
    while it has any open unpaid invoice.
    """
    with closing(_connect()) as conn:
        today = _shop_today(conn)
        inv = conn.execute(
            """SELECT i.id, i.vendor_id, i.amount, i.due_date, i.status, i.description,
                      v.name AS vendor_name, v.specialty, v.lead_days
               FROM invoices i JOIN vendors v ON v.id = i.vendor_id
               WHERE i.id = ?""",
            (invoice_id,),
        ).fetchone()
        if inv is None:
            return {"found": False, "error": f"No invoice with id {invoice_id}."}
        open_invoices = _open_invoices(conn, inv["vendor_id"])

    days_past_due = (today - date.fromisoformat(inv["due_date"])).days
    return {
        "found": True,
        "shop_today": today.isoformat(),
        "invoice_id": inv["id"],
        "description": inv["description"],
        "amount": inv["amount"],
        "due_date": inv["due_date"],
        "status": inv["status"],
        "is_overdue": inv["status"] == "open" and days_past_due > 0,
        "days_past_due": max(days_past_due, 0),
        "vendor": {
            "id": inv["vendor_id"],
            "name": inv["vendor_name"],
            "specialty": inv["specialty"],
            "lead_days": inv["lead_days"],
        },
        "vendor_on_hold": len(open_invoices) > 0,
        "open_invoices_for_vendor": [dict(r) for r in open_invoices],
        "total_open_with_vendor": round(sum(r["amount"] for r in open_invoices), 2),
    }


@mcp.tool
def check_rent_due(lease_id: int) -> dict:
    """Look up the rent owed on a lease, when it is due, and whether cash covers it.

    Reads leases (rent and next due date), desk (the shop's 'today') and
    cash_accounts (current balances). This tool only reports; it pays nothing.
    """
    with closing(_connect()) as conn:
        today = _shop_today(conn)
        lease = conn.execute(
            "SELECT id, space_name, landlord, monthly_rent, next_due, notes "
            "FROM leases WHERE id = ?",
            (lease_id,),
        ).fetchone()
        if lease is None:
            return {"found": False, "error": f"No lease with id {lease_id}."}
        accounts = conn.execute(
            "SELECT name, balance, date FROM cash_accounts"
        ).fetchall()

    days_until_due = (date.fromisoformat(lease["next_due"]) - today).days
    rent = lease["monthly_rent"]
    return {
        "found": True,
        "shop_today": today.isoformat(),
        "lease_id": lease["id"],
        "space_name": lease["space_name"],
        "landlord": lease["landlord"],
        "monthly_rent": rent,
        "next_due": lease["next_due"],
        "days_until_due": days_until_due,
        "is_overdue": days_until_due < 0,
        "cash_accounts": [
            {
                "name": a["name"],
                "balance": a["balance"],
                "as_of": a["date"],
                "covers_rent": a["balance"] >= rent,
                "balance_after_rent": round(a["balance"] - rent, 2),
            }
            for a in accounts
        ],
    }


@mcp.tool
def list_vendors() -> dict:
    """List every vendor with its specialty, lead time and whether it is on hold.

    Reads vendors, invoices (open unpaid bills per vendor) and desk (to give
    the earliest delivery date if ordered today). A vendor with any open
    invoice is on hold and will not ship.
    """
    with closing(_connect()) as conn:
        today = _shop_today(conn)
        vendors = conn.execute("SELECT * FROM vendors ORDER BY id").fetchall()
        out = []
        for v in vendors:
            open_inv = _open_invoices(conn, v["id"])
            out.append({
                "id": v["id"],
                "name": v["name"],
                "specialty": v["specialty"],
                "lead_days": v["lead_days"],
                "on_hold": bool(open_inv),
                "open_invoices": [dict(r) for r in open_inv],
                "earliest_delivery_if_ordered_today": (
                    None if open_inv
                    else date.fromordinal(today.toordinal() + v["lead_days"]).isoformat()
                ),
            })
    return {"shop_today": today.isoformat(), "vendors": out}


@mcp.tool
def get_cash_position() -> dict:
    """Show cash on hand, money already promised to pending requests, and what is left.

    Reads cash_accounts, approval_requests (pending or approved, not yet
    paid) and payments (what has gone out). No money comes in: the balance
    only goes down.
    """
    with closing(_connect()) as conn:
        accounts = conn.execute("SELECT * FROM cash_accounts").fetchall()
        pending = conn.execute(
            "SELECT id, ticket_id, kind, ref_id, amount, account, status "
            "FROM approval_requests WHERE status = 'pending' ORDER BY id"
        ).fetchall()
        paid = conn.execute("SELECT * FROM payments ORDER BY id").fetchall()
    result = []
    for a in accounts:
        committed = sum(p["amount"] for p in pending if p["account"] == a["name"])
        result.append({
            "name": a["name"],
            "balance": a["balance"],
            "as_of": a["date"],
            "pending_requests_total": round(committed, 2),
            "balance_if_all_pending_approved": round(a["balance"] - committed, 2),
            "can_cover_all_pending": a["balance"] - committed >= 0,
        })
    return {
        "accounts": result,
        "pending_requests": [dict(p) for p in pending],
        "payments_made": [dict(p) for p in paid],
    }


@mcp.tool
def check_discount_margin(sku: str, qty: int, discount_pct: float) -> dict:
    """Price a discount request and show what the shop still earns.

    Reads pricing (unit cost and list price). Returns the discounted unit
    price, order total, profit, margin percent, and the largest discount that
    still breaks even. It only calculates; it does not grant anything.
    """
    if not 0 <= discount_pct < 100:
        return {"ok": False, "error": "discount_pct must be between 0 and 100."}
    with closing(_connect()) as conn:
        p = conn.execute(
            "SELECT unit_cost, list_price FROM pricing WHERE sku = ?", (sku,)
        ).fetchone()
    if p is None:
        return {"ok": False, "error": f"No pricing row for SKU {sku}."}
    cost, price = p["unit_cost"], p["list_price"]
    unit_price = round(price * (1 - discount_pct / 100), 2)
    return {
        "ok": True,
        "sku": sku,
        "qty": qty,
        "unit_cost": cost,
        "list_price": price,
        "discount_pct": discount_pct,
        "discounted_unit_price": unit_price,
        "order_total_at_list": round(price * qty, 2),
        "order_total_discounted": round(unit_price * qty, 2),
        "profit_per_unit": round(unit_price - cost, 2),
        "order_profit": round((unit_price - cost) * qty, 2),
        "margin_pct": round((unit_price - cost) / unit_price * 100, 1) if unit_price else None,
        "sells_below_cost": unit_price < cost,
        "break_even_discount_pct": round((1 - cost / price) * 100, 1),
    }


# --------------------------------------------- tools that write to the board ---

@mcp.tool
def request_payment_approval(
    ticket_id: int,
    kind: Literal["invoice", "rent"],
    ref_id: int,
    requested_by: str,
    reason: str,
    account: str = "checking",
) -> dict:
    """Ask a human to approve paying a vendor invoice or rent. Pays nothing.

    The amount comes from the database: invoices.amount for kind='invoice'
    (ref_id = invoice id), leases.monthly_rent for kind='rent' (ref_id =
    lease id). Refuses already-paid invoices and duplicate requests. Reads
    tickets, invoices or leases, cash_accounts; writes approval_requests.
    """
    with closing(_connect()) as conn:
        if _ticket(conn, ticket_id) is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        acct = _account(conn, account)
        if acct is None:
            return {"ok": False, "error": f"No cash account named {account}."}

        vendor_id = None
        if kind == "invoice":
            inv = conn.execute("SELECT * FROM invoices WHERE id = ?", (ref_id,)).fetchone()
            if inv is None:
                return {"ok": False, "error": f"No invoice with id {ref_id}."}
            if inv["status"] != "open":
                return {"ok": False, "error": f"Invoice {ref_id} is '{inv['status']}', not open."}
            amount, vendor_id = inv["amount"], inv["vendor_id"]
        else:
            lease = conn.execute("SELECT * FROM leases WHERE id = ?", (ref_id,)).fetchone()
            if lease is None:
                return {"ok": False, "error": f"No lease with id {ref_id}."}
            amount = lease["monthly_rent"]

        dup = _live_request(conn, kind, ref_id)
        if dup is not None:
            return {
                "ok": False,
                "error": f"Request #{dup['id']} for this {kind} is already {dup['status']}.",
                "existing_request_id": dup["id"],
            }

        cur = conn.execute(
            "INSERT INTO approval_requests (ticket_id, kind, ref_id, vendor_id, amount, account, "
            "reason, requested_by, status, created_at) VALUES (?,?,?,?,?,?,?,?, 'pending', ?)",
            (ticket_id, kind, ref_id, vendor_id, amount, account, reason, requested_by, _now()),
        )
        conn.commit()
    return {
        "ok": True,
        "request_id": cur.lastrowid,
        "status": "pending",
        "kind": kind,
        "ref_id": ref_id,
        "amount": amount,
        "account": account,
        "balance_now": acct["balance"],
        "balance_after_if_approved": round(acct["balance"] - amount, 2),
        "note": "Waiting for a human. No money has moved.",
    }


@mcp.tool
def request_purchase_order_approval(
    ticket_id: int,
    vendor_id: int,
    sku: str,
    size: str,
    qty: int,
    requested_by: str,
    reason: str,
    account: str = "checking",
) -> dict:
    """Ask a human to approve a restock purchase order. Orders nothing yet.

    The cost is pricing.unit_cost x qty. If the vendor has an open unpaid
    invoice, the request is still recorded but flagged as blocked: it cannot
    be paid until that invoice is paid. Reads tickets, vendors, inventory,
    pricing, invoices, cash_accounts; writes approval_requests.
    """
    if qty <= 0:
        return {"ok": False, "error": "qty must be positive."}
    with closing(_connect()) as conn:
        if _ticket(conn, ticket_id) is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        vendor = conn.execute("SELECT * FROM vendors WHERE id = ?", (vendor_id,)).fetchone()
        if vendor is None:
            return {"ok": False, "error": f"No vendor with id {vendor_id}."}
        inv_row = conn.execute(
            "SELECT 1 FROM inventory WHERE sku = ? AND size = ?", (sku, size)
        ).fetchone()
        if inv_row is None:
            return {"ok": False, "error": f"No inventory row for {sku} size {size}."}
        price = conn.execute("SELECT unit_cost FROM pricing WHERE sku = ?", (sku,)).fetchone()
        if price is None:
            return {"ok": False, "error": f"No pricing row for SKU {sku}."}
        acct = _account(conn, account)
        if acct is None:
            return {"ok": False, "error": f"No cash account named {account}."}

        amount = round(price["unit_cost"] * qty, 2)
        holds = _open_invoices(conn, vendor_id)
        today = _shop_today(conn)
        cur = conn.execute(
            "INSERT INTO approval_requests (ticket_id, kind, ref_id, vendor_id, sku, size, qty, "
            "amount, account, reason, requested_by, status, created_at) "
            "VALUES (?, 'purchase_order', NULL, ?,?,?,?,?,?,?,?, 'pending', ?)",
            (ticket_id, vendor_id, sku, size, qty, amount, account, reason, requested_by, _now()),
        )
        conn.commit()
    return {
        "ok": True,
        "request_id": cur.lastrowid,
        "status": "pending",
        "vendor": vendor["name"],
        "lead_days": vendor["lead_days"],
        "sku": sku, "size": size, "qty": qty,
        "unit_cost": price["unit_cost"],
        "amount": amount,
        "balance_now": acct["balance"],
        "balance_after_if_approved": round(acct["balance"] - amount, 2),
        "blocked_by_open_invoices": [dict(h) for h in holds],
        "earliest_delivery_if_approved_today": (
            None if holds
            else date.fromordinal(today.toordinal() + vendor["lead_days"]).isoformat()
        ),
        "note": (
            "Vendor is on hold: this order cannot be paid until its open invoice is paid."
            if holds else "Waiting for a human. Nothing has been ordered."
        ),
    }


@mcp.tool
def post_to_board(
    ticket_id: int,
    kind: Literal["customer_draft", "vendor_draft", "landlord_draft", "internal_note", "resolution"],
    author: str,
    body: str,
    recipient: str = "",
    subject: str = "",
) -> dict:
    """Save a draft message or note on the ticket board. Nothing is ever sent.

    Drafts to customers, vendors or the landlord stay on the board for a
    human to read. Each outside-message kind has one owning agent:
    customer_draft -> customer_service, landlord_draft -> facilities,
    vendor_draft -> inventory or accounting, resolution -> boss. Any agent may
    post an internal_note. Reads tickets; writes board_posts.
    """
    if not body.strip():
        return {"ok": False, "error": "body is empty."}
    who = author.strip().lower().replace(" ", "_")
    allowed = POST_AUTHORS.get(kind)
    if allowed and who in {a.replace(" ", "_") for a in AGENT_NAMES} and who not in allowed:
        owner = " or ".join(sorted(allowed))
        return {
            "ok": False,
            "error": f"Only {owner} may post a {kind}. Ask {owner} to write or revise it "
                     "(ask_teammate), or leave an internal_note instead.",
        }
    with closing(_connect()) as conn:
        if _ticket(conn, ticket_id) is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        cur = conn.execute(
            "INSERT INTO board_posts (ticket_id, kind, author, recipient, subject, body, created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (ticket_id, kind, author, recipient, subject, body, _now()),
        )
        conn.commit()
    return {"ok": True, "post_id": cur.lastrowid, "sent": False,
            "note": "Saved on the board only. Not emailed or sent."}


@mcp.tool
def update_ticket_status(
    ticket_id: int,
    status: Literal["open", "in_progress", "awaiting_approval", "resolved"],
    updated_by: str,
    note: str = "",
) -> dict:
    """Move a ticket to a new status, with a note saved on the board.

    Reads and writes tickets; writes board_posts (the note). A ticket with a
    pending approval request cannot be marked resolved.
    """
    with closing(_connect()) as conn:
        t = _ticket(conn, ticket_id)
        if t is None:
            return {"ok": False, "error": f"No ticket with id {ticket_id}."}
        if status == "resolved":
            pending = conn.execute(
                "SELECT id FROM approval_requests WHERE ticket_id = ? AND status = 'pending'",
                (ticket_id,),
            ).fetchall()
            if pending:
                return {
                    "ok": False,
                    "error": "Ticket has approval requests still waiting on a human; "
                             "use 'awaiting_approval' instead.",
                    "pending_request_ids": [p["id"] for p in pending],
                }
        conn.execute("UPDATE tickets SET status = ? WHERE id = ?", (status, ticket_id))
        if note.strip():
            conn.execute(
                "INSERT INTO board_posts (ticket_id, kind, author, body, created_at) "
                "VALUES (?, ?, ?, ?, ?)",
                (ticket_id, "resolution" if status == "resolved" else "internal_note",
                 updated_by, note, _now()),
            )
        conn.commit()
    return {"ok": True, "ticket_id": ticket_id, "old_status": t["status"], "new_status": status}


# --------------------------------------- human-only tool (hidden from agents) ---

@mcp.tool
def record_human_decision(
    request_id: int,
    decision: Literal["approve", "reject"],
    decided_by: str,
    note: str = "",
) -> dict:
    """HUMAN ONLY. Approve or reject a pending request; approving pays it.

    The agent backend never gives this tool to an agent; only the human
    dashboard calls it. On approve it checks, in one transaction, that the
    balance stays at or above zero and (for purchase orders) that the vendor
    has no open invoice. Then it writes payments, lowers cash_accounts, and
    marks the invoice paid or moves the lease's next_due forward one month.
    If a check fails, nothing is paid and the request is marked 'refused'.
    """
    approver = decided_by.strip()
    if not approver or approver.lower() in AGENT_NAMES:
        return {"ok": False, "error": "decided_by must be a named human, not an agent."}

    with closing(_connect()) as conn:
        req = conn.execute("SELECT * FROM approval_requests WHERE id = ?", (request_id,)).fetchone()
        if req is None:
            return {"ok": False, "error": f"No approval request with id {request_id}."}
        if req["status"] != "pending":
            return {"ok": False, "error": f"Request {request_id} is already {req['status']}."}

        def finish(status: str, msg: str, payment_id: int | None = None) -> dict:
            conn.execute(
                "UPDATE approval_requests SET status = ?, decided_by = ?, decided_at = ?, "
                "decision_note = ?, payment_id = ? WHERE id = ?",
                (status, approver, _now(), (note + " " + msg).strip(), payment_id, request_id),
            )
            conn.commit()
            return {"ok": status == "approved", "request_id": request_id, "status": status,
                    "message": msg, "payment_id": payment_id}

        if decision == "reject":
            return finish("rejected", "Rejected by human. No money moved.")

        try:
            conn.execute("BEGIN IMMEDIATE")
            acct = _account(conn, req["account"])
            if acct is None:
                conn.rollback()
                return finish("refused", f"Cash account {req['account']} not found.")
            amount = req["amount"]
            if acct["balance"] - amount < 0:
                conn.rollback()
                return finish(
                    "refused",
                    f"Refused: paying ${amount:,.2f} would leave {req['account']} at "
                    f"${acct['balance'] - amount:,.2f}. Balances may not go negative.",
                )
            if req["kind"] == "invoice":
                inv = conn.execute("SELECT status FROM invoices WHERE id = ?", (req["ref_id"],)).fetchone()
                if inv is None or inv["status"] != "open":
                    conn.rollback()
                    return finish("refused", f"Invoice {req['ref_id']} is no longer open.")
            if req["kind"] == "purchase_order" and _open_invoices(conn, req["vendor_id"]):
                conn.rollback()
                return finish("refused", "Refused: vendor still has an open unpaid invoice "
                                         "and will not ship. Pay that invoice first.")

            today = _shop_today(conn)
            new_balance = round(acct["balance"] - amount, 2)
            ref = req["ref_id"] if req["kind"] != "purchase_order" else req["id"]
            cur = conn.execute(
                "INSERT INTO payments (kind, ref_id, amount, account, paid_at, approved_by) "
                "VALUES (?,?,?,?,?,?)",
                (req["kind"], ref, amount, req["account"], today.isoformat(), approver),
            )
            conn.execute(
                "UPDATE cash_accounts SET balance = ?, date = ? WHERE name = ?",
                (new_balance, today.isoformat(), req["account"]),
            )
            effect = ""
            if req["kind"] == "invoice":
                conn.execute("UPDATE invoices SET status = 'paid' WHERE id = ?", (req["ref_id"],))
                effect = f"Invoice {req['ref_id']} marked paid."
            elif req["kind"] == "rent":
                lease = conn.execute("SELECT next_due FROM leases WHERE id = ?", (req["ref_id"],)).fetchone()
                nxt = _add_month(date.fromisoformat(lease["next_due"])).isoformat()
                conn.execute("UPDATE leases SET next_due = ? WHERE id = ?", (nxt, req["ref_id"]))
                effect = f"Lease {req['ref_id']} next_due moved to {nxt}."
            else:
                effect = (f"Purchase order paid: {req['qty']} x {req['sku']} size {req['size']}. "
                          "Stock arrives after the vendor's lead time.")
            return finish(
                "approved",
                f"Paid ${amount:,.2f} from {req['account']} (now ${new_balance:,.2f}). {effect}",
                cur.lastrowid,
            )
        except Exception:
            conn.rollback()
            raise


if __name__ == "__main__":
    mcp.run()
