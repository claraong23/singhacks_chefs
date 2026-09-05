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
  PriorityPolicy,
  PriorityPolicyEvaluation,
  RMFeedbackInput,
  KnowledgeDocument,
  KnowledgeSearchResult,
  AIDraftCandidate,
  AIDraftingProviderStatus,
  AIDraftStyle,
  InsightNarrativeDraft,
  EventImpactView,
  EventSummary,
  IntegrationCapabilities,
  IntegrationView,
  InboundIntegrationEvent,
  OutboundWorkOrder,
  HealthStatus,
  PortfolioAttribution,
} from './types'

const BASE = import.meta.env.VITE_API_BASE ?? ''
const WRITE_TOKEN_KEY = 'clarity_write_token'

export const hasWriteToken = () => Boolean(sessionStorage.getItem(WRITE_TOKEN_KEY))
export const setWriteToken = (token: string) => {
  if (token.trim()) sessionStorage.setItem(WRITE_TOKEN_KEY, token.trim())
  else sessionStorage.removeItem(WRITE_TOKEN_KEY)
  window.dispatchEvent(new Event('clarity-write-access'))
}
export const clearWriteToken = () => setWriteToken('')

async function json<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers)
  headers.set('Content-Type', 'application/json')
  if ((init?.method ?? 'GET').toUpperCase() !== 'GET') {
    const token = sessionStorage.getItem(WRITE_TOKEN_KEY)
    if (token) headers.set('Authorization', `Bearer ${token}`)
  }
  const response = await fetch(`${BASE}${path}`, {
    ...init,
    headers,
  })
  if (!response.ok) {
    if (response.status === 401) clearWriteToken()
    const body = await response.text()
    throw new Error(`${response.status} ${response.statusText}: ${body.slice(0, 200)}`)
  }
  return response.json() as Promise<T>
}

export const getBook = () => json<BookView>('/api/book')
export const getHealth = () => json<HealthStatus>('/api/health')

export const getKnowledgeDocuments = (role: SimulatedRole) =>
  json<{ documents: KnowledgeDocument[] }>(`/api/knowledge-documents?role=${role}`)

export const getKnowledgeDocument = (id: string, role: SimulatedRole) =>
  json<{ document: KnowledgeDocument }>(`/api/knowledge-documents/${id}?role=${role}`)

export const searchKnowledge = (input: { query?: string; category?: string; tag?: string; role: SimulatedRole; location: string }) => {
  const query = new URLSearchParams({ role: input.role, location: input.location })
  if (input.query) query.set('q', input.query)
  if (input.category) query.set('category', input.category)
  if (input.tag) query.set('tag', input.tag)
  return json<{ results: KnowledgeSearchResult[] }>(`/api/knowledge/search?${query.toString()}`)
}

export const createKnowledgeDocument = (input: Record<string, unknown>) =>
  json<{ document: KnowledgeDocument }>('/api/knowledge-documents', { method: 'POST', body: JSON.stringify(input) })

export const knowledgeDocumentAction = (id: string, action: 'revise' | 'submit' | 'approve' | 'reject', input: Record<string, unknown>) =>
  json<{ document: KnowledgeDocument }>(`/api/knowledge-documents/${id}/${action}`, { method: 'POST', body: JSON.stringify(input) })

export const getPriorityPolicies = () =>
  json<{ active_policy: PriorityPolicy; policies: PriorityPolicy[]; templates: Record<string, { name: string; weights: PriorityPolicy['weights'] }> }>('/api/priority-policies')

export const getPriorityPolicyEvaluation = (policyId: string) =>
  json<{ evaluation: PriorityPolicyEvaluation }>(`/api/priority-policies/${policyId}/evaluation`)

export const createPriorityPolicy = (input: Record<string, unknown>) =>
  json<{ policy: PriorityPolicy; evaluation: PriorityPolicyEvaluation }>('/api/priority-policies', { method: 'POST', body: JSON.stringify(input) })

export const priorityPolicyAction = (policyId: string, action: 'revise' | 'submit' | 'approve' | 'reject', input: Record<string, unknown>) =>
  json<{ policy: PriorityPolicy; evaluation?: PriorityPolicyEvaluation }>(`/api/priority-policies/${policyId}/${action}`, { method: 'POST', body: JSON.stringify(input) })

export const getClient = (clientId: string) => json<Dossier>(`/api/clients/${clientId}`)

export const getEvents = () => json<{ events: EventSummary[] }>('/api/events')

export const getEventImpact = (eventId: string) =>
  json<EventImpactView>(`/api/events/${eventId}/impact`)

