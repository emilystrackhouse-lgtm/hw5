import { useEffect, useRef, useState } from 'react'
import { money, useTween } from '../hooks'
import type { CashResponse } from '../types'

const KIND_LABEL: Record<string, string> = {
  invoice: 'Vendor invoice',
  rent: 'Rent',
  purchase_order: 'Purchase order',
}

export function CashPanel({ cash }: { cash: CashResponse | null }) {
  const balance = cash?.checking.balance ?? 0
  const shown = useTween(cash ? balance : null)
  const prev = useRef<number | null>(null)
  const [drop, setDrop] = useState<{ amount: number; key: number } | null>(null)

  useEffect(() => {
    if (cash == null) return
    if (prev.current != null && balance < prev.current) {
      setDrop({ amount: prev.current - balance, key: Date.now() })
      const t = window.setTimeout(() => setDrop(null), 3200)
      prev.current = balance
      return () => window.clearTimeout(t)
    }
    prev.current = balance
  }, [balance, cash])

  if (!cash) return <section className="panel cash"><p className="muted">Loading cash…</p></section>

  const c = cash.checking
  const start = Math.max(c.balance + cash.payments_made.reduce((s, p) => s + p.amount, 0), 1)
  const pctLeft = Math.max(0, (c.balance / start) * 100)
  const pctPending = Math.min(pctLeft, (c.pending_requests_total / start) * 100)

  return (
    <section className="panel cash" aria-labelledby="cash-title">
      <h2 id="cash-title" className="panel-title">Checking</h2>
      <div className="balance-row">
        <span className="balance" aria-live="polite">{money(shown)}</span>
        {drop && <span key={drop.key} className="drop-chip">−{money(drop.amount)}</span>}
      </div>
      <p className="muted small">as of {c.as_of} · no money comes in</p>

      <div className="meter" role="img"
        aria-label={`${money(c.balance)} left of ${money(start)}; ${money(c.pending_requests_total)} waiting on approval`}>
        <span className="meter-left" style={{ width: `${pctLeft}%` }} />
        <span className="meter-pending" style={{ width: `${pctPending}%`, left: `${pctLeft - pctPending}%` }} />
      </div>
      <dl className="cash-facts">
        <div><dt>Waiting on approval</dt><dd>{money(c.pending_requests_total)}</dd></div>
        <div className={c.can_cover_all_pending ? '' : 'warn'}>
          <dt>If you approve everything</dt><dd>{money(c.balance_if_all_pending_approved)}</dd>
        </div>
      </dl>

      <h3 className="sub-title">Paid out</h3>
      {cash.payments_made.length === 0 ? (
        <p className="muted small">Nothing paid yet.</p>
      ) : (
        <ul className="ledger">
          {[...cash.payments_made].reverse().map(p => (
            <li key={p.id}>
              <span>{KIND_LABEL[p.kind] ?? p.kind}{p.ref_id ? ` #${p.ref_id}` : ''}<small>approved by {p.approved_by}</small></span>
              <b>−{money(p.amount)}</b>
            </li>
          ))}
        </ul>
      )}
    </section>
  )
}
