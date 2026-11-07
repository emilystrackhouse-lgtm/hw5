import type { CSSProperties } from 'react'
import { AGENT_ORDER, AgentBadge, agentLook } from '../agents'
import type { BoardPost, ContributionsResponse } from '../types'

const POST_LABEL: Record<BoardPost['kind'], string> = {
  customer_draft: 'Customer draft',
  landlord_draft: 'Landlord draft',
  vendor_draft: 'Vendor draft',
  internal_note: 'Internal note',
  resolution: 'Resolution',
}

export function Contributions({ data }: { data: ContributionsResponse | null }) {
  if (!data || data.status === 'not_run') {
    return <p className="muted empty-note">No run yet. Each agent's contribution will appear here after the team works this ticket.</p>
  }
  const agents = [...data.agents].sort(
    (a, b) => AGENT_ORDER.indexOf(a.agent as never) - AGENT_ORDER.indexOf(b.agent as never),
  )
  const outcome = data.outcome
  return (
    <div className="contrib">
      {outcome && (
        <div className="verdict">
          <div className="verdict-head">
            <AgentBadge name="boss" />
            <span><b>The Boss's call</b></span>
          </div>
          <p>{outcome.decision}</p>
          {outcome.human_next_steps.length > 0 && (
            <>
              <h4>For you</h4>
              <ul>{outcome.human_next_steps.map((s, i) => <li key={i}>{s}</li>)}</ul>
            </>
          )}
        </div>
      )}
      <div className="contrib-grid">
        {agents.map(a => {
          const look = agentLook(a.agent)
          const summary = a.summaries[a.summaries.length - 1] ?? 'Still working…'
          return (
            <article key={a.agent} className="contrib-card" style={{ '--agent': look?.color } as CSSProperties}>
              <header>
                <AgentBadge name={a.agent} />
                <div>
                  <h4>{look?.label ?? a.agent}</h4>
                  <span className="muted small">
                    {a.asked_by.length > 0 ? `asked by ${a.asked_by.map(x => agentLook(x)?.label ?? x).join(', ')}` : 'led the ticket'}
                  </span>
                </div>
              </header>
              <p className="contrib-summary">{a.agent === 'boss' && outcome ? 'Coordinated the team and made the final call (above).' : summary}</p>
              {a.tools.length > 0 && (
                <div className="chips">
                  {a.tools.map(t => <code key={t.tool} className="tool-name">{t.tool}{t.calls > 1 ? ` ×${t.calls}` : ''}</code>)}
                </div>
              )}
              <footer className="muted small">
                {a.asked.length > 0 && <span>handed off to {a.asked.map(x => agentLook(x)?.label ?? x).join(', ')} · </span>}
                {a.tokens.toLocaleString()} tokens
              </footer>
            </article>
          )
        })}
      </div>
    </div>
  )
}

export function BoardDrafts({ posts }: { posts: BoardPost[] }) {
  // Only messages meant for outside people; notes and resolutions are internal.
  const drafts = posts.filter(p => p.kind.endsWith('_draft'))
  if (drafts.length === 0) return <p className="muted empty-note">No drafts on the board yet.</p>
  return (
    <div className="drafts">
      {drafts.map(p => {
        const look = agentLook(p.author)
        return (
          <article key={p.id} className="draft" style={{ '--agent': look?.color ?? 'var(--muted)' } as CSSProperties}>
            <header>
              <span className="draft-kind">{POST_LABEL[p.kind]} #{p.id}</span>
              <span className="unsent">Not sent</span>
            </header>
            <p className="draft-to">
              {p.recipient && <>To <b>{p.recipient}</b></>}
              {p.subject && <> · {p.subject}</>}
            </p>
            <p className="draft-body">{p.body}</p>
            <footer className="muted small">Written by {look?.label ?? p.author}</footer>
          </article>
        )
      })}
    </div>
  )
}
