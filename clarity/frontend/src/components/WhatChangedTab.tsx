import { useCallback, useEffect, useState } from 'react'
import type {
  ClientAttributionDraft,
  Dossier,
  HoldingChange,
  HoldingExplanation,
} from '../types'
import { getHoldingChanges, explainHolding, getClientAttribution } from '../api'
import { DivergingBars, ValueLine } from './charts'
import { signedUsd } from '../format'
import { PeriodSelector } from './PeriodSelector'
import { PortfolioScopeControl } from './PortfolioScopeControl'
import { MeaningfulChangesTable } from './MeaningfulChangesTable'
import { ExplanationDrawer } from './ExplanationDrawer'
import { ClientAttributionModal } from './ClientAttributionModal'

interface WhatChangedTabProps {
  dossier: Dossier
  initialFrom?: string
  initialTo?: string
  initialPortfolio?: string
  initialHoldingId?: string | null
  onUrlStateChange?: (params: {
    from: string
    to: string
    portfolio: string
    holding: string | null
  }) => void
}

export function WhatChangedTab({
  dossier,
  initialFrom = '2025-12-31',
  initialTo = '2026-08-26',
  initialPortfolio = 'all',
  initialHoldingId = null,
  onUrlStateChange,
}: WhatChangedTabProps) {
  const clientId = String(dossier.client.client_id)

  const [from, setFrom] = useState(initialFrom)
  const [to, setTo] = useState(initialTo)
  const [portfolio, setPortfolio] = useState(initialPortfolio)

  const [changes, setChanges] = useState<HoldingChange[]>([])
  const [loadingChanges, setLoadingChanges] = useState(false)

  // Drawer state
  const [explanation, setExplanation] = useState<HoldingExplanation | null>(null)
  const [loadingExplanation, setLoadingExplanation] = useState(false)

  // Modal state
  const [draft, setDraft] = useState<ClientAttributionDraft | null>(null)
  const [loadingDraft, setLoadingDraft] = useState(false)

  const ytd = dossier.explanation.ytd
  const recent = dossier.explanation.recent

  // Fetch changes
  const loadChanges = useCallback(
    async (f: string, t: string, p: string) => {
      setLoadingChanges(true)
      try {
        const res = await getHoldingChanges(clientId, {
          from: f,
          to: t,
          portfolio: p,
        })
        setChanges(res.changes || [])
      } catch (err) {
        console.error('Failed to load holding changes:', err)
      } finally {
        setLoadingChanges(false)
      }
    },
    [clientId],
  )

  useEffect(() => {
    void loadChanges(from, to, portfolio)
  }, [from, to, portfolio, loadChanges])

  // Update URL state
  const notifyUrlChange = useCallback(
    (f: string, t: string, p: string, h: string | null) => {
      if (onUrlStateChange) {
        onUrlStateChange({ from: f, to: t, portfolio: p, holding: h })
      }
    },
    [onUrlStateChange],
  )

  const handlePeriodChange = (newFrom: string, newTo: string) => {
    setFrom(newFrom)
    setTo(newTo)
    notifyUrlChange(newFrom, newTo, portfolio, explanation?.instrument_id || null)
  }

  const handlePortfolioChange = (newPortfolio: string) => {
    setPortfolio(newPortfolio)
    notifyUrlChange(from, to, newPortfolio, explanation?.instrument_id || null)
  }

  // Handle Explain holding
  const handleExplainHolding = async (changeOrId: HoldingChange | string) => {
    const instrumentId = typeof changeOrId === 'string' ? changeOrId : changeOrId.instrument_id
    setLoadingExplanation(true)
    notifyUrlChange(from, to, portfolio, instrumentId)
    try {
      const res = await explainHolding({
        clientId,
        instrumentId,
        from,
        to,
        portfolioId: portfolio === 'all' ? undefined : portfolio,
      })
      setExplanation(res.explanation)
    } catch (err) {
      alert(`Could not load explanation: ${String(err)}`)
    } finally {
      setLoadingExplanation(false)
    }
  }

  // Handle Open Client Attribution Modal
  const handleOpenAttribution = async (changeOrExp: HoldingChange | HoldingExplanation) => {
    const instrumentId = changeOrExp.instrument_id
    setLoadingDraft(true)
    try {
      const res = await getClientAttribution({
        clientId,
        instrumentId,
        from,
        to,
        portfolioId: portfolio === 'all' ? undefined : portfolio,
      })
      setDraft(res.draft)
    } catch (err) {
      alert(`Could not generate client attribution: ${String(err)}`)
    } finally {
      setLoadingDraft(false)
    }
  }

  // Deep-link initial holding inspection
  useEffect(() => {
    if (initialHoldingId) {
      void handleExplainHolding(initialHoldingId)
    }
  }, [initialHoldingId])

  return (
    <div className="stack">
      {/* Interactive Controls: Snapshot Period & Portfolio Scope */}
      <PeriodSelector from={from} to={to} onChange={handlePeriodChange} />
      <PortfolioScopeControl
        portfolios={dossier.portfolios}
        selectedPortfolio={portfolio}
        onChange={handlePortfolioChange}
      />

      {/* Meaningful Changes Table */}
      <MeaningfulChangesTable
        changes={changes}
        loading={loadingChanges}
        onExplain={handleExplainHolding}
        onOpenAttribution={handleOpenAttribution}
      />

      {/* Slide-out Explanation Drawer */}
      <ExplanationDrawer
        explanation={explanation}
        loading={loadingExplanation}
        onClose={() => {
          setExplanation(null)
          notifyUrlChange(from, to, portfolio, null)
        }}
        onPrepareAttribution={handleOpenAttribution}
      />

      {/* Client Attribution Modal */}
      <ClientAttributionModal
        draft={draft}
        loading={loadingDraft}
        onClose={() => setDraft(null)}
      />

      {/* Macro Portfolio Value & YTD Narrative */}
      <div className="card">
        <div className="card-head">
          <h2>Household value across the five snapshots</h2>
          <span className="sub">
            {ytd.start_label} to {ytd.end_label}
          </span>
        </div>
        <div className="card-body">
          <ValueLine points={dossier.wealth.timeseries} />
          <hr className="rule" />
          {ytd.narrative.map((sentence, index) => (
            <p
              key={index}
              style={{
                margin: index === 0 ? '0 0 10px' : '0 0 10px',
                fontSize: 13.5,
              }}
            >
              {sentence}
            </p>
          ))}
          <div className="footnote">
            Assembled from computed attribution, market_context.csv levels and event_log.csv
            entries. No language model wrote this paragraph, and every clause has a source row behind
            it.
          </div>
        </div>
      </div>

      {/* Drivers by Theme & Biggest Market Moves */}
      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h2>What drove it</h2>
            <span className="sub">Year to date, by theme</span>
          </div>
          <div className="card-body">
            <DivergingBars
              rows={ytd.drivers.map((driver) => ({
                label: driver.theme_name,
                value: driver.amount_usd,
                detail: driver.market_moves[0]
                  ? `${driver.market_moves[0].series_name}: ${driver.market_moves[0].start_value} → ${driver.market_moves[0].end_value} ${driver.market_moves[0].unit}`
                  : undefined,
              }))}
            />
            <hr className="rule" />
            <table className="kv">
              <tbody>
                <tr>
                  <td>Market movement</td>
                  <td
                    style={{ textAlign: 'right' }}
                    className={ytd.price_effect_usd >= 0 ? 'pos' : 'neg'}
                  >
                    {signedUsd(ytd.price_effect_usd)}
                  </td>
                </tr>
                <tr>
                  <td>Currency translation</td>
                  <td
                    style={{ textAlign: 'right' }}
                    className={ytd.fx_effect_usd >= 0 ? 'pos' : 'neg'}
                  >
                    {signedUsd(ytd.fx_effect_usd)}
                  </td>
                </tr>
                <tr>
                  <td>Money in and out</td>
                  <td style={{ textAlign: 'right' }}>{signedUsd(ytd.flow_effect_usd)}</td>
                </tr>
              </tbody>
            </table>
            {ytd.fx_dominates && (
              <div className="banner" style={{ marginTop: 14, marginBottom: 0 }}>
                Currency translation is larger than the market movement here. Reported in USD the
                household looks weaker than it does in the client's own reporting currency.
              </div>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Biggest market moves</h2>
            <span className="sub">Price effect only, excluding purchases</span>
          </div>
          <div className="card-body">
            <table className="postable">
              <thead>
                <tr>
                  <th>Position</th>
                  <th className="r">Price effect</th>
                  <th className="r">Price move</th>
                  <th className="r">Action</th>
                </tr>
              </thead>
              <tbody>
                {[...ytd.detractors, ...ytd.contributors].slice(0, 9).map((row) => (
                  <tr key={row.instrument_id}>
                    <td>
                      {row.instrument_name}
                      <div className="muted" style={{ fontSize: 11 }}>
                        {row.asset_class} · {row.currency}
                      </div>
                    </td>
                    <td className={`r ${row.price_effect_usd >= 0 ? 'pos' : 'neg'}`}>
                      {signedUsd(row.price_effect_usd)}
                    </td>
                    <td className="r muted">
                      {row.price_start !== null && row.price_end !== null
                        ? `${row.price_start} → ${row.price_end}`
                        : '—'}
                    </td>
                    <td className="r">
                      <button
                        className="btn quiet"
                        style={{ fontSize: 11, padding: '2px 6px' }}
                        onClick={() => handleExplainHolding(row.instrument_id)}
                      >
                        Explain
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div className="footnote">
              Positions bought during the period are measured against their cost basis, so a
              structured product marked below what the client paid shows as a loss rather than as an
              inflow.
            </div>
          </div>
        </div>
      </div>

      {/* Events Behind the Moves & Market Backdrop */}
      <div className="grid2">
        <div className="card">
          <div className="card-head">
            <h2>Events behind the moves</h2>
            <span className="sub">event_log.csv is authoritative for 2026</span>
          </div>
          <div className="card-body">
            {dossier.events.map((event) => (
              <div className="event-item" key={event.event_id}>
                <div className="d">
                  {event.event_date}
                  <div style={{ marginTop: 4 }}>
                    <span
                      className={`pill ${
                        event.severity === 'Severe'
                          ? 'critical'
                          : event.severity === 'High'
                          ? 'high'
                          : 'low'
                      }`}
                    >
                      {event.severity}
                    </span>
                  </div>
                </div>
                <div>
                  <div className="t">{event.description}</div>
                  <div className="ch">Reached portfolios through: {event.primary_transmission}</div>
                </div>
              </div>
            ))}
            {dossier.events.length === 0 && (
              <p className="muted small">
                No 2026 events in the log map to this client's themes. The moves here are structural
                rather than event-driven.
              </p>
            )}
          </div>
        </div>

        <div className="card">
          <div className="card-head">
            <h2>Market backdrop</h2>
            <span className="sub">Same five dates</span>
          </div>
          <div className="card-body">
            <table className="postable">
              <thead>
                <tr>
                  <th>Series</th>
                  {dossier.wealth.timeseries.map((point) => (
                    <th className="r" key={point.snapshot}>
                      {point.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {dossier.market.series.map((series) => (
                  <tr key={series.series_id}>
                    <td>
                      {series.series_name}
                      <div className="muted" style={{ fontSize: 11 }}>
                        {series.unit}
                      </div>
                    </td>
                    {series.points.map((point) => (
                      <td className="r" key={point.snapshot}>
                        {point.value === null ? '—' : point.value.toLocaleString('en-GB')}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
            <hr className="rule" />
            <div className="eyebrow" style={{ marginBottom: 8 }}>
              Since the half-year
            </div>
            <p className="small" style={{ margin: 0 }}>
              {recent.narrative[0]}
            </p>
          </div>
        </div>
      </div>
    </div>
  )
}
