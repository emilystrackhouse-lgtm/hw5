import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { api, ApiError, API_BASE } from './api'
import { AgentBadge } from './agents'
import { ActivityFeed, AgentRoster } from './components/ActivityFeed'
import { ApprovalQueue } from './components/ApprovalQueue'
import { CashPanel } from './components/CashPanel'
import { BoardDrafts, Contributions } from './components/Contributions'
import { StatusStepper, TicketRail, TYPE_LABEL, ticketLine } from './components/TicketRail'
import { money, useNow, usePoll, useStoredString } from './hooks'
import type {
  ActivityItem, ApprovalRequest, CashResponse, ContributionsResponse, RunState, Ticket, TicketDetail, TicketStatus,
} from './types'

interface Toast { id: number; tone: 'ok' | 'warn' | 'err'; text: string }

const AGENT_NAMES = new Set(['boss', 'inventory', 'accounting', 'facilities', 'customer_service'])

export default function App() {
  const [tickets, setTickets] = useState<Ticket[]>([])
  const [shopToday, setShopToday] = useState('')
  // A link like http://localhost:5173/#ticket=102 opens that ticket directly.
  const [selectedId, setSelectedId] = useState<number | null>(() => {
    const m = window.location.hash.match(/ticket=(\d+)/)
    return m ? Number(m[1]) : null
  })
  const [detail, setDetail] = useState<TicketDetail | null>(null)
  const [feed, setFeed] = useState<ActivityItem[]>([])
  const [contrib, setContrib] = useState<ContributionsResponse | null>(null)
  const [cash, setCash] = useState<CashResponse | null>(null)
  const [pending, setPending] = useState<ApprovalRequest[]>([])
  const [decided, setDecided] = useState<ApprovalRequest[]>([])
  const [run, setRun] = useState<RunState | null>(null)
  const [offline, setOffline] = useState<string | null>(null)
  const [toasts, setToasts] = useState<Toast[]>([])
  const [busyId, setBusyId] = useState<number | null>(null)
  const [starting, setStarting] = useState(false)
  const [celebrating, setCelebrating] = useState<Set<number>>(new Set())
  const [approver, setApprover] = useStoredString('cc-approver')

  const cursor = useRef(-1)
  const feedFor = useRef<number | null>(null)
  const inFlight = useRef<number | null>(null)
  const lastStatus = useRef<Map<number, TicketStatus>>(new Map())

  const toast = useCallback((tone: Toast['tone'], text: string) => {
    const id = Date.now() + Math.random()
    setToasts(t => [...t, { id, tone, text }])
    window.setTimeout(() => setToasts(t => t.filter(x => x.id !== id)), 6000)
  }, [])

  const working = tickets.some(t => t.agents_working) || run?.status === 'running'
  const selected = tickets.find(t => t.id === selectedId) ?? null

  // ---- data loading -------------------------------------------------------
  const loadBoard = useCallback(async () => {
    try {
      const [t, c, p, all] = await Promise.all([api.tickets(), api.cash(), api.approvals('pending'), api.approvals('all')])
      setOffline(null)
      setShopToday(t.shop_today)
      setTickets(t.tickets)
      setCash(c)
      setPending(p.requests)
      setDecided(all.requests.filter(r => r.status !== 'pending'))
      setSelectedId(id => id ?? t.tickets[0]?.id ?? null)

      // Celebrate tickets that just turned resolved.
      const fresh: number[] = []
      for (const tk of t.tickets) {
        const before = lastStatus.current.get(tk.id)
        if (before && before !== 'resolved' && tk.status === 'resolved') fresh.push(tk.id)
        lastStatus.current.set(tk.id, tk.status)
      }
      if (fresh.length) {
        setCelebrating(s => new Set([...s, ...fresh]))
        fresh.forEach(id => toast('ok', `Ticket #${id} is resolved.`))
        window.setTimeout(() => setCelebrating(s => new Set([...s].filter(x => !fresh.includes(x)))), 2600)
      }
    } catch (e) {
      setOffline(e instanceof ApiError ? e.message : String(e))
    }
  }, [toast])

  const loadTicket = useCallback(async () => {
    const id = selectedId
    if (id == null) return
    if (feedFor.current !== id) { feedFor.current = id; cursor.current = -1; setFeed([]); setContrib(null); setDetail(null) }
    if (inFlight.current === id) return  // a refresh for this ticket is already running
    inFlight.current = id
    try {
      const [d, a, k] = await Promise.all([api.ticket(id), api.activity(id, cursor.current), api.contributions(id)])
      if (feedFor.current !== id) return  // user switched tickets mid-request
      setDetail(d)
      setContrib(k)
      const fresh = a.items.filter(i => i.index > a.last_reset_index)
      // Append only items newer than what's shown, so overlapping refreshes never duplicate.
      if (fresh.length) {
        setFeed(f => {
          const newest = f.length ? f[f.length - 1].index : -1
          const add = fresh.filter(i => i.index > newest)
          return add.length ? [...f, ...add] : f
        })
      }
      cursor.current = Math.max(cursor.current, a.last_index)
    } catch { /* surfaced by loadBoard's offline banner */ } finally {
      if (inFlight.current === id) inFlight.current = null
    }
  }, [selectedId])

  const loadRun = useCallback(async () => {
    if (!run || run.status !== 'running') return
    try {
      const r = await api.run(run.run_id)
      setRun(r)
      if (r.status !== 'running') {
        if (r.status === 'completed') toast('ok', `Agents finished ticket #${r.ticket_id}.`)
        else toast('err', `Run on ticket #${r.ticket_id} ${r.status.replace(/_/g, ' ')}: ${r.error ?? ''}`)
      }
    } catch { /* keep polling */ }
  }, [run, toast])

  const interval = working ? 1500 : 5000
  usePoll(loadBoard, interval)
  usePoll(loadTicket, interval, selectedId != null)
  usePoll(loadRun, 1500, run?.status === 'running')

  useEffect(() => { void loadTicket() }, [selectedId, loadTicket])
  useEffect(() => {
    if (selectedId != null) window.history.replaceState(null, '', `#ticket=${selectedId}`)
  }, [selectedId])

  // ---- actions --------------------------------------------------------------
  const start = async () => {
    if (!selected) return
    setStarting(true)
    try {
      const r = await api.startRun(selected.id)
      setRun(r)
      toast('ok', `The Boss picked up ticket #${selected.id}.`)
      await loadBoard()
    } catch (e) {
      toast('err', e instanceof ApiError ? e.message : String(e))
    } finally {
      setStarting(false)
    }
  }

  const decide = async (id: number, decision: 'approve' | 'reject') => {
    setBusyId(id)
    try {
      const res = decision === 'approve' ? await api.approve(id, approver.trim()) : await api.reject(id, approver.trim())
      toast(res.status === 'approved' ? 'ok' : res.status === 'refused' ? 'warn' : 'ok', res.message)
      await Promise.all([loadBoard(), loadTicket()])
    } catch (e) {
      toast('err', e instanceof ApiError ? e.message : String(e))
    } finally {
      setBusyId(null)
    }
  }

  const reset = async () => {
    if (!window.confirm('Reset the shop database to its original values? Drafts, approvals and payments from earlier runs will be cleared.')) return
    try {
      const r = await api.reset()
      toast('ok', r.message)
      setRun(null); feedFor.current = null; lastStatus.current.clear()
      await Promise.all([loadBoard(), loadTicket()])
    } catch (e) {
      toast('err', e instanceof ApiError ? e.message : String(e))
    }
  }

  // ---- derived view state --------------------------------------------------------
  const lastRunItems = useMemo(() => {
    const startAt = feed.map(i => i.kind).lastIndexOf('run_start')
    return startAt === -1 ? feed : feed.slice(startAt)
  }, [feed])
  const involved = useMemo(() => new Set(lastRunItems.map(i => i.agent).filter(a => AGENT_NAMES.has(a))), [lastRunItems])
  const selectedRunning = !!selected?.agents_working
  const activeAgent = useMemo(() => {
    for (let i = lastRunItems.length - 1; i >= 0; i--) {
      const it = lastRunItems[i]
      if (it.kind === 'delegation') return it.to ?? null
      if (AGENT_NAMES.has(it.agent)) return it.agent
    }
    return null
  }, [lastRunItems])
  const now = useNow(selectedRunning)
  const elapsed = run && run.ticket_id === selectedId && run.status === 'running'
    ? Math.max(0, Math.round((now - Date.parse(run.started_at)) / 1000)) : null

  const ticketPending = pending.filter(p => p.ticket_id === selectedId)

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden><span /></span>
          <div>
            <h1>Campus Customs <em>Ops Floor</em></h1>
            <p className="muted small">Five agents run the back office. You hold the checkbook.</p>
          </div>
        </div>
        <div className="top-controls">
          {shopToday && <span className="chip">Shop date <b>{shopToday}</b></span>}
          <span className="chip">Model <b>gpt-6-luna</b></span>
          <label className="approver">
            <span>Approving as</span>
            <input value={approver} onChange={e => setApprover(e.target.value)} placeholder="Your name" maxLength={60} />
          </label>
          <button className="btn btn-ghost" onClick={reset} disabled={working}>Reset shop</button>
        </div>
      </header>

      {offline && (
        <div className="banner" role="alert">
          {offline} Start it from <code>backend/</code> with <code>uvicorn main:app --reload --port 8000</code> (expected at {API_BASE}).
        </div>
      )}

      <main className="floor">
        <TicketRail tickets={tickets} selectedId={selectedId} celebrating={celebrating} onSelect={setSelectedId} />

        <section className="stage" aria-label="Selected ticket">
          {selected ? (
            <>
              <div className={`hero${selected.is_resolved ? ' resolved' : ''}${celebrating.has(selected.id) ? ' celebrate' : ''}`}>
                <div className="hero-main">
                  <p className="eyebrow">{TYPE_LABEL[selected.type] ?? selected.type} · Ticket #{selected.id}</p>
                  <h2>{selected.subject}</h2>
                  <p className="hero-from">from <b>{selected.requester}</b> · <span className="mono">{ticketLine(selected)}</span></p>
                  {selected.notes && <blockquote>“{selected.notes}”</blockquote>}
                  <StatusStepper status={selected.status} working={selected.agents_working} />
                </div>
                <div className="hero-action">
                  {selected.is_resolved ? (
                    <div className="resolved-badge" role="status">
                      <span className="check" aria-hidden>✓</span>
                      <b>Resolved</b>
                      <span className="muted small">Reset the shop to run it again.</span>
                    </div>
                  ) : selected.status === 'awaiting_approval' && !selectedRunning ? (
                    <div className="resolved-badge waiting" role="status">
                      <b>Waiting on your OK</b>
                      <span className="muted small">Approve or reject in the panel on the right. The ticket resolves when you've decided.</span>
                    </div>
                  ) : (
                    <button className="btn btn-primary btn-big" onClick={start} disabled={working || starting}>
                      {selectedRunning ? 'Agents working…' : starting ? 'Starting…' : selected.status === 'open' ? 'Start the agent team' : 'Run the team again'}
                    </button>
                  )}
                  {elapsed !== null && <span className="muted small">running {elapsed}s · updates every 1.5s</span>}
                  {working && !selectedRunning && !selected.is_resolved && (
                    <span className="muted small">Another ticket is being worked. One at a time, since they share the cash.</span>
                  )}
                  {ticketPending.length > 0 && (
                    <span className="hero-flag">
                      {ticketPending.length} payment{ticketPending.length > 1 ? 's' : ''} ({money(ticketPending.reduce((s, p) => s + p.amount, 0))}) waiting on you →
                    </span>
                  )}
                </div>
              </div>

              <AgentRoster activeAgent={activeAgent} involved={involved} running={selectedRunning} />

              <section className="panel" aria-labelledby="feed-title">
                <h2 id="feed-title" className="panel-title">
                  Live floor {selectedRunning && <span className="live-dot">live</span>}
                </h2>
                <ActivityFeed items={feed} running={selectedRunning} />
              </section>

              <div className="two-up">
                <section className="panel" aria-labelledby="contrib-title">
                  <h2 id="contrib-title" className="panel-title">Who did what</h2>
                  <Contributions data={contrib} />
                </section>
                <section className="panel" aria-labelledby="drafts-title">
                  <h2 id="drafts-title" className="panel-title">On the board <span className="muted small">(drafts are never sent)</span></h2>
                  <BoardDrafts posts={detail?.board_posts ?? []} />
                </section>
              </div>
            </>
          ) : (
            <div className="panel"><p className="muted">Loading tickets…</p></div>
          )}
        </section>

        <aside className="side" aria-label="Cash and approvals">
          <CashPanel cash={cash} />
          <ApprovalQueue pending={pending} recent={decided} approver={approver} busyId={busyId} onDecide={decide} />
        </aside>
      </main>

      <div className="toasts" aria-live="polite">
        {toasts.map(t => (
          <div key={t.id} className={`toast toast-${t.tone}`}>
            {t.tone === 'ok' ? <AgentBadge name="boss" size="sm" /> : <span aria-hidden>{t.tone === 'warn' ? '⚠' : '✕'}</span>}
            <span>{t.text}</span>
          </div>
        ))}
      </div>
    </div>
  )
}
