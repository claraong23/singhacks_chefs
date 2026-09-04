import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ClientHeader } from './ClientHeader'
import { MeaningfulChangesTable } from './MeaningfulChangesTable'
import { ExplanationDrawer } from './ExplanationDrawer'
import { ClientAttributionModal } from './ClientAttributionModal'
import type {
  ClientAttributionDraft,
  Dossier,
  HoldingChange,
  HoldingExplanation,
} from '../types'

vi.mock('../api', () => ({
  addClientNote: vi.fn().mockResolvedValue({
    note: {
      note_id: 'N-101',
      note_date: '2026-08-26',
      channel: 'Client Meeting',
      rm_name: 'Priscilla Ong',
      note: 'Discussed German inheritance tax planning.',
    },
  }),
  proposeObjectiveUpdate: vi.fn().mockResolvedValue({
    proposal: {
      proposal_id: 'PROP-01',
      client_id: 'CL-0003',
      proposed_at: '2026-08-26',
      rm_id: 'RM-014',
      rm_name: 'Priscilla Ong',
      current_objectives: 'Conservative growth',
      proposed_objectives: 'Capital preservation and EUR 3.4m tax reserve',
      rationale: 'Confirmed inheritance tax due',
      status: 'pending_governance_review',
    },
  }),
  addDraftToMeetingBrief: vi.fn().mockResolvedValue({
    brief: { client_id: 'CL-0003', status: 'updated' },
  }),
}))

const mockDossier: Dossier = {
  as_of: '2026-08-26',
  client: {
    client_id: 'CL-0003',
    client_name: 'Margarethe Voss-Brenner',
    client_since: '2019-04-12',
    age: 71,
    gender: 'Female',
    nationality: 'German',
    country_of_residence: 'Germany',
    tax_domicile: 'Germany',
    booking_centre: 'Singapore',
    rm_id: 'RM-014',
    rm_name: 'Priscilla Ong',
    rm_desk: 'Asia Desk',
    base_currency: 'EUR',
    wealth_band: 'UHNW',
    life_stage: 'Inheritance / Estate Transition',
    source_of_wealth: 'Family Inheritance',
    risk_profile: 'Conservative',
    risk_tolerance_score: 3,
    investment_horizon_years: 5,
    liquidity_needs: 'High (EUR 3.4m tax)',
    kyc_review_due: '2026-09-15',
    objectives: 'Preserve inherited wealth and meet confirmed tax obligations.',
    reporting_language: 'German',
  },
  portfolios: [
    {
      portfolio_id: 'PF-0005',
      portfolio_name: 'Voss-Brenner Discretionary Classic',
      mandate_code: 'M-CON-01',
      mandate_name: 'Conservative Growth',
      service_model: 'Discretionary',
      base_currency: 'EUR',
      benchmark: 'Global Aggregate Bond + 20% MSCI World',
      inception_date: '2019-05-01',
      value_usd: 43513200,
      aum_series: [{ snapshot: '2026-08-26', label: 'Latest', value_base: 40290000 }],
      mandate_review: {
        governed: true,
        allocation_pct: { Equity: 34.2, 'Fixed Income': 52.8, Cash: 13.0 },
        band_breaches: [
          {
            portfolio_id: 'PF-0005',
            mandate_code: 'M-CON-01',
            asset_class: 'Equity',
            actual_pct: 34.2,
            min_pct: 10.0,
            target_pct: 20.0,
            max_pct: 25.0,
            direction: 'overweight',
            breach_pp: 9.2,
            value_base: 13779180,
            base_currency: 'EUR',
          },
        ],
        position_breaches: [],
        exclusion_breaches: [],
      },
      bands: { Equity: { min_pct: 10, target_pct: 20, max_pct: 25 } },
      mandate_notes: null,
    },
  ],
  wealth: {
    total_usd: 43513200,
    timeseries: [{ snapshot: '2026-08-26', label: 'Latest', total_usd: 43513200, change_usd: null, change_pct: null }],
    by_asset_class: { Equity: 14881514, 'Fixed Income': 22974969, Cash: 5656716 },
    by_liquidity_tier: { T0: 5656716, T1: 37856484 },
    by_currency: { EUR: 40290000 },
    by_region: { Europe: 43513200 },
    by_sector: { Energy: 4200000 },
    positions: [],
  },
  income: {
    annualised_gross_usd: 1250000,
    annualised_net_usd: 980000,
    yield_pct: 2.87,
    quarters_observed: 4,
  },
  explanation: {
    ytd: {
      client_id: 'CL-0003',
      period: '2025-12-31 to 2026-08-26',
      primary_driver: 'Renewable and equity repricing',
      fx_dominates: false,
      start: '2025-12-31',
      end: '2026-08-26',
      start_label: '31 Dec 2025',
      end_label: '26 Aug 2026',
      change_usd: -1250000,
      change_pct: -2.8,
      price_effect_usd: -1100000,
      fx_effect_usd: -150000,
      flow_effect_usd: 0,
      drivers: [],
      detractors: [],
      contributors: [],
      narrative: ['Portfolio experienced detraction from renewable energy holdings.'],
      provenance: 'deterministic',
    },
    recent: {
      client_id: 'CL-0003',
      period: '2026-06-30 to 2026-08-26',
      primary_driver: 'Stability',
      fx_dominates: false,
      start: '2026-06-30',
      end: '2026-08-26',
      start_label: '30 Jun 2026',
      end_label: '26 Aug 2026',
      change_usd: 50000,
      change_pct: 0.1,
      price_effect_usd: 50000,
      fx_effect_usd: 0,
      flow_effect_usd: 0,
      drivers: [],
      detractors: [],
      contributors: [],
      narrative: ['Recent quarter demonstrated relative stabilization.'],
      provenance: 'deterministic',
    },
  },
  exposures: { issuers: [], themes: [], unresolved: [] },
  liquidity: {
    client_id: 'CL-0003',
    snapshot: '2026-08-26',
    horizon_months: 12,
    horizon_end: '2027-08-26',
    total_usd: 43513200,
    by_tier: {},
    readily_realisable_usd: 5656716,
    encumbered_cap_usd: null,
    withdrawable_usd: 5656716,
    gated_usd: 0,
    illiquid_usd: 0,
    obligations: [],
    obligations_confirmed_usd: 3700000,
    obligations_total_usd: 3700000,
    coverage_ratio: 1.52,
    shortfall_usd: 0,
    gated_positions: [],
    notes: [],
  },
  facilities: [],
  insights: [],
  options: {},
  brief: {
    client_id: 'CL-0003',
    generated_at: '2026-08-26',
    as_of: '2026-08-26',
    purpose: 'Review estate inheritance and mandate alignment',
    talking_points: [],
    questions_to_ask: [],
    relationship_context: [],
    contradictions: [],
    do_not_say: [],
    draft_follow_up: '',
    provenance: 'deterministic',
  },
  notes: [],
  events: [],
  market: { series: [] },
  audit: [],
}

