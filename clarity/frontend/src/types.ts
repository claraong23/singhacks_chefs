/* Mirrors clarity/backend/clarity/contracts.py. Change both together. */

export type Severity = 'critical' | 'high' | 'medium' | 'low' | 'info'
export type InsightStatus =
  | 'new'
  | 'opened'
  | 'under_review'
  | 'rm_edited'
  | 'rm_reviewed'
  | 'escalated'
  | 'returned_for_review'
  | 'client_ready'
  | 'deferred'
  | 'dismissed'
export type Confidence = 'measured' | 'derived' | 'reported'
export type CheckResult = 'pass' | 'fail' | 'attention' | 'not_assessed'

export interface Evidence {
  source_file: string
  row_or_id: string
  field: string
  value: unknown
  snapshot_date: string | null
  note: string | null
}

export interface Assumption {
  statement: string
  basis: string
  impact_if_wrong: string | null
}

export interface SuitabilityCheck {
  check: string
  result: CheckResult
  detail: string
  reference: string | null
}

export interface DecisionGate {
  id: 'evidence' | 'suitability' | 'tax_planning' | 'data_model' | 'human_decision'
  label: string
  status: 'pass' | 'block'
  detail: string
  evidence: Evidence[]
}

export interface DecisionReadiness {
  can_mark_client_ready: boolean
  gates: DecisionGate[]
  evidence_version: string
}

export interface Fact {
  label: string
  value: string
  numeric: number | null
  unit: string | null
  trend: 'up' | 'down' | 'flat' | null
}

export interface Insight {
  id: string
  client_id: string
  category: string
  severity: Severity
  headline: string
  summary: string
  priority_score: number
  priority_reasons: string[]
  observed_facts: Fact[]
  client_relevance: string
  suggested_next_step: string
  evidence: Evidence[]
  assumptions: Assumption[]
  suitability_checks: SuitabilityCheck[]
  confidence: Confidence
  open_questions: string[]
  related_event_ids: string[]
  portfolio_ids: string[]
  instrument_ids: string[]
  amount_usd: number | null
  status: InsightStatus
  rm_note?: string
  selected_option_id?: string | null
  selected_scenario_id?: string | null
  scenario_calculation_version?: string | null
  decided_by?: string | null
  decided_at?: string | null
  edited?: boolean
  headline_original?: string
  suggested_next_step_original?: string
}

export interface ActionOption {
  id: string
  label: string
  rationale: string
  mechanics: string[]
  trade_offs: string[]
  suitability_checks: SuitabilityCheck[]
  requires: string[]
  estimated_impact: string | null
  evidence: Evidence[]
}

export interface ScenarioInput {
  key: string
  label: string
  unit: string
  minimum: number
  maximum: number
  step: number
  default: number
  help_text: string
}

export interface ScenarioTemplate {
  id: string
  client_id: string
  insight_id: string
  title: string
  description: string
  inputs: ScenarioInput[]
}

export interface ScenarioMetric {
  key: string
  label: string
  baseline: number | null
  scenario: number | null
  unit: string
  available: boolean
  detail: string
}

export interface ScenarioResult {
  template_id: string
  client_id: string
  insight_id: string
  option_id: string
  title: string
  as_of_date: string
  inputs: Record<string, number>
  assumptions: Assumption[]
  metrics: ScenarioMetric[]
  evidence: Evidence[]
  blocked_checks: string[]
  calculation_version: string
}

export interface SavedScenario {
  id: string
  name: string
  saved_by: string
  saved_at: string
  result: ScenarioResult
}

export interface BookRow {
  rank: number
  client_id: string
  client_name: string
  booking_centre: string
  base_currency: string
  wealth_band: string
  risk_profile: string
  life_stage: string
  total_usd: number
  priority_score: number
  top_headline: string
  top_category: string | null
  top_severity: Severity
  why_now: string[]
  insight_count: number
  severity_counts: Record<Severity, number>
  categories: Record<string, number>
  reviewed_count: number
  kyc_review_due: string
}

export interface BookView {
  as_of: string
  snapshots: { date: string; label: string }[]
  rm: { rm_id: string; rm_name: string; rm_desk: string }
  totals: {
    clients: number
    aum_usd: number
    insights: number
    critical: number
    high: number
    decisions: Record<string, number>
  }
  clients: BookRow[]
  data_warnings: string[]
  scoring: Record<string, string>
}

export interface Position {
  instrument_id: string
  instrument_name: string
  asset_class: string
  sub_asset_class: string
  sector: string
  region: string
  currency: string
  liquidity_tier: string
  market_value_usd: number
  weight_pct: number
  lending_value_usd: number
  advance_rate_pct: number | null
  unrealised_pnl_usd: number
  unrealised_pnl_pct: number | null
  portfolio_ids: string[]
  concentration_limit_applies: boolean
  sustainability_excluded: boolean
  underlying_reference: string
}

export interface ExposureLeg {
  instrument_id: string
  instrument_name: string
  wrapper: string
  market_value_usd: number
  attributed_usd: number
  basis_field: string
  basis_note: string
  portfolio_ids: string[]
}

export interface Exposure {
  key: string
  name: string
  kind: 'issuer' | 'theme'
  attributed_usd: number
  pct_of_household: number
  direct_usd: number
  looked_through_usd: number
  hidden: boolean
  legs: ExposureLeg[]
  event_ids: string[]
}

export interface MarketMove {
  series_id: string
  series_name: string
  unit: string
  start_value: number
  end_value: number
  change: number
  change_pct: number | null
}

