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
            <div className="stack" style={{ gap: 16 }}>
              {/* Section 1: Portfolio Impact */}
              <div className="card" style={{ borderLeft: '4px solid var(--accent)' }}>
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13, color: 'var(--accent)' }}>
                    1. Portfolio Impact ({explanation.start} → {explanation.end})
                  </h3>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  <div style={{ display: 'flex', alignItems: 'baseline', gap: 10, marginBottom: 8 }}>
                    <span style={{ fontSize: 15, fontWeight: 700, color: 'var(--ink)' }}>
                      {explanation.portfolio_impact?.contribution_text ||
                        `${signedUsd(explanation.what_changed.value_change_usd)} contribution`}
                    </span>
                  </div>
                  {explanation.portfolio_impact && (
                    <div className="meta" style={{ fontSize: 12, color: 'var(--ink-soft)' }}>
                      Overall portfolio shifted from {usd(explanation.portfolio_impact.portfolio_start_usd)} to{' '}
                      {usd(explanation.portfolio_impact.portfolio_end_usd)} ({signedUsd(explanation.portfolio_impact.portfolio_change_usd)}, {signedPct(explanation.portfolio_impact.portfolio_change_pct)}).
                    </div>
                  )}
                </div>
              </div>

              {/* Section 2: What Changed in the Holding */}
              <div className="card">
                <div
                  className="card-head"
                  style={{
                    padding: '10px 14px',
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                  }}
                >
                  <h3 style={{ fontSize: 13 }}>2. What Changed in the Holding</h3>
                  <span
                    className="pill accent"
                    style={{ fontSize: 10, textTransform: 'uppercase' }}
                  >
                    {explanation.movement_type || explanation.what_changed.movement_type || 'price-led'}
                  </span>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  <div
                    style={{
                      display: 'grid',
                      gridTemplateColumns: 'repeat(auto-fit, minmax(130px, 1fr))',
                      gap: 12,
                      marginBottom: 12,
                    }}
                  >
                    <div className="stat">
                      <span
                        className={`v ${
                          explanation.what_changed.value_change_usd >= 0 ? 'pos' : 'neg'
                        }`}
                        style={{ fontSize: 18 }}
                      >
                        {signedUsd(explanation.what_changed.value_change_usd)}
                      </span>
                      <span className="k">Holding Value Delta</span>
                    </div>

                    <div className="stat">
                      <span className="v" style={{ fontSize: 18 }}>
                        {explanation.what_changed.price_return_pct !== null
                          ? signedPct(explanation.what_changed.price_return_pct)
                          : '—'}
                      </span>
                      <span className="k">Price Return</span>
                    </div>

                    <div className="stat">
                      <span className="v" style={{ fontSize: 18 }}>
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
                      holding. The valuation reflects lagged reporting rather than real-time price discovery.
                    </div>
                  )}
                </div>
              </div>

              {/* Section 3: Market/Geopolitical Evidence */}
              <div className="card">
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13 }}>
                    3. Market & Geopolitical Evidence (<code>event_log.csv</code>)
                  </h3>
                  <span className="sub">
                    {explanation.event_evidence.length} linked event
                    {explanation.event_evidence.length === 1 ? '' : 's'}
                  </span>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  {explanation.event_evidence.length === 0 ? (
                    <div
                      style={{
                        padding: '10px 12px',
                        background: 'var(--surface-sunk)',
                        borderRadius: 'var(--radius)',
                        border: '1px dashed var(--rule)',
                        fontSize: 12.5,
                        color: 'var(--ink-soft)',
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 4 }}>
                        <span className="pill" style={{ background: 'var(--surface)', fontSize: 10 }}>
                          No verified linkage
                        </span>
                      </div>
                      No direct macro or geopolitical shock in <code>event_log.csv</code> matches this sector and region during this window. Movement reflects general asset-class momentum or security-specific dynamics.
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
                            className="pill accent"
                            style={{ fontSize: 10, padding: '1px 6px' }}
                          >
                            {ev.confidence || (ev.severity === 'critical' ? 'Direct evidence' : 'Qualified market context')}
                          </span>
                        </div>
                        <div style={{ fontSize: 12.5, fontWeight: 600, marginBottom: 4 }}>
                          {ev.description}
                        </div>
                        <div className="muted" style={{ fontSize: 11.5, marginBottom: 4 }}>
                          <strong>Transmission:</strong> {ev.primary_transmission}
                        </div>
                        {ev.rationale && (
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
                        )}
                      </div>
                    ))
                  )}
                </div>
              </div>

              {/* Section 4: Causal Explanation & Transmission */}
              <div className="card">
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13 }}>4. Causal Explanation & Transmission Path</h3>
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

              {/* Section 5: Why It Matters to This Client */}
              <div className="card">
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13 }}>5. Why It Matters to This Client</h3>
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

              {/* Section 6: Data Limitations (What Data Can & Cannot Prove) */}
              <div className="card" style={{ borderLeft: '3px solid var(--high)' }}>
                <div className="card-head" style={{ padding: '10px 14px' }}>
                  <h3 style={{ fontSize: 13, color: 'var(--high)' }}>
                    6. Data Boundaries & Limitations
                  </h3>
                </div>
                <div className="card-body" style={{ padding: '12px 14px' }}>
                  <ul className="brieflist">
                    {(explanation.limitations || [
                      'Data reflects point-in-time snapshot records; intraday order execution prices and market peaks/troughs are not observed.',
                      'The authoritative event_log.csv records external macroeconomic and geopolitical events; company-specific micro announcements may not have separate log entries.',
                    ]).map((limit, index) => (
                      <li key={index} style={{ fontSize: 12, color: 'var(--ink-soft)' }}>
                        {limit}
                      </li>
                    ))}
                    {explanation.uncertainties.map((u, index) => (
                      <li key={`u-${index}`} style={{ fontSize: 12, color: 'var(--ink-soft)' }}>
                        ⚠️ {u}
                      </li>
                    ))}
                  </ul>
                </div>
              </div>

              {/* Section 7: Neutral Conclusion */}
              <div
                style={{
                  padding: '12px 16px',
                  background: 'var(--surface-sunk)',
                  borderRadius: 'var(--radius)',
                  border: '1px solid var(--rule-strong)',
                }}
              >
                <div className="eyebrow" style={{ fontSize: 10.5, color: 'var(--muted)', marginBottom: 4 }}>
                  7. Conclusion (Single-Sentence Neutral Summary)
                </div>
                <div style={{ fontSize: 13, fontWeight: 600, color: 'var(--ink)', lineHeight: 1.45 }}>
                  {explanation.conclusion ||
                    `${explanation.instrument_name} moved by ${signedUsd(explanation.what_changed.value_change_usd)}, shifting weight from ${pct(explanation.what_changed.start_weight_pct)} to ${pct(explanation.what_changed.end_weight_pct)}.`}
                </div>
              </div>

              {/* Section 8: Prepare Client Attribution (Placed directly below conclusion) */}
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
                    Prepare Client Attribution
                  </strong>
                  <div className="muted" style={{ fontSize: 11.5 }}>
                    Generate 3 plain-English, empathetic talking points for Priscilla's client discussion.
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
