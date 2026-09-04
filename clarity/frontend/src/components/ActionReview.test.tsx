import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { getDecisionReadiness } from '../api'
import { ActionReview } from './ActionReview'
import type { ActionOption, DecisionReadiness, Insight } from '../types'

vi.mock('../api', () => ({ getDecisionReadiness: vi.fn() }))

const option: ActionOption = {
  id: 'option-1',
  label: 'Prepare a documented conversation',
  rationale: 'A controlled conversation is appropriate.',
  mechanics: ['Review the evidence.'],
  trade_offs: ['No portfolio change occurs automatically.'],
  suitability_checks: [],
  requires: ['RM approval'],
  estimated_impact: null,
  evidence: [],
}

const insight: Insight = {
  id: 'CL-0001-demo',
  client_id: 'CL-0001',
  category: 'opportunity',
  severity: 'low',
  headline: 'Demo finding',
  summary: 'Demo summary',
  priority_score: 1,
  priority_reasons: [],
  observed_facts: [],
  client_relevance: '',
  suggested_next_step: 'Prepare for a conversation.',
  evidence: [],
  assumptions: [],
  suitability_checks: [],
  confidence: 'measured',
  open_questions: [],
  related_event_ids: [],
  portfolio_ids: [],
  instrument_ids: [],
  amount_usd: null,
  status: 'rm_reviewed',
  selected_option_id: 'option-1',
  rm_note: 'Evidence reviewed and discussion purpose agreed.',
}

const blocked: DecisionReadiness = {
  can_mark_client_ready: false,
  evidence_version: 'demo-version',
  gates: [
    { id: 'evidence', label: 'Evidence', status: 'pass', detail: 'Source cited.', evidence: [] },
    { id: 'suitability', label: 'Suitability', status: 'block', detail: 'Mandate confirmation is unresolved.', evidence: [] },
    { id: 'tax_planning', label: 'Tax and planning', status: 'pass', detail: 'No tax control applies.', evidence: [] },
    { id: 'data_model', label: 'Data and model', status: 'pass', detail: 'No unresolved questions.', evidence: [] },
    { id: 'human_decision', label: 'Human decision', status: 'pass', detail: 'RM rationale recorded.', evidence: [] },
  ],
}

const passing: DecisionReadiness = {
  ...blocked,
  can_mark_client_ready: true,
  gates: blocked.gates.map((gate) => gate.id === 'suitability' ? { ...gate, status: 'pass', detail: 'All checks pass.' } : gate),
}

describe('ActionReview decision gates', () => {
  const onDecide = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => {
    vi.clearAllMocks()
  })

  afterEach(cleanup)

  it('shows blocking gates, disables client-ready, and offers controlled outcomes', async () => {
    vi.mocked(getDecisionReadiness).mockResolvedValue(blocked)
    render(<ActionReview insight={insight} options={[option]} busy={false} onDecide={onDecide} onClose={() => undefined} />)

    expect(await screen.findByText('Mandate confirmation is unresolved.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mark client-ready' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Escalate' })).toBeEnabled()
    expect(screen.getByText(/Resolve the blocking checks/)).toBeInTheDocument()
  })

  it('allows a reviewed, gate-cleared option to become client-ready', async () => {
    vi.mocked(getDecisionReadiness).mockResolvedValue(passing)
    render(<ActionReview insight={insight} options={[option]} busy={false} onDecide={onDecide} onClose={() => undefined} />)

    const user = userEvent.setup()
    const button = await screen.findByRole('button', { name: 'Mark client-ready' })
    await waitFor(() => expect(button).toBeEnabled())
    await user.selectOptions(screen.getByLabelText('Finding usefulness'), 'useful')
    await user.selectOptions(screen.getByLabelText('Urgency assessment'), 'right')
    await user.type(screen.getByLabelText('Calibration feedback rationale'), 'The finding is relevant for this client.')
    await user.click(button)
    expect(onDecide).toHaveBeenCalledWith(expect.objectContaining({ status: 'client_ready', selectedOptionId: 'option-1' }))
  })
})
