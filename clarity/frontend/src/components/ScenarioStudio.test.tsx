import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { evaluateScenario, getSavedScenarios, getScenarioTemplates, saveScenario } from '../api'
import { ScenarioStudio } from './ScenarioStudio'
import type { Dossier, ScenarioResult } from '../types'

vi.mock('../api', () => ({
  evaluateScenario: vi.fn(),
  getSavedScenarios: vi.fn(),
  getScenarioTemplates: vi.fn(),
  saveScenario: vi.fn(),
}))

const result: ScenarioResult = {
  template_id: 'lau-collateral-liquidity',
  client_id: 'CL-0014',
  insight_id: 'CL-0014-collateral-CF-0002',
  option_id: 'CL-0014-collateral-CF-0002-opt-deleverage',
  title: 'Collateral and redevelopment funding',
  as_of_date: '2026-08-26',
  inputs: { target_ltv_pct: 60, redevelopment_reserve_hkd: 15_000_000 },
  assumptions: [],
  metrics: [
    { key: 'ltv', label: 'Loan-to-value', baseline: 69.4, scenario: 60, unit: '%', available: true, detail: 'Current-state arithmetic.' },
    { key: 'market_impact', label: 'Market-price impact', baseline: null, scenario: null, unit: '', available: false, detail: 'Not modelled.' },
  ],
  evidence: [],
  blocked_checks: ['Credit review remains required.'],
  calculation_version: 'demo-version',
}

const dossier = {
  client: { client_id: 'CL-0014' },
  options: {
    'CL-0014-collateral-CF-0002': [{
      id: result.option_id,
      label: 'Reduce facility leverage',
      rationale: '', mechanics: [], trade_offs: [], suitability_checks: [], requires: [], estimated_impact: null, evidence: [],
    }],
  },
  insights: [{
    id: result.insight_id, client_id: 'CL-0014', category: 'collateral', severity: 'critical', headline: 'Facility', summary: '', priority_score: 90, priority_reasons: [], observed_facts: [], client_relevance: '', suggested_next_step: '', evidence: [], assumptions: [], suitability_checks: [], confidence: 'measured', open_questions: [], related_event_ids: [], portfolio_ids: [], instrument_ids: [], amount_usd: null, status: 'under_review',
  }],
} as unknown as Dossier

describe('ScenarioStudio', () => {
  const onAttach = vi.fn().mockResolvedValue(undefined)

  beforeEach(() => {
    vi.clearAllMocks()
    vi.mocked(getScenarioTemplates).mockResolvedValue({ templates: [{
      id: result.template_id, client_id: result.client_id, insight_id: result.insight_id,
      title: result.title, description: 'Compare source-backed outcomes.',
      inputs: [{ key: 'target_ltv_pct', label: 'Target loan-to-value', unit: '%', minimum: 10, maximum: 65, step: 0.5, default: 60, help_text: 'Bounded.' }],
    }] })
    vi.mocked(getSavedScenarios).mockResolvedValue({ scenarios: [] })
    vi.mocked(evaluateScenario).mockResolvedValue({ scenario: result })
  })

  afterEach(cleanup)

  it('compares metrics and makes unavailable data explicit', async () => {
    const user = userEvent.setup()
    render(<ScenarioStudio dossier={dossier} busy={false} onAttach={onAttach} />)
    await user.click(await screen.findByRole('button', { name: 'Compare with baseline' }))
    expect(await screen.findByText('Loan-to-value')).toBeInTheDocument()
    expect(screen.getByText('Not modelled.')).toBeInTheDocument()
    expect(screen.getByText('Credit review remains required.')).toBeInTheDocument()
  })

  it('saves and attaches a comparison to an in-progress RM review', async () => {
    const saved = { id: 'scn-demo', name: 'Lau comparison', saved_by: 'RM-SG-014', saved_at: '2026-08-26T10:00:00Z', result }
    vi.mocked(saveScenario).mockResolvedValue({ scenario: saved })
    const user = userEvent.setup()
    render(<ScenarioStudio dossier={dossier} busy={false} onAttach={onAttach} />)
    await user.click(await screen.findByRole('button', { name: 'Compare with baseline' }))
    await user.click(screen.getByRole('button', { name: 'Save comparison' }))
    const attach = await screen.findByRole('button', { name: 'Attach to RM review' })
    await waitFor(() => expect(attach).toBeEnabled())
    await user.click(attach)
    expect(onAttach).toHaveBeenCalledWith(expect.objectContaining({ id: result.insight_id }), saved)
  })
})