export interface DecisionInput {
  clientId: string
  status: InsightStatus
  rmNote?: string
  selectedOptionId?: string | null
  editedNextStep?: string | null
  selectedScenarioId?: string | null
  role?: SimulatedRole
  feedback?: RMFeedbackInput
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

export const getAIDraftingStatus = () =>
  json<AIDraftingProviderStatus>('/api/ai-drafting/status')

export const generateAIMeetingDraft = (packageId: string, targetKey: string, style: AIDraftStyle, role: SimulatedRole) =>
  json<{ draft: AIDraftCandidate }>(`/api/meeting-packages/${packageId}/ai-drafts`, {
    method: 'POST', body: JSON.stringify({ target_key: targetKey, style, role }),
  })

export const applyAIMeetingDraft = (packageId: string, draftId: string, rationale: string, role: SimulatedRole) =>
  json<{ package: MeetingPackage }>(`/api/meeting-packages/${packageId}/ai-drafts/${draftId}/apply`, {
    method: 'POST', body: JSON.stringify({ rationale, role }),
  })

export const getFollowThrough = (role: SimulatedRole, clientId?: string) =>
  json<FollowThroughView>(`/api/follow-through?role=${role}${clientId ? `&client_id=${clientId}` : ''}`)

export const getIntegrationCapabilities = () => json<IntegrationCapabilities>('/api/integrations/capabilities')
export const getIntegrations = (role: SimulatedRole, clientId?: string) =>
  json<IntegrationView>(`/api/integrations?role=${role}${clientId ? `&client_id=${clientId}` : ''}`)
export const receiveInboundIntegration = (input: Record<string, unknown>) =>
  json<{ event: InboundIntegrationEvent; replayed: boolean }>('/api/integrations/inbound', { method: 'POST', body: JSON.stringify(input) })
export const dispositionInboundIntegration = (id: string, action: 'accept' | 'reject', role: SimulatedRole, rationale: string) =>
  json<{ event: InboundIntegrationEvent; replayed?: boolean }>(`/api/integrations/inbound/${id}/${action}`, { method: 'POST', body: JSON.stringify({ role, rationale }) })
export const prepareWorkOrder = (input: Record<string, unknown>) =>
  json<{ work_order: OutboundWorkOrder; replayed: boolean }>('/api/integrations/work-orders', { method: 'POST', body: JSON.stringify(input) })
export const dispatchWorkOrder = (id: string, role: SimulatedRole) =>
  json<{ work_order: OutboundWorkOrder; replayed: boolean }>(`/api/integrations/work-orders/${id}/dispatch`, { method: 'POST', body: JSON.stringify({ role }) })
export const acknowledgeWorkOrder = (id: string, role: SimulatedRole) =>
  json<{ work_order: OutboundWorkOrder }>(`/api/integrations/work-orders/${id}/acknowledge`, { method: 'POST', body: JSON.stringify({ role }) })

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
      role: input.role ?? 'rm',
      feedback: input.feedback ? {
        usefulness: input.feedback.usefulness,
        urgency_assessment: input.feedback.urgencyAssessment,
        rationale: input.feedback.rationale,
      } : undefined,
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
  return json<{
    changes: HoldingChange[]
    period: { start: string; end: string }
    portfolio_id: string | null
    attribution?: PortfolioAttribution
  }>(`/api/clients/${clientId}/changes${qs ? `?${qs}` : ''}`)
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
  json<{ brief: Record<string, unknown>; draft: ClientAttributionDraft }>('/api/meeting-brief/add-draft', {
    method: 'POST',
    body: JSON.stringify({ client_id: clientId, draft }),
  })

export const getMeetingDrafts = (clientId: string) =>
  json<{ drafts: ClientAttributionDraft[] }>(`/api/clients/${clientId}/meeting-drafts`)

export const updateMeetingDraft = (
  clientId: string,
  draftId: string,
  draft: Partial<ClientAttributionDraft>,
) =>
  json<{ draft: ClientAttributionDraft }>(
    `/api/clients/${clientId}/meeting-drafts/${draftId}/update`,
    {
      method: 'POST',
      body: JSON.stringify({ draft }),
    },
  )

export const deleteMeetingDraft = (clientId: string, draftId: string) =>
  json<{ ok: boolean }>(`/api/clients/${clientId}/meeting-drafts/${draftId}/delete`, {
    method: 'POST',
    body: JSON.stringify({}),
  })

export const draftNarrative = (insightId: string, role: SimulatedRole) =>
  json<InsightNarrativeDraft>(`/api/insights/${insightId}/narrative`, {
    method: 'POST',
    body: JSON.stringify({ role }),
  })

