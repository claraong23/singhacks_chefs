import { useEffect, useMemo, useState } from 'react'
import type {
  ClientNote,
  Dossier,
  Insight,
  InsightStatus,
  ProposedObjective,
  SavedScenario,
  SimulatedRole,
} from '../types'
import {
  money,
  pct,
  signedPct,
  signedUsd,
  titleCase,
  usd,
  usdExact,
} from '../format'
import { BandChart, DonutList, LtvChart, TierBar } from './charts'
import { InsightCard } from './InsightCard'
import { EvidenceDrawer } from './EvidenceDrawer'
import { MeetingStudio } from './MeetingStudio'
import { ScenarioStudio } from './ScenarioStudio'
import { ClientHeader } from './ClientHeader'
import { WhatChangedTab } from './WhatChangedTab'
import { FollowThroughPanel } from './FollowThrough'

type Tab = 'why' | 'changed' | 'risk' | 'liquidity' | 'scenario' | 'brief' | 'follow'

const TABS: { key: Tab; label: string; hint: string }[] = [
  { key: 'why', label: 'Flags to address', hint: 'Ranked client flags requiring RM review and decision' },
  { key: 'changed', label: 'What changed and why', hint: 'Attribution against the event log' },
  { key: 'risk', label: 'Exposure and mandate', hint: 'Look-through, concentration, bands' },
  { key: 'liquidity', label: 'Liquidity and collateral', hint: 'What is sellable, and what is pledged' },
  { key: 'scenario', label: 'Scenario Studio', hint: 'Compare constrained current-state options' },
  { key: 'brief', label: 'Meeting Studio', hint: 'Versioned client-ready communication' },
  { key: 'follow', label: 'Follow-through', hint: 'Owners, outcomes, evidence and re-review' },
]

