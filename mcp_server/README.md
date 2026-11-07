# Campus Customs MCP Server

## Purpose

This server is the agent team's only way to reach the shop's data. The Boss, Inventory, Accounting, Facilities and Customer Service agents all read and update the shop through its tools. Every tool answers only from the database and invents nothing.

It is built with [FastMCP](https://gofastmcp.com) in `server.py`.

## Database

- **Uses:** `data/campus_customs_new.db`, the working copy that changes as tickets are resolved.
- **Never touches:** `data/campus_customs.db`, the original. To start over, run `python -m backend.reset_db`.
- **Override:** set `DB_PATH` to point somewhere else. Relative paths are read from the project root (`hw5/`). FastMCP's stdio launcher doesn't pass on the caller's environment, so a client must pass `DB_PATH` explicitly. `.mcp.json` and the backend both do.
- **"Today":** every date calculation uses the shop's date, `desk.date_today` (2026-08-31), not the real calendar.
- **Added tables:** the server adds two tables to the working copy, for the team's own work. Both start empty after a reset:
  - `approval_requests`: payments and purchase orders waiting on a human.
  - `board_posts`: drafts and notes. Nothing is ever sent.

## Tools

### Read only

| Tool | Inputs | Reads | Returns |
|---|---|---|---|
| `list_open_tickets` | none | tickets, desk | Every ticket not yet resolved, plus the shop's "today" |
| `get_ticket` | `ticket_id` | tickets, board_posts, approval_requests | One ticket plus all drafts, notes and approval requests on it |
| `check_stock_shortfall` | `sku`, `size`, `qty_needed` | inventory, pricing | On hand, shortfall, other sizes, cost, price, margin, restock cost |
| `check_invoice_and_vendor_hold` | `invoice_id` | invoices, vendors, desk | Amount, due date, days overdue, vendor, lead time, whether the vendor is **on hold** |
| `check_rent_due` | `lease_id` | leases, desk, cash_accounts | Rent, due date, days until due, whether cash covers it |
| `list_vendors` | none | vendors, invoices, desk | Each vendor's specialty, lead time, on-hold status and earliest delivery date |
| `get_cash_position` | none | cash_accounts, approval_requests, payments | Balance, total of pending requests, balance if all approved, payments made |
| `check_discount_margin` | `sku`, `qty`, `discount_pct` | pricing | Discounted price, profit, margin, break-even discount |
| `list_tickets` | none | tickets, approval_requests, board_posts, desk | Every ticket (open or resolved) with its status, pending approvals and post count. Used by the dashboard. |
| `list_approval_requests` | `status` (pending/approved/rejected/refused/all) | approval_requests, vendors, cash_accounts | The approval queue, with the balance each request would leave. Used by the dashboard. |

### Write (no money moves)

| Tool | Inputs | Writes | Notes |
|---|---|---|---|
| `request_payment_approval` | `ticket_id`, `kind` (invoice/rent), `ref_id`, `requested_by`, `reason` | approval_requests | Amount is taken from the invoice or lease. Refuses paid invoices and duplicates. |
| `request_purchase_order_approval` | `ticket_id`, `vendor_id`, `sku`, `size`, `qty`, `requested_by`, `reason` | approval_requests | Cost = unit cost × qty. Flags the request if the vendor is on hold. |
| `post_to_board` | `ticket_id`, `kind`, `author`, `body`, `recipient`, `subject` | board_posts | Drafts and notes only; returns `sent: false`. Each outside message has one owning agent: `customer_draft` → customer_service, `landlord_draft` → facilities, `vendor_draft` → inventory/accounting, `resolution` → boss. Any agent may post an `internal_note`. |
| `update_ticket_status` | `ticket_id`, `status`, `updated_by`, `note` | tickets, board_posts | Won't mark a ticket `resolved` while an approval is pending. |

### Human only (moves money)

| Tool | Inputs | Writes | Notes |
|---|---|---|---|
| `record_human_decision` | `request_id`, `decision` (approve/reject), `decided_by`, `note` | payments, cash_accounts, invoices or leases, approval_requests | The backend never gives this tool to an agent, and it rejects agent names as approvers. On approval, in one transaction, it refuses if the balance would go negative or the vendor is still on hold. Otherwise it records the payment, lowers the balance, and marks the invoice paid or moves the lease's due date forward a month. |

## Running it

```bash
pip install -r requirements.txt
python mcp_server/server.py
```

The project-root `.mcp.json` registers this server for the vibe coder as `campus-customs`. The backend starts its own copy over stdio for each ticket run.
