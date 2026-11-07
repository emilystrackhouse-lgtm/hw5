import { useState } from 'react'
import type { CSSProperties } from 'react'
import { AgentBadge, agentLook } from '../agents'
import { money } from '../hooks'
import type { ApprovalRequest } from '../types'

function describe(r: ApprovalRequest): string {
  if (r.kind === 'invoice') return `Pay invoice #${r.ref_id}${r.vendor_name ? ` to ${r.vendor_name}` : ''}`
  if (r.kind === 'rent') return `Pay rent on lease #${r.ref_id}`
  return `Order ${r.qty} × ${r.sku} ${r.size}${r.vendor_name ? ` from ${r.vendor_name}` : ''}`
}

interface Props {
  pending: ApprovalRequest[]
  recent: ApprovalRequest[]
  approver: string
  busyId: number | null
  onDecide: (id: number, decision: 'approve' | 'reject') => void
}

export function ApprovalQueue({ pending, recent, approver, busyId, onDecide }: Props) {
  const [confirming, setConfirming] = useState<number | null>(null)
  const needName = approver.trim() === ''

  return (
    <section className="panel approvals" aria-labelledby="approvals-title">
      <h2 id="approvals-title" className="panel-title">
        Needs your approval {pending.length > 0 && <span className="count">{pending.length}</span>}
      </h2>
      {needName && pending.length > 0 && (
        <p className="hint">Enter your name in “Approving as” (top right) to approve or reject.</p>
      )}
      {pending.length === 0 && <p className="muted small">Nothing waiting. Agents prepare payments here; only you can approve them.</p>}

      <ul className="approval-list">
        {pending.map(r => {
          const look = agentLook(r.requested_by)
          const isConfirming = confirming === r.id
          return (
            <li key={r.id} className={`approval${r.would_overdraw ? ' overdraw' : ''}`}
                style={{ '--agent': look?.color } as CSSProperties}>
              <div className="approval-head">
                <span className="approval-amt">{money(r.amount)}</span>
                <span className="ticket-tag">Ticket #{r.ticket_id}</span>
              </div>
              <p className="approval-what">{describe(r)}</p>
              <p className="approval-why">{r.reason}</p>
              <p className="approval-by">
                <AgentBadge name={r.requested_by} size="sm" /> prepared by {look?.label ?? r.requested_by}
              </p>
              <p className={`after${r.would_overdraw ? ' warn' : ''}`}>
                {r.would_overdraw
                  ? `Would overdraw checking (${money(r.balance_after_if_approved ?? 0)}), so it will be refused`
                  : `Checking after: ${money(r.balance_after_if_approved ?? 0)}`}
              </p>
              <div className="approval-actions">
                {isConfirming ? (
                  <>
                    <button className="btn btn-approve" disabled={busyId === r.id}
                      onClick={() => { onDecide(r.id, 'approve'); setConfirming(null) }}>
                      {busyId === r.id ? 'Paying…' : `Confirm: pay ${money(r.amount)}`}
                    </button>
                    <button className="btn btn-ghost" onClick={() => setConfirming(null)}>Cancel</button>
                  </>
                ) : (
                  <>
                    <button className="btn btn-approve" disabled={needName || busyId !== null}
                      onClick={() => setConfirming(r.id)}>Approve</button>
                    <button className="btn btn-ghost" disabled={needName || busyId !== null}
                      onClick={() => onDecide(r.id, 'reject')}>Reject</button>
                  </>
                )}
              </div>
            </li>
          )
        })}
      </ul>

      {recent.length > 0 && (
        <>
          <h3 className="sub-title">Decided</h3>
          <ul className="decided-list">
            {recent.slice(0, 5).map(r => (
              <li key={r.id} className={`decided decided-${r.status}`}>
                <span>{describe(r)}</span>
                <span className="decided-status">{r.status} · {money(r.amount)}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  )
}
