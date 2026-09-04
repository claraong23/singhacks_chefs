import type { BookView, Dossier, InsightStatus } from './types'

const BASE = import.meta.env.VITE_API_BASE ?? ''

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...init,
  })
  if (!response.ok) {
    const body = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${body.slice(0, 200)}`)
  }
  return response.json() as Promise<T>
}

export const getBook = () => json<BookView>('/api/book')

export const getClient = (clientId: string) => json<Dossier>(`/api/clients/${clientId}`)

export interface DecisionInput {
  clientId: string
  status: InsightStatus
  rmNote?: string
  selectedOptionId?: string | null
  editedNextStep?: string | null
}

export const recordDecision = (insightId: string, input: DecisionInput) =>
  json<{ decision: Record<string, unknown> }>(`/api/insights/${insightId}/decision`, {
    method: 'POST',
    body: JSON.stringify({
      client_id: input.clientId,
      status: input.status,
      rm_note: input.rmNote ?? '',
      selected_option_id: input.selectedOptionId ?? null,
      edited_next_step: input.editedNextStep ?? null,
    }),
  })

export const resetDecisions = () =>
  json<{ status: string }>('/api/reset', { method: 'POST', body: '{}' })
