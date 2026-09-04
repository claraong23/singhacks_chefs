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
  priority_factors?: PriorityFactors | null
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

export interface PriorityFactors {
  severity_weight: number
  materiality_pct: number | null
  days_until: number | null
  amount_usd: number | null
}

export type PriorityPolicyStatus = 'draft' | 'submitted' | 'active' | 'rejected' | 'retired'
export interface PriorityPolicy {
  id: string
  name: string
  weights: { severity: number; materiality: number; urgency: number }
  status: PriorityPolicyStatus
  rationale: string
  created_by: string
  created_at: string
  template?: string | null
  activation_history: Record<string, unknown>[]
}

export interface PriorityPolicyEvaluation {
  policy_id: string
  active_policy_id: string
  feedback_count: number
  anchor_coverage: string[]
  activation_eligible: boolean
  warnings: string[]
  top_five_relevance_rate: number | null
  urgency_alignment_rate: number | null
  rank_changes: Array<{
    client_id: string
    headline: string
    candidate_rank: number
    active_rank: number
    rank_delta: number
    candidate_score: number
    active_score: number
  }>
}

export interface RMFeedbackInput {
  usefulness: 'useful' | 'partly_useful' | 'not_useful'
  urgencyAssessment: 'right' | 'overstated' | 'understated'
  rationale: string
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
  scoring: { formula: string; materiality: string; urgency: string; note: string; policy?: PriorityPolicy }
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

export type CommunicationChannel = 'email' | 'formal_briefing' | 'call_notes' | 'client_app'

export interface MeetingSection {
  key: string
  title: string
  content: string
  evidence_refs: string[]
}

export interface CommunicationVariant {
  channel: CommunicationChannel
  label: string
  content: string
  evidence_refs: string[]
}

export interface MeetingVersion {
  id: string
  version: number
  created_at: string
  actor: string
  reason: string
  sections: MeetingSection[]
  communications: CommunicationVariant[]
}

export interface CommunicationPreflight {
  can_hand_off: boolean
  checks: { id: string; label: string; status: 'pass' | 'block'; detail: string }[]
  checked_at: string
}

export interface MeetingHandoffEvent {
  id: string
  package_id: string
  channel: CommunicationChannel
  actor: string
  created_at: string
  preflight_version: number
}

export interface MeetingPackage {
  id: string
  client_id: string
  insight_id: string
  state: 'draft' | 'preflight_passed' | 'handed_off'
  created_at: string
  created_by: string
  client_reporting_language?: string
  source: {
    decision_status: string
    selected_option_id: string | null
    selected_scenario_id: string | null
    scenario_calculation_version: string | null
    evidence_version: string | null
    gate_snapshot: { status: string }[]
    evidence: Evidence[]
  }
  current_version: number
  versions: MeetingVersion[]
  handoffs: MeetingHandoffEvent[]
  last_preflight?: CommunicationPreflight
}

export type SimulatedRole = 'rm' | 'credit' | 'wealth_planning' | 'investment' | 'compliance_audit' | 'operations'
export type WorkStatus = 'open' | 'in_progress' | 'waiting' | 'completed' | 'cancelled'

export interface FollowThroughRecord {
  id: string
  client_id: string
  insight_id?: string | null
  meeting_package_id?: string | null
  owner_role?: string
  due_date?: string
  status: string
  evidence_refs?: string[]
  history: { timestamp: string; actor: string; action: string; reason: string }[]
  [key: string]: unknown
}

export interface FollowThroughView {
  tasks: FollowThroughRecord[]
  referrals: FollowThroughRecord[]
  outcomes: FollowThroughRecord[]
  evidence_updates: FollowThroughRecord[]
  reevaluations: FollowThroughRecord[]
}

export interface AuditTimelineEvent {
  id: string
  timestamp: string
  origin: 'source_data' | 'system' | 'user_decision'
  object_type: string
  object_id: string
  action: string
  actor: string
  client_id: string | null
  insight_id: string | null
  detail: Record<string, unknown>
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
  follow_through: FollowThroughView
  priority_policy?: PriorityPolicy
  audit: AuditTimelineEvent[]
}

export interface HoldingChange {
  instrument_id: string
  instrument_name: string
  asset_class: string
  sector: string
  region: string
  currency: string
  portfolio_ids: string[]
  start_quantity: number
  end_quantity: number
  quantity_change: number
  start_price: number | null
  end_price: number | null
  price_return_pct: number | null
  start_value_usd: number
  end_value_usd: number
  value_change_usd: number
  start_weight_pct: number
  end_weight_pct: number
  weight_change_pct: number
  trigger_badges: string[]
  is_meaningful: boolean
  valuation_lag: boolean
  liquidity_tier: string
}

export interface HoldingExplanation {
  client_id: string
  instrument_id: string
  instrument_name: string
  asset_class: string
  sector: string
  region: string
  start: string
  end: string
  portfolio_id: string | null
  what_changed: {
    start_value_usd: number
    end_value_usd: number
    value_change_usd: number
    start_quantity: number
    end_quantity: number
    quantity_change: number
    start_price: number | null
    end_price: number | null
    price_return_pct: number | null
    start_weight_pct: number
    end_weight_pct: number
    weight_change_pct: number
    currency: string
    valuation_lag: boolean
  }
  event_evidence: {
    event_id: string
    event_date: string
    event_type: string
    region: string
    description: string
    primary_transmission: string
    severity: string
    correlation_score: number
    rationale: string
  }[]
  transmission_mechanisms: string[]
  why_it_matters: string[]
  uncertainties: string[]
  source_evidence: Evidence[]
}

export interface ClientAttributionDraft {
  client_id: string
  instrument_id: string
  instrument_name: string
  headline: string
  what_happened_bullet: string
  why_it_matters_bullet: string
  next_steps_bullet: string
  confidence: string
  source_chips: string[]
  limitations: string[]
  language_disclaimer: string | null
  created_at: string
}

export interface ClientNote {
  note_id: string
  note_date: string
  channel: string
  rm_name: string
  note: string
}

export interface ProposedObjective {
  proposal_id: string
  client_id: string
  proposed_at: string
  rm_id: string
  rm_name: string
  current_objectives: string
  proposed_objectives: string
  rationale: string
  status: 'pending_governance_review' | 'approved' | 'rejected'
}