export function ClientDossier({
  dossier,
  busy,
  onDecide,
  onAttachScenario,
  onReset,
  role,
  onBack,
}: {
  dossier: Dossier
  busy: boolean
  onDecide: (
    insight: Insight,
    input: {
      status: InsightStatus
      rmNote: string
      selectedOptionId: string | null
      editedNextStep: string | null
    },
  ) => Promise<void>
  onAttachScenario: (insight: Insight, scenario: SavedScenario) => Promise<void>
  onReset?: (insight: Insight) => Promise<void>
  role: SimulatedRole
  onBack: () => void
}) {
  const searchParams = new URLSearchParams(window.location.search)
  const initialTab = (searchParams.get('tab') as Tab) || 'why'
  const [tab, setTab] = useState<Tab>(initialTab)
  const initialFrom = searchParams.get('from') || '2025-12-31'
  const initialTo = searchParams.get('to') || '2026-08-26'
  const initialPortfolio = searchParams.get('portfolio') || 'all'
  const initialHolding = searchParams.get('holding') || null

  const [localDossier, setLocalDossier] = useState<Dossier>(dossier)
  useEffect(() => {
    setLocalDossier(dossier)
  }, [dossier])

  const [evidenceFor, setEvidenceFor] = useState<Insight | null>(null)
  const [showDismissed, setShowDismissed] = useState(false)

  const insights = localDossier.insights.filter(
    (insight) => showDismissed || insight.status !== 'dismissed',
  )
  const dismissedCount = localDossier.insights.filter((i) => i.status === 'dismissed').length

  const handleTabChange = (nextTab: Tab) => {
    setTab(nextTab)
    const params = new URLSearchParams(window.location.search)
    params.set('tab', nextTab)
    window.history.replaceState(null, '', `?${params.toString()}`)
  }

  const handleNoteAdded = (newNote: ClientNote) => {
    setLocalDossier((prev) => ({
      ...prev,
      notes: [newNote, ...(prev.notes || [])],
    }))
  }

  const handleObjectiveProposed = (proposal: ProposedObjective) => {
    setLocalDossier((prev) => ({
      ...prev,
      client: {
        ...prev.client,
        objectives: `${prev.client.objectives} [Pending update: ${proposal.proposed_objectives}]`,
      },
    }))
  }

  return (
    <div>
      {/* Interactive Client Header: Hero bar, dual currency AUM, dynamic alert chips, admin drawer & modals */}
      <ClientHeader
        dossier={localDossier}
        onBack={onBack}
        onNoteAdded={handleNoteAdded}
        onObjectiveProposed={handleObjectiveProposed}
      />

      {/* The hint is exposed as a description rather than a title, so the
          accessible name stays identical to the visible label. */}
      <nav className="tabs" role="tablist">
        {TABS.map((entry) => (
          <button
            key={entry.key}
            role="tab"
            aria-selected={tab === entry.key}
            aria-description={entry.hint}
            onClick={() => handleTabChange(entry.key)}
          >
            {entry.label}
            {entry.key === 'why' && ` (${insights.length})`}
          </button>
        ))}
      </nav>

      {tab === 'why' && (
        <div className="stack">
          {insights.map((insight) => (
            <InsightCard
              key={insight.id}
              insight={insight}
              options={dossier.options[insight.id] ?? []}
              busy={busy}
              onEvidence={setEvidenceFor}
              onDecide={onDecide}
            />
          ))}
          {insights.length === 0 && (
            <div className="card">
              <div className="card-body muted">
                Nothing outstanding for this client at {dossier.as_of}.
              </div>
            </div>
          )}
          {dismissedCount > 0 && (
            <button className="btn quiet" onClick={() => setShowDismissed((v) => !v)}>
              {showDismissed ? 'Hide' : 'Show'} {dismissedCount} dismissed finding
              {dismissedCount === 1 ? '' : 's'}
            </button>
          )}
          {dossier.audit.length > 0 && (
            <div className="card">
              <div className="card-head">
                <h2>Audit trail</h2>
                <span className="sub">Every decision, with who and when</span>
              </div>
              <div className="card-body">
                <table className="postable">
                  <thead>
                    <tr>
                      <th>When</th>
                      <th>Who</th>
                      <th>Action</th>
                      <th>Finding</th>
                    </tr>
                  </thead>
                  <tbody>
                    {dossier.audit.map((entry, index) => (
                      <tr key={`${entry.timestamp}-${index}`}>
                        <td className="muted">{entry.timestamp}</td>
                        <td>{entry.actor}</td>
                        <td>{entry.action}</td>
                        <td className="muted">{entry.insight_id}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
        </div>
      )}

      {tab === 'scenario' && (
        <ScenarioStudio dossier={localDossier} busy={busy} onAttach={onAttachScenario} />
      )}

      {tab === 'changed' && (
        <WhatChangedTab
          dossier={localDossier}
          initialFrom={initialFrom}
          initialTo={initialTo}
          initialPortfolio={initialPortfolio}
          initialHoldingId={initialHolding}
          onUrlStateChange={(params) => {
            const url = new URLSearchParams(window.location.search)
            url.set('tab', 'changed')
            url.set('from', params.from)
            url.set('to', params.to)
            if (params.portfolio && params.portfolio !== 'all') {
              url.set('portfolio', params.portfolio)
            } else {
              url.delete('portfolio')
            }
            if (params.holding) {
              url.set('holding', params.holding)
            } else {
              url.delete('holding')
            }
            window.history.replaceState(null, '', `?${url.toString()}`)
          }}
        />
      )}
      {tab === 'risk' && <ExposureTab dossier={localDossier} />}
      {tab === 'liquidity' && <LiquidityTab dossier={localDossier} />}
      {tab === 'brief' && <MeetingStudio dossier={localDossier} onDecide={onDecide} onReset={onReset} />}
      {tab === 'follow' && <FollowThroughPanel dossier={localDossier} role={role} />}

      {evidenceFor && (
        <EvidenceDrawer insight={evidenceFor} onClose={() => setEvidenceFor(null)} />
      )}
    </div>
  )
}

/* ------------------------------------------------------------------------- */

function ExposureTab({ dossier }: { dossier: Dossier }) {
  const hiddenIssuers = dossier.exposures.issuers.filter((e) => e.legs.length > 1)
  const total = dossier.wealth.total_usd
  const assetClasses = useMemo(
    () =>
      Object.entries(dossier.wealth.by_asset_class).sort((a, b) => b[1] - a[1]) as [
        string,
        number,
      ][],
    [dossier],
  )

  return (
    <div className="stack">
      {hiddenIssuers.length > 0 && (
        <div className="card">
          <div className="card-head">
            <h2>The same bet, in more than one wrapper</h2>
            <span className="sub">
              Aggregated through instruments.underlying_reference
            </span>
          </div>
          <div className="card-body">
            {hiddenIssuers.map((exposure) => (
              <div key={exposure.key} style={{ marginBottom: 22 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'baseline' }}>
                  <h3 style={{ fontSize: 14 }}>{exposure.name}</h3>
                  <div>
                    <strong>{usd(exposure.attributed_usd)}</strong>{' '}
                    <span className="muted">· {pct(exposure.pct_of_household)} of household</span>
                  </div>
                </div>
                <table className="postable" style={{ marginTop: 8 }}>
                  <thead>
                    <tr>
                      <th>Line item</th>
                      <th>Wrapper</th>
                      <th>Seen via</th>
                      <th className="r">Attributed</th>
                      <th className="r">Of household</th>
                    </tr>
                  </thead>
                  <tbody>
                    {exposure.legs.map((leg) => (
                      <tr key={leg.instrument_id} className={leg.basis_field === 'underlying_reference' ? 'flag' : ''}>
                        <td>{leg.instrument_name}</td>
                        <td className="muted">{leg.wrapper}</td>
                        <td className="muted">
                          <span style={{ fontFamily: 'var(--mono)', fontSize: 11 }}>
                            {leg.basis_field}
                          </span>
                          <div style={{ fontSize: 11, marginTop: 2 }}>{leg.basis_note}</div>
                        </td>
                        <td className="r">{usdExact(leg.attributed_usd)}</td>
                        <td className="r">{pct((leg.attributed_usd / total) * 100)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ))}
            {dossier.exposures.unresolved.length > 0 && (
              <div className="banner" style={{ marginBottom: 0 }}>
                <strong>What we cannot verify.</strong>{' '}
                {dossier.exposures.unresolved.join(' ')}
              </div>
            )}
          </div>
        </div>
      )}

      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h2>Themes</h2>
            <span className="sub">One driver, several positions</span>
          </div>
          <div className="card-body">
            {dossier.exposures.themes.map((theme) => (
              <div key={theme.key} style={{ marginBottom: 14 }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 12.5, marginBottom: 5 }}>
                  <span>
                    {theme.name}{' '}
                    {theme.hidden && <span className="tag" style={{ marginLeft: 4 }}>look-through</span>}
                  </span>
                  <span className="muted">
                    {usd(theme.attributed_usd)} · {pct(theme.pct_of_household)}
                  </span>
                </div>
                <div style={{ height: 8, background: 'var(--surface-sunk)', borderRadius: 2 }}>
                  <div style={{
                    width: `${Math.min(100, theme.pct_of_household)}%`,
                    height: '100%',
                    background: theme.pct_of_household >= 30 ? 'var(--critical)' : 'var(--accent)',
                    borderRadius: 2,
                  }} />
                </div>
                <div className="footnote">
                  {theme.legs.map((leg) => leg.instrument_name).join(' · ')}
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Allocation</h2>
            <span className="sub">Household, all portfolios</span>
          </div>
          <div className="card-body">
            <DonutList entries={assetClasses} total={total} />
          </div>
        </div>
      </div>

      {dossier.portfolios.map((portfolio) => (
        <div className="card" key={portfolio.portfolio_id}>
          <div className="card-head">
            <h2>{portfolio.portfolio_name}</h2>
            <span className="sub">
              {portfolio.portfolio_id} · {portfolio.service_model} · {portfolio.mandate_name} ·{' '}
              {money(portfolio.value_usd, 'USD')}
            </span>
          </div>
          <div className="card-body">
            {portfolio.mandate_review?.governed ? (
              <>
                <BandChart
                  rows={Object.entries(portfolio.bands).map(([assetClass, band]) => ({
                    assetClass,
                    actual: portfolio.mandate_review?.allocation_pct[assetClass] ?? 0,
                    min: band.min_pct,
                    target: band.target_pct,
                    max: band.max_pct,
                    breach: portfolio.mandate_review?.band_breaches.find(
                      (b) => b.asset_class === assetClass,
                    ),
                  }))}
                />
                {(portfolio.mandate_review.position_breaches.length > 0 ||
                  portfolio.mandate_review.exclusion_breaches.length > 0) && (
                  <>
                    <hr className="rule" />
                    {portfolio.mandate_review.position_breaches.map((breach) => (
                      <div key={breach.instrument_id} className="small" style={{ marginBottom: 6 }}>
                        <span className="pill high">Position limit</span>{' '}
                        {breach.instrument_name} at {pct(breach.actual_pct)} against a{' '}
                        {pct(breach.limit_pct, 0)} ceiling.
                      </div>
                    ))}
                    {portfolio.mandate_review.exclusion_breaches.map((breach) => (
                      <div key={breach.instrument_id} className="small" style={{ marginBottom: 6 }}>
                        <span className="pill critical">Excluded</span>{' '}
                        {breach.instrument_name} at {pct(breach.pct_of_portfolio)} inside a
                        mandate with binding exclusions ({breach.service_model.toLowerCase()}).
                      </div>
                    ))}
                  </>
                )}
                {portfolio.mandate_notes && (
                  <div className="footnote">Mandate note: {portfolio.mandate_notes}</div>
                )}
              </>
            ) : (
              <p className="small muted" style={{ margin: 0 }}>
                Custody account. It forms part of the client's wealth but no bank mandate
                governs it, so no band or exclusion test is applied here.
              </p>
            )}
          </div>
        </div>
      ))}

      <div className="card">
        <div className="card-head">
          <h2>Positions</h2>
          <span className="sub">{dossier.wealth.positions.length} instruments, aggregated across portfolios</span>
        </div>
        <div className="card-body" style={{ overflowX: 'auto' }}>
          <table className="postable">
            <thead>
              <tr>
                <th>Instrument</th>
                <th>Asset class</th>
                <th>Liquidity</th>
                <th className="r">Value</th>
                <th className="r">Weight</th>
                <th className="r">Unrealised</th>
                <th className="r">Advance</th>
              </tr>
            </thead>
            <tbody>
              {dossier.wealth.positions.map((position) => (
                <tr key={position.instrument_id}>
                  <td>
                    {position.instrument_name}
                    <div className="muted" style={{ fontSize: 11 }}>
                      {position.instrument_id} · {position.portfolio_ids.join(', ')}
                      {position.sustainability_excluded && (
                        <span className="pill critical" style={{ marginLeft: 6 }}>excluded</span>
                      )}
                      {position.underlying_reference && (
                        <div style={{ marginTop: 2 }}>→ {position.underlying_reference}</div>
                      )}
                    </div>
                  </td>
                  <td className="muted">{position.asset_class}</td>
                  <td className="muted">{position.liquidity_tier}</td>
                  <td className="r">{usdExact(position.market_value_usd)}</td>
                  <td className="r">{pct(position.weight_pct)}</td>
                  <td className={`r ${position.unrealised_pnl_usd >= 0 ? 'pos' : 'neg'}`}>
                    {signedUsd(position.unrealised_pnl_usd)}
                    <div className="muted" style={{ fontSize: 11 }}>
                      {signedPct(position.unrealised_pnl_pct)}
                    </div>
                  </td>
                  <td className="r muted">{pct(position.advance_rate_pct, 0)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}

/* ------------------------------------------------------------------------- */

function LiquidityTab({ dossier }: { dossier: Dossier }) {
  const liquidity = dossier.liquidity

  return (
    <div className="stack">
      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h2>What can actually be sold</h2>
            <span className="sub">By liquidity tier</span>
          </div>
          <div className="card-body">
            <TierBar tiers={liquidity.by_tier} />
            <hr className="rule" />
            <table className="kv">
              <tbody>
                <tr>
                  <td>Daily and weekly</td>
                  <td style={{ textAlign: 'right' }}>{usdExact(liquidity.readily_realisable_usd)}</td>
                </tr>
                {liquidity.encumbered_cap_usd ? (
                  <tr>
                    <td>Less: pledged as collateral</td>
                    <td style={{ textAlign: 'right' }} className="neg">
                      −{usdExact(liquidity.encumbered_cap_usd).replace('USD ', 'USD ')}
                    </td>
                  </tr>
                ) : null}
                <tr>
                  <td><strong>Withdrawable without a margin call</strong></td>
                  <td style={{ textAlign: 'right' }}><strong>{usdExact(liquidity.withdrawable_usd)}</strong></td>
                </tr>
                {liquidity.gated_usd > 0 && (
                  <tr>
                    <td>Behind a redemption gate</td>
                    <td style={{ textAlign: 'right' }}>{usdExact(liquidity.gated_usd)}</td>
                  </tr>
                )}
                {liquidity.illiquid_usd > 0 && (
                  <tr>
                    <td>Illiquid</td>
                    <td style={{ textAlign: 'right' }}>{usdExact(liquidity.illiquid_usd)}</td>
                  </tr>
                )}
              </tbody>
            </table>
            {liquidity.notes.map((note) => (
              <div className="footnote" key={note}>{note}</div>
            ))}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>What is owed</h2>
            <span className="sub">Next {liquidity.horizon_months} months, to {liquidity.horizon_end}</span>
          </div>
          <div className="card-body">
            <div style={{ display: 'flex', gap: 28, marginBottom: 16 }}>
              <div className="stat">
                <span className="v">{usd(liquidity.obligations_total_usd)}</span>
                <span className="k">Total obligations</span>
              </div>
              <div className="stat">
                <span className="v" style={{ color: (liquidity.coverage_ratio ?? 9) < 1 ? 'var(--critical)' : undefined }}>
                  {liquidity.coverage_ratio === null ? '—' : `${liquidity.coverage_ratio.toFixed(2)}×`}
                </span>
                <span className="k">Cover</span>
              </div>
              {liquidity.shortfall_usd > 0 && (
                <div className="stat">
                  <span className="v neg">{usd(liquidity.shortfall_usd)}</span>
                  <span className="k">Shortfall</span>
                </div>
              )}
            </div>
            <table className="postable">
              <thead>
                <tr>
                  <th>Obligation</th>
                  <th>Window</th>
                  <th className="r">Amount</th>
                </tr>
              </thead>
              <tbody>
                {liquidity.obligations.map((obligation) => (
                  <tr key={obligation.id}>
                    <td>
                      {obligation.description}
                      <div className="muted" style={{ fontSize: 11 }}>
                        {obligation.id} · {obligation.certainty} · {obligation.recurrence}
                      </div>
                    </td>
                    <td className="muted">
                      {obligation.due_from}
                      {obligation.occurrences > 1 && ` ×${obligation.occurrences}`}
                    </td>
                    <td className="r">
                      {money(obligation.amount_ccy, obligation.currency)}
                      <div className="muted" style={{ fontSize: 11 }}>
                        {usdExact(obligation.total_usd)}
                      </div>
                    </td>
                  </tr>
                ))}
                {liquidity.obligations.length === 0 && (
                  <tr>
                    <td colSpan={3} className="muted">Nothing recorded inside the horizon.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {dossier.facilities.map((facility) => (
        <div className="card" key={facility.facility_id}>
          <div className="card-head">
            <h2>{facility.facility_type} · {facility.facility_id}</h2>
            <span className="sub">
              Secured on {facility.portfolio_id} · limit {money(facility.credit_limit, facility.currency)} ·{' '}
              {pct(facility.interest_rate_pct, 2)} p.a.
            </span>
          </div>
          <div className="card-body">
            <div className="grid2">
              <LtvChart series={facility.series} trigger={facility.margin_call_ltv_pct} />
              <div>
                <table className="kv">
                  <tbody>
                    <tr>
                      <td>Drawn today</td>
                      <td style={{ textAlign: 'right' }}>
                        {money(facility.series[facility.series.length - 1].drawn, facility.currency)}
                      </td>
                    </tr>
                    <tr>
                      <td>Lending value</td>
                      <td style={{ textAlign: 'right' }}>
                        {money(facility.series[facility.series.length - 1].lending_value, facility.currency)}
                      </td>
                    </tr>
                    <tr>
                      <td>Loan to value</td>
                      <td style={{ textAlign: 'right' }}>
                        {pct(facility.series[facility.series.length - 1].ltv_pct, 2)}
                      </td>
                    </tr>
                    <tr>
                      <td>Headroom to trigger</td>
                      <td style={{ textAlign: 'right' }} className={(facility.headroom_pp ?? 99) < 5 ? 'neg' : ''}>
                        {facility.headroom_pp === null ? '—' : `${facility.headroom_pp.toFixed(2)} pp`}
                      </td>
                    </tr>
                    <tr>
                      <td>Collateral fall that triggers a call</td>
                      <td style={{ textAlign: 'right' }} className={(facility.collateral_fall_to_trigger_pct ?? 99) < 5 ? 'neg' : ''}>
                        {pct(facility.collateral_fall_to_trigger_pct)}
                      </td>
                    </tr>
                  </tbody>
                </table>
                {facility.cure_narrative && (
                  <div className="banner" style={{ marginTop: 14 }}>
                    <strong>Read this carefully.</strong> {facility.cure_narrative}
                  </div>
                )}
                {facility.drawn_reconciliation
                  .filter((row) => Math.abs(row.unexplained) > 1000)
                  .map((row) => (
                    <div className="banner" key={row.to_snapshot} style={{ marginTop: 10 }}>
                      <strong>Reconciliation gap.</strong> Drawn moved{' '}
                      {money(row.drawn_change, facility.currency)} between {row.from_snapshot}{' '}
                      and {row.to_snapshot}, but transactions.csv records only{' '}
                      {money(row.explained_by_transactions, facility.currency)} of facility
                      activity ({row.transaction_ids.join(', ')}). The{' '}
                      {money(row.unexplained, facility.currency)} difference is reported
                      rather than reconciled away.
                    </div>
                  ))}
              </div>
            </div>
          </div>
        </div>
      ))}

      {dossier.liquidity.gated_positions.length > 0 && (
        <div className="card">
          <div className="card-head">
            <h2>Positions that cannot be sold on demand</h2>
            <span className="sub">Gated and illiquid</span>
          </div>
          <div className="card-body">
            <table className="postable">
              <thead>
                <tr>
                  <th>Position</th>
                  <th>Tier</th>
                  <th className="r">Value</th>
                  <th className="r">Advance rate</th>
                </tr>
              </thead>
              <tbody>
                {dossier.liquidity.gated_positions.map((position) => (
                  <tr key={position.instrument_id}>
                    <td>{position.instrument_name}</td>
                    <td className="muted">{position.liquidity_tier}</td>
                    <td className="r">{usdExact(position.market_value_usd)}</td>
                    <td className="r muted">{pct(position.advance_rate_pct, 0)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="footnote">
              A zero advance rate means the position adds nothing to borrowing capacity, so
              it can neither be sold quickly nor borrowed against.
            </div>
          </div>
        </div>
      )}

      {dossier.notes.length > 0 && (
        <div className="card">
          <div className="card-head">
            <h2>Relationship context</h2>
            <span className="sub">{titleCase('rm_notes.json')} — subjective, and not independently verified</span>
          </div>
          <div className="card-body">
            {dossier.notes.map((note) => (
              <div className="note-item" key={note.note_id}>
                <div className="h">
                  {note.note_date} · {note.channel} · {note.note_id}
                </div>
                <div className="t">{note.note}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
