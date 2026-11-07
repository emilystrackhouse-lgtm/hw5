// Thin client for the FastAPI backend. Base URL: http://localhost:8000 (VITE_API_BASE).
import type {
  ActivityResponse, ApprovalRequest, CashResponse, ContributionsResponse,
  DecisionResult, RunState, TicketDetail, TicketsResponse,
} from './types'

export const API_BASE: string = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

export class ApiError extends Error {
  status: number
  constructor(status: number, message: string) {
    super(message)
    this.status = status
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let res: Response
  try {
    res = await fetch(API_BASE + path, {
      ...init,
      headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    })
  } catch {
    throw new ApiError(0, `Can't reach the backend at ${API_BASE}. Is uvicorn running?`)
  }
  if (!res.ok) {
    let message = res.statusText
    try {
      const body = await res.json()
      message = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail)
    } catch { /* keep statusText */ }
    throw new ApiError(res.status, message)
  }
  return res.json() as Promise<T>
}

const post = <T,>(path: string, body?: unknown) =>
  request<T>(path, { method: 'POST', body: body === undefined ? undefined : JSON.stringify(body) })

export const api = {
  tickets: () => request<TicketsResponse>('/api/tickets'),
  ticket: (id: number) => request<TicketDetail>(`/api/tickets/${id}`),
  contributions: (id: number) => request<ContributionsResponse>(`/api/tickets/${id}/contributions`),
  startRun: (id: number) => post<RunState>(`/api/tickets/${id}/run`),
  run: (runId: string) => request<RunState>(`/api/runs/${runId}`),
  runs: () => request<RunState[]>('/api/runs'),
  activity: (ticketId: number, since: number) =>
    request<ActivityResponse>(`/api/activity?ticket_id=${ticketId}&since=${since}&limit=500`),
  approvals: (status: 'pending' | 'all' = 'pending') =>
    request<{ requests: ApprovalRequest[] }>(`/api/approvals?status=${status}`),
  approve: (id: number, decidedBy: string) =>
    post<DecisionResult>(`/api/approvals/${id}/approve`, { decided_by: decidedBy }),
  reject: (id: number, decidedBy: string) =>
    post<DecisionResult>(`/api/approvals/${id}/reject`, { decided_by: decidedBy }),
  cash: () => request<CashResponse>('/api/cash'),
  reset: () => post<{ ok: boolean; message: string }>('/api/reset'),
}
