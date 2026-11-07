// How each agent looks on the dashboard: one color, one monogram, one icon.
import type { CSSProperties } from 'react'
import type { AgentName } from './types'

export interface AgentLook {
  name: AgentName
  label: string
  short: string
  role: string
  color: string
}

export const AGENTS: Record<AgentName, AgentLook> = {
  boss: { name: 'boss', label: 'Boss', short: 'B', role: 'Routes work, makes the call', color: 'var(--a-boss)' },
  inventory: { name: 'inventory', label: 'Inventory', short: 'In', role: 'Stock, shortfalls, vendors', color: 'var(--a-inventory)' },
  accounting: { name: 'accounting', label: 'Accounting', short: 'Ac', role: 'Cash, margins, approvals', color: 'var(--a-accounting)' },
  facilities: { name: 'facilities', label: 'Facilities', short: 'Fa', role: 'Lease, rent, landlord', color: 'var(--a-facilities)' },
  customer_service: { name: 'customer_service', label: 'Customer Service', short: 'CS', role: 'Drafts replies', color: 'var(--a-cs)' },
}

export const AGENT_ORDER: AgentName[] = ['boss', 'inventory', 'accounting', 'facilities', 'customer_service']

export function agentLook(name: string): AgentLook | null {
  return (AGENTS as Record<string, AgentLook>)[name] ?? null
}

/** Small line icon per agent, so color is never the only cue. */
export function AgentIcon({ name, size = 16 }: { name: string; size?: number }) {
  const common = { width: size, height: size, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor',
    strokeWidth: 2, strokeLinecap: 'round' as const, strokeLinejoin: 'round' as const, 'aria-hidden': true }
  switch (name) {
    case 'boss': // crown
      return <svg {...common}><path d="M3 8l4.5 4L12 5l4.5 7L21 8l-2 11H5L3 8z" /></svg>
    case 'inventory': // box
      return <svg {...common}><path d="M3 7l9-4 9 4-9 4-9-4z" /><path d="M3 7v10l9 4 9-4V7" /><path d="M12 11v10" /></svg>
    case 'accounting': // coins
      return <svg {...common}><ellipse cx="9" cy="7" rx="6" ry="3" /><path d="M3 7v5c0 1.7 2.7 3 6 3s6-1.3 6-3V7" /><path d="M15 11.5c3.3 0 6 1.3 6 3v3c0 1.7-2.7 3-6 3-2 0-3.8-.5-4.9-1.3" /></svg>
    case 'facilities': // storefront
      return <svg {...common}><path d="M3 10l2-6h14l2 6" /><path d="M4 10v10h16V10" /><path d="M3 10h18" /><path d="M10 20v-6h4v6" /></svg>
    case 'customer_service': // speech bubble
      return <svg {...common}><path d="M21 12a8 8 0 0 1-11.6 7.1L4 20l1-4.6A8 8 0 1 1 21 12z" /><path d="M8.5 12h.01M12 12h.01M15.5 12h.01" /></svg>
    default: // person
      return <svg {...common}><circle cx="12" cy="8" r="4" /><path d="M4 21a8 8 0 0 1 16 0" /></svg>
  }
}

export function AgentBadge({ name, size = 'md', pulse = false }: { name: string; size?: 'sm' | 'md' | 'lg'; pulse?: boolean }) {
  const look = agentLook(name)
  const isHuman = name.startsWith('human')
  return (
    <span
      className={`avatar avatar-${size}${pulse ? ' avatar-pulse' : ''}${isHuman ? ' avatar-human' : ''}`}
      style={look ? ({ '--agent': look.color } as CSSProperties) : undefined}
      title={look?.label ?? (isHuman ? 'Human' : name)}
    >
      <AgentIcon name={look ? name : 'human'} size={size === 'sm' ? 12 : size === 'lg' ? 22 : 16} />
    </span>
  )
}
