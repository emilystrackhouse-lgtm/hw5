// Shapes returned by the FastAPI backend (backend/main.py).

export type AgentName = 'boss' | 'inventory' | 'accounting' | 'facilities' | 'customer_service'
export type TicketStatus = 'open' | 'in_progress' | 'awaiting_approval' | 'resolved'

export interface Ticket {
  id: number
  type: string
  requester: string
  subject: string
  sku: string | null
  size: string | null
  qty: number | null
  lease_id: number | null
  invoice_id: number | null
  status: TicketStatus
  notes: string | null
  created_at: string
  pending_approvals: number
  board_posts: number
  is_resolved: boolean
  agents_working: boolean
  run_id: string | null
}

export interface TicketsResponse {
  shop_today: string
  tickets: Ticket[]
}

export interface BoardPost {
  id: number
  ticket_id: number
  kind: 'customer_draft' | 'vendor_draft' | 'landlord_draft' | 'internal_note' | 'resolution'
  author: string
  recipient: string | null
  subject: string | null
  body: string
  created_at: string
}

export interface ApprovalRequest {
  id: number
  ticket_id: number
  kind: 'invoice' | 'rent' | 'purchase_order'
  ref_id: number | null
  vendor_id: number | null
  vendor_name?: string | null
  sku: string | null
  size: string | null
  qty: number | null
  amount: number
  account: string
  reason: string
  requested_by: string
  status: 'pending' | 'approved' | 'rejected' | 'refused'
  decided_by: string | null
  decided_at: string | null
  decision_note: string | null
  payment_id: number | null
  created_at: string
  balance_now?: number | null
  balance_after_if_approved?: number | null
  would_overdraw?: boolean
}

export interface TicketDetail {
  found: boolean
  shop_today: string
  ticket: Ticket
  board_posts: BoardPost[]
  approval_requests: ApprovalRequest[]
}

export interface Usage {
  requests?: number | null
  tool_calls?: number | null
  input_tokens?: number
  output_tokens?: number
  total_tokens?: number
}

export type ActivityKind =
  | 'message' | 'tool_call' | 'tool_result' | 'delegation' | 'delegation_refused'
  | 'agent_done' | 'run_start' | 'run_end' | 'error' | 'human_decision'

export interface ActivityItem {
  index: number
  timestamp: string
  run_id: string
  ticket_id: number | null
  agent: string
  depth: number
  kind: ActivityKind
  text?: string
  tool?: string
  args?: Record<string, unknown>
  to?: string
  usage?: Usage | null
}

export interface ActivityResponse {
  last_index: number
  last_reset_index: number
  items: ActivityItem[]
}

export interface Payment {
  id: number
  kind: string
  ref_id: number | null
  amount: number
  account: string
  paid_at: string
  approved_by: string
}

export interface CashResponse {
  checking: {
    name: string
    balance: number
    as_of: string
    pending_requests_total: number
    balance_if_all_pending_approved: number
    can_cover_all_pending: boolean
  }
  pending_requests: Pick<ApprovalRequest, 'id' | 'ticket_id' | 'kind' | 'ref_id' | 'amount' | 'account' | 'status'>[]
  payments_made: Payment[]
}

export interface RunState {
  run_id: string
  ticket_id: number
  status: 'running' | 'completed' | 'failed' | 'stopped_by_limit'
  started_at: string
  finished_at: string | null
  outcome: Outcome | null
  error: string | null
}

export interface Fact {
  label: string
  value: string
  source_tool: string
}

export interface Outcome {
  ticket_id: number
  decision: string
  final_status: TicketStatus
  agents_consulted: AgentName[]
  key_facts: Fact[]
  approval_request_ids: number[]
  board_post_ids: number[]
  human_next_steps: string[]
  risks: string[]
}

export interface Contribution {
  agent: string
  summaries: string[]
  tools: { tool: string; calls: number }[]
  asked: string[]
  asked_by: string[]
  approval_request_ids: number[]
  board_post_ids: number[]
  tokens: number
}

export interface ContributionsResponse {
  ticket_id: number
  run_id: string | null
  status: string
  agents: Contribution[]
  outcome: Outcome | null
  usage?: Usage | null
}

export interface DecisionResult {
  ok: boolean
  request_id: number
  status: ApprovalRequest['status']
  message: string
  payment_id: number | null
  ticket_resolved?: number
}