export interface Driver {
  theme_key: string
  theme_name: string
  amount_usd: number
  pct_of_start: number | null
  market_moves: MarketMove[]
  events: {
    event_id: string
    event_date: string
    description: string
    primary_transmission: string
    severity: string
  }[]
}

export interface Explanation {
  client_id: string
  period: string
  primary_driver: string
  fx_dominates: boolean
  start: string
  end: string
  start_label: string
  end_label: string
  change_usd: number
  change_pct: number | null
  price_effect_usd: number
  fx_effect_usd: number
  flow_effect_usd: number
  drivers: Driver[]
  detractors: Contribution[]
  contributors: Contribution[]
  narrative: string[]
  provenance: string
}

export interface Contribution {
  instrument_id: string
  instrument_name: string
  asset_class: string
  currency: string
  start_value_usd: number
  end_value_usd: number
  price_effect_usd: number
  fx_effect_usd: number
  flow_effect_usd: number
  total_usd: number
  price_return_pct: number | null
  price_start: number | null
  price_end: number | null
}

export interface Obligation {
  id: string
  source: string
  description: string
  currency: string
  amount_ccy: number
  amount_usd: number
  occurrences: number
  total_usd: number
  due_from: string
  due_to: string
  certainty: string
  recurrence: string
}

export interface LiquidityView {
  client_id: string
  snapshot: string
  horizon_months: number
  horizon_end: string
  total_usd: number
  by_tier: Record<string, number>
  readily_realisable_usd: number
  encumbered_cap_usd: number | null
  withdrawable_usd: number
  gated_usd: number
  illiquid_usd: number
  obligations: Obligation[]
  obligations_confirmed_usd: number
  obligations_total_usd: number
  coverage_ratio: number | null
  shortfall_usd: number
  gated_positions: {
    instrument_id: string
    instrument_name: string
    liquidity_tier: string
    market_value_usd: number
    advance_rate_pct: number | null
  }[]
  notes: string[]
}

export interface LtvPoint {
  snapshot: string
  label: string
  drawn: number | null
  collateral_market_value: number | null
  lending_value: number | null
  ltv_pct: number | null
  headroom: number | null
  breached: boolean
}

export interface Facility {
  facility_id: string
  client_id: string
  portfolio_id: string
  facility_type: string
  currency: string
  credit_limit: number
  interest_rate_pct: number
  margin_call_ltv_pct: number
  series: LtvPoint[]
  headroom_pp: number | null
  collateral_fall_to_trigger_pct: number | null
  breaches: LtvPoint[]
  cure_narrative: string | null
  drawn_reconciliation: {
    from_snapshot: string
    to_snapshot: string
    drawn_change: number
    explained_by_transactions: number
    unexplained: number
    transaction_ids: string[]
  }[]
}

export interface BandBreach {
  portfolio_id: string
  mandate_code: string
  asset_class: string
  actual_pct: number
  min_pct: number
  target_pct: number
  max_pct: number
  direction: string
  breach_pp: number
  value_base: number
  base_currency: string
}

export interface PortfolioView {
  portfolio_id: string
  portfolio_name: string
  mandate_code: string
  mandate_name: string
  service_model: string
  base_currency: string
  benchmark: string
  inception_date: string
  value_usd: number
  aum_series: { snapshot: string; label: string; value_base: number | null }[]
  mandate_review: {
    governed: boolean
    allocation_pct: Record<string, number>
    band_breaches: BandBreach[]
    position_breaches: {
      instrument_id: string
      instrument_name: string
      actual_pct: number
      limit_pct: number
      breach_pp: number
    }[]
    exclusion_breaches: {
      instrument_id: string
      instrument_name: string
      pct_of_portfolio: number
      service_model: string
      mandate_notes: string
    }[]
  } | null
  bands: Record<string, { min_pct: number; target_pct: number; max_pct: number }>
  mandate_notes: string | null
}

export interface MeetingBriefView {
  client_id: string
  generated_at: string
  as_of: string
  purpose: string
  talking_points: string[]
  questions_to_ask: string[]
  relationship_context: string[]
  contradictions: string[]
  do_not_say: string[]
  draft_follow_up: string
  provenance: string
}

export interface Dossier {
  as_of: string
  client: Record<string, string | number | null>
  portfolios: PortfolioView[]
  wealth: {
    total_usd: number
    timeseries: {
      snapshot: string
      label: string
      total_usd: number
      change_usd: number | null
      change_pct: number | null
    }[]
    by_asset_class: Record<string, number>
    by_liquidity_tier: Record<string, number>
    by_currency: Record<string, number>
    by_region: Record<string, number>
    by_sector: Record<string, number>
    positions: Position[]
  }
  income: {
    annualised_gross_usd: number
    annualised_net_usd: number
    yield_pct: number | null
    quarters_observed: number
  }
  explanation: { ytd: Explanation; recent: Explanation }
  exposures: { issuers: Exposure[]; themes: Exposure[]; unresolved: string[] }
  liquidity: LiquidityView
  facilities: Facility[]
  insights: Insight[]
  options: Record<string, ActionOption[]>
  brief: MeetingBriefView
  notes: {
    note_id: string
    note_date: string
    channel: string
    rm_name: string
    note: string
  }[]
  events: {
    event_id: string
    event_date: string
    event_type: string
    region: string
    description: string
    primary_transmission: string
    severity: string
  }[]
  market: {
    series: {
      series_id: string
      series_name: string
      category: string
      unit: string
      points: { snapshot: string; value: number | null }[]
    }[]
  }
  audit: {
    timestamp: string
    actor: string
    action: string
    insight_id: string
    client_id: string
    detail: Record<string, unknown>
  }[]
}
