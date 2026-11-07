import { useEffect, useRef } from 'react'
import type { CSSProperties } from 'react'
import { AGENT_ORDER, AGENTS, AgentBadge, agentLook } from '../agents'
import type { ActivityItem, AgentName } from '../types'

const TOOL_LABEL: Record<string, string> = {
  get_ticket: 'read the ticket',
  list_open_tickets: 'listed open tickets',
  check_stock_shortfall: 'checked stock',
  check_invoice_and_vendor_hold: 'checked the invoice & vendor hold',
  check_rent_due: 'checked rent due',
  list_vendors: 'looked up vendors',
  get_cash_position: 'checked cash',
  check_discount_margin: 'priced a discount',
  request_payment_approval: 'requested payment approval',
  request_purchase_order_approval: 'requested a purchase order',
  post_to_board: 'posted to the board',
  update_ticket_status: 'updated the ticket status',
}

const name = (a: string) => agentLook(a)?.label ?? (a.startsWith('human:') ? a.slice(6) : a)

function ArgChips({ args }: { args?: Record<string, unknown> }) {
  if (!args) return null
  const shown = Object.entries(args).filter(([k]) => !['author', 'updated_by', 'requested_by', 'body', 'reason', 'note'].includes(k))
  if (shown.length === 0) return null
  return (
    <span className="chips">
      {shown.map(([k, v]) => (
        <span key={k} className="chip-arg"><b>{k}</b> {String(v)}</span>
      ))}
    </span>
  )
}

function FeedItem({ item }: { item: ActivityItem }) {
  const look = agentLook(item.agent)
  const style = { '--agent': look?.color ?? 'var(--muted)', '--depth': item.depth } as CSSProperties

  switch (item.kind) {
    case 'run_start':
      return <li className="feed-divider">▶ Agents started on this ticket</li>
    case 'run_end':
      return (
        <li className="feed-divider end">
          ■ Run {item.text === 'completed' ? 'finished' : item.text}
          {item.usage?.total_tokens ? ` · ${item.usage.total_tokens.toLocaleString()} tokens` : ''}
        </li>
      )
    case 'delegation': {
      const to = agentLook(item.to ?? '')
      return (
        <li className="feed-item handoff" style={{ ...style, '--to': to?.color ?? 'var(--muted)' } as CSSProperties}>
          <div className="handoff-line">
            <AgentBadge name={item.agent} size="sm" />
            <span className="handoff-arrow" aria-hidden>→</span>
            <AgentBadge name={item.to ?? ''} size="sm" />
            <span><b>{name(item.agent)}</b> asked <b>{name(item.to ?? '')}</b></span>
          </div>
          <p className="handoff-task">“{item.text}”</p>
        </li>
      )
    }
    case 'delegation_refused':
      return (
        <li className="feed-item note" style={style}>
          <span className="feed-who">{name(item.agent)}</span> couldn't hand off to {name(item.to ?? '')}: {item.text}
        </li>
      )
    case 'tool_call':
      return (
        <li className="feed-item tool" style={style}>
          <AgentBadge name={item.agent} size="sm" />
          <div>
            <span className="feed-who">{name(item.agent)}</span>{' '}
            <span className="feed-action">{TOOL_LABEL[item.tool ?? ''] ?? `called ${item.tool}`}</span>
            <code className="tool-name">{item.tool}</code>
            <ArgChips args={item.args} />
          </div>
        </li>
      )
    case 'tool_result':
      return (
        <li className="feed-item result" style={style}>
          <details>
            <summary><span className="result-tag">result</span> {item.tool}</summary>
            <pre>{item.text}</pre>
          </details>
        </li>
      )
    case 'message':
    case 'agent_done':
      return (
        <li className={`feed-item bubble${item.kind === 'agent_done' ? ' done' : ''}`} style={style}>
          <AgentBadge name={item.agent} />
          <div className="bubble-body">
            <div className="bubble-head">
              <span className="feed-who">{name(item.agent)}</span>
              {item.kind === 'agent_done' && <span className="done-tag">reported back</span>}
            </div>
            <p>{item.text}</p>
          </div>
        </li>
      )
    case 'human_decision':
      return <li className="feed-item note human" style={style}>🧑‍💼 {name(item.agent)}: {item.text}</li>
    case 'error':
      return <li className="feed-item error" style={style}>⚠ {name(item.agent)} hit an error: {item.text}</li>
    default:
      return null
  }
}

interface Props {
  items: ActivityItem[]
  running: boolean
  activeAgent: string | null
  involved: Set<string>
}

export function AgentRoster({ activeAgent, involved, running }: Omit<Props, 'items'>) {
  return (
    <ul className="roster" aria-label="Agent team">
      {AGENT_ORDER.map((a: AgentName) => {
        const look = AGENTS[a]
        const state = running && activeAgent === a ? 'active' : involved.has(a) ? 'involved' : 'idle'
        return (
          <li key={a} className={`roster-agent ${state}`} style={{ '--agent': look.color } as CSSProperties}>
            <AgentBadge name={a} size="lg" pulse={state === 'active'} />
            <span className="roster-name">{look.label}</span>
            <span className="roster-role">{state === 'active' ? 'working now…' : look.role}</span>
          </li>
        )
      })}
    </ul>
  )
}

export function ActivityFeed({ items, running }: Pick<Props, 'items' | 'running'>) {
  const box = useRef<HTMLDivElement>(null)
  const stick = useRef(true)

  useEffect(() => {
    const el = box.current
    if (el && stick.current) el.scrollTop = el.scrollHeight
  }, [items.length])

  return (
    <div
      className="feed"
      ref={box}
      onScroll={e => {
        const el = e.currentTarget
        stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80
      }}
      aria-live="polite"
      aria-busy={running}
    >
      {items.length === 0 ? (
        <div className="feed-empty">
          <p className="big">Quiet on the floor.</p>
          <p className="muted">Start the agents and their messages, tool calls and hand-offs will stream in here.</p>
        </div>
      ) : (
        <ol className="feed-list">
          {items.map((i, n) => <FeedItem key={`${i.index}-${n}`} item={i} />)}
          {running && (
            <li className="typing" aria-label="Agents are working">
              <span /><span /><span />
            </li>
          )}
        </ol>
      )}
    </div>
  )
}
