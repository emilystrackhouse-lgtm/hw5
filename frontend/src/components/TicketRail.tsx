import type { Ticket, TicketStatus } from '../types'

export const TYPE_LABEL: Record<string, string> = {
  customer_order: 'Customer order',
  rent_notice: 'Rent notice',
  price_override: 'Discount request',
}

export const STATUS_LABEL: Record<TicketStatus, string> = {
  open: 'Open',
  in_progress: 'Agents working',
  awaiting_approval: 'Needs your OK',
  resolved: 'Resolved',
}

const STEPS: TicketStatus[] = ['open', 'in_progress', 'awaiting_approval', 'resolved']

export function ticketLine(t: Ticket): string {
  if (t.sku) return `${t.qty ?? ''} × ${t.sku} · ${t.size}`.trim()
  if (t.lease_id) return `Lease ${t.lease_id}`
  return t.subject
}

export function StatusStepper({ status, working }: { status: TicketStatus; working: boolean }) {
  const current = working ? 1 : STEPS.indexOf(status)
  return (
    <ol className="stepper" aria-label={`Progress: ${working ? 'Agents working' : STATUS_LABEL[status]}`}>
      {STEPS.map((s, i) => (
        <li key={s} className={i < current ? 'done' : i === current ? 'now' : ''}>
          <span className="dot" aria-hidden />
          <span className="step-label">{STATUS_LABEL[s]}</span>
        </li>
      ))}
    </ol>
  )
}

export function StatusPill({ status, working }: { status: TicketStatus; working: boolean }) {
  const s = working ? 'in_progress' : status
  return <span className={`status-pill status-${s}`}>{working ? 'Agents working…' : STATUS_LABEL[s]}</span>
}

interface Props {
  tickets: Ticket[]
  selectedId: number | null
  celebrating: Set<number>
  onSelect: (id: number) => void
}

export function TicketRail({ tickets, selectedId, celebrating, onSelect }: Props) {
  return (
    <nav className="ticket-rail" aria-label="Tickets">
      <h2 className="rail-title">Ticket board</h2>
      {tickets.length === 0 && <p className="muted small">No tickets yet.</p>}
      {tickets.map(t => (
        <button
          key={t.id}
          className={`ticket-card${t.id === selectedId ? ' selected' : ''}${t.is_resolved ? ' is-resolved' : ''}`}
          onClick={() => onSelect(t.id)}
          aria-pressed={t.id === selectedId}
          aria-label={`Ticket ${t.id}: ${t.subject}, ${t.agents_working ? 'agents working' : STATUS_LABEL[t.status]}`}
        >
          <span className="ticket-top">
            <span className="ticket-num">#{t.id}</span>
            <StatusPill status={t.status} working={t.agents_working} />
          </span>
          <span className="ticket-subject">{t.subject}</span>
          <span className="ticket-meta-line">{TYPE_LABEL[t.type] ?? t.type} · {t.requester}</span>
          <span className="ticket-meta-line mono">{ticketLine(t)}</span>
          {t.pending_approvals > 0 && (
            <span className="ticket-flag">{t.pending_approvals} payment{t.pending_approvals > 1 ? 's' : ''} waiting on you</span>
          )}
          {t.is_resolved && (
            <span className={`stamp${celebrating.has(t.id) ? ' stamp-pop' : ''}`} aria-hidden>Resolved ✓</span>
          )}
          {t.agents_working && <span className="working-bar" aria-hidden />}
        </button>
      ))}
    </nav>
  )
}
