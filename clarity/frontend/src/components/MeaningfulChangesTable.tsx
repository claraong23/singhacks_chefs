import { useState, useMemo } from 'react'
import type { HoldingChange } from '../types'
import { pct, signedPct, signedUsd, usd } from '../format'

interface MeaningfulChangesTableProps {
  changes: HoldingChange[]
  loading: boolean
  onExplain: (change: HoldingChange) => void
  onOpenAttribution: (change: HoldingChange) => void
}

type FilterMode = 'meaningful' | 'all' | 'breach' | 'price' | 'dollar' | 'lag'

export function MeaningfulChangesTable({
  changes,
  loading,
  onExplain,
  onOpenAttribution,
}: MeaningfulChangesTableProps) {
  const [filterMode, setFilterMode] = useState<FilterMode>('meaningful')
  const [searchQuery, setSearchQuery] = useState('')

  const filteredChanges = useMemo(() => {
    return changes.filter((c) => {
      // Text search
      if (
        searchQuery &&
        !c.instrument_name.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !c.instrument_id.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !c.sector.toLowerCase().includes(searchQuery.toLowerCase()) &&
        !c.asset_class.toLowerCase().includes(searchQuery.toLowerCase())
      ) {
        return false
      }

      // Filter chips
      if (filterMode === 'meaningful') return c.is_meaningful
      if (filterMode === 'breach')
        return c.trigger_badges.some((b) => b.toLowerCase().includes('breach'))
      if (filterMode === 'price')
        return c.trigger_badges.some((b) => b.toLowerCase().includes('price'))
      if (filterMode === 'dollar')
        return c.trigger_badges.some((b) => b.toLowerCase().includes('dollar'))
      if (filterMode === 'lag') return c.valuation_lag
      return true // 'all'
    })
  }, [changes, filterMode, searchQuery])

  const meaningfulCount = useMemo(() => changes.filter((c) => c.is_meaningful).length, [changes])
  const breachCount = useMemo(
    () => changes.filter((c) => c.trigger_badges.some((b) => b.toLowerCase().includes('breach'))).length,
    [changes],
  )
  const priceCount = useMemo(
    () => changes.filter((c) => c.trigger_badges.some((b) => b.toLowerCase().includes('price'))).length,
    [changes],
  )

  return (
    <div className="card" style={{ marginBottom: 24 }}>
      <div className="card-head" style={{ flexWrap: 'wrap', gap: 12 }}>
        <div>
          <h2>Meaningful Holding Movements</h2>
          <span className="sub">
            Triple-trigger evaluation: Dollar moves ≥$50k/0.5%, Price shocks ≥10%, or Mandate breaches
          </span>
        </div>
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <input
            type="search"
            className="input"
            style={{ width: 190, padding: '4px 8px', fontSize: 12 }}
            placeholder="Search instrument or sector…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
        </div>
      </div>

      <div className="card-body">
        {/* Quick Filter Chips */}
        <div className="filters" style={{ marginBottom: 16 }}>
          <button
            className="chip"
            aria-pressed={filterMode === 'meaningful'}
            onClick={() => setFilterMode('meaningful')}
          >
            ⚡ Meaningful Changes ({meaningfulCount})
          </button>
          <button
            className="chip"
            aria-pressed={filterMode === 'all'}
            onClick={() => setFilterMode('all')}
          >
            All Holdings Evaluated ({changes.length})
          </button>
          {breachCount > 0 && (
            <button
              className="chip"
              aria-pressed={filterMode === 'breach'}
              onClick={() => setFilterMode('breach')}
            >
              ⚠️ Mandate Breaches ({breachCount})
            </button>
          )}
          <button
            className="chip"
            aria-pressed={filterMode === 'price'}
            onClick={() => setFilterMode('price')}
          >
            📉 Price Shocks ({priceCount})
          </button>
          <button
            className="chip"
            aria-pressed={filterMode === 'dollar'}
            onClick={() => setFilterMode('dollar')}
          >
            💵 Large Dollar Moves
          </button>
          <button
            className="chip"
            aria-pressed={filterMode === 'lag'}
            onClick={() => setFilterMode('lag')}
          >
            ⏳ Valuation Lag Only
          </button>
        </div>

        {loading ? (
          <div className="loading">Evaluating holding changes across snapshot dates…</div>
        ) : filteredChanges.length === 0 ? (
          <div style={{ padding: '30px 0', textAlign: 'center', color: 'var(--muted)' }}>
            No holdings matched the selected criteria in this period.
          </div>
        ) : (
          <div style={{ overflowX: 'auto' }}>
            <table className="postable">
              <thead>
                <tr>
                  <th>Holding & Details</th>
                  <th>Portfolio</th>
                  <th className="r">Start → End Value (USD)</th>
                  <th className="r">Value Delta ($)</th>
                  <th className="r">Price Return</th>
                  <th className="r">Weight Delta</th>
                  <th>Triggers & Badges</th>
                  <th className="r">Advisory Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredChanges.map((c) => {
                  const hasBreach = c.trigger_badges.some((b) =>
                    b.toLowerCase().includes('breach'),
                  )
                  const isPositiveDelta = c.value_change_usd >= 0
                  return (
                    <tr
                      key={c.instrument_id}
                      className={hasBreach ? 'flag' : ''}
                      style={{
                        background: c.is_meaningful
                          ? undefined
                          : 'var(--surface-sunk)',
                        opacity: c.is_meaningful ? 1 : 0.78,
                      }}
                    >
                      <td>
                        <div style={{ fontWeight: 600 }}>{c.instrument_name}</div>
                        <div className="muted" style={{ fontSize: 11 }}>
                          {c.instrument_id} · {c.asset_class} · {c.sector} ({c.region})
                        </div>
                      </td>
                      <td style={{ fontSize: 12 }}>
                        {c.portfolio_ids.length === 1
                          ? c.portfolio_ids[0]
                          : `${c.portfolio_ids.length} portfolios`}
                      </td>
                      <td className="r" style={{ fontSize: 12 }}>
                        <div>{usd(c.end_value_usd)}</div>
                        <div className="muted" style={{ fontSize: 11 }}>
                          was {usd(c.start_value_usd)}
                        </div>
                      </td>
                      <td
                        className={`r ${isPositiveDelta ? 'pos' : 'neg'}`}
                        style={{ fontWeight: 600, fontSize: 12.5 }}
                      >
                        {signedUsd(c.value_change_usd)}
                      </td>
                      <td className="r" style={{ fontSize: 12 }}>
                        {c.price_return_pct !== null ? (
                          <span className={c.price_return_pct >= 0 ? 'pos' : 'neg'}>
                            {signedPct(c.price_return_pct, 1)}
                          </span>
                        ) : (
                          <span className="muted">Static/Illiquid</span>
                        )}
                        {c.start_price !== null && c.end_price !== null && (
                          <div className="muted" style={{ fontSize: 10.5 }}>
                            {c.start_price} → {c.end_price} {c.currency}
                          </div>
                        )}
                      </td>
                      <td className="r" style={{ fontSize: 12 }}>
                        {c.weight_change_pct >= 0 ? '+' : '−'}
                        {Math.abs(c.weight_change_pct).toFixed(2)} pp
                        <div className="muted" style={{ fontSize: 10.5 }}>
                          {pct(c.start_weight_pct)} → {pct(c.end_weight_pct)}
                        </div>
                      </td>
                      <td>
                        <div style={{ display: 'flex', gap: 4, flexWrap: 'wrap' }}>
                          {c.trigger_badges.map((badge, idx) => {
                            const isCrit = badge.includes('Mandate Breach')
                            const isHigh = badge.includes('Price Shock')
                            return (
                              <span
                                key={idx}
                                className={`pill ${
                                  isCrit ? 'critical' : isHigh ? 'high' : 'accent'
                                }`}
                                style={{ fontSize: 10.5, padding: '1px 6px' }}
                              >
                                {badge}
                              </span>
                            )
                          })}
                          {c.valuation_lag && (
                            <span
                              className="pill medium"
                              style={{ fontSize: 10.5, padding: '1px 6px' }}
                              title="Illiquid asset with reporting lag"
                            >
                              ⏳ Lag
                            </span>
                          )}
                        </div>
                      </td>
                      <td className="r">
                        <div
                          style={{
                            display: 'flex',
                            gap: 5,
                            justifyContent: 'flex-end',
                            alignItems: 'center',
                          }}
                        >
                          <button
                            className="btn primary"
                            style={{ fontSize: 11.5, padding: '3px 9px' }}
                            onClick={() => onExplain(c)}
                            title="Inspect causal events and transmission mechanism"
                          >
                            🔍 Explain
                          </button>
                          <button
                            className="btn"
                            style={{ fontSize: 11.5, padding: '3px 8px' }}
                            onClick={() => onOpenAttribution(c)}
                            title="Generate client-facing attribution talking points"
                          >
                            💬 Talking Points
                          </button>
                        </div>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )}

        <div className="footnote" style={{ marginTop: 14 }}>
          Holdings changelog continuously tracks quantity, FX, and price components. Explanations
          connect deterministic changes directly to the authoritative <code>event_log.csv</code>{' '}
          registry.
        </div>
      </div>
    </div>
  )
}