const mockChange: HoldingChange = {
  instrument_id: 'IN-0012',
  instrument_name: 'Nordvind Energy ASA',
  asset_class: 'Equity',
  sector: 'Renewable Energy',
  region: 'Europe',
  currency: 'EUR',
  portfolio_ids: ['PF-0005'],
  start_quantity: 45000,
  end_quantity: 45000,
  quantity_change: 0,
  start_price: 92.5,
  end_price: 76.2,
  price_return_pct: -17.62,
  start_value_usd: 4515000,
  end_value_usd: 3720000,
  value_change_usd: -795000,
  start_weight_pct: 10.1,
  end_weight_pct: 8.55,
  weight_change_pct: -1.55,
  trigger_badges: ['⚡ Dollar Move (-$795,000)', '📉 Price Shock (-17.6%)', '⚠️ Mandate Breach (Equity Overweight)'],
  is_meaningful: true,
  valuation_lag: false,
  liquidity_tier: 'T0 (Daily)',
}

const mockExplanation: HoldingExplanation = {
  client_id: 'CL-0003',
  instrument_id: 'IN-0012',
  instrument_name: 'Nordvind Energy ASA',
  asset_class: 'Equity',
  sector: 'Renewable Energy',
  region: 'Europe',
  start: '2025-12-31',
  end: '2026-08-26',
  portfolio_id: 'PF-0005',
  what_changed: {
    start_value_usd: 4515000,
    end_value_usd: 3720000,
    value_change_usd: -795000,
    start_quantity: 45000,
    end_quantity: 45000,
    quantity_change: 0,
    start_price: 92.5,
    end_price: 76.2,
    price_return_pct: -17.62,
    start_weight_pct: 10.1,
    end_weight_pct: 8.55,
    weight_change_pct: -1.55,
    currency: 'EUR',
    valuation_lag: false,
  },
  event_evidence: [
    {
      event_id: 'EV-0004',
      event_date: '2026-02-14',
      event_type: 'Regulatory / Geopolitical',
      region: 'Europe',
      description: 'EU grid integration bottlenecks and supply chain tariffs on wind turbines.',
      primary_transmission: 'Reduced forward margin guidance for offshore operators',
      severity: 'high',
      correlation_score: 0.95,
      rationale: 'Direct sector and regional alignment with European renewable operators.',
    },
  ],
  transmission_mechanisms: [
    'Tariff pressure and grid delay announcements reduced institutional earnings expectations.',
    'Nordvind repriced downwards by -17.6% without any active portfolio selling.',
  ],
  why_it_matters: [
    'Client has a conservative risk profile (tolerance score 3/10) which clashes with single-stock equity volatility.',
    'Confirmed EUR 3.4m inheritance tax liability is due in 2026.',
  ],
  uncertainties: [
    'FX translation: Euro strength against USD cushioned base-currency loss slightly.',
  ],
  source_evidence: [],
}

