import type { HoldingExplanation } from '../types'
import { pct, signedPct, signedUsd, usd } from '../format'

interface ExplanationDrawerProps {
  explanation: HoldingExplanation | null
  loading: boolean
  onClose: () => void
  onPrepareAttribution: (explanation: HoldingExplanation) => void
}

export function ExplanationDrawer({
  explanation,
  loading,
  onClose,
  onPrepareAttribution,
}: ExplanationDrawerProps) {
  if (!explanation && !loading) return null

  return (
    <div className="drawer-backdrop" onClick={onClose}>
      <aside
        className="drawer"
        style={{ width: 'min(680px, 100vw)' }}
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="Holding Movement Explanation"
      >
        <div className="drawer-head">
          <div style={{ flex: 1 }}>
            <div className="eyebrow" style={{ color: 'var(--accent)' }}>
              Holding Deep Dive · {explanation?.start} to {explanation?.end}
            </div>
            <h2 style={{ fontSize: 17, marginTop: 4 }}>
              {explanation?.instrument_name || 'Loading holding explanation…'}
            </h2>
            <div className="muted" style={{ fontSize: 12, marginTop: 3 }}>
              {explanation?.instrument_id} · {explanation?.asset_class} · {explanation?.sector} (
              {explanation?.region})
            </div>
          </div>
          <button className="btn quiet" onClick={onClose} aria-label="Close drawer">
            ✕
          </button>
        </div>

        <div className="drawer-body">
          {loading || !explanation ? (
            <div className="loading">Retrieving event evidence and transmission path…</div>
          ) : (
            <div className="stack" style={{ gap: 18 }}>
              {/* Section 1: What Changed Deterministically */}
              <div className="card">
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13 }}>1. What Changed (Deterministic Attribution)</h3>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))',
                      gap: 12,
                      marginBottom: 12,
                    }}
                  >
                    <div className="stat">
                      <span
                        className={`v ${
                          explanation.what_changed.value_change_usd >= 0 ? 'pos' : 'neg'
                        }`}
                        style={{ fontSize: 19 }}
                      >
                        {signedUsd(explanation.what_changed.value_change_usd)}
                      </span>
                      <span className="k">Value Delta (USD)</span>
                    </div>

                    <div className="stat">
                      <span className="v" style={{ fontSize: 19 }}>
                        {explanation.what_changed.price_return_pct !== null
                          ? signedPct(explanation.what_changed.price_return_pct)
                          : '—'}
                      </span>
                      <span className="k">Price Return</span>
                    </div>

                    <div className="stat">
                      <span className="v" style={{ fontSize: 19 }}>
                        {explanation.what_changed.weight_change_pct >= 0 ? '+' : '−'}
                        {Math.abs(explanation.what_changed.weight_change_pct).toFixed(2)} pp
                      </span>
                      <span className="k">Weight Delta</span>
                    </div>
                  </div>

                  <table className="kv">
                    <tbody>
                      <tr>
                        <td>Market Value</td>
                        <td style={{ textAlign: 'right' }}>
                          {usd(explanation.what_changed.start_value_usd)} →{' '}
                          <strong>{usd(explanation.what_changed.end_value_usd)}</strong>
                        </td>
                      </tr>
                      <tr>
                        <td>Price Move</td>
                        <td style={{ textAlign: 'right' }}>
                          {explanation.what_changed.start_price !== null &&
                          explanation.what_changed.end_price !== null
                            ? `${explanation.what_changed.start_price} → ${explanation.what_changed.end_price} ${explanation.what_changed.currency}`
                            : 'Unchanged / Not priced'}
                        </td>
                      </tr>
                      <tr>
                        <td>Quantity Held</td>
                        <td style={{ textAlign: 'right' }}>
                          {explanation.what_changed.quantity_change === 0
                            ? `Static (${explanation.what_changed.end_quantity.toLocaleString()} units)`
                            : `${explanation.what_changed.start_quantity.toLocaleString()} → ${explanation.what_changed.end_quantity.toLocaleString()} (${
                                explanation.what_changed.quantity_change > 0 ? '+' : ''
                              }${explanation.what_changed.quantity_change.toLocaleString()} traded)`}
                        </td>
                      </tr>
                      <tr>
                        <td>Portfolio Weight</td>
                        <td style={{ textAlign: 'right' }}>
                          {pct(explanation.what_changed.start_weight_pct)} →{' '}
                          <strong>{pct(explanation.what_changed.end_weight_pct)}</strong>
                        </td>
                      </tr>
                    </tbody>
                  </table>

                  {explanation.what_changed.valuation_lag && (
                    <div
                      className="banner"
                      style={{ marginTop: 12, marginBottom: 0, fontSize: 12 }}
                    >
                      ⏳ <strong>Valuation Lag:</strong> This is an illiquid / private markets
                      holding. The valuation reflects lagged reporting rather than real-time price
                      discovery.
                    </div>
                  )}
                </div>
              </div>

              {/* Section 2: Authoritative Event Evidence */}
              <div className="card">
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13 }}>
                    2. Authoritative Event Evidence (<code>event_log.csv</code>)
                  </h3>
                  <span className="sub">
                    {explanation.event_evidence.length} linked event
                    {explanation.event_evidence.length === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  {explanation.event_evidence.length === 0 ? (
                    <div className="muted" style={{ fontSize: 12.5 }}>
                      No direct macro or geopolitical event matched this sector and region during the
                      period. The move reflects standard market fluctuation or single-stock dynamics.
                    </div>
                  ) : (
                    explanation.event_evidence.map((ev) => (
                      <div
                        key={ev.event_id}
                        style={{
                          padding: '10px 12px',
                          border: '1px solid var(--rule)',
                          borderRadius: 'var(--radius)',
                          marginBottom: 10,
                          background: 'var(--surface-sunk)',
                        }}
                      >
                        <div
                          style={{
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'baseline',
                            marginBottom: 4,
                          }}
                        >
                          <span
                            style={{
                              fontFamily: 'var(--mono)',
                              fontSize: 11,
                              color: 'var(--accent)',
                              fontWeight: 600,
                            }}
                          >
                            [{ev.event_id}] · {ev.event_date}
                          </span>
                          <span
                            className={`pill ${
                              ev.severity === 'high' || ev.severity === 'critical'
                                ? 'critical'
                                : 'accent'
                            }`}
                            style={{ fontSize: 10, padding: '1px 5px' }}
                          >
                            {ev.severity.toUpperCase()}
                          </span>
                        </div>
                        <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 4 }}>
                          {ev.description}
                        </div>
                        <div className="muted" style={{ fontSize: 11.5, marginBottom: 4 }}>
                          <strong>Primary Transmission:</strong> {ev.primary_transmission}
                        </div>
                        <div
                          style={{
                            fontSize: 11.5,
                            color: 'var(--ink-soft)',
                            borderTop: '1px dashed var(--rule-strong)',
                            paddingTop: 4,
                            marginTop: 4,
                          }}
                        >
                          💡 <em>Relevance: {ev.rationale}</em>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Section 3: Why It Matters to This Client */}
              <div className="card">
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13 }}>3. Why It Matters to This Client</h3>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  <ul className="brieflist">
                    {explanation.why_it_matters.map((point, index) => (
                      <li key={index} style={{ fontSize: 12.5 }}>
                        {point}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Section 4: Transmission Mechanisms */}
              <div className="card">
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13 }}>4. Transmission Mechanism & Causal Chain</h3>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  <ol style={{ margin: 0, paddingLeft: 18 }}>
                    {explanation.transmission_mechanisms.map((mech, index) => (
                      <li
                        key={index}
                        style={{
                          fontSize: 12.5,
                          marginBottom: 6,
                          color: 'var(--ink-soft)',
                        }}
                      >
                        {mech}
                      </li>
                    ))}
                  </ol>
                </div>
              </div>

              {/* Section 5: Uncertainties & Data Caveats */}
              {explanation.uncertainties.length > 0 && (
                <div className="card" style={{ borderLeft: '3px solid var(--high)' }}>
                  <div className="card-head" style={{ padding: '10px 14px' }}>
                    <h3 style={{ fontSize: 13, color: 'var(--high)' }}>
                      5. Model Assumptions & Data Caveats
                    </h3>
                  </div>
                  <div className="card-body" style={{ padding: '12px 14px' }}>
                    <ul className="brieflist">
                      {explanation.uncertainties.map((u, index) => (
                        <li key={index} style={{ fontSize: 12, color: 'var(--ink-soft)' }}>
                          {u}
                        </li>
                      ))}
                    </ul>
                  </div>
                </div>
              )}

              {/* Action Callout */}
              <div
                style={{
                  padding: '14px 16px',
                  background: 'var(--accent-wash)',
                  border: '1px solid #cfdeeb',
                  borderRadius: 'var(--radius)',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 14,
                }}
              >
                <div>
                  <strong style={{ fontSize: 13, color: 'var(--accent)' }}>
                    Translate into Client Language
                  </strong>
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    Convert these technical findings into 3 empathetic talking points for Priscilla's
                    conversation.
                  </div>
                </div>
                <button
                  className="btn primary"
                  style={{ whiteSpace: 'nowrap' }}
                  onClick={() => onPrepareAttribution(explanation)}
                >
                  ✨ Prepare Client Attribution
                </button>
              </div>
            </div>
          )}
        </div>
      </aside>
    </div>
  )
}
