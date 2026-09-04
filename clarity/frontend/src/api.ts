import type {
  BookView,
  DecisionReadiness,
  Dossier,
  SavedScenario,
  ScenarioResult,
  ScenarioTemplate,
  InsightStatus,
} from './types'

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
  selectedScenarioId?: string | null
}

export interface ReadinessInput {
  clientId: string
  selectedOptionId: string | null
  rmNote: string
  editedNextStep?: string | null
}

export const getDecisionReadiness = (insightId: string, input: ReadinessInput) =>
  json<DecisionReadiness>(`/api/insights/${insightId}/readiness`, {
    method: 'POST',
    body: JSON.stringify({
      client_id: input.clientId,
      selected_option_id: input.selectedOptionId,
      rm_note: input.rmNote,
      edited_next_step: input.editedNextStep ?? null,
    }),
  })

export const getScenarioTemplates = (clientId: string) =>
  json<{ templates: ScenarioTemplate[] }>(`/api/clients/${clientId}/scenario-templates`)

export const getSavedScenarios = (clientId: string) =>
  json<{ scenarios: SavedScenario[] }>(`/api/clients/${clientId}/scenarios`)

export interface ScenarioInputPayload {
  templateId: string
  insightId: string
  optionId: string
  inputs: Record<string, number>
}

const scenarioBody = (input: ScenarioInputPayload) => ({
  template_id: input.templateId,
  insight_id: input.insightId,
  option_id: input.optionId,
  inputs: input.inputs,
})

export const evaluateScenario = (clientId: string, input: ScenarioInputPayload) =>
  json<{ scenario: ScenarioResult }>(`/api/clients/${clientId}/scenarios/evaluate`, {
    method: 'POST',
    body: JSON.stringify(scenarioBody(input)),
  })

export const saveScenario = (clientId: string, name: string, input: ScenarioInputPayload) =>
  json<{ scenario: SavedScenario }>(`/api/clients/${clientId}/scenarios`, {
    method: 'POST',
    body: JSON.stringify({ name, ...scenarioBody(input) }),
  })

export const recordDecision = (insightId: string, input: DecisionInput) =>
  json<{ decision: Record<string, unknown> }>(`/api/insights/${insightId}/decision`, {
    method: 'POST',
    body: JSON.stringify({
      client_id: input.clientId,
      status: input.status,
      rm_note: input.rmNote ?? '',
      selected_option_id: input.selectedOptionId ?? null,
      selected_scenario_id: input.selectedScenarioId ?? null,
      edited_next_step: input.editedNextStep ?? null,
    }),
  })

export const resetDecisions = () =>
  json<{ status: string }>('/api/reset', { method: 'POST', body: '{}' })