const mockDraft: ClientAttributionDraft = {
  client_id: 'CL-0003',
  instrument_id: 'IN-0012',
  instrument_name: 'Nordvind Energy ASA',
  headline: 'Recent repricing in European renewable energy and Nordvind Energy',
  what_happened_bullet:
    'Nordvind Energy experienced an industry-wide repricing of approximately 17.6% due to European grid delays and supply-chain pressures.',
  why_it_matters_bullet:
    'Because your primary objective is conservative capital preservation alongside preparing your confirmed EUR 3.4m tax payment, this holding represents heightened equity exposure.',
  next_steps_bullet:
    'We recommend discussing a structured de-risking rebalance to ring-fence your upcoming tax reserve while maintaining defensive income generation.',
  confidence: 'Derived (Grounded in 1 event, 1 mandate check)',
  source_chips: ['event_log.csv:EV-0004', 'holdings.csv', 'mandates.csv'],
  limitations: [],
  language_disclaimer:
    'English RM preview — Client preferred reporting language is German. Please review and communicate in German.',
  created_at: '2026-08-26T10:00:00Z',
}

describe('Client Explanation Module Components', () => {
  afterEach(() => {
    cleanup()
  })

  it('ClientHeader renders hero info, dual currency AUM, and dynamic alert chips', async () => {
    const user = userEvent.setup()
    const onBack = vi.fn()

    render(<ClientHeader dossier={mockDossier} onBack={onBack} />)

    expect(screen.getByRole('heading', { name: 'Margarethe Voss-Brenner' })).toBeInTheDocument()
    expect(screen.getByText(/CL-0003/)).toBeInTheDocument()
    // Dual currency display
    expect(screen.getByText(/EUR 40,290,000/)).toBeInTheDocument()
    // Dynamic alert chip for mandate breach
    expect(screen.getByText(/1 Mandate Breach Active/)).toBeInTheDocument()
    // Language preview chip
    expect(screen.getByText(/Prefers German Communication/)).toBeInTheDocument()

    // Expand administrative details drawer
    const adminButton = screen.getByText(/Admin & Domicile Details/)
    await user.click(adminButton)
    expect(screen.getByText(/Administrative & Compliance Dossier/)).toBeInTheDocument()
    expect(screen.getByText(/RM-014/)).toBeInTheDocument()
    expect(screen.getByText(/Family Inheritance/)).toBeInTheDocument()

    // Open Note Modal
    const noteBtn = screen.getByText('📝 Add RM Note')
    await user.click(noteBtn)
    expect(screen.getByText('Add RM Relationship Note')).toBeInTheDocument()
  })

  it('MeaningfulChangesTable displays triple-trigger badges and fires explain', async () => {
    const user = userEvent.setup()
    const onExplain = vi.fn()
    const onAttribution = vi.fn()

    render(
      <MeaningfulChangesTable
        changes={[mockChange]}
        loading={false}
        onExplain={onExplain}
        onOpenAttribution={onAttribution}
      />,
    )

    expect(screen.getByText('Nordvind Energy ASA')).toBeInTheDocument()
    expect(screen.getAllByText(/⚡ Dollar Move/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/📉 Price Shock/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/⚠️ Mandate Breach/).length).toBeGreaterThan(0)

    const explainBtn = screen.getByText('🔍 Explain')
    await user.click(explainBtn)
    expect(onExplain).toHaveBeenCalledWith(mockChange)

    const talkingPointsBtn = screen.getByText('💬 Talking Points')
    await user.click(talkingPointsBtn)
    expect(onAttribution).toHaveBeenCalledWith(mockChange)
  })

  it('ExplanationDrawer renders event citations and client relevance', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()
    const onPrepare = vi.fn()

    render(
      <ExplanationDrawer
        explanation={mockExplanation}
        loading={false}
        onClose={onClose}
        onPrepareAttribution={onPrepare}
      />,
    )

    expect(screen.getByText(/Holding Deep Dive/)).toBeInTheDocument()
    expect(screen.getByText(/EV-0004/)).toBeInTheDocument()
    expect(screen.getByText(/EU grid integration bottlenecks/)).toBeInTheDocument()
    expect(screen.getByText(/EUR 3.4m inheritance tax liability/)).toBeInTheDocument()

    const prepareBtn = screen.getByText('✨ Prepare Client Attribution')
    await user.click(prepareBtn)
    expect(onPrepare).toHaveBeenCalledWith(mockExplanation)
  })

  it('ClientAttributionModal renders plain English points and German language preview notice', async () => {
    const user = userEvent.setup()
    const onClose = vi.fn()

    render(<ClientAttributionModal draft={mockDraft} loading={false} onClose={onClose} />)

    expect(screen.getByText(/Client Conversation Studio/)).toBeInTheDocument()
    expect(screen.getByText(/Recent repricing in European renewable energy/)).toBeInTheDocument()
    expect(screen.getByText(/1. What Happened/)).toBeInTheDocument()
    expect(screen.getByText(/2. Why It Matters For You/)).toBeInTheDocument()
    expect(screen.getByText(/3. Next Steps to Discuss/)).toBeInTheDocument()
    expect(screen.getByText(/Language Preview Notice/)).toBeInTheDocument()

    const addBtn = screen.getByText('➕ Add to Meeting Brief')
    await user.click(addBtn)
    await waitFor(() => {
      expect(screen.getByText(/Added to Meeting Studio!/)).toBeInTheDocument()
    })
  })
})
