import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPriorityPolicy, getPriorityPolicies, getPriorityPolicyEvaluation, priorityPolicyAction } from '../api'
import { CalibrationLab } from './CalibrationLab'
import type { PriorityPolicy } from '../types'

vi.mock('../api', () => ({
  createPriorityPolicy: vi.fn(), getPriorityPolicies: vi.fn(), getPriorityPolicyEvaluation: vi.fn(), priorityPolicyAction: vi.fn(),
}))

const active: PriorityPolicy = { id: 'baseline-v1', name: 'Published baseline', weights: { severity: .45, materiality: .30, urgency: .25 }, status: 'active', rationale: 'Published.', created_by: 'system', created_at: '2026-08-26', activation_history: [] }
const draft: PriorityPolicy = { ...active, id: 'candidate-1', name: 'Urgency-first', weights: { severity: .35, materiality: .20, urgency: .45 }, status: 'submitted' }
const evaluation = { policy_id: 'candidate-1', active_policy_id: 'baseline-v1', feedback_count: 0, anchor_coverage: [], activation_eligible: false, warnings: ['At least three final RM feedback records are required before activation.'], top_five_relevance_rate: null, urgency_alignment_rate: null, rank_changes: [{ client_id: 'CL-0014', headline: 'Funding plan', candidate_rank: 1, active_rank: 2, rank_delta: 1, candidate_score: 80, active_score: 75 }] }

describe('Calibration Lab', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getPriorityPolicies).mockResolvedValue({ active_policy: active, policies: [active, draft], templates: { baseline: { name: 'Published baseline', weights: active.weights }, urgency_first: { name: 'Urgency-first', weights: draft.weights } } })
    vi.mocked(getPriorityPolicyEvaluation).mockResolvedValue({ evaluation })
  })
  afterEach(cleanup)

  it('shows the active policy and lets the RM create a bounded candidate', async () => {
    vi.mocked(createPriorityPolicy).mockResolvedValue({ policy: draft, evaluation })
    const user = userEvent.setup()
    render(<CalibrationLab role="rm" onActivePolicyChanged={() => undefined} />)
    expect(await screen.findByText('Calibration Lab')).toBeInTheDocument()
    await user.type(screen.getByPlaceholderText('e.g. Review-period candidate'), 'Test candidate')
    await user.type(screen.getByPlaceholderText('Why should this policy be evaluated?'), 'Test the visible scoring policy.')
    await user.click(screen.getByRole('button', { name: 'Create draft candidate' }))
    await waitFor(() => expect(createPriorityPolicy).toHaveBeenCalled())
    expect(screen.getByText(/At least three final RM feedback/)).toBeInTheDocument()
  })

  it('keeps candidate approval unavailable until evaluation coverage passes', async () => {
    render(<CalibrationLab role="compliance_audit" onActivePolicyChanged={() => undefined} />)
    await screen.findByText('Calibration Lab')
    await userEvent.setup().click(screen.getAllByRole('button', { name: 'Compare' })[1])
    expect(await screen.findByRole('button', { name: 'Approve and activate' })).toBeDisabled()
    expect(priorityPolicyAction).not.toHaveBeenCalled()
  })
})
