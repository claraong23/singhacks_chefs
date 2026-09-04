import type {
  BookView,
  DecisionReadiness,
  Dossier,
  SavedScenario,
  ScenarioResult,
  ScenarioTemplate,
  InsightStatus,
  CommunicationChannel,
  CommunicationPreflight,
  MeetingPackage,
  HoldingChange,
  HoldingExplanation,
  ClientAttributionDraft,
  ClientNote,
  ProposedObjective,
  AuditTimelineEvent,
  FollowThroughView,
  SimulatedRole,
  WorkStatus,
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

export const getMeetingPackages = (clientId: string) =>
  json<{ packages: MeetingPackage[] }>(`/api/clients/${clientId}/meeting-packages`)

export const createMeetingPackage = (insightId: string, clientId: string) =>
  json<{ package: MeetingPackage }>(`/api/insights/${insightId}/meeting-packages`, {
    method: 'POST', body: JSON.stringify({ client_id: clientId }),
  })

export const saveMeetingSection = (
  packageId: string, key: string, content: string, evidenceRefs: string[], reason = 'RM edit',
) => json<{ package: MeetingPackage }>(`/api/meeting-packages/${packageId}/versions`, {
  method: 'POST', body: JSON.stringify({ key, content, evidence_refs: evidenceRefs, reason }),
})

export const regenerateMeetingSection = (packageId: string, key: string) =>
  json<{ package: MeetingPackage }>(`/api/meeting-packages/${packageId}/regenerate`, {
    method: 'POST', body: JSON.stringify({ key }),
  })

export const restoreMeetingVersion = (packageId: string, version: number) =>
  json<{ package: MeetingPackage }>(`/api/meeting-packages/${packageId}/restore`, {
    method: 'POST', body: JSON.stringify({ version }),
  })

export const preflightMeetingPackage = (packageId: string) =>
  json<{ preflight: CommunicationPreflight }>(`/api/meeting-packages/${packageId}/preflight`, {
    method: 'POST', body: '{}',
  })

export const handoffMeetingPackage = (packageId: string, channel: CommunicationChannel) =>
  json<{ package: MeetingPackage }>(`/api/meeting-packages/${packageId}/handoff`, {
    method: 'POST', body: JSON.stringify({ channel }),
  })

export const getFollowThrough = (role: SimulatedRole, clientId?: string) =>
  json<FollowThroughView>(`/api/follow-through?role=${role}${clientId ? `&client_id=${clientId}` : ''}`)

export const getAudit = (filters: Record<string, string> = {}) =>
  json<{ audit: AuditTimelineEvent[] }>(`/api/audit?${new URLSearchParams(filters).toString()}`)

export const createFollowTask = (input: Record<string, unknown>) =>
  json<{ task: Record<string, unknown> }>('/api/follow-through/tasks', { method: 'POST', body: JSON.stringify(input) })

export const createReferral = (input: Record<string, unknown>) =>
  json<{ referral: Record<string, unknown> }>('/api/follow-through/referrals', { method: 'POST', body: JSON.stringify(input) })

export const createOutcome = (input: Record<string, unknown>) =>
  json<{ outcome: Record<string, unknown> }>('/api/follow-through/outcomes', { method: 'POST', body: JSON.stringify(input) })

export const createEvidenceUpdate = (input: Record<string, unknown>) =>
  json<{ evidence_update: Record<string, unknown>; reevaluation: Record<string, unknown> }>('/api/follow-through/evidence-updates', { method: 'POST', body: JSON.stringify(input) })

export const updateFollowRecord = (collection: 'tasks' | 'referrals' | 'reevaluations', id: string, role: SimulatedRole, status: WorkStatus | 'queued' | 'acknowledged' | 'complete', reason = '') =>
  json<Record<string, unknown>>(`/api/follow-through/${collection}/${id}/update`, { method: 'POST', body: JSON.stringify({ role, status, reason }) })

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

export const resetDecision = (insightId: string) =>
  json<{ status: string; insight_id: string }>(`/api/insights/${insightId}/reset`, {
    method: 'POST',
    body: JSON.stringify({}),
  })

export const getHoldingChanges = (
  clientId: string,
  params?: { from?: string; to?: string; portfolio?: string },
) => {
  const query = new URLSearchParams()
  if (params?.from) query.set('from', params.from)
  if (params?.to) query.set('to', params.to)
  if (params?.portfolio && params.portfolio !== 'all') query.set('portfolio', params.portfolio)
  const qs = query.toString()
  return json<{ changes: HoldingChange[]; period: { start: string; end: string }; portfolio_id: string | null }>(
    `/api/clients/${clientId}/changes${qs ? `?${qs}` : ''}`,
  )
}

export const explainHolding = (payload: {
  clientId: string
  instrumentId: string
  from?: string
  to?: string
  portfolioId?: string
}) =>
  json<{ explanation: HoldingExplanation }>('/api/explain-holding', {
    method: 'POST',
    body: JSON.stringify({
      client_id: payload.clientId,
      instrument_id: payload.instrumentId,
      from: payload.from,
      to: payload.to,
      portfolio_id: payload.portfolioId,
    }),
  })

export const getClientAttribution = (payload: {
  clientId: string
  instrumentId: string
  from?: string
  to?: string
  portfolioId?: string
}) =>
  json<{ draft: ClientAttributionDraft }>('/api/client-attribution', {
    method: 'POST',
    body: JSON.stringify({
      client_id: payload.clientId,
      instrument_id: payload.instrumentId,
      from: payload.from,
      to: payload.to,
      portfolio_id: payload.portfolioId,
    }),
  })

export const addClientNote = (
  clientId: string,
  note: string,
  channel = 'Client Meeting',
  rmName = 'Priscilla Ong',
) =>
  json<{ note: ClientNote }>(`/api/clients/${clientId}/notes`, {
    method: 'POST',
    body: JSON.stringify({ note, channel, rm_name: rmName }),
  })

export const proposeObjectiveUpdate = (
  clientId: string,
  proposedObjectives: string,
  rationale: string,
  rmName = 'Priscilla Ong',
) =>
  json<{ proposal: ProposedObjective }>(`/api/clients/${clientId}/propose-objective`, {
    method: 'POST',
    body: JSON.stringify({
      proposed_objectives: proposedObjectives,
      rationale,
      rm_name: rmName,
    }),
  })

export const addDraftToMeetingBrief = (clientId: string, draft: ClientAttributionDraft) =>
  json<{ brief: Record<string, unknown> }>('/api/meeting-brief/add-draft', {
    method: 'POST',
    body: JSON.stringify({ client_id: clientId, draft }),
  })

